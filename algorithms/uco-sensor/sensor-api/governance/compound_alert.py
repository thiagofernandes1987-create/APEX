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
    RED      APS verdict = DEGRADING_PERSISTENT  AND  predictor BIASED_UP
             (quality falling AND the predictor is systematically OPTIMISTIC —
             actual H is *higher* / worse than forecast.  Sprint G fix: prior
             versions wired this to BIASED_DOWN, the opposite sign — pessimistic
             predictor — which is the safe direction, not the dangerous one.)
    AMBER    APS DEGRADING / DEGRADING_PERSISTENT  XOR  predictor BIASED_*
    YELLOW   any degrading APS slope AND predictor MAE high relative to H
    GREEN    nothing else

Sign convention (canonical, see api/server.py:2952):
    bias = actual − forecast
    BIASED_UP    → bias > 0  → actual > forecast → predictor UNDERSHOT
                                                    (genuinely dangerous)
    BIASED_DOWN  → bias < 0  → actual < forecast → predictor OVERSHOT
                                                    (pessimistic / safe)

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
    """Return (tier, reasons[]).

    Sprint G fix (C-2): the RED condition uses BIASED_UP (predictor
    consistently undershoots the actual H = systematically optimistic
    about degradation).  Prior versions used BIASED_DOWN, which is the
    OPPOSITE — a pessimistic predictor whose forecast is *above* what
    actually happens.  That meant the genuinely dangerous regime never
    reached RED and the safe regime falsely did.
    """
    reasons: List[str] = []

    # RED — both signals scream: quality degrading persistently AND
    # the predictor is systematically optimistic about how fast.
    if (aps_verdict == "DEGRADING_PERSISTENT"
            and predictor_verdict == "BIASED_UP"):
        reasons.append("APS degrading persistently (Hurst > 0.55, slope < 0)")
        reasons.append("Predictor consistently undershoots — actual H steeper than forecast (bias > 0)")
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

# Sprint H: aps_trend / predictor_accuracy were duplicated here before —
# they now live in governance.signals as the single source of truth.
# The thin wrappers below preserve the legacy private names so external
# tests that import them (test_marco_m32) keep working.
from governance.signals import aps_trend as _signals_aps_trend
from governance.signals import predictor_accuracy as _signals_pred_accuracy


def _aps_trend_from_store(store: Any, module_id: str, window: int) -> Dict[str, Any]:
    """Deprecated thin wrapper — use governance.signals.aps_trend directly."""
    return _signals_aps_trend(store, module_id, window=window)


def _predictor_accuracy_from_store(store: Any, module_id: str, window: int
                                    ) -> Dict[str, Any]:
    """Deprecated thin wrapper — use governance.signals.predictor_accuracy directly."""
    return _signals_pred_accuracy(store, module_id, window=window)


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
