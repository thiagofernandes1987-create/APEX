"""
UCO-Sensor — AutofixEngine  (M5.2 + M8.1)
============================================
Orchestrates a pipeline of AST-based code transforms to automatically
reduce code quality debt (Hamiltonian, cyclomatic complexity, dead code).

Pipeline
--------
1. Parse source → AST.
2. Apply each enabled transform in order.
3. Unparse the (possibly mutated) AST back to source.
4. Validate the result compiles correctly.
5. Return ``AutofixResult`` with before/after source, applied transforms,
   and whether the output is valid Python.

Available transforms (applied in this order by default):
  1. UnusedImportRemover       — removes provably unused imports
  2. BooleanSimplifier         — x==True→x, x==False→not x, etc.
  3. RedundantElseRemover      — converts if/else with terminating if to guard clauses
  4. DeadCodeRemover           — strips unreachable statements after return/raise
  5. MutableDefaultRemover     — def f(x=[]) → def f(x=None) + guard  [M8.1]
  6. BareExceptReplacer        — except: → except Exception as e:       [M8.1]
  7. NoneComparisonSimplifier  — x==None → x is None                   [M8.1]
  8. DocstringAdder            — placeholder docstring for public fns    [M8.1]
  9. ContextManagerAdvisor     — flags open() outside with (suggestion) [M8.1]
  10. ExtractMethodAdvisor     — flags LOC>50/CC>10 (suggestion)        [M8.1]
  11. StringConcatLoopAdvisor  — flags s+=x in loop (suggestion)        [M8.1]
  12. TypeHintAdder            — adds : Any annotations + typing import  [M8.1]

Usage
-----
    from sensor_core.autofix.engine import AutofixEngine

    engine = AutofixEngine()
    result = engine.apply(source_code)

    if result.is_valid_python:
        print(result.fixed_source)
    for tr in result.transforms_applied:
        print(tr.description)
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from sensor_core.autofix.transforms.base import BaseTransform, TransformResult
from sensor_core.autofix.transforms.unused_imports import UnusedImportRemover
from sensor_core.autofix.transforms.dead_code import DeadCodeRemover
from sensor_core.autofix.transforms.redundant_else import RedundantElseRemover
from sensor_core.autofix.transforms.boolean_simplify import BooleanSimplifier
# M8.1 — new transforms #5-12
from sensor_core.autofix.transforms.remove_mutable_default import MutableDefaultRemover
from sensor_core.autofix.transforms.replace_bare_except import BareExceptReplacer
from sensor_core.autofix.transforms.simplify_comparison import NoneComparisonSimplifier
from sensor_core.autofix.transforms.add_docstring import DocstringAdder
from sensor_core.autofix.transforms.add_context_manager import ContextManagerAdvisor
from sensor_core.autofix.transforms.extract_method import ExtractMethodAdvisor
from sensor_core.autofix.transforms.replace_string_concat_loop import StringConcatLoopAdvisor
from sensor_core.autofix.transforms.add_type_hints import TypeHintAdder


# ── AutofixResult ─────────────────────────────────────────────────────────────

@dataclass
class AutofixResult:
    """
    Result of running the AutofixEngine on a single source string.

    Attributes
    ----------
    original_source : str
        The source code as received.
    fixed_source : str
        The source after all transforms were applied.  Equals
        ``original_source`` when nothing changed or when the parse failed.
    transforms_applied : list[TransformResult]
        Every individual change made, in application order.
    total_lines_removed : int
        Sum of ``lines_removed`` across all TransformResult entries.
    is_valid_python : bool
        True if ``fixed_source`` compiles without error.
    parse_error : str | None
        If the input could not be parsed, contains the error message.
    changed : bool
        Convenience: True when fixed_source != original_source.
    """
    original_source:     str
    fixed_source:        str
    transforms_applied:  List[TransformResult] = field(default_factory=list)
    total_lines_removed: int  = 0
    is_valid_python:     bool = True
    parse_error:         Optional[str] = None

    @property
    def changed(self) -> bool:
        return self.fixed_source != self.original_source

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_source":     self.original_source,
            "fixed_source":        self.fixed_source,
            "transforms_applied":  [
                {
                    "transform":     t.transform,
                    "description":   t.description,
                    "location":      t.location,
                    "lines_removed": t.lines_removed,
                }
                for t in self.transforms_applied
            ],
            "total_lines_removed": self.total_lines_removed,
            "is_valid_python":     self.is_valid_python,
            "parse_error":         self.parse_error,
            "changed":             self.changed,
        }


# ── Default pipeline ──────────────────────────────────────────────────────────

_DEFAULT_PIPELINE: List[Type[BaseTransform]] = [
    UnusedImportRemover,          # 1.  remove dead imports first (no AST deps)
    BooleanSimplifier,            # 2.  simplify conditions (may expose guard patterns)
    RedundantElseRemover,         # 3.  flatten else-after-return (creates new terminators)
    DeadCodeRemover,              # 4.  remove unreachable code (catches code after hoisted returns)
    MutableDefaultRemover,        # 5.  replace mutable defaults with None + guard  [M8.1]
    BareExceptReplacer,           # 6.  bare except: → except Exception as e:       [M8.1]
    NoneComparisonSimplifier,     # 7.  == None → is None                           [M8.1]
    DocstringAdder,               # 8.  placeholder docstring for public fns         [M8.1]
    ContextManagerAdvisor,        # 9.  open() outside with (suggestion)            [M8.1]
    ExtractMethodAdvisor,         # 10. LOC>50/CC>10 refactoring hint (suggestion)  [M8.1]
    StringConcatLoopAdvisor,      # 11. s+=x in loop → list+join (suggestion)       [M8.1]
    TypeHintAdder,                # 12. add : Any annotations + import              [M8.1]
]


# ── AutofixEngine ─────────────────────────────────────────────────────────────

class AutofixEngine:
    """
    Applies a configurable pipeline of AST transforms to Python source code.

    Parameters
    ----------
    transforms : list[type[BaseTransform]] | None
        Transform classes to use (in order).  ``None`` → default pipeline.
    """

    def __init__(
        self,
        transforms: Optional[List[Type[BaseTransform]]] = None,
    ) -> None:
        pipeline = transforms if transforms is not None else _DEFAULT_PIPELINE
        self._transforms: List[BaseTransform] = [cls() for cls in pipeline]

    # ── Public API ────────────────────────────────────────────────────────────

    def apply(self, source: str) -> AutofixResult:
        """
        Parse *source*, run all transforms, unparse, and validate.

        Parameters
        ----------
        source : str
            Python source code string.

        Returns
        -------
        AutofixResult
        """
        # ── 1. Parse ─────────────────────────────────────────────────────────
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return AutofixResult(
                original_source=source,
                fixed_source=source,
                is_valid_python=False,
                parse_error=str(exc),
            )

        # ── 2. Apply transforms ───────────────────────────────────────────────
        all_results: List[TransformResult] = []
        for transform in self._transforms:
            try:
                tree, results = transform.apply(tree, source)
                all_results.extend(results)
            except Exception:
                # A transform bug must never break the pipeline
                pass

        # ── 3. Unparse ────────────────────────────────────────────────────────
        try:
            fixed = ast.unparse(tree)
        except Exception:
            # Unparse failure: return original unchanged
            return AutofixResult(
                original_source=source,
                fixed_source=source,
                transforms_applied=all_results,
                is_valid_python=True,
            )

        # ── 4. Validate ───────────────────────────────────────────────────────
        valid = True
        parse_err: Optional[str] = None
        try:
            compile(fixed, "<autofix>", "exec")
        except SyntaxError as exc:
            valid = False
            parse_err = str(exc)
            fixed = source  # revert to original if broken

        total_removed = sum(r.lines_removed for r in all_results)

        return AutofixResult(
            original_source=source,
            fixed_source=fixed,
            transforms_applied=all_results,
            total_lines_removed=total_removed,
            is_valid_python=valid,
            parse_error=parse_err,
        )

    def apply_named(
        self,
        source:     str,
        transform_names: List[str],
    ) -> AutofixResult:
        """
        Apply only the transforms whose class names are in *transform_names*.

        Useful for targeted fixes from the /repair endpoint.
        """
        selected = [
            t for t in self._transforms
            if t.name in transform_names
        ]
        engine = AutofixEngine(transforms=[type(t) for t in selected])
        return engine.apply(source)
