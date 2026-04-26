/**
 * UCO-Sensor VS Code Extension — API Client  (M4.2)
 * ===================================================
 * Typed HTTP client for the UCO-Sensor REST API.
 * Uses the browser-compatible Fetch API available in VS Code 1.85+ (Node 18+).
 *
 * All methods return typed promises and throw on HTTP errors.
 */

// ── Domain types ──────────────────────────────────────────────────────────────

export interface SASTFinding {
    rule_id:      string;
    severity:     "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO";
    cwe_id:       string;
    owasp:        string;
    title:        string;
    description:  string;
    line:         number;   // 1-based
    col:          number;   // 0-based (convert to 1-based for SARIF/VS Code)
    code_snippet: string;
    remediation:  string;
    debt_minutes: number;
}

export interface SASTResult {
    findings:           SASTFinding[];
    total_debt_minutes: number;
    security_rating:    "A" | "B" | "C" | "D" | "E";
    parse_error:        boolean;
}

export interface FunctionProfile {
    name:                  string;
    lineno:                number;   // 1-based
    cyclomatic_complexity: number;
    cognitive_complexity:  number;
    loc:                   number;
    halstead_volume:       number;
    risk_level:            "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
}

export interface MetricVector {
    module_id:              string;
    commit_hash:            string;
    timestamp:              number;
    language:               string;
    lines_of_code:          number;
    hamiltonian:            number;
    cyclomatic_complexity:  number;
    infinite_loop_risk:     number;
    dsm_density:            number;
    dsm_cyclic_ratio:       number;
    dependency_instability: number;
    syntactic_dead_code:    number;
    duplicate_block_count:  number;
    halstead_bugs:          number;
    status:                 "STABLE" | "WARNING" | "CRITICAL";
    // M1 advanced (Python-only, mode=full)
    cognitive_complexity?:  number;
    cognitive_fn_max?:      number;
    sqale_debt_minutes?:    number;
    sqale_ratio?:           number;
    sqale_rating?:          "A" | "B" | "C" | "D" | "E";
    clone_count?:           number;
    ratings?:               Record<string, string>;
    function_profiles?:     FunctionProfile[];
}

export interface AnalyzeResult {
    sast?:           SASTResult;
    metric_vector:   MetricVector;
    classification?: {
        primary_error:     string;
        severity:          string;
        confidence:        number;
        dominant_band:     string;
        plain_english:     string;
        spectral_evidence: any;
    };
    history_size:    number;
    apex_event_sent: boolean;
}

export interface AnalyzeRequest {
    code:             string;
    module_id:        string;
    commit_hash:      string;
    file_extension?:  string;
    timestamp?:       number;
}

export interface ScanRepoRequest {
    path:           string;
    commit_hash?:   string;
    max_files?:     number;
    include_tests?: boolean;
    persist?:       boolean;
    top_n?:         number;
}

export interface HealthResponse {
    status:          string;
    version:         string;
    timestamp:       number;
    modules_tracked: number;
    auth_enabled:    boolean;
    languages:       string[];
}

export interface DashboardResponse {
    modules:         ModuleSummary[];
    total_modules:   number;
    status_counts:   { critical: number; warning: number; stable: number };
    trend_counts:    { degrading: number; improving: number; stable: number };
    debt_budget:     DebtBudget;
    generated_at:    number;
}

export interface ModuleSummary {
    module_id:             string;
    status:                string;
    hamiltonian:           number;
    cyclomatic_complexity: number;
    cognitive_complexity?: number;
    sqale_rating?:         string;
    sqale_debt_minutes:    number;
    ratings?:              Record<string, string>;
    trend_direction:       string;
    trend_slope_pct:       number;
    snapshots_count:       number;
}

export interface DebtBudget {
    total_debt_minutes:   number;
    budget_minutes:       number;
    over_budget:          boolean;
    days_until_exhausted: number | null;
}

export interface GateResult {
    passed:      boolean;
    gate_score:  number;
    grade:       string;
    violations:  any[];
    metric_vector: Record<string, any>;
    policy_name: string;
}

// ── UCO API Client ────────────────────────────────────────────────────────────

export class UCOClient {
    private baseUrl: string;
    private apiKey:  string;

    /**
     * @param baseUrl  API server URL (e.g. "http://localhost:8080"). No trailing slash.
     * @param apiKey   Optional X-UCO-API-Key header value.
     */
    constructor(baseUrl: string = "http://localhost:8080", apiKey: string = "") {
        this.baseUrl = baseUrl.replace(/\/+$/, "");
        this.apiKey  = apiKey;
    }

    // ── Config update (mutable for configureServer command) ───────────────────

    setConfig(serverUrl: string, apiKey: string): void {
        this.baseUrl = serverUrl.replace(/\/+$/, "");
        this.apiKey  = apiKey;
    }

    getBaseUrl(): string { return this.baseUrl; }

    // ── HTTP helpers ──────────────────────────────────────────────────────────

    private buildHeaders(): Record<string, string> {
        const h: Record<string, string> = { "Content-Type": "application/json" };
        if (this.apiKey) { h["X-UCO-API-Key"] = this.apiKey; }
        return h;
    }

    private async request<T>(
        method:  "GET" | "POST" | "DELETE",
        path:    string,
        body?:   unknown,
        timeoutMs: number = 10_000,
    ): Promise<T> {
        const url = `${this.baseUrl}${path}`;
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), timeoutMs);

        try {
            const opts: RequestInit = {
                method,
                headers: this.buildHeaders(),
                signal:  controller.signal,
            };
            if (body !== undefined) {
                opts.body = JSON.stringify(body);
            }

            const resp = await fetch(url, opts);
            if (!resp.ok) {
                const text = await resp.text().catch(() => resp.statusText);
                throw new Error(`UCO-Sensor HTTP ${resp.status}: ${text}`);
            }

            const json = (await resp.json()) as { status: string; data: T };
            // Unwrap envelope {status, data} or return root if no envelope
            return (json as any).data ?? (json as unknown as T);

        } finally {
            clearTimeout(timer);
        }
    }

    // ── Public API ────────────────────────────────────────────────────────────

    /** POST /analyze — analyse source code and persist snapshot. */
    async analyze(req: AnalyzeRequest): Promise<AnalyzeResult> {
        return this.request<AnalyzeResult>("POST", "/analyze", req);
    }

    /** GET /health — liveness probe. */
    async health(): Promise<HealthResponse> {
        return this.request<HealthResponse>("GET", "/health");
    }

    /** Ping — returns true when server is reachable and healthy. */
    async ping(): Promise<boolean> {
        try {
            const h = await this.health();
            return h.status === "healthy";
        } catch {
            return false;
        }
    }

    /** GET /dashboard — project-wide quality dashboard. */
    async getDashboard(): Promise<DashboardResponse> {
        return this.request<DashboardResponse>("GET", "/dashboard");
    }

    /** GET /history?module=&window= — snapshot history for a module. */
    async getHistory(moduleId: string, window = 20): Promise<any> {
        const params = new URLSearchParams({
            module: moduleId,
            window: String(window),
        });
        return this.request<any>("GET", `/history?${params}`);
    }

    /** GET /trend?module=&metric=&window= */
    async getTrend(moduleId: string, metric = "hamiltonian", window = 10): Promise<any> {
        const params = new URLSearchParams({
            module: moduleId,
            metric,
            window: String(window),
        });
        return this.request<any>("GET", `/trend?${params}`);
    }

    /** POST /sast — standalone security scan. */
    async sast(code: string, fileExt = ".py"): Promise<SASTResult> {
        return this.request<SASTResult>("POST", "/sast", {
            code,
            file_extension: fileExt,
        });
    }

    /** POST /gate — quality gate for CI integration. */
    async gate(code: string, moduleId: string, fileExt = ".py"): Promise<GateResult> {
        return this.request<GateResult>("POST", "/gate", {
            code,
            module_id:      moduleId,
            file_extension: fileExt,
        });
    }

    /** POST /scan-repo — scan an entire local directory. */
    async scanRepo(req: ScanRepoRequest): Promise<any> {
        return this.request<any>("POST", "/scan-repo", req);
    }

    /** GET /sast/rules — catalogue of all SAST rules. */
    async getSastRules(): Promise<any> {
        return this.request<any>("GET", "/sast/rules");
    }

    /** GET /modules — list all tracked modules. */
    async getModules(): Promise<any> {
        return this.request<any>("GET", "/modules");
    }

    /** GET /baseline?module= */
    async getBaseline(moduleId: string): Promise<any> {
        const params = new URLSearchParams({ module: moduleId });
        return this.request<any>("GET", `/baseline?${params}`);
    }
}
