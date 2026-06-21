"""
Sprint O — Spectral Fingerprint Index + Similarity Search  (v3.4.0)
====================================================================
Builds an in-memory index of every module's **5-channel spectral
fingerprint** (Sprint F) and exposes nearest-neighbor lookup.

The 5-channel fingerprint
-------------------------
Each module's persisted APS time series is summarised into a compact
signature with five scalars:

    band_low_fraction    ∈ [0, 1]
    band_mid_fraction    ∈ [0, 1]
    band_high_fraction   ∈ [0, 1]
    spectral_entropy     ∈ [0, 1]
    cycle_length         > 0     (period of dominant frequency, in commits)

Two modules with similar fingerprints have **similar quality regimes
over time** — even if their current APS scores differ. This is a
territory no existing analyzer touches.

Public API
----------
- ``build_index(store, *, window=100)`` → ``FingerprintIndex``
- ``FingerprintIndex.find_similar(module_id, k=10, metric='euclidean')``
- ``FingerprintIndex.cluster_distances(metric='euclidean')``

Design contract
---------------
- Index is **stateless and computed on-demand** from the store — no
  separate persistence (keeps the storage layer simple; Sprint U can
  add a cache layer later).
- Modules whose fingerprint computation fails (insufficient samples,
  scipy error) are **omitted** from the index, not represented as
  zero-vectors (which would lie about coverage).
- Distance metrics:
    * ``euclidean`` (default) — straightforward L2 distance
    * ``cosine``    — angular distance, scale-invariant
    * ``manhattan`` — L1 distance, robust to outlier dimensions
- Pure numpy on the hot path; scipy not required.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


_METRICS = ("euclidean", "cosine", "manhattan")


@dataclass
class Fingerprint:
    module_id:            str
    band_low_fraction:    float
    band_mid_fraction:    float
    band_high_fraction:   float
    spectral_entropy:     float
    cycle_length:         float
    n_samples:            int

    def to_vector(self) -> List[float]:
        # Normalise cycle_length to a comparable scale (log dampens its range).
        cycle_norm = math.log1p(self.cycle_length) / 10.0 if self.cycle_length > 0 else 0.0
        return [
            float(self.band_low_fraction or 0.0),
            float(self.band_mid_fraction or 0.0),
            float(self.band_high_fraction or 0.0),
            float(self.spectral_entropy or 0.0),
            cycle_norm,
        ]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":          self.module_id,
            "band_low_fraction":  round(self.band_low_fraction, 4),
            "band_mid_fraction":  round(self.band_mid_fraction, 4),
            "band_high_fraction": round(self.band_high_fraction, 4),
            "spectral_entropy":   round(self.spectral_entropy,  4),
            "cycle_length":       round(self.cycle_length,      2),
            "n_samples":          self.n_samples,
        }


@dataclass
class SimilarityHit:
    module_id: str
    distance:  float
    fingerprint: Fingerprint

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":   self.module_id,
            "distance":    round(self.distance, 4),
            "fingerprint": self.fingerprint.to_dict(),
        }


# ─── Distance helpers ─────────────────────────────────────────────────────────

def _euclidean(a: List[float], b: List[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _manhattan(a: List[float], b: List[float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b))


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na < 1e-12 or nb < 1e-12:
        return 1.0   # max distance — undefined direction → far
    return 1.0 - (dot / (na * nb))


_DIST_FN = {
    "euclidean": _euclidean,
    "cosine":    _cosine,
    "manhattan": _manhattan,
}


# ─── Fingerprint computation ──────────────────────────────────────────────────

def _build_fingerprint(store: Any, module_id: str, window: int) -> Optional[Fingerprint]:
    try:
        from metrics.spectral_aps import aps_fingerprint
        fp = aps_fingerprint(store, module_id, window=window)
    except Exception:
        return None
    if not isinstance(fp, dict) or fp.get("status") != "OK":
        return None
    return Fingerprint(
        module_id=module_id,
        band_low_fraction=float(fp.get("band_low_fraction")  or 0.0),
        band_mid_fraction=float(fp.get("band_mid_fraction")  or 0.0),
        band_high_fraction=float(fp.get("band_high_fraction") or 0.0),
        spectral_entropy=float(fp.get("spectral_entropy")    or 0.0),
        cycle_length=float(fp.get("cycle_length")            or 0.0),
        n_samples=int(fp.get("n_samples")                    or 0),
    )


# ─── Index ────────────────────────────────────────────────────────────────────

@dataclass
class FingerprintIndex:
    """In-memory index of spectral fingerprints — built per request."""
    fingerprints: Dict[str, Fingerprint] = field(default_factory=dict)

    @property
    def size(self) -> int:
        return len(self.fingerprints)

    def find_similar(
        self,
        module_id: str,
        k: int = 10,
        *,
        metric: str = "euclidean",
    ) -> List[SimilarityHit]:
        if module_id not in self.fingerprints:
            return []
        if metric not in _DIST_FN:
            metric = "euclidean"
        anchor = self.fingerprints[module_id].to_vector()
        dist_fn = _DIST_FN[metric]
        hits: List[SimilarityHit] = []
        for other_id, fp in self.fingerprints.items():
            if other_id == module_id:
                continue
            d = dist_fn(anchor, fp.to_vector())
            hits.append(SimilarityHit(other_id, d, fp))
        hits.sort(key=lambda h: (h.distance, h.module_id))
        return hits[: max(0, int(k))]

    def cluster_distances(
        self,
        *,
        metric: str = "euclidean",
    ) -> List[Dict[str, Any]]:
        """All pairwise distances — useful for clustering / heatmap rendering.
        Returns list of {from, to, distance}, lower-triangular only (no
        duplicates, no diagonal).
        """
        if metric not in _DIST_FN:
            metric = "euclidean"
        dist_fn = _DIST_FN[metric]
        out: List[Dict[str, Any]] = []
        ids = sorted(self.fingerprints.keys())
        vecs = {mid: self.fingerprints[mid].to_vector() for mid in ids}
        for i, a in enumerate(ids):
            for b in ids[:i]:
                out.append({
                    "from":     a,
                    "to":       b,
                    "distance": round(dist_fn(vecs[a], vecs[b]), 4),
                })
        return out


def build_index(store: Any, *, window: int = 100) -> FingerprintIndex:
    """Walk every module in *store* and assemble the fingerprint index.

    Modules whose fingerprint computation fails (insufficient samples,
    scipy error) are silently omitted.
    """
    try:
        modules = list(store.list_modules())
    except Exception:
        modules = []

    fps: Dict[str, Fingerprint] = {}
    for module_id in modules:
        fp = _build_fingerprint(store, module_id, window)
        if fp is not None:
            fps[module_id] = fp
    return FingerprintIndex(fingerprints=fps)
