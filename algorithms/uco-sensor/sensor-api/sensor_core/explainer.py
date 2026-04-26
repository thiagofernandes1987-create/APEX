"""
UCO-Sensor — FixExplainer  (M5.3)
===================================
Bridges AutofixResult (M5.2) + DegradationForecast (M5.1) + APEX Templates
into a structured ``ExplanationReport`` ready to be consumed by the APEX
engineer agent.

Responsibilities
----------------
1. Auto-detect anomaly type when not provided (from transforms applied +
   forecast risk signals).
2. Render the APEX apex_prompt with real metric values from the analysis.
3. Summarise what the AutofixEngine already corrected.
4. List what transforms still remain for a human/agent to perform.
5. Build a risk_narrative from the DegradationForecast (if available).

Usage
-----
    from sensor_core.explainer import FixExplainer
    from sensor_core.autofix import AutofixEngine

    engine  = AutofixEngine()
    result  = engine.apply(source)
    exp     = FixExplainer()
    report  = exp.explain(result, module_id="src/auth.py")
    print(report.apex_prompt)
    print(report.to_dict())
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from apex_integration.templates import (
    get_template,
    render_prompt,
    fix_action_for,
    all_error_types,
)
from sensor_core.autofix.engine import AutofixResult
from sensor_core.predictor import DegradationForecast


# ── Mapping: AutofixEngine transform → APEX anomaly type ─────────────────────

_TRANSFORM_TO_ANOMALY: Dict[str, str] = {
    "DeadCodeRemover":      "DEAD_CODE_DRIFT",
    "UnusedImportRemover":  "DEAD_CODE_DRIFT",
    "RedundantElseRemover": "COGNITIVE_COMPLEXITY_EXPLOSION",
    "BooleanSimplifier":    "COGNITIVE_COMPLEXITY_EXPLOSION",
}

# Forecast risk → anomaly when no transforms fired
_RISK_TO_ANOMALY: Dict[str, str] = {
    "CRITICAL": "TECH_DEBT_ACCUMULATION",
    "HIGH":     "TECH_DEBT_ACCUMULATION",
    "MEDIUM":   "COGNITIVE_COMPLEXITY_EXPLOSION",
    "LOW":      "DEAD_CODE_DRIFT",
    "STABLE":   "UNKNOWN",
}


def _infer_anomaly_type(
    result:   AutofixResult,
    forecast: Optional[DegradationForecast],
) -> str:
    """
    Infer the most relevant APEX anomaly type from available signals.

    Priority:
      1. Dominant transform applied by AutofixEngine.
      2. DegradationForecast risk_level.
      3. Fallback → "TECH_DEBT_ACCUMULATION".
    """
    # Count which anomaly type appears most from applied transforms
    counts: Dict[str, int] = {}
    for tr in result.transforms_applied:
        atype = _TRANSFORM_TO_ANOMALY.get(tr.transform)
        if atype:
            counts[atype] = counts.get(atype, 0) + 1

    if counts:
        return max(counts, key=lambda k: counts[k])

    if forecast and forecast.risk_level in _RISK_TO_ANOMALY:
        return _RISK_TO_ANOMALY[forecast.risk_level]

    return "TECH_DEBT_ACCUMULATION"


# ── ExplanationReport ─────────────────────────────────────────────────────────

@dataclass
class ExplanationReport:
    """
    Structured APEX explanation combining AutofixResult and DegradationForecast.

    Attributes
    ----------
    module_id : str
    anomaly_type : str
        APEX anomaly classification (e.g. "TECH_DEBT_ACCUMULATION").
    apex_prompt : str
        Ready-to-use prompt for the APEX engineer agent.
    mode : str
        APEX execution mode: FAST | DEEP | RESEARCH | SCIENTIFIC.
    agents : list[str]
        Recommended APEX agents to involve.
    transforms_summary : str
        Human-readable summary of what AutofixEngine already corrected.
    transforms_auto_applied : list[str]
        Names of transforms that were automatically applied.
    remaining_transforms : list[str]
        Transforms recommended by the APEX template that still need manual work.
    success_criteria : str
        APEX-defined success criteria for this anomaly type.
    risk_narrative : str
        Narrative derived from DegradationForecast (empty if no forecast).
    intervention_now : bool
        True if the APEX template requires immediate action.
    uco_channels : list[str]
        UCO metric channels most affected.
    autofix_changed : bool
        Whether AutofixEngine actually changed the source.
    """
    module_id:               str
    anomaly_type:            str
    apex_prompt:             str
    mode:                    str
    agents:                  List[str]
    transforms_summary:      str
    transforms_auto_applied: List[str]
    remaining_transforms:    List[str]
    success_criteria:        str
    risk_narrative:          str
    intervention_now:        bool
    uco_channels:            List[str]
    autofix_changed:         bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":               self.module_id,
            "anomaly_type":            self.anomaly_type,
            "apex_prompt":             self.apex_prompt,
            "mode":                    self.mode,
            "agents":                  self.agents,
            "transforms_summary":      self.transforms_summary,
            "transforms_auto_applied": self.transforms_auto_applied,
            "remaining_transforms":    self.remaining_transforms,
            "success_criteria":        self.success_criteria,
            "risk_narrative":          self.risk_narrative,
            "intervention_now":        self.intervention_now,
            "uco_channels":            self.uco_channels,
            "autofix_changed":         self.autofix_changed,
        }


# ── FixExplainer ──────────────────────────────────────────────────────────────

class FixExplainer:
    """
    Generates an ExplanationReport from AutofixResult and optional forecast.

    Parameters
    ----------
    default_anomaly : str | None
        Override for anomaly type inference.  ``None`` = auto-detect.
    """

    def __init__(self, default_anomaly: Optional[str] = None) -> None:
        self._default_anomaly = default_anomaly

    # ── Public ────────────────────────────────────────────────────────────────

    def explain(
        self,
        autofix_result: AutofixResult,
        module_id:      str                         = "unknown.module",
        forecast:       Optional[DegradationForecast] = None,
        anomaly_type:   Optional[str]               = None,
        # Optional raw metric values for richer apex_prompt rendering
        delta_h:        float = 0.0,
        hurst:          float = 0.5,
        commit:         str   = "HEAD",
        cc:             int   = 1,
        delta_cc:       int   = 0,
        dsm_density:    float = 0.0,
        dsm_cyclic:     float = 0.0,
        ilr:            float = 0.0,
        dead:           int   = 0,
        halstead:       float = 0.0,
        severity:       str   = "WARNING",
    ) -> ExplanationReport:
        """
        Build an ExplanationReport for the given autofix result.

        Parameters
        ----------
        autofix_result : AutofixResult
            Output of AutofixEngine.apply().
        module_id : str
        forecast : DegradationForecast | None
            From DegradationPredictor.predict() — enriches risk_narrative.
        anomaly_type : str | None
            Override APEX anomaly classification.  Auto-detected if None.
        delta_h … severity : optional raw metric values for prompt rendering.
        """
        # ── 1. Resolve anomaly type ───────────────────────────────────────────
        atype = (
            anomaly_type
            or self._default_anomaly
            or _infer_anomaly_type(autofix_result, forecast)
        )
        if atype not in all_error_types() and atype != "UNKNOWN":
            atype = "UNKNOWN"

        # ── 2. Pull template action ───────────────────────────────────────────
        action = fix_action_for(atype)
        tmpl   = get_template(atype)

        # ── 3. Enrich delta_h from forecast when not provided ─────────────────
        if delta_h == 0.0 and forecast and not forecast.insufficient_data:
            delta_h = round(forecast.predicted_h - forecast.current_h, 4)
        if hurst == 0.5 and forecast:
            hurst = forecast.hurst_exponent

        # ── 4. Render apex_prompt ─────────────────────────────────────────────
        apex = render_prompt(
            error_type=atype,
            module_id=module_id,
            delta_h=delta_h,
            hurst=hurst,
            commit=commit,
            cc=cc,
            delta_cc=delta_cc,
            dsm_density=dsm_density,
            dsm_cyclic=dsm_cyclic,
            ilr=ilr,
            dead=dead,
            halstead=halstead,
            severity=severity,
        )

        # ── 5. Transforms summary ─────────────────────────────────────────────
        applied_names = [tr.transform for tr in autofix_result.transforms_applied]
        applied_descs = [tr.description for tr in autofix_result.transforms_applied]
        if applied_descs:
            transforms_summary = (
                f"AutofixEngine applied {len(applied_descs)} change(s): "
                + "; ".join(applied_descs[:5])
                + ("…" if len(applied_descs) > 5 else "")
            )
        else:
            transforms_summary = "No automatic transforms were applied."

        # ── 6. Remaining transforms ───────────────────────────────────────────
        # Template suggests transforms; subtract those already automated
        _AUTO_NAMES = {
            "remove_dead_code",
            "remove_unused_imports",
            "simplify_conditionals",
            "early_return",
        }
        remaining = [
            t for t in action["transforms"]
            if t not in _AUTO_NAMES
        ]

        # ── 7. Risk narrative from forecast ───────────────────────────────────
        risk_narrative = ""
        if forecast and not forecast.insufficient_data:
            risk_narrative = (
                f"Degradation forecast ({forecast.n_samples} snapshots): "
                f"slope={forecast.slope_pct:+.2f}%/snapshot | "
                f"Hurst={forecast.hurst_exponent:.3f} | "
                f"predicted_H={forecast.predicted_h:.2f} in {forecast.horizon} snapshots | "
                f"risk={forecast.risk_level} | "
                f"confidence={forecast.confidence:.2f}. "
                + forecast.advice
            )
        elif forecast and forecast.insufficient_data:
            risk_narrative = (
                "Insufficient historical data for degradation forecast "
                f"({forecast.n_samples} snapshots — need ≥ 4)."
            )

        return ExplanationReport(
            module_id=module_id,
            anomaly_type=atype,
            apex_prompt=apex,
            mode=action["mode"],
            agents=action["agents"],
            transforms_summary=transforms_summary,
            transforms_auto_applied=list(dict.fromkeys(applied_names)),  # dedup, order-preserving
            remaining_transforms=remaining,
            success_criteria=action["success_criteria"],
            risk_narrative=risk_narrative,
            intervention_now=action["intervention_now"],
            uco_channels=action["uco_channels"],
            autofix_changed=autofix_result.changed,
        )
