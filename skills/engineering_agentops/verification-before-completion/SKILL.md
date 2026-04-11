---
skill_id: engineering_agentops.verification-before-completion
name: verification-before-completion
description: >
  Gate function obrigatória antes de qualquer claim de conclusão: identificar o comando
  de verificação, executá-lo, ler o output completo, verificar se confirma o claim —
  SOMENTE ENTÃO fazer o claim com evidência. Iron Law: SEM EVIDÊNCIA = SEM CLAIM.
  Proíbe "should work", "probably", "seems to", e qualquer expressão de satisfação prematura.
version: v00.36.0
status: ADOPTED
domain_path: engineering_agentops/verification-before-completion
source_repo: obra/superpowers
risk: safe
tier: ADAPTED
anchors:
  - verification
  - completion_gate
  - evidence_based
  - no_assumptions
  - test_verification
  - honesty
  - anti_hallucination
cross_domain_bridges:
  - to: engineering_agentops.test-driven-development
    strength: 0.92
    reason: "RED-GREEN cycle é a forma mais robusta de evidence before claims"
  - to: engineering_agentops.systematic-debugging
    strength: 0.88
    reason: "verificar que o fix resolveu o problema aplica o mesmo princípio"
  - to: engineering_agentops.finishing-a-development-branch
    strength: 0.90
    reason: "finishing verifica testes antes de apresentar opções — aplicação direta"
  - to: meta.output_integrity_checker
    strength: 0.95
    reason: "output_integrity_checker é a implementação APEX deste mesmo princípio"
  - to: engineering_agentops.subagent-driven-development
    strength: 0.80
    reason: "verificar output de subagentes antes de marcar tarefa como completa"
input_schema:
  - name: claim_to_make
    type: string
    description: "O claim que se quer fazer (ex: 'testes passam', 'bug corrigido')"
    required: true
  - name: verification_command
    type: string
    description: "Comando que prova ou refuta o claim"
    required: true
output_schema:
  - name: verification_output
    type: string
    description: "Output completo do comando de verificação"
  - name: claim_supported
    type: boolean
    description: "Se o output suporta o claim"
  - name: actual_status
    type: string
    description: "Status real baseado em evidência (não em suposição)"
what_if_fails: >
  Se comando de verificação não existe: NÃO fazer o claim — reportar que verificação não é possível.
  Se output ambíguo: reportar ambiguidade — não interpretar como sucesso.
  Se output confirma falha: reportar falha com evidência — não tentar explicar por que "deveria ter funcionado".
synergy_map:
  - type: skill
    ref: engineering_agentops.test-driven-development
    benefit: "RED-GREEN é a forma canônica de evidence-based verification"
  - type: skill
    ref: engineering_agentops.finishing-a-development-branch
    benefit: "verifica testes antes de qualquer opção de merge"
  - type: diff
    ref: OPP-134
    description: "output_integrity_checker implementa este princípio para outputs de LLM"
security:
  - risk: "False positive de verificação (teste passa por razão errada)"
    mitigation: "RED-GREEN cycle: verificar que o teste FALHA sem o código antes de considerar verificado"
  - risk: "Verificação parcial (apenas subset de testes)"
    mitigation: "Sempre rodar a suite completa — verificação parcial não conta"
executor: LLM_BEHAVIOR
---

# Verification Before Completion

## Overview

Claiming work is complete without verification is dishonesty, not efficiency.

**Core principle:** Evidence before claims, always.

**Violating the letter of this rule is violating the spirit of this rule.**

## The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

If you haven't run the verification command in this message, you cannot claim it passes.

## The Gate Function

```
BEFORE claiming any status or expressing satisfaction:

1. IDENTIFY: What command proves this claim?
2. RUN: Execute the FULL command (fresh, complete)
3. READ: Full output, check exit code, count failures
4. VERIFY: Does output confirm the claim?
   - If NO: State actual status with evidence
   - If YES: State claim WITH evidence
5. ONLY THEN: Make the claim

Skip any step = lying, not verifying
```

## Common Failures

| Claim | Requires | Not Sufficient |
|-------|----------|----------------|
| Tests pass | Test command output: 0 failures | Previous run, "should pass" |
| Linter clean | Linter output: 0 errors | Partial check, extrapolation |
| Build succeeds | Build command: exit 0 | Linter passing, logs look good |
| Bug fixed | Test original symptom: passes | Code changed, assumed fixed |
| Regression test works | Red-green cycle verified | Test passes once |
| Agent completed | VCS diff shows changes | Agent reports "success" |
| Requirements met | Line-by-line checklist | Tests passing |

## Red Flags - STOP

- Using "should", "probably", "seems to"
- Expressing satisfaction before verification ("Great!", "Perfect!", "Done!", etc.)
- About to commit/push/PR without verification
- Trusting agent success reports
- Relying on partial verification
- Thinking "just this once"
- Tired and wanting work over
- **ANY wording implying success without having run verification**

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "Should work now" | RUN the verification |
| "I'm confident" | Confidence ≠ evidence |
| "Just this once" | No exceptions |
| "Linter passed" | Linter ≠ compiler |
| "Agent said success" | Verify independently |
| "I'm tired" | Exhaustion ≠ excuse |
| "Partial check is enough" | Partial proves nothing |
| "Different words so rule doesn't apply" | Spirit over letter |

## Key Patterns

**Tests:**
```
✅ [Run test command] [See: 34/34 pass] "All tests pass"
❌ "Should pass now" / "Looks correct"
```

**Regression tests (TDD Red-Green):**
```
✅ Write → Run (pass) → Revert fix → Run (MUST FAIL) → Restore → Run (pass)
❌ "I've written a regression test" (without red-green verification)
```

**Build:**
```
✅ [Run build] [See: exit 0] "Build passes"
❌ "Linter passed" (linter doesn't check compilation)
```

**Requirements:**
```
✅ Re-read plan → Create checklist → Verify each → Report gaps or completion
❌ "Tests pass, phase complete"
```

**Agent delegation:**
```
✅ Agent reports success → Check VCS diff → Verify changes → Report actual state
❌ Trust agent report
```

## Why This Matters

From 24 failure memories:
- your human partner said "I don't believe you" - trust broken
- Undefined functions shipped - would crash
- Missing requirements shipped - incomplete features
- Time wasted on false completion → redirect → rework
- Violates: "Honesty is a core value. If you lie, you'll be replaced."

## When To Apply

**ALWAYS before:**
- ANY variation of success/completion claims
- ANY expression of satisfaction
- ANY positive statement about work state
- Committing, PR creation, task completion
- Moving to next task
- Delegating to agents

**Rule applies to:**
- Exact phrases
- Paraphrases and synonyms
- Implications of success
- ANY communication suggesting completion/correctness

## The Bottom Line

**No shortcuts for verification.**

Run the command. Read the output. THEN claim the result.

This is non-negotiable.
