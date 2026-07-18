#!/usr/bin/env python3
"""
verification_gate.py — APEX verification_gate (v00.32.1, OPP-MAS-07), nativized.

WHY: verifying is cheaper than generating (P≠NP insight), but verifying EVERY hypothesis in
SCIENTIFIC can eat 25-33% of a 12k budget. The MCFE acts as a router: only RISKY hypotheses
(high ΔH / low confidence, per mode) go through expensive PoT verification, capped by a budget
gate, with premature pruning (fail Test 1 -> skip Tests 2,3).

WHEN: STEP_3, before interference. Disabled in EXPRESS/FAST/CLARIFY.

WHAT IF IT FAILS: sandbox unavailable -> skip [VERIFICATION_GATE_SKIPPED]; budget exhausted ->
stop [VERIFICATION_BUDGET_EXHAUSTED]. The gate NEVER blocks all hypotheses — on failure it
continues without the filter.
"""
ROUTING = {
    "EXPRESS": {"enabled": False}, "FAST": {"enabled": False}, "CLARIFY": {"enabled": False},
    "DEEP":      {"enabled": True, "trigger": lambda h: h["delta_h"] > 0.15 and h["confidence"] < 65, "max_verify": 3},
    "RESEARCH":  {"enabled": True, "trigger": lambda h: h["delta_h"] > 0.10 or h["confidence"] < 70, "max_verify": 5},
    "SCIENTIFIC":{"enabled": True, "trigger": lambda h: h["confidence"] < 80, "max_verify": None,
                  "budget_gate": 0.25},
    "FOGGY":     {"enabled": True, "trigger": lambda h: h["delta_h"] > 0.20, "max_verify": 2},
}


def route(hypotheses, cognitive_mode, token_budget=12000, verify_cost=600):
    """Decide which hypotheses to verify. Returns {verify_list, skip_list, budget_cap}."""
    cfg = ROUTING.get(cognitive_mode, {"enabled": False})
    if not cfg.get("enabled"):
        return {"verify_list": [], "skip_list": [h["id"] for h in hypotheses],
                "reason": f"gate disabled in {cognitive_mode}"}
    # risky first, by ΔH desc (prioritize high information)
    risky = sorted([h for h in hypotheses if cfg["trigger"](h)],
                   key=lambda h: -h.get("delta_h", 0))
    cap = cfg.get("max_verify")
    if cap is not None:
        risky = risky[:cap]
    budget_cap = None
    if "budget_gate" in cfg:                       # SCIENTIFIC: 25% of budget
        budget_cap = int(token_budget * cfg["budget_gate"])
        max_by_budget = max(1, budget_cap // verify_cost)
        risky = risky[:max_by_budget]
    verify_ids = {h["id"] for h in risky}
    return {"verify_list": [h["id"] for h in risky],
            "skip_list": [h["id"] for h in hypotheses if h["id"] not in verify_ids],
            "budget_cap": budget_cap}


def verify_hypothesis(tests):
    """Premature pruning: run tests in order; fail one -> stop (skip the rest)."""
    for i, passed in enumerate(tests, 1):
        if not passed:
            return {"passed": False, "rejected_at_test": i, "tests_run": i}
    return {"passed": True, "rejected_at_test": None, "tests_run": len(tests)}


if __name__ == "__main__":
    hyps = [
        {"id": "H1", "delta_h": 0.30, "confidence": 55},
        {"id": "H2", "delta_h": 0.05, "confidence": 90},
        {"id": "H3", "delta_h": 0.20, "confidence": 60},
        {"id": "H4", "delta_h": 0.02, "confidence": 40},
    ]
    for mode in ("EXPRESS", "DEEP", "SCIENTIFIC"):
        print(mode, "->", route(hyps, mode))
    print("premature pruning [T1 pass, T2 fail, T3]:", verify_hypothesis([True, False, True]))
