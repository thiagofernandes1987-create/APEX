#!/usr/bin/env python3
"""
skill_ledger.py — remember MY choices: the provenance of every skill/tool decision.

WHY THIS EXISTS:
  The runtime discovers skills, equips agents, and solves problems — but without a durable record of
  WHAT it chose and WHETHER it worked, every new session re-decides from scratch. This module writes
  the full decision provenance so the swap memory can carry it across sessions and the next run
  *remembers how we planned to use things*: which problem, which skill, which agent, did it solve it,
  was it promoted, which repo, and the exact commands (+ what each does).

WHEN TO USE:
  Right after a skill/agent is used on a real problem (success OR failure). Call `record(...)`. At the
  start of a related task call `recall(problem)` to see what was chosen before, and `worked_for(task)`
  to bias attraction toward skills that already solved similar problems.

HOW IT PERSISTS (no new plumbing — reuses the swap-captured stores):
  - memory (semantic + meta)   -> recall(problem) finds the choice           [swap: memory]
  - knowledge-graph edge        -> problem --resolved_by/attempted--> skill    [swap: knowledge_graph]
  - governance ledger event     -> tamper-evident SHA-256 chain                [swap: ledger]
  - learning outcome            -> promote/demote the skill by success rate    [swap: stores.learning]
  page_out(session) captures ALL of these, so page_in on another machine restores the choices AND the
  attraction prior (worked_for) intact.

WHAT IF IT FAILS:
  Every sub-store write is best-effort and isolated; a missing store degrades that facet only and the
  call never raises. `recall`/`worked_for` return [] when there is no history yet.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

MARK = "SKILL_CHOICE"   # tags the semantic record so recall() can tell choices from other memories


def record(problem, skill, agent=None, solved=None, repo=None, commands=None,
           domain="general", session="default", memory_db=None):
    """Persist one skill/tool decision (the 7 fields). `commands` is a list of
    {"cmd": str, "does": str}. Returns the provenance dict (with `promoted` resolved from learning)."""
    import memory
    commands = commands or []
    prov = {"problem": problem, "skill": skill, "agent": agent, "solved": solved,
            "repo": repo, "commands": commands, "domain": domain, "ts": time.time()}
    store = memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()

    cmds_txt = "; ".join(f"`{c.get('cmd')}` ({c.get('does')})" for c in commands) or "—"
    text = (f"{MARK} :: problem: {problem} | skill: {skill} | agent: {agent} | "
            f"solved: {solved} | promoted: ? | repo: {repo} | commands: {cmds_txt}")
    sha = store.remember(text, kind="semantic", meta=prov, session=session)
    prov["memory_sha"] = sha

    # knowledge-graph edge: problem -> skill (typed by outcome) so recall_graph can walk it
    try:
        rel = "resolved_by" if solved else ("attempted" if solved is not None else "considered")
        store.relate_text(f"problem: {problem}",
                          f"skill: {skill}" + (f" ({repo})" if repo else ""), rel, session=session)
    except Exception:
        pass

    # learning outcome -> promote/demote (writes its own governance event on a status change)
    promoted = None
    if solved is not None:
        try:
            import learning
            out = learning.LearningStore().record_outcome(
                "skill", skill, domain, success=bool(solved),
                evidence={"problem": problem, "repo": repo, "agent": agent})
            promoted = (out.get("status") == "PROMOTED")
        except Exception:
            pass
    prov["promoted"] = promoted

    # tamper-evident provenance in the governance ledger
    try:
        store.record_event("skill_choice", subject=skill,
                           action=("solved" if solved else "attempted" if solved is not None else "considered"),
                           evidence=prov)
    except Exception:
        pass
    return prov


def _is_choice(hit):
    m = hit.get("meta") or {}
    return isinstance(m, dict) and "skill" in m and "problem" in m


def recall(problem, k=5, memory_db=None):
    """What did we choose for a similar problem before? Returns the stored choices (7 fields each),
    most relevant first, annotated with the skill's current learning status."""
    import memory
    store = memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()
    # Oversample: record() also writes empty-meta graph-projection nodes ("problem: …")
    # that are near-duplicates of the query and outrank the tagged choice record, so a
    # small window would be flooded by non-choices. recall() scores every row regardless
    # of k, so a large pool is free; we filter to choice records BEFORE truncating to k.
    hits = [h for h in store.recall(problem, k=max(k * 40, 200)) if _is_choice(h)]
    try:
        import learning
        ls = learning.LearningStore()
        status = {b.get("subject"): b.get("status") for b in ls.best("skill", "general", k=50, include_demoted=True)}
    except Exception:
        status = {}
    out = []
    for h in hits[:k]:
        m = h["meta"]
        out.append({"problem": m.get("problem"), "skill": m.get("skill"), "agent": m.get("agent"),
                    "solved": m.get("solved"), "promoted": m.get("promoted"), "repo": m.get("repo"),
                    "commands": m.get("commands", []), "domain": m.get("domain"),
                    "learning_status": status.get(m.get("skill")), "score": h.get("score")})
    return out


def worked_for(task, domain="general", k=5, memory_db=None):
    """Attraction prior: skills that ALREADY solved a similar problem (promoted/active, success>0).
    Feed into gravity/discovery so a proven skill is pulled first next time."""
    import memory
    store = memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()
    # see recall(): oversample so accumulated graph-projection nodes can't bury the
    # proven choice record (filter-before-truncate); recall scores all rows anyway.
    hits = [h for h in store.recall(task, k=max(k * 40, 200)) if _is_choice(h)]
    agg = {}
    for h in hits:
        m = h["meta"]
        if not m.get("skill"):
            continue
        a = agg.setdefault(m["skill"], {"skill": m["skill"], "repo": m.get("repo"),
                                        "solved": 0, "tried": 0, "score": 0.0,
                                        "problem": m.get("problem")})
        a["tried"] += 1
        if m.get("solved"):
            a["solved"] += 1
        if h.get("score", 0) > a["score"]:
            # carry the best-matching remembered problem text — the hybrid facet gate
            # (orchestrator.resolution_check v1.62) compares task facets against it
            a["problem"] = m.get("problem") or a["problem"]
        a["score"] = max(a["score"], h.get("score", 0))
    ranked = [a for a in agg.values() if a["solved"] > 0]
    # blend recency/relevance (recall score) with proven success rate
    for a in ranked:
        a["success_rate"] = round(a["solved"] / a["tried"], 3)
        a["prior"] = round(0.5 * a["score"] + 0.5 * a["success_rate"], 4)
    ranked.sort(key=lambda a: a["prior"], reverse=True)
    return ranked[:k]


if __name__ == "__main__":
    # demo: record a choice, then recall it
    home = os.environ.get("APEX_METHOD_HOME") or ""
    p = record("extract text from a pdf report", "pdf", agent="doc-specialist", solved=True,
               repo="anthropics/skills",
               commands=[{"cmd": "npx skills add anthropics/skills", "does": "install the pdf skill"}])
    print("recorded:", json.dumps(p, ensure_ascii=False)[:200])
    print("recall   :", json.dumps(recall("work with pdf"), ensure_ascii=False)[:300])
    print("worked_for:", json.dumps(worked_for("pdf"), ensure_ascii=False)[:200])
