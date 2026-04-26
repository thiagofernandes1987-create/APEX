"""
AutofixEngine — DeadCodeRemover
================================
Removes provably unreachable statements inside function bodies.

Rule: within a flat sequence of statements (function body, branch body),
any statement that follows an **unconditional** ``return``, ``raise``,
``continue``, or ``break`` can never execute.

Safety constraints:
  - Only removes at the **same nesting level** as the terminator.
  - Does NOT remove ``pass`` placeholders (would break empty bodies).
  - Does NOT touch module-level code (only FunctionDef/AsyncFunctionDef).
  - Preserves docstrings (first Expr with Constant string at top of body).
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_TERMINATORS = (ast.Return, ast.Raise, ast.Continue, ast.Break)


def _trim_after_terminator(
    stmts: List[ast.stmt],
    location: str,
    results: List[TransformResult],
    transform_name: str,
) -> List[ast.stmt]:
    """
    Return stmts with everything after the first unconditional terminator
    removed.  Appends a TransformResult if anything was removed.
    """
    cut_idx = None
    for i, stmt in enumerate(stmts):
        if isinstance(stmt, _TERMINATORS):
            cut_idx = i
            break

    if cut_idx is None or cut_idx == len(stmts) - 1:
        return stmts  # nothing to remove

    # Count what we'd remove (exclude trailing pass that may be the only stmt)
    tail = stmts[cut_idx + 1:]
    removable = [
        s for s in tail
        if not (isinstance(s, ast.Pass) and len(stmts) - len(tail) <= 1)
    ]
    if not removable:
        return stmts

    removed_lines = sum(
        (getattr(s, "end_lineno", getattr(s, "lineno", 0))
         - getattr(s, "lineno", 0) + 1)
        for s in removable
    )

    results.append(TransformResult(
        transform=transform_name,
        description=(
            f"Removed {len(removable)} unreachable statement(s) after "
            f"{type(stmts[cut_idx]).__name__}"
        ),
        location=location,
        lines_removed=max(removed_lines, len(removable)),
    ))

    return stmts[: cut_idx + 1]


class DeadCodeRemover(BaseTransform):
    """
    Strips unreachable statements that follow unconditional
    return / raise / continue / break inside function bodies.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            location = node.name
            new_body = _trim_after_terminator(
                node.body, location, results, self.name
            )
            node.body = new_body

            # Also trim inside if/else/for/while/try branches
            for child in ast.walk(node):
                if isinstance(child, (ast.If, ast.For, ast.While, ast.With)):
                    child.body = _trim_after_terminator(
                        child.body, location, results, self.name
                    )
                    if hasattr(child, "orelse") and child.orelse:
                        child.orelse = _trim_after_terminator(
                            child.orelse, location, results, self.name
                        )
                elif isinstance(child, ast.Try):
                    child.body = _trim_after_terminator(
                        child.body, location, results, self.name
                    )
                    for handler in child.handlers:
                        handler.body = _trim_after_terminator(
                            handler.body, location, results, self.name
                        )

        ast.fix_missing_locations(tree)
        return tree, results
