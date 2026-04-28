"""
AutofixEngine — NoneComparisonSimplifier  (M8.1, transform #7)
================================================================
Rewrites identity-style None comparisons to use ``is`` / ``is not``.

Before:
    if x == None:
        ...
    if y != None:
        ...

After:
    if x is None:
        ...
    if y is not None:
        ...

Safety constraints:
  - Only rewrites comparators that are *exactly* ``None`` (ast.Constant
    with value None).
  - Replaces ``==`` (ast.Eq) → ``is`` (ast.Is) and
    ``!=`` (ast.NotEq) → ``is not`` (ast.IsNot).
  - Handles chained comparisons: ``a == None == b`` is split and each
    comparator pair is evaluated independently.
  - Does NOT touch other equality comparisons (e.g. ``x == 0``).
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _is_none_const(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is None


class NoneComparisonSimplifier(BaseTransform):
    """
    Replaces ``== None`` with ``is None`` and ``!= None`` with ``is not None``.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue

            changed = False
            for i, (op, comp) in enumerate(zip(node.ops, node.comparators)):
                if _is_none_const(comp):
                    if isinstance(op, ast.Eq):
                        node.ops[i] = ast.Is()
                        changed = True
                        results.append(TransformResult(
                            transform=self.name,
                            description="Replaced '== None' with 'is None'",
                            location=f"line {getattr(node, 'lineno', 0)}",
                        ))
                    elif isinstance(op, ast.NotEq):
                        node.ops[i] = ast.IsNot()
                        changed = True
                        results.append(TransformResult(
                            transform=self.name,
                            description="Replaced '!= None' with 'is not None'",
                            location=f"line {getattr(node, 'lineno', 0)}",
                        ))
                # Also handle reversed: None == x  →  x is None
                # (the left side is the base; comparators are right-hand sides,
                # so None on the left appears as node.left, not in comparators)

            # Check if node.left is None for first comparison
            if _is_none_const(node.left) and node.ops:
                op = node.ops[0]
                if isinstance(op, ast.Eq):
                    node.ops[0] = ast.Is()
                    changed = True
                    results.append(TransformResult(
                        transform=self.name,
                        description="Replaced 'None ==' with 'is' (reversed None comparison)",
                        location=f"line {getattr(node, 'lineno', 0)}",
                    ))
                elif isinstance(op, ast.NotEq):
                    node.ops[0] = ast.IsNot()
                    changed = True
                    results.append(TransformResult(
                        transform=self.name,
                        description="Replaced 'None !=' with 'is not' (reversed None comparison)",
                        location=f"line {getattr(node, 'lineno', 0)}",
                    ))

        ast.fix_missing_locations(tree)
        return tree, results
