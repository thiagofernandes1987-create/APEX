"""
test_marco_m27.py — M9.0 Tree-Sitter Multi-Language SAST (30 tests TG01-TG30)
=============================================================================
Validates the M9.0 deliverable (→ v3.2.0):

  TG01-TG04  TreeSitterBridge (availability probe, regex fallback primitives)
  TG05-TG14  JavaScript / TypeScript rules JS01-JS10
  TG15-TG22  Java rules JV01-JV10
  TG23-TG28  Go rules GO01-GO10
  TG29-TG30  Engine integration (dispatch, rating, dedupe, clean code)
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lang_adapters.tree_sitter_bridge import TreeSitterBridge
from sast.multilang_scanner import (
    scan_multilang, rule_count, language_for_extension, _ALL_RULES,
)


def _ids(source: str, ext: str):
    return {f.rule_id for f in scan_multilang(source, ext).findings}


# ══════════════════════════════════════════════════════════════════════════════
# TG01-TG04 — TreeSitterBridge
# ══════════════════════════════════════════════════════════════════════════════

class TestTreeSitterBridge(unittest.TestCase):

    def test_TG01_available_returns_bool_no_crash(self):
        """TG01: available() never raises and returns a bool (grammar may be absent)."""
        b = TreeSitterBridge("javascript")
        self.assertIsInstance(b.available(), bool)

    def test_TG02_parse_none_in_fallback_mode(self):
        """TG02: when grammars are absent, parse() returns None (regex fallback)."""
        b = TreeSitterBridge("go")
        tree = b.parse("package main")
        # Either a real tree (if installed) or None (fallback) — both valid.
        self.assertTrue(tree is None or hasattr(tree, "root_node"))

    def test_TG03_iter_lines_numbers_from_one(self):
        """TG03: iter_lines yields 1-based line numbers."""
        lines = list(TreeSitterBridge.iter_lines("a\nb\nc"))
        self.assertEqual(lines[0], (1, "a"))
        self.assertEqual(lines[2], (3, "c"))

    def test_TG04_search_lines_reports_line_and_col(self):
        """TG04: search_lines returns (lineno, col, text, match)."""
        hits = list(TreeSitterBridge.search_lines(re.compile(r"eval"), "x\neval(y)\n"))
        self.assertEqual(len(hits), 1)
        lineno, col, text, m = hits[0]
        self.assertEqual(lineno, 2)
        self.assertEqual(col, 0)


# ══════════════════════════════════════════════════════════════════════════════
# TG05-TG14 — JavaScript / TypeScript
# ══════════════════════════════════════════════════════════════════════════════

class TestJavaScriptRules(unittest.TestCase):

    def test_TG05_js01_innerhtml_xss(self):
        self.assertIn("JS01", _ids("el.innerHTML = userInput;", ".js"))

    def test_TG06_js02_document_write(self):
        self.assertIn("JS02", _ids("document.write(data);", ".js"))

    def test_TG07_js03_dangerously_set_inner_html(self):
        self.assertIn("JS03", _ids('<div dangerouslySetInnerHTML={{ __html: x }} />', ".tsx"))

    def test_TG08_js04_eval(self):
        self.assertIn("JS04", _ids("const r = eval(expr);", ".js"))

    def test_TG09_js05_function_constructor(self):
        self.assertIn("JS05", _ids("const f = new Function('return 1');", ".ts"))

    def test_TG10_js06_child_process_exec_interpolation(self):
        self.assertIn("JS06", _ids("child_process.exec(`ls ${dir}`);", ".js"))

    def test_TG11_js07_prototype_pollution(self):
        self.assertIn("JS07", _ids('obj["__proto__"] = payload;', ".js"))

    def test_TG12_js08_weak_hash_md5(self):
        self.assertIn("JS08", _ids("const h = crypto.createHash('md5');", ".js"))

    def test_TG13_js09_math_random(self):
        self.assertIn("JS09", _ids("const token = Math.random();", ".js"))

    def test_TG14_js10_sql_concat(self):
        self.assertIn("JS10", _ids('db.query("SELECT * FROM t WHERE id=" + id);', ".js"))


# ══════════════════════════════════════════════════════════════════════════════
# TG15-TG22 — Java
# ══════════════════════════════════════════════════════════════════════════════

class TestJavaRules(unittest.TestCase):

    def test_TG15_jv01_runtime_exec(self):
        self.assertIn("JV01", _ids('Runtime.getRuntime().exec("sh -c " + cmd);', ".java"))

    def test_TG16_jv02_sql_statement_concat(self):
        self.assertIn("JV02", _ids('st.executeQuery("SELECT * FROM t WHERE id=" + id);', ".java"))

    def test_TG17_jv03_xxe_documentbuilder(self):
        self.assertIn("JV03", _ids("DocumentBuilderFactory.newInstance();", ".java"))

    def test_TG18_jv04_object_input_stream(self):
        self.assertIn("JV04", _ids("ObjectInputStream ois = new ObjectInputStream(in);", ".java"))

    def test_TG19_jv05_weak_messagedigest(self):
        self.assertIn("JV05", _ids('MessageDigest.getInstance("MD5");', ".java"))

    def test_TG20_jv07_hardcoded_password(self):
        self.assertIn("JV07", _ids('String password = "supersecret";', ".java"))

    def test_TG21_jv08_insecure_random(self):
        self.assertIn("JV08", _ids("Random rng = new Random();", ".java"))

    def test_TG22_jv09_cors_wildcard(self):
        self.assertIn("JV09", _ids('@CrossOrigin("*")', ".java"))


# ══════════════════════════════════════════════════════════════════════════════
# TG23-TG28 — Go
# ══════════════════════════════════════════════════════════════════════════════

class TestGoRules(unittest.TestCase):

    def test_TG23_go01_exec_command_concat(self):
        self.assertIn("GO01", _ids('exec.Command("sh", "-c", "ls "+dir)', ".go"))

    def test_TG24_go02_sql_sprintf(self):
        self.assertIn("GO02", _ids('db.Query(fmt.Sprintf("SELECT %d", id))', ".go"))

    def test_TG25_go03_weak_hash(self):
        self.assertIn("GO03", _ids("h := md5.New()", ".go"))

    def test_TG26_go04_math_rand(self):
        self.assertIn("GO04", _ids("n := rand.Intn(100)", ".go"))

    def test_TG27_go05_insecure_skip_verify(self):
        self.assertIn("GO05", _ids("tls.Config{InsecureSkipVerify: true}", ".go"))

    def test_TG28_go08_text_template(self):
        self.assertIn("GO08", _ids('import "text/template"', ".go"))


# ══════════════════════════════════════════════════════════════════════════════
# TG29-TG30 — Engine integration
# ══════════════════════════════════════════════════════════════════════════════

class TestEngineIntegration(unittest.TestCase):

    def test_TG29_rule_inventory_and_dispatch(self):
        """TG29: 43 rules total; unsupported ext → empty; rating reflects worst sev."""
        self.assertEqual(rule_count(), 43)
        self.assertEqual(len(_ALL_RULES), 43)
        # Unsupported extension returns an empty, error-free result
        empty = scan_multilang("x = 1", ".py")
        self.assertEqual(empty.findings, [])
        self.assertFalse(empty.parse_error)
        # CRITICAL finding → rating E
        crit = scan_multilang("eval(x);", ".js")
        self.assertEqual(crit.security_rating, "E")

    def test_TG30_clean_code_and_comment_skipping(self):
        """TG30: clean code yields no findings; // commented threats are ignored."""
        clean_js = "const x = 1;\nconst y = JSON.parse(s);\nel.textContent = v;\n"
        self.assertEqual(scan_multilang(clean_js, ".js").findings, [])
        # A threat inside a // comment must not be flagged
        commented = "// eval(payload) is dangerous, do not use\nconst x = 1;\n"
        self.assertEqual(scan_multilang(commented, ".js").findings, [])


if __name__ == "__main__":
    unittest.main()
