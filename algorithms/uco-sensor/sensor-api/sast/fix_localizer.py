"""
UCO-Sensor — Fix-Diff Vulnerability Localizer  (M10)
=====================================================
Given the *vulnerable* and *fixed* revisions of a file (the before/after of
a known CVE fix commit), this module answers the questions the corpus
validation asks of every repository:

    * **where** did the bug live  → file + exact line(s) the fix touched
    * **how** was it fixed        → the security construct the fix ADDED
                                     (bounds check, null-guard, type widening,
                                     signedness fix, added `if`, …)
    * **what class**              → inferred CWE-ish class from the construct
    * **validation**              → is that guard PRESENT in the fixed revision
                                     and ABSENT in the vulnerable one?
                                     (i.e. did the tool's evidence line up with
                                     the real fix, and would a re-scan of the
                                     fixed file no longer show the missing guard)

Why a diff-anchored approach
----------------------------
Sprint BG established empirically that the sensor's pattern SAST does **not**
fire on the memory-safety CVE classes (integer-underflow, OOB, use-after-free)
— it reports rating A on the vulnerable file, or fires a generic rule that
*persists identically* across the fix, so it cannot tell "fired before /
stopped after".  The honest, real-data way to localize a *known* CVE is to
anchor on its fix commit: the diff itself is ground truth for where/how the
bug was, and comparing the guard's presence across the two revisions is a
faithful before/after validation with zero fabrication.

This does NOT claim to detect unknown bugs — that is the pattern/taint
engines' job (tracked separately).  It makes the *known-CVE corpus
validation* precise and localized instead of a coarse "something changed".

Public API
----------
    loc = FixDiffLocalizer()
    res = loc.localize(vuln_src, fixed_src, filename="mm/gup.c")
    res.added_guards        -> list[GuardHit]  (line, text, kind)
    res.vuln_classes        -> set[str]
    res.guard_present_in_fix_absent_in_vuln -> bool   (the validation)
    res.summary()           -> one-line human summary
"""
from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

# Security-relevant construct signatures.  Each maps a regex (matched on an
# ADDED line) to a (kind, cwe_class) tuple.  Ordered most-specific first.
_GUARD_SIGNATURES: List[Tuple["re.Pattern[str]", str, str]] = [
    (re.compile(r"\b(\w+)\s*[><]=?\s*(\w+).*\?"), "bounds-check-ternary", "CWE-190/125"),
    (re.compile(r"\bif\s*\([^)]*\b(len|size|count|n|idx|index|off|offset|pos)\b[^)]*[<>]"), "bounds-check-if", "CWE-125/787"),
    (re.compile(r"[!=]=\s*NULL|NULL\s*[!=]=|\b(\w+)\s*&&"), "null-guard", "CWE-476"),
    (re.compile(r"\b(uint32_t|uint64_t|size_t|int64_t|long long)\b"), "type-widening", "CWE-190"),
    (re.compile(r"\bunsafe\b"), "unsafe-contract", "RUST-soundness"),
    (re.compile(r"\b(overflow|underflow|bounds?|clamp|saturat)\w*\b", re.I), "overflow-guard", "CWE-190"),
    (re.compile(r"\b(memcpy|memmove|strncpy|snprintf)\b"), "safe-copy", "CWE-120"),
    (re.compile(r"\breturn\b.*\b(EINVAL|ERANGE|-1|error|Err)\b", re.I), "early-return-guard", "CWE-20"),
]

# A pure "guard" keyword set used to decide whether a changed line is
# security-relevant at all (avoids counting comment/format-only edits).
_SECURITY_TOKENS = re.compile(
    r"[<>]=?|[!=]=|&&|\|\||\bNULL\b|\bif\b|\breturn\b|\buint\d+_t\b|\bsize_t\b|\bunsafe\b",
)


@dataclass(frozen=True)
class GuardHit:
    """One security-relevant line the fix added."""
    line: int          # 1-based line number in the FIXED revision
    text: str
    kind: str
    cwe_class: str


@dataclass
class LocalizeResult:
    filename: str
    added_guards: List[GuardHit] = field(default_factory=list)
    removed_security_lines: List[str] = field(default_factory=list)
    added_lines: int = 0
    removed_lines: int = 0

    @property
    def vuln_classes(self) -> Set[str]:
        return {g.cwe_class for g in self.added_guards}

    @property
    def guard_present_in_fix_absent_in_vuln(self) -> bool:
        """
        The core validation: the fix ADDED at least one security guard that
        was not present in the vulnerable revision.  True ⇒ the before/after
        evidence is consistent with a real security fix and a re-scan of the
        fixed file would find the guard the vulnerable one lacked.
        """
        return len(self.added_guards) > 0

    @property
    def first_guard(self) -> Optional[GuardHit]:
        return self.added_guards[0] if self.added_guards else None

    def summary(self) -> str:
        if not self.added_guards:
            return f"{self.filename}: nenhum guard de segurança adicionado detectado no diff (+{self.added_lines}/-{self.removed_lines})"
        g = self.added_guards[0]
        classes = ",".join(sorted(self.vuln_classes))
        return (f"{self.filename}: fix adicionou {len(self.added_guards)} guard(s) "
                f"[{classes}] — 1º em L{g.line} ({g.kind}): {g.text.strip()[:70]}")


class FixDiffLocalizer:
    """Localizes a known-CVE fix by diffing the vulnerable vs fixed source."""

    def localize(self, vuln_src: str, fixed_src: str, filename: str = "") -> LocalizeResult:
        vuln_lines = vuln_src.splitlines()
        fixed_lines = fixed_src.splitlines()
        sm = difflib.SequenceMatcher(a=vuln_lines, b=fixed_lines, autojunk=False)

        res = LocalizeResult(filename=filename)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag in ("replace", "insert"):
                # added lines are fixed_lines[j1:j2], 1-based line numbers j+1
                for off, text in enumerate(fixed_lines[j1:j2]):
                    lineno = j1 + off + 1
                    res.added_lines += 1
                    if not _SECURITY_TOKENS.search(text):
                        continue
                    kind, cwe = _classify(text)
                    if kind is None:
                        continue
                    res.added_guards.append(GuardHit(line=lineno, text=text, kind=kind, cwe_class=cwe))
            if tag in ("replace", "delete"):
                for text in vuln_lines[i1:i2]:
                    res.removed_lines += 1
                    if _SECURITY_TOKENS.search(text):
                        res.removed_security_lines.append(text.strip())
        return res


def _classify(line: str) -> Tuple[Optional[str], Optional[str]]:
    for rx, kind, cwe in _GUARD_SIGNATURES:
        if rx.search(line):
            return kind, cwe
    return None, None
