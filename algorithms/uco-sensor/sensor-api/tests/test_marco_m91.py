"""
Marco 91 — M21: Weak-Point Score (META D) — "onde alguém pode quebrar"
=====================================================================
Score probabilístico de ponto fraco por módulo, combinando segurança
(M11 + taint + taint-lite), superfície de injeção, complexidade e
hamiltoniano num número 0–100 EXPLICÁVEL (top_reasons). Validado com dado
real (php-src, handler injetável, util limpo).
"""
from __future__ import annotations

from sast.weak_point import WeakPointScorer, WeakPoint


def _score(src: str, ext: str, mid: str = "m") -> WeakPoint:
    return WeakPointScorer().score(src, ext, mid)


def test_T91_clean_file_scores_near_zero():
    w = _score("def add(a, b):\n    return a + b\n", ".py", "util")
    assert w.score < 5.0
    assert w.n_security == 0
    assert w.top_reasons == []


def test_T91_injection_file_scores_high_and_explains():
    src = ("from flask import request\nimport os, pickle\n"
           "def h():\n    c = request.args.get('x')\n    os.system(c)\n"
           "    return pickle.loads(request.data)\n")
    w = _score(src, ".py", "handler")
    assert w.score > 30.0
    assert w.n_security >= 1
    assert w.factors["injection"] > 0.0
    assert any("fonte" in r or "fluxo" in r for r in w.top_reasons)


def test_T91_memory_safety_file_flags_and_explains():
    src = "int f(char* base, int a, int b){ char* p = base + a - b; return *p; }\n"
    w = _score(src, ".c", "mem")
    assert w.n_security >= 1
    assert w.factors["security"] > 0.0
    assert any("memory-safety" in r for r in w.top_reasons)


def test_T91_ranking_injection_gt_clean():
    inj = _score("from flask import request\nimport os\ndef h():\n c=request.args.get('x'); os.system(c)\n", ".py", "a")
    clean = _score("def add(a,b):\n return a+b\n", ".py", "b")
    assert inj.score > clean.score


def test_T91_score_bounded_0_100():
    w = _score("int f(char*b,int a,int c){char*p=b+a-c;return *p;}\n", ".c", "x")
    assert 0.0 <= w.score <= 100.0
    d = w.to_dict()
    assert set(d["factors"]) == {"security", "injection", "complexity", "hamiltonian"}
