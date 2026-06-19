"""
Sprint K — NoOpAssignRemover (SAST042)
=======================================
Removes self-assignments that do not change state:

    x = x
    x += 0  /  x -= 0
    x *= 1  /  x /= 1  /  x //= 1
    x = x + 0  /  x = x * 1

These are CWE-563 (assignment to variable without use) markers — usually
refactor remnants or typos.  Pure AST rewrite: walk every statement-bearing
block and drop the matching nodes.

The bridge-based ``UCONoOpRemover`` does NOT cover ``x = x`` because the
UCO core's ``NoOpAssignmentSimplifier`` was tuned for arithmetic identities
only.  This transform fills the gap.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _is_noop_assign(stmt: ast.AST) -> bool:
    """True for `x = x` and `x = x + 0`, `x = x * 1` shapes."""
    if isinstance(stmt, ast.Assign):
        if len(stmt.targets) != 1 or not isinstance(stmt.targets[0], ast.Name):
            return False
        tgt = stmt.targets[0].id
        # Form: x = x
        if isinstance(stmt.value, ast.Name) and stmt.value.id == tgt:
            return True
        # Form: x = x + 0 / x = x - 0 / x = x * 1
        if isinstance(stmt.value, ast.BinOp):
            left, right = stmt.value.left, stmt.value.right
            left_is_x  = isinstance(left,  ast.Name) and left.id  == tgt
            right_is_x = isinstance(right, ast.Name) and right.id == tgt
            if isinstance(stmt.value.op, (ast.Add, ast.Sub)):
                if left_is_x and isinstance(right, ast.Constant) and right.value == 0:
                    return True
                if right_is_x and isinstance(left, ast.Constant) and left.value == 0:
                    return True
            if isinstance(stmt.value.op, (ast.Mult,)):
                if left_is_x and isinstance(right, ast.Constant) and right.value == 1:
                    return True
                if right_is_x and isinstance(left, ast.Constant) and left.value == 1:
                    return True
        return False

    if isinstance(stmt, ast.AugAssign):
        if not isinstance(stmt.value, ast.Constant):
            return False
        v = stmt.value.value
        if isinstance(stmt.op, (ast.Add, ast.Sub)) and v == 0:
            return True
        if isinstance(stmt.op, (ast.Mult, ast.Div, ast.FloorDiv)) and v == 1:
            return True
    return False


class NoOpAssignRemover(BaseTransform):
    """Drops no-op self-assignments. CWE-563."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for parent in ast.walk(tree):
            block = getattr(parent, "body", None)
            if not isinstance(block, list):
                continue
            kept: List[ast.AST] = []
            for stmt in block:
                if _is_noop_assign(stmt):
                    line = getattr(stmt, "lineno", 0)
                    results.append(TransformResult(
                        transform=self.name,
                        description="Removed no-op self-assignment (CWE-563)",
                        location=f"line {line}" if line else "module",
                        lines_removed=1,
                    ))
                    continue
                kept.append(stmt)
            block[:] = kept

        ast.fix_missing_locations(tree)
        return tree, results
