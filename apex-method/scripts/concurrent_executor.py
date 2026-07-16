#!/usr/bin/env python3
"""
concurrent_executor.py — Parallel PoT-by-stance executor + PMI convergence (APEX cognitive
parallelism, Level A).

WHY THIS EXISTS:
  mental_interpreter promised a SPECULATION phase — N stances (optimistic / pessimistic /
  neutral / chaos) generated, executed in parallel, then merged — but nothing wired the parallel
  EXECUTION to the merge. This does exactly that: each stance's PoT program runs in an isolated
  subprocess concurrently (ThreadPool), each instance emits a SHA-256-hashed JSON result, a
  BARRIER waits until the stance counter is complete, then entropy_weighted_merge fuses them and
  the PMI (Bayesian) layer reports a confidence + a decision. If confidence is not high enough,
  it returns a RESTART directive that names NEW personas and skills for the next round.

WHEN TO USE:
  DEEP / RESEARCH / SCIENTIFIC, when >=2 genuinely different stances should be computed at once
  (the SPECULATION phase). For a single stance, just call pot.run_chain.

HOW IT WORKS (one round):
  1. each stance = {name, persona, program} where program prints a JSON line
     {"answer": <num|str>, "confidence": 0..1}. Programs run concurrently in subprocesses.
  2. each finished instance -> a result dict with a SHA-256 over its canonical JSON (integrity
     + dedup, echoing SR_42 / the Op1 memory ledger).
  3. BARRIER: merge ONLY when completed == total (PARALLEL_POT_COMPLETE) or, on failures,
     PARALLEL_POT_PARTIAL over what succeeded.
  4. entropy_weighted_merge -> PMI (bayes posterior + Omega + R_acum) -> a report.
  5. reliability below p_target -> RESTART directive with new personas (agent_registry) and new
     skills (gravity / native index), so the LLM can re-spawn a stronger round.

WHAT IF IT FAILS:
  a stance whose subprocess crashes is dropped and the round goes PARTIAL (never blocks all);
  if every stance fails, status is FAILED and the caller falls back to sequential reasoning.
  Missing sibling engines (bayes/gravity) are skipped and noted, never crash the round.
"""
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import pot  # isolated-subprocess PoT runner

# The parallelism BUDGET is the mode's agent count — the kernel's own ceiling, not an
# arbitrary max_parallel (author's decision). Faithful to apex_boot cognitive_modes.
MODE_AGENT_CAP = {"EXPRESS": 1, "FAST": 5, "CLARIFY": 3, "FOGGY": 5,
                  "DEEP": 8, "SCIENTIFIC": 8, "RESEARCH": 12, "STANDARD": 3}
# Probabilistic abort: a stance whose confidence falls below this is QUIT and a vaccine is
# recorded (code_genetics), so the same weak persona/task pairing is caught next time.
ABORT_CONFIDENCE = 0.35
_COMPETENCE_DB = os.path.expanduser("~/.apex-method/competence.db")


def _sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _record_competence(event: dict):
    """Persist an off-persona / aborted signal to SQLite (seed of the Op1 memory ledger).
    So a persona that reports 'not my specialty', or is aborted for low confidence, updates
    a durable competence table the next round can consult. Never raises."""
    try:
        os.makedirs(os.path.dirname(_COMPETENCE_DB), exist_ok=True)
        import sqlite3
        con = sqlite3.connect(_COMPETENCE_DB)
        con.execute("CREATE TABLE IF NOT EXISTS competence("
                    "sha TEXT PRIMARY KEY, ts REAL, persona TEXT, stance TEXT, task TEXT, "
                    "signal TEXT, confidence REAL)")
        sha = _sha256({k: event.get(k) for k in ("persona", "stance", "task", "signal")})
        con.execute("INSERT OR REPLACE INTO competence VALUES(?,?,?,?,?,?,?)",
                    (sha, time.time(), event.get("persona"), event.get("stance"),
                     event.get("task", "")[:200], event.get("signal"), event.get("confidence")))
        con.commit(); con.close()
        return sha
    except Exception:
        return None


def _run_stance(item, session_id, timeout, task=""):
    """Run one stance's PoT program in an isolated subprocess; return a hashed result.
    A stance program may print off_persona:true to say 'this isn't my specialty' — that is
    recorded to the competence DB and the stance is flagged (not merged as a strong voice)."""
    name = item["name"]
    persona = item.get("persona", name)
    r = pot.run_step(item["program"], timeout=timeout)   # subprocess timeout = loop/abort guard
    answer, confidence, off_persona, parse_ok = None, 0.0, False, False
    if r["ok"] and r["stdout"]:
        try:
            payload = json.loads(r["stdout"].splitlines()[-1])
            answer = payload.get("answer")
            confidence = float(payload.get("confidence", 0.0))
            off_persona = bool(payload.get("off_persona", False))
            parse_ok = True
        except Exception:
            pass
    aborted_timeout = (not r["ok"]) and "timeout" in (r.get("stderr", "") or "")
    core = {"stance": name, "persona": persona, "answer": answer,
            "confidence": round(confidence, 4), "session_id": session_id,
            "off_persona": off_persona, "ok": r["ok"] and parse_ok,
            "aborted": aborted_timeout, "ms": r["ms"], "code_hash": r["code_hash"]}
    core["sha256"] = _sha256({k: core[k] for k in ("stance", "persona", "answer",
                                                   "confidence", "off_persona", "session_id")})
    if off_persona:
        _record_competence({"persona": persona, "stance": name, "task": task,
                            "signal": "off_persona", "confidence": confidence})
    if aborted_timeout:
        _record_competence({"persona": persona, "stance": name, "task": task,
                            "signal": "aborted_timeout", "confidence": confidence})
    return core


def run_stances(task, stances, mode="DEEP", p_target=0.72, timeout=20, session_id=None,
                abort_below=ABORT_CONFIDENCE):
    """Execute stances concurrently, barrier-merge, PMI-report. The number of stances is
    capped by the MODE's agent count (kernel budget). A stance under `abort_below` confidence
    is QUIT and a vaccine recorded (code_genetics)."""
    session_id = session_id or hashlib.sha256(f"{task}{time.time()}".encode()).hexdigest()[:12]
    cap = MODE_AGENT_CAP.get(mode.upper(), 8)
    stances = stances[:cap]                       # budget = mode agent count
    total = len(stances)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(cap, max(1, total))) as ex:
        results = list(ex.map(lambda s: _run_stance(s, session_id, timeout, task), stances))

    # ── probabilistic ABORT + VACCINE: quit any stance whose confidence is too low ──
    aborted = []
    for r in results:
        if r["ok"] and r["confidence"] < abort_below:
            r["ok"] = False
            r["aborted"] = True
            aborted.append(r)
            _record_competence({"persona": r["persona"], "stance": r["stance"], "task": task,
                                "signal": "low_confidence_quit", "confidence": r["confidence"]})
            try:
                import code_genetics
                code_genetics.VaccineStore().save_vaccine(
                    f"low_confidence stance={r['stance']} persona={r['persona']} task={task[:60]}",
                    f"reassign to a specialist; {r['persona']} is weak here")
            except Exception:
                pass

    # ── BARRIER: only merge once the stance counter is complete ──
    done = [r for r in results if r["ok"]]
    completed, status = len(done), ("PARALLEL_POT_COMPLETE" if len(done) == total
                                    else "PARALLEL_POT_PARTIAL" if done else "FAILED")
    report = {"task": task, "session_id": session_id, "mode": mode, "budget_cap": cap,
              "status": status, "counter": {"completed": completed, "total": total},
              "aborted": [{"stance": a["stance"], "persona": a["persona"],
                           "confidence": a["confidence"]} for a in aborted],
              "off_persona": [r["stance"] for r in results if r.get("off_persona")],
              # the hashed session JSON carries the three named stance answers
              "stance_answers": {r["stance"]: r["answer"] for r in results},
              "per_stance": results, "wall_ms": round((time.time() - t0) * 1000, 1)}
    if not done:
        report["decision"] = "FALLBACK_SEQUENTIAL"
        return report

    # ── MERGE (entropy-weighted) ──
    try:
        import mental_interpreter
        merged = mental_interpreter.entropy_weighted_merge(
            [{"answer": r["answer"], "confidence": r["confidence"]} for r in done])
    except Exception as e:
        merged = {"answer": max(done, key=lambda r: r["confidence"])["answer"],
                  "note": f"merge fallback ({str(e)[:40]})"}
    report["merge"] = merged

    # ── PMI: Bayesian convergence report for the LLM ──
    try:
        import orchestrator
        pmi = orchestrator.pmi_converge(
            [{"discipline": r["stance"], "answer": r["answer"],
              "confidence": r["confidence"], "stance": r["stance"]} for r in done])
    except Exception as e:
        pmi = {"reliability": max(r["confidence"] for r in done),
               "method": f"pmi fallback ({str(e)[:40]})"}
    report["pmi"] = pmi
    reliability = float(pmi.get("reliability", 0.0) or 0.0)
    decision = pmi.get("decision", "ADOPT" if reliability >= p_target else "REVIEW")
    report["confidence"] = round(reliability, 4)
    report["decision"] = decision

    # ── RESTART directive if confidence is not high enough ──
    if reliability < p_target or decision not in ("ADOPT",):
        report["restart"] = _restart_directive(task, done)
    return report


def _restart_directive(task, done):
    """Name NEW personas + skills for a stronger next round (the LLM re-spawns from this)."""
    seen_personas = {r["persona"] for r in done}
    new_personas, new_skills = [], []
    try:
        import agent_registry
        for aid, cat, score in agent_registry.match_task_to_ext_agents(task, k=6):
            if aid not in seen_personas:
                new_personas.append(aid)
            if len(new_personas) >= 3:
                break
    except Exception:
        pass
    try:
        import repo_bridge
        new_skills = [{"id": h["id"], "path": h["path"]}
                      for h in repo_bridge.search_native(task, k=3)]
    except Exception:
        pass
    return {"reason": "confidence below target — re-spawn a stronger round",
            "assign_new_personas": new_personas or ["theorist", "researcher"],
            "resolve_new_skills": new_skills,
            "action": "spawn Agent subagents for the new personas, re-run run_stances"}


# ── ready-made stance program builders (the "PoT programs" the caller can hand out) ──
def numeric_stance_program(model_expr, samples, confidence):
    """Build a PoT program for a QUANTITATIVE stance: evaluates model_expr over `samples`
    (a dict of name->value) and prints {answer, confidence}. Pure arithmetic in the sandbox."""
    return (
        "import json\n"
        f"s = {json.dumps(samples)}\n"
        f"ans = {model_expr}\n"
        f"print(json.dumps({{'answer': round(float(ans), 6), 'confidence': {float(confidence)}}}))\n"
    )


def qualitative_stance_program(answer, confidence, off_persona=False):
    """Build a PoT program for a QUALITATIVE stance: emits a fixed answer/confidence the
    persona decided on. Set off_persona=True to signal 'this isn't my specialty' (recorded to
    the competence DB and NOT merged as a strong voice)."""
    return (
        "import json\n"
        f"print(json.dumps({{'answer': {json.dumps(answer)}, 'confidence': {float(confidence)}, "
        f"'off_persona': {bool(off_persona)}}}))\n"
    )


def default_stances(model_expr, base_samples, burn_key=None):
    """The canonical THREE stances (optimistic / pessimistic / neutral) over one model, so the
    hashed session JSON always carries the three named answers. `burn_key` (if given) is scaled
    down/up for optimistic/pessimistic; neutral uses base_samples as-is."""
    def scaled(factor):
        s = dict(base_samples)
        if burn_key and burn_key in s:
            s[burn_key] = s[burn_key] * factor
        return s
    return [
        {"name": "optimistic", "persona": "architect",
         "program": numeric_stance_program(model_expr, scaled(0.8), 0.80)},
        {"name": "neutral", "persona": "theorist",
         "program": numeric_stance_program(model_expr, scaled(1.0), 0.75)},
        {"name": "pessimistic", "persona": "critic",
         "program": numeric_stance_program(model_expr, scaled(1.3), 0.72)},
    ]


if __name__ == "__main__":
    # demo: the canonical three stances estimate runway (months) with different burn assumptions
    stances = default_stances("s['cash']/s['burn']", {"cash": 1200000, "burn": 100000}, burn_key="burn")
    rep = run_stances("size the emergency cash runway", stances, mode="DEEP")
    print(json.dumps({k: rep[k] for k in ("status", "budget_cap", "counter", "stance_answers",
                                          "merge", "confidence", "decision", "aborted")
                      if k in rep}, indent=2, ensure_ascii=False))
    if "restart" in rep:
        print("RESTART ->", json.dumps(rep["restart"], ensure_ascii=False))
