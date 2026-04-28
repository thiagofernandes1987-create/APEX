"""
test_marco_m18.py — UCO-Sensor M8.1 (FASE 4) — IDE/LSP Integration
====================================================================
Tests for v2.7.0 deliverables:
  TL01-TL10  SASTFinding enrichment (suggested_fix, confidence, explanation)
  TL11-TL16  TaintFlow enrichment (suggested_fix, confidence, explanation)
  TL17-TL24  AutoFix transforms #5-12 (M8.1 new transforms)
  TL25-TL30  LSP endpoint (handle_lsp_diagnostics format + signals)

All tests are pure unit tests — no network, no DB, no filesystem side effects.
"""
from __future__ import annotations

import ast
import sys
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

# ── path setup ────────────────────────────────────────────────────────────────
_SENSOR_DIR = Path(__file__).resolve().parent.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

import pytest


# =============================================================================
# TL01-TL10 — SASTFinding enrichment (WBS 6.1)
# =============================================================================

class TestSASTFindingEnrichment:
    """TL01-TL07: SASTFinding now carries suggested_fix, confidence, explanation."""

    def setup_method(self):
        from sast.scanner import scan, SASTFinding, RULES, _RULE_MAP
        self.scan      = scan
        self.SASTFinding = SASTFinding
        self.RULES     = RULES
        self.RULE_MAP  = _RULE_MAP

    def test_tl01_sast_finding_has_suggested_fix(self):
        """TL01: SASTFinding dataclass exposes suggested_fix field."""
        from sast.scanner import SASTFinding
        f = SASTFinding(
            rule_id="SAST001", severity="CRITICAL", cwe_id="CWE-89",
            owasp="A03:2021", title="SQL Injection", description="d",
            line=1, col=0, code_snippet="x", remediation="r",
            debt_minutes=240, suggested_fix="use param", confidence=0.9,
            explanation="explain",
        )
        assert f.suggested_fix == "use param"
        assert f.confidence    == 0.9
        assert f.explanation   == "explain"

    def test_tl02_sast_finding_to_dict_includes_new_fields(self):
        """TL02: to_dict() serialises the three new fields."""
        from sast.scanner import SASTFinding
        f = SASTFinding(
            rule_id="SAST002", severity="CRITICAL", cwe_id="CWE-78",
            owasp="A03:2021", title="OS Cmd", description="d",
            line=5, col=2, code_snippet="os.system(x)", remediation="r",
            debt_minutes=240, suggested_fix="subprocess.run(['cmd'])",
            confidence=0.85, explanation="shell injection",
        )
        d = f.to_dict()
        assert d["suggested_fix"] == "subprocess.run(['cmd'])"
        assert d["confidence"]    == 0.85
        assert d["explanation"]   == "shell injection"

    def test_tl03_sast001_rule_has_suggested_fix(self):
        """TL03: SAST001 (SQL Injection) rule carries a suggested_fix."""
        rule = self.RULE_MAP.get("SAST001")
        assert rule is not None
        assert rule.suggested_fix != ""
        assert "param" in rule.suggested_fix.lower() or "execute" in rule.suggested_fix.lower()

    def test_tl04_sast002_rule_has_suggested_fix(self):
        """TL04: SAST002 (OS Command Injection) rule carries a suggested_fix."""
        rule = self.RULE_MAP.get("SAST002")
        assert rule is not None
        assert rule.suggested_fix != ""
        assert "subprocess" in rule.suggested_fix.lower() or "shell" in rule.suggested_fix.lower()

    def test_tl05_sast003_rule_has_suggested_fix(self):
        """TL05: SAST003 (eval/exec) rule carries a suggested_fix."""
        rule = self.RULE_MAP.get("SAST003")
        assert rule is not None
        assert rule.suggested_fix != ""
        assert rule.confidence == 0.95   # higher confidence for eval

    def test_tl06_scan_sast001_finding_has_suggested_fix(self):
        """TL06: SAST001 findings from scan() include suggested_fix."""
        source = """
import sqlite3
def query(user_id):
    conn = sqlite3.connect('db.sqlite')
    cursor = conn.cursor()
    sql = "SELECT * FROM users WHERE id = " + user_id
    cursor.execute(sql)
"""
        result = self.scan(source)
        sql_findings = [f for f in result.findings if f.rule_id == "SAST001"]
        assert sql_findings, "Expected SAST001 findings"
        f = sql_findings[0]
        assert isinstance(f.suggested_fix, str)
        assert isinstance(f.confidence, float)
        assert isinstance(f.explanation, str)

    def test_tl07_default_rule_confidence(self):
        """TL07: Rules without explicit confidence default to 0.9."""
        rule = self.RULE_MAP.get("SAST004")   # Pickle — no explicit confidence set
        assert rule is not None
        assert rule.confidence == 0.9

    def test_tl08_default_finding_fields_empty_str(self):
        """TL08: Rules without suggested_fix/explanation produce empty strings (not None)."""
        rule = self.RULE_MAP.get("SAST005")   # YAML unsafe load
        assert rule is not None
        assert rule.suggested_fix == "" or isinstance(rule.suggested_fix, str)
        assert rule.explanation   == "" or isinstance(rule.explanation, str)

    def test_tl09_all_rules_have_confidence_float(self):
        """TL09: Every rule in RULES has confidence as a float between 0 and 1."""
        for rule in self.RULES:
            assert isinstance(rule.confidence, float), f"{rule.rule_id} confidence not float"
            assert 0.0 <= rule.confidence <= 1.0,      f"{rule.rule_id} confidence out of range"

    def test_tl10_scan_result_to_dict_roundtrip(self):
        """TL10: SASTResult.to_dict() round-trips cleanly with new fields."""
        source = "import os\nos.system(user_input)"
        result = self.scan(source)
        d = result.to_dict()
        assert "findings" in d
        for finding_dict in d["findings"]:
            assert "suggested_fix" in finding_dict
            assert "confidence"    in finding_dict
            assert "explanation"   in finding_dict


# =============================================================================
# TL11-TL16 — TaintFlow enrichment (WBS 6.1 — taint_engine.py)
# =============================================================================

class TestTaintFlowEnrichment:
    """TL11-TL16: TaintFlow.to_dict() exposes suggested_fix, confidence, explanation."""

    def setup_method(self):
        from sast.taint_engine import TaintAnalyzer, _TAINT_RULE_META
        self.TaintAnalyzer    = TaintAnalyzer
        self.TAINT_RULE_META  = _TAINT_RULE_META

    def test_tl11_taint_rule_meta_has_suggested_fix(self):
        """TL11: All taint rules in _TAINT_RULE_META have suggested_fix."""
        for rule_id, meta in self.TAINT_RULE_META.items():
            assert "suggested_fix" in meta, f"{rule_id} missing suggested_fix"
            assert isinstance(meta["suggested_fix"], str)

    def test_tl12_taint_rule_meta_has_explanation(self):
        """TL12: All taint rules in _TAINT_RULE_META have explanation."""
        for rule_id, meta in self.TAINT_RULE_META.items():
            assert "explanation" in meta, f"{rule_id} missing explanation"
            assert meta["explanation"] != "", f"{rule_id} explanation is empty"

    def test_tl13_taint_rule_meta_has_confidence(self):
        """TL13: All taint rules have confidence float in (0, 1]."""
        for rule_id, meta in self.TAINT_RULE_META.items():
            c = meta.get("confidence", -1)
            assert isinstance(c, float), f"{rule_id} confidence not float"
            assert 0.0 < c <= 1.0,       f"{rule_id} confidence out of range"

    def test_tl14_taintflow_to_dict_includes_suggested_fix(self):
        """TL14: TaintFlow.to_dict() includes suggested_fix."""
        source = """
def handler(request):
    uid = request.args
    cursor.execute(uid)
"""
        result = self.TaintAnalyzer().analyze(source)
        assert result.flows, "Expected at least one taint flow"
        d = result.flows[0].to_dict()
        assert "suggested_fix" in d
        assert isinstance(d["suggested_fix"], str)

    def test_tl15_taintflow_to_dict_includes_confidence(self):
        """TL15: TaintFlow.to_dict() includes confidence float."""
        source = """
def handler(request):
    cmd = request.args['cmd']
    import os
    os.system(cmd)
"""
        result = self.TaintAnalyzer().analyze(source)
        flows = [f for f in result.flows if f.rule_id == "SAST041"]
        assert flows, "Expected SAST041 flow"
        d = flows[0].to_dict()
        assert "confidence" in d
        assert isinstance(d["confidence"], float)
        assert d["confidence"] > 0

    def test_tl16_taintflow_to_dict_includes_explanation(self):
        """TL16: TaintFlow.to_dict() includes explanation string."""
        source = """
def handler(request):
    expr = request.form['expr']
    eval(expr)
"""
        result = self.TaintAnalyzer().analyze(source)
        flows = [f for f in result.flows if f.rule_id == "SAST043"]
        assert flows, "Expected SAST043 (code injection) flow"
        d = flows[0].to_dict()
        assert "explanation" in d
        assert isinstance(d["explanation"], str)
        assert d["explanation"] != ""


# =============================================================================
# TL17-TL24 — AutoFix transforms #5-12 (WBS 6.2)
# =============================================================================

class TestAutofixTransforms:
    """TL17-TL24: 8 new AutoFix transforms produce correct results."""

    def _apply(self, transform_cls, source: str):
        tree = ast.parse(source)
        t = transform_cls()
        new_tree, results = t.apply(tree, source)
        fixed = ast.unparse(new_tree)
        return fixed, results

    def test_tl17_mutable_default_remover_basic(self):
        """TL17: MutableDefaultRemover replaces =[] with =None."""
        from sensor_core.autofix.transforms.remove_mutable_default import MutableDefaultRemover
        src = "def f(items=[]):\n    pass\n"
        fixed, results = self._apply(MutableDefaultRemover, src)
        assert results, "Expected at least one TransformResult"
        assert "items" in results[0].description
        assert "None" in fixed  # default replaced

    def test_tl18_bare_except_replacer(self):
        """TL18: BareExceptReplacer replaces bare except: with except Exception as e."""
        from sensor_core.autofix.transforms.replace_bare_except import BareExceptReplacer
        src = "try:\n    pass\nexcept:\n    pass\n"
        fixed, results = self._apply(BareExceptReplacer, src)
        assert results, "Expected TransformResult"
        assert "Exception" in fixed
        assert "except:" not in fixed

    def test_tl19_none_comparison_simplifier_eq(self):
        """TL19: NoneComparisonSimplifier rewrites x == None → x is None."""
        from sensor_core.autofix.transforms.simplify_comparison import NoneComparisonSimplifier
        src = "if x == None:\n    pass\n"
        fixed, results = self._apply(NoneComparisonSimplifier, src)
        assert results
        assert "is None" in fixed
        assert "== None" not in fixed

    def test_tl20_none_comparison_simplifier_neq(self):
        """TL20: NoneComparisonSimplifier rewrites x != None → x is not None."""
        from sensor_core.autofix.transforms.simplify_comparison import NoneComparisonSimplifier
        src = "if x != None:\n    pass\n"
        fixed, results = self._apply(NoneComparisonSimplifier, src)
        assert results
        assert "is not None" in fixed

    def test_tl21_docstring_adder_public(self):
        """TL21: DocstringAdder adds placeholder docstring to public function."""
        from sensor_core.autofix.transforms.add_docstring import DocstringAdder
        src = "def process(data):\n    return data\n"
        fixed, results = self._apply(DocstringAdder, src)
        assert results, "Expected TransformResult"
        assert "TODO" in fixed

    def test_tl21b_docstring_adder_skips_private(self):
        """TL21b: DocstringAdder does NOT add docstring to private functions."""
        from sensor_core.autofix.transforms.add_docstring import DocstringAdder
        src = "def _helper(x):\n    return x\n"
        _, results = self._apply(DocstringAdder, src)
        assert not results, "Private function should be skipped"

    def test_tl22_context_manager_advisor(self):
        """TL22: ContextManagerAdvisor detects open() outside with."""
        from sensor_core.autofix.transforms.add_context_manager import ContextManagerAdvisor
        src = "f = open('data.txt')\ndata = f.read()\nf.close()\n"
        tree = ast.parse(src)
        t = ContextManagerAdvisor()
        new_tree, results = t.apply(tree, src)
        assert results, "Expected suggestion for open() without with"
        assert new_tree is tree   # no mutation
        assert "open" in results[0].description.lower()

    def test_tl23_extract_method_advisor(self):
        """TL23: ExtractMethodAdvisor flags functions with LOC>50."""
        from sensor_core.autofix.transforms.extract_method import ExtractMethodAdvisor
        # Build a function with >50 lines
        long_body = "\n".join(f"    x_{i} = {i}" for i in range(55))
        src = f"def big_function():\n{long_body}\n"
        tree = ast.parse(src)
        t = ExtractMethodAdvisor()
        new_tree, results = t.apply(tree, src)
        assert results, "Expected suggestion for large function"
        assert "LOC" in results[0].description or "big_function" in results[0].description

    def test_tl24_string_concat_loop_advisor(self):
        """TL24: StringConcatLoopAdvisor detects += in a loop."""
        from sensor_core.autofix.transforms.replace_string_concat_loop import StringConcatLoopAdvisor
        src = "result = ''\nfor item in items:\n    result += item\n"
        tree = ast.parse(src)
        t = StringConcatLoopAdvisor()
        new_tree, results = t.apply(tree, src)
        assert results, "Expected suggestion for string concatenation in loop"
        assert "append" in results[0].description.lower() or "+=" in results[0].description

    def test_tl24b_type_hint_adder(self):
        """TL24b: TypeHintAdder adds : Any to unannotated parameters."""
        from sensor_core.autofix.transforms.add_type_hints import TypeHintAdder
        src = "def process(data, count):\n    return data\n"
        fixed, results = self._apply(TypeHintAdder, src)
        assert results, "Expected TransformResult"
        assert "Any" in fixed

    def test_tl24c_mutable_default_dict(self):
        """TL24c: MutableDefaultRemover handles ={} default."""
        from sensor_core.autofix.transforms.remove_mutable_default import MutableDefaultRemover
        src = "def f(opts={}):\n    pass\n"
        fixed, results = self._apply(MutableDefaultRemover, src)
        assert results
        # None appears in the fixed output (replaced default)
        assert "None" in fixed

    def test_tl24d_autofix_engine_runs_all_new_transforms(self):
        """TL24d: AutofixEngine default pipeline includes M8.1 transforms."""
        from sensor_core.autofix.engine import AutofixEngine, _DEFAULT_PIPELINE
        from sensor_core.autofix.transforms.remove_mutable_default import MutableDefaultRemover
        from sensor_core.autofix.transforms.replace_bare_except import BareExceptReplacer
        from sensor_core.autofix.transforms.simplify_comparison import NoneComparisonSimplifier
        assert MutableDefaultRemover in _DEFAULT_PIPELINE
        assert BareExceptReplacer   in _DEFAULT_PIPELINE
        assert NoneComparisonSimplifier in _DEFAULT_PIPELINE

        src = "def f(x=[]):\n    if x == None:\n        pass\n"
        engine = AutofixEngine()
        result = engine.apply(src)
        assert result.is_valid_python
        assert result.transforms_applied   # something was applied


# =============================================================================
# TL25-TL30 — LSP endpoint (WBS 6.3)
# =============================================================================

class TestLSPDiagnostics:
    """TL25-TL30: handle_lsp_diagnostics returns correct LSP format."""

    def setup_method(self):
        from api.server import handle_lsp_diagnostics, _lsp_range, _finding_to_lsp_diag
        self.handle    = handle_lsp_diagnostics
        self.lsp_range = _lsp_range
        self.finding_to_lsp = _finding_to_lsp_diag

    def _make_snapshot(self, flow=None, reliability=None, maintainability=None):
        """Build a mock snapshot object."""
        snap = SimpleNamespace(
            commit_hash="abc123",
            timestamp=1700000000.0,
            flow=flow,
            reliability=reliability,
            maintainability=maintainability,
            sast_result=None,
        )
        return snap

    def test_tl25_lsp_range_0indexed(self):
        """TL25: _lsp_range converts 1-indexed lines to 0-indexed LSP lines."""
        r = self.lsp_range(1, 0)
        assert r["start"]["line"]      == 0
        assert r["end"]["line"]        == 0
        assert r["start"]["character"] == 0

    def test_tl26_lsp_range_line5(self):
        """TL26: _lsp_range for SAST line 5 → LSP line 4."""
        r = self.lsp_range(5, 3)
        assert r["start"]["line"]      == 4
        assert r["start"]["character"] == 3

    def test_tl27_no_module_returns_400(self):
        """TL27: Missing module parameter returns 400."""
        with patch("api.server._store") as mock_store:
            code, data = self.handle(None)
        assert code == 400
        assert "error" in data

    def test_tl28_unknown_module_returns_404(self):
        """TL28: Module with no history returns 404."""
        with patch("api.server._store") as mock_store:
            mock_store.get_history.return_value = []
            code, data = self.handle("unknown.module")
        assert code == 404

    def test_tl29_lsp_response_schema(self):
        """TL29: Successful response follows LSP schema (uri, diagnostics, count)."""
        snap = self._make_snapshot()
        with patch("api.server._store") as mock_store:
            mock_store.get_history.return_value = [snap]
            code, data = self.handle("myapp.utils")
        assert code == 200
        assert "uri"         in data
        assert "diagnostics" in data
        assert "count"       in data
        assert isinstance(data["diagnostics"], list)
        assert data["count"] == len(data["diagnostics"])

    def test_tl30_lsp_flow_vector_signal(self):
        """TL30: FlowVector with unsanitized paths produces Error diagnostic."""
        fv = SimpleNamespace(
            taint_source_count=2,
            taint_sink_count=1,
            taint_path_count=2,
            taint_sanitized_ratio=0.0,
            cross_fn_taint_risk=0,
            injection_surface=2.0,
            unsanitized_paths=2,
        )
        # Attach the flow_rating method
        fv.flow_rating = lambda: "D"

        snap = self._make_snapshot(flow=fv)
        with (
            patch("api.server._store") as mock_store,
            patch("api.server._TAINT_ENGINE_AVAILABLE", True),
            patch("api.server._RELIABILITY_VECTOR_AVAILABLE", False),
            patch("api.server._MAINTAINABILITY_VECTOR_AVAILABLE", False),
        ):
            mock_store.get_history.return_value = [snap]
            code, data = self.handle("myapp.routes")

        assert code == 200
        flow_diags = [d for d in data["diagnostics"] if d.get("code") == "UCO-FLOW-001"]
        assert flow_diags, "Expected UCO-FLOW-001 diagnostic"
        diag = flow_diags[0]
        assert diag["severity"] == 1            # Error
        assert diag["source"]   == "uco-sensor"
        assert "range" in diag
        assert "start" in diag["range"]
        assert "end"   in diag["range"]
        assert "data"  in diag
        assert diag["data"]["unsanitized_paths"] == 2


# =============================================================================
# Bonus: finding_to_lsp_diag conversion
# =============================================================================

class TestFindingToLSP:
    """TL30b: _finding_to_lsp_diag correctly maps severity → LSP severity code."""

    def setup_method(self):
        from api.server import _finding_to_lsp_diag
        self.conv = _finding_to_lsp_diag

    def _make_finding_dict(self, severity: str) -> dict:
        return {
            "rule_id":       "SAST001",
            "severity":      severity,
            "cwe_id":        "CWE-89",
            "owasp":         "A03:2021",
            "title":         "SQL Injection",
            "description":   "Test",
            "line":          10,
            "col":           4,
            "code_snippet":  "cursor.execute(sql)",
            "remediation":   "Use params",
            "debt_minutes":  240,
            "suggested_fix": "cursor.execute(sql, (p,))",
            "confidence":    0.9,
            "explanation":   "Explain",
        }

    def test_critical_maps_to_error(self):
        d = self.conv(self._make_finding_dict("CRITICAL"))
        assert d["severity"] == 1

    def test_high_maps_to_error(self):
        d = self.conv(self._make_finding_dict("HIGH"))
        assert d["severity"] == 1

    def test_medium_maps_to_warning(self):
        d = self.conv(self._make_finding_dict("MEDIUM"))
        assert d["severity"] == 2

    def test_low_maps_to_information(self):
        d = self.conv(self._make_finding_dict("LOW"))
        assert d["severity"] == 3

    def test_data_field_includes_enrichment(self):
        d = self.conv(self._make_finding_dict("CRITICAL"))
        assert d["data"]["suggested_fix"] == "cursor.execute(sql, (p,))"
        assert d["data"]["confidence"]    == 0.9
        assert d["data"]["explanation"]   == "Explain"
