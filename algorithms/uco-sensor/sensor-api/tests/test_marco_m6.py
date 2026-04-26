"""
test_marco_m6.py — M6 Predictor API + Fleet Health Engine
==========================================================
30 tests covering:

  TA01-TA10  AutoAnalyzer            — per-module analysis + fleet analysis
  TA11-TA20  FleetReport             — dataclass, to_dict(), aggregation logic
  TA21-TA25  handle_predict()        — REST handler (unit, no HTTP)
  TA26-TA30  handle_predict_all()    — fleet REST handler + integration
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports under test ────────────────────────────────────────────────────────
from sensor_core.auto_analyzer import AutoAnalyzer, FleetReport   # noqa: E402
from sensor_core.predictor import DegradationForecast             # noqa: E402
from sensor_storage.snapshot_store import SnapshotStore           # noqa: E402
from core.data_structures import MetricVector                     # noqa: E402

# Server handlers (unit-testable without HTTP)
from api.server import handle_predict, handle_predict_all         # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_store_with_modules(
    module_specs: Dict[str, List[float]],
) -> SnapshotStore:
    """
    Create an in-memory store populated with the given module_id → [H values].
    """
    store   = SnapshotStore(":memory:")
    base_ts = 1_700_000_000.0

    for module_id, h_vals in module_specs.items():
        for i, h in enumerate(h_vals):
            mv = MetricVector(
                module_id=module_id,
                commit_hash=f"{module_id[:4]}{i:04d}",
                timestamp=base_ts + i * 3600,
                hamiltonian=h,
                cyclomatic_complexity=max(1, int(h)),
                infinite_loop_risk=0.0,
                dsm_density=0.0,
                dsm_cyclic_ratio=0.0,
                dependency_instability=0.0,
                syntactic_dead_code=0,
                duplicate_block_count=0,
                halstead_bugs=0.0,
            )
            store.insert(mv)

    return store


def _store_with_trend() -> SnapshotStore:
    """
    Two modules: 'rising.mod' (strong upward trend) and 'stable.mod' (flat).
    """
    return _make_store_with_modules({
        "rising.mod":  [float(i * 2) for i in range(1, 11)],    # 2,4,6,...,20
        "stable.mod":  [5.0] * 10,
    })


# ══════════════════════════════════════════════════════════════════════════════
# TA01-TA10 — AutoAnalyzer
# ══════════════════════════════════════════════════════════════════════════════

def test_TA01_auto_analyzer_instantiates():
    """TA01: AutoAnalyzer can be instantiated with a SnapshotStore."""
    store = SnapshotStore(":memory:")
    aa = AutoAnalyzer(store)
    assert aa is not None
    assert aa.default_window == 20


def test_TA02_analyze_module_empty_store_returns_insufficient():
    """TA02: analyze_module on empty store → insufficient_data=True."""
    store = SnapshotStore(":memory:")
    aa    = AutoAnalyzer(store)
    fc    = aa.analyze_module("nonexistent.mod")
    assert fc.insufficient_data is True
    assert fc.module_id == "nonexistent.mod"


def test_TA03_analyze_module_with_enough_data():
    """TA03: analyze_module with ≥ 4 snapshots → insufficient_data=False."""
    store = _make_store_with_modules({"src/a.py": [1.0, 2.0, 3.0, 4.0, 5.0]})
    aa    = AutoAnalyzer(store)
    fc    = aa.analyze_module("src/a.py")
    assert fc.insufficient_data is False
    assert isinstance(fc, DegradationForecast)


def test_TA04_analyze_module_horizon_passed_through():
    """TA04: horizon parameter is reflected in the returned forecast."""
    store = _make_store_with_modules({"m": [1.0, 2.0, 3.0, 4.0, 5.0]})
    aa    = AutoAnalyzer(store)
    fc    = aa.analyze_module("m", horizon=15)
    assert fc.horizon == 15


def test_TA05_analyze_module_rising_trend_not_stable():
    """TA05: steadily rising H → risk != STABLE (with sufficient data)."""
    store = _store_with_trend()
    aa    = AutoAnalyzer(store)
    fc    = aa.analyze_module("rising.mod")
    assert fc.risk_level != "STABLE"
    assert fc.slope_pct > 0


def test_TA06_analyze_fleet_returns_fleet_report():
    """TA06: analyze_fleet() returns a FleetReport instance."""
    store  = _store_with_trend()
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet()
    assert isinstance(report, FleetReport)


def test_TA07_analyze_fleet_covers_all_modules():
    """TA07: fleet report total_modules equals store.list_modules() count."""
    store  = _store_with_trend()
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet()
    assert report.total_modules == len(store.list_modules())
    assert report.total_modules == 2


def test_TA08_analyze_fleet_top_n_limits_most_at_risk():
    """TA08: top_n=1 → most_at_risk has at most 1 entry."""
    store  = _store_with_trend()
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet(top_n=1)
    assert len(report.most_at_risk) <= 1


def test_TA09_analyze_fleet_all_forecasts_sorted_by_risk():
    """TA09: all_forecasts is ordered best-risk first (CRITICAL before STABLE)."""
    specs  = {
        "crit.mod":   [float(i * 3) for i in range(1, 11)],  # strong upward
        "flat.mod":   [4.0] * 10,                              # stable
    }
    store  = _make_store_with_modules(specs)
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet()

    # The stable module should be last
    risks  = [f.risk_level for f in report.all_forecasts]
    # STABLE should come after any non-STABLE risk
    stable_indices = [i for i, r in enumerate(risks) if r == "STABLE"]
    non_stable_idx = [i for i, r in enumerate(risks) if r != "STABLE"]
    if stable_indices and non_stable_idx:
        assert min(stable_indices) > max(non_stable_idx)


def test_TA10_analyze_fleet_empty_store():
    """TA10: analyze_fleet on empty store → total_modules=0, no crash."""
    store  = SnapshotStore(":memory:")
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet()
    assert report.total_modules == 0
    assert report.critical_count == 0
    assert report.all_forecasts == []


# ══════════════════════════════════════════════════════════════════════════════
# TA11-TA20 — FleetReport dataclass + to_dict()
# ══════════════════════════════════════════════════════════════════════════════

def _make_fleet_report(n: int = 3) -> FleetReport:
    """Build a synthetic FleetReport for testing."""
    store = _make_store_with_modules({
        f"mod{i}": [float(j + i) for j in range(8)]
        for i in range(n)
    })
    aa = AutoAnalyzer(store)
    return aa.analyze_fleet()


def test_TA11_fleet_report_to_dict_has_required_keys():
    """TA11: FleetReport.to_dict() contains all required top-level keys."""
    report   = _make_fleet_report()
    d        = report.to_dict()
    expected = {
        "total_modules", "analysed_modules", "risk_counts",
        "critical_count", "high_count", "avg_confidence",
        "most_at_risk", "all_forecasts", "generated_at",
        "window", "horizon",
    }
    assert expected == set(d.keys())


def test_TA12_fleet_report_risk_counts_keys():
    """TA12: risk_counts contains exactly 5 keys (CRITICAL/HIGH/MEDIUM/LOW/STABLE)."""
    report = _make_fleet_report()
    d      = report.to_dict()
    assert set(d["risk_counts"].keys()) == {"CRITICAL", "HIGH", "MEDIUM", "LOW", "STABLE"}


def test_TA13_fleet_report_critical_count_consistent():
    """TA13: critical_count == risk_counts['CRITICAL']."""
    report = _make_fleet_report(5)
    d      = report.to_dict()
    assert d["critical_count"] == d["risk_counts"]["CRITICAL"]


def test_TA14_fleet_report_avg_confidence_bounded():
    """TA14: avg_confidence is in [0, 1]."""
    report = _make_fleet_report(4)
    assert 0.0 <= report.avg_confidence <= 1.0


def test_TA15_fleet_report_to_dict_json_serialisable():
    """TA15: FleetReport.to_dict() is fully JSON-serialisable."""
    report = _make_fleet_report(3)
    try:
        serialised = json.dumps(report.to_dict(), default=str)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"FleetReport.to_dict() is not JSON-serialisable: {exc}")
    assert len(serialised) > 100


def test_TA16_fleet_report_summary_returns_string():
    """TA16: FleetReport.summary() returns a non-empty string."""
    report = _make_fleet_report()
    s      = report.summary()
    assert isinstance(s, str) and len(s) > 10


def test_TA17_fleet_report_generated_at_is_recent():
    """TA17: generated_at timestamp is within 10 s of now."""
    before = time.time()
    report = _make_fleet_report()
    after  = time.time()
    assert before - 1 <= report.generated_at <= after + 1


def test_TA18_fleet_report_most_at_risk_subset_of_all():
    """TA18: every entry in most_at_risk also appears in all_forecasts."""
    store  = _store_with_trend()
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet(top_n=5)
    all_ids = {f.module_id for f in report.all_forecasts}
    for fc in report.most_at_risk:
        assert fc.module_id in all_ids


def test_TA19_fleet_report_analysed_modules_lte_total():
    """TA19: analysed_modules <= total_modules."""
    report = _make_fleet_report(3)
    assert report.analysed_modules <= report.total_modules


def test_TA20_fleet_report_window_and_horizon_stored():
    """TA20: window and horizon fields match the call parameters."""
    store  = _store_with_trend()
    aa     = AutoAnalyzer(store)
    report = aa.analyze_fleet(window=15, horizon=7)
    assert report.window   == 15
    assert report.horizon  == 7


# ══════════════════════════════════════════════════════════════════════════════
# TA21-TA25 — handle_predict() REST handler (unit)
# ══════════════════════════════════════════════════════════════════════════════

def test_TA21_handle_predict_no_module_returns_400():
    """TA21: handle_predict(None) → HTTP 400."""
    # Patch the global _store with our test store
    import api.server as srv
    original_store = srv._store
    srv._store = SnapshotStore(":memory:")
    try:
        code, data = handle_predict(None)
        assert code == 400
        assert "error" in data
    finally:
        srv._store = original_store


def test_TA22_handle_predict_unknown_module_insufficient():
    """TA22: handle_predict for module with no history → insufficient_data=True."""
    import api.server as srv
    original_store = srv._store
    srv._store = SnapshotStore(":memory:")
    try:
        code, data = handle_predict("ghost.mod")
        assert code == 200
        assert data["insufficient_data"] is True
    finally:
        srv._store = original_store


def test_TA23_handle_predict_known_module_returns_forecast():
    """TA23: handle_predict with enough snapshots → full forecast dict."""
    import api.server as srv
    original_store = srv._store
    srv._store = _make_store_with_modules({"src/x.py": [float(i) for i in range(1, 9)]})
    try:
        code, data = handle_predict("src/x.py", horizon=3)
        assert code == 200
        assert data["module_id"] == "src/x.py"
        assert data["horizon"]   == 3
        assert "risk_level"     in data
        assert "slope_pct"      in data
    finally:
        srv._store = original_store


def test_TA24_handle_predict_forecast_has_advice():
    """TA24: returned forecast dict contains a non-empty 'advice' string."""
    import api.server as srv
    original_store = srv._store
    srv._store = _make_store_with_modules({"a.py": [float(i) for i in range(10)]})
    try:
        code, data = handle_predict("a.py")
        assert code == 200
        assert isinstance(data.get("advice"), str) and len(data["advice"]) > 0
    finally:
        srv._store = original_store


def test_TA25_handle_predict_risk_in_valid_set():
    """TA25: risk_level in returned forecast is always one of 5 valid values."""
    import api.server as srv
    original_store = srv._store
    srv._store = _make_store_with_modules({"b.py": [1.0, 2.0, 4.0, 8.0, 16.0] * 2})
    try:
        code, data = handle_predict("b.py")
        assert code == 200
        assert data["risk_level"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "STABLE"}
    finally:
        srv._store = original_store


# ══════════════════════════════════════════════════════════════════════════════
# TA26-TA30 — handle_predict_all() + integration
# ══════════════════════════════════════════════════════════════════════════════

def test_TA26_handle_predict_all_empty_store():
    """TA26: handle_predict_all on empty store → 200 with total_modules=0."""
    import api.server as srv
    original_store = srv._store
    srv._store = SnapshotStore(":memory:")
    try:
        code, data = handle_predict_all()
        assert code == 200
        assert data["total_modules"] == 0
        assert data["all_forecasts"] == []
    finally:
        srv._store = original_store


def test_TA27_handle_predict_all_returns_fleet_dict():
    """TA27: handle_predict_all returns a well-formed fleet dict."""
    import api.server as srv
    original_store = srv._store
    srv._store = _store_with_trend()
    try:
        code, data = handle_predict_all()
        assert code == 200
        for key in ("total_modules", "risk_counts", "most_at_risk", "all_forecasts"):
            assert key in data
    finally:
        srv._store = original_store


def test_TA28_handle_predict_all_top_n_respected():
    """TA28: top_n parameter limits most_at_risk length."""
    import api.server as srv
    original_store = srv._store
    srv._store = _make_store_with_modules({
        f"m{i}": [float(j + i) for j in range(8)] for i in range(5)
    })
    try:
        code, data = handle_predict_all(top_n=2)
        assert code == 200
        assert len(data["most_at_risk"]) <= 2
    finally:
        srv._store = original_store


def test_TA29_handle_predict_all_json_serialisable():
    """TA29: full fleet response is JSON-serialisable."""
    import api.server as srv
    original_store = srv._store
    srv._store = _store_with_trend()
    try:
        code, data = handle_predict_all()
        try:
            serialised = json.dumps(data, default=str)
        except (TypeError, ValueError) as exc:
            pytest.fail(f"Fleet response is not JSON-serialisable: {exc}")
        assert len(serialised) > 50
    finally:
        srv._store = original_store


def test_TA30_end_to_end_analyze_then_predict():
    """TA30: Full pipeline — insert via store, predict via AutoAnalyzer, validate."""
    store   = SnapshotStore(":memory:")
    mod     = "e2e.module"
    base_ts = 1_700_000_000.0

    # Populate with a clear rising trend (10 snapshots)
    for i in range(10):
        mv = MetricVector(
            module_id=mod,
            commit_hash=f"e2e{i:04d}",
            timestamp=base_ts + i * 3600,
            hamiltonian=float(1 + i * 2),   # 1, 3, 5, ..., 19
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

    aa      = AutoAnalyzer(store)
    forecast = aa.analyze_module(mod, horizon=5)
    fleet    = aa.analyze_fleet()

    # Per-module assertions
    assert forecast.module_id       == mod
    assert forecast.insufficient_data is False
    assert forecast.slope_pct        > 0          # degrading
    assert forecast.n_samples        == 10
    assert 0.0 <= forecast.confidence <= 1.0

    # Fleet assertions
    assert fleet.total_modules >= 1
    assert any(f.module_id == mod for f in fleet.all_forecasts)

    store.close()


# ══════════════════════════════════════════════════════════════════════════════
# Inventory (for CI summary)
# ══════════════════════════════════════════════════════════════════════════════

_ALL_TESTS = [
    ("TA01", test_TA01_auto_analyzer_instantiates),
    ("TA02", test_TA02_analyze_module_empty_store_returns_insufficient),
    ("TA03", test_TA03_analyze_module_with_enough_data),
    ("TA04", test_TA04_analyze_module_horizon_passed_through),
    ("TA05", test_TA05_analyze_module_rising_trend_not_stable),
    ("TA06", test_TA06_analyze_fleet_returns_fleet_report),
    ("TA07", test_TA07_analyze_fleet_covers_all_modules),
    ("TA08", test_TA08_analyze_fleet_top_n_limits_most_at_risk),
    ("TA09", test_TA09_analyze_fleet_all_forecasts_sorted_by_risk),
    ("TA10", test_TA10_analyze_fleet_empty_store),
    ("TA11", test_TA11_fleet_report_to_dict_has_required_keys),
    ("TA12", test_TA12_fleet_report_risk_counts_keys),
    ("TA13", test_TA13_fleet_report_critical_count_consistent),
    ("TA14", test_TA14_fleet_report_avg_confidence_bounded),
    ("TA15", test_TA15_fleet_report_to_dict_json_serialisable),
    ("TA16", test_TA16_fleet_report_summary_returns_string),
    ("TA17", test_TA17_fleet_report_generated_at_is_recent),
    ("TA18", test_TA18_fleet_report_most_at_risk_subset_of_all),
    ("TA19", test_TA19_fleet_report_analysed_modules_lte_total),
    ("TA20", test_TA20_fleet_report_window_and_horizon_stored),
    ("TA21", test_TA21_handle_predict_no_module_returns_400),
    ("TA22", test_TA22_handle_predict_unknown_module_insufficient),
    ("TA23", test_TA23_handle_predict_known_module_returns_forecast),
    ("TA24", test_TA24_handle_predict_forecast_has_advice),
    ("TA25", test_TA25_handle_predict_risk_in_valid_set),
    ("TA26", test_TA26_handle_predict_all_empty_store),
    ("TA27", test_TA27_handle_predict_all_returns_fleet_dict),
    ("TA28", test_TA28_handle_predict_all_top_n_respected),
    ("TA29", test_TA29_handle_predict_all_json_serialisable),
    ("TA30", test_TA30_end_to_end_analyze_then_predict),
]

if __name__ == "__main__":
    passed = failed = 0
    for tid, fn in _ALL_TESTS:
        try:
            fn()
            print(f"  OK {tid} {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {tid} {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
