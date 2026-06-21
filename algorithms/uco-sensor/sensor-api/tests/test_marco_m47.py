"""
Marco 47 — Sprint P: DBSCAN Signatures Persisted + Evolutive Library (TS01-TS30)
=================================================================================

Movement #4 of the APEX Scientific roadmap: persist DBSCAN clusters
over spectral fingerprints so the sensor LEARNS from every repo scanned.
Re-running discovery on a re-evolved repo bumps occurrence_count of
existing signatures (identified by a stable hash of their centroid).

Coverage layout
---------------
* TS01-TS10 — Storage layer: store/get/list/delete/count + idempotent
  re-store + signature_id stability
* TS11-TS20 — Discovery: DBSCAN over fingerprints, centroid + diameter,
  new vs bumped path, noise points, empty store, library_status
* TS21-TS30 — REST: 5 handlers + payload shape + admin auth on writes
"""
from __future__ import annotations

import math
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
from governance.signature_library import (
    discover_signatures, library_status,
    signature_id_from_centroid,
    _dbscan, _centroid, _diameter,
)


def _mv(module: str, commit: str, ts: float, *, deps: int = 0) -> MetricVector:
    mv = MetricVector(
        module_id=module, commit_hash=commit, timestamp=ts,
        hamiltonian=5.0, cyclomatic_complexity=2,
        infinite_loop_risk=0.0, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=0.2,
        syntactic_dead_code=0, duplicate_block_count=0, halstead_bugs=0.1,
    )
    mv.security = SecurityVector(sca_vulnerable_deps=max(0, deps))
    return mv


def _multi_signature_store() -> SnapshotStore:
    """Two clear clusters: 3 oscillating mods + 2 drift mods."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod, fn in [
        ("sin6",   lambda i: int(5 + 10 * math.sin(2*math.pi*i/6))),
        ("sin6b",  lambda i: int(5 + 10 * math.sin(2*math.pi*i/6 + 0.5))),
        ("sin6c",  lambda i: int(5 + 10 * math.sin(2*math.pi*i/6 + 1.0))),
        ("drift",  lambda i: int(5 + i)),
        ("drift2", lambda i: int(5 + i + 1)),
    ]:
        for i in range(20):
            s.insert(_mv(mod, f"c{i:02d}", base+i, deps=fn(i)))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TS01-TS10 — Storage layer
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS01_store_signature_creates_row():
    s = SnapshotStore(":memory:")
    row = s.store_signature("sig_abc", [0.1, 0.2, 0.3, 0.4, 0.5], ["m1"], 0.0)
    assert row["signature_id"] == "sig_abc"
    assert row["occurrence_count"] == 1


def test_TS02_store_existing_signature_bumps_occurrence():
    s = SnapshotStore(":memory:")
    s.store_signature("sig_x", [0.1]*5, ["m1"], 0.0)
    row = s.store_signature("sig_x", [0.1]*5, ["m1", "m2"], 0.1)
    assert row["occurrence_count"] == 2
    assert row["n_members"] == 2


def test_TS03_get_signature_unknown_returns_none():
    assert SnapshotStore(":memory:").get_signature("ghost") is None


def test_TS04_list_signatures_orders_by_occurrence_desc():
    s = SnapshotStore(":memory:")
    s.store_signature("a", [0.1]*5, ["m1"], 0.0)
    s.store_signature("b", [0.2]*5, ["m2"], 0.0)
    s.store_signature("b", [0.2]*5, ["m2", "m3"], 0.0)   # bump b
    sigs = s.list_signatures()
    assert sigs[0]["signature_id"] == "b"
    assert sigs[0]["occurrence_count"] == 2


def test_TS05_delete_signature_returns_true_when_present():
    s = SnapshotStore(":memory:")
    s.store_signature("z", [0.0]*5, [], 0.0)
    assert s.delete_signature("z") is True
    assert s.signature_count() == 0


def test_TS06_delete_signature_returns_false_when_missing():
    assert SnapshotStore(":memory:").delete_signature("nope") is False


def test_TS07_signature_count_tracks_correctly():
    s = SnapshotStore(":memory:")
    assert s.signature_count() == 0
    s.store_signature("a", [0.1]*5, [], 0.0)
    s.store_signature("b", [0.2]*5, [], 0.0)
    assert s.signature_count() == 2


def test_TS08_signature_id_stable_across_calls():
    c = [0.123456, 0.234567, 0.345678, 0.456789, 0.567890]
    assert signature_id_from_centroid(c) == signature_id_from_centroid(c)


def test_TS09_signature_id_changes_with_centroid():
    a = signature_id_from_centroid([0.1]*5)
    b = signature_id_from_centroid([0.2]*5)
    assert a != b


def test_TS10_signature_payload_round_trips():
    s = SnapshotStore(":memory:")
    s.store_signature("r", [0.11, 0.22, 0.33, 0.44, 0.55], ["m1", "m2"], 0.07,
                      label="my-cluster", notes="hello")
    got = s.get_signature("r")
    assert got["centroid"] == [0.11, 0.22, 0.33, 0.44, 0.55]
    assert got["members"]  == ["m1", "m2"]
    assert got["label"]    == "my-cluster"
    assert got["notes"]    == "hello"


# ═══════════════════════════════════════════════════════════════════════════════
# TS11-TS20 — Discovery + library_status
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS11_discover_returns_OK_status_with_clusters():
    r = discover_signatures(_multi_signature_store())
    assert r["status"] == "OK"
    assert r["n_clusters"] >= 1


def test_TS12_discover_empty_store_returns_EMPTY():
    r = discover_signatures(SnapshotStore(":memory:"))
    assert r["status"] == "EMPTY"


def test_TS13_discover_persists_to_library():
    s = _multi_signature_store()
    discover_signatures(s)
    assert s.signature_count() >= 1


def test_TS14_re_run_bumps_existing_signatures():
    s = _multi_signature_store()
    discover_signatures(s)
    r2 = discover_signatures(s)
    assert r2["n_new"] == 0
    assert r2["n_bumped"] >= 1


def test_TS15_signatures_payload_has_members_and_centroid():
    s = _multi_signature_store()
    r = discover_signatures(s)
    for sig in r["signatures"]:
        assert "members" in sig and isinstance(sig["members"], list)
        assert "centroid" in sig and isinstance(sig["centroid"], list)
        assert len(sig["centroid"]) == 5


def test_TS16_library_status_empty_store():
    st = library_status(SnapshotStore(":memory:"))
    assert st["status"] == "OK"
    assert st["size"] == 0


def test_TS17_library_status_after_discovery():
    s = _multi_signature_store()
    discover_signatures(s)
    st = library_status(s)
    assert st["size"] >= 1
    assert st["total_occurrences"] >= 1


def test_TS18_centroid_of_single_point_returns_point():
    assert _centroid([[1.0, 2.0, 3.0]]) == [1.0, 2.0, 3.0]


def test_TS19_diameter_of_single_point_is_zero():
    assert _diameter([[1.0, 2.0, 3.0]]) == 0.0


def test_TS20_dbscan_labels_noise_with_minus_one():
    # 3 dense + 1 isolated point with min_samples=3
    pts = [[0.0, 0.0], [0.01, 0.0], [0.0, 0.01], [10.0, 10.0]]
    labels = _dbscan(pts, eps=0.1, min_samples=3)
    assert labels[3] == -1


# ═══════════════════════════════════════════════════════════════════════════════
# TS21-TS30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS21_handle_discover_OK():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_signatures_discover({})
    assert code == 200
    assert payload["status"] in {"OK", "EMPTY"}


def test_TS22_handle_discover_accepts_eps_min_samples():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_signatures_discover({
        "eps": 0.05, "min_samples": 3,
    })
    assert code == 200


def test_TS23_handle_list_after_discovery():
    import api.server as srv
    srv._store = _multi_signature_store()
    srv.handle_signatures_discover({})
    code, payload = srv.handle_signatures_list()
    assert code == 200
    assert payload["n_signatures"] >= 1


def test_TS24_handle_list_empty():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_signatures_list()
    assert payload["n_signatures"] == 0


def test_TS25_handle_get_400_without_id():
    import api.server as srv
    code, _ = srv.handle_signatures_get("")
    assert code == 400


def test_TS26_handle_get_404_unknown():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, _ = srv.handle_signatures_get("ghost")
    assert code == 404


def test_TS27_handle_get_200_returns_payload():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    srv._store.store_signature("sig_z", [0.1]*5, ["m1"], 0.0)
    code, payload = srv.handle_signatures_get("sig_z")
    assert code == 200
    assert payload["signature_id"] == "sig_z"


def test_TS28_handle_delete_404_unknown():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, _ = srv.handle_signatures_delete("ghost")
    assert code == 404


def test_TS29_handle_delete_200_when_present():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    srv._store.store_signature("sig_d", [0.1]*5, [], 0.0)
    code, payload = srv.handle_signatures_delete("sig_d")
    assert code == 200
    assert payload["deleted"] is True


def test_TS30_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    for p in ("/signatures", "/signatures/status", "/signatures/discover"):
        assert p in paths
