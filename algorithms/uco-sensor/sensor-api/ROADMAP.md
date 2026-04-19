# UCO-Sensor API — Roadmap de Marcos (PMI/APEX)

> Gerado pelo agente **pmi_pm** do APEX — v00.36.0  
> Data: 2026-04-19 | Método: Decomposição por valor entregável + gate de testes

---

## Visão Geral

**Objetivo do Produto**: API de análise de qualidade de código baseada em UCO v4 + FrequencyEngine espectral,
integrada ao APEX Event Bus, operável como REST API standalone ou como sensor cognitivo nativo do APEX.

**Critério de Conclusão**: Todos os testes dos 8 marcos passam + Docker funcional + CI/CD verde.

---

## Estado Atual

```
╔══════╦══════════════════════════════╦════════════╦══════════════╦════════╗
║ Marco║ Entregável                   ║ Dependência║ Valor APEX   ║ Status ║
╠══════╬══════════════════════════════╬════════════╬══════════════╬════════╣
║  M1  ║ Core: UCOBridge + Pipeline   ║ —          ║ ANALISAR     ║ ✅     ║
║  M2  ║ Lang Adapters + Auth + CI/CD ║ M1         ║ EXPANDIR     ║ ✅     ║
║  M3  ║ APEX Integration (EventBus)  ║ M2         ║ CONECTAR     ║ ✅     ║
║  M4  ║ HTML Report + Badge SVG      ║ M1-M3 ✅   ║ VISUALIZAR   ║ 🔄     ║
║  M5  ║ Benchmark repos reais +      ║ M4         ║ CALIBRAR     ║ ✅     ║
║      ║ diff mode (2 commits)        ║            ║              ║        ║
║  M6  ║ pyproject + Docker + Release ║ M5         ║ DISTRIBUIR   ║ ✅     ║
║  M7  ║ Templates APEX + /apex/fix   ║ M6         ║ AGIR         ║ ✅     ║
║  M8  ║ Demo final + Docs completas  ║ M7         ║ ENTREGAR     ║ ✅     ║
╚══════╩══════════════════════════════╩════════════╩══════════════╩════════╝
```

---

## Marco 4 — Report & Visualization

**Objetivo**: Exportação visual de análises UCO em HTML standalone e badges SVG para embed em READMEs e dashboards.

**Entregáveis**:
- `report/html_report.py` — gerador HTML (já existe, testes pendentes)
- `report/badge.py` — gerador SVG badge (já existe, testes pendentes)
- `GET /report?module=<id>` — endpoint que gera HTML do histórico do módulo
- `GET /badge?module=<id>` — badge SVG do status atual do módulo
- `GET /badge?score=<n>&status=<s>` — badge SVG direto por score

**Acceptance Criteria** (T40–T49):
- T40: `badge_color` retorna paleta correta por faixa
- T41: `generate_badge_svg` produz SVG válido com score no texto
- T42: `generate_status_badge_svg` produz SVG para STABLE/WARNING/CRITICAL
- T43: Badge contém valor score correto e não excede 100
- T44: `generate_html_report(ScanResult)` retorna HTML com doctype
- T45: HTML report contém UCO Score no conteúdo
- T46: HTML report contém project status (CRITICAL/WARNING/STABLE)
- T47: HTML report contém tabela de arquivos com colunas corretas
- T48: `GET /report?module=<id>` retorna Content-Type text/html
- T49: `GET /badge?score=87` retorna SVG válido

**Riscos**:
- Baixo: HTML é self-contained, sem dependências externas
- Médio: ScanResult mock precisa de todos os campos obrigatórios

---

## Marco 5 — Scanner Integration

**Objetivo**: Testes de integração para RepoScanner e GitHistoryScanner — pipeline de scan real funcional.

**Entregáveis**:
- `tests/test_marco5.py` — T50–T59
- Validação de `scan/repo_scanner.py` via diretório temporário
- Validação de `scan/git_history_scanner.py` via repo git mínimo
- Integração CLI `scan` e `git-history`

**Acceptance Criteria** (T50–T59):
- T50: RepoScanner descobre arquivos .py em diretório temporário
- T51: RepoScanner produz ScanResult com uco_score ∈ [0,100]
- T52: RepoScanner respeita exclude patterns
- T53: ScanResult.to_dict() serializa para JSON válido
- T54: ScanResult.summary() retorna string não-vazia
- T55: POST /scan-repo com path válido retorna ScanResult
- T56: GitHistoryScanner extrai commits de repo git mínimo
- T57: GitHistoryScanner produz FileTemporalResult por arquivo
- T58: CLI `scan <dir>` roda sem erro e imprime summary
- T59: CLI `scan <dir> --format json` retorna JSON válido

---

## Marco 6 — CLI End-to-End

**Objetivo**: Suite de testes automatizados para todos os subcomandos do CLI.

**Entregáveis**:
- `tests/test_marco6.py` — T60–T69
- `cli.py` completamente testado via subprocess + parser direto

**Acceptance Criteria** (T60–T69):
- T60: `uco-sensor --help` imprime usage sem erro
- T61: `uco-sensor analyze <file>` analisa arquivo real
- T62: `uco-sensor scan <dir>` retorna exit 0 em projeto limpo
- T63: `uco-sensor scan <dir> --format json` serializa corretamente
- T64: `uco-sensor scan <dir> --format html > report.html` gera HTML válido
- T65: `uco-sensor serve --port 0` (porta dinâmica) sobe servidor
- T66: `uco-sensor key create --name test` cria key no store
- T67: `uco-sensor key list` lista keys criadas
- T68: `uco-sensor key revoke <prefix>` remove key
- T69: `uco-sensor git-history <repo>` roda em repo git mínimo

---

## Marco 7 — Production Hardening

**Objetivo**: Garantir operação em produção: Docker funcional, CI/CD completo, performance sob carga, inputs maliciosos rejeitados.

**Entregáveis**:
- `tests/test_marco7.py` — T70–T79
- `Dockerfile` atualizado + `docker-compose.yml`
- `ci/uco-pr-check.yml` completo
- Input sanitization robusta

**Acceptance Criteria** (T70–T79):
- T70: Dockerfile faz `docker build` sem erro
- T71: Container health check responde em < 2s após start
- T72: 50 requests POST /analyze em < 5s (throughput mínimo)
- T73: Input XSS/injection rejeitado ou sanitizado em `/analyze`
- T74: `/auth/keys` sem admin key retorna 403
- T75: API key expirada/revogada retorna 401
- T76: SARIF output de `/analyze-pr` valida contra schema 2.1.0
- T77: POST /analyze com 10MB de código retorna 413 ou processa < 10s
- T78: Módulo com > 500 commits não estoura memória
- T79: `uco-pr-check.yml` tem steps de lint, test e upload-artifact

---

## Marco 8 — Validation & Release

**Objetivo**: Validar calibração do UCO Score contra repositórios reais, gerar release tag e documentação final.

**Entregáveis**:
- `tests/test_marco8.py` — T80–T89
- `validation/validation_report.json` atualizado
- `README.md` com badges e instruções de uso
- Tag `v0.3.0` no repo

**Acceptance Criteria** (T80–T89):
- T80: UCO Score de repo de produção saudável ≥ 60/100
- T81: UCO Score de repo com dívida técnica alta ≤ 50/100
- T82: Hurst H de série estável ∈ [0.3, 0.7]
- T83: Hurst H de série com trend forte ≥ 0.7
- T84: Benchmark: 100 módulos analisados em < 30s
- T85: `validation/validate_real_repos.py` roda sem erro
- T86: README.md tem badge UCO Score, instrução install, exemplo de uso
- T87: CHANGELOG.md documenta todos os marcos entregues
- T88: `python -m pytest tests/` passa todos os marcos 1–8
- T89: Docker Hub push bem-sucedido (ou registry local)

---

## Sequência de Priorização (APEX BDS)

```
M4 → M5 → M6 → M7 → M8
 ↑ dependências simples      ↑ dependências de infra
```

- M4 tem zero dependências pendentes (report/ já existe) → **começar agora**
- M5 depende de M4 (report de scan usa HTML gerado)
- M6 depende de M5 (CLI chama scanners)
- M7 depende de M6 (todos os endpoints testados antes de hardening)
- M8 depende de M7 (produção estável antes de release)

---

*Gerado por: pmi_pm (APEX v00.36.0) | UCO-Sensor sensor-api v0.3.0*
