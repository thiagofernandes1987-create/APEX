"""AutofixEngine — transforms package  (M5.2 + M8.1 + AFix+ FASE 8)."""
# ── Original 4 transforms (M5.2) ──────────────────────────────────────────────
from sensor_core.autofix.transforms.base import BaseTransform, TransformResult
from sensor_core.autofix.transforms.dead_code import DeadCodeRemover
from sensor_core.autofix.transforms.redundant_else import RedundantElseRemover
from sensor_core.autofix.transforms.boolean_simplify import BooleanSimplifier
from sensor_core.autofix.transforms.unused_imports import UnusedImportRemover

# ── M8.1 — 8 new transforms (#5-12) ──────────────────────────────────────────
from sensor_core.autofix.transforms.remove_mutable_default import MutableDefaultRemover
from sensor_core.autofix.transforms.replace_bare_except import BareExceptReplacer
from sensor_core.autofix.transforms.simplify_comparison import NoneComparisonSimplifier
from sensor_core.autofix.transforms.add_docstring import DocstringAdder
from sensor_core.autofix.transforms.add_context_manager import ContextManagerAdvisor
from sensor_core.autofix.transforms.extract_method import ExtractMethodAdvisor
from sensor_core.autofix.transforms.replace_string_concat_loop import StringConcatLoopAdvisor
from sensor_core.autofix.transforms.add_type_hints import TypeHintAdder

# ── AFix+ FASE 8 — 4 security transforms (#13-16) ─────────────────────────────
from sensor_core.autofix.transforms.replace_weak_hash import WeakHashReplacer
from sensor_core.autofix.transforms.replace_insecure_random import InsecureRandomReplacer
from sensor_core.autofix.transforms.add_loop_guard import LoopGuardAdvisor
from sensor_core.autofix.transforms.replace_format_string import FormatStringModernizer

__all__ = [
    # Base
    "BaseTransform",
    "TransformResult",
    # M5.2
    "DeadCodeRemover",
    "RedundantElseRemover",
    "BooleanSimplifier",
    "UnusedImportRemover",
    # M8.1
    "MutableDefaultRemover",
    "BareExceptReplacer",
    "NoneComparisonSimplifier",
    "DocstringAdder",
    "ContextManagerAdvisor",
    "ExtractMethodAdvisor",
    "StringConcatLoopAdvisor",
    "TypeHintAdder",
    # AFix+ FASE 8
    "WeakHashReplacer",
    "InsecureRandomReplacer",
    "LoopGuardAdvisor",
    "FormatStringModernizer",
]
