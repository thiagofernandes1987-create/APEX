#!/usr/bin/env python3
"""
geodesic_scheduler.py — APEX geodesic_scheduler (v00.32.1, OPP-MAS-B7, SR_34), nativized.

WHY: a fixed step order wastes tokens when the direction is already clear. This greedily
orders steps by information-per-token (ΔH_cognitive / tokens_expected), skipping low-value
steps. Greedy O(k) with 1-step lookahead captures ~60-70% of full-A* value at a fraction of
the cost (full A* needs a predictive cost model that isn't precise enough to exist).

WHEN: cognitive_mode IN [DEEP, RESEARCH, SCIENTIFIC].

WHAT IF IT FAILS: tokens > 115% of baseline -> rollback to default order [GEODESIC_ROLLBACK];
ΔH not computable -> fixed order. The pipeline always works without the scheduler; fixed order
is a valid fallback. Ethical violations get sys.maxsize cost so they are never scheduled (SR_34).
"""
import sys

ROLLBACK_FACTOR = 1.15   # tokens_used > 115% baseline -> rollback


def compute_cost(step):
    """Token cost of a step; ethical violation -> sys.maxsize (SR_34, ethical_barrier)."""
    if step.get("ethical_violation"):
        return sys.maxsize
    return max(1, int(step.get("tokens", 100)))


def _ratio(step):
    c = compute_cost(step)
    if c >= sys.maxsize:
        return -1.0
    return step.get("delta_h", 0.0) / c


def evaluate_steps(remaining_steps, token_budget, min_ratio=1e-4):
    """
    Greedy schedule by max(ΔH/tokens) with 1-step lookahead. Skips low-value steps and steps
    that don't fit the budget. Returns {plan, skipped, tokens, rollback}.
    """
    baseline = sum(compute_cost(s) for s in remaining_steps if not s.get("ethical_violation"))
    pool = [s for s in remaining_steps]
    plan, skipped, tokens = [], [], 0
    while pool:
        # 1-step lookahead: score each candidate by its ratio plus the best follow-up ratio
        scored = []
        for i, s in enumerate(pool):
            r = _ratio(s)
            if r < 0:
                continue
            rest = [_ratio(x) for j, x in enumerate(pool) if j != i and _ratio(x) >= 0]
            lookahead = max(rest) if rest else 0
            scored.append((r + 0.25 * lookahead, i, s, r))
        if not scored:
            break
        scored.sort(reverse=True)
        _, idx, best, r = scored[0]
        cost = compute_cost(best)
        if r < min_ratio:                       # low-information -> skip the rest
            skipped.extend(pool)
            break
        if tokens + cost > token_budget:        # doesn't fit
            skipped.append(best)
            pool.pop(idx)
            continue
        plan.append(best["id"])
        tokens += cost
        pool.pop(idx)

    rollback = tokens > ROLLBACK_FACTOR * baseline if baseline else False
    if rollback:
        return {"plan": [s["id"] for s in remaining_steps if not s.get("ethical_violation")],
                "skipped": [], "tokens": baseline, "rollback": True, "event": "[GEODESIC_ROLLBACK]"}
    return {"plan": plan, "skipped": [s["id"] for s in skipped], "tokens": tokens,
            "rollback": False, "baseline": baseline}


if __name__ == "__main__":
    steps = [
        {"id": "STEP_1_classify", "delta_h": 0.30, "tokens": 300},
        {"id": "STEP_2_inject",   "delta_h": 0.05, "tokens": 500},   # low value/token
        {"id": "STEP_5_expand",   "delta_h": 0.40, "tokens": 400},
        {"id": "STEP_X_unethical","delta_h": 0.90, "tokens": 100, "ethical_violation": True},
        {"id": "STEP_9_synth",    "delta_h": 0.25, "tokens": 200},
    ]
    print(evaluate_steps(steps, token_budget=1200))
