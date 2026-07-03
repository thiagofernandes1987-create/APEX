"""
UCO-Sensor — Inter-procedural Taint Analysis  (M17)
====================================================
Rastreia fluxo de dados contaminado (taint) que **atravessa funções** —
o caso que o motor intra-procedural (`TaintAnalyzer`, cujo próprio docstring
diz "interprocedural DFA … deferred") não cobre e que domina em código real
e gerado por IA:

    def handler(req):
        name = req.args.get("name")      # SOURCE (entrada do usuário)
        render(name)                     # passa taint para outra função

    def render(value):
        html = "<b>" + value + "</b>"
        return response(html)            # SINK (XSS) — em OUTRA função

O intra-procedural nunca liga `req.args.get` (em `handler`) ao sink em
`render`. O M17 constrói um mini call-graph e propaga taint por **posição de
parâmetro**: se um argumento contaminado é passado para uma função de
usuário, o parâmetro correspondente entra contaminado; se esse parâmetro
alcança um sink lá dentro, reportamos o fluxo inter-procedural com o caminho
`fonte(fnA:linha) → fnB(param) → sink(fnB:linha)`.

Design (bounded, sem SMT, sem call-graph pesado)
------------------------------------------------
* Reusa o reconhecimento de SOURCE/SINK/SANITIZER já calibrado em
  `taint_engine` (instancia um `TaintAnalyzer` e usa `_is_source`/`_is_sink`).
* Ponto-fixo sobre um conjunto finito: `tainted_params[func] ⊆ params(func)`.
  Semear: params que recebem, em algum call-site, um argumento contaminado
  (contaminado = veio de um source local OU de um param já contaminado).
  Itera até estabilizar (nº de params é finito → termina).
* Só considera chamadas a **funções definidas no próprio módulo** (user
  functions) — chamadas a libs são sinks/sources/sanitizers, não hops.
* Conservador em sanitização: se o valor passa por um sanitizer conhecido
  antes do hop/sink, não propaga (evita FP — o mesmo contrato do intra).

Escopo honesto do MVP
---------------------
* Python (AST nativo). Multi-linguagem fica no `taint_lite` (M20).
* 1..N hops dentro do mesmo módulo/arquivo. Não resolve chamadas via
  atributo de objeto (`self.helper(x)`) além do nome simples — registrado
  como limitação; cobre o caso funcional dominante.

API
---
    flows = InterprocTaintAnalyzer().analyze(source)   # -> List[InterprocFlow]
    for f in flows:
        print(f.to_dict())   # source_fn, sink_fn, sink_line, path, rule_id…
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .taint_engine import TaintAnalyzer


@dataclass
class InterprocFlow:
    """Um fluxo de taint que cruza ao menos uma fronteira de função."""
    source_desc: str
    source_fn: str
    source_line: int
    sink_desc: str
    sink_fn: str
    sink_line: int
    param: str                      # o parâmetro por onde o taint entrou no sink_fn
    hops: List[str] = field(default_factory=list)   # cadeia de funções fonte→sink
    rule_id: str = "SAST-IPT"
    cwe_id: str = "CWE-20"
    severity: str = "HIGH"
    vuln_type: str = "INTERPROC_TAINT"

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id, "severity": self.severity, "cwe_id": self.cwe_id,
            "vuln_type": self.vuln_type,
            "source_desc": self.source_desc, "source_fn": self.source_fn,
            "source_line": self.source_line,
            "sink_desc": self.sink_desc, "sink_fn": self.sink_fn, "line": self.sink_line,
            "param": self.param, "flow_path": self.hops, "interprocedural": True,
        }


def _call_user_fn_name(call: ast.Call) -> Optional[str]:
    """
    Nome da função-alvo de uma chamada, para resolução de hop inter-procedural.
    Cobre `nome(...)` (função de módulo) e `obj.metodo(...)` (o nome do método,
    ex.: `self.render(x)`). A resolução por nome é conservadora: só vira hop se
    o nome existir na tabela de funções do módulo (`callee in funcs`, no
    chamador) — métodos de lib (`list.append`) não casam; sinks
    (`cursor.execute`) já foram tratados antes. Captura o padrão dominante
    `self.<metodo>(tainted)` de código OO/gerado por IA sem abrir FP externo.
    """
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


class InterprocTaintAnalyzer:
    """Análise de taint inter-procedural para Python (M17)."""

    def __init__(self) -> None:
        # Reusa o reconhecedor de source/sink/sanitizer já calibrado (M9.x).
        self._t = TaintAnalyzer()

    # ── coleta de funções e seus parâmetros ─────────────────────────────────────
    def _collect_functions(self, tree: ast.AST) -> Dict[str, ast.FunctionDef]:
        funcs: Dict[str, ast.FunctionDef] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                funcs[node.name] = node  # type: ignore[assignment]
        return funcs

    @staticmethod
    def _params(fn: ast.FunctionDef) -> List[str]:
        a = fn.args
        names = [p.arg for p in a.posonlyargs] + [p.arg for p in a.args] + [p.arg for p in a.kwonlyargs]
        if a.vararg:
            names.append(a.vararg.arg)
        if a.kwarg:
            names.append(a.kwarg.arg)
        return names

    # ── análise local de UMA função, dado o conjunto de params contaminados ─────
    def _analyze_fn(
        self,
        fn: ast.FunctionDef,
        tainted_params: Set[str],
        funcs: Dict[str, ast.FunctionDef],
    ) -> Tuple[List[InterprocFlow], List[Tuple[str, int, str, int]]]:
        """
        Retorna:
          - fluxos sink alcançados dentro desta função por valor contaminado;
          - propagações: (callee_name, param_index, origin_desc, origin_line)
            para cada chamada a função de usuário recebendo argumento contaminado.
        A contaminação local nasce de: params contaminados + SOURCES no corpo.
        """
        tainted: Dict[str, Tuple[str, int]] = {}   # var -> (origin_desc, origin_line)
        for p in tainted_params:
            tainted[p] = (f"param `{p}`", fn.lineno)

        flows: List[InterprocFlow] = []
        propagations: List[Tuple[str, int, str, int]] = []

        def expr_taint(e: ast.AST) -> Optional[Tuple[str, int]]:
            """Origem do taint de uma expressão, se contaminada (source direto ou var contaminada)."""
            src = self._t._is_source(e)  # reusa reconhecedor calibrado
            if src:
                return (src, getattr(e, "lineno", fn.lineno))
            for n in ast.walk(e):
                if isinstance(n, ast.Name) and n.id in tainted:
                    return tainted[n.id]
            return None

        def is_sanitized_call(e: ast.AST) -> bool:
            return isinstance(e, ast.Call) and bool(self._t._is_sanitizer(e))  # type: ignore[attr-defined]

        for node in ast.walk(fn):
            # Atribuições: propaga taint local (var = <expr contaminada>)
            if isinstance(node, ast.Assign):
                if is_sanitized_call(node.value):
                    for tgt in node.targets:
                        for nm in _names_of_target(tgt):
                            tainted.pop(nm, None)
                    continue
                org = expr_taint(node.value)
                if org:
                    for tgt in node.targets:
                        for nm in _names_of_target(tgt):
                            tainted[nm] = org
            # Chamadas: sink? hop para função de usuário?
            elif isinstance(node, ast.Call):
                # sink dentro desta função?
                sink = self._t._get_sink_meta(node)  # (rule_id, severity, vuln_type, cwe_id) ou None
                if sink:
                    desc, rule, cwe, sev = _unpack_sink(sink)
                    # (CD v3.53.0) Query PARAMETRIZADA é segura: em
                    # `cursor.execute(sql, params)` só o 1º argumento (a query)
                    # carrega risco de injeção — os demais são bound parameters,
                    # que o driver escapa.  Para sinks SQL (SAST040/CWE-89)
                    # checamos SÓ o arg 0; isso elimina o FP de flagrar
                    # `execute('... %s', (x,))` (uso correto) como injeção.
                    is_sql = (rule == "SAST040") or (cwe == "CWE-89")
                    if is_sql:
                        args_to_check = node.args[:1]
                    else:
                        args_to_check = list(node.args) + [kw.value for kw in node.keywords]
                    for arg in args_to_check:
                        org = expr_taint(arg)
                        if org:
                            flows.append(InterprocFlow(
                                source_desc=org[0], source_fn=fn.name, source_line=org[1],
                                sink_desc=desc, sink_fn=fn.name, sink_line=getattr(node, "lineno", fn.lineno),
                                param=next((n.id for n in ast.walk(arg) if isinstance(n, ast.Name) and n.id in tainted), ""),
                                hops=[fn.name], rule_id=rule, cwe_id=cwe, severity=sev,
                            ))
                    continue
                # hop: chamada a função de usuário com argumento contaminado.
                # Resolve o NOME do parâmetro-alvo já com o offset do receptor
                # implícito: em `self.render(x)` o `x` (arg 0) mapeia para o
                # 2º parâmetro (`value`), pois `self` ocupa o índice 0.
                callee = _call_user_fn_name(node)
                if callee and callee in funcs and callee != fn.name:
                    cparams = self._params(funcs[callee])
                    is_method_call = isinstance(node.func, ast.Attribute)
                    offset = 1 if (is_method_call and cparams and cparams[0] in ("self", "cls")) else 0
                    for idx, arg in enumerate(node.args):
                        org = expr_taint(arg)
                        if org and not is_sanitized_call(arg):
                            p_idx = idx + offset
                            if p_idx < len(cparams):
                                propagations.append((callee, cparams[p_idx], org[0], org[1]))
        return flows, propagations

    # ── ponto-fixo sobre tainted_params de todas as funções ─────────────────────
    def analyze(self, source: str) -> List[InterprocFlow]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        funcs = self._collect_functions(tree)
        if not funcs:
            return []

        tainted_params: Dict[str, Set[str]] = {name: set() for name in funcs}
        # origem que semeou cada param contaminado (para o caminho)
        seed_origin: Dict[Tuple[str, str], Tuple[str, int, List[str]]] = {}

        changed = True
        guard = 0
        while changed and guard < 64:   # nº de params finito → converge; guard anti-loop
            changed = False
            guard += 1
            for name, fn in funcs.items():
                _, props = self._analyze_fn(fn, tainted_params[name], funcs)
                for callee, pname, org_desc, org_line in props:
                    if pname and pname not in tainted_params[callee]:
                        tainted_params[callee].add(pname)
                        prev = seed_origin.get((name, ""), None)
                        chain = (prev[2] if prev else [name]) + [callee]
                        seed_origin[(callee, pname)] = (org_desc, org_line, chain)
                        changed = True

        # coleta de fluxos finais: rodar cada função com seus params contaminados
        out: List[InterprocFlow] = []
        seen: Set[Tuple[str, int, str]] = set()
        for name, fn in funcs.items():
            flows, _ = self._analyze_fn(fn, tainted_params[name], funcs)
            for fl in flows:
                # enriquece o caminho/origem se o taint entrou por um param semeado
                seed = seed_origin.get((name, fl.param))
                if seed:
                    fl.source_desc, fl.source_line, fl.hops = seed[0], seed[1], seed[2]
                    fl.source_fn = seed[2][0] if seed[2] else name
                # só reporta como inter-procedural se a cadeia cruza função
                if len(fl.hops) < 2:
                    continue
                key = (fl.sink_fn, fl.sink_line, fl.param)
                if key in seen:
                    continue
                seen.add(key)
                out.append(fl)
        out.sort(key=lambda f: (f.sink_line, f.sink_fn))
        return out


# ── helpers de nível de módulo ─────────────────────────────────────────────────
def _names_of_target(tgt: ast.AST) -> List[str]:
    if isinstance(tgt, ast.Name):
        return [tgt.id]
    out: List[str] = []
    for n in ast.walk(tgt):
        if isinstance(n, ast.Name):
            out.append(n.id)
    return out


def _unpack_sink(sink) -> Tuple[str, str, str, str]:
    """`_get_sink_meta` retorna (rule_id, severity, vuln_type, cwe_id).
    Normaliza para (desc, rule, cwe, sev) usado pelo InterprocFlow."""
    if isinstance(sink, (tuple, list)) and len(sink) >= 4:
        rule_id, severity, vuln_type, cwe_id = sink[0], sink[1], sink[2], sink[3]
        return str(vuln_type), str(rule_id), str(cwe_id), str(severity)
    return (str(sink), "SAST-IPT", "CWE-20", "HIGH")

