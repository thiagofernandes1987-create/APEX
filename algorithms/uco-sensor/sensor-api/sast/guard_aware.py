"""
UCO-Sensor — Guard-Aware Memory-Safety Scanner  (M11)
======================================================
Detects a *known-CVE class* of memory-safety bug **without needing the fix
commit** — and, crucially, stops firing once the fix adds the missing guard.
This is the real "rastrear bug conhecido / avaliar código gerado por IA"
capability the pattern-SAST lacked (Sprint BG diagnostic showed rating A on
the vulnerable file, or a generic rule persisting identically across the fix).

The insight: a bare risky construct is not, by itself, a bug — it is a bug
*only when the guard that would make it safe is absent from its function*.
So M11 is **guard-aware**: it finds the risky sink, extracts the variables
that need protection, then scans the enclosing function for a guard on those
same variables.  It fires only when no guard is present.  The fix, which adds
that guard, therefore suppresses the finding — a faithful before/after.

Classes covered (initial, driven by the real corpus)
----------------------------------------------------
* **GA01 — unchecked subtraction in pointer/length arithmetic**
  ``p = base + a - b`` (or ``len = a - b`` used as a size) without a guard
  ``a > b`` / ``a >= b`` / ``b < a`` on the operands → integer underflow →
  out-of-bounds (CWE-191/CWE-190/CWE-125).  This is exactly php-src
  CVE-2019-11043 (``env_path_info + pilen - slen`` with no ``pilen > slen``).
* **GA02 — memcpy/memmove with a length variable and no bound in scope**
  ``memcpy(dst, src, n)`` where ``n`` is a variable never compared against a
  size/limit in the function (CWE-120).

Design
------
* Function segmentation is a light brace-matcher (C/C++/Rust/Java/JS-ish);
  when it can't segment (e.g. Python), it treats the whole file as one scope
  — conservative (fewer, not more, findings).
* Pure and offline.  ``scan(source, ext)`` → ``list[GuardFinding]`` with the
  1-based line, the risky expression, the variables needing a guard, and why.

Public API
----------
    findings = GuardAwareScanner().scan(src, ".c")
    f.line, f.rule_id, f.title, f.needs_guard_on, f.snippet
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

_C_LIKE = {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".rs", ".java", ".js", ".ts", ".go", ".php"}

# base + a - b   (pointer/length arithmetic with a subtraction)
_SUBTRACT_ARITH = re.compile(
    r"([A-Za-z_]\w*)\s*\+\s*([A-Za-z_]\w*)\s*-\s*([A-Za-z_]\w*)"
)
# memcpy-family with 3 args, capturing the length arg identifier
_COPY_CALL = re.compile(
    r"\b(memcpy|memmove|strncpy|strncat|bcopy)\s*\(\s*[^,]+,\s*[^,]+,\s*([A-Za-z_]\w*)\s*\)"
)


@dataclass(frozen=True)
class GuardFinding:
    rule_id: str
    severity: str
    cwe_id: str
    title: str
    line: int
    snippet: str
    needs_guard_on: Tuple[str, ...]
    explanation: str


def _split_functions(source: str, ext: str) -> List[Tuple[int, int]]:
    """
    Return list of (start_line, end_line) 1-based spans for each brace-delimited
    function-ish block.  Falls back to a single whole-file span when the
    language isn't brace-delimited or no braces are found.
    """
    lines = source.splitlines()
    if ext not in _C_LIKE:
        return [(1, len(lines))]
    spans: List[Tuple[int, int]] = []
    depth = 0
    start = None
    for i, ln in enumerate(lines, start=1):
        opens = ln.count("{")
        closes = ln.count("}")
        if depth == 0 and opens > 0:
            start = start if start is not None else i
        depth += opens - closes
        if depth <= 0 and start is not None:
            spans.append((start, i))
            start = None
            depth = 0
    if not spans:
        return [(1, len(lines))]
    return spans


def _guard_present(block: str, a: str, b: str) -> bool:
    """
    True if the function block contains a comparison guard between *a* and *b*
    (either order / any relational operator), or a range check on either.
    """
    if a == b:
        return True  # x + y - y style, degenerate
    esc_a, esc_b = re.escape(a), re.escape(b)
    patterns = [
        rf"\b{esc_a}\s*[<>]=?\s*{esc_b}\b",
        rf"\b{esc_b}\s*[<>]=?\s*{esc_a}\b",
        rf"\b{esc_a}\s*[<>]=?\s*{esc_b}\s*[?:]",
    ]
    return any(re.search(p, block) for p in patterns)


def _bound_present(block: str, var: str) -> bool:
    """True if *var* is compared against something (a limit/size) in the block."""
    esc = re.escape(var)
    return bool(re.search(rf"\b{esc}\s*[<>]=?", block) or re.search(rf"[<>]=?\s*{esc}\b", block))


class GuardAwareScanner:
    """Guard-aware detection of unchecked memory-safety constructs."""

    # guard-scope: preferimos o ESCOPO REAL DA FUNÇÃO via tree-sitter (M14);
    # se a gramática não estiver disponível ou a linha estiver fora de função,
    # caímos para uma janela local de ±WINDOW linhas.  A janela sozinha gerava
    # FP por atravessar fronteiras de função (Sprint BH); o escopo por AST corta.
    WINDOW = 45

    def __init__(self) -> None:
        try:
            from sast.scope import FunctionScoper
            self._scoper = FunctionScoper()
        except Exception:  # pragma: no cover
            self._scoper = None

    def _scope(self, spans, lines: List[str], lineno: int) -> str:
        if spans is not None:
            from sast.scope import FunctionScoper as _FS
            span = _FS.smallest_enclosing(spans, lineno)
            if span is not None:
                s, e = span
                return "\n".join(lines[s - 1:e])
        lo = max(0, lineno - 1 - self.WINDOW)
        hi = min(len(lines), lineno - 1 + self.WINDOW + 1)
        return "\n".join(lines[lo:hi])

    def scan(self, source: str, ext: str = ".c") -> List[GuardFinding]:
        lines = source.splitlines()
        findings: List[GuardFinding] = []
        seen: Set[Tuple[str, int]] = set()
        # UM parse por scan: spans de função via AST (None → fallback janela)
        spans = None
        if self._scoper is not None:
            try:
                spans = self._scoper.function_spans(source, ext)
            except Exception:  # pragma: no cover
                spans = None

        for lineno, ln in enumerate(lines, start=1):
            scope = None  # lazy — só monta a janela quando há um match

            # GA01 — unchecked subtraction in pointer/length arithmetic
            for m in _SUBTRACT_ARITH.finditer(ln):
                base, a, b = m.group(1), m.group(2), m.group(3)
                if a == b:
                    continue
                if scope is None:
                    scope = self._scope(spans, lines, lineno)
                if _guard_present(scope, a, b):
                    continue
                key = ("GA01", lineno, a, b)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(GuardFinding(
                    rule_id="GA01", severity="HIGH", cwe_id="CWE-191",
                    title="Subtração não-checada em aritmética de ponteiro/comprimento (possível underflow → OOB)",
                    line=lineno, snippet=ln.strip()[:160],
                    needs_guard_on=(a, b),
                    explanation=(f"`{base} + {a} - {b}` sem guard `{a} > {b}` no escopo: se "
                                 f"{a} < {b}, o resultado faz underflow (aritmética unsigned) e "
                                 f"aponta/aloca fora dos limites."),
                ))

            # GA02 — memcpy-family with an unbounded length variable
            for m in _COPY_CALL.finditer(ln):
                fn, nvar = m.group(1), m.group(2)
                if scope is None:
                    scope = self._scope(spans, lines, lineno)
                if _bound_present(scope, nvar):
                    continue
                key = ("GA02", lineno, nvar)
                if key in seen:
                    continue
                seen.add(key)
                findings.append(GuardFinding(
                    rule_id="GA02", severity="HIGH", cwe_id="CWE-120",
                    title=f"{fn}() com comprimento variável sem bound no escopo (possível overflow)",
                    line=lineno, snippet=ln.strip()[:160],
                    needs_guard_on=(nvar,),
                    explanation=(f"`{fn}(..., {nvar})` sem comparação de `{nvar}` contra um "
                                 f"tamanho/limite no escopo — comprimento não validado."),
                ))
        findings.sort(key=lambda f: (f.line, f.rule_id))
        return findings
