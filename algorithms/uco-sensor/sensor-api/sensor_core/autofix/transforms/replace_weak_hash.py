"""
AutofixEngine — WeakHashReplacer  (AFix+ FASE 8, transform #13)
================================================================
Rewrites weak cryptographic hash constructors to ``sha256``.

Before:
    import hashlib
    digest = hashlib.md5(data).hexdigest()
    other  = hashlib.sha1(payload).hexdigest()

After:
    import hashlib
    digest = hashlib.sha256(data).hexdigest()
    other  = hashlib.sha256(payload).hexdigest()

Weak hashes (MD5, SHA-1) are vulnerable to collision attacks and must not
be used for integrity or signature purposes (CWE-327 / CWE-328).

Safety constraints
------------------
- Only rewrites attribute calls on the ``hashlib`` module
  (``hashlib.md5`` / ``hashlib.sha1``).  A bare ``md5(...)`` is left
  untouched because its provenance is unknown.
- ``hashlib.new("md5")`` string-argument form is rewritten too:
  the literal ``"md5"`` / ``"sha1"`` becomes ``"sha256"``.
- The number and order of arguments is preserved exactly.
- Never touches non-hashlib code.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_WEAK = {"md5", "sha1"}
_STRONG = "sha256"


class WeakHashReplacer(BaseTransform):
    """Replaces ``hashlib.md5`` / ``hashlib.sha1`` with ``hashlib.sha256``."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func

            # Form 1: hashlib.md5(...) / hashlib.sha1(...)
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "hashlib"
                and func.attr in _WEAK
            ):
                weak = func.attr
                func.attr = _STRONG
                line = getattr(node, "lineno", 0)
                results.append(TransformResult(
                    transform=self.name,
                    description=f"Replaced 'hashlib.{weak}' with 'hashlib.{_STRONG}' (CWE-327)",
                    location=f"line {line}" if line else "module",
                ))
                continue

            # Form 2: hashlib.new("md5") / hashlib.new("sha1")
            if (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "hashlib"
                and func.attr == "new"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
                and node.args[0].value.lower() in _WEAK
            ):
                weak = node.args[0].value.lower()
                node.args[0] = ast.Constant(value=_STRONG)
                line = getattr(node, "lineno", 0)
                results.append(TransformResult(
                    transform=self.name,
                    description=f"Replaced hashlib.new('{weak}') with hashlib.new('{_STRONG}') (CWE-327)",
                    location=f"line {line}" if line else "module",
                ))

        ast.fix_missing_locations(tree)
        return tree, results
