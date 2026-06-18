"""
Sprint B — Repo-level meta-score + APS outliers  (v3.2.6)
==========================================================
Aggregates the per-module persisted APS (LEAP 2) into one number per
repository at the current snapshot, plus a Z-score outlier helper that
flags modules whose APS is k σ below the repo mean.

Why this is now possible
------------------------
Before LEAP 1+2 there was no per-module APS to aggregate; the score had
to be recomputed every REST call.  With APS persisted, the repo-level
view is a pure read.

Public API
----------
    compute_repo_meta_score(store, window=100)             -> RepoMetaScore
    compute_aps_outliers(store, window=100, k=2.0)         -> List[APSOutlier]
    repo_meta_score_history(store, window=50, step=1)      -> List[Dict]

Meta-score formula
------------------
    raw_score      = weighted_mean(aps_i, weight=loc_i)
    penalty_red    = 5 × count(RED compound-alert modules from Sprint A)
    meta_score     = max(0, min(100, raw_score − penalty_red))

The penalty connects Sprint A's compound signal to a single CI-actionable
number: any RED module drags the repo health down even if its APS alone
wouldn't move the weighted mean much.

Rating ladder (matches the APS rating):
    A ≥ 90,  B 80-89,  C 60-79,  D 40-59,  E < 40
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class RepoMetaScore:
    score:           Optional[float]      # final number ∈ [0, 100] or None when UNKNOWN
    rating:          str                  # A-E or "UNKNOWN" (insufficient data)
    n_modules:       int                  # total in store
    n_modules_valid: int                  # with non-null APS
    raw_score:       Optional[float]      # weighted mean before RED penalty
    weighted_aps:    Optional[float]      # same as raw_score (LOC-weighted)
    mean_aps:        Optional[float]      # unweighted arithmetic mean
    median_aps:      Optional[float]
    penalty_red:     int                  # weighted RED count subtracted
    n_red:           int                  # count of RED modules (Sprint A)
    n_amber:         int

    def to_dict(self) -> Dict[str, Any]:
        def _r(v: Optional[float]) -> Optional[float]:
            return None if v is None else round(v, 2)
        return {
            "score":           _r(self.score),
            "rating":          self.rating,
            "n_modules":       self.n_modules,
            "n_modules_valid": self.n_modules_valid,
            "raw_score":       _r(self.raw_score),
            "weighted_aps":    _r(self.weighted_aps),
            "mean_aps":        _r(self.mean_aps),
            "median_aps":      _r(self.median_aps),
            "penalty_red":     self.penalty_red,
            "n_red":           self.n_red,
            "n_amber":         self.n_amber,
        }


@dataclass
class APSOutlier:
    module_id:   str
    aps:         float
    z_score:     float
    threshold:   float       # − k (the σ multiplier the user requested, negated)
    deviation:   float       # aps − mean_aps (how many APS points below avg)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "aps":       round(self.aps, 2),
            "z_score":   round(self.z_score, 3),
            "threshold": round(self.threshold, 3),
            "deviation": round(self.deviation, 2),
        }


# ─── Rating helper ────────────────────────────────────────────────────────────

def _rate(score: Optional[float]) -> str:
    """A-E ladder; UNKNOWN when score is None (insufficient data).

    Sprint G fix (C-1): UNKNOWN is a hard fail for downstream quality
    gates — it must NOT be treated as 'A' or as 'pass'.
    """
    if score is None:
        return "UNKNOWN"
    if score >= 90.0: return "A"
    if score >= 80.0: return "B"
    if score >= 60.0: return "C"
    if score >= 40.0: return "D"
    return "E"


# ─── Latest-snapshot collector ────────────────────────────────────────────────

def _latest_aps_per_module(store: Any, window: int) -> List[Dict[str, Any]]:
    """
    Return ``[{module_id, aps, loc}]`` taking the most-recent persisted
    APS per module.  Modules with no APS samples are omitted.
    """
    out: List[Dict[str, Any]] = []
    for module_id in store.list_modules():
        hist = store.get_aps_history(module_id, window=window)
        if not hist:
            continue
        latest_aps = next(
            (aps for _, _, aps in reversed(hist) if aps is not None), None,
        )
        if latest_aps is None:
            continue
        full_hist = store.get_history(module_id, window=1)
        loc = int(getattr(full_hist[-1], "lines_of_code", 0)) if full_hist else 0
        out.append({"module_id": module_id, "aps": float(latest_aps),
                    "loc": max(0, loc)})
    return out


# ─── Compound-alert tier counters (reuse Sprint A) ───────────────────────────

def _count_red_amber(store: Any, window: int) -> Dict[str, int]:
    """Run Sprint A's compound alert per module and count RED / AMBER."""
    try:
        from governance.compound_alert import compute_compound_alert
    except Exception:
        return {"RED": 0, "AMBER": 0}
    counts = {"RED": 0, "AMBER": 0}
    for module_id in store.list_modules():
        try:
            alert = compute_compound_alert(store, module_id, window=window)
        except Exception:
            continue
        if alert.tier in counts:
            counts[alert.tier] += 1
    return counts


# ─── Public functions ─────────────────────────────────────────────────────────

def compute_repo_meta_score(store: Any, window: int = 100) -> RepoMetaScore:
    """
    Compute the single repo-level health number from the latest APS of every
    module the store knows about.

    LOC weighting: a module's contribution to the weighted_aps is proportional
    to its size.  Modules with LOC=0 fall back to weight=1 so they aren't
    silently dropped.

    RED penalty: each Sprint-A RED module subtracts 5 points from the raw
    score (bounded to [0, 100]).  AMBER modules are not penalised — they are
    monitored, not blocked.
    """
    snapshots = _latest_aps_per_module(store, window)
    n_modules = len(list(store.list_modules()))

    if not snapshots:
        # Empty repo OR no APS samples yet anywhere.
        # Sprint G fix (C-1): UNKNOWN, NOT 'A'. Quality gates must NOT pass on
        # absence of evidence — a freshly cloned repo or one whose scanner
        # crashed used to score 100/A under the old code, silently approving
        # everything downstream.
        return RepoMetaScore(
            score=None, rating="UNKNOWN",
            n_modules=n_modules, n_modules_valid=0,
            raw_score=None, weighted_aps=None,
            mean_aps=None, median_aps=None,
            penalty_red=0, n_red=0, n_amber=0,
        )

    apses = [s["aps"] for s in snapshots]
    weights = [max(1, s["loc"]) for s in snapshots]
    total_weight = sum(weights)
    weighted = sum(a * w for a, w in zip(apses, weights)) / total_weight
    mean = sum(apses) / len(apses)
    sorted_apses = sorted(apses)
    mid = len(sorted_apses) // 2
    median = (sorted_apses[mid] if len(sorted_apses) % 2
              else (sorted_apses[mid - 1] + sorted_apses[mid]) / 2)

    tier_counts = _count_red_amber(store, window)
    n_red = tier_counts["RED"]
    n_amber = tier_counts["AMBER"]
    penalty = 5 * n_red
    raw = weighted
    score = max(0.0, min(100.0, raw - penalty))

    return RepoMetaScore(
        score=round(score, 2), rating=_rate(score),
        n_modules=n_modules, n_modules_valid=len(snapshots),
        raw_score=round(raw, 2), weighted_aps=round(weighted, 2),
        mean_aps=round(mean, 2), median_aps=round(median, 2),
        penalty_red=penalty, n_red=n_red, n_amber=n_amber,
    )


def compute_aps_outliers(
    store: Any, window: int = 100, k: float = 2.0,
) -> List[APSOutlier]:
    """
    Flag modules whose latest APS is more than *k* standard deviations BELOW
    the repo mean.  Modules above the mean are never flagged — outliers here
    are the bad-news kind (low APS = many anti-patterns).

    Special cases:
    - Fewer than 3 modules with non-null APS → returns []
    - All modules identical (σ = 0) → returns []
    - k ≤ 0 → returns []
    """
    if k <= 0:
        return []

    snapshots = _latest_aps_per_module(store, window)
    if len(snapshots) < 3:
        return []

    apses = [s["aps"] for s in snapshots]
    n = len(apses)
    mean = sum(apses) / n
    variance = sum((a - mean) ** 2 for a in apses) / n
    sd = math.sqrt(variance)
    if sd == 0:
        return []

    threshold = -k
    out: List[APSOutlier] = []
    for s in snapshots:
        z = (s["aps"] - mean) / sd
        if z <= threshold:
            out.append(APSOutlier(
                module_id=s["module_id"],
                aps=s["aps"], z_score=z, threshold=threshold,
                deviation=s["aps"] - mean,
            ))
    out.sort(key=lambda o: o.z_score)  # worst (most negative) first
    return out


def repo_meta_score_history(
    store: Any, window: int = 50, step: int = 1,
) -> List[Dict[str, Any]]:
    """
    Reconstruct a time-series of the repo meta-score by walking the union of
    all commit timestamps and computing the LOC-weighted APS using each
    module's most-recent persisted APS at-or-before that timestamp.

    Parameters
    ----------
    window : history window passed to each module's get_aps_history (per module)
    step   : downsample factor — take every k-th unique timestamp.  ``step=1``
             keeps every point; ``step=10`` keeps every 10th — useful for
             large repos to keep response size manageable.

    Returns
    -------
    List of ``{timestamp, score, n_modules_valid}`` ordered ASC.  RED-penalty
    is intentionally NOT applied here — historical Sprint-A tiers would need
    full per-snapshot replay (expensive); this endpoint reflects the raw
    weighted APS view of the repo over time.
    """
    if step < 1:
        step = 1

    modules = list(store.list_modules())
    series: Dict[str, List[Dict[str, Any]]] = {}
    all_ts: set = set()
    for m in modules:
        hist = store.get_aps_history(m, window=window)
        full = store.get_history(m, window=window)
        loc_map = {h.commit_hash: int(getattr(h, "lines_of_code", 0) or 0)
                   for h in full}
        valid = [
            {"ts": ts, "aps": aps, "loc": max(1, loc_map.get(c, 0))}
            for c, ts, aps in hist if aps is not None
        ]
        if valid:
            series[m] = valid
            all_ts.update(s["ts"] for s in valid)

    if not all_ts:
        return []

    ts_sorted = sorted(all_ts)[::step]
    out: List[Dict[str, Any]] = []
    for ts in ts_sorted:
        contributions: List[float] = []
        weights: List[int] = []
        for m, samples in series.items():
            # latest sample at or before ts
            latest = None
            for s in samples:
                if s["ts"] <= ts:
                    latest = s
                else:
                    break
            if latest is not None:
                contributions.append(latest["aps"])
                weights.append(latest["loc"])
        if not contributions:
            continue
        total = sum(weights)
        weighted = sum(a * w for a, w in zip(contributions, weights)) / total
        out.append({
            "timestamp":       ts,
            "score":           round(weighted, 2),
            "n_modules_valid": len(contributions),
        })
    return out
