#!/usr/bin/env python3
"""
chaos_operators.py — APEX ChaosOperators (DIFF_v22_001), nativized as an OFFENSIVE
exploration engine.

WHY THIS EXISTS:
  The chaos stance is not just a brake against premature convergence (SR_11) — from FOGGY up
  it is the INNOVATION driver that forces the reasoning out of its comfort zone. This ports
  the repo's structured perturbation operators so "think outside the obvious" is real math,
  not a vibe:
    - Levy flight (heavy-tail, alpha=1.5): occasional BIG jumps that escape deep local minima.
    - structural_mutation: rewrites a hypothesis's structure, not just its value.
    - recombine: crosses two hypotheses to birth a third the LLM would not have proposed.
  Temperature T = H_cognitive (MCFE entropy); P_chaos = min(0.30, T). Counterintuitive but
  validated in the repo: HIGH T = more acceptances (healthy exploration); LOW T + a rejection
  streak = a stuck agent (that is the replacement trigger, not high T — see competence_matrix).

WHEN TO USE:
  From FOGGY upward, per the exploration policy (config.exploration_policy). In RESEARCH the
  chaos stance is MANDATORY and must yield at least one non-obvious ("genius") hypothesis.

WHAT IF IT FAILS:
  Pure stdlib (random/math); the only failure mode is empty input, which returns the input
  unchanged. Chaos never fabricates a FINDING on its own (SR_11) — it proposes; the PMI adjudicates.
"""
import math
import random

LEVY_ALPHA = 1.5           # heavy-tail exponent (repo value)
MAX_CHAOS_PROB = 0.30      # P_chaos ceiling (repo value)
MIN_NODES_RECOMBINE = 2


def p_chaos(temperature: float) -> float:
    """P_chaos = min(0.30, T), T = H_cognitive (MCFE entropy). Clamped to [0, 0.30]."""
    return max(0.0, min(MAX_CHAOS_PROB, float(temperature)))


def levy_step(alpha: float = LEVY_ALPHA, rng: random.Random = None) -> float:
    """Levy heavy-tail step: u/|v|^(1/alpha), u,v ~ N(0,1). Occasionally huge -> escapes
    deep local minima (the jump a gradient step would never take)."""
    rng = rng or random
    u = rng.gauss(0, 1)
    v = rng.gauss(0, 1)
    return u / max(abs(v) ** (1.0 / alpha), 1e-10)


def perturb_scalar(x: float, temperature: float, rng: random.Random = None) -> float:
    """Perturb a numeric hypothesis by a Levy step scaled by temperature — small most of the
    time, occasionally a large exploratory leap."""
    return x + p_chaos(temperature) * levy_step(rng=rng) * (abs(x) + 1.0)


def structural_mutation(hyp: dict, rng: random.Random = None) -> dict:
    """Rewrite a hypothesis's STRUCTURE (not just its value): flip a stance, invert an
    assumption, or negate the framing — forcing a genuinely different shape."""
    rng = rng or random
    out = dict(hyp)
    flips = {"optimistic": "pessimistic", "pessimistic": "optimistic",
             "neutral": "contrarian", "adopt": "reject", "reject": "adopt"}
    if "stance" in out and out["stance"] in flips:
        out["stance"] = flips[out["stance"]]
    out["mutated"] = True
    out["framing"] = rng.choice(["invert-the-goal", "remove-a-constraint",
                                 "swap-cause-and-effect", "assume-the-opposite"])
    return out


def recombine(hyp_a: dict, hyp_b: dict) -> dict:
    """Cross two hypotheses into a third (uniform crossover of their fields) — a child the
    single-context LLM would not have generated on its own."""
    child = {}
    for k in set(hyp_a) | set(hyp_b):
        child[k] = hyp_a.get(k) if (hash(str(k)) & 1) else hyp_b.get(k, hyp_a.get(k))
    child["recombined_from"] = [hyp_a.get("id", "a"), hyp_b.get("id", "b")]
    return child


def genius_stance(task: str, base_hypotheses: list, temperature: float = 0.30) -> dict:
    """The MANDATORY non-obvious stance for RESEARCH: apply a Levy jump + structural mutation
    to the most confident base hypothesis so the LLM is FORCED to propose the unconventional.
    Returns a scaffold the LLM fills with the actual out-of-the-box idea."""
    seed = max(base_hypotheses, key=lambda h: h.get("confidence", 0), default={"stance": "neutral"})
    mutated = structural_mutation(seed)
    return {"stance": "genius", "persona": "chaos", "role": "expand-horizons",
            "seed_from": seed.get("stance", "neutral"), "framing": mutated["framing"],
            "levy_kick": round(abs(levy_step()), 3),
            "instruction": (f"Propose a NON-OBVIOUS hypothesis for: {task[:120]}. "
                            f"Reframe via '{mutated['framing']}'. It must NOT restate the "
                            f"optimistic/neutral/pessimistic answers — surface the overlooked option."),
            "confidence": 0.25}   # deliberately low (SR_11): never the main finding alone


if __name__ == "__main__":
    import json
    random.seed(7)
    print("P_chaos(T=0.5) =", p_chaos(0.5), "| P_chaos(T=0.05) =", p_chaos(0.05))
    print("levy steps:", [round(levy_step(), 2) for _ in range(5)])
    print("perturb 10.0 @T=0.3:", round(perturb_scalar(10.0, 0.3), 3))
    print("mutation:", structural_mutation({"stance": "optimistic", "id": "H1"}))
    print("recombine:", recombine({"id": "A", "stance": "optimistic"}, {"id": "B", "risk": "high"}))
    print("genius:", json.dumps(genius_stance("optimize the reasoning pipeline",
          [{"stance": "optimistic", "confidence": 0.8}]), ensure_ascii=False)[:200])
