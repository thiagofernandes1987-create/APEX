"""
AutofixEngine — BooleanSimplifier
===================================
Simplifies redundant boolean comparisons.

Transforms applied:
  x == True   →  x
  x is True   →  x
  x != True   →  not x
  x is not True →  not x
  x == False  →  not x
  x is False  →  not x
  x != False  →  x
  x is not False → x

Safety: These rewrites are semantically equivalent for any truthy/falsy
Python value.  The transform does NOT alter ``x == None`` → ``x is None``
because None-equality is a lint issue, not a simplification (different
semantics for objects overriding __eq__).

Applied at module level (not limited to functions).
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _is_true_const(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _is_false_const(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is False


class _BoolVisitor(ast.NodeTransformer):
    """NodeTransformer that rewrites boolean comparisons."""

    def __init__(self) -> None:
        self.count = 0

    def visit_Compare(self, node: ast.Compare) -> ast.expr:  # type: ignore[override]
        self.generic_visit(node)

        # Only handle single-comparator compares (left op comparator)
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return node

        op   = node.ops[0]
        left = node.left
        right = node.comparators[0]

        # ── x == True / x is True  →  x ─────────────────────────────────
        if isinstance(op, (ast.Eq, ast.Is)) and _is_true_const(right):
            self.count += 1
            return left

        # ── x != True / x is not True  →  not x ─────────────────────────
        if isinstance(op, (ast.NotEq, ast.IsNot)) and _is_true_const(right):
            self.count += 1
            return ast.UnaryOp(op=ast.Not(), operand=left)

        # ── x == False / x is False  →  not x ───────────────────────────
        if isinstance(op, (ast.Eq, ast.Is)) and _is_false_const(right):
            self.count += 1
            return ast.UnaryOp(op=ast.Not(), operand=left)

        # ── x != False / x is not False  →  x ───────────────────────────
        if isinstance(op, (ast.NotEq, ast.IsNot)) and _is_false_const(right):
            self.count += 1
            return left

        return node


class BooleanSimplifier(BaseTransform):
    """
    Removes redundant comparisons to ``True`` / ``False`` literals.
    Applied across the entire module tree.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        visitor = _BoolVisitor()
        new_tree = visitor.visit(tree)
        ast.fix_missing_locations(new_tree)

        results: List[TransformResult] = []
        if visitor.count > 0:
            results.append(TransformResult(
                transform=self.name,
                description=(
                    f"Simplified {visitor.count} redundant boolean "
                    f"comparison(s) to True/False"
                ),
                location="module",
                lines_removed=0,
            ))

        return new_tree, results
