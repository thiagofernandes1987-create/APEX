"""
Sprint W fix (audit-3, HIGH) — Channel naming SSOT
====================================================
Single source of truth for the 9-channel map shared by Sprint M
(propagation), Sprint S (Granger), and any future cross-channel module.

Pre-fix: ``governance/granger_causality.py`` and ``governance/propagation.py``
contained byte-identical copies of ``_CHANNELS`` + ``_ATTR_BY_SHORT`` +
``_series()``.  Adding a 10th channel or renaming an attribute would have
silently drifted one copy.  This module is the only authoritative
definition; both consumers import from here.
"""
from __future__ import annotations

from typing import Any, List, Tuple


CHANNELS: Tuple[str, ...] = (
    "H", "CC", "ILR",
    "DSM_d", "DSM_c", "DI",
    "dead", "dups", "bugs",
)

ATTR_BY_SHORT = {
    "H":     "hamiltonian",
    "CC":    "cyclomatic_complexity",
    "ILR":   "infinite_loop_risk",
    "DSM_d": "dsm_density",
    "DSM_c": "dsm_cyclic_ratio",
    "DI":    "dependency_instability",
    "dead":  "syntactic_dead_code",
    "dups":  "duplicate_block_count",
    "bugs":  "halstead_bugs",
}


def series(history: List[Any], short: str) -> List[float]:
    """Pull the per-channel float series from a list of MetricVector-ish rows."""
    attr = ATTR_BY_SHORT[short]
    return [float(getattr(mv, attr, 0.0) or 0.0) for mv in history]
