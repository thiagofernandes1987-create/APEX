"""
Marco 88 — META A: precisão do GA01 (gate anti-cadeia-compensada)
=================================================================
Diagnóstico com dado real (Sprint BS): o GA01 disparava em
`overheadlen + olddatasize - olditemsize + newitemsize` (postgres
arrayfuncs.c) — um FALSO-POSITIVO: a subtração é fragmento de uma cadeia
maior e o `+ newitemsize` seguinte compensa o underflow.

Correção: se a subtração `base + a - b` é seguida por outro operador
aritmético (`+`/`-`), não é o padrão de risco isolado → não dispara.
Mantém o verdadeiro-positivo isolado (php-src `env_path_info + pilen - slen`).
"""
from __future__ import annotations

from sast.guard_aware import GuardAwareScanner


def _ga01(src: str):
    return [g for g in GuardAwareScanner().scan(src, ".c") if g.rule_id == "GA01"]


def test_T88_isolated_subtraction_still_fires():
    # padrão php-src: subtração isolada, sem termo compensatório → dispara
    src = ("static int f(char *base, int pilen, int slen){\n"
           "    char *p = base + pilen - slen;\n"
           "    return p != base;\n}\n")
    finds = _ga01(src)
    assert len(finds) == 1
    assert finds[0].needs_guard_on == ("pilen", "slen")


def test_T88_compensated_chain_does_not_fire():
    # padrão postgres: `a + b - c + d` — o `+ d` compensa → NÃO dispara (FP cortado)
    src = ("static int g(int overheadlen,int olddatasize,int olditemsize,int newitemsize){\n"
           "    int newsize = overheadlen + olddatasize - olditemsize + newitemsize;\n"
           "    return newsize;\n}\n")
    assert _ga01(src) == []


def test_T88_subtraction_then_minus_does_not_fire():
    src = ("static int h(int a,int b,int c,int d){\n"
           "    int r = a + b - c - d;\n"
           "    return r;\n}\n")
    assert _ga01(src) == []


def test_T88_guarded_subtraction_still_suppressed():
    # regressão: com guard no escopo, continua suprimido
    src = ("static int f(char *base, int pilen, int slen){\n"
           "    if (pilen > slen) {\n"
           "        char *p = base + pilen - slen;\n"
           "        return p != base;\n"
           "    }\n    return 0;\n}\n")
    assert _ga01(src) == []
