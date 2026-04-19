# UCO-Sensor — CHANGELOG

Todas as mudanças notáveis são documentadas aqui.  
Formato: [Semantic Versioning](https://semver.org/) | Convenção: [Keep a Changelog](https://keepachangelog.com/)

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
