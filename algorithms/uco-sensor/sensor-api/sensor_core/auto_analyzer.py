"""
UCO-Sensor — AutoAnalyzer + FleetReport  (M6)
==============================================
Runs the DegradationPredictor across all modules stored in a SnapshotStore
and aggregates results into a FleetReport.

Classes
-------
FleetReport
    Aggregated prediction across all known modules.
AutoAnalyzer
    Orchestrates per-module and fleet-wide analysis.

Usage
-----
    from sensor_core.auto_analyzer import AutoAnalyzer
    from sensor_storage.snapshot_store import SnapshotStore

    store    = SnapshotStore("uco_sensor.db")
    analyzer = AutoAnalyzer(store)

    # Single module
    forecast = analyzer.analyze_module("src/auth.py", horizon=5)

    # Fleet
    report   = analyzer.analyze_fleet(window=20, top_n=10)
    print(report.to_dict())
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sensor_core.predictor import DegradationForecast, DegradationPredictor

# Risk ordering for sorting
_RISK_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "STABLE": 4}


# ── FleetReport ───────────────────────────────────────────────────────────────

@dataclass
class FleetReport:
    """
    Aggregated degradation forecast across all modules in a store.

    Attributes
    ----------
    total_modules : int
        Number of modules analysed (including insufficient-data ones).
    analysed_modules : int
        Modules with enough data to produce a forecast.
    risk_counts : dict
        Counts per risk level: CRITICAL, HIGH, MEDIUM, LOW, STABLE.
    critical_count : int
    high_count : int
    avg_confidence : float
        Mean confidence across modules with sufficient data (0–1).
    most_at_risk : list[DegradationForecast]
        Top-N modules ordered by risk level then slope_pct descending.
    all_forecasts : list[DegradationForecast]
        Full list ordered by risk.
    generated_at : float
        Unix timestamp of report generation.
    window : int
        History window used.
    horizon : int
        Forecast horizon used.
    """
    total_modules:    int
    analysed_modules: int
    risk_counts:      Dict[str, int]
    critical_count:   int
    high_count:       int
    avg_confidence:   float
    most_at_risk:     List[DegradationForecast]
    all_forecasts:    List[DegradationForecast]
    generated_at:     float
    window:           int
    horizon:          int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_modules":    self.total_modules,
            "analysed_modules": self.analysed_modules,
            "risk_counts":      self.risk_counts,
            "critical_count":   self.critical_count,
            "high_count":       self.high_count,
            "avg_confidence":   round(self.avg_confidence, 4),
            "most_at_risk":     [f.to_dict() for f in self.most_at_risk],
            "all_forecasts":    [f.to_dict() for f in self.all_forecasts],
            "generated_at":     self.generated_at,
            "window":           self.window,
            "horizon":          self.horizon,
        }

    def summary(self) -> str:
        """Human-readable one-liner."""
        return (
            f"Fleet: {self.total_modules} modules | "
            f"CRITICAL={self.critical_count} HIGH={self.high_count} | "
            f"avg_confidence={self.avg_confidence:.2f}"
        )


# ── AutoAnalyzer ──────────────────────────────────────────────────────────────

class AutoAnalyzer:
    """
    Orchestrates DegradationPredictor over all modules in a SnapshotStore.

    Parameters
    ----------
    store : SnapshotStore
        Populated snapshot store.
    primary_metric : str
        MetricVector attribute to forecast (default ``"hamiltonian"``).
    default_horizon : int
        Default forecast horizon in snapshots.
    default_window : int
        Default history window (max snapshots to fetch per module).
    """

    def __init__(
        self,
        store: Any,                   # SnapshotStore (avoid circular import)
        primary_metric:  str = "hamiltonian",
        default_horizon: int = 5,
        default_window:  int = 20,
    ) -> None:
        self.store           = store
        self.default_window  = default_window
        self._predictor      = DegradationPredictor(
            primary_metric=primary_metric,
            default_horizon=default_horizon,
        )

    # ── Per-module ────────────────────────────────────────────────────────────

    def analyze_module(
        self,
        module_id: str,
        window:    Optional[int] = None,
        horizon:   Optional[int] = None,
    ) -> DegradationForecast:
        """
        Forecast degradation for a single module.

        Parameters
        ----------
        module_id : str
        window    : history window (snapshots). Defaults to self.default_window.
        horizon   : forecast horizon. Defaults to predictor default.

        Returns
        -------
        DegradationForecast
        """
        w       = window  if window  is not None else self.default_window
        history = self.store.get_history(module_id, window=w)
        return self._predictor.predict(history, module_id=module_id, horizon=horizon)

    # ── Fleet ─────────────────────────────────────────────────────────────────

    def analyze_fleet(
        self,
        window: Optional[int] = None,
        top_n:  int           = 10,
        horizon: Optional[int] = None,
    ) -> FleetReport:
        """
        Run predictor on every module in the store and aggregate results.

        Parameters
        ----------
        window  : history window per module.
        top_n   : number of modules to include in ``most_at_risk``.
        horizon : forecast horizon.

        Returns
        -------
        FleetReport
        """
        w          = window if window is not None else self.default_window
        module_ids = self.store.list_modules()

        forecasts: List[DegradationForecast] = []
        for mid in module_ids:
            fc = self.analyze_module(mid, window=w, horizon=horizon)
            forecasts.append(fc)

        # Sort: risk order, then slope_pct descending
        forecasts.sort(
            key=lambda f: (_RISK_ORDER.get(f.risk_level, 9), -f.slope_pct)
        )

        # Aggregate
        risk_counts: Dict[str, int] = {
            "CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "STABLE": 0,
        }
        analysed   = 0
        conf_total = 0.0

        for fc in forecasts:
            risk_counts[fc.risk_level] = risk_counts.get(fc.risk_level, 0) + 1
            if not fc.insufficient_data:
                analysed   += 1
                conf_total += fc.confidence

        avg_conf = (conf_total / analysed) if analysed > 0 else 0.0

        return FleetReport(
            total_modules=len(forecasts),
            analysed_modules=analysed,
            risk_counts=risk_counts,
            critical_count=risk_counts.get("CRITICAL", 0),
            high_count=risk_counts.get("HIGH", 0),
            avg_confidence=round(avg_conf, 4),
            most_at_risk=forecasts[:top_n],
            all_forecasts=forecasts,
            generated_at=time.time(),
            window=w,
            horizon=horizon if horizon is not None else self._predictor.default_horizon,
        )
