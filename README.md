# APEX — Autonomous Polymorphic Engineering eXpert

**Version**: v00.36.0 | **Skills**: 2.624 | **Domínios**: 50 | **DIFFs**: 127 | [![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by-nc/4.0/)

> Um framework DSL que transforma qualquer LLM em um sistema de engenharia cognitiva multi-agente — com governança, execução híbrida e trilha de auditoria.

---

## O que é o APEX? (5 minutos)

**Problema**: LLMs são poderosos mas caóticos. Alucinam APIs, simulam execução sem avisar, misturam raciocínio com fabricação, e não mantêm estado de runtime entre turnos.

**Solução APEX**: Um sistema de regras, schemas e agentes especializados que age como *sistema operacional cognitivo* sobre o LLM — sem mudar o modelo, só orquestrando como ele pensa.

```
Sem APEX:  Usuário → LLM → Resposta (caixa-preta, sem auditoria)

Com APEX:  Usuário → [Boot] → [Detecção de Runtime] → [Modo Cognitivo]
                   → [Agentes Especializados] → [UCO Gate] → [Auditoria] → Resposta verificada
```

**Para quem é:**
- Engenheiros que precisam de outputs verificáveis, não apenas plausíveis
- Times usando múltiplos LLMs (Claude, GPT-4o, Gemini, DeepSeek) com comportamento consistente
- Projetos que exigem separação explícita entre execução real e simulação

---

## Início Rápido

### Para Humanos

```bash
git clone https://github.com/thiagofernandes1987-create/APEX.git

# Leia APEX_CREATION_GUIDE.md para criar artefatos
# Navegue skills/ para ver a biblioteca de 2.624 skills
# Veja diffs/ para entender o histórico de evolução
```

### Para LLMs (cole no system prompt ou contexto inicial)

```
1. Leia: README.md            → contexto geral (você está aqui)
2. Leia: INDEX.md             → domain_map completo (machine-parseable YAML)
3. Leia: meta/llm_compat.yaml → instruções específicas para seu runtime
4. Carregue: apex_boot/apex_v00_36_0_master_full.txt → system prompt completo (18.516 linhas, 127 DIFFs)
5. Qualquer skill: skills/{domínio}/{skill}/SKILL.md (≤ 3 passos via INDEX.md)
```

---

## Estrutura do Repositório

```
APEX/
├── README.md                          ← Onboarding 5 minutos (você está aqui)
├── INDEX.md                           ← Hub gerado automaticamente via tools/generate_index.py
├── APEX_CREATION_GUIDE.md             ← Guia canônico: schemas, templates, quality gates, anti-patterns
├── INTAKE_WORKFLOW.md                 ← Pipeline de ingestão de repositórios externos
│
├── apex_boot/
│   └── apex_v00_36_0_master_full.txt  ← System prompt completo (18.516 linhas)
│
├── skills/                            ← 2.624 skills em 50 domínios normalizados (OPP-133)
│   ├── engineering_frontend/          ← ATENÇÃO: nome canônico é "engineering_frontend", não "frontend"
│   ├── engineering_backend/
│   ├── marketing/
│   ├── legal/
│   ├── finance/
│   ├── mathematics/
│   └── ...                            ← 44 outros domínios
│
├── agents/                            ← 19 agentes especializados com schemas completos
│
├── algorithms/
│   └── uco/
│       ├── universal_code_optimizer_v4.py  ← UCO: 4.152 linhas
│       └── UCO_API_SURFACE.yaml            ← API canônica (4 métodos públicos)
│
├── diffs/
│   └── v00_36_0/                      ← OPP-125–134, skill_normalizer, normalization_report
│
├── meta/
│   ├── llm_compat.yaml                ← Compatibilidade por LLM (Claude/GPT-4o/Gemini/DeepSeek/Llama)
│   ├── output_integrity_checker.yaml  ← Validador pós-output: detecta claims sem evidência (OPP-134)
│   └── anchors.yaml                   ← Taxonomia de âncoras para attraction_engine
│
└── tools/
    └── generate_index.py              ← Gerador automático do INDEX.md a partir de skills/
```

---

## Modos Cognitivos

Seleção automática com base na complexidade detectada:

| Modo | Agentes | Latência | Quando Usar |
|------|---------|----------|-------------|
| EXPRESS | 1 | ~2s | Perguntas triviais, respostas diretas |
| FAST | 2–3 | ~5s | Veredicto rápido, problemas conhecidos |
| CLARIFY | 3 | ~8s | Escopo ambíguo, definições vagas |
| DEEP | 4–5 | ~15s | Análise estruturada, múltiplos ângulos |
| RESEARCH | 6–8 | ~30s | Máxima profundidade, exaustivo |
| SCIENTIFIC | 8 | ~60s | Descoberta, simulação, verificação simbólica |
| FOGGY | 5 | ~20s | Contexto fragmentado, incerteza alta |

---

## Compatibilidade por LLM

| LLM | Nível | Python Sandbox | GitHub | ForgeSkills | Notas Críticas |
|-----|-------|---------------|--------|-------------|----------------|
| Claude Code | FULL | Bash nativo | MCP/git | git clone | Referência canônica |
| GPT-4o | PARTIAL | Code Interpreter | raw URLs | urllib | sqlite3 indisponível |
| Gemini | PARTIAL | tool_code | Grounding | urllib | sympy indisponível |
| DeepSeek | PARTIAL | @Sandbox obrigatório | @Sandbox | urllib | Ver critical_warnings abaixo |
| Llama/Local | MINIMAL | Indisponível | Indisponível | Paste manual | LLM_BEHAVIOR only |

**DeepSeek — avisos críticos** (baseados em falhas observadas em produção):
- Sempre prefixar com `@Sandbox` e `@Numpy` — sem eles, o modelo simula sem avisar
- `uco.gate()` **não existe** — método alucinado; usar `uco.analyze()` + threshold manual
- Hashes SHA-256 gerados sem execução real são descritivos, não verificáveis
- Ver [`meta/llm_compat.yaml`](meta/llm_compat.yaml) → seção `deepseek` → `critical_warnings`

---

## UCO — Universal Code Optimizer

Analisa e otimiza código com métricas Halstead, CFG, cyclomatic complexity e dead code detection.

**API pública** — exatamente 4 métodos, nenhum outro existe:

```python
uco = UniversalCodeOptimizer()

result = uco.analyze(code)           # H, bugs, complexity, score, dead_code, duplicates
result = uco.quick_optimize(code)    # optimized_code, score_before, score_after (sem numpy)
result = uco.optimize_fast(code)     # optimized_code, improvement_pct (Simulated Annealing)
result = uco.optimize(code)          # HMC completo — requer numpy
```

**Padrão correto de UCO gate** (não usar `uco.gate()` — não existe):

```python
result = uco.analyze(code)
THRESHOLDS = {"EXPRESS": 40, "FAST": 55, "DEEP": 70, "SCIENTIFIC": 85}
gate_pass = result['score'] >= THRESHOLDS[cognitive_mode] and result['bugs'] < 0.1
```

Ver: [`algorithms/uco/UCO_API_SURFACE.yaml`](algorithms/uco/UCO_API_SURFACE.yaml)

---

## Skills: Schema Normalizado

Todas as 2.624 skills seguem schema uniforme (OPP-133 — normalização automática):

```yaml
skill_id: dominio.subdomain.nome
anchors: [keyword1, keyword2, ...]
cross_domain_bridges:
  - to: dominio_b.skill_x
    strength: 0.85          # 0.0–1.0
    reason: "por que se conectam"
input_schema: [campo1, campo2]
output_schema: [saida1, saida2]
what_if_fails: "fallback explícito — o que fazer se esta skill falhar"
synergy_map:
  - type: agent|diff|skill
    ref: nome_do_artefato
    benefit: "como potencializa"
security:
  - risk: "descrição do risco"
    mitigation: "como mitigar"
tier: ADAPTED               # CORE | ADAPTED | COMMUNITY | IMPORTED
```

**Navegar skills**: `INDEX.md` → `domain_map` → path direto para `SKILL.md`

---

## Regras de Segurança Invioláveis

| Regra | O que proíbe / exige |
|-------|---------------------|
| SR_37 | AST scan obrigatório antes de qualquer import externo |
| SR_42 | SHA-256 verification em todo ForgeSkills (OPP-125) |
| SR_43 | Approval gate por cognitive_mode antes de outputs irreversíveis |
| SR_44 | FMEA completo em todo OPP antes de aprovação |
| SR_45 | Ghost dependency blocker — sem imports de módulos não declarados |

---

## Integridade de Output

O módulo `output_integrity_checker` (OPP-134) verifica automaticamente:

| Padrão detectado | Ação se sem evidência |
|------------------|-----------------------|
| `[UCO_GATE_PASS]` sem código Python acima | → `[UCO_GATE_PASS: UNVERIFIED]` |
| `[SANDBOX_EXECUTED]` sem bloco executável | → `[SIMULATED: marcador incorreto]` |
| `sha256:nome_descritivo` (< 64 hex chars) | → `[PLACEHOLDER_HASH]` |
| `uco.gate()` ou método inexistente | → `[UCO_API_HALLUCINATION]` |
| Path `frontend/` em vez de `engineering_frontend/` | → `[PATH_WARNING]` |

---

## Criar Novos Artefatos

Ver [`APEX_CREATION_GUIDE.md`](APEX_CREATION_GUIDE.md):
- Templates copy-paste para skills, agentes, OPPs, algoritmos
- Quality gates: `SkillQualityBar` (6 checks), `AgentQualityBar` (8 checks), `OPPQualityBar` (7 checks)
- 20+ anti-patterns com exemplos do que não fazer
- Padrões de segurança contra injection e ghost dependencies

---

## Histórico de Versões

| Versão | DIFFs | Destaques |
|--------|-------|-----------|
| v00.36.0 | 127 | SR_42–SR_45, skill_normalizer (2.549 skills), OPP-134 DeepSeek profile + UCO API surface + output integrity |
| v00.35.0 | 119 | APEX_CREATION_GUIDE.md, quality gates, FMEA obrigatório |
| v00.33.0 | 92 | Base pública, 50 domínios, 19 agentes, intake workflow |

---

## Links Rápidos

| Recurso | Arquivo |
|---------|---------|
| System prompt completo | [`apex_boot/apex_v00_36_0_master_full.txt`](apex_boot/apex_v00_36_0_master_full.txt) |
| Guia de criação de artefatos | [`APEX_CREATION_GUIDE.md`](APEX_CREATION_GUIDE.md) |
| Compatibilidade por LLM | [`meta/llm_compat.yaml`](meta/llm_compat.yaml) |
| API canônica do UCO | [`algorithms/uco/UCO_API_SURFACE.yaml`](algorithms/uco/UCO_API_SURFACE.yaml) |
| Validador de integridade | [`meta/output_integrity_checker.yaml`](meta/output_integrity_checker.yaml) |
| Índice de skills (gerado) | [`INDEX.md`](INDEX.md) |
| Workflow de ingestão | [`INTAKE_WORKFLOW.md`](INTAKE_WORKFLOW.md) |
| Gerador do INDEX.md | [`tools/generate_index.py`](tools/generate_index.py) |

**Repositório**: https://github.com/thiagofernandes1987-create/APEX
**Raw base**: `https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/`
**Whitelist APEX**: `trusted_domains` contém este repositório desde v00.33.0 (OPP-104)

---

## Licença

Este projeto está licenciado sob **Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**.

- **Uso livre**: pesquisa, educação, projetos pessoais, open source não-comercial
- **Uso comercial**: requer permissão explícita do autor

Ver [`LICENSE`](LICENSE) | [Texto completo CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/legalcode)
