"""
UCO-Sensor — APEX Auto-Correction Loop (MVP local)  (M19)
==========================================================
Fecha o ciclo que é a razão-de-ser do produto: **o Sensor emite sinais → um
"corretor" aplica o patch sugerido → o Sensor revalida e confirma que o sinal
silenciou**. Este MVP roda **100% local, sem IA externa** — o "corretor" é o
`FixSuggester` (M18), que deriva o patch determinístico do próprio finding
(ex.: inserir o guard `pilen > slen` que faltava). A integração com IA/MCP
real (um LLM propondo o patch) pluga aqui depois, trocando só o `corrector`.

Fluxo (uma passada)
-------------------
    sinais   = Sensor.scan(source)          # M11 guard-aware (+ M17 taint p/ Python)
    p/ cada finding corrigível:
        sug      = corrector.suggest(finding)   # M18 FixSuggester
        source'  = corrector.apply(source', sug)
    após     = Sensor.scan(source')          # revalidação
    silenciou = chaves(sinais) − chaves(após)  # o que o patch de fato apagou

A comparação é por **chave (rule_id, variáveis-do-guard)** — independente de
linha — para ser robusta ao deslocamento causado pela inserção dos patches.
Nenhum dado é inventado: se o patch não silencia o sinal, ele aparece em
`still_firing` (honesto).

API
---
    loop = ApexLoop()
    rep  = loop.run(source, ext=".c")
    rep.silenced          -> [chaves de findings que o patch apagou]
    rep.still_firing      -> [findings que persistiram]
    rep.patched_source    -> código com os patches aplicados
    rep.to_dict()         -> artefato serializável (para o dataset/relatório)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from sast.guard_aware import GuardAwareScanner, GuardFinding
from sast.fix_suggester import FixSuggester, FixSuggestion

# M17 taint (Python) é opcional no sinal — importado defensivamente para não
# acoplar o loop a AST-Python quando o alvo é C/Rust.
try:
    from sast.taint_interproc import InterprocTaintAnalyzer
except Exception:  # pragma: no cover
    InterprocTaintAnalyzer = None  # type: ignore[assignment]


def _guard_key(gf: GuardFinding) -> Tuple[str, Tuple[str, ...]]:
    """Chave estável de um finding: (regra, variáveis que precisam de guard)."""
    return (gf.rule_id, tuple(gf.needs_guard_on))


@dataclass
class ApexLoopReport:
    """Resultado de uma passada do loop de auto-correção."""
    ext: str
    signals_before: List[Dict[str, Any]] = field(default_factory=list)
    fixes_applied: List[Dict[str, Any]] = field(default_factory=list)
    silenced: List[Dict[str, Any]] = field(default_factory=list)
    still_firing: List[Dict[str, Any]] = field(default_factory=list)
    taint_flows: List[Dict[str, Any]] = field(default_factory=list)
    patched_source: str = ""

    @property
    def silenced_count(self) -> int:
        return len(self.silenced)

    @property
    def fully_resolved(self) -> bool:
        """True se todos os sinais iniciais foram silenciados pelos patches."""
        return bool(self.signals_before) and not self.still_firing

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ext": self.ext,
            "signals_before": len(self.signals_before),
            "fixes_applied": len(self.fixes_applied),
            "silenced": len(self.silenced),
            "still_firing": len(self.still_firing),
            "taint_flows": len(self.taint_flows),
            "fully_resolved": self.fully_resolved,
            "detail": {
                "silenced": self.silenced,
                "still_firing": self.still_firing,
                "fixes": self.fixes_applied,
            },
        }


class ApexLoop:
    """
    Orquestrador do ciclo Sensor→Corretor→Revalidação (MVP local).

    O `corrector` é injetável: por padrão o `FixSuggester` determinístico
    (M18). Trocá-lo por um cliente IA/MCP no futuro não muda o loop — só a
    fonte do patch.
    """

    def __init__(self, corrector: FixSuggester | None = None) -> None:
        self._scanner = GuardAwareScanner()
        self._corrector = corrector or FixSuggester()

    # ── fase de sinal ────────────────────────────────────────────────────────
    def _emit_signals(self, source: str, ext: str) -> List[GuardFinding]:
        return self._scanner.scan(source, ext)

    def _emit_taint(self, source: str, ext: str) -> List[Dict[str, Any]]:
        if ext == ".py" and InterprocTaintAnalyzer is not None:
            try:
                return [f.to_dict() for f in InterprocTaintAnalyzer().analyze(source)]
            except Exception:  # pragma: no cover
                return []
        return []

    # ── uma passada completa do loop ─────────────────────────────────────────
    def run(self, source: str, ext: str = ".c") -> ApexLoopReport:
        rep = ApexLoopReport(ext=ext)

        signals = self._emit_signals(source, ext)
        rep.signals_before = [self._finding_dict(g) for g in signals]
        rep.taint_flows = self._emit_taint(source, ext)

        # fase de correção — aplica o patch determinístico de cada finding
        patched = source
        for gf in signals:
            sug: FixSuggestion = self._corrector.suggest_for_guard(gf)
            if not getattr(sug, "guard_expr", None):
                continue
            new_patched = FixSuggester.apply_fix(patched, sug)
            if new_patched != patched:
                patched = new_patched
                rep.fixes_applied.append(sug.to_dict())
        rep.patched_source = patched

        # revalidação — o Sensor re-escaneia o código corrigido
        after = self._emit_signals(patched, ext)
        after_keys = {_guard_key(g) for g in after}

        for g in signals:
            k = _guard_key(g)
            d = self._finding_dict(g)
            if k not in after_keys:
                rep.silenced.append(d)
            else:
                rep.still_firing.append(d)
        return rep

    @staticmethod
    def _finding_dict(g: GuardFinding) -> Dict[str, Any]:
        return {
            "rule_id": g.rule_id, "cwe_id": g.cwe_id, "line": g.line,
            "title": g.title, "guard_on": list(g.needs_guard_on),
            "snippet": g.snippet[:120],
        }
