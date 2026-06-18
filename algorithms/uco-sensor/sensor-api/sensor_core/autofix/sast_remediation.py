"""
LEAP 3 — AutoFix ↔ SAST Closed Loop  (M8.2)
=============================================
Orchestrator that auto-remediates SAST findings whose rule has a known
AutoFix transform mapping.

Pipeline
--------
  source ─► sast.scan() ──► findings_before
              │
              ▼ (collect rules present, look up transforms)
       AutofixEngine(only relevant transforms).apply(source)
              │
              ▼
  patched_source ─► sast.scan() ─► findings_after
              │
              ▼
  RemediationResult{ patched_source, transforms_applied, findings_before,
                     findings_after, fixed_count, residual_count, is_valid }

Mapping table
-------------
Only **high-confidence rewrites** (transforms that produce valid Python with
no semantic change at the per-finding level) are mapped.  Advisory-only
transforms (LoopGuardAdvisor, FormatStringModernizer, …) are NOT auto-applied
even when a matching SAST rule fires — the user has to inspect them.

Adding a new mapping is one line: ``"SASTNNN": TransformClass`` in
``SAST_TO_TRANSFORM``.  Add a TY-test in ``test_marco_m30`` and the closed
loop covers that rule.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Type

from sensor_core.autofix.engine import AutofixEngine
from sensor_core.autofix.transforms.base import BaseTransform

# All eligible high-confidence rewrite transforms
from sensor_core.autofix.transforms.replace_weak_hash       import WeakHashReplacer
from sensor_core.autofix.transforms.replace_insecure_random import InsecureRandomReplacer
from sensor_core.autofix.transforms.replace_bare_except     import BareExceptReplacer
from sensor_core.autofix.transforms.remove_mutable_default  import MutableDefaultRemover
from sensor_core.autofix.transforms.simplify_comparison     import NoneComparisonSimplifier


# ─── Mapping table — single source of truth ──────────────────────────────────

SAST_TO_TRANSFORM: Dict[str, Type[BaseTransform]] = {
    "SAST006": WeakHashReplacer,         # Weak Crypto (md5/sha1) → sha256
    "SAST007": InsecureRandomReplacer,   # Insecure random — choice → secrets.choice
    "SAST038": BareExceptReplacer,       # Bare except → except Exception as e
    "SAST039": MutableDefaultRemover,    # Mutable default arg → None + guard
}


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class RemediationResult:
    """
    Outcome of a single ``auto_remediate(source)`` call.

    Fields
    ------
    patched_source       : the rewritten source (==source when no fix applied)
    is_valid             : True if patched_source compiles cleanly
    transforms_applied   : transform names that contributed at least one change
    findings_before      : SAST finding rule IDs present in the original source
    findings_after       : SAST finding rule IDs still present after fixing
    fixed_rules          : rule IDs that disappeared between before and after
    residual_count       : len(findings_after)
    """
    patched_source:     str
    is_valid:           bool
    transforms_applied: List[str]   = field(default_factory=list)
    findings_before:    List[str]   = field(default_factory=list)
    findings_after:     List[str]   = field(default_factory=list)
    fixed_rules:        List[str]   = field(default_factory=list)
    residual_count:     int         = 0

    @property
    def fixed_count(self) -> int:
        return len(self.fixed_rules)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "patched_source":     self.patched_source,
            "is_valid":           self.is_valid,
            "transforms_applied": self.transforms_applied,
            "findings_before":    self.findings_before,
            "findings_after":     self.findings_after,
            "fixed_rules":        self.fixed_rules,
            "fixed_count":        self.fixed_count,
            "residual_count":     self.residual_count,
        }


# ─── Public API ───────────────────────────────────────────────────────────────

def _scan_rule_ids(source: str) -> List[str]:
    """Return the list of SAST rule IDs triggered on *source*; empty on parse error."""
    try:
        from sast.scanner import scan
        result = scan(source, file_extension=".py")
    except Exception:
        return []
    if getattr(result, "parse_error", False):
        return []
    return [f.rule_id for f in getattr(result, "findings", [])]


def _select_transforms(rule_ids: List[str]) -> List[Type[BaseTransform]]:
    """
    Pick the (deduplicated, deterministically-ordered) transforms whose
    mapped rule IDs appear in *rule_ids*.
    """
    seen: Set[Type[BaseTransform]] = set()
    selected: List[Type[BaseTransform]] = []
    # Preserve the canonical order from the mapping table for determinism.
    for rule, transform_cls in SAST_TO_TRANSFORM.items():
        if rule in rule_ids and transform_cls not in seen:
            seen.add(transform_cls)
            selected.append(transform_cls)
    return selected


def auto_remediate(source: str, module_id: str = "") -> RemediationResult:
    """
    Run SAST → select matching transforms → apply → re-run SAST.

    Parameters
    ----------
    source     : Python source code to fix
    module_id  : optional identifier carried through into the result (debug)

    Returns
    -------
    RemediationResult.  Always returns — never raises on user input.
    On SAST parse errors the result has the original source unchanged.
    """
    findings_before = _scan_rule_ids(source)

    transform_classes = _select_transforms(findings_before)
    if not transform_classes:
        # Nothing to do — return identity result so callers handle it uniformly.
        return RemediationResult(
            patched_source=source,
            is_valid=True,
            transforms_applied=[],
            findings_before=findings_before,
            findings_after=findings_before,
            fixed_rules=[],
            residual_count=len(findings_before),
        )

    engine = AutofixEngine(transforms=transform_classes)
    result = engine.apply(source)

    patched_source = result.fixed_source if result.is_valid_python else source
    findings_after = _scan_rule_ids(patched_source)

    transforms_applied = sorted(
        {r.transform for r in result.transforms_applied}
    )

    # Set difference: rules that disappeared.
    before_set = set(findings_before)
    after_set  = set(findings_after)
    fixed_rules = sorted(before_set - after_set)

    return RemediationResult(
        patched_source=patched_source,
        is_valid=result.is_valid_python,
        transforms_applied=transforms_applied,
        findings_before=findings_before,
        findings_after=findings_after,
        fixed_rules=fixed_rules,
        residual_count=len(findings_after),
    )
