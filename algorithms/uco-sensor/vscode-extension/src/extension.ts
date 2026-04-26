/**
 * UCO-Sensor VS Code Extension — Main Entry Point  (M4.2)
 * =========================================================
 * Provides:
 *   • Status bar item: UCO score + status for the active file
 *   • Inline SAST decorations: coloured line highlights with hover messages
 *   • VS Code Diagnostics integration (Problems panel)
 *   • Commands: analyze, showDashboard, analyzeWorkspace, configureServer
 *   • Auto-analyze on save (configurable)
 *   • WebView dashboard panel (fetches /dashboard from UCO-Sensor API)
 *
 * Design:
 *   • Zero hard dependencies beyond the VS Code API
 *   • API communication via UCOClient (src/api.ts)
 *   • Graceful degradation when server is offline (status bar shows "offline")
 */

import * as vscode from "vscode";
import { UCOClient, AnalyzeResult, SASTFinding, FunctionProfile } from "./api";

// ── Decoration types (singleton per extension instance) ──────────────────────

const DEC_CRITICAL = vscode.window.createTextEditorDecorationType({
    backgroundColor: "rgba(248,113,113,0.14)",
    border:          "1px solid rgba(248,113,113,0.55)",
    borderRadius:    "2px",
    overviewRulerColor: "#f87171",
    overviewRulerLane:  vscode.OverviewRulerLane.Right,
    light: { backgroundColor: "rgba(220,38,38,0.07)" },
    dark:  { backgroundColor: "rgba(248,113,113,0.14)" },
});

const DEC_HIGH = vscode.window.createTextEditorDecorationType({
    backgroundColor: "rgba(251,191,36,0.12)",
    border:          "1px solid rgba(251,191,36,0.45)",
    borderRadius:    "2px",
    overviewRulerColor: "#fbbf24",
    overviewRulerLane:  vscode.OverviewRulerLane.Right,
});

const DEC_MEDIUM = vscode.window.createTextEditorDecorationType({
    border:       "1px dashed rgba(148,163,184,0.40)",
    borderRadius: "2px",
    overviewRulerColor: "#94a3b8",
    overviewRulerLane:  vscode.OverviewRulerLane.Left,
});

// ── Extension-level state ─────────────────────────────────────────────────────

let statusBarItem:       vscode.StatusBarItem;
let diagnosticCollection: vscode.DiagnosticCollection;
let client:              UCOClient;
let dashboardPanel:      vscode.WebviewPanel | undefined;

// Severity rank for filtering
const SEV_RANK: Record<string, number> = {
    CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0,
};

// ── Activate ──────────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
    const cfg = vscode.workspace.getConfiguration("ucoSensor");

    // API client
    client = new UCOClient(
        cfg.get<string>("serverUrl", "http://localhost:8080"),
        cfg.get<string>("apiKey",    ""),
    );

    // Status bar (right side, priority 100)
    statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Right, 100,
    );
    statusBarItem.command = "uco-sensor.analyze";
    statusBarItem.text    = "$(pulse) UCO";
    statusBarItem.tooltip = "UCO-Sensor: Click to analyse current file";
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Diagnostics collection
    diagnosticCollection = vscode.languages.createDiagnosticCollection("uco-sensor");
    context.subscriptions.push(diagnosticCollection);

    // ── Register commands ─────────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.commands.registerCommand("uco-sensor.analyze",          analyzeCurrentFile),
        vscode.commands.registerCommand("uco-sensor.showDashboard",    showDashboard),
        vscode.commands.registerCommand("uco-sensor.analyzeWorkspace", analyzeWorkspace),
        vscode.commands.registerCommand("uco-sensor.configureServer",  configureServer),
    );

    // ── Auto-analyze on save ──────────────────────────────────────────────────
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(async (doc) => {
            const c = vscode.workspace.getConfiguration("ucoSensor");
            if (c.get<boolean>("analyzeOnSave", true) && isSupportedLang(doc.languageId)) {
                await analyzeDocument(doc);
            }
        }),
        vscode.window.onDidChangeActiveTextEditor((editor) => {
            if (!editor || !isSupportedLang(editor.document.languageId)) {
                updateStatusBar(null);
            }
        }),
        vscode.workspace.onDidChangeConfiguration((e) => {
            if (e.affectsConfiguration("ucoSensor")) {
                const c = vscode.workspace.getConfiguration("ucoSensor");
                client.setConfig(
                    c.get<string>("serverUrl", "http://localhost:8080"),
                    c.get<string>("apiKey", ""),
                );
            }
        }),
    );

    // Analyse active document at startup
    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor && isSupportedLang(activeEditor.document.languageId)) {
        analyzeDocument(activeEditor.document).catch(() => {/* offline — silent */});
    }
}

export function deactivate(): void {
    diagnosticCollection?.dispose();
    statusBarItem?.dispose();
    dashboardPanel?.dispose();
    DEC_CRITICAL.dispose();
    DEC_HIGH.dispose();
    DEC_MEDIUM.dispose();
}

// ── Language helpers ──────────────────────────────────────────────────────────

function isSupportedLang(langId: string): boolean {
    return ["python", "javascript", "typescript", "java", "go"].includes(langId);
}

function langToExt(langId: string): string {
    const map: Record<string, string> = {
        python: ".py", javascript: ".js", typescript: ".ts", java: ".java", go: ".go",
    };
    return map[langId] ?? ".py";
}

// ── Status bar ────────────────────────────────────────────────────────────────

function updateStatusBar(result: AnalyzeResult | null): void {
    if (!result) {
        statusBarItem.text  = "$(pulse) UCO";
        statusBarItem.color = undefined;
        return;
    }
    const mv     = result.metric_vector;
    const status = mv.status ?? "STABLE";
    const fmt    = vscode.workspace.getConfiguration("ucoSensor").get<string>("statusBarFormat", "both");

    const icon  = status === "CRITICAL" ? "$(error)" : status === "WARNING" ? "$(warning)" : "$(check)";
    const color = status === "CRITICAL" ? "#f87171"  : status === "WARNING"  ? "#fbbf24"   : "#4ade80";

    let text = `${icon} UCO`;
    if (fmt === "score" || fmt === "both") {
        text += ` H:${(mv.hamiltonian ?? 0).toFixed(1)}`;
    }
    if (fmt === "status" || fmt === "both") {
        text += ` ${status}`;
    }

    statusBarItem.text    = text;
    statusBarItem.color   = color;
    statusBarItem.tooltip = (
        `UCO-Sensor\n` +
        `H=${(mv.hamiltonian ?? 0).toFixed(2)}  CC=${mv.cyclomatic_complexity}  ` +
        `Status=${status}\n` +
        `SQALE=${mv.sqale_rating ?? "—"}  Debt=${mv.sqale_debt_minutes ?? "—"} min`
    );
}

// ── Analyse current file ──────────────────────────────────────────────────────

async function analyzeCurrentFile(): Promise<void> {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
        vscode.window.showWarningMessage("UCO-Sensor: No active editor");
        return;
    }
    if (!isSupportedLang(editor.document.languageId)) {
        vscode.window.showInformationMessage(
            `UCO-Sensor: Language "${editor.document.languageId}" is not supported.`
        );
        return;
    }
    await analyzeDocument(editor.document);
}

async function analyzeDocument(doc: vscode.TextDocument): Promise<void> {
    statusBarItem.text  = "$(sync~spin) UCO…";
    statusBarItem.color = undefined;

    try {
        const result = await client.analyze({
            code:           doc.getText(),
            module_id:      doc.uri.fsPath,
            commit_hash:    `vsc_${Date.now()}`,
            file_extension: langToExt(doc.languageId),
        });

        updateStatusBar(result);
        applyDecorations(doc, result);
        updateDiagnostics(doc, result);

    } catch (err: any) {
        statusBarItem.text    = "$(circle-slash) UCO offline";
        statusBarItem.color   = "#64748b";
        statusBarItem.tooltip = `UCO-Sensor: Server unreachable — ${err.message}`;
    }
}

// ── Inline decorations ────────────────────────────────────────────────────────

function applyDecorations(doc: vscode.TextDocument, result: AnalyzeResult): void {
    const editor = vscode.window.visibleTextEditors.find((e) => e.document === doc);
    if (!editor) { return; }

    const cfg    = vscode.workspace.getConfiguration("ucoSensor");
    if (!cfg.get<boolean>("showInlineDecorations", true)) {
        editor.setDecorations(DEC_CRITICAL, []);
        editor.setDecorations(DEC_HIGH,     []);
        editor.setDecorations(DEC_MEDIUM,   []);
        return;
    }

    const minSev  = cfg.get<string>("minSeverityToDecorate", "MEDIUM");
    const minRank = SEV_RANK[minSev] ?? 2;

    const critOpts: vscode.DecorationOptions[] = [];
    const highOpts: vscode.DecorationOptions[] = [];
    const medOpts:  vscode.DecorationOptions[] = [];

    const findings: SASTFinding[] = result.sast?.findings ?? [];
    for (const f of findings) {
        if ((SEV_RANK[f.severity] ?? 0) < minRank) { continue; }

        const lineIdx = Math.max(0, (f.line ?? 1) - 1);
        const safeLine = Math.min(lineIdx, doc.lineCount - 1);
        const colIdx  = Math.max(0, f.col ?? 0);
        const endChar = doc.lineAt(safeLine).range.end.character;

        const range = new vscode.Range(safeLine, colIdx, safeLine, endChar);
        const hover = new vscode.MarkdownString(
            `**${f.rule_id}** — ${f.title}\n\n` +
            `${f.description}\n\n` +
            `*${f.cwe_id} / ${f.owasp}* — severity: **${f.severity}**\n\n` +
            `💡 **Remediation:** ${f.remediation}\n\n` +
            `Debt: **${f.debt_minutes} min**`,
        );
        hover.isTrusted = true;

        const opt: vscode.DecorationOptions = { range, hoverMessage: hover };
        if (f.severity === "CRITICAL") {
            critOpts.push(opt);
        } else if (f.severity === "HIGH") {
            highOpts.push(opt);
        } else {
            medOpts.push(opt);
        }
    }

    editor.setDecorations(DEC_CRITICAL, critOpts);
    editor.setDecorations(DEC_HIGH,     highOpts);
    editor.setDecorations(DEC_MEDIUM,   medOpts);
}

// ── Diagnostics (Problems panel) ──────────────────────────────────────────────

function updateDiagnostics(doc: vscode.TextDocument, result: AnalyzeResult): void {
    const diagnostics: vscode.Diagnostic[] = [];
    const maxLine = doc.lineCount - 1;

    // SAST findings → Diagnostics
    const findings: SASTFinding[] = result.sast?.findings ?? [];
    for (const f of findings) {
        const lineIdx = Math.max(0, Math.min((f.line ?? 1) - 1, maxLine));
        const colIdx  = Math.max(0, f.col ?? 0);
        const endChar = doc.lineAt(lineIdx).range.end.character;
        const range   = new vscode.Range(lineIdx, colIdx, lineIdx, endChar);

        const sev =
            f.severity === "CRITICAL" || f.severity === "HIGH"
                ? vscode.DiagnosticSeverity.Error
                : f.severity === "MEDIUM"
                    ? vscode.DiagnosticSeverity.Warning
                    : vscode.DiagnosticSeverity.Information;

        const diag = new vscode.Diagnostic(
            range,
            `[${f.rule_id}] ${f.title}: ${f.description}`,
            sev,
        );
        diag.source = "UCO-Sensor SAST";
        diag.code   = { value: f.rule_id, target: vscode.Uri.parse("https://owasp.org") };
        diagnostics.push(diag);
    }

    // Function profiles → Diagnostics for HIGH/CRITICAL risk
    const profiles: FunctionProfile[] = result.metric_vector?.function_profiles ?? [];
    for (const fp of profiles) {
        if (fp.risk_level !== "CRITICAL" && fp.risk_level !== "HIGH") { continue; }
        const lineIdx = Math.max(0, Math.min((fp.lineno ?? 1) - 1, maxLine));
        const range   = new vscode.Range(lineIdx, 0, lineIdx, doc.lineAt(lineIdx).range.end.character);
        const diag    = new vscode.Diagnostic(
            range,
            `[UCO] Function '${fp.name}' — CC=${fp.cyclomatic_complexity} CogCC=${fp.cognitive_complexity} Risk=${fp.risk_level}`,
            vscode.DiagnosticSeverity.Warning,
        );
        diag.source = "UCO-Sensor Quality";
        diagnostics.push(diag);
    }

    diagnosticCollection.set(doc.uri, diagnostics);
}

// ── Analyse workspace ─────────────────────────────────────────────────────────

async function analyzeWorkspace(): Promise<void> {
    const folders = vscode.workspace.workspaceFolders;
    if (!folders?.length) {
        vscode.window.showWarningMessage("UCO-Sensor: No workspace folder is open.");
        return;
    }
    const rootPath = folders[0].uri.fsPath;

    await vscode.window.withProgress(
        {
            location:    vscode.ProgressLocation.Notification,
            title:       "UCO-Sensor: Scanning workspace…",
            cancellable: false,
        },
        async (progress) => {
            progress.report({ message: "Sending to UCO-Sensor API…" });
            try {
                const res = await client.scanRepo({
                    path:          rootPath,
                    max_files:     200,
                    include_tests: false,
                });
                const status = (res as any).status ?? "UNKNOWN";
                const score  = ((res as any).uco_score ?? 0) as number;
                const crit   = (res as any).critical_count ?? 0;
                const warn   = (res as any).warning_count  ?? 0;

                vscode.window.showInformationMessage(
                    `UCO-Sensor Workspace: ${status} | Score: ${score.toFixed(1)} | ` +
                    `Critical: ${crit}  Warning: ${warn}`,
                );
            } catch (err: any) {
                vscode.window.showErrorMessage(
                    `UCO-Sensor: Workspace scan failed — ${err.message}`
                );
            }
        },
    );
}

// ── Dashboard WebView ─────────────────────────────────────────────────────────

async function showDashboard(): Promise<void> {
    if (dashboardPanel) {
        dashboardPanel.reveal(vscode.ViewColumn.Beside);
        return;
    }

    dashboardPanel = vscode.window.createWebviewPanel(
        "ucoDashboard",
        "UCO-Sensor Dashboard",
        vscode.ViewColumn.Beside,
        {
            enableScripts:            true,
            retainContextWhenHidden:  true,
            localResourceRoots:       [],
        },
    );
    dashboardPanel.onDidDispose(() => { dashboardPanel = undefined; });

    dashboardPanel.webview.html = buildLoadingHTML();

    try {
        const data = await client.getDashboard();
        dashboardPanel.webview.html = buildDashboardHTML(data);
    } catch (err: any) {
        dashboardPanel.webview.html = buildOfflineHTML(err.message);
    }
}

function buildLoadingHTML(): string {
    return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>UCO-Sensor</title></head>
<body style="background:#0f1117;color:#94a3b8;font-family:system-ui;padding:32px;display:flex;align-items:center;gap:12px">
<span style="font-size:1.5rem">⏳</span>
<span>Connecting to UCO-Sensor server…</span>
</body></html>`;
}

function buildOfflineHTML(msg: string): string {
    return `<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>UCO-Sensor</title></head>
<body style="background:#0f1117;color:#e2e8f0;font-family:system-ui;padding:32px">
<h2 style="color:#f87171">⚠ UCO-Sensor server unreachable</h2>
<p style="color:#94a3b8;margin-top:12px">${msg}</p>
<hr style="border-color:#2d3352;margin:20px 0">
<p style="color:#64748b;font-size:.85rem">
  Start the server: <code style="color:#7dd3fc">python server.py --port 8080 --no-auth</code>
</p>
<p style="color:#64748b;font-size:.85rem;margin-top:8px">
  Configure URL: <strong>UCO-Sensor: Configure Server URL</strong> in the Command Palette.
</p>
</body></html>`;
}

function buildDashboardHTML(data: any): string {
    const modules = (data.modules ?? []) as any[];
    const counts  = data.status_counts ?? {};
    const budget  = data.debt_budget   ?? {};

    const moduleRows = modules.map((m: any) => {
        const statusColor =
            m.status === "CRITICAL" ? "#f87171" :
            m.status === "WARNING"  ? "#fbbf24" :
                                      "#4ade80";
        const ratingBg = ({ A:"#4ade80",B:"#86efac",C:"#fbbf24",D:"#f97316",E:"#ef4444" })[
            m.sqale_rating as string] ?? "#64748b";
        return `<tr style="border-bottom:1px solid #1a1f35">
          <td style="padding:8px;max-width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"
              title="${escHtml(m.module_id)}">${escHtml(m.module_id)}</td>
          <td style="padding:8px;color:${statusColor}">${m.status}</td>
          <td style="padding:8px">${(m.hamiltonian ?? 0).toFixed(2)}</td>
          <td style="padding:8px">${m.cyclomatic_complexity ?? 0}</td>
          <td style="padding:8px">
            ${m.sqale_rating
                ? `<span style="background:${ratingBg};color:#0f1117;padding:2px 6px;border-radius:4px;font-weight:700">${m.sqale_rating}</span>`
                : "—"}
          </td>
          <td style="padding:8px">${m.trend_direction ?? "—"}</td>
          <td style="padding:8px">${m.snapshots_count ?? 0}</td>
        </tr>`;
    }).join("");

    const debtPct = Math.min(100,
        (budget.total_debt_minutes ?? 0) / Math.max(budget.budget_minutes ?? 480, 1) * 100
    ).toFixed(1);
    const barColor = Number(debtPct) >= 100 ? "#f87171" : Number(debtPct) >= 75 ? "#fbbf24" : "#4ade80";

    return `<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8"><title>UCO-Sensor Dashboard</title>
<meta http-equiv="refresh" content="30">
</head>
<body style="background:#0f1117;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;padding:20px">

<h1 style="color:#3b82f6;margin-bottom:16px;font-size:1.3rem">
  UCO-Sensor Dashboard
  <span style="font-size:.7rem;background:#3b82f6;color:#fff;padding:2px 8px;border-radius:9999px;margin-left:8px;font-weight:700">v1.0.0</span>
</h1>

<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap">
  ${["CRITICAL","WARNING","STABLE"].map(s => {
    const col = s==="CRITICAL"?"#f87171":s==="WARNING"?"#fbbf24":"#4ade80";
    const key = s.toLowerCase() as "critical"|"warning"|"stable";
    return `<div style="background:#1e2130;border:1px solid #2d3352;border-radius:10px;padding:12px 20px;text-align:center;min-width:100px">
      <div style="font-size:2rem;font-weight:800;color:${col}">${counts[key] ?? 0}</div>
      <div style="font-size:.72rem;color:#64748b;text-transform:uppercase">${s}</div>
    </div>`;
  }).join("")}
</div>

<div style="background:#1e2130;border:1px solid #2d3352;border-radius:10px;padding:16px;margin-bottom:20px">
  <h2 style="font-size:.9rem;font-weight:600;color:#cbd5e1;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2d3352">
    Module Health
  </h2>
  <table style="width:100%;border-collapse:collapse;font-size:.8rem">
    <thead><tr style="border-bottom:1px solid #2d3352">
      <th style="text-align:left;padding:8px;color:#64748b">Module</th>
      <th style="padding:8px;color:#64748b">Status</th>
      <th style="padding:8px;color:#64748b">H</th>
      <th style="padding:8px;color:#64748b">CC</th>
      <th style="padding:8px;color:#64748b">SQALE</th>
      <th style="padding:8px;color:#64748b">Trend</th>
      <th style="padding:8px;color:#64748b">Snaps</th>
    </tr></thead>
    <tbody>${moduleRows || '<tr><td colspan="7" style="text-align:center;color:#4ade80;padding:16px">✅ No modules tracked yet</td></tr>'}</tbody>
  </table>
</div>

<div style="background:#1e2130;border:1px solid #2d3352;border-radius:10px;padding:16px">
  <h2 style="font-size:.9rem;font-weight:600;color:#cbd5e1;margin-bottom:10px">SQALE Debt Budget</h2>
  <div style="display:flex;justify-content:space-between;font-size:.8rem;margin-bottom:6px;flex-wrap:wrap;gap:6px">
    <span>Total: <strong>${budget.total_debt_minutes ?? 0} min</strong></span>
    <span>Budget: <strong>${budget.budget_minutes ?? 480} min</strong></span>
    <span>Used: <strong>${debtPct}%</strong></span>
  </div>
  <div style="height:8px;background:#1a1f35;border-radius:4px;overflow:hidden">
    <div style="height:100%;background:${barColor};width:${debtPct}%;border-radius:4px;transition:width .5s"></div>
  </div>
</div>

</body></html>`;
}

function escHtml(s: string): string {
    return String(s)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ── Configure server URL ──────────────────────────────────────────────────────

async function configureServer(): Promise<void> {
    const current = vscode.workspace.getConfiguration("ucoSensor").get<string>(
        "serverUrl", "http://localhost:8080",
    );
    const url = await vscode.window.showInputBox({
        prompt:      "UCO-Sensor API server URL",
        value:       current,
        placeHolder: "http://localhost:8080",
        validateInput: (v) =>
            v && (v.startsWith("http://") || v.startsWith("https://"))
                ? undefined
                : "URL must start with http:// or https://",
    });

    if (url) {
        await vscode.workspace.getConfiguration().update(
            "ucoSensor.serverUrl", url, vscode.ConfigurationTarget.Global,
        );
        const key = vscode.workspace.getConfiguration("ucoSensor").get<string>("apiKey", "");
        client.setConfig(url, key);
        const alive = await client.ping();
        if (alive) {
            vscode.window.showInformationMessage(`UCO-Sensor: Connected to ${url} ✅`);
        } else {
            vscode.window.showWarningMessage(
                `UCO-Sensor: Server configured (${url}) but not reachable — check it is running.`,
            );
        }
    }
}
