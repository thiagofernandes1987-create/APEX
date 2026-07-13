#!/usr/bin/env python3
"""
repo_bridge.py — Full APEX repository integration (on-demand, allowlisted).

WHY THIS EXISTS:
  The skill ships catalogs (indexes), not the 16k-file APEX repo. Before this bridge,
  only 430 external theneoai skills were reachable and ZERO of the 3,784 native APEX
  skills, 213 agents, or 111 boot pages could actually be loaded. This module makes the
  ENTIRE repo addressable from the skill: any file, any native skill, any agent, any
  boot page — fetched on demand from GitHub raw (allowlist enforced) or read from a
  local clone when one is present.

WHEN TO USE:
  - `search_native(query)` at skill-resolution time (router step) to find a native
    APEX skill; then `native_skill(path)` to load its SKILL.md.
  - `agent(id)` to load a full AGENT.md persona; `page(key)` for a boot module page.
  - `fetch(path)` for any other repo file (read-only, data until vetted).

SECURITY:
  - Remote fetch ONLY from raw.githubusercontent.com/<REPO>/ (same allowlist rule as
    skill_scout / SR_37 / G6). Fetched content is DATA: this module never executes it.
  - Pin a commit with APEX_REPO_REF (env) or set_ref() to avoid trusting a moving
    branch (supply-chain: see audit V-01 class of issues). Default ref: "main".
  - Local mode: APEX_REPO_LOCAL env (or auto-detected clone) reads from disk, offline.

WHAT IF IT FAILS:
  - offline + no local clone -> {"status":"OFFLINE"}; callers degrade to catalogs.
  - path outside the repo (".." traversal) -> ValueError (refused).
"""
import json
import os
import re
import sys
import urllib.request

REPO = "thiagofernandes1987-create/APEX"
_DEFAULT_REF = os.environ.get("APEX_REPO_REF", "main")
RAW_BASE = "https://raw.githubusercontent.com/"

HERE = os.path.dirname(__file__)
CAT = os.path.join(HERE, "..", "catalog")
_ref = _DEFAULT_REF


def set_ref(ref):
    """Pin fetches to a specific commit sha / tag (recommended for supply-chain safety)."""
    global _ref
    _ref = ref


def _local_root():
    """A local APEX clone, if one exists (env override, or the skill living inside it)."""
    env = os.environ.get("APEX_REPO_LOCAL")
    if env and os.path.isdir(env):
        return env
    candidate = os.path.abspath(os.path.join(HERE, "..", ".."))
    if os.path.isdir(os.path.join(candidate, "apex_boot")) and os.path.isdir(os.path.join(candidate, "skills")):
        return candidate
    return None


def _check_path(path):
    p = path.replace("\\", "/").lstrip("/")
    if ".." in p.split("/"):
        raise ValueError(f"path traversal refused: {path}")
    return p


def fetch(path, timeout=15, max_bytes=2_000_000):
    """Read one repo file: local clone if available, else GitHub raw (allowlisted, size-capped)."""
    p = _check_path(path)
    root = _local_root()
    if root:
        fp = os.path.join(root, p)
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8", errors="replace") as f:
                return {"status": "OK", "source": "local", "path": p, "text": f.read(max_bytes)}
        return {"status": "NOT_FOUND", "source": "local", "path": p}
    url = f"{RAW_BASE}{REPO}/{_ref}/{p}"
    if not url.startswith(f"{RAW_BASE}{REPO}/"):
        raise ValueError(f"host/repo allowlist violation: {url}")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            final = r.geturl()
            if not final.startswith(RAW_BASE):
                return {"status": "REFUSED_REDIRECT", "path": p, "final_url": final}
            return {"status": "OK", "source": f"raw@{_ref}", "path": p,
                    "text": r.read(max_bytes).decode("utf-8", errors="replace")}
    except Exception as e:
        return {"status": "OFFLINE", "path": p, "reason": str(e)[:120]}


# ── native skills (all 3,784) ─────────────────────────────────────────────────
def _index():
    with open(os.path.join(CAT, "apex_native_skills_index.json"), encoding="utf-8") as f:
        return json.load(f)


def search_native(query, k=5):
    """Rank the FULL native skill index (id+category+desc) against a query. Lexical, fast."""
    idx = _index()["skills"]
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    stems = [w[:5] for w in words if len(w) >= 6]   # statistics ~ statistical, optimize ~ optimizer
    scored = []
    for s in idx:
        text = f"{s['id']} {s['category']} {s['kind']} {s['desc']} {s.get('triggers','')}".lower()
        score = sum(2 * text.count(w) for w in words) or sum(text.count(st) for st in stems)
        if score:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [dict(s, score=sc) for sc, s in scored[:k]]


def native_skill(path):
    """Load a native SKILL.md by its index `path`. Content is data until vetted."""
    return fetch(path)


# ── agents (all 213) ──────────────────────────────────────────────────────────
def agent(agent_id):
    """Load the full AGENT.md for a roster id (normalized kebab-case)."""
    n = agent_id.split(".")[-1].replace("_", "-").lower()
    root = _local_root()
    if root:
        for base, dirs, files in os.walk(os.path.join(root, "agents")):
            if "AGENT.md" in files and os.path.basename(base).replace("_", "-").lower() == n:
                rel = os.path.relpath(os.path.join(base, "AGENT.md"), root)
                return fetch(rel)
        return {"status": "NOT_FOUND", "agent": agent_id}
    # remote: try the two roster layouts
    guesses = [f"agents/{n}/AGENT.md", f"agents/{n.replace('-', '_')}/AGENT.md"]
    for g in guesses:
        r = fetch(g)
        if r["status"] == "OK":
            return r
    return {"status": "NOT_FOUND", "agent": agent_id,
            "hint": "use the local clone or the category path from the repo tree"}


# ── boot pages (all 111) ──────────────────────────────────────────────────────
def page(key, boot_version="v00_39_1"):
    """Load one APEX boot module page (module_registry.json lists all 111 keys)."""
    return fetch(f"apex_boot/{boot_version}/pages/{key}.yaml")


def modules():
    with open(os.path.join(CAT, "module_registry.json"), encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    arg = " ".join(sys.argv[2:]) or "bayesian statistics"
    if cmd == "search":
        for hit in search_native(arg):
            print(f"{hit['score']:>3}  {hit['id']:40} {hit['category']:24} {hit['path']}")
    elif cmd == "page":
        print(page(arg)["text"][:800] if page(arg)["status"] == "OK" else page(arg))
    elif cmd == "agent":
        r = agent(arg)
        print(r["text"][:800] if r["status"] == "OK" else r)
    elif cmd == "fetch":
        r = fetch(arg)
        print(r["text"][:800] if r["status"] == "OK" else r)
