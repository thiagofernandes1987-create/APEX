#!/usr/bin/env python3
"""
local_discovery.py — LOCAL-first skill & MCP discovery (what is ALREADY installed here).

WHY THIS EXISTS:
  The marketplace tiers (skills.sh, GitHub) look OUTWARD for skills to install. But the runtime
  usually ALREADY has skills on disk (`~/.claude/skills`, `/mnt/skills/...`) and MCP servers wired
  up — immediately executable, zero network, zero install, zero H5 (they are already trusted). This
  module maps that local inventory so it becomes the FIRST tier of the discovery cascade and can be
  pointed at the agents that spawn.

WHEN TO USE:
  As tier 0 of discovery (before native index / skills.sh / GitHub). An installed skill that matches
  the task should always beat a marketplace candidate that still needs approval + install.

WHAT IT DOES:
  - skills: walks the SAME container directories the `npx skills` CLI walks (root, skills/,
    skills/.curated/, .claude/skills/, .agents/skills/, data/skills/, ...) under a set of roots
    (~/.claude/skills, /mnt/skills/{public,examples}, the project, and APEX_LOCAL_SKILLS), parses
    each SKILL.md, and semantic-ranks descriptions against the task.
  - MCPs: reads `mcpServers` from the standard config files (.mcp.json, ~/.claude.json projects,
    .claude/settings*.json) plus the APEX_MCP_SERVERS env var, so agents can be told which
    `mcp__<server>__*` tools are live.

WHAT IF IT FAILS:
  - a missing root/dir           -> skipped (best-effort).
  - a malformed SKILL.md/config  -> ignored per-item; never raises.
  - nothing installed            -> returns [] and the cascade moves to native/marketplace/GitHub.
"""
import json
import os
import glob
import sys

sys.path.insert(0, os.path.dirname(__file__))
import skill_scout
import _tfidf

# Container directories the `npx skills` CLI walks inside a repo/root (vercel-labs/skills convention).
CONTAINER_DIRS = ("", "skills", "skills/.curated", "skills/.experimental", "skills/.system",
                  ".claude/skills", ".agents/skills", "data/skills", ".continue/skills",
                  ".crush/skills", ".devin/skills")


def _roots():
    """Where installed skills live. Env APEX_LOCAL_SKILLS (os.pathsep list) extends the defaults."""
    home = os.path.expanduser("~")
    roots = [os.path.join(home, ".claude", "skills"),
             "/mnt/skills/public", "/mnt/skills/examples",
             os.path.join(os.getcwd(), ".claude", "skills"), os.getcwd()]
    extra = os.environ.get("APEX_LOCAL_SKILLS", "")
    roots += [p for p in extra.split(os.pathsep) if p]
    # de-dup, keep only existing
    seen, out = set(), []
    for r in roots:
        rp = os.path.abspath(r)
        if rp not in seen and os.path.isdir(rp):
            seen.add(rp); out.append(rp)
    return out


def _find_skill_mds(root, max_files=400):
    """SKILL.md files under a root, walking the CLI container dirs one/two levels deep."""
    found = []
    for c in CONTAINER_DIRS:
        base = os.path.join(root, c) if c else root
        if not os.path.isdir(base):
            continue
        # flat: <base>/<name>/SKILL.md ; catalog: <base>/<cat>/<name>/SKILL.md ; and <base>/SKILL.md
        for pat in (os.path.join(base, "SKILL.md"),
                    os.path.join(base, "*", "SKILL.md"),
                    os.path.join(base, "*", "*", "SKILL.md")):
            found.extend(glob.glob(pat))
            if len(found) >= max_files:
                break
    return found


def local_skills():
    """Parsed inventory of every installed skill: [{name, description, path, source:'local'}]."""
    out, seen = [], set()
    for root in _roots():
        for md in _find_skill_mds(root):
            rp = os.path.realpath(md)
            if rp in seen:
                continue
            seen.add(rp)
            try:
                meta = skill_scout.parse_skill_md(open(md, encoding="utf-8", errors="replace").read())
            except Exception:
                continue
            name = meta.get("name")
            if not name or name == "?":
                continue
            out.append({"name": name, "description": meta.get("description", ""),
                        "path": md, "source": "local"})
    # de-dup by name (a shallower/earlier root shadows a nested duplicate — CLI semantics)
    dedup, names = [], set()
    for s in out:
        if s["name"] not in names:
            names.add(s["name"]); dedup.append(s)
    return dedup


# ── MCP servers (live tool namespace agents can be pointed at) ────────────────────────────────
_MCP_CONFIG_FILES = (
    os.path.join(os.getcwd(), ".mcp.json"),
    os.path.join(os.getcwd(), ".claude", "settings.json"),
    os.path.join(os.getcwd(), ".claude", "settings.local.json"),
    os.path.expanduser("~/.claude/settings.json"),
    os.path.expanduser("~/.claude.json"),
)


def _walk_mcp_servers(obj):
    """Yield mcpServers dicts found anywhere in a config tree (top-level or per-project)."""
    if isinstance(obj, dict):
        mv = obj.get("mcpServers")
        if isinstance(mv, dict):
            yield mv
        for v in obj.values():
            yield from _walk_mcp_servers(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_mcp_servers(v)


def mcp_servers():
    """Live/configured MCP servers: [{name, tool_prefix, source}]. Reads config files +
    APEX_MCP_SERVERS (comma list). Empty when none are configured (degrades cleanly)."""
    names = {}
    for f in _MCP_CONFIG_FILES:
        if not os.path.isfile(f):
            continue
        try:
            data = json.load(open(f, encoding="utf-8", errors="replace"))
        except Exception:
            continue
        for servers in _walk_mcp_servers(data):
            for n in servers:
                names.setdefault(n, f)
    for n in (os.environ.get("APEX_MCP_SERVERS", "") or "").split(","):
        n = n.strip()
        if n:
            names.setdefault(n, "env:APEX_MCP_SERVERS")
    return [{"name": n, "tool_prefix": f"mcp__{n}__", "source": src} for n, src in sorted(names.items())]


def search(query, k=5):
    """Rank the LOCALLY installed skills against the task (semantic). Returns the top-k as
    ready-to-use hits — no install, no H5 (already installed). Includes the live MCP inventory."""
    skills = local_skills()
    mcps = mcp_servers()
    if not skills:
        return {"status": "EMPTY", "query": query, "results": [], "mcp_servers": mcps}
    scores, backend = _tfidf.semantic_rank(query, [s["description"] or s["name"] for s in skills])
    for s, sc in zip(skills, scores):
        s["semantic"] = round(float(sc), 4)
    ranked = sorted(skills, key=lambda s: s["semantic"], reverse=True)
    return {"status": "OK", "query": query, "backend": backend,
            "results": ranked[:k], "mcp_servers": mcps,
            "counts": {"skills": len(skills), "mcp_servers": len(mcps)}}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "work with pdf and word documents"
    out = search(q)
    print(f"STATUS {out['status']} | {out.get('counts')}")
    for r in out.get("results", []):
        print(f"  [{r.get('semantic'):.3f}] {r['name']:<24} {r['source']}  ({r['path']})")
    if out.get("mcp_servers"):
        print("MCP servers:", [m["tool_prefix"] for m in out["mcp_servers"]])
