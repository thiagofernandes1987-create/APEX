"""
Marco 94 — M22: Taint fluxo-sensível sobre a CFG do UCO V4
==========================================================
O `CFGTaintAnalyzer` (M22) operacionaliza o taint-tracking sobre a CFG REAL do
UCO V4 (`uco_core.PythonCFGBuilder`), consumindo os `python_defs_uses` (defs/uses
por nó) e rodando um ponto-fixo forward path-sensitive nas arestas do grafo.

Diferencial validado (o que só a CFG entrega):
  * sanitização CONDICIONAL (só num braço do `if`) → o caminho `else` mantém a
    variável contaminada → o sink DISPARA (um motor "viu escape ⇒ limpo" erra);
  * sanitização INCONDICIONAL antes do sink → mata o taint em todos os caminhos
    → NÃO dispara;
  * reuso do vocabulário calibrado do M7.2 (source/sink/sanitizer) e do gating
    SQL arg[0] do M17/CD (query parametrizada é segura).
"""
from __future__ import annotations

from sast.taint_cfg import CFGTaintAnalyzer, CFGTaintFlow


_DIRECT = '''
def f(request):
    x = request.GET['id']
    cursor.execute('SELECT ' + x)
'''

_COND_SANITIZE = '''
def f(request):
    x = request.GET['id']
    if cond:
        x = escape(x)
    cursor.execute(x)
'''

_UNCOND_SANITIZE = '''
def f(request):
    x = request.GET['id']
    x = escape(x)
    cursor.execute(x)
'''

_CAST_INT = '''
def f(request):
    x = int(request.GET['id'])
    cursor.execute('SELECT ' + str(x))
'''

_NO_SOURCE = '''
def f():
    x = 'literal'
    cursor.execute(x)
'''

_PARAMETERIZED = '''
def f(request):
    x = request.GET['id']
    cursor.execute('SELECT * FROM u WHERE id=%s', (x,))
'''


def test_T94_direct_source_to_sink_fires():
    flows = CFGTaintAnalyzer().analyze(_DIRECT)
    assert len(flows) == 1
    f = flows[0]
    assert isinstance(f, CFGTaintFlow)
    assert f.cwe_id == "CWE-89" and f.var == "x"
    assert f.source_desc.startswith("request.GET")


def test_T94_conditional_sanitize_still_fires():
    # DIFERENCIAL path-sensitive: o braço `else` não sanitiza → ainda vulnerável.
    flows = CFGTaintAnalyzer().analyze(_COND_SANITIZE)
    assert len(flows) == 1
    assert flows[0].cwe_id == "CWE-89"
    # a linha do sink vem da CFG (line_start real), não do re-parse (=1).
    assert flows[0].sink_line >= 5


def test_T94_unconditional_sanitize_is_clean():
    # sanitização em TODOS os caminhos → taint morto → nenhum fluxo.
    assert CFGTaintAnalyzer().analyze(_UNCOND_SANITIZE) == []


def test_T94_int_cast_is_sanitizer():
    # `int(...)` é sanitizador forte (herdado do M7.2/CD) → não dispara.
    assert CFGTaintAnalyzer().analyze(_CAST_INT) == []


def test_T94_no_source_no_flow():
    assert CFGTaintAnalyzer().analyze(_NO_SOURCE) == []


def test_T94_parameterized_query_is_safe():
    # gating SQL arg[0] (M17/CD): o dado vai na tupla de params → seguro.
    assert CFGTaintAnalyzer().analyze(_PARAMETERIZED) == []


def test_T94_syntax_error_returns_empty_not_raises():
    # contrato "nunca levanta".
    assert CFGTaintAnalyzer().analyze("def (:::") == []


def test_T94_command_injection_via_os_system():
    code = '''
def h(request):
    cmd = request.args.get("cmd")
    os.system(cmd)
'''
    flows = CFGTaintAnalyzer().analyze(code)
    assert len(flows) >= 1
    assert flows[0].var == "cmd"
