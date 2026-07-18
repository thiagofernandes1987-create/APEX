#!/usr/bin/env python3
"""
competence_matrix.py — APEX metacognition (Op3): the agent x domain heat-map + the
persona/skill/rule diagnosis.

WHY THIS EXISTS:
  When an agent's answer is weak, the system must know WHY: is it the wrong PERSONA (right
  domain, stuck perspective), a missing SKILL, or just a HARD PROBLEM? This module builds the
  "heat-map" the author remembers — a matrix keyed by (agent, domain) whose cells carry the
  temperature T (H_cognitive), the historical reward, the estimated difficulty, and the
  rejections/variance state — and emits a structured diagnosis + action.

WHEN TO USE:
  - concurrent_executor: to decide abort/replace and HOW (swap persona vs inject skill).
  - mental_interpreter/deep_research: to pick the best agents and when to restart a round.

DIAGNOSIS (faithful to DIFF_v22_008 + DIFF_AGENT_SKILL):
  - stuck (rejections_streak>20 OR var(conf)<0.03) + domain IS the agent's -> PERSONA_SWAP
    (reassign with phase_offset += pi, opposite perspective).
  - low reward for the domain (success_tracker) -> INJECT_SKILL (forced_skill; find it in the
    native library or the marketplace).
  - high estimated difficulty (BehavioralDifficultyEstimator) -> HARD_PROBLEM (escalate mode
    / add the governing rule/diff — it is the problem, not the agent).

WHAT IF IT FAILS:
  Pure stdlib; a missing competence DB just means zero history (neutral reward). estimate()
  degrades to the average difficulty when no reference matches. Never raises on bad input.
"""
import math
import os
import re
import sqlite3
import time

# AUD-W1: APEX_METHOD_HOME redirects the durable store (tests/CI isolation) — see config.py.
_COMPETENCE_DB = os.path.join(os.environ.get("APEX_METHOD_HOME")
                              or os.path.expanduser("~/.apex-method"), "competence.db")

REJECTIONS_THRESHOLD = 20      # DIFF_v22_008
LOW_VARIANCE_THRESHOLD = 0.03  # variance < 3% = stuck agent
PI = math.pi


# ── BehavioralDifficultyEstimator (DIFF_v22_004), nativized ──────────────────
DIFFICULTY_REFS = {
    "logistic_growth": {"keywords": {"logistic", "crescimento", "logístico", "ode", "dx/dt",
                                     "k", "r", "população", "capacidade"}, "difficulty": 0.35},
    "lotka_volterra": {"keywords": {"lotka", "volterra", "predador", "presa", "alpha", "beta",
                                    "delta", "gamma", "ciclo", "dx/dt", "dy/dt"}, "difficulty": 0.55},
    "navier_stokes": {"keywords": {"navier", "stokes", "turbulência", "fluido", "reynolds",
                                   "pressão", "viscosidade", "pde"}, "difficulty": 0.92},
    "optimization_simple": {"keywords": {"minimizar", "maximizar", "otimizar", "custo",
                                         "objetivo", "variável", "restrição"}, "difficulty": 0.40},
    "optimization_combinatorial": {"keywords": {"tsp", "caixeiro", "mochila", "knapsack",
                                                "combinatória", "np-hard", "discreto", "roteamento"},
                                   "difficulty": 0.70},
    "linear_algebra": {"keywords": {"matriz", "autovalor", "eigenvalue", "decomposição",
                                    "svd", "lu", "ax=b", "sistema linear"}, "difficulty": 0.30},
    "stochastic_simulation": {"keywords": {"estocástico", "monte carlo", "amostrar",
                                           "distribuição", "mcmc", "bayesiano", "probabilidade"},
                              "difficulty": 0.60},
    # non-math classes (the old refs were math-only, so audit/security/engineering tasks fell to
    # the average fallback ~0.5 and never escalated — the real difficulty was never established):
    "security_audit": {"keywords": {"audit", "auditoria", "autópsia", "autopsia", "autopsy",
                                    "security", "segurança", "seguranca", "vulnerability",
                                    "vulnerabilidade", "exploit", "threat", "ameaça", "pentest",
                                    "cve", "forensic", "forense", "breach", "hardening"},
                       "difficulty": 0.80},
    "architecture_design": {"keywords": {"architecture", "arquitetura", "design", "system",
                                        "sistema", "distributed", "distribuído", "scalability",
                                        "escalabilidade", "microservices", "microserviços",
                                        "refactor", "refatorar", "coupling", "acoplamento"},
                            "difficulty": 0.62},
    "compliance_regulatory": {"keywords": {"compliance", "conformidade", "hipaa", "gdpr", "lgpd",
                                          "regulatory", "regulação", "regulacao", "regulamentação",
                                          "legal", "contract", "contrato", "sox", "pci", "privacy",
                                          "privacidade"}, "difficulty": 0.72},
    "debugging_rootcause": {"keywords": {"debug", "bug", "root cause", "causa raiz", "incident",
                                        "incidente", "crash", "race condition", "deadlock",
                                        "regression", "regressão", "flaky", "heisenbug"},
                            "difficulty": 0.66},
}


def _keywords(text):
    return set(re.findall(r"\b\w{3,}\b", (text or "").lower()))


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def estimate_difficulty(problem_text, cfi_preliminary=0.5):
    """bde_score + fused_cfi via Jaccard vs known references (BehavioralDifficultyEstimator).
    fused_cfi = 0.6*CFI + 0.4*bde_score. Returns the difficulty of the closest problem class."""
    kw = _keywords(problem_text)
    best_ref, best_sim, best_diff = None, -1.0, 0.35
    for name, ref in DIFFICULTY_REFS.items():
        sim = _jaccard(kw, ref["keywords"])
        if sim > best_sim:
            best_sim, best_ref, best_diff = sim, name, ref["difficulty"]
    uncertain = best_sim < 0.10
    if uncertain:
        # the estimator does NOT recognize the problem class. Do NOT settle on a mediocre average
        # (that silently under-rates novel/hard tasks — the real difficulty was never established).
        # Treat UNKNOWN as a conservative escalation signal: bde is pushed up, uncertain=True flags
        # that the 3 dissect personas MUST establish the real difficulty before proceeding.
        bde = 0.70
        best_ref = "UNKNOWN_CLASS"
    else:
        bde = best_diff
    return {"bde_score": round(bde, 3), "best_ref": best_ref, "uncertain": uncertain,
            "jaccard": round(max(0, best_sim), 3),
            "fused_cfi": round(min(1.0, 0.6 * cfi_preliminary + 0.4 * bde), 3)}


# ── historical reward per (agent, domain) from the competence ledger ─────────
def _reward(agent, domain):
    """Historical reward in [0,1]: 1 - (fraction of off_persona/low_confidence signals for this
    agent), from the SESSION competence ledger. When the DURABLE cross-session learning store
    (Op-P3, learning.py) has enough evidence for (agent, domain), its validated posterior WINS —
    that is what makes learning persist and change future picks. Neutral 0.5 when there is no
    history."""
    session_reward, n = 0.5, 0
    try:
        con = sqlite3.connect(_COMPETENCE_DB)
        rows = con.execute("SELECT signal, confidence FROM competence WHERE persona=?",
                           (agent,)).fetchall()
        con.close()
        if rows:
            bad = sum(1 for s, _ in rows if s in ("off_persona", "low_confidence_quit", "aborted_timeout"))
            session_reward, n = round(max(0.0, 1.0 - bad / len(rows)), 3), len(rows)
    except Exception:
        pass
    # Op-P3: durable, validated reward overrides once there is enough cross-session evidence.
    try:
        import learning
        d = learning.score("persona", agent, domain)
        if d["n"] >= learning.MIN_OBS:
            return d["mean"], d["n"] + n
    except Exception:
        pass
    return session_reward, n


def is_stuck(rejections_streak, confidence_history):
    """DIFF_v22_008 trigger: rejections_streak > 20 OR var(last 3 confidences) < 0.03."""
    if rejections_streak > REJECTIONS_THRESHOLD:
        return True, "rejections_streak"
    recent = list(confidence_history)[-3:]
    if len(recent) >= 2:
        mean = sum(recent) / len(recent)
        var = sum((x - mean) ** 2 for x in recent) / len(recent)
        if var < LOW_VARIANCE_THRESHOLD:
            return True, "low_variance"
    return False, None


def diagnose(agent, domain, task, temperature=0.3, rejections_streak=0,
             confidence_history=(), phase_offset=0.0):
    """Emit the structured diagnosis + action. This is the persona-vs-skill-vs-rule decision."""
    reward, n_hist = _reward(agent, domain)
    diff = estimate_difficulty(task)
    stuck, why = is_stuck(rejections_streak, confidence_history)

    if diff["bde_score"] >= 0.85:
        action = {"diagnosis": "HARD_PROBLEM", "why": f"difficulty {diff['bde_score']} ({diff['best_ref']})",
                  "action": "escalate mode + attach the governing rule/diff (norm/standard)",
                  "not_the_agent": True}
    elif reward < 0.4 and n_hist >= 2:
        action = {"diagnosis": "INJECT_SKILL",
                  "why": f"low reward {reward} for {agent} in this domain (n={n_hist})",
                  "action": "inject a forced_skill (native library or marketplace) — skill gap, not persona"}
    elif stuck:
        action = {"diagnosis": "PERSONA_SWAP", "why": f"agent stuck ({why})",
                  "action": "reassign with opposite perspective (phase_offset += pi)",
                  "new_phase_offset": round((phase_offset + PI) % (2 * PI), 4)}
    else:
        action = {"diagnosis": "OK", "why": "healthy — high T is exploration, not failure",
                  "action": "continue"}

    return {"agent": agent, "domain": domain, "temperature": round(temperature, 3),
            "reward": reward, "history": n_hist, "difficulty": diff, "stuck": stuck, **action}


def heatmap(agents, domain, task, states=None):
    """Build the agent x domain heat-map: one diagnosed cell per agent. `states` (optional)
    maps agent -> {rejections_streak, confidence_history, temperature, phase_offset}."""
    states = states or {}
    cells = []
    for a in agents:
        st = states.get(a, {})
        cells.append(diagnose(a, domain, task,
                              temperature=st.get("temperature", 0.3),
                              rejections_streak=st.get("rejections_streak", 0),
                              confidence_history=st.get("confidence_history", ()),
                              phase_offset=st.get("phase_offset", 0.0)))
    # rank the best agents for this domain: high reward, low difficulty-mismatch, not stuck
    ranked = sorted(cells, key=lambda c: (-c["reward"], c["stuck"]))
    return {"domain": domain, "task": task[:120], "cells": cells,
            "best_agents": [c["agent"] for c in ranked if c["diagnosis"] in ("OK", "PERSONA_SWAP")][:3],
            "generated_at": time.time()}


if __name__ == "__main__":
    import json
    print("difficulty (navier stokes turbulência):",
          estimate_difficulty("resolver turbulência de fluido via navier stokes pde"))
    print("difficulty (linear system):", estimate_difficulty("resolver sistema linear ax=b via svd"))
    print("stuck (streak 25):", is_stuck(25, [0.5]))
    print("stuck (flat conf):", is_stuck(3, [0.50, 0.505, 0.50]))
    print("diagnose HARD:", json.dumps(diagnose("architect", "science",
          "navier stokes turbulência fluido reynolds pde", temperature=0.4), ensure_ascii=False))
    print("diagnose SWAP:", json.dumps(diagnose("critic", "engineering", "refatorar backend",
          rejections_streak=25), ensure_ascii=False))
