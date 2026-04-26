"""
UCO-Sensor — Degradation Predictor  (M5.1)
===========================================
Predicts future code quality degradation combining two signals:

  1. **Hurst Exponent** via Rescaled Range (R/S) analysis:
       H > 0.55 → persistent / trending   (quality keeps degrading)
       H ≈ 0.50 → random walk             (no predictable direction)
       H < 0.45 → anti-persistent         (quality self-corrects)

  2. **OLS Slope** (% change per snapshot):
       positive slope → Hamiltonian growing → degradation

  Combined into `risk_level`: CRITICAL | HIGH | MEDIUM | LOW | STABLE

Requires: numpy (already in dependencies).

Usage:
    from sensor_core.predictor import DegradationPredictor

    predictor = DegradationPredictor(primary_metric="hamiltonian")
    history   = store.get_history("my.module", window=20)
    forecast  = predictor.predict(history, module_id="my.module", horizon=5)
    print(forecast.to_dict())
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np

# ── Thresholds ────────────────────────────────────────────────────────────────

_HURST_PERSISTENT   = 0.55   # H above → persistent trend (amplifies risk)
_HURST_ANTIPERSIST  = 0.45   # H below → mean-reverting

_SLOPE_CRITICAL_PCT = 20.0   # % change per snapshot → CRITICAL
_SLOPE_HIGH_PCT     = 10.0
_SLOPE_MEDIUM_PCT   =  5.0
_SLOPE_LOW_PCT      =  1.0

_MIN_SAMPLES_FORECAST = 4    # minimum snapshots for any forecast
_MIN_SAMPLES_RELIABLE = 8    # minimum for reliable Hurst estimate


# ── DegradationForecast ───────────────────────────────────────────────────────

@dataclass
class DegradationForecast:
    """
    Degradation prediction for one module over a future horizon.

    Attributes
    ----------
    module_id : str
    n_samples : int
        Number of historical snapshots used.
    hurst_exponent : float
        R/S Hurst estimate ∈ [0, 1].
    slope_pct : float
        OLS slope as % change per snapshot (positive = degrading).
    current_h : float
        Most recent Hamiltonian.
    predicted_h : float
        Forecast Hamiltonian at `horizon` snapshots ahead.
    velocity_h_per_snapshot : float
        Raw ΔH per snapshot (OLS slope in original units).
    r_squared : float
        OLS R² goodness-of-fit ∈ [0, 1].
    confidence : float
        Combined confidence ∈ [0, 1] (scales with n_samples × R²).
    risk_level : str
        CRITICAL | HIGH | MEDIUM | LOW | STABLE.
    horizon : int
        Forecast horizon in snapshots.
    advice : str
        Human-readable single-line action recommendation.
    insufficient_data : bool
        True when n_samples < _MIN_SAMPLES_FORECAST.
    """
    module_id:               str
    n_samples:               int
    hurst_exponent:          float
    slope_pct:               float
    current_h:               float
    predicted_h:             float
    velocity_h_per_snapshot: float
    r_squared:               float
    confidence:              float
    risk_level:              str
    horizon:                 int
    advice:                  str
    insufficient_data:       bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":               self.module_id,
            "n_samples":               self.n_samples,
            "hurst_exponent":          round(self.hurst_exponent, 4),
            "slope_pct":               round(self.slope_pct, 4),
            "current_h":               round(self.current_h, 4),
            "predicted_h":             round(self.predicted_h, 4),
            "velocity_h_per_snapshot": round(self.velocity_h_per_snapshot, 6),
            "r_squared":               round(self.r_squared, 4),
            "confidence":              round(self.confidence, 4),
            "risk_level":              self.risk_level,
            "horizon":                 self.horizon,
            "advice":                  self.advice,
            "insufficient_data":       self.insufficient_data,
        }


# ── Hurst R/S estimator ───────────────────────────────────────────────────────

def hurst_rs(series: List[float]) -> float:
    """
    Estimate the Hurst exponent via Rescaled Range (R/S) analysis.

    Algorithm
    ---------
    1. For each sub-series length L (from n//4 to n, step ≈ n//8):
       a. Divide the series into ⌊n/L⌋ non-overlapping sub-series.
       b. For each sub-series:
            • mean-adjust: Z = cumsum(X - mean(X))
            • range:    R = max(Z) - min(Z)
            • std:      S = std(X, ddof=1)
            • ratio:    R/S
       c. Take the average R/S over all sub-series.
    2. Fit log(R/S) = H·log(L) + c via OLS.
    3. H = slope.

    Parameters
    ----------
    series : list[float]
        Time-ordered scalar values (e.g. Hamiltonian per commit).

    Returns
    -------
    float
        H ∈ [0, 1].  Returns 0.5 for series with < 4 points or zero variance.
    """
    arr = np.asarray(series, dtype=float)
    n   = len(arr)

    if n < 4:
        return 0.5
    if float(np.std(arr)) < 1e-10:
        return 0.5   # constant series — no trend

    log_rs: List[float] = []
    log_n:  List[float] = []

    min_len = max(4, n // 4)
    step    = max(1, (n - min_len) // 8)
    lengths = list(range(min_len, n + 1, step))
    if n not in lengths:
        lengths.append(n)

    for sub_len in lengths:
        if sub_len < 4:
            continue
        n_subs = n // sub_len
        if n_subs < 1:
            continue

        rs_vals: List[float] = []
        for k in range(n_subs):
            sub  = arr[k * sub_len: (k + 1) * sub_len]
            mean = float(np.mean(sub))
            z    = np.cumsum(sub - mean)
            r    = float(np.max(z) - np.min(z))
            s    = float(np.std(sub, ddof=1))
            if s > 1e-10 and r > 1e-10:
                rs_vals.append(r / s)

        if rs_vals:
            log_rs.append(math.log(float(np.mean(rs_vals))))
            log_n.append(math.log(float(sub_len)))

    if len(log_rs) < 2:
        return 0.5

    # OLS: H = slope of log(R/S) ~ H·log(L) + c
    x = np.array(log_n)
    y = np.array(log_rs)
    h = float(np.polyfit(x, y, 1)[0])
    return max(0.0, min(1.0, h))


# ── OLS helpers ───────────────────────────────────────────────────────────────

def _ols(xs: List[float], ys: List[float]):
    """Return (slope, intercept) from ordinary least squares."""
    x = np.array(xs, dtype=float)
    y = np.array(ys, dtype=float)
    if len(x) < 2:
        return 0.0, float(y[0]) if len(y) else 0.0
    slope, intercept = np.polyfit(x, y, 1)
    return float(slope), float(intercept)


def _r2(xs, ys, slope: float, intercept: float) -> float:
    """Coefficient of determination R²."""
    x     = np.array(xs, dtype=float)
    y     = np.array(ys, dtype=float)
    n     = len(y)
    if n < 2:
        return 1.0
    mean_y  = float(np.mean(y))
    ss_res  = float(np.sum((y - (slope * x + intercept)) ** 2))
    ss_tot  = float(np.sum((y - mean_y) ** 2))
    return max(0.0, 1.0 - ss_res / ss_tot) if ss_tot > 1e-12 else 1.0


# ── Risk classification ───────────────────────────────────────────────────────

def _classify_risk(
    slope_pct: float,
    hurst:     float,
    insuf:     bool,
) -> str:
    if insuf or slope_pct <= 0:
        return "STABLE"

    persistent = hurst > _HURST_PERSISTENT
    s          = abs(slope_pct)

    if s >= _SLOPE_CRITICAL_PCT or (persistent and s >= _SLOPE_HIGH_PCT):
        return "CRITICAL"
    if s >= _SLOPE_HIGH_PCT     or (persistent and s >= _SLOPE_MEDIUM_PCT):
        return "HIGH"
    if s >= _SLOPE_MEDIUM_PCT:
        return "MEDIUM"
    if s >= _SLOPE_LOW_PCT:
        return "LOW"
    return "STABLE"


def _advice(risk: str, hurst: float, slope_pct: float, predicted_h: float) -> str:
    if risk == "CRITICAL":
        return (
            f"IMMEDIATE ACTION: H forecast = {predicted_h:.1f}. "
            f"Hurst={hurst:.2f} (persistent). Halt new features — remediate now."
        )
    if risk == "HIGH":
        return (
            f"HIGH URGENCY: slope {slope_pct:.1f}%/snapshot. "
            f"Schedule refactoring sprint in current cycle."
        )
    if risk == "MEDIUM":
        return (
            f"Slope {slope_pct:.1f}%/snapshot — monitor closely. "
            f"Address in next sprint if trend persists."
        )
    if risk == "LOW":
        return "Low degradation rate — add to technical debt backlog."
    return "Quality is stable. No action required."


# ── DegradationPredictor ──────────────────────────────────────────────────────

class DegradationPredictor:
    """
    Produces DegradationForecast from a list of MetricVector snapshots.

    Parameters
    ----------
    primary_metric : str
        MetricVector attribute to forecast (default ``"hamiltonian"``).
    default_horizon : int
        Default number of future snapshots to project.
    """

    def __init__(
        self,
        primary_metric:  str = "hamiltonian",
        default_horizon: int = 5,
    ) -> None:
        self.primary_metric  = primary_metric
        self.default_horizon = default_horizon

    def predict(
        self,
        history:   List[Any],            # list[MetricVector]
        module_id: str          = "",
        horizon:   Optional[int] = None,
    ) -> DegradationForecast:
        """
        Forecast degradation from historical MetricVectors.

        Parameters
        ----------
        history : list[MetricVector]
            Ordered oldest → newest.
        module_id : str
            Used in output only; auto-detected from history[0] if empty.
        horizon : int | None
            Forecast horizon.  Defaults to ``self.default_horizon``.

        Returns
        -------
        DegradationForecast
        """
        h_val = horizon if horizon is not None else self.default_horizon
        mid   = module_id or (
            getattr(history[0], "module_id", "unknown") if history else "unknown"
        )
        n     = len(history)
        insuf = n < _MIN_SAMPLES_FORECAST

        # ── Insufficient data fast-path ────────────────────────────────────────
        if insuf or not history:
            return DegradationForecast(
                module_id=mid, n_samples=n,
                hurst_exponent=0.5,  slope_pct=0.0,
                current_h=0.0,       predicted_h=0.0,
                velocity_h_per_snapshot=0.0,
                r_squared=0.0,       confidence=0.0,
                risk_level="STABLE", horizon=h_val,
                advice="Insufficient data — need ≥ 4 snapshots for forecast.",
                insufficient_data=True,
            )

        # ── Extract values ────────────────────────────────────────────────────
        values = [
            float(getattr(mv, self.primary_metric, 0) or 0)
            for mv in history
        ]
        xs = list(range(n))

        # ── OLS slope ────────────────────────────────────────────────────────
        slope, intercept = _ols(xs, values)
        r2_val           = _r2(xs, values, slope, intercept)

        current_h  = values[-1]
        slope_pct  = (slope / max(abs(current_h), 0.01)) * 100.0
        predicted_h = max(0.0, intercept + slope * (n - 1 + h_val))

        # ── Hurst exponent ────────────────────────────────────────────────────
        hurst = hurst_rs(values)

        # ── Confidence ────────────────────────────────────────────────────────
        # Scales with sample count (full at ≥ 20) and goodness-of-fit R²
        sample_factor = min(1.0, n / 20.0)
        confidence    = round(min(1.0, sample_factor * max(0.0, r2_val)), 4)

        # ── Classification ────────────────────────────────────────────────────
        risk   = _classify_risk(slope_pct, hurst, insuf)
        advice = _advice(risk, hurst, slope_pct, predicted_h)

        return DegradationForecast(
            module_id=mid,
            n_samples=n,
            hurst_exponent=round(hurst, 4),
            slope_pct=round(slope_pct, 4),
            current_h=round(current_h, 4),
            predicted_h=round(predicted_h, 4),
            velocity_h_per_snapshot=round(slope, 6),
            r_squared=round(r2_val, 4),
            confidence=confidence,
            risk_level=risk,
            horizon=h_val,
            advice=advice,
            insufficient_data=insuf,
        )
