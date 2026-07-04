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


# ── CE (v3.54.0): dois canais reais que o M10 captava mas não processava ──────
# Diagnóstico dos not_tracked do corpus: o sinal existia no diff, mas (1) uma
# chamada a helper de bounds-check em CamelCase escapava do gate/assinaturas e
# (2) o filtro anti-relocação por PRESENÇA descartava um early-return genuíno
# só porque o mesmo idioma existia noutro ponto do arquivo.  Ambos corrigidos.

def test_T78_bounds_check_call_camelcase():
    """postgres CVE-2021-32027: fix insere `ArrayCheckBounds(...)` (CamelCase).
    A regra overflow-guard (`\\bbounds`) perdia por causa do `\\b` no meio do
    identificador; a nova `bounds-check-call` casa a forma-de-chamada."""
    vuln = ("ArrayType *construct(int ndim, int *dim) {\n"
            "    nitems = ArrayGetNItems(ndim, dim);\n"
            "    return build(ndim, dim, nitems);\n}\n")
    fixed = ("ArrayType *construct(int ndim, int *dim) {\n"
             "    nitems = ArrayGetNItems(ndim, dim);\n"
             "    ArrayCheckBounds(ndim, dim, lBound);\n"
             "    return build(ndim, dim, nitems);\n}\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="arrayfuncs.c")
    assert any(g.kind == "bounds-check-call" for g in r.added_guards)
    assert r.guard_present_in_fix_absent_in_vuln


def test_T78_early_return_not_dropped_when_idiom_repeats():
    """ffmpeg CVE-2020-22015: o fix adiciona `return AVERROR(EINVAL);` como
    guard de range antes de `1 << bits`.  O idioma já existe noutro ponto do
    arquivo — o filtro por CONTAGEM (fix=2 > vuln=1) o mantém; o antigo filtro
    por presença o descartava."""
    vuln = ("int a(int x){ if(x) return AVERROR(EINVAL); return 0; }\n"
            "int b(int bits){\n"
            "    int pal = 1 << bits;\n"
            "    return pal;\n}\n")
    fixed = ("int a(int x){ if(x) return AVERROR(EINVAL); return 0; }\n"
             "int b(int bits){\n"
             "    if (bits < 0 || bits > 8)\n"
             "        return AVERROR(EINVAL);\n"
             "    int pal = 1 << bits;\n"
             "    return pal;\n}\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="movenc.c")
    assert any(g.kind == "early-return-guard" for g in r.added_guards)


def test_T78_redos_mitigation_regex_to_string():
    """CL v3.61.0: fix de ReDoS que REMOVE regex propensa a backtracking e
    ADICIONA parsing por string → kind 'redos-mitigation' (canal na REMOÇÃO que
    as assinaturas de guard-adicionado perdiam). Ex.: urllib3 CVE-2021-33503."""
    vuln = ("SUBAUTHORITY_RE = re.compile(PAT, re.UNICODE)\n"
            "def split(authority):\n"
            "    auth, host, port = SUBAUTHORITY_RE.match(authority).groups()\n"
            "    return host\n")
    fixed = ("def split(authority):\n"
             "    auth, _, host_port = authority.rpartition('@')\n"
             "    return host_port\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="url.py")
    assert any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_redos_no_fp_without_regex_removal():
    """Anti-FP: adicionar um `.split()` SEM remover regex não vira redos-mitigation."""
    vuln = "def f(s):\n    return s\n"
    fixed = "def f(s):\n    a, b = s.partition('@')[::2]\n    return a\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="x.py")
    assert not any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_relocation_still_filtered_by_count():
    """Anti-FP preservado: uma linha só RELOCADA (contagem constante 1→1) NÃO
    conta como guard adicionado (sqlite CVE-2019-19646 — o clamp relocado)."""
    clamp = "colUsed |= 1 << (iCol>=BMS ? BMS-1 : iCol);"
    vuln = f"void f(){{\n    a();\n    {clamp}\n}}\n"
    fixed = f"void f(){{\n    a();\n    b();\n    {clamp}\n}}\n"  # clamp só desce 1 linha
    r = FixDiffLocalizer().localize(vuln, fixed, filename="resolve.c")
    # o clamp relocado não deve aparecer como guard adicionado
    assert all(clamp not in g.text for g in r.added_guards)
