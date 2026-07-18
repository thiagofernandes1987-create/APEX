"""
Marco 79 — M11: Guard-Aware Memory-Safety Scanner — dispara no vuln, para no fix
================================================================================
M11 é a primeira detecção REAL (sem âncora no commit de fix) de uma classe de
CVE de memory-safety que a Sprint BG mostrou que o SAST de padrão não pegava.
A regra é *guard-aware*: uma subtração em aritmética de ponteiro/comprimento
(`base + a - b`) só é reportada quando NÃO há guard `a > b` no escopo local.
O fix da CVE, que adiciona o guard, faz a regra PARAR de disparar — o
before/after fiel.

Fixtures reproduzem, offline, o padrão REAL de php/php-src CVE-2019-11043
(`sapi/fpm/fpm/fpm_main.c`), validado ao vivo na Sprint BH: GA01 dispara na
linha `env_path_info + pilen - slen` da versão vulnerável e silencia na
corrigida `(env_path_info && pilen > slen) ? ...`.
"""
from __future__ import annotations

from sast.guard_aware import GuardAwareScanner, GuardFinding

_VULN = """\
static void init_request_info(void)
{
    char *path_info;
    if (env_path_info) {
        path_info = env_path_info + pilen - slen;
        tflag = (orig_path_info != path_info);
    }
}
"""

_FIXED = """\
static void init_request_info(void)
{
    char *path_info;
    if (env_path_info) {
        path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;
        tflag = path_info && (orig_path_info != path_info);
    }
}
"""


def _ga01(findings):
    return [f for f in findings if f.rule_id == "GA01" and f.needs_guard_on == ("pilen", "slen")]


def test_T79_fires_on_vulnerable_unguarded_subtraction():
    findings = GuardAwareScanner().scan(_VULN, ".c")
    hits = _ga01(findings)
    assert len(hits) == 1
    assert hits[0].cwe_id == "CWE-191"
    assert hits[0].line >= 1
    assert "pilen" in hits[0].explanation and "slen" in hits[0].explanation


def test_T79_silent_on_fixed_with_guard():
    findings = GuardAwareScanner().scan(_FIXED, ".c")
    # o guard `pilen > slen` no escopo suprime GA01 para (pilen,slen)
    assert _ga01(findings) == []


def test_T79_before_after_delta_is_the_cve_line():
    v = _ga01(GuardAwareScanner().scan(_VULN, ".c"))
    f = _ga01(GuardAwareScanner().scan(_FIXED, ".c"))
    # disparou (1) e parou (0) — a evidência before/after da correção
    assert len(v) == 1 and len(f) == 0


def test_T79_ga02_unbounded_memcpy():
    src = "void f(char*d,char*s,int n){\n memcpy(d, s, n);\n}\n"
    findings = GuardAwareScanner().scan(src, ".c")
    assert any(g.rule_id == "GA02" and g.needs_guard_on == ("n",) for g in findings)


def test_T79_ga02_bounded_memcpy_is_silent():
    src = "void f(char*d,char*s,int n){\n if (n < 256) memcpy(d, s, n);\n}\n"
    findings = GuardAwareScanner().scan(src, ".c")
    assert not any(g.rule_id == "GA02" for g in findings)


def test_T79_returns_guardfinding_dataclass():
    findings = GuardAwareScanner().scan(_VULN, ".c")
    assert all(isinstance(f, GuardFinding) for f in findings)


# ── DT/Achado #4: dominância — bound de branch irmão NÃO conta ────────────────

def test_T79_ga02_unrelated_bound_in_sibling_branch_still_fires():
    # `len < 999999` num branch de debug que FECHA antes do memcpy não protege.
    src = (
        "void f(char *dst, char *src, int len, int debug_mode) {\n"
        '  if (debug_mode) { if (len < 999999) { log_debug("x"); } }\n'
        "  memcpy(dst, src, len);\n"
        "}\n"
    )
    findings = GuardAwareScanner().scan(src, ".c")
    assert any(g.rule_id == "GA02" and g.needs_guard_on == ("len",) for g in findings)


def test_T79_ga02_dominating_early_return_guard_is_silent():
    # guard que DOMINA o sink (early-return no mesmo nível) suprime corretamente.
    for body in ("if (len > size) return;", "if (len > size) { return; }"):
        src = (
            "void g(char *dst, char *src, int len, int size) {\n"
            f"  {body}\n"
            "  memcpy(dst, src, len);\n"
            "}\n"
        )
        assert not any(g.rule_id == "GA02" for g in GuardAwareScanner().scan(src, ".c")), body


def test_T79_ga01_unrelated_guard_in_sibling_branch_still_fires():
    src = (
        "void f(char *base, int pilen, int slen, int dbg) {\n"
        "  if (dbg) { if (pilen > slen) { note(); } }\n"
        "  char *p = base + pilen - slen;\n"
        "}\n"
    )
    hits = [f for f in GuardAwareScanner().scan(src, ".c")
            if f.rule_id == "GA01" and f.needs_guard_on == ("pilen", "slen")]
    assert len(hits) == 1
