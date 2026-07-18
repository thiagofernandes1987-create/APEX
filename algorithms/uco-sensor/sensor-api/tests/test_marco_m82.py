"""
Marco 82 — M14: FunctionScoper — escopo real de função por AST
==============================================================
Substitui a janela de ±N linhas do M11 (Sprint BH) pelo escopo real da função
via tree-sitter (o mesmo motor do M9.2). O brace-matcher falhava em C real
(macros function-like, preprocessador); o escopo por AST corta falsos-negativos
(guard em outra função suprimindo achado) e falsos-positivos (guard além da
janela numa função grande — php-src `init_request_info` tem 394 linhas).
"""
from __future__ import annotations

import pytest

from sast.scope import FunctionScoper

_C = """\
#include <stdio.h>
int outer(int a, int b) {
    int r = a - b;
    return r;
}
void inner(char *p, int pilen, int slen) {
    char *path;
    if (env) {
        path = p + pilen - slen;
    }
}
"""


def _scoper():
    fs = FunctionScoper()
    if not fs.available_for(".c"):
        pytest.skip("tree-sitter C grammar indisponível")
    return fs


def test_T82_finds_enclosing_function():
    fs = _scoper()
    # linha do `path = p + pilen - slen;` (0-based ~ linha 9 1-based)
    span = fs.enclosing_span(_C, 9, ".c")
    assert span is not None
    s, e = span
    # deve ser a função inner (não outer)
    assert s <= 9 <= e
    body = "\n".join(_C.splitlines()[s - 1:e])
    assert "inner" in body and "outer" not in body


def test_T82_line_outside_function_returns_none_or_toplevel():
    fs = _scoper()
    span = fs.enclosing_span(_C, 1, ".c")  # #include — fora de função
    # ou None ou um span que NÃO cobre a linha 1 de forma espúria
    assert span is None or not (span[0] <= 1 <= span[1] and "inner" in _C)


def test_T82_function_spans_single_parse():
    fs = _scoper()
    spans = fs.function_spans(_C, ".c")
    assert spans is not None
    assert len(spans) >= 2  # outer + inner


def test_T82_smallest_enclosing_picks_innermost():
    spans = [(1, 20), (5, 10), (6, 8)]
    assert FunctionScoper.smallest_enclosing(spans, 7) == (6, 8)
    assert FunctionScoper.smallest_enclosing(spans, 3) == (1, 20)
    assert FunctionScoper.smallest_enclosing(spans, 99) is None


def test_T82_unknown_ext_returns_none():
    fs = FunctionScoper()
    assert fs.function_spans("x = 1", ".xyz") is None
    assert fs.enclosing_span("x = 1", 1, ".xyz") is None
