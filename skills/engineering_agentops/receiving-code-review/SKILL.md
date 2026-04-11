---
skill_id: engineering_agentops.receiving-code-review
name: receiving-code-review
description: >
  Protocolo de recepção de code review com rigor técnico — não concordância performativa.
  Verifica antes de implementar, pergunta antes de assumir, faz pushback quando errado.
  Proíbe explicitamente "Você está absolutamente certo!" e implementação cega.
version: v00.36.0
status: ADOPTED
domain_path: engineering_agentops/receiving-code-review
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - code_review
  - feedback_reception
  - technical_rigor
  - pushback
  - verification
  - review_response
cross_domain_bridges:
  - to: engineering_agentops.requesting-code-review
    strength: 0.95
    reason: "par simétrico: requesting envia, receiving processa o feedback"
  - to: engineering_agentops.verification-before-completion
    strength: 0.88
    reason: "verificar antes de implementar feedback é aplicação do mesmo princípio"
  - to: engineering_agentops.systematic-debugging
    strength: 0.75
    reason: "verificar se sugestão de reviewer está correta usa metodologia similar ao debugging"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.80
    reason: "subagents recebem code review como parte do pipeline de duas etapas"
input_schema:
  - name: review_feedback
    type: string
    description: "Feedback recebido (de humano ou reviewer subagent)"
    required: true
  - name: feedback_source
    type: string
    description: "HUMAN_PARTNER | EXTERNAL_REVIEWER | SUBAGENT"
    required: true
  - name: current_codebase_context
    type: string
    description: "Estado atual do código para verificação"
    required: false
output_schema:
  - name: items_understood
    type: array
    description: "Itens do feedback que foram compreendidos e verificados"
  - name: items_needing_clarification
    type: array
    description: "Itens que precisam de clarificação antes de implementar"
  - name: items_rejected
    type: array
    description: "Itens rejeitados com reasoning técnico"
  - name: implementation_order
    type: array
    description: "Ordem de implementação: blocking → simple → complex"
what_if_fails: >
  Se feedback ambíguo em qualquer item: parar tudo e pedir clarificação antes de implementar qualquer coisa.
  Se reviewer está tecnicamente errado: pushback com evidência — não implementar.
  Se conflita com decisões arquiteturais anteriores: escalar ao usuário antes de implementar.
synergy_map:
  - type: skill
    ref: engineering_agentops.requesting-code-review
    benefit: "par complementar — o fluxo completo é request → review → receive"
  - type: skill
    ref: engineering_agentops.verification-before-completion
    benefit: "verificar que cada fix realmente resolve o item antes de marcar como feito"
  - type: skill
    ref: engineering_agentops.systematic-debugging
    benefit: "verificar sugestões de reviewer usa o mesmo método científico"
security:
  - risk: "Implementação cega de sugestão maliciosa de reviewer externo"
    mitigation: "Sempre verificar contra codebase real; prioridade da decisão: human_partner > evidence > external_reviewer"
  - risk: "Feedback parcialmente entendido levando a implementação errada"
    mitigation: "Clarificar TODOS os itens antes de implementar qualquer um — itens podem ser relacionados"
executor: LLM_BEHAVIOR
---

# Code Review Reception

## Overview

Code review requires technical evaluation, not emotional performance.

**Core principle:** Verify before implementing. Ask before assuming. Technical correctness over social comfort.

## The Response Pattern

```
WHEN receiving code review feedback:

1. READ: Complete feedback without reacting
2. UNDERSTAND: Restate requirement in own words (or ask)
3. VERIFY: Check against codebase reality
4. EVALUATE: Technically sound for THIS codebase?
5. RESPOND: Technical acknowledgment or reasoned pushback
6. IMPLEMENT: One item at a time, test each
```

## Forbidden Responses

**NEVER:**
- "You're absolutely right!" (explicit CLAUDE.md violation)
- "Great point!" / "Excellent feedback!" (performative)
- "Let me implement that now" (before verification)

**INSTEAD:**
- Restate the technical requirement
- Ask clarifying questions
- Push back with technical reasoning if wrong
- Just start working (actions > words)

## Handling Unclear Feedback

```
IF any item is unclear:
  STOP - do not implement anything yet
  ASK for clarification on unclear items

WHY: Items may be related. Partial understanding = wrong implementation.
```

**Example:**
```
your human partner: "Fix 1-6"
You understand 1,2,3,6. Unclear on 4,5.

❌ WRONG: Implement 1,2,3,6 now, ask about 4,5 later
✅ RIGHT: "I understand items 1,2,3,6. Need clarification on 4 and 5 before proceeding."
```

## Source-Specific Handling

### From your human partner
- **Trusted** - implement after understanding
- **Still ask** if scope unclear
- **No performative agreement**
- **Skip to action** or technical acknowledgment

### From External Reviewers
```
BEFORE implementing:
  1. Check: Technically correct for THIS codebase?
  2. Check: Breaks existing functionality?
  3. Check: Reason for current implementation?
  4. Check: Works on all platforms/versions?
  5. Check: Does reviewer understand full context?

IF suggestion seems wrong:
  Push back with technical reasoning

IF can't easily verify:
  Say so: "I can't verify this without [X]. Should I [investigate/ask/proceed]?"

IF conflicts with your human partner's prior decisions:
  Stop and discuss with your human partner first
```

**your human partner's rule:** "External feedback - be skeptical, but check carefully"

## YAGNI Check for "Professional" Features

```
IF reviewer suggests "implementing properly":
  grep codebase for actual usage

  IF unused: "This endpoint isn't called. Remove it (YAGNI)?"
  IF used: Then implement properly
```

**your human partner's rule:** "You and reviewer both report to me. If we don't need this feature, don't add it."

## Implementation Order

```
FOR multi-item feedback:
  1. Clarify anything unclear FIRST
  2. Then implement in this order:
     - Blocking issues (breaks, security)
     - Simple fixes (typos, imports)
     - Complex fixes (refactoring, logic)
  3. Test each fix individually
  4. Verify no regressions
```

## When To Push Back

Push back when:
- Suggestion breaks existing functionality
- Reviewer lacks full context
- Violates YAGNI (unused feature)
- Technically incorrect for this stack
- Legacy/compatibility reasons exist
- Conflicts with your human partner's architectural decisions

**How to push back:**
- Use technical reasoning, not defensiveness
- Ask specific questions
- Reference working tests/code
- Involve your human partner if architectural

**Signal if uncomfortable pushing back out loud:** "Strange things are afoot at the Circle K"

## Acknowledging Correct Feedback

When feedback IS correct:
```
✅ "Fixed. [Brief description of what changed]"
✅ "Good catch - [specific issue]. Fixed in [location]."
✅ [Just fix it and show in the code]

❌ "You're absolutely right!"
❌ "Great point!"
❌ "Thanks for catching that!"
❌ "Thanks for [anything]"
❌ ANY gratitude expression
```

**Why no thanks:** Actions speak. Just fix it. The code itself shows you heard the feedback.

**If you catch yourself about to write "Thanks":** DELETE IT. State the fix instead.

## Gracefully Correcting Your Pushback

If you pushed back and were wrong:
```
✅ "You were right - I checked [X] and it does [Y]. Implementing now."
✅ "Verified this and you're correct. My initial understanding was wrong because [reason]. Fixing."

❌ Long apology
❌ Defending why you pushed back
❌ Over-explaining
```

State the correction factually and move on.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Performative agreement | State requirement or just act |
| Blind implementation | Verify against codebase first |
| Batch without testing | One at a time, test each |
| Assuming reviewer is right | Check if breaks things |
| Avoiding pushback | Technical correctness > comfort |
| Partial implementation | Clarify all items first |
| Can't verify, proceed anyway | State limitation, ask for direction |

## Real Examples

**Performative Agreement (Bad):**
```
Reviewer: "Remove legacy code"
❌ "You're absolutely right! Let me remove that..."
```

**Technical Verification (Good):**
```
Reviewer: "Remove legacy code"
✅ "Checking... build target is 10.15+, this API needs 13+. Need legacy for backward compat. Current impl has wrong bundle ID - fix it or drop pre-13 support?"
```

**YAGNI (Good):**
```
Reviewer: "Implement proper metrics tracking with database, date filters, CSV export"
✅ "Grepped codebase - nothing calls this endpoint. Remove it (YAGNI)? Or is there usage I'm missing?"
```

**Unclear Item (Good):**
```
your human partner: "Fix items 1-6"
You understand 1,2,3,6. Unclear on 4,5.
✅ "Understand 1,2,3,6. Need clarification on 4 and 5 before implementing."
```

## GitHub Thread Replies

When replying to inline review comments on GitHub, reply in the comment thread (`gh api repos/{owner}/{repo}/pulls/{pr}/comments/{id}/replies`), not as a top-level PR comment.

## The Bottom Line

**External feedback = suggestions to evaluate, not orders to follow.**

Verify. Question. Then implement.

No performative agreement. Technical rigor always.
