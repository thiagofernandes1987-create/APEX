"""
test_marco_m19.py — UCO-Sensor M7.4 (FASE 5a) — PerformanceVector
==================================================================
Tests for v2.8.0 deliverables:

  TP01-TP06  PerformanceVector dataclass (WBS 7.1)
  TP07-TP12  N+1, list_in_loop, string_concat (WBS 7.2)
  TP13-TP20  Nested loops, repeated computation, regex/io in loop (WBS 7.3)
  TP21-TP26  inefficient_dict_lookup + combined scenarios
  TP27-TP30  Pipeline integration + API endpoint handlers (WBS 7.4)

All tests are pure unit tests — no network, no DB, no filesystem side effects.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

_SENSOR_DIR = Path(__file__).resolve().parent.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

import pytest


# =============================================================================
# Helpers
# =============================================================================

def _analyze(source: str):
    from metrics.performance_analyzer import PerformanceAnalyzer
    return PerformanceAnalyzer().analyze(source)


def _vector(source: str, module_id: str = "test"):
    from metrics.performance_analyzer import PerformanceAnalyzer
    from metrics.extended_vectors import PerformanceVector
    result = PerformanceAnalyzer().analyze(source, module_id=module_id)
    return PerformanceVector.from_analyzer(result, module_id=module_id)


# =============================================================================
# TP01-TP06 — PerformanceVector dataclass (WBS 7.1)
# =============================================================================

class TestPerformanceVectorDataclass:
    """TP01-TP06: PerformanceVector has correct structure, defaults, and methods."""

    def test_tp01_all_channels_zero_by_default(self):
        """TP01: All 8 channels default to 0."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector()
        assert pv.n_plus_one_risk             == 0
        assert pv.list_in_loop_append_count   == 0
        assert pv.string_concat_in_loop       == 0
        assert pv.quadratic_nested_loop_count == 0
        assert pv.repeated_computation_count  == 0
        assert pv.regex_compile_in_loop       == 0
        assert pv.io_in_tight_loop            == 0
        assert pv.inefficient_dict_lookup     == 0

    def test_tp02_default_rating_A(self):
        """TP02: Zero-issue PerformanceVector has rating A."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector()
        assert pv.performance_rating() == "A"

    def test_tp03_total_issues_sum(self):
        """TP03: total_issues sums all 8 channels."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(
            n_plus_one_risk=1,
            list_in_loop_append_count=2,
            string_concat_in_loop=1,
            quadratic_nested_loop_count=1,
        )
        assert pv.total_issues == 5

    def test_tp04_to_dict_has_all_keys(self):
        """TP04: to_dict() includes all 8 channels + rating + total_issues."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(n_plus_one_risk=2, regex_compile_in_loop=1)
        d = pv.to_dict()
        for key in [
            "n_plus_one_risk", "list_in_loop_append_count",
            "string_concat_in_loop", "quadratic_nested_loop_count",
            "repeated_computation_count", "regex_compile_in_loop",
            "io_in_tight_loop", "inefficient_dict_lookup",
            "performance_rating", "total_issues", "weighted_score",
        ]:
            assert key in d, f"Missing key: {key}"

    def test_tp05_rating_E_high_n1(self):
        """TP05: N+1 risk has weight 3 — 5 N+1 hits = score 15 → rating E."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(n_plus_one_risk=5)
        assert pv.weighted_score == 15
        assert pv.performance_rating() == "E"

    def test_tp06_from_dict_roundtrip(self):
        """TP06: from_dict(to_dict()) reconstructs the vector correctly."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(
            n_plus_one_risk=1, string_concat_in_loop=2,
            regex_compile_in_loop=3, module_id="myapp",
        )
        d  = pv.to_dict()
        pv2 = PerformanceVector.from_dict(d)
        assert pv2.n_plus_one_risk           == 1
        assert pv2.string_concat_in_loop     == 2
        assert pv2.regex_compile_in_loop     == 3
        assert pv2.module_id                 == "myapp"


# =============================================================================
# TP07-TP12 — N+1, list_in_loop, string_concat (WBS 7.2)
# =============================================================================

class TestN1ListConcat:
    """TP07-TP12: N+1 queries, list append, string concat detection."""

    def test_tp07_n1_cursor_execute_in_loop(self):
        """TP07: cursor.execute() inside for loop → n_plus_one_risk > 0."""
        src = """
for user_id in user_ids:
    cursor.execute("SELECT * FROM orders WHERE uid = ?", (user_id,))
"""
        r = _analyze(src)
        assert r.n_plus_one_risk >= 1

    def test_tp08_n1_orm_filter_in_loop(self):
        """TP08: db.query().filter() inside for loop → n_plus_one_risk > 0."""
        src = """
for item in items:
    result = session.query(Order).filter(Order.user_id == item.id).all()
"""
        r = _analyze(src)
        assert r.n_plus_one_risk >= 1

    def test_tp09_list_append_in_loop(self):
        """TP09: list.append() inside for loop → list_in_loop_append_count > 0."""
        src = """
result = []
for x in data:
    result.append(x * 2)
"""
        r = _analyze(src)
        assert r.list_in_loop_append_count >= 1

    def test_tp10_string_concat_augassign_in_for(self):
        """TP10: s += item inside for loop → string_concat_in_loop > 0."""
        src = """
result = ""
for item in items:
    result += item
"""
        r = _analyze(src)
        assert r.string_concat_in_loop >= 1

    def test_tp11_string_concat_in_while(self):
        """TP11: s += x inside while loop → string_concat_in_loop > 0."""
        src = """
s = ""
i = 0
while i < n:
    s += data[i]
    i += 1
"""
        r = _analyze(src)
        assert r.string_concat_in_loop >= 1

    def test_tp12_clean_code_no_n1(self):
        """TP12: Parameterised batch query outside loop → no N+1 detected."""
        src = """
user_ids = [1, 2, 3]
cursor.execute("SELECT * FROM orders WHERE uid IN ?", (user_ids,))
rows = cursor.fetchall()
"""
        r = _analyze(src)
        assert r.n_plus_one_risk == 0
        assert r.string_concat_in_loop == 0


# =============================================================================
# TP13-TP20 — Nested loops, repeated computation, regex/io in loop (WBS 7.3)
# =============================================================================

class TestNestedAndRegexIO:
    """TP13-TP20: quadratic loops, repeated computation, regex/io detection."""

    def test_tp13_quadratic_nested_loop(self):
        """TP13: Nested for-in-for → quadratic_nested_loop_count >= 1."""
        src = """
for i in range(n):
    for j in range(n):
        process(i, j)
"""
        r = _analyze(src)
        assert r.quadratic_nested_loop_count >= 1

    def test_tp14_triple_nested_loop(self):
        """TP14: for-in-for-in-for → quadratic_nested_loop_count >= 2."""
        src = """
for i in a:
    for j in b:
        for k in c:
            pass
"""
        r = _analyze(src)
        assert r.quadratic_nested_loop_count >= 2

    def test_tp15_single_loop_no_quadratic(self):
        """TP15: Single for loop (no nesting) → quadratic_nested_loop_count == 0."""
        src = """
for x in data:
    process(x)
"""
        r = _analyze(src)
        assert r.quadratic_nested_loop_count == 0

    def test_tp16_repeated_computation_in_loop(self):
        """TP16: Same call expression ≥2× in loop body → repeated_computation_count > 0."""
        src = """
for item in items:
    x = compute(item)
    y = compute(item)
    z = compute(item)
"""
        r = _analyze(src)
        assert r.repeated_computation_count >= 1

    def test_tp17_no_repeated_if_different_calls(self):
        """TP17: Different call expressions don't trigger repeated_computation_count."""
        src = """
for item in items:
    x = compute_a(item)
    y = compute_b(item)
"""
        r = _analyze(src)
        assert r.repeated_computation_count == 0

    def test_tp18_regex_compile_in_loop(self):
        """TP18: re.compile() inside for loop → regex_compile_in_loop > 0."""
        src = """
import re
patterns = [r'\\d+', r'\\w+', r'[a-z]+']
for pattern in patterns:
    rx = re.compile(pattern)
    rx.search(text)
"""
        r = _analyze(src)
        assert r.regex_compile_in_loop >= 1

    def test_tp19_re_search_in_loop(self):
        """TP19: re.search() inside for loop → regex_compile_in_loop > 0."""
        src = """
import re
for line in lines:
    m = re.search(r'error:\\s+(.*)', line)
"""
        r = _analyze(src)
        assert r.regex_compile_in_loop >= 1

    def test_tp20_io_open_in_loop(self):
        """TP20: open() inside for loop → io_in_tight_loop > 0."""
        src = """
for filename in files:
    f = open(filename)
    data = f.read()
    f.close()
"""
        r = _analyze(src)
        assert r.io_in_tight_loop >= 1


# =============================================================================
# TP21-TP26 — inefficient_dict_lookup + combined scenarios
# =============================================================================

class TestDictLookupAndCombined:
    """TP21-TP26: inefficient_dict_lookup + combined multi-pattern scenarios."""

    def test_tp21_keys_in_membership_test(self):
        """TP21: 'k in d.keys()' → inefficient_dict_lookup > 0."""
        src = """
if key in my_dict.keys():
    do_something()
"""
        r = _analyze(src)
        assert r.inefficient_dict_lookup >= 1

    def test_tp22_direct_in_test_not_flagged(self):
        """TP22: 'k in d' (without .keys()) → no inefficient_dict_lookup."""
        src = """
if key in my_dict:
    do_something()
"""
        r = _analyze(src)
        assert r.inefficient_dict_lookup == 0

    def test_tp23_multiple_keys_calls(self):
        """TP23: Multiple 'k in d.keys()' lines → count matches occurrences."""
        src = """
for k in candidates:
    if k in primary.keys():
        result.append(primary[k])
    if k in secondary.keys():
        result.append(secondary[k])
"""
        r = _analyze(src)
        assert r.inefficient_dict_lookup >= 2

    def test_tp24_requests_get_in_loop(self):
        """TP24: requests.get() inside for loop → io_in_tight_loop > 0."""
        src = """
import requests
for url in urls:
    resp = requests.get(url, timeout=10)
    results.append(resp.json())
"""
        r = _analyze(src)
        assert r.io_in_tight_loop >= 1

    def test_tp25_combined_antipatterns(self):
        """TP25: Multiple anti-patterns in one function → all channels populated."""
        src = """
import re
result = ""
for user in users:
    # N+1 query
    orders = session.query(Order).filter(Order.user_id == user.id).all()
    # string concat
    result += str(user.name)
    # regex in loop
    m = re.search(r'\\d+', user.email)
    # nested loop
    for order in orders:
        pass
"""
        r = _analyze(src)
        assert r.n_plus_one_risk >= 1
        assert r.string_concat_in_loop >= 1
        assert r.regex_compile_in_loop >= 1
        assert r.quadratic_nested_loop_count >= 1

    def test_tp26_clean_idiomatic_code_zero_issues(self):
        """TP26: Well-written code has zero performance issues."""
        src = """
import re

PATTERN = re.compile(r'\\d+')

def process(users):
    names = [u.name for u in users]
    user_ids = [u.id for u in users]
    # Batch query outside loop
    orders = session.query(Order).filter(Order.user_id.in_(user_ids)).all()
    result = "".join(names)
    return result
"""
        r = _analyze(src)
        # No loops containing re.compile (it's at module level)
        assert r.regex_compile_in_loop == 0
        # No string concat in loop (using join outside)
        assert r.string_concat_in_loop == 0


# =============================================================================
# TP27-TP30 — Pipeline integration + API endpoints (WBS 7.4)
# =============================================================================

class TestPipelineAndAPI:
    """TP27-TP30: PerformanceVector wired into UCOBridge + API handlers."""

    def test_tp27_mv_has_performance_attr(self):
        """TP27: UCOBridge.analyze() attaches .performance to MetricVector."""
        from sensor_core.uco_bridge import UCOBridge
        src = "x = 1\n"
        mv = UCOBridge().analyze(src, module_id="test", commit_hash="abc")
        # May be None if analyzer unavailable, but attribute must exist
        assert hasattr(mv, "performance")

    def test_tp28_tainted_code_reflected_in_performance(self):
        """TP28: Code with N+1 pattern → mv.performance.n_plus_one_risk > 0."""
        from sensor_core.uco_bridge import UCOBridge
        src = """
for uid in user_ids:
    rows = cursor.execute("SELECT * FROM t WHERE id=?", (uid,))
"""
        mv = UCOBridge().analyze(src, module_id="test", commit_hash="abc")
        pv = getattr(mv, "performance", None)
        if pv is None:
            pytest.skip("PerformanceAnalyzer not available in this environment")
        assert pv.n_plus_one_risk >= 1

    def test_tp29_scan_performance_endpoint_200(self):
        """TP29: POST /scan-performance with valid code returns 200."""
        from api.server import handle_scan_performance
        src = """
for user in users:
    result = db.query(User).filter(User.id == user.id).first()
"""
        code, data = handle_scan_performance({"code": src, "module_id": "test"})
        assert code == 200
        assert "performance_vector" in data
        assert "summary" in data
        assert "performance_rating" in data["performance_vector"]
        assert data["summary"]["n_plus_one_risk"] >= 1

    def test_tp30_scan_performance_no_code_400(self):
        """TP30: POST /scan-performance without code returns 400."""
        from api.server import handle_scan_performance
        code, data = handle_scan_performance({})
        assert code in (400, 503)   # 503 if analyzer missing, 400 if available

    def test_tp30b_scan_performance_empty_code_400(self):
        """TP30b: POST /scan-performance with empty code returns 400."""
        from api.server import handle_scan_performance
        code, data = handle_scan_performance({"code": "   "})
        assert code in (400, 503)

    def test_tp30c_metrics_performance_no_module_400(self):
        """TP30c: GET /metrics/performance without module → 400."""
        from api.server import handle_metrics_performance
        code, data = handle_metrics_performance(None)
        assert code in (400, 503)

    def test_tp30d_metrics_performance_unknown_module_404(self):
        """TP30d: GET /metrics/performance for unknown module → 404."""
        from api.server import handle_metrics_performance
        with patch("api.server._store") as mock_store:
            mock_store.get_history.return_value = []
            code, data = handle_metrics_performance("unknown.module")
        assert code in (404, 503)

    def test_tp30e_performance_vector_from_analyzer(self):
        """TP30e: PerformanceVector.from_analyzer() maps all fields correctly."""
        from metrics.extended_vectors import PerformanceVector
        from metrics.performance_analyzer import PerformanceResult
        pr = PerformanceResult(
            n_plus_one_risk=2,
            list_in_loop_append_count=3,
            string_concat_in_loop=1,
            quadratic_nested_loop_count=1,
            repeated_computation_count=0,
            regex_compile_in_loop=2,
            io_in_tight_loop=1,
            inefficient_dict_lookup=4,
        )
        pv = PerformanceVector.from_analyzer(pr, module_id="app.views")
        assert pv.n_plus_one_risk             == 2
        assert pv.list_in_loop_append_count   == 3
        assert pv.string_concat_in_loop       == 1
        assert pv.quadratic_nested_loop_count == 1
        assert pv.regex_compile_in_loop       == 2
        assert pv.io_in_tight_loop            == 1
        assert pv.inefficient_dict_lookup     == 4
        assert pv.module_id                   == "app.views"
        assert pv.total_issues                == 14

    def test_tp30f_performance_rating_B(self):
        """TP30f: 1 N+1 hit → weighted_score=3 → rating B."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(n_plus_one_risk=1)
        assert pv.weighted_score == 3
        assert pv.performance_rating() == "B"

    def test_tp30g_performance_rating_C(self):
        """TP30g: 2 nested loops → weighted_score=4 → rating C."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(quadratic_nested_loop_count=2)
        assert pv.weighted_score == 4
        assert pv.performance_rating() == "C"

    def test_tp30h_performance_rating_D(self):
        """TP30h: Moderate issues → rating D (weighted_score 9-14)."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(
            n_plus_one_risk=2,            # 6
            quadratic_nested_loop_count=1, # 2
            string_concat_in_loop=1,       # 2
        )
        assert pv.weighted_score == 10
        assert pv.performance_rating() == "D"

    def test_tp30i_syntax_error_returns_zeroed_result(self):
        """TP30i: SyntaxError in source → PerformanceResult all zeros, no crash."""
        from metrics.performance_analyzer import PerformanceAnalyzer
        src = "def broken(:\n    pass\n"
        result = PerformanceAnalyzer().analyze(src)
        assert result.n_plus_one_risk == 0
        assert result.total_issues    == 0 if hasattr(result, "total_issues") else True

    def test_tp30j_performance_vector_repr(self):
        """TP30j: PerformanceVector.__repr__ includes rating and issue counts."""
        from metrics.extended_vectors import PerformanceVector
        pv = PerformanceVector(n_plus_one_risk=1)
        r = repr(pv)
        assert "PerformanceVector" in r
        assert "rating=" in r
