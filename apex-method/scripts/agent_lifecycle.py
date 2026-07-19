#!/usr/bin/env python3
"""
agent_lifecycle.py — the CLOSED-LOOP agent pipeline: dissect → competence matrix → find-or-create
agent → validate/equip skills (discovery cascade) → executable spec → (host executes) → evolve.

WHY THIS EXISTS (the author's O-2 flow, made real):
  spawn() alone assembles ONE agent spec. It did not, by itself, drive the full loop the author
  described: dissect the problem, let the PMI/architect/chaos build a competence matrix (discipline
  → subdomain → specialization + tools/diffs), look for a real agent in the online repo, CREATE a
  generic one when none exists, validate whether the needed skills are already equipped, and if not
  search (native repo → skills.sh → GitHub) or FORGE a new skill for the agent to develop — then,
  after a validated run, update the vector-node RAG index and persist/evolve the agent + anchors so
  the prompt library grows. This module wires those existing pieces into that single loop.

THE 8 STEPS (mapped to modules, all pre-existing — this file only orchestrates them):
  1. dissect ................ orchestrator.dissect  (which disciplines the task touches)
  2. competence matrix ...... taxonomy.classify     (domain → subdomain → intent → specialties)
  3. tools & diffs .......... gravity.plan          (attract skills/scripts/diffs; flag gaps)
  4. find-or-create agent ... agent_registry.match_task_to_ext_agents + repo_bridge.agent;
                              if nothing clears the bar → agent_spawn.spawn(synthesize=True)
  5. validate/equip skills .. agent_spawn spec.skills + discovery cascade
                              (repo_bridge.search_native → skills_sh → GitHub) → skill_forge scaffold
  6. execute ................ HOST instantiates the Level-B subagent from spec.instruction
  7. update RAG ............. rag_index.sync  (re-vectorize only what changed)
  8. evolve agent+anchors ... learning.record_outcome + agent_registry.save_grant + memory anchor

BOUNDARIES / GATES (non-negotiable, mirrors the skill's philosophy):
  - Python cannot instantiate the LLM subagent NOR author a skill body: run() returns an
    EXECUTABLE plan; the host executes step 6 and the LLM fills the forged scaffold.
  - Nothing auto-installs or auto-equips: discovery/forge are STAGED and require H5 approval.
  - The library evolves ONLY on a validated success: finalize(validated=True) — otherwise it
    refuses (no reputation poisoning from an unvalidated run).

WHAT IF IT FAILS:
  Every step degrades independently (a missing engine → that step is skipped and reported); the
  loop never raises. skills.sh blocked by network policy → cascade reports OFFLINE and falls back
  to native + GitHub discovery.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Calibrated against the real roster: lexical match scores cluster in ~0.05–0.11 and a no-match
# returns [] (empty). So the strong "synthesize" signal is an EMPTY/near-zero match, not a high bar
# — 0.10 wrongly rejected correct agents (postgres-pro 0.095, data-engineer 0.078). 0.05 accepts a
# real-but-weak match and still synthesizes when the roster genuinely offers nothing.
MIN_ROSTER_SCORE = 0.05


# ── steps 1+2: the competence matrix ─────────────────────────────────────────
def competence_matrix(task):
    """Dissect the task into disciplines and reduce it to canonical facets
    (discipline → subdomain → specialization). This is the matrix the architect/chaos/PMI fill."""
    disciplines, facets = [], {}
    try:
        import orchestrator
        disciplines = orchestrator.dissect(task)
    except Exception:
        pass
    try:
        import taxonomy
        facets = taxonomy.classify(task)
    except Exception:
        pass
    # facets can be a set (taxonomy) — normalize to a sorted list so the matrix is JSON-serializable
    raw_facets = facets.get("facets", [])
    return {"task": task[:200], "disciplines": disciplines,
            "domain": facets.get("domain"), "subdomain": facets.get("subdomain"),
            "intent": facets.get("intent"), "specialties": list(facets.get("specialties", [])),
            "facets": sorted(raw_facets) if isinstance(raw_facets, (set, frozenset)) else list(raw_facets)}


# ── step 4: find a real agent (roster/online repo) or decide to synthesize one ─
def resolve_agent(task, matrix=None, min_score=MIN_ROSTER_SCORE):
    """Find the best real agent in the roster / online repo. If none clears `min_score`, decide to
    SYNTHESIZE a generic agent whose id encodes its facets (create-generic branch of the flow)."""
    matrix = matrix or competence_matrix(task)
    best = None
    try:
        import agent_registry
        matches = agent_registry.match_task_to_ext_agents(task, k=3)   # [(id, category, score), …]
        if matches:
            aid, cat, sc = matches[0]
            best = {"agent_id": aid, "category": cat, "score": sc}
    except Exception:
        pass
    if best and best["score"] >= min_score:
        source = "roster"
        try:                                    # confirm it is loadable from the online repo (data only)
            import repo_bridge
            r = repo_bridge.agent(best["agent_id"])
            if isinstance(r, dict) and r.get("status") == "OK":
                source = "repo"
        except Exception:
            pass
        return {"agent_id": best["agent_id"], "source": source, "score": best["score"],
                "synthesize": False, "matrix": matrix}
    # no adequate real agent → synthesize a generic id from the facets
    dom = matrix.get("domain") or (matrix.get("disciplines") or ["general"])[0]
    sub = matrix.get("subdomain")
    gid = "generic-" + "-".join(x for x in (dom, sub) if x)
    return {"agent_id": gid, "source": "synthesized", "score": (best or {}).get("score", 0.0),
            "synthesize": True, "matrix": matrix}


# ── step 5b: STAGE an LLM-authored skill scaffold (never written/adopted here) ─
def scaffold_skill(task, matrix=None):
    """Emit a CANDIDATE SKILL.md (as text, STAGED) reusing skill_forge's schema-valid template, for
    the LLM to author when discovery finds no existing skill. Never writes to disk, never adopts."""
    matrix = matrix or competence_matrix(task)
    dom = matrix.get("domain") or "engineering"
    sub = matrix.get("subdomain") or "general"
    spec_words = ", ".join(matrix.get("specialties", [])[:4]) or "the task"
    try:
        import skill_forge
        name = skill_forge.kebab(f"{dom}-{sub}-skill")
        desc = skill_forge.validate_desc(
            f"Capability for {dom}/{sub} synthesized on demand. Use when: {task[:120]}")
        content = skill_forge.TEMPLATE.format(
            name=name, display=f"{dom.title()} {sub.title()} Skill", kind="workflow",
            domain=dom, subtype=sub, description=desc,
            author="apex-method (agent_lifecycle scaffold)",
            today=__import__("datetime").date.today().isoformat())
    except Exception as e:
        return {"status": "SCAFFOLD_FAILED", "reason": str(e)[:80]}
    return {"status": "STAGED_CANDIDATE", "skill_id": name, "focus": spec_words,
            "skill_md": content,
            "adopt_gate": "LLM authors the body; user approves (H5); then skill_forge.promote → ADOPTED"}


# ── step 5: validate equipment, run the discovery cascade, stage a forge if empty ─
def plan_equipment(task, spec, matrix=None):
    """Validate whether the needed skills are already equipped. For gaps, run the discovery cascade
    native(repo) → skills.sh → GitHub. If nothing is found, STAGE a skill_forge scaffold. Nothing
    auto-installs (H5)."""
    equipped = list(spec.get("skills") or [])
    gaps, cascade = [], {}
    try:
        import gravity
        gp = gravity.plan(task)
        gaps = gp.get("gaps", [])
        cascade["install_requests"] = gp.get("install_requests", [])
        cascade["mcp_suggestions"] = gp.get("mcp_suggestions", [])
    except Exception:
        pass
    native = []
    try:                                        # native repo first (3,784 skills, offline-capable)
        import repo_bridge
        native = repo_bridge.search_native(task, k=3) or []
    except Exception:
        pass
    cascade["native"] = [n.get("id") for n in native][:3]
    sh = {"status": "SKIPPED"}
    try:                                        # skills.sh marketplace (may be OFFLINE by policy)
        import skills_sh
        sh = skills_sh.install_requests(task)
    except Exception:
        pass
    cascade["skills_sh"] = sh
    # forge only when the agent has NO equipment AND discovery found nothing installable
    sh_hit = isinstance(sh, dict) and sh.get("status") == "OK" and sh.get("requests")
    need_forge = not equipped and not cascade["native"] and not sh_hit
    forge = [scaffold_skill(task, matrix)] if need_forge else []
    return {"equipped": equipped, "gaps": gaps, "cascade": cascade, "forge_candidates": forge,
            "equip_gate": "discovery/forge are STAGED — explicit user approval (H5) before install/equip"}


# ── the loop, up to the executable spec (steps 1–5 + a directive for 6–8) ─────
def run(task, mode="DEEP", min_score=MIN_ROSTER_SCORE):
    """Drive the closed loop to an EXECUTABLE spec. The host then executes the subagent (step 6)
    and calls finalize(validated=…) to run steps 7–8. Returns the whole plan with explicit gates."""
    matrix = competence_matrix(task)
    decision = resolve_agent(task, matrix, min_score)
    import agent_spawn
    spec = agent_spawn.spawn(decision["agent_id"], task, mode=mode,
                             synthesize=decision["synthesize"])
    equipment = plan_equipment(task, spec, matrix)
    return {
        "task": task[:200], "matrix": matrix, "agent": decision, "spec": spec,
        "equipment": equipment,
        "status": spec.get("status"), "spawn_ready": spec.get("spawn_ready"),
        "next": {
            "6_execute": ("host: instantiate the Level-B subagent from spec['instruction'], then "
                          "call agent_lifecycle.finalize(task, agent_id, matrix, validated=<bool>, "
                          "equipped_skills=[…])"),
            "gates": ["equip/forge require H5 approval before install",
                      "finalize persists ONLY when validated=True"]},
    }


# ── learn from a FAILURE: demote + vaccinate (error → WHY), so the mistake is not repeated ─
def record_failure(task, agent_id, error, why, matrix=None):
    """A run that did NOT validate still TEACHES. This records the mistake into the DURABLE stores
    the swap carries: a DEMOTION (learning: this persona/skill under-performed for the domain) and
    a VACCINE (code_genetics: the exact error text + WHY it was wrong / the fix), plus a memory
    anchor. Next session, context_pack surfaces these as 'DEMOTED (do NOT default to)' and
    'LESSONS (validated error→fix)' so the same error is not committed again. This is the honest
    other half of finalize: the library learns from failures, not only successes."""
    matrix = matrix or competence_matrix(task)
    dom = matrix.get("domain") or (matrix.get("disciplines") or ["general"])[0]
    out = {"status": "LEARNED_FROM_FAILURE", "agent_id": agent_id, "domain": dom,
           "demoted": None, "vaccine": None, "anchor": None}
    try:                                        # learning: record the negative outcome for the domain
        import learning
        learning.record_outcome("persona", agent_id, dom, False, evidence=(error or "")[:120])
        out["demoted"] = learning.score("persona", agent_id, dom).get("status")
    except Exception as e:
        out["demoted"] = f"err:{str(e)[:40]}"
    try:                                        # vaccine: the ERROR and WHY, for future context
        import code_genetics
        code_genetics.durable_store().save_vaccine(error or "unspecified error",
                                                   why or "no root-cause recorded")
        out["vaccine"] = "SAVED"
    except Exception as e:
        out["vaccine"] = f"err:{str(e)[:40]}"
    try:                                        # memory anchor: the failure is durable + auditable
        import memory
        m = memory.MemoryStore()
        sha = m.remember(f"MISTAKE by '{agent_id}' in {dom}: {(error or '')[:100]} — WHY: "
                         f"{(why or '')[:100]}", kind="semantic")
        m.record_event("demote", agent_id, f"error in {dom}: {(error or '')[:60]}")
        out["anchor"] = sha[:12]
    except Exception as e:
        out["anchor"] = f"err:{str(e)[:40]}"
    return out


# ── steps 6–8 (post-validation): evolve the library, gated on a validated success ─
def finalize(task, agent_id, matrix=None, validated=False, equipped_skills=None,
             success_evidence=None, index_path=None, error=None, why=None):
    """After the host executes: on a VALIDATED success, record the outcome (learning), persist the
    agent's equipment durably (grants), drop a memory anchor, re-sync the vector-node RAG index, and
    (for a grown generic agent) MATERIALIZE it as a standardized specialist. On a FAILURE with an
    `error`/`why`, it does NOT evolve the library but DOES learn from the mistake (record_failure:
    demote + vaccine) so the swap carries what went wrong and why. No reputation poisoning: only a
    validated success promotes."""
    if not validated:
        if error:                               # unvalidated BUT we know what went wrong → learn it
            res = record_failure(task, agent_id, error, why, matrix=matrix)
            res["status"] = "SKIPPED_EVOLUTION_LEARNED_FAILURE"
            return res
        return {"status": "SKIPPED",
                "reason": "not validated — the library evolves only on a gated, validated success"}
    matrix = matrix or competence_matrix(task)
    dom = matrix.get("domain") or (matrix.get("disciplines") or ["general"])[0]
    out = {"status": "EVOLVED", "agent_id": agent_id, "domain": dom,
           "learning": None, "grants": 0, "anchor": None, "rag": None, "materialized": None}
    try:                                        # learning: the persona proved out for this domain
        import learning
        learning.record_outcome("persona", agent_id, dom, True,
                                evidence=success_evidence or "validated by host")
        out["learning"] = learning.score("persona", agent_id, dom).get("status")
    except Exception as e:
        out["learning"] = f"err:{str(e)[:40]}"
    try:                                        # persist equipment durably = create/update the agent
        import agent_registry
        for sid in (equipped_skills or []):
            agent_registry.save_grant(sid, agent_id, source="agent_lifecycle", approved=True)
            out["grants"] += 1
    except Exception:
        pass
    try:                                        # memory anchor: evolve the durable prompt library
        import memory
        m = memory.MemoryStore()
        sha = m.remember(f"Agent '{agent_id}' validated for {dom}: {task[:120]}", kind="semantic")
        m.record_event("promote", agent_id, f"validated for {dom}")
        out["anchor"] = sha[:12]
    except Exception as e:
        out["anchor"] = f"err:{str(e)[:40]}"
    try:                                        # RAG re-sync: make the new agent/skill discoverable
        import rag_index
        r = rag_index.sync(index_path) if index_path else rag_index.sync()
        out["rag"] = r.get("status") if isinstance(r, dict) else "OK"
    except Exception as e:
        out["rag"] = f"err:{str(e)[:40]}"
    # v1.55: GROW THE TAXONOMY from this validated run — associate the task's salient terms with the
    # domain/subdomain that proved out, so future similar tasks classify correctly (the vocabulary
    # expands with experience). Durable overlay, loaded next session. Gated on validation (here).
    try:
        import taxonomy
        ev = taxonomy.evolve(task, domain=matrix.get("domain") or dom,
                             subdomain=matrix.get("subdomain"),
                             specialties=matrix.get("specialties"))
        out["taxonomy"] = {"status": ev.get("status"), "added_terms": ev.get("added_terms")}
    except Exception as e:
        out["taxonomy"] = f"err:{str(e)[:40]}"
    # v1.54: if this was a GROWN generic agent, crystallize it into a STANDARDIZED, discoverable
    # specialist (AGENT.md + SKILL.md in the repo layout) + register it in the roster overlay, so
    # NEXT session finds the specialist instead of re-synthesizing. Only for synthesized agents.
    if str(agent_id).startswith("generic-"):
        try:
            import agent_materializer
            m = agent_materializer.materialize(agent_id, matrix, validated=True,
                                               promoted_skills=equipped_skills,
                                               evidence=success_evidence)
            out["materialized"] = {"status": m.get("status"),
                                   "written": len(m.get("written", [])),
                                   "registered": (m.get("registered") or {}).get("status")}
        except Exception as e:
            out["materialized"] = f"err:{str(e)[:40]}"
    return out


if __name__ == "__main__":
    import json
    t = sys.argv[1] if len(sys.argv) > 1 else \
        "dimensione uma viga de concreto armado no estado limite último"
    plan = run(t)
    print(json.dumps({"agent": plan["agent"], "status": plan["status"],
                      "spawn_ready": plan["spawn_ready"],
                      "matrix": plan["matrix"],
                      "equipped": plan["equipment"]["equipped"],
                      "cascade": {k: (v if not isinstance(v, dict) else v.get("status", v))
                                  for k, v in plan["equipment"]["cascade"].items()},
                      "forge": [f["status"] for f in plan["equipment"]["forge_candidates"]]},
                     ensure_ascii=False, indent=1))
