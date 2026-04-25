"""
UCO-Sensor — Testes Marco M1: Advanced Metrics (v0.7.0)
=========================================================

Valida as métricas avançadas introduzidas no Marco M1.

  TM01  cognitive_complexity — função simples: if/for/while básico
  TM02  cognitive_complexity — elif/else incrementos flat
  TM03  cognitive_complexity — aninhamento profundo incrementa por profundidade
  TM04  cognitive_complexity — BoolOp conta +1 flat por sequência
  TM05  cognitive_complexity — lambda conta +1 + depth
  TM06  cognitive_complexity — ternary (IfExp) conta +1 flat
  TM07  cognitive_complexity — recursão detectada: +1 flat por call recursivo
  TM08  cognitive_complexity — nested function: +1 + depth para definição
  TM09  cognitive_complexity — excepts: +1 + depth por handler
  TM10  cognitive_complexity — código limpo sem control flow → 0
  TM11  sqale_debt           — código limpo → rating A, debt 0
  TM12  sqale_debt           — CC alto → debt > 0, rating piora
  TM13  sqale_debt           — dead code → debt proporcional
  TM14  sqale_debt           — clone groups → debt acumulado
  TM15  build_function_profiles — retorna lista de FunctionProfile
  TM16  build_function_profiles — CC e cogCC corretos por função
  TM17  build_function_profiles — is_complex = True para CC > 10
  TM18  detect_clones        — código sem clones → 0
  TM19  detect_clones        — funções idênticas estruturalmente → 1 grupo
  TM20  compute_ratings      — UCO ≥ 80 → ratings A
  TM21  compute_ratings      — UCO < 20 → uco = E
  TM22  compute_ratings      — ILR alto → reliability piora
  TM23  compute_ratings      — halstead_bugs > 3 → security piora
  TM24  ImportGraphAnalyzer  — DI real via import graph
  TM25  AdvancedAnalyzer     — enriquece MetricVector com atributos M1
  TM26  AdvancedAnalyzer     — UCOBridge.analyze injeta M1 em mode=full
  TM27  AdvancedAnalyzer     — mode=fast NÃO injeta M1
  TM28  SQALEResult          — to_dict round-trip
  TM29  FunctionProfile      — to_dict round-trip
  TM30  ImportGraphAnalyzer  — instability_summary stats
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict, Any

# ── Path setup ─────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sensor_core.advanced_metrics import (
    cognitive_complexity,
    sqale_debt,
    build_function_profiles,
    detect_clones,
    compute_ratings,
    ImportGraphAnalyzer,
    AdvancedAnalyzer,
    SQALEResult,
    FunctionProfile,
    Ratings,
)


# ══════════════════════════════════════════════════════════════════════════════
# TM01-TM10 — Cognitive Complexity
# ══════════════════════════════════════════════════════════════════════════════

def test_TM01_cog_simple_control_flow():
    """if/for/while básicos — cada um conta +1 (depth=0 dentro da função)."""
    src = """
def foo():
    if x:
        pass
    for i in lst:
        pass
    while cond:
        pass
"""
    total, fns = cognitive_complexity(src)
    # each control flow +1 + depth=0 = 1 each → 3
    assert fns.get("foo", 0) == 3, f"foo CC={fns.get('foo', 0)} esperado 3"
    assert total == 3


def test_TM02_cog_elif_else_flat():
    """elif e else somam +1 flat (sem bônus de profundidade)."""
    src = """
def foo():
    if a:
        pass
    elif b:
        pass
    else:
        pass
"""
    total, fns = cognitive_complexity(src)
    # if(+1) + elif(+1 flat) + else(+1 flat) = 3
    assert fns.get("foo", 0) == 3, f"foo CC={fns.get('foo', 0)} esperado 3"


def test_TM03_cog_nesting_bonus():
    """Aninhamento profundo: if dentro de for → +2 (1 + depth=1)."""
    src = """
def foo():
    for i in lst:
        if cond:
            pass
"""
    total, fns = cognitive_complexity(src)
    # for: +1+0=1, if: +1+1=2 → total=3
    assert fns.get("foo", 0) == 3, f"foo CC={fns.get('foo', 0)} esperado 3"


def test_TM04_cog_bool_op_flat():
    """BoolOp (and/or) conta +1 flat por sequência de mesmo operador."""
    src = """
def foo():
    if a and b and c:
        pass
"""
    total, fns = cognitive_complexity(src)
    # if: +1, BoolOp(and): +1 flat → 2
    assert fns.get("foo", 0) == 2, f"foo CC={fns.get('foo', 0)} esperado 2"


def test_TM05_cog_lambda_with_nesting():
    """Lambda dentro de for conta +1 + depth(=1)."""
    src = """
def foo():
    for i in lst:
        f = lambda x: x
"""
    total, fns = cognitive_complexity(src)
    # for: +1+0=1, lambda at depth=1: +1+1=2 → total=3
    assert fns.get("foo", 0) == 3, f"foo CC={fns.get('foo', 0)} esperado 3"


def test_TM06_cog_ternary_flat():
    """Ternary (IfExp) conta +1 flat."""
    src = """
def foo():
    x = a if cond else b
"""
    total, fns = cognitive_complexity(src)
    # ternary: +1 flat
    assert fns.get("foo", 0) == 1, f"foo CC={fns.get('foo', 0)} esperado 1"


def test_TM07_cog_recursion_increment():
    """Chamada recursiva dentro da função → +1 flat por site de chamada."""
    src = """
def factorial(n):
    return factorial(n - 1)
"""
    total, fns = cognitive_complexity(src)
    # recursion: +1 flat
    assert fns.get("factorial", 0) >= 1, \
        f"factorial CC={fns.get('factorial', 0)} esperado ≥1"


def test_TM08_cog_nested_function():
    """Função aninhada dentro de outra → +1 + depth para a definição."""
    src = """
def outer():
    def inner():
        if x:
            pass
"""
    total, fns = cognitive_complexity(src)
    # inner: +1 (nested def at depth=0 → 1+0=1) + inner's if (depth=0) +1 = 2
    # outer fn_score = 1 (nesting increment) + inner.fn_score(1) = 2
    assert "inner" in str(fns) or "outer.inner" in fns, \
        f"inner não detectado: {fns}"
    inner_key = "outer.inner" if "outer.inner" in fns else "inner"
    assert fns.get(inner_key, 0) == 1, \
        f"inner CC={fns.get(inner_key, 0)} esperado 1 (apenas o if)"
    outer_key = "outer"
    assert fns.get(outer_key, 0) == 2, \
        f"outer CC={fns.get(outer_key, 0)} esperado 2 (nesting+inner)"


def test_TM09_cog_except_handlers():
    """Cada except handler conta +1 + depth."""
    src = """
def foo():
    try:
        pass
    except ValueError:
        pass
    except TypeError:
        pass
"""
    total, fns = cognitive_complexity(src)
    # try=0, except1: +1+0=1, except2: +1+0=1 → 2
    assert fns.get("foo", 0) == 2, f"foo CC={fns.get('foo', 0)} esperado 2"


def test_TM10_cog_clean_code_zero():
    """Função sem control flow tem cognitive CC = 0."""
    src = """
def add(a, b):
    return a + b
"""
    total, fns = cognitive_complexity(src)
    assert fns.get("add", 0) == 0, f"add CC={fns.get('add', 0)} esperado 0"
    assert total == 0


# ══════════════════════════════════════════════════════════════════════════════
# TM11-TM14 — SQALE Technical Debt
# ══════════════════════════════════════════════════════════════════════════════

def test_TM11_sqale_clean_code():
    """Código limpo → debt=0, rating=A."""
    result = sqale_debt({
        "cyclomatic_complexity": 3,
        "fn_cc_max": 3,
        "cognitive_cc": 2,
        "cognitive_fn_max": 2,
        "syntactic_dead_code": 0,
        "ilr_loop_count": 0,
        "clone_count": 0,
        "dependency_instability": 0.3,
        "halstead_bugs": 0.1,
    }, loc=50)
    assert result.debt_minutes == 0, f"debt={result.debt_minutes} esperado 0"
    assert result.rating == "A", f"rating={result.rating} esperado A"
    assert result.sqale_ratio == 0.0


def test_TM12_sqale_high_cc():
    """CC > 10 per function → debt > 0, rating piora."""
    result = sqale_debt({
        "cyclomatic_complexity": 15,
        "fn_cc_max": 15,
        "cognitive_cc": 5,
        "cognitive_fn_max": 5,
        "syntactic_dead_code": 0,
        "ilr_loop_count": 0,
        "clone_count": 0,
        "dependency_instability": 0.3,
        "halstead_bugs": 0.1,
    }, loc=30)
    assert result.debt_minutes >= 30, f"debt={result.debt_minutes} esperado ≥30"
    assert "cc_high" in result.breakdown


def test_TM13_sqale_dead_code():
    """Dead code lines → debt proporcional (5 min/linha)."""
    result = sqale_debt({
        "cyclomatic_complexity": 3,
        "fn_cc_max": 3,
        "cognitive_cc": 1,
        "cognitive_fn_max": 1,
        "syntactic_dead_code": 10,
        "ilr_loop_count": 0,
        "clone_count": 0,
        "dependency_instability": 0.2,
        "halstead_bugs": 0.1,
    }, loc=50)
    assert result.debt_minutes >= 50, f"debt={result.debt_minutes} esperado ≥50"
    assert "dead_code" in result.breakdown
    assert result.breakdown["dead_code"] == 50   # 10 * 5min


def test_TM14_sqale_clones():
    """Clone groups → debt acumulado."""
    result = sqale_debt({
        "cyclomatic_complexity": 3,
        "fn_cc_max": 3,
        "cognitive_cc": 1,
        "cognitive_fn_max": 1,
        "syntactic_dead_code": 0,
        "ilr_loop_count": 0,
        "clone_count": 3,
        "dependency_instability": 0.2,
        "halstead_bugs": 0.1,
    }, loc=100)
    assert result.debt_minutes >= 90, f"debt={result.debt_minutes} esperado ≥90"
    assert "clone_groups" in result.breakdown
    assert result.breakdown["clone_groups"] == 90   # 3 * 30min


# ══════════════════════════════════════════════════════════════════════════════
# TM15-TM17 — Function Profiles
# ══════════════════════════════════════════════════════════════════════════════

_PROFILE_SRC = """
def simple(x):
    return x + 1

def complex_fn(data):
    for item in data:
        if item > 0:
            for j in range(item):
                if j % 2 == 0:
                    result = j * 2
                else:
                    result = j
    return result
"""


def test_TM15_profiles_list():
    """build_function_profiles retorna lista de FunctionProfile."""
    fn_cc  = {"simple": 1, "complex_fn": 5}
    fn_cog = {"simple": 0, "complex_fn": 8}
    profiles = build_function_profiles(_PROFILE_SRC, fn_cc, fn_cog)
    assert isinstance(profiles, list)
    assert len(profiles) == 2
    names = {p.name for p in profiles}
    assert "simple" in names
    assert "complex_fn" in names


def test_TM16_profiles_cc_values():
    """CC e cognitive_cc corretos por função."""
    fn_cc  = {"simple": 1, "complex_fn": 7}
    fn_cog = {"simple": 0, "complex_fn": 9}
    profiles = build_function_profiles(_PROFILE_SRC, fn_cc, fn_cog)
    by_name = {p.name: p for p in profiles}

    assert by_name["simple"].cc == 1
    assert by_name["simple"].cognitive_cc == 0
    assert by_name["complex_fn"].cc == 7
    assert by_name["complex_fn"].cognitive_cc == 9


def test_TM17_profiles_is_complex():
    """is_complex = True para CC > 10."""
    fn_cc  = {"big_fn": 12}
    fn_cog = {"big_fn": 5}
    src = "def big_fn():\n    pass\n"
    profiles = build_function_profiles(src, fn_cc, fn_cog)
    assert len(profiles) == 1
    assert profiles[0].is_complex is True
    assert profiles[0].risk_level == "MEDIUM"


# ══════════════════════════════════════════════════════════════════════════════
# TM18-TM19 — Clone Detection
# ══════════════════════════════════════════════════════════════════════════════

def test_TM18_no_clones():
    """Código sem funções duplicadas → 0 grupos de clones."""
    src = """
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
    assert detect_clones(src) == 0


def test_TM19_clone_detected():
    """Duas funções com estrutura idêntica (Type-2) → 1 grupo de clone."""
    src = """
def process_users(users):
    result = []
    for item in users:
        if item.active:
            for sub in item.items:
                if sub.valid:
                    result.append(sub.value)
    return result

def process_products(products):
    result = []
    for item in products:
        if item.active:
            for sub in item.items:
                if sub.valid:
                    result.append(sub.value)
    return result
"""
    groups = detect_clones(src)
    assert groups >= 1, f"Esperado ≥1 grupo de clone, got {groups}"


# ══════════════════════════════════════════════════════════════════════════════
# TM20-TM23 — Ratings
# ══════════════════════════════════════════════════════════════════════════════

def test_TM20_ratings_all_a():
    """UCO ≥ 80, baixo SQALE → todos os ratings A."""
    r = compute_ratings(
        uco_score=85.0, sqale_ratio_pct=2.0,
        ilr=0.0, cc=3, dead_lines=0, loc=100, halstead_bugs=0.1,
    )
    assert r.uco == "A",         f"uco={r.uco}"
    assert r.sqale == "A",       f"sqale={r.sqale}"
    assert r.reliability == "A", f"reliability={r.reliability}"
    assert r.security == "A",    f"security={r.security}"


def test_TM21_ratings_uco_e():
    """UCO < 20 → uco = E."""
    r = compute_ratings(uco_score=10.0, sqale_ratio_pct=5.0)
    assert r.uco == "E", f"uco={r.uco} esperado E"


def test_TM22_ratings_ilr_degrades_reliability():
    """ILR > 0.5 → reliability piora (não A)."""
    r = compute_ratings(
        uco_score=75.0, sqale_ratio_pct=3.0,
        ilr=0.7, cc=5, dead_lines=0, loc=100, halstead_bugs=0.2,
    )
    assert r.reliability != "A", f"reliability={r.reliability} deveria ser < A"


def test_TM23_ratings_high_bugs_security():
    """Halstead bugs > 3 → security piora."""
    r = compute_ratings(
        uco_score=75.0, sqale_ratio_pct=3.0,
        ilr=0.0, cc=5, dead_lines=0, loc=100, halstead_bugs=3.5,
    )
    assert r.security != "A", f"security={r.security} deveria ser < A"


# ══════════════════════════════════════════════════════════════════════════════
# TM24, TM30 — ImportGraphAnalyzer
# ══════════════════════════════════════════════════════════════════════════════

def test_TM24_import_graph_di():
    """DI real via import graph — Ce/(Ca+Ce)."""
    analyzer = ImportGraphAnalyzer()
    # A imports B and C; B imports C; C imports nothing
    analyzer.add_module("A", {"B", "C"})
    analyzer.add_module("B", {"C"})
    analyzer.add_module("C", set())

    di = analyzer.compute_di()
    # A: Ce=2(B+C), Ca=0 → DI = 2/(0+2) = 1.0
    assert di["A"] == 1.0, f"DI(A)={di['A']} esperado 1.0"
    # B: Ce=1(C), Ca=1(A) → DI = 1/(1+1) = 0.5
    assert di["B"] == 0.5, f"DI(B)={di['B']} esperado 0.5"
    # C: Ce=0, Ca=2(A+B) → DI = 0/(2+0) = 0.0
    assert di["C"] == 0.0, f"DI(C)={di['C']} esperado 0.0"


def test_TM30_import_graph_summary():
    """instability_summary retorna stats corretas."""
    analyzer = ImportGraphAnalyzer()
    analyzer.add_module("A", {"B"})
    analyzer.add_module("B", set())

    summary = analyzer.instability_summary()
    assert summary["count"] == 2
    assert "avg_di" in summary
    assert "max_di" in summary
    assert isinstance(summary["unstable_modules"], list)


# ══════════════════════════════════════════════════════════════════════════════
# TM25-TM27 — AdvancedAnalyzer integration
# ══════════════════════════════════════════════════════════════════════════════

class _FakeMV:
    """Minimal mock MetricVector for AdvancedAnalyzer tests."""
    def __init__(self):
        self.module_id = "test"
        self.lines_of_code = 20
        self.cyclomatic_complexity = 3
        self.infinite_loop_risk = 0.0
        self.syntactic_dead_code = 0
        self.dependency_instability = 0.2
        self.halstead_bugs = 0.1
        self.status = "STABLE"


class _FakeVisitor:
    """Minimal mock visitor for AdvancedAnalyzer tests."""
    def __init__(self):
        self.fn_cc = {"add": 1, "multiply": 2}
        self.loop_risk_count = 0


def test_TM25_advanced_analyzer_enriches_mv():
    """AdvancedAnalyzer.analyze() adiciona atributos M1 ao MetricVector."""
    src = """
def add(a, b):
    return a + b

def multiply(a, b):
    result = 0
    for _ in range(b):
        result += a
    return result
"""
    mv = _FakeMV()
    visitor = _FakeVisitor()

    analyzer = AdvancedAnalyzer()
    analyzer.analyze(src, mv, visitor)

    assert hasattr(mv, "cognitive_complexity"), "cognitive_complexity ausente"
    assert hasattr(mv, "sqale_debt_minutes"),   "sqale_debt_minutes ausente"
    assert hasattr(mv, "sqale_rating"),          "sqale_rating ausente"
    assert hasattr(mv, "clone_count"),           "clone_count ausente"
    assert hasattr(mv, "ratings"),               "ratings ausente"
    assert hasattr(mv, "function_profiles"),     "function_profiles ausente"
    assert mv.advanced_ok is True


def test_TM26_bridge_injects_m1_in_full_mode():
    """UCOBridge.analyze(mode='full') injeta atributos M1."""
    from sensor_core.uco_bridge import UCOBridge
    src = """
def compute(data):
    total = 0
    for item in data:
        if item > 0:
            total += item
    return total
"""
    bridge = UCOBridge(mode="full")
    mv = bridge.analyze(src, module_id="test.compute",
                        commit_hash="abc123")

    assert hasattr(mv, "cognitive_complexity"), "cognitive_complexity ausente"
    assert isinstance(mv.cognitive_complexity, int)
    assert mv.cognitive_complexity >= 0
    assert hasattr(mv, "ratings"), "ratings ausente"
    assert isinstance(mv.ratings, dict)
    assert "uco" in mv.ratings
    assert mv.ratings["uco"] in "ABCDE"


def test_TM27_bridge_no_m1_in_fast_mode():
    """UCOBridge.analyze(mode='fast') NÃO injeta atributos M1."""
    from sensor_core.uco_bridge import UCOBridge
    src = "def f(x):\n    return x + 1\n"
    bridge = UCOBridge(mode="fast")
    mv = bridge.analyze(src, module_id="test.f", commit_hash="abc123")

    # In fast mode, M1 attributes should NOT be present
    assert not hasattr(mv, "cognitive_complexity"), \
        "cognitive_complexity não deve estar em mode=fast"


# ══════════════════════════════════════════════════════════════════════════════
# TM28-TM29 — Dataclass round-trips
# ══════════════════════════════════════════════════════════════════════════════

def test_TM28_sqale_result_dict():
    """SQALEResult campos corretos."""
    r = SQALEResult(
        debt_minutes=60,
        sqale_ratio=4.5,
        rating="A",
        breakdown={"cc_high": 30, "dead_code": 30},
    )
    assert r.debt_minutes == 60
    assert r.sqale_ratio == 4.5
    assert r.rating == "A"
    assert r.breakdown["cc_high"] == 30


def test_TM29_function_profile_dict():
    """FunctionProfile.to_dict() retorna campos esperados."""
    p = FunctionProfile(
        name="my_func",
        loc=25,
        cc=5,
        cognitive_cc=7,
        halstead_volume=112.5,
        is_complex=False,
        debt_minutes=0,
        risk_level="LOW",
    )
    d = p.to_dict()
    assert d["name"] == "my_func"
    assert d["cc"] == 5
    assert d["cognitive_cc"] == 7
    assert d["is_complex"] is False
    assert d["risk_level"] == "LOW"


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    ("TM01", test_TM01_cog_simple_control_flow),
    ("TM02", test_TM02_cog_elif_else_flat),
    ("TM03", test_TM03_cog_nesting_bonus),
    ("TM04", test_TM04_cog_bool_op_flat),
    ("TM05", test_TM05_cog_lambda_with_nesting),
    ("TM06", test_TM06_cog_ternary_flat),
    ("TM07", test_TM07_cog_recursion_increment),
    ("TM08", test_TM08_cog_nested_function),
    ("TM09", test_TM09_cog_except_handlers),
    ("TM10", test_TM10_cog_clean_code_zero),
    ("TM11", test_TM11_sqale_clean_code),
    ("TM12", test_TM12_sqale_high_cc),
    ("TM13", test_TM13_sqale_dead_code),
    ("TM14", test_TM14_sqale_clones),
    ("TM15", test_TM15_profiles_list),
    ("TM16", test_TM16_profiles_cc_values),
    ("TM17", test_TM17_profiles_is_complex),
    ("TM18", test_TM18_no_clones),
    ("TM19", test_TM19_clone_detected),
    ("TM20", test_TM20_ratings_all_a),
    ("TM21", test_TM21_ratings_uco_e),
    ("TM22", test_TM22_ratings_ilr_degrades_reliability),
    ("TM23", test_TM23_ratings_high_bugs_security),
    ("TM24", test_TM24_import_graph_di),
    ("TM25", test_TM25_advanced_analyzer_enriches_mv),
    ("TM26", test_TM26_bridge_injects_m1_in_full_mode),
    ("TM27", test_TM27_bridge_no_m1_in_fast_mode),
    ("TM28", test_TM28_sqale_result_dict),
    ("TM29", test_TM29_function_profile_dict),
    ("TM30", test_TM30_import_graph_summary),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco M1 — Advanced Metrics ({len(TESTS)} testes)")
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
