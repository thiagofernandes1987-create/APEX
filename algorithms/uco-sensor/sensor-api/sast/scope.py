"""
UCO-Sensor — Function Scoper  (M14)
====================================
Dá a um scanner o **escopo real da função** que contém uma linha, via
tree-sitter (o mesmo motor AST do M9.2).  Substitui a janela de ±N linhas
usada pelo M11 (Sprint BH), que gerava falso-positivos por atravessar
fronteiras de função — o brace-matching falha em C real (macros
function-like, diretivas de preprocessador).

`FunctionScoper.enclosing_span(source, line, ext)` devolve `(start, end)`
1-based do nó de função (`function_definition` em C/C++, `function_item` em
Rust, `method_declaration`/`function_declaration` em Java/JS/Go, `function_…`
em PHP/Ruby) que contém `line`; ou `None` quando a gramática não está
disponível ou a linha não está numa função — nesse caso o chamador usa o
fallback de janela.

Degradação graciosa: sem tree-sitter → `available()` falso → `None`.
"""
from __future__ import annotations

from typing import Optional, Tuple

from lang_adapters.tree_sitter_bridge import TreeSitterBridge

# ext → (linguagem do bridge, tipos de nó que contam como "função")
_LANG_FN_NODES = {
    ".c":    ("c", {"function_definition"}),
    ".h":    ("c", {"function_definition"}),
    ".cpp":  ("cpp", {"function_definition"}),
    ".cc":   ("cpp", {"function_definition"}),
    ".cxx":  ("cpp", {"function_definition"}),
    ".hpp":  ("cpp", {"function_definition"}),
    ".rs":   ("rust", {"function_item"}),
    ".java": ("java", {"method_declaration", "constructor_declaration"}),
    ".js":   ("javascript", {"function_declaration", "method_definition", "function_expression", "arrow_function"}),
    ".go":   ("go", {"function_declaration", "method_declaration"}),
    ".php":  ("php", {"function_definition", "method_declaration"}),
    ".rb":   ("ruby", {"method", "singleton_method"}),
    ".cs":   ("csharp", {"method_declaration", "constructor_declaration", "local_function_statement"}),
    ".kt":   ("kotlin", {"function_declaration"}),
}


class FunctionScoper:
    """Escopo de função por AST tree-sitter, com fallback gracioso."""

    def __init__(self) -> None:
        self._bridges: dict = {}

    def _bridge(self, lang: str) -> TreeSitterBridge:
        if lang not in self._bridges:
            self._bridges[lang] = TreeSitterBridge(lang)
        return self._bridges[lang]

    def available_for(self, ext: str) -> bool:
        info = _LANG_FN_NODES.get(ext.lower())
        if info is None:
            return False
        return self._bridge(info[0]).available()

    def function_spans(self, source: str, ext: str) -> Optional[list]:
        """
        Todos os spans (start_line, end_line) 1-based de funções no arquivo,
        via UM único parse.  None se a gramática não estiver disponível.
        """
        info = _LANG_FN_NODES.get(ext.lower())
        if info is None:
            return None
        lang, fn_types = info
        tree = self._bridge(lang).parse(source)
        if tree is None:
            return None
        spans = []
        stack = [tree.root_node]
        while stack:
            n = stack.pop()
            if n.type in fn_types:
                spans.append((n.start_point[0] + 1, n.end_point[0] + 1))
            for c in n.children:
                stack.append(c)
        return spans

    @staticmethod
    def smallest_enclosing(spans: list, line: int) -> Optional[Tuple[int, int]]:
        """Menor span que contém *line* (1-based), ou None."""
        best = None
        best_size = 1 << 30
        for s, e in spans:
            if s <= line <= e and (e - s) < best_size:
                best, best_size = (s, e), e - s
        return best

    def enclosing_span(self, source: str, line: int, ext: str) -> Optional[Tuple[int, int]]:
        """(start,end) da menor função que contém *line* (conveniência: 1 parse)."""
        spans = self.function_spans(source, ext)
        if spans is None:
            return None
        return self.smallest_enclosing(spans, line)
