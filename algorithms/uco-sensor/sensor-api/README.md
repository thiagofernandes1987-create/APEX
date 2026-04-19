# UCO-Sensor

![UCO Score](https://img.shields.io/badge/UCO%20Score-87%2F100-4c1?style=flat-square)
![Status](https://img.shields.io/badge/status-STABLE-4c1?style=flat-square)
![Version](https://img.shields.io/badge/version-0.4.0-blue?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9%2B-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![APEX](https://img.shields.io/badge/APEX-v00.36.0-7c3aed?style=flat-square)

> **API de análise espectral de qualidade de código** — powered by **UCO v4** + **FrequencyEngine**.  
> Detecta degradação de código *antes* que vire dívida técnica irreversível, integrada nativamente ao **APEX Event Bus**.

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

## Endpoints

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| GET  | `/health` | — | Liveness probe |
| GET  | `/docs` | — | Auto-documentação |
| GET  | `/badge` | — | Badge SVG (`?score=87&status=STABLE` ou `?module=`) |
| POST | `/analyze` | ✓ | Analisa código (multi-linguagem) |
| POST | `/repair` | ✓ | Sugere e aplica transforms UCO |
| POST | `/diff` | ✓ | Diff UCO entre 2 commits |
| POST | `/analyze-pr` | ✓ | Análise de PR (SARIF 2.1.0) |
| POST | `/scan-repo` | ✓ | Scan de repositório inteiro |
| GET  | `/modules` | ✓ | Lista módulos rastreados |
| GET  | `/history` | ✓ | Histórico de snapshots |
| GET  | `/baseline` | ✓ | Baseline e z-scores |
| GET  | `/report` | ✓ | Relatório HTML standalone |
| GET  | `/anomalies` | ✓ | Anomalias detectadas |
| GET  | `/apex/status` | ✓ | Status integração APEX |
| GET  | `/apex/ping` | ✓ | Ping APEX |
| POST | `/apex/webhook` | ✓ | Webhook bidirecional APEX |
| POST | `/apex/fix` | ✓ | Fix guiado pelo APEX |
| POST | `/auth/keys` | admin | Cria API key |
| GET  | `/auth/keys` | admin | Lista API keys |
| DELETE | `/auth/keys` | admin | Revoga API key |

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
│   └── server.py           — HTTP server (stdlib only, zero deps extras)
├── sensor_core/
│   └── uco_bridge.py       — UCOBridge: extrai 9 canais do UCO v4
├── sensor_storage/
│   └── snapshot_store.py   — SnapshotStore SQLite com baseline e z-score
├── lang_adapters/          — Python, JS/TS, Java, Go
├── apex_integration/
│   ├── event_bus.py        — ApexEventBus (webhook/callback/file/null)
│   ├── connector.py        — ApexConnector com severity gate
│   └── templates.py        — 8 templates de ação corretiva
├── scan/
│   ├── repo_scanner.py     — Scan de repositório completo
│   └── git_history_scanner.py — Análise temporal de commits
├── report/
│   ├── html_report.py      — Relatório HTML standalone
│   └── badge.py            — Badges SVG estilo shields.io
├── cli.py                  — CLI completa
├── pyproject.toml          — Packaging PEP 517/518
├── Dockerfile              — Multi-stage (Python 3.11-slim)
├── docker-compose.yml      — Stack dev/prod
├── CHANGELOG.md            — Histórico v0.1.0 → v0.4.0
└── ROADMAP.md              — Marcos M1–M8 com critérios de aceitação
```

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

| Marcos | Testes | Status |
|--------|--------|--------|
| M1 Core | 30 | ✅ |
| M2 Lang+Auth | 20 | ✅ |
| M3 APEX | 16 | ✅ |
| M4 Reports | 35 | ✅ |
| M5 Diff+Bench | 15 | ✅ |
| M6 Docker | 14 | ✅ |
| M7 Templates | 16 | ✅ |
| M8 Demo | 10 | ✅ |
| **Total** | **156** | **✅** |

---

## Licença

MIT — © APEX Project 2026  
Desenvolvido com **[APEX v00.36.0](https://github.com/thiagofernandes1987-create/APEX)** — agente `pmi_pm` + `engineer` + `architect`
