"""
Marco 46 — Sprint O: Spectral Fingerprint Index + Similarity (TR01-TR30)
=========================================================================

Builds an in-memory KD-style index of every module's 5-channel spectral
fingerprint (Sprint F) and exposes nearest-neighbor lookup via REST.

Coverage layout
---------------
* TR01-TR10 — Fingerprint dataclass + build_index pure
* TR11-TR20 — FingerprintIndex find_similar + cluster_distances
* TR21-TR30 — REST: /similar, /fingerprint/index, /fingerprint/clusters
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
from governance.fingerprint_index import (
    Fingerprint, FingerprintIndex, SimilarityHit,
    build_index, _euclidean, _cosine, _manhattan,
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
    """Four modules with distinct spectral signatures."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod, fn in [
        ("sin6",  lambda i: int(5 + 10 * math.sin(2*math.pi*i/6))),
        ("sin6b", lambda i: int(5 + 10 * math.sin(2*math.pi*i/6 + 0.5))),
        ("noise", lambda i: int(5 + ((i*131) % 17))),
        ("drift", lambda i: int(5 + i)),
    ]:
        for i in range(20):
            s.insert(_mv(mod, f"c{i:02d}", base+i, deps=fn(i)))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TR01-TR10 — Fingerprint + build_index
# ═══════════════════════════════════════════════════════════════════════════════

def test_TR01_fingerprint_to_vector_has_five_dims():
    fp = Fingerprint("m", 0.1, 0.2, 0.3, 0.5, 4.0, 20)
    assert len(fp.to_vector()) == 5


def test_TR02_fingerprint_to_dict_serializable():
    import json
    fp = Fingerprint("m", 0.1, 0.2, 0.3, 0.5, 4.0, 20)
    text = json.dumps(fp.to_dict())
    assert "spectral_entropy" in text


def test_TR03_build_index_empty_store_returns_empty_index():
    idx = build_index(SnapshotStore(":memory:"))
    assert idx.size == 0


def test_TR04_build_index_skips_modules_without_fingerprint():
    s = SnapshotStore(":memory:")
    # Module with 3 samples — too few for fingerprint (needs 8+).
    base = time.time()
    for i in range(3):
        s.insert(_mv("short", f"c{i}", base + i))
    idx = build_index(s)
    assert "short" not in idx.fingerprints


def test_TR05_build_index_includes_well_sampled_modules():
    idx = build_index(_multi_signature_store())
    assert idx.size == 4
    assert set(idx.fingerprints.keys()) == {"sin6", "sin6b", "noise", "drift"}


def test_TR06_fingerprint_carries_n_samples():
    idx = build_index(_multi_signature_store())
    assert all(fp.n_samples >= 8 for fp in idx.fingerprints.values())


def test_TR07_fingerprint_band_fractions_in_unit_interval():
    idx = build_index(_multi_signature_store())
    for fp in idx.fingerprints.values():
        assert 0.0 <= fp.band_low_fraction  <= 1.0
        assert 0.0 <= fp.band_mid_fraction  <= 1.0
        assert 0.0 <= fp.band_high_fraction <= 1.0


def test_TR08_fingerprint_entropy_in_unit_interval():
    idx = build_index(_multi_signature_store())
    for fp in idx.fingerprints.values():
        assert 0.0 <= fp.spectral_entropy <= 1.0


def test_TR09_build_index_defensive_on_broken_store():
    class Broken:
        def list_modules(self):
            raise RuntimeError("boom")
    idx = build_index(Broken())
    assert idx.size == 0


def test_TR10_fingerprint_handles_zero_cycle_length_in_vector():
    fp = Fingerprint("m", 0.3, 0.3, 0.3, 0.5, 0.0, 10)
    v = fp.to_vector()
    assert v[4] == 0.0   # cycle_norm fallback


# ═══════════════════════════════════════════════════════════════════════════════
# TR11-TR20 — find_similar + cluster_distances
# ═══════════════════════════════════════════════════════════════════════════════

def test_TR11_find_similar_returns_k_hits():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=2)
    assert len(hits) == 2


def test_TR12_find_similar_excludes_anchor_module():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=10)
    for h in hits:
        assert h.module_id != "sin6"


def test_TR13_find_similar_sorted_ascending_distance():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=10)
    dists = [h.distance for h in hits]
    assert dists == sorted(dists)


def test_TR14_find_similar_unknown_module_returns_empty():
    idx = build_index(_multi_signature_store())
    assert idx.find_similar("ghost") == []


def test_TR15_find_similar_sin6_to_sin6b_is_closest():
    """sin6 and sin6b differ only by phase — should be each other's nearest."""
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=1)
    assert hits[0].module_id == "sin6b"


def test_TR16_find_similar_cosine_metric_works():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=2, metric="cosine")
    assert len(hits) == 2
    assert all(0.0 <= h.distance <= 2.0 for h in hits)


def test_TR17_find_similar_manhattan_metric_works():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=2, metric="manhattan")
    assert len(hits) == 2


def test_TR18_find_similar_unknown_metric_falls_back_to_euclidean():
    idx = build_index(_multi_signature_store())
    hits = idx.find_similar("sin6", k=2, metric="mystery")
    assert len(hits) == 2


def test_TR19_cluster_distances_returns_lower_triangular():
    idx = build_index(_multi_signature_store())
    pairs = idx.cluster_distances()
    n = idx.size
    expected = n * (n - 1) // 2
    assert len(pairs) == expected


def test_TR20_distance_helpers_sanity():
    a = [1.0, 0.0, 0.0, 0.0, 0.0]
    b = [0.0, 1.0, 0.0, 0.0, 0.0]
    assert _euclidean(a, b) == pytest.approx(math.sqrt(2))
    assert _manhattan(a, b) == pytest.approx(2.0)
    # Cosine of orthogonal unit vectors = 1.0 (max distance).
    assert _cosine(a, b)    == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# TR21-TR30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TR21_handle_similar_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_similar("")
    assert code == 400


def test_TR22_handle_similar_404_unknown_module():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_similar("ghost")
    assert code == 404
    assert "index_size" in payload


def test_TR23_handle_similar_200_returns_hits():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_similar("sin6", k=2)
    assert code == 200
    assert payload["k"] == 2
    assert payload["index_size"] == 4
    assert len(payload["hits"]) == 2


def test_TR24_handle_similar_anchor_payload_present():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_similar("sin6")
    assert "anchor" in payload
    assert payload["anchor"]["module_id"] == "sin6"


def test_TR25_handle_similar_metric_propagated():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_similar("sin6", metric="cosine")
    assert payload["metric"] == "cosine"


def test_TR26_handle_fingerprint_index_200():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_fingerprint_index()
    assert code == 200
    assert payload["index_size"] == 4
    assert len(payload["fingerprints"]) == 4


def test_TR27_handle_fingerprint_index_empty_store():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_fingerprint_index()
    assert code == 200
    assert payload["index_size"] == 0


def test_TR28_handle_fingerprint_clusters_returns_pairs():
    import api.server as srv
    srv._store = _multi_signature_store()
    code, payload = srv.handle_fingerprint_clusters()
    assert code == 200
    assert payload["n_pairs"] == 4 * 3 // 2   # lower-triangular


def test_TR29_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    for p in ("/similar", "/fingerprint/index", "/fingerprint/clusters"):
        assert p in paths


def test_TR30_handle_similar_window_clamped_to_min_8():
    import api.server as srv
    srv._store = _multi_signature_store()
    # window=1 → clamped to 8 internally; should not crash
    code, payload = srv.handle_similar("sin6", window=1)
    assert code in (200, 404)
