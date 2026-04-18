---
skill_id: ai_ml.intelligent_agent_factory
name: intelligent-agent-factory
description: >
  Projeta, implementa e valida agentes LLM de ponta a ponta. Orquestra: design do
  agente → definição de skills → implementação com TDD → avaliação de performance →
  deployment com monitoramento. Cobre o gap entre ai_ml_agents (design) e
  engineering_agentops (implementação). Resultado: agente pronto para produção com
  métricas de qualidade verificadas.
version: v00.36.0
status: ADOPTED
tier: SUPER
executor: LLM_BEHAVIOR
domain_path: ai_ml/intelligent_agent_factory
risk: medium
opp: OPP-Phase4-super-skills
anchors:
  - agent_design
  - agent_factory
  - llm_agent
  - skill_creation
  - evaluation
  - benchmarking
  - deployment
  - monitoring
  - multi_agent
  - orchestration
  - production_ready
input_schema:
  - name: agent_purpose
    type: string
    description: "Objetivo e domínio de atuação do agente"
    required: true
  - name: target_llm
    type: string
    enum: [claude, gpt4o, gemini, llama, custom]
    description: "LLM alvo para o agente"
    required: false
    default: "claude"
  - name: required_tools
    type: array
    description: "Ferramentas que o agente deve ter acesso (APIs, databases, etc)"
    required: false
  - name: performance_target
    type: object
    description: "Métricas mínimas aceitáveis: accuracy, latency, cost_per_call"
    required: false
output_schema:
  - name: agent_spec
    type: object
    description: "Especificação completa do agente: skills, tools, prompts, protocols"
  - name: agent_skills
    type: array
    description: "Lista de SKILL.md gerados para o agente"
  - name: eval_results
    type: object
    description: "Resultados de avaliação: benchmark scores, edge cases, fail modes"
  - name: deployment_config
    type: object
    description: "Configuração de deployment com monitoring e alertas"
synergy_map:
  complements:
    - ai_ml_agents.agent-designer
    - engineering_agentops.writing-skills
    - engineering_agentops.brainstorming
    - ai_ml_agents.agent-workflow-designer
    - community_general.skill-tester
  cross_domain_bridges:
    - domain: engineering_agentops
      strength: 0.95
      note: "Agent factory produces agents that run in agentops pipeline"
    - domain: ai_ml_ml
      strength: 0.85
      note: "ML models can be integrated as agent tools"
    - domain: engineering_devops
      strength: 0.80
      note: "Deployment phase requires CI/CD integration"
    - domain: engineering_testing
      strength: 0.88
      note: "Eval phase uses testing skills for benchmark suite"
orchestration:
  - phase: 1
    skill: ai_ml_agents.agent-designer
    gate: "agent_spec aprovado — define type, tools, protocols, APEX schema"
    strength: 0.95
  - phase: 2
    skill: engineering_agentops.writing-skills
    gate: "SKILL.md gerado para cada capability do agente"
    strength: 0.90
  - phase: 3
    skill: engineering_agentops.brainstorming
    gate: "Cada skill complexa refinada socraticamente"
    condition: "para cada skill com ambiguidade"
    strength: 0.88
  - phase: 4
    skill: ai_ml_agents.agent-workflow-designer
    gate: "Workflow spec com edge cases mapeados"
    strength: 0.85
  - phase: 5
    skill: community_general.skill-tester
    gate: "eval_results com benchmark scores e fail modes identificados"
    strength: 0.88
security:
  level: standard
  pii: false
  approval_required: false
  note: "Agents with PII access require security.level = high and explicit approval"
what_if_fails: >
  Se agent_purpose muito vago: aplicar brainstorming socrático para refinar.
  Se performance abaixo do target: iterar sobre skills e prompts antes de deployment.
  Se eval encontrar fail modes críticos: redesenhar skill afetada antes de prosseguir.
  Se required_tools indisponível: documentar fallback no agent_spec antes de deployment.
---

# Intelligent Agent Factory — Super-Skill

Pipeline completo de criação de agentes LLM: do `agent_purpose` vago ao agente em
produção com métricas de qualidade verificadas e configuração de monitoring.

## Why This Skill Exists

O APEX tem `ai_ml_agents.agent-designer` para design e `engineering_agentops.writing-skills`
para criação de skills, mas **não existe pipeline que conecte design → skills → eval →
deployment**. O resultado é que agentes são criados sem avaliação sistemática, sem
benchmarks de qualidade e sem configuração de monitoring — chegam à produção sem evidência
de que funcionam. Esta super-skill fecha o gap `ai_ml_agents ↔ engineering_agentops`,
criando uma fábrica determinística de agentes production-ready.

## When to Use

Use esta skill quando:
- Precisar criar um novo agente LLM de qualquer domínio do zero
- Quiser garantir que o agente seja avaliado antes de chegar à produção
- Precisar de um `agent_spec` completo com APEX schema (SKILL.md para cada capability)
- O agente terá múltiplas tools ou integrações complexas

**Não use** para: modificar agente existente (use `engineering_agentops.writing-skills` diretamente),
ou exploração de capabilities (use `ai_ml_agents.agent-designer` isolado).

## What If Fails

| Fase | Falha | Ação |
|------|-------|------|
| 1 – Agent Design | Purpose vago | Aplicar brainstorming socrático até convergência |
| 2 – Writing Skills | Skill ambígua | Iterar com brainstorming (fase 3) antes de prosseguir |
| 4 – Workflow Design | Edge cases sem cobertura | Adicionar fail modes ao agent_spec |
| 5 – Evaluation | Performance abaixo do target | Iterar skills/prompts; não fazer deploy |
| 5 – Evaluation | Fail mode crítico encontrado | Redesenhar skill afetada; re-evaluar |
| Qualquer | Tool indisponível | Documentar fallback no agent_spec; não bloquear |

## Orchestration Protocol

```
PHASE 1: ai_ml_agents.agent-designer
  → Define: agent type (reactive/proactive/hybrid)
  → Define: tool set e access scope
  → Define: APEX schema (skill_id, executor, tier, anchors)
  → Output: agent_spec
  → GATE: agent_spec aprovado

PHASE 2: engineering_agentops.writing-skills
  → Para cada capability no agent_spec:
    → Cria SKILL.md com schema APEX completo
    → Define input_schema, output_schema, what_if_fails
  → Output: agent_skills[]
  → GATE: todos os SKILL.md gerados

PHASE 3: engineering_agentops.brainstorming [se skill complexa]
  → Refina design da skill com processo socrático
  → Obtém aprovação antes de implementar
  → Loop: repetir por skill com ambiguidade

PHASE 4: ai_ml_agents.agent-workflow-designer
  → Mapeia fluxos de decisão do agente
  → Identifica edge cases e fail modes
  → Gera workflow spec com decision trees
  → GATE: todos os edge cases com handling documentado

PHASE 5: community_general.skill-tester
  → Roda eval suite com casos de teste
  → Mede: accuracy, latency, cost_per_call
  → Identifica: fail modes reais vs documentados
  → Output: eval_results + deployment_config
  → GATE: performance_target atingido
```

## Agent Taxonomy

| agent_type | Executor | Tier | Uso típico |
|------------|---------|------|-----------|
| reactive | LLM_BEHAVIOR | 1-2 | Responde a eventos; sem memória cross-session |
| proactive | LLM_BEHAVIOR | 1 | Monitora e age sem trigger explícito |
| hybrid | HYBRID | 1-2 | Combina LLM reasoning com code execution |
| code_agent | SANDBOX_CODE | 2-3 | Execução de código com LLM como planner |

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — fecha gap ai_ml_agents ↔ engineering_agentops
