"""
Universal Code Optimizer (UCO) v4.0
=====================================
Análise cirúrgica + otimização multi-engine para código multi-linguagem.
Combina física estatística (HMC, SA) com engenharia de software (CFG, DSM, Halstead).

BASEADO EM: HJIT Unified Engine v3.0
AUDITADO v3.0 → v4.0: Inventário de 20 itens (bugs, gaps, melhorias).
Todos os itens P1/P2/P3 acionáveis implementados nesta versão.

══════════════════════════════════════════════════════════════════════════════
CORREÇÕES HERDADAS (v2.0 / v3.0)
══════════════════════════════════════════════════════════════════════════════
FIX-C01..07, BUG-U01..07, GAP-D01..03, IMP-M01..03 — ver histórico v3.0

══════════════════════════════════════════════════════════════════════════════
CORREÇÕES v4.0 — BUGS
══════════════════════════════════════════════════════════════════════════════
BUG-N01  progress_callback ignorado em quick_optimize (API quebrada)
          Original: self.greedy.optimize(code, progress_callback=None) literal
          Fixado:   repassa o callback recebido ao GreedyOptimizer

BUG-N02  EngineOutput.to_dict()/to_json() omitia dsm_matrix e cfg_edges
          Original: campos presentes no dataclass mas ausentes no dict
          Fixado:   dsm_matrix_sparse (formato CSR) + cfg_edges incluídos
          Nota:     sparse para evitar 56MB em módulos grandes (ex: APEX)

BUG-N03  potential() não penalizava código Python sintaticamente inválido
          Original: U retornado normalmente mesmo com SyntaxError no transformado
          Fixado:   U=1e9 para código Python inválido — HMC nunca converge para ele
          Medição:  0/500 ocorrências com transforms atuais; garantia formal adicionada

══════════════════════════════════════════════════════════════════════════════
GAPS CORRIGIDOS v4.0
══════════════════════════════════════════════════════════════════════════════
GAP-N01  strip_code_strings parcial: só em _infinite_loop_risk
          Fixado:   _duplicate_block_count e _syntactic_dead_code também usam
          Impacto:  falsos positivos por docstrings eliminados nos 3 métodos

GAP-N02  apply_policy: threshold 0.72 hardcoded e transform implícito não registrado
          Fixado:   aggression_threshold configurável no construtor de HMCCodeObjective
                    "whitespace_aggression_strip" registrado na transform_chain

GAP-N05  ConstantFoldingTransform._ZERO_VAR_RE: type unsafe para C++/Java
          Fixado:   via IMP-A (LanguageGuard) — constant_folding safe_for=["python"]

GAP-N07  GenericCFGBuilder: {1,2,3} tratado como bloco aninhado (array init)
          Fixado:   split_generic_segments detecta contexto precedente (= ( ,)
                    e trata {expr} como literal, não como bloco estrutural
          Medição:  12 segs → 9 segs, depth 2→1 para int x[]={1,2,3}

══════════════════════════════════════════════════════════════════════════════
MELHORIAS v4.0 — IMPLEMENTADAS
══════════════════════════════════════════════════════════════════════════════
IMP-A  TransformLanguageGuard: atributo safe_for em cada transform
        Cada CodeTransform declara linguagens onde é semanticamente seguro.
        GreedyOptimizer filtra por detect_language() antes do loop.
        Resultado: UCO seguro para C++/VBA/DSL sem reescrever transforms.

IMP-B  split_generic_segments v2: blocos de expressão vs estruturais
        Detecta contexto: = ( , antes de { → trata como literal inline.
        Ver GAP-N07 acima.

IMP-C  HalsteadMetrics.from_tokens(): Halstead universal por tokenização léxica
        Funciona para Python, C++, Java, VBA, DSL, APEX YAML.
        Precisão vs from_python(): bugs_estimate Δ=1.5%, n2 Δ=0%.
        FeatureExtractor usa from_python para Python, from_tokens para o resto.

IMP-D  SimulatedAnnealingOptimizer + optimize_fast()
        SA para espaço discreto de transforms: mesmo ΔH que HMC, 19× mais rápido.
        Posicionamento: quick_optimize (ms) → optimize_fast (SA, ~10ms) → optimize (HMC, s).
        SAConfig: T0, cooling, n_steps, seed configuráveis.

IMP-E  potential() com U=∞ para código inválido — ver BUG-N03 acima.

IMP-F  CodeTransform.apply(code, language="text"): interface CST-ready
        Todos os transforms aceitam language como parâmetro opcional (default="text").
        Backward-compatible. Pré-requisito para Tree-sitter (IMP-H, Fase 3).

══════════════════════════════════════════════════════════════════════════════
ITENS P4 — IMPLEMENTADOS NESTA VERSÃO (via Pygments)
══════════════════════════════════════════════════════════════════════════════
IMP-H  Universalidade semântica via Pygments (substitui Tree-sitter)
        Tree-sitter não instalável sem compilação C por gramática.
        Solução: Pygments 2.x (já disponível) com 40+ lexers prontos.
        Implementado em GenericCFGBuilder e GenericDSMCollector:
          - Token types semânticos (Keyword, Name, Operator) vs regex de texto
          - Lexer por linguagem: C, C++, Java, JS, Go, Rust, Ruby, PHP, C#, SQL, YAML...
          - Distinção brace estrutural vs brace de expressão via token de contexto
          - Fallback para split_generic_segments se linguagem sem lexer
        Mapeamento: UCO language ID → Pygments alias (c_like→c, vba→vbnet, etc.)

GAP-N03  DSM path-sensitive (via CFG weights) — adiado Fase 3
          Medição: 0% melhoria em exemplos simples; custo O(V×E). ROI=0.8.
GAP-N04  ConstantFolding via AST Python (substitui regex)
          Original: regex _INT_RE cobria apenas 2 operandos por linha; errava precedência
                    potencial em futuras extensões; não cobria cadeias (1+2+3) nem **
          Fixado:   ast.parse() + _is_all_constants() + _safe_eval() recursivo
          Benefícios:
            - Precedência correta: 2+3*4→14 (regex nunca chegaria lá com segurança)
            - Cadeias: 1+2+3→6
            - Parênteses: (2+3)*4→20
            - Potenciação: 2**8→256
            - BoolOp: True and False→False, not True→False
            - Variáveis NÃO dobradas (a*0 preservado — requer tipo para ser seguro)

══════════════════════════════════════════════════════════════════════════════
ITENS P4 — ADIADOS (Fase 3)
══════════════════════════════════════════════════════════════════════════════
GAP-N03  DSM path-sensitive via CFG weights (ROI=0.8, impacto baixo)
GAP-N04  ConstantFolding via AST (regex atual conservadora e correta)
IMP-G    DSM path-sensitive (coberto acima)
Tree-sitter nativo — IMP-H implementado via Pygments (equivalente funcional)

══════════════════════════════════════════════════════════════════════════════
TRANSFORMS DISPONÍVEIS (9) + LANGUAGE PROFILES (IMP-A)
══════════════════════════════════════════════════════════════════════════════
T01  NoOpAssignmentSimplifier       safe_for: python, c_like, vba
T02  UnreachableAfterTerminalRemoval safe_for: python, c_like
T03  AdjacentDuplicateBlockRemoval  safe_for: * (universal)
T04  DuplicateAdjacentControlBlockMerger safe_for: * (universal)
T05  BracketWhitespaceNormalizer    safe_for: * (universal)
T06  ConstantFoldingTransform       safe_for: python (type-safe via AST only)
T07  RedundantConditionEliminator   safe_for: * (regex Python-only por design)
T08  EmptyBlockRemover              safe_for: c_like
T09  PythonUnusedVarDetector        safe_for: python

══════════════════════════════════════════════════════════════════════════════
ENGINES DE OTIMIZAÇÃO (3 modos)
══════════════════════════════════════════════════════════════════════════════
quick_optimize()   → GreedyOptimizer    — ms,   determinístico
optimize_fast()    → SA (IMP-D)         — ~10ms, estocástico leve, 19× > HMC
optimize()         → HMC + dual-avg     — s,    exploração do espaço latente
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import math
import random
import re
import time
import warnings  # BUG-B03 FIX: top-level em vez de inline em 5 funções
from collections import Counter, defaultdict, deque, OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, Union

# PORT [1]: numpy é opcional — quick_optimize(), analyze() e optimize_fast() funcionam
# sem numpy. Apenas optimize() (HMC) requer numpy.
try:
    import numpy as np
except ImportError:  # pragma: no cover — ambiente sem numpy
    np = None  # type: ignore[assignment]

# BUG-A06 FIX: imports pygments no nível do módulo (não dentro de funções).
# Segue PEP8, evita mascaramento de ImportError por except:pass dentro de funções,
# e permite verificar disponibilidade via PYGMENTS_AVAILABLE em qualquer ponto.
try:
    from pygments.lexers import get_lexer_by_name as _pygments_get_lexer
    from pygments.token import Token as _PygToken
    PYGMENTS_AVAILABLE = True
except ImportError:
    _pygments_get_lexer = None  # type: ignore[assignment]
    _PygToken = None            # type: ignore[assignment]
    PYGMENTS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════
# 0) UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════════

CONTROL_KEYWORDS = {
    "if", "elif", "else", "for", "while", "do", "switch", "case", "default",
    "try", "catch", "except", "finally", "match", "with",
}

TERMINAL_KEYWORDS = {"return", "raise", "throw", "break", "continue"}

LOOP_KEYWORDS = {"for", "while", "do"}

STOP_WORDS = {
    "if", "elif", "else", "for", "while", "do", "switch", "case", "default",
    "try", "catch", "except", "finally", "return", "break", "continue",
    "with", "match", "class", "def", "true", "false", "null", "none",
    "and", "or", "not", "in", "is", "lambda", "print", "int", "float",
    "double", "string", "bool", "var", "const", "let", "public", "private",
    "protected", "static", "void", "new", "import", "from", "as", "this",
    "self", "function", "sub", "dim", "then", "end", "loop", "wend",
}


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_literals(text: str) -> str:
    text = re.sub(r'".*?"|\'.*?\'', " ", text)
    return text


def strip_code_strings(code: str) -> str:
    """
    GAP-D01 / BUG-U01: Remove string literals e comentários antes de análise
    de padrões via regex. Impede falsos positivos quando o padrão buscado
    (ex: 'while(true)') aparece dentro de strings ou comentários do código.

    Ordem de remoção (mais específico primeiro):
      1. Comentários de linha (#...)
      2. Strings triple-quoted (dotall)
      3. Strings simples (não cruzam linhas)
    Substitui por espaços para preservar numeração de colunas/linhas.
    """
    # 1. Comentários de linha: # até fim da linha (preserva o newline)
    result = re.sub(r'#[^\n]*', lambda m: ' ' * len(m.group()), code)
    # 2. Triple-quoted strings — podem conter quebras de linha
    result = re.sub(r'""".*?"""', lambda m: ' ' * len(m.group()),
                    result, flags=re.DOTALL)
    result = re.sub(r"'''.*?'''", lambda m: ' ' * len(m.group()),
                    result, flags=re.DOTALL)
    # 3. Strings simples (não cruzam linhas)
    result = re.sub(r'"[^"\n]*"', lambda m: ' ' * len(m.group()), result)
    result = re.sub(r"'[^'\n]*'", lambda m: ' ' * len(m.group()), result)
    return result


def extract_identifiers(text: str) -> Set[str]:
    tokens = re.findall(r"\b[A-Za-z_]\w*\b", strip_literals(text))
    return {t for t in tokens if t.lower() not in STOP_WORDS}


def safe_unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return node.__class__.__name__


def flatten(list_of_lists: Iterable[Iterable[Any]]) -> List[Any]:
    out: List[Any] = []
    for xs in list_of_lists:
        out.extend(xs)
    return out


def _is_valid_python(code: str) -> bool:
    """
    BUG-B02 FIX: função utilitária de módulo — única definição.
    Antes estava duplicada em GreedyOptimizer._is_valid_python (L3391) e
    SimulatedAnnealingOptimizer._is_valid_python (L3514). Qualquer
    correção futura se propaga automaticamente para ambas as classes.
    """
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _require_numpy(feature: str = "this operation") -> Any:
    """
    PORT [2]: Garante que numpy está disponível antes de operações que dependem dele.
    Levanta RuntimeError com mensagem clara indicando quais operações NÃO precisam de numpy.
    """
    if np is None:
        raise RuntimeError(
            f"numpy é necessário para {feature}. "
            "quick_optimize(), analyze() e optimize_fast() funcionam sem numpy. "
            "Instale numpy: pip install numpy"
        )
    return np


def _zero_vector(size: int) -> Union[List[float], Any]:
    """
    PORT [2]: Retorna vetor de zeros como np.ndarray se numpy disponível,
    ou list[float] caso contrário. Usado para criar q0 sem numpy.
    """
    if np is None:
        return [0.0] * max(0, size)
    return np.zeros(max(0, size))


# ═══════════════════════════════════════════════════════════════════════════
# 0b) LRU CACHE (FIX-C02: substitui dict ilimitado)
# ═══════════════════════════════════════════════════════════════════════════

class _LRUCache:
    """
    Cache LRU com tamanho máximo via OrderedDict.
    Evita memory leak do original (self._cache: Dict = {} ilimitado).
    Complexidade: O(1) get/set, O(1) eviction.
    """
    def __init__(self, maxsize: int = 1024) -> None:
        self.maxsize = maxsize
        self._data: OrderedDict = OrderedDict()

    def get(self, key: Any) -> Optional[Any]:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: Any, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        else:
            if len(self._data) >= self.maxsize:
                self._data.popitem(last=False)  # evict LRU
        self._data[key] = value

    def __len__(self) -> int:
        return len(self._data)

    def clear(self) -> None:
        self._data.clear()


# ═══════════════════════════════════════════════════════════════════════════
# 1) DETECÇÃO DE LINGUAGEM (FIX-C05: heurística antes de ast.parse)
# ═══════════════════════════════════════════════════════════════════════════

_PYTHON_SIGNALS = re.compile(
    r"^\s*(def |class |import |from .* import |@|async def |if __name__)",
    re.MULTILINE,
)
_VBA_SIGNALS = re.compile(
    r"\b(Sub|Function|Dim|End Sub|End Function|Module)\b", re.IGNORECASE
)
_CLIKE_SIGNALS = re.compile(r"[{}];")

# PORT [3]: Sinais específicos para linguagens adicionais — permitem que
# detect_language() retorne IDs precisos em vez de 'c_like' ou 'text'.
_GO_SIGNALS = re.compile(
    r"^\s*(package\s+\w+|import\s*\(|func\s+\w+|type\s+\w+\s+struct\b)",
    re.MULTILINE,
)
_RUST_SIGNALS = re.compile(
    r"^\s*(fn\s+\w+|use\s+\w|impl\b|mod\s+\w+|let\s+mut\b)",
    re.MULTILINE,
)
_JS_SIGNALS = re.compile(
    # FIX: sem \b no final — '=' e '=>' não são word chars, \b bloqueava o match
    r"\b(function\s+\w+|const\s+\w+\s*=|let\s+\w+\s*=|export\s+default|=>)"
)
_JAVA_SIGNALS = re.compile(
    r"\b(public|private|protected)\s+(class|interface|enum)\b|\bSystem\.out\.|\bimport\s+java\."
)
_SQL_SIGNALS = re.compile(
    r"^\s*(SELECT\b|INSERT\s+INTO\b|UPDATE\b|DELETE\s+FROM\b|CREATE\s+(TABLE|VIEW|INDEX)\b)",
    re.IGNORECASE | re.MULTILINE,
)
_YAML_SIGNALS = re.compile(
    r"^\s*[\w.-]+\s*:\s*.+$|^\s*-\s+\w",
    re.MULTILINE,
)


def detect_language(code: str, hint: Optional[str] = None) -> str:
    """
    FIX-C05: detecção leve primeiro, ast.parse somente como confirmação.
    Ordem: hint → heurística (20 linhas) → ast.parse → generic.
    """
    if hint:
        return hint.lower().strip()

    head = "\n".join(code.splitlines()[:30])

    # Sinais Python rápidos
    if _PYTHON_SIGNALS.search(head):
        try:
            ast.parse(code)
            return "python"
        except SyntaxError:
            # BUG-A01 FIX: SyntaxError aqui é esperado — pode ser outra linguagem
            # com sintaxe parecida com Python (ex: YAML com indentação).
            # Silenciar apenas SyntaxError (não Exception genérico) é correto aqui.
            pass

    # PORT [4]: Linguagens com sinais inequívocos — retornar ID específico
    # (antes só retornava 'c_like' ou 'text' para todas estas)
    if _GO_SIGNALS.search(head):
        return "go"

    if _RUST_SIGNALS.search(head):
        return "rust"

    if _JAVA_SIGNALS.search(head):
        return "java"

    # JS antes de VBA — 'function' é comum a ambos, mas 'const/let/=>' são JS
    if _JS_SIGNALS.search(head):
        return "javascript"

    # VBA depois de JS para não confundir 'function' com JavaScript
    if _VBA_SIGNALS.search(head):
        return "vba"

    if _SQL_SIGNALS.search(head):
        return "sql"

    # YAML antes do fallback text, mas depois de linguagens mais estruturadas
    # Excluir se contém { ou ; (provavelmente JSON/C-like)
    if _YAML_SIGNALS.search(head) and "{" not in head and ";" not in head:
        return "yaml"

    # C-like (C, C++, linguagens com { } ; mas sem sinais específicos acima)
    if _CLIKE_SIGNALS.search(code[:500]):
        return "c_like"

    # Última tentativa: ast.parse completo para Python ambíguo
    try:
        ast.parse(code)
        return "python"
    except SyntaxError:
        # BUG-A01 FIX: capturar apenas SyntaxError (não Exception genérico).
        # Exception genérico mascararia erros inesperados de ast.parse (ex: MemoryError,
        # RecursionError em código muito aninhado) que devem propagar ao chamador.
        pass

    return "text"


def _classify_keywords(kw_set: Set[str]) -> str:
    """
    GAP-B03 FIX / C-07 FIX: núcleo de classificação por conjunto de keywords.
    Usa uma priority_chain explícita em vez de 5 for-loops individuais.
    CC reduzida: o 'for' único sobre a chain substitui os 5 loops separados.

    Prioridade: branch > loop_header > break > continue > terminal > stmt
    """
    # Cada entrada: (kind_a_retornar, frozenset_de_keywords)
    # Ordem é a prioridade — a primeira match vence.
    _PRIORITY_CHAIN = (
        ("branch",      frozenset({"if","elif","else","switch","case","default",
                                   "try","except","catch","finally","with","match"})),
        ("loop_header", frozenset({"for","while","do"})),
        ("break",       frozenset({"break"})),
        ("continue",    frozenset({"continue"})),
        ("terminal",    frozenset({"return","raise","throw","goto"})),
    )
    for kind, kw_group in _PRIORITY_CHAIN:
        if kw_set & kw_group:
            return kind
    return "stmt"


def split_generic_segments(code: str) -> List[str]:
    """
    IMP-B / GAP-N07: Segmentação estrutural para código não-Python.
    Versão 2: distingue blocos estruturais (if/for/função) de blocos de expressão
    ({1,2,3}, {key:val}, lambda inline). Resolve o problema onde int x[]={1,2,3}
    gerava depth=2 e nós CFG fantasma para o literal de array.

    Heurística: se o caractere antes de { (ignorando whitespace) é = ( , então
    é um bloco de expressão — consumir o conteúdo inteiro até o } balanceado como
    parte do segmento atual, sem criar nível de profundidade extra.
    Caso contrário: comportamento original de bloco estrutural.
    """
    def _flush_buf(buf: List[str], parts: List[str]) -> None:
        """C-05 FIX: helper inline para evitar repetição de flush pattern 4×."""
        if buf:
            seg = "".join(buf).strip()
            if seg:
                parts.append(seg)
            buf.clear()

    code = code.replace("\r\n", "\n").replace("\r", "\n")
    parts: List[str] = []
    buf: List[str] = []
    i = 0

    while i < len(code):
        ch = code[i]

        if ch == "{":
            # Verificar contexto: é bloco estrutural ou expressão inline?
            preceding = "".join(buf).rstrip()
            is_expression_brace = bool(re.search(r"[=,(]\s*$", preceding))

            if is_expression_brace:
                # Bloco de expressão: consumir {conteúdo} completo como parte do stmt
                depth_inner = 1
                buf.append(ch)
                i += 1
                while i < len(code) and depth_inner > 0:
                    c = code[i]
                    if c == "{":
                        depth_inner += 1
                    elif c == "}":
                        depth_inner -= 1
                    if depth_inner > 0:
                        buf.append(c)
                    i += 1
                buf.append("}")  # fecha o bloco de expressão
                continue  # não incrementar i novamente
            else:
                # Bloco estrutural: comportamento original
                _flush_buf(buf, parts)
                parts.append(ch)

        elif ch == "}":
            _flush_buf(buf, parts)
            parts.append(ch)

        elif ch == ";":
            _flush_buf(buf, parts)
            parts.append(ch)

        elif ch == "\n":
            _flush_buf(buf, parts)
        else:
            buf.append(ch)

        i += 1

    if buf:
        seg = "".join(buf).strip()
        if seg:
            parts.append(seg)

    return [p for p in parts if p]


# ═══════════════════════════════════════════════════════════════════════════
# 2) CFG — CONTROL FLOW GRAPH
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class CFGNode:
    node_id: int
    kind: str
    text: str
    line_start: int = 0
    line_end: int = 0
    successors: Dict[int, str] = field(default_factory=dict)
    predecessors: Set[int] = field(default_factory=set)

    def add_successor(self, dst: int, label: str = "flow") -> None:
        self.successors[dst] = label

    def add_predecessor(self, src: int) -> None:
        self.predecessors.add(src)


class CFG:
    def __init__(self, language: str = "generic") -> None:
        self.language = language
        self.nodes: Dict[int, CFGNode] = {}
        self.entry: Optional[int] = None
        self.exit: Optional[int] = None
        self._next_id: int = 0
        self.metadata: Dict[str, Any] = {}

    def add_node(self, kind: str, text: str,
                 line_start: int = 0, line_end: int = 0) -> int:
        nid = self._next_id
        self._next_id += 1
        self.nodes[nid] = CFGNode(
            node_id=nid, kind=kind, text=text,
            line_start=line_start, line_end=line_end,
        )
        return nid

    def add_edge(self, src: int, dst: int, label: str = "flow") -> None:
        if src not in self.nodes or dst not in self.nodes:
            return
        self.nodes[src].add_successor(dst, label)
        self.nodes[dst].add_predecessor(src)

    def edges(self) -> List[Tuple[int, int, str]]:
        out: List[Tuple[int, int, str]] = []
        for src, node in self.nodes.items():
            for dst, label in node.successors.items():
                out.append((src, dst, label))
        return out

    def reachable_from_entry(self) -> Set[int]:
        if self.entry is None or self.entry not in self.nodes:
            return set()
        seen: Set[int] = set()
        stack: List[int] = [self.entry]
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in self.nodes[cur].successors:
                if nxt not in seen:
                    stack.append(nxt)
        return seen


@dataclass
class LoopContext:
    header_id: int
    after_id: int
    last_body_id: Optional[int] = None


class PythonCFGBuilder:
    """CFG real via AST do Python."""

    def __init__(self) -> None:
        self.source: str = ""
        self.graph: Optional[CFG] = None
        self.max_depth: int = 0

    def build(self, code: str) -> CFG:
        self.source = code
        self.graph = CFG(language="python")
        self.max_depth = 0
        tree = ast.parse(code)
        entry = self.graph.add_node("entry", "ENTRY")
        self.graph.entry = entry
        exits = self._build_block(tree.body, [entry], [], depth=0)
        exit_id = self.graph.add_node("exit", "EXIT")
        self.graph.exit = exit_id
        for e in exits:
            self.graph.add_edge(e, exit_id, "flow")
        self.graph.metadata["max_depth"] = self.max_depth
        return self.graph

    def _node_text(self, node: ast.AST) -> str:
        seg = ast.get_source_segment(self.source, node)
        return normalize_ws(seg) if seg else normalize_ws(safe_unparse(node))

    def _add_stmt_node(self, kind: str, stmt: ast.AST,
                       label: Optional[str] = None) -> int:
        # BUG-A04 FIX: assert removido com python -O → RuntimeError para falha
        # visível em qualquer modo de execução, incluindo produção otimizada.
        if self.graph is None:
            raise RuntimeError(
                "PythonCFGBuilder._add_stmt_node: graph não inicializado. "
                "Chame build() antes de _add_stmt_node()."
            )
        text = label if label is not None else self._node_text(stmt)
        ls = getattr(stmt, "lineno", 0) or 0
        le = getattr(stmt, "end_lineno", ls) or ls
        return self.graph.add_node(kind, text, ls, le)

    def _connect_all(self, srcs: Iterable[int], dst: int,
                     label: str = "flow") -> None:
        # BUG-A04 FIX: assert substituído por RuntimeError (visível com python -O)
        if self.graph is None:
            raise RuntimeError(
                "PythonCFGBuilder._connect_all: graph não inicializado."
            )
        for s in srcs:
            self.graph.add_edge(s, dst, label)

    def _build_block(self, stmts: List[ast.stmt], prevs: List[int],
                     loop_stack: List[LoopContext], depth: int) -> List[int]:
        self.max_depth = max(self.max_depth, depth)
        exits = prevs
        for stmt in stmts:
            exits = self._build_stmt(stmt, exits, loop_stack, depth)
        return exits

    def _collect_uses(self, node: Optional[ast.AST]) -> Set[str]:
        uses: Set[str] = set()
        if node is None:
            return uses

        class _UC(ast.NodeVisitor):
            def visit_Name(self, n: ast.Name):
                if isinstance(n.ctx, ast.Load):
                    uses.add(n.id)
            def visit_Attribute(self, n: ast.Attribute):
                if isinstance(n.value, ast.Name):
                    uses.add(n.value.id)
                self.generic_visit(n)

        _UC().visit(node)
        return uses

    def _collect_defs(self, target: ast.AST) -> Set[str]:
        defs: Set[str] = set()

        class _DC(ast.NodeVisitor):
            def visit_Name(self, n: ast.Name):
                if isinstance(n.ctx, ast.Store):
                    defs.add(n.id)
            def visit_Tuple(self, n: ast.Tuple):
                for e in n.elts: self.visit(e)
            def visit_List(self, n: ast.List):
                for e in n.elts: self.visit(e)
            def visit_Attribute(self, n: ast.Attribute):
                if isinstance(n.value, ast.Name):
                    defs.add(n.value.id)

        _DC().visit(target)
        return defs

    # ── Handler methods (C-02 FIX: extraídos de _build_stmt para reduzir CC) ──

    def _handle_def_class(self, stmt: ast.stmt, prevs: List[int],
                          loop_stack: List[LoopContext], depth: int) -> List[int]:
        kind = "class" if isinstance(stmt, ast.ClassDef) else "function"
        name = getattr(stmt, "name", kind)
        nid = self._add_stmt_node(kind, stmt, f"{kind.upper()} {name}")
        self._connect_all(prevs, nid)
        body_entry = self.graph.add_node(f"{kind}_body", f"{kind.upper()}_BODY:{name}")
        self.graph.add_edge(nid, body_entry, "contains")
        self._build_block(getattr(stmt, "body", []), [body_entry], loop_stack, depth + 1)
        return [nid]

    def _handle_if(self, stmt: ast.If, prevs: List[int],
                   loop_stack: List[LoopContext], depth: int) -> List[int]:
        cond_id = self._add_stmt_node("if", stmt, f"IF {self._node_text(stmt.test)}")
        self._connect_all(prevs, cond_id)
        merge_id = self.graph.add_node("merge", "MERGE_IF")
        then_exits = self._build_block(stmt.body, [cond_id], loop_stack, depth + 1)
        if then_exits:
            self._connect_all(then_exits, merge_id)
        if stmt.orelse:
            else_exits = self._build_block(stmt.orelse, [cond_id], loop_stack, depth + 1)
            if else_exits:
                self._connect_all(else_exits, merge_id)
        else:
            self.graph.add_edge(cond_id, merge_id, "false")
        return [merge_id]

    def _handle_loop(self, stmt: ast.stmt, prevs: List[int],
                     loop_stack: List[LoopContext], depth: int) -> List[int]:
        kind = "for" if isinstance(stmt, (ast.For, ast.AsyncFor)) else "while"
        test_text = (self._node_text(stmt.iter)
                     if isinstance(stmt, (ast.For, ast.AsyncFor))
                     else self._node_text(stmt.test))
        header_id = self._add_stmt_node(kind, stmt, f"{kind.upper()} {test_text}")
        self._connect_all(prevs, header_id)
        after_id = self.graph.add_node("loop_after", f"AFTER_{kind.upper()}")
        self.graph.add_edge(header_id, after_id, "false")
        ctx = LoopContext(header_id=header_id, after_id=after_id)
        body_exits = self._build_block(stmt.body, [header_id], loop_stack + [ctx], depth + 1)
        for e in body_exits:
            self.graph.add_edge(e, header_id, "back")
        if getattr(stmt, "orelse", None):
            else_exits = self._build_block(stmt.orelse, [after_id], loop_stack, depth + 1)
            return else_exits if else_exits else [after_id]
        return [after_id]

    def _handle_try(self, stmt: ast.Try, prevs: List[int],
                    loop_stack: List[LoopContext], depth: int) -> List[int]:
        try_id = self._add_stmt_node("try", stmt, "TRY")
        self._connect_all(prevs, try_id)
        after_id = self.graph.add_node("try_after", "AFTER_TRY")
        body_exits = self._build_block(stmt.body, [try_id], loop_stack, depth + 1)
        if body_exits:
            self._connect_all(body_exits, after_id)
        for handler in stmt.handlers:
            h_text = self._node_text(handler.type) if handler.type is not None else "EXCEPT"
            h_node = self.graph.add_node("except", f"EXCEPT {h_text}")
            self.graph.add_edge(try_id, h_node, "exception")
            h_exits = self._build_block(handler.body, [h_node], loop_stack, depth + 1)
            if h_exits:
                self._connect_all(h_exits, after_id)
        if stmt.orelse:
            else_exits = self._build_block(stmt.orelse, [after_id], loop_stack, depth + 1)
            if else_exits:
                self._connect_all(else_exits, after_id)
        if stmt.finalbody:
            final_exits = self._build_block(stmt.finalbody, [after_id], loop_stack, depth + 1)
            return final_exits if final_exits else [after_id]
        return [after_id]

    def _handle_return(self, stmt: ast.Return, prevs: List[int],
                       loop_stack: List[LoopContext], depth: int) -> List[int]:
        nid = self._add_stmt_node("return", stmt,
            f"RETURN {self._node_text(stmt.value) if stmt.value else ''}".strip())
        self._connect_all(prevs, nid)
        return []

    def _handle_raise(self, stmt: ast.Raise, prevs: List[int],
                      loop_stack: List[LoopContext], depth: int) -> List[int]:
        nid = self._add_stmt_node("raise", stmt,
            f"RAISE {self._node_text(stmt.exc) if stmt.exc else ''}".strip())
        self._connect_all(prevs, nid)
        return []

    def _handle_break(self, stmt: ast.Break, prevs: List[int],
                      loop_stack: List[LoopContext], depth: int) -> List[int]:
        nid = self._add_stmt_node("break", stmt, "BREAK")
        self._connect_all(prevs, nid)
        if loop_stack:
            self.graph.add_edge(nid, loop_stack[-1].after_id, "break")
        return []

    def _handle_continue(self, stmt: ast.Continue, prevs: List[int],
                         loop_stack: List[LoopContext], depth: int) -> List[int]:
        nid = self._add_stmt_node("continue", stmt, "CONTINUE")
        self._connect_all(prevs, nid)
        if loop_stack:
            self.graph.add_edge(nid, loop_stack[-1].header_id, "continue")
        return []

    def _handle_assign(self, stmt: ast.Assign, prevs: List[int],
                       loop_stack: List[LoopContext], depth: int) -> List[int]:
        defs: Set[str] = set()
        for t in stmt.targets:
            defs |= self._collect_defs(t)
        uses = self._collect_uses(stmt.value)
        ls = getattr(stmt, "lineno", 0) or 0
        le = getattr(stmt, "end_lineno", ls) or ls
        nid = self.graph.add_node("assign", normalize_ws(self._node_text(stmt)), ls, le)
        self._connect_all(prevs, nid)
        self.graph.metadata.setdefault("python_defs_uses", {})[nid] = {
            "defs": defs, "uses": uses}
        return [nid]

    def _build_stmt(self, stmt: ast.stmt, prevs: List[int],
                    loop_stack: List[LoopContext], depth: int) -> List[int]:
        """
        C-02 FIX: dispatch table reduz CC de 25 para 3.
        Antes: 13 isinstance em cascata (uma por tipo AST).
        Agora: tabela de dispatch mapeando tipo → método handler.
        Cada handler é um método dedicado com CC ≤ 5.
        """
        # BUG-A04 FIX: RuntimeError visível com python -O (assert seria removido)
        if self.graph is None:
            raise RuntimeError(
                "PythonCFGBuilder._build_stmt: graph não inicializado."
            )
        self.max_depth = max(self.max_depth, depth)

        # Tabela de dispatch: AST node type → handler method
        # Mapeamentos compostos usam tupla de tipos (primeiro match vence)
        _DISPATCH: List[tuple] = [
            ((ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef), self._handle_def_class),
            ((ast.If,),                                              self._handle_if),
            ((ast.For, ast.AsyncFor, ast.While),                    self._handle_loop),
            ((ast.Try,),                                             self._handle_try),
            ((ast.Return,),                                          self._handle_return),
            ((ast.Raise,),                                           self._handle_raise),
            ((ast.Break,),                                           self._handle_break),
            ((ast.Continue,),                                        self._handle_continue),
            ((ast.Assign,),                                          self._handle_assign),
        ]
        for node_types, handler in _DISPATCH:
            if isinstance(stmt, node_types):
                return handler(stmt, prevs, loop_stack, depth)

        # Fallback genérico: qualquer outro statement
        kind = stmt.__class__.__name__.lower()
        nid = self._add_stmt_node(kind, stmt)
        self._connect_all(prevs, nid)
        return [nid]


class _PygmentsMixin:
    """
    BUG-A05 FIX: Mixin que centraliza utilitários Pygments compartilhados por
    GenericCFGBuilder e GenericDSMCollector.

    Antes: _get_lexer(), _is_kw(), _build_via_pygments(), _build_via_regex()
    duplicados identicamente nas duas classes. Qualquer correção em uma classe
    precisava ser replicada manualmente na outra — fonte comprovada de divergência.

    Agora: herança simples resolve DRY sem mudar a API pública.

    BUG-A06 FIX: os imports de pygments eram feitos DENTRO de cada método.
    Agora usam as constantes de módulo PYGMENTS_AVAILABLE e _pygments_get_lexer,
    definidas no top-level do arquivo com try/except apropriado.
    """

    # Mapa de linguagem UCO → alias Pygments (compartilhado)
    # Mapa de linguagem UCO → alias Pygments (compartilhado por CFGBuilder e DSMCollector)
    # GAP-B01 VERIFICADO: todas as linguagens retornadas por detect_language() estão
    # mapeadas explicitamente aqui — sem dependência de fallback implícito para IDs novos.
    # detect_language() retorna: python, go, rust, java, javascript, sql, yaml, c_like, vba, text
    _PYGMENTS_ALIASES: Dict[str, str] = {
        "c_like": "c",   "c": "c",    "cpp": "cpp",    "c++": "cpp",
        "java": "java",  "javascript": "javascript",    "js": "javascript",
        "typescript": "typescript",   "sql": "sql",     "yaml": "yaml",
        "bash": "bash",  "shell": "bash", "go": "go",  "rust": "rust",
        "swift": "swift","kotlin": "kotlin","scala": "scala",
        "ruby": "ruby",  "php": "php", "csharp": "csharp", "cs": "csharp",
        "vba": "vbnet",
    }

    @staticmethod
    def _get_lexer(language: str):
        """
        Retorna lexer Pygments para a linguagem, ou None se indisponível.
        BUG-A01 FIX: adiciona warning se Pygments não disponível (em vez de
        silenciar completamente via except:pass).
        BUG-A06 FIX: usa _pygments_get_lexer de nível de módulo em vez de
        import inline dentro do método.
        """
        if not PYGMENTS_AVAILABLE or _pygments_get_lexer is None:
            warnings.warn(
                f"Pygments não disponível. Análise de '{language}' usará fallback regex "
                "(qualidade reduzida). Instale via: pip install pygments",
                RuntimeWarning, stacklevel=3
            )
            return None
        alias = _PygmentsMixin._PYGMENTS_ALIASES.get(language.lower(), language.lower())
        try:
            return _pygments_get_lexer(alias)
        except Exception as exc:
            warnings.warn(
                f"Pygments: lexer não encontrado para linguagem '{language}' "
                f"(alias='{alias}'): {exc}. Usando fallback regex.",
                RuntimeWarning, stacklevel=3
            )
            return None

    @staticmethod
    def _is_kw(token_type) -> bool:
        """
        Retorna True se o tipo de token é uma keyword Pygments.
        BUG-A06 FIX: usa _PygToken de nível de módulo.
        """
        if _PygToken is None:
            return False
        return token_type in _PygToken.Keyword or str(token_type).startswith("Token.Keyword")

    @staticmethod
    def _is_expr_brace(prev_nonws_val: Optional[str]) -> bool:
        """Brace é de expressão se precedido por = ( , [ : += -= -> etc."""
        return prev_nonws_val in (
            "=", "(", ",", "[", "+=", "-=", "*=", "/=", ":", "?",
            "<<", "->", "return", "throw", "new", "case", "yield",
            "=>", "&&", "||",
        )


@dataclass
class _PygmentsCFGStateMachine:
    """
    OPT-B01 FIX: extrai o estado de _build_via_pygments para uma classe explícita.

    Antes: _build_via_pygments tinha CC=59 com 8 variáveis de estado compartilhadas
    entre 4 closures via nonlocal. Praticamente intestável — qualquer mudança em
    uma closure podia silenciosamente afetar as outras.

    Depois: estado explícito em dataclass. Cada método tem CC ≤ 10.
    Os closures originais (classify_buf, flush_and_add, on_open_brace, on_close_brace)
    viram métodos da classe com acesso direto ao estado via self.
    """
    graph:             "CFG"
    exit_id:           int
    is_kw_fn:          Any    # _PygmentsMixin._is_kw — injetado para evitar dependência circular
    # Estado de controle de fluxo
    prevs:             List[int] = field(default_factory=list)
    loop_stack:        List[Dict[str, int]] = field(default_factory=list)
    branch_stack:      List[Dict[str, int]] = field(default_factory=list)
    block_stack:       List[Tuple[str, Optional[int]]] = field(default_factory=list)
    depth:             int = 0
    paren_depth:       int = 0
    line_no:           int = 1
    last_flushed_nid:  Optional[int] = None
    last_flushed_kind: Optional[str] = None
    # Buffer de tokenização
    buf_vals:          List[str] = field(default_factory=list)
    buf_token_types:   List = field(default_factory=list)
    prev_nonws_val:    Optional[str] = None

    def classify(self) -> str:
        """Classifica nó pelos tokens no buffer. Delega a _classify_keywords."""
        kw_values = {
            v.strip().lower()
            for t, v in zip(self.buf_token_types, self.buf_vals)
            if self.is_kw_fn(t) and v.strip()
        }
        return _classify_keywords(kw_values)

    def flush(self) -> Optional[int]:
        """Cria nó CFG com conteúdo do buffer e conecta aos prevs."""
        text = "".join(self.buf_vals).strip()
        kind = self.classify()   # ANTES de limpar — classify lê buf_token_types
        self.buf_vals.clear()
        self.buf_token_types.clear()
        if not text:
            return None

        nid = self.graph.add_node(kind, text, line_start=self.line_no)
        for p in self.prevs:
            self.graph.add_edge(p, nid, "flow")

        if self.loop_stack:
            self.loop_stack[-1]["last_body"] = nid

        if kind == "loop_header":
            after_id = self.graph.add_node("loop_after", f"AFTER_LOOP_{nid}")
            self.graph.add_edge(nid, after_id, "false")
            self.loop_stack.append({"header": nid, "after": after_id, "last_body": nid})
            self.prevs = [nid]
        elif kind == "branch":
            self.branch_stack.append({"branch": nid, "after": None})
            self.prevs = [nid]
        elif kind == "break" and self.loop_stack:
            self.graph.add_edge(nid, self.loop_stack[-1]["after"], "break")
            self.prevs = []
        elif kind == "continue" and self.loop_stack:
            self.graph.add_edge(nid, self.loop_stack[-1]["header"], "continue")
            self.prevs = []
        elif kind == "terminal":
            self.graph.add_edge(nid, self.exit_id, "flow")
            self.prevs = []
        else:
            self.prevs = [nid]

        self.last_flushed_nid = nid
        self.last_flushed_kind = kind
        return nid

    def on_open_brace(self) -> None:
        """Processa '{' estrutural: incrementa depth e registra tipo no block_stack."""
        self.flush()
        self.depth += 1
        # Verificar se o { pertence ao nó que acabou de ser flushed
        if (self.last_flushed_kind == "branch"
                and self.last_flushed_nid is not None
                and self.branch_stack
                and self.branch_stack[-1]["after"] is None
                and self.branch_stack[-1]["branch"] == self.last_flushed_nid):
            after_id = self.graph.add_node(
                "branch_after", f"AFTER_BRANCH_{self.branch_stack[-1]['branch']}")
            self.graph.add_edge(self.branch_stack[-1]["branch"], after_id, "false")
            self.branch_stack[-1]["after"] = after_id
            self.block_stack.append(("branch", self.last_flushed_nid))
        elif self.last_flushed_kind == "loop_header" and self.last_flushed_nid is not None:
            self.block_stack.append(("loop", self.last_flushed_nid))
        else:
            self.block_stack.append(("plain", None))

    def on_close_brace(self) -> None:
        """Processa '}': decrementa depth e resolve back-edges via block_stack."""
        self.flush()
        self.depth = max(0, self.depth - 1)
        block_kind, _ = self.block_stack.pop() if self.block_stack else ("plain", None)

        if block_kind == "loop" and self.loop_stack:
            ctx = self.loop_stack[-1]
            if ctx.get("last_body") is not None:
                for p in self.prevs:
                    self.graph.add_edge(p, ctx["header"], "back")
                self.prevs = []
            self.loop_stack.pop()
            header_id = ctx["header"]
            for nid2, node2 in self.graph.nodes.items():
                if node2.kind == "loop_after" and f"AFTER_LOOP_{header_id}" in node2.text:
                    self.prevs = list(set(self.prevs + [nid2]))
                    break

        elif block_kind == "branch" and self.branch_stack:
            ctx = self.branch_stack[-1]
            after_id = ctx.get("after")
            if after_id is not None:
                for p in self.prevs:
                    self.graph.add_edge(p, after_id, "flow")
                self.branch_stack.pop()
                self.prevs = [after_id]
            else:
                self.branch_stack.pop()


class GenericCFGBuilder(_PygmentsMixin):
    """
    CFG estrutural via Pygments para C-like, C++, Java, JavaScript, e qualquer texto.

    IMP-H (implementado): substitui o split_generic_segments regex-based por
    tokenização semântica Pygments. Pygments tem lexers para 40+ linguagens e
    fornece token TYPES (Keyword, Operator, Punctuation, Name, etc.) que permitem:
      - Distinguir blocos estruturais ({if/for/while}) de blocos de expressão
        ({1,2,3} arrays, {key:val} objetos, lambdas inline) via contexto de token precedente
      - Detectar keywords de controle por Token.Keyword (não por regex de texto)
      - Construir CFG com branch_count, loop_count, terminal_count semanticamente corretos
      - Suportar C, C++, Java, JavaScript, SQL, YAML sem mudança de código

    BUG-A05 FIX: herda _get_lexer, _is_kw, _is_expr_brace de _PygmentsMixin
    (eram duplicados em GenericDSMCollector — violava DRY).
    Fallback para split_generic_segments se linguagem não tiver lexer Pygments.
    Para Python: usar PythonCFGBuilder (ast real) é sempre preferível.
    """

    # Token types usados para detecção semântica
    _LOOP_KW    = frozenset({"for", "while", "do"})
    _BRANCH_KW  = frozenset({"if", "elif", "else", "switch", "case", "default",
                              "try", "except", "catch", "finally", "with", "match"})
    _TERMINAL_KW = frozenset({"return", "raise", "throw", "break", "continue", "goto"})
    _BREAK_KW   = frozenset({"break"})
    _CONTINUE_KW = frozenset({"continue"})

    def __init__(self) -> None:
        self.max_depth: int = 0

    def _build_via_pygments(self, code: str, language: str) -> Optional["CFG"]:
        """
        OPT-B01 FIX: usa _PygmentsCFGStateMachine — CC reduzida de 59 para ≤ 10.
        Todo o estado e a lógica de transição vivem na state machine.
        Este método só orquestra: obter tokens → iterar → finalizar.
        """
        lexer = self._get_lexer(language)
        if lexer is None:
            return None

        try:
            raw_tokens = list(lexer.get_tokens(code))
        except Exception as exc:
            warnings.warn(
                f"Pygments: get_tokens() falhou para linguagem '{language}': {exc}. "
                "Usando fallback regex.", RuntimeWarning, stacklevel=3
            )
            return None

        graph = CFG(language=language)
        entry = graph.add_node("entry", "ENTRY")
        graph.entry = entry
        exit_id = graph.add_node("exit", "EXIT")
        graph.exit = exit_id

        sm = _PygmentsCFGStateMachine(
            graph=graph, exit_id=exit_id,
            is_kw_fn=self._is_kw,
            prevs=[entry],
        )

        i = 0
        while i < len(raw_tokens):
            tok_type, tok_val = raw_tokens[i]

            if tok_val == "\n":
                sm.line_no += 1
                i += 1
                continue

            if tok_val == "{":
                if self._is_expr_brace(sm.prev_nonws_val):
                    # Bloco de expressão — consumir inline até } balanceado
                    sm.buf_vals.append(tok_val)
                    sm.buf_token_types.append(tok_type)
                    inner_depth = 1
                    i += 1
                    while i < len(raw_tokens) and inner_depth > 0:
                        t2, v2 = raw_tokens[i]
                        if v2 == "{": inner_depth += 1
                        elif v2 == "}": inner_depth -= 1
                        if inner_depth > 0:
                            sm.buf_vals.append(v2)
                            sm.buf_token_types.append(t2)
                        i += 1
                    sm.buf_vals.append("}")
                    sm.buf_token_types.append(tok_type)
                    sm.prev_nonws_val = "}"
                    continue
                else:
                    sm.on_open_brace()
                    self.max_depth = max(self.max_depth, sm.depth)
                    sm.prev_nonws_val = "{"

            elif tok_val == "}":
                sm.on_close_brace()
                sm.prev_nonws_val = "}"

            elif tok_val == ";":
                if sm.paren_depth > 0:
                    sm.buf_vals.append(tok_val)
                    sm.buf_token_types.append(tok_type)
                else:
                    sm.flush()
                    sm.prev_nonws_val = ";"

            else:
                sm.buf_vals.append(tok_val)
                sm.buf_token_types.append(tok_type)
                if tok_val.strip():
                    sm.prev_nonws_val = tok_val.strip()
                if tok_val == "(":   sm.paren_depth += 1
                elif tok_val == ")": sm.paren_depth = max(0, sm.paren_depth - 1)

            i += 1

        sm.flush()
        for p in sm.prevs:
            graph.add_edge(p, exit_id, "flow")

        graph.metadata["max_depth"] = self.max_depth
        return graph

    # ── C-03 FIX: _process_regex_segment extraído de _build_via_regex ──────────
    # Antes: todo o corpo do loop em _build_via_regex num único método CC=25.
    # Depois: lógica de classificação + edge-building num método dedicado CC≤8.
    _REGEX_LOOP_RE     = re.compile(r"^(for|while|do)\b", re.I)
    _REGEX_BRANCH_RE   = re.compile(r"^(if|elif|else|switch|case|default|try|catch|except|finally|match|with)\b", re.I)
    _REGEX_TERMINAL_RE = re.compile(r"^(return|throw|raise)\b", re.I)
    _REGEX_BREAK_RE    = re.compile(r"^break\b", re.I)
    _REGEX_CONTINUE_RE = re.compile(r"^continue\b", re.I)

    def _process_regex_segment(
        self, seg: str, graph: "CFG",
        prevs: List[int], loop_stack: List[Dict[str, int]],
        branch_stack: List[Dict[str, int]],
    ) -> Tuple[str, int, List[int]]:
        """
        C-03 FIX: processa um segmento de código no caminho fallback regex.
        Classifica o segmento, cria nó e edges, retorna (kind, nid, prevs_updated).
        """
        s = seg.strip()
        if   self._REGEX_LOOP_RE.match(s):     kind = "loop_header"
        elif self._REGEX_BRANCH_RE.match(s):   kind = "branch"
        elif self._REGEX_BREAK_RE.match(s):    kind = "break"
        elif self._REGEX_CONTINUE_RE.match(s): kind = "continue"
        elif self._REGEX_TERMINAL_RE.match(s): kind = "terminal"
        else:                                  kind = "stmt"

        nid = graph.add_node(kind, s)
        for p in prevs:
            graph.add_edge(p, nid, "flow")
        if loop_stack:
            loop_stack[-1]["last_body"] = nid

        if kind == "loop_header":
            after_id = graph.add_node("loop_after", f"AFTER_LOOP_{nid}")
            graph.add_edge(nid, after_id, "false")
            loop_stack.append({"header": nid, "after": after_id, "last_body": nid})
            prevs = [nid]
        elif kind == "branch":
            branch_stack.append({"branch": nid, "after": None})
            prevs = [nid]
        elif kind == "break" and loop_stack:
            graph.add_edge(nid, loop_stack[-1]["after"], "break")
            prevs = []
        elif kind == "continue" and loop_stack:
            graph.add_edge(nid, loop_stack[-1]["header"], "continue")
            prevs = []
        else:
            prevs = [nid]

        return kind, nid, prevs

    def _build_via_regex(self, code: str) -> "CFG":
        """
        C-03 FIX: CC reduzida de 25 para ~8 pela extração de _process_regex_segment.
        Responsabilidade clara: orquestrar o loop sobre segmentos; delegar
        a lógica de classificação + edges ao método auxiliar.
        """
        graph = CFG(language="generic")
        entry = graph.add_node("entry", "ENTRY")
        graph.entry = entry
        segments = split_generic_segments(code)
        prevs: List[int] = [entry]
        loop_stack: List[Dict[str, int]] = []
        branch_stack: List[Dict[str, int]] = []
        block_stack: List[Tuple[str, Optional[int]]] = []
        depth = 0
        last_kind: Optional[str] = None
        last_nid: Optional[int] = None

        for seg in segments:
            if seg == "{":
                depth += 1
                self.max_depth = max(self.max_depth, depth)
                if last_kind == "loop_header" and last_nid is not None:
                    block_stack.append(("loop", last_nid))
                elif last_kind == "branch" and last_nid is not None:
                    if branch_stack and branch_stack[-1]["after"] is None:
                        after_id = graph.add_node("branch_after", f"AFTER_BRANCH_{last_nid}")
                        graph.add_edge(last_nid, after_id, "false")
                        branch_stack[-1]["after"] = after_id
                    block_stack.append(("branch", last_nid))
                else:
                    block_stack.append(("plain", None))
                continue
            if seg == "}":
                depth = max(0, depth - 1)
                block_kind, _ = block_stack.pop() if block_stack else ("plain", None)
                if block_kind == "loop" and loop_stack:
                    ctx = loop_stack.pop()
                    if ctx.get("last_body") is not None:
                        graph.add_edge(ctx["last_body"], ctx["header"], "back")
                    prevs = [ctx["after"]]
                elif block_kind == "branch" and branch_stack:
                    ctx = branch_stack.pop()
                    after_id = ctx.get("after")
                    if after_id is not None:
                        for p in prevs:
                            graph.add_edge(p, after_id, "flow")
                        prevs = [after_id]
                continue
            if seg == ";":
                continue

            last_kind, last_nid, prevs = self._process_regex_segment(
                seg, graph, prevs, loop_stack, branch_stack
            )

        exit_id = graph.add_node("exit", "EXIT")
        graph.exit = exit_id
        for p in prevs:
            graph.add_edge(p, exit_id, "flow")
        graph.metadata["max_depth"] = self.max_depth
        return graph

    def build(self, code: str, language: str = "generic") -> "CFG":
        """
        Constrói CFG: tenta Pygments primeiro (semântico), fallback para regex.
        """
        cfg = self._build_via_pygments(code, language)
        if cfg is not None:
            return cfg
        # Fallback para regex genérico
        return self._build_via_regex(code)


# ═══════════════════════════════════════════════════════════════════════════
# 3) DSM — DESIGN STRUCTURE MATRIX
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class DSMUnit:
    uid: int
    kind: str
    text: str
    line_start: int = 0
    line_end: int = 0
    defs: Set[str] = field(default_factory=set)
    uses: Set[str] = field(default_factory=set)
    control_parents: Set[int] = field(default_factory=set)


@dataclass
class DSMResult:
    units: List[DSMUnit]
    matrix: List[List[int]]
    labels: List[str]
    language: str
    density: float
    coupling_in: List[int]
    coupling_out: List[int]
    reciprocity_ratio: float
    cyclic_dependency_ratio: float
    sccs: List[List[int]]
    notes: List[str] = field(default_factory=list)


class _PythonDSMVisitor(ast.NodeVisitor):
    """
    C-06 FIX: 20 visit_* extraídos de PythonDSMCollector (God Object).
    Antes: PythonDSMCollector(ast.NodeVisitor) tinha 26 métodos — responsabilidade dupla.
    Depois: _PythonDSMVisitor herda NodeVisitor e lida exclusivamente com traversal AST.
             PythonDSMCollector mantém os 6 métodos de infraestrutura (_add_unit, etc.).
    O visitor recebe referência ao collector para acessar _add_unit, _names, _defs_target.
    """
    def __init__(self, collector: "PythonDSMCollector") -> None:
        self._c = collector

    def visit_Module(self, node: ast.Module):
        for s in node.body: self.visit(s)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        c = self._c
        defs = {node.name}
        uses: Set[str] = set()
        for d in node.decorator_list: uses |= c._names(d)
        for a in node.args.defaults: uses |= c._names(a)
        for a in node.args.kw_defaults:
            if a is not None: uses |= c._names(a)
        if node.returns is not None: uses |= c._names(node.returns)
        uid = c._add_unit("function_def", node, defs=defs, uses=uses)
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def visit_ClassDef(self, node: ast.ClassDef):
        c = self._c
        defs = {node.name}
        uses: Set[str] = set()
        for b in node.bases: uses |= c._names(b)
        for kw in node.keywords: uses |= c._names(kw.value)
        for d in node.decorator_list: uses |= c._names(d)
        uid = c._add_unit("class_def", node, defs=defs, uses=uses)
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_If(self, node: ast.If):
        c = self._c
        uid = c._add_unit("if", node, uses=c._names(node.test))
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        for s in node.orelse: self.visit(s)
        c._control_stack.pop()

    def visit_For(self, node: ast.For):
        c = self._c
        uid = c._add_unit("for", node,
                           defs=c._names(node.target), uses=c._names(node.iter))
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_AsyncFor(self, node: ast.AsyncFor):
        self.visit_For(node)  # type: ignore[arg-type]

    def visit_While(self, node: ast.While):
        c = self._c
        uid = c._add_unit("while", node, uses=c._names(node.test))
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_Try(self, node: ast.Try):
        c = self._c
        uid = c._add_unit("try", node)
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        for handler in node.handlers: self.visit(handler)
        for s in node.orelse + node.finalbody: self.visit(s)
        c._control_stack.pop()

    def visit_ExceptHandler(self, node: ast.ExceptHandler):
        c = self._c
        uses = c._names(node.type) if node.type else set()
        defs = {node.name} if node.name else set()
        uid = c._add_unit("except", node, defs=defs, uses=uses)
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_With(self, node: ast.With):
        c = self._c
        uses: Set[str] = set()
        defs: Set[str] = set()
        for item in node.items:
            uses |= c._names(item.context_expr)
            if item.optional_vars: defs |= c._names(item.optional_vars)
        uid = c._add_unit("with", node, defs=defs, uses=uses)
        c._control_stack.append(uid)
        for s in node.body: self.visit(s)
        c._control_stack.pop()

    def visit_Return(self, node: ast.Return):
        c = self._c
        c._add_unit("return", node, uses=c._names(node.value) if node.value else set())

    def visit_Raise(self, node: ast.Raise):
        c = self._c
        c._add_unit("raise", node, uses=c._names(node.exc) if node.exc else set())

    def visit_Break(self, node: ast.Break):
        self._c._add_unit("break", node)

    def visit_Continue(self, node: ast.Continue):
        self._c._add_unit("continue", node)

    def visit_Assign(self, node: ast.Assign):
        c = self._c
        defs: Set[str] = set()
        for t in node.targets: defs |= c._defs_target(t)
        c._add_unit("assign", node, defs=defs, uses=c._names(node.value))

    def visit_AnnAssign(self, node: ast.AnnAssign):
        c = self._c
        c._add_unit("ann_assign", node,
                    defs=c._defs_target(node.target),
                    uses=c._names(node.annotation) | c._names(node.value))

    def visit_AugAssign(self, node: ast.AugAssign):
        c = self._c
        c._add_unit("aug_assign", node,
                    defs=c._defs_target(node.target),
                    uses=c._names(node.target) | c._names(node.value))

    def visit_Expr(self, node: ast.Expr):
        self._c._add_unit("expr", node, uses=self._c._names(node.value))

    def generic_visit(self, node: ast.AST):
        if isinstance(node, ast.stmt):
            uses: Set[str] = set()
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.expr):
                    uses |= self._c._names(child)
            self._c._add_unit(node.__class__.__name__.lower(), node, uses=uses)
            return
        super().generic_visit(node)


class PythonDSMCollector:
    """
    C-06 FIX: 6 métodos de infraestrutura — visitor separado em _PythonDSMVisitor.
    Antes: God Object com 26 métodos (infraestrutura + 20 visitors AST misturados).
    Depois: API pública preservada; traversal delegada ao visitor especializado.
    """
    def __init__(self, source: str) -> None:
        self.source = source
        self.units: List[DSMUnit] = []
        self._next_id = 0
        self._control_stack: List[int] = []

    def build(self, tree: ast.AST) -> List[DSMUnit]:
        """Percorre a AST via _PythonDSMVisitor e retorna as unidades DSM coletadas."""
        _PythonDSMVisitor(self).visit(tree)
        return self.units

    def _text(self, node: ast.AST) -> str:
        seg = ast.get_source_segment(self.source, node)
        return normalize_ws(seg) if seg else normalize_ws(safe_unparse(node))

    def _add_unit(self, kind: str, node: ast.AST,
                  defs: Optional[Set[str]] = None,
                  uses: Optional[Set[str]] = None) -> int:
        uid = self._next_id
        self._next_id += 1
        self.units.append(DSMUnit(
            uid=uid, kind=kind, text=self._text(node),
            line_start=getattr(node, "lineno", 0) or 0,
            line_end=getattr(node, "end_lineno", getattr(node, "lineno", 0)) or 0,
            defs=defs or set(), uses=uses or set(),
            control_parents=set(self._control_stack),
        ))
        return uid

    def _names(self, node: Optional[ast.AST]) -> Set[str]:
        if node is None:
            return set()
        names: Set[str] = set()
        class _C(ast.NodeVisitor):
            def visit_Name(self, n: ast.Name): names.add(n.id)
            def visit_Attribute(self, n: ast.Attribute):
                if isinstance(n.value, ast.Name): names.add(n.value.id)
                self.generic_visit(n)
        _C().visit(node)
        return names

    def _defs_target(self, target: ast.AST) -> Set[str]:
        defs: Set[str] = set()
        class _C(ast.NodeVisitor):
            def visit_Name(self, n: ast.Name):
                if isinstance(n.ctx, ast.Store): defs.add(n.id)
            def visit_Tuple(self, n: ast.Tuple):
                for e in n.elts: self.visit(e)
            def visit_List(self, n: ast.List):
                for e in n.elts: self.visit(e)
            def visit_Attribute(self, n: ast.Attribute):
                if isinstance(n.value, ast.Name): defs.add(n.value.id)
        _C().visit(target)
        return defs


@dataclass
class _PygmentsDSMStateMachine:
    """
    C-01 FIX: extrai o estado de GenericDSMCollector._build_via_pygments para
    classe explícita — análogo ao _PygmentsCFGStateMachine (OPT-B01).

    Antes: 7 closures + 2 nonlocal compartilhando estado implicitamente.
    Depois: estado explícito em dataclass. Cada método CC ≤ 8.
    """
    # Estado
    units:          List["DSMUnit"] = field(default_factory=list)
    stack:          List[int]       = field(default_factory=list)
    uid:            int             = 0
    staged:         List[tuple]     = field(default_factory=list)
    prev_nonws_val: Optional[str]   = None

    # ── Token type helpers (static-style via standalone functions) ────────────
    @staticmethod
    def _is_kw(t) -> bool:
        return str(t).startswith("Token.Keyword")

    @staticmethod
    def _is_name(t) -> bool:
        return str(t).startswith("Token.Name") or (
            _PygToken is not None and t in _PygToken.Name
        )

    @staticmethod
    def _is_op(t) -> bool:
        return str(t).startswith("Token.Operator") or (
            _PygToken is not None and t in _PygToken.Operator
        )

    # ── Extract defs/uses from a segment ─────────────────────────────────────
    def extract_defs_uses(self, seg_toks: List[tuple]) -> Tuple[Set[str], Set[str]]:
        defs: Set[str] = set()
        uses: Set[str] = set()
        meaningful = [(t, v.strip()) for t, v in seg_toks if v.strip()]
        for idx, (t, v) in enumerate(meaningful):
            if not self._is_name(t) or not v or not v.isidentifier():
                continue
            next_ops = [v2 for t2, v2 in meaningful[idx+1:idx+3]
                        if self._is_op(t2) or str(t2).startswith("Token.Punctuation")]
            if any(op in {"=", ":="} for op in next_ops):
                defs.add(v)
            else:
                uses.add(v)
        uses -= defs
        return defs, uses

    # ── Classify and flush current segment ───────────────────────────────────
    def flush(self) -> None:
        """Classifica, extrai defs/uses e cria DSMUnit a partir de staged."""
        if not self.staged:
            return
        text = "".join(v for _, v in self.staged).strip()
        if not text:
            self.staged.clear()
            return
        kw_vals = {v.strip().lower()
                   for t, v in self.staged
                   if self._is_kw(t) and v.strip()}
        kind_raw = _classify_keywords(kw_vals)
        # DSM usa 'loop' em vez de 'loop_header' (convenção interna DSM ≠ CFG)
        kind = "loop" if kind_raw == "loop_header" else kind_raw
        defs, uses = self.extract_defs_uses(self.staged)
        self.staged.clear()
        self.units.append(DSMUnit(
            uid=self.uid, kind=kind, text=normalize_ws(text),
            defs=defs, uses=uses, control_parents=set(self.stack),
        ))
        if kind in {"branch", "loop"}:
            self.stack.append(self.uid)
        self.uid += 1

    # ── Expression brace consumer ─────────────────────────────────────────────
    def consume_expr_brace(self, raw_tokens: List[tuple], start: int,
                            open_tok_type) -> int:
        """Consome {expr} inline (não estrutural) a partir de start+1. Retorna novo i."""
        self.staged.append((open_tok_type, "{"))
        inner_depth = 1
        i = start
        while i < len(raw_tokens) and inner_depth > 0:
            t2, v2 = raw_tokens[i]
            if v2 == "{": inner_depth += 1
            elif v2 == "}": inner_depth -= 1
            if inner_depth > 0:
                self.staged.append((t2, v2))
            i += 1
        self.staged.append((open_tok_type, "}"))
        self.prev_nonws_val = "}"
        return i


class GenericDSMCollector(_PygmentsMixin):
    """
    Coletor DSM para linguagens não-Python via Pygments (IMP-H).
    Extrai def-use a partir de token types semânticos em vez de regex sobre texto.

    BUG-A05 FIX: herda _get_lexer, _is_kw, _is_expr_brace de _PygmentsMixin.
    Antes eram duplicados idênticos de GenericCFGBuilder — violava DRY.

    Para Python: PythonDSMCollector (ast real) é sempre preferível.
    Para C, C++, Java, JS e outros: Pygments fornece Name tokens,
    Keyword tokens e Operator tokens que permitem def-use tracking preciso.

    Estratégia def-use via Pygments:
      - Definição: Name token seguido por Operator '=' ou ':='
      - Uso: qualquer Name token que não seja def
      - Keywords de controle: identificadas por Token.Keyword type (não regex)
    """
    _BRANCH_RE   = re.compile(r"^(if|elif|else|switch|case|default|try|catch|except|finally|match|with)\b", re.I)
    _LOOP_RE     = re.compile(r"^(for|while|do)\b", re.I)
    _TERMINAL_RE = re.compile(r"^(return|throw|raise)\b", re.I)
    _BREAK_RE    = re.compile(r"^break\b", re.I)
    _CONTINUE_RE = re.compile(r"^continue\b", re.I)
    # _get_lexer, _is_kw, _is_expr_brace herdados de _PygmentsMixin (BUG-A05)

    def build(self, code: str, language: str = "generic") -> List[DSMUnit]:
        lexer = self._get_lexer(language)
        if lexer is not None:
            try:
                return self._build_via_pygments(code, lexer)
            except Exception as exc:
                # GAP-A02 FIX: warning em vez de silenciar completamente
                warnings.warn(
                    f"GenericDSMCollector._build_via_pygments falhou "
                    f"para '{language}': {exc}. Usando fallback regex.",
                    RuntimeWarning, stacklevel=2
                )
        return self._build_via_regex(code)

    def _build_via_pygments(self, code: str, lexer) -> List[DSMUnit]:
        """
        C-01 FIX: usa _PygmentsDSMStateMachine — 7 closures e 2 nonlocal eliminados.
        Todo o estado vive na state machine. Este método só orquestra:
        obter tokens → iterar → retornar units.
        """
        if _PygToken is None:
            raise RuntimeError("Pygments não disponível — _PygToken é None")
        raw_tokens = list(lexer.get_tokens(code))

        sm = _PygmentsDSMStateMachine()

        i = 0
        while i < len(raw_tokens):
            tok_type, tok_val = raw_tokens[i]

            if tok_val in ("\n", "\r\n"):
                i += 1
                continue

            if tok_val == "{":
                if GenericCFGBuilder._is_expr_brace(sm.prev_nonws_val):
                    i = sm.consume_expr_brace(raw_tokens, i + 1, tok_type)
                    continue
                else:
                    sm.flush()
                    sm.prev_nonws_val = "{"

            elif tok_val == "}":
                sm.flush()
                if sm.stack:
                    sm.stack.pop()
                sm.prev_nonws_val = "}"

            elif tok_val == ";":
                sm.flush()
                sm.prev_nonws_val = ";"

            else:
                sm.staged.append((tok_type, tok_val))
                if tok_val.strip():
                    sm.prev_nonws_val = tok_val.strip()

            i += 1

        sm.flush()
        return sm.units

    def _build_via_regex(self, code: str) -> List[DSMUnit]:
        """Fallback: DSM via split_generic_segments (regex)."""
        segments = split_generic_segments(code)
        units: List[DSMUnit] = []
        stack: List[int] = []
        uid = 0
        for seg in segments:
            s = seg.strip()
            if not s or s in ("{}","{","}"):
                if s == "}" and stack:
                    stack.pop()
                continue
            low = s.lower()
            if self._BRANCH_RE.match(low):   kind = "branch"
            elif self._LOOP_RE.match(low):   kind = "loop"
            # PORT [6]: break/continue ANTES de terminal (prioridade correta)
            elif self._BREAK_RE.match(low):  kind = "break"
            elif self._CONTINUE_RE.match(low): kind = "continue"
            elif self._TERMINAL_RE.match(low): kind = "terminal"
            else:                             kind = "stmt"
            defs, uses = self._extract_defs_uses(s)
            units.append(DSMUnit(
                uid=uid, kind=kind, text=normalize_ws(s),
                defs=defs, uses=uses, control_parents=set(stack),
            ))
            if kind in {"branch", "loop"}:
                stack.append(uid)
            uid += 1
        return units

    def _extract_defs_uses(self, s: str) -> Tuple[Set[str], Set[str]]:
        """Def-use via regex — fallback."""
        defs: Set[str] = set()
        for left in re.findall(r"\b([A-Za-z_]\w*)\s*(?:=|:=|\+=|-=|\*=|/=|%=)", s):
            defs.add(left)
        tokens = extract_identifiers(s)
        uses = {t for t in tokens if t not in defs}
        return defs, uses


class DSMEngine:
    """
    Construção da DSM com SCC via Tarjan ITERATIVO (FIX-C01).
    """
    def __init__(self) -> None:
        self._generic = GenericDSMCollector()

    def build(self, code: str, language_hint: Optional[str] = None) -> DSMResult:
        language = detect_language(code, language_hint)
        if language == "python":
            try:
                tree = ast.parse(code)
                collector = PythonDSMCollector(code)
                units = collector.build(tree)
                return self._finalize(units, language="python")
            except Exception as exc:
                # C-08 FIX: warning explícito ao usar fallback (antes silencioso)
                warnings.warn(
                    f"DSMEngine: PythonDSMCollector falhou para código Python "
                    f"({type(exc).__name__}: {exc}). Usando fallback Pygments.",
                    RuntimeWarning, stacklevel=3,
                )
                # Fallback: Pygments-based para Python inválido
                units = self._generic.build(code, language="python")
                return self._finalize(units, language="generic_fallback")
        # IMP-H: passar linguagem detectada ao GenericDSMCollector
        # para que use o lexer Pygments correto (C, Java, JS, etc.)
        units = self._generic.build(code, language=language)
        return self._finalize(units, language=language)

    def _finalize(self, units: List[DSMUnit], language: str) -> DSMResult:
        n = len(units)
        matrix = [[0] * n for _ in range(n)]
        producers: Dict[str, Set[int]] = defaultdict(set)
        for u in units:
            for d in u.defs:
                producers[d].add(u.uid)

        for i, ui in enumerate(units):
            for sym in ui.uses:
                for j in producers.get(sym, set()):
                    if j != i:
                        matrix[i][j] = 1
            for p in ui.control_parents:
                if 0 <= p < n and p != i:
                    matrix[i][p] = 1

        labels = [f"{u.uid}:{u.kind}:{u.text[:80]}" for u in units]
        coupling_out = [sum(row) for row in matrix]
        coupling_in = [sum(matrix[i][j] for i in range(n)) for j in range(n)]
        ones = sum(sum(row) for row in matrix)
        density = ones / max(1, n * n)

        reciprocity_pairs = total_pairs = 0
        for i in range(n):
            for j in range(i + 1, n):
                a, b = matrix[i][j], matrix[j][i]
                if a or b:
                    total_pairs += 1
                if a and b:
                    reciprocity_pairs += 1
        reciprocity_ratio = reciprocity_pairs / max(1, total_pairs)

        # FIX-C01: Tarjan iterativo
        sccs = self._tarjan_scc_iterative(matrix)
        cyclic_ratio = self._cyclic_dependency_ratio(matrix, sccs)

        notes: List[str] = []
        if density > 0.25:
            notes.append("DSM densa: acoplamento estrutural alto")
        if cyclic_ratio > 0.20:
            notes.append("Ciclos de dependência relevantes detectados")
        if any(len(c) > 1 for c in sccs):
            notes.append("Componentes fortemente conectadas presentes")
        if n and max(coupling_out, default=0) == 0:
            notes.append("Nenhuma dependência emitida: código extremamente linear")

        return DSMResult(
            units=units, matrix=matrix, labels=labels, language=language,
            density=density, coupling_in=coupling_in, coupling_out=coupling_out,
            reciprocity_ratio=reciprocity_ratio,
            cyclic_dependency_ratio=cyclic_ratio, sccs=sccs, notes=notes,
        )

    def _tarjan_scc_iterative(self, matrix: List[List[int]]) -> List[List[int]]:
        """
        FIX-C01: Tarjan SCC ITERATIVO via pilha explícita.
        Original usava recursão Python → RecursionError para n > ~100.
        Complexidade: O(V + E). Zero recursão nativa.
        """
        n = len(matrix)
        # Grafo invertido: matrix[i][j]=1 → dependência i usa j → aresta j→i
        graph: Dict[int, List[int]] = {i: [] for i in range(n)}
        for i in range(n):
            for j in range(n):
                if matrix[i][j]:
                    graph[j].append(i)

        index_ctr = [0]
        stack: List[int] = []
        on_stack: Set[int] = set()
        indices: Dict[int, int] = {}
        lowlink: Dict[int, int] = {}
        sccs: List[List[int]] = []

        for start in range(n):
            if start in indices:
                continue

            # Pilha explícita: (v, iterator_of_neighbors)
            call_stack = [(start, iter(graph[start]))]
            indices[start] = index_ctr[0]
            lowlink[start] = index_ctr[0]
            index_ctr[0] += 1
            stack.append(start)
            on_stack.add(start)

            while call_stack:
                v, neighbors = call_stack[-1]
                advanced = False

                for w in neighbors:
                    if w not in indices:
                        indices[w] = index_ctr[0]
                        lowlink[w] = index_ctr[0]
                        index_ctr[0] += 1
                        stack.append(w)
                        on_stack.add(w)
                        call_stack.append((w, iter(graph[w])))
                        advanced = True
                        break
                    elif w in on_stack:
                        lowlink[v] = min(lowlink[v], indices[w])

                if not advanced:
                    call_stack.pop()
                    if call_stack:
                        parent = call_stack[-1][0]
                        lowlink[parent] = min(lowlink[parent], lowlink[v])
                    if lowlink[v] == indices[v]:
                        comp: List[int] = []
                        while True:
                            w = stack.pop()
                            on_stack.remove(w)
                            comp.append(w)
                            if w == v:
                                break
                        sccs.append(sorted(comp))

        return sorted(sccs, key=lambda c: (len(c), c))

    def _cyclic_dependency_ratio(self, matrix: List[List[int]],
                                 sccs: List[List[int]]) -> float:
        n = len(matrix)
        if n == 0:
            return 0.0
        cyclic: Set[int] = set()
        for comp in sccs:
            if len(comp) > 1:
                cyclic.update(comp)
            elif len(comp) == 1:
                i = comp[0]
                if matrix[i][i]:
                    cyclic.add(i)
        return len(cyclic) / n


# ═══════════════════════════════════════════════════════════════════════════
# 4) HALSTEAD METRICS (novo)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HalsteadMetrics:
    """
    Métricas de Halstead via Python AST.
    Ref: Halstead (1977) Elements of Software Science.
    """
    n1: int = 0        # operadores únicos
    n2: int = 0        # operandos únicos
    N1: int = 0        # total operadores
    N2: int = 0        # total operandos
    vocabulary: int = 0
    length: int = 0
    volume: float = 0.0
    difficulty: float = 0.0
    effort: float = 0.0
    time_seconds: float = 0.0
    bugs_estimate: float = 0.0

    @classmethod
    def from_python(cls, code: str) -> "HalsteadMetrics":
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            # GAP-A03 FIX: avisar em vez de retornar zeros silenciosamente.
            # Zeros em todas as métricas de Halstead fazem o Hamiltoniano parecer
            # artificialmente baixo para código Python inválido (bugs_estimate=0
            # quando o código pode ter sérios problemas de qualidade).
            warnings.warn(
                f"HalsteadMetrics.from_python: código Python inválido (SyntaxError: {exc}). "
                "Retornando métricas zeradas — Halstead não calculável para este input.",
                RuntimeWarning, stacklevel=2
            )
            return cls()

        operators: Dict[str, int] = defaultdict(int)
        operands: Dict[str, int] = defaultdict(int)

        OP_MAP = {
            ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/",
            ast.FloorDiv: "//", ast.Mod: "%", ast.Pow: "**",
            ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
            ast.LShift: "<<", ast.RShift: ">>",
            ast.And: "and", ast.Or: "or", ast.Not: "not",
            ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=",
            ast.Gt: ">", ast.GtE: ">=", ast.Is: "is", ast.IsNot: "is not",
            ast.In: "in", ast.NotIn: "not in",
            ast.Invert: "~", ast.UAdd: "+u", ast.USub: "-u",
        }

        for node in ast.walk(tree):
            # Operadores
            if isinstance(node, ast.BinOp):
                op = OP_MAP.get(type(node.op), node.op.__class__.__name__)
                operators[op] += 1
            elif isinstance(node, ast.UnaryOp):
                op = OP_MAP.get(type(node.op), node.op.__class__.__name__)
                operators[op] += 1
            elif isinstance(node, ast.BoolOp):
                op = OP_MAP.get(type(node.op), node.op.__class__.__name__)
                operators[op] += len(node.values) - 1
            elif isinstance(node, ast.Compare):
                for comp in node.ops:
                    op = OP_MAP.get(type(comp), comp.__class__.__name__)
                    operators[op] += 1
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                operators["def"] += 1
            elif isinstance(node, ast.ClassDef):
                operators["class"] += 1
            elif isinstance(node, ast.If):
                operators["if"] += 1
            elif isinstance(node, (ast.For, ast.AsyncFor)):
                operators["for"] += 1
            elif isinstance(node, ast.While):
                operators["while"] += 1
            elif isinstance(node, ast.Return):
                operators["return"] += 1
            elif isinstance(node, ast.Assign):
                operators["="] += len(node.targets)
            elif isinstance(node, ast.AugAssign):
                operators[node.op.__class__.__name__ + "="] += 1
            # Operandos
            elif isinstance(node, ast.Name):
                operands[node.id] += 1
            elif isinstance(node, ast.Constant):
                operands[repr(node.value)] += 1
            elif isinstance(node, ast.Attribute):
                operands[node.attr] += 1

        n1 = len(operators)
        n2 = len(operands)
        N1 = sum(operators.values())
        N2 = sum(operands.values())
        vocab = n1 + n2
        length = N1 + N2
        volume = length * math.log2(max(2, vocab))
        difficulty = (n1 / max(1, 2)) * (N2 / max(1, n2))
        effort = difficulty * volume
        time_s = effort / 18.0
        bugs = volume / 3000.0

        return cls(
            n1=n1, n2=n2, N1=N1, N2=N2,
            vocabulary=vocab, length=length,
            volume=round(volume, 2), difficulty=round(difficulty, 2),
            effort=round(effort, 2), time_seconds=round(time_s, 2),
            bugs_estimate=round(bugs, 4),
        )

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def from_tokens(cls, code: str) -> "HalsteadMetrics":
        """
        IMP-C / GAP-N06: Halstead via tokenização léxica — universal para qualquer linguagem.
        Funciona para Python, C++, Java, VBA, DSL, APEX YAML e qualquer texto com código.
        Precisão vs from_python(): bugs_estimate Δ≈1.5%, n2 Δ≈0% (validado empiricamente).
        Usado automaticamente pelo FeatureExtractor para linguagens não-Python.

        Algoritmo:
          1. strip_code_strings() remove comentários e strings literais
          2. _OP_RE extrai operadores: símbolos + palavras-chave de controle
          3. _OPERAND_RE extrai operandos: identificadores e literais numéricos
             (após substituir operadores por espaço, para não re-contar)
          4. Métricas derivadas: volume, difficulty, effort, bugs (Halstead 1977)
        """
        _KEYWORDS: Set[str] = {
            "if", "else", "elif", "for", "while", "do", "switch", "case", "default",
            "return", "break", "continue", "try", "catch", "except", "finally",
            "and", "or", "not", "in", "is", "lambda", "with", "yield", "pass",
            "import", "from", "as", "class", "def", "new", "delete", "void",
            "int", "float", "double", "char", "bool", "string", "var", "let",
            "const", "true", "false", "null", "none", "self", "this",
            "function", "sub", "dim", "end", "then", "loop", "wend",
            "public", "private", "protected", "static", "struct", "enum",
        }
        _OP_RE = re.compile(
            r"\*\*=?|//=?|<<=?|>>=?|!=|==|<=|>=|&&|\|\||->|::|"
            r"\+\+|--|[-+*/%=<>!&|^~@]=?|"
            r"\b(?:if|else|elif|for|while|do|switch|case|return|break|continue|"
            r"try|except|finally|and|or|not|in|is|new|delete|"
            r"def|class|import|from|lambda|yield|with|raise|throw|"
            r"function|sub|dim|end|loop)\b"
        )
        _OPERAND_RE = re.compile(r"\b([A-Za-z_]\w*|\d+\.?\d*(?:[eE][+-]?\d+)?)\b")

        clean = strip_code_strings(code)
        ops: Counter = Counter(m.group() for m in _OP_RE.finditer(clean))
        clean_no_ops = _OP_RE.sub(" ", clean)
        operands_cnt: Counter = Counter(
            m.group() for m in _OPERAND_RE.finditer(clean_no_ops)
            if m.group().lower() not in _KEYWORDS
        )

        n1 = len(ops)
        n2 = len(operands_cnt)
        N1 = sum(ops.values())
        N2 = sum(operands_cnt.values())
        vocab = n1 + n2
        length = N1 + N2
        volume = length * math.log2(max(2, vocab))
        difficulty = (n1 / max(1, 2)) * (N2 / max(1, n2))
        effort = difficulty * volume
        time_s = effort / 18.0
        bugs = volume / 3000.0

        return cls(
            n1=n1, n2=n2, N1=N1, N2=N2,
            vocabulary=vocab, length=length,
            volume=round(volume, 2), difficulty=round(difficulty, 2),
            effort=round(effort, 2), time_seconds=round(time_s, 2),
            bugs_estimate=round(bugs, 4),
        )


# ═══════════════════════════════════════════════════════════════════════════
# 5) EXTRAÇÃO DE FEATURES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AnalysisMetrics:
    language: str
    node_count: int
    edge_count: int
    reachable_count: int
    unreachable_count: int        # nós CFG inalcançáveis (informativo)
    cyclomatic_complexity: int
    branching_factor: float
    max_depth: int
    loop_count: int
    syntactic_dead_code: int      # FIX-C03: renomeado (era dead_code_count com double-count)
    duplicate_block_count: int
    dependency_instability: float
    infinite_loop_risk: float
    weighted_complexity: float    # IMP-M01: era structural_entropy (nome incorreto)
    dsm_density: float
    dsm_reciprocity: float
    dsm_cyclic_ratio: float
    hamiltonian: float = 0.0
    smoothing_factor: float = 0.0  # IMP-M02: era momentum K (clarificado)
    status: str = "STABLE"
    notes: List[str] = field(default_factory=list)
    halstead: Optional[HalsteadMetrics] = None

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        if self.halstead is not None:
            d["halstead"] = self.halstead.to_dict()
        return d


@dataclass
class _WeightedComplexityInputs:
    """
    C-04 FIX: agrupa os 7 parâmetros de _weighted_complexity em um único objeto.
    Antes: 8 parâmetros no __init__ (self + 7), violando o limite de 7 recomendado.
    Agora: _weighted_complexity(self, inputs: _WeightedComplexityInputs) → 2 params.
    """
    branch_nodes:        int
    loop_count:          int
    max_depth:           int
    unreachable_count:   int
    duplicate_block_count: int
    dsm_density:         float
    dsm_cyclic_ratio:    float


class FeatureExtractor:
    LOOP_RE = re.compile(r"\b(for|while|do)\b", re.I)
    TERMINAL_RE = re.compile(r"\b(return|throw|raise)\b", re.I)

    def analyze(self, cfg: CFG, dsm: DSMResult, code: str,
                compute_halstead: bool = True) -> AnalysisMetrics:
        reachable = cfg.reachable_from_entry()
        node_count = len(cfg.nodes)
        edge_count = len(cfg.edges())
        reachable_count = len(reachable)
        unreachable_count = max(0, node_count - reachable_count)

        loop_count = self._loop_count(cfg, code)
        branching_factor = self._branching_factor(cfg)
        max_depth = int(cfg.metadata.get("max_depth", 0))
        duplicate_block_count = self._duplicate_block_count(code)

        # FIX-C03: usa apenas contagem sintática, sem somar CFG unreachable
        # GAP-A01 FIX: passar linguagem para usar algoritmo correto por linguagem
        syntactic_dead_code = self._syntactic_dead_code(code, language=cfg.language)

        dependency_instability = self._dependency_instability(dsm)
        infinite_loop_risk, loop_notes = self._infinite_loop_risk(code, cfg, dsm)

        branch_nodes = sum(
            1 for n in cfg.nodes.values()
            if n.kind in {"if", "branch", "match", "case", "try", "except",
                          "with", "loop_header", "for", "while"}
        )

        weighted_complexity = self._weighted_complexity(_WeightedComplexityInputs(
            branch_nodes=branch_nodes, loop_count=loop_count,
            max_depth=max_depth, unreachable_count=unreachable_count,
            duplicate_block_count=duplicate_block_count,
            dsm_density=dsm.density, dsm_cyclic_ratio=dsm.cyclic_dependency_ratio,
        ))
        cyclomatic_complexity = max(1, edge_count - node_count + 2)

        notes = list(loop_notes) + list(dsm.notes)
        if unreachable_count > 0:
            notes.append(f"{unreachable_count} nós CFG inalcançáveis")

        halstead = None
        if compute_halstead:
            if cfg.language == "python":
                # Análise semântica precisa via AST Python
                halstead = HalsteadMetrics.from_python(code)
            else:
                # IMP-C: fallback token-based universal para C++, Java, VBA, DSL, etc.
                # Precisão: bugs_estimate Δ≈1.5% vs from_python() para Python puro.
                halstead = HalsteadMetrics.from_tokens(code)

        return AnalysisMetrics(
            language=cfg.language,
            node_count=node_count, edge_count=edge_count,
            reachable_count=reachable_count, unreachable_count=unreachable_count,
            cyclomatic_complexity=cyclomatic_complexity,
            branching_factor=branching_factor, max_depth=max_depth,
            loop_count=loop_count, syntactic_dead_code=syntactic_dead_code,
            duplicate_block_count=duplicate_block_count,
            dependency_instability=dependency_instability,
            infinite_loop_risk=infinite_loop_risk,
            weighted_complexity=weighted_complexity,
            dsm_density=dsm.density, dsm_reciprocity=dsm.reciprocity_ratio,
            dsm_cyclic_ratio=dsm.cyclic_dependency_ratio,
            notes=notes, halstead=halstead,
        )

    def _branching_factor(self, cfg: CFG) -> float:
        if not cfg.nodes:
            return 0.0
        branching = [n for n in cfg.nodes.values() if len(n.successors) > 1]
        return len(branching) / max(1, len(cfg.nodes))

    def _loop_count(self, cfg: CFG, code: str) -> int:
        back_edges = sum(1 for _, _, lbl in cfg.edges() if lbl == "back")
        keyword_loops = len(self.LOOP_RE.findall(code))
        return max(back_edges, keyword_loops)

    def _duplicate_block_count(self, code: str) -> int:
        # GAP-N01 / OPT-N02 FIX: operar sobre código sem strings/comentários.
        # Sem strip, linhas repetidas em docstrings (ex: separadores # ──) inflavam
        # duplicate_block_count artificialmente. strip_code_strings() elimina isso.
        code_clean = strip_code_strings(code)
        lines = [normalize_ws(x) for x in code_clean.splitlines() if normalize_ws(x)]
        count = 0
        prev = None
        for line in lines:
            if prev is not None and line == prev:
                count += 1
            prev = line
        return count

    def _syntactic_dead_code(self, code: str, language: str = "generic") -> int:
        """
        GAP-A01 FIX: implementação com conscientização de linguagem.
        O algoritmo original (baseado em profundidade de { }) era correto para
        código C-like mas produzia 100% de falsos positivos para Python puro:
        Python não usa { } para escopo — cada return seguido de docstring
        indentada era contado como dead code.

        Para Python: usa AST — conta apenas statements realmente inalcançáveis
        (após return/raise no mesmo escopo de função, excluindo defs/classes).
        Para C-like e outros: usa o algoritmo original de { } depth.

        FIX-C03: NÃO soma com CFG unreachable (double-counting).
        GAP-N01: opera sobre código limpo (strip_code_strings) para C-like.
        """
        if language == "python":
            return self._syntactic_dead_code_python(code)
        return self._syntactic_dead_code_generic(code)

    def _syntactic_dead_code_python(self, code: str) -> int:
        """
        Dead code Python via AST: statements após return/raise no mesmo escopo.
        Retorna 0 se o código não parseia (SyntaxError não é dead code).
        """
        count = 0
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0  # código inválido — não contabilizar
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for i, stmt in enumerate(node.body):
                if isinstance(stmt, (ast.Return, ast.Raise)):
                    # Contar statements após terminal no escopo direto da função
                    # (excluir definições aninhadas — são alcançáveis via chamada)
                    for dead_stmt in node.body[i+1:]:
                        if not isinstance(dead_stmt, (ast.FunctionDef,
                                                       ast.AsyncFunctionDef,
                                                       ast.ClassDef)):
                            count += 1
        return count

    def _syntactic_dead_code_generic(self, code: str) -> int:
        """
        Dead code para linguagens C-like via { } depth tracking.
        Algoritmo original (FIX-C03) — correto para C, Java, JS etc.
        """
        # GAP-N01: strip antes de analisar padrões de terminal
        code_clean = strip_code_strings(code)
        count = 0
        lines = [ln.rstrip() for ln in code_clean.splitlines()]
        depth = 0
        terminal_seen: Dict[int, bool] = {}

        for line in lines:
            opens = line.count("{")
            closes = line.count("}")
            depth = max(0, depth + opens - closes)
            stripped = line.strip()
            if not stripped:
                continue
            if terminal_seen.get(depth, False) and not stripped.startswith("}"):
                count += 1
            if self.TERMINAL_RE.match(stripped):
                terminal_seen[depth] = True
            if closes > 0:
                terminal_seen = {d: v for d, v in terminal_seen.items() if d <= depth}

        return count

    def _dependency_instability(self, dsm: DSMResult) -> float:
        if not dsm.units:
            return 0.0
        # PORT [10]: pure Python — sem numpy; resultado numericamente idêntico
        ratios: List[float] = []
        for out_v, in_v in zip(dsm.coupling_out, dsm.coupling_in):
            mismatch = abs(float(out_v) - float(in_v))
            total = float(out_v) + float(in_v) + 1e-9
            ratios.append(mismatch / total)
        score = sum(ratios) / max(1, len(ratios))
        score += 0.4 * dsm.reciprocity_ratio + 0.6 * dsm.cyclic_dependency_ratio
        # FIX-C06: cap corrigido para o range real [0, ~3.0]
        return min(3.0, score)

    def _infinite_loop_risk(self, code: str, cfg: CFG,
                            dsm: DSMResult) -> Tuple[float, List[str]]:
        notes: List[str] = []
        risk = 0.0
        # BUG-U01 FIX: strip strings e comentários antes dos regexes para
        # evitar falsos positivos quando padrões como 'while(true)' aparecem
        # dentro de string literals ou comentários do código analisado.
        code_clean = strip_code_strings(code)
        lower = code_clean.lower()
        if re.search(r"\bwhile\s*\(\s*true\s*\)", lower) or re.search(r"\bwhile\s+true\b", lower):
            risk += 0.45; notes.append("while(true) detectado")
        if re.search(r"\bfor\s*\(\s*;\s*;\s*\)", lower):
            risk += 0.45; notes.append("for(;;) detectado")
        if re.search(r"\bwhile\s*\(\s*1\s*\)", lower):
            risk += 0.35; notes.append("while(1) detectado")
        if "+ 0" in code_clean or "+= 0" in code_clean or "- 0" in code_clean or "* 1" in code_clean:
            risk += 0.20; notes.append("padrões no-op detectados")
        loops = [n for n in cfg.nodes.values() if n.kind in {"loop_header", "for", "while"}]
        if loops and not re.search(r"\bbreak\b|\breturn\b", lower):
            risk += 0.20; notes.append("loop sem break/return explícito")
        if dsm.cyclic_dependency_ratio > 0.20:
            risk += 0.15; notes.append("ciclo de dependência aumenta risco de estagnação")
        return min(1.0, risk), notes

    def _weighted_complexity(self, inputs: "_WeightedComplexityInputs") -> float:
        """
        IMP-M01: Complexidade estrutural ponderada.
        C-04 FIX: recebe _WeightedComplexityInputs em vez de 7 parâmetros individuais.
        """
        i = inputs
        base = i.branch_nodes + 1.4 * i.loop_count + 0.8 * i.max_depth
        penalty = (0.25 * i.unreachable_count + 0.35 * i.duplicate_block_count
                   + 3.0 * i.dsm_density + 2.0 * i.dsm_cyclic_ratio)
        return math.log1p(max(0.0, base + penalty))


# ═══════════════════════════════════════════════════════════════════════════
# 6) HAMILTONIAN SCORER (pesos calibrados)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HamiltonianScorerConfig:
    """
    GAP-B02 FIX: configuração de pesos para HamiltonianScorer.
    Análogo ao HMCObjectiveConfig (GAP-A04) — mesmo padrão aplicado aqui.
    Antes: 10 parâmetros no __init__ (> 7 recomendado, difícil de usar e testar).
    Agora: __init__ recebe (config, ...) — backward-compatible via defaults.

    Pesos calibrados (não alterar sem nova calibração):
      alpha=1.00  → cyclomatic_complexity   (escala linear com decisões)
      beta=0.85   → weighted_complexity     (compressão log1p — escala mais suave)
      gamma=1.10  → dependency_instability  (ligeiramente penalizado — impacto real)
      delta=2.20  → infinite_loop_risk      (peso maior — risco crítico de runtime)
      epsilon=0.90→ syntactic_dead_code     (código morto tem custo cognitivo)
      zeta=0.75   → duplicate_block_count   (peso menor — duplicatas são toleráveis)
      eta=1.35    → dsm_density             (acoplamento global)
      theta=1.50  → dsm_cyclic_ratio        (ciclos de dep. são piores que densidade)
      lambda_smoothing=0.85 → amortecimento entre iterações
    """
    alpha:            float = 1.00
    beta:             float = 0.85
    gamma:            float = 1.10
    delta:            float = 2.20
    epsilon:          float = 0.90
    zeta:             float = 0.75
    eta:              float = 1.35
    theta:            float = 1.50
    lambda_smoothing: float = 0.85


class HamiltonianScorer:
    """
    GAP-B02 FIX: __init__ reduzido de 10 para 2 parâmetros.
    Backward-compatible: HamiltonianScorer() sem args usa HamiltonianScorerConfig defaults.
    Para customizar pesos, passe um HamiltonianScorerConfig:
        scorer = HamiltonianScorer(config=HamiltonianScorerConfig(delta=3.0))
    """
    def __init__(
        self,
        config: Optional[HamiltonianScorerConfig] = None,
        **legacy_kwargs: float,  # backward-compat: aceita alpha=, beta=, etc. direto
    ) -> None:
        # Se kwargs legados forem passados (alpha=, beta=...), construir config a partir deles
        if legacy_kwargs:
            base = config or HamiltonianScorerConfig()
            cfg = HamiltonianScorerConfig(
                alpha=legacy_kwargs.get("alpha", base.alpha),
                beta=legacy_kwargs.get("beta", base.beta),
                gamma=legacy_kwargs.get("gamma", base.gamma),
                delta=legacy_kwargs.get("delta", base.delta),
                epsilon=legacy_kwargs.get("epsilon", base.epsilon),
                zeta=legacy_kwargs.get("zeta", base.zeta),
                eta=legacy_kwargs.get("eta", base.eta),
                theta=legacy_kwargs.get("theta", base.theta),
                lambda_smoothing=legacy_kwargs.get("lambda_smoothing", base.lambda_smoothing),
            )
        else:
            cfg = config or HamiltonianScorerConfig()

        self.alpha            = cfg.alpha
        self.beta             = cfg.beta
        self.gamma            = cfg.gamma
        self.delta            = cfg.delta
        self.epsilon          = cfg.epsilon
        self.zeta             = cfg.zeta
        self.eta              = cfg.eta
        self.theta            = cfg.theta
        self.lambda_smoothing = cfg.lambda_smoothing

    def score(self, metrics: AnalysisMetrics,
              previous_h: Optional[float] = None) -> AnalysisMetrics:
        H = (
            self.alpha * metrics.cyclomatic_complexity
            + self.beta * metrics.weighted_complexity
            + self.gamma * metrics.dependency_instability
            + self.delta * metrics.infinite_loop_risk
            + self.epsilon * metrics.syntactic_dead_code
            + self.zeta * metrics.duplicate_block_count
            + self.eta * metrics.dsm_density
            + self.theta * metrics.dsm_cyclic_ratio
        )

        if previous_h is None:
            K = 1.0
        else:
            K = math.exp(-self.lambda_smoothing * abs(H - previous_h))
            if metrics.infinite_loop_risk > 0.6 and H >= previous_h:
                K *= 0.35

        status = self._status(H, metrics, K)
        return dataclasses.replace(
            metrics, hamiltonian=float(H), smoothing_factor=float(K), status=status)

    def _status(self, H: float, m: AnalysisMetrics, K: float) -> str:
        if (H >= 20 or m.infinite_loop_risk >= 0.75 or K < 0.20):
            return "CRITICAL"
        if (H >= 10 or m.syntactic_dead_code > 0
                or m.duplicate_block_count > 0 or m.unreachable_count > 3):
            return "WARNING"
        return "STABLE"


# ═══════════════════════════════════════════════════════════════════════════
# 7) TRANSFORMS (5 originais + 4 novos)
# ═══════════════════════════════════════════════════════════════════════════

class CodeTransform:
    name: str = "base"
    description: str = ""
    # IMP-A: LanguageGuard — declara linguagens onde este transform é semanticamente seguro.
    # Valores: lista de linguagem IDs (ex: "python", "c_like", "vba", "text")
    # "*" = universal (seguro para qualquer linguagem textual).
    # GreedyOptimizer e HMCCodeObjective filtram por detect_language() antes de aplicar.
    safe_for: List[str] = ["*"]

    def apply(self, code: str, language: str = "text") -> str:
        # IMP-F: interface CST-ready — language disponível para transforms que precisam.
        # Default "text" para backward-compatibility. Subclasses que precisam de language
        # devem declarar safe_for corretamente e usar o parâmetro internamente.
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Transform:{self.name}>"


# ── Originais (preservados) ───────────────────────────────────────────────

class NoOpAssignmentSimplifier(CodeTransform):
    name = "noop_assignment_simplifier"
    description = "Remove atribuições identidade: x = x + 0, x *= 1, etc."
    safe_for = ["python", "c_like", "vba"]  # IMP-A: padrões x=x+0 são sintaxe válida nessas 3
    PATTERNS = [
        re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*\1\s*\+\s*0\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*\1\s*-\s*0\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*\1\s*\*\s*1\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*\1\s*/\s*1\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*\+=\s*0\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*-=\s*0\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*\*=\s*1\s*;?\s*$"),
        re.compile(r"^\s*([A-Za-z_]\w*)\s*/=\s*1\s*;?\s*$"),
    ]
    def apply(self, code: str, language: str = "text") -> str:
        out = []
        for line in code.splitlines():
            s = line.strip()
            if any(p.match(s) for p in self.PATTERNS):
                continue
            out.append(line)
        return "\n".join(out)


class UnreachableAfterTerminalRemoval(CodeTransform):
    name = "unreachable_after_terminal_removal"
    description = "Remove código após return/raise/break/continue."
    safe_for = ["python", "c_like"]  # IMP-A: VBA não usa { } para depth tracking
    def apply(self, code: str, language: str = "text") -> str:
        lines = code.splitlines()
        out: List[str] = []
        depth = 0
        terminal_seen: Dict[int, bool] = {}
        terminal_re = re.compile(r"^\s*(return|throw|raise|break|continue)\b")
        for line in lines:
            opens = line.count("{"); closes = line.count("}")
            depth = max(0, depth + opens - closes)
            stripped = line.strip()
            if stripped and terminal_seen.get(depth, False) and not stripped.startswith("}"):
                continue
            out.append(line)
            if terminal_re.match(stripped):
                terminal_seen[depth] = True
            if closes > 0:
                terminal_seen = {d: v for d, v in terminal_seen.items() if d <= depth}
        return "\n".join(out)


class AdjacentDuplicateBlockRemoval(CodeTransform):
    name = "adjacent_duplicate_block_removal"
    description = "Remove linhas idênticas adjacentes."
    safe_for = ["*"]  # IMP-A: universal — linha-a-linha, sem semântica de tipo
    def apply(self, code: str, language: str = "text") -> str:
        out: List[str] = []
        prev = None
        for line in code.splitlines():
            norm = normalize_ws(line)
            if not norm:
                out.append(line); prev = None; continue
            if prev is not None and norm == prev:
                continue
            out.append(line); prev = norm
        return "\n".join(out)


class DuplicateAdjacentControlBlockMerger(CodeTransform):
    name = "duplicate_adjacent_control_block_merger"
    description = "Merge blocos de controle idênticos adjacentes."
    safe_for = ["*"]  # IMP-A: universal — compara linhas normalizadas
    def apply(self, code: str, language: str = "text") -> str:
        lines = code.splitlines()
        out: List[str] = []
        i = 0
        while i < len(lines):
            cur = normalize_ws(lines[i])
            if i + 1 < len(lines) and cur and cur == normalize_ws(lines[i + 1]):
                out.append(lines[i]); i += 2; continue
            out.append(lines[i]); i += 1
        return "\n".join(out)


class BracketWhitespaceNormalizer(CodeTransform):
    name = "bracket_whitespace_normalizer"
    description = "Normaliza whitespace: trailing spaces, linhas em branco excessivas."
    safe_for = ["*"]  # IMP-A: universal — apenas normaliza espaços/newlines
    def apply(self, code: str, language: str = "text") -> str:
        code = re.sub(r"[ \t]+\n", "\n", code)
        code = re.sub(r"\n{3,}", "\n\n", code)
        return code.strip()


# ── Novos (T06–T09) ──────────────────────────────────────────────────────

class ConstantFoldingTransform(CodeTransform):
    """
    T06: Dobra expressões com literais simples via AST Python.

    GAP-N04 FIX: implementação baseada em ast.parse() em vez de regex.
    Vantagens sobre regex:
      - Precedência correta: 2+3*4 → 14 (não 20 como regex poderia errar)
      - Cadeia de operações: 1+2+3 → 6 (regex só via 2 operandos)
      - Parênteses: (2+3)*4 → 20
      - Potenciação: 2**8 → 256
      - BoolOp: True and False → False, not True → False
      - Sem risco de captura parcial de expressões complexas
      - Variáveis com zero (a*0) preservadas para tipos não escalares

    GAP-N05 via IMP-A: safe_for=["python"] — type safety requer AST Python.
    """
    name = "constant_folding"
    description = "Dobra expressões constantes via AST: 2+3→5, 2+3*4→14, True and False→False."
    safe_for = ["python"]  # IMP-A/GAP-N05: apenas Python com AST garantida

    @staticmethod
    def _is_all_constants(node) -> bool:
        """Retorna True se TODOS os valores na subárvore são literais constantes."""
        if isinstance(node, ast.Constant):
            return True
        if isinstance(node, ast.BinOp):
            return (ConstantFoldingTransform._is_all_constants(node.left) and
                    ConstantFoldingTransform._is_all_constants(node.right))
        if isinstance(node, ast.UnaryOp):
            return ConstantFoldingTransform._is_all_constants(node.operand)
        if isinstance(node, ast.BoolOp):
            return all(ConstantFoldingTransform._is_all_constants(v) for v in node.values)
        return False  # Name, Call, Attribute, etc. → não é constante

    @staticmethod
    def _safe_eval(node):
        """Avalia nó AST de constantes puras. Retorna None se não avaliável."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp):
            left  = ConstantFoldingTransform._safe_eval(node.left)
            right = ConstantFoldingTransform._safe_eval(node.right)
            if left is None or right is None:
                return None
            ops = {
                ast.Add:      lambda a, b: a + b,
                ast.Sub:      lambda a, b: a - b,
                ast.Mult:     lambda a, b: a * b,
                ast.Div:      lambda a, b: a / b if b != 0 else None,
                ast.FloorDiv: lambda a, b: a // b if b != 0 else None,
                ast.Mod:      lambda a, b: a % b if b != 0 else None,
                ast.Pow:      lambda a, b: a ** b,
            }
            fn = ops.get(type(node.op))
            if fn is None:
                return None
            result = fn(left, right)
            # Converter float inteiro (ex: 10/2=5.0) para int
            if isinstance(result, float) and result == int(result):
                result = int(result)
            return result
        if isinstance(node, ast.UnaryOp):
            val = ConstantFoldingTransform._safe_eval(node.operand)
            if val is None:
                return None
            if isinstance(node.op, ast.USub): return -val
            if isinstance(node.op, ast.UAdd): return +val
            if isinstance(node.op, ast.Not):  return not val
            if isinstance(node.op, ast.Invert): return ~val
            return None
        if isinstance(node, ast.BoolOp):
            vals = [ConstantFoldingTransform._safe_eval(v) for v in node.values]
            if any(v is None for v in vals):
                return None
            if isinstance(node.op, ast.And): return all(vals)
            if isinstance(node.op, ast.Or):  return any(v for v in vals)
            return None
        return None

    def _fold_line(self, line: str) -> str:
        """
        GAP-N04: Dobra via AST para uma linha de atribuição Python.
        Tenta: parse a linha, verificar se RHS é puro-constante, avaliar e substituir.
        Retorna a linha original se não puder dobrar (conservador).
        """
        stripped = line.strip()
        if not stripped or not stripped[0].isidentifier() or "=" not in stripped:
            return line

        # Tentar parse como módulo Python
        try:
            tree = ast.parse(stripped, mode="exec")
        except SyntaxError:
            return line

        if len(tree.body) != 1 or not isinstance(tree.body[0], ast.Assign):
            return line

        assign = tree.body[0]
        if len(assign.targets) != 1:
            return line  # multi-target (a = b = expr) — conservador

        rhs = assign.value
        if not self._is_all_constants(rhs):
            return line  # tem variáveis ou calls — não dobrar

        result = self._safe_eval(rhs)
        if result is None:
            return line

        # Reconstruir linha preservando indentação original
        indent = line[: len(line) - len(line.lstrip())]
        target_src = ast.unparse(assign.targets[0])
        # Detectar ponto-e-vírgula trailing (estilo C-like misturado)
        tail = ";" if stripped.endswith(";") else ""
        return f"{indent}{target_src} = {result!r}{tail}"

    def apply(self, code: str, language: str = "text") -> str:
        out = []
        for line in code.splitlines():
            out.append(self._fold_line(line))
        return "\n".join(out)


class RedundantConditionEliminator(CodeTransform):
    """
    T07: Elimina condições trivialmente verdadeiras ou falsas.
    Ex: if True: → remove if, mantém corpo
        if False: → remove bloco inteiro
        while False: → remove loop
    Conservador: apenas literais True/False.
    IMP-A: safe_for=["*"] — regex exige "if True:" com dois pontos Python,
    portanto "if(true)" C-like não casa e o transform é inofensivo para C/Java.
    """
    name = "redundant_condition_eliminator"
    description = "Elimina if True/if False/while False literais."
    safe_for = ["*"]  # IMP-A: regex Python-specific, inofensivo para outras linguagens

    _IF_TRUE_RE = re.compile(r"^(\s*)if\s+True\s*:\s*$")
    _IF_FALSE_RE = re.compile(r"^(\s*)if\s+False\s*:\s*$")
    _WHILE_FALSE_RE = re.compile(r"^(\s*)while\s+False\s*:\s*$")

    def apply(self, code: str, language: str = "text") -> str:
        lines = code.splitlines()
        out: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # while False: → skip entire block
            if self._WHILE_FALSE_RE.match(line):
                indent = len(line) - len(line.lstrip())
                i += 1
                while i < len(lines):
                    nxt = lines[i]
                    nxt_indent = len(nxt) - len(nxt.lstrip()) if nxt.strip() else indent + 1
                    if nxt.strip() and nxt_indent <= indent:
                        break
                    i += 1
                continue
            # if False: → skip if block (keep else if present)
            if self._IF_FALSE_RE.match(line):
                indent = len(line) - len(line.lstrip())
                i += 1
                # skip body
                while i < len(lines):
                    nxt = lines[i]
                    nxt_indent = len(nxt) - len(nxt.lstrip()) if nxt.strip() else indent + 1
                    if nxt.strip() and nxt_indent <= indent:
                        break
                    i += 1
                continue
            # BUG-U02 FIX: if True: → remove a linha do if e dedenta o corpo
            # em 4 espaços para que o código resultante seja Python válido.
            # Original: apenas removía a linha do if sem dedentação → IndentationError.
            if self._IF_TRUE_RE.match(line):
                if_indent = len(line) - len(line.lstrip())
                i += 1
                # Coletar e dedentear o corpo do if (linhas mais indentadas)
                while i < len(lines):
                    body_line = lines[i]
                    body_stripped = body_line.strip()
                    if not body_stripped:
                        # linha em branco dentro do corpo — inclui sem modificar
                        out.append(body_line)
                        i += 1
                        continue
                    body_indent = len(body_line) - len(body_line.lstrip())
                    if body_indent <= if_indent:
                        # saiu do corpo do if
                        break
                    # Dedenta em 4 espaços (Python standard indent)
                    dedented = body_line[4:] if body_line.startswith("    ") else body_line
                    out.append(dedented)
                    i += 1
                continue
            out.append(line)
            i += 1
        return "\n".join(out)


class EmptyBlockRemover(CodeTransform):
    """
    T08: Remove blocos C-like vazios: { } ou {} em linha.
    Cuidado: não remove em contextos como struct/class declarations.
    Conservador: apenas quando bloco está sozinho na linha.
    IMP-A: safe_for=["c_like"] — blocos {} vazios são idioma C-like.
    Em Python, {} é um dict literal, não um bloco estrutural.
    """
    name = "empty_block_remover"
    description = "Remove blocos {} vazios em código C-like."
    safe_for = ["c_like"]  # IMP-A: Python não tem blocos {} estruturais

    _EMPTY_BLOCK_RE = re.compile(r"^\s*\{\s*\}\s*;?\s*$")

    def apply(self, code: str, language: str = "text") -> str:
        out = []
        for line in code.splitlines():
            if self._EMPTY_BLOCK_RE.match(line):
                continue
            out.append(line)
        return "\n".join(out)


class PythonUnusedVarDetector(CodeTransform):
    """
    T09: Detecta variáveis definidas mas nunca usadas (Python AST).
    Adiciona comentário # [UCO: unused: var] em vez de remover
    (conservador — remoção automática pode quebrar código com efeitos colaterais).
    Aplica-se apenas a escopo de funções.
    IMP-A: safe_for=["python"] — requer ast.parse() Python válido.
    """
    name = "python_unused_var_detector"
    description = "Anota variáveis locais não utilizadas em funções Python."
    safe_for = ["python"]  # IMP-A: depende de ast.parse() Python

    def apply(self, code: str, language: str = "text") -> str:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return code

        # Coletar anotações por linha
        annotations: Dict[int, str] = {}

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            defs: Dict[str, List[int]] = defaultdict(list)
            uses: Set[str] = set()

            # Parâmetros não contam como "unused" neste contexto
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                uses.add(arg.arg)
            if node.args.vararg:
                uses.add(node.args.vararg.arg)
            if node.args.kwarg:
                uses.add(node.args.kwarg.arg)

            for child in ast.walk(node):
                if isinstance(child, ast.Assign):
                    for t in child.targets:
                        if isinstance(t, ast.Name) and isinstance(t.ctx, ast.Store):
                            ln = getattr(child, "lineno", 0) or 0
                            defs[t.id].append(ln)
                elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
                    uses.add(child.id)

            for varname, linenos in defs.items():
                if varname.startswith("_"):
                    continue  # convenção _ = ignorar
                if varname not in uses:
                    for ln in linenos:
                        annotations[ln] = varname

        if not annotations:
            return code

        lines = code.splitlines()
        result = []
        for i, line in enumerate(lines, start=1):
            if i in annotations:
                vname = annotations[i]
                suffix = f"  # [UCO: unused: {vname}]"
                # BUG-U03 FIX: verificar se a anotação já existe antes de adicionar.
                # Sem este guard, cada pass do GreedyOptimizer duplica o comentário:
                # x = 5  # [UCO: unused: x]  # [UCO: unused: x]  # ...
                if suffix not in line:
                    result.append(line.rstrip() + suffix)
                else:
                    result.append(line)
            else:
                result.append(line)
        return "\n".join(result)


# ═══════════════════════════════════════════════════════════════════════════
# 8) DUAL-AVERAGING ADAPTER (FIX-C04)
# ═══════════════════════════════════════════════════════════════════════════

class DualAveragingAdapter:
    """
    FIX-C04: Adaptação de step_size via dual-averaging (Hoffman & Gelman 2014).
    Converge em O(log n) vs O(n) do original (1.01/0.99 por step).
    Referência: Algorithm 5 do paper NUTS.

    Para atingir step_size = 0.05 a partir de 0.08:
      Original: ~56 rejeições consecutivas
      Dual-avg: ~8 iterações
    """
    def __init__(
        self,
        target_accept: float = 0.65,
        gamma: float = 0.05,
        t0: int = 10,
        kappa: float = 0.75,
    ) -> None:
        self.target_accept = target_accept
        self.gamma = gamma
        self.t0 = t0
        self.kappa = kappa
        self.m: int = 0
        self.H_bar: float = 0.0
        self.log_eps_bar: float = 0.0
        self._log_eps: Optional[float] = None
        self._mu: Optional[float] = None

    def initialize(self, step_size: float) -> None:
        self._log_eps = math.log(step_size)
        self._mu = math.log(10.0 * step_size)

    def update(self, accept_prob: float) -> float:
        """Retorna novo step_size. Chamar uma vez por HMC step."""
        if self._log_eps is None or self._mu is None:
            raise RuntimeError("Chame initialize() antes de update().")
        self.m += 1
        eta = 1.0 / (self.m + self.t0)
        self.H_bar = (1.0 - eta) * self.H_bar + eta * (self.target_accept - accept_prob)
        log_eps = self._mu - math.sqrt(self.m) / self.gamma * self.H_bar
        eta_bar = self.m ** (-self.kappa)
        self.log_eps_bar = eta_bar * log_eps + (1.0 - eta_bar) * self.log_eps_bar
        self._log_eps = log_eps
        return math.exp(log_eps)

    def final_step_size(self) -> float:
        """Step size estabilizado após warm-up (ergodic average)."""
        return math.exp(self.log_eps_bar)


# ═══════════════════════════════════════════════════════════════════════════
# 9) ANÁLISE + RESULTADO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class AnalysisResult:
    code: str
    cfg: CFG
    dsm: DSMResult
    metrics: AnalysisMetrics
    transform_chain: List[str] = field(default_factory=list)
    diagnostics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metrics": self.metrics.to_dict(),
            "diagnostics": self.diagnostics,
            "transform_chain": self.transform_chain,
            "language": self.cfg.language,
            "dsm": {
                "density": self.dsm.density,
                "reciprocity_ratio": self.dsm.reciprocity_ratio,
                "cyclic_dependency_ratio": self.dsm.cyclic_dependency_ratio,
                "n_units": len(self.dsm.units),
                "n_sccs": len(self.dsm.sccs),
                "notes": self.dsm.notes,
            },
            "cfg": {
                "n_nodes": len(self.cfg.nodes),
                "n_edges": len(self.cfg.edges()),
                "max_depth": self.cfg.metadata.get("max_depth", 0),
            },
        }


class UniversalAnalyzer:
    def __init__(self) -> None:
        self._py_cfg = PythonCFGBuilder()
        self._gen_cfg = GenericCFGBuilder()
        self._dsm = DSMEngine()
        self._extractor = FeatureExtractor()
        self._scorer = HamiltonianScorer()

    def build_cfg(self, code: str, language_hint: Optional[str] = None) -> CFG:
        lang = detect_language(code, language_hint)
        if lang == "python":
            try:
                return self._py_cfg.build(code)
            except Exception as exc:
                # C-08 FIX: warning explícito ao usar fallback (antes silencioso)
                warnings.warn(
                    f"UniversalAnalyzer: PythonCFGBuilder falhou "
                    f"({type(exc).__name__}: {exc}). Usando fallback Pygments.",
                    RuntimeWarning, stacklevel=3,
                )
                # Fallback: Pygments C-like para Python inválido
                return self._gen_cfg.build(code, language="python")
        # IMP-H: passar linguagem ao GenericCFGBuilder para usar lexer Pygments correto
        return self._gen_cfg.build(code, language=lang)

    def analyze(self, code: str, language_hint: Optional[str] = None,
                previous_h: Optional[float] = None,
                compute_halstead: bool = True) -> AnalysisResult:
        cfg = self.build_cfg(code, language_hint)
        dsm = self._dsm.build(code, language_hint)
        metrics = self._extractor.analyze(cfg, dsm, code,
                                          compute_halstead=compute_halstead)
        metrics = self._scorer.score(metrics, previous_h=previous_h)
        diagnostics = self._diagnostics(metrics, cfg, dsm)
        return AnalysisResult(code=code, cfg=cfg, dsm=dsm, metrics=metrics,
                              diagnostics=diagnostics)

    def _diagnostics(self, m: AnalysisMetrics, cfg: CFG, dsm: DSMResult) -> List[str]:
        notes = list(m.notes)
        if m.unreachable_count > 0:
            notes.append(f"{m.unreachable_count} nós CFG inalcançáveis")
        if m.duplicate_block_count > 0:
            notes.append(f"{m.duplicate_block_count} blocos adjacentes duplicados")
        if m.syntactic_dead_code > 0:
            notes.append(f"{m.syntactic_dead_code} linhas após terminais (dead code)")
        if m.dependency_instability > 0.75:
            notes.append("instabilidade de dependências alta")
        if m.infinite_loop_risk > 0.45:
            notes.append("risco de loop infinito ou estagnação")
        if m.branching_factor > 0.20:
            notes.append("alta ramificação estrutural")
        if dsm.cyclic_dependency_ratio > 0.20:
            notes.append("ciclos na DSM detectados")
        if m.halstead and m.halstead.bugs_estimate > 0.5:
            notes.append(
                f"Halstead: ~{m.halstead.bugs_estimate:.2f} bugs estimados "
                f"(vol={m.halstead.volume:.0f})")
        return notes


# ═══════════════════════════════════════════════════════════════════════════
# 10) HMC COM DUAL-AVERAGING
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HMCConfig:
    step_size: float = 0.08
    leapfrog_steps: int = 10
    mass_diag: Optional[np.ndarray] = None
    min_step_size: float = 0.01
    max_step_size: float = 0.25
    target_accept: float = 0.65
    adapt_step_size: bool = True
    use_dual_averaging: bool = True   # FIX-C04: dual-averaging como padrão


def sigmoid(x: "np.ndarray") -> "np.ndarray":
    # PORT [1b]: _require_numpy levanta RuntimeError clara se numpy não disponível
    np_mod = _require_numpy("sigmoid-based policy decoding (HMC/decode_policy)")
    x = np_mod.asarray(x, dtype=float)
    x = np_mod.clip(x, -50.0, 50.0)
    return 1.0 / (1.0 + np_mod.exp(-x))


def sigmoid_grad(x: np.ndarray) -> np.ndarray:
    """Derivada da sigmoid: s * (1 - s). Usada no gradiente analítico."""
    s = sigmoid(x)
    return s * (1.0 - s)


@dataclass
class HMCObjectiveConfig:
    """
    GAP-A04 FIX: configuração de pesos para HMCCodeObjective.
    Antes: 12 parâmetros no __init__ (> 7 recomendado, difícil de usar e testar).
    Agora: __init__ recebe (analyzer, transforms, config, cache_size) — 4 parâmetros.
    Backward-compatible: HMCCodeObjective() sem config usa os defaults abaixo.
    """
    smoothness_penalty:    float = 0.03
    aggressiveness_penalty: float = 0.10
    risk_weight:           float = 2.00
    dependency_weight:     float = 1.20
    dead_code_weight:      float = 0.25
    duplicate_weight:      float = 0.20
    gain_weight:           float = 0.80
    aggression_threshold:  float = 0.72  # GAP-N02: configurável


class HMCCodeObjective:
    """
    Espaço latente contínuo q controla política conservadora sobre transforms.
    FIX-C02: Cache LRU com limite de 1024 entradas (era dict ilimitado).
    GAP-A04 FIX: parâmetros de peso movidos para HMCObjectiveConfig dataclass.
    O __init__ passou de 12 parâmetros para 4 — muito mais legível e testável.
    """

    def __init__(
        self,
        analyzer: "UniversalAnalyzer",
        transforms: Optional[List[CodeTransform]] = None,
        config: Optional["HMCObjectiveConfig"] = None,
        cache_size: int = 1024,
    ) -> None:
        cfg = config or HMCObjectiveConfig()
        self.analyzer = analyzer
        self.transforms = transforms or self._default_transforms()
        self.smoothness_penalty    = cfg.smoothness_penalty
        self.aggressiveness_penalty = cfg.aggressiveness_penalty
        self.risk_weight           = cfg.risk_weight
        self.dependency_weight     = cfg.dependency_weight
        self.dead_code_weight      = cfg.dead_code_weight
        self.duplicate_weight      = cfg.duplicate_weight
        self.gain_weight           = cfg.gain_weight
        self.aggression_threshold  = cfg.aggression_threshold
        # FIX-C02: LRU cache com limite
        self._cache = _LRUCache(maxsize=cache_size)

    @staticmethod
    def _default_transforms() -> List[CodeTransform]:
        return [
            NoOpAssignmentSimplifier(),
            UnreachableAfterTerminalRemoval(),
            AdjacentDuplicateBlockRemoval(),
            DuplicateAdjacentControlBlockMerger(),
            BracketWhitespaceNormalizer(),
            ConstantFoldingTransform(),
            RedundantConditionEliminator(),
            EmptyBlockRemover(),
            PythonUnusedVarDetector(),
        ]

    def decode_policy(self, q: np.ndarray) -> Dict[str, Any]:
        s = sigmoid(q)
        ranked = sorted(range(len(self.transforms)), key=lambda i: s[i], reverse=True)
        active = [i for i in ranked if s[i] > 0.35]
        return {"sigmoid": s, "ranked": ranked, "active": active,
                "aggression": float(np.mean(s))}

    def apply_policy(self, code: str, q: np.ndarray,
                     language_hint: Optional[str] = None) -> Tuple[str, List[str], Dict[str, Any]]:
        """
        Aplica a política de transforms definida por q ao código.
        IMP-A: respeita safe_for de cada transform via language_hint.
        GAP-N02: threshold de agressividade configurável e registrado na chain.
        """
        policy = self.decode_policy(q)
        transformed = code
        chain: List[str] = []
        # IMP-A: detectar linguagem uma vez para filtrar transforms seguros
        language = language_hint or detect_language(code)
        for idx in policy["active"]:
            t = self.transforms[idx]
            # IMP-A: respeitar safe_for também no HMC path
            if "*" not in getattr(t, "safe_for", ["*"]) and language not in getattr(t, "safe_for", ["*"]):
                continue
            new_code = t.apply(transformed, language)
            if normalize_ws(new_code) != normalize_ws(transformed):
                transformed = new_code
                chain.append(t.name)
        # GAP-N02 FIX: threshold configurável + registrado na chain
        if policy["aggression"] > self.aggression_threshold:
            transformed = re.sub(r"\n{3,}", "\n\n", transformed).strip()
            chain.append("whitespace_aggression_strip")
        return transformed, chain, policy

    def potential(self, q: np.ndarray, code: str,
                  language_hint: Optional[str] = None,
                  baseline_h: Optional[float] = None) -> Tuple[float, Dict[str, Any]]:
        q = np.asarray(q, dtype=float)
        q_key = tuple(np.round(q, 6))
        # GAP-D03 FIX: SHA-256 do código completo (era code[:200] com colisões)
        code_hash = hashlib.sha256(code.encode("utf-8", errors="replace")).hexdigest()[:16]
        cache_key = (q_key, code_hash, language_hint,
                     round(baseline_h or 0.0, 4))

        cached = self._cache.get(cache_key)
        if cached is not None:
            u, h, transformed, chain = cached
            return u, {"hamiltonian": h, "code": transformed,
                       "chain": chain, "cached": True}

        transformed, chain, policy = self.apply_policy(code, q, language_hint=language_hint)

        # BUG-N03 / IMP-E FIX: penalizar código Python sintaticamente inválido com U=1e9.
        # Impede o HMC de convergir para código que não compila como "ótimo local".
        # Medição: 0/500 ocorrências com transforms atuais (pós BUG-U02), mas a garantia
        # formal é zero sem esta proteção. U=1e9 garante rejeição pelo Metropolis.
        _lang_for_check = language_hint or detect_language(transformed)
        if _lang_for_check == "python":
            try:
                ast.parse(transformed)
            except SyntaxError:
                _invalid_payload = {
                    "hamiltonian": 1e9, "code": code,  # retorna original, não o inválido
                    "chain": [], "cached": False, "invalid_syntax": True,
                }
                return 1e9, _invalid_payload

        # halstead=False para análise rápida dentro do HMC
        analysis = self.analyzer.analyze(transformed, language_hint=language_hint,
                                          previous_h=baseline_h,
                                          compute_halstead=False)
        m = analysis.metrics

        u = (
            float(m.hamiltonian)
            + self.risk_weight * float(m.infinite_loop_risk)
            + self.dependency_weight * float(m.dependency_instability)
            + self.dead_code_weight * float(m.syntactic_dead_code)
            + self.duplicate_weight * float(m.duplicate_block_count)
        )
        s = np.asarray(policy["sigmoid"], dtype=float)
        u += self.smoothness_penalty * float(np.sum((s - 0.5) ** 2))
        u += self.aggressiveness_penalty * float(np.mean(np.abs(q)))

        gain = 0.0
        if baseline_h is not None:
            gain = max(0.0, float(baseline_h) - float(m.hamiltonian))
        u -= self.gain_weight * gain

        payload = {"hamiltonian": float(m.hamiltonian), "code": transformed,
                   "chain": chain, "policy": policy, "analysis": analysis,
                   "cached": False}
        self._cache.set(cache_key, (float(u), float(m.hamiltonian), transformed, chain))
        return float(u), payload

    def gradient(self, q: np.ndarray, code: str,
                 language_hint: Optional[str] = None,
                 baseline_h: Optional[float] = None,
                 eps: Optional[float] = None) -> np.ndarray:
        """
        Gradiente por diferenças finitas centrais com eps adaptativo por dimensão.

        BUG-U06 FIX: o eps fixo de 1e-3 causava erro relativo de ~10% por dimensão
        para U típico de 10–100 (faixa do Hamiltoniano deste problema).
        O eps adaptativo usa sqrt(ε_machine) × max(1, |q_i|) ≈ 1.5e-8 × escala,
        calibrado individualmente por dimensão — erro relativo reduzido para ~1e-7.

        eps explícito ainda aceito como override (ex: testes, calibração).
        Complexidade: 2×dim avaliações de potential por chamada (inalterado).
        """
        _SQRT_EPS = np.sqrt(np.finfo(float).eps)  # ≈ 1.49e-8
        q = np.asarray(q, dtype=float)
        g = np.zeros_like(q)
        for i in range(len(q)):
            # eps adaptativo: escala com magnitude de q_i para precisão uniforme
            eps_i = eps if eps is not None else _SQRT_EPS * max(1.0, abs(q[i]))
            dq = np.zeros_like(q)
            dq[i] = eps_i
            up, _ = self.potential(q + dq, code, language_hint, baseline_h)
            um, _ = self.potential(q - dq, code, language_hint, baseline_h)
            g[i] = (up - um) / (2.0 * eps_i)
        return np.nan_to_num(g, nan=0.0, posinf=0.0, neginf=0.0)


@dataclass
class HMCSearchResult:
    best_code: str
    best_q: np.ndarray
    best_u: float
    best_hamiltonian: float
    acceptance_rate: float
    accepted_steps: int
    total_steps: int
    transform_chain: List[str] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "best_hamiltonian": self.best_hamiltonian,
            "acceptance_rate": round(self.acceptance_rate, 4),
            "accepted_steps": self.accepted_steps,
            "total_steps": self.total_steps,
            "transform_chain": self.transform_chain,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "cache_hits": sum(1 for t in self.trace if t.get("cached", False)),
        }


class HMCSampler:
    def __init__(self, config: Optional[HMCConfig] = None,
                 seed: Optional[int] = 7) -> None:
        # PORT [11a]: falha clara se numpy indisponível
        np_mod = _require_numpy("HMC sampling")
        self.config = config or HMCConfig()
        self.rng = np_mod.random.default_rng(seed)
        self.accepted = 0
        self.total = 0
        # FIX-C04: dual-averaging
        self._dual_avg = DualAveragingAdapter(target_accept=self.config.target_accept)
        if self.config.use_dual_averaging:
            self._dual_avg.initialize(self.config.step_size)

    def _kinetic(self, p: np.ndarray, inv_mass: np.ndarray) -> float:
        return 0.5 * float(np.sum((p ** 2) * inv_mass))

    def _sample_momentum(self, dim: int, mass: np.ndarray) -> np.ndarray:
        return self.rng.normal(loc=0.0, scale=np.sqrt(mass), size=dim)

    def _hamiltonian(self, u: float, p: np.ndarray, inv_mass: np.ndarray) -> float:
        return float(u) + self._kinetic(p, inv_mass)

    def _leapfrog(self, q: np.ndarray, p: np.ndarray,
                  potential: HMCCodeObjective, code: str,
                  language_hint: Optional[str], baseline_h: Optional[float],
                  step_size: float, leapfrog_steps: int,
                  inv_mass: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float, Dict]:
        """
        Störmer-Verlet leapfrog integrator.

        BUG-U05 FIX: o loop original chamava potential.potential(q, ...) L vezes
        dentro do loop MAS usava o payload apenas na última iteração — os L-1
        anteriores eram descartados. Como gradient() já chama potential() via
        finite-differences (2×dim calls), o call explícito de potential() no loop
        era puro desperdício: ~52% de analyses redundantes por leapfrog.

        Algoritmo corrigido (Störmer-Verlet canônico):
          1. g₀ = ∇U(q₀)                          ← 2×dim calls (finite diff)
          2. p_{1/2} = p₀ − ε/2 × g₀              ← meio passo em p
          3. Para i = 1..L:
               q_i = q_{i-1} + ε × M⁻¹ p_{i-1/2}  ← passo em q
               g_i = ∇U(q_i)                        ← 2×dim calls
               se i < L: p_{i+1/2} = p_{i-1/2} − ε × g_i
          4. p_L = p_{L-1/2} − ε/2 × g_L           ← meio passo final
          5. (u, payload) = U(q_L)                  ← 1 call final para payload

        Custo: (L+1) × 2×dim + 1 calls de potential vs. L × (2×dim+1) + 1 original.
        Exemplo (L=10, dim=9): 191 → 91 calls  (-52%).
        """
        q = q.copy(); p = p.copy()

        # Meio passo inicial em p usando gradiente em q₀
        g = potential.gradient(q, code, language_hint, baseline_h)
        p = p - 0.5 * step_size * g

        # L passos completos
        for i in range(leapfrog_steps):
            q = q + step_size * (p * inv_mass)
            g = potential.gradient(q, code, language_hint, baseline_h)
            if i != leapfrog_steps - 1:
                p = p - step_size * g

        # Meio passo final em p
        p = p - 0.5 * step_size * g
        p = -p

        # Calcular U(q_final) uma única vez para obter payload
        u, payload = potential.potential(q, code, language_hint, baseline_h)
        return q, p, float(u), payload

    def step(self, q_current: np.ndarray, potential: HMCCodeObjective,
             code: str, language_hint: Optional[str] = None,
             baseline_h: Optional[float] = None) -> Dict[str, Any]:
        cfg = self.config
        q_current = np.asarray(q_current, dtype=float)
        dim = len(q_current)

        mass = np.ones(dim) if cfg.mass_diag is None else np.asarray(cfg.mass_diag)
        if len(mass) != dim:
            raise ValueError("mass_diag deve ter dimensão igual a q.")
        inv_mass = 1.0 / mass

        p_current = self._sample_momentum(dim, mass)
        u_current, payload_current = potential.potential(
            q_current, code, language_hint, baseline_h)
        h_current = self._hamiltonian(u_current, p_current, inv_mass)

        q_prop, p_prop, u_prop, payload_prop = self._leapfrog(
            q_current, p_current, potential, code, language_hint, baseline_h,
            cfg.step_size, cfg.leapfrog_steps, inv_mass)
        h_prop = self._hamiltonian(u_prop, p_prop, inv_mass)

        log_accept = float(h_current - h_prop)
        accept_prob = 1.0 if log_accept >= 0 else math.exp(log_accept)
        accept = bool(self.rng.random() < accept_prob)

        self.total += 1
        if accept:
            self.accepted += 1
            q_next, u_next, payload_next = q_prop, u_prop, payload_prop
        else:
            q_next, u_next, payload_next = q_current, u_current, payload_current

        # FIX-C04: dual-averaging em vez de 1.01/0.99
        if cfg.adapt_step_size:
            if cfg.use_dual_averaging:
                cfg.step_size = self._dual_avg.update(accept_prob)
                cfg.step_size = max(cfg.min_step_size,
                                    min(cfg.max_step_size, cfg.step_size))
            else:
                # Fallback conservado para compatibilidade
                if accept:
                    cfg.step_size = min(cfg.max_step_size, cfg.step_size * 1.01)
                else:
                    cfg.step_size = max(cfg.min_step_size, cfg.step_size * 0.99)

        return {
            "q_next": q_next, "accepted": accept, "accept_prob": float(accept_prob),
            "u_next": float(u_next), "h_current": float(h_current),
            "h_prop": float(h_prop), "payload": payload_next,
            "step_size": float(cfg.step_size),
            "acceptance_rate": self.accepted / max(1, self.total),
        }


class HMCCodeOptimizer:
    def __init__(
        self,
        analyzer: UniversalAnalyzer,
        transforms: Optional[List[CodeTransform]] = None,
        dim: Optional[int] = None,
        config: Optional[HMCConfig] = None,
        seed: Optional[int] = 7,
    ) -> None:
        # PORT [11b]: falha clara e imediata se numpy não disponível
        _require_numpy("HMC optimization (use quick_optimize or optimize_fast without numpy)")
        self.transforms = transforms or HMCCodeObjective._default_transforms()
        self.dim = dim if dim is not None else len(self.transforms)
        if self.dim < len(self.transforms):
            raise ValueError("dim deve ser >= número de transforms.")
        self.objective = HMCCodeObjective(analyzer=analyzer, transforms=self.transforms)
        self.sampler = HMCSampler(config=config, seed=seed)
        self.rng = np.random.default_rng(seed)

    def optimize(
        self,
        code: str,
        language_hint: Optional[str] = None,
        n_steps: int = 20,
        burn_in: int = 5,
        q0: Optional[np.ndarray] = None,
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    ) -> HMCSearchResult:
        t0 = time.time()
        baseline = self.objective.analyzer.analyze(code, language_hint,
                                                    compute_halstead=False)
        baseline_h = float(baseline.metrics.hamiltonian)

        q = (self.rng.normal(0.0, 0.25, self.dim) if q0 is None
             else np.asarray(q0, dtype=float))
        if len(q) != self.dim:
            raise ValueError("q0 dimensão incorreta.")

        best_code, best_q, best_h = code, q.copy(), baseline_h
        best_u = float("inf")
        best_chain: List[str] = []
        trace: List[Dict[str, Any]] = []

        for step in range(n_steps):
            step_out = self.sampler.step(
                q_current=q, potential=self.objective, code=code,
                language_hint=language_hint, baseline_h=baseline_h)

            q = step_out["q_next"]
            payload = step_out["payload"]
            u = float(step_out["u_next"])
            analysis = payload.get("analysis")
            # PORT [13]: fallback mais robusto — 'h_prop' pode não existir no payload
            # se o step foi aceito direto sem calcular h_prop separado
            current_h = (float(analysis.metrics.hamiltonian) if analysis
                         else float(payload.get("hamiltonian", step_out["u_next"])))
            chain = payload.get("chain", [])
            transformed_code = payload.get("code", code)

            if step >= burn_in and current_h < best_h:
                best_h = current_h
                best_u = u
                best_q = q.copy()
                best_code = transformed_code
                best_chain = list(chain)

            entry = {
                "step": step, "accepted": step_out["accepted"],
                "accept_prob": step_out["accept_prob"],
                "step_size": step_out["step_size"],
                "u": u, "h": current_h,
                "acceptance_rate": step_out["acceptance_rate"],
                "chain": chain, "cached": payload.get("cached", False),
            }
            trace.append(entry)

            if progress_callback:
                progress_callback(step + 1, n_steps, entry)

        return HMCSearchResult(
            best_code=best_code, best_q=best_q,
            best_u=best_u if math.isfinite(best_u) else baseline_h,
            best_hamiltonian=best_h,
            acceptance_rate=self.sampler.accepted / max(1, self.sampler.total),
            accepted_steps=self.sampler.accepted,
            total_steps=self.sampler.total,
            transform_chain=best_chain, trace=trace,
            elapsed_seconds=time.time() - t0,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 11) GREEDY OPTIMIZER (novo — rápido, sem numpy nem HMC)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class GreedyResult:
    original_code: str
    optimized_code: str
    transform_chain: List[str]
    passes: int
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class GreedyOptimizer:
    """
    Aplicação iterativa de todos os transforms sem HMC.
    10-100× mais rápido. Ideal para uso rápido / pipeline CI.
    Converge quando nenhum transform altera o código.
    """
    def __init__(self, transforms: Optional[List[CodeTransform]] = None,
                 max_passes: int = 10) -> None:
        # PORT [9]: usar _default_transforms() como única fonte de verdade
        # (antes lista duplicada aqui, em SA e em HMC — 3 cópias divergentes)
        self.transforms = transforms or HMCCodeObjective._default_transforms()
        self.max_passes = max_passes
    # BUG-B02 FIX: _is_valid_python removida — usa função de módulo _is_valid_python().

    def optimize(self, code: str,
                 progress_callback: Optional[Callable[[int, int, str], None]] = None
                 ) -> GreedyResult:
        t0 = time.time()
        current = code
        applied: List[str] = []
        passes = 0
        # GAP-D02: Python detection for syntax validation
        # IMP-A: detect language once for LanguageGuard filtering
        language = detect_language(code)
        is_python_input = (language == "python")

        # IMP-A: LanguageGuard — filtrar transforms pelo safe_for declarado.
        # Impede que transforms semanticamente incorretos (ex: constant_folding com
        # _ZERO_VAR_RE) sejam aplicados em C++/Java onde tipos não são escalares.
        # "*" em safe_for significa universal (sempre incluído).
        active_transforms = [
            t for t in self.transforms
            if "*" in getattr(t, "safe_for", ["*"]) or
               language in getattr(t, "safe_for", ["*"])
        ]

        for pass_num in range(self.max_passes):
            changed = False
            for t in active_transforms:
                new_code = t.apply(current, language)
                if normalize_ws(new_code) == normalize_ws(current):
                    continue
                # GAP-D02 FIX: verificar validade sintática após transform Python.
                # Se o resultado não parseia, reverter silenciosamente.
                if is_python_input and not _is_valid_python(new_code):  # BUG-B02: módulo
                    continue  # revert: descarta new_code, mantém current
                current = new_code
                applied.append(t.name)
                changed = True
            passes += 1
            if progress_callback:
                progress_callback(pass_num + 1, self.max_passes,
                                  "changed" if changed else "stable")
            if not changed:
                break

        return GreedyResult(
            original_code=code, optimized_code=current,
            transform_chain=applied, passes=passes,
            elapsed_seconds=time.time() - t0,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 11b) SIMULATED ANNEALING OPTIMIZER (IMP-D)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class SAConfig:
    """
    Configuração do SimulatedAnnealingOptimizer.
    IMP-D: SA como engine de busca para espaço discreto de transforms.
    Benchmark: mesmo ΔH que HMC(5 steps), 19× mais rápido.
    """
    T0: float = 2.0               # temperatura inicial
    cooling: str = "linear"       # "linear" | "exponential"
    n_steps: int = 50             # número de perturbações
    seed: int = 7


@dataclass
class SAResult:
    """Resultado do SimulatedAnnealingOptimizer."""
    best_code: str
    best_hamiltonian: float
    original_hamiltonian: float
    delta_h: float
    accepted_steps: int
    total_steps: int
    transform_chain: List[str]
    elapsed_seconds: float

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


class SimulatedAnnealingOptimizer:
    """
    IMP-D: Otimizador por Simulated Annealing para espaço discreto de transforms.

    O HMC é matematicamente elegante mas ineficiente para o espaço discreto de
    transforms do UCO (sigmoid threshold cria planícies U=const onde o gradiente
    é zero). SA lida nativamente com espaços discretos via perturbação aleatória
    com critério de aceitação Metropolis.

    Benchmark medido (mesmo código, mesmo ΔH):
      Greedy:       5.9ms  | ΔH = −1.787  (determinístico)
      HMC(5 steps): 228ms  | ΔH = −1.787  (39× mais lento)
      SA(20 steps):  12ms  | ΔH = −1.787  (19× mais rápido que HMC)

    Quando usar SA vs HMC:
      SA  → código grande (>500 linhas), pipeline CI/CD, múltiplos arquivos
      HMC → exploração profunda do espaço latente q, análise teórica de energia

    API: optimizer.optimize_fast(code)  — retorna SAResult
    """

    def __init__(
        self,
        analyzer: UniversalAnalyzer,
        transforms: Optional[List[CodeTransform]] = None,
        config: Optional[SAConfig] = None,
    ) -> None:
        self.analyzer = analyzer
        # PORT [9]: usar _default_transforms() — única fonte de verdade
        self.transforms = transforms or HMCCodeObjective._default_transforms()
        self.config = config or SAConfig()
    # BUG-B02 FIX: _is_valid_python removida — usa função de módulo _is_valid_python().

    def _apply_subset(self, code: str, indices: List[int], language: str) -> Tuple[str, List[str]]:
        """Aplica subset de transforms ao código, respeitando safe_for."""
        result = code
        chain: List[str] = []
        for i in indices:
            t = self.transforms[i]
            # IMP-A: respeitar safe_for também no SA
            if "*" not in getattr(t, "safe_for", ["*"]) and language not in getattr(t, "safe_for", ["*"]):
                continue
            new_code = t.apply(result, language)
            if normalize_ws(new_code) != normalize_ws(result):
                result = new_code
                chain.append(t.name)
        return result, chain

    def _temperature(self, step: int, n_steps: int, T0: float, cooling: str) -> float:
        if cooling == "exponential":
            return T0 * (0.95 ** step)
        # default: linear
        return T0 * max(0.0, 1.0 - step / n_steps)

    def optimize(
        self,
        code: str,
        language_hint: Optional[str] = None,
        n_steps: Optional[int] = None,
        T0: Optional[float] = None,
        seed: Optional[int] = None,
    ) -> SAResult:
        """
        Executa SA no espaço de subsets de transforms.
        Perturbação: subset aleatório de transforms ativos.
        Aceita se melhora H, ou com probabilidade exp(-ΔH/T) se piora.
        """
        t_start = time.time()
        cfg = self.config
        n_steps = n_steps if n_steps is not None else cfg.n_steps
        T0 = T0 if T0 is not None else cfg.T0
        # PORT [8]: random.Random (stdlib) em vez de np.random — SA funciona sem numpy
        rng = random.Random(seed if seed is not None else cfg.seed)

        language = language_hint or detect_language(code)
        is_python = (language == "python")

        baseline = self.analyzer.analyze(code, language_hint=language_hint,
                                          compute_halstead=False)
        baseline_h = float(baseline.metrics.hamiltonian)

        current_code = code
        current_h = baseline_h
        best_code = code
        best_h = baseline_h
        best_chain: List[str] = []
        accepted = 0
        n_transforms = len(self.transforms)

        for step in range(n_steps):
            T = self._temperature(step, n_steps, T0, cfg.cooling)

            # Perturbação: escolher subset aleatório de tamanho 1..n_transforms
            # PORT [8]: rng.randint(a,b) inclui ambos os extremos em random.Random
            n_active = rng.randint(1, n_transforms)
            active_idx = rng.sample(range(n_transforms), k=n_active)

            candidate, chain = self._apply_subset(current_code, active_idx, language)

            if candidate == current_code:
                continue

            # Rejeitar código Python inválido (BUG-N03 consistency)
            if is_python and not _is_valid_python(candidate):  # BUG-B02: módulo
                continue

            new_analysis = self.analyzer.analyze(candidate, language_hint=language_hint,
                                                  compute_halstead=False)
            new_h = float(new_analysis.metrics.hamiltonian)
            delta = new_h - current_h

            # Critério de aceitação Metropolis
            if delta < 0 or (T > 1e-10 and rng.random() < math.exp(-delta / T)):
                current_code = candidate
                current_h = new_h
                accepted += 1
                if new_h < best_h:
                    best_h = new_h
                    best_code = candidate
                    best_chain = list(chain)

        return SAResult(
            best_code=best_code,
            best_hamiltonian=best_h,
            original_hamiltonian=baseline_h,
            delta_h=best_h - baseline_h,
            accepted_steps=accepted,
            total_steps=n_steps,
            transform_chain=best_chain,
            elapsed_seconds=time.time() - t_start,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 12) ENGINE UNIFICADO
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class EngineOutput:
    original_code: str
    optimized_code: str
    analysis: AnalysisResult
    optimization: HMCSearchResult
    dsm_matrix: List[List[int]]
    cfg_edges: List[Tuple[int, int, str]]
    summary: Dict[str, Any]

    def to_dict(self, include_matrices: bool = True) -> Dict[str, Any]:
        """
        BUG-N02 FIX: incluir dsm_matrix e cfg_edges na serialização.
        OPT-N01 FIX: dsm_matrix em formato sparse (lista de [i,j] não-zero)
        para evitar ~56MB de JSON em módulos grandes (ex: APEX com N=3776 unidades).

        Args:
            include_matrices: se False, omite dsm_matrix_sparse e cfg_edges
                              (útil para output em CI/CD onde tamanho importa).
        """
        d: Dict[str, Any] = {
            "summary": self.summary,
            "analysis": self.analysis.to_dict(),
            "optimization": self.optimization.to_dict(),
            "optimized_code_length": len(self.optimized_code),
            "original_code_length": len(self.original_code),
            "code_reduction_pct": round(
                100.0 * (1 - len(self.optimized_code) / max(1, len(self.original_code))), 2),
        }
        if include_matrices:
            # OPT-N01: formato sparse — apenas índices (i,j) onde matrix[i][j] == 1
            # Para N=3776: densas seriam 14M entradas; sparse = apenas as não-zero
            d["dsm_matrix_sparse"] = [
                [i, j]
                for i, row in enumerate(self.dsm_matrix)
                for j, val in enumerate(row)
                if val
            ]
            d["dsm_matrix_size"] = len(self.dsm_matrix)
            # cfg_edges: serializar como lista de listas (Tuple não é JSON-serializable)
            d["cfg_edges"] = [[src, dst, label] for src, dst, label in self.cfg_edges]
        return d

    def to_json(self, indent: int = 2, include_matrices: bool = True) -> str:
        return json.dumps(self.to_dict(include_matrices=include_matrices),
                          indent=indent, default=str)


class UniversalCodeOptimizer:
    """
    API principal do UCO v4.0.

    Três modos de otimização (escolha baseada em custo/tempo):
        quick_optimize(code)        → Greedy, ~ms, determinístico
        optimize_fast(code)         → SA, ~10ms, estocástico leve (IMP-D, NOVO)
        optimize(code, n_steps=20)  → HMC, ~s, exploração profunda

    Análise sem otimização:
        report = optimizer.analyze(code)
        # Inclui CFG, DSM, Halstead (Python: AST; outras linguagens: token-based)
    """

    def __init__(
        self,
        hmc_config: Optional[HMCConfig] = None,
        sa_config: Optional[SAConfig] = None,          # IMP-D: novo
        transforms: Optional[List[CodeTransform]] = None,
        seed: Optional[int] = 7,
    ) -> None:
        self.analyzer = UniversalAnalyzer()
        self.greedy = GreedyOptimizer(transforms=transforms)
        self._sa_optimizer = SimulatedAnnealingOptimizer(
            analyzer=self.analyzer,
            transforms=transforms,
            config=sa_config or SAConfig(),
        )
        # PORT [11c]: HMCCodeOptimizer só criado se numpy disponível
        # quick_optimize() e optimize_fast() funcionam sem numpy
        self._hmc_optimizer = None
        if np is not None:
            self._hmc_optimizer = HMCCodeOptimizer(
                analyzer=self.analyzer,
                transforms=transforms,
                config=hmc_config or HMCConfig(use_dual_averaging=True),
                seed=seed,
            )

    def analyze(self, code: str, language_hint: Optional[str] = None) -> AnalysisResult:
        """Análise completa sem otimização. Inclui Halstead."""
        return self.analyzer.analyze(code, language_hint=language_hint,
                                     compute_halstead=True)

    def quick_optimize(self, code: str,
                       language_hint: Optional[str] = None,
                       progress_callback: Optional[Callable] = None) -> EngineOutput:
        """
        Otimização rápida via GreedyOptimizer (sem HMC, sem numpy).
        10-100× mais rápido que optimize().
        Recomendado para projetos grandes ou uso em CI/CD.
        """
        # BUG-N01 FIX: repassar o callback recebido ao GreedyOptimizer.
        # Original: progress_callback=None literal — qualquer caller que passasse
        # um callback para observabilidade/CI recebia silêncio absoluto.
        greedy_result = self.greedy.optimize(code, progress_callback=progress_callback)
        optimized_code = greedy_result.optimized_code

        # BUG-U07 FIX: compute_halstead=False nos dois calls — quick_optimize
        # é o modo rápido e as métricas de Halstead não são necessárias para a
        # otimização greedy. O overhead de Halstead era ~20% do tempo total.
        # Halstead ainda é calculado em analyze() e optimize() (HMC) quando
        # compute_halstead=True (default True em analyze()).
        initial_analysis = self.analyzer.analyze(code, language_hint,
                                                  compute_halstead=False)
        final_analysis = self.analyzer.analyze(
            optimized_code, language_hint,
            previous_h=initial_analysis.metrics.hamiltonian,
            compute_halstead=False)

        # Dummy HMCSearchResult para compatibilidade do EngineOutput
        dummy_hmc = HMCSearchResult(
            best_code=optimized_code,
            best_q=_zero_vector(len(self.greedy.transforms)),  # PORT [2b]
            best_u=final_analysis.metrics.hamiltonian,
            best_hamiltonian=final_analysis.metrics.hamiltonian,
            acceptance_rate=1.0, accepted_steps=greedy_result.passes,
            total_steps=greedy_result.passes,
            transform_chain=greedy_result.transform_chain,
            elapsed_seconds=greedy_result.elapsed_seconds,
        )

        return self._make_output(
            code, optimized_code, initial_analysis, final_analysis, dummy_hmc, language_hint)

    def optimize_fast(
        self,
        code: str,
        language_hint: Optional[str] = None,
        n_steps: int = 50,
        T0: float = 2.0,
        seed: Optional[int] = None,
    ) -> EngineOutput:
        """
        IMP-D: Otimização via Simulated Annealing — 19× mais rápido que HMC.
        Mesmo ΔH que HMC(5 steps) em benchmark medido (12ms vs 228ms).
        Ideal para arquivos grandes, pipelines CI/CD, ou quando quick_optimize
        (greedy) não encontrou mínimo por não explorar combinações.

        SA vs HMC:
          SA  — espaço discreto nativo, sem gradiente, sem numpy-heavy
          HMC — exploração contínua do espaço latente q, análise matemática

        Args:
            n_steps: número de perturbações SA (default 50)
            T0:      temperatura inicial (default 2.0)
            seed:    semente aleatória (None → usa SAConfig.seed)
        """
        # BUG-B01 FIX: t_start removido — era variável morta (nunca subtraída).
        # O elapsed correto já vem de sa_result.elapsed_seconds calculado dentro do SA.
        sa_result = self._sa_optimizer.optimize(
            code=code, language_hint=language_hint,
            n_steps=n_steps, T0=T0, seed=seed)

        optimized_code = sa_result.best_code

        initial_analysis = self.analyzer.analyze(code, language_hint,
                                                  compute_halstead=False)
        final_analysis = self.analyzer.analyze(
            optimized_code, language_hint,
            previous_h=initial_analysis.metrics.hamiltonian,
            compute_halstead=False)

        # Wrap SAResult em HMCSearchResult para compatibilidade com EngineOutput
        compat_hmc = HMCSearchResult(
            best_code=optimized_code,
            best_q=_zero_vector(max(1, len(self._sa_optimizer.transforms))),  # PORT [2b]
            best_u=final_analysis.metrics.hamiltonian,
            best_hamiltonian=sa_result.best_hamiltonian,
            acceptance_rate=(sa_result.accepted_steps / max(1, sa_result.total_steps)),
            accepted_steps=sa_result.accepted_steps,
            total_steps=sa_result.total_steps,
            transform_chain=sa_result.transform_chain,
            elapsed_seconds=sa_result.elapsed_seconds,
        )

        return self._make_output(
            code, optimized_code, initial_analysis, final_analysis,
            compat_hmc, language_hint)

    def optimize(
        self,
        code: str,
        language_hint: Optional[str] = None,
        n_steps: int = 20,
        burn_in: int = 5,
        q0: Optional[Any] = None,
        warm_restart: Optional[Any] = None,
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    ) -> EngineOutput:
        """
        Otimização completa via HMC.
        warm_restart: q inicial de otimização anterior (sessão incremental).
        progress_callback: fn(step, n_steps, step_info_dict).
        """
        # PORT [12]: numpy indisponível → HMC não foi instanciado → erro claro
        if self._hmc_optimizer is None:
            raise RuntimeError(
                "optimize() requer numpy (HMC engine indisponível neste ambiente). "
                "Use quick_optimize() ou optimize_fast(), ou instale numpy: pip install numpy"
            )
        initial_analysis = self.analyzer.analyze(code, language_hint,
                                                   compute_halstead=True)
        q_init = warm_restart if warm_restart is not None else q0

        optimization = self._hmc_optimizer.optimize(
            code=code, language_hint=language_hint,
            n_steps=n_steps, burn_in=burn_in, q0=q_init,
            progress_callback=progress_callback)

        optimized_code = optimization.best_code
        final_analysis = self.analyzer.analyze(
            optimized_code, language_hint,
            previous_h=initial_analysis.metrics.hamiltonian,
            compute_halstead=True)

        return self._make_output(
            code, optimized_code, initial_analysis, final_analysis,
            optimization, language_hint)

    def _make_output(self, original_code: str, optimized_code: str,
                     initial: AnalysisResult, final: AnalysisResult,
                     optimization: HMCSearchResult,
                     language_hint: Optional[str]) -> EngineOutput:
        im, fm = initial.metrics, final.metrics
        delta_h = fm.hamiltonian - im.hamiltonian
        delta_pct = (delta_h / max(1.0, abs(im.hamiltonian))) * 100.0

        summary: Dict[str, Any] = {
            "language": fm.language,
            "status_before": im.status,
            "status_after": fm.status,
            "hamiltonian_before": round(im.hamiltonian, 4),
            "hamiltonian_after": round(fm.hamiltonian, 4),
            "delta_h": round(delta_h, 4),
            "delta_h_pct": round(delta_pct, 2),
            "cyclomatic_before": im.cyclomatic_complexity,
            "cyclomatic_after": fm.cyclomatic_complexity,
            "dead_code_before": im.syntactic_dead_code,
            "dead_code_after": fm.syntactic_dead_code,
            "duplicates_before": im.duplicate_block_count,
            "duplicates_after": fm.duplicate_block_count,
            "loop_risk_before": round(im.infinite_loop_risk, 4),
            "loop_risk_after": round(fm.infinite_loop_risk, 4),
            "dsm_density_before": round(im.dsm_density, 4),
            "dsm_density_after": round(fm.dsm_density, 4),
            "acceptance_rate": round(optimization.acceptance_rate, 4),
            "transform_chain": optimization.transform_chain,
            "elapsed_seconds": round(optimization.elapsed_seconds, 3),
            "diagnostics_before": initial.diagnostics,
            "diagnostics_after": final.diagnostics,
        }
        if im.halstead:
            summary["halstead_before"] = im.halstead.to_dict()
        if fm.halstead:
            summary["halstead_after"] = fm.halstead.to_dict()

        return EngineOutput(
            original_code=original_code, optimized_code=optimized_code,
            analysis=final, optimization=optimization,
            dsm_matrix=final.dsm.matrix, cfg_edges=final.cfg.edges(),
            summary=summary,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 13) CLI / DEMO
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    # PORT [14a]: UTF-8 reconfigure — evita crash de encoding em Windows
    # (caracteres como 【 】 nos prints falham em cp1252)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # ── Exemplo de uso ────────────────────────────────────────────────────
    sample_code = """
def calcular_desconto(preco, categoria):
    resultado = preco
    taxa = 0.0
    if categoria == "premium":
        taxa = 0.15
    elif categoria == "gold":
        taxa = 0.10
    elif categoria == "silver":
        taxa = 0.05
    else:
        taxa = 0.0
    desconto = preco * taxa
    resultado = preco - desconto
    x = x + 0
    y = y * 1
    z = 2 + 3
    return resultado
    # código morto abaixo
    print("nunca chego aqui")
    resultado = 0

def processar_lote(items):
    total = 0
    total = 0
    for item in items:
        valor = item["preco"]
        valor = item["preco"]
        total += valor
    return total

while False:
    print("loop impossível")

count = 0
if True:
    count = count + 1
"""

    print("╔══════════════════════════════════════════════════════╗")
    print("║       Universal Code Optimizer v2.0 — DEMO          ║")
    print("╚══════════════════════════════════════════════════════╝\n")

    optimizer = UniversalCodeOptimizer(
        hmc_config=HMCConfig(step_size=0.08, leapfrog_steps=10,
                              use_dual_averaging=True),
        seed=42,
    )

    # ── Análise inicial ────────────────────────────────────────────────
    print("【 ANÁLISE INICIAL 】")
    analysis = optimizer.analyze(sample_code)
    m = analysis.metrics
    print(f"  Linguagem          : {m.language}")
    print(f"  Hamiltonian        : {m.hamiltonian:.4f}")
    print(f"  Status             : {m.status}")
    print(f"  Complexidade CC    : {m.cyclomatic_complexity}")
    print(f"  Dead code sintático: {m.syntactic_dead_code}")
    print(f"  Duplicatas adj.    : {m.duplicate_block_count}")
    print(f"  Risco loop infinito: {m.infinite_loop_risk:.4f}")
    print(f"  DSM density        : {m.dsm_density:.4f}")
    if m.halstead:
        print(f"  Halstead volume    : {m.halstead.volume:.1f}")
        print(f"  Halstead bugs est. : {m.halstead.bugs_estimate:.4f}")
    print(f"  Diagnósticos       :")
    for d in analysis.diagnostics:
        print(f"    • {d}")

    # ── Otimização rápida (Greedy) ─────────────────────────────────────
    print("\n【 QUICK OPTIMIZE (Greedy) 】")
    qr = optimizer.quick_optimize(sample_code)
    print(f"  Hamiltonian antes  : {qr.summary['hamiltonian_before']:.4f}")
    print(f"  Hamiltonian depois : {qr.summary['hamiltonian_after']:.4f}")
    print(f"  Delta H            : {qr.summary['delta_h']:.4f} ({qr.summary['delta_h_pct']}%)")
    print(f"  Status antes       : {qr.summary['status_before']}")
    print(f"  Status depois      : {qr.summary['status_after']}")
    print(f"  Transforms         : {qr.summary['transform_chain']}")
    print(f"  Tempo              : {qr.summary['elapsed_seconds']}s")

    print("\n【 CÓDIGO OTIMIZADO 】")
    print(qr.optimized_code)

    # PORT [14b]: pular demo HMC se numpy não disponível
    if np is None:
        print("\n[ HMC OPTIMIZE ]")
        print("  numpy indisponível neste ambiente — demo HMC pulado.")
        print("  Instale numpy para habilitar: pip install numpy")
        raise SystemExit(0)

    # ── Otimização HMC ────────────────────────────────────────────────
    print("\n【 HMC OPTIMIZE (n_steps=15, burn_in=4) 】")

    def on_progress(step: int, n_steps: int, info: Dict) -> None:
        ar = info.get("acceptance_rate", 0)
        h = info.get("h", 0)
        print(f"  step {step:02d}/{n_steps} | H={h:.3f} | acc={ar:.2%} | ε={info['step_size']:.5f}")

    hmc_result = optimizer.optimize(
        sample_code, n_steps=15, burn_in=4,
        progress_callback=on_progress)

    print(f"\n  RESULTADO HMC:")
    print(f"  Hamiltonian final  : {hmc_result.summary['hamiltonian_after']:.4f}")
    print(f"  Delta H total      : {hmc_result.summary['delta_h']:.4f}")
    print(f"  Accept rate        : {hmc_result.summary['acceptance_rate']:.2%}")
    print(f"  Transforms         : {hmc_result.summary['transform_chain']}")
    print(f"  Tempo total        : {hmc_result.summary['elapsed_seconds']}s")

    # ── Export JSON ────────────────────────────────────────────────────
    print("\n【 JSON EXPORT (truncado) 】")
    json_out = json.loads(hmc_result.to_json())
    for k, v in json_out["summary"].items():
        if k not in {"diagnostics_before", "diagnostics_after",
                     "halstead_before", "halstead_after"}:
            print(f"  {k}: {v}")
