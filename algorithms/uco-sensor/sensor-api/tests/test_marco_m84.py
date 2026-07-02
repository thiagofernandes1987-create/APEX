"""
Marco 84 — M16: expansão da detecção de fonte do motor de taint
================================================================
Diagnóstico (Sprint BN, dado real): o `TaintAnalyzer` detectava
`request.args["x"]` (subscript) mas NÃO `request.args.get("x")` (método
acessor) — o padrão de entrada Flask/Django MAIS comum — nem cadeias com
prefixo de módulo (`flask.request.args...`). Sem isso, o motor perdia a
maioria dos fluxos web reais (sources=0 → nenhum caminho fonte→sink).

M16 fecha o gap: métodos acessores (`get`/`getlist`/`get_json`/…) sobre um
atributo-fonte + casamento do último segmento do objeto para tolerar a
cadeia — mantendo precisão (um `dict.get()` benigno NÃO é fonte).
"""
from __future__ import annotations

from sast.taint_engine import TaintAnalyzer


def _sources(src: str) -> int:
    return TaintAnalyzer().analyze(src).to_dict().get("source_count", 0)


def _paths(src: str) -> int:
    return TaintAnalyzer().analyze(src).to_dict().get("taint_path_count", 0)


_SINK = "    os.system('ls ' + str(c))\n"


def test_T84_request_args_get_is_source():
    src = "from flask import request\nimport os\ndef f():\n    c = request.args.get('x')\n" + _SINK
    assert _sources(src) >= 1
    assert _paths(src) >= 1


def test_T84_chained_flask_request_is_source():
    src = "import flask, os\ndef f():\n    c = flask.request.args.get('x')\n" + _SINK
    assert _sources(src) >= 1


def test_T84_getlist_and_get_json_are_sources():
    a = "from flask import request\nimport os\ndef f():\n    c = request.form.getlist('x')\n" + _SINK
    b = "from flask import request\nimport os\ndef f():\n    c = request.get_json()\n" + _SINK
    assert _sources(a) >= 1
    assert _sources(b) >= 1


def test_T84_subscript_source_regression():
    src = "from flask import request\nimport os\ndef f():\n    c = request.args['x']\n" + _SINK
    assert _sources(src) >= 1


def test_T84_benign_dict_get_is_not_a_source():
    src = "def f(d):\n    c = d.get('x')\n    return c\n"
    assert _sources(src) == 0
    assert _paths(src) == 0
