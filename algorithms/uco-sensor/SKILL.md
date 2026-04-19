---
skill_id: algorithms.uco-sensor.sensor
name: "UCO-Sensor — Spectral Code Quality Analysis"
description: >
  Analisador espectral de qualidade de código multi-linguagem (Python, JS/TS, Java, Go).
  Detecta 8 padrões de degradação via pipeline FFT/Wavelet/PELT sobre 9 canais UCO:
  H (Hamiltoniano), CC, ILR, DSM_d, DSM_c, DI, dead, dups, bugs.
  Publica UCO_ANOMALY_DETECTED no APEX EventBus para classificações CRITICAL.
  Alternativa open-source ao SonarQube — sem LLM, billing por chamada de API.
version: v00.37.0
status: CANDIDATE
domain_path: algorithms/uco-sensor
anchors:
  - uco
  - uco_sensor
  - spectral_analysis
  - code_quality
  - sonarqube_alternative
  - hamiltonian
  - cyclomatic_complexity
  - infinite_loop_risk
  - dead_code
  - duplicate_detection
  - apex_integration
  - UCO_ANOMALY_DETECTED
  - frequency_engine
  - sarif
  - multi_language
source_repo: uco-sensor
risk: safe
languages: [python]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.37.0
apex_events:
  publishes:
    - event_type: UCO_ANOMALY_DETECTED
      trigger: classification severity >= CRITICAL
      fields: [primary_error, severity, uco_score, apex_prompt, change_point, spectral_evidence]
  consumes: []
test_coverage:
  frequency_engine: 88/88
  marco1: 27/27
  marco2: 30/30
  marco3: 16/16
  marco_c_real_code: 48/48
  total: 209/209
entry_points:
  cli:    sensor-api/cli.py
  server: sensor-api/api/server.py
  scan:   sensor-api/scan/repo_scanner.py
---

# UCO-Sensor

Analisador espectral de qualidade de código — alternativa open-source ao SonarQube.

## O que faz

Analisa código-fonte em **Python, JavaScript/TypeScript, Java e Go** extraindo 9 canais UCO:

| Canal   | Descrição |
|---------|-----------|
| H       | Hamiltoniano (Halstead effort / LOC) |
| CC      | Cyclomatic Complexity |
| ILR     | Infinite Loop Risk |
| DSM_d   | Density de dependências |
| DSM_c   | Ciclicidade de dependências |
| DI      | Dependency Instability |
| dead    | Linhas de código morto |
| dups    | Blocos duplicados |
| bugs    | Halstead bug density |

O **FrequencyEngine** aplica FFT/Wavelet/PELT sobre séries temporais desses canais para detectar 8 padrões:

- `AI_CODE_BOMB` — spike simultâneo em dead + dups + ILR
- `TECH_DEBT_ACCUMULATION` — H crescendo em ULF/LF
- `GOD_CLASS_FORMATION` — DI dominante em HF
- `COGNITIVE_COMPLEXITY_EXPLOSION` — CC burst agudo
- `DEPENDENCY_CYCLE_INTRODUCTION` — DSM_c > 0.5
- `LOOP_RISK_INTRODUCTION` — ILR isolado
- `DEAD_CODE_DRIFT` — dead acumulando (Hurst ≈ 1.0, irreversível)
- `REFACTORING_OPPORTUNITY` — correlação DSM_d + CC

## Integração APEX

Quando `severity == CRITICAL`, o `ApexConnector` publica `UCO_ANOMALY_DETECTED` no `ApexEventBus`:

```python
from apex_integration.connector import get_connector

connector = get_connector()
connector.handle(classification_result, store)
# → publica {"event_type": "UCO_ANOMALY_DETECTED", "primary_error": "AI_CODE_BOMB", ...}
```

## CLI

```bash
# Escanear repositório local
python cli.py scan ./meu-projeto

# Escanear todos os repos de um usuário GitHub
python cli.py scan-github thiagofernandes1987-create

# Filtrar repos específicos
python cli.py scan-github thiagofernandes1987-create --repos apex,uco-sensor

# Saída SARIF para GitHub Code Scanning
python cli.py scan ./meu-projeto --format sarif > results.sarif

# Iniciar servidor HTTP
python cli.py serve --port 8080 --db uco.db --apex-url https://apex.example.com
```

## API REST

```
POST /analyze          — analisa código + classifica
POST /analyze-pr       — analisa diff de PR → SARIF + status
POST /scan-repo        — escaneia diretório remoto
GET  /health           — liveness probe
GET  /docs             — auto-documentação
GET  /anomalies        — eventos UCO_ANOMALY_DETECTED persistidos
POST /auth/keys        — cria API key
GET  /apex/status      — status da integração APEX
POST /apex/ping        — testa conectividade APEX
```

## Instalação

```bash
pip install numpy scipy PyWavelets
# Opcional (tree-sitter para JS/TS/Java/Go):
pip install tree-sitter tree-sitter-python tree-sitter-javascript \
            tree-sitter-typescript tree-sitter-java tree-sitter-go
```

## CI/CD

Copie `.github/workflows/uco-sensor.yml` (gerado em `sensor-api/ci/`) para o seu repositório.
Funciona como quality gate: bloqueia PRs com arquivos CRITICAL, faz upload SARIF para GitHub Code Scanning.

## Diff History

- **v00.37.0**: Marco 3 completo — APEX integration, scan-github CLI, 209/209 testes
- **v00.36.0**: Marco 2 completo — multi-language adapters, auth/billing, CI/CD
- **v00.35.0**: Marco 1 completo — UCOBridge, SnapshotStore, FrequencyEngine pipeline
