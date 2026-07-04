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


def test_T78_cache_vary_guard():
    """CN v3.63.0: fix que adiciona `Vary: Cookie` (anti cache-poisoning) →
    kind 'cache-vary-guard' (CWE-525/539). Ex.: Flask CVE-2023-30861."""
    vuln = "def save(self, app, session, response):\n    response.set_cookie('s', 'x')\n"
    fixed = ("def save(self, app, session, response):\n"
             "    response.vary.add('Cookie')\n"
             "    response.set_cookie('s', 'x')\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="sessions.py")
    assert any(g.kind == "cache-vary-guard" for g in r.added_guards)


def test_T78_path_containment_guard():
    """CO v3.64.0: fix de path-traversal que adiciona `.relative_to(root)` para
    confinar o caminho normalizado à raiz → kind 'path-containment-guard'
    (CWE-22). Ex.: aiohttp CVE-2024-23334."""
    vuln = "def serve(self, filename):\n    filepath = self._directory.joinpath(filename)\n    return filepath\n"
    fixed = ("def serve(self, filename):\n"
             "    unresolved = self._directory.joinpath(filename)\n"
             "    normalized = Path(os.path.normpath(unresolved))\n"
             "    normalized.relative_to(self._directory)\n"
             "    return normalized.resolve()\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="web_urldispatcher.py")
    assert any(g.kind == "path-containment-guard" for g in r.added_guards)


def test_T78_path_containment_no_fp():
    """Anti-FP: um `.resolve()` sem containment não vira path-containment-guard."""
    vuln = "def f(p):\n    return p\n"
    fixed = "def f(p):\n    return p.resolve()\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="x.py")
    assert not any(g.kind == "path-containment-guard" for g in r.added_guards)


def test_T78_cache_vary_no_fp_plain_cookie():
    """Anti-FP: mexer em cookie SEM `vary` não vira cache-vary-guard."""
    vuln = "def f(r):\n    return r\n"
    fixed = "def f(r):\n    r.set_cookie('a', 'b')\n    return r\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="x.py")
    assert not any(g.kind == "cache-vary-guard" for g in r.added_guards)


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


# ── CT (v3.69.0): ReDoS por quantificador LIMITADO (setuptools CVE-2022-40897) ─
def test_T78_redos_bounded_quantifier():
    """2º padrão canônico de mitigação ReDoS: mantém o regex mas limita o
    quantificador (`\\s*` → `\\s{0,10}`). Dado REAL do fix do setuptools."""
    vuln = ('REL = re.compile(r"""<([^>]*\\srel\\s*=\\s*[\'"]?([^\'">]+)[^>]*)>""", re.I)\n')
    fixed = ('REL = re.compile(r"""<([^>]*\\srel\\s{0,10}=\\s{0,10}[\'"]?([^\'" >]+)[^>]*)>""", re.I)\n')
    r = FixDiffLocalizer().localize(vuln, fixed, filename="package_index.py")
    assert any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_redos_bounded_no_fp_on_plain_regex():
    """Anti-FP: adicionar um regex SEM limitar quantificador não é mitigação ReDoS."""
    vuln = "x = 1\n"
    fixed = "x = 1\nPAT = re.compile(r'\\d+')\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_redos_regex_simplification():
    """3º padrão ReDoS: SIMPLIFICA o regex removendo o segmento catastrófico
    (`\\s+.*\\s+`), mantendo uma chamada de regex. Dado REAL do Pygments
    CVE-2022-40896 (templates.py)."""
    vuln = ("        if re.search(\n"
            "            r'\\{%-?\\s*macro \\w+\\(.*\\)\\s*-?%\\}\\s+.*\\s+\\{%-?\\s*endmacro\\s*-?%\\}',\n"
            "            text, re.S):\n"
            "            return 0.1\n")
    fixed = ("        if re.search(r'\\{%-?\\s*macro \\w+\\(.*\\)\\s*-?%\\}', text):\n"
             "            return 0.1\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="templates.py")
    assert any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_redos_negated_class_multiline_regex():
    """ReDoS via classe negada num regex MULTI-LINHA (mako CVE-2022-40023):
    `".*?"` → `"[^"]*?"`. A linha do fix é corpo de padrão (sem `re.compile(`),
    então o predicado do padrão C aceita linha regex-ish (`(?:`/`[^`/`\\s`)."""
    vuln = ('    tag = re.compile(r"""\n'
            '            ((?:\\s+\\w+|\\s*=\\s*|".*?"|\'.*?\')*)  # attr\n'
            '        """, re.X)\n')
    fixed = ('    tag = re.compile(r"""\n'
             '            ((?:\\s+\\w+|\\s*=\\s*|"[^"]*?"|\'[^\']*?\'|\\s*,\\s*)*)  # attr\n'
             '        """, re.X)\n')
    r = FixDiffLocalizer().localize(vuln, fixed, filename="lexer.py")
    assert any(g.kind == "redos-mitigation" for g in r.added_guards)


def test_T78_security_guard_netloc_redirect_prefix():
    """security-conditional-guard casa `redirect_request_netloc` (redirect como
    PREFIXO, `_` é word-char) e `netloc` — scrapy CVE-2022-0577 (dropa Cookie em
    redirect cross-domain). O `\\bredirect\\b` antigo perdia `redirect_request`."""
    vuln = "def build(src):\n    return src.replace()\n"
    fixed = ("def build(src):\n"
             "    r = src.replace()\n"
             "    if source_netloc != redirect_request_netloc:\n"
             "        del r.headers['Cookie']\n"
             "    return r\n")
    res = FixDiffLocalizer().localize(vuln, fixed, filename="redirect.py")
    assert any(g.kind == "security-conditional-guard" for g in res.added_guards)


# ── CX (v3.73.0): XXE-hardening + trust embutido em snake_case ────────────────
def test_T78_xxe_hardening_resolve_entities():
    """Assinatura XXE nova (fonttools CVE-2023-45139): `resolve_entities=False`
    no XMLParser desabilita entidades externas → CWE-611."""
    vuln = "    parser = etree.XMLParser()\n"
    fixed = ("    parser = etree.XMLParser(\n"
             "        resolve_entities=False,  # anti-XXE\n"
             "    )\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="svg.py")
    assert any(g.kind == "xxe-hardening" for g in r.added_guards)


def test_T78_security_guard_trust_in_snake_case():
    """security-conditional-guard casa `check_host_trust` (host/trust embutidos
    em snake_case, sem fronteira) — werkzeug CVE-2024-34069 (debugger valida
    Host). O `\\bhost\\b` antigo perdia `check_host_trust`."""
    vuln = "def exec_cmd(self, request):\n    return run()\n"
    fixed = ("def exec_cmd(self, request):\n"
             "    if not self.check_host_trust(request.environ):\n"
             "        return SecurityError()\n"
             "    return run()\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="debug.py")
    assert any(g.kind == "security-conditional-guard" for g in r.added_guards)


# ── CY (v3.74.0): remoção de sink dinâmico perigoso (RCE via eval/exec) ───────
def test_T78_dangerous_sink_removed_eval():
    """Fixes de code-injection que REMOVEM `eval(...)` sem adicionar um guard
    reconhecível são localizados pela ausência do eval no fix (CWE-95/94)."""
    vuln = "def f(t, v):\n    return eval(t + '(' + v + ')')\n"
    fixed = "def f(t, v):\n    if t == 'int':\n        return int(v)\n    return v\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="cli.py")
    assert any(g.kind == "dangerous-sink-removed" for g in r.added_guards)


def test_T78_dangerous_sink_removed_no_fp_when_eval_stays():
    """Anti-FP: se o `eval` PERMANECE no fix (não foi removido), não dispara."""
    vuln = "def f(v):\n    return eval(v)\n"
    fixed = "def f(v):\n    log('x')\n    return eval(v)\n"  # eval continua
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind == "dangerous-sink-removed" for g in r.added_guards)


# ── DA (v3.76.0): ReDoS bounded em regex de CLASSE-DE-CARACTERE (sem backslash) ─
def test_T78_redos_bounded_char_class_regex():
    """ReDoS bounded num regex de char-class sem backslash (oauthlib
    CVE-2022-36087): `([A-Fa-f0-9:]+:+)+[A-Fa-f0-9]+` → `...[A-Fa-f0-9]{1,4}`.
    O `_REGEXISH_RE` relaxado passa a reconhecer `[...]`+quantificador."""
    vuln = 'IPv6 = r"([A-Fa-f0-9:]+:+)+[A-Fa-f0-9]+"\n'
    fixed = 'IPv6 = r"([A-Fa-f0-9:]+[:$])[A-Fa-f0-9]{1,4}"\n'
    r = FixDiffLocalizer().localize(vuln, fixed, filename="uri_validate.py")
    assert any(g.kind == "redos-mitigation" for g in r.added_guards)


# ── DB (v3.77.0): terminação de laço contra loop infinito (CWE-835) ───────────
def test_T78_loop_termination_guard():
    """Fix de loop infinito que adiciona terminador vazio/EOF a `while ... not in`
    (pypdf CVE-2023-36464): `(b"\\r", b"\\n")` → `(b"\\r", b"\\n", b"")`."""
    vuln = 'def f(s):\n    while peek not in (b"\\r", b"\\n"):\n        peek = s.read(1)\n'
    fixed = 'def f(s):\n    while peek not in (b"\\r", b"\\n", b""):\n        peek = s.read(1)\n'
    r = FixDiffLocalizer().localize(vuln, fixed, filename="_data_structures.py")
    assert any(g.kind == "loop-termination-guard" for g in r.added_guards)


# ── DD (v3.79.0): input-validation-raise reconhece `raise Invalid...` ─────────
def test_T78_input_validation_raise_invalid_exception():
    """`raise InvalidHeader(...)` (gunicorn CVE-2024-1135) — exceção que NÃO
    termina em Error/Exception mas começa com Invalid → é validação."""
    vuln = "def set_body(self):\n    self.chunked = True\n"
    fixed = ("def set_body(self):\n"
             "    if chunked:\n"
             "        raise InvalidHeader('TRANSFER-ENCODING', req=self)\n"
             "    self.chunked = True\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="message.py")
    assert any(g.kind == "input-validation-raise" for g in r.added_guards)


# ── DE (v3.80.0): path-containment via os.path.commonprefix ───────────────────
def test_T78_path_containment_commonprefix():
    """streamlit CVE-2022-35918: contenção de path via `os.path.commonprefix`
    (antes só reconhecíamos commonpath/relative_to)."""
    vuln = "def get(self, filename):\n    self.serve(filename)\n"
    fixed = ("def get(self, filename):\n"
             "    abspath = os.path.realpath(os.path.join(root, filename))\n"
             "    if os.path.commonprefix([root, abspath]) != root:\n"
             "        self.set_status(403)\n"
             "        return\n"
             "    self.serve(filename)\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="components.py")
    assert any(g.kind == "path-containment-guard" for g in r.added_guards)


# ── DF (v3.81.0): input-validation-raise reconhece `raise Bad...` ─────────────
def test_T78_input_validation_raise_bad_exception():
    """`raise BadRequest(...)`/`raise BadHttpMessage(...)` — exceções de validação
    que começam com Bad (comuns em parsers HTTP)."""
    vuln = "def h(r):\n    return process(r)\n"
    fixed = ("def h(r):\n"
             "    if b'\\n' in r.ext:\n"
             "        raise BadRequest('bad chunk')\n"
             "    return process(r)\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="parser.py")
    assert any(g.kind == "input-validation-raise" for g in r.added_guards)


# ── DH (v3.83.0): output-encoding reconhece o alias html_escape ───────────────
def test_T78_output_encoding_html_escape_alias():
    """aiohttp CVE-2024-27306: escape via alias `html_escape(name)` (partial de
    html.escape) — antes só `html.escape(`/`escape(` diretos."""
    vuln = "def index(files):\n    return ''.join(f'<a>{n}</a>' for n in files)\n"
    fixed = ("def index(files):\n"
             "    return ''.join(f'<a>{html_escape(n)}</a>' for n in files)\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="web_urldispatcher.py")
    assert any(g.kind == "output-encoding" for g in r.added_guards)


# ── DI (v3.84.0): path-containment via os.path.samefile ───────────────────────
def test_T78_path_containment_samefile():
    """pymdown-extensions CVE-2023-32309: contenção via `os.path.samefile(base,
    dirname(abspath))` (antes só commonpath/commonprefix/relative_to)."""
    vuln = "def get(base, path):\n    return open(os.path.join(base, path)).read()\n"
    fixed = ("def get(base, path):\n"
             "    filename = os.path.abspath(os.path.join(base, path))\n"
             "    if not os.path.samefile(base, os.path.dirname(filename)):\n"
             "        continue\n"
             "    return open(filename).read()\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="snippets.py")
    assert any(g.kind == "path-containment-guard" for g in r.added_guards)


# ── DK (v3.86.0): M31 sinais diff-semânticos (default-flip + raise-indirect) ──
def test_T78_m31_security_default_flip():
    """bleach CVE-2020-6802: kwarg de segurança `scripting=False→True` (flip)."""
    vuln = "def _parse(self, stream, scripting=False, **kw):\n    return go(stream)\n"
    fixed = "def _parse(self, stream, scripting=True, **kw):\n    return go(stream)\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="html5lib_shim.py")
    assert any(g.kind == "security-default-flip" for g in r.added_guards)

def test_T78_m31_default_flip_no_fp_on_nonsecurity_kwarg():
    """Anti-FP: kwarg NÃO-segurança (`verbose=False→True`) não dispara."""
    vuln = "def f(verbose=False):\n    pass\n"
    fixed = "def f(verbose=True):\n    pass\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind == "security-default-flip" for g in r.added_guards)

def test_T78_m31_raise_indirect():
    """aiohttp CVE-2024-52304: erro construído numa var + `raise exc`."""
    vuln = "def parse(self, ext):\n    return process(ext)\n"
    fixed = ("def parse(self, ext):\n"
             "    if b'\\n' in ext:\n"
             "        exc = BadHttpMessage('bad chunk-ext')\n"
             "        set_exception(self.payload, exc)\n"
             "        raise exc\n"
             "    return process(ext)\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="http_parser.py")
    assert any(g.kind == "raise-indirect" for g in r.added_guards)


# ── DL (v3.87.0): M29 detector de RACE (close-state guard) ────────────────────
def test_T78_m29_race_close_guard():
    """waitress CVE-2024-49768: fix adiciona guard de close-state dentro da seção
    crítica (`if will_close or close_when_flushed: return False`) — CWE-362."""
    vuln = "def received(self, data):\n    self.process(data)\n    return True\n"
    fixed = ("def received(self, data):\n"
             "    with self.requests_lock:\n"
             "        if self.will_close or self.close_when_flushed:\n"
             "            return False\n"
             "    self.process(data)\n    return True\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="channel.py")
    # M29 detecta o race por lock-novo+estado OU close-guard (ambos CWE-362)
    assert any(g.kind in ("race-close-guard", "race-lock-guard") for g in r.added_guards)

def test_T78_m29_no_fp_on_plain_if():
    """Anti-FP: um `if` comum sem termo de ciclo-de-vida de conexão não dispara."""
    vuln = "def f(x):\n    return x\n"
    fixed = "def f(x):\n    if x > 0:\n        return x\n    return 0\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind in ("race-close-guard", "race-lock-guard") for g in r.added_guards)


# ── DM (v3.88.0): M31b decode-before-validate ────────────────────────────────
def test_T78_m31b_decode_before_validate():
    """mlflow CVE-2023-6909: `unquote(path)` adicionado em contexto de validação
    de path (função tem checks de `..`) → decode-before-validate (CWE-29)."""
    vuln = "def validate_path_is_safe(path):\n    if '..' in path:\n        raise ValueError('bad')\n"
    fixed = ("def validate_path_is_safe(path):\n"
             "    path = urllib.parse.unquote(path)\n"
             "    if '..' in path:\n        raise ValueError('bad')\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="uri.py")
    assert any(g.kind == "decode-before-validate" for g in r.added_guards)

def test_T78_m31b_no_fp_unquote_without_path_ctx():
    """Anti-FP: `unquote` SEM contexto de validação de path não dispara."""
    vuln = "def f(q):\n    return q\n"
    fixed = "def f(q):\n    q = urllib.parse.unquote(q)\n    return q.upper()\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind == "decode-before-validate" for g in r.added_guards)


# ── DP (v3.91.0): abspath-reject (rejeição de path absoluto em contexto de path) ─
def test_T78_abspath_reject():
    """werkzeug CVE-2024-49766: `or filename.startswith('/')` no safe_join."""
    vuln = "def safe_join(directory, filename):\n    if os.path.isabs(filename):\n        return None\n    return join(directory, filename)\n"
    fixed = ("def safe_join(directory, filename):\n"
             "    if os.path.isabs(filename) or filename.startswith('/'):\n"
             "        return None\n    return join(directory, filename)\n")
    r = FixDiffLocalizer().localize(vuln, fixed, filename="security.py")
    assert any(g.kind == "abspath-reject" for g in r.added_guards)

def test_T78_abspath_reject_no_fp_without_path_ctx():
    """Anti-FP: `startswith('/')` FORA de contexto de path não dispara."""
    vuln = "def f(s):\n    return s\n"
    fixed = "def f(s):\n    if s.startswith('/'):\n        s = s[1:]\n    return s\n"
    r = FixDiffLocalizer().localize(vuln, fixed, filename="m.py")
    assert not any(g.kind == "abspath-reject" for g in r.added_guards)
