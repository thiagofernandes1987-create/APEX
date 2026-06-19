"""
Sprint K — UnusedVarRemover (SAST043)
======================================
Drops local-variable assignments whose value is never read later in the
enclosing function body.  Pure AST transform — no dependency on the UCO
core's PythonUnusedVarDetector (which is an *advisor*, not a rewriter).

Scope and safety
----------------
- Function-body local names only.  Module-level state, class attributes
  and free variables are left untouched (their use is non-local and
  cannot be proved unused by AST alone).
- Function parameters are NEVER removed (the caller depends on them).
- Variables starting with ``_`` are conventionally "intentionally
  unused" — skipped to avoid removing pytest fixtures and similar.
- Removes ONLY the Assign / AnnAssign / AugAssign statement; nested
  side-effects in the RHS (calls, comprehensions) are preserved by
  refusing to drop assignments whose RHS contains a Call.
"""
from __future__ import annotations

import ast
from typing import List, Set, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


def _rhs_has_side_effect(node: ast.AST) -> bool:
    """Conservative: a Call anywhere in RHS may mutate global state."""
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            return True
    return False


def _collect_loaded(func: ast.AST) -> Set[str]:
    loaded: Set[str] = set()
    for child in ast.walk(func):
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            loaded.add(child.id)
    return loaded


def _assign_target(stmt: ast.AST) -> str:
    """Return the lone target name, or '' for shapes we don't handle."""
    if isinstance(stmt, ast.Assign):
        if (len(stmt.targets) == 1
                and isinstance(stmt.targets[0], ast.Name)):
            return stmt.targets[0].id
    if isinstance(stmt, (ast.AnnAssign, ast.AugAssign)):
        if isinstance(stmt.target, ast.Name):
            return stmt.target.id
    return ""


class UnusedVarRemover(BaseTransform):
    """Drops dead local assignments in function bodies. CWE-563."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for func in ast.walk(tree):
            if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            param_names = {a.arg for a in func.args.args + func.args.kwonlyargs}
            if func.args.vararg:
                param_names.add(func.args.vararg.arg)
            if func.args.kwarg:
                param_names.add(func.args.kwarg.arg)

            loaded = _collect_loaded(func)

            for parent in ast.walk(func):
                block = getattr(parent, "body", None)
                if not isinstance(block, list):
                    continue
                kept: List[ast.AST] = []
                for stmt in block:
                    name = _assign_target(stmt)
                    is_unused = (
                        bool(name)
                        and name not in loaded
                        and name not in param_names
                        and not name.startswith("_")
                        and not _rhs_has_side_effect(
                            stmt.value if hasattr(stmt, "value") and stmt.value else stmt
                        )
                    )
                    if is_unused:
                        line = getattr(stmt, "lineno", 0)
                        results.append(TransformResult(
                            transform=self.name,
                            description=f"Removed unused local variable '{name}' (CWE-563)",
                            location=f"line {line}" if line else "module",
                            lines_removed=1,
                        ))
                        continue
                    kept.append(stmt)
                block[:] = kept

        ast.fix_missing_locations(tree)
        return tree, results
