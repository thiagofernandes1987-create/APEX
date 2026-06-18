"""
AutofixEngine — JWTVerifyEnabler  (Sprint D / SAST024)
========================================================
Rewrites JWT decode calls whose signature verification is disabled or
whose ``algorithms`` list contains ``"none"``.

Before:
    jwt.decode(token, key, verify=False)
    jwt.decode(token, key, options={"verify_signature": False})
    jwt.decode(token, key, algorithms=["none", "HS256"])

After:
    jwt.decode(token, key, verify=True)
    jwt.decode(token, key, options={"verify_signature": True})
    jwt.decode(token, key, algorithms=["HS256"])

These misconfigurations defeat JWT integrity entirely (CWE-347 / OWASP A02).

Safety constraints
------------------
- Touches only ``jwt.decode(...)`` or ``PyJWT.decode(...)``.
- Three forms handled, deterministic order:
    1. legacy ``verify=False`` flag → ``verify=True``
    2. ``options={"verify_signature": False}`` → flip the inner value
    3. ``algorithms=[..., "none", ...]`` → drop "none" entries (case-insensitive)
- Empty algorithm list after pruning is replaced with ``["HS256"]`` —
  a conservative default that still requires a signing key.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


_JWT_MODULES = {"jwt", "PyJWT"}


class JWTVerifyEnabler(BaseTransform):
    """Force JWT signature verification."""

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
            if not (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id in _JWT_MODULES
                and func.attr == "decode"
            ):
                continue

            changed_here = False
            for kw in node.keywords:
                # Form 1 — verify=False
                if (
                    kw.arg == "verify"
                    and isinstance(kw.value, ast.Constant)
                    and kw.value.value is False
                ):
                    kw.value = ast.Constant(value=True)
                    changed_here = True
                    results.append(self._record(node, "verify=False → True"))

                # Form 2 — options={"verify_signature": False}
                elif kw.arg == "options" and isinstance(kw.value, ast.Dict):
                    for i, (k, v) in enumerate(zip(kw.value.keys, kw.value.values)):
                        if (
                            isinstance(k, ast.Constant)
                            and k.value == "verify_signature"
                            and isinstance(v, ast.Constant)
                            and v.value is False
                        ):
                            kw.value.values[i] = ast.Constant(value=True)
                            changed_here = True
                            results.append(self._record(
                                node, "options['verify_signature']=False → True"
                            ))

                # Form 3 — algorithms=[..., "none", ...]
                elif kw.arg == "algorithms" and isinstance(kw.value, ast.List):
                    new_elts = []
                    dropped = 0
                    for elt in kw.value.elts:
                        if (
                            isinstance(elt, ast.Constant)
                            and isinstance(elt.value, str)
                            and elt.value.lower() == "none"
                        ):
                            dropped += 1
                            continue
                        new_elts.append(elt)
                    if dropped:
                        if not new_elts:
                            # Conservative default: still requires a signing key.
                            new_elts.append(ast.Constant(value="HS256"))
                        kw.value.elts = new_elts
                        changed_here = True
                        results.append(self._record(
                            node, f"algorithms: dropped {dropped} 'none' entries"
                        ))

            if changed_here:
                pass  # already recorded above

        ast.fix_missing_locations(tree)
        return tree, results

    def _record(self, node: ast.Call, detail: str) -> TransformResult:
        line = getattr(node, "lineno", 0)
        return TransformResult(
            transform=self.name,
            description=f"JWT decode hardened ({detail}) — CWE-347",
            location=f"line {line}" if line else "module",
        )
