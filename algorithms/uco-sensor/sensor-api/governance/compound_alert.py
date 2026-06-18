"""
Sprint A — Compound Alert  (v3.2.5)
====================================
Cross-correlates two persisted signals to produce a single, actionable risk
verdict per module:

  • APS time-series          (LEAP 2) → trend + Hurst R/S
  • Predictor accuracy       (LEAP 4) → MAE + bias + verdict

The compound signal identifies modules where quality is degrading AND
the predictor is systematically wrong about how fast — a class of risk
that no static analyzer in the free market exposes today, because none
persist both streams.

Tier ladder
-----------
    RED      APS verdict = DEGRADING_PERSISTENT  AND  predictor BIASED_DOWN
             (quality falling faster than the model is willing to admit)
    AMBER    APS DEGRADING / DEGRADING_PERSISTENT  XOR  predictor BIASED_*
    YELLOW   any degrading APS slope AND predictor MAE high relative to H
    GREEN    nothing else

priority_score ∈ [0, 100] sorts the repo-wide ranking deterministically.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Reuse the trend + accuracy logic from the api server module to avoid drift.
# Importing the handlers directly would create a circular dep, so we re-call
# the helpers on the store object that the handlers themselves call.


# ─── Compound result dataclass ────────────────────────────────────────────────

@dataclass
class CompoundAlert:
    """Per-module compound risk signal."""
    module_id:        str
    n_samples:        int                       # APS samples used for trend
    aps:              Dict[str, Any]            = field(default_factory=dict)
    predictor:        Dict[str, Any]            = field(default_factory=dict)
    tier:             str                       = "GREEN"      # RED / AMBER / YELLOW / GREEN
    priority_score:   float                     = 0.0
    reasons:          List[str]                 = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":      self.module_id,
            "n_samples":      self.n_samples,
            "aps":            self.aps,
            "predictor":      self.predictor,
            "tier":           self.tier,
            "priority_score": round(self.priority_score, 2),
            "reasons":        self.reasons,
        }


# ─── Tier policy (single source of truth) ─────────────────────────────────────

_DEGRADING_APS = {"DEGRADING", "DEGRADING_PERSISTENT"}
_BIASED_PRED   = {"BIASED_DOWN", "BIASED_UP"}

# Base priority per tier — adjusted slightly by slope / MAE intensity
_TIER_BASE = {"RED": 90.0, "AMBER": 60.0, "YELLOW": 30.0, "GREEN": 5.0}


def _classify(aps_verdict: str, predictor_verdict: str,
              aps_slope: float, predictor_mae_rel: float
              ) -> Tuple[str, List[str]]:
    """Return (tier, reasons[])."""
    reasons: List[str] = []

    # RED — both signals scream
    if (aps_verdict == "DEGRADING_PERSISTENT"
            and predictor_verdict == "BIASED_DOWN"):
        reasons.append("APS degrading persistently (Hurst > 0.55, slope < 0)")
        reasons.append("Predictor consistently undershoots — actual fall steeper than forecast")
        return "RED", reasons

    # AMBER — one of the two strong indicators fires
    if aps_verdict in _DEGRADING_APS:
        reasons.append(f"APS verdict {aps_verdict}")
        return "AMBER", reasons
    if predictor_verdict in _BIASED_PRED:
        reasons.append(f"Predictor verdict {predictor_verdict}")
        return "AMBER", reasons

    # YELLOW — weaker compound: any decline + noisy predictor
    if aps_slope < 0.0 and predictor_mae_rel > 0.10:
        reasons.append(f"APS slope negative ({aps_slope:.2f} units/snapshot)")
        reasons.append(f"Predictor MAE high (~{predictor_mae_rel:.0%} of mean H)")
        return "YELLOW", reasons

    return "GREEN", []


def _priority(tier: str, aps_slope: float, predictor_mae_rel: float) -> float:
    """
    Refine the base tier score with the intensity of each signal.
    Bounded to [0, 100].  Higher = more urgent.
    """
    score = _TIER_BASE[tier]
    # Each step of negative APS slope adds up to +5 points (capped)
    score += min(5.0, max(0.0, -aps_slope))
    # MAE-relative bumps up to +5 (only counts above the 10% floor)
    score += min(5.0, max(0.0, (predictor_mae_rel - 0.10) * 50.0))
    return max(0.0, min(100.0, score))


# ─── Public API ───────────────────────────────────────────────────────────────

def _aps_trend_from_store(store: Any, module_id: str, window: int) -> Dict[str, Any]:
    """
    Compute the APS trend (verdict + slope + Hurst) directly from *store*,
    reusing the exact same logic the /anti-pattern-score/trend endpoint
    runs — but on the store object we were given, not the module-level
    api.server._store.  Returns a dict shaped like the endpoint response.
    """
    raw = store.get_aps_history(module_id, window=window)
    series = [aps for _, _, aps in raw if aps is not None]
    if len(series) < 4:
        return {"verdict": "INSUFFICIENT", "n_samples": len(series),
                "slope": 0.0, "latest_aps": series[-1] if series else None,
                "latest_rating": None, "hurst": 0.5}

    n      = len(series)
    mean   = sum(series) / n
    xs     = list(range(n))
    x_mean = (n - 1) / 2.0
    num = sum((xs[i] - x_mean) * (series[i] - mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n)) or 1.0
    slope = num / den

    try:
        from sensor_core.predictor import hurst_rs
        hurst = hurst_rs(series)
    except Exception:
        hurst = 0.5

    if slope < -0.5 and hurst > 0.55:
        verdict = "DEGRADING_PERSISTENT"
    elif slope < -0.5:
        verdict = "DEGRADING"
    elif slope > 0.5:
        verdict = "IMPROVING"
    else:
        verdict = "STABLE"

    try:
        from metrics.anti_pattern_score import rate_aps
        latest_rating = rate_aps(series[-1])
    except Exception:
        latest_rating = None

    return {
        "verdict":       verdict,
        "n_samples":     n,
        "slope":         round(slope, 4),
        "latest_aps":    round(series[-1], 2),
        "latest_rating": latest_rating,
        "hurst":         round(hurst, 4),
    }


def _predictor_accuracy_from_store(store: Any, module_id: str, window: int
                                    ) -> Dict[str, Any]:
    """
    Same as _aps_trend_from_store but for the predictor accuracy summary
    (mirror of /predictor/accuracy logic, operating on the given store).
    """
    samples = store.get_predictor_history(module_id, window=window)
    pairs = [s["forecast_error"] for s in samples
             if s.get("forecast_error") is not None]
    if len(pairs) < 3:
        return {"verdict": "INSUFFICIENT", "n_evaluated": len(pairs),
                "mae": None, "rmse": None, "bias": None,
                "mae_relative": 0.0}

    n   = len(pairs)
    mae = sum(abs(e) for e in pairs) / n
    rmse = (sum(e * e for e in pairs) / n) ** 0.5
    bias = sum(pairs) / n
    mean_h = sum(s["hamiltonian"] for s in samples) / max(len(samples), 1)
    mae_rel = (mae / mean_h) if mean_h else mae

    if mae_rel < 0.10:
        verdict = "ACCURATE"
    elif abs(bias) > mae / 2:
        verdict = "BIASED_UP" if bias > 0 else "BIASED_DOWN"
    else:
        verdict = "NOISY"

    return {
        "verdict":      verdict,
        "n_evaluated":  n,
        "mae":          round(mae, 4),
        "rmse":         round(rmse, 4),
        "bias":         round(bias, 4),
        "mae_relative": round(mae_rel, 4),
        "mean_hamiltonian": round(mean_h, 4),
    }


def compute_compound_alert(
    store: Any,
    module_id: str,
    window: int = 100,
) -> CompoundAlert:
    """
    Build the compound alert for *module_id* by combining the persisted APS
    trend (LEAP 2) and the predictor accuracy summary (LEAP 4).

    Pure read-only — never writes to the store, never raises on missing data.
    """
    aps_data  = _aps_trend_from_store(store, module_id, window)
    pred_data = _predictor_accuracy_from_store(store, module_id, window)

    aps_verdict  = aps_data.get("verdict", "INSUFFICIENT")
    aps_slope    = float(aps_data.get("slope", 0.0) or 0.0)
    pred_verdict = pred_data.get("verdict", "INSUFFICIENT")
    pred_mae_rel = float(pred_data.get("mae_relative", 0.0) or 0.0)

    tier, reasons = _classify(aps_verdict, pred_verdict, aps_slope, pred_mae_rel)
    priority = _priority(tier, aps_slope, pred_mae_rel)

    return CompoundAlert(
        module_id=module_id,
        n_samples=int(aps_data.get("n_samples", 0) or 0),
        aps={
            "verdict":       aps_verdict,
            "latest":        aps_data.get("latest_aps"),
            "latest_rating": aps_data.get("latest_rating"),
            "slope":         aps_data.get("slope"),
            "hurst":         aps_data.get("hurst"),
        },
        predictor={
            "verdict":      pred_verdict,
            "mae":          pred_data.get("mae"),
            "rmse":         pred_data.get("rmse"),
            "bias":         pred_data.get("bias"),
            "mae_relative": pred_data.get("mae_relative"),
            "n_evaluated":  pred_data.get("n_evaluated"),
        },
        tier=tier,
        priority_score=priority,
        reasons=reasons,
    )


def repo_compound_alerts(
    store: Any,
    window: int = 100,
    top_k: Optional[int] = None,
    include_green: bool = False,
) -> List[CompoundAlert]:
    """
    Run :func:`compute_compound_alert` for every module the store knows about
    and return them sorted by priority_score DESC (worst first).

    Parameters
    ----------
    store          : SnapshotStore-like with ``list_modules()``
    window         : history window passed through to each underlying handler
    top_k          : optional cap on number of results (after sort)
    include_green  : when False (default) GREEN-tier modules are filtered out
                     so the response focuses on actionable items
    """
    modules = list(store.list_modules())
    alerts = [compute_compound_alert(store, m, window=window) for m in modules]

    if not include_green:
        alerts = [a for a in alerts if a.tier != "GREEN"]

    alerts.sort(key=lambda a: a.priority_score, reverse=True)
    if top_k is not None and top_k > 0:
        alerts = alerts[:top_k]
    return alerts


def repo_tier_histogram(alerts: List[CompoundAlert]) -> Dict[str, int]:
    """Count how many modules fell into each tier — for dashboards / CI."""
    histogram = {"RED": 0, "AMBER": 0, "YELLOW": 0, "GREEN": 0}
    for a in alerts:
        if a.tier in histogram:
            histogram[a.tier] += 1
    return histogram
