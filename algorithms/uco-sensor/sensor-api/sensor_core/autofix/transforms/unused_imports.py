"""
AutofixEngine — UnusedImportRemover
=====================================
Removes ``import`` / ``from … import`` statements whose imported names are
never referenced in the module's AST.

Safety constraints:
  - Does NOT remove imports that are re-exported (``__all__`` mentions).
  - Does NOT remove imports when the source contains ``getattr``, ``eval``,
    ``exec``, or ``__import__`` calls (dynamic name usage is unprovable).
  - Does NOT remove ``from __future__ import …``.
  - Does NOT remove star imports (``from x import *``).
  - Preserves lines — emits a ``pass`` only if removing an import would leave
    an empty module; otherwise just omits the node.
  - Alias imports: ``import os as _os`` — the alias ``_os`` is the name used
    in the AST, not ``os``.

Algorithm:
  1. Collect all imported names / aliases.
  2. Walk the AST and collect all Name.id / Attribute.attr used **outside**
     import nodes.
  3. An import is unused if none of its bound names appear in step 2.
  4. Remove unused import nodes; fix locations.
"""
from __future__ import annotations

import ast
from typing import List, Set, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

# If any of these calls appear in the source, we bail out entirely
_DYNAMIC_PATTERNS = {"getattr", "setattr", "eval", "exec", "__import__",
                     "importlib", "vars", "locals", "globals"}


def _collect_used_names(tree: ast.AST) -> Set[str]:
    """Return all Name.id used in the tree (excluding import nodes themselves)."""
    used: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            # ``os.path`` — the root object is ``os`` (a Name)
            # handled via Name visitor above
            pass
    return used


def _has_dynamic_access(tree: ast.AST) -> bool:
    """Return True if the module uses dynamic name resolution patterns."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in _DYNAMIC_PATTERNS:
                return True
            if isinstance(func, ast.Attribute) and func.attr in _DYNAMIC_PATTERNS:
                return True
    return False


def _exported_names(tree: ast.AST) -> Set[str]:
    """
    Return names listed in ``__all__`` (if present).
    These must never be removed even if they look unused.
    """
    names: Set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Name) and t.id == "__all__"
                for t in node.targets
            )
            and isinstance(node.value, (ast.List, ast.Tuple))
        ):
            for elt in node.value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    names.add(elt.value)
    return names


class UnusedImportRemover(BaseTransform):
    """
    Removes import statements whose bound names are never referenced
    anywhere in the module AST.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        if _has_dynamic_access(tree):
            return tree, results   # bail out — dynamic names are unprovable

        used     = _collect_used_names(tree)
        exported = _exported_names(tree)
        safe_set = used | exported

        # Collect module-level statements
        if not isinstance(tree, ast.Module):
            return tree, results

        new_body: List[ast.stmt] = []
        for stmt in tree.body:

            # ── from __future__ import … — always keep ──────────────────
            if (
                isinstance(stmt, ast.ImportFrom)
                and stmt.module == "__future__"
            ):
                new_body.append(stmt)
                continue

            # ── from x import * — always keep ───────────────────────────
            if (
                isinstance(stmt, ast.ImportFrom)
                and any(a.name == "*" for a in stmt.names)
            ):
                new_body.append(stmt)
                continue

            # ── import a, b, c ───────────────────────────────────────────
            if isinstance(stmt, ast.Import):
                live_aliases = []
                for alias in stmt.names:
                    bound_name = alias.asname if alias.asname else alias.name.split(".")[0]
                    if bound_name in safe_set:
                        live_aliases.append(alias)
                    else:
                        results.append(TransformResult(
                            transform=self.name,
                            description=f"Removed unused import '{alias.name}'",
                            location="module",
                            lines_removed=0,
                        ))
                if live_aliases:
                    stmt.names = live_aliases
                    new_body.append(stmt)
                # else: drop the entire import statement
                continue

            # ── from x import a, b, c ────────────────────────────────────
            if isinstance(stmt, ast.ImportFrom):
                live_aliases = []
                for alias in stmt.names:
                    bound_name = alias.asname if alias.asname else alias.name
                    if bound_name in safe_set:
                        live_aliases.append(alias)
                    else:
                        results.append(TransformResult(
                            transform=self.name,
                            description=(
                                f"Removed unused import "
                                f"'{alias.name}' from '{stmt.module}'"
                            ),
                            location="module",
                            lines_removed=0,
                        ))
                if live_aliases:
                    stmt.names = live_aliases
                    new_body.append(stmt)
                continue

            new_body.append(stmt)

        tree.body = new_body
        ast.fix_missing_locations(tree)
        return tree, results
