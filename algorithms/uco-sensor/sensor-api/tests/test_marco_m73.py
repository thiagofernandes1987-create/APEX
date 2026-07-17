"""
Marco 73 — JS12: comando-injeção via `_.template`'s `variable` option (lodash)
================================================================================

Correção de uma mischaracterization documentada nesta própria base
(``AF_consolidated_timeline.md`` linha lodash, task #63 "JS12 ReDoS
literal"): CVE-2021-23337 (GHSA-35jh-r3h4-6jhm, lodash) NÃO é ReDoS — é
CWE-94 (command injection). O fix real (sha vulnerável
``ded9bc66583ed0b4e3b7dc906206d40757b4a90a``, fix
``3469357cff396a26c363f8c1b5a91dde28ba4b1c``, "Prevent command injection
through `_.template`'s `variable` option") adiciona uma checagem
``reForbiddenIdentifierChars.test(variable)`` antes que a opção externa
`variable` seja concatenada em
``'function(' + (variable || 'obj') + ') {\\n' + ...`` — string que
acaba sendo compilada via `Function(...)`. Sem essa validação, um
atacante que controla `variable` escapa da lista de parâmetros e injeta
código arbitrário no corpo da função gerada.

JS12 detecta o shape (whole-file, mesma técnica de CS06/C05): captura o
nome da variável atribuída a partir de
``hasOwnProperty.call(options, 'variable') && options.variable`` e
verifica a ausência de qualquer ``.test(<mesmo nome>)`` no arquivo
inteiro antes do ponto onde essa variável é concatenada em
``'function(' + ...``. Validado contra o `lodash.js` real nos dois SHAs
(scratch desta sessão): dispara 1x na versão vulnerável, silencioso na
corrigida.
"""
from __future__ import annotations

from sast.multilang_scanner import scan_multilang


def _scan_ids(src: str) -> list:
    res = scan_multilang(src, file_extension=".js")
    return [f.rule_id for f in res.findings]


_VULN_TEMPLATE_SNIPPET = (
    "function template(string, options, guard) {\n"
    "  var variable = hasOwnProperty.call(options, 'variable') && options.variable;\n"
    "  if (!variable) {\n"
    "    source = 'with (obj) {\\n' + source + '\\n}\\n';\n"
    "  }\n"
    "  source = 'function(' + (variable || 'obj') + ') {\\n' +\n"
    "    (variable\n"
    "      ? ''\n"
    "      : 'obj || (obj = {});\\n'\n"
    "    ) +\n"
    "    \"var __t, __p = ''\" +\n"
    "    ';\\n  return __p\\n}';\n"
    "  var result = attempt(function() {\n"
    "    return Function(...);\n"
    "  });\n"
    "  return result;\n"
    "}\n"
)

_FIXED_TEMPLATE_SNIPPET = (
    "function template(string, options, guard) {\n"
    "  var reForbiddenIdentifierChars = /[()=,{}\\[\\]\\/\\s]/;\n"
    "  var variable = hasOwnProperty.call(options, 'variable') && options.variable;\n"
    "  if (!variable) {\n"
    "    source = 'with (obj) {\\n' + source + '\\n}\\n';\n"
    "  }\n"
    "  else if (reForbiddenIdentifierChars.test(variable)) {\n"
    "    throw new Error(INVALID_TEMPL_VAR_ERROR_TEXT);\n"
    "  }\n"
    "  source = 'function(' + (variable || 'obj') + ') {\\n' +\n"
    "    (variable\n"
    "      ? ''\n"
    "      : 'obj || (obj = {});\\n'\n"
    "    ) +\n"
    "    \"var __t, __p = ''\" +\n"
    "    ';\\n  return __p\\n}';\n"
    "  var result = attempt(function() {\n"
    "    return Function(...);\n"
    "  });\n"
    "  return result;\n"
    "}\n"
)


def test_TAO01_js12_fires_on_real_vulnerable_template_shape():
    assert "JS12" in _scan_ids(_VULN_TEMPLATE_SNIPPET)


def test_TAO02_js12_silent_on_real_fixed_template_shape():
    assert "JS12" not in _scan_ids(_FIXED_TEMPLATE_SNIPPET)


def test_TAO03_js12_silent_without_variable_option_assignment():
    src = (
        "function template(string, options, guard) {\n"
        "  source = 'function(obj) {\\n' + body + '\\n}';\n"
        "  return Function('obj', source);\n"
        "}\n"
    )
    assert "JS12" not in _scan_ids(src)


def test_TAO04_js12_silent_when_validation_guards_a_different_named_variable():
    """Guard must reference the SAME captured variable name, not an unrelated one."""
    src = (
        "function template(string, options, guard) {\n"
        "  var variable = hasOwnProperty.call(options, 'variable') && options.variable;\n"
        "  var other = options.other;\n"
        "  if (reSomethingElse.test(other)) {\n"
        "    throw new Error('bad');\n"
        "  }\n"
        "  source = 'function(' + (variable || 'obj') + ') {\\n' + body;\n"
        "  return Function(variable, source);\n"
        "}\n"
    )
    assert "JS12" in _scan_ids(src)


def test_TAO05_js12_silent_on_unrelated_function_string_concat():
    src = (
        "function buildLabel(name) {\n"
        "  return 'function(' + name + ') {}';\n"
        "}\n"
    )
    assert "JS12" not in _scan_ids(src)
