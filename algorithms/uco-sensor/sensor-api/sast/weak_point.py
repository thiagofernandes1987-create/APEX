"""
UCO-Sensor — Weak-Point Score  (M21)  ·  "onde alguém pode quebrar/invadir"
===========================================================================
META D: um **score probabilístico de ponto fraco** por módulo, que combina
os sinais que o Sensor já emite numa única medida explicável — o mapa de
superfície de ataque da missão ("identifica falhas de segurança e possíveis
pontos fracos").

Fatores (cada um normalizado para [0,1]) e sua leitura:
  * `security` — achados de segurança (M11 memory-safety + taint injeção/
    deser + taint-lite PHP/JS), ponderados por severidade → risco DIRETO.
  * `injection` — superfície de injeção (fontes→sinks) do taint → quão
    exposto a entrada do usuário.
  * `complexity` — complexidade ciclomática normalizada → mais caminhos,
    mais lugares para quebrar (degradação = superfície).
  * `hamiltonian` — energia estrutural (UCO) normalizada → módulos "quentes".

Score final 0–100 = 100 · (w·fatores).  Acompanha o BREAKDOWN dos fatores
para ser acionável (não é um número opaco — diz *por que* é fraco).

Determinístico e leve; usa só os motores já presentes.  Sem numpy
obrigatório.  Dado real, sem inventar.

API
---
    wp = WeakPointScorer().score(source, ".c", module_id="fpm_main.c")
    wp.score        -> float 0-100
    wp.factors      -> dict fator→[0,1]
    wp.top_reasons  -> list[str] (explicação acionável)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

_SEV_W = {"CRITICAL": 1.0, "HIGH": 0.7, "MEDIUM": 0.4, "LOW": 0.2}

# Pesos dos fatores no score final (somam 1.0).
_W = {"security": 0.45, "injection": 0.25, "complexity": 0.18, "hamiltonian": 0.12}


@dataclass
class WeakPoint:
    module_id: str
    score: float
    factors: Dict[str, float] = field(default_factory=dict)
    n_security: int = 0
    top_reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"module_id": self.module_id, "score": round(self.score, 1),
                "factors": {k: round(v, 3) for k, v in self.factors.items()},
                "n_security": self.n_security, "top_reasons": self.top_reasons}


def _sat(x: float, k: float) -> float:
    """Satura x/(x+k) em [0,1) — retornos decrescentes."""
    return x / (x + k) if x > 0 else 0.0


class WeakPointScorer:
    def __init__(self) -> None:
        # imports tardios: mantêm o módulo importável mesmo sem deps
        from lang_adapters.registry import get_registry
        from sast.guard_aware import GuardAwareScanner
        from sast.taint_engine import TaintAnalyzer
        from sast.taint_lite import TaintLite
        self._reg = get_registry()
        self._m11 = GuardAwareScanner()
        self._taint = TaintAnalyzer()
        self._lite = TaintLite()

    def score(self, source: str, ext: str = "", module_id: str = "") -> WeakPoint:
        reasons: List[str] = []

        # ── segurança (M11 + taint + taint-lite) ────────────────────────────
        sec_w = 0.0
        n_sec = 0
        for gf in self._m11.scan(source, ext):
            sec_w += _SEV_W.get(getattr(gf, "severity", "HIGH"), 0.5)
            n_sec += 1
        if n_sec:
            reasons.append(f"{n_sec} risco(s) de memory-safety (M11)")

        inj_surface = 0.0
        if ext.lower().startswith(".py") or ext.lower() == ".py":
            td = self._taint.analyze(source).to_dict()
            paths = td.get("taint_path_count", 0)
            inj_surface = td.get("injection_surface", 0.0) or 0.0
            for _f in range(len(td.get("flows", []) or [])):
                sec_w += _SEV_W["CRITICAL"] * 0.8
            n_flows = len(td.get("flows", []) or [])
            if n_flows:
                reasons.append(f"{n_flows} fluxo(s) fonte→sink (taint Python)")
            n_sec += n_flows
        lite = self._lite.scan(source, ext)
        for lf in lite:
            sec_w += _SEV_W.get(lf.severity, 0.7)
        if lite:
            reasons.append(f"{len(lite)} injeção(ões) PHP/JS (taint-lite)")
            n_sec += len(lite)
            inj_surface = max(inj_surface, _sat(len(lite), 2.0))

        # ── degradação estrutural (UCO MetricVector) ────────────────────────
        cyc = ham = 0.0
        try:
            mv = self._reg.analyze(source, file_extension=ext or ".txt",
                                   module_id=module_id or "x", commit_hash="x")
            cyc = float(getattr(mv, "cyclomatic_complexity", 0) or 0)
            ham = float(getattr(mv, "hamiltonian", 0.0) or 0.0)
        except Exception:  # pragma: no cover
            pass
        if cyc >= 40:
            reasons.append(f"complexidade ciclomática alta ({int(cyc)})")

        factors = {
            "security": _sat(sec_w, 1.5),
            "injection": min(1.0, inj_surface),
            "complexity": _sat(cyc, 40.0),
            "hamiltonian": _sat(ham, 50.0),
        }
        score = 100.0 * sum(_W[k] * factors[k] for k in _W)
        return WeakPoint(module_id=module_id or "module", score=score,
                         factors=factors, n_security=n_sec,
                         top_reasons=reasons[:4])
