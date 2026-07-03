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
    """
    Resultado de UMA passada do loop de auto-correção Sensor→Corretor→Revalida.

    Campos (o que cada um significa numa auditoria):
      * signals_before   — findings que o Sensor emitiu no código ORIGINAL.
      * fixes_applied    — patches que o corretor de fato aplicou (mudaram o
                           texto). Finding sem `guard_expr` não gera patch.
      * silenced         — findings originais que SUMIRAM após o patch
                           (o objetivo: "parou de disparar").
      * still_firing     — findings originais que PERSISTIRAM após o patch.
      * newly_introduced — findings que NÃO existiam no original e apareceram
                           SÓ depois do patch: regressões que o próprio
                           auto-fix criou. É a razão de existir do
                           `before_keys` (comparar antes×depois). Adicionado
                           no Sprint BZ (v3.49.0).
      * taint_flows      — fluxos fonte→sink do M17 (informativo por ora).
      * patched_source   — código já com todos os patches aplicados.
    """
    ext: str
    signals_before: List[Dict[str, Any]] = field(default_factory=list)
    fixes_applied: List[Dict[str, Any]] = field(default_factory=list)
    silenced: List[Dict[str, Any]] = field(default_factory=list)
    still_firing: List[Dict[str, Any]] = field(default_factory=list)
    newly_introduced: List[Dict[str, Any]] = field(default_factory=list)  # BZ: regressão do auto-fix
    taint_flows: List[Dict[str, Any]] = field(default_factory=list)
    patched_source: str = ""

    @property
    def silenced_count(self) -> int:
        return len(self.silenced)

    @property
    def regressed(self) -> bool:
        """True se o auto-fix INTRODUZIU algum sinal novo (regressão)."""
        return bool(self.newly_introduced)

    @property
    def fully_resolved(self) -> bool:
        """
        True só quando o loop resolveu tudo COM SEGURANÇA: havia sinais,
        nenhum persistiu, E o patch não introduziu sinal novo. A cláusula
        anti-regressão (`not self.regressed`) entrou no Sprint BZ — antes,
        um patch que silenciava o alvo mas criava outro problema ainda era
        contado como "resolvido", o que é falso.
        """
        return bool(self.signals_before) and not self.still_firing and not self.regressed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ext": self.ext,
            "signals_before": len(self.signals_before),
            "fixes_applied": len(self.fixes_applied),
            "silenced": len(self.silenced),
            "still_firing": len(self.still_firing),
            "newly_introduced": len(self.newly_introduced),
            "regressed": self.regressed,
            "taint_flows": len(self.taint_flows),
            "fully_resolved": self.fully_resolved,
            "detail": {
                "silenced": self.silenced,
                "still_firing": self.still_firing,
                "newly_introduced": self.newly_introduced,
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

        # ── revalidação ──────────────────────────────────────────────────────
        # O Sensor re-escaneia o código JÁ corrigido. Comparamos o conjunto de
        # findings ANTES (before_keys) com o DEPOIS (after_keys) por chave
        # estável (regra + variáveis-do-guard):
        #   • silenced          = estava em before, sumiu em after   → resolvido
        #   • still_firing      = estava em before e continua em after → não resolvido
        #   • newly_introduced  = está em after mas NÃO estava em before → o
        #                         próprio patch criou (regressão). Sem esta
        #                         comparação (before_keys) o loop não perceberia
        #                         que "consertou" criando outro bug — daí o
        #                         `before_keys` ser essencial, não dead code.
        before_keys = {_guard_key(g) for g in signals}         # BZ: baseline p/ detectar regressão
        after = self._emit_signals(patched, ext)
        after_keys = {_guard_key(g) for g in after}

        for g in signals:                                       # veredito por finding original
            k = _guard_key(g)
            d = self._finding_dict(g)
            if k not in after_keys:
                rep.silenced.append(d)                          # parou de disparar ✓
            else:
                rep.still_firing.append(d)                      # persistiu

        for g in after:                                         # BZ: sinais que só existem pós-patch
            if _guard_key(g) not in before_keys:
                rep.newly_introduced.append(self._finding_dict(g))  # regressão criada pelo corretor
        return rep

    @staticmethod
    def _finding_dict(g: GuardFinding) -> Dict[str, Any]:
        return {
            "rule_id": g.rule_id, "cwe_id": g.cwe_id, "line": g.line,
            "title": g.title, "guard_on": list(g.needs_guard_on),
            "snippet": g.snippet[:120],
        }
