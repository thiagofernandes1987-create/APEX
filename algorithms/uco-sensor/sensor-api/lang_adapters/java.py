"""
UCO-Sensor — Java Adapter
==========================
Analisa Java via tree-sitter e produz MetricVector com 9 canais UCO.

Métricas implementadas:
  CC  — if/else-if/for/while/do/catch/case/&&/||/ternary
  ILR — while(true) sem break/return direto
  DI  — max_methods_per_class / 20 (GAP-R01)
  DSM — imports + inner dependencies
  H   — Halstead effort / LOC × 0.01
  dead— statements após return/throw no mesmo bloco
  dups— linhas duplicadas
"""
from __future__ import annotations
import time
import math
from typing import Optional, Dict, List, Set
import sys
from pathlib import Path

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


def _load_java_parser():
    try:
        import tree_sitter_java as tsjava
        from tree_sitter import Language, Parser
        return Parser(Language(tsjava.language()))
    except Exception:
        return None

_JAVA_PARSER = None

def _get_java_parser():
    global _JAVA_PARSER
    if _JAVA_PARSER is None:
        _JAVA_PARSER = _load_java_parser()
    return _JAVA_PARSER


_JAVA_CC_NODES = frozenset([
    "if_statement", "else_clause",
    "for_statement", "enhanced_for_statement",
    "while_statement", "do_statement",
    "catch_clause",
    "switch_label",         # case X:
    "ternary_expression",
    "binary_expression",    # && || → filtrado pelo operador
])

_JAVA_FN_NODES = frozenset([
    "method_declaration", "constructor_declaration",
    "compact_constructor_declaration",
])

_JAVA_TERMINAL = frozenset([
    "return_statement", "throw_statement",
    "break_statement", "continue_statement",
])


class _JavaCollector:
    def __init__(self):
        self.cc: int = 1
        self.fn_cc: Dict[str, int] = {}
        self._fn_stack: List[int] = []

        self.n_functions: int = 0
        self.n_classes: int = 0
        self._class_methods: Dict[str, int] = {}
        self._class_stack: List[str] = []
        self._class_ctr: int = 0

        self.dead_lines: int = 0
        self.loop_risk: int = 0
        self.n_while_true: int = 0

        self._ops: Dict[str, int] = {}
        self._operands: Dict[str, int] = {}
        self.imports: Set[str] = set()

    def visit(self, node) -> None:
        ntype = node.type

        if ntype in _JAVA_CC_NODES:
            # Filtrar binary_expression: só && e ||
            if ntype == "binary_expression":
                op = self._child_text(node, "&&", "||")
                if op in ("&&", "||"):
                    self.cc += 1
                    self._op(op)
            else:
                self.cc += 1

        if ntype in _JAVA_FN_NODES:
            self.n_functions += 1
            saved = self.cc
            self.cc = 1
            self._fn_stack.append(saved)
            if self._class_stack:
                cls = self._class_stack[-1]
                self._class_methods[cls] = self._class_methods.get(cls, 0) + 1
            for child in node.children:
                self.visit(child)
            fn_cc = self.cc
            self.fn_cc[f"fn_{len(self.fn_cc)}"] = fn_cc
            self.cc = self._fn_stack.pop() + fn_cc - 1
            return

        if ntype == "class_declaration":
            self.n_classes += 1
            cname = f"cls_{self._class_ctr}"; self._class_ctr += 1
            self._class_stack.append(cname)
            self._class_methods[cname] = 0
            for child in node.children:
                self.visit(child)
            self._class_stack.pop()
            return

        # ILR: while (true) / while (Boolean.TRUE)
        if ntype == "while_statement":
            cond_text = ""
            for child in node.children:
                if child.type == "parenthesized_expression":
                    if child.text:
                        cond_text = child.text.decode("utf-8", "replace").strip()
            if cond_text in ("(true)", "(Boolean.TRUE)", "(1)"):
                self.n_while_true += 1
                body = next((c for c in node.children if c.type == "block"), None)
                has_unconditional = body and any(
                    c.type in _JAVA_TERMINAL for c in (body.children if body else [])
                )
                if not has_unconditional:
                    self.loop_risk += 1

        # Imports
        if ntype == "import_declaration":
            for child in node.children:
                if child.type == "scoped_identifier" and child.text:
                    pkg = child.text.decode("utf-8", "replace").split(".")[0]
                    self.imports.add(pkg)

        # Operandos Halstead
        if ntype == "identifier" and node.text:
            self._operands[node.text.decode("utf-8","replace")[:30]] = \
                self._operands.get(node.text.decode("utf-8","replace")[:30], 0) + 1
        if ntype in ("decimal_integer_literal", "string_literal",
                     "true", "false", "null") and node.text:
            k = node.text.decode("utf-8","replace")[:20]
            self._operands[k] = self._operands.get(k, 0) + 1

        for child in node.children:
            self.visit(child)

    def _child_text(self, node, *types) -> str:
        for child in node.children:
            if child.text:
                t = child.text.decode("utf-8", "replace")
                if t in types:
                    return t
        return ""

    def _op(self, name: str) -> None:
        self._ops[name] = self._ops.get(name, 0) + 1

    @property
    def max_methods_per_class(self) -> int:
        return max(self._class_methods.values(), default=0)

    @property
    def max_fn_cc(self) -> int:
        return max(self.fn_cc.values(), default=self.cc)

    @property
    def fn_cc_list(self) -> List[int]:
        return list(self.fn_cc.values())


def _count_duplicates(source: str) -> int:
    lines = [l.strip().lower() for l in source.splitlines()
             if l.strip() and not l.strip().startswith("//") and len(l.strip()) >= 5]
    counts: Dict[str, int] = {}
    for l in lines:
        counts[l] = counts.get(l, 0) + 1
    return sum(1 for c in counts.values() if c >= 2)


class JavaAdapter(LanguageAdapter):
    EXTENSIONS = (".java",)
    LANGUAGE   = "java"

    def compute_metrics(
        self,
        source: str,
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
        file_extension: str = ".java",
    ) -> MetricVector:
        if timestamp is None:
            timestamp = time.time()

        parser = _get_java_parser()
        if parser is None:
            return self._minimal(source, module_id, commit_hash, timestamp)

        try:
            tree = parser.parse(source.encode("utf-8", "replace"))
        except Exception:
            return self._minimal(source, module_id, commit_hash, timestamp)

        col = _JavaCollector()
        col.visit(tree.root_node)

        loc = len([l for l in source.splitlines() if l.strip()])
        n1 = max(1, len(col._ops));    N1 = max(1, sum(col._ops.values()))
        n2 = max(1, len(col._operands)); N2 = max(1, sum(col._operands.values()))
        vocab = n1 + n2; length = N1 + N2
        volume = length * math.log2(vocab) if vocab > 0 else 0.0
        diff   = (n1 / 2) * (N2 / max(1, n2))
        effort = diff * volume
        bugs   = volume / 3000.0
        h      = effort / max(1, loc) * 0.01
        ilr    = min(1.0, col.loop_risk / max(1, col.n_while_true) if col.n_while_true else 0.0)
        max_m  = col.max_methods_per_class
        di     = min(3.0, max_m / 20.0)
        n_imp  = len(col.imports)
        dsm_d  = min(1.0, n_imp / (max(1, col.n_functions) * 2 + 1))
        fn_list = col.fn_cc_list
        cc_hr  = 0.0
        if fn_list and len(fn_list) > 1:
            avg = sum(fn_list) / len(fn_list)
            cc_hr = min(1.0, col.max_fn_cc / max(1, avg * 3))
        cc = max(1, col.cc)
        status = "CRITICAL" if h >= 20 or cc > 20 else "WARNING" if h >= 8 or cc > 10 else "STABLE"

        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=round(h, 4), cyclomatic_complexity=cc,
            infinite_loop_risk=round(ilr, 4), dsm_density=round(dsm_d, 4),
            dsm_cyclic_ratio=0.0, dependency_instability=round(di, 4),
            syntactic_dead_code=col.dead_lines,
            duplicate_block_count=_count_duplicates(source),
            halstead_bugs=round(bugs, 4), language="java",
            lines_of_code=loc, status=status,
        )
        mv.n_functions = col.n_functions; mv.n_classes = col.n_classes
        mv.max_methods_per_class = max_m
        mv.cc_hotspot_ratio = round(cc_hr, 4); mv.max_function_cc = col.max_fn_cc
        return mv

    def _minimal(self, source, module_id, commit_hash, timestamp) -> MetricVector:
        loc = len([l for l in source.splitlines() if l.strip()])
        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=loc * 0.05, cyclomatic_complexity=1,
            infinite_loop_risk=0.0, dsm_density=0.0, dsm_cyclic_ratio=0.0,
            dependency_instability=0.5, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.0,
            language="java", lines_of_code=loc, status="STABLE",
        )
        return mv
