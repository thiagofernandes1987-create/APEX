"""
AutofixEngine — ContextManagerAdvisor  (M8.1, transform #9)
=============================================================
Detects ``open()`` calls that are assigned to a variable **outside** a
``with`` statement and suggests wrapping them in a context manager.

This transform is **suggestion-only** — it does NOT mutate the AST.
It returns ``TransformResult`` entries describing each offending call
site so the caller can display actionable advice.

Before (flagged):
    f = open("data.txt")
    data = f.read()
    f.close()

Suggested fix:
    with open("data.txt") as f:
        data = f.read()

Safety constraints:
  - Only flags ``open()`` calls assigned to a plain variable (``Name``
    target), not calls that appear inside ``with`` blocks.
  - Tracks ``with`` statement depth during the walk to avoid false
    positives on ``with open(...) as f`` (which is already correct).
  - Does not modify the AST — returns the original tree unchanged.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


class _OpenDetector(ast.NodeVisitor):
    """Visitor that finds open() assignments outside with-blocks."""

    def __init__(self) -> None:
        self.issues: List[Tuple[int, str]] = []   # (lineno, snippet)
        self._with_depth: int = 0

    def visit_With(self, node: ast.With) -> None:
        self._with_depth += 1
        self.generic_visit(node)
        self._with_depth -= 1

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._with_depth += 1
        self.generic_visit(node)
        self._with_depth -= 1

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._with_depth > 0:
            self.generic_visit(node)
            return

        # Check if the value is an open() call
        val = node.value
        if (
            isinstance(val, ast.Call)
            and isinstance(val.func, ast.Name)
            and val.func.id == "open"
        ):
            lineno = getattr(node, "lineno", 0)
            # Build a brief snippet from the assignment target names
            targets = [
                t.id for t in node.targets
                if isinstance(t, ast.Name)
            ]
            snippet = f"{', '.join(targets)} = open(...)" if targets else "= open(...)"
            self.issues.append((lineno, snippet))

        self.generic_visit(node)


class ContextManagerAdvisor(BaseTransform):
    """
    Identifies ``open()`` calls assigned outside ``with`` blocks and
    suggests converting them to ``with open(...) as f:`` form.

    This transform is suggestion-only — it never mutates the AST.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        detector = _OpenDetector()
        detector.visit(tree)

        results: List[TransformResult] = []
        for lineno, snippet in detector.issues:
            results.append(TransformResult(
                transform=self.name,
                description=(
                    f"Suggestion: wrap '{snippet}' in 'with open(...) as f:' "
                    f"at line {lineno} to ensure the file is always closed"
                ),
                location=f"line {lineno}",
            ))

        return tree, results   # no AST mutation
