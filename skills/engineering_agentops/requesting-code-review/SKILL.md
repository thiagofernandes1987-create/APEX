---
skill_id: engineering_agentops.requesting-code-review
name: requesting-code-review
description: "Review — Despacha subagente code-reviewer com contexto preciso e isolado — nunca herda"
  Despacha subagente code-reviewer com contexto preciso e isolado — nunca herda
  histórico da sessão. Solicita review após cada tarefa em subagent-driven-development,
  após features maiores, e antes de merge. Usa SHAs git para delimitar o escopo exato.
version: v00.36.0
status: ADOPTED
domain_path: engineering_agentops/requesting-code-review
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - code_review
  - review_request
  - subagent_review
  - git_diff
  - quality_gate
  - pre_merge
cross_domain_bridges:
  - to: engineering_agentops.receiving-code-review
    strength: 0.95
    reason: "par simétrico: requesting despacha, receiving processa o feedback retornado"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.90
    reason: "code review é etapa obrigatória após cada tarefa do pipeline SDD"
  - to: engineering_agentops.executing-plans
    strength: 0.80
    reason: "review após cada batch de 3 tarefas"
  - to: engineering_agentops.finishing-a-development-branch
    strength: 0.75
    reason: "review final antes do merge/PR"
  - to: engineering_agentops.dispatching-parallel-agents
    strength: 0.70
    reason: "reviews paralelas por área de código usando parallel dispatch"
input_schema:
  - name: what_was_implemented
    type: string
    description: "O que foi construído nesta tarefa"
    required: true
  - name: plan_or_requirements
    type: string
    description: "O que deveria ter sido feito (spec/plan de referência)"
    required: true
  - name: base_sha
    type: string
    description: "Commit SHA inicial (antes das mudanças)"
    required: true
  - name: head_sha
    type: string
    description: "Commit SHA final (após as mudanças)"
    required: true
  - name: description
    type: string
    description: "Resumo de 1-2 frases do que mudou"
    required: false
output_schema:
  - name: review_result
    type: object
    description: "Strengths, Issues (Critical/Important/Minor), Assessment"
  - name: blocking_issues
    type: array
    description: "Issues críticos que impedem progressão"
  - name: assessment
    type: string
    description: "APPROVED | NEEDS_FIXES | BLOCKED"
what_if_fails: >
  Se subagente reviewer não disponível: fazer auto-review com checklist da spec.
  Se reviewer retorna feedback inválido tecnicamente: usar receiving-code-review para avaliar pushback.
  Se Critical issues: NUNCA prosseguir antes de resolver.
synergy_map:
  - type: skill
    ref: engineering_agentops.receiving-code-review
    benefit: "processa o feedback retornado pelo reviewer"
  - type: skill
    ref: engineering_agentops.subagent-driven-development
    benefit: "integrado como etapa obrigatória do pipeline"
  - type: skill
    ref: engineering_agentops.dispatching-parallel-agents
    benefit: "pode paralelizar reviews por área"
security:
  - risk: "Reviewer com contexto insuficiente aprova código inseguro"
    mitigation: "Sempre incluir contexto de segurança no prompt do reviewer — nunca assumir que ele conhece o sistema"
  - risk: "SHA incorreto delimita escopo errado e review não cobre as mudanças reais"
    mitigation: "Verificar git diff entre BASE_SHA e HEAD_SHA antes de despachar"
executor: LLM_BEHAVIOR
---

# Requesting Code Review

Dispatch superpowers:code-reviewer subagent to catch issues before they cascade. The reviewer gets precisely crafted context for evaluation — never your session's history. This keeps the reviewer focused on the work product, not your thought process, and preserves your own context for continued work.

**Core principle:** Review early, review often.

## When to Request Review

**Mandatory:**
- After each task in subagent-driven development
- After completing major feature
- Before merge to main

**Optional but valuable:**
- When stuck (fresh perspective)
- Before refactoring (baseline check)
- After fixing complex bug

## How to Request

**1. Get git SHAs:**
```bash
BASE_SHA=$(git rev-parse HEAD~1)  # or origin/main
HEAD_SHA=$(git rev-parse HEAD)
```

**2. Dispatch code-reviewer subagent:**

Use Task tool with superpowers:code-reviewer type, fill template at `code-reviewer.md`

**Placeholders:**
- `{WHAT_WAS_IMPLEMENTED}` - What you just built
- `{PLAN_OR_REQUIREMENTS}` - What it should do
- `{BASE_SHA}` - Starting commit
- `{HEAD_SHA}` - Ending commit
- `{DESCRIPTION}` - Brief summary

**3. Act on feedback:**
- Fix Critical issues immediately
- Fix Important issues before proceeding
- Note Minor issues for later
- Push back if reviewer is wrong (with reasoning)

## Example

```
[Just completed Task 2: Add verification function]

You: Let me request code review before proceeding.

BASE_SHA=$(git log --oneline | grep "Task 1" | head -1 | awk '{print $1}')
HEAD_SHA=$(git rev-parse HEAD)

[Dispatch superpowers:code-reviewer subagent]
  WHAT_WAS_IMPLEMENTED: Verification and repair functions for conversation index
  PLAN_OR_REQUIREMENTS: Task 2 from docs/superpowers/plans/deployment-plan.md
  BASE_SHA: a7981ec
  HEAD_SHA: 3df7661
  DESCRIPTION: Added verifyIndex() and repairIndex() with 4 issue types

[Subagent returns]:
  Strengths: Clean architecture, real tests
  Issues:
    Important: Missing progress indicators
    Minor: Magic number (100) for reporting interval
  Assessment: Ready to proceed

You: [Fix progress indicators]
[Continue to Task 3]
```

## Integration with Workflows

**Subagent-Driven Development:**
- Review after EACH task
- Catch issues before they compound
- Fix before moving to next task

**Executing Plans:**
- Review after each batch (3 tasks)
- Get feedback, apply, continue

**Ad-Hoc Development:**
- Review before merge
- Review when stuck

## Red Flags

**Never:**
- Skip review because "it's simple"
- Ignore Critical issues
- Proceed with unfixed Important issues
- Argue with valid technical feedback

**If reviewer wrong:**
- Push back with technical reasoning
- Show code/tests that prove it works
- Request clarification

See template at: requesting-code-review/code-reviewer.md

---

## Why This Skill Exists

Review — Despacha subagente code-reviewer com contexto preciso e isolado — nunca herda

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires requesting code review capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

Se subagente reviewer não disponível: fazer auto-review com checklist da spec.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
