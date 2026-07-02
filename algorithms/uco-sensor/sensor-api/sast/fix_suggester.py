"""
UCO-Sensor — Fix Suggester  (M18)  ·  o elo Sensor → UCO Core → patch
=====================================================================
Fecha a promessa da missão: *"UCO Core identifica o que falhou e o que
corrigir"*.  Dado um **finding do Sensor** (um `GuardFinding` do M11 ou um
fluxo de taint do motor de dados), o suggester emite o **patch mínimo
sugerido** — dirigido pela CLASSE do bug e pelas VARIÁVEIS que o próprio
Sensor já extraiu (ex.: `needs_guard_on=(pilen, slen)`), sem inventar
contexto.

Não é um auto-fixer cego: é a ponte que transforma *sinal* em *ação
concreta e localizada*, com racional, para a camada APEX (IA/MCP) consumir
depois.

Validação com dado real (sem fabricar)
--------------------------------------
Para uma CVE conhecida, a sugestão pode ser conferida contra o **fix real**:
``explains_real_fix(suggestion, fixed_source)`` verifica se o guard que o
Core propôs aparece na versão corrigida pelos mantenedores.  Ex.: no php-src
CVE-2019-11043 o Core sugere o guard sobre ``(pilen, slen)``; o fix real
adicionou ``pilen > slen`` — logo a sugestão do Core **coincide com o que os
mantenedores fizeram**.

API
---
    sug = FixSuggester().suggest_for_guard(guard_finding)     -> FixSuggestion
    sug = FixSuggester().suggest_for_taint(taint_flow_dict)   -> FixSuggestion
    FixSuggester().explains_real_fix(sug, fixed_source)       -> bool
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class FixSuggestion:
    rule_id: str
    cwe_id: str
    line: int
    vuln_type: str
    suggested_patch: str          # o trecho de correção sugerido
    rationale: str                # por que este patch resolve
    guard_expr: Optional[str] = None   # expressão de guarda proposta (p/ validação)
    guard_vars: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id, "cwe_id": self.cwe_id, "line": self.line,
            "vuln_type": self.vuln_type, "suggested_patch": self.suggested_patch,
            "rationale": self.rationale, "guard_expr": self.guard_expr,
            "guard_vars": list(self.guard_vars),
        }


# Sugestões por vuln_type de taint (sink → mitigação canônica).
_TAINT_FIX: Dict[str, Tuple[str, str]] = {
    "COMMAND_INJECTION": (
        "subprocess.run([...], shell=False)  # ou shlex.quote(arg)",
        "Nunca passe entrada do usuário para o shell; use lista de argumentos "
        "com shell=False, ou escape com shlex.quote().",
    ),
    "UNSAFE_DESERIALIZATION": (
        "json.loads(data)  # ou yaml.safe_load(data)",
        "Troque pickle/marshal/yaml.load por um desserializador seguro "
        "(json / yaml.safe_load); pickle executa código arbitrário.",
    ),
    "SQL_INJECTION": (
        "cursor.execute('... WHERE x = ?', (value,))",
        "Use query parametrizada (placeholder + parâmetros); nunca concatene "
        "entrada do usuário na string SQL.",
    ),
    "TEMPLATE_INJECTION": (
        "render_template('t.html', var=value)  # autoescape ligado",
        "Nunca construa o template a partir de entrada do usuário; use um "
        "template estático com autoescape e passe dados como variáveis.",
    ),
    "PATH_TRAVERSAL": (
        "p = os.path.realpath(os.path.join(base, name)); assert p.startswith(base)",
        "Canonize o caminho (realpath) e valide que ele permanece dentro do "
        "diretório-base antes de abrir.",
    ),
    "CODE_INJECTION": (
        "ast.literal_eval(data)  # nunca eval()/exec() em entrada do usuário",
        "Remova eval/exec sobre entrada; use ast.literal_eval para dados, ou "
        "um parser dedicado.",
    ),
}


class FixSuggester:
    """Emite o patch mínimo sugerido para um finding do Sensor (o UCO Core)."""

    # ── M11 GuardFinding (memory-safety, C) ───────────────────────────────────
    def suggest_for_guard(self, gf) -> FixSuggestion:
        rid = getattr(gf, "rule_id", "")
        vars_ = tuple(getattr(gf, "needs_guard_on", ()) or ())
        line = getattr(gf, "line", 0)
        cwe = getattr(gf, "cwe_id", "")

        if rid == "GA01" and len(vars_) >= 2:
            a, b = vars_[0], vars_[1]
            guard = f"{a} > {b}"
            patch = (f"if (!({guard})) {{ /* {a} < {b}: underflow — trate o erro "
                     f"(ex.: retorne/aborte) */ }}\n// ou torne seguro: "
                     f"({guard}) ? <expr> : <valor_seguro>")
            rationale = (f"A subtração `{a} - {b}` faz underflow (aritmética unsigned) "
                         f"quando {a} < {b}, gerando acesso fora dos limites. "
                         f"Adicionar o guard `{guard}` no escopo elimina a classe.")
            return FixSuggestion(rid, cwe, line, "INTEGER_UNDERFLOW", patch,
                                 rationale, guard_expr=guard, guard_vars=(a, b))

        if rid == "GA02" and len(vars_) >= 1:
            n = vars_[0]
            guard = f"{n} <= sizeof(dest)"
            patch = (f"if (!({guard})) {{ /* comprimento não validado */ return; }}\n"
                     f"memcpy(dest, src, {n});")
            rationale = (f"A cópia usa `{n}` sem comparar contra o tamanho do destino; "
                         f"valide `{guard}` antes.")
            return FixSuggestion(rid, cwe, line, "BUFFER_OVERFLOW", patch,
                                 rationale, guard_expr=guard, guard_vars=(n,))

        # fallback genérico
        return FixSuggestion(rid, cwe, line, "MEMORY_SAFETY",
                             "// adicione validação de limites sobre: " + ", ".join(vars_),
                             "Valide os operandos de risco antes do uso.",
                             guard_vars=vars_)

    # ── Taint flow (injeção/deserialização, Python) ───────────────────────────
    def suggest_for_taint(self, flow: Dict) -> FixSuggestion:
        vt = flow.get("vuln_type", "TAINT_FLOW")
        patch, rationale = _TAINT_FIX.get(
            vt, ("# sanitize a entrada antes do sink",
                 "Sanitize/valide o valor controlado pelo usuário antes do sink."))
        return FixSuggestion(
            rule_id=flow.get("rule_id", "SAST045"),
            cwe_id=flow.get("cwe_id", ""),
            line=flow.get("sink_line", 0),
            vuln_type=vt, suggested_patch=patch, rationale=rationale,
        )

    # ── Validação: a sugestão coincide com o fix real? ────────────────────────
    @staticmethod
    def explains_real_fix(sug: FixSuggestion, fixed_source: str) -> bool:
        """
        True se o guard proposto pelo Core aparece na versão corrigida real
        (compara operandos com qualquer relacional entre eles).  Para taint,
        procura o marcador da mitigação canônica.
        """
        if sug.guard_vars and len(sug.guard_vars) >= 2:
            a, b = re.escape(sug.guard_vars[0]), re.escape(sug.guard_vars[1])
            # a (> >= < <=) b   ou   b (> >= < <=) a  no fonte corrigido
            pat = re.compile(rf"\b{a}\b\s*(?:>=|>|<=|<)\s*\b{b}\b|"
                             rf"\b{b}\b\s*(?:>=|>|<=|<)\s*\b{a}\b")
            return bool(pat.search(fixed_source))
        if sug.guard_vars and len(sug.guard_vars) == 1:
            n = re.escape(sug.guard_vars[0])
            return bool(re.search(rf"\b{n}\b\s*(?:>=|>|<=|<)", fixed_source))
        # taint: procura marcador da mitigação
        markers = {
            "UNSAFE_DESERIALIZATION": r"json\.loads|safe_load",
            "COMMAND_INJECTION": r"shlex\.quote|shell\s*=\s*False|\[",
            "SQL_INJECTION": r"execute\([^,]+,\s*[\(\[]",
            "PATH_TRAVERSAL": r"realpath|abspath|startswith",
            "CODE_INJECTION": r"literal_eval",
        }
        m = markers.get(sug.vuln_type)
        return bool(m and re.search(m, fixed_source))
