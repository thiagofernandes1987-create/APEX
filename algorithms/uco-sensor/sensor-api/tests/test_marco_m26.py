"""
test_marco_m26.py — AFix+ FASE 8: 4 security autofix transforms (30 tests TX01-TX30)
=====================================================================================
Validates the AFix+ deliverable (FASE 8 → v3.1.3):

  TX01-TX08  WeakHashReplacer        (hashlib.md5/sha1 → sha256, hashlib.new form)
  TX09-TX16  InsecureRandomReplacer  (random.choice → secrets.choice + import; advisory)
  TX17-TX22  LoopGuardAdvisor        (while True without break — advisory)
  TX23-TX27  FormatStringModernizer  ("%s" % x — advisory)
  TX28-TX30  Engine integration       (16-transform pipeline, validity, idempotence)
"""
from __future__ import annotations

import ast
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

from sensor_core.autofix.engine import AutofixEngine, _DEFAULT_PIPELINE
from sensor_core.autofix.transforms import (
    WeakHashReplacer, InsecureRandomReplacer,
    LoopGuardAdvisor, FormatStringModernizer,
)


def _run(transform, src: str):
    """Apply a single transform to dedented source; return (new_src, results)."""
    src = textwrap.dedent(src).lstrip("\n")
    tree = ast.parse(src)
    new_tree, results = transform.apply(tree, src)
    return ast.unparse(new_tree), results


# ══════════════════════════════════════════════════════════════════════════════
# TX01-TX08 — WeakHashReplacer
# ══════════════════════════════════════════════════════════════════════════════

class TestWeakHashReplacer(unittest.TestCase):

    def test_TX01_md5_rewritten_to_sha256(self):
        out, res = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.md5(b'a')\n")
        self.assertIn("hashlib.sha256", out)
        self.assertNotIn("hashlib.md5", out)
        self.assertEqual(len(res), 1)

    def test_TX02_sha1_rewritten_to_sha256(self):
        out, _ = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.sha1(b'a')\n")
        self.assertIn("hashlib.sha256", out)
        self.assertNotIn("hashlib.sha1", out)

    def test_TX03_hashlib_new_md5_string_rewritten(self):
        out, res = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.new('md5')\n")
        self.assertIn("'sha256'", out)
        self.assertEqual(len(res), 1)

    def test_TX04_hashlib_new_sha1_string_rewritten(self):
        out, _ = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.new('SHA1')\n")
        self.assertIn("'sha256'", out)

    def test_TX05_sha256_already_strong_untouched(self):
        out, res = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.sha256(b'a')\n")
        self.assertEqual(res, [])
        self.assertIn("hashlib.sha256", out)

    def test_TX06_bare_md5_not_hashlib_untouched(self):
        # bare md5() of unknown provenance must NOT be rewritten
        out, res = _run(WeakHashReplacer(), "x = md5(b'a')\n")
        self.assertEqual(res, [])
        self.assertIn("md5", out)

    def test_TX07_preserves_arguments(self):
        out, _ = _run(WeakHashReplacer(),
                      "import hashlib\nx = hashlib.md5(b'data', usedforsecurity=True)\n")
        self.assertIn("b'data'", out)
        self.assertIn("usedforsecurity=True", out)

    def test_TX08_cwe_referenced_in_description(self):
        _, res = _run(WeakHashReplacer(), "import hashlib\nx = hashlib.md5(b'a')\n")
        self.assertIn("CWE-327", res[0].description)


# ══════════════════════════════════════════════════════════════════════════════
# TX09-TX16 — InsecureRandomReplacer
# ══════════════════════════════════════════════════════════════════════════════

class TestInsecureRandomReplacer(unittest.TestCase):

    def test_TX09_random_choice_rewritten(self):
        out, res = _run(InsecureRandomReplacer(),
                        "import random\nx = random.choice(pool)\n")
        self.assertIn("secrets.choice(pool)", out)
        self.assertTrue(any("secrets.choice" in r.description for r in res))

    def test_TX10_secrets_import_injected(self):
        out, _ = _run(InsecureRandomReplacer(),
                      "import random\nx = random.choice(pool)\n")
        self.assertIn("import secrets", out)

    def test_TX11_secrets_import_not_duplicated(self):
        out, _ = _run(InsecureRandomReplacer(),
                      "import random\nimport secrets\nx = random.choice(pool)\n")
        self.assertEqual(out.count("import secrets"), 1)

    def test_TX12_randint_is_advisory_not_rewritten(self):
        out, res = _run(InsecureRandomReplacer(),
                        "import random\nx = random.randint(1, 9)\n")
        self.assertIn("random.randint", out)  # not mutated
        self.assertTrue(any("[ADVISORY]" in r.description for r in res))

    def test_TX13_random_random_advisory(self):
        _, res = _run(InsecureRandomReplacer(),
                      "import random\nx = random.random()\n")
        self.assertTrue(any("ADVISORY" in r.description for r in res))

    def test_TX14_no_secrets_import_when_only_advisory(self):
        out, _ = _run(InsecureRandomReplacer(),
                      "import random\nx = random.randint(1, 9)\n")
        self.assertNotIn("import secrets", out)

    def test_TX15_bare_choice_untouched(self):
        out, res = _run(InsecureRandomReplacer(), "x = choice(pool)\n")
        self.assertEqual(res, [])

    def test_TX16_output_is_valid_python(self):
        out, _ = _run(InsecureRandomReplacer(),
                      "import random\nx = random.choice(pool)\n")
        ast.parse(out)  # must not raise


# ══════════════════════════════════════════════════════════════════════════════
# TX17-TX22 — LoopGuardAdvisor
# ══════════════════════════════════════════════════════════════════════════════

class TestLoopGuardAdvisor(unittest.TestCase):

    def test_TX17_while_true_without_break_flagged(self):
        _, res = _run(LoopGuardAdvisor(), "while True:\n    work()\n")
        self.assertEqual(len(res), 1)
        self.assertIn("CWE-835", res[0].description)

    def test_TX18_while_true_with_break_ok(self):
        _, res = _run(LoopGuardAdvisor(),
                      "while True:\n    if done():\n        break\n")
        self.assertEqual(res, [])

    def test_TX19_while_true_with_return_ok(self):
        _, res = _run(LoopGuardAdvisor(),
                      "def f():\n    while True:\n        return 1\n")
        self.assertEqual(res, [])

    def test_TX20_while_true_with_raise_ok(self):
        _, res = _run(LoopGuardAdvisor(),
                      "while True:\n    raise SystemExit\n")
        self.assertEqual(res, [])

    def test_TX21_while_condition_not_true_ignored(self):
        _, res = _run(LoopGuardAdvisor(), "while running:\n    work()\n")
        self.assertEqual(res, [])

    def test_TX22_advisory_does_not_mutate_source(self):
        out, _ = _run(LoopGuardAdvisor(), "while True:\n    work()\n")
        self.assertIn("while True", out)


# ══════════════════════════════════════════════════════════════════════════════
# TX23-TX27 — FormatStringModernizer
# ══════════════════════════════════════════════════════════════════════════════

class TestFormatStringModernizer(unittest.TestCase):

    def test_TX23_percent_s_flagged(self):
        _, res = _run(FormatStringModernizer(), "msg = 'Hello %s' % name\n")
        self.assertEqual(len(res), 1)

    def test_TX24_percent_d_flagged(self):
        _, res = _run(FormatStringModernizer(), "msg = 'count %d' % n\n")
        self.assertEqual(len(res), 1)

    def test_TX25_no_conversion_specifier_ignored(self):
        # "100%" has no conversion spec → should be ignored
        _, res = _run(FormatStringModernizer(), "msg = '100 percent' % ()\n")
        self.assertEqual(res, [])

    def test_TX26_non_string_mod_ignored(self):
        # numeric modulo must never be flagged
        _, res = _run(FormatStringModernizer(), "x = 10 % 3\n")
        self.assertEqual(res, [])

    def test_TX27_advisory_does_not_mutate(self):
        out, _ = _run(FormatStringModernizer(), "msg = 'Hi %s' % name\n")
        self.assertIn("%s", out)


# ══════════════════════════════════════════════════════════════════════════════
# TX28-TX30 — Engine integration
# ══════════════════════════════════════════════════════════════════════════════

class TestEngineIntegration(unittest.TestCase):

    def test_TX28_default_pipeline_has_16_transforms(self):
        self.assertEqual(len(_DEFAULT_PIPELINE), 16)
        names = {t.__name__ for t in _DEFAULT_PIPELINE}
        for n in ("WeakHashReplacer", "InsecureRandomReplacer",
                  "LoopGuardAdvisor", "FormatStringModernizer"):
            self.assertIn(n, names)

    def test_TX29_end_to_end_security_fix_valid(self):
        eng = AutofixEngine()
        src = textwrap.dedent("""
            import hashlib
            import random
            def token(pool):
                h = hashlib.md5(b'x').hexdigest()
                return random.choice(pool)
        """).lstrip("\n")
        result = eng.apply(src)
        self.assertTrue(result.is_valid_python)
        self.assertIn("hashlib.sha256", result.fixed_source)
        self.assertIn("secrets.choice", result.fixed_source)
        applied = {r.transform for r in result.transforms_applied}
        self.assertIn("WeakHashReplacer", applied)
        self.assertIn("InsecureRandomReplacer", applied)

    def test_TX30_idempotent_on_already_fixed_code(self):
        eng = AutofixEngine()
        clean = textwrap.dedent('''
            import hashlib
            import secrets
            def token(pool: object) -> object:
                """Docstring."""
                h = hashlib.sha256(b'x').hexdigest()
                return secrets.choice(pool)
        ''').lstrip("\n")
        result = eng.apply(clean)
        # No weak-hash / insecure-random transform should fire on clean code
        applied = {r.transform for r in result.transforms_applied}
        self.assertNotIn("WeakHashReplacer", applied)
        self.assertNotIn("InsecureRandomReplacer", applied)
        self.assertTrue(result.is_valid_python)


if __name__ == "__main__":
    unittest.main()
