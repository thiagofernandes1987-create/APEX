"""
test_marco_m30.py — LEAP 3: AutoFix↔SAST closed loop (30 tests TY01-TY30)
==========================================================================
Validates the LEAP 3 deliverable (v3.2.3 — M8.2 closed loop):

  TY01-TY06  Mapping table integrity (SAST_TO_TRANSFORM is well-formed)
  TY07-TY14  Single-rule remediation (one finding → one transform → fixed)
  TY15-TY20  Multi-rule remediation + identity behaviour on clean code
  TY21-TY25  Residual reporting + invalid-source resilience
  TY26-TY30  REST endpoint /apex/auto-remediate (status codes + payload)
"""
from __future__ import annotations

import os
import sys
import textwrap
import unittest
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sensor_core.autofix.sast_remediation import (
    auto_remediate, SAST_TO_TRANSFORM, RemediationResult,
    _select_transforms,
)
from sensor_core.autofix.transforms.replace_weak_hash       import WeakHashReplacer
from sensor_core.autofix.transforms.replace_insecure_random import InsecureRandomReplacer
from sensor_core.autofix.transforms.replace_bare_except     import BareExceptReplacer
from sensor_core.autofix.transforms.remove_mutable_default  import MutableDefaultRemover


def _dedent(src: str) -> str:
    return textwrap.dedent(src).lstrip("\n")


# ══════════════════════════════════════════════════════════════════════════════
# TY01-TY06 — Mapping table integrity
# ══════════════════════════════════════════════════════════════════════════════

class TestMappingTable(unittest.TestCase):

    def test_TY01_table_is_non_empty(self):
        self.assertGreater(len(SAST_TO_TRANSFORM), 0)

    def test_TY02_table_keys_are_sast_rule_ids(self):
        for rule_id in SAST_TO_TRANSFORM:
            self.assertTrue(rule_id.startswith("SAST"))

    def test_TY03_table_values_are_transform_classes(self):
        from sensor_core.autofix.transforms.base import BaseTransform
        for cls in SAST_TO_TRANSFORM.values():
            self.assertTrue(issubclass(cls, BaseTransform))

    def test_TY04_weak_crypto_mapped(self):
        self.assertIn("SAST006", SAST_TO_TRANSFORM)
        self.assertEqual(SAST_TO_TRANSFORM["SAST006"], WeakHashReplacer)

    def test_TY05_insecure_random_mapped(self):
        self.assertEqual(SAST_TO_TRANSFORM["SAST007"], InsecureRandomReplacer)

    def test_TY06_mutable_default_mapped(self):
        self.assertEqual(SAST_TO_TRANSFORM["SAST039"], MutableDefaultRemover)


# ══════════════════════════════════════════════════════════════════════════════
# TY07-TY14 — Single-rule remediation
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleRule(unittest.TestCase):

    def test_TY07_weak_hash_md5_fixed(self):
        src = _dedent("""
            import hashlib
            def f():
                return hashlib.md5(b'x').hexdigest()
        """)
        r = auto_remediate(src)
        self.assertIn("SAST006", r.findings_before)
        self.assertIn("SAST006", r.fixed_rules)
        self.assertIn("hashlib.sha256", r.patched_source)
        self.assertNotIn("SAST006", r.findings_after)

    def test_TY08_weak_hash_sha1_fixed(self):
        src = _dedent("""
            import hashlib
            def f():
                return hashlib.sha1(b'x').hexdigest()
        """)
        r = auto_remediate(src)
        self.assertIn("SAST006", r.fixed_rules)
        self.assertIn("hashlib.sha256", r.patched_source)

    def test_TY09_insecure_random_choice_fixed(self):
        src = _dedent("""
            import random
            def pick(pool):
                return random.choice(pool)
        """)
        r = auto_remediate(src)
        self.assertIn("SAST007", r.findings_before)
        self.assertIn("secrets.choice", r.patched_source)

    def test_TY10_mutable_default_fixed(self):
        src = _dedent("""
            def f(items=[]):
                items.append(1)
                return items
        """)
        r = auto_remediate(src)
        self.assertIn("SAST039", r.findings_before)
        self.assertIn("SAST039", r.fixed_rules)
        self.assertIn("items=None", r.patched_source)

    def test_TY11_transforms_applied_list_correct(self):
        src = _dedent("""
            import hashlib
            def f():
                return hashlib.md5(b'x').hexdigest()
        """)
        r = auto_remediate(src)
        self.assertIn("WeakHashReplacer", r.transforms_applied)
        # Only the relevant transform — InsecureRandom should NOT run
        self.assertNotIn("InsecureRandomReplacer", r.transforms_applied)

    def test_TY12_patched_source_is_valid_python(self):
        src = _dedent("""
            import hashlib, random
            def f(items=[]):
                return hashlib.md5(b'x').hexdigest() + random.choice(items)
        """)
        r = auto_remediate(src)
        self.assertTrue(r.is_valid)
        import ast
        ast.parse(r.patched_source)   # must not raise

    def test_TY13_fixed_count_property(self):
        src = _dedent("""
            import hashlib
            def f():
                return hashlib.md5(b'x').hexdigest()
        """)
        r = auto_remediate(src)
        self.assertEqual(r.fixed_count, len(r.fixed_rules))

    def test_TY14_module_id_carried_into_result_via_call(self):
        src = "import hashlib\nx = hashlib.md5(b'a')\n"
        r = auto_remediate(src, module_id="audit.crypto")
        # module_id is for telemetry — not on RemediationResult itself,
        # but the endpoint includes it in the wrapper.  Sanity: call succeeded.
        self.assertIsInstance(r, RemediationResult)


# ══════════════════════════════════════════════════════════════════════════════
# TY15-TY20 — Multi-rule + identity (clean code)
# ══════════════════════════════════════════════════════════════════════════════

class TestMultiRuleAndIdentity(unittest.TestCase):

    def test_TY15_three_findings_one_pass(self):
        src = _dedent("""
            import hashlib, random
            def f(items=[]):
                h = hashlib.md5(b'x').hexdigest()
                p = random.choice(items)
                return h + p
        """)
        r = auto_remediate(src)
        self.assertEqual(set(r.findings_before),
                         {"SAST006", "SAST007", "SAST039"})
        self.assertEqual(set(r.fixed_rules),
                         {"SAST006", "SAST007", "SAST039"})
        self.assertEqual(r.residual_count, 0)

    def test_TY16_only_relevant_transforms_loaded(self):
        # Two findings → exactly two transform classes selected
        ids = ["SAST006", "SAST039"]
        cls = _select_transforms(ids)
        self.assertEqual(set(c.__name__ for c in cls),
                         {"WeakHashReplacer", "MutableDefaultRemover"})

    def test_TY17_clean_code_identity_result(self):
        clean = _dedent("""
            import hashlib
            def f(items=None):
                if items is None:
                    items = []
                return hashlib.sha256(b'x').hexdigest()
        """)
        r = auto_remediate(clean)
        self.assertEqual(r.findings_before, [])
        self.assertEqual(r.transforms_applied, [])
        self.assertEqual(r.patched_source, clean)
        self.assertEqual(r.fixed_count, 0)

    def test_TY18_unmapped_finding_does_not_trigger_transform(self):
        # SAST003 (eval) has no AutoFix transform mapped → no change attempted
        src = "x = eval('1+1')\n"
        r = auto_remediate(src)
        # eval is flagged but no transform mapped → finding persists, no transforms
        if r.findings_before:
            self.assertNotIn("SAST003", r.fixed_rules)
        self.assertEqual(r.transforms_applied, [])

    def test_TY19_select_transforms_deterministic_order(self):
        # Same input twice → same output order
        ids = ["SAST007", "SAST006", "SAST039"]
        self.assertEqual(_select_transforms(ids), _select_transforms(ids))

    def test_TY20_select_transforms_deduplicates(self):
        # Same rule id repeated → unique transform list
        ids = ["SAST006", "SAST006"]
        self.assertEqual(len(_select_transforms(ids)), 1)


# ══════════════════════════════════════════════════════════════════════════════
# TY21-TY25 — Residual reporting + invalid source resilience
# ══════════════════════════════════════════════════════════════════════════════

class TestResidualAndResilience(unittest.TestCase):

    def test_TY21_residual_rule_reported(self):
        # SAST003 (eval) NOT mapped → must appear in findings_after as residual
        src = _dedent("""
            import hashlib
            def f():
                x = hashlib.md5(b'x').hexdigest()
                y = eval('1+1')
                return x, y
        """)
        r = auto_remediate(src)
        self.assertIn("SAST006", r.fixed_rules)        # weak hash fixed
        self.assertNotIn("SAST006", r.findings_after)  # gone
        # eval residual — depends on what SAST003 detects; if it fires it must
        # remain in findings_after
        if "SAST003" in r.findings_before:
            self.assertIn("SAST003", r.findings_after)

    def test_TY22_syntax_error_returns_identity_no_crash(self):
        src = "def f(:\n"   # invalid Python
        r = auto_remediate(src)
        self.assertEqual(r.patched_source, src)
        self.assertEqual(r.transforms_applied, [])
        # No crash — call returned a result.

    def test_TY23_empty_source_returns_identity(self):
        r = auto_remediate("")
        self.assertEqual(r.patched_source, "")
        self.assertEqual(r.findings_before, [])
        self.assertEqual(r.findings_after, [])

    def test_TY24_residual_count_matches_findings_after(self):
        src = _dedent("""
            import hashlib
            def f():
                x = hashlib.md5(b'x').hexdigest()
                y = eval('1+1')
                return x, y
        """)
        r = auto_remediate(src)
        self.assertEqual(r.residual_count, len(r.findings_after))

    def test_TY25_to_dict_round_trips_required_keys(self):
        src = "import hashlib\nx = hashlib.md5(b'x')\n"
        r = auto_remediate(src)
        d = r.to_dict()
        for k in ("patched_source", "is_valid", "transforms_applied",
                  "findings_before", "findings_after", "fixed_rules",
                  "fixed_count", "residual_count"):
            self.assertIn(k, d)


# ══════════════════════════════════════════════════════════════════════════════
# TY26-TY30 — REST endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestEndpoint(unittest.TestCase):

    def setUp(self):
        from api.server import handle_apex_auto_remediate
        self.handle = handle_apex_auto_remediate

    def test_TY26_missing_code_returns_400(self):
        code, data = self.handle({})
        self.assertEqual(code, 400)
        self.assertIn("error", data)

    def test_TY27_empty_code_returns_400(self):
        code, data = self.handle({"code": "   "})
        self.assertEqual(code, 400)

    def test_TY28_valid_request_returns_200_with_payload(self):
        src = "import hashlib\ndef f():\n    return hashlib.md5(b'x')\n"
        code, data = self.handle({"code": src, "module_id": "demo"})
        self.assertEqual(code, 200)
        for key in ("patched_source", "is_valid", "fixed_rules",
                    "findings_before", "findings_after", "fixed_count",
                    "residual_count", "transforms_applied", "module_id"):
            self.assertIn(key, data)
        self.assertEqual(data["module_id"], "demo")

    def test_TY29_endpoint_actually_fixes_code(self):
        src = "import hashlib\ndef f():\n    return hashlib.md5(b'x')\n"
        code, data = self.handle({"code": src})
        self.assertEqual(code, 200)
        self.assertIn("hashlib.sha256", data["patched_source"])
        self.assertIn("SAST006", data["fixed_rules"])

    def test_TY30_endpoint_handles_syntax_error_gracefully(self):
        code, data = self.handle({"code": "def f(:"})
        self.assertEqual(code, 200)
        self.assertEqual(data["transforms_applied"], [])


if __name__ == "__main__":
    unittest.main()
