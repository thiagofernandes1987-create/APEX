#!/usr/bin/env python3
"""
agent_registry.py — Agent roster + competence mapping (APEX method).

WHY THIS EXISTS:
  APEX reasons through personas ("agents"). This registry keeps, for each persona:
  its personality, its specialization, and WHICH SKILLS it is competent to use —
  with an experience counter. When the skill scout stages a new skill and the user
  APPROVES it, this module maps that skill to the agents whose specialization fits
  and grants it to them (adds the skill + its scripts as available tools, bumps
  experience). That is how "installing a skill upgrades the agents".

HONEST SCOPE:
  - Agents are sequential personas the LLM adopts, NOT parallel processes.
  - "experience" is a competence COUNTER (bookkeeping), not model learning.
  - grant_skill() must only be called AFTER the human approval gate (APEX H5). The
    scout stages; the user approves; then this grants.

WHAT IF IT FAILS:
  - No matching agent for a skill -> it is granted to the generalist (pmi_pm) and
    flagged for manual assignment; nothing is lost.
"""
import json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN = True
except ImportError:                    # audit fix v1.17.0: sklearn was a HARD dependency —
    from _tfidf import rank as _rank   # the entry point crashed in any clean environment.
    _SKLEARN = False                   # Pure-python fallback keeps every router alive.

HERE = os.path.dirname(__file__)
AGENTS = os.path.join(HERE, "..", "catalog", "agents_catalog.json")
SKILLS = os.path.join(HERE, "..", "catalog", "skills_catalog.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _agent_text(a):
    return " ".join([a["personality"],
                     " ".join(a["specialization"]["domains"]),
                     " ".join(a["specialization"]["keywords"])])


def _rank_texts(query, texts):
    """TF-IDF cosine of query vs texts — sklearn when present, pure-python otherwise."""
    if _SKLEARN:
        vec = TfidfVectorizer(ngram_range=(1, 2)).fit(texts + [query])
        return list(cosine_similarity(vec.transform([query]), vec.transform(texts))[0])
    return _rank(query, texts)


def match_task_to_agents(task, agents_doc, k=3):
    """Rank agents by fit to a task (specialization + personality)."""
    ags = agents_doc["agents"]
    ids = list(ags)
    sims = _rank_texts(task, [_agent_text(ags[i]) for i in ids])
    order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
    return [(ids[i], round(float(sims[i]), 3)) for i in order if sims[i] > 0]


def match_skill_to_agents(skill, agents_doc, threshold=0.05):
    """Return agent ids whose specialization matches a skill (by domain + text)."""
    ags = agents_doc["agents"]
    skill_dom = skill.get("domain", "")
    skill_text = f"{skill.get('name','')} {skill.get('description','')} {skill_dom} {' '.join(skill.get('tags',[]))}"
    matched = []
    # 1) direct domain match
    for aid, a in ags.items():
        if skill_dom and skill_dom in a["specialization"]["domains"]:
            matched.append(aid)
    # 2) text similarity fallback if no direct domain hit
    if not matched:
        ids = list(ags)
        sims = _rank_texts(skill_text, [_agent_text(ags[i]) for i in ids])
        order = sorted(range(len(sims)), key=lambda i: -sims[i])[:2]
        matched = [ids[i] for i in order if sims[i] > threshold]
    return matched or ["pmi_pm"]  # generalist fallback


def grant_skill(skill, agents_doc, approved: bool, scripts=None, ext_grants=None):
    """
    Grant an APPROVED skill to the compatible agents, updating competence + experience.
    Returns the list of (agent_id, new_experience). Refuses if not approved (APEX H5).

    audit (SCIENTIFIC): grants also reach the 213-agent EXTENDED roster, not only the 11
    core personas. `ext_grants` is an in-memory competence store {agent_id: {skill: uses}}
    the caller keeps across a session; if omitted, extended matches are still reported so
    "installing a skill upgrades the matching agent" holds for the whole roster.
    """
    if not approved:
        return {"status": "BLOCKED", "reason": "skill not approved by user (APEX H5)"}
    targets = match_skill_to_agents(skill, agents_doc)
    updated = []
    for aid in targets:
        comp = agents_doc["agents"][aid]["competence"]
        entry = comp.get(skill["id"], {"experience": 0, "scripts": []})
        entry["experience"] += 1
        entry["use_when"] = skill.get("use_when", skill.get("description", ""))[:100]
        entry["source"] = skill.get("source", "")
        if scripts:
            entry["scripts"] = sorted(set(entry.get("scripts", []) + list(scripts)))
        comp[skill["id"]] = entry
        # aggregate domain experience
        dom = skill.get("domain", "misc")
        de = agents_doc["agents"][aid]["domain_experience"]
        de[dom] = de.get(dom, 0) + 1
        updated.append((aid, entry["experience"]))

    # extended roster (213): route the skill to the best-matching real APEX agents and
    # record the grant so the whole roster — not just the 11 core — gains competence.
    ext_updated = []
    skill_text = f"{skill.get('name','')} {skill.get('description','')} {skill.get('domain','')}"
    for aid, cat, score in match_task_to_ext_agents(skill_text, k=2):
        if ext_grants is not None:
            store = ext_grants.setdefault(aid, {})
            store[skill["id"]] = store.get(skill["id"], 0) + 1
            ext_updated.append((aid, store[skill["id"]]))
        else:
            ext_updated.append((aid, 1))
    return {"status": "GRANTED", "skill": skill["id"],
            "agents": updated, "ext_agents": ext_updated}


def tier(exp):
    return "expert" if exp >= 6 else "proficient" if exp >= 3 else "familiar" if exp >= 1 else "untrained"


def render_roster(agents_doc):
    lines = ["# AGENT ROSTER"]
    for aid, a in agents_doc["agents"].items():
        comp = a["competence"]
        skills = ", ".join(f"{k.split('/')[-1]}({tier(v['experience'])})" for k, v in comp.items()) or "—"
        lines.append(f"- **{a['display_name']}** [{a['role']}] :: {skills}")
    return "\n".join(lines)


if __name__ == "__main__":
    agents = load(AGENTS)
    skills = load(SKILLS)
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"

    if cmd == "match" and len(sys.argv) > 2:
        for aid, s in match_task_to_agents(sys.argv[2], agents):
            print(f"{s:.3f}  {aid}  — {agents['agents'][aid]['display_name']}")
    else:
        # demo: grant the first finance + first software skill, show experience gain
        by_dom = {}
        for s in skills:
            by_dom.setdefault(s["domain"], s)
        demo_skills = [by_dom.get("finance"), by_dom.get("software"), by_dom.get("ai-ml")]
        for sk in filter(None, demo_skills):
            res = grant_skill(sk, agents, approved=True, scripts=["router.py"])
            print(res["status"], sk["id"], "->", res["agents"])
        print("\n" + render_roster(agents))

# ── Extended roster (all 213 real APEX agents mined from thiagofernandes1987-create/APEX) ──
ROSTER_EXT = os.path.join(HERE, "..", "catalog", "apex_agents_roster.json")


def load_ext_roster():
    try:
        with open(ROSTER_EXT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def match_task_to_ext_agents(task, k=5):
    """Route a task to the best of the 213 extended APEX agents by domain keywords."""
    roster = load_ext_roster()
    if not roster:
        return []
    texts = [" ".join([a["id"], a.get("category", "")] + a.get("domains", [])) for a in roster]
    sims = _rank_texts(task, texts)
    order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
    return [(roster[i]["id"], roster[i].get("category", ""), round(float(sims[i]), 3))
            for i in order if sims[i] > 0]

