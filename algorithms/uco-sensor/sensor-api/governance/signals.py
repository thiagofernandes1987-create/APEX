"""
Sprint H — Domain signals (single source of truth)  (v3.3.0)
=============================================================
Pre-Sprint-H the OLS+Hurst trend of APS and the predictor-accuracy
summary lived in **two copies each**:

  • `api/server.py:handle_anti_pattern_score_trend`
  • `governance/compound_alert.py:_aps_trend_from_store`
  • `api/server.py:handle_predictor_accuracy`
  • `governance/compound_alert.py:_predictor_accuracy_from_store`

That duplication is what allowed the C-2 sign-inversion bug to nest in
one copy and stay hidden because the test suite exercised the other.
This module is the **only** place where these computations live.
Both handlers and the Compound Alert call `aps_trend(store, …)` and
`predictor_accuracy(store, …)` — drift is now structurally impossible.

Design contract
---------------
- Pure functions of the (store, module_id, window) triple.
- ``store`` is treated as a duck — anything exposing
  `get_aps_history` / `get_predictor_history` works (in particular
  SnapshotStore for production, a stub object for unit tests).
- Never raise on missing data: every error path returns a structured
  dict with `verdict="INSUFFICIENT"` or `"ERROR"`.
- Hurst gating respects ``sensor_core.predictor._MIN_SAMPLES_RELIABLE``
  (= 8) — set in Sprint G fix C-3.  Below threshold the verdict
  downgrades to plain ``DEGRADING`` (no ``_PERSISTENT``).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


_HURST_PERSISTENT_THRESHOLD = 0.55
_APS_SLOPE_DEGRADING        = -0.5
_APS_SLOPE_IMPROVING        =  0.5
_PREDICTOR_MIN_PAIRS        = 3
_PREDICTOR_MAE_REL_ACCURATE = 0.10


def _min_samples_reliable() -> int:
    """Late-import to avoid circular dependency on sensor_core.predictor.

    Falls back to 8 if the predictor module can't be imported in some
    weird sandbox — that's the canonical value baked in there anyway.
    """
    try:
        from sensor_core.predictor import _MIN_SAMPLES_RELIABLE
        return int(_MIN_SAMPLES_RELIABLE)
    except Exception:
        return 8


# ─── APS trend ────────────────────────────────────────────────────────────────

def aps_trend(store: Any, module_id: str, window: int = 100) -> Dict[str, Any]:
    """
    Compute OLS slope + Hurst R/S verdict over the persisted APS series.

    Returned shape (superset — callers ignore what they don't need):
        {
          "module_id":      str,
          "n_samples":      int,
          "latest_aps":     Optional[float],
          "latest_rating":  Optional[str],
          "slope":          float,           # APS units per snapshot
          "slope_pct":      float,           # slope / mean  (0 when mean=0)
          "intercept":      float,           # OLS intercept (for forecast_next)
          "forecast_next":  float,           # slope * n + intercept
          "hurst":          float,           # 0.5 when not reliable / failed
          "hurst_reliable": bool,
          "verdict":        "DEGRADING_PERSISTENT" | "DEGRADING" |
                            "IMPROVING" | "STABLE" | "INSUFFICIENT",
          "min_required":   int              # only present when INSUFFICIENT
        }
    """
    try:
        raw = store.get_aps_history(module_id, window=window)
    except Exception as exc:
        return {
            "module_id":  module_id,
            "n_samples":  0,
            "verdict":    "ERROR",
            "error":      f"{type(exc).__name__}: {exc}",
        }

    series = [float(aps) for _, _, aps in raw if aps is not None]
    if len(series) < 4:
        return {
            "module_id":    module_id,
            "n_samples":    len(series),
            "verdict":      "INSUFFICIENT",
            "min_required": 4,
            "latest_aps":   round(series[-1], 2) if series else None,
            "latest_rating": _rate(series[-1]) if series else None,
            "slope":        0.0,
            "slope_pct":    0.0,
            "intercept":    0.0,
            "forecast_next": float(series[-1]) if series else 0.0,
            "hurst":        0.5,
            "hurst_reliable": False,
        }

    n      = len(series)
    mean   = sum(series) / n
    xs     = list(range(n))
    x_mean = (n - 1) / 2.0
    num = sum((xs[i] - x_mean) * (series[i] - mean) for i in range(n))
    den = sum((xs[i] - x_mean) ** 2 for i in range(n)) or 1.0
    slope = num / den
    intercept = mean - slope * x_mean
    forecast_next = slope * n + intercept
    slope_pct = (slope / mean) if mean else 0.0

    # Sprint G fix C-3: only compute Hurst when n ≥ _MIN_SAMPLES_RELIABLE.
    hurst, hurst_reliable = _hurst_with_gate(series)

    if slope < _APS_SLOPE_DEGRADING and hurst > _HURST_PERSISTENT_THRESHOLD \
            and hurst_reliable:
        verdict = "DEGRADING_PERSISTENT"
    elif slope < _APS_SLOPE_DEGRADING:
        verdict = "DEGRADING"
    elif slope > _APS_SLOPE_IMPROVING:
        verdict = "IMPROVING"
    else:
        verdict = "STABLE"

    return {
        "module_id":      module_id,
        "n_samples":      n,
        "latest_aps":     round(series[-1], 2),
        "latest_rating":  _rate(series[-1]),
        "slope":          round(slope, 4),
        "slope_pct":      round(slope_pct, 4),
        "intercept":      round(intercept, 4),
        "forecast_next":  round(forecast_next, 2),
        "hurst":          round(hurst, 4),
        "hurst_reliable": hurst_reliable,
        "verdict":        verdict,
    }


def _hurst_with_gate(series):
    n = len(series)
    min_required = _min_samples_reliable()
    if n < min_required:
        return 0.5, False
    try:
        from sensor_core.predictor import hurst_rs
        h = float(hurst_rs(series))
        return h, True
    except Exception:
        return 0.5, False


def _rate(score: Optional[float]) -> Optional[str]:
    try:
        from metrics.anti_pattern_score import rate_aps
        return rate_aps(score)
    except Exception:
        return None


# ─── Predictor accuracy ───────────────────────────────────────────────────────

def predictor_accuracy(store: Any, module_id: str, window: int = 100) -> Dict[str, Any]:
    """
    MAE / RMSE / bias summary over the persisted forecast_error series.

    Sign convention (canonical — Sprint G fix C-2):
        bias = actual - forecast
        BIASED_UP    bias > 0  → predictor undershoots  (dangerous regime)
        BIASED_DOWN  bias < 0  → predictor overshoots   (pessimistic, safe)

    Returned shape::
        {
          "module_id":         str,
          "n_evaluated":       int,
          "verdict":           "ACCURATE" | "BIASED_UP" | "BIASED_DOWN" |
                               "NOISY" | "INSUFFICIENT" | "ERROR",
          "mae":               float,
          "rmse":              float,
          "bias":              float,
          "mae_relative":      float,
          "mean_hamiltonian":  float,
          "min_required":      int    # only present when INSUFFICIENT
        }
    """
    try:
        samples = store.get_predictor_history(module_id, window=window)
    except Exception as exc:
        return {
            "module_id":   module_id,
            "n_evaluated": 0,
            "verdict":     "ERROR",
            "error":       f"{type(exc).__name__}: {exc}",
        }

    evaluated = [s for s in samples if s.get("forecast_error") is not None]
    pairs = [s["forecast_error"] for s in evaluated]
    if len(pairs) < _PREDICTOR_MIN_PAIRS:
        return {
            "module_id":    module_id,
            "n_evaluated":  len(pairs),
            "verdict":      "INSUFFICIENT",
            "min_required": _PREDICTOR_MIN_PAIRS,
            "mae":          None,
            "rmse":         None,
            "bias":         None,
            "mae_relative": 0.0,
        }

    n   = len(pairs)
    mae = sum(abs(e) for e in pairs) / n
    rmse = (sum(e * e for e in pairs) / n) ** 0.5
    bias = sum(pairs) / n
    mean_h = (sum(s["hamiltonian"] for s in evaluated) / n) if n else 0.0
    mae_rel = (mae / mean_h) if mean_h else mae

    if mae_rel < _PREDICTOR_MAE_REL_ACCURATE:
        verdict = "ACCURATE"
    elif abs(bias) > mae / 2:
        verdict = "BIASED_UP" if bias > 0 else "BIASED_DOWN"
    else:
        verdict = "NOISY"

    return {
        "module_id":         module_id,
        "n_evaluated":       n,
        "mae":               round(mae, 4),
        "rmse":              round(rmse, 4),
        "bias":              round(bias, 4),
        "mae_relative":      round(mae_rel, 4),
        "mean_hamiltonian":  round(mean_h, 4),
        "verdict":           verdict,
    }
