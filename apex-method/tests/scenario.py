#!/usr/bin/env python3
"""
scenario.py — end-to-end behavioral AUDIT harness for apex-method.

WHY: unit tests (benchmark.py) check each module in isolation. This drives the WHOLE skill through
realistic SCENARIOS the way a session would, MONITORS behaviour (mode routing, loop termination,
provider degradation, error paths, the parallel round, the durable stores), and REPORTS anomalies.
It is the "run while monitoring, capture errors, verify behaviour" loop — reproducible and committable.

RUN: python3 tests/scenario.py   (exit 0 = clean; exit 1 = anomalies found)
"""
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

SCENARIOS = []


def scenario(name):
    def deco(fn):
        SCENARIOS.append((name, fn))
        return fn
    return deco


# ── 1. ENTRY GATE: mode routing is sane and nothing raises ────────────────────────────────────
@scenario("entry_gate_routing")
def s_entry():
    import orchestrator as o
    cases = [
        ("What is 2+2?",                                   "EXPRESS",   None),
        ("list 3 fruits?",                                 "EXPRESS",   None),
        ("design a fault-tolerant payment API",            "FULL_PIPELINE", "DEEP"),
        ("solve navier stokes turbulência de fluido pde",  "FULL_PIPELINE", "SCIENTIFIC"),
        ("prove that sqrt(2) is irrational",               "FULL_PIPELINE", "SCIENTIFIC"),
    ]
    anomalies, observed = [], []
    for task, exp_path, exp_mode in cases:
        r = o.run(task)
        observed.append({"task": task[:32], "path": r.get("path"), "mode": r.get("mode")})
        if r.get("path") != exp_path:
            anomalies.append(f"'{task[:28]}' path={r.get('path')} expected {exp_path}")
        if exp_mode and r.get("mode") != exp_mode:
            anomalies.append(f"'{task[:28]}' mode={r.get('mode')} expected {exp_mode}")
    return {"observed": observed, "anomalies": anomalies}


# ── 2. ERROR PATHS: run NEVER raises; malformed input degrades safely ─────────────────────────
@scenario("error_handling")
def s_errors():
    import orchestrator as o
    anomalies, observed = [], []
    for bad in [None, "", "   ", 12345, {"x": 1}]:
        try:
            r = o.run(bad)
            observed.append({"input": repr(bad)[:20], "path": r.get("path"), "has_mode": "mode" in r})
            if "mode" not in r:
                anomalies.append(f"input {bad!r}: result missing 'mode'")
        except Exception as e:
            anomalies.append(f"input {bad!r}: RAISED {type(e).__name__} (run must never raise)")
    return {"observed": observed, "anomalies": anomalies}


# ── 3. LOOP TERMINATION: the guard always stops a runaway loop ─────────────────────────────────
@scenario("loop_termination")
def s_loop():
    import execution_policy as ep
    import llm_adapter as la
    anomalies = []
    lim = la.limits()
    # simulate a loop that never improves: it MUST stop by max_iterations or stagnation
    stopped_at = None
    progress = []
    for i in range(1, 50):
        progress.append(0.01)                        # flat -> no progress
        g = ep.loop_guard(i, progress_history=progress, restarts=0, reliability=0.6)
        if g["stop"]:
            stopped_at = i
            break
    if stopped_at is None:
        anomalies.append("loop NEVER stopped over 49 iterations (runaway)")
    elif stopped_at > lim["max_iterations"] + 1:
        anomalies.append(f"loop stopped late at {stopped_at} (cap {lim['max_iterations']})")
    # restart cap + early-exit
    if not ep.loop_guard(1, restarts=lim["max_restarts"] + 1)["stop"]:
        anomalies.append("restart cap not enforced")
    if not ep.loop_guard(1, reliability=0.1)["stop"]:
        anomalies.append("early-exit on low reliability not enforced")
    return {"observed": {"stopped_at_iteration": stopped_at, "limits": lim}, "anomalies": anomalies}


# ── 4. PROVIDER DEGRADATION: every provider yields a runnable plan ─────────────────────────────
@scenario("provider_degradation")
def s_providers():
    import llm_adapter as la
    anomalies, observed = [], []
    for prov in ("claude", "gpt", "gemini", "deepseek", "local", "unknown-xyz"):
        d = la.degrade(prov, "RESEARCH")
        observed.append({"provider": prov, "parallelism": d["parallelism"],
                         "mode": d["effective_mode"], "adjustments": len(d["adjustments"])})
        if d["parallelism"] not in ("A", "B"):
            anomalies.append(f"{prov}: bad parallelism {d['parallelism']}")
        if prov == "claude" and d["parallelism"] != "B":
            anomalies.append("claude should be Level B")
        if prov in ("gpt", "deepseek", "local") and d["parallelism"] != "A":
            anomalies.append(f"{prov} should degrade to Level A")
    return {"observed": observed, "anomalies": anomalies}


# ── 5. PARALLEL ROUND: evaluate_hypotheses + run_stances behave and terminate ─────────────────
@scenario("parallel_round")
def s_parallel():
    import concurrent_executor as ce
    for db in ("competence.db", "learning.db"):
        try:
            os.remove(os.path.expanduser(f"~/.apex-method/{db}"))
        except OSError:
            pass
    anomalies = []
    hyps = [{"stance": "optimistic", "answer": "A", "confidence": 0.78},
            {"stance": "neutral", "answer": "A", "confidence": 0.70},
            {"stance": "pessimistic", "answer": "B", "confidence": 0.55}]
    out = ce.evaluate_hypotheses("optimize the retry policy", hyps, mode="DEEP")
    if out.get("decision") not in ("ADOPT", "REVIEW", "REJECT"):
        anomalies.append(f"evaluate_hypotheses bad decision {out.get('decision')}")
    if not all(len(l.get("sha256", "")) == 64 for l in out.get("laudos", [])):
        anomalies.append("laudos not all SHA-256 hashed")
    # a stuck persona must ABORT (not loop)
    st = {"critic": {"rejections_streak": 25, "confidence_history": [0.75]}}
    r = ce.run_stances("refactor", [{"name": "s", "persona": "critic",
                                     "program": ce.qualitative_stance_program("X", 0.75)}],
                       mode="DEEP", agent_states=st)
    if not r.get("aborted"):
        anomalies.append("stuck persona did not abort")
    return {"observed": {"decision": out.get("decision"), "n_directors": out.get("n_directors"),
                         "aborted": len(r.get("aborted", []))}, "anomalies": anomalies}


# ── 6. DURABLE STORES: memory/KG + swap round-trip + learning promote/demote ───────────────────
@scenario("durable_stores")
def s_stores():
    import tempfile
    import memory as mem_mod
    import swap_store as ss
    import learning as lrn
    anomalies = []
    db = os.path.join(tempfile.mkdtemp(), "m.db")
    m = mem_mod.MemoryStore(db)
    a = m.remember("the retry budget must be bounded", "semantic")
    b = m.remember("unbounded retries cause a storm", "semantic")
    m.relate(a, b, "causa")
    if not m.recall_graph("retry", k=1, depth=1)["seeds"]:
        anomalies.append("recall_graph returned no seeds")
    # swap page-out / page-in integrity
    bundle = ss.export_bundle("sc", memory_db=db, snapshot={"objective": "audit"})
    if not ss.import_bundle(bundle, memory_db=os.path.join(tempfile.mkdtemp(), "m2.db"))["integrity_ok"]:
        anomalies.append("swap bundle integrity failed")
    # learning promote/demote
    ls = lrn.LearningStore(os.path.join(tempfile.mkdtemp(), "l.db"))
    for _ in range(3):
        rr = ls.record_outcome("persona", "architect", "engineering", True)
    if rr["status"] != "PROMOTED":
        anomalies.append(f"learning did not promote a repeatedly-successful persona ({rr['status']})")
    return {"observed": {"promoted": rr["status"], "stats": ls.stats()}, "anomalies": anomalies}


# ── 7. EXECUTION ROUTING: discovery never lands in the sandbox ────────────────────────────────
@scenario("execution_routing")
def s_routing():
    import execution_policy as ep
    anomalies = []
    for probe in ("compute the hash", "search skills.sh for a legal MCP", "download the latest repo",
                  "integrate the ODE", "buscar paper no arxiv"):
        r = ep.route(probe)
        if r["surface"] == "subprocess" and r["needs_internet"]:
            anomalies.append(f"'{probe}' routed discovery into the sandbox (HARD RULE broken)")
    plan = ep.dissect_entry("build a HIPAA-compliant billing pipeline")
    if "needs_internet=True is NEVER routed to the subprocess" not in plan.get("hard_rule", ""):
        anomalies.append("dissect_entry missing the hard-rule guarantee")
    return {"observed": {"micros": len(plan.get("micros", []))}, "anomalies": anomalies}


def main():
    print("=" * 78)
    print("APEX-METHOD END-TO-END BEHAVIORAL AUDIT")
    print("=" * 78)
    total_anomalies, ran = [], 0
    for name, fn in SCENARIOS:
        t0 = time.time()
        try:
            res = fn()
            ran += 1
            anom = res.get("anomalies", [])
            status = "CLEAN" if not anom else f"{len(anom)} ANOMALY"
            print(f"[{status:>10}] {name:22} {round((time.time()-t0)*1000):>5}ms")
            for a in anom:
                print(f"             ↳ {a}")
                total_anomalies.append(f"{name}: {a}")
        except Exception:
            print(f"[     ERROR] {name:22}")
            print("             ↳ " + traceback.format_exc().splitlines()[-1])
            total_anomalies.append(f"{name}: harness raised")
    print("-" * 78)
    print(f"scenarios: {ran}/{len(SCENARIOS)} ran | anomalies: {len(total_anomalies)}")
    print("VERDICT:", "ALL CLEAN ✅" if not total_anomalies else "ANOMALIES FOUND ❌")
    return 0 if not total_anomalies else 1


if __name__ == "__main__":
    sys.exit(main())
