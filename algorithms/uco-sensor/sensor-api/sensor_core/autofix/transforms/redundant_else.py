"""
AutofixEngine — RedundantElseRemover
======================================
Converts ``if/else`` blocks to guard-clause style when every branch of the
``if`` body ends with an unconditional terminator (``return`` / ``raise``).

Before:
    def f(x):
        if x > 0:
            return x
        else:
            return -x

After:
    def f(x):
        if x > 0:
            return x
        return -x

Safety constraints:
  - Only applies inside functions (FunctionDef / AsyncFunctionDef).
  - Only when ALL paths through the ``if`` body terminate
    (last statement is return/raise).
  - The ``else`` block is hoisted, not the ``if`` block.
  - Nested ifs: each is independently evaluated.
  - ``elif`` chains: represented as nested If in the orelse; applied
    recursively once the outer body terminates.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_TERMINATORS = (ast.Return, ast.Raise)


def _body_always_terminates(stmts: List[ast.stmt]) -> bool:
    """
    Return True if the statement list provably always reaches a
    Return or Raise before falling through to the next statement.
    """
    if not stmts:
        return False
    last = stmts[-1]
    if isinstance(last, _TERMINATORS):
        return True
    # If the last statement is itself an If with both branches terminating
    if isinstance(last, ast.If) and last.orelse:
        return (
            _body_always_terminates(last.body)
            and _body_always_terminates(last.orelse)
        )
    return False


def _flatten_if_else(
    stmts: List[ast.stmt],
    location: str,
    results: List[TransformResult],
    transform_name: str,
) -> List[ast.stmt]:
    """
    Walk stmts and flatten ``if … else …`` where the if-body terminates.
    Returns the new statement list (may be longer if orelse was hoisted).
    """
    new_stmts: List[ast.stmt] = []
    changed = False

    for stmt in stmts:
        if (
            isinstance(stmt, ast.If)
            and stmt.orelse
            and _body_always_terminates(stmt.body)
            # Exclude elif chains (orelse starts with another If — handled
            # recursively by the caller's next pass)
            and not (len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If))
        ):
            # Hoist the else body: strip the else from the If node
            else_body = stmt.orelse
            stmt.orelse = []
            new_stmts.append(stmt)
            new_stmts.extend(else_body)

            results.append(TransformResult(
                transform=transform_name,
                description=(
                    f"Removed redundant else after if-block that always returns"
                ),
                location=location,
                lines_removed=0,   # lines not removed, just restructured
            ))
            changed = True
        else:
            new_stmts.append(stmt)

    return new_stmts if changed else stmts


class RedundantElseRemover(BaseTransform):
    """
    Transforms ``if … return … else: …`` to guard-clause style.
    Applied inside every function body (multi-pass until stable).
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
            # Multi-pass: repeat until no more changes (handles nested ifs)
            for _ in range(10):
                new_body = _flatten_if_else(
                    node.body, location, results, self.name
                )
                if new_body is node.body:
                    break
                node.body = new_body

        ast.fix_missing_locations(tree)
        return tree, results
