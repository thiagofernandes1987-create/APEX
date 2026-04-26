# UCO-Sensor — CHANGELOG

Todas as mudanças notáveis são documentadas aqui.  
Formato: [Semantic Versioning](https://semver.org/) | Convenção: [Keep a Changelog](https://keepachangelog.com/)

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
