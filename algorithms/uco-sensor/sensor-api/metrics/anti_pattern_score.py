"""
UCO-Sensor — Anti-Pattern Score (APS)  (M7.7)
==============================================
Aggregates seventeen signals from the extended-vector family into a single
[0, 100] composite that maps to a SonarQube-style A–E quality gate.

Score = 100 means perfect (no anti-patterns).
Score =   0 means every threshold maximally violated.

Components
----------
The APS is a weighted average of seventeen per-signal sub-scores.  Each
sub-score is ``min(1.0, raw / threshold)`` — i.e. clipped after the value
hits the "critical" threshold.  Weights group the signals into five
dimensions:

* Security        — taint, injection, SCA, IaC  (sum 60)
* Reliability     — bare_except, leaks, defaults (sum 20)
* Performance     — N+1, nested loops, str concat (sum 15)
* Maintainability — docs, length, hotspot         (sum 15)
* Thread safety   — locks, asyncio blocking, globals (sum 20)

Sub-totals are normalised by ``sum(weights)`` (130) and inverted so that
high raw values lower the score.  The final number is rounded to two
decimals.

Rating ladder (matches SonarQube's classic A–E gate)
----------------------------------------------------
A  ≥ 90
B  80 – 89
C  60 – 79
D  40 – 59
E  <  40

Public API
----------
    APS_COMPONENTS                       — the weight table (frozen)
    APS_WEIGHT_SUM                       — sum of all weights
    compute_aps(signals: dict) -> float  — main scoring function
    rate_aps(score: float)    -> str     — A–E grade
    aps_from_metric_vector(mv) -> dict   — convenience: extract & score

Reference
---------
Roadmap UCO_SENSOR_ROADMAP.md §7.5 — APS_COMPONENTS table is authoritative.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Tuple


# ─── Component table — frozen ────────────────────────────────────────────────
# Each entry: signal_name -> (weight, critical_threshold)
# A *raw* value of 0 contributes 0 to the violation total.
# A raw value at the threshold contributes ``weight``.
# Anything past the threshold is clipped to ``weight``.

APS_COMPONENTS: Mapping[str, Tuple[int, float]] = {
    # ── Security — peso 60 ───────────────────────────────────────────────────
    "taint_path_count":            (30, 1.0),
    "injection_surface":           (15, 0.5),
    "sca_vulnerable_deps":         (10, 3.0),
    "iac_misconfig_count":         ( 5, 5.0),
    # ── Reliability — peso 20 ────────────────────────────────────────────────
    "bare_except_count":           ( 5, 3.0),
    "resource_leak_risk":          ( 5, 2.0),
    "mutable_default_arg_count":   ( 5, 2.0),
    "inconsistent_return_count":   ( 5, 3.0),
    # ── Performance — peso 15 ────────────────────────────────────────────────
    "n_plus_one_risk":             ( 5, 1.0),
    "quadratic_nested_loop_count": ( 5, 2.0),
    "string_concat_in_loop":       ( 5, 3.0),
    # ── Maintainability — peso 15 ────────────────────────────────────────────
    "missing_docstring_ratio":     ( 5, 0.5),
    "long_function_ratio":         ( 5, 0.3),
    "cognitive_cc_hotspot":        ( 5, 20.0),
    # ── Thread safety — peso 20 ──────────────────────────────────────────────
    "lock_missing_count":          (10, 1.0),
    "asyncio_blocking_call":       ( 5, 1.0),
    "global_shared_state_count":   ( 5, 2.0),
}

APS_WEIGHT_SUM: int = sum(w for w, _ in APS_COMPONENTS.values())  # = 130


# ─── Scoring ──────────────────────────────────────────────────────────────────

def compute_aps(signals: Dict[str, Any]) -> float:
    """
    Compute the Anti-Pattern Score in [0, 100] from a flat *signals* dict.

    Missing keys default to 0 (best possible value for that signal).
    Negative or non-numeric values are coerced to 0.

    Parameters
    ----------
    signals
        Flat mapping ``{signal_name: raw_value}``.  Only keys in
        ``APS_COMPONENTS`` are considered — extra keys are ignored.

    Returns
    -------
    float
        APS in [0.0, 100.0].  Higher is better (zero anti-patterns → 100).
    """
    if not signals:
        return 100.0

    violation = 0.0
    for name, (weight, threshold) in APS_COMPONENTS.items():
        raw = signals.get(name, 0)
        try:
            raw_f = float(raw)
        except (TypeError, ValueError):
            raw_f = 0.0
        if raw_f < 0:
            raw_f = 0.0
        normalised = min(1.0, raw_f / max(threshold, 1e-9))
        violation += weight * normalised

    score = 100.0 * (1.0 - violation / APS_WEIGHT_SUM)
    return round(max(0.0, min(100.0, score)), 2)


def rate_aps(score: float) -> str:
    """
    Map an APS score to an A–E grade.

    A  ≥ 90
    B  80–89
    C  60–79
    D  40–59
    E  <  40
    """
    if score >= 90.0: return "A"
    if score >= 80.0: return "B"
    if score >= 60.0: return "C"
    if score >= 40.0: return "D"
    return "E"


# ─── Convenience extraction from a MetricVector-shaped object ────────────────

def _read(obj: Any, *path: str) -> Any:
    """Resolve a dotted path against an object's attributes (None on miss)."""
    cur: Any = obj
    for p in path:
        if cur is None:
            return None
        cur = getattr(cur, p, None)
    return cur


def aps_from_metric_vector(mv: Any) -> Dict[str, Any]:
    """
    Extract the 17 signals required by ``compute_aps`` from a MetricVector-like
    object, then compute and grade the score.

    The function is tolerant: any missing attribute is treated as a 0 raw
    value, which is also the best-case contribution to the score.

    Returns
    -------
    dict
        ``{"aps": float, "rating": str, "components": dict[str, float]}``
        where ``components[name] = min(1.0, raw / threshold)`` — useful for
        radar charts and per-dimension dashboards.
    """
    signals: Dict[str, Any] = {
        # Security
        "taint_path_count":            _read(mv, "flow",           "taint_path_count")           or 0,
        "injection_surface":           _read(mv, "flow",           "injection_surface")          or 0.0,
        "sca_vulnerable_deps":         _read(mv, "security",       "sca_vulnerable_deps")        or 0,
        "iac_misconfig_count":         _read(mv, "security",       "iac_misconfig_count")        or 0,
        # Reliability
        "bare_except_count":           _read(mv, "reliability",    "bare_except_count")          or 0,
        "resource_leak_risk":          _read(mv, "reliability",    "resource_leak_risk")         or 0,
        "mutable_default_arg_count":   _read(mv, "reliability",    "mutable_default_arg_count")  or 0,
        "inconsistent_return_count":   _read(mv, "reliability",    "inconsistent_return_count")  or 0,
        # Performance
        "n_plus_one_risk":             _read(mv, "performance",    "n_plus_one_risk")            or 0,
        "quadratic_nested_loop_count": _read(mv, "performance",    "quadratic_nested_loop_count") or 0,
        "string_concat_in_loop":       _read(mv, "performance",    "string_concat_in_loop")      or 0,
        # Maintainability
        "missing_docstring_ratio":     _read(mv, "maintainability", "missing_docstring_ratio")   or 0.0,
        "long_function_ratio":         _read(mv, "maintainability", "long_function_ratio")       or 0.0,
        "cognitive_cc_hotspot":        _read(mv, "maintainability", "cognitive_cc_hotspot")      or 0,
        # Thread safety
        "lock_missing_count":          _read(mv, "thread_safety",  "lock_missing_count")         or 0,
        "asyncio_blocking_call":       _read(mv, "thread_safety",  "asyncio_blocking_call")      or 0,
        "global_shared_state_count":   _read(mv, "thread_safety",  "global_shared_state_count")  or 0,
    }

    score = compute_aps(signals)
    components: Dict[str, float] = {}
    for name, (_, threshold) in APS_COMPONENTS.items():
        raw = signals.get(name, 0)
        try:
            raw_f = max(0.0, float(raw))
        except (TypeError, ValueError):
            raw_f = 0.0
        components[name] = round(min(1.0, raw_f / max(threshold, 1e-9)), 4)

    return {
        "aps":        score,
        "rating":     rate_aps(score),
        "components": components,
        "signals":    signals,
    }
