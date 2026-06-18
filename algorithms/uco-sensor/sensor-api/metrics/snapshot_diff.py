"""
Sprint E — Snapshot Diff Vector  (M-Diff)
==========================================
Compute the **per-channel delta** between two MetricVector snapshots of
the same module.  Answers the question every code-review tool wants:
*"What actually changed between commit A and commit B for this module?"*

Three public entry points
-------------------------
- `compute_diff(mv_from, mv_to)`            — pure function on two vectors
- `compute_diff_by_commits(store, module, commit_from, commit_to)`
                                           — fetch + diff helper
- `top_volatile_channels(store, module, window, top_k)`
                                           — channels with highest
                                             coefficient-of-variation
                                             over a history window

Design decisions
----------------
- **Tracked canonical channels** are the 9 primary signals + APS + LOC.
  The 9 are the hard-coded core of the FrequencyEngine; APS is the
  composite quality score (Sprint A/B); LOC is the size denominator.
  Predictor channels are deliberately excluded (they describe the
  predictor, not the code).
- **delta_pct = NaN when both values are 0** — clean sentinel for
  "channel did not move".  ``inf`` only when from=0 and to≠0
  (genuine appearance of signal).
- **Direction**: ``UP``, ``DOWN``, ``FLAT`` — direction-aware aggregation
  in callers without re-deriving sign.
- **Volatility = coefficient of variation** (σ / |μ|).  CV is unit-free
  and comparable across channels with wildly different scales (e.g.,
  hamiltonian 0-100 vs duplicate_block_count 0-10).  Fallback to σ
  when |μ| < 1e-9.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple


# ─── Canonical channel list ───────────────────────────────────────────────────

_PRIMARY_CHANNELS: Tuple[Tuple[str, str], ...] = (
    ("hamiltonian",            "H"),
    ("cyclomatic_complexity",  "CC"),
    ("infinite_loop_risk",     "ILR"),
    ("dsm_density",            "DSM_d"),
    ("dsm_cyclic_ratio",       "DSM_c"),
    ("dependency_instability", "DI"),
    ("syntactic_dead_code",    "dead"),
    ("duplicate_block_count",  "dups"),
    ("halstead_bugs",          "bugs"),
)

# Extra channels resolved via getattr — None means "missing from snapshot".
_EXTRA_CHANNELS: Tuple[Tuple[str, str], ...] = (
    ("aps_score",      "APS"),
    ("lines_of_code",  "LOC"),
)


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class ChannelDelta:
    """One channel's movement between two snapshots."""
    name:       str
    short:      str
    value_from: float
    value_to:   float
    delta_abs:  float
    delta_pct:  float   # NaN if both sides are 0, +inf if from=0 & to>0
    direction:  str     # "UP" | "DOWN" | "FLAT"

    def to_dict(self) -> Dict[str, Any]:
        # JSON-friendly: replace NaN/inf with sentinel strings.
        def _safe(x: float) -> Any:
            if math.isnan(x):
                return None
            if math.isinf(x):
                return "inf" if x > 0 else "-inf"
            return x
        return {
            "name":       self.name,
            "short":      self.short,
            "value_from": _safe(self.value_from),
            "value_to":   _safe(self.value_to),
            "delta_abs":  _safe(self.delta_abs),
            "delta_pct":  _safe(self.delta_pct),
            "direction":  self.direction,
        }


@dataclass
class SnapshotDiff:
    """Full diff between two snapshots of the same module."""
    module_id:    str
    commit_from:  str
    commit_to:    str
    ts_from:      float
    ts_to:        float
    channels:     List[ChannelDelta] = field(default_factory=list)

    @property
    def n_changed(self) -> int:
        return sum(1 for c in self.channels if c.direction != "FLAT")

    @property
    def n_total(self) -> int:
        return len(self.channels)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id":   self.module_id,
            "commit_from": self.commit_from,
            "commit_to":   self.commit_to,
            "ts_from":     self.ts_from,
            "ts_to":       self.ts_to,
            "n_total":     self.n_total,
            "n_changed":   self.n_changed,
            "channels":    [c.to_dict() for c in self.channels],
        }


# ─── Pure compute_diff ────────────────────────────────────────────────────────

def _channel_value(mv: Any, attr: str) -> Optional[float]:
    """Return float(mv.attr) or None if the attribute is missing/None."""
    v = getattr(mv, attr, None)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _make_delta(name: str, short: str, vf: float, vt: float) -> ChannelDelta:
    delta_abs = vt - vf
    if abs(vf) < 1e-12 and abs(vt) < 1e-12:
        delta_pct = float("nan")
        direction = "FLAT"
    elif abs(vf) < 1e-12:
        delta_pct = float("inf") if vt > 0 else float("-inf")
        direction = "UP" if vt > 0 else "DOWN"
    else:
        delta_pct = delta_abs / vf
        if abs(delta_abs) < 1e-12:
            direction = "FLAT"
        elif delta_abs > 0:
            direction = "UP"
        else:
            direction = "DOWN"
    return ChannelDelta(
        name=name, short=short,
        value_from=vf, value_to=vt,
        delta_abs=delta_abs, delta_pct=delta_pct,
        direction=direction,
    )


def compute_diff(mv_from: Any, mv_to: Any) -> SnapshotDiff:
    """
    Compare two MetricVectors of the (presumably) same module.

    Channels missing from either side are skipped (not reported as
    FLAT — that would be a lie about coverage).
    """
    channels: List[ChannelDelta] = []
    for attr, short in _PRIMARY_CHANNELS + _EXTRA_CHANNELS:
        vf = _channel_value(mv_from, attr)
        vt = _channel_value(mv_to,   attr)
        if vf is None or vt is None:
            continue
        channels.append(_make_delta(attr, short, vf, vt))

    return SnapshotDiff(
        module_id=getattr(mv_to, "module_id", "") or getattr(mv_from, "module_id", ""),
        commit_from=getattr(mv_from, "commit_hash", ""),
        commit_to=getattr(mv_to,   "commit_hash", ""),
        ts_from=float(getattr(mv_from, "timestamp", 0.0)),
        ts_to=float(getattr(mv_to,   "timestamp", 0.0)),
        channels=channels,
    )


# ─── Store-backed helpers ─────────────────────────────────────────────────────

def compute_diff_by_commits(
    store: Any,
    module_id: str,
    commit_from: str,
    commit_to: str,
    *,
    history_window: int = 1000,
) -> Optional[SnapshotDiff]:
    """
    Resolve both commits in the persisted history and diff them.

    Returns None if either commit is not found in the window.  ``store``
    must expose ``get_history(module_id, window) -> List[MetricVector]``.
    """
    try:
        history = store.get_history(module_id, window=history_window)
    except Exception:
        return None

    mv_from = next((mv for mv in history if mv.commit_hash == commit_from), None)
    mv_to   = next((mv for mv in history if mv.commit_hash == commit_to),   None)
    if mv_from is None or mv_to is None:
        return None
    return compute_diff(mv_from, mv_to)


def top_volatile_channels(
    store: Any,
    module_id: str,
    *,
    window: int = 50,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Rank channels by **coefficient of variation** (σ / |μ|) over the
    window, descending — most volatile first.

    Channels with fewer than 3 samples or with σ ≈ 0 are skipped.
    When |μ| < 1e-9 the score falls back to plain σ so we don't divide
    by ~zero and lose all sub-unit-mean channels.

    Output: ``[{channel, short, mean, std, cv, n_samples}, ...]``
    """
    try:
        history = store.get_history(module_id, window=window)
    except Exception:
        return []
    if len(history) < 3:
        return []

    out: List[Dict[str, Any]] = []
    for attr, short in _PRIMARY_CHANNELS + _EXTRA_CHANNELS:
        values: List[float] = []
        for mv in history:
            v = _channel_value(mv, attr)
            if v is not None:
                values.append(v)
        if len(values) < 3:
            continue

        mean = statistics.fmean(values)
        try:
            std = statistics.stdev(values)
        except statistics.StatisticsError:
            continue
        if std < 1e-12:
            continue

        if abs(mean) < 1e-9:
            cv = std       # fallback — channel never deviates from ~0 baseline
        else:
            cv = std / abs(mean)

        out.append({
            "channel":   attr,
            "short":     short,
            "mean":      mean,
            "std":       std,
            "cv":        cv,
            "n_samples": len(values),
        })

    out.sort(key=lambda d: (-d["cv"], d["channel"]))
    return out[:max(0, int(top_k))]
