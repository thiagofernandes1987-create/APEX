#!/usr/bin/env python3
"""
capability_map.py — the TOOL-USE MEMORY: map every capability the runtime can wield and
REMEMBER how to extract the maximum from it (the author's item 2).

WHY THIS EXISTS:
  Installed skills are dead text the LLM rediscovers every session. APEX should not only
  FIND skills (discovery cascade) — it must LEARN to work with what is installed or approved:
  which commands each skill/script exposes, which languages/tools the environment offers,
  which libraries are importable, which design/document templates outputs must follow. This
  module builds that map once, exposes it through the node RAG (rag_index) so any question
  ("como gero um xlsx?", "que comando roda o benchmark?") resolves in milliseconds, and
  closes the loop with `record_use()` — real outcomes promote/demote a capability in the
  durable learning store, so "I know how to extract the maximum from X" is EARNED, not assumed.

WHEN TO USE:
  - build(): at packaging time and after installing/approving any new skill (same trigger as
    attraction_graph.rebuild + rag_index.rebuild — the three grow together).
  - how_to(query): before reaching for a tool — returns the capability + its exact commands.
  - record_use(capability_id, success): after actually using it (feeds learning/promotion).

WHAT IT IS NOT (security boundary):
  Mapping DOCUMENTS commands; it never executes them. Execution still goes through the gates
  (UCO/SR_33 for generated code, H5 for anything external). A command string in the map is
  DATA for the LLM to consider, with provenance.

WHAT IF IT FAILS:
  Missing dirs are skipped; unreadable SKILL.md files are ignored; the environment probe
  degrades to "unknown". build() never raises on normal input.
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
MAP_PATH = os.path.join(ROOT, "catalog", "capability_map.json")

# require a REAL invocation shape (python needs a .py/-m target; pip needs install/uninstall)
# so prose lines starting with "Python cannot..." never masquerade as commands.
_CMD_RE = re.compile(
    r"^\s*(?:\$\s*)?("
    r"python3?\s+(?:-m\s+\S+|\S+\.py)\S*.*"
    r"|pip3?\s+(?:install|uninstall)\s+\S.*"
    r"|(?:npx|npm|node|git|bash|pwsh|powershell)\s+\S.*"
    r")$", re.I)
_LIBS = ("numpy", "scipy", "sklearn", "sympy", "pandas", "yaml", "matplotlib",
         "sentence_transformers", "requests")
_TOOLS = ("python", "python3", "node", "npx", "npm", "git", "pip", "docker", "bash",
          "pwsh", "powershell", "gh")


def probe_environment():
    """What this machine actually offers: languages/CLIs on PATH + importable libraries.
    An environment FACT (not an LLM capability) — the same split numeric.capabilities uses."""
    tools = {t: bool(shutil.which(t)) for t in _TOOLS}
    libs = {}
    for lib in _LIBS:
        try:
            __import__(lib)
            libs[lib] = True
        except Exception:
            libs[lib] = False
    py = f"python {sys.version.split()[0]}"
    return {"python": py, "tools": tools, "libraries": libs,
            "os": os.name, "platform": sys.platform}


def _frontmatter(md):
    out = {}
    m = re.match(r"^---\s*\n(.*?)\n---", md, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line and not line.startswith((" ", "-", "\t")):
                k, v = line.split(":", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def _commands_in(md, limit=8):
    """Extract runnable command lines from fenced blocks / usage lines (documented, not run)."""
    cmds = []
    for line in md.splitlines():
        m = _CMD_RE.match(line)
        if m:
            c = m.group(1).strip()
            if c not in cmds:
                cmds.append(c)
        if len(cmds) >= limit:
            break
    return cmds


def scan_skill_dirs(dirs=None, max_depth=3, cap=200):
    """Find installed SKILL.md files (the user's installed skills + this one) and map each to a
    capability: what it does, its trigger words, and the exact commands it documents.
    Default roots: this skill, ~/.claude/skills, plus APEX_SKILLS_DIRS (os.pathsep-separated)."""
    roots = list(dirs or [])
    if not dirs:
        roots = [ROOT, os.path.expanduser("~/.claude/skills")]
        roots += [d for d in (os.environ.get("APEX_SKILLS_DIRS") or "").split(os.pathsep) if d]
    caps = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        base_depth = root.rstrip(os.sep).count(os.sep)
        for cur, dks, files in os.walk(root):
            if cur.count(os.sep) - base_depth > max_depth:
                dks[:] = []
                continue
            dks[:] = [d for d in dks if d not in (".git", "__pycache__", "node_modules")]
            if "SKILL.md" not in files:
                continue
            try:
                md = open(os.path.join(cur, "SKILL.md"), encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            fm = _frontmatter(md)
            name = fm.get("name") or os.path.basename(cur)
            trig = ""
            tm = re.search(r"Trigger Words\s*\n+(.+)", md)
            if tm:
                trig = tm.group(1)[:160]
            caps.append({"id": f"skill:{name}", "kind": "installed-skill",
                         "name": name, "path": os.path.join(cur, "SKILL.md"),
                         "description": (fm.get("description") or "")[:240],
                         "triggers": trig, "commands": _commands_in(md)})
            if len(caps) >= cap:
                return caps
    return caps


def scan_own_scripts():
    """Every syscall of this runtime as a capability: docstring summary + its CLI invocation
    (USAGE lines / __main__ presence) — so 'which command runs X' is answerable without reading code."""
    caps = []
    sdir = os.path.join(ROOT, "scripts")
    for f in sorted(os.listdir(sdir)):
        if not f.endswith(".py"):
            continue
        try:
            src = open(os.path.join(sdir, f), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        doc = ""
        m = re.search(r'"""(.*?)"""', src, re.S)
        if m:
            doc = m.group(1).strip()
        cmds = _commands_in(doc)
        if not cmds and "__main__" in src:
            cmds = [f"python scripts/{f}"]
        caps.append({"id": f"tool:{f[:-3]}", "kind": "runtime-tool", "name": f[:-3],
                     "path": f"scripts/{f}", "description": " ".join(doc.split())[:240],
                     "triggers": "", "commands": cmds})
    return caps


def design_models():
    """The document/design templates outputs must follow (nothing generic leaves the runtime):
    execution_policy.TEMPLATES + the shipped structure model. Extend with the user's own
    (ABNT etc.) by adding entries to this list via build(extra_capabilities=[...])."""
    caps = []
    try:
        import execution_policy as ep
        for name, sections in ep.TEMPLATES.items():
            caps.append({"id": f"template:{name}", "kind": "design-template", "name": name,
                         "path": "scripts/execution_policy.py",
                         "description": f"output template '{name}' — required sections: {sections}",
                         "triggers": "", "commands": []})
    except Exception:
        pass
    mp = os.path.join(ROOT, "models", "apex_structure.model.json")
    if os.path.isfile(mp):
        caps.append({"id": "template:apex_structure", "kind": "design-template",
                     "name": "apex_structure", "path": "models/apex_structure.model.json",
                     "description": "the canonical swap-tree/file-naming standard every backend must follow",
                     "triggers": "", "commands": []})
    return caps


def build(extra_dirs=None, extra_capabilities=None, path=MAP_PATH):
    """Assemble the full capability map and persist it. Call after ANY install/approval (the
    same rebuild trigger as attraction_graph + rag_index: the three memories grow together)."""
    import time
    caps = scan_own_scripts() + scan_skill_dirs(extra_dirs) + design_models()
    caps += list(extra_capabilities or [])
    doc = {"_meta": {"note": ("Tool-use memory: every capability the runtime can wield — "
                              "runtime tools (44 syscalls + CLI), installed skills (SKILL.md "
                              "commands/triggers), design templates — plus the environment "
                              "probe (languages/libraries actually present). Mapping documents "
                              "commands; it NEVER executes them (gates/H5 still govern). "
                              "record_use() feeds real outcomes into learning so promotion is "
                              "earned. Rebuild after every install."),
                     "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                     "count": len(caps)},
           "environment": probe_environment(), "capabilities": caps}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    return {"status": "OK", "path": path, "capabilities": len(caps),
            "tools_present": sum(doc["environment"]["tools"].values()),
            "libs_present": sum(doc["environment"]["libraries"].values())}


def rebuild(path=MAP_PATH):
    return build(path=path)


_CACHE = {}


def load(path=MAP_PATH):
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        build(path=path)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    _CACHE[path] = doc
    return doc


def how_to(query, k=3, path=MAP_PATH):
    """'How do I do X?' -> the capability + its exact commands, via the node RAG when built
    (rag_index indexes each capability as a node) with a lexical fallback over this map."""
    try:
        import rag_index
        hits = rag_index.search(query, k=k, node_type="capability")
        if hits:
            by_id = {c["id"]: c for c in load(path)["capabilities"]}
            return [dict(h, commands=by_id.get(h["id"].split("capability:", 1)[-1], {}).get("commands", []))
                    for h in hits]
    except Exception:
        pass
    words = set(re.findall(r"[a-zà-ÿ0-9]{3,}", query.lower()))
    scored = []
    for c in load(path)["capabilities"]:
        text = f"{c['name']} {c['description']} {c['triggers']}".lower()
        s = sum(1 for w in words if w in text)
        if s:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [{"id": c["id"], "path": c["path"], "summary": c["description"][:120],
             "commands": c["commands"]} for _, c in scored[:k]]


def record_use(capability_id, success, domain="tooling"):
    """The promotion loop: a REAL outcome of using a capability. Enough successes -> PROMOTED
    in the durable learning store -> context_pack starts recommending it; failures demote."""
    try:
        import learning
        return learning.record_outcome("skill", capability_id, domain, bool(success))
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80]}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(json.dumps(build(), indent=1))
    else:
        q = " ".join(sys.argv[1:]) or "como rodar o benchmark?"
        for h in how_to(q):
            print(f"{h['id']:32} {h['path']}")
            for c in h.get("commands", [])[:3]:
                print(f"    $ {c}")
