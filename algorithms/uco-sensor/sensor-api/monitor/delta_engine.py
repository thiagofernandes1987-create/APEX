"""
UCO-Sensor — DeltaEngine  (M8.0, WBS 11.2)
===========================================
Computes per-channel deltas between two consecutive MetricVectors of the
same module: ΔH, ΔCC, Δsecurity, Δreliability and the supporting raw
values needed by the AlertRuleEngine.

Numerical safety (FMEA NUMERICS failure mode)
---------------------------------------------
Percentage deltas guard against a ~0 baseline:

    delta_pct = (curr - prev) / max(|prev|, _EPS_BASELINE)

and a percentage signal is only meaningful when the absolute change also
exceeds ``min_abs_delta`` — tiny absolute moves on tiny baselines would
otherwise produce huge, noisy percentages (FMEA THEORY failure mode).

Public API
----------
    delta = DeltaEngine().compare(prev_mv, curr_mv)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# Baseline floor for percentage computation — avoids div-by-zero and the
# "0.001 → 0.002 = +100%" noise class.
_EPS_BASELINE: float = 0.5


def _safe_pct(prev: float, curr: float) -> float:
    """Percentage change with epsilon-guarded baseline. Returns fraction (0.2 = +20%)."""
    return (curr - prev) / max(abs(prev), _EPS_BASELINE)


def _vector_attr(mv: Any, *path: str, default: float = 0.0) -> float:
    """Dotted-path attribute read tolerant of missing extended vectors."""
    cur: Any = mv
    for p in path:
        cur = getattr(cur, p, None)
        if cur is None:
            return default
    try:
        return float(cur)
    except (TypeError, ValueError):
        return default


@dataclass
class MetricDelta:
    """
    Channel-level differences between two MetricVectors of the same module.

    ``*_pct`` fields are fractions: 0.20 means +20 %.
    """
    module_id: str = ""

    # ── Hamiltonian ───────────────────────────────────────────────────────────
    h_before:  float = 0.0
    h_after:   float = 0.0
    h_delta:   float = 0.0
    h_pct:     float = 0.0

    # ── Cyclomatic complexity ─────────────────────────────────────────────────
    cc_before: float = 0.0
    cc_after:  float = 0.0
    cc_delta:  float = 0.0
    cc_pct:    float = 0.0

    # ── Infinite-loop risk (current value matters more than delta) ───────────
    ilr_before: float = 0.0
    ilr_after:  float = 0.0

    # ── Security (SAST critical+high from SecurityVector, if attached) ───────
    security_before: float = 0.0
    security_after:  float = 0.0
    security_delta:  float = 0.0

    # ── Reliability (bare excepts + resource leaks, if attached) ─────────────
    reliability_before: float = 0.0
    reliability_after:  float = 0.0
    reliability_delta:  float = 0.0

    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":          self.module_id,
            "h_before":           round(self.h_before, 4),
            "h_after":            round(self.h_after, 4),
            "h_delta":            round(self.h_delta, 4),
            "h_pct":              round(self.h_pct, 4),
            "cc_before":          self.cc_before,
            "cc_after":           self.cc_after,
            "cc_delta":           self.cc_delta,
            "cc_pct":             round(self.cc_pct, 4),
            "ilr_before":         round(self.ilr_before, 4),
            "ilr_after":          round(self.ilr_after, 4),
            "security_before":    self.security_before,
            "security_after":     self.security_after,
            "security_delta":     self.security_delta,
            "reliability_before": self.reliability_before,
            "reliability_after":  self.reliability_after,
            "reliability_delta":  self.reliability_delta,
            "timestamp":          self.timestamp,
        }


class DeltaEngine:
    """
    Stateless comparator producing :class:`MetricDelta` from two
    MetricVector-shaped objects (``prev`` may be ``None`` on first sight
    of a module — all ``*_before`` fields then default to 0).
    """

    def compare(self, prev: Optional[Any], curr: Any) -> MetricDelta:
        """Build a MetricDelta from consecutive snapshots of one module."""
        d = MetricDelta(
            module_id=getattr(curr, "module_id", ""),
            timestamp=getattr(curr, "timestamp", 0.0),
        )

        # Hamiltonian
        d.h_before = _vector_attr(prev, "hamiltonian") if prev is not None else 0.0
        d.h_after  = _vector_attr(curr, "hamiltonian")
        d.h_delta  = d.h_after - d.h_before
        d.h_pct    = _safe_pct(d.h_before, d.h_after) if prev is not None else 0.0

        # Cyclomatic complexity
        d.cc_before = _vector_attr(prev, "cyclomatic_complexity") if prev is not None else 0.0
        d.cc_after  = _vector_attr(curr, "cyclomatic_complexity")
        d.cc_delta  = d.cc_after - d.cc_before
        d.cc_pct    = _safe_pct(d.cc_before, d.cc_after) if prev is not None else 0.0

        # Infinite-loop risk
        d.ilr_before = _vector_attr(prev, "infinite_loop_risk") if prev is not None else 0.0
        d.ilr_after  = _vector_attr(curr, "infinite_loop_risk")

        # Security: SAST critical + high (SecurityVector attached by M6.4)
        d.security_before = (
            _vector_attr(prev, "security", "sast_critical")
            + _vector_attr(prev, "security", "sast_high")
        ) if prev is not None else 0.0
        d.security_after = (
            _vector_attr(curr, "security", "sast_critical")
            + _vector_attr(curr, "security", "sast_high")
        )
        d.security_delta = d.security_after - d.security_before

        # Reliability: bare excepts + resource-leak risk (ReliabilityVector M7.3)
        d.reliability_before = (
            _vector_attr(prev, "reliability", "bare_except_count")
            + _vector_attr(prev, "reliability", "resource_leak_risk")
        ) if prev is not None else 0.0
        d.reliability_after = (
            _vector_attr(curr, "reliability", "bare_except_count")
            + _vector_attr(curr, "reliability", "resource_leak_risk")
        )
        d.reliability_delta = d.reliability_after - d.reliability_before

        return d
