#!/usr/bin/env python3
"""
agent_spawn.py — the SPAWN CONTRACT: turn a roster persona into a fully-equipped, executable
agent spec (RT-19/RT-27, the author's design).

WHY THIS EXISTS:
  The 213-entry roster is deliberately LEAN metadata — the differentiator is not shipping
  thousands of prompts, it is spawning GENERIC agents that, at creation time, ASSUME a real
  persona and ATTRACT their specialization: real skills, real diffs, real scripts, governance,
  and an output template. Abilities can be EQUIPPED (promoted) and UNEQUIPPED (revoked) and the
  configuration persists in the durable grant store — so the library and the memory of what each
  agent equipped stay correlated, and every spawn produces a specialized agent with specialized
  tools. This module is that assembly line: spawn(agent_id, task) returns the complete,
  executable AgentSpec the LLM host uses to instantiate a real subagent (Level B).

WHEN TO USE:
  - spawn(agent_id, task, mode, stance): before fanning out ANY Level-B subagent — the
    concurrent_executor manifest now calls this so every entry carries a real persona + real
    equipment, not just a one-line instruction.
  - equip(agent_id, skill)/unequip(agent_id, skill_id): promote/demote an ability durably
    (approval gate H5 still applies to external skills before equip).
  - spawn_contract(): the guideline/contract text for HOW to spawn (the RT-19 directive).

WHAT IT IS NOT:
  Python cannot instantiate an LLM subagent. The spec is EXECUTABLE BY THE HOST: it contains
  everything needed (system prompt, tools, skills, diffs, scripts, template, governance, output
  schema, checklist) — the host's Agent tool does the spawning. That boundary is explicit.

WHAT IF IT FAILS:
  Unknown agent id -> a generic spec flagged persona_loaded=False (the checklist gate catches
  it). Missing engines (graph/learning/repo_bridge) degrade to lighter equipment, never raise.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)

OUTPUT_SCHEMA = ('{"stance": "<stance>", "answer": <answer>, "confidence": 0..1, '
                 '"rationale": "1-2 sentences", "needs": ["optional: missing skill/tool"]}')


def _roster_entry(agent_id):
    try:
        import agent_registry
        for a in agent_registry.load_ext_roster():
            if a.get("id") == agent_id:
                return a
    except Exception:
        pass
    return None


def _core_entry(agent_id):
    try:
        import agent_registry
        doc = agent_registry.load(agent_registry.AGENTS)
        return doc["agents"].get(agent_id)
    except Exception:
        return None


def _persona_md(agent_id, max_chars=1200):
    """Full AGENT.md from the repo when reachable (local clone or allowlisted raw). Data only."""
    try:
        import repo_bridge
        r = repo_bridge.agent(agent_id)
        if r.get("status") == "OK":
            return r["text"][:max_chars]
    except Exception:
        pass
    return None


def _equipped_grants(agent_id):
    """Durable equipment: approved, non-revoked grants for this agent (core or extended)."""
    try:
        import agent_registry
        equipped = []
        for g in agent_registry.load_grants():          # in order: later revocations unequip
            if not g.get("approved"):
                continue
            sid, aid = g.get("skill_id"), g.get("agent_id")
            if g.get("revoked"):
                if aid is None or aid == agent_id:
                    equipped = [e for e in equipped if e != sid]
                continue
            if aid == agent_id and sid and sid not in equipped:
                equipped.append(sid)
        return equipped
    except Exception:
        return []


def spawn(agent_id, task, mode="DEEP", stance="neutral", budget=10):
    """Assemble the EXECUTABLE AgentSpec: persona real + skills/diffs/scripts reais (attracted
    via the precomputed graph + durable grants) + governance + template + output contract +
    a boolean spawn checklist. The host instantiates it as a real subagent (Level B)."""
    roster = _roster_entry(agent_id)
    core = _core_entry(agent_id)
    domains = (roster or {}).get("domains", []) or \
              (core or {}).get("specialization", {}).get("domains", [])
    personality = (core or {}).get("personality") or _persona_md(agent_id) or \
                  (f"Specialist persona '{agent_id}'"
                   f" ({(roster or {}).get('category', 'general')}): expert in "
                   f"{', '.join(domains) or 'the task domain'}." if roster else None)

    # ── attraction: the graph equips without re-discovery; grants overlay durably ──
    equipment = {"by_type": {}, "members": []}
    try:
        import attraction_graph
        equipment = attraction_graph.equip_for(f"{task} {' '.join(domains)}", budget=budget)
    except Exception:
        pass
    grants = _equipped_grants(agent_id)

    # ── cross-session history: is this persona proven (or demoted) for this domain? ──
    history = None
    try:
        import learning
        dom = domains[0] if domains else "general"
        history = learning.score("persona", agent_id, dom)
    except Exception:
        pass

    # ── governance + output template (nothing generic leaves a spawned agent) ──
    regulated, template = False, None
    try:
        import execution_policy as ep
        regulated = ep._is_regulated(task, domains[0] if domains else "")
        template = ep.TEMPLATES.get("report")
    except Exception:
        pass

    tools = (core or {}).get("tools", [])
    skills = equipment.get("by_type", {}).get("skill", [])
    diffs = equipment.get("by_type", {}).get("diff", [])
    scripts = equipment.get("by_type", {}).get("script", []) or [f"scripts/{t}" for t in tools]
    agents_nearby = [a for a in equipment.get("by_type", {}).get("agent", []) if a != agent_id]

    instruction = (
        f"You are the APEX '{agent_id}' agent (a REAL specialized instance, not a label).\n"
        f"PERSONA: {personality or 'generalist (persona file unavailable — say so in output)'}\n"
        f"TASK: {task[:200]}\nSTANCE: argue the **{stance}** hypothesis; be concrete.\n"
        f"EQUIPPED SKILLS: {', '.join(skills) or '—'}\n"
        f"EQUIPPED DIFF-RULES: {', '.join(diffs) or '—'}\n"
        f"EQUIPPED SCRIPTS (run, don't reimplement): {', '.join(scripts) or '—'}\n"
        f"DURABLE GRANTS (your promoted abilities): {', '.join(grants) or '—'}\n"
        + ("GOVERNANCE: this task is REGULATED — attach the region-specific rules "
           "(HIPAA/GDPR/LGPD/financial/legal) to every recommendation.\n" if regulated else "")
        + (f"OUTPUT TEMPLATE (never generic): sections {template}\n" if template else "")
        + f"Return ONE JSON object exactly: {OUTPUT_SCHEMA}")

    checklist = {
        "persona_loaded": bool(personality),
        "equipment_attached": bool(skills or scripts or diffs or tools),
        "grants_merged": True,                    # empty grants is a valid merged state
        "history_consulted": history is not None,
        "governance_checked": True,
        "template_attached": bool(template),
        "output_contract_set": True,
    }
    return {
        "agent_id": agent_id, "stance": stance, "mode": mode, "task": task[:200],
        "persona": personality, "domains": domains,
        "skills": skills, "diffs": diffs, "scripts": scripts, "tools": tools,
        "grants": grants, "collaborators": agents_nearby[:3],
        "history": history, "regulated": regulated, "template": template,
        "instruction": instruction, "output_schema": OUTPUT_SCHEMA,
        "spawn_checklist": checklist,
        "spawn_ready": all(checklist.values()),
    }


def equip(agent_id, skill, approved=True, scripts=None):
    """PROMOTE an ability durably (H5: only call with approved=True after the human gate).
    The grant survives reload — agent_registry.load() auto-merges it."""
    import agent_registry
    if not approved:
        return {"status": "BLOCKED", "reason": "skill not approved by user (APEX H5)"}
    sid = skill["id"] if isinstance(skill, dict) else str(skill)
    return agent_registry.save_grant(sid, agent_id, scripts=scripts,
                                     source=(skill.get("source", "") if isinstance(skill, dict) else ""),
                                     approved=True, ext=True)


def unequip(agent_id, skill_id):
    """DEMOTE/unequip an ability durably (revocation record; disappears on next load)."""
    import agent_registry
    return agent_registry.revoke_grant(skill_id, agent_id)


def spawn_contract():
    """The RT-19 directive: HOW a host must spawn (the contract, stated once, machine-readable)."""
    return {
        "contract": [
            "1. NEVER spawn from a bare name: call agent_spawn.spawn(agent_id, task, mode, stance) "
            "and use the returned spec — persona real, skills reais, diffs reais, scripts reais.",
            "2. Refuse to spawn when spawn_ready is False: fix the failing checklist item first "
            "(the boolean checklist says exactly what is missing).",
            "3. Instantiate each spec CONCURRENTLY as a real subagent; its system prompt is "
            "spec['instruction']; it must answer with spec['output_schema'] JSON only.",
            "4. Collect every JSON and feed them back via evaluate_hypotheses(..., "
            "subagent_hypotheses=[...]) — the barrier/merge/PMI adjudicates; no agent's answer "
            "is adopted alone.",
            "5. A spec that reports needs=[...] triggers the discovery cascade (native -> "
            "skills.sh -> GitHub) + H5 approval, then equip() — the agent LEARNS durably.",
        ],
        "equip": "agent_spawn.equip(agent_id, skill, approved=True)  # after H5",
        "unequip": "agent_spawn.unequip(agent_id, skill_id)",
    }


if __name__ == "__main__":
    aid = sys.argv[1] if len(sys.argv) > 1 else "tech-lead-orchestrator"
    task = " ".join(sys.argv[2:]) or "audit the backend code for security issues"
    spec = spawn(aid, task)
    print(json.dumps({k: spec[k] for k in ("agent_id", "domains", "skills", "diffs", "scripts",
                                           "grants", "spawn_ready", "spawn_checklist")},
                     indent=1, ensure_ascii=False))
    print("\nINSTRUCTION:\n" + spec["instruction"])
