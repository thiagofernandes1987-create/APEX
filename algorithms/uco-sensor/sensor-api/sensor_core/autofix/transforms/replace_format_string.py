"""
AutofixEngine — FormatStringModernizer  (AFix+ FASE 8, transform #16)
=====================================================================
Flags old-style ``%`` string formatting on string literals and recommends
f-strings or ``str.format``.

Before:
    msg = "Hello %s, you are %d" % (name, age)

Recommended:
    msg = f"Hello {name}, you are {age}"

Advisory only
-------------
Mechanically rewriting ``%`` formatting into an f-string is error-prone
(format-spec translation, tuple vs single-arg, ``%%`` escapes, mapping
forms), so this transform does **not** mutate the tree.  It records a
recommendation and leaves the code valid and unchanged.

Detection
---------
A ``BinOp`` with the ``Mod`` operator whose **left** operand is a string
constant containing a printf-style conversion (``%s``, ``%d``, ``%r``,
``%f``, ``%x``, …).  A bare ``%`` with no conversion specifier (e.g. a
literal percent in a non-format string) is ignored.
"""
from __future__ import annotations

import ast
import re
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

# printf-style conversion specifier (excludes the literal "%%")
_CONV = re.compile(r"%[-+ #0]*\d*(?:\.\d+)?[sdrfeigxXoc]")


class FormatStringModernizer(BaseTransform):
    """Advises replacing ``"..." % args`` with an f-string / str.format."""

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results: List[TransformResult] = []

        for node in ast.walk(tree):
            if not isinstance(node, ast.BinOp):
                continue
            if not isinstance(node.op, ast.Mod):
                continue
            left = node.left
            if not (isinstance(left, ast.Constant) and isinstance(left.value, str)):
                continue
            if not _CONV.search(left.value):
                continue

            line = getattr(node, "lineno", 0)
            results.append(TransformResult(
                transform=self.name,
                description=(
                    "Old-style '%' string formatting — prefer an f-string or "
                    "str.format() for readability and safety [ADVISORY]"
                ),
                location=f"line {line}" if line else "module",
            ))

        # Advisory: never mutate the tree.
        return tree, results
