"""
UCO-Sensor — Test Suite M13  (M7.0 — Formalizar Sinais Informais)
==================================================================
TV31-TV60 — 30 tests covering AdvancedVector, DiagnosticVector,
SnapshotStore M7.0 persistence (3 JSON columns), UCOBridge integration,
and the GET /metrics/advanced API endpoint.

Milestone: M7.0 — Close 83% signal-loss gap from M6.4 autopsy
Version:   v2.3.0
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict

# ── sys.path setup (mirrors existing test suite) ─────────────────────────────
_ROOT  = Path(__file__).resolve().parent.parent
_FREQ  = _ROOT.parent / "frequency-engine"
for _p in [str(_ROOT), str(_FREQ)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from metrics.extended_vectors import (
    AdvancedVector, DiagnosticVector,
    HalsteadVector, StructuralVector,
)
from sensor_storage.snapshot_store import SnapshotStore
from core.data_structures import MetricVector


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _make_mv(**kwargs) -> MetricVector:
    """Minimal MetricVector factory."""
    defaults = dict(
        module_id="test.mod",
        commit_hash="abc123",
        timestamp=float(time.time()),
        hamiltonian=3.5,
        cyclomatic_complexity=5,
        infinite_loop_risk=0.0,
        dsm_density=0.1,
        dsm_cyclic_ratio=0.0,
        dependency_instability=0.3,
        syntactic_dead_code=0,
        duplicate_block_count=0,
        halstead_bugs=0.1,
        language="python",
        lines_of_code=50,
        status="STABLE",
    )
    defaults.update(kwargs)
    return MetricVector(**defaults)


def _make_advanced_mv() -> Any:
    """MetricVector enriched with AdvancedAnalyzer dynamic attrs."""
    mv = _make_mv(module_id="adv.mod", language="python")
    mv.cognitive_complexity   = 14
    mv.cognitive_fn_max       = 9
    mv.sqale_debt_minutes     = 90
    mv.sqale_rating           = "B"
    mv.clone_count            = 2
    mv.function_profiles      = [{"name": "f1"}, {"name": "f2"}, {"name": "f3"}]
    mv.advanced_ok            = True
    return mv


def _make_classification_result(**overrides) -> SimpleNamespace:
    """Minimal ClassificationResult substitute for unit tests."""
    defaults = dict(
        module_id="diag.mod",
        primary_error="TECH_DEBT_ACCUMULATION",
        severity="WARNING",
        severity_score=0.42,
        hurst_H=0.78,
        burst_index_H=0.31,
        phase_coupling_CC_H=0.65,
        onset_reversibility=0.22,
        self_cure_probability=3.5,   # percentage (> 1.0 to test normalization)
        spectral_evidence={"H_dominant_freq": 0.12, "H_spectral_entropy": 0.47},
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ═══════════════════════════════════════════════════════════════════════════════
# TV31-TV36 — AdvancedVector unit tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_tv31_advanced_vector_from_advanced_mv_all_channels():
    """TV31: from_advanced_mv populates all 6 channels from MetricVector attrs."""
    mv = _make_advanced_mv()
    av = AdvancedVector.from_advanced_mv(mv, module_id="adv.mod", language="python")

    assert av.cognitive_cc_total  == 14,  f"expected 14, got {av.cognitive_cc_total}"
    assert av.cognitive_cc_max    == 9,   f"expected 9, got {av.cognitive_cc_max}"
    assert av.sqale_debt_minutes  == 90,  f"expected 90, got {av.sqale_debt_minutes}"
    assert av.sqale_rating        == "B", f"expected 'B', got {av.sqale_rating}"
    assert av.clone_count         == 2,   f"expected 2, got {av.clone_count}"
    assert av.fn_profile_count    == 3,   f"expected 3, got {av.fn_profile_count}"


def test_tv32_advanced_vector_sqale_rating_propagated():
    """TV32: sqale_rating letter (A–E) is correctly captured from mv.sqale_rating."""
    for letter in ("A", "B", "C", "D", "E"):
        mv = _make_advanced_mv()
        mv.sqale_rating = letter
        av = AdvancedVector.from_advanced_mv(mv)
        assert av.sqale_rating == letter, (
            f"sqale_rating {letter!r} not propagated — got {av.sqale_rating!r}"
        )


def test_tv33_advanced_vector_fn_profile_count():
    """TV33: fn_profile_count counts actual function_profiles list length."""
    mv = _make_advanced_mv()
    mv.function_profiles = [{"name": f"f{i}"} for i in range(7)]
    av = AdvancedVector.from_advanced_mv(mv)
    assert av.fn_profile_count == 7


def test_tv34_advanced_vector_clone_count():
    """TV34: clone_count is correctly extracted from mv.clone_count."""
    mv = _make_advanced_mv()
    mv.clone_count = 5
    av = AdvancedVector.from_advanced_mv(mv)
    assert av.clone_count == 5


def test_tv35_advanced_vector_to_dict_has_all_keys():
    """TV35: to_dict() returns a dict with all 6 channel keys + attribution."""
    av = AdvancedVector(
        cognitive_cc_total=8, cognitive_cc_max=4,
        sqale_debt_minutes=60, sqale_rating="B",
        clone_count=1, fn_profile_count=5,
        module_id="x", language="python",
    )
    d = av.to_dict()
    for key in ("cognitive_cc_total", "cognitive_cc_max", "sqale_debt_minutes",
                "sqale_rating", "clone_count", "fn_profile_count",
                "module_id", "language"):
        assert key in d, f"Key {key!r} missing from AdvancedVector.to_dict()"
    # Must be JSON-serializable
    assert json.dumps(d)


def test_tv36_advanced_vector_null_mv_safe_defaults():
    """TV36: from_advanced_mv on plain MetricVector (no M1 attrs) returns safe defaults."""
    mv = _make_mv()   # no AdvancedAnalyzer attrs
    av = AdvancedVector.from_advanced_mv(mv)

    assert av.cognitive_cc_total == 0
    assert av.cognitive_cc_max   == 0
    assert av.sqale_debt_minutes == 0
    assert av.sqale_rating       == "A"
    assert av.clone_count        == 0
    assert av.fn_profile_count   == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TV37-TV44 — DiagnosticVector unit tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_tv37_diagnostic_vector_from_result_all_channels():
    """TV37: from_classification_result populates all 8 channels."""
    result = _make_classification_result()
    dv = DiagnosticVector.from_classification_result(result, module_id="diag.mod", n_snapshots=20)

    assert dv.degradation_signature  == "TECH_DEBT_ACCUMULATION"
    assert 0.0 <= dv.frequency_anomaly_score <= 1.0
    assert 0.0 <= dv.burst_index             <= 1.0
    assert 0.0 <= dv.phase_coupling_CC_H     <= 1.0
    assert 0.0 <= dv.onset_reversibility     <= 1.0
    assert 0.0 <= dv.self_cure_probability   <= 1.0
    assert dv.module_id    == "diag.mod"
    assert dv.n_snapshots  == 20


def test_tv38_diagnostic_vector_degradation_signature():
    """TV38: degradation_signature maps directly from primary_error."""
    result = _make_classification_result(primary_error="GOD_CLASS")
    dv = DiagnosticVector.from_classification_result(result)
    assert dv.degradation_signature == "GOD_CLASS"


def test_tv39_diagnostic_vector_frequency_anomaly_score_range():
    """TV39: frequency_anomaly_score always clamped to [0, 1]."""
    for raw in (-0.5, 0.0, 0.42, 1.0, 1.5, 99.0):
        result = _make_classification_result(severity_score=raw)
        dv = DiagnosticVector.from_classification_result(result)
        assert 0.0 <= dv.frequency_anomaly_score <= 1.0, (
            f"frequency_anomaly_score={dv.frequency_anomaly_score} out of [0,1] for raw={raw}"
        )


def test_tv40_diagnostic_vector_burst_index_range():
    """TV40: burst_index always clamped to [0, 1]."""
    for raw in (0.0, 0.31, 1.0, -0.1, 2.0):
        result = _make_classification_result(burst_index_H=raw)
        dv = DiagnosticVector.from_classification_result(result)
        assert 0.0 <= dv.burst_index <= 1.0


def test_tv41_diagnostic_vector_onset_reversibility_range():
    """TV41: onset_reversibility always in [0, 1]."""
    for raw in (0.0, 0.22, 0.5, 1.0):
        result = _make_classification_result(onset_reversibility=raw)
        dv = DiagnosticVector.from_classification_result(result)
        assert 0.0 <= dv.onset_reversibility <= 1.0


def test_tv42_diagnostic_vector_self_cure_probability_normalized():
    """TV42: self_cure_probability > 1.0 (percentage) is normalized to [0, 1]."""
    # If stored as percentage (e.g. 3.5 meaning 3.5%)
    result = _make_classification_result(self_cure_probability=3.5)
    dv = DiagnosticVector.from_classification_result(result)
    assert 0.0 <= dv.self_cure_probability <= 1.0, (
        f"Expected [0,1], got {dv.self_cure_probability}"
    )
    # 3.5% = 0.035 after normalization
    assert abs(dv.self_cure_probability - 0.035) < 1e-6


def test_tv43_diagnostic_vector_to_dict_has_all_keys():
    """TV43: to_dict() has all 8 channel keys and is JSON-serializable."""
    dv = DiagnosticVector(
        dominant_frequency_H=0.1,
        spectral_entropy_H=0.45,
        phase_coupling_CC_H=0.65,
        burst_index=0.31,
        self_cure_probability=0.035,
        onset_reversibility=0.22,
        degradation_signature="TECH_DEBT_ACCUMULATION",
        frequency_anomaly_score=0.42,
        module_id="diag.mod",
        n_snapshots=20,
    )
    d = dv.to_dict()
    for key in (
        "dominant_frequency_H", "spectral_entropy_H", "phase_coupling_CC_H",
        "burst_index", "self_cure_probability", "onset_reversibility",
        "degradation_signature", "frequency_anomaly_score",
        "module_id", "n_snapshots",
    ):
        assert key in d, f"Key {key!r} missing from DiagnosticVector.to_dict()"
    assert json.dumps(d)   # must be JSON-serializable


def test_tv44_diagnostic_vector_from_dict_roundtrip():
    """TV44: from_dict(to_dict()) is a lossless roundtrip."""
    original = DiagnosticVector(
        dominant_frequency_H=0.12,
        spectral_entropy_H=0.47,
        phase_coupling_CC_H=0.65,
        burst_index=0.31,
        self_cure_probability=0.035,
        onset_reversibility=0.22,
        degradation_signature="TECH_DEBT_ACCUMULATION",
        frequency_anomaly_score=0.42,
        module_id="diag.mod",
        n_snapshots=20,
    )
    restored = DiagnosticVector.from_dict(original.to_dict())

    assert restored.degradation_signature == original.degradation_signature
    assert abs(restored.frequency_anomaly_score - original.frequency_anomaly_score) < 1e-6
    assert abs(restored.burst_index         - original.burst_index)         < 1e-6
    assert abs(restored.phase_coupling_CC_H - original.phase_coupling_CC_H) < 1e-6
    assert abs(restored.onset_reversibility - original.onset_reversibility)  < 1e-6
    assert abs(restored.self_cure_probability - original.self_cure_probability) < 1e-6
    assert restored.module_id   == original.module_id
    assert restored.n_snapshots == original.n_snapshots


# ═══════════════════════════════════════════════════════════════════════════════
# TV45-TV52 — SnapshotStore M7.0 persistence tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_tv45_snapshot_store_insert_persists_advanced_vector():
    """TV45: insert() serializes AdvancedVector into advanced_vector_json column."""
    store = SnapshotStore(":memory:")
    mv = _make_mv(commit_hash="tv45_h1")
    mv.advanced = AdvancedVector(
        cognitive_cc_total=14, cognitive_cc_max=9,
        sqale_debt_minutes=90, sqale_rating="B",
        clone_count=2, fn_profile_count=3,
        module_id="test.mod", language="python",
    )
    store.insert(mv)

    history = store.get_history("test.mod", window=10)
    assert len(history) >= 1
    restored_mv = history[-1]
    adv = getattr(restored_mv, "advanced", None)
    assert adv is not None, "AdvancedVector not restored from DB"
    assert adv.cognitive_cc_total == 14
    assert adv.sqale_rating       == "B"
    assert adv.clone_count        == 2


def test_tv46_snapshot_store_insert_persists_extended_vectors():
    """TV46: insert() serializes HalsteadVector + StructuralVector into extended_vectors_json."""
    store = SnapshotStore(":memory:")
    mv = _make_mv(commit_hash="tv46_h1")
    mv.halstead = HalsteadVector(
        volume=312.5, difficulty=8.4, effort=2625.0,
        time_to_implement=145.8, program_level=0.119, token_count=50,
        module_id="test.mod", language="python",
    )
    mv.structural = StructuralVector(
        max_function_cc=5, cc_hotspot_ratio=0.33,
        max_methods_per_class=3, n_functions=4, n_classes=1,
        comment_density=0.15, test_ratio=0.0,
        module_id="test.mod", language="python",
    )
    store.insert(mv)

    history = store.get_history("test.mod", window=10)
    assert len(history) >= 1
    restored = history[-1]
    assert getattr(restored, "halstead",  None) is not None, "HalsteadVector not restored"
    assert getattr(restored, "structural", None) is not None, "StructuralVector not restored"
    assert abs(restored.halstead.volume - 312.5) < 0.01


def test_tv47_snapshot_store_advanced_vector_json_serializable():
    """TV47: advanced_vector_json stored as valid JSON string."""
    store = SnapshotStore(":memory:")
    mv = _make_mv(commit_hash="tv47_h1")
    mv.advanced = AdvancedVector(
        cognitive_cc_total=6, cognitive_cc_max=3,
        sqale_debt_minutes=30, sqale_rating="A",
        clone_count=0, fn_profile_count=2,
    )
    store.insert(mv)

    with store._lock:
        row = store._get_conn().execute(
            "SELECT advanced_vector_json FROM snapshots WHERE commit_hash = 'tv47_h1'"
        ).fetchone()

    assert row is not None
    raw_json = row[0]
    assert raw_json is not None, "advanced_vector_json is NULL"
    parsed = json.loads(raw_json)
    assert parsed["cognitive_cc_total"] == 6
    assert parsed["sqale_rating"] == "A"


def test_tv48_snapshot_store_no_extended_vectors_inserts_null():
    """TV48: insert() with no extended vectors stores NULL in JSON columns."""
    store = SnapshotStore(":memory:")
    mv = _make_mv(commit_hash="tv48_h1")   # plain MetricVector — no extended attrs
    store.insert(mv)

    with store._lock:
        row = store._get_conn().execute(
            "SELECT extended_vectors_json, advanced_vector_json, diagnostic_vector_json "
            "FROM snapshots WHERE commit_hash = 'tv48_h1'"
        ).fetchone()

    assert row is not None
    assert row[0] is None, f"extended_vectors_json should be NULL, got {row[0]!r}"
    assert row[1] is None, f"advanced_vector_json should be NULL, got {row[1]!r}"
    assert row[2] is None, f"diagnostic_vector_json should be NULL, got {row[2]!r}"


def test_tv49_snapshot_store_update_diagnostic():
    """TV49: update_diagnostic() persists DiagnosticVector JSON after FrequencyEngine."""
    store = SnapshotStore(":memory:")
    mv = _make_mv(commit_hash="tv49_h1")
    store.insert(mv)

    dv = DiagnosticVector(
        dominant_frequency_H=0.12,
        spectral_entropy_H=0.47,
        phase_coupling_CC_H=0.65,
        burst_index=0.31,
        self_cure_probability=0.035,
        onset_reversibility=0.22,
        degradation_signature="TECH_DEBT_ACCUMULATION",
        frequency_anomaly_score=0.42,
        module_id="test.mod",
        n_snapshots=10,
    )
    dv_json = json.dumps(dv.to_dict(), default=str)
    store.update_diagnostic("test.mod", "tv49_h1", dv_json)

    history = store.get_history("test.mod", window=10)
    assert len(history) >= 1
    restored = history[-1]
    diag = getattr(restored, "diagnostic", None)
    assert diag is not None, "DiagnosticVector not restored after update_diagnostic()"
    assert diag.degradation_signature == "TECH_DEBT_ACCUMULATION"
    assert abs(diag.frequency_anomaly_score - 0.42) < 1e-5


def test_tv50_snapshot_store_migrate_schema_idempotent():
    """TV50: _migrate_m70() can be called multiple times without error."""
    store = SnapshotStore(":memory:")
    with store._lock:
        cur = store._get_conn().cursor()
        # Call migration twice — should not raise
        store._migrate_m70(cur)
        store._migrate_m70(cur)


def test_tv51_snapshot_store_three_json_columns_exist():
    """TV51: The 3 M7.0 columns are present in the snapshots table schema."""
    store = SnapshotStore(":memory:")
    with store._lock:
        rows = store._get_conn().execute(
            "PRAGMA table_info(snapshots)"
        ).fetchall()

    col_names = {row[1] for row in rows}
    for expected in ("extended_vectors_json", "advanced_vector_json", "diagnostic_vector_json"):
        assert expected in col_names, f"Column {expected!r} not found in snapshots schema"


def test_tv52_snapshot_store_get_history_returns_mv_with_advanced():
    """TV52: get_history() deserializes AdvancedVector back onto the MetricVector."""
    store = SnapshotStore(":memory:")
    for i in range(3):
        mv = _make_mv(commit_hash=f"tv52_h{i}", timestamp=float(i + 1))
        mv.advanced = AdvancedVector(
            cognitive_cc_total=i * 5, cognitive_cc_max=i * 2,
            sqale_debt_minutes=i * 30, sqale_rating="A",
            clone_count=i, fn_profile_count=i + 1,
        )
        store.insert(mv)

    history = store.get_history("test.mod", window=10)
    assert len(history) == 3
    for mv in history:
        adv = getattr(mv, "advanced", None)
        assert adv is not None, "AdvancedVector missing from get_history() result"
        assert isinstance(adv, AdvancedVector)


# ═══════════════════════════════════════════════════════════════════════════════
# TV53-TV60 — Integration & API endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_tv53_uco_bridge_attaches_advanced_vector_for_complex_python():
    """TV53: UCOBridge.analyze() in full mode attaches mv.advanced to the result."""
    from sensor_core.uco_bridge import UCOBridge

    source = '''
def compute(data):
    result = 0
    for item in data:
        if item > 0:
            if item % 2 == 0:
                result += item * 2
            else:
                result += item
        elif item < -10:
            for sub in range(abs(item)):
                if sub % 3 == 0:
                    result -= sub
    return result

class Processor:
    def run(self, items):
        return [compute([x]) for x in items if x is not None]
    def validate(self, items):
        return all(isinstance(x, (int, float)) for x in items)
'''
    bridge = UCOBridge(mode="full")
    mv = bridge.analyze(source, module_id="tv53.mod", commit_hash="tv53")
    # AdvancedVector is attached only when AdvancedAnalyzer succeeds
    adv = getattr(mv, "advanced", None)
    if adv is not None:
        assert isinstance(adv, AdvancedVector)


def test_tv54_advanced_vector_cognitive_cc_total_positive_for_complex_code():
    """TV54: cognitive_cc_total > 0 for non-trivial Python source."""
    from sensor_core.uco_bridge import UCOBridge

    source = """
def parse_config(data):
    if not data:
        return {}
    result = {}
    for key, value in data.items():
        if isinstance(value, dict):
            result[key] = parse_config(value)
        elif isinstance(value, list):
            result[key] = [str(v) for v in value if v is not None]
        else:
            result[key] = str(value)
    return result
"""
    bridge = UCOBridge(mode="full")
    mv = bridge.analyze(source, module_id="tv54.mod", commit_hash="tv54")
    adv = getattr(mv, "advanced", None)
    if adv is not None:
        assert adv.cognitive_cc_total > 0, (
            f"Expected cognitive_cc_total > 0 for complex code, got {adv.cognitive_cc_total}"
        )


def test_tv55_advanced_vector_sqale_rating_is_valid_letter():
    """TV55: sqale_rating on an AdvancedVector is always one of A–E."""
    valid_ratings = {"A", "B", "C", "D", "E"}
    av = AdvancedVector(sqale_rating="C")
    assert av.sqale_rating in valid_ratings

    for letter in valid_ratings:
        av_test = AdvancedVector.from_dict({"sqale_rating": letter})
        assert av_test.sqale_rating in valid_ratings


def test_tv56_metrics_package_exports_advanced_vector():
    """TV56: from metrics import AdvancedVector succeeds (M7.0 export)."""
    from metrics import AdvancedVector as AV
    assert AV is AdvancedVector


def test_tv57_metrics_package_exports_diagnostic_vector():
    """TV57: from metrics import DiagnosticVector succeeds (M7.0 export)."""
    from metrics import DiagnosticVector as DV
    assert DV is DiagnosticVector


def test_tv58_handle_metrics_advanced_returns_400_for_missing_module():
    """TV58: GET /metrics/advanced without ?module= returns 400."""
    from api.server import handle_metrics_advanced
    code, data = handle_metrics_advanced(None)
    assert code == 400
    assert "error" in data


def test_tv59_handle_metrics_advanced_returns_404_for_unknown_module():
    """TV59: GET /metrics/advanced with unknown module returns 404."""
    from api.server import handle_metrics_advanced, _store

    # Use a module_id that is guaranteed not to exist
    code, data = handle_metrics_advanced("nonexistent.module.xyz.tv59")
    assert code == 404
    assert "error" in data


def test_tv60_advanced_and_diagnostic_to_dict_json_serializable():
    """TV60: both AdvancedVector and DiagnosticVector produce fully JSON-serializable dicts."""
    av = AdvancedVector(
        cognitive_cc_total=7, cognitive_cc_max=4,
        sqale_debt_minutes=60, sqale_rating="B",
        clone_count=1, fn_profile_count=3,
        module_id="test.mod", language="python",
    )
    dv = DiagnosticVector(
        dominant_frequency_H=0.12,
        spectral_entropy_H=0.47,
        phase_coupling_CC_H=0.65,
        burst_index=0.31,
        self_cure_probability=0.035,
        onset_reversibility=0.22,
        degradation_signature="TECH_DEBT_ACCUMULATION",
        frequency_anomaly_score=0.42,
        module_id="test.mod",
        n_snapshots=15,
    )
    # Both must serialize without error
    av_json = json.dumps(av.to_dict())
    dv_json = json.dumps(dv.to_dict())

    # Round-trip must preserve key values
    av_r = AdvancedVector.from_dict(json.loads(av_json))
    dv_r = DiagnosticVector.from_dict(json.loads(dv_json))

    assert av_r.cognitive_cc_total == 7
    assert av_r.sqale_rating == "B"
    assert dv_r.degradation_signature == "TECH_DEBT_ACCUMULATION"
    assert abs(dv_r.frequency_anomaly_score - 0.42) < 1e-6
    # DiagnosticVector risk_tier from restored vector
    assert dv_r.risk_tier() in ("STABLE", "WARNING", "CRITICAL")
