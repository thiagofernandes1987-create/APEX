"""
Marco 44 — Sprint M: Cross-channel Propagation + Causality Matrix (TP01-TP30)
==============================================================================

Exposes the FrequencyEngine's PropagationAnalyzer as a governance signal
AND adds a 9×9 lag-correlation matrix on top of it — the foundation for
Granger-causality work (Sprint S).

Coverage layout
---------------
* TP01-TP10 — compute_propagation + compute_propagation_groups
* TP11-TP20 — compute_causality_matrix + top_causal_pairs (pure)
* TP21-TP30 — REST: 4 handlers + payload shape + edge cases
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
from governance.propagation import (
    compute_propagation, compute_propagation_groups,
    compute_causality_matrix, top_causal_pairs,
    _CHANNELS, _ATTR_BY_SHORT,
)


def _mv(module: str, commit: str, ts: float, *,
        h: float = 5.0, cc: int = 2, bugs: float = 0.1,
        di: float = 0.2, dead: int = 0) -> MetricVector:
    return MetricVector(
        module_id=module, commit_hash=commit, timestamp=ts,
        hamiltonian=h, cyclomatic_complexity=cc,
        infinite_loop_risk=0.05, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=di,
        syntactic_dead_code=dead, duplicate_block_count=0,
        halstead_bugs=bugs,
    )


def _store_with_lead(n: int = 20) -> SnapshotStore:
    """Build a series where CC LEADS bugs (CC rises commits 1..10, bugs rises 4..13)."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        cc = 2 + min(i, 10)
        bugs = 0.1 + max(0, (i - 3) * 0.05)
        s.insert(_mv("lead", f"c{i:02d}", base + i, cc=cc, bugs=bugs))
    return s


def _flat_store(n: int = 20) -> SnapshotStore:
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        s.insert(_mv("flat", f"c{i:02d}", base + i))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TP01-TP10 — propagation fingerprint
# ═══════════════════════════════════════════════════════════════════════════════

def test_TP01_compute_propagation_returns_dict_with_status():
    payload = compute_propagation(_store_with_lead(), "lead")
    assert "status" in payload
    assert payload["status"] in {"OK", "NO_ONSET", "INSUFFICIENT"}


def test_TP02_propagation_includes_pattern_field_when_ok():
    payload = compute_propagation(_store_with_lead(), "lead")
    if payload["status"] == "OK":
        assert "propagation_pattern" in payload


def test_TP03_propagation_no_history_returns_NO_HISTORY():
    payload = compute_propagation(SnapshotStore(":memory:"), "ghost")
    assert payload["status"] == "NO_HISTORY"


def test_TP04_propagation_short_history_returns_INSUFFICIENT_or_OK():
    s = SnapshotStore(":memory:")
    s.insert(_mv("short", "c0", 0.0))
    s.insert(_mv("short", "c1", 1.0))
    payload = compute_propagation(s, "short")
    assert payload["status"] in {"INSUFFICIENT", "NO_ONSET", "OK"}


def test_TP05_propagation_custom_channels_accepted():
    payload = compute_propagation(_store_with_lead(), "lead",
                                  primary_channels=["CC", "bugs"])
    assert payload["status"] != "ERROR"


def test_TP06_propagation_groups_returns_groups_dict():
    payload = compute_propagation_groups(_store_with_lead(), "lead")
    if payload["status"] == "OK":
        assert "groups" in payload
        assert isinstance(payload["groups"], dict)


def test_TP07_propagation_groups_no_history():
    payload = compute_propagation_groups(SnapshotStore(":memory:"), "ghost")
    assert payload["status"] in {"NO_HISTORY", "INSUFFICIENT"}


def test_TP08_propagation_module_id_carried():
    payload = compute_propagation(_store_with_lead(), "lead")
    assert payload["module_id"] == "lead"


def test_TP09_propagation_handles_store_error_gracefully():
    class Broken:
        def get_history(self, *a, **kw):
            raise RuntimeError("DB exploded")
    payload = compute_propagation(Broken(), "x")
    assert payload["status"] == "ERROR"


def test_TP10_propagation_payload_serializable():
    import json
    payload = compute_propagation(_store_with_lead(), "lead")
    text = json.dumps(payload)
    assert "module_id" in text


# ═══════════════════════════════════════════════════════════════════════════════
# TP11-TP20 — causality matrix
# ═══════════════════════════════════════════════════════════════════════════════

def test_TP11_matrix_returns_81_entries():
    m = compute_causality_matrix(_store_with_lead(), "lead", max_lag=5)
    assert m["status"] == "OK"
    assert len(m["matrix"]) == 9 * 9


def test_TP12_matrix_carries_required_fields_per_entry():
    m = compute_causality_matrix(_store_with_lead(), "lead", max_lag=3)
    for entry in m["matrix"]:
        for key in ("from", "to", "best_lag", "correlation", "direction"):
            assert key in entry


def test_TP13_matrix_diagonal_is_one_at_sync():
    m = compute_causality_matrix(_store_with_lead(), "lead", max_lag=3)
    for entry in m["matrix"]:
        if entry["from"] == entry["to"]:
            assert entry["best_lag"] == 0
            assert entry["correlation"] == 1.0
            assert entry["direction"] == "SYNC"


def test_TP14_matrix_lead_correlation_detected():
    """CC was constructed to LEAD bugs by 3 commits — matrix should show it."""
    m = compute_causality_matrix(_store_with_lead(40), "lead", max_lag=5)
    cc_bugs = next(e for e in m["matrix"] if e["from"] == "CC" and e["to"] == "bugs")
    assert cc_bugs["direction"] in {"LEADS", "SYNC"}
    assert abs(cc_bugs["correlation"]) > 0.5


def test_TP15_matrix_insufficient_samples_returns_status():
    s = SnapshotStore(":memory:")
    for i in range(3):
        s.insert(_mv("short", f"c{i}", float(i)))
    m = compute_causality_matrix(s, "short", max_lag=5)
    assert m["status"] == "INSUFFICIENT"


def test_TP16_matrix_no_history_returns_status():
    m = compute_causality_matrix(SnapshotStore(":memory:"), "ghost")
    assert m["status"] == "NO_HISTORY"


def test_TP17_matrix_channels_field_lists_all_nine():
    m = compute_causality_matrix(_store_with_lead(), "lead")
    assert set(m["channels"]) == set(_CHANNELS)
    assert len(m["channels"]) == 9


def test_TP18_matrix_handles_store_error_gracefully():
    class Broken:
        def get_history(self, *a, **kw):
            raise RuntimeError("boom")
    m = compute_causality_matrix(Broken(), "x")
    assert m["status"] == "ERROR"


def test_TP19_top_causal_pairs_top_k_bound():
    top = top_causal_pairs(_store_with_lead(), "lead", top_k=3)
    assert len(top["pairs"]) <= 3


def test_TP20_top_causal_pairs_excludes_diagonal():
    top = top_causal_pairs(_store_with_lead(), "lead", top_k=20)
    for p in top["pairs"]:
        assert p["from"] != p["to"]


# ═══════════════════════════════════════════════════════════════════════════════
# TP21-TP30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TP21_handle_propagation_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_propagation("")
    assert code == 400


def test_TP22_handle_propagation_200_with_data():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_propagation("lead")
    assert code == 200
    assert "status" in payload


def test_TP23_handle_propagation_groups_returns_groups():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_propagation_groups("lead")
    assert code == 200
    if payload["status"] == "OK":
        assert "groups" in payload


def test_TP24_handle_causality_matrix_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_causality_matrix("")
    assert code == 400


def test_TP25_handle_causality_matrix_200_with_data():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_causality_matrix("lead", max_lag=3)
    assert code == 200
    assert payload["status"] == "OK"
    assert len(payload["matrix"]) == 81


def test_TP26_handle_causality_top_returns_pairs():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_causality_top("lead", top_k=5)
    assert code == 200
    assert "pairs" in payload


def test_TP27_handle_causality_top_top_k_bound():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_causality_top("lead", top_k=4)
    assert len(payload["pairs"]) <= 4


def test_TP28_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    for p in ("/propagation", "/propagation/groups",
              "/causality/matrix", "/causality/top"):
        assert p in paths


def test_TP29_causality_matrix_max_lag_clamped_to_zero_floor():
    import api.server as srv
    srv._store = _store_with_lead()
    code, payload = srv.handle_causality_matrix("lead", max_lag=-1)
    assert code == 200   # clamped, no 500


def test_TP30_attr_map_covers_all_channels():
    """Pin: the channel ↔ attribute map must cover every short name."""
    for ch in _CHANNELS:
        assert ch in _ATTR_BY_SHORT
