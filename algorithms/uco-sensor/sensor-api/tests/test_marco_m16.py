"""
UCO-Sensor — M7.3 ReliabilityVector + MaintainabilityVector — Test Suite
=========================================================================
TV99-TV128  (30 tests per WBS 4.1-4.6)

Coverage
--------
TR01-TR05  ReliabilityVector dataclass: construction, total_issues, to_dict
TR06-TR10  ReliabilityVector from_mv, rating A-E, from_dict roundtrip
TM01-TM05  MaintainabilityVector dataclass: construction, rating A/B/C/D/E
TM06-TM10  _analyse_maintainability: magic-nums, long params, bool defaults,
           missing docstrings, avg args
TI01-TI05  Full pipeline: UCOBridge attaches reliability + maintainability
TI06-TI10  API handlers: handle_metrics_reliability / _maintainability
           return correct HTTP codes (400, 404, 503, 200)
"""
from __future__ import annotations

import sys
import os
import pytest

# ── path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from metrics.extended_vectors import (
    ReliabilityVector,
    MaintainabilityVector,
    _analyse_maintainability,
)
import ast as _ast


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_rel(**kwargs) -> ReliabilityVector:
    return ReliabilityVector(**kwargs)


def _make_mnt(**kwargs) -> MaintainabilityVector:
    return MaintainabilityVector(**kwargs)


def _analyse(source: str):
    """Return _analyse_maintainability result for given source."""
    tree  = _ast.parse(source)
    lines = source.splitlines()
    return _analyse_maintainability(tree, lines)


def _analyze_mv(source: str):
    """Return MetricVector via UCOBridge.analyze (Python mode)."""
    from sensor_core.uco_bridge import UCOBridge
    bridge = UCOBridge(mode="full")
    return bridge.analyze(source, module_id="tv_m16_test", commit_hash="m16abc")


# ═══════════════════════════════════════════════════════════════════════════════
# TR01-TR05 — ReliabilityVector: dataclass basics
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV99_ReliabilityDataclassDefaults:
    """TR01 — default construction yields all-zero/empty fields."""

    def test_default_all_zero(self):
        rv = ReliabilityVector()
        assert rv.bare_except_count          == 0
        assert rv.swallowed_exception_count  == 0
        assert rv.mutable_default_arg_count  == 0
        assert rv.inconsistent_return_count  == 0
        assert rv.shadow_builtin_count       == 0
        assert rv.global_mutation_count      == 0
        assert rv.empty_except_block_count   == 0
        assert rv.resource_leak_risk         == 0
        assert rv.regex_redos_risk           == 0
        assert rv.infinite_recursion_risk    == 0.0

    def test_default_total_issues_zero(self):
        rv = ReliabilityVector()
        assert rv.total_issues == 0

    def test_default_rating_A(self):
        rv = ReliabilityVector()
        assert rv.reliability_rating() == "A"

    def test_default_metadata(self):
        rv = ReliabilityVector(module_id="mod_x", language="python")
        assert rv.module_id == "mod_x"
        assert rv.language  == "python"


class TestTV100_ReliabilityTotalIssues:
    """TR02 — total_issues sums all integer channels correctly."""

    def test_total_issues_sum(self):
        rv = ReliabilityVector(
            bare_except_count         = 2,
            swallowed_exception_count = 1,
            mutable_default_arg_count = 1,
            inconsistent_return_count = 0,
            shadow_builtin_count      = 1,
            global_mutation_count     = 0,
            resource_leak_risk        = 2,
            regex_redos_risk          = 1,
        )
        # 2+1+1+0+1+0+2+1 = 8
        assert rv.total_issues == 8

    def test_total_issues_excludes_float(self):
        """infinite_recursion_risk (float) must NOT be counted in total_issues."""
        rv = ReliabilityVector(
            bare_except_count       = 0,
            infinite_recursion_risk = 0.95,
        )
        assert rv.total_issues == 0   # float channel excluded

    def test_total_issues_excludes_empty_except_alias(self):
        """empty_except_block_count is alias of swallowed, NOT double-counted."""
        rv = ReliabilityVector(
            swallowed_exception_count = 3,
            empty_except_block_count  = 3,   # same value — must NOT double-count
        )
        # total_issues uses swallowed_exception_count, not empty_except_block_count
        # so result should be 3, not 6
        assert rv.total_issues == 3


class TestTV101_ReliabilityRating:
    """TR03 — reliability_rating returns A–E per documented thresholds."""

    def test_rating_A_zero_issues(self):
        rv = _make_rel(bare_except_count=0, infinite_recursion_risk=0.05)
        assert rv.reliability_rating() == "A"

    def test_rating_B_one_issue(self):
        rv = _make_rel(bare_except_count=1)
        assert rv.reliability_rating() == "B"

    def test_rating_C_three_issues(self):
        rv = _make_rel(
            bare_except_count         = 1,
            swallowed_exception_count = 1,
            mutable_default_arg_count = 1,
        )
        assert rv.reliability_rating() == "C"

    def test_rating_D_six_issues(self):
        rv = _make_rel(
            bare_except_count         = 2,
            swallowed_exception_count = 2,
            mutable_default_arg_count = 1,
            shadow_builtin_count      = 1,
        )
        assert rv.reliability_rating() == "D"

    def test_rating_E_over_ten_issues(self):
        rv = _make_rel(
            bare_except_count         = 4,
            swallowed_exception_count = 3,
            mutable_default_arg_count = 2,
            resource_leak_risk        = 2,
        )
        assert rv.reliability_rating() == "E"

    def test_rating_E_bare_except_gt3(self):
        """bare_except > 3 alone triggers E regardless of total_issues."""
        rv = _make_rel(bare_except_count=4)
        assert rv.reliability_rating() == "E"

    def test_rating_D_high_ilr(self):
        """ILR > 0.5 → at least D."""
        rv = _make_rel(infinite_recursion_risk=0.6)
        assert rv.reliability_rating() in {"D", "E"}


class TestTV102_ReliabilityToDict:
    """TR04 — to_dict includes all channels + derived fields."""

    def test_to_dict_keys(self):
        rv = ReliabilityVector(bare_except_count=2, module_id="m1")
        d  = rv.to_dict()
        assert "bare_except_count"          in d
        assert "swallowed_exception_count"  in d
        assert "mutable_default_arg_count"  in d
        assert "inconsistent_return_count"  in d
        assert "shadow_builtin_count"       in d
        assert "global_mutation_count"      in d
        assert "resource_leak_risk"         in d
        assert "regex_redos_risk"           in d
        assert "infinite_recursion_risk"    in d
        assert "total_issues"               in d
        assert "reliability_rating"         in d

    def test_to_dict_derived_values(self):
        rv = ReliabilityVector(bare_except_count=1, swallowed_exception_count=1)
        d  = rv.to_dict()
        assert d["total_issues"]       == 2
        assert d["reliability_rating"] == "B"

    def test_to_dict_roundtrip_via_from_dict(self):
        rv1 = ReliabilityVector(
            bare_except_count=3, mutable_default_arg_count=1, module_id="x"
        )
        rv2 = ReliabilityVector.from_dict(rv1.to_dict())
        assert rv2.bare_except_count         == rv1.bare_except_count
        assert rv2.mutable_default_arg_count == rv1.mutable_default_arg_count
        assert rv2.module_id                 == rv1.module_id


class TestTV103_ReliabilityFromMV:
    """TR05-TR10 — ReliabilityVector.from_mv extracts AST-IMP counters."""

    def _make_mock_mv(self, **attrs):
        from types import SimpleNamespace
        defaults = dict(
            bare_except_count         = 0,
            swallowed_exception_count = 0,
            mutable_default_arg_count = 0,
            inconsistent_return_count = 0,
            shadow_builtin_count      = 0,
            global_mutation_count     = 0,
            infinite_loop_risk        = 0.0,
            module_id                 = "test_mod",
            language                  = "python",
        )
        defaults.update(attrs)
        return SimpleNamespace(**defaults)

    def test_from_mv_bare_except(self):
        mv = self._make_mock_mv(bare_except_count=3)
        rv = ReliabilityVector.from_mv(mv)
        assert rv.bare_except_count == 3

    def test_from_mv_mutable_default(self):
        mv = self._make_mock_mv(mutable_default_arg_count=2)
        rv = ReliabilityVector.from_mv(mv)
        assert rv.mutable_default_arg_count == 2

    def test_from_mv_ilr_proxy_clamped(self):
        """infinite_recursion_risk is clamped to [0, 1]."""
        mv = self._make_mock_mv(infinite_loop_risk=2.5)
        rv = ReliabilityVector.from_mv(mv)
        assert rv.infinite_recursion_risk <= 1.0

    def test_from_mv_sast_result_none(self):
        """from_mv with sast_result=None: resource_leak=0, redos=0."""
        mv = self._make_mock_mv()
        rv = ReliabilityVector.from_mv(mv, sast_result=None)
        assert rv.resource_leak_risk == 0
        assert rv.regex_redos_risk   == 0

    def test_from_mv_metadata_propagated(self):
        mv = self._make_mock_mv(module_id="my_module", language="python")
        rv = ReliabilityVector.from_mv(mv)
        assert rv.module_id == "my_module"
        assert rv.language  == "python"


# ═══════════════════════════════════════════════════════════════════════════════
# TM01-TM05 — MaintainabilityVector: dataclass basics
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV109_MaintainabilityDataclassDefaults:
    """TM01 — default construction."""

    def test_default_fields(self):
        mv = MaintainabilityVector()
        assert mv.missing_docstring_ratio == 0.0
        assert mv.avg_function_args       == 0.0
        assert mv.long_function_ratio     == 0.0
        assert mv.deeply_nested_ratio     == 0.0
        assert mv.cognitive_cc_hotspot    == 0
        assert mv.boolean_param_count     == 0
        assert mv.magic_number_count      == 0
        assert mv.long_parameter_list     == 0
        assert mv.invariant_density       == 0.5

    def test_default_rating_A(self):
        mv = MaintainabilityVector()
        assert mv.maintainability_rating() == "A"


class TestTV110_MaintainabilityRating:
    """TM02-TM05 — maintainability_rating() returns A–E per thresholds."""

    def test_rating_B_one_warning(self):
        """missing_docstring_ratio > 0.5 → 1 warning → B."""
        mv = _make_mnt(missing_docstring_ratio=0.6)
        assert mv.maintainability_rating() == "B"

    def test_rating_C_three_warnings(self):
        mv = _make_mnt(
            missing_docstring_ratio = 0.6,   # warning
            avg_function_args       = 5.0,   # warning
            long_function_ratio     = 0.3,   # warning
        )
        assert mv.maintainability_rating() == "C"

    def test_rating_D_five_warnings(self):
        mv = _make_mnt(
            missing_docstring_ratio = 0.6,
            avg_function_args       = 5.0,
            long_function_ratio     = 0.3,
            deeply_nested_ratio     = 0.2,
            boolean_param_count     = 5,
        )
        assert mv.maintainability_rating() == "D"

    def test_rating_E_hotspot_above_30(self):
        mv = _make_mnt(cognitive_cc_hotspot=31)
        assert mv.maintainability_rating() == "E"

    def test_rating_E_missing_doc_above_80pct(self):
        mv = _make_mnt(missing_docstring_ratio=0.9)
        assert mv.maintainability_rating() == "E"

    def test_rating_C_hotspot_above_20(self):
        """cognitive_cc_hotspot > 20 → C even with 0 other warnings."""
        mv = _make_mnt(cognitive_cc_hotspot=21)
        assert mv.maintainability_rating() == "C"

    def test_to_dict_includes_rating(self):
        mv = _make_mnt(cognitive_cc_hotspot=5)
        d  = mv.to_dict()
        assert "maintainability_rating" in d
        assert d["maintainability_rating"] == "A"


# ═══════════════════════════════════════════════════════════════════════════════
# TM06-TM10 — _analyse_maintainability AST helper
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV114_AnalyseMaintainability:
    """TM06-TM10 — _analyse_maintainability returns correct values."""

    def test_magic_number_detected(self):
        """Numeric literals ∉ {-1,0,1,2} should be counted as magic numbers."""
        src = "x = 42\ny = 100"
        (_, _, _, _, magic, _, _) = _analyse(src)
        assert magic >= 2

    def test_magic_number_exempt(self):
        """Literals {-1, 0, 1, 2} must NOT be counted as magic numbers."""
        src = "x = 0\ny = 1\nz = 2\nw = -1"
        (_, _, _, _, magic, _, _) = _analyse(src)
        assert magic == 0

    def test_long_parameter_list_detected(self):
        """Function with > 5 params → long_parameter_list >= 1."""
        src = "def big_fn(a, b, c, d, e, f):\n    return a + b"
        (_, _, _, _, _, long_params, _) = _analyse(src)
        assert long_params >= 1

    def test_long_parameter_list_not_triggered(self):
        """Function with ≤ 5 params → long_parameter_list == 0."""
        src = "def small_fn(a, b, c):\n    return a"
        (_, _, _, _, _, long_params, _) = _analyse(src)
        assert long_params == 0

    def test_boolean_param_count(self):
        """Params with default True/False → bool_param_count."""
        src = "def f(x=True, y=False):\n    pass"
        (_, _, _, bool_params, _, _, _) = _analyse(src)
        assert bool_params == 2

    def test_missing_docstring_ratio_all_missing(self):
        """All public fns lack docstring → ratio == 1.0."""
        src = (
            "def foo():\n    x = 1\n"
            "def bar():\n    y = 2\n"
        )
        (miss_doc, _, _, _, _, _, _) = _analyse(src)
        assert miss_doc == 1.0

    def test_missing_docstring_ratio_all_present(self):
        """All public fns have docstring → ratio == 0.0."""
        src = (
            'def foo():\n    """docstring"""\n    x = 1\n'
            'def bar():\n    """docstring"""\n    y = 2\n'
        )
        (miss_doc, _, _, _, _, _, _) = _analyse(src)
        assert miss_doc == 0.0

    def test_avg_function_args(self):
        """avg_function_args = total_args / n_fns."""
        src = (
            "def f1(a, b):\n    pass\n"    # 2 args
            "def f2(x, y, z):\n    pass\n" # 3 args
        )
        (_, avg_args, _, _, _, _, _) = _analyse(src)
        # (2 + 3) / 2 = 2.5
        assert abs(avg_args - 2.5) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# TI01-TI05 — Full pipeline: UCOBridge attaches vectors
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV119_FullPipelineReliability:
    """TI01-TI05 — ReliabilityVector is attached to MetricVector by UCOBridge."""

    _BARE_EXCEPT_SRC = (
        "def process():\n"
        "    try:\n"
        "        dangerous_call()\n"
        "    except:\n"
        "        pass\n"
    )

    def test_mv_has_reliability_attr(self):
        mv = _analyze_mv("x = 1")
        assert hasattr(mv, "reliability")

    def test_mv_reliability_is_correct_type(self):
        mv = _analyze_mv("x = 1")
        assert isinstance(mv.reliability, ReliabilityVector)

    def test_bare_except_flows_to_reliability(self):
        mv = _analyze_mv(self._BARE_EXCEPT_SRC)
        assert mv.reliability.bare_except_count >= 1

    def test_mv_has_maintainability_attr(self):
        mv = _analyze_mv("x = 1")
        assert hasattr(mv, "maintainability")

    def test_mv_maintainability_is_correct_type(self):
        mv = _analyze_mv("x = 1")
        assert isinstance(mv.maintainability, MaintainabilityVector)


class TestTV124_FullPipelineMaintainability:
    """TI06 — MaintainabilityVector from full pipeline reflects source."""

    _NO_DOC_SRC = (
        "def alpha():\n"
        "    x = 42\n"
        "def beta():\n"
        "    y = 99\n"
    )

    def test_magic_numbers_flow_to_maintainability(self):
        mv = _analyze_mv(self._NO_DOC_SRC)
        # 42 and 99 are magic numbers
        assert mv.maintainability.magic_number_count >= 2

    def test_missing_docstring_flows_to_maintainability(self):
        mv = _analyze_mv(self._NO_DOC_SRC)
        assert mv.maintainability.missing_docstring_ratio > 0.0

    def test_well_documented_code_low_miss_ratio(self):
        src = (
            'def alpha():\n'
            '    """Alpha function."""\n'
            '    return 1\n'
            'def beta():\n'
            '    """Beta function."""\n'
            '    return 2\n'
        )
        mv = _analyze_mv(src)
        assert mv.maintainability.missing_docstring_ratio == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# TI07-TI10 — API handler tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV127_APIHandlers:
    """TI07-TI10 — handle_metrics_reliability + _maintainability HTTP codes."""

    @pytest.fixture(autouse=True)
    def _import_handlers(self):
        """Import server handlers once per test class."""
        import os as _os
        _os.environ.setdefault("UCO_NO_AUTH", "1")
        from api.server import (
            handle_metrics_reliability,
            handle_metrics_maintainability,
            handle_analyze,
        )
        self.rel_handler  = handle_metrics_reliability
        self.mnt_handler  = handle_metrics_maintainability
        self.ana_handler  = handle_analyze

    def test_reliability_no_module_returns_400(self):
        code, body = self.rel_handler(None)
        assert code == 400
        assert "module" in body["error"].lower()

    def test_reliability_unknown_module_returns_404(self):
        code, body = self.rel_handler("__no_such_module__xyz__")
        assert code == 404

    def test_maintainability_no_module_returns_400(self):
        code, body = self.mnt_handler(None)
        assert code == 400
        assert "module" in body["error"].lower()

    def test_maintainability_unknown_module_returns_404(self):
        code, body = self.mnt_handler("__no_such_module__xyz__")
        assert code == 404

    def test_reliability_populated_module_returns_200(self):
        """After /analyze populates history, /metrics/reliability → 200."""
        import time
        uid = f"tv_api_m16_{int(time.time())}"
        # Seed the store via handle_analyze
        src = "x = 1"
        code_a, _ = self.ana_handler({
            "code":       src,
            "module_id":  uid,
            "commit_hash": "tv128abc",
        })
        assert code_a == 200, "handle_analyze must succeed before reliability check"

        code_r, body_r = self.rel_handler(uid)
        assert code_r == 200
        assert body_r["module_id"] == uid
        assert "reliability_rating" in body_r
        # vector dict may be None if ReliabilityVector not attached; just verify key
        assert "reliability_vector" in body_r
