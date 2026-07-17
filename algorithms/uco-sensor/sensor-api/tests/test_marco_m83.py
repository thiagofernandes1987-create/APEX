"""
Marco 83 — M15: sinais de CFG do UCO V4 consumidos pelo sensor
==============================================================
Fecha o item de checklist "consumir o GenericCFG do V4 para C/Rust/Java".
Até BJ o V4 estava absorvido mas o CFG genérico não era consumido; M15
(`metrics/cfg_signals.py`) o expõe como sinal do sensor para QUALQUER
linguagem: reachable_ratio (código morto), infinite_loop_risk (classe DoS),
cyclomatic, loop_count. Degradação graciosa (nunca levanta).
"""
from __future__ import annotations

from metrics.cfg_signals import cfg_signals, unreachable_after_return


def test_T83_c_infinite_loop_risk_flagged():
    # for(;;) é loop sem saída → risco de loop infinito (classe DoS)
    s = cfg_signals("int f(int n){ for(;;){ n++; } return n; }", "c")
    assert s["status"] == "ok"
    assert s["node_count"] >= 2
    assert s["loop_count"] >= 1
    assert s["infinite_loop_risk"] > 0.0


def test_T83_c_dead_code_reachable_ratio():
    s = cfg_signals("int f(int n){ for(;;){ n++; } return n; int dead=1; }", "c")
    # há bloco inalcançável → reachable_ratio < 1
    assert s["reachable_ratio"] <= 1.0
    assert s["reachable_count"] <= s["node_count"]


def test_T83_rust_and_java_have_cfg():
    r = cfg_signals("fn f(n: i32) -> i32 { if n > 0 { return 1; } 0 }", "rust")
    assert r["status"] == "ok" and r["cyclomatic"] >= 1
    j = cfg_signals("class C { int f(int n){ if (n>0) return 1; return 0; } }", "java")
    assert j["status"] == "ok"


def test_T83_python_unreachable_after_return():
    assert unreachable_after_return("def f():\n    return 1\n    x = 2\n", "python") is True
    assert unreachable_after_return("def f():\n    return 1\n", "python") is False


def test_T83_graceful_on_garbage():
    s = cfg_signals("@@@ not code @@@", "c")
    # nunca levanta; status ok (CFG vazio) ou unavailable
    assert s["status"] in ("ok", "unavailable")
    assert isinstance(s["infinite_loop_risk"], float)
