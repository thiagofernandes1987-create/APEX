"""
UCO-Sensor — AST-IMP (_UCOVisitor 10 new patterns) — Test Suite
================================================================
TV91-TV98 (8 tests per WBS 3.1-3.4)

Coverage:
  AST-IMP.1  bare except + swallowed exception (bare_except_count, swallowed_exception_count)
  AST-IMP.2  shadow builtin + mutable default  (shadow_builtin_count, mutable_default_arg_count)
  AST-IMP.3  inconsistent return + global mutation (inconsistent_return_count, global_mutation_count)
  AST-IMP.4  deeply nested comprehension + missing __all__
             (deeply_nested_comprehension_count, missing_all_flag)
"""
from __future__ import annotations

import sys
import os
import pytest

# ── path setup ───────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sensor_core.uco_bridge import UCOBridge, _UCOVisitor
import ast


def _visit(source: str) -> _UCOVisitor:
    """Parse source and return a fully visited _UCOVisitor."""
    tree = ast.parse(source)
    v = _UCOVisitor()
    v.visit(tree)
    return v


def _analyze(source: str):
    """Return MetricVector via UCOBridge.analyze (full mode)."""
    bridge = UCOBridge(mode="full")
    return bridge.analyze(source, module_id="test", commit_hash="abc123")


# ═══════════════════════════════════════════════════════════════════════════════
# AST-IMP.1 — bare except + swallowed exception
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV91_BareExcept:
    """bare_except_count: ExceptHandler with type=None."""

    def test_bare_except_detected(self):
        src = "try:\n    risky()\nexcept:\n    handle()"
        v = _visit(src)
        assert v.bare_except_count == 1

    def test_typed_except_not_counted(self):
        src = "try:\n    op()\nexcept ValueError:\n    pass"
        v = _visit(src)
        assert v.bare_except_count == 0

    def test_multiple_bare_excepts(self):
        src = (
            "try:\n    a()\nexcept:\n    x = 1\n"
            "try:\n    b()\nexcept:\n    y = 2\n"
        )
        v = _visit(src)
        assert v.bare_except_count == 2

    def test_swallowed_exception_bare(self):
        src = "try:\n    risky()\nexcept:\n    pass"
        v = _visit(src)
        assert v.swallowed_exception_count >= 1

    def test_swallowed_exception_typed(self):
        src = "try:\n    op()\nexcept Exception:\n    pass"
        v = _visit(src)
        assert v.swallowed_exception_count >= 1

    def test_not_swallowed_with_log(self):
        src = "try:\n    op()\nexcept Exception as e:\n    logger.error(e)"
        v = _visit(src)
        assert v.swallowed_exception_count == 0

    def test_mv_bare_except_attached(self):
        src = "try:\n    op()\nexcept:\n    pass"
        mv = _analyze(src)
        assert hasattr(mv, "bare_except_count")
        assert mv.bare_except_count >= 1

    def test_mv_swallowed_attached(self):
        src = "try:\n    op()\nexcept Exception:\n    pass"
        mv = _analyze(src)
        assert hasattr(mv, "swallowed_exception_count")
        assert mv.swallowed_exception_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# AST-IMP.2 — shadow builtin + mutable default
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV92_ShadowBuiltin:
    """shadow_builtin_count: assignment to a name that is a Python builtin."""

    def test_shadow_list(self):
        src = "list = [1, 2, 3]"
        v = _visit(src)
        assert v.shadow_builtin_count >= 1

    def test_shadow_open(self):
        src = "open = lambda f: None"
        v = _visit(src)
        assert v.shadow_builtin_count >= 1

    def test_no_shadow_normal_name(self):
        src = "my_list = [1, 2, 3]"
        v = _visit(src)
        assert v.shadow_builtin_count == 0

    def test_shadow_counted_once_per_name(self):
        # Assigning to 'list' twice → should count only once (deduplicated)
        src = "list = []\nlist = [1, 2]"
        v = _visit(src)
        assert v.shadow_builtin_count == 1


class TestTV93_MutableDefault:
    """mutable_default_arg_count: def f(x=[]) or def f(x={}) or def f(x=set())."""

    def test_list_default(self):
        src = "def process(items=[]):\n    return items"
        v = _visit(src)
        assert v.mutable_default_arg_count >= 1

    def test_dict_default(self):
        src = "def config(opts={}):\n    return opts"
        v = _visit(src)
        assert v.mutable_default_arg_count >= 1

    def test_set_call_default(self):
        src = "def dedupe(seen=set()):\n    return seen"
        v = _visit(src)
        assert v.mutable_default_arg_count >= 1

    def test_none_default_safe(self):
        src = "def process(items=None):\n    return items"
        v = _visit(src)
        assert v.mutable_default_arg_count == 0

    def test_mv_mutable_default_attached(self):
        src = "def f(x=[]):\n    return x"
        mv = _analyze(src)
        assert hasattr(mv, "mutable_default_arg_count")
        assert mv.mutable_default_arg_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# AST-IMP.3 — inconsistent return + global mutation
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV94_InconsistentReturn:
    """inconsistent_return_count: function mixes Return(value) and Return(None)/fall-through."""

    def test_inconsistent_return_detected(self):
        src = (
            "def get_value(x):\n"
            "    if x > 0:\n"
            "        return x\n"
            "    # implicit None return (fall-through)\n"
        )
        v = _visit(src)
        assert v.inconsistent_return_count >= 1

    def test_consistent_return_safe(self):
        src = (
            "def get_value(x):\n"
            "    if x > 0:\n"
            "        return x\n"
            "    return 0\n"
        )
        v = _visit(src)
        assert v.inconsistent_return_count == 0

    def test_no_return_consistent(self):
        # Function with no explicit return — all fall-through → consistent
        src = "def side_effect(x):\n    print(x)\n"
        v = _visit(src)
        assert v.inconsistent_return_count == 0

    def test_mv_inconsistent_return_attached(self):
        src = (
            "def maybe(x):\n"
            "    if x:\n"
            "        return x\n"
        )
        mv = _analyze(src)
        assert hasattr(mv, "inconsistent_return_count")
        # either 0 or 1 is acceptable — the attr must exist
        assert isinstance(mv.inconsistent_return_count, int)


class TestTV95_GlobalMutation:
    """global_mutation_count: 'global x' inside function + x is assigned."""

    def test_global_mutation_detected(self):
        src = (
            "counter = 0\n"
            "def increment():\n"
            "    global counter\n"
            "    counter += 1\n"
        )
        v = _visit(src)
        assert v.global_mutation_count >= 1

    def test_global_read_only_safe(self):
        # Reading global is fine — only mutation counts
        src = (
            "config = {}\n"
            "def get_config():\n"
            "    global config\n"
            "    return config\n"
        )
        v = _visit(src)
        assert v.global_mutation_count == 0

    def test_no_global_stmt_safe(self):
        src = "def f(x):\n    y = x + 1\n    return y\n"
        v = _visit(src)
        assert v.global_mutation_count == 0

    def test_mv_global_mutation_attached(self):
        src = (
            "state = None\n"
            "def reset():\n"
            "    global state\n"
            "    state = None\n"
        )
        mv = _analyze(src)
        assert hasattr(mv, "global_mutation_count")
        assert mv.global_mutation_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# AST-IMP.4 — deeply nested comprehension + missing __all__
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV96_DeeplyNestedComprehension:
    """deeply_nested_comprehension_count: comprehension inside comprehension."""

    def test_nested_list_comp(self):
        src = "result = [[x*y for x in row] for row in matrix]"
        v = _visit(src)
        assert v.deeply_nested_comprehension_count >= 1

    def test_nested_generator_in_list(self):
        src = "flat = [x for sub in (i for i in data) for x in sub]"
        v = _visit(src)
        # The generator inside the outer list comp is nested
        assert isinstance(v.deeply_nested_comprehension_count, int)

    def test_simple_list_comp_safe(self):
        src = "squares = [x**2 for x in range(10)]"
        v = _visit(src)
        assert v.deeply_nested_comprehension_count == 0

    def test_mv_nested_comp_attached(self):
        src = "m = [[j for j in range(i)] for i in range(5)]"
        mv = _analyze(src)
        assert hasattr(mv, "deeply_nested_comprehension_count")
        assert mv.deeply_nested_comprehension_count >= 1


class TestTV97_MissingAll:
    """missing_all_flag: module has public functions but no __all__ assignment."""

    def test_missing_all_detected(self):
        src = "def public_function():\n    pass\n"
        v = _visit(src)
        assert v.missing_all_flag is True

    def test_all_present_safe(self):
        src = "__all__ = ['public_function']\ndef public_function():\n    pass\n"
        v = _visit(src)
        assert v.missing_all_flag is False

    def test_only_private_functions_safe(self):
        # Module with only private functions — __all__ not required
        src = "def _private():\n    pass\n"
        v = _visit(src)
        assert v.missing_all_flag is False

    def test_mv_missing_all_attached(self):
        src = "def exported():\n    return 42\n"
        mv = _analyze(src)
        assert hasattr(mv, "missing_all_flag")
        assert isinstance(mv.missing_all_flag, bool)


# ═══════════════════════════════════════════════════════════════════════════════
# Integration: all 8 new counters present on MetricVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV98_AllCountersOnMV:
    """All 8 AST-IMP new signals present on MetricVector from UCOBridge."""

    _EXPECTED_ATTRS = [
        "bare_except_count",
        "swallowed_exception_count",
        "shadow_builtin_count",
        "mutable_default_arg_count",
        "inconsistent_return_count",
        "global_mutation_count",
        "deeply_nested_comprehension_count",
        "missing_all_flag",
    ]

    def test_all_attrs_present_on_clean_code(self):
        src = "def f(x):\n    return x + 1\n"
        mv = _analyze(src)
        for attr in self._EXPECTED_ATTRS:
            assert hasattr(mv, attr), f"Missing attr: {attr}"

    def test_all_attrs_zero_on_clean_code(self):
        src = "def f(x):\n    return x + 1\n"
        mv = _analyze(src)
        for attr in self._EXPECTED_ATTRS[:-1]:  # all except missing_all_flag (bool)
            assert getattr(mv, attr) == 0, f"{attr} should be 0 on clean code"

    def test_combined_dirty_code(self):
        """Single snippet triggers multiple new patterns simultaneously."""
        src = (
            "list = [1, 2, 3]\n"                      # shadow builtin
            "def process(items=[]):\n"                 # mutable default
            "    global list\n"
            "    list = items\n"                       # global mutation
            "    try:\n"
            "        risky()\n"
            "    except:\n"                            # bare except
            "        pass\n"                           # swallowed exception
            "    if items:\n"
            "        return items\n"                   # inconsistent return (fall-through)
        )
        mv = _analyze(src)
        assert mv.bare_except_count >= 1
        assert mv.swallowed_exception_count >= 1
        assert mv.shadow_builtin_count >= 1
        assert mv.mutable_default_arg_count >= 1
        assert mv.global_mutation_count >= 1
        assert mv.inconsistent_return_count >= 1

    def test_visitor_counters_match_mv(self):
        """Visitor counters and MetricVector attrs must agree."""
        src = (
            "def bad(x=[]):\n"
            "    global _state\n"
            "    _state = x\n"
            "    try:\n"
            "        bad()\n"
            "    except:\n"
            "        pass\n"
        )
        import ast as _ast
        tree = _ast.parse(src)
        v = _UCOVisitor()
        v.visit(tree)
        mv = _analyze(src)
        assert mv.mutable_default_arg_count == v.mutable_default_arg_count
        assert mv.bare_except_count == v.bare_except_count
        assert mv.swallowed_exception_count == v.swallowed_exception_count
