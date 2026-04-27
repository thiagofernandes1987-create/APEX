"""
UCO-Sensor — M7.2 Taint Analysis + FlowVector — Test Suite
===========================================================
TF01-TF30  (30 tests per WBS 5.1-5.7)

Coverage
--------
TF01-TF04  TaintSet data structure: add / remove / clone / merge
TF05-TF09  Source identification: request.args, sys.argv, os.environ, input(), os.getenv
TF10-TF14  Propagation rules: assignment, tuple unpack, f-string, BinOp, call heuristic
TF15-TF19  Sink detection: SQL execute, os.system, eval, open, subprocess.run
TF20-TF24  Sanitizer: html.escape, bleach.clean, re.escape, urllib.parse.quote; sanitizer clears taint
TF25-TF29  FlowVector: from_taint_result, ratings A-E, to_dict, unsanitized_paths
TF30       Full pipeline: UCOBridge.analyze attaches mv.flow (FlowVector)
           + API handler /scan-flow and /metrics/flow
"""
from __future__ import annotations

import sys
import os
import pytest

# ── path setup ────────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sast.taint_engine import (
    TaintAnalyzer,
    TaintSet,
    TaintInfo,
    TaintFlow,
    TaintResult,
)
from metrics.extended_vectors import FlowVector


# ── helpers ───────────────────────────────────────────────────────────────────

def _analyze(source: str) -> TaintResult:
    return TaintAnalyzer().analyze(source, module_id="test_m17")


def _fv(source: str) -> FlowVector:
    result = _analyze(source)
    return FlowVector.from_taint_result(result, module_id="test_m17")


# ═══════════════════════════════════════════════════════════════════════════════
# TF01-TF04 — TaintSet data structure
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF01_TaintSet:
    """TF01 — TaintSet add / is_tainted / get."""

    def test_add_and_query(self):
        ts   = TaintSet()
        info = TaintInfo(origin="request.args", origin_line=1, path=["q"])
        ts.add("q", info)
        assert ts.is_tainted("q")
        assert ts.get("q") is info

    def test_unknown_var_not_tainted(self):
        ts = TaintSet()
        assert not ts.is_tainted("x")
        assert ts.get("x") is None

    def test_remove_clears_taint(self):
        ts   = TaintSet()
        info = TaintInfo("src", 1, ["x"])
        ts.add("x", info)
        ts.remove("x")
        assert not ts.is_tainted("x")

    def test_remove_nonexistent_is_noop(self):
        ts = TaintSet()
        ts.remove("nonexistent")   # must not raise
        assert len(ts) == 0


class TestTF02_TaintSetClone:
    """TF02 — TaintSet.clone() is independent."""

    def test_clone_independent(self):
        ts   = TaintSet()
        info = TaintInfo("src", 1, ["a"])
        ts.add("a", info)
        ts2 = ts.clone()
        ts2.add("b", TaintInfo("src2", 2, ["b"]))
        assert not ts.is_tainted("b"), "original must not be mutated by clone"
        assert ts2.is_tainted("a"),    "clone must retain original entries"

    def test_clone_remove_independent(self):
        ts   = TaintSet()
        info = TaintInfo("src", 1, ["x"])
        ts.add("x", info)
        ts2 = ts.clone()
        ts2.remove("x")
        assert ts.is_tainted("x"),  "original unaffected by clone.remove()"
        assert not ts2.is_tainted("x")


class TestTF03_TaintSetMerge:
    """TF03 — TaintSet.merge_from() is conservative union."""

    def test_merge_adds_missing(self):
        ts1  = TaintSet()
        ts1.add("a", TaintInfo("s1", 1, ["a"]))
        ts2  = TaintSet()
        ts2.add("b", TaintInfo("s2", 2, ["b"]))
        ts1.merge_from(ts2)
        assert ts1.is_tainted("a")
        assert ts1.is_tainted("b")

    def test_merge_does_not_overwrite_existing(self):
        info_orig = TaintInfo("original", 1, ["x"])
        ts1 = TaintSet()
        ts1.add("x", info_orig)
        ts2 = TaintSet()
        ts2.add("x", TaintInfo("other", 2, ["x"]))
        ts1.merge_from(ts2)
        assert ts1.get("x").origin == "original"


class TestTF04_TaintInfoExtend:
    """TF04 — TaintInfo.extend() grows the path chain."""

    def test_extend_appends_var(self):
        info  = TaintInfo("request.args", 1, ["q"])
        info2 = info.extend("user_input")
        assert info2.path == ["q", "user_input"]
        assert info2.origin == "request.args"
        assert info2.origin_line == 1

    def test_extend_original_unchanged(self):
        info  = TaintInfo("src", 1, ["a"])
        info.extend("b")
        assert info.path == ["a"]   # original must be immutable


# ═══════════════════════════════════════════════════════════════════════════════
# TF05-TF09 — Source identification
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF05_SourceRequestArgs:
    """TF05 — request.args is a taint source."""

    def test_request_args_detected(self):
        src = "q = request.args['q']"
        result = _analyze(src)
        assert result.source_count >= 1

    def test_request_form_detected(self):
        src = "name = request.form['name']"
        result = _analyze(src)
        assert result.source_count >= 1

    def test_request_json_detected(self):
        src = "payload = request.json"
        result = _analyze(src)
        assert result.source_count >= 1


class TestTF06_SourceSysArgv:
    """TF06 — sys.argv is a taint source."""

    def test_sys_argv_subscript(self):
        src = "arg = sys.argv[1]"
        result = _analyze(src)
        assert result.source_count >= 1

    def test_sys_argv_as_list(self):
        """sys.argv itself (not subscripted) should propagate if used directly."""
        src = "args = sys.argv\nfirst = args[0]"
        result = _analyze(src)
        # source registered when sys.argv is accessed
        assert result.source_count >= 1


class TestTF07_SourceOsEnviron:
    """TF07 — os.environ is a taint source."""

    def test_os_environ_subscript(self):
        src = "key = os.environ['SECRET']"
        result = _analyze(src)
        assert result.source_count >= 1

    def test_os_getenv_call(self):
        src = "val = os.getenv('HOME')"
        result = _analyze(src)
        assert result.source_count >= 1


class TestTF08_SourceInput:
    """TF08 — input() is a taint source."""

    def test_input_call(self):
        src = "user = input('name: ')"
        result = _analyze(src)
        assert result.source_count >= 1

    def test_input_flows_to_sink(self):
        src = (
            "user = input('name: ')\n"
            "cursor.execute('SELECT * FROM u WHERE name=' + user)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1
        assert any(f.vuln_type == "SQL_INJECTION" for f in result.flows)


class TestTF09_MultipleSourcesTracked:
    """TF09 — multiple source expressions each registered once."""

    def test_dedup_same_line(self):
        src = "q = request.args['q']\nq2 = request.args['q2']"
        result = _analyze(src)
        # Two distinct source expressions
        assert result.source_count >= 2

    def test_sources_independent_of_sinks(self):
        """source_count reflects sources even when no sink is reached."""
        src = "q = request.args['q']\nprint(q)"
        result = _analyze(src)
        assert result.source_count >= 1
        assert result.taint_path_count == 0   # print is not a sink


# ═══════════════════════════════════════════════════════════════════════════════
# TF10-TF14 — Propagation rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF10_PropagationAssignment:
    """TF10 — direct assignment propagates taint."""

    def test_simple_assignment(self):
        src = (
            "q = request.args['q']\n"
            "query = q\n"
            "cursor.execute(query)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1

    def test_clean_reassignment_clears_taint(self):
        src = (
            "q = request.args['q']\n"
            "q = 'safe_literal'\n"
            "cursor.execute(q)\n"
        )
        result = _analyze(src)
        # q is reassigned to a literal → no taint flow to sink
        assert result.taint_path_count == 0


class TestTF11_PropagationTupleUnpack:
    """TF11 — tuple unpack propagates taint to all targets."""

    def test_tuple_unpack_both_tainted(self):
        src = (
            "pair = request.args['pair']\n"
            "a, b = pair, pair\n"
            "cursor.execute(a)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1


class TestTF12_PropagationFstring:
    """TF12 — f-string with tainted value is tainted."""

    def test_fstring_propagates(self):
        src = (
            "user = request.args['user']\n"
            "sql = f'SELECT * FROM t WHERE u={user}'\n"
            "cursor.execute(sql)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1
        assert any(f.vuln_type == "SQL_INJECTION" for f in result.flows)


class TestTF13_PropagationBinOp:
    """TF13 — binary op (string concat) propagates taint."""

    def test_concat_propagates(self):
        src = (
            "name = request.form['name']\n"
            "sql = 'SELECT * FROM users WHERE name=' + name\n"
            "cursor.execute(sql)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1

    def test_clean_plus_clean_is_clean(self):
        src = (
            "sql = 'SELECT * FROM t WHERE id=' + '42'\n"
            "cursor.execute(sql)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count == 0


class TestTF14_PropagationCallHeuristic:
    """TF14 — taint propagates through non-sink, non-sanitizer calls."""

    def test_call_propagation(self):
        src = (
            "raw = request.args['q']\n"
            "processed = some_transform(raw)\n"
            "cursor.execute(processed)\n"
        )
        result = _analyze(src)
        # processed inherits taint from raw via call heuristic
        assert result.taint_path_count >= 1

    def test_cross_fn_risk_counted(self):
        src = (
            "q = request.args['q']\n"
            "helper(q)\n"  # not a sink — cross_fn_risk
        )
        result = _analyze(src)
        assert result.cross_fn_risk >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# TF15-TF19 — Sink detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF15_SinkSQLExecute:
    """TF15 — cursor.execute with tainted arg → SQL_INJECTION."""

    def test_cursor_execute(self):
        src = (
            "q = request.args['q']\n"
            "cursor.execute('SELECT * FROM t WHERE v=' + q)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST040" for f in result.flows)

    def test_session_execute(self):
        src = (
            "val = request.form['v']\n"
            "session.execute('SELECT ' + val)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST040" for f in result.flows)


class TestTF16_SinkOsSystem:
    """TF16 — os.system with tainted arg → COMMAND_INJECTION."""

    def test_os_system(self):
        src = (
            "cmd = request.args['cmd']\n"
            "os.system(cmd)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST041" for f in result.flows)
        assert any(f.vuln_type == "COMMAND_INJECTION" for f in result.flows)

    def test_subprocess_run(self):
        src = (
            "arg = sys.argv[1]\n"
            "subprocess.run(arg)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST041" for f in result.flows)


class TestTF17_SinkEval:
    """TF17 — eval/exec with tainted arg → CODE_INJECTION."""

    def test_eval_tainted(self):
        src = (
            "code = request.args['code']\n"
            "eval(code)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST043" for f in result.flows)
        assert any(f.vuln_type == "CODE_INJECTION" for f in result.flows)

    def test_exec_tainted(self):
        src = (
            "code = input('code> ')\n"
            "exec(code)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST043" for f in result.flows)


class TestTF18_SinkOpen:
    """TF18 — open() with tainted arg → PATH_TRAVERSAL."""

    def test_open_tainted_path(self):
        src = (
            "path = request.args['file']\n"
            "f = open(path)\n"
        )
        result = _analyze(src)
        assert any(f.rule_id == "SAST044" for f in result.flows)
        assert any(f.vuln_type == "PATH_TRAVERSAL" for f in result.flows)


class TestTF19_SinkNotTriggeredOnClean:
    """TF19 — sinks with clean (non-tainted) args do not produce findings."""

    def test_execute_with_literal(self):
        src = "cursor.execute('SELECT 1')\n"
        result = _analyze(src)
        assert result.taint_path_count == 0

    def test_eval_with_literal(self):
        src = "eval('1 + 1')\n"
        result = _analyze(src)
        assert result.taint_path_count == 0

    def test_open_with_literal(self):
        src = "open('config.txt')\n"
        result = _analyze(src)
        assert result.taint_path_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TF20-TF24 — Sanitizer detection
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF20_SanitizerHtmlEscape:
    """TF20 — html.escape() neutralizes taint."""

    def test_html_escape_clears_taint(self):
        src = (
            "q = request.args['q']\n"
            "safe = html.escape(q)\n"
            "cursor.execute(safe)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count == 0, "html.escape must neutralize taint"

    def test_html_escape_not_assigned_taint_persists(self):
        """Calling html.escape but NOT assigning result → original var still tainted."""
        src = (
            "q = request.args['q']\n"
            "html.escape(q)\n"           # result ignored
            "cursor.execute(q)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count >= 1


class TestTF21_SanitizerBleach:
    """TF21 — bleach.clean() neutralizes taint."""

    def test_bleach_clean_clears(self):
        src = (
            "body = request.form['body']\n"
            "clean_body = bleach.clean(body)\n"
            "eval(clean_body)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count == 0


class TestTF22_SanitizerReEscape:
    """TF22 — re.escape() neutralizes taint."""

    def test_re_escape_clears(self):
        src = (
            "pattern = request.args['pattern']\n"
            "safe_pat = re.escape(pattern)\n"
            "cursor.execute(safe_pat)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count == 0


class TestTF23_SanitizerUrllibQuote:
    """TF23 — urllib.parse.quote() neutralizes taint."""

    def test_quote_clears(self):
        src = (
            "path = request.args['path']\n"
            "encoded = urllib.parse.quote(path)\n"
            "open(encoded)\n"
        )
        result = _analyze(src)
        assert result.taint_path_count == 0


class TestTF24_PartialSanitization:
    """TF24 — one sanitized path does not clear other unsanitized paths."""

    def test_mixed_flows(self):
        src = (
            "q = request.args['q']\n"
            "safe = html.escape(q)\n"
            "cursor.execute(safe)\n"     # sanitized → no finding
            "os.system(q)\n"             # NOT sanitized → finding
        )
        result = _analyze(src)
        # Only the unsanitized flow to os.system should appear
        assert result.taint_path_count >= 1
        assert any(f.vuln_type == "COMMAND_INJECTION" for f in result.flows)
        # No SQL_INJECTION finding (safe path)
        assert not any(f.rule_id == "SAST040" for f in result.flows)


# ═══════════════════════════════════════════════════════════════════════════════
# TF25-TF29 — FlowVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF25_FlowVectorDefaults:
    """TF25 — FlowVector default construction."""

    def test_default_all_zero(self):
        fv = FlowVector()
        assert fv.taint_source_count    == 0
        assert fv.taint_sink_count      == 0
        assert fv.taint_path_count      == 0
        assert fv.taint_sanitized_ratio == 0.0
        assert fv.cross_fn_taint_risk   == 0
        assert fv.injection_surface     == 0.0

    def test_default_rating_A(self):
        fv = FlowVector()
        assert fv.flow_rating() == "A"


class TestTF26_FlowVectorFromTaintResult:
    """TF26 — FlowVector.from_taint_result maps channels correctly."""

    def test_from_result_path_count(self):
        src = (
            "q = request.args['q']\n"
            "cursor.execute(q)\n"
        )
        result = _analyze(src)
        fv = FlowVector.from_taint_result(result)
        assert fv.taint_path_count == result.taint_path_count
        assert fv.taint_source_count == result.source_count

    def test_from_result_injection_surface(self):
        src = (
            "q = request.args['q']\n"
            "cursor.execute(q)\n"
        )
        result = _analyze(src)
        fv = FlowVector.from_taint_result(result)
        assert fv.injection_surface == result.injection_surface


class TestTF27_FlowVectorRatings:
    """TF27 — flow_rating returns A–E per thresholds."""

    def test_rating_A_no_flows(self):
        fv = FlowVector(taint_path_count=0, injection_surface=0.0)
        assert fv.flow_rating() == "A"

    def test_rating_B_one_unsanitized(self):
        fv = FlowVector(
            taint_path_count=1,
            taint_sanitized_ratio=0.0,
            injection_surface=1.0,
        )
        assert fv.flow_rating() == "B"

    def test_rating_C_two_unsanitized(self):
        fv = FlowVector(
            taint_path_count=2,
            taint_sanitized_ratio=0.0,
            injection_surface=2.0,
        )
        assert fv.flow_rating() == "C"

    def test_rating_D_four_unsanitized(self):
        fv = FlowVector(
            taint_path_count=4,
            taint_sanitized_ratio=0.0,
            injection_surface=4.0,
        )
        assert fv.flow_rating() == "D"

    def test_rating_E_seven_unsanitized(self):
        fv = FlowVector(
            taint_path_count=7,
            taint_sanitized_ratio=0.0,
            injection_surface=7.0,
        )
        assert fv.flow_rating() == "E"


class TestTF28_FlowVectorToDict:
    """TF28 — to_dict includes all channels + derived fields."""

    def test_to_dict_keys(self):
        fv = FlowVector(taint_path_count=1, injection_surface=1.0)
        d  = fv.to_dict()
        assert "taint_source_count"    in d
        assert "taint_sink_count"      in d
        assert "taint_path_count"      in d
        assert "taint_sanitized_ratio" in d
        assert "cross_fn_taint_risk"   in d
        assert "injection_surface"     in d
        assert "flow_rating"           in d
        assert "unsanitized_paths"     in d

    def test_to_dict_roundtrip(self):
        fv1 = FlowVector(taint_path_count=2, injection_surface=1.5, module_id="m")
        fv2 = FlowVector.from_dict(fv1.to_dict())
        assert fv2.taint_path_count == fv1.taint_path_count
        assert fv2.injection_surface == fv1.injection_surface
        assert fv2.module_id == fv1.module_id


class TestTF29_FlowVectorUnsanitizedPaths:
    """TF29 — unsanitized_paths computed correctly."""

    def test_zero_when_all_sanitized(self):
        fv = FlowVector(taint_path_count=3, taint_sanitized_ratio=1.0)
        assert fv.unsanitized_paths == 0

    def test_all_when_none_sanitized(self):
        fv = FlowVector(taint_path_count=4, taint_sanitized_ratio=0.0)
        assert fv.unsanitized_paths == 4


# ═══════════════════════════════════════════════════════════════════════════════
# TF30 — Full pipeline + API handlers
# ═══════════════════════════════════════════════════════════════════════════════

class TestTF30_FullPipelineAndAPI:
    """TF30 — UCOBridge attaches mv.flow; API handlers return correct codes."""

    def test_mv_has_flow_attr(self):
        from sensor_core.uco_bridge import UCOBridge
        bridge = UCOBridge(mode="full")
        mv = bridge.analyze("x = 1", module_id="tf30", commit_hash="abc")
        assert hasattr(mv, "flow")

    def test_mv_flow_is_flow_vector(self):
        from sensor_core.uco_bridge import UCOBridge
        bridge = UCOBridge(mode="full")
        mv = bridge.analyze("x = 1", module_id="tf30b", commit_hash="abc")
        assert isinstance(mv.flow, FlowVector)

    def test_tainted_code_reflected_in_flow(self):
        from sensor_core.uco_bridge import UCOBridge
        src = (
            "def view(request):\n"
            "    q = request.args['q']\n"
            "    cursor.execute('SELECT * FROM t WHERE v=' + q)\n"
        )
        bridge = UCOBridge(mode="full")
        mv = bridge.analyze(src, module_id="tf30c", commit_hash="abc")
        assert mv.flow.taint_path_count >= 1
        assert mv.flow.injection_surface > 0

    @pytest.fixture(autouse=True)
    def _import_server(self):
        import os as _os
        _os.environ.setdefault("UCO_NO_AUTH", "1")
        from api.server import handle_scan_flow, handle_metrics_flow
        self.scan_flow   = handle_scan_flow
        self.metrics_flow = handle_metrics_flow

    def test_scan_flow_empty_code_400(self):
        code, body = self.scan_flow({"code": "", "module_id": "tf30d"})
        assert code == 400

    def test_scan_flow_no_code_400(self):
        code, body = self.scan_flow({"module_id": "tf30d"})
        assert code == 400

    def test_scan_flow_clean_code_200(self):
        code, body = self.scan_flow({"code": "x = 1", "module_id": "tf30e"})
        assert code == 200
        assert "flow_vector" in body
        assert "flows"       in body
        assert "summary"     in body

    def test_scan_flow_tainted_code_detects_flow(self):
        src = (
            "q = request.args['q']\n"
            "cursor.execute('SELECT * FROM t WHERE v=' + q)\n"
        )
        code, body = self.scan_flow({"code": src, "module_id": "tf30f"})
        assert code == 200
        assert body["summary"]["taint_path_count"] >= 1
        assert body["flow_vector"]["flow_rating"] in {"B", "C", "D", "E"}

    def test_metrics_flow_no_module_400(self):
        code, body = self.metrics_flow(None)
        assert code == 400

    def test_metrics_flow_unknown_module_404(self):
        code, body = self.metrics_flow("__tf30_no_such_module__")
        assert code == 404
