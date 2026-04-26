# UCO-Sensor — CHANGELOG

Todas as mudanças notáveis são documentadas aqui.  
Formato: [Semantic Versioning](https://semver.org/) | Convenção: [Keep a Changelog](https://keepachangelog.com/)

---

## [1.0.0] — 2026-04-26 — M4 WEB UI + SARIF + GITHUB ACTIONS + VS CODE

### Adicionado — M4.3 SARIF 2.1.0 Melhorado

- **`report/sarif.py`** — `SARIFBuilder` incremental: 22 regras (9 UCO + 13 SAST)
- Line/column reais em `physicalLocation.region`: `startLine` e `startColumn` (1-based)
- `add_sast_findings(uri, sast_result)` — mapeia `SASTFinding.line/col` para região SARIF
- `add_uco_findings_from_profiles(uri, fps)` — emite UCO001/UCO002 por função com CC/CogCC alto
- `add_uco_finding(...)` — finding UCO com `logicalLocations` (nome da função)
- CWE/OWASP tags em `rule.properties`; `fullDescription` e `help.markdown` por regra
- `/analyze-pr` refatorado para usar `SARIFBuilder` (elimina `startLine: 1` hardcoded)

### Adicionado — M4.4 GitHub Actions Native Action

- **`algorithms/uco-sensor/action.yml`** — composite action com 8 inputs + 7 outputs
- Inputs: `path`, `fail_on_critical`, `fail_on_gate_fail`, `gate_threshold`, `sarif_output`,
  `policy_file`, `max_files`, `include_tests`, `python_version`, `upload_sarif`
- Outputs: `uco_score`, `status`, `critical_count`, `warning_count`, `files_scanned`,
  `sarif_file`, `debt_minutes`
- **`ci/action_entrypoint.py`** — script standalone: RepoScanner + SARIFBuilder + SAST scan
- SARIF auto-upload via `github/codeql-action/upload-sarif@v3`
- GitHub Step Summary com tabela de métricas + emoji de status

### Adicionado — M4.1 Web Dashboard Temporal

- **`report/webui.py`** — `generate_dashboard_html()`: HTML standalone com Chart.js 4.x (CDN)
- 4 canvas: Hamiltonian temporal, CC temporal, Cognitive CC por módulo, SQALE debt por módulo
- Module health cards com status/trend icons, SQALE rating badges
- Top-issues table + SQALE debt budget progress bar
- Auto-refresh configável via `setInterval + fetch('/dashboard')`
- `GET /dashboard/ui` — endpoint no servidor stdlib servindo o dashboard completo
- Dados pré-embutidos como JSON (`INITIAL_DATA`) para renderização imediata

### Adicionado — M4.2 VS Code Extension

- **`vscode-extension/package.json`** — manifesto completo v1.0.0
  - Activation: Python, JS, TS, Java, Go
  - 4 commands: `analyze`, `showDashboard`, `analyzeWorkspace`, `configureServer`
  - 6 configurações: serverUrl, apiKey, analyzeOnSave, decorations, statusBarFormat, refresh
- **`vscode-extension/src/api.ts`** — `UCOClient` typed (fetch-based): 10 métodos API
- **`vscode-extension/src/extension.ts`** — extensão completa:
  - Status bar com H/status/SQALE rating
  - 3 decoration types: CRITICAL, HIGH, MEDIUM (coloured highlights + hover)
  - VS Code Diagnostics (Problems panel) com SAST + função profiles
  - WebView dashboard panel (HTML inline, sem servidor Node)
  - Auto-analyse on save; configureServer com ping test

### Modificado

- `api/server.py` — versão `1.0.0`; `/analyze-pr` usa `SARIFBuilder`; `GET /dashboard/ui`
- `pyproject.toml` — versão `1.0.0`; `webui = [fastapi, uvicorn]` optional dep; `ci*` package

### Testes

- `tests/test_marco_m4.py` — 30 testes TW01-TW30, **30/30 PASS** (0 falhas na primeira execução)
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) = **120/120 PASS**

---

## [0.9.0] — 2026-04-25 — M3 SAST SECURITY RULES

### Adicionado — M3 SAST Security Rules

- **`sast/` package** — Static Application Security Testing engine com 13 regras de segurança
- **SAST001** (CWE-89, CRITICAL) — SQL Injection via `execute()` com string formatada ou concatenada
- **SAST002** (CWE-78, HIGH) — OS Command Injection via `os.system()` / `os.popen()` com argumento variável
- **SAST003** (CWE-95, HIGH) — Unsafe `eval()` / `exec()` com argumento não-literal
- **SAST004** (CWE-502, HIGH) — Pickle deserialization via `pickle.load()` / `pickle.loads()`
- **SAST005** (CWE-502, MEDIUM) — YAML unsafe load sem `Loader` contendo "safe"
- **SAST006** (CWE-327, MEDIUM) — Algoritmo de hash fraco: MD5, SHA1
- **SAST007** (CWE-338, MEDIUM) — Randomness insegura via módulo `random`
- **SAST008** (CWE-798, HIGH) — Segredo hardcoded: `password`, `api_key`, `token`, etc.; exclui placeholders (`CHANGEME`, `YOUR_`, etc.)
- **SAST009** (CWE-321, CRITICAL) — Chave privada PEM no código-fonte
- **SAST010** (CWE-489, MEDIUM) — Flask/app `debug=True` em produção
- **SAST011** (CWE-22, HIGH) — Path Traversal via `open()` com caminho variável
- **SAST012** (CWE-617, LOW) — `assert` usado para verificação de segurança
- **SAST013** (CWE-78, HIGH) — `subprocess` com `shell=True` + argumento não-literal
- **`SASTFinding` / `SASTResult`** — dataclasses com `to_dict()`, debt_minutes, security_rating A-E
- **Security rating** — CRITICAL→E, ≥2 HIGH→D, 1 HIGH→C, ≥2 MEDIUM→C, 1 MEDIUM→B, clean→A
- **SAST debt** — CRITICAL=240 min, HIGH=120 min, MEDIUM=60 min, LOW=30 min, INFO=5 min

### API — Novos endpoints (v0.9.0)

- `POST /sast` — scan de código-fonte; retorna findings + rating + debt
- `GET /sast/rules` — catálogo das 13 regras SAST
- `POST /analyze` — enriquecido com campo `"sast"` no payload de resposta

### Testes

- `tests/test_marco_m3.py` — 30 testes TS01-TS30, **30/30 PASS**
- Regressão: M1 (30/30) + M2 (30/30) mantidos intactos

---

## [0.8.0] — 2026-04-25 — M2 GOVERNANCE ENGINE

### Adicionado — M2 Governance Engine

**M2.1 — Policy Engine (`governance/policy_engine.py`)**
- `PolicyRule`: id, field, operator, threshold, severity (ERROR/WARNING/INFO)
- Operadores: `lte`, `gte`, `lt`, `gt`, `eq`, `neq`, `in`, `not_in`, `rating_lte`, `rating_gte`
- `evaluate_policy(metrics_dict, policy)` → `PolicyResult(passed, gate_score, grade, violations)`
- `load_default_policy()` — 11 regras default cobrindo CC, Cognitive CC, ILR, SQALE, DI, clones

**M2.2 — Quality Gate**
- `POST /gate` — analisa código e avalia política em uma chamada
- `gate_score` = 100 − Σ penalidades (ERROR −20, WARNING −10, INFO −2)
- `grade` A–F; `passed` = gate_score ≥ pass_threshold (default 70)
- Em caso de falha publica evento `UCO_GATE_FAILURE` ao APEX (quando apex_enabled=1)
- `gate_score_to_grade()`, `mv_to_metrics_dict()`

**M2.3 — Trend Engine (`governance/trend_engine.py`)**
- `analyze_trend(history, metric, window)` → `TrendAnalysis`
- Classificação: IMPROVING | STABLE | DEGRADING | VOLATILE | INSUFFICIENT_DATA
- Linear regression slope + R² — VOLATILE só quando R² < 0.6 AND CV > 30%
- `forecast_next` via extrapolação da regressão linear
- `analyze_module_trends()` — multi-metric para um módulo
- `overall_trend()` — direção agregada em múltiplas métricas

**M2.4 — Debt Budget**
- `track_debt_budget(module_debts, budget_minutes)` → `DebtBudget`
- Campos: `total_debt_minutes`, `remaining_minutes`, `over_budget`, `velocity_min_per_day`
- `days_until_exhausted` — previsão baseada na velocidade de acúmulo de dívida

**M2.5 + M2.6 — Dashboard + Trend API**
- `GET /trend?module=<id>&metric=<field>&window=<n>` — trend per-módulo
- `GET /dashboard` — snapshot de todos os módulos + debt budget + contagens por status/trend

### Testes
- `tests/test_marco_m2.py` — TG01–TG30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M2 Governance (30) | ✅ 30/30 |
| M1 Advanced (30)   | ✅ 30/30 |
| Calibration (25)   | ✅ 24/25 (1 skip) |
| Marco 6 (14)       | ✅ 14/14 |
| Marco 7 (16)       | ✅ 16/16 |
| Marco 8 (10)       | ✅ 10/10 |
| **Total acumulado** | **124/125** |

---

## [0.7.0] — 2026-04-25 — M1 ADVANCED METRICS

### Adicionado — M1 Advanced Quality Metrics

**M1.1 — Cognitive Complexity (Campbell 2018) (`advanced_metrics.py`)**
- `cognitive_complexity(source)` → `(total, per_function_dict)`
- Regras: +1 + depth para estruturas (if/for/while/except/with/lambda/fn aninhada)
- elif/else: +1 flat; BoolOp: +1 flat por sequência; ternary: +1 flat; recursão: +1 flat
- Nesting depth incrementa dentro de cada estrutura de controle

**M1.2 — SQALE Technical Debt (`advanced_metrics.py`)**
- `sqale_debt(metrics_dict, loc)` → `SQALEResult(debt_minutes, sqale_ratio, rating, breakdown)`
- Tabela de remediation costs: CC alto (30-60min), dead code (5min/linha), ILR (30min/loop), clones (30min/grupo), DI > 0.8 (480min)
- `sqale_ratio = debt / (loc × 30) × 100%`; Ratings A (≤5%) → E (>50%)

**M1.3 — Function-level Breakdown (`advanced_metrics.py`)**
- `build_function_profiles(source, fn_cc, fn_cog)` → `List[FunctionProfile]`
- `FunctionProfile`: name, loc, cc, cognitive_cc, halstead_volume, is_complex, debt_minutes, risk_level (LOW/MEDIUM/HIGH)

**M1.4 — Real Dependency Instability (`advanced_metrics.py`)**
- `ImportGraphAnalyzer` — compute real Martin DI via project-level import graph
- `DI(m) = Ce(m) / (Ca(m) + Ce(m))` contando apenas imports internos ao projeto

**M1.5 — Clone Detection Type-2 (`advanced_metrics.py`)**
- `detect_clones(source)` → número de grupos de clone
- Skeleton hash: normaliza `id`, `arg`, `attr`, `name`, `value` em AST dump
- Funções estruturalmente idênticas (renomeadas) são detectadas como Type-2 clones

**M1.6 — Ratings A–E (`advanced_metrics.py`)**
- `compute_ratings(uco_score, sqale_ratio_pct, ...)` → `Ratings(uco, sqale, reliability, security)`
- UCO: ≥80→A, ≥60→B, ≥40→C, ≥20→D, <20→E
- Reliability: penaliza ILR > 0.5 (−40pts) e CC > 20 (−20pts)
- Security: penaliza dead code ratio > 0.1 (−30pts) e Halstead bugs > 3 (−30pts)

**`AdvancedAnalyzer` — Orquestrador M1**
- `UCOBridge(mode="full")` injeta automaticamente todos os atributos M1 no MetricVector
- Dynamic attribute pattern: `mv.cognitive_complexity`, `mv.sqale_rating`, `mv.ratings`, `mv.function_profiles`, `mv.clone_count`, etc.
- `mode="fast"` não executa M1 (preserva performance de análises em lote)

**`/analyze` endpoint ampliado**
- Response inclui: `cognitive_complexity`, `cognitive_fn_max`, `sqale_debt_minutes`, `sqale_ratio`, `sqale_rating`, `clone_count`, `ratings`, `function_profiles`

### Testes
- `tests/test_marco_m1.py` — TM01–TM30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Advanced (30) | ✅ 30/30 |
| Calibration (25) | ✅ 24/25 (1 skip) |
| Marco 6 (14) | ✅ 14/14 |
| Marco 7 (16) | ✅ 16/16 |
| Marco 8 (10) | ✅ 10/10 |
| **Total novo** | **94/95** |

---

## [0.6.0] — 2026-04-25 — M0 FOUNDATION (Bug Fix Sprint)

### Corrigido — M0.1 Métricas (9 bugs de medição)

**BUG-06 — Halstead overcounting ~10× (uco_bridge.py)**
- `visit_Attribute`: removido `self._operand(node.attr)` — `.attr` é operador, não operando. Reduz n2/N2 em ~50%.

**BUG-07 — CC undercount ~33% — padrões Python ausentes (uco_bridge.py)**
- Adicionados visitors: `visit_AsyncFor`, `visit_AsyncWith`, `visit_Lambda`, `visit_match_case`

**BUG-15 — CC comprehension inflation (uco_bridge.py)**
- `visit_comprehension`: `+= 1` → `+= len(node.ifs)`. `[x for x in lst]` → +0 CC.

**BUG-08 — ILR: recursão sem base case não detectada (uco_bridge.py)**
- `_check_recursion_risk()`: detecta `def f(n): return f(n-1)` sem `if` guard → ILR+1.

**BUG-13 — Dead code: constant-False branches ignoradas (uco_bridge.py)**
- `_scan_dead_code()`: detecta `if False:`, `while False:`, `if True: ... else: ...`

**BUG-01 — Java CC logical expressions (java.py)**
- `child_by_field_name("operator")` substitui text-scan para `&&`/`||`.

**BUG-17 — Java while(true) case-sensitive (java.py)**
- Normaliza whitespace+lowercase: `while ( true )` e `while(TRUE)` detectados.

**BUG-02 — JS ILR sempre zero (javascript.py)**
- `child_by_field_name("condition")` substitui `_get_child(node, "condition")` (type ≠ field).

**BUG-16 — Go ILR false negative: time.After/ctx.Done (golang.py)**
- `_has_channel_escape()`: detecta `<-` operator, `time.After`, `time.NewTimer`, `ctx.Done`.

### Corrigido — M0.2 Estabilidade e Segurança

**BUG-03 — Registry race condition (registry.py)**
- Double-checked locking em `get_registry()`.

**BUG-04 — SQLite thread-unsafe (snapshot_store.py)**
- Per-thread connections via `threading.local()` + `_get_conn()` helper.

**BUG-05 — Auth desabilitada por padrão (server.py)**
- `auth_enabled` lê `UCO_AUTH_ENABLED` env var. Produção requer `UCO_AUTH_ENABLED=1`.

**SEC-04 — APEX webhook recursão ilimitada (server.py)**
- Depth guard via `threading.local()`, limite de 3 níveis.

**T77 — Body size sem limite (server.py)**
- Rejeita `Content-Length > 10MB` com HTTP 413.

### Adicionado

- `tests/test_calibration.py` — 25 testes: CC, ILR, DeadCode, Halstead, radon comparison, performance
- `pyproject.toml`: versão 0.3.0 → 0.6.0; `python_files` inclui `test_calibration.py`

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Core (27) | ✅ 27/27 |
| M2 Lang+Auth (48) | ✅ 48/48 |
| M3 APEX (16) | ✅ 16/16 |
| M4 Reports (35) | ✅ 35/35 |
| M5 Diff+Bench (15) | ✅ 15/15 |
| M6 Docker (14) | ✅ 14/14 |
| M7 Templates (16) | ✅ 16/16 |
| M8 Demo (10) | ✅ 10/10 |
| **Calibration (25)** | **✅ 24/25 (1 skip)** |
| **Total** | **205/206** |

---

## [0.5.0] — 2026-04-19 — ENTREGAR

### Adicionado — Marco 8 (M8 — ENTREGAR)
- `README.md` — documentação completa com badges, instalação, endpoints, APEX integration, tabela de marcos
- `demo/demo_full.py` — demo ponta a ponta em 8 steps: analyze → history → classify → diff → report → apex_event → apex_fix → status
- `tests/test_marco8.py` — T80–T89 (10 testes de integração E2E)
- `/docs` atualizado — 19 endpoints documentados
- Demo executa em < 2s; CHANGELOG cobre v0.1.0 → v0.5.0

---

## [0.4.0] — 2026-04-19 — AGIR

### Adicionado — Marco 7 (M7 — AGIR)
- `apex_integration/templates.py` — 8 templates de ação corretiva por tipo de erro UCO
  - TECH_DEBT_ACCUMULATION, AI_CODE_BOMB, GOD_CLASS_FORMATION
  - DEPENDENCY_CYCLE_INTRODUCTION, LOOP_RISK_INTRODUCTION
  - COGNITIVE_COMPLEXITY_EXPLOSION, DEAD_CODE_DRIFT, HALSTEAD_BUG_DENSITY
- `POST /apex/fix` — endpoint bidirecional: APEX envia `APEX_FIX_REQUEST`, sensor aplica transforms
  - Retorna: `fixed_code`, `h_before/after`, `delta_h`, `apex_prompt` contextualizado
  - `transforms_applied` detectados por comparação de métricas antes/depois
- `POST /apex/webhook` ampliado: `APEX_FIX_REQUEST` + `APEX_TEMPLATE_REQUEST`
- `render_prompt()` — preenchimento contextual do template com métricas reais
- `fix_action_for()` — retorna mode, agents, transforms por tipo
- Suite de testes T70–T7D (16 testes)

---

## [0.3.0] — 2026-04-19 — DISTRIBUIR

### Adicionado
- `pyproject.toml` — packaging PEP 517/518 com entry point `uco-sensor`
- `docker-compose.yml` — stack completa dev/prod com volume persistente e profile cron
- `CHANGELOG.md` — histórico de versões
- `ROADMAP.md` — plano de marcos PMI M4→M8

### Marco 6 (M6 — DISTRIBUIR)
- `pyproject.toml` com `[project.scripts] uco-sensor = "cli:main"`
- `docker-compose.yml` com service `uco-sensor` e `uco-cron` (profile)
- Dockerfile multi-stage existente validado (T65, T66)
- Suite de testes T60–T69: empacotamento, container, release artifacts

---

## [0.2.0] — 2026-04-19 — CALIBRAR

### Adicionado — Marco 5 (M5 — CALIBRAR)
- `POST /diff` — endpoint de comparação entre 2 commits
  - Retorna delta dos 9 canais UCO (Hamiltoniano, CC, ILR, DSM, ...)
  - Campo `regression` (bool) com threshold baseado em ΔH e ΔCC
  - `suggested_transforms`: lista de ações corretivas automáticas
  - `uco_score_before/after` e `score_delta`
  - `summary` legível: `"REGRESSÃO: ΔH=+3.2  ΔCC=+5  Score 72→45"`
- Benchmark confirmado: 20 arquivos < 5s
- Calibração: código saudável real → UCO Score ≥ 40
- Suite de testes T50–T5D (15 testes)

---

## [0.1.3] — 2026-04-19 — VISUALIZAR

### Adicionado — Marco 4 (M4 — VISUALIZAR)
- `GET /report?module=<id>` — HTML report standalone com:
  - Gauge SVG do UCO Score
  - Tabela de arquivos por status (CRITICAL/WARNING/STABLE)
  - Breakdown por linguagem
  - Sparklines de tendência
- `GET /badge?score=87&status=STABLE` — badge SVG estilo shields.io (público)
- `GET /badge?module=<id>` — badge gerado do histórico do módulo
- `report/html_report.py` — gerador HTML self-contained (zero deps externas)
- `report/badge.py` — badges SVG com paleta de cores por faixa de score
- `_send_html()` e `_send_svg()` no handler HTTP
- Suite de testes T40–T49 (35 testes)

---

## [0.1.2] — 2026-04-18 — CONECTAR

### Adicionado — Marco 3 (M3 — CONECTAR)
- `apex_integration/event_bus.py` — ApexEventBus com transportes: null, callback, file, webhook
- `apex_integration/connector.py` — ApexConnector com severity gate e SnapshotStore
- `GET /apex/status` — status da integração APEX
- `GET /apex/ping` — teste de conectividade bidirecional
- `POST /apex/webhook` — handshake bidirecional (ACK APEX_PING, APEX_RESCAN_REQUEST)
- `GET /anomalies` — lista anomalias persistidas
- Evento `UCO_ANOMALY_DETECTED` — publicado automaticamente em análise CRITICAL
- Suite de testes T30–T34 (16 testes)

---

## [0.1.1] — 2026-04-18 — EXPANDIR

### Adicionado — Marco 2 (M2 — EXPANDIR)
- `lang_adapters/` — registry multi-linguagem (Python, JS/TS, Java, Go)
- Auth/Billing: `POST /auth/keys`, `GET /auth/keys`, `DELETE /auth/keys`
- `POST /analyze-pr` — análise de PR com saída SARIF 2.1.0
- `ci/uco-pr-check.yml` — GitHub Actions Quality Gate
- `Dockerfile` multi-stage (Python 3.11-slim, usuário não-root)
- `requirements.txt` com numpy, scipy, PyWavelets, tree-sitter
- Suite de testes T10–T29 (20 testes)

---

## [0.1.0] — 2026-04-17 — ANALISAR

### Adicionado — Marco 1 (M1 — ANALISAR)
- `sensor_core/uco_bridge.py` — UCOBridge: extrai 9 canais do UCO v4
- `sensor_storage/snapshot_store.py` — SnapshotStore SQLite com baseline e z-score
- `api/server.py` — HTTP server stdlib-only (BaseHTTPRequestHandler)
  - `GET /health`, `GET /docs`, `GET /modules`, `GET /history`, `GET /baseline`
  - `POST /analyze`, `POST /repair`
- `POST /scan-repo` — RepoScanner batch
- FrequencyEngine integrado via `pipeline/` (frequency-engine)
- Gaps CSL: weighted_mean_freq (fw_shift), dual-confirmation, POST /repair
- Suite de testes T01–T08 (30 testes)

---

[Unreleased]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/thiagofernandes1987-create/APEX/releases/tag/v0.1.0
