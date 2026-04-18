---
skill_id: engineering_agentops.full_dev_cycle
name: full-dev-cycle
description: >
  Orquestra o ciclo completo de desenvolvimento de software: brainstorming →
  design aprovado → plano de implementação → execução com subagentes → TDD →
  verificação com evidência → finishing branch → code review. Pipeline
  determinístico de 8 fases com gates obrigatórios entre cada fase. Resolve
  qualquer feature request do primeiro vague idea ao PR pronto para merge.
version: v00.36.0
status: ADOPTED
tier: SUPER
executor: LLM_BEHAVIOR
domain_path: engineering_agentops/full_dev_cycle
risk: safe
opp: OPP-Phase4-super-skills
anchors:
  - full_cycle
  - end_to_end_development
  - orchestration
  - pipeline
  - hard_gate
  - brainstorming
  - implementation
  - verification
  - tdd
  - code_review
  - subagent
  - planning
input_schema:
  - name: feature_request
    type: string
    description: "Ideia bruta ou feature request — pode ser completamente vago"
    required: true
  - name: project_context
    type: string
    description: "Estado do projeto (arquivos, docs, commits recentes)"
    required: false
  - name: execution_mode
    type: string
    enum: [subagent, inline]
    description: "subagent: agentes paralelos (recomendado) | inline: execução na mesma sessão"
    required: false
    default: "subagent"
output_schema:
  - name: design_doc_path
    type: string
    description: "Path do spec aprovado gerado na fase 1"
  - name: plan_file_path
    type: string
    description: "Path do plano gerado na fase 2"
  - name: pr_url
    type: string
    description: "URL do Pull Request criado ao final"
  - name: test_coverage
    type: number
    description: "Percentual de cobertura de testes do código implementado"
  - name: phases_completed
    type: array
    description: "Lista de fases completadas com timestamps"
synergy_map:
  complements:
    - engineering_agentops.brainstorming
    - engineering_agentops.writing-plans
    - engineering_agentops.subagent-driven-development
    - engineering_agentops.executing-plans
    - engineering_agentops.test-driven-development
    - engineering_agentops.verification-before-completion
    - engineering_agentops.finishing-a-development-branch
    - engineering_agentops.requesting-code-review
  cross_domain_bridges:
    - domain: engineering_testing
      strength: 0.92
      note: "TDD phase integrates directly with testing domain skills"
    - domain: engineering_git
      strength: 0.90
      note: "Finishing and PR creation rely on git skills"
    - domain: security
      strength: 0.75
      note: "Code review phase can invoke security scan"
orchestration:
  - phase: 1
    skill: engineering_agentops.brainstorming
    gate: "design_doc aprovado pelo usuário — HARD_GATE, nunca pular"
    strength: 0.98
  - phase: 2
    skill: engineering_agentops.writing-plans
    gate: "plan_file com tasks de 2-5 min gerado"
    strength: 0.95
  - phase: "3a"
    skill: engineering_agentops.subagent-driven-development
    condition: "execution_mode == subagent"
    strength: 0.92
  - phase: "3b"
    skill: engineering_agentops.executing-plans
    condition: "execution_mode == inline"
    strength: 0.90
  - phase: 4
    skill: engineering_agentops.test-driven-development
    gate: "RED-GREEN-REFACTOR por task — obrigatório"
    strength: 0.90
  - phase: 5
    skill: engineering_agentops.verification-before-completion
    gate: "evidência de execução obrigatória antes de qualquer claim"
    strength: 0.95
  - phase: 6
    skill: engineering_agentops.finishing-a-development-branch
    gate: "suíte completa de testes passa antes do PR"
    strength: 0.90
  - phase: 7
    skill: engineering_agentops.requesting-code-review
    gate: "PR com contexto completo criado"
    strength: 0.85
security:
  level: standard
  pii: false
  approval_required: false
what_if_fails: >
  Fase 1 (brainstorming): iterar até design aprovado. Nunca pular para fase 2 sem aprovação.
  Fase 2 (writing-plans): se spec ambíguo, voltar para fase 1.
  Fase 3 (execução): se bloqueado, PARAR e pedir ajuda humana — nunca adivinhar.
  Fase 4 (TDD): se sem teste, escrever teste antes de qualquer código novo.
  Fase 5 (verificação): sem evidência = sem claim. NUNCA declarar "provavelmente funciona".
  Fase 6 (finishing): sempre rodar suíte completa de testes antes do PR.
---

# Full Dev Cycle — Super-Skill

Pipeline determinístico de 8 fases que leva qualquer feature request do `vague idea` ao
`PR pronto para merge`, com gates de qualidade verificáveis entre cada fase.

## Why This Skill Exists

O `engineering_agentops` tem o melhor pipeline end-to-end nativo do repo APEX —
brainstorming → writing-plans → subagent-driven-development → TDD →
verification-before-completion → finishing → code-review. Porém, nenhuma skill existente
**orquestra** esse pipeline completo; cada skill é invocada isoladamente, perdendo
os gates e a sequência determinística. Esta super-skill resolve isso: é o orquestrador
declarativo que garante que **nenhum código chega ao PR sem passar pelos 8 gates**.

## When to Use

Use esta skill quando:
- Receber qualquer feature request, bug fix ou refactoring task (vago ou detalhado)
- Quiser garantir que todo o ciclo de qualidade (design → test → review) seja executado
- Operar em modo subagente para paralelizar tasks independentes
- Precisar de um pipeline auditável com timestamps por fase (`phases_completed`)

**Não use** para: hotfixes urgentes sem gate (use `verification-before-completion` diretamente),
ou exploração exploratória sem output definido (use `brainstorming` isolado).

## What If Fails

| Fase | Falha | Ação |
|------|-------|------|
| 1 – Brainstorming | Design não converge | Iterar socrático; nunca avançar sem aprovação explícita |
| 2 – Writing Plans | Spec ambíguo | Retornar à fase 1; nunca criar plan de spec incompleto |
| 3 – Execução | Bloqueado | PARAR imediatamente; pedir ajuda humana; nunca adivinhar |
| 4 – TDD | Sem cobertura | Escrever teste antes de qualquer código — RED obrigatório |
| 5 – Verificação | Sem evidência | Nunca declarar "provavelmente funciona"; executar e citar output |
| 6 – Finishing | Teste falha | Não criar PR; corrigir e re-verificar |
| 7 – Code Review | PR bloqueado | Adereçar todos os comments antes de merge |

## Orchestration Protocol

```
PHASE 1: brainstorming
  → Input: feature_request + project_context
  → Output: design_doc_path
  → HARD_GATE: usuário aprova design antes de prosseguir

PHASE 2: writing-plans
  → Input: design_doc_path
  → Output: plan_file_path (tasks de 2-5 min cada)
  → GATE: plan_file_path existe e não está vazio

PHASE 3 [subagent]: subagent-driven-development
  → Input: plan_file_path
  → Dispatch: 1 subagente por task independente
  → GATE: todos os subagentes retornaram com sucesso

PHASE 3 [inline]: executing-plans
  → Input: plan_file_path
  → Executa task a task na mesma sessão

PHASE 4: test-driven-development (por task)
  → RED: escrever failing test → GREEN: mínimo para passar → REFACTOR
  → GATE: test_coverage >= projeto_baseline

PHASE 5: verification-before-completion (por claim)
  → Executar comando → ler output completo → citar evidência
  → GATE: nenhum claim sem evidência de execução

PHASE 6: finishing-a-development-branch
  → Rodar suíte completa → formatar commits → criar PR
  → GATE: PR url retornado

PHASE 7: requesting-code-review
  → Contexto do PR + checklist → solicitar review
  → Output: phases_completed[] com timestamps
```

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — super-skill compositora do pipeline engineering_agentops
