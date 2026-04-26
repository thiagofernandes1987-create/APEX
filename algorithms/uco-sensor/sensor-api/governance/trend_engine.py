"""
UCO-Sensor — Trend Engine (M2.3 + M2.4)
==========================================

M2.3  Trend Analysis — per-module quality trend over commit history
M2.4  Debt Budget    — technical debt budget tracking + velocity

Trend Analysis
--------------
Given a list of MetricVector snapshots (ordered by timestamp ascending),
compute for a chosen metric field:
  - Linear regression slope (positive = getting worse for H/CC)
  - Normalised volatility (coefficient of variation)
  - Direction: IMPROVING | STABLE | DEGRADING | VOLATILE | INSUFFICIENT_DATA
  - Forecast: estimated value at next commit (via regression extrapolation)

All computations are pure stdlib (no numpy/scipy).

Debt Budget
-----------
Tracks total SQALE technical debt across a project's modules and computes:
  - total_debt_minutes    : sum across all tracked modules
  - budget_minutes        : configured ceiling
  - remaining_minutes     : budget − spent
  - velocity_min_per_day  : debt accumulated in the last N days
  - over_budget           : bool

Public API
----------
    analyze_trend(history, field, window)  -> TrendAnalysis
    track_debt_budget(module_debts, budget_minutes, lookback_days)  -> DebtBudget
    trend_summary(trend)                   -> str
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ── Direction constants ───────────────────────────────────────────────────────

IMPROVING         = "IMPROVING"
STABLE            = "STABLE"
DEGRADING         = "DEGRADING"
VOLATILE          = "VOLATILE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"

# Slope thresholds (relative to the metric mean) to classify direction
_SLOPE_THRESHOLD    = 0.02   # 2% of mean per snapshot = meaningful change
_VOLATILITY_THRESHOLD = 0.30  # CV > 30% = volatile


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class TrendPoint:
    """One data point in a trend series."""
    timestamp:  float
    commit_hash: str
    value:      float


@dataclass
class TrendAnalysis:
    """Trend analysis result for one module / metric."""
    module_id:          str
    metric:             str
    direction:          str           # IMPROVING | STABLE | DEGRADING | VOLATILE | INSUFFICIENT_DATA
    slope:              float         # raw slope (units/snapshot)
    slope_pct:          float         # slope as % of mean (normalised)
    volatility:         float         # coefficient of variation (std/mean)
    window_used:        int           # how many snapshots were used
    mean:               float         # mean value over window
    latest:             float         # most recent value
    forecast_next:      float         # estimated value at next commit
    worst_snapshot:     Optional[str] # commit_hash of peak (worst) value
    improving_since:    Optional[str] # commit_hash where improvement started
    points:             List[TrendPoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":      self.module_id,
            "metric":         self.metric,
            "direction":      self.direction,
            "slope":          round(self.slope, 6),
            "slope_pct":      round(self.slope_pct, 4),
            "volatility":     round(self.volatility, 4),
            "window_used":    self.window_used,
            "mean":           round(self.mean, 4),
            "latest":         round(self.latest, 4),
            "forecast_next":  round(self.forecast_next, 4),
            "worst_snapshot": self.worst_snapshot,
            "improving_since": self.improving_since,
        }


@dataclass
class DebtBudget:
    """Technical debt budget status for a project."""
    total_debt_minutes:   int
    budget_minutes:       int
    remaining_minutes:    int
    over_budget:          bool
    budget_pct_used:      float          # 0–100+
    velocity_min_per_day: float          # debt added per day (last N days)
    days_until_exhausted: Optional[float] # None if improving or no velocity
    module_debts:         Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_debt_minutes":   self.total_debt_minutes,
            "budget_minutes":       self.budget_minutes,
            "remaining_minutes":    self.remaining_minutes,
            "over_budget":          self.over_budget,
            "budget_pct_used":      round(self.budget_pct_used, 1),
            "velocity_min_per_day": round(self.velocity_min_per_day, 2),
            "days_until_exhausted": (
                round(self.days_until_exhausted, 1)
                if self.days_until_exhausted is not None else None
            ),
            "top_debtor_modules": sorted(
                self.module_debts.items(), key=lambda x: x[1], reverse=True
            )[:10],
        }


# ── Trend analysis ────────────────────────────────────────────────────────────

def analyze_trend(
    history:    List[Any],       # list of MetricVector objects (ascending timestamp)
    metric:     str  = "hamiltonian",
    window:     int  = 10,
    module_id:  str  = "",
) -> TrendAnalysis:
    """
    Analyse the trend of `metric` over the last `window` snapshots.

    Parameters
    ----------
    history   : MetricVector list, ordered by timestamp ascending
    metric    : name of the metric field to analyse
    window    : maximum number of recent snapshots to use
    module_id : for labelling the result

    Returns
    -------
    TrendAnalysis with direction, slope, volatility, forecast
    """
    if not history:
        return _insufficient(module_id, metric, 0)

    # Extract values
    snapshots = history[-window:]
    points: List[TrendPoint] = []
    for mv in snapshots:
        v = getattr(mv, metric, None)
        if v is None:
            # Try ratings sub-field
            ratings = getattr(mv, "ratings", {})
            if isinstance(ratings, dict) and metric.startswith("rating_"):
                v = ratings.get(metric[7:])
            if v is None:
                continue
        try:
            fv = float(v)
        except (TypeError, ValueError):
            continue
        points.append(TrendPoint(
            timestamp=getattr(mv, "timestamp", 0.0),
            commit_hash=getattr(mv, "commit_hash", ""),
            value=fv,
        ))

    n = len(points)
    if n < 2:
        return _insufficient(module_id, metric, n)

    values = [p.value for p in points]
    mean_val = sum(values) / n

    # Linear regression (x = index 0..n-1)
    xs = list(range(n))
    slope, intercept = _linear_regression(xs, values)
    forecast_next = slope * n + intercept

    # Normalised slope: slope / mean
    slope_pct = (slope / mean_val) if mean_val != 0 else 0.0

    # Volatility: coefficient of variation
    std_val = _std(values)
    cv = (std_val / mean_val) if mean_val != 0 else 0.0

    # Direction classification
    # VOLATILE only when CV is high AND the linear fit is poor (low R²).
    # A monotonically increasing/decreasing series has high CV but R²≈1 → DEGRADING/IMPROVING.
    r2 = _r_squared(xs, values, slope, intercept)
    if cv > _VOLATILITY_THRESHOLD and r2 < 0.6 and n >= 4:
        direction = VOLATILE
    elif abs(slope_pct) < _SLOPE_THRESHOLD:
        direction = STABLE
    elif slope_pct > 0:
        direction = DEGRADING   # metric going up = worse (H, CC, etc.)
    else:
        direction = IMPROVING

    # Worst snapshot (highest value for degradation metrics)
    worst_idx = values.index(max(values))
    worst_hash = points[worst_idx].commit_hash if worst_idx < len(points) else None

    # Improving-since: first commit after which values consistently improved
    improving_since_hash: Optional[str] = None
    if direction == IMPROVING and n >= 3:
        for i in range(n - 2, 0, -1):
            if values[i] > values[i + 1]:  # found a local increase before improvement
                improving_since_hash = points[i + 1].commit_hash
                break

    return TrendAnalysis(
        module_id=module_id or (getattr(history[-1], "module_id", "") if history else ""),
        metric=metric,
        direction=direction,
        slope=slope,
        slope_pct=slope_pct,
        volatility=cv,
        window_used=n,
        mean=mean_val,
        latest=values[-1],
        forecast_next=forecast_next,
        worst_snapshot=worst_hash,
        improving_since=improving_since_hash,
        points=points,
    )


def _insufficient(module_id: str, metric: str, n: int) -> TrendAnalysis:
    return TrendAnalysis(
        module_id=module_id,
        metric=metric,
        direction=INSUFFICIENT_DATA,
        slope=0.0,
        slope_pct=0.0,
        volatility=0.0,
        window_used=n,
        mean=0.0,
        latest=0.0,
        forecast_next=0.0,
        worst_snapshot=None,
        improving_since=None,
    )


# ── Debt Budget tracking ──────────────────────────────────────────────────────

def track_debt_budget(
    module_debts:   Dict[str, int],   # {module_id: current_debt_minutes}
    budget_minutes: int = 480,        # default: 1 working day
    lookback_days:  float = 30.0,
    prev_total_debt: Optional[int] = None,  # total from N days ago (for velocity)
) -> DebtBudget:
    """
    Compute technical debt budget status.

    Parameters
    ----------
    module_debts    : {module_id: sqale_debt_minutes} for all modules
    budget_minutes  : maximum acceptable debt (default: 480 min = 1 day)
    lookback_days   : period for velocity calculation
    prev_total_debt : total debt N days ago (for velocity); None = unknown
    """
    total = sum(module_debts.values())
    remaining = budget_minutes - total
    over = total > budget_minutes
    pct_used = (total / max(1, budget_minutes)) * 100.0

    if prev_total_debt is not None and lookback_days > 0:
        delta = total - prev_total_debt
        velocity = delta / lookback_days
    else:
        velocity = 0.0

    days_until: Optional[float] = None
    if velocity > 0 and remaining > 0:
        days_until = remaining / velocity
    elif velocity > 0 and over:
        days_until = 0.0

    return DebtBudget(
        total_debt_minutes=total,
        budget_minutes=budget_minutes,
        remaining_minutes=remaining,
        over_budget=over,
        budget_pct_used=pct_used,
        velocity_min_per_day=velocity,
        days_until_exhausted=days_until,
        module_debts=dict(module_debts),
    )


# ── Multi-metric trend summary ────────────────────────────────────────────────

def analyze_module_trends(
    history:    List[Any],
    module_id:  str = "",
    window:     int = 10,
    metrics:    Optional[List[str]] = None,
) -> Dict[str, TrendAnalysis]:
    """
    Compute trend analysis for multiple metrics of a single module.

    Returns {metric_name: TrendAnalysis}
    """
    if metrics is None:
        metrics = [
            "hamiltonian",
            "cyclomatic_complexity",
            "infinite_loop_risk",
            "halstead_bugs",
            "cognitive_complexity",
            "sqale_debt_minutes",
        ]
    return {
        m: analyze_trend(history, metric=m, window=window, module_id=module_id)
        for m in metrics
    }


def trend_summary(trend: TrendAnalysis) -> str:
    """One-line human-readable summary of a trend analysis."""
    arrows = {
        IMPROVING:         "↓ IMPROVING",
        STABLE:            "→ STABLE",
        DEGRADING:         "↑ DEGRADING",
        VOLATILE:          "⚡ VOLATILE",
        INSUFFICIENT_DATA: "? INSUFFICIENT DATA",
    }
    arrow = arrows.get(trend.direction, "?")
    return (
        f"{trend.module_id} [{trend.metric}] {arrow} | "
        f"latest={trend.latest:.2f}  mean={trend.mean:.2f}  "
        f"slope={trend.slope_pct:+.1%}  "
        f"forecast={trend.forecast_next:.2f} (n={trend.window_used})"
    )


def overall_trend(trends: Dict[str, TrendAnalysis]) -> str:
    """
    Aggregate direction across multiple metrics for a module.

    Returns: IMPROVING | STABLE | DEGRADING | VOLATILE | MIXED
    """
    directions = [t.direction for t in trends.values()
                  if t.direction != INSUFFICIENT_DATA]
    if not directions:
        return INSUFFICIENT_DATA
    unique = set(directions)
    if unique == {IMPROVING}:
        return IMPROVING
    if unique == {STABLE}:
        return STABLE
    if DEGRADING in unique or VOLATILE in unique:
        return DEGRADING
    return "MIXED"


# ── Pure-stdlib math utilities ────────────────────────────────────────────────

def _linear_regression(x: List[float], y: List[float]) -> Tuple[float, float]:
    """Return (slope, intercept) for a simple linear regression."""
    n = len(x)
    if n < 2:
        return 0.0, (y[0] if y else 0.0)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den = sum((xi - mean_x) ** 2 for xi in x)
    slope     = num / den if den != 0 else 0.0
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _r_squared(x: List[float], y: List[float], slope: float, intercept: float) -> float:
    """Coefficient of determination R² for the linear fit."""
    n = len(y)
    if n < 2:
        return 1.0
    mean_y = sum(y) / n
    ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
    ss_tot = sum((yi - mean_y) ** 2 for yi in y)
    return 1.0 - ss_res / ss_tot if ss_tot != 0 else 1.0


def _std(values: List[float]) -> float:
    """Population standard deviation."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return (sum((v - mean) ** 2 for v in values) / n) ** 0.5
