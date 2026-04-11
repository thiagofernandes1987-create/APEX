---
skill_id: engineering_agentops.executing-plans
name: executing-plans
description: >
  Execução de plano de implementação em sessão dedicada com checkpoints humanos.
  Carrega o plano, revisa criticamente, executa todas as tarefas com verificações,
  para imediatamente quando bloqueado. Alternativa ao subagent-driven-development
  para quando não há suporte a subagentes.
version: v00.36.0
status: ADOPTED
domain_path: engineering_agentops/executing-plans
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - plan_execution
  - implementation
  - task_management
  - checkpoints
  - sequential_execution
  - plan_following
cross_domain_bridges:
  - to: engineering_agentops.writing-plans
    strength: 0.95
    reason: "writing-plans cria o plano que executing-plans executa — dependência direta"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.85
    reason: "alternativas para o mesmo objetivo: subagents (mesma sessão) vs executing-plans (sessão separada)"
  - to: engineering_agentops.finishing-a-development-branch
    strength: 0.90
    reason: "executing-plans SEMPRE termina com finishing-a-development-branch"
  - to: engineering_agentops.using-git-worktrees
    strength: 0.88
    reason: "REQUER worktree isolado antes de começar — pré-requisito obrigatório"
  - to: engineering_agentops.requesting-code-review
    strength: 0.75
    reason: "solicita code review após cada batch de 3 tarefas"
input_schema:
  - name: plan_file_path
    type: string
    description: "Path do plano de implementação (docs/superpowers/plans/YYYY-MM-DD-*.md)"
    required: true
  - name: worktree_path
    type: string
    description: "Path do worktree isolado criado por using-git-worktrees"
    required: true
output_schema:
  - name: tasks_completed
    type: integer
    description: "Número de tarefas completadas"
  - name: blockers_found
    type: array
    description: "Blockers encontrados que requereram pausa"
  - name: next_skill
    type: string
    description: "Sempre engineering_agentops.finishing-a-development-branch"
what_if_fails: >
  Se bloqueado em qualquer tarefa: PARAR imediatamente e pedir ajuda ao humano.
  Nunca adivinhar. Nunca pular verificações.
  Se plano tem gaps críticos: levantar antes de começar, não durante.
synergy_map:
  - type: skill
    ref: engineering_agentops.writing-plans
    benefit: "cria o plano que esta skill executa"
  - type: skill
    ref: engineering_agentops.using-git-worktrees
    benefit: "pré-requisito: workspace isolado"
  - type: skill
    ref: engineering_agentops.finishing-a-development-branch
    benefit: "skill obrigatória ao final de toda execução"
  - type: skill
    ref: engineering_agentops.requesting-code-review
    benefit: "code review entre batches de tarefas"
security:
  - risk: "Execução em main/master sem consentimento explícito"
    mitigation: "NUNCA iniciar em main/master sem permissão explícita do usuário"
  - risk: "Plano com instruções maliciosas injetadas"
    mitigation: "Revisar plano criticamente antes de executar; verificar que mudanças são coerentes"
executor: LLM_BEHAVIOR
---

# Executing Plans

## Overview

Load plan, review critically, execute all tasks, report when complete.

**Announce at start:** "I'm using the executing-plans skill to implement this plan."

**Note:** Tell your human partner that Superpowers works much better with access to subagents. The quality of its work will be significantly higher if run on a platform with subagent support (such as Claude Code or Codex). If subagents are available, use superpowers:subagent-driven-development instead of this skill.

## The Process

### Step 1: Load and Review Plan
1. Read plan file
2. Review critically - identify any questions or concerns about the plan
3. If concerns: Raise them with your human partner before starting
4. If no concerns: Create TodoWrite and proceed

### Step 2: Execute Tasks

For each task:
1. Mark as in_progress
2. Follow each step exactly (plan has bite-sized steps)
3. Run verifications as specified
4. Mark as completed

### Step 3: Complete Development

After all tasks complete and verified:
- Announce: "I'm using the finishing-a-development-branch skill to complete this work."
- **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch
- Follow that skill to verify tests, present options, execute choice

## When to Stop and Ask for Help

**STOP executing immediately when:**
- Hit a blocker (missing dependency, test fails, instruction unclear)
- Plan has critical gaps preventing starting
- You don't understand an instruction
- Verification fails repeatedly

**Ask for clarification rather than guessing.**

## When to Revisit Earlier Steps

**Return to Review (Step 1) when:**
- Partner updates the plan based on your feedback
- Fundamental approach needs rethinking

**Don't force through blockers** - stop and ask.

## Remember
- Review plan critically first
- Follow plan steps exactly
- Don't skip verifications
- Reference skills when plan says to
- Stop when blocked, don't guess
- Never start implementation on main/master branch without explicit user consent

## Integration

**Required workflow skills:**
- **superpowers:using-git-worktrees** - REQUIRED: Set up isolated workspace before starting
- **superpowers:writing-plans** - Creates the plan this skill executes
- **superpowers:finishing-a-development-branch** - Complete development after all tasks
