"""
AutofixEngine — ExtractMethodAdvisor  (M8.1, transform #10)
=============================================================
Identifies functions that are candidates for method extraction based on
two metrics:

  • LOC  > 50  — function body exceeds 50 logical lines
  • CC   > 10  — cyclomatic complexity exceeds 10

This transform is **suggestion-only** — it does NOT mutate the AST.
It returns ``TransformResult`` entries for each oversized function so
the IDE/CLI can surface actionable refactoring advice.

Cyclomatic Complexity (CC) approximation:
  CC = 1 + count of branching nodes:
    If, While, For, ExceptHandler, With, Assert,
    BoolOp (and/or adds one per extra operand)

Safety constraints:
  - Counts only direct children, not nested functions (each is its own
    reporting unit).
  - end_lineno is used when available (Python ≥ 3.8); falls back to 0.
  - Does not modify the AST — returns the original tree unchanged.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_LOC_THRESHOLD: int = 50
_CC_THRESHOLD:  int = 10

# Branching node types that each increment CC by 1
_BRANCH_NODES = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.Assert, ast.comprehension,
)


def _cyclomatic_complexity(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Approximate cyclomatic complexity for a single function body.
    Nested functions are not counted — they are reported separately.
    """
    cc = 1
    nested_fns: set = set()

    # Collect nested function ids to exclude their sub-nodes from the walk
    for child in ast.walk(fn_node):
        if child is fn_node:
            continue
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            nested_fns.add(id(child))

    for child in ast.walk(fn_node):
        if id(child) in nested_fns:
            continue
        if isinstance(child, _BRANCH_NODES):
            cc += 1
        elif isinstance(child, ast.BoolOp):
            # each extra operand adds a branch
            cc += len(child.values) - 1

    return cc


class ExtractMethodAdvisor(BaseTransform):
    """
    Flags functions with LOC > 50 or CC > 10 as refactoring candidates.
    Suggestion-only — does not modify the AST.
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

            start = getattr(node, "lineno", 0)
            end   = getattr(node, "end_lineno", start)
            loc   = max(0, end - start)
            cc    = _cyclomatic_complexity(node)

            reasons = []
            if loc > _LOC_THRESHOLD:
                reasons.append(f"LOC={loc}")
            if cc > _CC_THRESHOLD:
                reasons.append(f"CC={cc}")

            if not reasons:
                continue

            results.append(TransformResult(
                transform=self.name,
                description=(
                    f"Suggestion: '{node.name}' is a refactoring candidate "
                    f"({', '.join(reasons)}); consider extracting sub-functions"
                ),
                location=node.name,
            ))

        return tree, results   # suggestion only — no AST mutation
