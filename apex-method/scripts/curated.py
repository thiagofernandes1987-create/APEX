#!/usr/bin/env python3
"""
curated.py — Load the curated per-domain skill map and pre-assign skills to agents.

WHY: the user picked the best skills per domain (programming, frontend, backend,
design, ux-ui, engineering, mcp-servers, brainstorm, finance, math, sciences,
medicine). This wires each curated skill to the agent that should wield it, so the
roster starts pre-mapped. Real install still requires scout + user approval (H5).

WHAT IF IT FAILS: If the curated catalog is missing, for_domain() returns [] and the router is used instead.
"""
import json, os, sys
HERE = os.path.dirname(__file__)
CUR = os.path.join(HERE, "..", "catalog", "curated_skills.json")


def load():
    with open(CUR, encoding="utf-8") as f:
        return json.load(f)


def for_domain(domain):
    return load()["domains"].get(domain, [])


def _installs(v):
    """Parse '391K' -> 391000, '1.2M' -> 1200000, '523' -> 523, missing -> -1."""
    s = str(v or "").strip()
    try:
        if s.endswith("K"):
            return float(s[:-1]) * 1e3
        if s.endswith("M"):
            return float(s[:-1]) * 1e6
        return float(s)
    except ValueError:
        return -1.0


def best_for_task(domain, k=3):
    """Top skills for a domain, sorted by install count when available.
    (audit fix v1.17.0: the old parser read '1.2M' as 1.2 and '391K' as 391)"""
    return sorted(for_domain(domain), key=lambda s: _installs(s.get("installs")), reverse=True)[:k]


def preassign(agents_doc):
    """Attach curated skills to their designated agent as 'available' (not yet granted)."""
    cur = load()
    for domain, skills in cur["domains"].items():
        for s in skills:
            aid = s.get("agent", "pmi_pm")
            if aid in agents_doc["agents"]:
                av = agents_doc["agents"][aid].setdefault("available_skills", [])
                av.append({"id": s["id"], "domain": domain, "install": s["install"],
                           "use_when": s["use_when"], "source": s["source"], "status": "AVAILABLE_needs_approval"})
    return agents_doc


if __name__ == "__main__":
    cur = load()
    if len(sys.argv) > 1:
        for s in best_for_task(sys.argv[1]):
            print(f"  {s['id']:60} {s.get('installs','n/a'):>7}  -> {s['agent']}")
    else:
        for dom, sk in cur["domains"].items():
            print(f"{dom} ({len(sk)}): {', '.join(x['id'].split('/')[-1] for x in sk)}")
