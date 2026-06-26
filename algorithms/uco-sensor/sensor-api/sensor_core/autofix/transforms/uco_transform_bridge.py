"""
Sprint K — UCO transform bridge  (v3.3.3)
==========================================
Wrappers that expose **the UCO core's own transforms** as ``BaseTransform``
subclasses, so they can participate in the AutofixEngine pipeline and the
closed SAST↔Fix loop.

Why bridge instead of re-implement
----------------------------------
UCO core (``algorithms/uco/universal_code_optimizer_v4.py``) already ships
9 cirurgical transforms — ``UnreachableAfterTerminalRemoval``,
``RedundantConditionEliminator``, ``ConstantFoldingTransform``,
``NoOpAssignmentSimplifier``, ``PythonUnusedVarDetector``, … — written and
tested at the optimizer level.  Sprint K does not re-implement any of them.
It only adapts their string→string signature to the AST→AST contract the
sensor's AutofixEngine expects, and registers them in
``SAST_TO_TRANSFORM`` so the auto_remediate loop credits them properly.

Coverage delta:  SAST_TO_TRANSFORM grows from 7 to **11** rules — the
four newly mapped detectors are SAST040-043 (added in this sprint to
``sast/scanner.py``):

    SAST040  Unreachable Code After Terminal   →  UCOUnreachableRemover
    SAST041  Redundant Constant Condition      →  UCORedundantConditionRemover
    SAST042  No-Op Self-Assignment             →  UCONoOpRemover
    SAST043  Python Unused Variable            →  UCOUnusedVarTransformer
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


# ─── Resolve the UCO core path (algorithms/uco/) ──────────────────────────────
# __file__ chain:
#   parents[0]=transforms  [1]=autofix  [2]=sensor_core  [3]=sensor-api
#   parents[4]=uco-sensor  [5]=algorithms          → algorithms/uco/
_UCO_PATH = Path(__file__).resolve().parents[5] / "uco"
if str(_UCO_PATH) not in sys.path:
    sys.path.insert(0, str(_UCO_PATH))


def _safe_unparse(tree: ast.AST) -> str:
    """ast.unparse with a fallback for nodes that can't be unparsed."""
    try:
        return ast.unparse(tree)
    except Exception:
        return ""


def _safe_parse(source: str) -> ast.AST:
    """ast.parse but never raises — returns an empty Module on failure."""
    try:
        return ast.parse(source)
    except Exception:
        return ast.Module(body=[], type_ignores=[])


def _ucotx(class_name: str):
    """Lazy-import a UCO transform class.  Returns None on miss."""
    try:
        import universal_code_optimizer_v4 as ucm
        return getattr(ucm, class_name, None)
    except Exception:
        return None


class _UCOWrapTransform(BaseTransform):
    """Common skeleton: text-based UCO transform wrapped as BaseTransform.

    Concrete subclasses set ``_uco_class_name`` and ``_description``.  The
    bridge re-unparses the AST to source, hands it to the UCO transform,
    re-parses the result, and reports a single TransformResult if the
    source actually changed.
    """

    _uco_class_name: str = ""
    _description:    str = ""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        cls = _ucotx(self._uco_class_name)
        if cls is None:
            return tree, []

        original = _safe_unparse(tree) or source
        if not original.strip():
            return tree, []

        try:
            uco = cls()
            rewritten = uco.apply(original, language="python")
        except Exception:
            return tree, []

        if rewritten == original:
            return tree, []

        new_tree = _safe_parse(rewritten)
        if not isinstance(new_tree, ast.Module) or not new_tree.body:
            # Refuse to return an empty module unless the original was empty.
            try:
                if not ast.parse(original).body:
                    return new_tree, []
            except Exception:
                pass
            return tree, []

        lines_before = original.count("\n") + 1
        lines_after  = rewritten.count("\n") + 1
        ast.fix_missing_locations(new_tree)
        return new_tree, [TransformResult(
            transform=self.name,
            description=self._description,
            location="module",
            lines_removed=max(0, lines_before - lines_after),
        )]


# ─── Concrete bridged transforms ─────────────────────────────────────────────

class UCOUnreachableRemover(_UCOWrapTransform):
    """Removes statements after return/raise/break/continue (SAST040, CWE-561)."""
    _uco_class_name = "UnreachableAfterTerminalRemoval"
    _description    = "Removed unreachable code after terminal statement (CWE-561)"


class UCORedundantConditionRemover(_UCOWrapTransform):
    """Eliminates literal ``if True``/``if False``/``while False`` (SAST041)."""
    _uco_class_name = "RedundantConditionEliminator"
    _description    = "Eliminated redundant constant conditional (CWE-570/571)"


class UCONoOpRemover(_UCOWrapTransform):
    """Removes self-noop assignments like ``x = x + 0``, ``x *= 1`` (SAST042)."""
    _uco_class_name = "NoOpAssignmentSimplifier"
    _description    = "Removed no-op assignment (CWE-563)"


class UCOUnusedVarTransformer(_UCOWrapTransform):
    """Removes unused local variables in Python functions (SAST043, CWE-563)."""
    _uco_class_name = "PythonUnusedVarDetector"
    _description    = "Removed unused local variable (CWE-563)"


# ─── Sprint AA — UCO Deep Integration: 5 previously-orphan transforms ─────────
# Audited: 9 CodeTransform subclasses exist in the UCO core; only 4 were
# bridged above (Sprint K). This sprint bridges the remaining 5. Two of them
# (Adjacent duplicate removal, constant folding) map to new SAST rules
# (SAST044, SAST045 — see sast/scanner.py) and are wired into
# SAST_TO_TRANSFORM for the closed-loop. The other three (control-block
# merge, bracket whitespace, empty C-like block removal) are pure cosmetic
# cleanups with no associated defect to report — they are bridged as
# directly-callable transforms but intentionally NOT wired to a SAST rule.

class UCOAdjacentDuplicateRemover(_UCOWrapTransform):
    """Removes consecutive duplicate lines (SAST044, CWE-1041)."""
    _uco_class_name = "AdjacentDuplicateBlockRemoval"
    _description    = "Removed adjacent duplicate statement (CWE-1041)"


class UCOConstantFolder(_UCOWrapTransform):
    """Folds constant expressions to their literal value (SAST045, CWE-1164)."""
    _uco_class_name = "ConstantFoldingTransform"
    _description    = "Folded constant expression to literal value (CWE-1164)"


class UCODuplicateControlBlockMerger(_UCOWrapTransform):
    """Merges adjacent identical control-block lines. Cosmetic — no SAST rule."""
    _uco_class_name = "DuplicateAdjacentControlBlockMerger"
    _description    = "Merged duplicate adjacent control-block line"


class UCOBracketWhitespaceNormalizer(_UCOWrapTransform):
    """Normalizes trailing whitespace and excess blank lines. Cosmetic — no SAST rule."""
    _uco_class_name = "BracketWhitespaceNormalizer"
    _description    = "Normalized bracket/whitespace formatting"


class UCOEmptyBlockRemover(_UCOWrapTransform):
    """Removes empty C-like {} blocks. Cosmetic — no SAST rule, safe_for c_like only."""
    _uco_class_name = "EmptyBlockRemover"
    _description    = "Removed empty C-like block"
