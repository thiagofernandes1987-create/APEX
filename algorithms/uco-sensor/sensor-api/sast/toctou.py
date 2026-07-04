"""
UCO-Sensor — TOCTOU / Race Detector  (M28)  ·  CWE-367
=======================================================
Detecta o smell clássico de **Time-Of-Check to Time-Of-Use** (condição de
corrida em recurso de sistema de arquivos) — a classe de RACE que nem o M10
(guard-por-diff) nem o M11 (memory-safety) cobriam, e que é comum em código
gerado por IA (o objetivo comercial nº1): "checar" um caminho e depois "usar"
esse mesmo caminho de forma NÃO-atômica, deixando uma janela para o atacante
trocar o recurso entre a checagem e o uso.

Padrão vulnerável (o que dispara):
    if os.path.exists(p):        # TIME-OF-CHECK  (linha C)
        ...
    with open(p, "w") as f:      # TIME-OF-USE    (linha U > C, MESMA var p)
        ...

Padrão seguro (o que NÃO dispara — anti-FP):
    * abertura ATÔMICA que dispensa a checagem prévia:
        open(p, "x")             # modo exclusivo → cria-ou-falha atômico
        os.open(p, os.O_CREAT | os.O_EXCL)
    * check e use em VARIÁVEIS DIFERENTES (recursos distintos);
    * use ANTES do check (não é TOCTOU);
    * reatribuição da variável entre check e use (recurso mudou de propósito).

Disciplina anti-FP (princípio do projeto: um FP afirmado é pior que um miss):
  * exige a MESMA variável (ast.Name) no check e no use;
  * exige ordem check→use por número de linha;
  * suprime se o `use` é uma abertura atômica (modo 'x'/O_EXCL);
  * suprime se há reatribuição da var entre check e use;
  * escopo por função (reusa M14 se disponível; senão o módulo inteiro).

Só Python (AST).  Nunca levanta em `scan` (contrato de degradação graciosa).

API
---
    findings = TOCTOUDetector().scan(source)          # -> list[TOCTOUFinding]
    # cada finding: rule_id=SAST060, cwe_id=CWE-367, check_line, use_line, var,
    #               check_call, use_call, severity

Versão: introduzido em v3.67.0 (Sprint CR).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Tuple

# ── vocabulário (calibrado, baixo-FP) ────────────────────────────────────────
# CHECK: chamadas que apenas CONSULTAM o estado de um caminho (time-of-check),
#   mapeadas por (obj_qualificado, metodo).
_CHECK_ATTR: FrozenSet[Tuple[str, str]] = frozenset({
    ("os.path", "exists"), ("os.path", "isfile"), ("os.path", "isdir"),
    ("os.path", "islink"), ("os.path", "lexists"), ("os.path", "getsize"),
    ("os", "access"), ("os", "stat"), ("os", "lstat"),
    ("path", "exists"), ("path", "isfile"), ("path", "isdir"),  # from os import path
})
# USE: chamadas que AGEM sobre o caminho de forma não-atômica (time-of-use).
_USE_FUNC: FrozenSet[str] = frozenset({"open"})
_USE_ATTR: FrozenSet[Tuple[str, str]] = frozenset({
    ("os", "open"), ("os", "remove"), ("os", "unlink"), ("os", "rename"),
    ("os", "mkdir"), ("os", "makedirs"), ("os", "rmdir"), ("os", "chmod"),
    ("os", "chown"), ("os", "replace"),
    ("shutil", "copy"), ("shutil", "copy2"), ("shutil", "copyfile"),
    ("shutil", "move"), ("shutil", "rmtree"),
})


@dataclass(frozen=True)
class TOCTOUFinding:
    """Uma janela TOCTOU comprovada (check→use não-atômico na mesma var)."""
    rule_id: str
    cwe_id: str
    severity: str
    var: str
    check_call: str
    check_line: int
    use_call: str
    use_line: int
    function: str

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id, "cwe_id": self.cwe_id,
            "severity": self.severity, "var": self.var,
            "check_call": self.check_call, "check_line": self.check_line,
            "use_call": self.use_call, "use_line": self.use_line,
            "function": self.function,
            "message": (f"TOCTOU (CWE-367): '{self.var}' é checado por "
                        f"{self.check_call}() na L{self.check_line} e usado por "
                        f"{self.use_call}() na L{self.use_line} sem operação "
                        f"atômica — janela de corrida entre check e use."),
        }


def _qual(node: ast.AST) -> str:
    """Nome qualificado de um alvo de chamada (`os.path.exists` → 'os.path')."""
    if isinstance(node, ast.Attribute):
        base = _qual(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


class TOCTOUDetector:
    """Detector de TOCTOU/CWE-367 por função.  Nunca levanta em `scan`."""

    def scan(self, source: str) -> List[TOCTOUFinding]:
        """Retorna os TOCTOU encontrados.  [] em erro de sintaxe (contrato)."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        findings: List[TOCTOUFinding] = []
        # Escopo por função (uma janela TOCTOU vive dentro de uma função).
        for fn in self._iter_functions(tree):
            findings.extend(self._scan_function(fn))
        # Também varre o nível de módulo (scripts sem função).
        module_stmts = [n for n in tree.body
                        if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef,
                                              ast.ClassDef))]
        if module_stmts:
            findings.extend(self._scan_stmts(module_stmts, "<module>"))
        return findings

    # ── helpers de estrutura ────────────────────────────────────────────────
    @staticmethod
    def _iter_functions(tree: ast.AST):
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield node

    def _scan_function(self, fn: ast.AST) -> List[TOCTOUFinding]:
        name = getattr(fn, "name", "<fn>")
        return self._scan_stmts(list(getattr(fn, "body", [])), name)

    # ── núcleo: casa check→use na mesma var, com anti-FP ─────────────────────
    def _scan_stmts(self, body: List[ast.stmt], fn_name: str) -> List[TOCTOUFinding]:
        # 1) coleta, em ordem de linha, os CHECKs e USEs por variável de caminho.
        checks: Dict[str, Tuple[str, int]] = {}   # var → (check_call, line) — 1º check
        found: List[TOCTOUFinding] = []
        reassigned_after: Dict[str, int] = {}      # var → linha de reatribuição

        # percorre TODAS as chamadas/atribuições da função em ordem textual
        nodes = list(ast.walk(ast.Module(body=body, type_ignores=[])))
        calls = sorted(
            [n for n in nodes if isinstance(n, ast.Call)],
            key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))
        assigns = [n for n in nodes if isinstance(n, ast.Assign)]

        # mapa var → linhas de (re)atribuição (para invalidar checks obsoletos)
        assign_lines: Dict[str, List[int]] = {}
        for a in assigns:
            for tgt in a.targets:
                if isinstance(tgt, ast.Name):
                    assign_lines.setdefault(tgt.id, []).append(getattr(a, "lineno", 0))

        for call in calls:
            ln = getattr(call, "lineno", 0)
            kind, callname = self._classify(call)
            if kind is None:
                continue
            var = self._path_var(call, kind)
            if var is None:
                continue

            if kind == "check":
                # guarda só o PRIMEIRO check por var (o mais cedo).
                checks.setdefault(var, (callname, ln))
            elif kind == "use":
                # abertura atômica não é TOCTOU (é justamente o fix) → ignora.
                if self._is_atomic_open(call):
                    continue
                prior = checks.get(var)
                if prior is None:
                    continue
                check_call, check_line = prior
                if check_line >= ln:
                    continue  # use antes/na mesma linha do check → não é TOCTOU
                # anti-FP: se a var foi REATRIBUÍDA entre check e use, o recurso
                # pode ter mudado de propósito → suprime.
                if any(check_line < al < ln for al in assign_lines.get(var, [])):
                    continue
                found.append(TOCTOUFinding(
                    rule_id="SAST060", cwe_id="CWE-367", severity="MEDIUM",
                    var=var, check_call=check_call, check_line=check_line,
                    use_call=callname, use_line=ln, function=fn_name))
                # não re-reporta a mesma var (uma janela por par check→1º use)
                checks.pop(var, None)
        return found

    # ── classificação de uma chamada ────────────────────────────────────────
    @staticmethod
    def _classify(call: ast.Call) -> Tuple[Optional[str], str]:
        """(kind, callname) onde kind ∈ {'check','use',None}."""
        func = call.func
        if isinstance(func, ast.Attribute):
            obj = _qual(func.value)
            meth = func.attr
            # normaliza obj para o último 1-2 segmentos conhecidos
            last = obj.split(".")[-1]
            for (o, m) in _CHECK_ATTR:
                if m == meth and (obj == o or last == o.split(".")[-1] or obj.endswith(o)):
                    return "check", f"{o}.{m}"
            for (o, m) in _USE_ATTR:
                if m == meth and (obj == o or last == o or obj.endswith(o)):
                    return "use", f"{o}.{m}"
            return None, ""
        if isinstance(func, ast.Name):
            if func.id in _USE_FUNC:
                return "use", func.id
        return None, ""

    @staticmethod
    def _path_var(call: ast.Call, kind: str) -> Optional[str]:
        """
        Nome da variável de caminho no 1º argumento posicional da chamada.
        Só casamos por VARIÁVEL (ast.Name) — literais diferentes não formam par
        confiável e literais iguais raramente são o alvo real de um TOCTOU.
        """
        if not call.args:
            return None
        first = call.args[0]
        if isinstance(first, ast.Name):
            return first.id
        return None

    @staticmethod
    def _is_atomic_open(call: ast.Call) -> bool:
        """
        True se a chamada é uma abertura ATÔMICA (dispensa check prévio):
          * open(p, "x"/"xb"/...) — modo exclusivo;
          * os.open(p, ... O_EXCL ...) — flag O_EXCL.
        Esse é o PADRÃO-FIX de um TOCTOU — não deve disparar.
        """
        func = call.func
        # open(p, mode=...)
        if isinstance(func, ast.Name) and func.id == "open":
            mode = None
            if len(call.args) >= 2 and isinstance(call.args[1], ast.Constant):
                mode = call.args[1].value
            for kw in call.keywords:
                if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
                    mode = kw.value.value
            if isinstance(mode, str) and "x" in mode:
                return True
        # os.open(p, flags) com O_EXCL
        if isinstance(func, ast.Attribute) and func.attr == "open":
            for arg in call.args[1:]:
                for n in ast.walk(arg):
                    if isinstance(n, ast.Attribute) and n.attr == "O_EXCL":
                        return True
        return False
