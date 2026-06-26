"""
Marco 64 — Sprint AD: cross-ecosystem CVE diff + RustAdapter lifetime fix (TAD01-TAD08)
=========================================================================================

Sprint AD extended the AC-3 before/after CVE methodology to a representative
sample outside Python (curl/C, golang/go, axios/axios JS, spring-framework
Java, rust-lang/regex Rust). All 5 cases were genuine blind spots (no SAST
or metric-channel signal) — expected, since SAST046/047 are Python-AST
specific.

While investigating the rust-lang/regex CVE-2022-24713 case, a real bug was
found in ``lang_adapters/rust.py``'s ``STRING_RE``: the char-literal branch
used an unbounded ``*`` quantifier, so a bare lifetime/generic apostrophe
(``'a``, ``'static``, ``<'a>``) — which has no closing quote — would start a
"char literal" match that swallowed everything up to the next unrelated
quote anywhere in the file (confirmed: it merged a string literal and
several statements into one bogus "char literal" in a 1-line repro). This
caused cyclomatic_complexity to swing from 45 to 102 between two
near-identical regex crate snapshots, a pure measurement artifact with no
relation to the actual 17-line CVE fix. Fixed by bounding the char-literal
alternative to exactly one char/escape. This module pins the fix.
"""
from __future__ import annotations

from lang_adapters.rust import RustAdapter


def _clean(src: str) -> str:
    return RustAdapter()._strip(src)


def test_TAD01_lifetime_apostrophe_not_treated_as_string_start():
    src = "fn f<'a>(z: &'a i32) {}"
    assert _clean(src) == src


def test_TAD02_static_lifetime_not_treated_as_string_start():
    src = "let x: &'static str = \"hi\";"
    cleaned = _clean(src)
    assert "&'static str" in cleaned
    assert '""' in cleaned


def test_TAD03_real_char_literal_still_stripped():
    src = "let y = 'a';"
    assert _clean(src) == 'let y = "";'


def test_TAD04_escaped_char_literal_still_stripped():
    src = "let nl = '\\n';"
    assert _clean(src) == 'let nl = "";'


def test_TAD05_unicode_escape_char_literal_still_stripped():
    src = "let emoji = '\\u{1F600}';"
    assert _clean(src) == 'let emoji = "";'


def test_TAD06_lifetime_and_string_and_char_together_dont_merge():
    src = "let x: &'static str = \"hi\"; let y = 'a'; fn f<'a>(z: &'a i32) {}"
    cleaned = _clean(src)
    assert '"hi"' not in cleaned
    assert "'a'" not in cleaned or cleaned.count("'a'") == 0
    assert "&'static str" in cleaned
    assert "<'a>" in cleaned
    assert "&'a i32" in cleaned


def test_TAD07_complexity_stable_across_near_identical_snapshots():
    base = (
        "impl Compiler {\n"
        "    fn c(&mut self, expr: &Hir) -> ResultOrEmpty {\n"
        "        match *expr.kind() {\n"
        "            Empty => Ok(None),\n"
        "            Literal(hir::Literal::Unicode(c)) => self.c_char(c),\n"
        "            _ => Ok(None),\n"
        "        }\n"
        "    }\n"
        "}\n"
    )
    patched = base.replace("Empty => Ok(None),", "Empty => self.c_empty(),") + (
        "\nimpl Compiler {\n"
        "    fn c_empty(&mut self) -> ResultOrEmpty {\n"
        "        self.extra_inst_bytes += std::mem::size_of::<Inst>();\n"
        "        Ok(None)\n"
        "    }\n"
        "}\n"
    )
    m1 = RustAdapter().compute_metrics(base, "compile.rs", "x", 0)
    m2 = RustAdapter().compute_metrics(patched, "compile.rs", "x", 0)
    assert abs(m1.cyclomatic_complexity - m2.cyclomatic_complexity) <= 2


def test_TAD08_no_runaway_match_spanning_multiple_lines():
    src = "fn f<'a>(x: &'a str) -> &'a str {\n    \"unrelated literal\"\n}\n"
    cleaned = _clean(src)
    assert "unrelated literal" not in cleaned
    assert "<'a>" in cleaned
