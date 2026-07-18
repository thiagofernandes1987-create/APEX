#!/usr/bin/env python3
"""
token_tracker.py — medição REAL de tokens por rodada e por passo do kernel (OPP-99, item 3
do autor): as estimativas do fluxo por modo deixam de ser chute e passam a ser calibradas.

WHY THIS EXISTS:
  pipeline_dsm.mode_flow decidia rodar/pular passos com custos [APPROX] fixos. Este tracker
  registra, a cada rodada real do orchestrator, o TAMANHO dos payloads que cada passo produziu
  (proxy honesto: chars/4 ≈ tokens — é a medida do que o runtime gera, não a fatura exata do
  provedor, e é rotulada assim). Com amostras suficientes (>= MIN_SAMPLES), a média MEDIDA
  substitui a estimativa no DSM — o fluxo por modo passa a ser otimizado com dados reais desta
  máquina/uso, e o desperdício é cortado onde ele de fato acontece.

WHEN TO USE:
  - o orchestrator grava automaticamente (start_round/record/end_round em todo run FULL_PIPELINE);
  - averages(): médias medidas por passo (alimenta pipeline_dsm.mode_flow);
  - report(): medido vs estimado, passo a passo — onde a estimativa estava errada.

WHAT IF IT FAILS:
  Store ilegível -> recomeça vazio; nunca levanta exceção no caminho do orchestrator (medição
  jamais pode derrubar a execução). Proxy chars/4 é declarado, não escondido.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

MIN_SAMPLES = 3          # medições necessárias antes de uma média substituir a estimativa
KEEP_ROUNDS = 200        # rodadas retidas (janela deslizante)


def _store_path():
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "token_rounds.json")


def _tokens_of(payload):
    """Proxy declarado: chars/4. Aceita str/dict/list/int(chars)."""
    if isinstance(payload, int):
        chars = payload
    elif isinstance(payload, str):
        chars = len(payload)
    else:
        try:
            chars = len(json.dumps(payload, ensure_ascii=False, default=str))
        except Exception:
            chars = len(str(payload))
    return max(1, chars // 4)


def _load():
    try:
        with open(_store_path(), encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def _save(rounds):
    try:
        with open(_store_path(), "w", encoding="utf-8") as f:
            json.dump(rounds[-KEEP_ROUNDS:], f, ensure_ascii=False)
    except Exception:
        pass


def start_round(mode, task=""):
    """Abre uma rodada de medição (o orchestrator chama no início de todo FULL_PIPELINE)."""
    return {"mode": (mode or "STANDARD").upper(), "task": (task or "")[:80],
            "ts": time.time(), "steps": {}}


def record(rnd, step, payload):
    """Registra o payload REAL que um passo produziu (tokens = chars/4, declarado)."""
    if rnd is None:
        return None
    rnd["steps"][step] = rnd["steps"].get(step, 0) + _tokens_of(payload)
    return rnd


def end_round(rnd):
    """Fecha e persiste a rodada; devolve o total medido."""
    if rnd is None or not rnd.get("steps"):
        return {"status": "EMPTY"}
    rnd["total"] = sum(rnd["steps"].values())
    rounds = _load()
    rounds.append(rnd)
    _save(rounds)
    return {"status": "OK", "mode": rnd["mode"], "total": rnd["total"],
            "steps": rnd["steps"], "rounds_stored": len(rounds)}


def averages(min_samples=MIN_SAMPLES):
    """Média MEDIDA por passo (todas as rodadas). Só passos com >= min_samples amostras —
    é o que o pipeline_dsm consome no lugar da estimativa."""
    sums, counts = {}, {}
    for r in _load():
        for step, tk in r.get("steps", {}).items():
            sums[step] = sums.get(step, 0) + tk
            counts[step] = counts.get(step, 0) + 1
    return {s: {"avg": round(sums[s] / counts[s]), "n": counts[s]}
            for s in sums if counts[s] >= min_samples}


def report():
    """Medido vs estimado, passo a passo — onde a estimativa do DSM estava errada."""
    try:
        import pipeline_dsm
        est = {s: tk for s, _dh, tk in pipeline_dsm.STEP_EST}
    except Exception:
        est = {}
    meas = averages(min_samples=1)
    rows = []
    for step in sorted(set(est) | set(meas)):
        m = meas.get(step)
        rows.append({"step": step, "estimated": est.get(step),
                     "measured_avg": m and m["avg"], "samples": m and m["n"] or 0,
                     "calibrated": bool(m and m["n"] >= MIN_SAMPLES)})
    return {"note": "measured = chars/4 dos payloads do runtime (proxy declarado)",
            "rounds": len(_load()), "steps": rows}


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    r = report()
    print(f"rodadas medidas: {r['rounds']}  ({r['note']})")
    for row in r["steps"]:
        cal = "MEDIDO" if row["calibrated"] else ("parcial" if row["samples"] else "estimado")
        print(f"  {row['step']:20} est={str(row['estimated']):>6}  "
              f"medido={str(row['measured_avg']):>6} (n={row['samples']})  [{cal}]")
