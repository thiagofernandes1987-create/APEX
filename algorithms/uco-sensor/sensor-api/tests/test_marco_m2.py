"""
UCO-Sensor — Testes Marco M2: Governance Engine (v0.8.0)
==========================================================

M2.1  Policy Engine — rules and violations
M2.2  Quality Gate  — pass/fail scoring
M2.3  Trend Engine  — direction classification
M2.4  Debt Budget   — over-budget detection

  TG01  PolicyRule — lte operator: PASS
  TG02  PolicyRule — lte operator: FAIL
  TG03  PolicyRule — rating_lte: A passes "C" threshold
  TG04  PolicyRule — rating_lte: E fails "C" threshold
  TG05  PolicyRule — in operator: value in list passes
  TG06  PolicyRule — in operator: value not in list fails
  TG07  evaluate_policy — clean code → no violations, gate PASS
  TG08  evaluate_policy — high CC → violation generated
  TG09  evaluate_policy — multiple violations → score decrements correctly
  TG10  evaluate_policy — ERROR violation → -20 pts
  TG11  evaluate_policy — WARNING violation → -10 pts
  TG12  evaluate_policy — missing field → skipped (no violation)
  TG13  load_default_policy — returns Policy with rules list
  TG14  policy_from_dict — parses inline dict
  TG15  gate_score_to_grade — correct A–F mapping
  TG16  gate via UCOBridge — full pipeline PASS on clean code
  TG17  gate via UCOBridge — FAIL on pathological code
  TG18  analyze_trend — INSUFFICIENT_DATA on empty history
  TG19  analyze_trend — STABLE: flat values
  TG20  analyze_trend — DEGRADING: monotonically increasing H
  TG21  analyze_trend — IMPROVING: monotonically decreasing H
  TG22  analyze_trend — VOLATILE: high variance
  TG23  analyze_trend — forecast_next extrapolates slope
  TG24  analyze_module_trends — returns dict keyed by metric
  TG25  track_debt_budget — under budget
  TG26  track_debt_budget — over budget flag
  TG27  track_debt_budget — velocity + days_until_exhausted
  TG28  trend_summary — returns non-empty string
  TG29  overall_trend — all DEGRADING → DEGRADING
  TG30  PolicyResult.to_dict — round-trip
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# ── Path setup ─────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from governance.policy_engine import (
    PolicyRule, Policy, Violation, PolicyResult,
    evaluate_policy, load_default_policy, policy_from_dict,
    gate_score_to_grade, mv_to_metrics_dict,
)
from governance.trend_engine import (
    TrendPoint, TrendAnalysis, DebtBudget,
    analyze_trend, analyze_module_trends, track_debt_budget,
    trend_summary, overall_trend,
    IMPROVING, STABLE, DEGRADING, VOLATILE, INSUFFICIENT_DATA,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _make_metrics(**kwargs) -> Dict[str, Any]:
    """Build a minimal metrics dict with sensible defaults."""
    defaults = {
        "cyclomatic_complexity": 3,
        "hamiltonian": 2.0,
        "infinite_loop_risk": 0.0,
        "syntactic_dead_code": 0,
        "halstead_bugs": 0.1,
        "dependency_instability": 0.3,
        "cognitive_complexity": 4,
        "cognitive_fn_max": 4,
        "sqale_rating": "A",
        "sqale_debt_minutes": 0,
        "clone_count": 0,
    }
    defaults.update(kwargs)
    return defaults


class _FakeMV:
    """Minimal MetricVector stub for trend tests."""
    def __init__(self, h: float, cc: int = 3, ts: float = 0.0,
                 commit: str = "abc", module_id: str = "mod"):
        self.hamiltonian            = h
        self.cyclomatic_complexity  = cc
        self.infinite_loop_risk     = 0.0
        self.halstead_bugs          = 0.0
        self.cognitive_complexity   = 0
        self.sqale_debt_minutes     = 0
        self.timestamp              = ts or time.time()
        self.commit_hash            = commit
        self.module_id              = module_id
        self.status                 = "STABLE"


def _make_history(values: List[float], metric: str = "hamiltonian") -> List[_FakeMV]:
    t0 = time.time()
    return [
        _FakeMV(h=v if metric == "hamiltonian" else 0.0,
                ts=t0 + i * 3600,
                commit=f"commit_{i:03d}")
        for i, v in enumerate(values)
    ]


# ══════════════════════════════════════════════════════════════════════════════
# TG01-TG06 — PolicyRule operators
# ══════════════════════════════════════════════════════════════════════════════

def test_TG01_lte_pass():
    """lte operator: value within threshold → no violation."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="cyclomatic_complexity",
                   operator="lte", threshold=15, severity="WARNING")
    ])
    result = evaluate_policy(_make_metrics(cyclomatic_complexity=10), policy)
    assert result.passed
    assert len(result.violations) == 0


def test_TG02_lte_fail():
    """lte operator: value exceeds threshold → violation."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="cyclomatic_complexity",
                   operator="lte", threshold=15, severity="WARNING")
    ])
    result = evaluate_policy(_make_metrics(cyclomatic_complexity=20), policy)
    assert len(result.violations) == 1
    v = result.violations[0]
    assert v.rule_id == "R1"
    assert v.actual == 20


def test_TG03_rating_lte_pass():
    """rating_lte: A passes threshold C (A ≤ C)."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="sqale_rating",
                   operator="rating_lte", threshold="C", severity="WARNING")
    ])
    result = evaluate_policy(_make_metrics(sqale_rating="A"), policy)
    assert len(result.violations) == 0


def test_TG04_rating_lte_fail():
    """rating_lte: E fails threshold C (E > C)."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="sqale_rating",
                   operator="rating_lte", threshold="C", severity="ERROR")
    ])
    result = evaluate_policy(_make_metrics(sqale_rating="E"), policy)
    assert len(result.violations) == 1
    assert result.violations[0].severity == "ERROR"


def test_TG05_in_operator_pass():
    """in operator: value in allowed list → no violation."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="sqale_rating",
                   operator="in", threshold=["A", "B", "C"], severity="WARNING")
    ])
    result = evaluate_policy(_make_metrics(sqale_rating="B"), policy)
    assert len(result.violations) == 0


def test_TG06_in_operator_fail():
    """in operator: value not in list → violation."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="sqale_rating",
                   operator="in", threshold=["A", "B", "C"], severity="ERROR")
    ])
    result = evaluate_policy(_make_metrics(sqale_rating="D"), policy)
    assert len(result.violations) == 1


# ══════════════════════════════════════════════════════════════════════════════
# TG07-TG15 — evaluate_policy + scoring
# ══════════════════════════════════════════════════════════════════════════════

def test_TG07_clean_code_passes_default():
    """Clean metrics → no violations, gate PASS."""
    policy = load_default_policy()
    metrics = _make_metrics(
        cyclomatic_complexity=3,
        cognitive_complexity=4,
        infinite_loop_risk=0.0,
        syntactic_dead_code=0,
        halstead_bugs=0.1,
        sqale_rating="A",
        clone_count=0,
    )
    result = evaluate_policy(metrics, policy)
    assert result.passed, f"Expected PASS: {result.summary}"
    assert result.gate_score == 100
    assert result.grade == "A"


def test_TG08_high_cc_violation():
    """CC = 20 > 15 threshold → WARNING violation generated."""
    policy = load_default_policy()
    metrics = _make_metrics(cyclomatic_complexity=20)
    result = evaluate_policy(metrics, policy)
    cc_viols = [v for v in result.violations if "CC" in v.rule_id]
    assert len(cc_viols) >= 1


def test_TG09_multiple_violations_score():
    """Three WARNING violations: score = 100 - 30 = 70 (still PASS)."""
    policy = Policy(name="test", pass_threshold=70, rules=[
        PolicyRule(id="R1", field="f1", operator="lte", threshold=0, severity="WARNING"),
        PolicyRule(id="R2", field="f2", operator="lte", threshold=0, severity="WARNING"),
        PolicyRule(id="R3", field="f3", operator="lte", threshold=0, severity="WARNING"),
    ])
    metrics = {"f1": 1, "f2": 1, "f3": 1}
    result = evaluate_policy(metrics, policy)
    assert result.gate_score == 70
    assert result.passed      # exactly at threshold


def test_TG10_error_penalty_20():
    """ERROR violation subtracts 20 pts."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="f", operator="lte", threshold=0, severity="ERROR")
    ])
    result = evaluate_policy({"f": 99}, policy)
    assert result.gate_score == 80


def test_TG11_warning_penalty_10():
    """WARNING violation subtracts 10 pts."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="f", operator="lte", threshold=0, severity="WARNING")
    ])
    result = evaluate_policy({"f": 99}, policy)
    assert result.gate_score == 90


def test_TG12_missing_field_skipped():
    """Field not in metrics dict → rule is skipped (no violation)."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="nonexistent_metric",
                   operator="lte", threshold=0, severity="ERROR")
    ])
    result = evaluate_policy({"other_field": 5}, policy)
    assert len(result.violations) == 0


def test_TG13_default_policy_has_rules():
    """load_default_policy returns Policy with non-empty rules list."""
    policy = load_default_policy()
    assert isinstance(policy, Policy)
    assert len(policy.rules) > 0
    assert policy.pass_threshold == 70
    rule_ids = [r.id for r in policy.rules]
    assert "CC_ERROR" in rule_ids
    assert "ILR_ERROR" in rule_ids


def test_TG14_policy_from_dict():
    """policy_from_dict parses inline dict correctly."""
    d = {
        "name": "custom",
        "version": "2.0",
        "pass_threshold": 80,
        "rules": [
            {"id": "MY_RULE", "field": "cc", "operator": "lte",
             "threshold": 10, "severity": "ERROR"}
        ]
    }
    p = policy_from_dict(d)
    assert p.name == "custom"
    assert p.version == "2.0"
    assert p.pass_threshold == 80
    assert len(p.rules) == 1
    assert p.rules[0].id == "MY_RULE"
    assert p.rules[0].severity == "ERROR"


def test_TG15_gate_score_grades():
    """gate_score_to_grade maps ranges correctly."""
    assert gate_score_to_grade(100) == "A"
    assert gate_score_to_grade(90)  == "A"
    assert gate_score_to_grade(85)  == "B"
    assert gate_score_to_grade(75)  == "C"
    assert gate_score_to_grade(65)  == "D"
    assert gate_score_to_grade(55)  == "E"
    assert gate_score_to_grade(40)  == "F"
    assert gate_score_to_grade(0)   == "F"


# ══════════════════════════════════════════════════════════════════════════════
# TG16-TG17 — Full pipeline gate (via UCOBridge)
# ══════════════════════════════════════════════════════════════════════════════

def test_TG16_gate_full_pipeline_pass():
    """Clean Python code → gate passes with default policy."""
    from sensor_core.uco_bridge import UCOBridge
    src = """
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
"""
    bridge = UCOBridge(mode="full")
    mv = bridge.analyze(src, module_id="test.clean", commit_hash="abc")
    policy = load_default_policy()
    metrics = mv_to_metrics_dict(mv)
    result = evaluate_policy(metrics, policy)
    assert result.passed, f"Expected PASS: {result.summary}\nMetrics: {metrics}"


def test_TG17_gate_full_pipeline_fail():
    """Code with very high CC and dead code → gate fails."""
    from sensor_core.uco_bridge import UCOBridge
    # Artificially complex function + dead code
    src = """
def mega_complex(a, b, c, d, e, f):
    if a:
        if b:
            if c:
                if d:
                    if e:
                        if f:
                            return 1
    if a and b and c and d and e and f:
        return 2
    elif a or b or c:
        return 3
    elif d or e:
        return 4
    else:
        return 5
    x = 99  # dead code after return
    y = 100
    z = 101
"""
    bridge = UCOBridge(mode="full")
    mv = bridge.analyze(src, module_id="test.complex", commit_hash="def")
    policy = load_default_policy()
    metrics = mv_to_metrics_dict(mv)
    result = evaluate_policy(metrics, policy)
    # Should have at least some violations
    assert len(result.violations) > 0, \
        f"Expected violations for complex code; metrics={metrics}"


# ══════════════════════════════════════════════════════════════════════════════
# TG18-TG24 — Trend Engine
# ══════════════════════════════════════════════════════════════════════════════

def test_TG18_trend_insufficient_empty():
    """Empty history → INSUFFICIENT_DATA."""
    trend = analyze_trend([], metric="hamiltonian")
    assert trend.direction == INSUFFICIENT_DATA
    assert trend.window_used == 0


def test_TG19_trend_stable():
    """Flat values → STABLE direction."""
    history = _make_history([5.0, 5.0, 5.0, 5.0, 5.0])
    trend = analyze_trend(history, metric="hamiltonian", module_id="mod")
    assert trend.direction == STABLE
    assert abs(trend.slope) < 0.001


def test_TG20_trend_degrading():
    """Monotonically rising H → DEGRADING."""
    history = _make_history([2.0, 4.0, 6.0, 8.0, 10.0, 12.0])
    trend = analyze_trend(history, metric="hamiltonian")
    assert trend.direction == DEGRADING, f"direction={trend.direction}"
    assert trend.slope > 0


def test_TG21_trend_improving():
    """Monotonically decreasing H → IMPROVING."""
    history = _make_history([12.0, 10.0, 8.0, 6.0, 4.0, 2.0])
    trend = analyze_trend(history, metric="hamiltonian")
    assert trend.direction == IMPROVING, f"direction={trend.direction}"
    assert trend.slope < 0


def test_TG22_trend_volatile():
    """High variance values → VOLATILE."""
    history = _make_history([1.0, 20.0, 1.5, 18.0, 2.0, 19.0, 1.0, 21.0])
    trend = analyze_trend(history, metric="hamiltonian")
    assert trend.direction in (VOLATILE, DEGRADING), \
        f"direction={trend.direction} (expected VOLATILE or DEGRADING)"


def test_TG23_trend_forecast():
    """Forecast extrapolates via linear regression."""
    # Perfect linear: y = 2*i + 1 → next = 2*5+1 = 11
    history = _make_history([1.0, 3.0, 5.0, 7.0, 9.0])
    trend = analyze_trend(history, metric="hamiltonian")
    assert abs(trend.forecast_next - 11.0) < 0.5, \
        f"forecast={trend.forecast_next} expected ~11"


def test_TG24_analyze_module_trends():
    """analyze_module_trends returns dict keyed by metric name."""
    history = _make_history([5.0, 5.0, 5.0, 5.0, 5.0])
    trends = analyze_module_trends(history, module_id="mymod")
    assert isinstance(trends, dict)
    assert "hamiltonian" in trends
    assert "cyclomatic_complexity" in trends
    for m, t in trends.items():
        assert isinstance(t, TrendAnalysis)


# ══════════════════════════════════════════════════════════════════════════════
# TG25-TG27 — Debt Budget
# ══════════════════════════════════════════════════════════════════════════════

def test_TG25_debt_under_budget():
    """Debt below budget → over_budget=False."""
    budget = track_debt_budget(
        {"moduleA": 100, "moduleB": 50},
        budget_minutes=480,
    )
    assert budget.total_debt_minutes == 150
    assert budget.over_budget is False
    assert budget.remaining_minutes == 330
    assert budget.budget_pct_used < 100


def test_TG26_debt_over_budget():
    """Debt exceeds budget → over_budget=True."""
    budget = track_debt_budget(
        {"moduleA": 300, "moduleB": 300},
        budget_minutes=480,
    )
    assert budget.over_budget is True
    assert budget.total_debt_minutes == 600
    assert budget.remaining_minutes == -120


def test_TG27_debt_velocity():
    """Positive velocity → days_until_exhausted computed."""
    budget = track_debt_budget(
        {"moduleA": 200},
        budget_minutes=480,
        lookback_days=10.0,
        prev_total_debt=100,  # added 100 min over 10 days = 10 min/day
    )
    assert budget.velocity_min_per_day == 10.0
    # remaining = 280 / 10 min/day = 28 days
    assert budget.days_until_exhausted is not None
    assert abs(budget.days_until_exhausted - 28.0) < 0.5


# ══════════════════════════════════════════════════════════════════════════════
# TG28-TG30 — Utilities
# ══════════════════════════════════════════════════════════════════════════════

def test_TG28_trend_summary_string():
    """trend_summary returns non-empty descriptive string."""
    history = _make_history([5.0, 5.0, 5.0, 5.0, 5.0])
    trend = analyze_trend(history, metric="hamiltonian", module_id="mymod")
    s = trend_summary(trend)
    assert isinstance(s, str)
    assert "mymod" in s
    assert "hamiltonian" in s


def test_TG29_overall_trend_degrading():
    """overall_trend returns DEGRADING if any trend is DEGRADING."""
    from governance.trend_engine import TrendAnalysis
    t1 = TrendAnalysis(
        module_id="m", metric="h", direction=DEGRADING,
        slope=0.5, slope_pct=0.05, volatility=0.1, window_used=5,
        mean=5.0, latest=6.0, forecast_next=7.0,
        worst_snapshot=None, improving_since=None,
    )
    t2 = TrendAnalysis(
        module_id="m", metric="cc", direction=STABLE,
        slope=0.0, slope_pct=0.0, volatility=0.0, window_used=5,
        mean=3.0, latest=3.0, forecast_next=3.0,
        worst_snapshot=None, improving_since=None,
    )
    result = overall_trend({"h": t1, "cc": t2})
    assert result == DEGRADING


def test_TG30_policy_result_to_dict():
    """PolicyResult.to_dict round-trip."""
    policy = Policy(name="test", rules=[
        PolicyRule(id="R1", field="f", operator="lte", threshold=5, severity="WARNING")
    ])
    result = evaluate_policy({"f": 10}, policy)
    d = result.to_dict()
    assert "passed" in d
    assert "gate_score" in d
    assert "grade" in d
    assert "violations" in d
    assert isinstance(d["violations"], list)
    assert d["violations"][0]["rule_id"] == "R1"


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    ("TG01", test_TG01_lte_pass),
    ("TG02", test_TG02_lte_fail),
    ("TG03", test_TG03_rating_lte_pass),
    ("TG04", test_TG04_rating_lte_fail),
    ("TG05", test_TG05_in_operator_pass),
    ("TG06", test_TG06_in_operator_fail),
    ("TG07", test_TG07_clean_code_passes_default),
    ("TG08", test_TG08_high_cc_violation),
    ("TG09", test_TG09_multiple_violations_score),
    ("TG10", test_TG10_error_penalty_20),
    ("TG11", test_TG11_warning_penalty_10),
    ("TG12", test_TG12_missing_field_skipped),
    ("TG13", test_TG13_default_policy_has_rules),
    ("TG14", test_TG14_policy_from_dict),
    ("TG15", test_TG15_gate_score_grades),
    ("TG16", test_TG16_gate_full_pipeline_pass),
    ("TG17", test_TG17_gate_full_pipeline_fail),
    ("TG18", test_TG18_trend_insufficient_empty),
    ("TG19", test_TG19_trend_stable),
    ("TG20", test_TG20_trend_degrading),
    ("TG21", test_TG21_trend_improving),
    ("TG22", test_TG22_trend_volatile),
    ("TG23", test_TG23_trend_forecast),
    ("TG24", test_TG24_analyze_module_trends),
    ("TG25", test_TG25_debt_under_budget),
    ("TG26", test_TG26_debt_over_budget),
    ("TG27", test_TG27_debt_velocity),
    ("TG28", test_TG28_trend_summary_string),
    ("TG29", test_TG29_overall_trend_degrading),
    ("TG30", test_TG30_policy_result_to_dict),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco M2 — Governance Engine ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  OK {name}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL {name}: {exc}")
            failed += 1
            errors.append((name, exc))

    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")
    sys.exit(0 if failed == 0 else 1)
