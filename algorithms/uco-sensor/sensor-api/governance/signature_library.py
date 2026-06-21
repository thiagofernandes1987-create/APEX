"""
Sprint P — Signature Library: DBSCAN over Fingerprints + Persistence  (v3.4.1)
================================================================================
Runs DBSCAN over the 5-dim spectral fingerprints (Sprint O) and
**persists** each cluster as a discovered signature.  Re-running
``discover_signatures()`` later **bumps the occurrence_count** of
existing signatures (identified by a stable hash of their centroid) and
inserts only genuinely new ones.

Why this matters
----------------
Pre-Sprint-P the DBSCANDiscovery from frequency-engine produced clusters
but the results were lost the instant the request returned.  No memory,
no evolution.  Now the sensor LEARNS: every scan of a new repo
contributes to a growing library of behavioral patterns.

Public API
----------
- ``discover_signatures(store, *, window=100, eps=0.25, min_samples=2)``
  → ``Dict`` with counts (new, bumped, total) and the signatures touched
- ``library_status(store)`` → ``Dict`` with size + most-frequent

Algorithm
---------
1. ``build_index(store)`` → fingerprints 5-dim per module (Sprint O).
2. DBSCAN (pure numpy / Python) over the 5-dim space with Euclidean
   distance.  Defaults eps=0.25, min_samples=2 are calibrated for the
   fingerprint scale [0..1].
3. For each cluster: centroid = mean, diameter = max pairwise distance.
4. signature_id = MD5(rounded centroid) — stable across runs.
5. Persist via ``store.store_signature`` (Sprint P storage layer).
"""
from __future__ import annotations

import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Set, Tuple

_log = logging.getLogger("uco-sensor.signatures")


# ─── Tiny DBSCAN (pure Python, no scipy) ─────────────────────────────────────

def _euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _dbscan(
    points: List[List[float]],
    eps: float,
    min_samples: int,
) -> List[int]:
    """
    Return cluster label per point.  -1 = noise.  Clusters are 0-indexed.

    Standard DBSCAN — region query is naive O(n), fine for the sensor's
    scale (modules typically ≤ 10³ even in monorepos).
    """
    n = len(points)
    labels = [-2] * n      # -2 = unvisited, -1 = noise
    cluster_id = 0

    def region_query(idx: int) -> List[int]:
        return [j for j in range(n) if _euclidean(points[idx], points[j]) <= eps]

    for i in range(n):
        if labels[i] != -2:
            continue
        neighbors = region_query(i)
        if len(neighbors) < min_samples:
            labels[i] = -1
            continue
        labels[i] = cluster_id
        seeds = list(neighbors)
        k = 0
        while k < len(seeds):
            q = seeds[k]
            if labels[q] == -1:
                labels[q] = cluster_id
            if labels[q] == -2:
                labels[q] = cluster_id
                q_neigh = region_query(q)
                if len(q_neigh) >= min_samples:
                    for new_n in q_neigh:
                        if new_n not in seeds:
                            seeds.append(new_n)
            k += 1
        cluster_id += 1

    return labels


# ─── Centroid + identity ─────────────────────────────────────────────────────

def _centroid(points: List[List[float]]) -> List[float]:
    if not points:
        return []
    dim = len(points[0])
    return [sum(p[d] for p in points) / len(points) for d in range(dim)]


def _diameter(points: List[List[float]]) -> float:
    """Max pairwise distance — quick measure of cluster tightness."""
    n = len(points)
    if n < 2:
        return 0.0
    best = 0.0
    for i in range(n):
        for j in range(i + 1, n):
            d = _euclidean(points[i], points[j])
            if d > best:
                best = d
    return best


def signature_id_from_centroid(centroid: List[float], decimals: int = 3) -> str:
    """
    Stable hash of a rounded centroid — two DBSCAN runs on equivalent
    repos produce the same signature_id.  MD5 is fine here (we want a
    short, deterministic identifier; not a security primitive).
    """
    rounded = [round(float(x), decimals) for x in centroid]
    payload = ",".join(f"{x:+.4f}" for x in rounded).encode("utf-8")
    digest = hashlib.md5(payload).hexdigest()[:16]
    return f"sig_{digest}"


# ─── Public API ──────────────────────────────────────────────────────────────

def discover_signatures(
    store: Any,
    *,
    window: int = 100,
    eps: float = 0.25,
    min_samples: int = 2,
) -> Dict[str, Any]:
    """
    Discover new behavioral signatures from the spectral fingerprint
    space and persist them.  Re-running on a re-evolved repo BUMPS
    existing signatures instead of duplicating.

    Returns a summary::
        {
          "status":          "OK" | "EMPTY",
          "n_modules":       int,
          "n_clusters":      int,
          "n_new":           int,
          "n_bumped":        int,
          "n_noise":         int,
          "library_size":    int,
          "signatures":      [ {signature_id, n_members, diameter,
                                 occurrence_count, members[], created_at, …} ],
        }
    """
    try:
        from governance.fingerprint_index import build_index
        idx = build_index(store, window=window)
    except Exception as exc:
        return {"status": "ERROR", "error": f"fingerprint index: {exc}"}

    if idx.size < min_samples:
        return {
            "status":       "EMPTY",
            "n_modules":    idx.size,
            "n_clusters":   0, "n_new": 0, "n_bumped": 0, "n_noise": 0,
            "library_size": _safe_library_size(store),
            "signatures":   [],
        }

    module_ids = list(idx.fingerprints.keys())
    vectors    = [idx.fingerprints[mid].to_vector() for mid in module_ids]

    labels = _dbscan(vectors, eps=eps, min_samples=min_samples)

    # Group members per cluster
    clusters: Dict[int, List[int]] = {}
    n_noise = 0
    for i, lbl in enumerate(labels):
        if lbl == -1:
            n_noise += 1
            continue
        clusters.setdefault(lbl, []).append(i)

    persisted: List[Dict[str, Any]] = []
    n_new = 0
    n_bumped = 0

    for lbl, indices in clusters.items():
        cluster_points = [vectors[i] for i in indices]
        cluster_members = [module_ids[i] for i in indices]
        centroid = _centroid(cluster_points)
        diameter = _diameter(cluster_points)
        sig_id   = signature_id_from_centroid(centroid)

        existed = store.get_signature(sig_id) is not None if hasattr(store, "get_signature") else False
        row = store.store_signature(
            sig_id, centroid, cluster_members, diameter,
            label=f"cluster_{lbl}",
        )
        if existed:
            n_bumped += 1
        else:
            n_new += 1
        persisted.append(row)

    return {
        "status":       "OK",
        "n_modules":    idx.size,
        "n_clusters":   len(clusters),
        "n_new":        n_new,
        "n_bumped":     n_bumped,
        "n_noise":      n_noise,
        "library_size": _safe_library_size(store),
        "signatures":   persisted,
    }


def library_status(store: Any) -> Dict[str, Any]:
    """Summary of the persisted signature library."""
    try:
        all_sigs = store.list_signatures(limit=10**6)
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc), "size": 0}

    if not all_sigs:
        return {
            "status":           "OK",
            "size":             0,
            "most_frequent":    [],
            "total_occurrences": 0,
        }

    top = sorted(all_sigs, key=lambda s: -s["occurrence_count"])[:5]
    return {
        "status":           "OK",
        "size":             len(all_sigs),
        "most_frequent":    [
            {"signature_id": s["signature_id"],
             "occurrence_count": s["occurrence_count"],
             "n_members": s["n_members"],
             "label": s["label"]}
            for s in top
        ],
        "total_occurrences": sum(s["occurrence_count"] for s in all_sigs),
    }


def _safe_library_size(store: Any) -> int:
    try:
        return int(store.signature_count())
    except Exception:
        return 0
