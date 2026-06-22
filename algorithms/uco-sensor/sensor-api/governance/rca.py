"""
Sprint R — Automated Root-Cause Analysis  (v3.4.2)
====================================================
Orchestrates PELT change-points (Sprint L), git blame enrichment, and
the cross-channel causality matrix (Sprint M) into a single pipeline
that answers the question every quality-gate tool quietly wants:

  "In which commit did the quality regime shift, who authored it,
   which channel was the ROOT CAUSE, and what was the lag to the
   visible effect on the Hamiltonian?"

No existing SAST/quality-gate tool produces this signal end-to-end.

Public API
----------
- ``analyze(store, module_id, *, repo_dir=None, window=200, top_k_pairs=3)``
  → ``RCAReport``
- ``analyze_repo(store, *, repo_dir=None, window=200, top_k=10)``
  → ``List[RCAReport]`` (modules with change-points, sorted by confidence)

Algorithm
---------
1. PELT detects regime shift commit + affected_channels (Sprint L).
2. Git blame enriches with author / commit_subject / date (Sprint L).
3. Causality matrix (Sprint M) finds top_k pairs by |corr|.
4. Filter: pairs where the LEADING channel ∈ affected_channels of CP
   become root-cause candidates. The leading_channel that maximises
   |corr| is the **root**.
5. ``lag_to_visible_effect`` = best_lag of the winning pair.
"""
from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

_log = logging.getLogger("uco-sensor.rca")


@dataclass
class RCARootCause:
    """One root-cause candidate."""
    root_channel:           str
    target_channel:         str
    correlation:            float
    lag_to_visible_effect:  int
    confidence:             float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RCAReport:
    """End-to-end RCA payload for a single module."""
    module_id:          str
    status:             str                       = "OK"
    # Change-point block
    commit_hash:        Optional[str]             = None
    commit_idx:         int                       = 0
    timestamp:          float                     = 0.0
    changepoint_confidence: float                 = 0.0
    affected_channels:  List[str]                 = field(default_factory=list)
    # Git enrichment
    author:             Optional[str]             = None
    author_email:       Optional[str]             = None
    commit_subject:     Optional[str]             = None
    commit_date:        Optional[str]             = None
    # Root-cause derivation
    root_causes:        List[RCARootCause]        = field(default_factory=list)
    primary_root:       Optional[RCARootCause]    = None
    # Narrative
    summary_text:       str                       = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["root_causes"]  = [rc for rc in d["root_causes"]]
        if self.primary_root is not None:
            d["primary_root"] = self.primary_root.to_dict()
        return d


# ─── Pipeline ─────────────────────────────────────────────────────────────────

def analyze(
    store: Any,
    module_id: str,
    *,
    repo_dir: Optional[str] = None,
    window: int = 200,
    top_k_pairs: int = 3,
) -> RCAReport:
    """
    Run the RCA pipeline for *module_id*. Returns ``RCAReport`` with status:
    ``"NO_CHANGEPOINT"``, ``"NO_HISTORY"``, ``"ERROR"`` or ``"OK"``.
    """
    # Defensive imports — RCA module never raises just because a downstream
    # module is missing.
    try:
        from governance.changepoints import (
            detect_changepoints, annotate_with_git,
        )
        from governance.propagation import top_causal_pairs
    except Exception as exc:
        return RCAReport(
            module_id=module_id, status="ERROR",
            summary_text=f"dependency import failed: {exc}",
        )

    # 1. PELT change-points
    try:
        records = detect_changepoints(store, module_id, window=window)
    except Exception as exc:
        return RCAReport(
            module_id=module_id, status="ERROR",
            summary_text=f"PELT detect failed: {exc}",
        )

    if not records:
        return RCAReport(
            module_id=module_id, status="NO_CHANGEPOINT",
            summary_text="No regime shift detected on the persisted history.",
        )

    cp = records[0]   # most confident change-point

    # 2. Git enrichment (best-effort; silent on no-git/no-repo)
    if repo_dir:
        try:
            annotate_with_git([cp], repo_dir=repo_dir)
        except Exception:
            pass   # never block on git failure

    # 3. Causality matrix → top pairs
    causality_top: Dict[str, Any] = {}
    try:
        causality_top = top_causal_pairs(
            store, module_id, max_lag=5, window=window, top_k=top_k_pairs,
        )
    except Exception as exc:
        _log.warning("causality for %s failed: %s", module_id, exc)

    pairs = causality_top.get("pairs", []) if causality_top.get("status") == "OK" else []

    # 4. Filter root-cause candidates: leading channel must be in the
    #    affected_channels of the change-point.
    affected_set = set(cp.affected_channels)
    candidates: List[RCARootCause] = []
    for p in pairs:
        # Only LEADS pairs make sense for root-cause analysis.
        if p["direction"] != "LEADS":
            continue
        if p["from"] not in affected_set:
            continue
        candidates.append(RCARootCause(
            root_channel=p["from"],
            target_channel=p["to"],
            correlation=float(p["correlation"]),
            lag_to_visible_effect=int(p["best_lag"]),
            confidence=float(cp.confidence) * float(abs(p["correlation"])),
        ))

    primary = candidates[0] if candidates else None
    summary = _build_summary_text(cp, primary)

    return RCAReport(
        module_id=module_id, status="OK",
        commit_hash=cp.commit_hash,
        commit_idx=cp.commit_idx,
        timestamp=cp.timestamp,
        changepoint_confidence=cp.confidence,
        affected_channels=list(cp.affected_channels),
        author=cp.author,
        author_email=cp.author_email,
        commit_subject=cp.commit_subject,
        commit_date=cp.commit_date,
        root_causes=candidates,
        primary_root=primary,
        summary_text=summary,
    )


def _build_summary_text(cp: Any, primary: Optional[RCARootCause]) -> str:
    """Build the human-readable single-sentence RCA verdict."""
    who = cp.author if cp.author else "unknown author"
    where = cp.commit_hash[:8] if cp.commit_hash else "unknown commit"
    when  = cp.commit_date or ""
    channels = ", ".join(cp.affected_channels) if cp.affected_channels else "?"
    base = (
        f"Quality regime of this module shifted at commit {where}"
        f" ({when})" if when else f"Quality regime shifted at commit {where}"
    )
    base += f" — author {who}, channels affected: {channels}"
    base += f" (PELT confidence {cp.confidence:.2f})"
    if primary:
        base += (
            f". Root cause: {primary.root_channel} → {primary.target_channel}"
            f" with lag {primary.lag_to_visible_effect:+d}"
            f" (corr {primary.correlation:+.2f})"
        )
    return base + "."


# ─── Repo-wide ────────────────────────────────────────────────────────────────

def analyze_repo(
    store: Any,
    *,
    repo_dir: Optional[str] = None,
    window: int = 200,
    top_k: int = 10,
) -> List[RCAReport]:
    """
    Walk every module in the store; return only modules where a change-point
    was detected, sorted by changepoint_confidence descending.
    """
    try:
        modules = list(store.list_modules())
    except Exception:
        return []

    reports: List[RCAReport] = []
    for module_id in modules:
        r = analyze(store, module_id, repo_dir=repo_dir, window=window)
        if r.status == "OK":
            reports.append(r)

    reports.sort(key=lambda r: -r.changepoint_confidence)
    return reports[: max(0, int(top_k))]
