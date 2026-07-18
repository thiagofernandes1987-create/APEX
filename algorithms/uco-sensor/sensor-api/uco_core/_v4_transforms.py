"""
uco_core._v4_transforms — transformações de código do UCO V4 (extraído, item 4)
==============================================================================
As 10 CodeTransform + o helper `normalize_ws` foram movidos do monolito
`universal_code_optimizer_v4.py` (era 4318 linhas) para cá — bloco COESO e quase
LEAF (dependia só de `normalize_ws`, agora aqui). Import ONE-WAY: o V4 importa
destas classes; este módulo NÃO importa o V4 (sem ciclo). Comportamento
idêntico — apenas relocado. Ver Sprint DU / auditoria de dogfooding.
"""
from __future__ import annotations

import ast
import math
import re
from collections import Counter, defaultdict, deque, OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union


def normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


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
