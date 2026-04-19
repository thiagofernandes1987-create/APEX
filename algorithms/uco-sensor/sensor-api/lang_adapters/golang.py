"""
UCO-Sensor — Go Adapter
========================
Analisa Go via tree-sitter e produz MetricVector com 9 canais UCO.

Go tem características distintas:
  - goroutines: loops infinitos legítimos (select{} / for{})
    → ILR calibrado: penalizar only when sem channel receive ou ctx.Done()
  - múltiplos retornos: contados como 1 operador (não inflam CC)
  - interfaces implícitas: DI via struct methods / interfaces importadas
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


def _load_go_parser():
    try:
        import tree_sitter_go as tsgo
        from tree_sitter import Language, Parser
        return Parser(Language(tsgo.language()))
    except Exception:
        return None

_GO_PARSER = None

def _get_go_parser():
    global _GO_PARSER
    if _GO_PARSER is None:
        _GO_PARSER = _load_go_parser()
    return _GO_PARSER


_GO_CC_NODES = frozenset([
    "if_statement", "else_clause",
    "for_statement",
    "expression_switch_statement", "type_switch_statement",
    "case_clause", "default_clause",
    "select_statement",
    "binary_expression",   # && || filtrado
    "communication_case",  # select case
])

_GO_FN_NODES = frozenset([
    "function_declaration", "method_declaration", "func_literal",
])

_GO_TERMINAL = frozenset([
    "return_statement", "goto_statement", "break_statement", "continue_statement",
])


class _GoCollector:
    def __init__(self):
        self.cc: int = 1
        self.fn_cc: Dict[str, int] = {}
        self._fn_stack: List[int] = []
        self.n_functions: int = 0
        self.n_types: int = 0   # struct/interface = proxy de classes
        self._type_methods: Dict[str, int] = {}
        self.dead_lines: int = 0
        self.loop_risk: int = 0
        self.n_for_infinite: int = 0
        self._ops: Dict[str, int] = {}
        self._operands: Dict[str, int] = {}
        self.imports: Set[str] = set()

    def visit(self, node) -> None:
        ntype = node.type

        if ntype in _GO_CC_NODES:
            if ntype == "binary_expression":
                op = self._op_text(node)
                if op in ("&&", "||"):
                    self.cc += 1
            else:
                self.cc += 1

        if ntype in _GO_FN_NODES:
            self.n_functions += 1
            saved = self.cc; self.cc = 1
            self._fn_stack.append(saved)
            for child in node.children:
                self.visit(child)
            fn_cc = self.cc
            self.fn_cc[f"fn_{len(self.fn_cc)}"] = fn_cc
            self.cc = self._fn_stack.pop() + fn_cc - 1
            return

        # Struct e interface como proxies de "classe"
        if ntype in ("type_declaration",):
            self.n_types += 1

        # ILR: for {} (loop infinito em Go) sem select/channel case
        if ntype == "for_statement":
            # for sem condição = for{}
            has_condition = any(c.type in ("binary_expression", "unary_expression",
                                           "identifier", "call_expression")
                                for c in node.children if c.type != "block")
            if not has_condition:
                self.n_for_infinite += 1
                body = next((c for c in node.children if c.type == "block"), None)
                # select{} ou <-ctx.Done() = escape legítimo em goroutines
                # busca recursiva — garante detecção mesmo em tree-sitter >= 0.22
                if not self._has_channel_escape(body):
                    self.loop_risk += 1

        # Imports
        if ntype == "import_spec" and node.text:
            pkg = node.text.decode("utf-8","replace").strip('"').split("/")[-1]
            self.imports.add(pkg)

        # Halstead
        if ntype == "identifier" and node.text:
            k = node.text.decode("utf-8","replace")[:30]
            self._operands[k] = self._operands.get(k, 0) + 1
        if ntype in ("int_literal","float_literal","string_literal",
                     "true","false","nil") and node.text:
            k = node.text.decode("utf-8","replace")[:20]
            self._operands[k] = self._operands.get(k, 0) + 1

        for child in node.children:
            self.visit(child)

    def _has_channel_escape(self, node) -> bool:
        """Busca recursiva: retorna True se há select/return/break em qualquer
        nível abaixo de `node` (cobre tree-sitter >= 0.22 onde block pode ter
        nós intermediários dependendo da versão da grammar)."""
        if node is None:
            return False
        if node.type in ("select_statement", "return_statement", "break_statement"):
            return True
        for child in node.children:
            if self._has_channel_escape(child):
                return True
        return False

    def _op_text(self, node) -> str:
        for child in node.children:
            if child.text and child.text.decode("utf-8","replace") in ("&&","||","!"):
                return child.text.decode("utf-8","replace")
        return ""

    @property
    def max_methods_per_type(self) -> int:
        return max(self._type_methods.values(), default=0)

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


class GoAdapter(LanguageAdapter):
    EXTENSIONS = (".go",)
    LANGUAGE   = "go"

    def compute_metrics(
        self,
        source: str,
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
        file_extension: str = ".go",
    ) -> MetricVector:
        if timestamp is None:
            timestamp = time.time()

        parser = _get_go_parser()
        if parser is None:
            return self._minimal(source, module_id, commit_hash, timestamp)

        try:
            tree = parser.parse(source.encode("utf-8", "replace"))
        except Exception:
            return self._minimal(source, module_id, commit_hash, timestamp)

        col = _GoCollector()
        col.visit(tree.root_node)

        loc = len([l for l in source.splitlines() if l.strip()])
        n1 = max(1, len(col._ops)); N1 = max(1, sum(col._ops.values()))
        n2 = max(1, len(col._operands)); N2 = max(1, sum(col._operands.values()))
        vocab = n1 + n2; length = N1 + N2
        volume = length * math.log2(vocab) if vocab > 0 else 0.0
        effort = (n1 / 2) * (N2 / max(1, n2)) * volume
        bugs   = volume / 3000.0
        h      = effort / max(1, loc) * 0.01

        n_infinite = col.n_for_infinite
        ilr = min(1.0, col.loop_risk / max(1, n_infinite) if n_infinite else 0.0)
        n_classes = col.n_types  # structs/interfaces como proxy
        di = min(3.0, col.max_methods_per_type / 20.0)
        dsm_d = min(1.0, len(col.imports) / (max(1, col.n_functions) * 2 + 1))
        fn_list = col.fn_cc_list
        cc_hr = 0.0
        if fn_list and len(fn_list) > 1:
            avg = sum(fn_list) / len(fn_list)
            cc_hr = min(1.0, col.max_fn_cc / max(1, avg * 3))
        cc = max(1, col.cc)
        status = "CRITICAL" if h >= 20 or cc > 20 else "WARNING" if h >= 8 or cc > 10 else "STABLE"

        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=round(h,4), cyclomatic_complexity=cc,
            infinite_loop_risk=round(ilr,4), dsm_density=round(dsm_d,4),
            dsm_cyclic_ratio=0.0, dependency_instability=round(di,4),
            syntactic_dead_code=col.dead_lines,
            duplicate_block_count=_count_duplicates(source),
            halstead_bugs=round(bugs,4), language="go",
            lines_of_code=loc, status=status,
        )
        mv.n_functions=col.n_functions; mv.n_classes=n_classes
        mv.max_methods_per_class=col.max_methods_per_type
        mv.cc_hotspot_ratio=round(cc_hr,4); mv.max_function_cc=col.max_fn_cc
        return mv

    def _minimal(self, source, module_id, commit_hash, timestamp) -> MetricVector:
        loc = len([l for l in source.splitlines() if l.strip()])
        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=loc*0.05, cyclomatic_complexity=1,
            infinite_loop_risk=0.0, dsm_density=0.0, dsm_cyclic_ratio=0.0,
            dependency_instability=0.5, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.0,
            language="go", lines_of_code=loc, status="STABLE",
        )
        return mv
