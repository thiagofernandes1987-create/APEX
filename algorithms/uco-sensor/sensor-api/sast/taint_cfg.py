"""
UCO-Sensor — CFG-backed Flow-Sensitive Taint  (M22)
====================================================
Operacionaliza o taint-tracking **sobre a CFG real do UCO V4** (`uco_core`,
`PythonCFGBuilder`), consumindo os `python_defs_uses` (defs/uses por nó) que a
CFG já computa e adicionando uma análise de dataflow **fluxo/caminho-sensível**
por ponto-fixo (worklist) nas arestas do grafo de fluxo de controle.

Por que isto (ANGLE 1 do deep-research — "amplificar o motor de dataflow")
-------------------------------------------------------------------------
Os motores de taint existentes trabalham por STATEMENT/linha:
  * `TaintAnalyzer` (M7.2)      — intra-procedural, ordem textual;
  * `InterprocTaintAnalyzer` (M17) — cruza funções via call-graph.
Nenhum dos dois é **path-sensitive**: eles não sabem que um sanitizador dentro
de UM braço de `if` NÃO limpa a variável no OUTRO braço.  Ex.:

    x = request.GET['id']       # source
    if cond:
        x = escape(x)           # sanitiza SÓ neste caminho
    cursor.execute(x)           # ainda vulnerável pelo caminho `else`

Um motor "viu um escape ⇒ limpo" daria falso-negativo aqui.  A CFG do V4 tem o
nó de MERGE cujos predecessores são os dois braços; unindo o taint dos
predecessores (`IN[n] = ∪ OUT[p]`), o caminho não-sanitizado mantém `x`
contaminado e o sink dispara corretamente.  E o inverso — sanitização
INCONDICIONAL antes do sink — mata o taint em todos os caminhos e NÃO dispara.
Essa é a precisão que só a CFG dá.

Dataflow (forward, may-taint):
    IN[n]  = ∪ { OUT[p] : p ∈ predecessores(n) }      (união = may-analysis)
    OUT[n] = (IN[n] − KILL[n]) ∪ GEN[n]
    GEN[n]  = defs(n)  se  n é source  OU  (uses(n) ∩ IN[n] ≠ ∅ e n não é sanitizador)
    KILL[n] = defs(n)  se  n redefine com valor limpo (sanitizador / RHS não-tainted)
    FLOW    = n é sink  E  (uses relevantes de n) ∩ IN[n] ≠ ∅

Reaproveitamento (sinergia máxima — não reimplementa vocabulário):
  * fontes  → `TaintAnalyzer._is_source`
  * sinks   → `TaintAnalyzer._get_sink_meta`  (+ gating SQL arg[0], igual M17/CD)
  * sanit.  → `TaintAnalyzer._is_sanitizer`
  * defs/uses → `cfg.metadata["python_defs_uses"]`  (a CFG do V4, não recomputado)

Degradação graciosa: qualquer falha (V4 ausente, parse impossível) → lista
vazia; nunca levanta.  Só Python (a CFG def-use rica do V4 é Python-AST).

API
---
    flows = CFGTaintAnalyzer().analyze(source_code)
    # flows: List[CFGTaintFlow]  (source_desc, sink_desc, sink_line, var,
    #                             rule_id, cwe_id, severity, path_lines)

Versão: introduzido em v3.55.0 (Sprint CF).
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Vocabulário calibrado de source/sink/sanitizer — REUSADO do M7.2 (não
# duplicar; qualquer regra nova de taint entra lá e este módulo herda).
from sast.taint_engine import TaintAnalyzer

# Unpack (rule_id, severity, vuln_type, cwe_id) → (desc, rule, cwe, sev),
# a mesma ordem usada pelo M17 (reuso p/ consistência dos relatórios).
from sast.taint_interproc import _unpack_sink


@dataclass(frozen=True)
class CFGTaintFlow:
    """Um fluxo tainted source→sink comprovado na CFG (path-sensitive)."""
    source_desc: str
    sink_desc: str
    sink_line: int
    var: str
    rule_id: str
    cwe_id: str
    severity: str
    path_lines: Tuple[int, ...] = field(default_factory=tuple)

    def __str__(self) -> str:  # pragma: no cover - conveniência de debug
        return (f"CFGTaintFlow({self.source_desc} → {self.sink_desc} "
                f"@L{self.sink_line} via {self.var}; {self.rule_id}/{self.cwe_id})")


class CFGTaintAnalyzer:
    """Taint fluxo-sensível sobre a CFG do UCO V4.  Nunca levanta em `analyze`."""

    def __init__(self) -> None:
        # Instância única do reconhecedor calibrado (source/sink/sanitizer).
        self._t = TaintAnalyzer()

    # ── API pública ─────────────────────────────────────────────────────────
    def analyze(self, source: str) -> List[CFGTaintFlow]:
        """
        Retorna os fluxos tainted que alcançam um sink por ALGUM caminho da CFG.
        Degrada para [] em qualquer erro (V4 ausente, sintaxe inválida).
        """
        try:
            return self._analyze(source)
        except Exception:  # noqa: BLE001 — contrato "nunca levanta"
            return []

    # ── implementação ───────────────────────────────────────────────────────
    def _analyze(self, source: str) -> List[CFGTaintFlow]:
        # 1) CFG real do V4 (import tardio: degradação graciosa se ausente).
        from uco_core import PythonCFGBuilder  # M13/M15 — CFG canônica do V4

        cfg = PythonCFGBuilder().build(source)
        defs_uses: Dict[int, Dict[str, Set[str]]] = cfg.metadata.get(
            "python_defs_uses", {})
        if not defs_uses:
            return []

        # 2) Classificação por nó (source/sink/sanitizer) re-parseando o texto
        #    normalizado do nó.  Só assign/expr carregam source/sink; ifs/loops
        #    não são sinks — se o parse falhar, o nó só propaga via defs/uses.
        #    node_stmt[nid] = AST do statement do nó (ou None).
        node_stmt: Dict[int, Optional[ast.AST]] = {}
        for nid in defs_uses:
            node_stmt[nid] = self._reparse(cfg.nodes[nid].text)

        # 3) Ponto-fixo forward (worklist) sobre as arestas da CFG.
        #    taint_out[nid] = conjunto de nomes contaminados APÓS o nó.
        taint_out: Dict[int, Set[str]] = {nid: set() for nid in cfg.nodes}
        # Origem (rótulo) de cada variável contaminada, p/ relatório honesto.
        origin: Dict[str, str] = {}

        worklist: List[int] = list(cfg.nodes.keys())
        # Limite defensivo de iterações (grafo finito → converge; guarda extra).
        guard = 0
        max_iter = len(cfg.nodes) * (len(cfg.nodes) + 4) + 16
        while worklist and guard < max_iter:
            guard += 1
            nid = worklist.pop(0)
            node = cfg.nodes[nid]

            # IN[n] = união do OUT dos predecessores (may-analysis).
            in_set: Set[str] = set()
            for p in node.predecessors:
                in_set |= taint_out[p]

            du = defs_uses.get(nid)
            new_out = set(in_set)
            if du is not None:
                stmt = node_stmt.get(nid)
                gen, kill, src_lbl = self._transfer(stmt, du, in_set, origin)
                new_out = (in_set - kill) | gen
                # registra origem das variáveis recém-contaminadas
                if src_lbl:
                    for d in du.get("defs", set()):
                        origin[d] = src_lbl

            if new_out != taint_out[nid]:
                taint_out[nid] = new_out
                # reenfileira sucessores (propagação forward).
                for s in node.successors:
                    if s not in worklist:
                        worklist.append(s)

        # 4) Coleta de fluxos: para cada nó-sink, se um uso relevante está no
        #    IN (taint que chega ao nó), reporta.  Recalcula IN a partir do
        #    ponto-fixo estável.
        return self._collect_flows(cfg, defs_uses, node_stmt, taint_out, origin)

    # ── função de transferência de UM nó ────────────────────────────────────
    def _transfer(
        self,
        stmt: Optional[ast.AST],
        du: Dict[str, Set[str]],
        in_set: Set[str],
        origin: Dict[str, str],
    ) -> Tuple[Set[str], Set[str], Optional[str]]:
        """
        Devolve (GEN, KILL, source_label) para o nó.
          * source_label != None  ⇒ o RHS é uma fonte de taint (defs viram tainted);
          * sanitizador           ⇒ KILL = defs (limpa);
          * RHS usa var tainted    ⇒ GEN = defs (propaga);
          * senão (redefinição limpa) ⇒ KILL = defs.
        """
        defs: Set[str] = set(du.get("defs", set()))
        uses: Set[str] = set(du.get("uses", set()))
        gen: Set[str] = set()
        kill: Set[str] = set()

        rhs = self._assign_rhs(stmt)  # RHS de um assign, se for assign

        # (a) SOURCE — RHS é uma fonte reconhecida (request.GET[...], input(), …)
        if rhs is not None:
            src = self._t._is_source(rhs)
            if src:
                gen |= defs
                return gen, kill, src
            # (b) SANITIZER — RHS é chamada de sanitizador (escape/int/quote/…)
            if isinstance(rhs, ast.Call) and self._t._is_sanitizer(rhs):
                kill |= defs   # valor limpo → mata taint no destino
                return gen, kill, None

        # (c) PROPAGAÇÃO — o nó usa alguma variável contaminada → defs herdam.
        if defs and (uses & in_set):
            gen |= defs
            # herda a origem da primeira var tainted usada (relatório)
            for u in uses:
                if u in origin:
                    for d in defs:
                        origin.setdefault(d, origin[u])
                    break
            return gen, kill, None

        # (d) REDEFINIÇÃO LIMPA — define algo sem taint no RHS → mata taint prévio.
        if defs:
            kill |= defs
        return gen, kill, None

    # ── coleta de sinks alcançados por taint ────────────────────────────────
    def _collect_flows(
        self,
        cfg,
        defs_uses: Dict[int, Dict[str, Set[str]]],
        node_stmt: Dict[int, Optional[ast.AST]],
        taint_out: Dict[int, Set[str]],
        origin: Dict[str, str],
    ) -> List[CFGTaintFlow]:
        flows: List[CFGTaintFlow] = []
        seen: Set[Tuple[str, int, str]] = set()  # dedup (var, linha, rule)

        for nid, node in cfg.nodes.items():
            stmt = node_stmt.get(nid)
            call = self._stmt_call(stmt)
            if call is None:
                continue
            sink = self._t._get_sink_meta(call)
            if not sink:
                continue
            desc, rule, cwe, sev = _unpack_sink(sink)

            # IN do nó-sink = união do OUT dos predecessores (taint que chega).
            in_set: Set[str] = set()
            for p in node.predecessors:
                in_set |= taint_out[p]
            if not in_set:
                continue

            # Gating SQL (igual M17/CD v3.53.0): em query parametrizada só o 1º
            # argumento (a query) carrega risco — a tupla de params é segura.
            is_sql = (rule == "SAST040") or (cwe == "CWE-89")
            check_args = call.args[:1] if is_sql else list(call.args) + [
                kw.value for kw in call.keywords]

            # nomes usados nos argumentos relevantes do sink
            arg_names: Set[str] = set()
            for a in check_args:
                for n in ast.walk(a):
                    if isinstance(n, ast.Name):
                        arg_names.add(n.id)

            # A linha REAL do sink vem do nó da CFG (line_start).  O `call.lineno`
            # do re-parse é relativo ao snippet do nó (=1), não à fonte original.
            sink_line = cfg.nodes[nid].line_start or getattr(call, "lineno", 0)

            tainted_hit = arg_names & in_set
            for var in sorted(tainted_hit):
                key = (var, sink_line, rule)
                if key in seen:
                    continue
                seen.add(key)
                flows.append(CFGTaintFlow(
                    source_desc=origin.get(var, "tainted"),
                    sink_desc=desc,
                    sink_line=sink_line,
                    var=var,
                    rule_id=rule,
                    cwe_id=cwe,
                    severity=sev,
                    path_lines=(),
                ))
        return flows

    # ── helpers de AST ───────────────────────────────────────────────────────
    @staticmethod
    def _reparse(text: str) -> Optional[ast.AST]:
        """
        Re-parseia o texto normalizado de um nó da CFG para um statement AST.
        Nós de controle carregam rótulos ('IF ...', 'RETURN ...', 'FUNCTION f')
        que não são statements válidos — retornamos None (só propagam def/use).
        """
        if not text:
            return None
        # rótulos maiúsculos de controle nunca são source/sink → descarta cedo
        head = text.split(" ", 1)[0]
        if head in {"IF", "FOR", "WHILE", "RETURN", "RAISE", "TRY", "EXCEPT",
                    "FUNCTION", "CLASS", "MERGE_IF", "BREAK", "CONTINUE",
                    "ENTRY", "EXIT"}:
            return None
        try:
            mod = ast.parse(text)
        except SyntaxError:
            return None
        return mod.body[0] if mod.body else None

    @staticmethod
    def _assign_rhs(stmt: Optional[ast.AST]):
        """RHS de um ast.Assign/AnnAssign, ou None."""
        if isinstance(stmt, ast.Assign):
            return stmt.value
        if isinstance(stmt, ast.AnnAssign):
            return stmt.value
        return None

    @staticmethod
    def _stmt_call(stmt: Optional[ast.AST]) -> Optional[ast.Call]:
        """
        Extrai a ast.Call de um statement que pode ser um sink:
        um Expr solto (`cursor.execute(x)`) ou o RHS de um assign
        (`row = cursor.execute(x)`).
        """
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            return stmt.value
        if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
            return stmt.value
        return None
