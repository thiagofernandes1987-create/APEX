"""
UCO-Sensor — AlertRuleEngine  (M8.0, WBS 11.3)
===============================================
Threshold rules that turn a :class:`MetricDelta` into zero or more alerts.

Default rule set (roadmap §4.2.3)
---------------------------------
RULE-H-SPIKE     ΔH > +20 %  AND  |ΔH| ≥ min_abs_h          → WARNING
                 ΔH > +50 %  AND  |ΔH| ≥ min_abs_h          → CRITICAL
RULE-ILR-HIGH    ILR_after > 0.7                            → CRITICAL
RULE-SAST-NEW    security_delta > 0 (new critical/high SAST) → CRITICAL
RULE-CC-SPIKE    ΔCC > +30 % AND ΔCC ≥ 5                    → WARNING
RULE-REL-REGRESS reliability_delta > 0                      → WARNING

The ``min_abs_h`` guard (default 1.0) suppresses percentage noise on
near-zero baselines (FMEA THEORY failure mode — see delta_engine).

Public API
----------
    alerts = AlertRuleEngine().evaluate(delta)
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

from .delta_engine import MetricDelta


@dataclass
class Alert:
    """One triggered alert."""
    rule:      str                # e.g. "RULE-H-SPIKE"
    severity:  str                # "WARNING" | "CRITICAL"
    module_id: str
    message:   str
    value:     float = 0.0        # the offending measurement
    threshold: float = 0.0        # the rule threshold that was crossed
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule":      self.rule,
            "severity":  self.severity,
            "module_id": self.module_id,
            "message":   self.message,
            "value":     round(self.value, 4),
            "threshold": self.threshold,
            "timestamp": self.timestamp,
        }


class AlertRuleEngine:
    """
    Evaluates a MetricDelta against the default threshold rules.

    Thresholds are constructor parameters so CI/governance layers can
    tighten or relax them per repository.
    """

    def __init__(
        self,
        h_warn_pct:   float = 0.20,
        h_crit_pct:   float = 0.50,
        min_abs_h:    float = 1.0,
        ilr_critical: float = 0.70,
        cc_warn_pct:  float = 0.30,
        min_abs_cc:   float = 5.0,
    ):
        self.h_warn_pct   = h_warn_pct
        self.h_crit_pct   = h_crit_pct
        self.min_abs_h    = min_abs_h
        self.ilr_critical = ilr_critical
        self.cc_warn_pct  = cc_warn_pct
        self.min_abs_cc   = min_abs_cc

    def evaluate(self, delta: MetricDelta) -> List[Alert]:
        """Return every alert triggered by *delta* (possibly empty)."""
        alerts: List[Alert] = []
        mod = delta.module_id

        # RULE-H-SPIKE — Hamiltonian degradation
        if delta.h_pct > self.h_warn_pct and abs(delta.h_delta) >= self.min_abs_h:
            severity = "CRITICAL" if delta.h_pct > self.h_crit_pct else "WARNING"
            alerts.append(Alert(
                rule="RULE-H-SPIKE", severity=severity, module_id=mod,
                message=(
                    f"Hamiltonian rose {delta.h_pct:+.0%} "
                    f"({delta.h_before:.2f} → {delta.h_after:.2f})"
                ),
                value=delta.h_pct, threshold=self.h_warn_pct,
            ))

        # RULE-ILR-HIGH — infinite-loop risk above hard ceiling
        if delta.ilr_after > self.ilr_critical:
            alerts.append(Alert(
                rule="RULE-ILR-HIGH", severity="CRITICAL", module_id=mod,
                message=f"Infinite-loop risk at {delta.ilr_after:.2f} (> {self.ilr_critical})",
                value=delta.ilr_after, threshold=self.ilr_critical,
            ))

        # RULE-SAST-NEW — new critical/high security findings
        if delta.security_delta > 0:
            alerts.append(Alert(
                rule="RULE-SAST-NEW", severity="CRITICAL", module_id=mod,
                message=(
                    f"{int(delta.security_delta)} new critical/high SAST finding(s) "
                    f"({int(delta.security_before)} → {int(delta.security_after)})"
                ),
                value=delta.security_delta, threshold=0.0,
            ))

        # RULE-CC-SPIKE — cyclomatic-complexity jump
        if delta.cc_pct > self.cc_warn_pct and delta.cc_delta >= self.min_abs_cc:
            alerts.append(Alert(
                rule="RULE-CC-SPIKE", severity="WARNING", module_id=mod,
                message=(
                    f"Cyclomatic complexity rose {delta.cc_pct:+.0%} "
                    f"({int(delta.cc_before)} → {int(delta.cc_after)})"
                ),
                value=delta.cc_pct, threshold=self.cc_warn_pct,
            ))

        # RULE-REL-REGRESS — reliability regression
        if delta.reliability_delta > 0:
            alerts.append(Alert(
                rule="RULE-REL-REGRESS", severity="WARNING", module_id=mod,
                message=(
                    f"Reliability regression: +{int(delta.reliability_delta)} "
                    f"bare-except/resource-leak site(s)"
                ),
                value=delta.reliability_delta, threshold=0.0,
            ))

        return alerts
