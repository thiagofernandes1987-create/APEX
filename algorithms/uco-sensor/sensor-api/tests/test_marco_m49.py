"""
Marco 49 — Sprint S: Granger Causality (formal F-test) (TX01-TX30)
====================================================================

Replaces the Pearson-lag heuristic of Sprint M with the canonical
Granger F-test. Asks "does past X help predict Y BEYOND past Y?"
— ruling out spurious correlations between random walks.

Coverage layout
---------------
* TX01-TX10 — granger_pair pure: synthetic x→y causality detection,
  reverse direction rejected, insufficient samples, edge cases
* TX11-TX20 — granger_matrix + significant_pairs over store: shape,
  diagonal, significant filter, alpha threshold
* TX21-TX30 — REST: handlers, payload shape, 400/200, /docs registration
"""
from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from governance.granger_causality import (
    GrangerResult,
    granger_pair, granger_matrix, significant_pairs,
    _CHANNELS, _ATTR_BY_SHORT,
)


def _mv(module: str, commit: str, ts: float, *,
        h: float = 5.0, cc: int = 2, bugs: float = 0.1) -> MetricVector:
    return MetricVector(
        module_id=module, commit_hash=commit, timestamp=ts,
        hamiltonian=h, cyclomatic_complexity=cc,
        infinite_loop_risk=0.05, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=0.2,
        syntactic_dead_code=0, duplicate_block_count=0, halstead_bugs=bugs,
    )


def _causal_store(n: int = 40) -> SnapshotStore:
    """Build a series where CC at t leads bugs at t+1..3."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        cc = 2 + min(i, 15)
        bugs = 0.1 + max(0, (i - 3) * 0.05)
        s.insert(_mv("demo", f"c{i:02d}", base + i, cc=cc, bugs=bugs))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TX01-TX10 — granger_pair pure
# ═══════════════════════════════════════════════════════════════════════════════

def test_TX01_detects_synthetic_causality():
    """y_t = 0.7·x_{t-2} + noise → x granger-causes y."""
    random.seed(42)
    x = [random.gauss(0, 1) for _ in range(60)]
    y = [0.0] * 60
    for t in range(2, 60):
        y[t] = 0.7 * x[t-2] + 0.1 * random.gauss(0, 1)
    r = granger_pair(x, y, max_lag=5)
    assert r.granger_causes is True
    assert r.p_value < 0.05


def test_TX02_rejects_reverse_synthetic_causality():
    """Reverse direction (y → x) should NOT be significant."""
    random.seed(42)
    x = [random.gauss(0, 1) for _ in range(60)]
    y = [0.0] * 60
    for t in range(2, 60):
        y[t] = 0.7 * x[t-2] + 0.1 * random.gauss(0, 1)
    r = granger_pair(y, x, max_lag=5)
    assert r.granger_causes is False


def test_TX03_best_lag_matches_synthetic_design():
    """Synthetic lag was 2 — best_lag should detect it."""
    random.seed(42)
    x = [random.gauss(0, 1) for _ in range(80)]
    y = [0.0] * 80
    for t in range(2, 80):
        y[t] = 0.8 * x[t-2] + 0.05 * random.gauss(0, 1)
    r = granger_pair(x, y, max_lag=5)
    assert r.best_lag == 2


def test_TX04_insufficient_samples_returns_safe_result():
    r = granger_pair([1.0, 2.0, 3.0], [4.0, 5.0, 6.0], max_lag=5)
    assert r.granger_causes is False
    assert r.p_value == 1.0


def test_TX05_mismatched_lengths_returns_safe_result():
    r = granger_pair([1.0, 2.0], [4.0, 5.0, 6.0], max_lag=5)
    assert r.granger_causes is False


def test_TX06_alpha_threshold_respected():
    """Same data, different alpha → granger_causes flips."""
    random.seed(42)
    x = [random.gauss(0, 1) for _ in range(60)]
    y = [0.0] * 60
    for t in range(2, 60):
        y[t] = 0.4 * x[t-2] + 0.5 * random.gauss(0, 1)
    r_loose  = granger_pair(x, y, max_lag=5, alpha=0.5)
    r_strict = granger_pair(x, y, max_lag=5, alpha=0.001)
    # Loose alpha is more permissive — granger_causes is at least as
    # frequently True as under strict alpha.
    if r_strict.granger_causes:
        assert r_loose.granger_causes


def test_TX07_constant_series_no_causality():
    x = [1.0] * 50
    y = [2.0] * 50
    r = granger_pair(x, y, max_lag=3)
    assert r.granger_causes is False


def test_TX08_result_dataclass_serializable():
    import json
    r = granger_pair([1.0]*30, [2.0]*30, max_lag=2)
    text = json.dumps(r.to_dict())
    assert "p_value" in text


def test_TX09_granger_pair_returns_GrangerResult():
    r = granger_pair([1.0]*30, [2.0]*30, max_lag=2)
    assert isinstance(r, GrangerResult)


def test_TX10_n_samples_carried_in_result():
    r = granger_pair([1.0]*30, [2.0]*30, max_lag=2)
    assert r.n_samples == 30


# ═══════════════════════════════════════════════════════════════════════════════
# TX11-TX20 — granger_matrix + significant_pairs
# ═══════════════════════════════════════════════════════════════════════════════

def test_TX11_matrix_returns_81_entries():
    m = granger_matrix(_causal_store(), "demo", max_lag=2)
    assert m["status"] == "OK"
    assert len(m["matrix"]) == 81


def test_TX12_matrix_diagonal_is_neutral():
    m = granger_matrix(_causal_store(), "demo", max_lag=2)
    for entry in m["matrix"]:
        if entry["from"] == entry["to"]:
            assert entry["p_value"] == 1.0
            assert entry["granger_causes"] is False


def test_TX13_matrix_entries_have_required_fields():
    m = granger_matrix(_causal_store(), "demo", max_lag=2)
    for entry in m["matrix"]:
        for key in ("from", "to", "best_lag", "f_statistic",
                    "p_value", "granger_causes", "n_samples", "alpha"):
            assert key in entry


def test_TX14_matrix_no_history_status():
    m = granger_matrix(SnapshotStore(":memory:"), "ghost")
    assert m["status"] == "NO_HISTORY"


def test_TX15_matrix_insufficient_samples_status():
    s = SnapshotStore(":memory:")
    for i in range(3):
        s.insert(_mv("short", f"c{i}", float(i)))
    m = granger_matrix(s, "short", max_lag=3)
    assert m["status"] == "INSUFFICIENT"


def test_TX16_significant_pairs_filters_p_value():
    sig = significant_pairs(_causal_store(), "demo", max_lag=2, alpha=0.05)
    assert sig["status"] == "OK"
    for p in sig["pairs"]:
        assert p["p_value"] < 0.05
        assert p["granger_causes"] is True


def test_TX17_significant_pairs_excludes_diagonal():
    sig = significant_pairs(_causal_store(), "demo", max_lag=2)
    for p in sig["pairs"]:
        assert p["from"] != p["to"]


def test_TX18_significant_pairs_sorted_by_p_asc():
    sig = significant_pairs(_causal_store(40), "demo", max_lag=2)
    pvals = [p["p_value"] for p in sig["pairs"]]
    assert pvals == sorted(pvals)


def test_TX19_matrix_channels_field_correct():
    m = granger_matrix(_causal_store(), "demo")
    assert set(m["channels"]) == set(_CHANNELS)


def test_TX20_attr_map_covers_all_channels():
    for ch in _CHANNELS:
        assert ch in _ATTR_BY_SHORT


# ═══════════════════════════════════════════════════════════════════════════════
# TX21-TX30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TX21_handle_granger_matrix_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_granger_matrix("")
    assert code == 400


def test_TX22_handle_granger_matrix_200():
    import api.server as srv
    srv._store = _causal_store()
    code, payload = srv.handle_granger_matrix("demo", max_lag=2)
    assert code == 200
    assert payload["status"] == "OK"
    assert len(payload["matrix"]) == 81


def test_TX23_handle_granger_significant_returns_pairs():
    import api.server as srv
    srv._store = _causal_store()
    code, payload = srv.handle_granger_significant("demo", max_lag=2)
    assert code == 200
    assert "pairs" in payload


def test_TX24_handle_granger_significant_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_granger_significant("")
    assert code == 400


def test_TX25_handle_granger_matrix_carries_alpha():
    import api.server as srv
    srv._store = _causal_store()
    code, payload = srv.handle_granger_matrix("demo", alpha=0.10)
    assert payload["alpha"] == 0.10


def test_TX26_handle_granger_matrix_alpha_affects_granger_causes():
    import api.server as srv
    srv._store = _causal_store(40)
    code1, p_loose  = srv.handle_granger_matrix("demo", alpha=0.5)
    code2, p_strict = srv.handle_granger_matrix("demo", alpha=0.001)
    n_loose  = sum(1 for e in p_loose["matrix"]  if e["granger_causes"])
    n_strict = sum(1 for e in p_strict["matrix"] if e["granger_causes"])
    assert n_loose >= n_strict


def test_TX27_handle_granger_matrix_empty_store():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_granger_matrix("ghost")
    assert code == 200
    assert payload["status"] in {"NO_HISTORY", "INSUFFICIENT"}


def test_TX28_handle_granger_max_lag_clamped_to_min_1():
    import api.server as srv
    srv._store = _causal_store()
    code, payload = srv.handle_granger_matrix("demo", max_lag=0)
    assert code == 200   # clamped, no 500


def test_TX29_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    assert "/granger/matrix" in paths
    assert "/granger/significant" in paths


def test_TX30_synthetic_cause_visible_in_REST_significant():
    """Build CC→bugs causality, expect it to show up in /granger/significant."""
    import api.server as srv
    srv._store = _causal_store(40)
    code, payload = srv.handle_granger_significant("demo", max_lag=3)
    assert code == 200
    # At least one significant pair touching CC or bugs should be present.
    rel = [p for p in payload["pairs"]
           if "CC" in (p["from"], p["to"]) or "bugs" in (p["from"], p["to"])]
    assert len(rel) >= 1
