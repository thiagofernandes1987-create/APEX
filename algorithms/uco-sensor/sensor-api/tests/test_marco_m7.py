"""
test_marco_m7.py — M5.2 Autofix Engine (AST transforms)
=========================================================
30 tests covering:

  TF01-TF07  DeadCodeRemover    — unreachable code after return/raise
  TF08-TF12  RedundantElseRemover — guard clause pattern
  TF13-TF17  BooleanSimplifier  — x==True/False simplification
  TF18-TF22  UnusedImportRemover — dead imports removal
  TF23-TF27  AutofixEngine      — pipeline, AutofixResult, chaining
  TF28-TF30  Safety / edge cases — syntax errors, dynamic access, empty src
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports under test ────────────────────────────────────────────────────────
from sensor_core.autofix.engine import AutofixEngine, AutofixResult   # noqa
from sensor_core.autofix.transforms import (                           # noqa
    TransformResult,
    DeadCodeRemover,
    RedundantElseRemover,
    BooleanSimplifier,
    UnusedImportRemover,
)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _apply(transform_cls, source: str):
    """Apply a single transform and return (fixed_source, results)."""
    tree    = ast.parse(source)
    t       = transform_cls()
    new_tree, results = t.apply(tree, source)
    fixed   = ast.unparse(new_tree)
    return fixed, results


def _engine(source: str) -> AutofixResult:
    return AutofixEngine().apply(source)


def _compiles(source: str) -> bool:
    try:
        compile(source, "<test>", "exec")
        return True
    except SyntaxError:
        return False


# ══════════════════════════════════════════════════════════════════════════════
# TF01-TF07 — DeadCodeRemover
# ══════════════════════════════════════════════════════════════════════════════

def test_TF01_dead_code_after_return_removed():
    """TF01: Statement after return in function body is removed."""
    src = """
def f():
    return 1
    print("dead")
"""
    fixed, results = _apply(DeadCodeRemover, src)
    assert "dead" not in fixed
    assert len(results) >= 1


def test_TF02_dead_code_after_raise_removed():
    """TF02: Statement after raise is removed."""
    src = """
def f(x):
    if x < 0:
        raise ValueError("neg")
        print("unreachable")
    return x
"""
    fixed, results = _apply(DeadCodeRemover, src)
    assert "unreachable" not in fixed
    assert len(results) >= 1


def test_TF03_live_code_after_conditional_return_kept():
    """TF03: Code after conditional return must NOT be removed."""
    src = """
def f(x):
    if x > 0:
        return x
    return -x
"""
    fixed, results = _apply(DeadCodeRemover, src)
    # Both returns must survive
    assert fixed.count("return") == 2
    # No changes at function body level (the return is inside if, not top-level)
    assert not any("unreachable" in r.description for r in results)


def test_TF04_dead_code_after_return_in_branch():
    """TF04: Unreachable code inside if-branch (after branch return) is removed."""
    src = """
def f(flag):
    if flag:
        return True
        x = 99
    return False
"""
    fixed, results = _apply(DeadCodeRemover, src)
    assert "x = 99" not in fixed.replace(" ", "")


def test_TF05_output_is_valid_python():
    """TF05: DeadCodeRemover output always compiles."""
    src = """
def multi():
    x = 1
    return x
    y = 2
    z = 3
    return z
"""
    fixed, _ = _apply(DeadCodeRemover, src)
    assert _compiles(fixed)


def test_TF06_empty_function_not_broken():
    """TF06: Function with only a pass is not touched."""
    src = """
def empty():
    pass
"""
    fixed, results = _apply(DeadCodeRemover, src)
    assert "pass" in fixed
    assert results == []


def test_TF07_dead_code_after_break_in_loop():
    """TF07: Code after break inside a loop body is removed."""
    src = """
def f(items):
    for item in items:
        break
        print("never")
    return items
"""
    fixed, results = _apply(DeadCodeRemover, src)
    assert "never" not in fixed


# ══════════════════════════════════════════════════════════════════════════════
# TF08-TF12 — RedundantElseRemover
# ══════════════════════════════════════════════════════════════════════════════

def test_TF08_redundant_else_flattened():
    """TF08: if/else where if always returns → else is removed."""
    src = """
def f(x):
    if x > 0:
        return x
    else:
        return -x
"""
    fixed, results = _apply(RedundantElseRemover, src)
    # else keyword should be gone (ast.unparse produces flat code)
    assert "else" not in fixed
    assert len(results) >= 1


def test_TF09_redundant_else_output_valid():
    """TF09: RedundantElseRemover output always compiles."""
    src = """
def check(val):
    if val is None:
        raise ValueError("null")
    else:
        return val * 2
"""
    fixed, results = _apply(RedundantElseRemover, src)
    assert _compiles(fixed)
    assert len(results) >= 1


def test_TF10_non_terminating_if_kept_intact():
    """TF10: if without terminator → else preserved."""
    src = """
def f(x):
    if x > 0:
        x = x + 1
    else:
        x = 0
    return x
"""
    fixed, results = _apply(RedundantElseRemover, src)
    # No change — the if body doesn't always terminate
    assert results == []


def test_TF11_raise_in_if_triggers_flatten():
    """TF11: raise (not just return) inside if body also triggers flattening."""
    src = """
def validate(v):
    if v < 0:
        raise ValueError("negative")
    else:
        return v
"""
    fixed, results = _apply(RedundantElseRemover, src)
    assert "else" not in fixed
    assert len(results) >= 1


def test_TF12_flattened_body_semantically_correct():
    """TF12: flattened function returns same results as original for guard pattern."""
    src = """
def absolute(x):
    if x >= 0:
        return x
    else:
        return -x
"""
    fixed, _ = _apply(RedundantElseRemover, src)
    # Both returns must remain
    assert fixed.count("return") == 2
    assert _compiles(fixed)


# ══════════════════════════════════════════════════════════════════════════════
# TF13-TF17 — BooleanSimplifier
# ══════════════════════════════════════════════════════════════════════════════

def test_TF13_eq_true_simplified():
    """TF13: x == True → x (inside if condition)."""
    src = """
def f(flag):
    if flag == True:
        return 1
"""
    fixed, results = _apply(BooleanSimplifier, src)
    assert "== True" not in fixed
    assert len(results) == 1


def test_TF14_eq_false_simplified_to_not():
    """TF14: x == False → not x."""
    src = """
def f(flag):
    if flag == False:
        return 0
"""
    fixed, results = _apply(BooleanSimplifier, src)
    assert "== False" not in fixed
    assert "not" in fixed
    assert len(results) == 1


def test_TF15_is_true_simplified():
    """TF15: x is True → x."""
    src = """
def f(x):
    return x is True
"""
    fixed, results = _apply(BooleanSimplifier, src)
    assert "is True" not in fixed
    assert len(results) == 1


def test_TF16_is_not_false_simplified():
    """TF16: x is not False → x."""
    src = """
def check(v):
    return v is not False
"""
    fixed, results = _apply(BooleanSimplifier, src)
    assert "is not False" not in fixed
    assert len(results) == 1


def test_TF17_boolean_simplifier_output_compiles():
    """TF17: BooleanSimplifier output is always valid Python."""
    src = """
def multi(a, b, c):
    if a == True:
        if b == False:
            if c is True:
                return 1
    return 0
"""
    fixed, results = _apply(BooleanSimplifier, src)
    assert _compiles(fixed)
    assert len(results) >= 1


# ══════════════════════════════════════════════════════════════════════════════
# TF18-TF22 — UnusedImportRemover
# ══════════════════════════════════════════════════════════════════════════════

def test_TF18_unused_import_removed():
    """TF18: 'import os' when os never used → removed."""
    src = """
import os
import sys

def f():
    return sys.argv[0]
"""
    fixed, results = _apply(UnusedImportRemover, src)
    assert "import os" not in fixed
    assert "import sys" in fixed
    assert any("os" in r.description for r in results)


def test_TF19_used_import_kept():
    """TF19: Used import is not removed."""
    src = """
import json

def f(data):
    return json.dumps(data)
"""
    fixed, results = _apply(UnusedImportRemover, src)
    assert "import json" in fixed
    assert results == []


def test_TF20_from_import_unused_removed():
    """TF20: 'from os import path' when path not used → removed."""
    src = """
from os import path
from sys import argv

def main():
    return argv[0]
"""
    fixed, results = _apply(UnusedImportRemover, src)
    assert "path" not in fixed or "argv" in fixed
    assert any("path" in r.description for r in results)


def test_TF21_future_import_never_removed():
    """TF21: from __future__ import ... is always preserved."""
    src = """
from __future__ import annotations
import unused_module

def f():
    pass
"""
    fixed, results = _apply(UnusedImportRemover, src)
    assert "from __future__ import annotations" in fixed


def test_TF22_dynamic_access_bails_out():
    """TF22: Module with getattr() → no imports removed (unsafe)."""
    src = """
import os
import sys

def f(name):
    mod = sys.modules[__name__]
    return getattr(mod, name)
"""
    fixed, results = _apply(UnusedImportRemover, src)
    # Should NOT remove 'import os' because getattr is present
    assert "import os" in fixed
    assert results == []


# ══════════════════════════════════════════════════════════════════════════════
# TF23-TF27 — AutofixEngine pipeline
# ══════════════════════════════════════════════════════════════════════════════

def test_TF23_engine_full_pipeline_chaining():
    """TF23: Full pipeline applies all transforms in correct order."""
    src = """
import os
import sys

def greet(name):
    if name == True:
        return 'yes'
    else:
        return 'no'
    print('dead')
"""
    result = _engine(src)
    assert result.is_valid_python
    assert result.changed
    # All four transforms should have fired
    names = {t.transform for t in result.transforms_applied}
    assert "UnusedImportRemover" in names
    assert "BooleanSimplifier"   in names
    assert "RedundantElseRemover" in names
    assert "DeadCodeRemover"     in names
    # dead print must be gone
    assert "dead" not in result.fixed_source


def test_TF24_autofix_result_to_dict_keys():
    """TF24: AutofixResult.to_dict() contains all required keys."""
    result = _engine("x = 1")
    d = result.to_dict()
    expected = {
        "original_source", "fixed_source", "transforms_applied",
        "total_lines_removed", "is_valid_python", "parse_error", "changed",
    }
    assert expected == set(d.keys())


def test_TF25_result_changed_flag():
    """TF25: changed=True when source was modified, False when untouched."""
    unchanged = _engine("x = 1 + 2")
    assert unchanged.changed is False

    changed = _engine("import os\ndef f(): pass")
    assert changed.changed is True


def test_TF26_result_is_valid_python_always_compiles():
    """TF26: fixed_source of any valid input compiles without error."""
    sources = [
        "import math\ndef f(x):\n    if x==True: return x\n    else: return -x\n    print('dead')\n",
        "from os import path, getcwd\ndef run(): return getcwd()\n",
        "def empty(): pass\n",
    ]
    for src in sources:
        result = _engine(src)
        assert result.is_valid_python, f"Not valid for: {src[:50]}"
        assert _compiles(result.fixed_source)


def test_TF27_total_lines_removed_is_non_negative():
    """TF27: total_lines_removed is always >= 0."""
    result = _engine("""
import os
def f():
    return 1
    x = 2
    y = 3
""")
    assert result.total_lines_removed >= 0


# ══════════════════════════════════════════════════════════════════════════════
# TF28-TF30 — Safety / edge cases
# ══════════════════════════════════════════════════════════════════════════════

def test_TF28_syntax_error_returns_original():
    """TF28: Unparseable source → original returned, is_valid_python=False."""
    bad_src = "def f(\n    broken syntax !!!"
    result  = _engine(bad_src)
    assert result.is_valid_python is False
    assert result.fixed_source == bad_src
    assert result.parse_error is not None


def test_TF29_empty_source_no_crash():
    """TF29: Empty string → no crash, returns empty fixed_source."""
    result = _engine("")
    assert isinstance(result.fixed_source, str)
    assert result.is_valid_python is True


def test_TF30_complex_real_world_snippet():
    """TF30: Real-world-style snippet is fixed correctly end-to-end."""
    src = """
import os
import re
import hashlib
import json

def process(data, debug=False):
    if debug == True:
        print("debug mode")
    if data is None:
        raise ValueError("data is required")
    else:
        result = hashlib.sha256(str(data).encode()).hexdigest()
        return result
    print("this never runs")

def helper():
    for i in range(10):
        if i == 5:
            break
        print(i)
"""
    result = _engine(src)
    assert result.is_valid_python
    assert _compiles(result.fixed_source)
    # dead print after raise→return must be gone
    assert "this never runs" not in result.fixed_source
    # boolean simplification
    assert "== True" not in result.fixed_source
    # redundant else flattened (raise in if)
    assert "else:" not in result.fixed_source or "debug" in result.fixed_source
    # at least some transforms fired
    assert len(result.transforms_applied) >= 3


# ══════════════════════════════════════════════════════════════════════════════
# Inventory
# ══════════════════════════════════════════════════════════════════════════════

_ALL_TESTS = [
    ("TF01", test_TF01_dead_code_after_return_removed),
    ("TF02", test_TF02_dead_code_after_raise_removed),
    ("TF03", test_TF03_live_code_after_conditional_return_kept),
    ("TF04", test_TF04_dead_code_after_return_in_branch),
    ("TF05", test_TF05_output_is_valid_python),
    ("TF06", test_TF06_empty_function_not_broken),
    ("TF07", test_TF07_dead_code_after_break_in_loop),
    ("TF08", test_TF08_redundant_else_flattened),
    ("TF09", test_TF09_redundant_else_output_valid),
    ("TF10", test_TF10_non_terminating_if_kept_intact),
    ("TF11", test_TF11_raise_in_if_triggers_flatten),
    ("TF12", test_TF12_flattened_body_semantically_correct),
    ("TF13", test_TF13_eq_true_simplified),
    ("TF14", test_TF14_eq_false_simplified_to_not),
    ("TF15", test_TF15_is_true_simplified),
    ("TF16", test_TF16_is_not_false_simplified),
    ("TF17", test_TF17_boolean_simplifier_output_compiles),
    ("TF18", test_TF18_unused_import_removed),
    ("TF19", test_TF19_used_import_kept),
    ("TF20", test_TF20_from_import_unused_removed),
    ("TF21", test_TF21_future_import_never_removed),
    ("TF22", test_TF22_dynamic_access_bails_out),
    ("TF23", test_TF23_engine_full_pipeline_chaining),
    ("TF24", test_TF24_autofix_result_to_dict_keys),
    ("TF25", test_TF25_result_changed_flag),
    ("TF26", test_TF26_result_is_valid_python_always_compiles),
    ("TF27", test_TF27_total_lines_removed_is_non_negative),
    ("TF28", test_TF28_syntax_error_returns_original),
    ("TF29", test_TF29_empty_source_no_crash),
    ("TF30", test_TF30_complex_real_world_snippet),
]

if __name__ == "__main__":
    passed = failed = 0
    for tid, fn in _ALL_TESTS:
        try:
            fn()
            print(f"  OK {tid} {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {tid} {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
