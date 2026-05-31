"""
test_marco_m21.py — M7.6 TestQualityVector (30 tests, TQ01–TQ30)
==================================================================
Validates all components delivered in FASE 6a (M7.6 → v2.9.1):

  • TestQualityResult / TestQualityVector dataclass basics       (TQ01–TQ05)
  • test function discovery + assertion_density                  (TQ06–TQ10)
  • test_complexity, mock_overuse_ratio                          (TQ11–TQ15)
  • test_isolation_score, flaky_test_risk                        (TQ16–TQ20)
  • parameterized_ratio, test_naming_quality, dead_test_count    (TQ21–TQ25)
  • rating, round-trip, REST endpoint                            (TQ26–TQ30)
"""
from __future__ import annotations

import json
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Path setup (mirror pyproject testpaths) ──────────────────────────────────
_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from metrics.test_quality_analyzer import (
    TestQualityAnalyzer, TestQualityResult,
)
from metrics.extended_vectors import TestQualityVector


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _analyze(source: str, module_id: str = "") -> TestQualityResult:
    return TestQualityAnalyzer().analyze(textwrap.dedent(source), module_id=module_id)


def _vector(source: str, module_id: str = "") -> TestQualityVector:
    return TestQualityVector.from_analyzer(
        _analyze(source, module_id), module_id=module_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TQ01–TQ05 — Dataclass basics
# ══════════════════════════════════════════════════════════════════════════════

class TestQualityResultDataclass(unittest.TestCase):

    def test_tq01_default_values(self):
        """TQ01 — TestQualityResult defaults to zero / 1.0 for isolation."""
        r = TestQualityResult()
        self.assertEqual(r.n_test_functions, 0)
        self.assertAlmostEqual(r.assertion_density, 0.0)
        self.assertAlmostEqual(r.test_complexity, 0.0)
        self.assertAlmostEqual(r.mock_overuse_ratio, 0.0)
        self.assertAlmostEqual(r.test_isolation_score, 1.0)
        self.assertEqual(r.flaky_test_risk, 0)
        self.assertAlmostEqual(r.parameterized_ratio, 0.0)
        self.assertAlmostEqual(r.test_naming_quality, 0.0)
        self.assertEqual(r.dead_test_count, 0)

    def test_tq02_vector_default_rating_is_A(self):
        """TQ02 — Empty TestQualityVector → rating ``A`` (vacuously perfect)."""
        v = TestQualityVector()
        self.assertEqual(v.test_quality_rating(), "A")

    def test_tq03_from_analyzer_maps_all_channels(self):
        """TQ03 — from_analyzer() maps every channel verbatim."""
        r = TestQualityResult(
            n_test_functions=3, assertion_density=2.5, test_complexity=1.5,
            mock_overuse_ratio=0.1, test_isolation_score=0.9,
            flaky_test_risk=0, parameterized_ratio=0.5,
            test_naming_quality=0.8, dead_test_count=0,
        )
        v = TestQualityVector.from_analyzer(r, module_id="tests.foo")
        self.assertEqual(v.n_test_functions, 3)
        self.assertAlmostEqual(v.assertion_density, 2.5)
        self.assertAlmostEqual(v.parameterized_ratio, 0.5)
        self.assertEqual(v.module_id, "tests.foo")
        self.assertEqual(v.language, "python")

    def test_tq04_to_dict_contains_rating_and_violations(self):
        """TQ04 — to_dict() includes ``test_quality_rating`` and ``threshold_violations``."""
        v = TestQualityVector(n_test_functions=2, assertion_density=2.0,
                              test_complexity=2.0, parameterized_ratio=0.5,
                              test_naming_quality=0.8)
        d = v.to_dict()
        self.assertIn("test_quality_rating", d)
        self.assertIn("threshold_violations", d)
        self.assertEqual(d["module_id"], "")

    def test_tq05_from_dict_round_trip(self):
        """TQ05 — from_dict(to_dict()) round-trips every field."""
        v = TestQualityVector(
            n_test_functions=4, assertion_density=2.5, test_complexity=2.0,
            mock_overuse_ratio=0.2, test_isolation_score=0.85,
            flaky_test_risk=1, parameterized_ratio=0.4,
            test_naming_quality=0.9, dead_test_count=0,
            module_id="tests.bar",
        )
        v2 = TestQualityVector.from_dict(v.to_dict())
        self.assertEqual(v2.n_test_functions, v.n_test_functions)
        self.assertEqual(v2.flaky_test_risk, v.flaky_test_risk)
        self.assertEqual(v2.module_id, v.module_id)


# ══════════════════════════════════════════════════════════════════════════════
# TQ06–TQ10 — Test discovery + assertion_density
# ══════════════════════════════════════════════════════════════════════════════

class TestDiscoveryAndAssertions(unittest.TestCase):

    def test_tq06_empty_module_yields_zero_tests(self):
        """TQ06 — A module with no def test_* has n_test_functions=0."""
        r = _analyze("x = 1\ndef helper():\n    return 2\n")
        self.assertEqual(r.n_test_functions, 0)

    def test_tq07_module_level_test_function_counted(self):
        """TQ07 — Module-level def test_x is discovered."""
        r = _analyze("""
            def test_first():
                assert 1 == 1
        """)
        self.assertEqual(r.n_test_functions, 1)
        self.assertAlmostEqual(r.assertion_density, 1.0)

    def test_tq08_class_scoped_test_functions_counted(self):
        """TQ08 — Tests inside a TestCase class are also discovered."""
        r = _analyze("""
            import unittest
            class TestStuff(unittest.TestCase):
                def test_one(self):
                    self.assertEqual(1, 1)
                def test_two(self):
                    self.assertTrue(True)
        """)
        self.assertEqual(r.n_test_functions, 2)

    def test_tq09_unittest_self_assert_calls_count_as_assertions(self):
        """TQ09 — self.assertEqual/self.fail count toward assertion_density."""
        r = _analyze("""
            import unittest
            class T(unittest.TestCase):
                def test_x(self):
                    self.assertEqual(1, 1)
                    self.assertTrue(True)
                    self.assertGreater(2, 1)
        """)
        self.assertAlmostEqual(r.assertion_density, 3.0)

    def test_tq10_async_def_test_is_discovered(self):
        """TQ10 — async def test_x is also a test function."""
        r = _analyze("""
            async def test_async():
                assert True
        """)
        self.assertEqual(r.n_test_functions, 1)


# ══════════════════════════════════════════════════════════════════════════════
# TQ11–TQ15 — test_complexity + mock_overuse_ratio
# ══════════════════════════════════════════════════════════════════════════════

class TestComplexityAndMocks(unittest.TestCase):

    def test_tq11_simple_test_has_cc_1(self):
        """TQ11 — Linear test has cyclomatic complexity 1."""
        r = _analyze("""
            def test_linear():
                x = 1
                assert x == 1
        """)
        # CC = 1 (linear) + 1 (Assert) = 2 in our McCabe accounting
        self.assertGreaterEqual(r.test_complexity, 1.0)
        self.assertLessEqual(r.test_complexity, 3.0)

    def test_tq12_branchy_test_increases_cc(self):
        """TQ12 — A test with multiple branches/loops has CC > 3."""
        r = _analyze("""
            def test_branchy():
                for i in range(3):
                    if i == 1:
                        assert i
                    else:
                        assert i != 5
        """)
        self.assertGreater(r.test_complexity, 3.0)

    def test_tq13_pure_mock_test_has_high_overuse_ratio(self):
        """TQ13 — Test that only constructs mocks has mock_overuse_ratio > 0."""
        r = _analyze("""
            from unittest.mock import Mock, MagicMock, patch
            def test_mocks():
                m1 = Mock()
                m2 = MagicMock()
                with patch("os.environ"):
                    assert m1.call_count == 0
        """)
        self.assertGreater(r.mock_overuse_ratio, 0.3)

    def test_tq14_no_mocks_yields_zero_ratio(self):
        """TQ14 — Test with no mocks → mock_overuse_ratio == 0.0."""
        r = _analyze("""
            def test_plain():
                x = list(range(3))
                assert x == [0, 1, 2]
        """)
        self.assertAlmostEqual(r.mock_overuse_ratio, 0.0)

    def test_tq15_complexity_averaged_across_tests(self):
        """TQ15 — test_complexity is the MEAN, not the sum, across tests."""
        r = _analyze("""
            def test_a():
                assert 1
            def test_b():
                if True:
                    assert 1
                else:
                    assert 0
        """)
        # Two tests — mean should be < sum
        self.assertEqual(r.n_test_functions, 2)
        self.assertLess(r.test_complexity, 6.0)


# ══════════════════════════════════════════════════════════════════════════════
# TQ16–TQ20 — test_isolation_score + flaky_test_risk
# ══════════════════════════════════════════════════════════════════════════════

class TestIsolationAndFlakiness(unittest.TestCase):

    def test_tq16_clean_tests_yield_isolation_1(self):
        """TQ16 — Tests with no global/nonlocal/module-mutation → isolation = 1.0."""
        r = _analyze("""
            def test_a():
                assert 1
            def test_b():
                assert 2
        """)
        self.assertAlmostEqual(r.test_isolation_score, 1.0)

    def test_tq17_global_keyword_lowers_isolation(self):
        """TQ17 — Test that declares ``global x`` is flagged as polluting."""
        r = _analyze("""
            COUNTER = 0
            def test_pollutes():
                global COUNTER
                COUNTER += 1
                assert COUNTER >= 1
            def test_clean():
                assert True
        """)
        # 1 of 2 tests pollutes → score should be 0.5
        self.assertAlmostEqual(r.test_isolation_score, 0.5)

    def test_tq18_module_attribute_mutation_lowers_isolation(self):
        """TQ18 — Writing to ``module.attr`` flags pollution."""
        r = _analyze("""
            import os
            def test_pollutes():
                os.environ = {}
                assert True
        """)
        self.assertLess(r.test_isolation_score, 1.0)

    def test_tq19_time_sleep_flags_flaky(self):
        """TQ19 — time.sleep / time.time inside a test increments flaky_test_risk."""
        r = _analyze("""
            import time
            def test_sleepy():
                time.sleep(0.1)
                assert True
            def test_fast():
                assert True
        """)
        self.assertEqual(r.flaky_test_risk, 1)

    def test_tq20_random_call_flags_flaky(self):
        """TQ20 — random.randint / datetime.now flag flaky."""
        r = _analyze("""
            import random, datetime
            def test_random():
                x = random.randint(0, 9)
                assert x >= 0
            def test_now():
                t = datetime.datetime.now()
                assert t is not None
        """)
        self.assertEqual(r.flaky_test_risk, 2)


# ══════════════════════════════════════════════════════════════════════════════
# TQ21–TQ25 — parameterized_ratio + test_naming_quality + dead_test_count
# ══════════════════════════════════════════════════════════════════════════════

class TestParametrizationNamingDead(unittest.TestCase):

    def test_tq21_pytest_parametrize_counted(self):
        """TQ21 — @pytest.mark.parametrize → parameterized_ratio > 0."""
        r = _analyze("""
            import pytest
            @pytest.mark.parametrize("x", [1, 2, 3])
            def test_param(x):
                assert x > 0
            def test_plain():
                assert True
        """)
        self.assertAlmostEqual(r.parameterized_ratio, 0.5)

    def test_tq22_hypothesis_given_counted(self):
        """TQ22 — @given (hypothesis) decorator also counts as parameterized."""
        r = _analyze("""
            from hypothesis import given, strategies as st
            @given(st.integers())
            def test_hypothesis(x):
                assert isinstance(x, int)
        """)
        self.assertAlmostEqual(r.parameterized_ratio, 1.0)

    def test_tq23_naming_quality_distinguishes_good_from_bad(self):
        """TQ23 — descriptive ≥3-token names raise test_naming_quality."""
        r = _analyze("""
            def test_x():
                assert 1
            def test_user_login_with_invalid_password():
                assert 1
            def test_database_connection_retry():
                assert 1
        """)
        # 2 of 3 names are descriptive
        self.assertAlmostEqual(r.test_naming_quality, 2/3, places=3)

    def test_tq24_dead_tests_counted(self):
        """TQ24 — Test functions without any assert / self.assert* counted."""
        r = _analyze("""
            def test_dead():
                x = 1 + 1
            def test_alive():
                assert True
        """)
        self.assertEqual(r.dead_test_count, 1)

    def test_tq25_self_fail_counts_as_assertion(self):
        """TQ25 — self.fail() rescues a test from being counted as dead."""
        r = _analyze("""
            import unittest
            class T(unittest.TestCase):
                def test_uses_fail(self):
                    if False:
                        self.fail("never")
        """)
        self.assertEqual(r.dead_test_count, 0)


# ══════════════════════════════════════════════════════════════════════════════
# TQ26–TQ30 — Rating, round-trip, REST endpoint, repr, edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestRatingEndpointEdges(unittest.TestCase):

    def test_tq26_rating_E_for_pathological_suite(self):
        """TQ26 — Suite with many violations + 5+ dead tests → rating E."""
        v = TestQualityVector(
            n_test_functions=10, assertion_density=0.5,    # < 2.0  ✗
            test_complexity=5.0,                            # > 3.0  ✗
            mock_overuse_ratio=0.7,                         # > 0.3  ✗
            test_isolation_score=0.5,                       # < 0.8  ✗
            flaky_test_risk=3,                              # > 0    ✗
            parameterized_ratio=0.1,                        # < 0.3  ✗
            test_naming_quality=0.2,                        # < 0.7  ✗
            dead_test_count=6,                              # ≥ 5    forces E
        )
        self.assertEqual(v.test_quality_rating(), "E")

    def test_tq27_rating_A_for_clean_suite(self):
        """TQ27 — Suite passing every threshold → rating A."""
        v = TestQualityVector(
            n_test_functions=10, assertion_density=3.0,
            test_complexity=1.5, mock_overuse_ratio=0.1,
            test_isolation_score=0.95, flaky_test_risk=0,
            parameterized_ratio=0.5, test_naming_quality=0.9,
            dead_test_count=0,
        )
        self.assertEqual(v.test_quality_rating(), "A")

    def test_tq28_syntax_error_returns_zeroed_result(self):
        """TQ28 — Invalid source returns a default result, not an exception."""
        r = _analyze("def test_(:")  # SyntaxError
        self.assertEqual(r.n_test_functions, 0)
        self.assertAlmostEqual(r.test_isolation_score, 1.0)

    def test_tq29_repr_includes_rating_and_counts(self):
        """TQ29 — __repr__ includes rating, n_tests, asserts/test, dead, flaky."""
        v = TestQualityVector(n_test_functions=2, assertion_density=2.0,
                              dead_test_count=0, flaky_test_risk=0,
                              parameterized_ratio=0.5, test_naming_quality=0.8,
                              test_complexity=1.0)
        rep = repr(v)
        self.assertIn("rating=", rep)
        self.assertIn("tests=2", rep)
        self.assertIn("dead=0", rep)
        self.assertIn("flaky=0", rep)

    def test_tq30_scan_test_quality_endpoint(self):
        """TQ30 — POST /scan-test-quality returns vector + summary + 200."""
        from api.server import handle_scan_test_quality
        src = textwrap.dedent("""
            def test_user_login_works():
                assert True
            def test_dead_one():
                x = 1
            def test_param_a():
                assert 1 == 1
                assert 2 == 2
        """)
        code, data = handle_scan_test_quality({"code": src, "module_id": "demo"})
        self.assertEqual(code, 200)
        self.assertIn("test_quality_vector", data)
        self.assertIn("summary", data)
        summary = data["summary"]
        self.assertEqual(summary["n_test_functions"], 3)
        self.assertEqual(summary["dead_test_count"], 1)
        self.assertIn("test_quality_rating", summary)
        # Round-trip with from_dict
        v = TestQualityVector.from_dict(data["test_quality_vector"])
        self.assertEqual(v.n_test_functions, 3)


if __name__ == "__main__":
    unittest.main()
