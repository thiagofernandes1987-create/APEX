"""
Marco 89 — META B: M11 guard-aware language-aware (C/C++/Rust)
=============================================================
As classes de memory-safety (GA01 underflow em subtração, GA02 memcpy sem
bound) só têm sentido em linguagens com aritmética unsigned/ponteiro e sem
bounds-check de runtime: C, C++, Rust (wraparound em release). Em Go/Java
(int signed + arrays bounds-checked) ou JS (floats), o `a - b` NÃO é
memory-unsafe → disparar seria FALSO-POSITIVO. Sprint BT torna o M11
language-aware: dispara nas memory-unsafe, silencia nas managed.
"""
from __future__ import annotations

from sast.guard_aware import GuardAwareScanner

_SUB = "{ p = base + a - b; }"  # padrão universal de subtração


def _ga01(src: str, ext: str):
    return [g for g in GuardAwareScanner().scan(src, ext) if g.rule_id == "GA01"]


def test_T89_fires_on_memory_unsafe_langs():
    for ext in (".c", ".cpp", ".cc", ".rs"):
        src = f"int f(char* base,int a,int b) {_SUB}"
        assert _ga01(src, ext), f"deveria disparar em {ext}"


def test_T89_silent_on_managed_langs():
    # Go/Java/JS: a subtração não é memory-unsafe → não dispara (sem FP)
    for ext in (".go", ".java", ".js", ".ts", ".py"):
        src = f"function f(base,a,b) {_SUB}"
        assert _ga01(src, ext) == [], f"NÃO deveria disparar em {ext}"


def test_T89_rust_is_supported():
    src = "fn f(base:usize,a:usize,b:usize)->usize{ let p = base + a - b; p }"
    finds = _ga01(src, ".rs")
    assert len(finds) == 1
    assert finds[0].needs_guard_on == ("a", "b")


def test_T89_c_still_works_regression():
    src = "int f(char* base,int pilen,int slen){ char* p = base + pilen - slen; return *p; }"
    finds = _ga01(src, ".c")
    assert finds and finds[0].needs_guard_on == ("pilen", "slen")


def test_T89_ga02_allocated_to_fit_is_not_flagged():
    """Sprint CA: memcpy cujo comprimento foi usado para dimensionar o buffer
    (idioma allocated-to-fit) NÃO deve disparar GA02 — era FP real (php-src
    L1666/L1672: realloc(..., off + len + ...) antes de memcpy(..., ..., len))."""
    from sast.guard_aware import GuardAwareScanner
    safe = (
        "void f(char *src, int off, int len) {\n"
        "    buf = erealloc(buf, off + len + 2);\n"
        "    memcpy(buf + off, src, len);\n"
        "}\n"
    )
    findings = GuardAwareScanner().scan(safe, ".c")
    assert not any(g.rule_id == "GA02" for g in findings)


def test_T89_ga02_unbounded_still_flags():
    """Contraprova: memcpy com length sem bound nem alloc-to-fit ainda dispara."""
    from sast.guard_aware import GuardAwareScanner
    vuln = (
        "void f(char *dst, char *src, int len) {\n"
        "    memcpy(dst, src, len);\n"
        "}\n"
    )
    findings = GuardAwareScanner().scan(vuln, ".c")
    assert any(g.rule_id == "GA02" for g in findings)
