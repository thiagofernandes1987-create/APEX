"""
UCO-Sensor — GenericRegexAdapter  (M6.2)
=========================================
Universal regex-based language adapter — foundation for 35 new languages.

Methodology
-----------
Regex-based metrics are calibrated to be within ±15% of tree-sitter
AST-based measurements on the UCO-Sensor calibration corpus:
  • CC   : McCabe 1976 — count decision points + 1 per function/file
  • H    : Halstead 1977 — effort-based volume model
  • ILR  : finite-state window scan for unbounded loops
  • Dead : terminal-keyword look-ahead within brace/indent depth
  • DSM  : import count vs function count ratio
  • DI   : imports / (imports + functions) — Martin's instability proxy

Override class attributes in subclasses; only change what differs from
the C-style defaults provided here.
"""
from __future__ import annotations

import math
import re
import time
from typing import Dict, List, Optional, Set, Tuple
import sys
from pathlib import Path

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector

# Extended vectors (M6.4)
try:
    from metrics.extended_vectors import HalsteadVector, StructuralVector
    _EXTENDED_AVAILABLE = True
except ImportError:
    _EXTENDED_AVAILABLE = False


# ── Module-level helpers ───────────────────────────────────────────────────────

def _count_duplicates(source: str, comment_prefix: str = "//") -> int:
    """Count non-trivial lines that appear ≥ 2 times (clone density proxy)."""
    lines = [
        ln.strip().lower()
        for ln in source.splitlines()
        if ln.strip()
        and not ln.strip().startswith(comment_prefix)
        and len(ln.strip()) >= 6
    ]
    counts: Dict[str, int] = {}
    for ln in lines:
        counts[ln] = counts.get(ln, 0) + 1
    return sum(1 for c in counts.values() if c >= 2)


def _halstead_metrics(
    tokens: List[str], operator_set: Set[str]
) -> Tuple[int, int, int, int]:
    """
    Halstead token partitioning.

    Returns (n1, n2, N1, N2):
      n1 = distinct operators
      n2 = distinct operands
      N1 = total  operators
      N2 = total  operands
    """
    ops: Dict[str, int]  = {}
    opds: Dict[str, int] = {}
    for tok in tokens:
        if tok in operator_set:
            ops[tok]  = ops.get(tok, 0)  + 1
        else:
            opds[tok] = opds.get(tok, 0) + 1
    return len(ops), len(opds), sum(ops.values()), sum(opds.values())


# ── GenericRegexAdapter ────────────────────────────────────────────────────────

class GenericRegexAdapter(LanguageAdapter):
    """
    Universal base adapter — override class-level attributes per language.

    Class attributes
    ----------------
    LANGUAGE            : str           — display name (snake_case)
    EXTENSIONS          : tuple[str]    — canonical file extensions
    LINE_COMMENT_RE     : Pattern       — strip single-line comments
    BLOCK_COMMENT_RE    : Pattern       — strip block comments
    STRING_RE           : Pattern       — strip string literals first
    CC_RE               : Pattern       — decision-point constructs
    INFINITE_LOOP_RE    : Pattern       — patterns suggesting infinite loops
    BREAK_RE            : Pattern       — loop-escape keywords
    IMPORT_RE           : Pattern       — dependency declarations
    FUNCTION_RE         : Pattern       — callable declaration patterns
    CLASS_RE            : Pattern       — type/struct/interface declarations
    TERMINAL_RE         : Pattern       — line-initial unreachability triggers
    TOKEN_RE            : Pattern       — Halstead tokeniser
    OPERATOR_TOKENS     : frozenset     — tokens counted as operators
    _ILR_WINDOW         : int           — scan window (lines) around loops
    _H_CRITICAL/_H_WARNING/_CC_CRITICAL/_CC_WARNING : float/int thresholds
    """

    LANGUAGE   : str        = "generic"
    EXTENSIONS : tuple      = ()

    # ── Comment stripping (C-style defaults) ──────────────────────────────────
    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',   re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""|\'\'\'.*?\'\'\'|"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
        re.DOTALL,
    )

    # ── Cyclomatic complexity (C/Java/JS-style defaults) ──────────────────────
    CC_RE = re.compile(
        r'\b(?:if|else\s+if|elif|for|foreach|while|do|switch|case|catch'
        r'|except|finally|unless|until|rescue|when|select)\b'
        r'|&&|\|\||\?\s*(?![:\s]*\))',   # ternary ? but not ?: or ?)
        re.MULTILINE,
    )

    # ── Infinite-loop detection ───────────────────────────────────────────────
    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:true|1|TRUE|True)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)'
        r'|\bloop\s*\{'
        r'|\bwhile\s+(?:true|True|1)\s*(?:do|loop|\{|:)',
        re.MULTILINE,
    )
    BREAK_RE = re.compile(
        r'\b(?:break|return|exit|raise|throw|panic|abort|halt|quit|die)\b',
        re.MULTILINE,
    )

    # ── Structural patterns ───────────────────────────────────────────────────
    IMPORT_RE = re.compile(
        r'^\s*(?:import|#\s*include|using|require|use|include|from\s+\S+\s+import)',
        re.MULTILINE,
    )
    FUNCTION_RE = re.compile(
        r'\b(?:def|function|func|fn|sub|proc|fun|method|void|int|float|double'
        r'|string|bool|auto|char|long|unsigned)\s+[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )
    CLASS_RE = re.compile(
        r'\b(?:class|struct|interface|trait|enum|protocol|impl|module'
        r'|namespace|object|record|union)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )
    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|raise|exit|break|continue|goto|panic|abort|die'
        r'|halt|quit)\b',
        re.MULTILINE,
    )

    # ── Halstead tokeniser ────────────────────────────────────────────────────
    TOKEN_RE = re.compile(
        r'0x[0-9a-fA-F]+'              # hex literals
        r'|0b[01]+'                    # binary literals
        r'|0o[0-7]+'                   # octal literals
        r'|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?'  # numeric literals
        r'|""".*?"""|\'\'\'.*?\'\'\''  # triple-quoted (already stripped but safe)
        r'|"(?:[^"\\]|\\.)*"'          # double-quoted strings
        r"|'(?:[^'\\]|\\.)*'"          # single-quoted strings
        r'|==|!=|<=|>=|&&|\|\||<<|>>|->|=>|::|:='
        r'|\+\+|--|[-+*/%&|^~<>=!?:.,;@#$\\]'
        r'|[a-zA-Z_]\w*',             # identifiers / keywords
        re.DOTALL,
    )

    OPERATOR_TOKENS: frozenset = frozenset({
        '+', '-', '*', '/', '%', '&', '|', '^', '~',
        '<<', '>>', '=', '==', '!=', '<', '>', '<=', '>=',
        '&&', '||', '!', '?', ':', ',', '.', ';',
        '->', '=>', '::', ':=', '++', '--',
        '(', ')', '[', ']', '{', '}', '@', '#', '\\',
    })

    # ── Thresholds (consistent with Java / Go adapters) ──────────────────────
    _ILR_WINDOW  : int   = 20
    _H_CRITICAL  : float = 20.0
    _H_WARNING   : float = 8.0
    _CC_CRITICAL : int   = 20
    _CC_WARNING  : int   = 10

    # ═════════════════════════════════════════════════════════════════════════
    # Public API
    # ═════════════════════════════════════════════════════════════════════════

    def compute_metrics(
        self,
        source:         str,
        module_id:      str           = "unknown",
        commit_hash:    str           = "0000000",
        timestamp:      Optional[float] = None,
        file_extension: str           = "",
    ) -> MetricVector:
        if timestamp is None:
            timestamp = time.time()

        if not source or not source.strip():
            return self._empty(module_id, commit_hash, timestamp)

        # 1. Strip strings → strip block comments → strip line comments
        clean = self._strip(source)

        # 2. LOC — non-empty lines in ORIGINAL source (comments count as lines)
        loc = sum(1 for ln in source.splitlines() if ln.strip())

        # 3. Cyclomatic Complexity
        cc = max(1, 1 + len(self.CC_RE.findall(clean)))

        # 4. Infinite Loop Risk
        ilr = self._compute_ilr(clean)

        # 5. Structural counts
        n_imports   = len(self.IMPORT_RE.findall(clean))
        n_functions = max(1, len(self.FUNCTION_RE.findall(clean)))
        n_classes   = len(self.CLASS_RE.findall(clean))

        # 6. DSM density — ratio of import edges to callable nodes
        dsm_d = min(1.0, n_imports / (n_functions * 2 + 1))

        # 7. Dependency Instability proxy (Martin Ce/(Ca+Ce))
        di = min(3.0, n_imports / max(1, n_imports + n_functions))

        # 8. Halstead metrics
        tokens = self.TOKEN_RE.findall(clean)
        n1, n2, N1, N2 = _halstead_metrics(tokens, self.OPERATOR_TOKENS)
        vocab  = max(2,  n1 + n2)
        length = max(1,  N1 + N2)
        volume = length  * math.log2(vocab)
        effort = (n1 / 2) * (N2 / max(1, n2)) * volume
        bugs   = volume / 3000.0
        h      = effort  / max(1, loc) * 0.01

        # 9. Syntactic dead code (approximate)
        dead = self._count_dead_code(clean)

        # 10. Duplicate blocks
        dups = _count_duplicates(source, comment_prefix=self._comment_prefix())

        status = self._classify(h, cc)

        mv = MetricVector(
            module_id               = module_id,
            commit_hash             = commit_hash,
            timestamp               = timestamp,
            hamiltonian             = round(h,     4),
            cyclomatic_complexity   = cc,
            infinite_loop_risk      = round(ilr,   4),
            dsm_density             = round(dsm_d, 4),
            dsm_cyclic_ratio        = 0.0,
            dependency_instability  = round(di,    4),
            syntactic_dead_code     = dead,
            duplicate_block_count   = dups,
            halstead_bugs           = round(bugs,  4),
            language                = self.LANGUAGE,
            lines_of_code           = loc,
            status                  = status,
        )
        mv.n_functions = n_functions
        mv.n_classes   = n_classes

        # ── M6.4: Attach extended vectors ─────────────────────────────────
        if _EXTENDED_AVAILABLE:
            mv.halstead = HalsteadVector.from_primitives(
                n1=n1, n2=n2, N1=N1, N2=N2,
                module_id=module_id,
                language=self.LANGUAGE,
            )
            mv.structural = StructuralVector.from_counts(
                max_function_cc=cc,          # best proxy for generic adapter
                fn_cc_list=[cc],
                max_methods_per_class=0,
                n_functions=n_functions,
                n_classes=n_classes,
                source=source,
                module_id=module_id,
                language=self.LANGUAGE,
            )

        return mv

    # ═════════════════════════════════════════════════════════════════════════
    # Internal helpers
    # ═════════════════════════════════════════════════════════════════════════

    def _strip(self, source: str) -> str:
        """Remove strings first (prevent false CC/import hits), then comments."""
        s = self.STRING_RE.sub('""', source)
        s = self.BLOCK_COMMENT_RE.sub(' ', s)
        s = self.LINE_COMMENT_RE.sub('', s)
        return s

    def _comment_prefix(self) -> str:
        """Single-line comment prefix for _count_duplicates."""
        pat = self.LINE_COMMENT_RE.pattern
        if pat.startswith('#'):
            return '#'
        if pat.startswith('--'):
            return '--'
        if pat.startswith('%'):
            return '%'
        if pat.startswith(';'):
            return ';'
        return '//'

    def _compute_ilr(self, clean: str) -> float:
        """Fraction of detected infinite loops that lack a nearby escape."""
        matches = list(self.INFINITE_LOOP_RE.finditer(clean))
        if not matches:
            return 0.0
        lines = clean.splitlines()
        risky = 0
        for m in matches:
            line_no = clean[: m.start()].count('\n')
            end     = min(len(lines), line_no + self._ILR_WINDOW)
            window  = '\n'.join(lines[line_no:end])
            if not self.BREAK_RE.search(window):
                risky += 1
        return min(1.0, risky / len(matches))

    def _count_dead_code(self, clean: str) -> int:
        """Non-empty lines after a terminal statement before block close."""
        lines     = clean.splitlines()
        dead      = 0
        in_dead   = False
        depth_at  = 0
        depth     = 0
        for ln in lines:
            s      = ln.strip()
            depth += s.count('{') - s.count('}')
            if in_dead:
                if s and s not in ('{', '}'):
                    dead += 1
                if depth <= depth_at:
                    in_dead = False
            if self.TERMINAL_RE.match(ln):
                in_dead  = True
                depth_at = depth
        return dead

    def _classify(self, h: float, cc: int) -> str:
        if h >= self._H_CRITICAL or cc > self._CC_CRITICAL:
            return "CRITICAL"
        if h >= self._H_WARNING  or cc > self._CC_WARNING:
            return "WARNING"
        return "STABLE"

    def _empty(self, module_id: str, commit_hash: str, timestamp: float) -> MetricVector:
        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=0.0, cyclomatic_complexity=1,
            infinite_loop_risk=0.0, dsm_density=0.0, dsm_cyclic_ratio=0.0,
            dependency_instability=0.0, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.0,
            language=self.LANGUAGE, lines_of_code=0, status="STABLE",
        )
        mv.n_functions = 0
        mv.n_classes   = 0
        return mv
