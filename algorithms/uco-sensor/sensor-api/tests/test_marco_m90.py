"""
Marco 90 — M20: Taint-Lite multi-linguagem (PHP + JS/TS) [META B restante]
==========================================================================
Estende a detecção de injeção sem-âncora para PHP e JavaScript/TypeScript —
linguagens web do corpus que o TaintAnalyzer (AST-Python) não cobria. Fluxo
fonte→sink por escopo de função (M14), FP-controlado (exige a mesma variável
ou fonte direta; parâmetro sem fonte NÃO dispara).
"""
from __future__ import annotations

from sast.taint_lite import TaintLite


def _scan(src: str, ext: str):
    return TaintLite().scan(src, ext)


def test_T90_php_command_injection_via_var():
    src = "<?php\nfunction h(){\n  $c = $_GET['cmd'];\n  system($c);\n}"
    f = _scan(src, ".php")
    assert len(f) == 1
    assert f[0].vuln_type == "COMMAND_INJECTION"
    assert f[0].var == "$c"


def test_T90_php_direct_source_in_sink():
    src = "<?php\nfunction h(){ system($_GET['cmd']); }"
    f = _scan(src, ".php")
    assert f and f[0].vuln_type == "COMMAND_INJECTION"


def test_T90_php_unserialize_is_deserialization():
    src = "<?php\nfunction h(){ $d = $_POST['d']; unserialize($d); }"
    f = _scan(src, ".php")
    assert f and f[0].vuln_type == "UNSAFE_DESERIALIZATION"


def test_T90_php_param_without_source_is_clean():
    # sem fonte de usuário → não dispara (sem FP)
    src = "<?php\nfunction h($c){ system(escapeshellarg($c)); }"
    assert _scan(src, ".php") == []


def test_T90_js_eval_injection():
    src = "function h(req){ let x = req.query.code; eval(x); }"
    f = _scan(src, ".js")
    assert f and f[0].vuln_type == "CODE_INJECTION"


def test_T90_js_safe_is_clean():
    src = "function h(req){ let x = req.query.code; console.log(x); }"
    assert _scan(src, ".js") == []


def test_T90_unsupported_ext_returns_empty():
    assert _scan("whatever", ".c") == []
    assert _scan("whatever", ".py") == []
