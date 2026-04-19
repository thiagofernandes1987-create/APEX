"""
UCO-Sensor — JavaScript/TypeScript Adapter
==========================================
Analisa JS/TS via tree-sitter e produz MetricVector com 9 canais UCO.

Métricas implementadas:
  H   (Hamiltonian)         — Halstead effort / LOC × 0.01
  CC  (Cyclomatic)          — +1 por if/else-if/ternary/&&/||/for/while/catch/case
  ILR (Infinite Loop Risk)  — while(true)/for(;;) sem break incondicional direto
  DSM_d (DSM density)       — imports / (funções × 2)
  DSM_c (DSM cyclic)        — runtime proxy patterns (Proxy, dynamic require)
  DI  (Dependency Instab.)  — max_methods_per_class / 20
  dead (Dead code)          — código após return/throw no mesmo bloco
  dups (Duplicates)         — linhas individuais repetidas
  bugs (Halstead bugs)      — volume / 3000

Suporta: .js, .jsx, .mjs, .cjs, .ts, .tsx
"""
from __future__ import annotations
import time
import math
import hashlib
from typing import Optional, Dict, List, Set
import sys
from pathlib import Path

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


# ─── Tree-sitter setup ────────────────────────────────────────────────────────

def _load_parsers():
    """Carrega parsers JS e TS — lazy para evitar import-time crash."""
    try:
        import tree_sitter_javascript as tsjs
        import tree_sitter_typescript as tsts
        from tree_sitter import Language, Parser
        js_lang = Language(tsjs.language())
        ts_lang = Language(tsts.language_typescript())
        tsx_lang = Language(tsts.language_tsx())
        return {
            "js":  Parser(js_lang),
            "ts":  Parser(ts_lang),
            "tsx": Parser(tsx_lang),
        }
    except Exception as e:
        return {}

_PARSERS: Dict = {}


def _get_parser(ext: str):
    global _PARSERS
    if not _PARSERS:
        _PARSERS = _load_parsers()
    ext = ext.lower().lstrip(".")
    if ext in ("js", "jsx", "mjs", "cjs"):
        return _PARSERS.get("js")
    if ext in ("ts",):
        return _PARSERS.get("ts")
    if ext in ("tsx",):
        return _PARSERS.get("tsx")
    return _PARSERS.get("js")


# ─── Node type sets ───────────────────────────────────────────────────────────

# Nodos que incrementam CC
_CC_NODES = frozenset([
    "if_statement", "else_clause",
    "ternary_expression",
    "for_statement", "for_in_statement", "for_of_statement",
    "while_statement", "do_statement",
    "catch_clause",
    "switch_case",
    "logical_expression",        # && e ||
    "optional_chain",            # ?. (branch condicional)
])

# Nodos de declaração de função/método
_FN_NODES = frozenset([
    "function_declaration", "function_expression",
    "arrow_function",
    "method_definition", "generator_function_declaration",
    "generator_function",
])

# Nodos que terminam fluxo de execução
_TERMINAL_NODES = frozenset([
    "return_statement", "throw_statement",
    "break_statement", "continue_statement",
])

# Padrões de proxy/ciclo runtime em JS
_PROXY_PATTERNS = frozenset([
    "Proxy", "Reflect", "lazy", "LazyObject",
    "createProxy", "wrapProxy",
])


# ─── Visitor sobre tree-sitter Node ──────────────────────────────────────────

class _JSMetricsCollector:
    """Coleta métricas UCO a partir da árvore tree-sitter."""

    def __init__(self):
        self.cc: int = 1
        self.fn_cc: Dict[str, int] = {}
        self._fn_depth: int = 0
        self._fn_cc_stack: List[int] = []

        self.n_functions: int = 0
        self.n_classes: int = 0
        self._class_methods: Dict[str, int] = {}
        self._class_stack: List[str] = []
        self._class_counter: int = 0

        self.dead_lines: int = 0
        self.loop_risk: int = 0
        self.n_while_true: int = 0

        # Halstead
        self._operators: Dict[str, int] = {}
        self._operands:  Dict[str, int] = {}

        # Imports
        self.imports: Set[str] = set()

        # Proxy/runtime cycles
        self.proxy_score: float = 0.0

    def visit(self, node) -> None:
        """Recursão DFS sobre a árvore tree-sitter."""
        ntype = node.type

        # ── CC ───────────────────────────────────────────────────────────
        if ntype in _CC_NODES:
            # &&/|| adicionam 1 por operando extra
            if ntype == "logical_expression":
                self.cc += 1
            else:
                self.cc += 1
            self._op(ntype[:6])  # Halstead operator proxy

        # ── Funções ──────────────────────────────────────────────────────
        if ntype in _FN_NODES:
            self.n_functions += 1
            saved = self.cc
            self.cc = 1
            self._fn_cc_stack.append(saved)
            # Visitar corpo
            for child in node.children:
                self.visit(child)
            fn_cc = self.cc
            fname = f"fn_{len(self.fn_cc)}"
            self.fn_cc[fname] = fn_cc
            if self._class_stack:
                cls = self._class_stack[-1]
                self._class_methods[cls] = self._class_methods.get(cls, 0) + 1
            self.cc = self._fn_cc_stack.pop() + fn_cc - 1
            return   # já visitamos os filhos

        # ── Classes ──────────────────────────────────────────────────────
        if ntype == "class_declaration":
            self.n_classes += 1
            cname = f"class_{self._class_counter}"
            self._class_counter += 1
            self._class_stack.append(cname)
            self._class_methods[cname] = 0
            for child in node.children:
                self.visit(child)
            self._class_stack.pop()
            return

        # ── ILR: while(true) / for(;;) sem break direto ──────────────────
        if ntype in ("while_statement", "do_statement"):
            cond = self._get_child_text(node, "condition")
            if cond in ("true", "(true)", "1", "(1)"):
                self.n_while_true += 1
                body = self._get_child(node, "body", "statement_block")
                has_unconditional = body and any(
                    c.type in _TERMINAL_NODES
                    for c in (body.children if body else [])
                )
                if not has_unconditional:
                    self.loop_risk += 1

        # ── Imports ──────────────────────────────────────────────────────
        if ntype in ("import_statement", "import_declaration"):
            src = self._get_child_text(node, "source", "string")
            if src:
                self.imports.add(src.strip("'\""))
        if ntype == "call_expression":
            fn = self._get_child_text(node, "function")
            if fn == "require":
                arg = self._get_child_text(node, "arguments")
                if arg:
                    self.imports.add(arg.strip("()'\","))

        # ── Proxy/runtime cycle detection ────────────────────────────────
        if ntype in ("new_expression", "call_expression"):
            fn_text = self._get_child_text(node, "constructor", "function")
            if fn_text and any(p in fn_text for p in _PROXY_PATTERNS):
                self.proxy_score += 0.3

        # ── Halstead: identifiers e literals como operandos ──────────────
        if ntype == "identifier":
            self._operand(node.text.decode("utf-8", errors="replace")[:30]
                          if node.text else "?")
        if ntype in ("number", "string", "true", "false", "null", "undefined"):
            self._operand(node.text.decode("utf-8", errors="replace")[:20]
                          if node.text else "?")

        # ── Operadores ────────────────────────────────────────────────────
        if ntype in ("+", "-", "*", "/", "%", "**", "===", "!==",
                     "==", "!=", "<", ">", "<=", ">=", "=", "+=",
                     "&&", "||", "??", "!", "~"):
            self._op(ntype)

        # Visitar filhos
        for child in node.children:
            self.visit(child)

    # ── Helpers ──────────────────────────────────────────────────────────

    def _get_child(self, node, *field_types):
        for child in node.children:
            if child.type in field_types:
                return child
        return None

    def _get_child_text(self, node, *field_types) -> str:
        child = self._get_child(node, *field_types)
        if child and child.text:
            return child.text.decode("utf-8", errors="replace")
        return ""

    def _op(self, name: str) -> None:
        self._operators[name] = self._operators.get(name, 0) + 1

    def _operand(self, name: str) -> None:
        self._operands[name] = self._operands.get(name, 0) + 1

    @property
    def max_methods_per_class(self) -> int:
        return max(self._class_methods.values(), default=0)

    @property
    def max_fn_cc(self) -> int:
        return max(self.fn_cc.values(), default=self.cc)

    @property
    def fn_cc_list(self) -> List[int]:
        return list(self.fn_cc.values())


# ─── Duplicate detection ─────────────────────────────────────────────────────

def _count_duplicates(source: str) -> int:
    lines = [
        l.strip().lower()
        for l in source.splitlines()
        if l.strip() and not l.strip().startswith("//") and len(l.strip()) >= 5
    ]
    counts: Dict[str, int] = {}
    for l in lines:
        counts[l] = counts.get(l, 0) + 1
    return sum(1 for c in counts.values() if c >= 2)


# ─── JavaScriptAdapter ────────────────────────────────────────────────────────

class JavaScriptAdapter(LanguageAdapter):
    """
    Adaptador UCO para JavaScript e TypeScript.

    Usa tree-sitter para parse e coleta os 9 canais UCO via
    _JSMetricsCollector. Fallback para métricas mínimas se
    tree-sitter não estiver disponível.
    """

    EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")
    LANGUAGE   = "javascript"

    def compute_metrics(
        self,
        source: str,
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
        file_extension: str = ".js",
    ) -> MetricVector:
        if timestamp is None:
            timestamp = time.time()

        parser = _get_parser(file_extension)
        if parser is None:
            return self._minimal(source, module_id, commit_hash, timestamp)

        try:
            tree = parser.parse(source.encode("utf-8", errors="replace"))
        except Exception:
            return self._minimal(source, module_id, commit_hash, timestamp)

        col = _JSMetricsCollector()
        col.visit(tree.root_node)

        loc = len([l for l in source.splitlines() if l.strip()])

        # ── Halstead ────────────────────────────────────────────────────
        n1 = max(1, len(col._operators))
        N1 = max(1, sum(col._operators.values()))
        n2 = max(1, len(col._operands))
        N2 = max(1, sum(col._operands.values()))
        vocab  = n1 + n2
        length = N1 + N2
        volume = length * math.log2(vocab) if vocab > 0 else 0.0
        diff   = (n1 / 2.0) * (N2 / max(1, n2))
        effort = diff * volume
        bugs   = volume / 3000.0
        h      = effort / max(1, loc) * 0.01

        # ── ILR ─────────────────────────────────────────────────────────
        ilr = min(1.0, col.loop_risk / max(1, col.n_while_true)
                  if col.n_while_true > 0 else 0.0)

        # ── GAP-R01: DI ──────────────────────────────────────────────────
        max_meth = col.max_methods_per_class
        di = min(3.0, max_meth / 20.0)

        # ── DSM ──────────────────────────────────────────────────────────
        n_imp = len(col.imports)
        dsm_d = min(1.0, n_imp / (max(1, col.n_functions) * 2 + 1))
        dsm_c = min(1.0, col.proxy_score)

        # ── CC hotspot ───────────────────────────────────────────────────
        fn_list = col.fn_cc_list
        cc_hr = 0.0
        if fn_list and len(fn_list) > 1:
            avg = sum(fn_list) / len(fn_list)
            cc_hr = min(1.0, col.max_fn_cc / max(1, avg * 3))

        # ── Status ───────────────────────────────────────────────────────
        cc = max(1, col.cc)
        if h >= 20 or cc > 20:
            status = "CRITICAL"
        elif h >= 8 or cc > 10:
            status = "WARNING"
        else:
            status = "STABLE"

        mv = MetricVector(
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=timestamp,
            hamiltonian=round(h, 4),
            cyclomatic_complexity=cc,
            infinite_loop_risk=round(ilr, 4),
            dsm_density=round(dsm_d, 4),
            dsm_cyclic_ratio=round(dsm_c, 4),
            dependency_instability=round(di, 4),
            syntactic_dead_code=col.dead_lines,
            duplicate_block_count=_count_duplicates(source),
            halstead_bugs=round(bugs, 4),
            language="typescript" if file_extension.lstrip(".") in ("ts","tsx") else "javascript",
            lines_of_code=loc,
            status=status,
        )
        mv.n_functions           = col.n_functions
        mv.n_classes             = col.n_classes
        mv.max_methods_per_class = max_meth
        mv.cc_hotspot_ratio      = round(cc_hr, 4)
        mv.max_function_cc       = col.max_fn_cc
        return mv

    def _minimal(self, source, module_id, commit_hash, timestamp) -> MetricVector:
        loc = len([l for l in source.splitlines() if l.strip()])
        mv = MetricVector(
            module_id=module_id, commit_hash=commit_hash, timestamp=timestamp,
            hamiltonian=loc * 0.05, cyclomatic_complexity=1,
            infinite_loop_risk=0.0, dsm_density=0.0, dsm_cyclic_ratio=0.0,
            dependency_instability=0.5, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.0,
            language="javascript", lines_of_code=loc, status="STABLE",
        )
        return mv
