"""
Marco 78 — M10: FixDiffLocalizer — localização de vulnerabilidade por diff
==========================================================================
Sprint BG estabeleceu empiricamente que o SAST de padrão do sensor NÃO
dispara nas classes de CVE de memory-safety (o rating fica A na versão
vulnerável, ou uma regra genérica dispara e PERSISTE idêntica no fix) — logo
não sabe dizer "disparou antes / parou depois". O `FixDiffLocalizer` (M10)
resolve a validação de CVE-conhecida ancorando no diff do fix: extrai a
construção de segurança ADICIONADA (bounds-check, null-guard, type-widening,
early-return) com a LINHA exata, e valida presente-no-fix / ausente-no-vuln.

As fixtures abaixo reproduzem, offline, o padrão REAL do fix de
CVE-2019-11043 (php/php-src, `sapi/fpm/fpm/fpm_main.c`): o vulnerável faz
`env_path_info + pilen - slen` sem checar `pilen > slen` (underflow → OOB);
o fix adiciona `(env_path_info && pilen > slen) ? ... : NULL`.
"""
from __future__ import annotations

from sast.fix_localizer import FixDiffLocalizer, LocalizeResult, GuardHit

_VULN = """\
static void init_request_info(void)
{
    if (env_path_info) {
        path_info = env_path_info + pilen - slen;
        tflag = (orig_path_info != path_info);
    }
}
"""

_FIXED = """\
static void init_request_info(void)
{
    if (env_path_info) {
        path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;
        tflag = path_info && (orig_path_info != path_info);
    }
}
"""


def test_T78_localizes_added_bounds_check_with_line():
    loc = FixDiffLocalizer()
    r = loc.localize(_VULN, _FIXED, filename="fpm_main.c")
    assert isinstance(r, LocalizeResult)
    # o fix adicionou pelo menos o bounds-check `pilen > slen`
    assert r.guard_present_in_fix_absent_in_vuln is True
    kinds = {g.kind for g in r.added_guards}
    assert "bounds-check-ternary" in kinds or "null-guard" in kinds
    # linha exata reportada (dentro do arquivo corrigido)
    g = r.first_guard
    assert g is not None and g.line >= 1
    assert "CWE" in g.cwe_class or "RUST" in g.cwe_class


def test_T78_identical_source_no_guard():
    loc = FixDiffLocalizer()
    r = loc.localize(_VULN, _VULN, filename="x.c")
    assert r.guard_present_in_fix_absent_in_vuln is False
    assert r.added_guards == []


def test_T78_comment_only_change_is_not_a_guard():
    a = "int f(int n){ return n+1; }\n"
    b = "int f(int n){ /* faster now */ return n+1; }\n"
    r = FixDiffLocalizer().localize(a, b, filename="c.c")
    # mudança de comentário não é guard de segurança
    assert r.guard_present_in_fix_absent_in_vuln is False


def test_T78_type_widening_detected():
    a = "unsigned char index;\nfor (index=0; index<len; index++) buf[index]=0;\n"
    b = "size_t index;\nfor (index=0; index<len; index++) buf[index]=0;\n"
    r = FixDiffLocalizer().localize(a, b, filename="w.c")
    assert any(g.kind == "type-widening" for g in r.added_guards)


def test_T78_summary_is_localized_and_human():
    r = FixDiffLocalizer().localize(_VULN, _FIXED, filename="fpm_main.c")
    s = r.summary()
    assert "fpm_main.c" in s and "L" in s


# ── BZ+ (v3.50.0): guard relocado NÃO conta como adição de segurança ──────────
def test_T78_relocated_guard_is_not_counted_as_new():
    """
    Se o fix apenas DESLOCA (por inserir linhas acima) um guard que já existia
    no vulnerável, o difflib o vê como 'insert' — mas NÃO é uma correção nova.
    O localizador deve ignorá-lo (anti-FP de relocação). Reproduz o padrão real
    do sqlite CVE-2019-19646 (clamp `iCol>=BMS ? BMS-1 : iCol` presente em ambos).
    """
    guard = "colUsed |= (1)<<(iCol>=BMS ? BMS-1 : iCol);"
    vuln = f"void f(){{\n  {guard}\n}}\n"
    # fix só adiciona um comentário ACIMA — o guard fica relocado, não novo:
    fixed = f"void f(){{\n  /* nota */\n  {guard}\n}}\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="s.c")
    assert r.guard_present_in_fix_absent_in_vuln is False   # relocação, não correção


# ── CB (v3.51.0): M10 localiza fixes de injeção/escaping (não só memory-safety) ─
def test_T78_localizes_output_encoding_fix():
    """Fix que adiciona escape() em saída → localizado como output-encoding (XSS)."""
    vuln = 'def render(k, v):\n    items.append(f\'{k}="{escape(v)}"\')\n'
    fixed = 'def render(k, v):\n    items.append(f\'{escape(k)}="{escape(v)}"\')\n'
    r = FixDiffLocalizer().localize(vuln, fixed, filename="filters.py")
    assert r.guard_present_in_fix_absent_in_vuln is True
    assert any(g.kind == "output-encoding" for g in r.added_guards)


def test_T78_localizes_input_validation_raise():
    """Fix que adiciona `raise ValueError` sobre entrada perigosa → validação."""
    vuln = 'def attr(key):\n    return key\n'
    fixed = ('def attr(key):\n'
             '    if _space_re.search(key) is not None:\n'
             '        raise ValueError("Spaces not allowed")\n'
             '    return key\n')
    r = FixDiffLocalizer().localize(vuln, fixed, filename="filters.py")
    assert any(g.kind == "input-validation-raise" for g in r.added_guards)


# ── CC (v3.52.0): guard condicional de segurança (and/or) e limite de recurso ──
def test_T78_python_conditional_security_guard():
    """`if ... and ...` com termo sensível (scheme/password) — guard que o C-only perdia."""
    vuln = "def rebuild(proxies, u, p):\n    proxies['Proxy-Authorization'] = basic(u, p)\n"
    fixed = ("def rebuild(proxies, u, p):\n"
             "    if not scheme.startswith('https') and u and p:\n"
             "        del proxies['Proxy-Authorization']\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="sessions.py")
    assert any(g.kind == "security-conditional-guard" for g in r.added_guards)


def test_T78_resource_limit_dos_guard():
    """Introdução de limite de recurso (max_form_parts) → classe DoS/CWE-400."""
    vuln = "def parse(stream):\n    return list(iter_parts(stream))\n"
    fixed = ("def parse(stream, max_form_parts=1000):\n"
             "    self.max_form_parts = max_form_parts\n"
             "    return list(iter_parts(stream, max_parts=max_form_parts))\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="formparser.py")
    assert any(g.kind == "resource-limit" for g in r.added_guards)
