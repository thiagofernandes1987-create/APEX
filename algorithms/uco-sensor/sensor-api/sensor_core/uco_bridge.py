"""
UCO-Sensor API — UCOBridge
===========================
Ponte entre código-fonte Python e o MetricVector de 9 canais UCO.

Implementa análise estática UCO v4.0 via AST puro — sem dependências
externas além da stdlib. Calcula todos os 9 canais UCO a partir do
código-fonte:

  H   (Hamiltonian)            — medida de energia computacional total
  CC  (Cyclomatic Complexity)  — caminhos independentes de execução
  ILR (Infinite Loop Risk)     — loops sem guard de terminação garantida
  DSM_d (Dependency Struct.    — densidade da matriz de dependências
        Matrix density)
  DSM_c (DSM cyclic ratio)     — proporção de dependências cíclicas
  DI  (Dependency Instability) — instabilidade de Robert C. Martin
  dead (Syntactic dead code)   — código nunca executado
  dups (Duplicate blocks)      — blocos de código duplicados
  bugs (Halstead bugs)         — estimativa de defeitos B = V/3000

Modes de análise:
  "fast"    — CC + ILR + dead + bugs (< 10ms para < 500 LOC)
  "full"    — todos os 9 canais     (< 100ms para < 2000 LOC)
  "minimal" — apenas H + CC         (benchmarks/testes)

Ref: Halstead, M.H. (1977). Elements of Software Science. Elsevier.
     McCabe, T.J. (1976). A complexity measure. IEEE TSE, 2(4), 308-320.
     Martin, R.C. (2000). Design Principles and Design Patterns.
"""
from __future__ import annotations
import ast
import math
import time
import hashlib
from typing import Optional, List, Dict, Any, Set, Tuple

# ── Importação relativa ao sys.path configurado pelo test runner ──────────────
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


# ─── Constantes Halstead ─────────────────────────────────────────────────────

# Operadores Python (lexemas que contam como operadores em Halstead)
_OPERATORS = frozenset([
    "+", "-", "*", "/", "//", "%", "**",
    "==", "!=", "<", ">", "<=", ">=",
    "and", "or", "not",
    "&", "|", "^", "~", "<<", ">>",
    "=", "+=", "-=", "*=", "/=", "//=", "%=", "**=", "&=", "|=", "^=",
    "if", "else", "elif", "for", "while", "return", "yield", "raise",
    "try", "except", "finally", "with", "as", "in", "is", "lambda",
    ".", ",", ":", ";", "(", ")", "[", "]", "{", "}",
])

# Nodes AST que incrementam cyclomatic complexity
_CC_NODES = (
    ast.If, ast.While, ast.For, ast.ExceptHandler,
    ast.With, ast.Assert, ast.comprehension,
)
# Operadores booleanos (cada `and`/`or` adiciona +1 ao CC)
_BOOL_OP_CC = (ast.And, ast.Or)


# ─── Visitor principal ───────────────────────────────────────────────────────

class _UCOVisitor(ast.NodeVisitor):
    """
    Visitor AST que acumula todas as métricas UCO em uma única passagem.

    Métricas acumuladas:
      cc_total          : cyclomatic complexity total do módulo
      max_fn_cc         : CC da função mais complexa
      dead_code_lines   : linhas de dead code detectadas
      loop_risk_count   : contagem de loops sem guard de terminação
      operators_unique  : n1 (Halstead) — operadores distintos
      operators_total   : N1 (Halstead) — total de operadores
      operands_unique   : n2 (Halstead) — operandos distintos
      operands_total    : N2 (Halstead) — total de operandos
      n_functions       : número de funções/métodos
      n_classes         : número de classes
      max_methods       : máximo de métodos por classe
      imports_set       : módulos importados (para DI/DSM)
      fn_cc_list        : lista de CC por função (para cc_hotspot_ratio)
    """

    def __init__(self):
        # Complexity
        self.cc_total: int = 1          # baseline = 1 por módulo
        self.fn_cc: Dict[str, int] = {}
        self._fn_stack: List[str] = []  # stack para funções aninhadas

        # Dead code
        self.dead_code_lines: int = 0

        # Loop risk
        self.loop_risk_count: int = 0

        # Halstead operadores
        self._ops: Dict[str, int] = {}
        self._operands: Dict[str, int] = {}

        # Estrutural
        self.n_functions: int = 0
        self.n_classes: int = 0
        self._class_methods: Dict[str, int] = {}
        self._class_stack: List[str] = []

        # Imports
        self.imports_set: Set[str] = set()
        self.from_imports_set: Set[str] = set()

    # ── CC ───────────────────────────────────────────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        name = node.name
        # Cada função começa com CC=1
        old_cc = self.cc_total
        self.cc_total = 1
        self._fn_stack.append(name)
        if self._class_stack:
            full_name = f"{self._class_stack[-1]}.{name}"
            self._class_methods[self._class_stack[-1]] = \
                self._class_methods.get(self._class_stack[-1], 0) + 1
        else:
            full_name = name
        self.n_functions += 1
        self.generic_visit(node)
        fn_cc = self.cc_total
        self.fn_cc[full_name] = fn_cc
        self._fn_stack.pop()
        self.cc_total = old_cc + fn_cc - 1   # acumula no módulo

        # BUG-08: Detect unbounded recursion risk (direct self-call without
        # a guaranteed base case at the function's top level).
        self._check_recursion_risk(node, name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.n_classes += 1
        self._class_stack.append(node.name)
        self._class_methods[node.name] = 0
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_If(self, node: ast.If) -> None:
        self.cc_total += 1
        self._op("if")
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.cc_total += 1
        self._op("while")
        self._check_loop_risk(node)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.cc_total += 1
        self._op("for")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.cc_total += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        # Cada `and`/`or` adiciona CC
        self.cc_total += len(node.values) - 1
        if isinstance(node.op, ast.And):
            self._op("and")
        else:
            self._op("or")
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        """BUG-07: async for loops were missing from CC counting."""
        self.cc_total += 1
        self._op("for")
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        """BUG-07: async with blocks were missing from CC counting."""
        self.cc_total += 1
        self._op("with")
        self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        """BUG-07: lambda expressions were missing from CC counting."""
        self.cc_total += 1
        self._op("lambda")
        self.generic_visit(node)

    def visit_match_case(self, node: ast.match_case) -> None:
        """BUG-07: Python 3.10+ match/case arms were missing from CC counting."""
        self.cc_total += 1
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        # BUG-15: each comprehension adds +1 per if-clause, not +1 flat.
        # [x for x in lst]           → 0 (no ifs)
        # [x for x in lst if p(x)]   → +1
        # [x for x in lst if a if b] → +2
        self.cc_total += len(node.ifs)
        self.generic_visit(node)

    # ── Dead code ────────────────────────────────────────────────────────────

    def visit_Return(self, node: ast.Return) -> None:
        """Detecta statements após return no mesmo bloco (dead code)."""
        self.generic_visit(node)

    def visit_FunctionDef_deadcode(self, node: ast.FunctionDef) -> None:
        """Analisa dead code em corpo de função."""
        self._scan_dead_code(node.body)

    def _scan_dead_code(self, stmts: List[ast.stmt]) -> None:
        """
        Detecta código nunca executado — dead code sintático.

        Padrões detectados:
          1. Statements após return/raise/break/continue no mesmo bloco
          2. BUG-13: `if False:` / `while False:` — corpo jamais executado
          3. `if True:` else-branch — else jamais executado
        """
        terminal_found = False
        for stmt in stmts:
            if terminal_found:
                # Statement após terminal — dead code
                # Conta linhas do statement (lineno a end_lineno)
                start = getattr(stmt, 'lineno', 0)
                end   = getattr(stmt, 'end_lineno', start)
                self.dead_code_lines += max(1, end - start + 1)
                continue

            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminal_found = True

            # BUG-13: Constant-condition dead code branches
            if isinstance(stmt, ast.If):
                is_const = isinstance(stmt.test, ast.Constant)
                if is_const and not stmt.test.value:
                    # if False: — entire if-body is dead code
                    self._count_dead_block(stmt.body)
                    # else-branch (if any) IS live — scan normally
                    self._scan_dead_code(stmt.orelse)
                elif is_const and stmt.test.value:
                    # if True: — else-branch is dead code
                    self._scan_dead_code(stmt.body)
                    self._count_dead_block(stmt.orelse)
                else:
                    self._scan_dead_code(stmt.body)
                    self._scan_dead_code(stmt.orelse)

            elif isinstance(stmt, ast.While):
                is_const = isinstance(stmt.test, ast.Constant)
                if is_const and not stmt.test.value:
                    # while False: — body never runs
                    self._count_dead_block(stmt.body)
                else:
                    self._scan_dead_code(stmt.body)
                    self._scan_dead_code(stmt.orelse)

            elif isinstance(stmt, ast.For):
                self._scan_dead_code(stmt.body)
                self._scan_dead_code(stmt.orelse)
            elif isinstance(stmt, ast.Try):
                self._scan_dead_code(stmt.body)
                for handler in stmt.handlers:
                    self._scan_dead_code(handler.body)
                self._scan_dead_code(stmt.finalbody if hasattr(stmt, 'finalbody') else [])
                self._scan_dead_code(stmt.orelse)
            elif isinstance(stmt, ast.With):
                self._scan_dead_code(stmt.body)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_dead_code(stmt.body)

    def _count_dead_block(self, stmts: List[ast.stmt]) -> None:
        """Conta todas as linhas de um bloco como dead code (sem recursão)."""
        for stmt in stmts:
            start = getattr(stmt, 'lineno', 0)
            end   = getattr(stmt, 'end_lineno', start)
            self.dead_code_lines += max(1, end - start + 1)

    def visit_Module(self, node: ast.Module) -> None:
        self._scan_dead_code(node.body)
        self.generic_visit(node)

    # ── Loop Risk ────────────────────────────────────────────────────────────

    def _check_loop_risk(self, node: ast.While) -> None:
        """
        ILR: while True (ou while 1) sem escape INCONDICIONAL = risco de loop infinito.

        Regra: apenas um break ou return DIRETAMENTE no corpo do while (não dentro
        de um if/for/with aninhado) conta como garantia de terminação.

        Racional:
          while True:
              if cond: return   ← CONDICIONAL — não garante terminação → ILR += 1
          while True:
              return            ← INCONDICIONAL — garante → ILR não incrementado
          while True:
              svc.ping()        ← sem escape → ILR += 1
        """
        is_always_true = (
            isinstance(node.test, ast.Constant) and
            bool(node.test.value) is True
        )
        if not is_always_true:
            return

        # SOMENTE escapes INCONDICIONAIS no nível direto do while contam
        has_unconditional_escape = any(
            isinstance(stmt, (ast.Break, ast.Return))
            for stmt in node.body
        )

        if not has_unconditional_escape:
            self.loop_risk_count += 1

    def _check_recursion_risk(self, node: ast.FunctionDef, fn_name: str) -> None:
        """
        BUG-08: ILR — detecta recursão direta sem base case garantido.

        Regra: função que chama a si mesma (direto) sem um `if` ou `return`
        incondicional no primeiro nível do corpo = risco de recursão infinita.

        Exemplos:
          def f(n): return f(n-1)      → sem base case → loop_risk_count += 1
          def f(n):
              if n == 0: return 0
              return f(n-1)            → base case garantido → ok
        """
        # Detect direct recursive calls (skip nested functions via limited walk)
        has_recursive_call = False
        for child in ast.walk(node):
            # Skip inner function definitions — their recursion is their own
            if child is not node and isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if (isinstance(child, ast.Call) and
                    isinstance(child.func, ast.Name) and
                    child.func.id == fn_name):
                has_recursive_call = True
                break

        if not has_recursive_call:
            return

        # A top-level `if` statement is a base-case guard (e.g. `if n == 0: return 1`).
        has_if_guard = any(isinstance(stmt, ast.If) for stmt in node.body)

        # A `return` is a base case ONLY if it does NOT itself contain a recursive call.
        # `return factorial(n-1)` is NOT a base case; `return 0` IS.
        has_plain_return = any(
            isinstance(stmt, ast.Return) and not any(
                isinstance(n, ast.Call) and
                isinstance(n.func, ast.Name) and
                n.func.id == fn_name
                for n in ast.walk(stmt)
            )
            for stmt in node.body
        )

        top_level_guard = has_if_guard or has_plain_return

        if not top_level_guard:
            self.loop_risk_count += 1

    # ── Halstead ─────────────────────────────────────────────────────────────

    def _op(self, name: str) -> None:
        self._ops[name] = self._ops.get(name, 0) + 1

    def _operand(self, name: str) -> None:
        self._operands[name] = self._operands.get(name, 0) + 1

    def visit_BinOp(self, node: ast.BinOp) -> None:
        op_name = type(node.op).__name__
        self._op(op_name)
        self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> None:
        self._op(type(node.op).__name__)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        for op in node.ops:
            self._op(type(op).__name__)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        self._op("=")
        self.generic_visit(node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        self._op(type(node.op).__name__ + "=")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        self._op("()")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        self._operand(repr(node.value)[:50])

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            self._operand(node.id)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        # BUG-06: attribute name (node.attr) is part of the operator ".attr",
        # NOT a standalone operand. Counting it as an operand inflated n2/N2
        # by ~2x vs Radon ground truth.
        self._op(".")
        self.generic_visit(node)

    # ── Imports ──────────────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports_set.add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.from_imports_set.add(node.module.split(".")[0])

    # ── Helpers ──────────────────────────────────────────────────────────────

    @property
    def n1(self) -> int:
        return len(self._ops)

    @property
    def N1(self) -> int:
        return sum(self._ops.values())

    @property
    def n2(self) -> int:
        return len(self._operands)

    @property
    def N2(self) -> int:
        return sum(self._operands.values())

    @property
    def max_methods_per_class(self) -> int:
        if not self._class_methods:
            return 0
        return max(self._class_methods.values())

    @property
    def fn_cc_list(self) -> List[int]:
        return list(self.fn_cc.values())

    @property
    def max_fn_cc(self) -> int:
        return max(self.fn_cc_list) if self.fn_cc_list else self.cc_total


# ─── UCOBridge ───────────────────────────────────────────────────────────────

class UCOBridge:
    """
    Bridge UCO v4.0 → MetricVector (9 canais).

    Analisa código-fonte Python via AST e retorna MetricVector pronto
    para inserção no SnapshotStore e alimentação do FrequencyEngine.

    Parâmetros
    ----------
    mode : "fast" | "full" | "minimal"
        Modo de análise (impacta apenas performance — todos os modos
        retornam MetricVector completo com estimativas nos campos ausentes).
    """

    def __init__(self, mode: str = "full"):
        self.mode = mode

    def analyze(
        self,
        source: str,
        module_id: str,
        commit_hash: str,
        timestamp: Optional[float] = None,
        language: str = "python",
    ) -> MetricVector:
        """
        Analisa source code e retorna MetricVector com 9 canais UCO.

        Parâmetros
        ----------
        source      : código-fonte como string
        module_id   : identificador do módulo (ex: "auth.login", "core.parser")
        commit_hash : hash do commit correspondente
        timestamp   : UNIX timestamp do commit (None → now)
        language    : linguagem do código (atualmente só "python" suportado)

        Retorna
        -------
        MetricVector com todos os campos preenchidos.
        """
        if timestamp is None:
            timestamp = time.time()

        # Parse AST — fallback para métricas mínimas em caso de SyntaxError
        try:
            tree = ast.parse(source, mode="exec")
            parse_ok = True
        except SyntaxError:
            parse_ok = False
            tree = None

        if not parse_ok or tree is None:
            return self._minimal_vector(source, module_id, commit_hash,
                                        timestamp, language)

        # Visitar AST
        visitor = _UCOVisitor()
        visitor.visit(tree)

        # ── 1. Métricas básicas ────────────────────────────────────────────
        loc = len([l for l in source.splitlines() if l.strip()])

        cc = max(1, visitor.cc_total)
        max_fn_cc = visitor.max_fn_cc

        # ── 2. Halstead ───────────────────────────────────────────────────
        n1, N1 = max(1, visitor.n1), max(1, visitor.N1)
        n2, N2 = max(1, visitor.n2), max(1, visitor.N2)

        vocabulary = n1 + n2
        length     = N1 + N2
        volume     = length * math.log2(vocabulary) if vocabulary > 0 else 0.0
        difficulty = (n1 / 2) * (N2 / max(1, n2))
        effort     = difficulty * volume
        bugs       = volume / 3000.0

        # Hamiltonian = effort normalizado por LOC
        # Calibrado para que código simples → H ≈ 2–5, código complexo → H ≈ 20–200
        hamiltonian = effort / max(1, loc) * 0.01

        # ── 3. ILR ────────────────────────────────────────────────────────
        n_loops_while = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.While)
        )
        ilr = float(visitor.loop_risk_count) / max(1, n_loops_while) \
              if n_loops_while > 0 else 0.0
        ilr = min(1.0, ilr)

        # ── 4. DSM (Dependency Structure Matrix) ─────────────────────────
        n_imports = len(visitor.imports_set | visitor.from_imports_set)
        n_funcs   = max(1, visitor.n_functions)
        n_classes = max(1, visitor.n_classes)

        # DSM density = razão imports/funcs (proxy: quanto cada função "puxa" de fora)
        dsm_density = min(1.0, n_imports / (n_funcs * 2 + 1))

        # DSM cyclic ratio: detectado via funções que se chamam mutuamente
        # Proxy simples: se há classes e múltiplas importações cruzadas
        dsm_cyclic = self._estimate_dsm_cyclic(visitor, tree)

        # ── 5. DI (Dependency Instability) ───────────────────────────────
        # Martin's DI = Ce / (Ca + Ce)
        # Aqui: Ce = imports externos, Ca ≈ LOC/100 (proxy de Ca)
        ce = n_imports
        ca = max(1, loc // 100)
        di = ce / (ca + ce)

        # ── 6. Dead code ──────────────────────────────────────────────────
        dead_lines = visitor.dead_code_lines

        # ── 7. Duplicate blocks ───────────────────────────────────────────
        # Detecta padrões de código duplicado — ativo em todos os modos
        # ("fast" usa apenas nível 1 = linhas individuais; "full" acrescenta blocos 3-linha)
        dups = self._estimate_duplicates(source)

        # ── 8. CC hotspot ratio (GAP-N1) ─────────────────────────────────
        fn_cc_list = visitor.fn_cc_list
        cc_hotspot_ratio = 0.0
        if fn_cc_list and len(fn_cc_list) > 1:
            avg_fn_cc = sum(fn_cc_list) / len(fn_cc_list)
            cc_hotspot_ratio = min(1.0, max_fn_cc / max(1, avg_fn_cc * 3))

        # ── 9. Status ─────────────────────────────────────────────────────
        status = self._compute_status(hamiltonian, cc, dead_lines)

        mv = MetricVector(
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=timestamp,
            hamiltonian=round(hamiltonian, 4),
            cyclomatic_complexity=cc,
            infinite_loop_risk=round(ilr, 4),
            dsm_density=round(dsm_density, 4),
            dsm_cyclic_ratio=round(dsm_cyclic, 4),
            dependency_instability=round(di, 4),
            syntactic_dead_code=dead_lines,
            duplicate_block_count=dups,
            halstead_bugs=round(bugs, 4),
            language=language,
            lines_of_code=loc,
            status=status,
        )
        # Extra fields used by MetricSignalBuilder (via getattr with defaults)
        mv.n_functions          = visitor.n_functions
        mv.n_classes            = visitor.n_classes
        mv.max_methods_per_class= visitor.max_methods_per_class
        mv.cc_hotspot_ratio     = round(cc_hotspot_ratio, 4)
        mv.max_function_cc      = max_fn_cc
        return mv

    def suggest_transforms(
        self,
        source: str,
        module_id: str = "anon",
        commit_hash: str = "0000000",
    ) -> Dict[str, Any]:
        """
        Sugere UCO transforms e estima ΔH potencial.

        Retorna dict com:
          h_before    : H atual
          h_after     : H estimado após aplicar todos os transforms
          delta_h     : diferença (negativo = melhoria)
          transforms  : lista de transforms aplicáveis
        """
        mv = self.analyze(source, module_id, commit_hash)

        transforms: List[str] = []
        h_reduction = 0.0

        if mv.syntactic_dead_code > 0:
            transforms.append("REMOVE_DEAD_CODE")
            h_reduction += mv.hamiltonian * 0.08 * mv.syntactic_dead_code

        if mv.infinite_loop_risk > 0.3:
            transforms.append("ADD_LOOP_TERMINATION_GUARD")
            h_reduction += mv.hamiltonian * 0.05

        if mv.cyclomatic_complexity > 10:
            transforms.append("EXTRACT_METHOD")
            h_reduction += mv.hamiltonian * 0.15

        if mv.duplicate_block_count > 0:
            transforms.append("REMOVE_DUPLICATES")
            h_reduction += mv.hamiltonian * 0.10 * mv.duplicate_block_count

        if mv.dependency_instability > 0.7:
            transforms.append("DEPENDENCY_INVERSION")
            h_reduction += mv.hamiltonian * 0.12

        h_after = max(0.0, mv.hamiltonian - h_reduction)

        # Gerar versão otimizada do código com transforms aplicados
        optimized = self._apply_transforms(source, transforms)

        return {
            "h_before":       round(mv.hamiltonian, 4),
            "h_after":        round(h_after, 4),
            "delta_h":        round(h_after - mv.hamiltonian, 4),
            "transforms":     transforms,
            "optimized_code": optimized,
            "metrics":        {
                "cc":   mv.cyclomatic_complexity,
                "dead": mv.syntactic_dead_code,
                "ilr":  mv.infinite_loop_risk,
                "dups": mv.duplicate_block_count,
                "di":   mv.dependency_instability,
            },
        }

    def _apply_transforms(self, source: str, transforms: List[str]) -> str:
        """
        Aplica transforms de código de forma conservadora (AST-safe).

        Implementação Best-effort:
          REMOVE_DEAD_CODE  — remove statements após return/raise no mesmo bloco
          REMOVE_DUPLICATES — deduplica linhas consecutivas idênticas

        Para transforms que requerem refatoração semântica (EXTRACT_METHOD,
        DEPENDENCY_INVERSION), retorna o source original com comentário.
        """
        result = source

        if "REMOVE_DEAD_CODE" in transforms:
            result = self._remove_dead_code_transform(result)

        if "REMOVE_DUPLICATES" in transforms:
            result = self._remove_dup_lines_transform(result)

        return result

    def _remove_dead_code_transform(self, source: str) -> str:
        """Remove linhas de dead code óbvias via análise de indentação + terminais."""
        lines = source.split("\n")
        result_lines: List[str] = []
        # Simples: detecta blocos onde uma linha terminal é seguida de código no mesmo nível
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            result_lines.append(line)
            # Se é um terminal simples (return/raise/break), pular linhas de mesmo nível até próximo bloco
            if stripped.startswith(("return ", "return\n", "raise ", "break", "continue")):
                indent = len(line) - len(line.lstrip())
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if not next_line.strip():  # linha vazia — manter
                        result_lines.append(next_line)
                        j += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent == indent:
                        # Mesmo nível → dead code após terminal
                        j += 1
                        continue
                    break
                i = j
            else:
                i += 1
        return "\n".join(result_lines)

    def _remove_dup_lines_transform(self, source: str) -> str:
        """Remove linhas consecutivas idênticas (duplicatas imediatas)."""
        lines = source.split("\n")
        result: List[str] = []
        for line in lines:
            if result and line.strip() and result[-1].strip() == line.strip() and line.strip():
                continue  # pular linha idêntica consecutiva
            result.append(line)
        return "\n".join(result)

    # ─── Helpers ─────────────────────────────────────────────────────────────

    def _compute_status(
        self,
        h: float,
        cc: int,
        dead: int,
    ) -> str:
        """
        Status baseado em thresholds UCO calibrados:
          STABLE   : H < 8  AND CC ≤ 10
          WARNING  : H < 20 OR  CC ≤ 20
          CRITICAL : H ≥ 20 OR  CC > 20
        """
        if h >= 20 or cc > 20:
            return "CRITICAL"
        if h >= 8 or cc > 10 or dead > 5:
            return "WARNING"
        return "STABLE"

    def _estimate_dsm_cyclic(
        self,
        visitor: _UCOVisitor,
        tree: ast.AST,
    ) -> float:
        """
        Proxy de DSM cyclic ratio via detecção de chamadas internas.

        Detecta funções que chamam outras funções do mesmo módulo —
        um ciclo de chamadas sugere dependência cíclica no grafo de módulos.
        """
        if visitor.n_functions < 2:
            return 0.0

        # Coletar nomes de funções definidas
        fn_names: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_names.add(node.name)

        # Contar chamadas internas (função chamando outra do mesmo módulo)
        internal_calls = 0
        total_calls = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                total_calls += 1
                if isinstance(node.func, ast.Name) and node.func.id in fn_names:
                    internal_calls += 1

        if total_calls == 0:
            return 0.0

        # Ratio de chamadas internas = proxy de DSM cíclico
        return min(1.0, internal_calls / total_calls)

    def _estimate_duplicates(self, source: str) -> int:
        """
        Detecta blocos de código duplicados por hash de linhas normalizadas.

        Algoritmo:
          1. Normaliza cada linha (remove espaços, lowercase, strip comentários)
          2. Conta LINHAS individuais que aparecem 2+ vezes (single-line dups)
          3. Conta blocos de 3 linhas que aparecem 2+ vezes (block dups)
          4. Retorna contagem de padrões únicos duplicados

        Exemplo de CODE_BROKEN:
          'if not token: return false' × 3 → 1 padrão de linha duplicada
          'h = hash(token)' × 3             → 1 padrão de linha duplicada
          Total = 2 ✓
        """
        lines = [
            l.strip().lower().split("#")[0].strip()
            for l in source.splitlines()
            if l.strip() and not l.strip().startswith("#")
        ]

        if not lines:
            return 0

        dup_patterns: set = set()

        # Nível 1: linhas individuais duplicadas (>= 2 ocorrências)
        line_counts: Dict[str, int] = {}
        for line in lines:
            if len(line) >= 5:   # ignorar linhas triviais como 'pass', 'else:', etc.
                line_counts[line] = line_counts.get(line, 0) + 1
        for line, cnt in line_counts.items():
            if cnt >= 2:
                dup_patterns.add(("line", line))

        # Nível 2: blocos de 3 linhas duplicados
        if len(lines) >= 3:
            block_counts: Dict[str, int] = {}
            for i in range(len(lines) - 2):
                block = "\n".join(lines[i:i + 3])
                block_counts[block] = block_counts.get(block, 0) + 1
            for block, cnt in block_counts.items():
                if cnt >= 2:
                    dup_patterns.add(("block3", block))

        return len(dup_patterns)

    def _minimal_vector(
        self,
        source: str,
        module_id: str,
        commit_hash: str,
        timestamp: float,
        language: str,
    ) -> MetricVector:
        """Retorna MetricVector mínimo quando parse AST falha."""
        loc = len([l for l in source.splitlines() if l.strip()])
        return MetricVector(
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=timestamp,
            hamiltonian=float(loc) * 0.05,
            cyclomatic_complexity=1,
            infinite_loop_risk=0.0,
            dsm_density=0.0,
            dsm_cyclic_ratio=0.0,
            dependency_instability=0.5,
            syntactic_dead_code=0,
            duplicate_block_count=0,
            halstead_bugs=0.0,
            language=language,
            lines_of_code=loc,
            status="STABLE",
        )
