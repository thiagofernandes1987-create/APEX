"""
UCO-Sensor — ReDoS Pattern Analyzer  (M7.1)
============================================
Detects regular-expression patterns susceptible to catastrophic backtracking
(ReDoS — CWE-400) using pure-stdlib analysis — no external dependencies.

Three vulnerability classes are detected:

  Class A — Nested Quantifiers
      Patterns of the form (X+)+ or (X*)+ or (X+)*.  The inner quantifier
      lets the engine try exponentially many ways to fill the group, causing
      catastrophic backtracking when the overall match fails.
      Examples: (\\w+)+, (a+)+, (.+)+, ([a-z]+)*

  Class B — Overlapping Alternation Under Quantifier
      Patterns of the form (a|aa)+ or (ab|a)+ where two alternation branches
      can match the same prefix.  The engine explores every possible split
      among branches, leading to exponential time.
      Examples: (a|aa)+, (foo|fo)+, (he|she|his|hers)+

  Class C — Quantified Repetition of Overlapping Character Classes
      Patterns such as ([a-zA-Z0-9._]+@)+ — a quantified group with a
      character class that overlaps with an adjacent quantified group.
      Often found in e-mail / URL validators.

References
----------
Davis, J.C. et al. (2018). "Why aren't regular expressions a solved problem?"
  PLDI '18. https://doi.org/10.1145/3192366.3192390
OWASP ReDoS — https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS
"""
from __future__ import annotations

import re
from typing import List, NamedTuple, Optional


# ══════════════════════════════════════════════════════════════════════════════
# Data structures
# ══════════════════════════════════════════════════════════════════════════════

class ReDoSFinding(NamedTuple):
    """One detected ReDoS vulnerability in a regex pattern."""
    pattern:     str   # original pattern string
    vuln_class:  str   # A_NESTED_QUANTIFIER | B_OVERLAP_ALTERNATION | C_CHAR_CLASS_OVERLAP
    fragment:    str   # the specific sub-pattern that triggers the issue
    description: str   # human-readable explanation


# ══════════════════════════════════════════════════════════════════════════════
# Compiled detection patterns
# ══════════════════════════════════════════════════════════════════════════════

# Class A — group (capturing or non-capturing) containing a quantified token,
# itself followed by a quantifier.
# Matches: (\w+)+  ([a-z]+)*  (.+)+  (?:a+)+
_CLASS_A = re.compile(
    r"""
    \(                          # opening paren
    (?:                         # optional non-capturing / named group prefix
      \?(?::|\<\w+\>|P\<\w+\>) # ?: or ?<name> or ?P<name>
    )?
    [^()]*                      # group content (no nested parens — simplified)
    [+*]                        # inner quantifier
    [^()]*                      # rest of content
    \)                          # closing paren
    [+*]                        # outer quantifier on the group
    """,
    re.VERBOSE,
)

# Class B — alternation group under quantifier.
# We'll find (alt1|alt2|...) followed by + or *
_CLASS_B = re.compile(
    r"""
    \((?!\?[=!<])               # opening paren — not lookahead/lookbehind
    ([^()]+                     # capture alternation content (no nested parens)
    \|                          # must have at least one pipe
    [^()]+)
    \)
    [+*]                        # outer quantifier
    """,
    re.VERBOSE,
)

# Class C — character class with quantifier followed by same/overlapping class
# e.g. [\w.]+@[\w.]+ where both sides overlap under an outer quantifier
_CLASS_C = re.compile(
    r"""
    \([^()]*                    # group start
    \[[^\]]+\][+*?]             # [chars]+ inside group
    [^()]*                      # any other content
    \)[+*]                      # outer quantifier
    """,
    re.VERBOSE,
)


# ══════════════════════════════════════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════════════════════════════════════

def analyze_pattern(pattern: str) -> List[ReDoSFinding]:
    """
    Analyze a regex pattern string for catastrophic backtracking risk.

    Parameters
    ----------
    pattern : str
        The raw regex pattern string (not a compiled re.Pattern object).

    Returns
    -------
    List[ReDoSFinding]
        Empty list = no detected vulnerability.
        Non-empty = one or more ReDoS risk findings.
    """
    findings: List[ReDoSFinding] = []

    # ── Class A: nested quantifiers ───────────────────────────────────────────
    m = _CLASS_A.search(pattern)
    if m:
        fragment = m.group()
        findings.append(ReDoSFinding(
            pattern=pattern,
            vuln_class="A_NESTED_QUANTIFIER",
            fragment=fragment,
            description=(
                f"Nested quantifier detected: {fragment!r}. "
                "A quantified group whose body contains a quantifier creates "
                "exponentially many match paths on crafted non-matching input. "
                "Consider using possessive quantifiers or atomic groups, or "
                "rewrite to eliminate the inner quantifier."
            ),
        ))

    # ── Class B: overlapping alternation under quantifier ─────────────────────
    for m in _CLASS_B.finditer(pattern):
        # Skip if we already reported this region from Class A
        content = m.group(1)
        alternatives = content.split("|")
        if _alternatives_overlap(alternatives):
            fragment = m.group()
            findings.append(ReDoSFinding(
                pattern=pattern,
                vuln_class="B_OVERLAP_ALTERNATION",
                fragment=fragment,
                description=(
                    f"Overlapping alternation under quantifier: {fragment!r}. "
                    f"Branches {[a.strip() for a in alternatives]!r} can match "
                    "the same input in multiple ways, causing exponential "
                    "backtracking on non-matching input."
                ),
            ))
            break  # one finding per pattern is sufficient

    # ── Class C: character-class overlap in quantified group ──────────────────
    if not findings:   # only report C when A and B are absent (avoid noise)
        m = _CLASS_C.search(pattern)
        if m:
            fragment = m.group()
            findings.append(ReDoSFinding(
                pattern=pattern,
                vuln_class="C_CHAR_CLASS_OVERLAP",
                fragment=fragment,
                description=(
                    f"Quantified group with overlapping character class: "
                    f"{fragment!r}. Adjacent character classes with a "
                    "shared character set under quantifiers can lead to "
                    "polynomial or exponential backtracking."
                ),
            ))

    return findings


def is_vulnerable(pattern: str) -> bool:
    """Shorthand: return True if the pattern has any detected ReDoS risk."""
    return len(analyze_pattern(pattern)) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ══════════════════════════════════════════════════════════════════════════════

def _alternatives_overlap(alternatives: List[str]) -> bool:
    """
    Heuristic: detect if any two alternation branches share a leading prefix,
    indicating they can match the same input string.

    Catches:
      (a|aa)    → 'a' is prefix of 'aa'
      (ab|a)    → 'a' is prefix of 'ab'
      (foo|fo)  → 'fo' is prefix of 'foo'
      (\\w|\\w+) → same class, both start with \\w
    """
    if len(alternatives) < 2:
        return False

    normed = [a.strip() for a in alternatives if a.strip()]

    for i in range(len(normed)):
        for j in range(i + 1, len(normed)):
            a, b = normed[i], normed[j]
            if not a or not b:
                continue
            # Direct prefix relationship
            if a.startswith(b) or b.startswith(a):
                return True
            # Same leading character class or literal
            if _leading_token(a) == _leading_token(b):
                return True

    return False


def _leading_token(s: str) -> str:
    """
    Extract the first meaningful token from a pattern fragment.
    Handles: literals, \\d, \\w, \\s, [class], .
    """
    s = s.lstrip("^")
    if not s:
        return ""
    if s[0] == "\\" and len(s) >= 2:
        return s[:2]          # e.g. \\w, \\d
    if s[0] == "[":
        end = s.find("]", 1)
        return s[:end + 1] if end != -1 else s[0]
    return s[0]               # literal character or .
