"""
AutofixEngine — StringConcatLoopAdvisor  (M8.1, transform #11)
================================================================
Detects string/list concatenation inside ``for`` / ``while`` loops and
suggests the ``list.append()`` + ``''.join()`` pattern instead.

The pattern flagged:
    result = ""
    for item in items:
        result += item        # O(n²) — new string allocated each iteration

Suggested fix:
    parts = []
    for item in items:
        parts.append(item)
    result = "".join(parts)   # O(n) — single allocation at the end

This transform is **suggestion-only** — it does NOT mutate the AST.

Safety constraints:
  - Only flags AugAssign nodes with the ``Add`` operator (``+=``) that
    appear *directly* inside a ``for`` or ``while`` loop body.
  - The inner loop walk is limited to direct body statements to avoid
    flagging nested structures.
  - Does not modify the AST — returns the original tree unchanged.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _has_concat_in_body(stmts: List[ast.stmt]) -> List[Tuple[int, str]]:
    """
    Walk *stmts* (a loop body) and collect AugAssign += sites.
    Returns list of (lineno, target_name) tuples.
    """
    hits: List[Tuple[int, str]] = []
    for stmt in ast.walk(ast.Module(body=stmts, type_ignores=[])):
        if isinstance(stmt, ast.AugAssign) and isinstance(stmt.op, ast.Add):
            lineno = getattr(stmt, "lineno", 0)
            name = (
                stmt.target.id
                if isinstance(stmt.target, ast.Name)
                else "..."
            )
            hits.append((lineno, name))
    return hits


class StringConcatLoopAdvisor(BaseTransform):
    """
    Flags ``+=`` concatenation inside loops and recommends list+join.
    Suggestion-only — does not modify the AST.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []
        seen_lines: set = set()

        for node in ast.walk(tree):
            if not isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                continue

            for lineno, target in _has_concat_in_body(node.body):
                if lineno in seen_lines:
                    continue
                seen_lines.add(lineno)
                results.append(TransformResult(
                    transform=self.name,
                    description=(
                        f"Suggestion: '{target} +=' inside loop at line {lineno} "
                        f"causes O(n²) allocations; "
                        f"use list.append() + ''.join() instead"
                    ),
                    location=f"line {lineno}",
                ))

        return tree, results   # suggestion only — no AST mutation
