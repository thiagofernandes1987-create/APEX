"""
AutofixEngine — MutableDefaultRemover  (M8.1, transform #5)
=============================================================
Replaces mutable default argument values with ``None`` and inserts a
guard statement at the top of the function body.

Before:
    def f(items=[]):
        items.append(1)

After:
    def f(items=None):
        if items is None:
            items = []
        items.append(1)

Safety constraints:
  - Only applies to *positional* args with mutable defaults
    (ast.List, ast.Dict, ast.Set, or a bare call to list()/dict()/set()).
  - kwonlyargs and posonlyargs with mutable defaults are also fixed.
  - Guard is inserted before any existing body statements.
  - Nested functions are each processed independently.
"""
from __future__ import annotations

import ast
from typing import List, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult


_MUTABLE_CALL_NAMES: frozenset = frozenset({"list", "dict", "set"})


def _is_mutable_default(node: ast.expr) -> bool:
    """Return True if *node* is a mutable default (literal or empty factory call)."""
    if isinstance(node, (ast.List, ast.Dict, ast.Set)):
        return True
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in _MUTABLE_CALL_NAMES
        and not node.args
        and not node.keywords
    ):
        return True
    return False


def _make_guard(arg_name: str, original_default: ast.expr) -> ast.If:
    """Build ``if <arg_name> is None: <arg_name> = <original_default>``."""
    guard = ast.If(
        test=ast.Compare(
            left=ast.Name(id=arg_name, ctx=ast.Load()),
            ops=[ast.Is()],
            comparators=[ast.Constant(value=None)],
        ),
        body=[
            ast.Assign(
                targets=[ast.Name(id=arg_name, ctx=ast.Store())],
                value=original_default,
                lineno=0,
                col_offset=0,
            )
        ],
        orelse=[],
    )
    return guard


def _process_args(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
    results: List[TransformResult],
    transform_name: str,
) -> List[ast.stmt]:
    """
    Walk the function's argument list and patch mutable defaults.
    Returns a list of guard If-statements to prepend to the body.
    """
    guards: List[ast.stmt] = []

    def _patch(args_list: List[ast.arg], defaults: List[ast.expr]) -> None:
        n_args     = len(args_list)
        n_defaults = len(defaults)
        offset     = n_args - n_defaults
        for i, default in enumerate(defaults):
            if not _is_mutable_default(default):
                continue
            arg = args_list[offset + i]
            guards.append(_make_guard(arg.arg, default))
            defaults[i] = ast.Constant(value=None)
            results.append(TransformResult(
                transform=transform_name,
                description=(
                    f"Replaced mutable default for '{arg.arg}' with None "
                    f"+ guard in '{fn_node.name}'"
                ),
                location=fn_node.name,
            ))

    _patch(fn_node.args.args,         fn_node.args.defaults)
    _patch(fn_node.args.posonlyargs,  fn_node.args.defaults)
    if fn_node.args.kwonlyargs:
        kw_defaults = [d for d in fn_node.args.kw_defaults if d is not None]
        _patch(fn_node.args.kwonlyargs, kw_defaults)

    return guards


class MutableDefaultRemover(BaseTransform):
    """
    Replaces mutable default arguments (``=[]``, ``={}``, ``=set()``)
    with ``=None`` and inserts a guard statement in the function body.
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

            guards = _process_args(node, results, self.name)
            if guards:
                node.body = guards + node.body

        ast.fix_missing_locations(tree)
        return tree, results
