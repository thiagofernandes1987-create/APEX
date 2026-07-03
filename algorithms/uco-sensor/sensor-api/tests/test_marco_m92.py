"""
Marco 92 — M17: Taint inter-procedural (fonte→sink cruzando funções)
====================================================================
O motor intra-procedural (`TaintAnalyzer`) não liga uma fonte numa função ao
sink em OUTRA função (seu próprio docstring diz "interprocedural DFA …
deferred"). O `InterprocTaintAnalyzer` (M17) constrói um mini call-graph e
propaga taint por posição de parâmetro até um ponto-fixo, reportando o fluxo
que cruza a fronteira — o caso dominante em código real e gerado por IA.

Contrato validado:
  * detecta SQL-injection cross-fn (`view` → `query_db`) que o intra perde;
  * respeita sanitizer no meio do caminho (anti-FP);
  * não reporta fluxo puramente intra como inter-procedural.
"""
from __future__ import annotations

from sast.taint_interproc import InterprocTaintAnalyzer, InterprocFlow
from sast.taint_engine import TaintAnalyzer


_SQLI_CROSS = '''
def view(request):
    uid = request.GET["id"]
    query_db(uid)

def query_db(x):
    cursor.execute("SELECT * FROM u WHERE id=" + x)
'''

_SANITIZED = '''
import html
def view(request):
    raw = request.GET["name"]
    safe = html.escape(raw)
    render(safe)

def render(value):
    cursor.execute("SELECT " + value)
'''

_INTRA_ONLY = '''
def view(request):
    uid = request.GET["id"]
    cursor.execute("SELECT * FROM u WHERE id=" + uid)
'''


def test_T92_detects_cross_function_sqli():
    flows = InterprocTaintAnalyzer().analyze(_SQLI_CROSS)
    assert len(flows) >= 1
    f = flows[0]
    assert isinstance(f, InterprocFlow)
    assert f.source_fn == "view" and f.sink_fn == "query_db"
    assert f.hops == ["view", "query_db"]
    assert f.cwe_id == "CWE-89"


def test_T92_interproc_catches_what_intra_misses():
    # o intra-procedural NÃO liga view→query_db; o M17 sim.
    intra = TaintAnalyzer().analyze(_SQLI_CROSS)
    inter = InterprocTaintAnalyzer().analyze(_SQLI_CROSS)
    assert len(inter) > len(intra.flows)


def test_T92_respects_sanitizer_in_path():
    # html.escape antes do hop → não deve reportar fluxo inter-procedural.
    flows = InterprocTaintAnalyzer().analyze(_SANITIZED)
    assert flows == []


def test_T92_pure_intra_not_reported_as_interproc():
    # fluxo que começa e termina na mesma função não é inter-procedural.
    flows = InterprocTaintAnalyzer().analyze(_INTRA_ONLY)
    assert flows == []


def test_T92_syntax_error_is_empty_not_raises():
    assert InterprocTaintAnalyzer().analyze("def (:::") == []


# ── ampliação de source-recognition (Sprint BX): aliases de request ──────────
_CMDI_REQ_ALIAS = '''
def handler(req):
    cmd = req.args.get("cmd")
    runner(cmd)
def runner(value):
    import os
    os.system(value)
'''


def test_T92_request_alias_source_cross_fn():
    # `req.args.get(...)` (alias `req` de request) agora é reconhecido como
    # source; o fluxo cmd-injection cruza handler->runner.
    flows = InterprocTaintAnalyzer().analyze(_CMDI_REQ_ALIAS)
    assert len(flows) >= 1
    assert flows[0].source_fn == "handler" and flows[0].sink_fn == "runner"


def test_T92_request_alias_source_recognized_directly():
    from sast.taint_engine import _REQUEST_DATA_ATTRS
    # os atributos de dados foram derivados corretamente de _SOURCE_ATTRS
    assert "args" in _REQUEST_DATA_ATTRS and "GET" in _REQUEST_DATA_ATTRS


# ── hops via atributo de objeto (Sprint BY): self.<metodo>(tainted) ──────────
_OO_HOP = '''
class View:
    def handle(self, request):
        name = request.GET["name"]
        self.render(name)
    def render(self, value):
        cursor.execute("SELECT " + value)
'''
_OO_HOP_SAFE = '''
import html
class View:
    def handle(self, request):
        name = request.GET["name"]
        self.render(html.escape(name))
    def render(self, value):
        cursor.execute("SELECT " + value)
'''


def test_T92_object_method_hop():
    # `self.render(name)` resolve o hop com offset do `self` implícito.
    flows = InterprocTaintAnalyzer().analyze(_OO_HOP)
    assert len(flows) >= 1
    assert flows[0].source_fn == "handle" and flows[0].sink_fn == "render"


def test_T92_object_method_hop_respects_sanitizer():
    # sanitizado antes do hop → não dispara (anti-FP também no caminho OO).
    assert InterprocTaintAnalyzer().analyze(_OO_HOP_SAFE) == []
