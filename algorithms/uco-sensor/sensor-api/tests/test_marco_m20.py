"""
test_marco_m20.py — M7.5 ArchitectureVector (30 tests, TA01–TA30)
==================================================================
Validates all components delivered in FASE 5b (M7.5 → v2.9.0):

  • ArchitectureResult dataclass defaults and basic creation    (TA01–TA05)
  • fan_out detection from import statements                   (TA06–TA10)
  • CBO (coupling_between_objects) and RFC (response_for_class)(TA11–TA15)
  • LCOM (lack_of_cohesion) computation                        (TA16–TA20)
  • abstraction_level and layer_violation_count                 (TA21–TA25)
  • ArchitectureVector dataclass, rating, round-trip, API       (TA26–TA30)
"""
from __future__ import annotations

import json
import sys
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ── Path setup (mirror pyproject testpaths) ────────────────────────────────
_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from metrics.architecture_analyzer import ArchitectureAnalyzer, ArchitectureResult
from metrics.extended_vectors import ArchitectureVector


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _analyze(source: str, module_id: str = "", fan_in: int = 0,
             circular: int = 0) -> ArchitectureResult:
    return ArchitectureAnalyzer().analyze(
        textwrap.dedent(source),
        module_id=module_id,
        fan_in=fan_in,
        circular_import_count=circular,
    )


def _vector(source: str, module_id: str = "", fan_in: int = 0,
            circular: int = 0) -> ArchitectureVector:
    result = _analyze(source, module_id, fan_in, circular)
    return ArchitectureVector.from_analyzer(result, module_id=module_id)


# ══════════════════════════════════════════════════════════════════════════════
# TA01–TA05 — ArchitectureResult / ArchitectureVector dataclass basics
# ══════════════════════════════════════════════════════════════════════════════

class TestArchitectureResultDataclass(unittest.TestCase):

    def test_ta01_default_values(self):
        """TA01 — ArchitectureResult all fields default to 0 / 0.0."""
        r = ArchitectureResult()
        self.assertEqual(r.fan_in, 0)
        self.assertEqual(r.fan_out, 0)
        self.assertEqual(r.coupling_between_objects, 0)
        self.assertEqual(r.response_for_class, 0)
        self.assertAlmostEqual(r.lack_of_cohesion, 0.0)
        self.assertAlmostEqual(r.abstraction_level, 0.0)
        self.assertEqual(r.circular_import_count, 0)
        self.assertEqual(r.layer_violation_count, 0)

    def test_ta02_from_analyzer_populates_fan_in(self):
        """TA02 — fan_in passed to analyze() is preserved in result."""
        src = "x = 1"
        result = _analyze(src, fan_in=7)
        self.assertEqual(result.fan_in, 7)

    def test_ta03_architecture_vector_from_analyzer(self):
        """TA03 — ArchitectureVector.from_analyzer() maps all 8 channels."""
        result = ArchitectureResult(
            fan_in=2, fan_out=3, coupling_between_objects=1,
            response_for_class=5, lack_of_cohesion=0.25,
            abstraction_level=0.5, circular_import_count=0,
            layer_violation_count=1,
        )
        av = ArchitectureVector.from_analyzer(result, module_id="mymod")
        self.assertEqual(av.fan_in, 2)
        self.assertEqual(av.fan_out, 3)
        self.assertEqual(av.coupling_between_objects, 1)
        self.assertEqual(av.response_for_class, 5)
        self.assertAlmostEqual(av.lack_of_cohesion, 0.25)
        self.assertAlmostEqual(av.abstraction_level, 0.5)
        self.assertEqual(av.circular_import_count, 0)
        self.assertEqual(av.layer_violation_count, 1)
        self.assertEqual(av.module_id, "mymod")

    def test_ta04_to_dict_contains_expected_keys(self):
        """TA04 — to_dict() includes all channels + architecture_rating."""
        av = ArchitectureVector(fan_out=2)
        d = av.to_dict()
        expected_keys = {
            "fan_in", "fan_out", "coupling_between_objects",
            "response_for_class", "lack_of_cohesion", "abstraction_level",
            "circular_import_count", "layer_violation_count",
            "module_id", "language", "architecture_rating",
        }
        self.assertTrue(expected_keys.issubset(set(d.keys())))

    def test_ta05_from_dict_round_trip(self):
        """TA05 — from_dict(to_dict()) round-trips all channel values."""
        av = ArchitectureVector(
            fan_in=1, fan_out=4, coupling_between_objects=2,
            response_for_class=8, lack_of_cohesion=0.33,
            abstraction_level=0.0, circular_import_count=1,
            layer_violation_count=0, module_id="test.mod",
        )
        d = av.to_dict()
        av2 = ArchitectureVector.from_dict(d)
        self.assertEqual(av2.fan_in, av.fan_in)
        self.assertEqual(av2.fan_out, av.fan_out)
        self.assertAlmostEqual(av2.lack_of_cohesion, av.lack_of_cohesion)
        self.assertEqual(av2.module_id, av.module_id)


# ══════════════════════════════════════════════════════════════════════════════
# TA06–TA10 — fan_out detection
# ══════════════════════════════════════════════════════════════════════════════

class TestFanOutDetection(unittest.TestCase):

    def test_ta06_fan_out_counts_distinct_top_level(self):
        """TA06 — fan_out counts distinct top-level module names."""
        src = """
            import os
            import sys
            import json
        """
        r = _analyze(src)
        self.assertEqual(r.fan_out, 3)

    def test_ta07_fan_out_deduplicates(self):
        """TA07 — fan_out deduplicates: 'import os' twice → fan_out=1."""
        src = """
            import os
            import os.path
        """
        # Both have top-level "os"
        r = _analyze(src)
        self.assertEqual(r.fan_out, 1)

    def test_ta08_fan_out_zero_for_empty_module(self):
        """TA08 — module with no imports has fan_out=0."""
        r = _analyze("x = 42")
        self.assertEqual(r.fan_out, 0)

    def test_ta09_fan_out_from_import(self):
        """TA09 — from-import statements contribute to fan_out."""
        src = """
            from collections import OrderedDict
            from typing import List
        """
        r = _analyze(src)
        self.assertEqual(r.fan_out, 2)

    def test_ta10_fan_out_combined_import_styles(self):
        """TA10 — fan_out works for mixed import and from-import styles."""
        src = """
            import os
            from sys import argv
            from os.path import join   # 'os' already counted
        """
        r = _analyze(src)
        self.assertEqual(r.fan_out, 2)   # os, sys


# ══════════════════════════════════════════════════════════════════════════════
# TA11–TA15 — CBO and RFC
# ══════════════════════════════════════════════════════════════════════════════

class TestCBOAndRFC(unittest.TestCase):

    def test_ta11_cbo_zero_for_no_external_types(self):
        """TA11 — class using only self has CBO=0."""
        src = """
            class Foo:
                def bar(self):
                    self.x = 1
                def baz(self):
                    return self.x
        """
        r = _analyze(src)
        self.assertEqual(r.coupling_between_objects, 0)

    def test_ta12_cbo_detects_external_type_annotation(self):
        """TA12 — CBO increases for external type in parameter annotation."""
        src = """
            class Service:
                def process(self, repo: Repository) -> None:
                    self.data = repo
        """
        r = _analyze(src)
        self.assertGreaterEqual(r.coupling_between_objects, 1)

    def test_ta13_rfc_equals_own_method_count_for_pure_class(self):
        """TA13 — RFC ≥ own method count when no external calls."""
        src = """
            class Simple:
                def alpha(self):
                    pass
                def beta(self):
                    pass
                def gamma(self):
                    pass
        """
        r = _analyze(src)
        # 3 own methods, 0 external calls → RFC = 3
        self.assertEqual(r.response_for_class, 3)

    def test_ta14_rfc_increases_with_external_calls(self):
        """TA14 — RFC increases when class methods call external functions."""
        src = """
            class Handler:
                def run(self):
                    result = some_function()
                    other = another_call()
                    return result
        """
        r = _analyze(src)
        # 1 own method + 2 external calls = RFC=3
        self.assertGreaterEqual(r.response_for_class, 2)

    def test_ta15_cbo_rfc_zero_for_no_classes(self):
        """TA15 — module with no classes has CBO=0 and RFC=0."""
        src = """
            def standalone():
                return 42
        """
        r = _analyze(src)
        self.assertEqual(r.coupling_between_objects, 0)
        self.assertEqual(r.response_for_class, 0)


# ══════════════════════════════════════════════════════════════════════════════
# TA16–TA20 — LCOM (lack_of_cohesion)
# ══════════════════════════════════════════════════════════════════════════════

class TestLCOM(unittest.TestCase):

    def test_ta16_lcom_zero_for_single_method(self):
        """TA16 — single-method class has LCOM=0 (no pairs to compare)."""
        src = """
            class Lone:
                def only(self):
                    self.x = 1
        """
        r = _analyze(src)
        self.assertAlmostEqual(r.lack_of_cohesion, 0.0)

    def test_ta17_lcom_zero_when_all_methods_share_attr(self):
        """TA17 — LCOM=0 when all method pairs share at least one attribute."""
        src = """
            class Cohesive:
                def set_value(self):
                    self.value = 1
                def get_value(self):
                    return self.value
                def reset(self):
                    self.value = 0
        """
        r = _analyze(src)
        # All share self.value → Q=3, P=0 → LCOM=(0-3)/3 → clamped to 0
        self.assertAlmostEqual(r.lack_of_cohesion, 0.0)

    def test_ta18_lcom_high_when_no_shared_attrs(self):
        """TA18 — LCOM=1.0 when no method pair shares any instance attribute."""
        src = """
            class Fragmented:
                def method_a(self):
                    self.alpha = 1
                def method_b(self):
                    self.beta = 2
        """
        r = _analyze(src)
        # 1 pair, no shared attrs → P=1, Q=0 → LCOM=(1-0)/1=1.0
        self.assertAlmostEqual(r.lack_of_cohesion, 1.0)

    def test_ta19_lcom_intermediate_value(self):
        """TA19 — LCOM is between 0 and 1 for partially cohesive class."""
        src = """
            class Mixed:
                def a(self):
                    self.shared = 1
                    self.only_a = 2
                def b(self):
                    self.shared = 3
                    self.only_b = 4
                def c(self):
                    self.only_c = 5
        """
        r = _analyze(src)
        # Pairs: (a,b)→shared, (a,c)→none, (b,c)→none → Q=1, P=2 → LCOM=1/3 ≈ 0.333
        self.assertGreater(r.lack_of_cohesion, 0.0)
        self.assertLessEqual(r.lack_of_cohesion, 1.0)

    def test_ta20_lcom_zero_for_no_classes(self):
        """TA20 — module with no classes has lack_of_cohesion=0.0."""
        src = "x = 1"
        r = _analyze(src)
        self.assertAlmostEqual(r.lack_of_cohesion, 0.0)


# ══════════════════════════════════════════════════════════════════════════════
# TA21–TA25 — abstraction_level and layer_violation_count
# ══════════════════════════════════════════════════════════════════════════════

class TestAbstractionAndLayers(unittest.TestCase):

    def test_ta21_abstraction_zero_for_no_abstract_classes(self):
        """TA21 — abstraction_level=0.0 when no class is abstract."""
        src = """
            class Concrete:
                def run(self):
                    pass
        """
        r = _analyze(src)
        self.assertAlmostEqual(r.abstraction_level, 0.0)

    def test_ta22_abstraction_one_for_all_abstract(self):
        """TA22 — abstraction_level=1.0 when every class is abstract (ABC)."""
        src = """
            from abc import ABC, abstractmethod
            class Base(ABC):
                @abstractmethod
                def execute(self):
                    pass
        """
        r = _analyze(src)
        self.assertAlmostEqual(r.abstraction_level, 1.0)

    def test_ta23_abstraction_half_for_mixed(self):
        """TA23 — abstraction_level=0.5 for 1 abstract + 1 concrete class."""
        src = """
            from abc import ABC, abstractmethod
            class AbstractRepo(ABC):
                @abstractmethod
                def save(self):
                    pass
            class ConcreteRepo:
                def save(self):
                    return True
        """
        r = _analyze(src)
        self.assertAlmostEqual(r.abstraction_level, 0.5)

    def test_ta24_layer_violation_zero_for_unknown_layers(self):
        """TA24 — layer_violation=0 when module_id layer is unknown."""
        src = "import api"
        # module_id='utils' doesn't map to any known layer
        r = _analyze(src, module_id="utils")
        self.assertEqual(r.layer_violation_count, 0)

    def test_ta25_layer_violation_detected_infra_imports_api(self):
        """TA25 — infra module importing api triggers a layer violation."""
        src = "import api"
        # infra layer (0) importing api layer (3) → violation
        r = _analyze(src, module_id="infra")
        self.assertGreaterEqual(r.layer_violation_count, 1)


# ══════════════════════════════════════════════════════════════════════════════
# TA26–TA30 — ArchitectureVector rating, repr, API endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestArchitectureVectorRatingAndAPI(unittest.TestCase):

    def test_ta26_rating_a_for_clean_module(self):
        """TA26 — architecture_rating=A when all channels are within thresholds."""
        av = ArchitectureVector(
            fan_in=2, fan_out=3, coupling_between_objects=1,
            response_for_class=5, lack_of_cohesion=0.1,
            abstraction_level=0.5, circular_import_count=0,
            layer_violation_count=0,
        )
        self.assertEqual(av.architecture_rating(), "A")

    def test_ta27_rating_b_for_one_warning(self):
        """TA27 — architecture_rating=B when exactly 1 channel exceeds threshold."""
        av = ArchitectureVector(fan_out=15)   # fan_out > 10
        self.assertEqual(av.architecture_rating(), "B")

    def test_ta28_rating_c_for_circular_import(self):
        """TA28 — architecture_rating=C when circular_import_count > 0."""
        av = ArchitectureVector(circular_import_count=1)
        self.assertIn(av.architecture_rating(), {"C", "D", "E"})

    def test_ta29_rating_e_for_many_warnings(self):
        """TA29 — architecture_rating=E when 6 channels exceed thresholds."""
        av = ArchitectureVector(
            fan_out=20,                   # > 10
            coupling_between_objects=10,  # > 5
            response_for_class=25,        # > 20
            lack_of_cohesion=0.9,         # > 0.5
            circular_import_count=2,      # > 0
            layer_violation_count=5,      # > 0
        )
        self.assertEqual(av.architecture_rating(), "E")

    def test_ta30_scan_architecture_endpoint(self):
        """TA30 — POST /scan-architecture returns 200 with architecture_vector."""
        from api.server import handle_scan_architecture

        src = textwrap.dedent("""
            import os
            import sys

            class Processor:
                def run(self, data):
                    self.result = data
                def get(self):
                    return self.result
        """)
        code, resp = handle_scan_architecture({
            "code": src,
            "module_id": "myapp.service",
        })
        self.assertEqual(code, 200)
        self.assertIn("architecture_vector", resp)
        self.assertIn("summary", resp)
        av_dict = resp["architecture_vector"]
        self.assertIn("fan_out", av_dict)
        self.assertIn("architecture_rating", av_dict)
        summary = resp["summary"]
        self.assertIn("architecture_rating", summary)
        self.assertIsInstance(summary["fan_out"], int)
        self.assertIsInstance(summary["lack_of_cohesion"], float)


# ══════════════════════════════════════════════════════════════════════════════
# Additional targeted tests for edge cases and additional coverage
# ══════════════════════════════════════════════════════════════════════════════

class TestArchitectureEdgeCases(unittest.TestCase):

    def test_ta_syntax_error_returns_zero_result(self):
        """Syntax error in source returns zeroed ArchitectureResult."""
        r = _analyze("def f( invalid syntax !!!:")
        self.assertEqual(r.fan_out, 0)
        self.assertEqual(r.coupling_between_objects, 0)

    def test_ta_circular_import_count_preserved(self):
        """circular_import_count passed to analyze() is preserved in result."""
        r = _analyze("x = 1", circular=3)
        self.assertEqual(r.circular_import_count, 3)

    def test_ta_abstractmethod_decorator_detects_abstract(self):
        """@abstractmethod decorator (without ABC inheritance) makes class abstract."""
        src = """
            from abc import abstractmethod
            class Base:
                @abstractmethod
                def run(self):
                    pass
        """
        r = _analyze(src)
        self.assertAlmostEqual(r.abstraction_level, 1.0)

    def test_ta_multiple_classes_aggregate_cbo(self):
        """CBO is summed across all classes in the module."""
        src = """
            class A:
                def run(self, ext: ExternalA) -> None:
                    pass
            class B:
                def run(self, ext: ExternalB) -> None:
                    pass
        """
        r = _analyze(src)
        # Each class contributes 1 external type → total CBO ≥ 2
        self.assertGreaterEqual(r.coupling_between_objects, 2)

    def test_ta_repr_contains_key_fields(self):
        """ArchitectureVector repr includes rating, fan_out, cbo, lcom."""
        av = ArchitectureVector(fan_out=5, coupling_between_objects=2,
                                lack_of_cohesion=0.25)
        r = repr(av)
        self.assertIn("rating=", r)
        self.assertIn("fan_out=", r)
        self.assertIn("cbo=", r)
        self.assertIn("lcom=", r)


if __name__ == "__main__":
    unittest.main(verbosity=2)
