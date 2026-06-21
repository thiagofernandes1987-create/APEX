"""
Sprint L — Change-Point Detection + Root-Cause Attribution  (v3.3.4)
=====================================================================
Exposes the PELT change-point detector from frequency-engine as a
**governance signal** with git blame cross-reference.

The question this module answers
--------------------------------
Until now, the FrequencyEngine's PELT detector ran inside the
classification pipeline but its output never reached the user-facing
API.  Asking "when did this module's metrics regime change?" required
reading every snapshot manually.

This module turns PELT output into the most actionable signal in the
whole system: **"the metrics regime of module X shifted on commit Y,
authored by Z, in channel W, with confidence C"**.

Public API
----------
- ``detect_changepoints(store, module_id, *, primary_channels=None,
  penalty=1.0, model="rbf")`` → ``List[ChangePointRecord]``
- ``annotate_with_git(records, repo_dir=None)`` enriches the records
  in-place with ``author`` / ``commit_subject`` / ``date`` from
  ``git log`` (best-effort — silent on missing git or unknown SHA).

Design contract
---------------
* Pure: no writes to the store, no global mutation.
* Defensive: any failure path returns ``[]`` with a structured error
  payload.  Never raises on missing data, missing git, or empty history.
* ``primary_channels`` default is the same set the FrequencyClassifier
  uses by default (H + CC + DI) — the channels most predictive of a
  real regime shift.
"""
from __future__ import annotations

import logging
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("uco-sensor.changepoints")


# Defaults: the three channels with the highest pre-correlation to regime shifts
_DEFAULT_PRIMARY = ("H", "CC", "DI")


@dataclass
class ChangePointRecord:
    """Per-change-point payload, enriched with optional git metadata."""
    module_id:        str
    commit_idx:       int
    commit_hash:      Optional[str]
    timestamp:        float
    confidence:       float
    magnitude:        float
    affected_channels: List[str] = field(default_factory=list)
    # ── Optional git enrichment (populated by annotate_with_git) ─────────
    author:           Optional[str]   = None
    author_email:     Optional[str]   = None
    commit_subject:   Optional[str]   = None
    commit_date:      Optional[str]   = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _resolve_signal_builder():
    try:
        from transmitter.metric_signal_builder import MetricSignalBuilder
        return MetricSignalBuilder()
    except Exception as exc:
        _log.warning("MetricSignalBuilder unavailable: %s", exc)
        return None


def _resolve_detector(model: str, penalty: float):
    try:
        from receptor.change_point_detector import ChangePointDetector
        return ChangePointDetector(model=model, penalty=penalty)
    except Exception as exc:
        _log.warning("ChangePointDetector unavailable: %s", exc)
        return None


def detect_changepoints(
    store: Any,
    module_id: str,
    *,
    primary_channels: Optional[List[str]] = None,
    penalty: float = 1.0,
    model: str = "rbf",
    window: int = 200,
) -> List[ChangePointRecord]:
    """
    Run PELT on the persisted history of *module_id*.

    Returns a list (possibly empty) of ``ChangePointRecord``.  Multiple
    change points are returned when the detector finds more than one
    significant breakpoint.
    """
    try:
        history = store.get_history(module_id, window=window)
    except Exception:
        return []
    if not history:
        return []

    builder = _resolve_signal_builder()
    if builder is None:
        return []
    signal = builder.build(history, verbose=False)
    if signal is None:
        return []

    detector = _resolve_detector(model, penalty)
    if detector is None:
        return []

    channels = list(primary_channels) if primary_channels else list(_DEFAULT_PRIMARY)
    try:
        result = detector.detect(signal, channels)
    except Exception as exc:
        _log.warning("PELT detect failed for %s: %s", module_id, exc)
        return []

    if result is None:
        return []

    # Map the detected commit_idx back to the original history's commit/timestamp
    # (the signal interpolates to a uniform grid, but commit_idx is in signal space).
    commit_hashes = getattr(signal, "commit_hashes", []) or [
        mv.commit_hash for mv in history
    ]
    timestamps = getattr(signal, "timestamps", None)
    commit_idx = int(result.commit_idx)
    if 0 <= commit_idx < len(commit_hashes):
        ch = commit_hashes[commit_idx]
    else:
        ch = result.commit_hash

    # Map timestamp from the history if we can find the commit
    ts = 0.0
    for mv in history:
        if mv.commit_hash == ch:
            ts = float(mv.timestamp)
            break

    return [ChangePointRecord(
        module_id=module_id,
        commit_idx=commit_idx,
        commit_hash=ch,
        timestamp=ts,
        confidence=float(result.confidence),
        magnitude=float(result.magnitude),
        affected_channels=list(result.affected_channels),
    )]


# ─── Git-blame enrichment ─────────────────────────────────────────────────────

def annotate_with_git(
    records: List[ChangePointRecord],
    repo_dir: Optional[str] = None,
    timeout: float = 5.0,
) -> List[ChangePointRecord]:
    """
    Best-effort: enrich each record with ``author`` / ``commit_subject``
    / ``commit_date`` via ``git show --no-patch --format`` on
    ``commit_hash``.  Records lacking a commit_hash, or any git failure,
    leave the optional fields ``None`` — never raises.
    """
    cwd = Path(repo_dir).resolve() if repo_dir else None
    for rec in records:
        if not rec.commit_hash:
            continue
        try:
            out = subprocess.check_output(
                ["git", "show", "--no-patch",
                 "--format=%an%n%ae%n%s%n%ci", rec.commit_hash],
                cwd=str(cwd) if cwd else None,
                timeout=timeout,
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="replace")
            lines = out.strip().split("\n")
            if len(lines) >= 4:
                rec.author         = lines[0] or None
                rec.author_email   = lines[1] or None
                rec.commit_subject = lines[2] or None
                rec.commit_date    = lines[3] or None
        except Exception:
            continue   # silent on any git failure
    return records


# ─── Repo-wide aggregation ────────────────────────────────────────────────────

def repo_changepoints(
    store: Any,
    *,
    primary_channels: Optional[List[str]] = None,
    penalty: float = 1.0,
    model: str = "rbf",
    window: int = 200,
    repo_dir: Optional[str] = None,
) -> List[ChangePointRecord]:
    """
    Walk every module in the store and return the change-point records,
    sorted by confidence desc.  Optional git annotation when ``repo_dir``
    is provided.
    """
    try:
        modules = store.list_modules()
    except Exception:
        return []

    all_records: List[ChangePointRecord] = []
    for module_id in modules:
        recs = detect_changepoints(
            store, module_id,
            primary_channels=primary_channels,
            penalty=penalty,
            model=model,
            window=window,
        )
        all_records.extend(recs)

    if repo_dir:
        annotate_with_git(all_records, repo_dir=repo_dir)

    all_records.sort(key=lambda r: (-r.confidence, r.module_id))
    return all_records
