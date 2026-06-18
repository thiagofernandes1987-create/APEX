"""
Marco 36 — Sprint E: Snapshot-Diff Vector (TV01-TV30)
=======================================================

Per-channel delta between two snapshots + volatility ranking
(coefficient of variation).  Answers the question every code-review
tool quietly wants: "what actually changed between commit A and B?"

Coverage layout
---------------
* TV01-TV10 — pure ``compute_diff`` correctness: deltas, percentages,
  direction labels, NaN/inf handling, missing-channel skipping,
  serialization.
* TV11-TV20 — ``compute_diff_by_commits`` over a populated
  SnapshotStore: hit, miss, identical commits, APS/LOC inclusion.
* TV21-TV30 — ``top_volatile_channels``: CV ranking, low-mean
  fallback, sample-count threshold, top_k bound, deterministic
  tiebreak, integration with handle_diff_volatile.
"""
from __future__ import annotations

import math
import time
import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector

from sensor_storage.snapshot_store import SnapshotStore
from metrics.snapshot_diff import (
    ChannelDelta, SnapshotDiff,
    compute_diff, compute_diff_by_commits, top_volatile_channels,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mv(commit: str, *, ts: float = 0.0, **kw) -> MetricVector:
    """Build a MetricVector with optional channel overrides."""
    base = dict(
        module_id="m",
        commit_hash=commit,
        timestamp=ts,
        hamiltonian=10.0,
        cyclomatic_complexity=5,
        infinite_loop_risk=0.1,
        dsm_density=0.5,
        dsm_cyclic_ratio=0.2,
        dependency_instability=0.3,
        syntactic_dead_code=2,
        duplicate_block_count=1,
        halstead_bugs=0.5,
    )
    base.update(kw)
    return MetricVector(**base)


def _populated_store(n: int = 8) -> SnapshotStore:
    store = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        store.insert(_mv(
            f"c{i}", ts=base + i,
            hamiltonian=10.0 + i * 2,
            infinite_loop_risk=0.1 * i,
            syntactic_dead_code=i,
            dsm_cyclic_ratio=0.1 + 0.05 * i,
        ))
    return store


# ─── compute_diff — pure (TV01-TV10) ──────────────────────────────────────────

def test_TV01_returns_snapshot_diff_object():
    d = compute_diff(_mv("a"), _mv("b"))
    assert isinstance(d, SnapshotDiff)
    assert d.commit_from == "a"
    assert d.commit_to   == "b"


def test_TV02_includes_all_nine_primary_channels():
    d = compute_diff(_mv("a"), _mv("b"))
    shorts = {c.short for c in d.channels}
    for required in ("H", "CC", "ILR", "DSM_d", "DSM_c", "DI", "dead", "dups", "bugs"):
        assert required in shorts


def test_TV03_no_change_yields_flat_direction():
    d = compute_diff(_mv("a"), _mv("b"))
    assert d.n_changed == 0
    assert all(c.direction == "FLAT" for c in d.channels)


def test_TV04_increase_yields_up_direction():
    d = compute_diff(_mv("a", hamiltonian=10.0), _mv("b", hamiltonian=14.0))
    h = next(c for c in d.channels if c.short == "H")
    assert h.direction == "UP"
    assert h.delta_abs == pytest.approx(4.0)
    assert h.delta_pct == pytest.approx(0.4)


def test_TV05_decrease_yields_down_direction():
    d = compute_diff(_mv("a", cyclomatic_complexity=10),
                     _mv("b", cyclomatic_complexity=6))
    cc = next(c for c in d.channels if c.short == "CC")
    assert cc.direction == "DOWN"
    assert cc.delta_abs == pytest.approx(-4.0)


def test_TV06_zero_to_nonzero_yields_inf_pct():
    d = compute_diff(_mv("a", syntactic_dead_code=0),
                     _mv("b", syntactic_dead_code=5))
    dead = next(c for c in d.channels if c.short == "dead")
    assert dead.direction == "UP"
    assert math.isinf(dead.delta_pct) and dead.delta_pct > 0


def test_TV07_both_zero_yields_nan_pct_and_flat():
    d = compute_diff(_mv("a", syntactic_dead_code=0),
                     _mv("b", syntactic_dead_code=0))
    dead = next(c for c in d.channels if c.short == "dead")
    assert math.isnan(dead.delta_pct)
    assert dead.direction == "FLAT"


def test_TV08_to_dict_replaces_nan_and_inf_with_sentinels():
    d = compute_diff(_mv("a", syntactic_dead_code=0),
                     _mv("b", syntactic_dead_code=3))
    payload = d.to_dict()
    dead = next(c for c in payload["channels"] if c["short"] == "dead")
    assert dead["delta_pct"] == "inf"

    d2 = compute_diff(_mv("a"), _mv("b"))
    payload2 = d2.to_dict()
    h = next(c for c in payload2["channels"] if c["short"] == "H")
    # 10 → 10 yields 0/10 = 0.0 (real float, not NaN)
    assert h["delta_pct"] == 0.0


def test_TV09_n_changed_counts_only_non_flat():
    d = compute_diff(
        _mv("a", hamiltonian=10.0, cyclomatic_complexity=5),
        _mv("b", hamiltonian=15.0, cyclomatic_complexity=5),
    )
    assert d.n_changed == 1
    assert d.n_total >= 9


def test_TV10_missing_channels_on_one_side_skipped_silently():
    mv_a = _mv("a")
    mv_b = _mv("b")
    # Knock out a primary channel on side B.
    object.__setattr__(mv_b, "halstead_bugs", None)
    d = compute_diff(mv_a, mv_b)
    shorts = {c.short for c in d.channels}
    assert "bugs" not in shorts
    assert "H" in shorts and "CC" in shorts


# ─── compute_diff_by_commits — store-backed (TV11-TV20) ───────────────────────

def test_TV11_resolves_two_existing_commits():
    store = _populated_store()
    d = compute_diff_by_commits(store, "m", "c1", "c5")
    assert d is not None
    h = next(c for c in d.channels if c.short == "H")
    assert h.value_from == pytest.approx(12.0)
    assert h.value_to   == pytest.approx(20.0)


def test_TV12_returns_none_when_from_missing():
    store = _populated_store()
    assert compute_diff_by_commits(store, "m", "ghost", "c2") is None


def test_TV13_returns_none_when_to_missing():
    store = _populated_store()
    assert compute_diff_by_commits(store, "m", "c2", "ghost") is None


def test_TV14_returns_none_for_unknown_module():
    store = _populated_store()
    assert compute_diff_by_commits(store, "nope", "c0", "c1") is None


def test_TV15_identical_commits_yields_all_flat():
    store = _populated_store()
    d = compute_diff_by_commits(store, "m", "c3", "c3")
    assert d is not None
    assert d.n_changed == 0


def test_TV16_reverse_direction_negates_deltas():
    store = _populated_store()
    forward  = compute_diff_by_commits(store, "m", "c1", "c5")
    backward = compute_diff_by_commits(store, "m", "c5", "c1")
    h_fwd = next(c for c in forward.channels  if c.short == "H")
    h_bwd = next(c for c in backward.channels if c.short == "H")
    assert h_fwd.delta_abs == pytest.approx(-h_bwd.delta_abs)


def test_TV17_aps_channel_present_when_persisted():
    # Sprint G fix (C-1): aps_score is computed at insert time from the
    # extended vectors actually attached.  Setting mv.aps_score = 42 on a
    # bare MV used to round-trip; under Sprint G the store recomputes APS
    # via aps_from_metric_vector, which now correctly returns None for an
    # MV with zero extended vectors.  Attach a real SecurityVector so the
    # channel materialises.
    from metrics.extended_vectors import SecurityVector
    store = SnapshotStore(":memory:")
    mv = _mv("c0", ts=10.0)
    object.__setattr__(mv, "security", SecurityVector(sca_vulnerable_deps=1))
    object.__setattr__(mv, "lines_of_code", 100)
    store.insert(mv)
    mv2 = _mv("c1", ts=11.0)
    object.__setattr__(mv2, "security", SecurityVector(sca_vulnerable_deps=4))
    object.__setattr__(mv2, "lines_of_code", 100)
    store.insert(mv2)

    d = compute_diff_by_commits(store, "m", "c0", "c1")
    shorts = {c.short for c in d.channels}
    assert "APS" in shorts
    assert "LOC" in shorts


def test_TV18_serialized_payload_contains_commits_and_channels():
    store = _populated_store()
    d = compute_diff_by_commits(store, "m", "c0", "c4")
    payload = d.to_dict()
    assert payload["commit_from"] == "c0"
    assert payload["commit_to"]   == "c4"
    assert payload["n_total"] >= 9
    assert isinstance(payload["channels"], list)


def test_TV19_module_id_carried_through():
    store = _populated_store()
    d = compute_diff_by_commits(store, "m", "c0", "c1")
    assert d.module_id == "m"


def test_TV20_window_too_small_returns_none_when_commits_outside():
    store = _populated_store(n=8)
    # Window=2 only sees latest two — older commit `c0` falls off.
    d = compute_diff_by_commits(store, "m", "c0", "c7", history_window=2)
    assert d is None


# ─── top_volatile_channels (TV21-TV30) ────────────────────────────────────────

def test_TV21_empty_history_returns_empty_list():
    store = SnapshotStore(":memory:")
    assert top_volatile_channels(store, "ghost") == []


def test_TV22_below_three_samples_returns_empty():
    store = SnapshotStore(":memory:")
    store.insert(_mv("c0", ts=1.0))
    store.insert(_mv("c1", ts=2.0))
    assert top_volatile_channels(store, "m") == []


def test_TV23_returns_descending_by_cv():
    store = _populated_store(n=10)
    rows = top_volatile_channels(store, "m", window=20, top_k=10)
    cvs = [r["cv"] for r in rows]
    assert cvs == sorted(cvs, reverse=True)


def test_TV24_top_k_bound_respected():
    store = _populated_store(n=10)
    rows = top_volatile_channels(store, "m", window=20, top_k=3)
    assert len(rows) <= 3


def test_TV25_constant_channel_excluded_from_ranking():
    store = _populated_store(n=10)
    rows = top_volatile_channels(store, "m", window=20, top_k=10)
    shorts = {r["short"] for r in rows}
    # DSM_d is always 0.5 in the fixture — should be filtered.
    assert "DSM_d" not in shorts


def test_TV26_rows_carry_n_samples():
    store = _populated_store(n=10)
    rows = top_volatile_channels(store, "m", window=20, top_k=5)
    assert all(r["n_samples"] >= 3 for r in rows)


def test_TV27_rows_carry_mean_std_cv():
    store = _populated_store(n=10)
    rows = top_volatile_channels(store, "m", window=20, top_k=5)
    for r in rows:
        assert "mean" in r and "std" in r and "cv" in r
        assert r["std"] >= 0
        assert r["cv"]  >= 0


def test_TV28_top_k_zero_returns_empty():
    store = _populated_store(n=10)
    assert top_volatile_channels(store, "m", window=20, top_k=0) == []


def test_TV29_deterministic_alpha_tiebreak_on_equal_cv():
    """Two channels with identical CV should sort by channel name asc."""
    store = SnapshotStore(":memory:")
    base = time.time()
    # Three snapshots where ILR and dead have IDENTICAL distributions.
    for i, (ilr, dead) in enumerate([(0.1, 1), (0.3, 3), (0.5, 5)]):
        store.insert(_mv(f"c{i}", ts=base + i,
                         infinite_loop_risk=ilr, syntactic_dead_code=dead))
    rows = top_volatile_channels(store, "m", window=10, top_k=5)
    pair = [r for r in rows if r["short"] in {"ILR", "dead"}]
    assert pair[0]["cv"] == pytest.approx(pair[1]["cv"], rel=1e-9)
    # Tiebreak by channel name alphabetical ascending.
    assert pair[0]["channel"] < pair[1]["channel"]


def test_TV30_end_to_end_via_handle_diff_volatile():
    """Smoke through the API surface."""
    import api.server as srv

    # Reset to known state — also keeps test isolated from neighbours.
    srv._store = SnapshotStore(":memory:")
    base = time.time()
    for i in range(8):
        srv._store.insert(_mv(
            f"c{i}", ts=base + i,
            hamiltonian=10.0 + i * 3,
            infinite_loop_risk=0.1 * i,
        ))
    code, data = srv.handle_diff_volatile("m", window=20, top_k=4)
    assert code == 200
    assert data["module_id"] == "m"
    assert data["n_rows"] >= 1
    assert all("cv" in c for c in data["channels"])
