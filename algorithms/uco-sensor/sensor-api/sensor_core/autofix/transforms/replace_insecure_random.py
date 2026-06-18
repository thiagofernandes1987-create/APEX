"""
AutofixEngine — InsecureRandomReplacer  (AFix+ FASE 8, transform #14)
=====================================================================
Hardens insecure ``random`` usage for security-sensitive code.

Two behaviours
--------------
1. **Rewrite** (safe, 1:1): ``random.choice(seq)`` → ``secrets.choice(seq)``
   and ``import secrets`` is injected if absent.  ``secrets.choice`` has the
   same signature and is cryptographically secure (CWE-330).

2. **Advisory** (no rewrite): ``random.random()``, ``random.randint()``,
   ``random.randrange()`` have no drop-in ``secrets`` equivalent, so the
   transform records a recommendation without mutating the call (preserving
   valid, runnable code).

Safety constraints
------------------
- Only attribute calls on the ``random`` module are considered; a bare
  ``choice(...)`` of unknown provenance is left alone.
- ``import secrets`` is inserted after the last existing import (or at the
  top of the module) and only when at least one ``random.choice`` rewrite
  actually happened and ``secrets`` is not already imported.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

# random.* calls that have no clean secrets equivalent → advisory only
_ADVISORY = {"random", "randint", "randrange", "uniform", "getrandbits", "sample", "shuffle"}


def _secrets_already_imported(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == "secrets" for alias in node.names):
                return True
    return False


def _last_import_index(body: List[ast.stmt]) -> int:
    idx = 0
    for i, stmt in enumerate(body):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            idx = i + 1
    return idx


class InsecureRandomReplacer(BaseTransform):
    """Rewrites ``random.choice`` → ``secrets.choice``; advises on the rest."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []
        rewrote_choice = False

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "random"
            ):
                continue

            line = getattr(node, "lineno", 0)
            loc = f"line {line}" if line else "module"

            if func.attr == "choice":
                # Safe 1:1 rewrite to secrets.choice
                func.value = ast.Name(id="secrets", ctx=ast.Load())
                rewrote_choice = True
                results.append(TransformResult(
                    transform=self.name,
                    description="Replaced 'random.choice' with 'secrets.choice' (CWE-330)",
                    location=loc,
                ))
            elif func.attr in _ADVISORY:
                # Advisory only — no safe drop-in equivalent
                results.append(TransformResult(
                    transform=self.name,
                    description=(
                        f"Insecure 'random.{func.attr}' in possibly security-sensitive "
                        f"context — consider 'secrets' module (CWE-330) [ADVISORY]"
                    ),
                    location=loc,
                ))

        # Inject `import secrets` if we rewrote a choice and it's not imported
        if rewrote_choice and isinstance(tree, ast.Module) and not _secrets_already_imported(tree):
            idx = _last_import_index(tree.body)
            tree.body.insert(idx, ast.Import(names=[ast.alias(name="secrets", asname=None)]))

        ast.fix_missing_locations(tree)
        return tree, results
