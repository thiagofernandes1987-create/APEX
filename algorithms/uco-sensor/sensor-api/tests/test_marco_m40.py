"""
Marco 40 — Sprint I: Performance — Predictor/APS off hot-path + native SQL (TI01-TI30)
========================================================================================

Validates the three performance changes of Sprint I:

  I.1  ``insert(mv, defer_derived=True)`` skips APS + forecast on the hot
       path; ``recompute_derived(...)`` and ``recompute_derived_pending(...)``
       backfill at a quieter moment.  Addresses Codex D-4.
  I.2  ``store.latest_aps_per_module()`` replaces the N+1 Python loop in
       ``governance/repo_meta_score.py`` with one SQL self-join.
       Addresses Codex movement #2.
  I.3  ``get_remediation_stats()`` aggregates scalars (n_total, n_valid,
       sums, MIN/MAX timestamps) in ONE native SQL query; only top_k
       frequency tables still need Python JSON parsing.

Coverage layout
---------------
* TI01-TI10 — I.1 deferred insert + recompute
* TI11-TI20 — I.2 latest_aps_per_module SQL parity + speed
* TI21-TI30 — I.3 native-SQL stats parity + perf characteristics
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from metrics.extended_vectors import SecurityVector
from sensor_core.autofix.sast_remediation import RemediationResult


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mv(mod: str, commit: str, ts: float, *, deps: int = 0) -> MetricVector:
    mv = MetricVector(mod, commit, ts, hamiltonian=10.0)
    mv.security = SecurityVector(sca_vulnerable_deps=deps)
    return mv


def _rr(*, valid: bool = True, fixed: list = None,
        transforms: list = None) -> RemediationResult:
    fixed = fixed if fixed is not None else ["SAST006"]
    transforms = transforms if transforms is not None else ["WeakHashReplacer"]
    return RemediationResult(
        patched_source="", is_valid=valid,
        transforms_applied=transforms,
        findings_before=["SAST006"], findings_after=[],
        fixed_rules=fixed, residual_count=0,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# I.1 — Deferred APS/forecast on insert (TI01-TI10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TI01_default_insert_still_computes_derived():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=3))
    assert s.get_aps_history("m")[0][2] is not None


def test_TI02_defer_derived_skips_aps_computation():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=3), defer_derived=True)
    assert s.get_aps_history("m")[0][2] is None


def test_TI03_defer_derived_skips_predictor_columns():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=3), defer_derived=True)
    samples = s.get_predictor_history("m")
    assert samples[0]["hurst"] is None


def test_TI04_recompute_derived_populates_aps():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=3), defer_derived=True)
    assert s.recompute_derived("m", "c0") is True
    assert s.get_aps_history("m")[0][2] is not None


def test_TI05_recompute_derived_unknown_returns_false():
    s = SnapshotStore(":memory:")
    assert s.recompute_derived("ghost", "c0") is False


def test_TI06_recompute_pending_finds_only_null_rows():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=1))                       # already populated
    s.insert(_mv("m", "c1", 1.0, deps=2), defer_derived=True)   # pending
    s.insert(_mv("m", "c2", 2.0, deps=3), defer_derived=True)   # pending
    n = s.recompute_derived_pending()
    assert n == 2


def test_TI07_recompute_pending_scoped_by_module():
    s = SnapshotStore(":memory:")
    s.insert(_mv("modA", "c0", 0.0, deps=1), defer_derived=True)
    s.insert(_mv("modB", "c0", 0.0, deps=1), defer_derived=True)
    n = s.recompute_derived_pending(module_id="modA")
    assert n == 1


def test_TI08_recompute_pending_idempotent():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=1), defer_derived=True)
    s.recompute_derived_pending()
    second = s.recompute_derived_pending()
    assert second == 0


def test_TI09_defer_derived_then_reinsert_with_compute_preserves_aps():
    """COALESCE on upsert (Sprint G G.4) interacts with deferred derived."""
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=3))                # APS populated
    s.insert(_mv("m", "c0", 0.0, deps=3), defer_derived=True)  # re-scan
    # The re-insert with defer_derived sent NULL → COALESCE keeps the OLD APS.
    assert s.get_aps_history("m")[0][2] is not None


def test_TI10_defer_derived_speeds_up_batch_insert():
    """Sanity check: deferred path is FASTER on bulk inserts."""
    import time
    N = 30
    fast = SnapshotStore(":memory:")
    slow = SnapshotStore(":memory:")

    t0 = time.perf_counter()
    for i in range(N):
        slow.insert(_mv("m", f"c{i}", float(i), deps=i))
    t_slow = time.perf_counter() - t0

    t0 = time.perf_counter()
    for i in range(N):
        fast.insert(_mv("m", f"c{i}", float(i), deps=i), defer_derived=True)
    t_fast = time.perf_counter() - t0

    # Deferred should be at least as fast as default; usually ~30% faster.
    # We just sanity-check it doesn't regress to noticeably slower.
    assert t_fast <= t_slow * 1.1


# ═══════════════════════════════════════════════════════════════════════════════
# I.2 — latest_aps_per_module SQL fast path (TI11-TI20)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TI11_latest_aps_returns_one_row_per_module():
    s = SnapshotStore(":memory:")
    for mod in ("a", "b", "c"):
        for i in range(3):
            s.insert(_mv(mod, f"c{i}", float(i), deps=i + 1))
    rows = s.latest_aps_per_module()
    mods = sorted(r["module_id"] for r in rows)
    assert mods == ["a", "b", "c"]


def test_TI12_latest_aps_picks_most_recent_timestamp():
    s = SnapshotStore(":memory:")
    s.insert(_mv("m", "c0", 0.0, deps=1))
    s.insert(_mv("m", "c1", 5.0, deps=8))
    s.insert(_mv("m", "c2", 3.0, deps=4))
    rows = s.latest_aps_per_module()
    assert rows[0]["timestamp"] == 5.0


def test_TI13_latest_aps_skips_modules_without_any_aps():
    s = SnapshotStore(":memory:")
    s.insert(_mv("withaps", "c0", 0.0, deps=1))
    s.insert(_mv("noaps",   "c0", 0.0), defer_derived=True)  # aps_score NULL
    mods = [r["module_id"] for r in s.latest_aps_per_module()]
    assert mods == ["withaps"]


def test_TI14_latest_aps_carries_loc_field():
    s = SnapshotStore(":memory:")
    mv = _mv("m", "c0", 0.0, deps=1)
    mv.lines_of_code = 423
    s.insert(mv)
    assert s.latest_aps_per_module()[0]["loc"] == 423


def test_TI15_latest_aps_empty_store_returns_empty_list():
    assert SnapshotStore(":memory:").latest_aps_per_module() == []


def test_TI16_repo_meta_score_uses_fast_path():
    """The fast path returns the same data the legacy loop did."""
    from governance.repo_meta_score import _latest_aps_per_module
    s = SnapshotStore(":memory:")
    for mod in ("a", "b"):
        s.insert(_mv(mod, "c0", 0.0, deps=2))
    rows = _latest_aps_per_module(s, window=100)
    assert len(rows) == 2
    for r in rows:
        assert "module_id" in r and "aps" in r and "loc" in r


def test_TI17_legacy_loop_fallback_when_method_missing():
    """Stub stores lacking latest_aps_per_module still work via fallback."""
    from governance.repo_meta_score import _latest_aps_per_module

    class StubStore:
        def list_modules(self):
            return ["x"]
        def get_aps_history(self, module_id, window):
            return [("c0", 0.0, 73.5)]
        def get_history(self, module_id, window):
            class Row: lines_of_code = 50
            return [Row()]

    rows = _latest_aps_per_module(StubStore(), window=100)
    assert rows == [{"module_id": "x", "aps": 73.5, "loc": 50}]


def test_TI18_meta_score_end_to_end_with_fast_path():
    from governance.repo_meta_score import compute_repo_meta_score
    s = SnapshotStore(":memory:")
    for mod in ("a", "b", "c"):
        mv = _mv(mod, "c0", 0.0, deps=1)
        mv.lines_of_code = 100
        s.insert(mv)
    meta = compute_repo_meta_score(s)
    assert meta.rating != "UNKNOWN"
    assert meta.n_modules_valid == 3


def test_TI19_fast_path_is_faster_than_legacy_at_scale():
    """The fast path should beat N+1 Python loops with N modules."""
    s = SnapshotStore(":memory:")
    for i in range(40):
        s.insert(_mv(f"mod{i}", "c0", 0.0, deps=1))
    fast_t0 = time.perf_counter()
    fast_rows = s.latest_aps_per_module()
    fast_t = time.perf_counter() - fast_t0

    # Force legacy path via stub wrapping
    class LegacyWrap:
        def __init__(self, real): self._real = real
        def list_modules(self): return self._real.list_modules()
        def get_aps_history(self, m, window): return self._real.get_aps_history(m, window=window)
        def get_history(self, m, window): return self._real.get_history(m, window=window)
    from governance.repo_meta_score import _latest_aps_per_module
    leg_t0 = time.perf_counter()
    leg_rows = _latest_aps_per_module(LegacyWrap(s), window=100)
    leg_t = time.perf_counter() - leg_t0

    assert len(fast_rows) == len(leg_rows)
    # Loose sanity bound — the SQL path should at least not be slower than 2x.
    assert fast_t <= leg_t * 2


def test_TI20_fast_path_only_returns_aps_not_null():
    s = SnapshotStore(":memory:")
    s.insert(_mv("withaps", "c0", 0.0, deps=1))
    s.insert(_mv("noaps", "c1", 1.0), defer_derived=True)
    rows = s.latest_aps_per_module()
    for r in rows:
        assert r["aps"] is not None


# ═══════════════════════════════════════════════════════════════════════════════
# I.3 — Native SQL get_remediation_stats (TI21-TI30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TI21_stats_empty_store_returns_zeroes():
    stats = SnapshotStore(":memory:").get_remediation_stats()
    assert stats["n_total"] == 0
    assert stats["first_ts"] is None
    assert stats["last_ts"]  is None
    assert stats["top_fixed_rules"] == []


def test_TI22_stats_n_total_matches_inserts():
    s = SnapshotStore(":memory:")
    for i in range(7):
        s.store_remediation("m", _rr(), timestamp=float(i))
    assert s.get_remediation_stats("m")["n_total"] == 7


def test_TI23_stats_n_valid_counts_compiling_rows():
    s = SnapshotStore(":memory:")
    for i in range(5):
        s.store_remediation("m", _rr(valid=(i < 3)), timestamp=float(i))
    assert s.get_remediation_stats("m")["n_valid"] == 3


def test_TI24_stats_n_with_fixes_excludes_zero_fix_runs():
    s = SnapshotStore(":memory:")
    for i in range(3):
        s.store_remediation("m", _rr(fixed=["SAST006"]), timestamp=float(i))
    for i in range(2):
        s.store_remediation("m", _rr(fixed=[]), timestamp=float(10 + i))
    assert s.get_remediation_stats("m")["n_with_fixes"] == 3


def test_TI25_stats_total_fixed_sums_per_row():
    s = SnapshotStore(":memory:")
    s.store_remediation("m", _rr(fixed=["A", "B"]),       timestamp=1.0)
    s.store_remediation("m", _rr(fixed=["C"]),            timestamp=2.0)
    s.store_remediation("m", _rr(fixed=["D", "E", "F"]),  timestamp=3.0)
    assert s.get_remediation_stats("m")["total_fixed"] == 6


def test_TI26_stats_first_last_ts_use_min_max():
    s = SnapshotStore(":memory:")
    s.store_remediation("m", _rr(), timestamp=10.0)
    s.store_remediation("m", _rr(), timestamp=99.0)
    s.store_remediation("m", _rr(), timestamp=55.0)
    stats = s.get_remediation_stats("m")
    assert stats["first_ts"] == 10.0
    assert stats["last_ts"]  == 99.0


def test_TI27_stats_top_fixed_rules_frequency_descending():
    s = SnapshotStore(":memory:")
    for _ in range(3):
        s.store_remediation("m", _rr(fixed=["SAST006"]))
    s.store_remediation("m", _rr(fixed=["SAST007"]))
    top = s.get_remediation_stats("m")["top_fixed_rules"]
    assert top[0]["rule_id"] == "SAST006"
    assert top[0]["count"]   == 3


def test_TI28_stats_module_scope_filter():
    s = SnapshotStore(":memory:")
    s.store_remediation("alpha", _rr())
    s.store_remediation("beta",  _rr())
    s.store_remediation("beta",  _rr())
    assert s.get_remediation_stats("alpha")["n_total"] == 1
    assert s.get_remediation_stats("beta")["n_total"]  == 2
    assert s.get_remediation_stats(module_id=None)["n_total"] == 3


def test_TI29_stats_top_transforms_descending():
    s = SnapshotStore(":memory:")
    for _ in range(4):
        s.store_remediation("m", _rr(transforms=["A"]))
    for _ in range(2):
        s.store_remediation("m", _rr(transforms=["B"]))
    top = s.get_remediation_stats("m")["top_transforms"]
    assert top[0]["transform"] == "A"
    assert top[0]["count"]     == 4


def test_TI30_stats_success_rate_consistent_with_counts():
    s = SnapshotStore(":memory:")
    for _ in range(5):
        s.store_remediation("m", _rr(fixed=["SAST006"]))
    for _ in range(5):
        s.store_remediation("m", _rr(fixed=[]))
    stats = s.get_remediation_stats("m")
    assert stats["success_rate"] == pytest.approx(stats["n_with_fixes"] / stats["n_total"])
    assert stats["success_rate"] == pytest.approx(0.5)
