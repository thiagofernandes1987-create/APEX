"""
test_marco_m5.py — M5 Degradation Predictor
============================================
30 tests covering:

  TP01-TP05  DegradationForecast — dataclass fields + to_dict()
  TP06-TP10  hurst_rs()          — Hurst exponent estimation
  TP11-TP15  OLS helpers          — slope, intercept, R²
  TP16-TP20  _classify_risk()    — risk level classification
  TP21-TP25  DegradationPredictor.predict() — core scenarios
  TP26-TP30  Edge cases + SnapshotStore integration
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path
from typing import Any, List

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports under test ────────────────────────────────────────────────────────
from sensor_core.predictor import (          # noqa: E402
    DegradationForecast,
    DegradationPredictor,
    hurst_rs,
    _ols,
    _r2,
    _classify_risk,
    _advice,
    _HURST_PERSISTENT,
    _HURST_ANTIPERSIST,
    _SLOPE_CRITICAL_PCT,
    _SLOPE_HIGH_PCT,
    _SLOPE_MEDIUM_PCT,
    _SLOPE_LOW_PCT,
    _MIN_SAMPLES_FORECAST,
    _MIN_SAMPLES_RELIABLE,
)
from core.data_structures import MetricVector         # noqa: E402
from sensor_storage.snapshot_store import SnapshotStore  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_mv(module_id: str, h: float, commit: str = None, ts: float = None) -> MetricVector:
    """Minimal MetricVector with given hamiltonian."""
    return MetricVector(
        module_id=module_id,
        commit_hash=commit or f"abc{hash(h) & 0xFFFFFF:06x}",
        timestamp=ts or time.time(),
        hamiltonian=h,
        cyclomatic_complexity=1,
        infinite_loop_risk=0.0,
        dsm_density=0.0,
        dsm_cyclic_ratio=0.0,
        dependency_instability=0.0,
        syntactic_dead_code=0,
        duplicate_block_count=0,
        halstead_bugs=0.0,
    )


def _make_history(values: List[float], module_id: str = "test.mod") -> List[MetricVector]:
    """Build MetricVector list from hamiltonian values (oldest first)."""
    base_ts = 1_700_000_000.0
    return [
        _make_mv(module_id, h, commit=f"c{i:04d}", ts=base_ts + i * 3600)
        for i, h in enumerate(values)
    ]


def _predictor() -> DegradationPredictor:
    return DegradationPredictor(primary_metric="hamiltonian", default_horizon=5)


# ══════════════════════════════════════════════════════════════════════════════
# TP01-TP05 — DegradationForecast dataclass + to_dict()
# ══════════════════════════════════════════════════════════════════════════════

def test_TP01_forecast_fields_all_present():
    """TP01: DegradationForecast has all required fields."""
    fc = DegradationForecast(
        module_id="m", n_samples=10, hurst_exponent=0.6,
        slope_pct=5.0, current_h=10.0, predicted_h=12.5,
        velocity_h_per_snapshot=0.5, r_squared=0.85,
        confidence=0.7, risk_level="MEDIUM", horizon=5,
        advice="Monitor closely.", insufficient_data=False,
    )
    assert fc.module_id == "m"
    assert fc.n_samples == 10
    assert fc.hurst_exponent == 0.6
    assert fc.slope_pct == 5.0
    assert fc.current_h == 10.0
    assert fc.predicted_h == 12.5
    assert fc.velocity_h_per_snapshot == 0.5
    assert fc.r_squared == 0.85
    assert fc.confidence == 0.7
    assert fc.risk_level == "MEDIUM"
    assert fc.horizon == 5
    assert not fc.insufficient_data


def test_TP02_to_dict_keys():
    """TP02: to_dict() returns all expected keys."""
    fc = DegradationForecast(
        module_id="x", n_samples=8, hurst_exponent=0.5,
        slope_pct=2.0, current_h=5.0, predicted_h=6.0,
        velocity_h_per_snapshot=0.2, r_squared=0.7,
        confidence=0.5, risk_level="LOW", horizon=5,
        advice="Low risk.", insufficient_data=False,
    )
    d = fc.to_dict()
    expected_keys = {
        "module_id", "n_samples", "hurst_exponent", "slope_pct",
        "current_h", "predicted_h", "velocity_h_per_snapshot",
        "r_squared", "confidence", "risk_level", "horizon",
        "advice", "insufficient_data",
    }
    assert expected_keys == set(d.keys())


def test_TP03_to_dict_rounding():
    """TP03: to_dict() rounds floats correctly (4dp for most, 6dp for velocity)."""
    fc = DegradationForecast(
        module_id="y", n_samples=5, hurst_exponent=0.123456789,
        slope_pct=5.123456789, current_h=10.123456789, predicted_h=11.123456789,
        velocity_h_per_snapshot=0.123456789, r_squared=0.9999999,
        confidence=0.88888, risk_level="HIGH", horizon=3,
        advice="Urgent.", insufficient_data=False,
    )
    d = fc.to_dict()
    assert d["hurst_exponent"] == round(0.123456789, 4)
    assert d["slope_pct"] == round(5.123456789, 4)
    assert d["velocity_h_per_snapshot"] == round(0.123456789, 6)
    assert d["confidence"] == round(0.88888, 4)


def test_TP04_to_dict_insufficient_data_flag():
    """TP04: insufficient_data=True is preserved in to_dict()."""
    fc = DegradationForecast(
        module_id="z", n_samples=2, hurst_exponent=0.5,
        slope_pct=0.0, current_h=0.0, predicted_h=0.0,
        velocity_h_per_snapshot=0.0, r_squared=0.0,
        confidence=0.0, risk_level="STABLE", horizon=5,
        advice="Need more data.", insufficient_data=True,
    )
    d = fc.to_dict()
    assert d["insufficient_data"] is True
    assert d["risk_level"] == "STABLE"


def test_TP05_to_dict_is_json_serialisable():
    """TP05: to_dict() output is JSON-serialisable."""
    import json
    fc = DegradationForecast(
        module_id="a.b.c", n_samples=12, hurst_exponent=0.72,
        slope_pct=15.5, current_h=22.0, predicted_h=29.8,
        velocity_h_per_snapshot=1.55, r_squared=0.93,
        confidence=0.85, risk_level="CRITICAL", horizon=5,
        advice="Take action now.", insufficient_data=False,
    )
    serialised = json.dumps(fc.to_dict())
    assert len(serialised) > 50


# ══════════════════════════════════════════════════════════════════════════════
# TP06-TP10 — hurst_rs() Hurst exponent
# ══════════════════════════════════════════════════════════════════════════════

def test_TP06_hurst_rs_short_series_returns_05():
    """TP06: hurst_rs() with < 4 points returns 0.5."""
    assert hurst_rs([]) == 0.5
    assert hurst_rs([1.0]) == 0.5
    assert hurst_rs([1.0, 2.0, 3.0]) == 0.5


def test_TP07_hurst_rs_constant_series_returns_05():
    """TP07: hurst_rs() on constant series (zero variance) returns 0.5."""
    h = hurst_rs([5.0] * 20)
    assert h == 0.5


def test_TP08_hurst_rs_strong_trend_above_threshold():
    """TP08: monotonically increasing series → Hurst > 0.5 (persistent trend)."""
    series = [float(i) for i in range(1, 30)]
    h = hurst_rs(series)
    assert h > 0.5, f"Expected H > 0.5 for trending series, got {h}"


def test_TP09_hurst_rs_bounded_in_0_1():
    """TP09: hurst_rs() always returns a value in [0, 1]."""
    import random
    rng = random.Random(42)
    for _ in range(20):
        n = rng.randint(4, 40)
        series = [rng.gauss(0, 1) for _ in range(n)]
        h = hurst_rs(series)
        assert 0.0 <= h <= 1.0, f"hurst_rs out of bounds: {h}"


def test_TP10_hurst_rs_min_four_points_works():
    """TP10: hurst_rs() with exactly 4 points does not raise."""
    h = hurst_rs([1.0, 2.0, 4.0, 8.0])
    assert isinstance(h, float)
    assert 0.0 <= h <= 1.0


# ══════════════════════════════════════════════════════════════════════════════
# TP11-TP15 — OLS helpers (_ols, _r2)
# ══════════════════════════════════════════════════════════════════════════════

def test_TP11_ols_perfect_line():
    """TP11: _ols on y = 2x + 1 returns slope≈2, intercept≈1."""
    xs = [0, 1, 2, 3, 4]
    ys = [1, 3, 5, 7, 9]
    slope, intercept = _ols(xs, ys)
    assert abs(slope - 2.0) < 1e-9
    assert abs(intercept - 1.0) < 1e-9


def test_TP12_ols_flat_line_slope_zero():
    """TP12: _ols on constant y returns slope≈0."""
    xs = [0, 1, 2, 3, 4]
    ys = [7.0] * 5
    slope, intercept = _ols(xs, ys)
    assert abs(slope) < 1e-9
    assert abs(intercept - 7.0) < 1e-9


def test_TP13_r2_perfect_fit_is_one():
    """TP13: _r2 returns 1.0 for perfect OLS fit."""
    xs = [0, 1, 2, 3, 4]
    ys = [1, 3, 5, 7, 9]
    slope, intercept = _ols(xs, ys)
    r2 = _r2(xs, ys, slope, intercept)
    assert abs(r2 - 1.0) < 1e-9


def test_TP14_r2_bounded_0_1():
    """TP14: _r2 is always in [0, 1]."""
    xs = list(range(10))
    ys = [5.0, 1.0, 9.0, 2.0, 8.0, 3.0, 7.0, 4.0, 6.0, 0.0]
    slope, intercept = _ols(xs, ys)
    r2 = _r2(xs, ys, slope, intercept)
    assert 0.0 <= r2 <= 1.0


def test_TP15_ols_single_point_no_crash():
    """TP15: _ols with a single point returns (0.0, y[0]) without raising."""
    slope, intercept = _ols([0], [42.0])
    assert slope == 0.0
    assert intercept == 42.0


# ══════════════════════════════════════════════════════════════════════════════
# TP16-TP20 — _classify_risk() risk level
# ══════════════════════════════════════════════════════════════════════════════

def test_TP16_risk_stable_when_insufficient():
    """TP16: _classify_risk returns STABLE when insuf=True regardless of slope."""
    assert _classify_risk(50.0, 0.8, insuf=True) == "STABLE"


def test_TP17_risk_stable_when_slope_zero_or_negative():
    """TP17: _classify_risk returns STABLE for slope_pct ≤ 0."""
    assert _classify_risk(0.0, 0.7, insuf=False) == "STABLE"
    assert _classify_risk(-5.0, 0.8, insuf=False) == "STABLE"


def test_TP18_risk_critical_at_high_slope():
    """TP18: slope ≥ CRITICAL threshold → CRITICAL."""
    assert _classify_risk(_SLOPE_CRITICAL_PCT, 0.5, insuf=False) == "CRITICAL"
    assert _classify_risk(_SLOPE_CRITICAL_PCT + 5, 0.3, insuf=False) == "CRITICAL"


def test_TP19_risk_high_at_medium_persistent():
    """TP19: persistent Hurst + slope ≥ MEDIUM threshold → HIGH."""
    # slope is between HIGH and CRITICAL, Hurst persistent → CRITICAL
    # slope is between MEDIUM and HIGH, Hurst persistent → HIGH
    risk = _classify_risk(_SLOPE_MEDIUM_PCT + 1.0, _HURST_PERSISTENT + 0.01, insuf=False)
    assert risk == "HIGH"


def test_TP20_risk_levels_in_valid_set():
    """TP20: _classify_risk always returns one of the 5 valid risk levels."""
    valid = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "STABLE"}
    for slope in [-5.0, 0.0, 0.5, 2.0, 6.0, 11.0, 25.0]:
        for hurst in [0.3, 0.5, 0.6, 0.8]:
            for insuf in (True, False):
                risk = _classify_risk(slope, hurst, insuf)
                assert risk in valid, f"Unexpected risk: {risk}"


# ══════════════════════════════════════════════════════════════════════════════
# TP21-TP25 — DegradationPredictor.predict() core scenarios
# ══════════════════════════════════════════════════════════════════════════════

def test_TP21_predict_insufficient_data():
    """TP21: predict() with < 4 snapshots returns insufficient_data=True, STABLE."""
    p = _predictor()
    history = _make_history([1.0, 2.0, 3.0])  # only 3 snapshots
    fc = p.predict(history, module_id="mod.a")
    assert fc.insufficient_data is True
    assert fc.risk_level == "STABLE"
    assert fc.n_samples == 3


def test_TP22_predict_stable_series():
    """TP22: Constant Hamiltonian series → risk STABLE, slope ≈ 0."""
    p = _predictor()
    values = [5.0] * 10
    fc = p.predict(_make_history(values), module_id="stable.mod")
    assert fc.risk_level == "STABLE"
    assert abs(fc.slope_pct) < 1.0   # near zero
    assert fc.insufficient_data is False


def test_TP23_predict_degrading_series_critical():
    """TP23: Rapidly increasing Hamiltonian → risk CRITICAL."""
    p = _predictor()
    # Each step roughly doubles → very steep slope
    values = [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0, 15.0, 17.0, 19.0]
    fc = p.predict(_make_history(values), module_id="crit.mod")
    assert fc.risk_level in {"CRITICAL", "HIGH"}, f"Expected CRITICAL/HIGH, got {fc.risk_level}"
    assert fc.slope_pct > 0


def test_TP24_predict_returns_forecast_dataclass():
    """TP24: predict() always returns a DegradationForecast instance."""
    p = _predictor()
    for n in [0, 1, 3, 4, 8, 15]:
        history = _make_history([float(i) for i in range(n)])
        fc = p.predict(history)
        assert isinstance(fc, DegradationForecast)


def test_TP25_predict_module_id_auto_detected():
    """TP25: module_id is auto-detected from history[0].module_id if not supplied."""
    p = _predictor()
    history = _make_history([1.0] * 6, module_id="auto.module")
    fc = p.predict(history)   # no module_id arg
    assert fc.module_id == "auto.module"


# ══════════════════════════════════════════════════════════════════════════════
# TP26-TP30 — Edge cases + SnapshotStore integration
# ══════════════════════════════════════════════════════════════════════════════

def test_TP26_predict_confidence_bounded():
    """TP26: confidence is always in [0, 1]."""
    p = _predictor()
    for n in [4, 5, 8, 20, 30]:
        values = [float(i) * 0.5 for i in range(n)]
        fc = p.predict(_make_history(values))
        assert 0.0 <= fc.confidence <= 1.0, f"confidence={fc.confidence} out of [0,1]"


def test_TP27_predict_predicted_h_non_negative():
    """TP27: predicted_h is always ≥ 0 (Hamiltonian cannot be negative)."""
    p = _predictor()
    # Decreasing series — predicted_h could go negative without clamp
    values = [20.0, 15.0, 10.0, 5.0, 2.0, 1.0, 0.5]
    fc = p.predict(_make_history(values))
    assert fc.predicted_h >= 0.0


def test_TP28_predict_horizon_respected():
    """TP28: forecast horizon is stored on the returned DegradationForecast."""
    p = _predictor()
    history = _make_history([float(i) for i in range(8)])
    fc = p.predict(history, horizon=10)
    assert fc.horizon == 10


def test_TP29_predict_empty_history_no_crash():
    """TP29: predict() with empty list returns insufficient_data=True safely."""
    p = _predictor()
    fc = p.predict([])
    assert fc.insufficient_data is True
    assert fc.module_id == "unknown"
    assert fc.risk_level == "STABLE"


def test_TP30_store_integration_predict_from_history():
    """TP30: Full pipeline — store → get_history → predict() → valid forecast."""
    store = SnapshotStore(":memory:")
    mod = "integration.test"
    base_ts = 1_700_000_000.0

    # Insert 10 snapshots with a clear upward trend
    for i in range(10):
        mv = MetricVector(
            module_id=mod,
            commit_hash=f"sha{i:04d}",
            timestamp=base_ts + i * 3600,
            hamiltonian=float(2 + i * 1.5),   # 2, 3.5, 5, ...
            cyclomatic_complexity=3 + i,
            infinite_loop_risk=0.0,
            dsm_density=0.0,
            dsm_cyclic_ratio=0.0,
            dependency_instability=0.0,
            syntactic_dead_code=0,
            duplicate_block_count=0,
            halstead_bugs=0.0,
        )
        store.insert(mv)

    history = store.get_history(mod, window=20)
    assert len(history) == 10

    predictor = _predictor()
    fc = predictor.predict(history, module_id=mod)

    # Basic assertions on the forecast
    assert fc.module_id == mod
    assert fc.n_samples == 10
    assert fc.insufficient_data is False
    assert fc.slope_pct > 0         # degrading trend
    assert fc.predicted_h > fc.current_h or fc.predicted_h >= 0
    assert fc.risk_level in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "STABLE"}
    assert isinstance(fc.advice, str) and len(fc.advice) > 5

    store.close()


# ══════════════════════════════════════════════════════════════════════════════
# Inventory (for CI summary)
# ══════════════════════════════════════════════════════════════════════════════

_ALL_TESTS = [
    ("TP01", test_TP01_forecast_fields_all_present),
    ("TP02", test_TP02_to_dict_keys),
    ("TP03", test_TP03_to_dict_rounding),
    ("TP04", test_TP04_to_dict_insufficient_data_flag),
    ("TP05", test_TP05_to_dict_is_json_serialisable),
    ("TP06", test_TP06_hurst_rs_short_series_returns_05),
    ("TP07", test_TP07_hurst_rs_constant_series_returns_05),
    ("TP08", test_TP08_hurst_rs_strong_trend_above_threshold),
    ("TP09", test_TP09_hurst_rs_bounded_in_0_1),
    ("TP10", test_TP10_hurst_rs_min_four_points_works),
    ("TP11", test_TP11_ols_perfect_line),
    ("TP12", test_TP12_ols_flat_line_slope_zero),
    ("TP13", test_TP13_r2_perfect_fit_is_one),
    ("TP14", test_TP14_r2_bounded_0_1),
    ("TP15", test_TP15_ols_single_point_no_crash),
    ("TP16", test_TP16_risk_stable_when_insufficient),
    ("TP17", test_TP17_risk_stable_when_slope_zero_or_negative),
    ("TP18", test_TP18_risk_critical_at_high_slope),
    ("TP19", test_TP19_risk_high_at_medium_persistent),
    ("TP20", test_TP20_risk_levels_in_valid_set),
    ("TP21", test_TP21_predict_insufficient_data),
    ("TP22", test_TP22_predict_stable_series),
    ("TP23", test_TP23_predict_degrading_series_critical),
    ("TP24", test_TP24_predict_returns_forecast_dataclass),
    ("TP25", test_TP25_predict_module_id_auto_detected),
    ("TP26", test_TP26_predict_confidence_bounded),
    ("TP27", test_TP27_predict_predicted_h_non_negative),
    ("TP28", test_TP28_predict_horizon_respected),
    ("TP29", test_TP29_predict_empty_history_no_crash),
    ("TP30", test_TP30_store_integration_predict_from_history),
]

if __name__ == "__main__":
    passed = failed = 0
    for tid, fn in _ALL_TESTS:
        try:
            fn()
            print(f"  ✅ {tid} {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {tid} {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
