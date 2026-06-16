"""
AutofixEngine — LoopGuardAdvisor  (AFix+ FASE 8, transform #15)
================================================================
Flags ``while True:`` loops that have no reachable ``break`` (and no
``return``/``raise`` terminator) inside the loop body — a common source of
unintended infinite loops (CWE-835).

Advisory only
-------------
Automatically inserting an exit condition could change program semantics,
so this transform never mutates the tree.  It records a ``TransformResult``
recommending an explicit termination guard, and the engine surfaces it as a
suggestion (no source rewrite).

Detection
---------
A ``while`` whose test is the literal ``True`` is flagged when, scanning its
body **without descending into nested function/class definitions**, none of
``break`` / ``return`` / ``raise`` appears.
"""
from __future__ import annotations

import ast
from typing import Iterator, List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _walk_no_fn(node: ast.AST) -> Iterator[ast.AST]:
    """Yield descendants without crossing function/class boundaries."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield child
        yield from _walk_no_fn(child)


def _is_true(node: ast.expr) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


class LoopGuardAdvisor(BaseTransform):
    """Advises adding a termination guard to ``while True:`` without break."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.While):
                continue
            if not _is_true(node.test):
                continue

            has_terminator = any(
                isinstance(child, (ast.Break, ast.Return, ast.Raise))
                for child in _walk_no_fn(node)
            )
            if has_terminator:
                continue

            line = getattr(node, "lineno", 0)
            results.append(TransformResult(
                transform=self.name,
                description=(
                    "'while True:' has no reachable break/return/raise — add an "
                    "explicit termination guard to avoid an infinite loop (CWE-835) [ADVISORY]"
                ),
                location=f"line {line}" if line else "module",
            ))

        # Advisory: never mutate the tree.
        return tree, results
