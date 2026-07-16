# geodesic_scheduler & verification_gate (deep dive)

Two DEEP/RESEARCH/SCIENTIFIC optimizers, nativized as real algorithms.

## geodesic_scheduler (`scripts/geodesic_scheduler.py`) — SR_34
Orders pipeline steps by **information-per-token**: `max(ΔH_cognitive / tokens_expected)`,
greedy with **1-step lookahead** (O(2), captures ~60-70% of full-A* value cheaply). Low-value
steps are skipped. **Ethical violations get `sys.maxsize` cost** so they can never be scheduled
(SR_34). Rollback to fixed order if the plan would use **> 115% of baseline tokens**
(`[GEODESIC_ROLLBACK]`). Fixed order is always a valid fallback — the pipeline works without it.
- `evaluate_steps(remaining_steps, token_budget)` → `{plan, skipped, tokens, rollback}`.
- Honest: the ordering is real; the ΔH/token estimates per step are supplied by the LLM/MCFE.

## verification_gate (`scripts/verification_gate.py`) — the P≠NP insight
Verifying is cheaper than generating, but verifying every hypothesis explodes the budget. The
gate **routes only risky hypotheses** to expensive PoT verification, per mode:
| Mode | trigger | max_verify | budget gate |
|------|---------|-----------|-------------|
| EXPRESS/FAST/CLARIFY | (disabled) | — | — |
| DEEP | ΔH>0.15 AND conf<65 | 3 | — |
| RESEARCH | ΔH>0.10 OR conf<70 | 5 | — |
| SCIENTIFIC | conf<80 | ∞ | 0.25 (3000 tok of 12k) |
| FOGGY | ΔH>0.20 | 2 | — |
- `route(hypotheses, mode, budget)` → `{verify_list, skip_list, budget_cap}`.
- `verify_hypothesis(tests)` does **premature pruning**: fail Test 1 → skip Tests 2,3.
- What if it fails: sandbox down → `[VERIFICATION_GATE_SKIPPED]`; budget out →
  `[VERIFICATION_BUDGET_EXHAUSTED]`. The gate NEVER blocks all hypotheses.
