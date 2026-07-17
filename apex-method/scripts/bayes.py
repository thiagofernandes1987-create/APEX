#!/usr/bin/env python3
"""
bayes.py — APEX Bayesian layer, made computable (was bayesian_curator LLM_BEHAVIOR).

Implements the concrete machinery specified in the APEX kernel defaults:
  - beta-binomial conjugate update (class_1)               -> posterior belief from evidence
  - Omega decision thresholds {adopt: 0.72, review: 0.5}   -> adopt / review / reject
  - filter_threshold 0.4                                   -> drop weak priors (G5)
  - posterior over competing hypotheses (normalized Bayes) -> dominant hypothesis + entropy
  - R_acum: accumulated reliability = product over sliding window N=20, gates 0.50 / 0.30

All functions are exact arithmetic — verifiable, not estimated. Where a value is a belief
the LLM supplies, it is an input; the UPDATE and the GATES are computed here.

WHY: The APEX Bayesian layer was LLM_BEHAVIOR (estimated); this computes it exactly.
WHEN: At PMI convergence / STEP_13 belief update, and for any reliability gate.
WHAT IF IT FAILS: Inputs (priors/likelihoods) are LLM-supplied; if absent, callers pass uniform priors and mark [APPROX].
"""
import math

OMEGA = {"adopt": 0.72, "review": 0.5}   # kernel.defaults.bayesian.omega_thresholds
FILTER_THRESHOLD = 0.4                     # kernel.defaults.bayesian.filter_threshold
R_WARNING, R_CRITICAL = 0.50, 0.30         # SR_10 reliability gates
R_WINDOW = 20                              # OPP-28 sliding window N=20


# ── class_1: beta-binomial conjugate update ───────────────────────────────────
def beta_binomial_update(prior_a, prior_b, successes, trials):
    """Prior Beta(a,b) + (successes/trials) -> posterior Beta(a+k, b+n-k). Exact."""
    a2, b2 = prior_a + successes, prior_b + (trials - successes)
    mean = a2 / (a2 + b2)
    var = (a2 * b2) / ((a2 + b2) ** 2 * (a2 + b2 + 1))
    sd = math.sqrt(var)
    return {"posterior_a": a2, "posterior_b": b2, "mean": round(mean, 4),
            "sd": round(sd, 4), "ci90": (round(max(0, mean - 1.645 * sd), 4),
                                          round(min(1, mean + 1.645 * sd), 4))}


def omega_decision(posterior_mean):
    """Ω_Bayes: adopt >=0.72, review >=0.5, else reject (kernel thresholds)."""
    if posterior_mean >= OMEGA["adopt"]:
        return "ADOPT"
    if posterior_mean >= OMEGA["review"]:
        return "REVIEW"
    return "REJECT"


# ── posterior over competing hypotheses (bayesian_curator core, computed) ──────
def posterior_over_hypotheses(priors: dict, likelihoods: dict):
    """P(H|E) ∝ P(E|H)·P(H), normalized. Returns posteriors, dominant, entropy."""
    unnorm = {h: priors.get(h, 0) * likelihoods.get(h, 0) for h in priors}
    z = sum(unnorm.values()) or 1.0
    post = {h: v / z for h, v in unnorm.items()}
    dominant = max(post, key=post.get)
    entropy = -sum(p * math.log2(p) for p in post.values() if p > 0)
    return {"posteriors": {h: round(v, 4) for h, v in post.items()},
            "dominant": dominant, "dominant_p": round(post[dominant], 4),
            "entropy_bits": round(entropy, 3), "decision": omega_decision(post[dominant])}


def filter_priors(components: dict, threshold=FILTER_THRESHOLD):
    """G5: drop components whose prior mean < filter_threshold before resolution."""
    return {h: p for h, p in components.items() if p >= threshold}


# ── R_acum: accumulated reliability with gates ────────────────────────────────
def r_acum(reliabilities, window=R_WINDOW, learning_rate=0.05):
    """
    R_acum = product of per-block reliabilities over the last `window` blocks.
    p_eff = p_base + α·ε applies a small temporal-correlation nudge (ε = prev-mean drift).
    Returns R_acum + gate status per SR_10.
    """
    r = list(reliabilities)[-window:]
    if not r:
        return {"r_acum": 1.0, "status": "OK", "blocks": 0}
    # temporal correlation nudge (bounded)
    eff = []
    prev = r[0]
    for x in r:
        e = x - prev
        eff.append(min(1.0, max(0.0, x + learning_rate * e)))
        prev = x
    R = 1.0
    for x in eff:
        R *= x
    status = ("CRITICAL_EARLY_EXIT" if R < R_CRITICAL else
              "WARNING_REPLAN" if R < R_WARNING else "OK")
    return {"r_acum": round(R, 4), "status": status, "blocks": len(r),
            "action": {"CRITICAL_EARLY_EXIT": "force EARLY_EXIT, status PARTIAL",
                       "WARNING_REPLAN": "emit RELIABILITY_WARNING + dynamic replanning",
                       "OK": "continue"}[status]}


if __name__ == "__main__":
    print("beta-binomial: prior Beta(1,1) + 8/10 ->", beta_binomial_update(1, 1, 8, 10))
    print("omega(0.75) ->", omega_decision(0.75))
    print("hypotheses ->", posterior_over_hypotheses(
        {"A": 0.5, "B": 0.3, "C": 0.2}, {"A": 0.8, "B": 0.4, "C": 0.1}))
    print("R_acum ok   ->", r_acum([0.9, 0.85, 0.8]))
    print("R_acum crit ->", r_acum([0.9, 0.6, 0.5, 0.6]))
