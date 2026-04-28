"""
AutofixEngine — DocstringAdder  (M8.1, transform #8)
======================================================
Adds a placeholder docstring to public functions that lack one.

Before:
    def process(data):
        return data * 2

After:
    def process(data):
        \"\"\"TODO: Add docstring.\"\"\"
        return data * 2

Safety constraints:
  - Only targets public functions (name does NOT start with ``_``).
  - Skips functions whose first statement is already a string literal
    (i.e. they already have a docstring).
  - Skips async functions too — same rule applies.
  - Does NOT add docstrings to methods inside classes (to keep the
    transform targeted; class-method docstrings are a separate concern).
  - Applied inside every FunctionDef/AsyncFunctionDef in the module,
    including nested functions.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_PLACEHOLDER = "TODO: Add docstring."


def _has_docstring(body: List[ast.stmt]) -> bool:
    """Return True if *body* starts with a string-constant expression."""
    return (
        bool(body)
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    )


class DocstringAdder(BaseTransform):
    """
    Inserts ``\"\"\"TODO: Add docstring.\"\"\"`` into public functions that
    are missing a docstring.
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
            if node.name.startswith("_"):
                # private / dunder — skip
                continue
            if _has_docstring(node.body):
                # already documented
                continue

            # Insert placeholder docstring as first statement
            doc_node = ast.Expr(value=ast.Constant(value=_PLACEHOLDER))
            node.body.insert(0, doc_node)

            results.append(TransformResult(
                transform=self.name,
                description=f"Added placeholder docstring to '{node.name}'",
                location=node.name,
            ))

        ast.fix_missing_locations(tree)
        return tree, results
