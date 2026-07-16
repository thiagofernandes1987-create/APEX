#!/usr/bin/env python3
"""
deep_research.py — Goal-like iterative deep research over the APEX domain and its agents.

WHY THIS EXISTS:
  A "goal" in APEX terms is a research loop that runs in RESEARCH/SCIENTIFIC mode: dissect
  the question, route each part to the right APEX agent, resolve the knowledge each agent
  needs (from the 3,784 NATIVE skills, or by DISCOVERING new specialised ones on
  skills.sh/GitHub), reason, and iterate until progress stalls (stagnation) or reliability
  is high enough — instead of a single one-shot answer.

WHEN TO USE:
  Multi-part, high-stakes, or exploratory questions where the user wants the pipeline to
  keep working: `menu.py research "<question>" --source native|search|both`.

HOW IT WORKS (each round):
  1. dissect -> disciplines; each maps to the best of the 213 APEX agents (agent need).
  2. for each agent need, RESOLVE a skill per the source policy:
       native  -> repo_bridge.search_native (the APEX library)
       search  -> skills_sh (marketplace, installs>=bar) + GitHub URL  [STAGED, H5]
       both    -> native first, then marketplace to fill remaining gaps
  3. run the pipeline (orchestrator) and record a per-round reliability.
  4. progress check via apex_st_metric (dS2); stop on stagnation (2x FLAT) or when
     R_acum over the rounds clears the target, or when max_rounds is hit.

SAFETY: discovery only STAGES skills with `npx skills add` for the user to approve (H5).
  Nothing installs or executes automatically.

WHAT IF IT FAILS:
  offline -> marketplace steps degrade to ready-to-run commands; the loop still runs on the
  native library. Any engine missing is skipped and noted, never crashes the loop.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import config as _config


def _agents_for(discipline_task):
    try:
        import agent_registry
        return agent_registry.match_task_to_ext_agents(discipline_task, k=2)
    except Exception:
        return []


def _resolve_native(need, k=3):
    try:
        import repo_bridge
        return [{"id": h["id"], "path": h["path"], "via": "native", "score": h.get("score", 0)}
                for h in repo_bridge.search_native(need, k=k)]
    except Exception:
        return []


def _resolve_marketplace(need, min_installs):
    try:
        import skills_sh
        r = skills_sh.install_requests(need, min_installs=min_installs, k=3)
        return r.get("requests", [])
    except Exception:
        return []


def _hit_quality(hit):
    """Honest per-hit strength: a native hit is scored by its search score (capped),
    a marketplace hit with real install data is strong, an offline STAGED command is weak."""
    if hit.get("via") == "native":
        return min(1.0, (hit.get("score", 0) or 0) / 6.0)   # native scores ~0..12
    if hit.get("installs"):
        return 0.9
    return 0.55   # STAGED discovery command (offline / not yet installed)


def _round_reliability(disciplines, resolved):
    """Per-round reliability = coverage x quality. A discipline counts as covered only if
    it has a hit; quality reflects HOW strong the best hit is (so weak coverage keeps the
    loop iterating instead of declaring victory on a marginal match)."""
    if not disciplines:
        return 0.5
    total = 0.0
    for d in disciplines:
        skills = resolved.get(d, {}).get("skills", []) if isinstance(resolved.get(d), dict) else resolved.get(d)
        best = max((_hit_quality(h) for h in (skills or [])), default=0.0)
        total += best
    coverage_quality = total / len(disciplines)
    return round(0.4 + 0.6 * coverage_quality, 3)


def research(question, source=None, mode=None, max_rounds=4, p_target=0.9):
    """Run the goal-like deep-research loop. source: native|search|both (else config)."""
    cfg = _config.load()
    source = source or cfg.get("discovery_source", "both")
    min_installs = cfg.get("min_installs", 1000)
    # honour the user's preferred mode; force RESEARCH/SCIENTIFIC family for deep work
    mode = (mode or cfg.get("default_mode") or "RESEARCH").upper()
    if mode not in ("RESEARCH", "SCIENTIFIC"):
        mode = "RESEARCH"

    import orchestrator
    try:
        import snapshot as snap_mod
        snap = snap_mod.new_snapshot(question, mode)
    except Exception:
        snap, snap_mod = None, None

    rounds, reliabilities, prev_curv = [], [], None
    for rnd in range(1, max_rounds + 1):
        disciplines = orchestrator.dissect(question)
        resolved, staged = {}, []
        for d in disciplines:
            need = f"{question} {d}"
            agents = _agents_for(need)
            hits = []
            if source in ("native", "both"):
                hits += _resolve_native(need)
            if source in ("search", "both") and (source == "search" or not hits):
                mkt = _resolve_marketplace(need, min_installs)
                staged += mkt
                hits += [{"id": r.get("skill") or r.get("gap"), "via": "marketplace",
                          "installs": r.get("installs"), "command": r.get("install_command")}
                         for r in mkt]
            resolved[d] = {"agents": [a[0] for a in agents], "skills": hits[:3]}
        rel = _round_reliability(disciplines, resolved)
        reliabilities.append(rel)
        rounds.append({"round": rnd, "disciplines": disciplines, "resolved": resolved,
                       "staged_installs": staged, "reliability": rel})

        # progress / stagnation via apex_st_metric
        curv = None
        try:
            import apex_st_metric
            prev = {"mcfe": reliabilities[-2]} if len(reliabilities) >= 2 else None
            st = apex_st_metric.compute_apex_st(
                {"mcfe": reliabilities[-2], "prev_curvature": prev_curv} if prev else None,
                {"mcfe": rel})
            curv = st["curvature"]
        except Exception:
            pass

        # stopping rules
        try:
            import bayes
            racum = bayes.r_acum(reliabilities)
        except Exception:
            racum = {"r_acum": rel, "status": "OK"}
        if snap_mod is not None:
            snap["milestones"].append(f"round {rnd}: {disciplines} rel={rel} curv={curv}")
        if rel >= p_target:
            return _finish(question, mode, source, rounds, reliabilities, racum,
                           "TARGET_REACHED", snap, snap_mod)
        if prev_curv == "FLAT" and curv == "FLAT":
            return _finish(question, mode, source, rounds, reliabilities, racum,
                           "STAGNATION", snap, snap_mod)
        prev_curv = curv
    try:
        import bayes
        racum = bayes.r_acum(reliabilities)
    except Exception:
        racum = {"r_acum": reliabilities[-1] if reliabilities else 0.5, "status": "OK"}
    return _finish(question, mode, source, rounds, reliabilities, racum,
                   "MAX_ROUNDS", snap, snap_mod)


def _finish(question, mode, source, rounds, reliabilities, racum, stop, snap, snap_mod):
    staged = [s for r in rounds for s in r.get("staged_installs", [])]
    if snap_mod is not None and snap is not None:
        for s in staged:
            snap["skills_staged"].append({"id": s.get("skill") or s.get("gap"),
                                          "status": "STAGED", "use_when": question[:60]})
    return {
        "question": question, "mode": mode, "source": source,
        "rounds_run": len(rounds), "stop_reason": stop,
        "reliability_trace": reliabilities, "r_acum": racum,
        "rounds": rounds,
        "staged_installs": staged,   # require user approval before `npx skills add` (H5)
        "snapshot": (snap_mod.to_context_block(snap) if snap_mod and snap else None),
    }


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = "both"
    for a in sys.argv[1:]:
        if a.startswith("--source="):
            src = a.split("=", 1)[1]
    q = " ".join(args) or "audit and optimize the APEX reasoning pipeline"
    out = research(q, source=src)
    print(f"QUESTION: {out['question']}\nMODE: {out['mode']} | SOURCE: {out['source']} | "
          f"STOP: {out['stop_reason']} after {out['rounds_run']} rounds")
    print(f"reliability trace: {out['reliability_trace']} | R_acum: {out['r_acum']['status']}")
    print(f"staged installs (need approval): {len(out['staged_installs'])}")
    for r in out["rounds"]:
        print(f"  round {r['round']}: {r['disciplines']} -> "
              f"{ {d: [s['id'] for s in v['skills']] for d, v in r['resolved'].items()} }")
