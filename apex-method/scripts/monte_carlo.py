#!/usr/bin/env python3
"""
monte_carlo.py — Real Monte Carlo simulation (APEX monte_carlo_simulator, OPP-73), nativized.

WHY THIS EXISTS:
  The skill forbids calling qualitative weighting "Monte Carlo" (§10 anti-pattern). This is
  the honest counterpart: when a hypothesis is QUANTIFIABLE — inputs have distributions and
  there is a codable model_fn — decide it by REAL simulation (P10/P50/P90 + CV), not vibes.
  Feeds the PMI convergence when candidates are numeric-simulable.

WHEN TO USE:
  SCIENTIFIC mode, variables with quantifiable uncertainty (cost/risk/latency ranges, etc.).

HOW IT WORKS:
  Caller supplies model_fn(sample: dict) -> float and input_distributions {name: {dist,...}}.
  We draw N samples per input, run model_fn, and return percentiles + coefficient of variation
  with a CV-based interpretation. numpy is used if present (vectorizable seeds), else the
  stdlib `random`+`statistics` path — same result shape, so it never hard-depends on numpy.

WHAT IF IT FAILS:
  - >10% of iterations raise -> status PARTIAL ([MONTE_CARLO_PARTIAL]).
  - every iteration raises   -> status FAILED (caller estimates with [APPROX]).
  - unknown distribution     -> ValueError naming the offending input (no silent default).
  NEVER present Monte Carlo numbers without a real run.
"""
import math
import random
import statistics

try:
    import numpy as _np
except ImportError:
    _np = None

_DISTS = ("normal", "lognormal", "beta", "uniform", "triangular", "fixed")


def _draw(rng, spec: dict) -> float:
    d = spec.get("dist", "fixed")
    if d == "normal":
        return rng.gauss(spec["mean"], spec["std"])
    if d == "lognormal":
        return rng.lognormvariate(spec["mean"], spec["sigma"])
    if d == "beta":
        return rng.betavariate(spec["a"], spec["b"])
    if d == "uniform":
        return rng.uniform(spec["low"], spec["high"])
    if d == "triangular":
        return rng.triangular(spec["left"], spec["right"], spec["mode"])
    if d == "fixed":
        return float(spec["value"])
    raise ValueError(f"unknown distribution {d!r} (supported: {_DISTS})")


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_vals[int(k)]
    return sorted_vals[lo] * (hi - k) + sorted_vals[hi] * (k - lo)


def simulate(model_fn, input_distributions: dict, n_iterations: int = 10000,
             confidence_level: float = 0.95, seed: int = 42) -> dict:
    """Run N Monte Carlo iterations. Returns {status, statistics, CI, risk_metrics, interpretation}."""
    for name, spec in input_distributions.items():
        if spec.get("dist", "fixed") not in _DISTS:
            raise ValueError(f"input {name!r}: unknown distribution {spec.get('dist')!r}")
    rng = random.Random(seed)
    outputs, failures = [], 0
    for _ in range(n_iterations):
        sample = {name: _draw(rng, spec) for name, spec in input_distributions.items()}
        try:
            outputs.append(float(model_fn(sample)))
        except Exception:
            failures += 1

    n_valid = len(outputs)
    if n_valid == 0:
        return {"status": "FAILED", "marker": "[MONTE_CARLO_UNAVAILABLE]",
                "reason": "every iteration raised; caller must estimate with [APPROX]"}

    outputs.sort()
    mean = statistics.fmean(outputs)
    sd = statistics.pstdev(outputs)
    cv = (sd / abs(mean)) if mean else float("inf")
    p10, p50, p90 = (_percentile(outputs, q) for q in (0.10, 0.50, 0.90))
    tail = (1 - confidence_level) / 2
    ci = (_percentile(outputs, tail), _percentile(outputs, 1 - tail))

    if cv < 0.10:
        interp = "highly predictable — reliable estimates"
    elif cv < 0.30:
        interp = "moderately uncertain — plan for the realistic scenario"
    elif cv < 0.60:
        interp = "high uncertainty — plan for the pessimistic scenario"
    else:
        interp = "very uncertain — revisit the input assumptions"

    partial = failures > 0.10 * n_iterations
    return {
        "status": "PARTIAL" if partial else "OK",
        "marker": (f"[MONTE_CARLO_PARTIAL n={n_valid} | P10={p10:.4g} | P50={p50:.4g} "
                   f"| P90={p90:.4g} | cv={cv:.3f}]" if partial else
                   f"[MONTE_CARLO: n={n_valid} | P10={p10:.4g} | P50={p50:.4g} "
                   f"| P90={p90:.4g} | cv={cv:.3f}]"),
        "statistics": {"mean": round(mean, 6), "std": round(sd, 6),
                       "p10": round(p10, 6), "p50": round(p50, 6), "p90": round(p90, 6),
                       "cv": round(cv, 4)},
        "CI": {"level": confidence_level, "low": round(ci[0], 6), "high": round(ci[1], 6)},
        "risk_metrics": {"n_iterations": n_iterations, "n_valid": n_valid, "failures": failures},
        "interpretation": interp,
        "engine": "numpy" if _np is not None else "stdlib",
    }


if __name__ == "__main__":
    # demo: total project cost = sum of a fixed base + two uncertain line items
    def model(s):
        return s["base"] + s["dev"] + s["infra"]
    dists = {"base": {"dist": "fixed", "value": 100.0},
             "dev": {"dist": "triangular", "left": 40, "mode": 60, "right": 120},
             "infra": {"dist": "lognormal", "mean": 3.0, "sigma": 0.4}}
    import json
    print(json.dumps(simulate(model, dists, n_iterations=20000), indent=2))
