#!/usr/bin/env python3
"""
mental_interpreter.py — APEX mental_interpreter_v4 (v00.32.0, OPP-75), nativized core.

WHAT IT IS: the execution orchestrator for DEEP/RESEARCH/SCIENTIFIC. It turns an intent into
a sized, verified execution plan through four phases:
  SPECULATION (fractal_depth>=2): N PoT programs with stances (optimistic/pessimistic/neutral)
              -> UCO gate each -> parallel execute -> entropy_weighted_merge -> register in
              hypothesis_dag. Emits PARALLEL_POT_COMPLETE / PARTIAL.
  WARMUP:     observe field geometry (N_WARM_BLOCKS).
  PLANNING:   n_final = max(MIN_SIZE, min(n_num, n_rel, MAX_SIZE))
                n_num = numerical limit (curvature, GeometryEstimator.optimal_block_size)
                n_rel = statistical limit (ReliabilityEstimator.optimal_size_for_target)
  PRODUCTION: fixed subprocess pipeline; error_evolution_loop on failure.

This module implements the PLANNING formula and the phase orchestration honestly: the numeric
pieces (n_final, entropy_weighted_merge) are real; the per-stance PoT generation is done by the
LLM (SpeculationPhase) and executed via the sibling scripts (pot, uco_gate, hypothesis_dag).

WHY: Turns intent into a sized, verified execution plan (n_final) instead of an unbounded loop.
WHEN: DEEP/RESEARCH/SCIENTIFIC modes; SPECULATION only when fractal_depth>=2.
WHAT IF IT FAILS: PRODUCTION failure triggers error_evolution_loop; unexpected ESCALATE falls back to MCFEAdapter.
"""
import math

MIN_SIZE, MAX_SIZE = 2, 64


def n_final(n_num, n_rel):
    """APEX planning formula: bounded by both the numerical and statistical limits."""
    return max(MIN_SIZE, min(int(n_num), int(n_rel), MAX_SIZE))


def optimal_block_size_geometry(curvature, base=30):
    """n_num proxy: higher curvature -> smaller blocks (GeometryEstimator idea)."""
    return max(MIN_SIZE, int(base / (1 + max(0.0, curvature))))


def optimal_size_for_target(p_target, epsilon=0.05):
    """n_rel proxy: blocks needed so accumulated reliability >= p_target (ReliabilityEstimator).
    (1-eps)^n >= p_target requires n <= log(p_target)/log(1-eps), so FLOOR is the correct
    bound — ceil produced a plan whose accumulated reliability fell BELOW the target
    (audit fix v1.17.0: p_target=0.9, eps=0.05 gave n=3 -> 0.857 < 0.9)."""
    p_target = min(0.999, max(0.01, p_target))
    return max(MIN_SIZE, math.floor(math.log(p_target) / math.log(1 - epsilon)))


def entropy_weighted_merge(candidates):
    """
    Merge speculative snapshots weighting each by 1/(1+entropy) — lower-entropy (more decisive)
    candidates weigh more. candidates: [{"answer","confidence"(0-1)}]. Real arithmetic.
    """
    if not candidates:
        return {"answer": None, "weight_sum": 0}
    def ent(p):  # binary entropy of a confidence
        p = min(0.999, max(0.001, p))
        return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))
    weights = {}
    for c in candidates:
        w = 1.0 / (1.0 + ent(c["confidence"]))
        weights[str(c["answer"])] = weights.get(str(c["answer"]), 0) + w
    top = max(weights, key=weights.get)
    z = sum(weights.values()) or 1.0
    return {"answer": top, "merged_weight": round(weights[top] / z, 4), "weights": weights}


def plan_phases(cognitive_mode, fractal_depth, curvature=0.5, p_target=0.9):
    """Return the phase plan for a task: which phases run and the computed block size."""
    phases = []
    if cognitive_mode in ("DEEP", "RESEARCH", "SCIENTIFIC") and fractal_depth >= 2:
        phases.append("SPECULATION")   # parallel PoT stances -> UCO -> merge -> hypothesis_dag
    phases += ["WARMUP", "PLANNING", "PRODUCTION"]
    n_num = optimal_block_size_geometry(curvature)
    n_rel = optimal_size_for_target(p_target)
    return {"phases": phases, "n_num": n_num, "n_rel": n_rel, "n_final": n_final(n_num, n_rel)}


if __name__ == "__main__":
    print("plan (SCIENTIFIC, depth 3):", plan_phases("SCIENTIFIC", 3, curvature=1.2, p_target=0.95))
    print("plan (STANDARD, depth 1):", plan_phases("STANDARD", 1))
    print("entropy_weighted_merge:", entropy_weighted_merge(
        [{"answer": "X", "confidence": 0.9}, {"answer": "X", "confidence": 0.85},
         {"answer": "Y", "confidence": 0.55}]))
