"""
UCO-Sensor — CFG-based Signals via UCO V4  (M15)
=================================================
Extrai sinais de **fluxo de controle** do UCO V4 absorvido (`uco_core`,
`UniversalAnalyzer` + `GenericCFGBuilder`) e os expõe como sinal de primeira
classe do sensor — para **qualquer** linguagem, não só Python.

Isto fecha o item de checklist "consumir o GenericCFG do V4 para C/Rust/Java":
até a Sprint BJ o V4 estava absorvido mas o CFG genérico não era consumido
pelo sensor.  Agora `cfg_signals(source, language)` devolve:

    * reachable_count / node_count / reachable_ratio  (código morto por CFG)
    * infinite_loop_risk        (heurística de loop sem saída — classe DoS)
    * cyclomatic_complexity / loop_count / max_depth
    * syntactic_dead_code       (blocos inalcançáveis)

Correção de honestidade (Sprint BJ): o V4 NÃO retorna None para não-Python —
computa tudo isso via CFG genérico (Pygments) quando invocado corretamente
(`analyze(code, language_hint=...)`).

Degradação graciosa: qualquer falha (V4 ausente, parse impossível) → sinais
zerados com ``status="unavailable"``; nunca levanta.

API
---
    sig = cfg_signals("int f(){...}", "c")
    sig["infinite_loop_risk"], sig["reachable_ratio"], sig["cyclomatic"]
"""
from __future__ import annotations

from typing import Dict


def cfg_signals(source: str, language: str = "python") -> Dict:
    """Sinais de CFG do UCO V4 para *source*.  Nunca levanta."""
    base = {
        "status": "ok", "language": language,
        "node_count": 0, "edge_count": 0, "reachable_count": 0,
        "reachable_ratio": 1.0, "syntactic_dead_code": 0,
        "infinite_loop_risk": 0.0, "cyclomatic": 0, "loop_count": 0,
        "max_depth": 0,
    }
    try:
        from uco_core import UniversalAnalyzer
    except Exception:  # pragma: no cover
        base["status"] = "unavailable"
        return base
    try:
        res = UniversalAnalyzer().analyze(source, language_hint=language)
        m = res.metrics
        nodes = int(getattr(m, "node_count", 0) or 0)
        reach = int(getattr(m, "reachable_count", 0) or 0)
        base.update(
            node_count=nodes,
            edge_count=int(getattr(m, "edge_count", 0) or 0),
            reachable_count=reach,
            reachable_ratio=(reach / nodes if nodes else 1.0),
            syntactic_dead_code=int(getattr(m, "syntactic_dead_code", 0) or 0),
            infinite_loop_risk=float(getattr(m, "infinite_loop_risk", 0.0) or 0.0),
            cyclomatic=int(getattr(m, "cyclomatic_complexity", 0) or 0),
            loop_count=int(getattr(m, "loop_count", 0) or 0),
            max_depth=int(getattr(m, "max_depth", 0) or 0),
        )
    except Exception:  # pragma: no cover
        base["status"] = "unavailable"
    return base


def unreachable_after_return(source: str, language: str = "python") -> bool:
    """
    True quando o CFG indica blocos inalcançáveis (código morto) — sinal de
    degradação frequentemente introduzido por refatorações/geração automática.
    """
    sig = cfg_signals(source, language)
    return sig["status"] == "ok" and sig["syntactic_dead_code"] > 0
