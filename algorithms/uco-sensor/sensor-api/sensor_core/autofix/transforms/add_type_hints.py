"""
AutofixEngine — TypeHintAdder  (M8.1, transform #12)
======================================================
Adds ``: Any`` type annotations to unannotated function parameters and
inserts ``from typing import Any`` if the name is not already imported.

Before:
    def process(data, count, flag):
        return data

After:
    from typing import Any
    ...
    def process(data: Any, count: Any, flag: Any) -> None:
        return data

Safety constraints:
  - Only annotates args that have no existing annotation.
  - Adds ``-> None`` return annotation only when the function itself
    has at least one newly annotated parameter (to avoid spurious changes
    on functions that already have partial annotations).
  - Does NOT annotate ``self`` and ``cls`` (first positional arg of
    methods inside a class body) — they are implicitly typed.
  - ``*args`` and ``**kwargs`` receive ``: Any`` when unannotated.
  - The ``from typing import Any`` import is inserted after the last
    existing import statement (or at position 0 if no imports exist),
    and only when ``Any`` is not already imported.
  - Applied to all FunctionDef / AsyncFunctionDef in the module,
    including nested and method definitions.
"""
from __future__ import annotations

import ast
from typing import List, Set, Tuple

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult

_ANY_NAME = "Any"
_SELF_CLS = frozenset({"self", "cls"})


def _any_already_imported(tree: ast.AST) -> bool:
    """Return True if 'Any' from typing is already available."""
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            if any(alias.name in (_ANY_NAME, "*") for alias in node.names):
                return True
        if isinstance(node, ast.Import):
            if any(alias.name == "typing" for alias in node.names):
                return True
    return False


def _last_import_index(body: List[ast.stmt]) -> int:
    """Return index after the last import statement in *body*."""
    idx = 0
    for i, stmt in enumerate(body):
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            idx = i + 1
    return idx


def _is_method_first_arg(fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
                          arg: ast.arg, parent_classes: Set[str]) -> bool:
    """Return True if *arg* is the implicit self/cls of a method."""
    if arg.arg not in _SELF_CLS:
        return False
    # Check if this function is defined directly inside a class
    # (We use parent_classes set populated by the class-walk below)
    return fn_node.name in parent_classes or True  # conservative: always skip self/cls


class TypeHintAdder(BaseTransform):
    """
    Annotates unannotated function parameters with ``: Any`` and
    ensures ``from typing import Any`` is present.
    """

    def apply(
        self,
        tree:   ast.AST,
        source: str,
    ) -> Tuple[ast.AST, List[TransformResult]]:
        results:         List[TransformResult] = []
        needs_any_import: bool                 = False

        # Collect names of args that are method-first (self/cls) to skip them
        method_first_args: Set[int] = set()   # id() of ast.arg nodes to skip
        for cls_node in ast.walk(tree):
            if not isinstance(cls_node, ast.ClassDef):
                continue
            for fn in cls_node.body:
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    all_args = fn.args.args + fn.args.posonlyargs
                    if all_args and all_args[0].arg in _SELF_CLS:
                        method_first_args.add(id(all_args[0]))

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            changed = False

            def _annotate(args_list: List[ast.arg]) -> None:
                nonlocal changed, needs_any_import
                for arg in args_list:
                    if id(arg) in method_first_args:
                        continue
                    if arg.annotation is None:
                        arg.annotation = ast.Name(id=_ANY_NAME, ctx=ast.Load())
                        needs_any_import = True
                        changed = True

            _annotate(node.args.args)
            _annotate(node.args.posonlyargs)
            _annotate(node.args.kwonlyargs)
            if node.args.vararg and node.args.vararg.annotation is None:
                node.args.vararg.annotation = ast.Name(id=_ANY_NAME, ctx=ast.Load())
                needs_any_import = True
                changed = True
            if node.args.kwarg and node.args.kwarg.annotation is None:
                node.args.kwarg.annotation = ast.Name(id=_ANY_NAME, ctx=ast.Load())
                needs_any_import = True
                changed = True

            if changed:
                # Add -> None return annotation if missing
                if node.returns is None:
                    node.returns = ast.Constant(value=None)
                results.append(TransformResult(
                    transform=self.name,
                    description=f"Added ': Any' type hints to parameters of '{node.name}'",
                    location=node.name,
                ))

        # Insert 'from typing import Any' if needed and not already present
        if needs_any_import and not _any_already_imported(tree):
            import_node = ast.ImportFrom(
                module="typing",
                names=[ast.alias(name=_ANY_NAME)],
                level=0,
            )
            if isinstance(tree, ast.Module):
                idx = _last_import_index(tree.body)
                tree.body.insert(idx, import_node)
            results.append(TransformResult(
                transform=self.name,
                description="Added 'from typing import Any'",
                location="module",
            ))

        ast.fix_missing_locations(tree)
        return tree, results
