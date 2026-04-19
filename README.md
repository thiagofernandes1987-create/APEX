# APEX — Autonomous Polymorphic Engineering eXpert

**Version**: v00.37.0 | **Skills**: 3,784 | **Domínios**: 52 | **DIFFs**: 132 | **Agentes**: 219 | [![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

> Framework DSL que transforma qualquer LLM em um sistema multi-agente de engenharia cognitiva com governança, execução híbrida e trilha de auditoria.

---

## O que é o APEX?

**Problema**: LLMs são poderosos, mas caóticos. Alucinam APIs, simulam execução sem aviso, misturam raciocínio com fabricação e não mantêm estado entre turnos.

**Solução APEX**: Um sistema de regras, schemas e agentes especializados que age como um *sistema operacional cognitivo* sobre o LLM — sem alterar o modelo, apenas orquestrando como ele pensa.

```
Sem APEX:  User → LLM → Resposta (black-box, sem auditoria)

Com APEX:  User → [Boot STEP_0] → [Detecção de Runtime] → [Modo Cognitivo]
                   → [Agentes Especializados] → [UCO Gate] → [Auditoria] → Resposta Verificada
```

**Para quem**: Engenheiros que precisam de outputs verificáveis (não apenas plausíveis), equipes usando múltiplos LLMs (Claude, GPT-4o, Gemini, DeepSeek) com comportamento consistente, projetos que exigem separação explícita entre execução real e simulação.

---

## Quick Start

**Para Humanos**:
```bash
git clone https://github.com/thiagofernandes1987-create/APEX.git
# Leia APEX_CREATION_GUIDE.md para criar artefatos
# Navegue skills/ — biblioteca com 3,784 skills em 52 domínios
# Veja diffs/ para entender a evolução histórica (132 DIFFs)
```

**Para LLMs** (cole no system prompt ou contexto inicial):
1. Leia: `README.md` (você está aqui)
2. Leia: `INDEX.md` (domain_map completo em YAML legível por máquina)
3. Leia: `meta/llm_compat.yaml` (instruções específicas por LLM)
4. Carregue: `apex_boot/apex_v00_37_0_master_full.txt` (system prompt completo — 20,173 linhas, 132 DIFFs)
5. Verifique: `apex_state.yaml` (estado persistente — versão, OPP atual, métricas do repo)
6. Qualquer skill: `skills/{dominio}/{skill}/SKILL.md` (≤3 passos via INDEX.md)

---

## Boot Verification (STEP_0) — novo em v00.37.0

O boot agora exige verificação explícita antes de liberar STEP_1:

```
[BOOT_VERIFIED: {hash_8chars} | lines: 20173 | version: v00.37.0]
```

- **Hash** = primeiros 8 chars do SHA-256 do boot file carregado
- Se hash ausente no output de STEP_0: `boot_verified: false` → STEP_1 bloqueado
- Estado rastreado em `apex_state.yaml` → campo `boot_verified`

---

## Estrutura do Repositório

```
APEX/
├── README.md                               ← Onboarding 5 minutos (você está aqui)
├── INDEX.md                                ← Auto-gerado via tools/generate_index.py
├── APEX_CREATION_GUIDE.md                  ← Guia canônico: schemas, templates, quality gates
├── INTAKE_WORKFLOW.md                      ← Pipeline de ingestão de repositórios externos
├── apex_state.yaml                         ← Estado persistente legível por máquina (OPP-160)
│
├── apex_boot/
│   └── apex_v00_37_0_master_full.txt       ← System prompt completo (20,173 linhas)
│
├── agents/                                 ← 219 agentes especializados
│   ├── architect/                          ← Decisões de arquitetura de sistema
│   ├── engineer/                           ← Implementação e código
│   ├── researcher/                         ← Análise e síntese de informação
│   ├── scientist_agent/                    ← Descoberta científica e simulação
│   ├── theorist/                           ← Raciocínio abstrato e formal
│   ├── critic/                             ← Revisão crítica e anti-patterns
│   ├── pmi_pm/                             ← Gestão de projetos (enforcement obrigatório v00.37.0)
│   ├── programme_director/                 ← Coordenação de programas
│   ├── diff_governance/                    ← Governança de OPPs e DIFFs
│   ├── bayesian_curator/                   ← Curadoria probabilística
│   ├── meta_learning_agent/                ← Meta-aprendizado
│   ├── meta_reasoning/                     ← Raciocínio sobre raciocínio
│   ├── event_observer/                     ← Observação de eventos de sistema
│   ├── anchor_destroyer/                   ← Remoção de vieses de ancoragem
│   ├── community-awesome/                  ← Agentes awesome-claude (OPP-153)
│   ├── community-subagents/                ← 163 sub-agentes de comunidade (OPP-153/155)
│   └── cs_cs_*/                            ← 41 agentes CS persona (OPP-154/156)
│       ├── cs_cs_ceo_advisor/
│       ├── cs_cs_cto_advisor/
│       ├── cs_cs_product_manager/
│       ├── cs_cs_engineering_lead/
│       ├── cs_cs_content_strategist/
│       ├── cs_cs_financial_analyst/
│       └── ... (35 mais)
│
├── algorithms/                             ← 40+ implementações algorítmicas
│   ├── uco/
│   │   ├── universal_code_optimizer_v4.py  ← UCO v4: 4,152 linhas
│   │   └── UCO_API_SURFACE.yaml            ← API canônica (4 métodos públicos)
│   ├── uco-sensor/                         ← UCO-Sensor v0.5.0
│   │   ├── sensor-api/                     ← REST API: 19 endpoints, 156 testes, M1–M8
│   │   │   ├── api/server.py               ← HTTP server (stdlib-only, zero deps extra)
│   │   │   ├── apex_integration/           ← EventBus + Connector + 8 templates APEX
│   │   │   ├── sensor_core/uco_bridge.py   ← Extrai 9 canais UCO v4
│   │   │   ├── sensor_storage/             ← SnapshotStore SQLite + baseline + z-score
│   │   │   ├── scan/                       ← RepoScanner + GitHistoryScanner
│   │   │   ├── report/                     ← Relatório HTML standalone + badges SVG
│   │   │   ├── lang_adapters/              ← Python, JS/TS, Java, Go
│   │   │   ├── demo/demo_full.py           ← Demo E2E 8 steps (< 2s)
│   │   │   ├── tests/test_marco1..8.py     ← 156 testes (M1 ANALISAR → M8 ENTREGAR)
│   │   │   ├── Dockerfile                  ← Multi-stage Python 3.11-slim
│   │   │   ├── docker-compose.yml          ← Stack dev/prod + perfil cron
│   │   │   └── pyproject.toml              ← PEP 517/518, entry point: uco-sensor
│   │   └── frequency-engine/               ← FrequencyEngine: FFT + Hurst + PCI
│   ├── optimization/
│   ├── anthropic-cli/
│   ├── anthropic-sdk-ruby/
│   ├── claude-agent-sdk/
│   ├── claude-code-cli/
│   ├── mcp-typescript-sdk/
│   ├── mcp-dotnet-sdk/
│   ├── github-mcp-server/
│   ├── playwright-mcp/
│   ├── awesome-claude-code/
│   ├── awesome-claude-skills/
│   ├── claude-cookbooks/
│   └── ... (26+ mais)
│
├── skills/                                 ← 3,784 skills | 52 domínios | 3,778 adotadas
│   ├── engineering/
│   │   ├── engineering_frontend/
│   │   ├── engineering_backend/
│   │   ├── engineering_api/
│   │   ├── engineering_devops/
│   │   ├── engineering_database/
│   │   ├── engineering_testing/
│   │   ├── engineering_security/
│   │   ├── engineering_cloud_aws/
│   │   ├── engineering_cloud_gcp/
│   │   ├── engineering_cloud_azure/
│   │   ├── engineering_mobile/
│   │   ├── engineering_git/
│   │   ├── engineering_cli/
│   │   └── engineering_agentops/
│   ├── ai_ml/
│   │   ├── ai_ml_agents/
│   │   ├── ai_ml_llm/
│   │   └── ai_ml_ml/
│   ├── business/
│   ├── data/data-science/
│   ├── marketing/
│   ├── legal/
│   ├── finance/
│   ├── mathematics/
│   ├── design/
│   ├── security/
│   ├── science/science_research/
│   ├── healthcare/
│   ├── product-management/
│   ├── knowledge-management/
│   ├── customer-support/
│   ├── anthropic-official/
│   ├── anthropic-skills/
│   ├── apex_internals/
│   ├── web3/
│   ├── integrations/
│   └── ... (34+ mais domínios)
│
├── diffs/
│   ├── v00_33_0/                           ← OPPs 1–92: base pública
│   ├── v00_34_0/                           ← OPPs 93–110: normalização de schemas
│   ├── v00_35_0/                           ← OPPs 111–119: quality gates + FMEA
│   └── v00_36_0/                           ← OPPs 120–132: skill_normalizer + SR_42–SR_45
│
├── integrations/
│   ├── mcp-servers/
│   ├── mcp-reference-servers/
│   ├── engineering-mcp/
│   ├── legal-mcp/
│   ├── marketing-mcp/
│   ├── github-mcp-server/
│   ├── playwright-mcp/
│   ├── science-physics-mcp/
│   ├── claude-commands/
│   ├── plugins/ + connectors/ + external-plugins/
│   └── ... (8+ mais)
│
├── meta/
│   ├── llm_compat.yaml                     ← Compatibilidade LLM (Claude/GPT/Gemini/DeepSeek/Llama)
│   ├── output_integrity_checker.yaml       ← Validador pós-output (OPP-134)
│   └── anchors.yaml                        ← Taxonomia para attraction_engine
│
└── tools/
    ├── generate_index.py                   ← Auto-gera INDEX.md
    └── commands/
```

---

## Modos Cognitivos

Selecionados automaticamente com base na complexidade detectada:

| Modo | Agentes | Latência | Caso de Uso |
|------|---------|----------|-------------|
| EXPRESS | 1 | ~2s | Perguntas triviais |
| FAST | 2–3 | ~5s | Veredictos rápidos |
| CLARIFY | 3 | ~8s | Escopo ambíguo |
| DEEP | 4–5 | ~15s | Análise estruturada |
| RESEARCH | 6–8 | ~30s | Profundidade máxima |
| SCIENTIFIC | 8 | ~60s | Descoberta/simulação |
| FOGGY | 5 | ~20s | Contexto fragmentado |

---

## Compatibilidade com LLMs

| LLM | Nível | Python Sandbox | GitHub | ForgeSkills | Notas Críticas |
|-----|-------|---------------|--------|-------------|----------------|
| Claude Code | FULL | Bash nativo | MCP/git | git clone | Referência canônica |
| GPT-4o | PARTIAL | Code Interpreter | raw URLs | urllib | sqlite3 indisponível |
| Gemini | PARTIAL | tool_code | Grounding | urllib | sympy indisponível |
| DeepSeek | PARTIAL | @Sandbox obrigatório | @Sandbox | urllib | Ver avisos críticos abaixo |
| Llama/Local | MINIMAL | Indisponível | Indisponível | Paste manual | Apenas LLM_BEHAVIOR |

**Avisos críticos DeepSeek** (falhas em produção documentadas):
- Sempre prefixe com `@Sandbox` e `@Numpy`
- `uco.gate()` **NÃO existe** (método alucinado); use `uco.analyze()` + threshold manual
- Hashes SHA-256 gerados sem execução real são descritivos, não verificáveis
- Ver `meta/llm_compat.yaml` → `deepseek` → `critical_warnings`

---

## UCO — Universal Code Optimizer v4

Analisa e otimiza código com métricas Halstead, CFG, complexidade ciclomática, detecção de código morto e duplicatas.

**API Pública** — exatamente 4 métodos (nenhum outro existe):

```python
uco = UniversalCodeOptimizer()

result = uco.analyze(code)           # H, bugs, complexity, score, dead_code, duplicates
result = uco.quick_optimize(code)    # optimized_code, score_before, score_after (sem numpy)
result = uco.optimize_fast(code)     # optimized_code, improvement_pct (Simulated Annealing)
result = uco.optimize(code)          # Full HMC — requer numpy
```

**Padrão correto de UCO gate** (NÃO use `uco.gate()` — não existe):

```python
result = uco.analyze(code)
THRESHOLDS = {"EXPRESS": 40, "FAST": 55, "DEEP": 70, "SCIENTIFIC": 85}
gate_pass = result['score'] >= THRESHOLDS[cognitive_mode] and result['bugs'] < 0.1
```

Ver: `algorithms/uco/UCO_API_SURFACE.yaml`

---

## UCO-Sensor v0.5.0

API REST de análise espectral de qualidade de código — sensor cognitivo nativo do APEX (M1–M8 completos).

**9 Canais UCO monitorados**:

| Canal | Símbolo | O que mede |
|-------|---------|-----------|
| Hamiltoniano UCO | **H** | Energia total — complexidade agregada |
| Cyclomatic Complexity | **CC** | Branches e caminhos lógicos |
| Infinite Loop Risk | **ILR** | While True, recursão sem base case |
| DSM Density | **DSM** | Acoplamento entre módulos |
| DSM Cyclic Ratio | **DSM_c** | Ciclos de dependência |
| Dependency Instability | **DI** | Instabilidade da interface |
| Syntactic Dead Code | **SDC** | Código nunca executado |
| Duplicate Block Count | **DBC** | Blocos duplicados |
| Halstead Bug Estimate | **HB** | Densidade de bugs estimada |

**Loop cognitivo bidirecional APEX ↔ UCO-Sensor**:
```
1. UCO detecta AI_CODE_BOMB em auth.service
2. Publica UCO_ANOMALY_DETECTED no APEX Event Bus
3. APEX aciona agente engineer com apex_prompt contextualizado
4. APEX envia APEX_FIX_REQUEST ao sensor via /apex/webhook
5. UCO aplica transforms e devolve fixed_code + delta_h
```

```bash
# Instalar e rodar
cd algorithms/uco-sensor/sensor-api
pip install -e ".[parsers,dev]"
python cli.py serve --port 8080

# Ou via Docker
docker compose up -d
```

Ver: `algorithms/uco-sensor/sensor-api/README.md`

---

## Skills: Schema Normalizado (OPP-133)

Todas as 3,784 skills seguem schema uniforme com normalização automática:

```yaml
skill_id: dominio.subdomain.nome
anchors: [keyword1, keyword2, ...]
cross_domain_bridges:
  - to: dominio_b.skill_x
    strength: 0.85
    reason: "por que se conectam"
input_schema: [field1, field2]
output_schema: [output1, output2]
what_if_fails: "fallback explícito"
synergy_map:
  - type: agent|diff|skill
    ref: artifact_name
    benefit: "como potencializa"
security:
  - risk: "descrição do risco"
    mitigation: "como mitigar"
tier: ADAPTED               # CORE | ADAPTED | COMMUNITY | IMPORTED
```

**Navegar skills**: `INDEX.md` → `domain_map` → caminho direto para `SKILL.md`

---

## Regras de Segurança Invioláveis

| Regra | O que proíbe / exige |
|-------|----------------------|
| SR_37 | Scan AST obrigatório antes de qualquer import externo |
| SR_38 | Isolamento de contexto entre agentes paralelos |
| SR_39 | Outputs simulados devem ser marcados `[SIMULATED]` |
| SR_40 | Compliance check em todos os artefatos |
| SR_41 | Sem paths relativos em imports de skills |
| SR_42 | Verificação SHA-256 em todos os ForgeSkills (OPP-125) |
| SR_43 | Gate de aprovação por cognitive_mode antes de outputs irreversíveis |
| SR_44 | FMEA completa em cada OPP antes de aprovação |
| SR_45 | Ghost dependency blocker — sem imports de módulos não declarados |

---

## Integridade de Output (OPP-134)

O módulo `output_integrity_checker` verifica automaticamente padrões de alucinação:

| Padrão Detectado | Ação se Sem Evidência |
|------------------|----------------------|
| `[UCO_GATE_PASS]` sem código Python | → `[UCO_GATE_PASS: UNVERIFIED]` |
| `[SANDBOX_EXECUTED]` sem bloco executável | → `[SIMULATED: marcador incorreto]` |
| `sha256:nome_descritivo` (< 64 hex chars) | → `[PLACEHOLDER_HASH]` |
| `uco.gate()` ou método inexistente | → `[UCO_API_HALLUCINATION]` |
| Path `frontend/` em vez de `engineering_frontend/` | → `[PATH_WARNING]` |

---

## Criar Novos Artefatos

Ver `APEX_CREATION_GUIDE.md`:
- Templates copy-paste para skills, agentes, OPPs, algoritmos
- Quality gates: SkillQualityBar (6 checks), AgentQualityBar (8 checks), OPPQualityBar (7 checks)
- 20+ anti-patterns com exemplos
- Padrões de segurança contra injection e ghost dependencies

---

## Histórico de Versões

| Versão | DIFFs | Skills | Agentes | Destaques |
|--------|-------|--------|---------|-----------|
| **v00.37.0** | **132** | **3,784** | **219** | community-subagents 163 (OPP-153/155), CS persona agents 41 (OPP-154/156), boot verification STEP_0 (OPP-157), pmi_pm enforcement gate (OPP-158), UCO runtime digest (OPP-159), apex_state.yaml machine-readable (OPP-160), UCO-Sensor v0.5.0 M1–M8 (156 testes) |
| v00.36.0 | 127 | 2,624 | 19 | SR_42–SR_45, skill_normalizer automático (OPP-133), output_integrity_checker (OPP-134), UCO API surface canônica, perfil crítico DeepSeek |
| v00.35.0 | 119 | — | 19 | APEX_CREATION_GUIDE.md, SkillQualityBar/AgentQualityBar/OPPQualityBar, FMEA obrigatório em OPPs |
| v00.34.0 | 110 | — | 19 | Normalização de schemas, expansão de domínios, quality gates iniciais |
| v00.33.0 | 92 | — | 19 | Base pública: 50 domínios, 19 agentes, intake workflow, SR_37–SR_41 |

---

## Quick Links

| Recurso | Arquivo |
|---------|---------|
| System prompt completo | `apex_boot/apex_v00_37_0_master_full.txt` |
| Estado persistente (máquina) | `apex_state.yaml` |
| Guia de criação de artefatos | `APEX_CREATION_GUIDE.md` |
| Compatibilidade LLM | `meta/llm_compat.yaml` |
| UCO API canônica (4 métodos) | `algorithms/uco/UCO_API_SURFACE.yaml` |
| UCO-Sensor REST API (19 endpoints) | `algorithms/uco-sensor/sensor-api/README.md` |
| Validador de integridade de output | `meta/output_integrity_checker.yaml` |
| Índice de skills (gerado) | `INDEX.md` |
| Workflow de ingestão | `INTAKE_WORKFLOW.md` |
| Gerador de INDEX.md | `tools/generate_index.py` |

**Repositório**: https://github.com/thiagofernandes1987-create/APEX  
**Raw base**: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/  
**Whitelist**: APEX incluído em `trusted_domains` desde v00.33.0 (OPP-104)

---

## Licença

**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**

- Uso livre: pesquisa, educação, projetos pessoais, open source não-comercial
- Uso comercial: requer permissão explícita do autor

Ver `LICENSE` | [Texto completo CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)
