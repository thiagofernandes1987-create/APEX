#!/usr/bin/env python3
"""
pipeline_dsm.py — the Design Structure Matrix of the runtime itself (the author's item 3):
map module coupling + the per-mode pipeline flow, and CUT token waste per execution mode.

WHY THIS EXISTS:
  DSM is one of APEX's own validation frameworks (references/validation.md) — but it was never
  turned on the runtime itself. This module does exactly that, honestly split in two:
    (a) MODULE DSM (static, exact): AST-parse the local imports of every scripts/*.py into a
        dependency matrix -> topological levels (what can load/run in parallel), cycles (design
        smells), and the highest fan-in modules (the load-bearing core).
    (b) MODE FLOW (estimated, [APPROX]): the kernel steps x the mode's token budget, ordered by
        geodesic_scheduler (max ΔH/token) -> which steps each mode should RUN vs SKIP, and the
        estimated savings vs running everything. Step costs are calibrated estimates, not
        measurements — they are labeled as such.
  The one optimization APPLIED in code (not just reported): context_budget(mode) — the
  context_pack injection is sized per mode (EXPRESS gets zero, RESEARCH gets the most), so
  experience enrichment never becomes token waste on cheap paths.

WHEN TO USE:
  build() after structural changes (new modules / new kernel steps); context_budget(mode) is
  consumed by orchestrator.run and agent_spawn.spawn on every call.

WHAT IF IT FAILS:
  Pure stdlib + sibling engines. An unparseable script is skipped; a missing geodesic engine
  degrades to the fixed step order. Never raises on normal input.
"""
import ast
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
DSM_PATH = os.path.join(ROOT, "catalog", "pipeline_dsm.json")

# per-mode context injection budget (chars ~ 4*tokens). THE applied optimization: cheap modes
# must not pay for experience enrichment they can't use.
CONTEXT_BUDGET_CHARS = {"EXPRESS": 0, "STANDARD": 500, "FOGGY": 900,
                        "DEEP": 1300, "SCIENTIFIC": 1600, "RESEARCH": 2000}

# mode token budgets (SKILL.md §1.1) and [APPROX] per-step costs/values for the geodesic pass
MODE_TOKENS = {"EXPRESS": 400, "STANDARD": 2000, "FOGGY": 5500,
               "DEEP": 8000, "SCIENTIFIC": 12000, "RESEARCH": 16000}
STEP_EST = [  # (kernel step, delta_h [APPROX], tokens [APPROX])
    ("TRIAGE", 0.30, 60), ("DISSECT", 0.25, 80), ("RESOLVE_SPECIALISTS", 0.30, 250),
    ("MODE", 0.10, 20), ("PHASE_PLAN", 0.15, 60), ("CONTEXT_PACK", 0.35, 350),
    ("SPAWN_AGENTS", 0.45, 900), ("RUN_STANCES", 0.50, 1500), ("BARRIER_MERGE", 0.40, 600),
    ("VERIFY", 0.45, 800), ("PMI_CONVERGE", 0.35, 250), ("SNAPSHOT", 0.20, 200),
    ("PAGE_OUT", 0.15, 150),
]


def context_budget(mode):
    """Chars of validated-experience context a mode may inject (0 for EXPRESS — applied waste cut)."""
    return CONTEXT_BUDGET_CHARS.get((mode or "STANDARD").upper(), 900)


def import_graph():
    """Exact local-import adjacency of the 44+ scripts (who depends on whom)."""
    sdir = os.path.join(ROOT, "scripts")
    mods = {f[:-3] for f in os.listdir(sdir) if f.endswith(".py")}
    deps = {}
    for m in sorted(mods):
        try:
            tree = ast.parse(open(os.path.join(sdir, m + ".py"), encoding="utf-8",
                                  errors="replace").read())
        except Exception:
            deps[m] = []
            continue
        found = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                found |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                found.add(n.module.split(".")[0])
        deps[m] = sorted((found & mods) - {m})
    return deps


def _cycles(deps):
    """Import cycles (A needs B needs A) — coupling smells the DSM must surface."""
    cycles, seen_pairs = [], set()
    for a, ds in deps.items():
        for b in ds:
            if a in deps.get(b, []) and (b, a) not in seen_pairs:
                cycles.append([a, b])
                seen_pairs.add((a, b))
    return cycles


def module_dsm():
    """Topological levels (parallel batches), cycles, and the load-bearing core (fan-in)."""
    deps = import_graph()
    fan_in = {m: 0 for m in deps}
    for ds in deps.values():
        for d in ds:
            fan_in[d] = fan_in.get(d, 0) + 1
    cyc = _cycles(deps)
    cyc_members = {m for pair in cyc for m in pair}
    remaining = set(deps)
    levels = []
    while remaining:
        ready = sorted(m for m in remaining
                       if all(d not in remaining or d in cyc_members for d in deps[m]))
        if not ready:                          # only cycles left — emit and stop
            levels.append(sorted(remaining))
            break
        levels.append(ready)
        remaining -= set(ready)
    core = sorted(fan_in.items(), key=lambda kv: -kv[1])[:8]
    return {"modules": len(deps), "deps": deps, "levels": levels, "cycles": cyc,
            "load_bearing": [{"module": m, "fan_in": n} for m, n in core if n > 0]}


def mode_flow():
    """Per mode: the geodesic-ordered step plan under the mode's token budget — which steps
    run, which are skipped as low value-per-token, and the savings vs run-everything.

    v1.47 (OPP-99): when token_tracker has enough REAL samples for a step (>=3 rounds), the
    MEASURED average replaces the [APPROX] estimate — the flow optimizes on this machine's
    actual usage. `calibration` says which steps are measured vs estimated."""
    measured = {}
    try:
        import token_tracker
        measured = token_tracker.averages()
    except Exception:
        pass
    est = [(s, dh, measured[s]["avg"] if s in measured else tk) for s, dh, tk in STEP_EST]
    calibration = {s: ("measured" if s in measured else "estimated") for s, _dh, _tk in STEP_EST}
    flows = {"_calibration": calibration}
    naive_cost = sum(t for _, _, t in est)
    for mode, budget in MODE_TOKENS.items():
        steps = [{"id": s, "delta_h": dh, "tokens": tk} for s, dh, tk in est]
        # mode-specific pruning facts: EXPRESS answers directly; light modes skip heavy fan-out
        if mode == "EXPRESS":
            flows[mode] = {"plan": ["TRIAGE"], "skipped": [s["id"] for s in steps[1:]],
                           "tokens_est": 60, "savings_vs_naive": naive_cost - 60,
                           "context_budget_chars": context_budget(mode),
                           "note": "trivial path: triage answers directly (token economy)"}
            continue
        try:
            import geodesic_scheduler as gs
            r = gs.evaluate_steps(steps, token_budget=budget)
            flows[mode] = {"plan": r["plan"], "skipped": r["skipped"],
                           "tokens_est": r["tokens"], "savings_vs_naive": naive_cost - r["tokens"]}
        except Exception:
            flows[mode] = {"plan": [s["id"] for s in steps], "skipped": [],
                           "tokens_est": naive_cost, "savings_vs_naive": 0,
                           "note": "geodesic unavailable — fixed order fallback"}
        flows[mode]["context_budget_chars"] = context_budget(mode)
    return flows


def build(path=DSM_PATH):
    doc = {"_meta": {"note": ("DSM of the runtime: (a) EXACT module-import matrix -> parallel "
                              "load levels, cycles, load-bearing core; (b) [APPROX] per-mode "
                              "step flow via geodesic ΔH/token -> run/skip + savings. The "
                              "applied optimization is context_budget(mode): experience "
                              "injection sized per mode, zero on EXPRESS.")},
           "module_dsm": module_dsm(), "mode_flow": mode_flow(),
           "context_budget_chars": CONTEXT_BUDGET_CHARS}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    d = doc["module_dsm"]
    return {"status": "OK", "path": path, "modules": d["modules"],
            "levels": len(d["levels"]), "cycles": d["cycles"],
            "load_bearing": d["load_bearing"][:3]}


if __name__ == "__main__":
    r = build()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    doc = json.load(open(DSM_PATH, encoding="utf-8"))
    print("\nMODE FLOW (run/skip + savings; calibration:",
          doc["mode_flow"].get("_calibration", {}), "):")
    for mode, f in doc["mode_flow"].items():
        if mode.startswith("_"):
            continue
        print(f"  {mode:10} ctx={f['context_budget_chars']:>4}ch  run={len(f['plan'])} "
              f"skip={len(f['skipped'])} est={f['tokens_est']}tk save~{f['savings_vs_naive']}tk")
