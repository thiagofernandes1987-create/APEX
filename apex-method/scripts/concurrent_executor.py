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


def _sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _run_stance(item, session_id, timeout):
    """Run one stance's PoT program in an isolated subprocess; return a hashed result."""
    name = item["name"]
    persona = item.get("persona", name)
    r = pot.run_step(item["program"], timeout=timeout)
    answer, confidence, parse_ok = None, 0.0, False
    if r["ok"] and r["stdout"]:
        try:
            payload = json.loads(r["stdout"].splitlines()[-1])
            answer = payload.get("answer")
            confidence = float(payload.get("confidence", 0.0))
            parse_ok = True
        except Exception:
            pass
    core = {"stance": name, "persona": persona, "answer": answer,
            "confidence": round(confidence, 4), "session_id": session_id,
            "ok": r["ok"] and parse_ok, "ms": r["ms"], "code_hash": r["code_hash"]}
    core["sha256"] = _sha256({k: core[k] for k in ("stance", "persona", "answer",
                                                   "confidence", "session_id")})
    return core


def run_stances(task, stances, p_target=0.72, timeout=20, max_workers=4, session_id=None):
    """Execute stances concurrently, barrier-merge, PMI-report. Returns the full report."""
    session_id = session_id or hashlib.sha256(f"{task}{time.time()}".encode()).hexdigest()[:12]
    total = len(stances)
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=min(max_workers, max(1, total))) as ex:
        results = list(ex.map(lambda s: _run_stance(s, session_id, timeout), stances))

    # ── BARRIER: only merge once the stance counter is complete ──
    done = [r for r in results if r["ok"]]
    completed, status = len(done), ("PARALLEL_POT_COMPLETE" if len(done) == total
                                    else "PARALLEL_POT_PARTIAL" if done else "FAILED")
    report = {"task": task, "session_id": session_id, "status": status,
              "counter": {"completed": completed, "total": total},
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


def qualitative_stance_program(answer, confidence):
    """Build a PoT program for a QUALITATIVE stance: emits a fixed answer/confidence the
    persona decided on (the reasoning is the LLM's; this just carries it into the merge)."""
    return (
        "import json\n"
        f"print(json.dumps({{'answer': {json.dumps(answer)}, 'confidence': {float(confidence)}}}))\n"
    )


if __name__ == "__main__":
    # demo: 3 stances estimate a project's runway (months) with different burn assumptions
    stances = [
        {"name": "optimistic", "persona": "architect",
         "program": numeric_stance_program("s['cash']/s['burn']", {"cash": 1200000, "burn": 90000}, 0.80)},
        {"name": "pessimistic", "persona": "critic",
         "program": numeric_stance_program("s['cash']/s['burn']", {"cash": 1200000, "burn": 130000}, 0.75)},
        {"name": "chaos", "persona": "chaos",
         "program": qualitative_stance_program("do-not-hedge", 0.30)},
    ]
    rep = run_stances("size the emergency cash runway", stances)
    print(json.dumps({k: rep[k] for k in ("status", "counter", "merge", "confidence",
                                          "decision") if k in rep}, indent=2, ensure_ascii=False))
    if "restart" in rep:
        print("RESTART ->", json.dumps(rep["restart"], ensure_ascii=False))
