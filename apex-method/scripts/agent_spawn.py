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


def context_pack(task, agent_id=None, budget_chars=1800):
    """EXPERIENCE -> CONTEXT (the author's thesis: context beats prompt). Assemble a bounded,
    provenance-carrying briefing from everything the runtime LEARNED, so a future window/agent
    never starts cold:
      - vaccines (code_genetics durable store): past error->fix lessons relevant to this task;
      - validated memory (memory.recall): facts with what/where/how provenance;
      - learning: which personas/skills PROVED OUT (and which were demoted — the don'ts);
      - rag_index nodes: where to read more (pointers, not dumps).
    Everything here passed a gate (promotion/dedup/ledger) — it is validated experience, not
    chat history. Returns {sections, rendered} with `rendered` capped at budget_chars."""
    sections = {"vaccines": [], "memories": [], "proven": [], "demoted": [], "nodes": []}
    try:
        import code_genetics
        sections["vaccines"] = [
            {"lesson": v.get("error", ""), "fix": v["fix"],
             "proof": f"{v['successes']}/{v['uses']} uses"}
            for v in code_genetics.durable_store().relevant(task, k=3)]
    except Exception:
        pass
    try:
        import memory
        sections["memories"] = [{"fact": r["text"][:160], "score": r["score"]}
                                for r in memory.MemoryStore().recall(task, k=3)]
    except Exception:
        pass
    try:
        import learning
        dom = "general"
        try:
            import orchestrator
            disc = orchestrator.dissect(task)
            dom = disc[0] if disc else "general"
        except Exception:
            pass
        sections["proven"] = learning.best("persona", dom, k=3)
        allb = learning.best("persona", dom, k=10, include_demoted=True)
        sections["demoted"] = [b for b in allb if b["status"] == "DEMOTED"][:3]
    except Exception:
        pass
    try:
        import rag_index
        sections["nodes"] = rag_index.search(task, k=3)
    except Exception:
        pass
    lines = []
    if sections["vaccines"]:
        lines.append("LESSONS (validated error->fix vaccines):")
        lines += [f"- {v['lesson'][:90]} -> {v['fix'][:90]} [{v['proof']}]" for v in sections["vaccines"]]
    if sections["memories"]:
        lines.append("VALIDATED MEMORY (durable, deduped):")
        lines += [f"- {m['fact']}" for m in sections["memories"]]
    if sections["proven"]:
        lines.append("PROVEN for this domain (cross-session, beta-binomial): "
                     + ", ".join(f"{b['subject']} ({b['mean']:.2f}, n={b['n']})" for b in sections["proven"]))
    if sections["demoted"]:
        lines.append("DEMOTED (do NOT default to): "
                     + ", ".join(b["subject"] for b in sections["demoted"]))
    if sections["nodes"]:
        lines.append("READ MORE (rag nodes): "
                     + "; ".join(f"{n['id']} -> {n['path']}" for n in sections["nodes"]))
    rendered = "\n".join(lines)[:budget_chars]
    return {"sections": sections, "rendered": rendered, "chars": len(rendered)}


def _synthesize_persona(agent_id, task, domains):
    """O-2 fix (v1.53.0): when NO roster/repo persona exists, SYNTHESIZE a generic-but-specialized
    persona from the task's canonical facets (taxonomy) instead of soft-blocking. This is the
    author's stated design — "spawning GENERIC agents that ASSUME a real persona and ATTRACT their
    specialization". The agent still equips real skills/scripts by attraction; it just was not
    pre-authored in the 213-entry roster. The persona is HONEST about being synthesized."""
    facets = {}
    try:
        import taxonomy
        facets = taxonomy.classify(task)
    except Exception:
        pass
    dom = facets.get("domain") or (domains[0] if domains else None) or "general"
    sub = facets.get("subdomain")
    spec = facets.get("specialties") or []
    where = f"{dom}/{sub}" if sub else dom
    focus = ", ".join(spec[:5]) or "the task domain"
    return (f"Generic APEX agent synthesized for {where} (no roster persona existed). "
            f"Assume a specialist in {focus}; equip real skills/scripts by attraction and state "
            f"in the output that this persona was synthesized, not pre-authored.")


def spawn(agent_id, task, mode="DEEP", stance="neutral", budget=10, shared=None,
          synthesize=False):
    """Assemble the EXECUTABLE AgentSpec: persona real + skills/diffs/scripts reais (attracted
    via the precomputed graph + durable grants) + governance + template + output contract +
    a boolean spawn checklist. The host instantiates it as a real subagent (Level B).

    synthesize (O-2, v1.53.0): when the agent_id is UNKNOWN (not in roster/repo), default False
    keeps the historical soft-block (persona=None, spawn_ready=False, status BLOCKED_UNKNOWN_AGENT).
    Pass synthesize=True (agent_lifecycle does) to instead SYNTHESIZE a generic persona from the
    task's taxonomy so the generic agent can become spawn_ready once equipped."""
    roster = _roster_entry(agent_id)
    core = _core_entry(agent_id)
    domains = (roster or {}).get("domains", []) or \
              (core or {}).get("specialization", {}).get("domains", [])
    personality = (core or {}).get("personality") or _persona_md(agent_id) or \
                  (f"Specialist persona '{agent_id}'"
                   f" ({(roster or {}).get('category', 'general')}): expert in "
                   f"{', '.join(domains) or 'the task domain'}." if roster else None)
    synthesized = False
    if personality is None and synthesize:
        personality = _synthesize_persona(agent_id, task, domains)
        synthesized = True

    # ── attraction: the graph equips without re-discovery; grants overlay durably ──
    equipment = {"by_type": {}, "members": []}
    try:
        import attraction_graph
        # AUDIT FIX (v1.52.0, USER-A): seed equipment from the TASK, not task+domains.
        # The persona's generic domain words ('system_design', 'architecture', 'quality')
        # are ambiguous and pulled unrelated VISUAL-design skills onto code-audit agents.
        # Domains pass as `bias` (light re-rank / short-task fallback only), never as seed.
        equipment = attraction_graph.equip_for(task, budget=budget, bias=" ".join(domains))
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

    # v1.44 — the author's thesis: context beats prompt. Every spawned agent receives the
    # runtime's VALIDATED experience (vaccines, memory, proven/demoted, rag pointers) inline.
    # v1.49 dogfooding fix: `shared` deduplica o trabalho POR TAREFA num fan-out — o exercício
    # instrumentado provou que os 5 framings de um manifesto produziam contextos IDÊNTICOS
    # (1 distinto em 5) e rotinas de conteúdo igual: context_pack 5x, compose 5x, ~956ms à toa.
    # O chamador (subagent_manifest) computa uma vez e compartilha; sem `shared`, tudo igual.
    shared = shared or {}
    ctx = {"rendered": "", "sections": {}}
    if shared.get("context") is not None:
        ctx = shared["context"]
    else:
        try:
            cbudget = 1200
            try:                                # DSM optimization: context sized per mode
                import pipeline_dsm
                cbudget = pipeline_dsm.context_budget(mode)
            except Exception:
                pass
            if cbudget > 0:
                ctx = context_pack(task, agent_id, budget_chars=cbudget)
        except Exception:
            pass

    # v1.46 — a ROTINA da persona: o fluxo encadeado de capacidades complementares (o que
    # enviar, o que receber, para onde alimenta). Reutiliza uma rotina COMPROVADA quando há;
    # senão compõe uma nova. A persona sabe COMO trabalhar, não só com o quê.
    routine = shared.get("routine")
    if routine is None:
        try:
            import routine_composer as rc
            routine = rc.best_routine(agent_id, task) or rc.compose(task, agent_id=agent_id)
        except Exception:
            pass
    routine_txt = ""
    if routine and routine.get("steps"):
        lines = [f"  {s['order']}. [{s['stage']}] {s['capability']} — envia: {s['send'][:70]} | "
                 f"recebe: {s['receive'][:70]}" for s in routine["steps"][:7]]
        if routine.get("gaps"):
            lines.append(f"  GAPS (descubra + H5 antes): {[g['stage'] for g in routine['gaps']]}")
        routine_txt = "ROUTINE (execute IN ORDER; each receive feeds the next send):\n" + "\n".join(lines) + "\n"

    # O-2 fix: the leading line must NOT claim "a REAL specialized instance" when the persona is
    # synthesized or unresolved — that fabricated authority is exactly the soft-gate risk the audit
    # flagged. Tell the truth in all three states.
    if synthesized:
        head = (f"You are a SYNTHESIZED APEX '{agent_id}' agent (generic persona assumed for this "
                f"task — NOT a pre-authored roster persona; say so in your output).\n")
    elif personality:
        head = f"You are the APEX '{agent_id}' agent (a REAL specialized instance, not a label).\n"
    else:
        head = (f"You are an UNRESOLVED APEX '{agent_id}' agent (no persona was found — do not "
                f"claim expertise; flag this and ask to synthesize or pick a real agent).\n")
    instruction = (
        head +
        f"PERSONA: {personality or 'generalist (persona file unavailable — say so in output)'}\n"
        f"TASK: {task[:200]}\nSTANCE: argue the **{stance}** hypothesis; be concrete.\n"
        f"EQUIPPED SKILLS: {', '.join(skills) or '—'}\n"
        f"EQUIPPED DIFF-RULES: {', '.join(diffs) or '—'}\n"
        f"EQUIPPED SCRIPTS (run, don't reimplement): {', '.join(scripts) or '—'}\n"
        f"DURABLE GRANTS (your promoted abilities): {', '.join(grants) or '—'}\n"
        + ("GOVERNANCE: this task is REGULATED — attach the region-specific rules "
           "(HIPAA/GDPR/LGPD/financial/legal) to every recommendation.\n" if regulated else "")
        + (f"OUTPUT TEMPLATE (never generic): sections {template}\n" if template else "")
        + (f"CONTEXT (validated experience — use it, don't rediscover):\n{ctx['rendered']}\n"
           if ctx.get("rendered") else "")
        + routine_txt
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
    ready = all(checklist.values())
    # O-2: an explicit top-level status so a caller is never forced to infer the gate from a
    # missing key (the audit's soft-gate finding). BLOCKED_UNKNOWN_AGENT is the honest signal for
    # an unknown agent that was not synthesized.
    if ready:
        status = "READY"
    elif synthesized:
        status = "SYNTHESIZED"            # generic persona assumed; may still be under-equipped
    elif personality is None:
        status = "BLOCKED_UNKNOWN_AGENT"  # unknown id, synthesize=False -> historical soft-block
    else:
        status = "INCOMPLETE"             # real persona but a checklist item failed
    return {
        "agent_id": agent_id, "stance": stance, "mode": mode, "task": task[:200],
        "persona": personality, "domains": domains, "synthesized": synthesized,
        "status": status,
        "skills": skills, "diffs": diffs, "scripts": scripts, "tools": tools,
        "grants": grants, "collaborators": agents_nearby[:3],
        "history": history, "regulated": regulated, "template": template,
        "context": ctx, "routine": routine, "instruction": instruction,
        "output_schema": OUTPUT_SCHEMA,
        "spawn_checklist": checklist,
        "spawn_ready": ready,
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


# ── the AGENT BUNDLE: a trained agent as a portable, verifiable artifact ─────────────────────
AGENT_BUNDLE_SCHEMA = "agent/1.0"


def _agent_sha(bundle):
    import hashlib
    unsigned = {k: v for k, v in bundle.items() if k != "sha256"}
    return hashlib.sha256(json.dumps(unsigned, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def export_agent(agent_id, path=None):
    """Serialize a TRAINED agent as a portable artifact: persona + equipped grants + validated
    learning history + attraction edges + ledger provenance, SHA-256 signed. Share/install it
    like a skill — except it arrives TRAINED and keeps learning (the product leap: agents as
    versioned, evolving artifacts; nobody ships verifiable track record with a persona)."""
    import time
    learning_rows = []
    try:
        import learning, sqlite3
        s = learning.LearningStore()
        con = sqlite3.connect(s.db_path)
        for r in con.execute("SELECT sha,kind,subject,domain,successes,trials,status,mean,updated "
                             "FROM outcomes WHERE subject=?", (agent_id,)):
            learning_rows.append(dict(zip(("sha", "kind", "subject", "domain", "successes",
                                           "trials", "status", "mean", "updated"), r)))
        con.close()
    except Exception:
        pass
    edges = []
    try:
        import attraction_graph
        edges = attraction_graph.neighbors(f"agent:{agent_id}", k=8)
    except Exception:
        pass
    provenance = []
    try:
        import memory, sqlite3
        con = sqlite3.connect(memory.DB_DEFAULT)
        for r in con.execute("SELECT sha,ts,kind,subject,action,evidence,prev_sha FROM ledger "
                             "WHERE subject LIKE ? ORDER BY ts ASC", (f"%{agent_id}%",)):
            provenance.append(dict(zip(("sha", "ts", "kind", "subject", "action",
                                        "evidence", "prev_sha"), r)))
    except Exception:
        pass
    bundle = {"schema": AGENT_BUNDLE_SCHEMA, "agent_id": agent_id, "exported_at": time.time(),
              "persona": {"roster": _roster_entry(agent_id), "core": _core_entry(agent_id),
                          "agent_md": _persona_md(agent_id, max_chars=2000)},
              "grants": _equipped_grants(agent_id), "learning": learning_rows,
              "edges": edges, "provenance": provenance}
    bundle["sha256"] = _agent_sha(bundle)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(bundle, f, ensure_ascii=False, indent=1)
    return bundle


def import_agent(bundle, approved=False):
    """Install a trained agent from a bundle. FAIL CLOSED: integrity first, then the H5 human
    gate (approved=True required — a trained agent equips abilities, exactly what H5 governs).
    Restores grants + learning history durably; spawn(agent_id, ...) then reproduces the
    trained agent on this machine."""
    if _agent_sha(bundle) != bundle.get("sha256"):
        return {"status": "REJECTED", "reason": "agent bundle hash mismatch — refusing tampered agent"}
    if bundle.get("schema") != AGENT_BUNDLE_SCHEMA:
        return {"status": "REJECTED_SCHEMA", "reason": f"unknown schema {bundle.get('schema')!r}"}
    if not approved:
        return {"status": "BLOCKED", "reason": "importing a trained agent requires user approval (H5)"}
    aid = bundle["agent_id"]
    equipped = 0
    try:
        import agent_registry
        for sid in bundle.get("grants", []):
            agent_registry.save_grant(sid, aid, approved=True, ext=True)
            equipped += 1
    except Exception:
        pass
    learned = 0
    try:
        import learning, sqlite3
        s = learning.LearningStore()
        con = sqlite3.connect(s.db_path)
        for r in bundle.get("learning", []):
            con.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?)",
                        (r["sha"], r["kind"], r["subject"], r["domain"], r["successes"],
                         r["trials"], r["status"], r["mean"], r["updated"]))
            learned += 1
        con.commit(); con.close()
    except Exception:
        pass
    return {"status": "INSTALLED", "agent_id": aid, "equipped": equipped,
            "learning_rows": learned, "provenance_events": len(bundle.get("provenance", [])),
            "next": f"agent_spawn.spawn({aid!r}, task) now reproduces the trained agent"}


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
    if len(sys.argv) > 2 and sys.argv[1] == "export":
        out = sys.argv[3] if len(sys.argv) > 3 else f"{sys.argv[2]}.agent.json"
        b = export_agent(sys.argv[2], path=out)
        print(json.dumps({"agent_id": b["agent_id"], "grants": len(b["grants"]),
                          "learning": len(b["learning"]), "sha": b["sha256"][:16],
                          "written": out}, ensure_ascii=False, indent=1))
        sys.exit(0)
    if len(sys.argv) > 2 and sys.argv[1] == "import":
        b = json.load(open(sys.argv[2], encoding="utf-8"))
        print(json.dumps(import_agent(b, approved="--approved" in sys.argv),
                         ensure_ascii=False, indent=1))
        sys.exit(0)
    aid = sys.argv[1] if len(sys.argv) > 1 else "tech-lead-orchestrator"
    task = " ".join(sys.argv[2:]) or "audit the backend code for security issues"
    spec = spawn(aid, task)
    print(json.dumps({k: spec[k] for k in ("agent_id", "domains", "skills", "diffs", "scripts",
                                           "grants", "spawn_ready", "spawn_checklist")},
                     indent=1, ensure_ascii=False))
    print("\nINSTRUCTION:\n" + spec["instruction"])
