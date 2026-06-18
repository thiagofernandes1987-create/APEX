"""
Marco 37 — Sprint G: Signal Correctness (TG01–TG30)
=====================================================

Pins the **corrected** behavior of eight cirurgical fixes against
the bugs the Codex audit (2026-06-18) surfaced:

  C-1 (CRITICAL): "Absence = perfection"
  C-2 (HIGH):     Inverted RED tier sign (BIASED_DOWN vs BIASED_UP)
  C-3 (HIGH):     Hurst R/S gating < _MIN_SAMPLES_RELIABLE
  C-4 (MEDIUM):   INSERT OR REPLACE wiped diagnostic_vector
  C-5 (MEDIUM):   get_history without deterministic tiebreak
  C-7 (MEDIUM):   fixed_rules credited rules whose transform did not run
  C-8 (MEDIUM):   persist_error indistinguishable from opt-out
  lateral (LOW):  non-constant-time admin key comparison

Each test asserts the FIXED behavior — running these against the
pre-Sprint-G code base would fail, which is the whole point: they
become a permanent regression guard.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from metrics.anti_pattern_score import (
    aps_from_metric_vector, rate_aps,
)
from metrics.extended_vectors import SecurityVector, FlowVector
from governance.compound_alert import _classify, _aps_trend_from_store
from governance.repo_meta_score import compute_repo_meta_score
from sensor_core.predictor import _MIN_SAMPLES_RELIABLE


# ═══════════════════════════════════════════════════════════════════════════════
# G.1 — Absence ≠ perfection  (TG01–TG05)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG01_bare_metric_vector_yields_unknown():
    class Bare: pass
    result = aps_from_metric_vector(Bare())
    assert result["aps"] is None
    assert result["rating"] == "UNKNOWN"


def test_TG02_rate_aps_none_is_unknown():
    assert rate_aps(None) == "UNKNOWN"


def test_TG03_empty_repo_meta_is_unknown():
    meta = compute_repo_meta_score(SnapshotStore(":memory:"))
    assert meta.rating == "UNKNOWN"
    assert meta.score is None
    assert meta.n_modules_valid == 0


def test_TG04_one_extended_vector_is_enough_to_score():
    # Even ONE attached vector unlocks scoring (UNKNOWN only applies to total absence).
    mv = MetricVector("m", "c", 0.0)
    mv.security = SecurityVector(sca_vulnerable_deps=3)
    result = aps_from_metric_vector(mv)
    assert result["aps"] is not None
    assert result["rating"] != "UNKNOWN"


def test_TG05_unknown_payload_serializes_with_null_score():
    meta = compute_repo_meta_score(SnapshotStore(":memory:"))
    payload = meta.to_dict()
    assert payload["score"] is None
    assert payload["rating"] == "UNKNOWN"
    assert payload["weighted_aps"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# G.2 — RED tier sign correctness  (TG06–TG09)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG06_biased_up_with_persistent_degrading_yields_red():
    # bias > 0  ⇔  actual > forecast  ⇔  predictor UNDERSHOT (dangerous)
    tier, reasons = _classify("DEGRADING_PERSISTENT", "BIASED_UP", -1.0, 0.2)
    assert tier == "RED"
    # Reason text should reflect undershoot semantics, not overshoot.
    joined = " ".join(reasons).lower()
    assert "undershoot" in joined or "steeper" in joined


def test_TG07_biased_down_with_persistent_degrading_is_amber_not_red():
    # bias < 0  ⇔  predictor OVERSHOT (safe direction).
    # This was the BUG: previously fired RED.  Now should be AMBER.
    tier, _ = _classify("DEGRADING_PERSISTENT", "BIASED_DOWN", -1.0, 0.2)
    assert tier == "AMBER"


def test_TG08_only_biased_up_still_amber_without_persistent_aps():
    tier, _ = _classify("STABLE", "BIASED_UP", 0.0, 0.2)
    assert tier == "AMBER"


def test_TG09_green_remains_green_with_clean_signals():
    tier, _ = _classify("STABLE", "ACCURATE", 0.0, 0.02)
    assert tier == "GREEN"


# ═══════════════════════════════════════════════════════════════════════════════
# G.3 — Hurst gate ≥ _MIN_SAMPLES_RELIABLE  (TG10–TG12)
# ═══════════════════════════════════════════════════════════════════════════════

def _store_with_n_aps_samples(n: int) -> SnapshotStore:
    """Create a store with n APS samples, decreasing — a degrading series."""
    store = SnapshotStore(":memory:")
    for i in range(n):
        mv = MetricVector("m", f"c{i}", float(i), hamiltonian=100.0 - i * 10)
        # Attach a vector that varies — drives APS down across the series.
        mv.security = SecurityVector(sca_vulnerable_deps=i)
        store.insert(mv)
    return store


def test_TG10_below_reliable_threshold_never_persistent():
    # 7 samples < 8 → cannot be DEGRADING_PERSISTENT, may still be DEGRADING.
    store = _store_with_n_aps_samples(7)
    trend = _aps_trend_from_store(store, "m", window=50)
    assert trend["verdict"] != "DEGRADING_PERSISTENT"


def test_TG11_at_reliable_threshold_may_be_persistent():
    # 10 samples ≥ 8 → eligible for the persistent verdict if Hurst > 0.55.
    store = _store_with_n_aps_samples(10)
    trend = _aps_trend_from_store(store, "m", window=50)
    # We don't pin the exact verdict (depends on the series shape) — only that
    # the gate is now eligible to fire on a long enough monotonic series.
    assert trend["n_samples"] >= _MIN_SAMPLES_RELIABLE


def test_TG12_min_samples_reliable_constant_remains_eight():
    # If someone bumps this without updating callers, the gate logic breaks.
    assert _MIN_SAMPLES_RELIABLE == 8


# ═══════════════════════════════════════════════════════════════════════════════
# G.4 — Re-insert preserves diagnostic  (TG13–TG15)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG13_reinsert_preserves_diagnostic_vector():
    store = SnapshotStore(":memory:")
    mv = MetricVector("m", "c", 1.0, hamiltonian=5.0)
    store.insert(mv)
    store.update_diagnostic("m", "c", '{"primary_error":"GOD_CLASS"}')
    store.insert(mv)  # re-scan
    diag = getattr(store.get_history("m")[0], "diagnostic", None)
    assert diag is not None


def test_TG14_reinsert_overwrites_primary_channels():
    store = SnapshotStore(":memory:")
    store.insert(MetricVector("m", "c", 1.0, hamiltonian=5.0))
    store.insert(MetricVector("m", "c", 1.0, hamiltonian=42.0))
    hist = store.get_history("m")
    assert len(hist) == 1
    assert hist[0].hamiltonian == 42.0


def test_TG15_reinsert_preserves_aps_when_new_is_null():
    """When the new insert has no extended vectors, the previously-computed
    APS must NOT be wiped (COALESCE preserves it)."""
    store = SnapshotStore(":memory:")
    mv_with_vec = MetricVector("m", "c", 1.0, hamiltonian=5.0)
    mv_with_vec.security = SecurityVector(sca_vulnerable_deps=5)
    store.insert(mv_with_vec)
    # Re-insert with NO vectors — should NOT wipe the APS.
    plain = MetricVector("m", "c", 1.0, hamiltonian=5.0)
    store.insert(plain)
    hist = store.get_aps_history("m")
    assert hist[0][2] is not None  # APS preserved


# ═══════════════════════════════════════════════════════════════════════════════
# G.5 — Deterministic tiebreak on get_history  (TG16–TG18)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG16_get_history_breaks_ties_by_id_desc():
    store = SnapshotStore(":memory:")
    # Same timestamp on both — old code's ordering was undefined.
    store.insert(MetricVector("m", "cA", 1.0, hamiltonian=1.0))
    store.insert(MetricVector("m", "cB", 1.0, hamiltonian=9.0))
    hist = store.get_history("m", window=10)
    # ASC after reversal of DESC ⇒ oldest insert first ⇒ cA before cB.
    assert hist[0].commit_hash == "cA"
    assert hist[1].commit_hash == "cB"


def test_TG17_get_aps_history_breaks_ties_by_id_desc():
    store = SnapshotStore(":memory:")
    mv1 = MetricVector("m", "cA", 1.0, hamiltonian=1.0)
    mv1.security = SecurityVector(sca_vulnerable_deps=1)
    mv2 = MetricVector("m", "cB", 1.0, hamiltonian=1.0)
    mv2.security = SecurityVector(sca_vulnerable_deps=2)
    store.insert(mv1)
    store.insert(mv2)
    hist = store.get_aps_history("m")
    assert [h[0] for h in hist] == ["cA", "cB"]


def test_TG18_get_predictor_history_breaks_ties_by_id_desc():
    store = SnapshotStore(":memory:")
    store.insert(MetricVector("m", "cA", 1.0, hamiltonian=1.0))
    store.insert(MetricVector("m", "cB", 1.0, hamiltonian=2.0))
    hist = store.get_predictor_history("m")
    assert [h["commit"] for h in hist] == ["cA", "cB"]


# ═══════════════════════════════════════════════════════════════════════════════
# G.6 — fixed_rules causally restricted  (TG19–TG22)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG19_unmapped_rule_not_credited_as_fixed():
    """When auto_remediate runs but the rule that disappeared has NO mapped
    transform, it must NOT be in fixed_rules."""
    from sensor_core.autofix.sast_remediation import auto_remediate
    # Source with weak hash (mapped via SAST006) + nothing else.
    # The fix runs WeakHashReplacer; only SAST006 should be credited.
    src = "import hashlib\nhashlib.md5(b'x').hexdigest()\n"
    r = auto_remediate(src, module_id="g19")
    assert r.fixed_rules == ["SAST006"]
    # Anything else that "disappeared by accident" would have shown up here.


def test_TG20_no_transform_applied_means_no_fixed_rules():
    from sensor_core.autofix.sast_remediation import auto_remediate
    src = "x = 1\n"
    r = auto_remediate(src, module_id="g20")
    assert r.fixed_rules == []
    assert r.transforms_applied == []


def test_TG21_combined_run_only_credits_mapped_rules():
    """A combined fix should credit only the rules whose transform mapping ran."""
    from sensor_core.autofix.sast_remediation import auto_remediate
    src = (
        "import hashlib\nimport jwt\n"
        "hashlib.md5(b'x').hexdigest()\n"
        "jwt.decode(t, k, verify=False)\n"
    )
    r = auto_remediate(src, module_id="g21")
    assert set(r.fixed_rules) <= {"SAST006", "SAST024"}
    assert "SAST006" in r.fixed_rules
    assert "SAST024" in r.fixed_rules


def test_TG22_fixed_count_matches_fixed_rules_length():
    from sensor_core.autofix.sast_remediation import auto_remediate
    src = "import hashlib\nhashlib.md5(b'x').hexdigest()\n"
    r = auto_remediate(src)
    assert r.fixed_count == len(r.fixed_rules)


# ═══════════════════════════════════════════════════════════════════════════════
# G.7 — persist_error distinguishable from opt-out  (TG23–TG25)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG23_persist_failure_surfaces_persist_error_field():
    import api.server as srv
    from unittest.mock import patch
    src = "import hashlib\nhashlib.md5(b'x').hexdigest()\n"
    with patch.object(srv._store, "store_remediation",
                      side_effect=RuntimeError("disk full")):
        code, payload = srv.handle_apex_auto_remediate(
            {"code": src, "module_id": "g23", "persist": True}
        )
    assert code == 200
    assert payload["persisted_id"] is None
    assert "persist_error" in payload
    assert "RuntimeError" in payload["persist_error"]


def test_TG24_opt_out_does_not_surface_persist_error():
    import api.server as srv
    src = "import hashlib\nhashlib.md5(b'x').hexdigest()\n"
    code, payload = srv.handle_apex_auto_remediate(
        {"code": src, "module_id": "g24", "persist": False}
    )
    assert code == 200
    assert payload["persisted_id"] is None
    # Opt-out: no error key in payload — distinguishes from failure.
    assert "persist_error" not in payload


def test_TG25_successful_persist_has_no_error_field():
    import api.server as srv
    src = "import hashlib\nhashlib.md5(b'x').hexdigest()\n"
    code, payload = srv.handle_apex_auto_remediate(
        {"code": src, "module_id": "g25", "persist": True}
    )
    assert code == 200
    assert payload["persisted_id"] is not None
    assert "persist_error" not in payload


# ═══════════════════════════════════════════════════════════════════════════════
# G.8 — Constant-time admin compare  (TG26–TG27)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG26_authenticate_admin_uses_compare_digest():
    """Inspect source — paranoid pin: nobody silently reverts to ``==``."""
    import inspect, api.server as srv
    src = inspect.getsource(srv._authenticate)
    assert "compare_digest" in src
    assert "plain_key == admin_k" not in src


def test_TG27_admin_compare_accepts_correct_and_rejects_wrong():
    import api.server as srv
    saved_key  = srv._config.admin_key
    saved_auth = srv._config.auth_enabled
    srv._config.admin_key   = "secret-admin-token"
    srv._config.auth_enabled = True       # _authenticate short-circuits in dev mode
    try:
        ok, _ = srv._authenticate("secret-admin-token", require_admin=True)
        assert ok is True
        ok, _ = srv._authenticate("wrong-token",         require_admin=True)
        assert ok is False
        ok, _ = srv._authenticate("",                    require_admin=True)
        assert ok is False
    finally:
        srv._config.admin_key    = saved_key
        srv._config.auth_enabled = saved_auth


# ═══════════════════════════════════════════════════════════════════════════════
# Integration  (TG28–TG30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TG28_meta_score_unknown_propagates_through_payload():
    """End-to-end: handle_repo_health_score on an empty store returns UNKNOWN."""
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_repo_health_score(window=50)
    assert code == 200
    assert payload["rating"] == "UNKNOWN"
    assert payload["score"] is None


def test_TG29_compound_alert_on_short_series_cannot_be_red():
    """End-to-end: a module with 5 APS samples can never reach RED, even if
    the synthetic series perfectly fits a persistent-degrading pattern."""
    import api.server as srv
    from governance.compound_alert import compute_compound_alert
    srv._store = SnapshotStore(":memory:")
    for i in range(5):
        mv = MetricVector("m", f"c{i}", float(i), hamiltonian=100.0 - i*20)
        mv.security = SecurityVector(sca_vulnerable_deps=i)
        srv._store.insert(mv)
    alert = compute_compound_alert(srv._store, "m", window=50)
    assert alert.tier != "RED"


def test_TG30_aps_persist_to_diagnostic_loop_survives_reinsert():
    """G.1 + G.4 together: APS is computed once, diagnostic added after, the
    same (module, commit) re-inserted — both must survive."""
    store = SnapshotStore(":memory:")
    mv = MetricVector("m", "c", 1.0, hamiltonian=5.0)
    mv.security = SecurityVector(sca_vulnerable_deps=2)
    store.insert(mv)
    store.update_diagnostic("m", "c", '{"primary_error":"GOD_CLASS"}')
    # Re-scan: same commit, no extended vectors this time.
    bare = MetricVector("m", "c", 1.0, hamiltonian=5.0)
    store.insert(bare)
    # APS was preserved (G.4 COALESCE) AND diagnostic survives.
    hist_full = store.get_history("m")
    hist_aps  = store.get_aps_history("m")
    assert hist_aps[0][2] is not None              # APS preserved
    assert getattr(hist_full[0], "diagnostic", None) is not None
