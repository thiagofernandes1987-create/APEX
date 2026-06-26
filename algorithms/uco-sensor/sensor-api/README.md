# UCO-Sensor

![UCO Score](https://img.shields.io/badge/UCO%20Score-87%2F100-4c1?style=flat-square)
![Status](https://img.shields.io/badge/status-STABLE-4c1?style=flat-square)
![Version](https://img.shields.io/badge/version-3.10.0-blue?style=flat-square)
![Tests](https://img.shields.io/badge/tests-2185%2B%20passing-4c1?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

> **Plataforma SaaS de análise espectral de qualidade de código** — powered by **UCO v4** + **FrequencyEngine**.  
> Detecta degradação de código *antes* que vire dívida técnica irreversível, integrada nativamente ao **APEX Event Bus**.
>
> v3.10.0 entrega: **isolamento multi-tenant real**, billing atômico, 76+ endpoints REST, 13 transformações fechadas SAST↔Fix, 5 invariantes formais executáveis, paper POPL/PLDI skeleton.

---

## O que é o UCO-Sensor?

O UCO-Sensor extrai **9 canais de métricas** de cada commit e aplica análise espectral (FFT + Hurst + PCI) para identificar **padrões de degradação temporais** — não apenas "você tem tech debt", mas:

> *"Seu tech debt **começou** no commit `abc123` (45 dias atrás), Hurst H=0.96 indica que é **irreversível** sem refactoring ativo."*

### Os 9 Canais UCO

| Canal | Símbolo | O que mede |
|-------|---------|-----------|
| Hamiltoniano UCO | **H** | Energia total do código — complexidade agregada |
| Cyclomatic Complexity | **CC** | Branches e caminhos lógicos |
| Infinite Loop Risk | **ILR** | While True, recursão sem base case |
| DSM Density | **DSM** | Acoplamento entre módulos |
| DSM Cyclic Ratio | **DSM_c** | Ciclos de dependência |
| Dependency Instability | **DI** | Instabilidade da interface |
| Syntactic Dead Code | **SDC** | Código nunca executado |
| Duplicate Block Count | **DBC** | Blocos duplicados |
| Halstead Bug Estimate | **HB** | Densidade de bugs estimada |

---

## Instalação

### Rápida (desenvolvimento)

```bash
# Clone o repositório APEX
git clone https://github.com/thiagofernandes1987-create/APEX.git
cd APEX/algorithms/uco-sensor/sensor-api

# Instalar dependências core
pip install numpy scipy PyWavelets

# Opcional: suporte multi-linguagem (JS, TS, Java, Go)
pip install tree-sitter tree-sitter-python tree-sitter-javascript \
            tree-sitter-typescript tree-sitter-java tree-sitter-go
```

### Via pyproject.toml

```bash
pip install -e ".[parsers,dev]"
```

### Docker

```bash
# Build e start
docker compose up -d

# Verificar saúde
curl http://localhost:8080/health
```

---

## Uso

### CLI

```bash
# Analisar um arquivo
python cli.py analyze src/auth.py

# Escanear repositório inteiro
python cli.py scan ./meu-projeto

# Saída JSON
python cli.py scan ./meu-projeto --format json > report.json

# Relatório HTML
python cli.py scan ./meu-projeto --format html > report.html

# Histórico de commits git
python cli.py git-history ./meu-projeto --commits 90

# Iniciar servidor HTTP
python cli.py serve --port 8080 --no-auth
```

### API REST

```bash
# Analisar código
curl -X POST http://localhost:8080/analyze \
  -H "Content-Type: application/json" \
  -d '{"code": "def f(x): return x", "module_id": "utils.math", "commit_hash": "abc123"}'

# Diff entre 2 versões
curl -X POST http://localhost:8080/diff \
  -H "Content-Type: application/json" \
  -d '{
    "before": {"code": "def f(): pass", "commit_hash": "v1"},
    "after":  {"code": "def f():\n  x=1\n  return x", "commit_hash": "v2"}
  }'

# Relatório HTML do módulo
curl http://localhost:8080/report?module=utils.math > report.html

# Badge SVG (embed em README)
curl "http://localhost:8080/badge?score=87&status=STABLE" > uco-badge.svg

# Fix guiado pelo APEX
curl -X POST http://localhost:8080/apex/fix \
  -H "Content-Type: application/json" \
  -d '{"module_id": "auth.login", "code": "...", "error_type": "DEAD_CODE_DRIFT"}'
```

### Python (embutido)

```python
import sys
sys.path.insert(0, "/path/to/uco-sensor/sensor-api")
sys.path.insert(0, "/path/to/frequency-engine")

from sensor_core.uco_bridge import UCOBridge
from sensor_storage.snapshot_store import SnapshotStore
from pipeline.frequency_engine import FrequencyEngine

bridge = UCOBridge(mode="fast")
store  = SnapshotStore("uco.db")
engine = FrequencyEngine()

# Analisar código
mv = bridge.analyze(source_code, "auth.service", "commit_hash")
store.insert(mv)

# Classificar padrão temporal
history = store.get_history("auth.service", window=60)
result  = engine.analyze(history, module_id="auth.service")

print(f"{result.primary_error} | {result.severity} | conf={result.primary_confidence:.0%}")
# AI_CODE_BOMB | CRITICAL | conf=87%
```

---

## Endpoints (76+)

Categorias principais (lista completa via `GET /docs`):

| Categoria | Endpoints | Notas |
|---|---|---|
| **Liveness/Discovery** | `/health`, `/docs`, `/badge` | sem auth |
| **Análise core** | `/analyze`, `/diff`, `/repair`, `/repair/hmc`, `/scan-incremental`, `/scan-repo`, `/analyze-pr` (SARIF 2.1.0) | billable |
| **SAST / SCA / IaC** | `/sast`, `/scan-sca`, `/scan-iac`, `/scan-flow`, `/scan-performance`, `/scan-architecture`, `/scan-test-quality`, `/scan-thread-safety` | billable |
| **AutoFix loop** | `/apex/auto-remediate`, `/gate` | 13 regras SAST mapeadas (SAST006/7/22/24/27/38/39/40/41/42/43/44/45) |
| **Histórico / Trend** | `/modules`, `/history`, `/baseline`, `/anti-pattern-score`, `/anti-pattern-score/history`, `/anti-pattern-score/trend`, `/predictor/accuracy` | leitura |
| **Marketplace** | `/marketplace/publish`, `/marketplace/pull`, `/marketplace/list`, `/marketplace/import` | Sprint V |
| **Signatures (DBSCAN)** | `/signatures/discover`, `/signatures/import`, `/similar` | Sprint P/U |
| **CFG visualization** | `/cfg/graph`, `/cfg/hotspots` | Sprint X |
| **Multi-tenant SaaS** | `/tenants` (CRUD), `/tenants/{id}/usage`, `/tenants/{id}/suspend`, `/tenants/{id}/reactivate`, `/auth/keys` (admin) | Sprint Y |
| **Billing** | `/billing/usage`, `/billing/quota`, `/billing/events`, charged via `_billed_dispatch` (atomic check_and_charge) | Sprint Y |
| **Invariants** | `/invariants/check`, `/invariants/violations` | Sprint Z (I1-I5 formal) |
| **Feeds** | `/feeds/sast/load`, `/feeds/cve/load`, `/feeds/rules/list` | path-jail Sprint W |
| **APEX integration** | `/apex/status`, `/apex/ping`, `/apex/webhook`, `/apex/fix` | Event Bus bidirecional |
| **Cache admin** | `/cache/invalidate` | admin |

> **Auth**: a maioria dos endpoints exige API key (`X-API-Key` header). Admin-only endpoints exigem `UCO_ADMIN_KEY` **independente** de `UCO_AUTH_ENABLED` (Sprint W audit-1). Billable endpoints rejeitam 402 quando a quota do tenant é insuficiente (Sprint Y SY-FIX-6).

---

## Multi-tenant SaaS quickstart (< 5 min)

```bash
# 1. Iniciar o servidor com auth e admin key
export UCO_AUTH_ENABLED=1
export UCO_ADMIN_KEY=$(openssl rand -hex 32)
python cli.py serve --port 8080 &

# 2. Criar um tenant (admin)
curl -X POST http://localhost:8080/tenants \
  -H "X-Admin-Key: $UCO_ADMIN_KEY" \
  -d '{"tenant_id": "acme-corp", "plan": "PRO", "unit_budget": 100000}'

# 3. Gerar API key para o tenant (admin)
KEY=$(curl -X POST http://localhost:8080/auth/keys \
  -H "X-Admin-Key: $UCO_ADMIN_KEY" \
  -d '{"name": "acme-prod", "tenant_id": "acme-corp"}' | jq -r .key)

# 4. Cliente faz análise (debita 1 unidade do budget de acme-corp)
curl -X POST http://localhost:8080/analyze \
  -H "X-API-Key: $KEY" \
  -d '{"code": "def f(x): return x", "module_id": "utils.math", "commit_hash": "abc123"}'

# 5. Verificar consumo
curl -H "X-Admin-Key: $UCO_ADMIN_KEY" \
  http://localhost:8080/tenants/acme-corp/usage?period=2026-06
```

A partir de v3.10.0 (Sprint AB), **dados de produto são isolados por tenant
no schema**: snapshots, anomalies, discovered_signatures, remediations e
marketplace_signatures todas têm coluna `tenant_id` + `UNIQUE(tenant_id,
module_id, commit_hash)`. Tenant A não vê / sobrescreve dados do tenant B.

---

## Integração APEX

O UCO-Sensor é um **sensor cognitivo nativo do APEX**. Quando integrado:

1. **UCO detecta** `AI_CODE_BOMB` no módulo `auth.service`
2. **Publica** `UCO_ANOMALY_DETECTED` no APEX Event Bus
3. **APEX** aciona agente `engineer` com o `apex_prompt` contextualizado
4. **APEX** envia `APEX_FIX_REQUEST` de volta ao sensor via webhook
5. **UCO aplica** transforms e devolve `fixed_code + delta_h`

```yaml
# Configuração APEX (variáveis de ambiente)
APEX_WEBHOOK_URL: https://apex.mycompany.com/events
APEX_API_KEY:     <apex_key>
UCO_APEX_ENABLED: "1"
```

### Variáveis de ambiente (referência completa)

| Variável | Onde | Default | Descrição |
|---|---|---|---|
| `UCO_AUTH_ENABLED` | `api/server.py` | `0` | `"1"` exige API key em endpoints sensíveis (ingest, admin). |
| `UCO_ADMIN_KEY` | `api/server.py` | _none_ | Chave **sempre** exigida em endpoints `admin/*` (independente de `UCO_AUTH_ENABLED`). Sprint W audit-1. |
| `UCO_INCLUDE_TRACE` | `api/server.py` | `0` | `"1"` inclui stack trace em respostas 500; default **strip** (QA-FIX-1, v3.9.1). |
| `UCO_APEX_ENABLED` | `api/server.py` | `0` | Liga o conector APEX (envio de `UCO_ANOMALY_DETECTED`). |
| `APEX_WEBHOOK_URL` | conector APEX | _none_ | URL do Event Bus APEX. |
| `APEX_API_KEY` | conector APEX | _none_ | Token de autenticação no Event Bus APEX. |
| `UCO_FEEDS_DIR` | `sensor_storage/path_jail.py` | _none_ | **Raíz do path-jail** para `/feeds/*/load`. Sem essa variável, todo file-load é rejeitado (Sprint W audit-5). |
| `UCO_REDIS_URL` | `sensor_storage/cache.py` | _none_ | Quando setada, cache compartilhado via Redis; caso contrário usa LRU local. |
| `UCO_CACHE_MAX_SIZE` | `sensor_storage/cache.py` | `1024` | Capacidade do LRU local (entradas). |
| `UCO_DB_PATH` | `sensor_storage/snapshot_store.py` | `:memory:` | Caminho do SQLite. Usar arquivo (ex.: `/var/lib/uco/uco.db`) em produção para persistência + WAL. |
| `BYPASS_TENANTS` | `governance/tenancy.py` | _hardcoded_ | Tenant IDs que bulam invariants de billing (ex.: `default` para legacy single-tenant). |


### Templates de Ação por Tipo de Anomalia

| Tipo | Mode APEX | Intervenção Imediata |
|------|-----------|---------------------|
| `TECH_DEBT_ACCUMULATION` | DEEP | Não |
| `AI_CODE_BOMB` | DEEP | **Sim** |
| `GOD_CLASS_FORMATION` | DEEP | Não |
| `LOOP_RISK_INTRODUCTION` | FAST | **Sim** |
| `COGNITIVE_COMPLEXITY_EXPLOSION` | DEEP | Não |
| `DEAD_CODE_DRIFT` | FAST | Não |
| `HALSTEAD_BUG_DENSITY` | DEEP | Não |
| `DEPENDENCY_CYCLE_INTRODUCTION` | DEEP | Não |

---

## GitHub Actions (CI/CD)

```yaml
# .github/workflows/uco-sensor.yml
# Copie de: ci/uco-pr-check.yml

# O que faz:
# 1. Detecta arquivos modificados no PR
# 2. Analisa via /analyze-pr → SARIF 2.1.0
# 3. Upload para GitHub Code Scanning
# 4. Comenta no PR com score UCO
# 5. Bloqueia merge se status = CRITICAL
# 6. Publica UCO_ANOMALY_DETECTED no APEX (se configurado)
```

---

## Estrutura do Projeto

```
sensor-api/
├── api/
│   └── server.py           — HTTP server (stdlib only, _billed_dispatch, 76+ handlers)
├── sensor_core/
│   ├── uco_bridge.py       — UCOBridge fast tier (9 canais, calibrado, zero-dep)
│   └── autofix/            — engine + 13 transforms + sast_remediation closed-loop
├── sensor_storage/
│   ├── snapshot_store.py   — SQLite + WAL, tabelas multi-tenant (Sprint AB)
│   ├── cache.py            — LRU local / Redis opcional
│   └── path_jail.py        — File-load guard (Sprint W audit-5)
├── governance/             — channels (SSOT), invariants (I1-I5), policy_engine,
│                              tenancy, billing, marketplace, trend_engine, signals
├── sast/                   — scanner (33 regras: SAST001-SAST045), regex_analyzer,
│                              rules_feed (dynamic), taint_engine
├── sca/                    — vulnerability_scanner (205 CVEs / 12 ecosystems)
├── iac/                    — scanner (102 regras / 8 formats: TF, K8s, Docker, etc.)
├── metrics/                — extended_vectors (96 canais estendidos),
│                              anti_pattern_score, hmc_repair
├── lang_adapters/          — Python, JS/TS, Java, Go (tree-sitter / fallback)
├── apex_integration/       — event_bus, connector, templates
├── scan/                   — repo_scanner, git_history_scanner, incremental
├── report/                 — html_report, badge SVG, SARIF 2.1.0
├── ci/                     — action_entrypoint (GitHub Action), uco-pr-check.yml
├── paper/                  — paper.tex (POPL/PLDI), experiments.md, reproducibility.py
├── tests/                  — test_marco_m1..test_marco_m62 (2185+ tests)
├── cli.py                  — CLI completa
├── pyproject.toml          — Packaging PEP 517/518 (v3.10.0)
├── Dockerfile              — Multi-stage (Python 3.11-slim)
├── docker-compose.yml      — Stack dev/prod
├── CHANGELOG.md            — Histórico v0.1.0 → v3.10.0
├── ROADMAP.md              — Marcos M1–M62 + roadmap Sprint AC+
└── inventario.md (./..)    — Tracking persistente entre sessões (APEX SCIENTIFIC)
```

### Tabelas SQLite (Sprint AB, v3.10.0)

| Tabela | Owner | tenant_id? | Notas |
|---|---|---|---|
| `snapshots`            | Sprint A    | ✓ Sprint AB | UNIQUE(tenant_id, module_id, commit_hash) |
| `anomalies`            | Sprint A    | ✓ Sprint AB | |
| `discovered_signatures`| Sprint P    | ✓ Sprint AB | DBSCAN clusters por tenant |
| `remediations`         | Sprint C    | ✓ Sprint AB | AutoFix telemetry |
| `marketplace_signatures`| Sprint V   | ✓ Sprint AB | Compartilhado entre tenants vs. privado |
| `api_keys`             | Sprint M    | ✓ Sprint Y  | |
| `tenants`              | Sprint Y    | n/a (é a tabela) | |
| `usage_events`         | Sprint Y    | ✓ Sprint Y  | Atomic check_and_charge |

---

## Badge no seu README

```markdown
<!-- Badge dinâmico via UCO-Sensor -->
![UCO Score](http://localhost:8080/badge?score=87&status=STABLE&label=UCO%20Score)

<!-- Badge estático gerado -->
![UCO Score](./uco-badge.svg)
```

Gerar badge estático:

```python
from report.badge import generate_badge_svg
from pathlib import Path
svg = generate_badge_svg(score=87, status="STABLE", label="UCO Score")
Path("uco-badge.svg").write_text(svg)
```

---

## Testes

```bash
# Marco específico
python tests/test_marco1.py
python tests/test_marco4.py   # Reports & Badges
python tests/test_marco7.py   # Templates APEX + /apex/fix

# Suite completa
python -m pytest tests/ -v

# Com cobertura
python -m pytest tests/ --cov=. --cov-report=html
```

| Marcos / Sprints | Escopo | Testes | Status |
|------------------|--------|--------|--------|
| M1 Core              | Pipeline e MetricVector                  | 30   | ✅ |
| M2 Lang+Auth         | Multi-linguagem + API keys               | 20   | ✅ |
| M3 APEX              | Conector Event Bus                        | 16   | ✅ |
| M4 Reports           | HTML + Badge SVG                         | 35   | ✅ |
| M5 Diff+Bench        | /diff + benchmark suite                  | 15   | ✅ |
| M6 Docker            | Multi-stage + docker-compose             | 14   | ✅ |
| M7 Templates         | /apex/fix + templates de ação            | 16   | ✅ |
| M8 Demo              | Pipeline end-to-end + README pin         | 10   | ✅ |
| M9–M30 (LEAP 1–4)    | Persistence, AutoFix, APS               | ~450 | ✅ |
| M31–M45 (Sprints C–N)| Telemetry, signatures, SAST feed         | ~600 | ✅ |
| M46–M52 (Sprints O–T)| DBSCAN, HMC, RCA, Granger                | ~350 | ✅ |
| M53–M55 (Sprints W/W2)| Gates 1+2 hardening                      | ~150 | ✅ |
| M56–M60 (Sprints V–Z) | Marketplace, CFG, multi-tenant, paper+invariants | ~250 | ✅ |
| M61 (Sprint AA)      | UCO Deep Integration — AA-1 parcial      | 16   | ✅ |
| M62 (Sprint AB)      | Multi-tenant isolation + 4 quick-wins    | 30   | ✅ v3.10.0 |
| **Total**            | **M1–M62**                                | **~2191** | **✅** |

> Para rodar a suíte completa: `python -m pytest tests/ -q` (≈ 2-3min em CI moderna).

---

## Histórico de versões

| Versão | Sprint | Highlights |
|---|---|---|
| **v3.10.0** | AB | Multi-tenant **schema isolation real** (tenant_id em 5 tabelas + _scoped helper), charge-after-2xx, cache invalidate on writes, ReDoS guard reuse |
| v3.9.1 | QA Loop | 4-lente 2-round convergence, QA-FIX-1..6 |
| v3.9.0 | Z | Paper POPL/PLDI skeleton, 5 invariantes formais executáveis |
| v3.8.0 | Y | Multi-tenant **billing** + atomic check_and_charge (isolation entregue em AB) |
| v3.7.0 | X | CFG visualizável + port-allocator |
| v3.6.0 | V | Marketplace de spectral signatures |
| v3.5.2 | W2 | Gate-2 deep audit (G2-1..G2-8) |
| v3.5.1 | W  | Gate-1 hardening (audit-1..6) |
| v3.5.0 | R/S/Q/T/U | RCA, Granger, HMC repair, VS Code, Cache/ASGI |
| ... | ... | (`CHANGELOG.md` para histórico completo desde v0.1.0) |

---

## Licença

MIT — © APEX Project 2026  
Plataforma desenvolvida iterativamente sob disciplina **APEX SCIENTIFIC** (DSM + Ishikawa + Pareto + FMEA + WBS), com workflows multi-agente para design panel e adversarial review onde a complexidade justifica.
