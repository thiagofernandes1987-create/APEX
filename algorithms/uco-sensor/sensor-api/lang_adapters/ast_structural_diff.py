"""
UCO-Sensor — AST Structural Diff  (M9.2)
=========================================
A tree-sitter-backed structural fingerprint and before/after differ, built
to detect the *small* security fixes (single-line bounds checks, added
null-guards, ternary-condition hardening) that the regex-calibrated
``GenericRegexAdapter`` family under-detects.

Motivation
----------
The CVE-anchored before/after methodology (Sprint AC→AP) compares the
spectral fingerprint of a file at the vulnerable commit vs. the fix commit.
For Python/JS/Java/Go this rides on real tree-sitter parses and is sensitive
enough to move on a one-line change.  For the Tier-2 *regex* languages
(C, C++, PHP, Ruby, C#) the metric vector is computed from line-oriented
regex heuristics whose granularity floor is coarser than a single added
comparison operator — so genuine fixes can register a **zero delta**.

Concrete failure case (Sprint AQ): ``php/php-src`` CVE-2019-11043, file
``sapi/fpm/fpm/fpm_main.c``.  The fix adds a ``pilen > slen`` bounds check
and a ``path_info &&`` null-guard:

    -  path_info = env_path_info ? env_path_info + pilen - slen : NULL;
    -  tflag = (orig_path_info != path_info);
    +  path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;
    +  tflag = path_info && (orig_path_info != path_info);

The regex ``CAdapter`` reports delta = 0 on all nine UCO channels.  A real
tree-sitter parse reports a non-zero structural churn: ``&&`` +2, ``>`` +1,
``binary_expression`` +3 — i.e. it *sees* the bounds check.  That is exactly
the signal needed to confirm the fix as a SAST CVE-anchored data point.

Design
------
* ``ASTStructuralDiff(language)`` wraps a :class:`TreeSitterBridge`; if the
  grammar is unavailable it degrades to ``available() == False`` and the
  caller can fall back to the existing spectral delta — never an import-time
  or runtime crash.
* ``signature(source)`` → :class:`ASTSignature`: a node-type histogram, total
  node count, and max tree depth.
* ``diff(before, after)`` → :class:`ASTDiff`: per-node-type churn, the
  security-relevant operator deltas, and a single ``churn`` scalar (the sum
  of absolute per-type count differences) that is > 0 whenever the AST
  shape changed at all.

This is intentionally language-agnostic structural accounting (not a
semantic patch classifier).  It does NOT claim to decide *whether* a change
is a security fix; it provides the missing *sensitivity* so that a known
CVE fix commit, supplied by the caller, produces a measurable signal instead
of a misleading zero.

Public API
----------
    differ = ASTStructuralDiff("c")
    differ.available()                       -> bool
    differ.signature(src)                    -> ASTSignature
    d = differ.diff(before_src, after_src)   -> ASTDiff
    d.churn                                  -> int   (0 ⇢ identical AST shape)
    d.changed_node_types                     -> dict[str, (before, after)]
    d.security_operator_delta                -> dict[str, int]
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

from .tree_sitter_bridge import TreeSitterBridge

# Operators / node types whose appearance is disproportionately associated
# with security hardening (bounds checks, null-guards, signedness fixes).
# Used only for a human-readable *highlight* of a diff — not for a verdict.
_SECURITY_OPERATORS = frozenset(
    {
        "&&", "||", "!",            # added guards
        ">", "<", ">=", "<=",       # bounds checks
        "==", "!=",                 # null / sentinel comparisons
        "binary_expression",
        "unary_expression",
        "parenthesized_expression",
        "conditional_expression",   # ternary hardening
        "if_statement",
    }
)


@dataclass(frozen=True)
class ASTSignature:
    """Compact structural fingerprint of one source revision."""

    node_types: Counter
    total_nodes: int
    max_depth: int

    def top(self, n: int = 10) -> Dict[str, int]:
        return dict(self.node_types.most_common(n))


@dataclass(frozen=True)
class ASTDiff:
    """Structural delta between two source revisions of the same file."""

    churn: int
    total_nodes_delta: int
    max_depth_delta: int
    changed_node_types: Dict[str, Tuple[int, int]] = field(default_factory=dict)
    security_operator_delta: Dict[str, int] = field(default_factory=dict)

    @property
    def detected(self) -> bool:
        """True when the AST shape changed at all (churn > 0)."""
        return self.churn > 0

    @property
    def security_relevant(self) -> bool:
        """True when at least one security-associated operator count moved."""
        return any(v != 0 for v in self.security_operator_delta.values())


class ASTStructuralDiff:
    """
    Tree-sitter structural signature/diff with a graceful unavailability mode.

    Parameters
    ----------
    language
        One of ``c`` / ``cpp`` / ``php`` / ``ruby`` / ``csharp`` (and the
        already-supported ``python`` / ``javascript`` / ``typescript`` /
        ``java`` / ``go``).  Unknown or grammar-less languages yield
        ``available() == False``.
    """

    def __init__(self, language: str) -> None:
        self.language = language.lower()
        self._bridge = TreeSitterBridge(self.language)

    # ── availability ──────────────────────────────────────────────────────────

    def available(self) -> bool:
        return self._bridge.available()

    # ── signature ─────────────────────────────────────────────────────────────

    def signature(self, source: str) -> Optional[ASTSignature]:
        """
        Return the structural :class:`ASTSignature` for *source*, or ``None``
        when the grammar is unavailable / the source fails to parse.
        """
        tree = self._bridge.parse(source)
        if tree is None:
            return None
        types: Counter = Counter()
        max_depth = 0
        # Iterative DFS — avoids Python recursion limits on deep ASTs
        # (real-world C files reach depth ~30, but generated code can be worse).
        stack = [(tree.root_node, 0)]
        while stack:
            node, depth = stack.pop()
            types[node.type] += 1
            if depth > max_depth:
                max_depth = depth
            for child in node.children:
                stack.append((child, depth + 1))
        total = sum(types.values())
        return ASTSignature(node_types=types, total_nodes=total, max_depth=max_depth)

    # ── diff ──────────────────────────────────────────────────────────────────

    def diff(self, before: str, after: str) -> Optional[ASTDiff]:
        """
        Structural delta between *before* and *after*.  Returns ``None`` when
        the grammar is unavailable or either revision fails to parse — the
        caller should then fall back to the spectral metric delta.
        """
        sig_b = self.signature(before)
        sig_a = self.signature(after)
        if sig_b is None or sig_a is None:
            return None

        all_types = set(sig_b.node_types) | set(sig_a.node_types)
        changed: Dict[str, Tuple[int, int]] = {}
        churn = 0
        for t in all_types:
            cb = sig_b.node_types.get(t, 0)
            ca = sig_a.node_types.get(t, 0)
            if cb != ca:
                changed[t] = (cb, ca)
                churn += abs(ca - cb)

        sec_delta = {
            t: sig_a.node_types.get(t, 0) - sig_b.node_types.get(t, 0)
            for t in _SECURITY_OPERATORS
            if sig_a.node_types.get(t, 0) != sig_b.node_types.get(t, 0)
        }

        return ASTDiff(
            churn=churn,
            total_nodes_delta=sig_a.total_nodes - sig_b.total_nodes,
            max_depth_delta=sig_a.max_depth - sig_b.max_depth,
            changed_node_types=changed,
            security_operator_delta=sec_delta,
        )
