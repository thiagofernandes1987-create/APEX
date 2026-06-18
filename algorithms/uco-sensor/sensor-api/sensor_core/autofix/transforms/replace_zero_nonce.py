"""
AutofixEngine — ZeroNonceReplacer  (Sprint D / SAST022)
=========================================================
Rewrites all-zero IV / nonce arguments on cipher constructors with
``os.urandom(N)`` of the same length.

Before:
    cipher = AES.new(key, AES.MODE_GCM, nonce=b'\\x00' * 12)
    cipher = AES.new(key, AES.MODE_CBC, b'\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00')

After:
    import os
    cipher = AES.new(key, AES.MODE_GCM, nonce=os.urandom(12))
    cipher = AES.new(key, AES.MODE_CBC, os.urandom(16))

A constant or all-zero IV/nonce defeats the IND-CPA goals of every AEAD
or block cipher (CWE-329 / OWASP A02).

Safety constraints
------------------
- Only rewrites the ``.new(...)`` constructor call where the module is
  a known cipher family (AES, Crypto.Cipher.AES, Cryptodome.Cipher.AES, etc.).
- Replaces the literal in either positional form (3rd arg) or keyword form
  (``iv=`` / ``nonce=`` / ``IV=`` / ``initial_value=``).
- Both ``b'\\x00' * N`` and a fully zero ``bytes`` constant are detected.
- A top-level ``import os`` statement is inserted at the top of the module
  if (and only if) at least one rewrite happens AND ``os`` is not already
  imported.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


_CIPHER_LAST_SEGMENTS = {"AES", "ChaCha20", "ChaCha20_Poly1305",
                         "Salsa20", "Blowfish"}
_NONCE_KEYWORDS = {"iv", "nonce", "IV", "initial_value"}


def _is_zero_bytes(node: ast.AST) -> Tuple[bool, int]:
    """
    Detect ``b'\\x00' * N`` or a literal bytes-of-zeros.

    Returns ``(is_zero, length)``.  Length is best-effort: 0 when unknown.
    """
    # Pattern 1: b"" or b"\x00\x00..."
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        return (all(b == 0 for b in node.value), len(node.value))

    # Pattern 2: b"\x00" * N
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
        left, right = node.left, node.right
        for lit, mul in ((left, right), (right, left)):
            if (
                isinstance(lit, ast.Constant)
                and isinstance(lit.value, bytes)
                and all(b == 0 for b in lit.value)
                and isinstance(mul, ast.Constant)
                and isinstance(mul.value, int)
            ):
                length = len(lit.value) * mul.value if lit.value else mul.value
                return (True, length)
    return (False, 0)


def _is_cipher_call(call: ast.Call) -> bool:
    """``X.new(...)`` where the final segment of X is a known cipher family."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr == "new"):
        return False
    # Walk up the attribute chain to find the immediate parent module name.
    parent = func.value
    if isinstance(parent, ast.Name):
        return parent.id in _CIPHER_LAST_SEGMENTS
    if isinstance(parent, ast.Attribute):
        return parent.attr in _CIPHER_LAST_SEGMENTS
    return False


def _os_urandom(length: int) -> ast.Call:
    """Construct ``os.urandom(N)``."""
    return ast.Call(
        func=ast.Attribute(
            value=ast.Name(id="os", ctx=ast.Load()),
            attr="urandom",
            ctx=ast.Load(),
        ),
        args=[ast.Constant(value=length if length > 0 else 16)],
        keywords=[],
    )


def _module_has_os_import(tree: ast.AST) -> bool:
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "os":
                    return True
    return False


class ZeroNonceReplacer(BaseTransform):
    """Replaces all-zero IV/nonce literals with ``os.urandom(N)``."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not _is_cipher_call(node):
                continue

            # Positional arg #3 — IV/nonce.
            if len(node.args) >= 3:
                is_zero, length = _is_zero_bytes(node.args[2])
                if is_zero:
                    node.args[2] = _os_urandom(length)
                    results.append(self._record(node, length, where="positional"))

            # Keyword arg ``iv=`` / ``nonce=`` / etc.
            for kw in node.keywords:
                if kw.arg in _NONCE_KEYWORDS:
                    is_zero, length = _is_zero_bytes(kw.value)
                    if is_zero:
                        kw.value = _os_urandom(length)
                        results.append(self._record(node, length, where=kw.arg))

        if results and isinstance(tree, ast.Module) and not _module_has_os_import(tree):
            tree.body.insert(0, ast.Import(names=[ast.alias(name="os", asname=None)]))

        ast.fix_missing_locations(tree)
        return tree, results

    def _record(self, node: ast.Call, length: int, *, where: str) -> TransformResult:
        line = getattr(node, "lineno", 0)
        return TransformResult(
            transform=self.name,
            description=(
                f"Replaced all-zero {where} with os.urandom({length}) "
                f"on cipher.new(...) (CWE-329)"
            ),
            location=f"line {line}" if line else "module",
        )
