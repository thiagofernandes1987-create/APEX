"""
Marco 34 — Sprint C: Auto-Fix Telemetry (TR01–TR30)
====================================================

Closes the LEAP 3 loop by persisting every ``auto_remediate()`` call into
the ``remediations`` table, then aggregating that history into stats
(success rate, top fixed rules, top transforms, …).

Coverage:
  * Persistence  (TR01–TR10): store_remediation correctness, idempotence,
    duck-typing of RemediationResult vs dict, defensive behaviour on
    partial inputs.
  * History      (TR11–TR20): ordering, limit, multi-module separation,
    repo-wide aggregation, payload round-trip.
  * Stats        (TR21–TR30): aggregation correctness, frequency ranking,
    top-k bounds, repo-wide vs per-module filter, time bookends.
"""
from __future__ import annotations

import time
import pytest

from sensor_storage.snapshot_store import SnapshotStore
from sensor_core.autofix.sast_remediation import RemediationResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def store() -> SnapshotStore:
    return SnapshotStore(":memory:")


def _make_result(
    *,
    is_valid: bool = True,
    transforms: list = None,
    before: list = None,
    after: list = None,
    fixed: list = None,
) -> RemediationResult:
    """Build a synthetic RemediationResult — bypasses the real SAST scan."""
    before = before if before is not None else ["SAST006", "SAST007"]
    after  = after  if after  is not None else []
    fixed  = fixed  if fixed  is not None else sorted(set(before) - set(after))
    transforms = transforms if transforms is not None else ["WeakHashReplacer"]
    return RemediationResult(
        patched_source="# patched\n",
        is_valid=is_valid,
        transforms_applied=transforms,
        findings_before=before,
        findings_after=after,
        fixed_rules=fixed,
        residual_count=len(after),
    )


# ─── Persistence (TR01–TR10) ──────────────────────────────────────────────────

def test_TR01_store_returns_positive_row_id(store):
    rid = store.store_remediation("mod1", _make_result())
    assert rid > 0


def test_TR02_multiple_inserts_get_distinct_ids(store):
    ids = [store.store_remediation("m", _make_result()) for _ in range(5)]
    assert len(set(ids)) == 5
    assert all(i > 0 for i in ids)


def test_TR03_all_fields_round_trip(store):
    r = _make_result(transforms=["A", "B"], before=["X1", "X2"], after=["X2"], fixed=["X1"])
    store.store_remediation("modX", r, commit_hash="abc123")
    row = store.get_remediation_history("modX")[0]
    assert row["module_id"]          == "modX"
    assert row["commit_hash"]        == "abc123"
    assert row["is_valid"]           is True
    assert row["findings_before"]    == 2
    assert row["findings_after"]     == 1
    assert row["fixed_count"]        == 1
    assert row["residual_count"]     == 1
    assert row["transforms_applied"] == ["A", "B"]
    assert row["fixed_rules"]        == ["X1"]


def test_TR04_accepts_dict_input(store):
    payload = _make_result().to_dict()
    rid = store.store_remediation("mD", payload)
    assert rid > 0
    row = store.get_remediation_history("mD")[0]
    assert row["fixed_count"] == 2


def test_TR05_uses_provided_timestamp(store):
    store.store_remediation("mT", _make_result(), timestamp=1000.0)
    assert store.get_remediation_history("mT")[0]["timestamp"] == 1000.0


def test_TR06_falls_back_to_current_time(store):
    before = time.time()
    store.store_remediation("mT2", _make_result())
    after = time.time()
    ts = store.get_remediation_history("mT2")[0]["timestamp"]
    assert before - 1.0 <= ts <= after + 1.0


def test_TR07_empty_findings_persisted_cleanly(store):
    r = _make_result(before=[], after=[], fixed=[], transforms=[])
    store.store_remediation("mE", r)
    row = store.get_remediation_history("mE")[0]
    assert row["findings_before"]    == 0
    assert row["findings_after"]     == 0
    assert row["fixed_count"]        == 0
    assert row["transforms_applied"] == []


def test_TR08_invalid_fix_persisted_as_false(store):
    r = _make_result(is_valid=False, after=["SAST006", "SAST007"], fixed=[])
    store.store_remediation("mI", r)
    row = store.get_remediation_history("mI")[0]
    assert row["is_valid"] is False
    assert row["fixed_count"] == 0


def test_TR09_partial_dict_uses_neutral_defaults(store):
    rid = store.store_remediation("mP", {"is_valid": True})
    assert rid > 0
    row = store.get_remediation_history("mP")[0]
    assert row["findings_before"]    == 0
    assert row["findings_after"]     == 0
    assert row["fixed_count"]        == 0
    assert row["transforms_applied"] == []


def test_TR10_modules_are_isolated(store):
    store.store_remediation("modA", _make_result())
    store.store_remediation("modB", _make_result())
    assert len(store.get_remediation_history("modA")) == 1
    assert len(store.get_remediation_history("modB")) == 1


# ─── History (TR11–TR20) ──────────────────────────────────────────────────────

def test_TR11_history_empty_for_unknown_module(store):
    assert store.get_remediation_history("ghost") == []


def test_TR12_history_oldest_first(store):
    for ts in (300.0, 100.0, 200.0):
        store.store_remediation("mO", _make_result(), timestamp=ts)
    timestamps = [r["timestamp"] for r in store.get_remediation_history("mO")]
    assert timestamps == sorted(timestamps)


def test_TR13_history_respects_limit(store):
    for ts in range(10):
        store.store_remediation("mL", _make_result(), timestamp=float(ts))
    rows = store.get_remediation_history("mL", limit=4)
    assert len(rows) == 4


def test_TR14_history_repo_wide_when_module_is_none(store):
    store.store_remediation("a", _make_result())
    store.store_remediation("b", _make_result())
    store.store_remediation("c", _make_result())
    assert len(store.get_remediation_history(module_id=None)) == 3


def test_TR15_findings_after_rules_round_trip(store):
    r = _make_result(before=["SAST006", "SAST007", "SAST038"],
                     after=["SAST038"], fixed=["SAST006", "SAST007"])
    store.store_remediation("mF", r)
    row = store.get_remediation_history("mF")[0]
    assert row["findings_after_rules"] == ["SAST038"]


def test_TR16_transforms_list_round_trip(store):
    r = _make_result(transforms=["WeakHashReplacer", "InsecureRandomReplacer"])
    store.store_remediation("mTR", r)
    row = store.get_remediation_history("mTR")[0]
    assert row["transforms_applied"] == ["WeakHashReplacer", "InsecureRandomReplacer"]


def test_TR17_commit_hash_round_trip(store):
    store.store_remediation("mC", _make_result(), commit_hash="deadbeef")
    assert store.get_remediation_history("mC")[0]["commit_hash"] == "deadbeef"


def test_TR18_history_filter_by_module(store):
    store.store_remediation("alpha", _make_result(before=["SAST006"], after=[], fixed=["SAST006"]))
    store.store_remediation("beta",  _make_result(before=["SAST007"], after=[], fixed=["SAST007"]))
    rows = store.get_remediation_history("alpha")
    assert len(rows) == 1
    assert rows[0]["fixed_rules"] == ["SAST006"]


def test_TR19_findings_before_rules_round_trip(store):
    r = _make_result(before=["SAST006", "SAST007", "SAST039"], after=["SAST039"])
    store.store_remediation("mB", r)
    row = store.get_remediation_history("mB")[0]
    assert row["findings_before_rules"] == ["SAST006", "SAST007", "SAST039"]


def test_TR20_history_keeps_repeated_rule_ids(store):
    # A run that fixed the same rule twice (multi-occurrence in source).
    r = _make_result(before=["SAST006", "SAST006"], after=[], fixed=["SAST006"])
    store.store_remediation("mR", r)
    row = store.get_remediation_history("mR")[0]
    assert row["findings_before_rules"] == ["SAST006", "SAST006"]
    assert row["fixed_rules"]           == ["SAST006"]


# ─── Stats (TR21–TR30) ────────────────────────────────────────────────────────

def test_TR21_stats_zero_when_empty(store):
    stats = store.get_remediation_stats(module_id="empty")
    assert stats["n_total"]       == 0
    assert stats["success_rate"]  == 0.0
    assert stats["top_fixed_rules"] == []


def test_TR22_stats_n_total_counts_rows(store):
    for _ in range(7):
        store.store_remediation("mN", _make_result())
    assert store.get_remediation_stats("mN")["n_total"] == 7


def test_TR23_stats_success_rate(store):
    # 3 runs that fixed something, 2 that did not.
    for _ in range(3):
        store.store_remediation("mS", _make_result())  # fixes SAST006+SAST007
    for _ in range(2):
        store.store_remediation("mS", _make_result(before=["SAST038"], after=["SAST038"], fixed=[]))
    stats = store.get_remediation_stats("mS")
    assert stats["n_total"]      == 5
    assert stats["n_with_fixes"] == 3
    assert stats["success_rate"] == pytest.approx(0.6, abs=1e-9)


def test_TR24_stats_total_fixed_aggregates(store):
    for _ in range(4):
        # Each run fixes 2 rules.
        store.store_remediation("mA", _make_result())
    assert store.get_remediation_stats("mA")["total_fixed"] == 8


def test_TR25_stats_top_fixed_rules_frequency_desc(store):
    store.store_remediation("mF", _make_result(before=["SAST006"], after=[], fixed=["SAST006"]))
    store.store_remediation("mF", _make_result(before=["SAST006"], after=[], fixed=["SAST006"]))
    store.store_remediation("mF", _make_result(before=["SAST007"], after=[], fixed=["SAST007"]))
    top = store.get_remediation_stats("mF")["top_fixed_rules"]
    assert top[0] == {"rule_id": "SAST006", "count": 2}
    assert top[1] == {"rule_id": "SAST007", "count": 1}


def test_TR26_stats_top_transforms_frequency_desc(store):
    store.store_remediation("mT", _make_result(transforms=["A", "B"]))
    store.store_remediation("mT", _make_result(transforms=["A"]))
    store.store_remediation("mT", _make_result(transforms=["A", "C"]))
    top = store.get_remediation_stats("mT")["top_transforms"]
    assert top[0]["transform"] == "A"
    assert top[0]["count"]     == 3


def test_TR27_stats_top_k_bounds(store):
    # 5 distinct rule IDs.
    for rule in ("R1", "R2", "R3", "R4", "R5"):
        store.store_remediation("mK", _make_result(
            before=[rule], after=[], fixed=[rule],
        ))
    top = store.get_remediation_stats("mK", top_k=3)["top_fixed_rules"]
    assert len(top) == 3


def test_TR28_stats_mean_fixed_per_run(store):
    store.store_remediation("mM", _make_result(before=["X"], after=[],          fixed=["X"]))           # 1
    store.store_remediation("mM", _make_result(before=["Y", "Z"], after=[],     fixed=["Y", "Z"]))      # 2
    store.store_remediation("mM", _make_result(before=["W", "V", "U"], after=[], fixed=["W", "V", "U"])) # 3
    stats = store.get_remediation_stats("mM")
    assert stats["mean_fixed"] == pytest.approx(2.0, abs=1e-9)


def test_TR29_stats_module_filter_vs_repo_wide(store):
    store.store_remediation("alpha", _make_result())
    store.store_remediation("beta",  _make_result())
    store.store_remediation("beta",  _make_result())

    assert store.get_remediation_stats("alpha")["n_total"]      == 1
    assert store.get_remediation_stats("beta")["n_total"]       == 2
    assert store.get_remediation_stats(module_id=None)["n_total"] == 3


def test_TR30_stats_first_last_timestamps(store):
    store.store_remediation("mE", _make_result(), timestamp=10.0)
    store.store_remediation("mE", _make_result(), timestamp=99.0)
    store.store_remediation("mE", _make_result(), timestamp=55.0)
    stats = store.get_remediation_stats("mE")
    assert stats["first_ts"] == 10.0
    assert stats["last_ts"]  == 99.0
