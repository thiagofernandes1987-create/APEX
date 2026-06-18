"""
AutofixEngine — SSLVerifyEnabler  (Sprint D / SAST027)
========================================================
Rewrites disabled TLS certificate verification on the popular HTTP client
modules (``requests``, ``httpx``) to verify-enabled.

Before:
    requests.get("https://api.example.com", verify=False)

After:
    requests.get("https://api.example.com", verify=True)

Disabling certificate verification opens the door to MITM attacks
(CWE-295 / OWASP A07).

Safety constraints
------------------
- Only rewrites the literal ``verify=False`` keyword.  ``verify=<expr>``
  with any non-Constant or non-False value is left untouched — the rule's
  intent is ambiguous when verify is computed at runtime.
- Only rewrites calls whose function attribute belongs to a known HTTP
  client module (``requests`` or ``httpx``) and a known HTTP method.
- Number / order of other arguments is preserved.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_HTTP_MODULES = {"requests", "httpx"}
_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head",
                 "options", "request"}


class SSLVerifyEnabler(BaseTransform):
    """Replaces ``verify=False`` with ``verify=True`` on HTTP client calls."""

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
            if not isinstance(func, ast.Attribute):
                continue
            if not isinstance(func.value, ast.Name):
                continue
            if func.value.id not in _HTTP_MODULES:
                continue
            if func.attr not in _HTTP_METHODS:
                continue

            for kw in node.keywords:
                if (
                    kw.arg == "verify"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    kw.value = ast.Constant(value=True)
                    line = getattr(node, "lineno", 0)
                    results.append(TransformResult(
                        transform=self.name,
                        description=(
                            f"Enabled TLS verification on "
                            f"'{func.value.id}.{func.attr}' (CWE-295)"
                        ),
                        location=f"line {line}" if line else "module",
                    ))

        ast.fix_missing_locations(tree)
        return tree, results
