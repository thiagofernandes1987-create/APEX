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


# ── I/O CONTRACTS (v1.46): what you SEND, what you RECEIVE, where to APPLY ───────────────────
# Curated for the load-bearing runtime tools (accurate beats guessed); heuristic fallback for
# the rest. This is what lets a routine CHAIN capabilities: step N's `receive` feeds step N+1.
IO_CONTRACTS = {
    "tool:pot": {"send": "passos [{name, code}] — o stdout de um passo vira stdin do próximo",
                 "receive": "{ok, final_output, snapshot(checklist por passo)}",
                 "apply_when": "qualquer subproblema com >2 passos numéricos/lógicos"},
    "tool:uco_gate": {"send": "código gerado (string)",
                      "receive": "{status PASS/REJECTED, reasons, metrics(loop_risk, hamiltonian)}",
                      "apply_when": "SEMPRE antes de executar código gerado (SR_33)"},
    "tool:verify": {"send": "lhs, rhs (expressões simbólicas)",
                    "receive": "{tag FORMAL_VERIFIED/REFUTED/CONJECTURA_FORMAL, residual}",
                    "apply_when": "qualquer identidade/derivada/integral afirmada"},
    "tool:numeric": {"send": "deriv(state)->d/dt, s0, dt, steps",
                     "receive": "estado final (RK4/scipy) — validar contra quantidade conservada",
                     "apply_when": "dinâmica/EDO multidimensional"},
    "tool:monte_carlo": {"send": "model_fn(sample)->float + distribuições por input",
                         "receive": "{P10/P50/P90, cv, CI, interpretation}",
                         "apply_when": "incerteza quantificável (custo/risco/latência)"},
    "tool:orchestrator": {"send": "a tarefa (string) [+ candidates, snapshot]",
                          "receive": "{mode, specialists, kernel_checklist, llm_actions, gate}",
                          "apply_when": "TODO início de trabalho não-trivial (ponto de entrada)"},
    "tool:agent_spawn": {"send": "agent_id + task + mode + stance",
                         "receive": "AgentSpec executável {instruction, skills, context, spawn_ready}",
                         "apply_when": "antes de todo fan-out Level-B"},
    "tool:concurrent_executor": {"send": "stances [{name, persona, program}] ou hypotheses",
                                 "receive": "{merge, pmi, decision, restart?} (barrier + laudos SHA-256)",
                                 "apply_when": "rodada paralela DEEP+ (Level A) / painel de diretores"},
    "tool:gravity": {"send": "a necessidade/tarefa (texto)",
                     "receive": "constelação {agent, skill, script, diff} + gaps + pedidos STAGED",
                     "apply_when": "resolver especialistas e recursos por disciplina"},
    "tool:attraction_graph": {"send": "competência-semente ou texto da necessidade (equip_for)",
                              "receive": "membros que se completam, ranqueados por atração",
                              "apply_when": "compor ferramentas complementares sem re-descoberta"},
    "tool:rag_index": {"send": "pergunta PT/EN",
                       "receive": "top nós {id, path, summary} para LER em seguida",
                       "apply_when": "localizar qualquer coisa no repositório"},
    "tool:capability_map": {"send": "pergunta 'como faço X?'",
                            "receive": "capacidade + comandos exatos + contrato de I/O",
                            "apply_when": "antes de usar qualquer ferramenta"},
    "tool:memory": {"send": "remember(texto, kind) / recall(query) / relate(a, b, rel)",
                    "receive": "sha da memória / top-k fatos / caminhada no grafo",
                    "apply_when": "persistir e recuperar conhecimento validado"},
    "tool:swap_store": {"send": "page_out(session, memory_db) / page_in_session(dir)",
                        "receive": "bundle assinado + drive_manifest / stores restaurados",
                        "apply_when": "fim de sessão DEEP+ (persist_due) / retomada (resume_due)"},
    "tool:skill_scout": {"send": "URL raw de um SKILL.md (+ code_urls)",
                         "receive": "{status STAGED/REJECTED_UNSAFE, checks, snapshot_entry}",
                         "apply_when": "SEMPRE antes de considerar uma skill externa (H5 depois)"},
    "tool:learning": {"send": "record_outcome(kind, subject, domain, success)",
                      "receive": "{mean, n, status PROMOTED/DEMOTED, changed}",
                      "apply_when": "após cada rodada adjudicada / uso real de capacidade"},
    "tool:bayes": {"send": "priors + likelihoods (crenças do LLM)",
                   "receive": "posterior + decisão Ω (ADOPT/REVIEW/REJECT) + R_acum",
                   "apply_when": "convergência PMI / decisão entre hipóteses"},
    "tool:project_ledger": {"send": "micros {who, what, to whom, depends_on}",
                            "receive": "DSM (caminho crítico + lotes paralelos) + gate de conclusão",
                            "apply_when": "projeto DEEP+ que atravessa sessões"},
}


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


def _scan_cache_path():
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "capability_scan_cache.json")


def scan_skill_dirs(dirs=None, max_depth=3, cap=500, use_cache=True):
    """Find installed SKILL.md files (the user's installed skills + this one) and map each to a
    capability: what it does, its trigger words, and the exact commands it documents.
    Default roots: this skill, ~/.claude/skills, plus APEX_SKILLS_DIRS (os.pathsep-separated).

    v1.47 INCREMENTAL CACHE: with hundreds of installed skills a full re-parse per build gets
    slow. Each SKILL.md's parsed entry is cached by (path, mtime, size) in the machine-local
    APEX home; unchanged files are served from cache, changed/new ones re-parsed, and entries
    whose file disappeared are pruned. scan stats ride along in `_scan_stats`."""
    roots = list(dirs or [])
    if not dirs:
        roots = [ROOT, os.path.expanduser("~/.claude/skills")]
        roots += [d for d in (os.environ.get("APEX_SKILLS_DIRS") or "").split(os.pathsep) if d]
    cache = {}
    if use_cache:
        try:
            with open(_scan_cache_path(), encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    caps, seen_paths, parsed, cached = [], set(), 0, 0
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
            mdp = os.path.join(cur, "SKILL.md")
            seen_paths.add(mdp)
            try:
                st = os.stat(mdp)
                key = f"{st.st_mtime_ns}:{st.st_size}"
            except OSError:
                continue
            hit = cache.get(mdp)
            if use_cache and hit and hit.get("key") == key:
                caps.append(hit["entry"])
                cached += 1
                if len(caps) >= cap:
                    break
                continue
            try:
                md = open(mdp, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            parsed += 1
            fm = _frontmatter(md)
            name = fm.get("name") or os.path.basename(cur)
            trig = ""
            tm = re.search(r"Trigger Words\s*\n+(.+)", md)
            if tm:
                trig = tm.group(1)[:160]
            desc = (fm.get("description") or "")[:240]
            use_when = ""
            uw = re.search(r"Use when:?\s*(.+)", md, re.I)
            if uw:
                use_when = uw.group(1)[:140]
            entry = {"id": f"skill:{name}", "kind": "installed-skill",
                     "name": name, "path": mdp,
                     "description": desc, "triggers": trig,
                     "commands": _commands_in(md),
                     "io": {"send": "a tarefa/artefato descrito nos triggers do SKILL.md",
                            "receive": "orientação/artefato conforme a seção de uso da skill",
                            "apply_when": use_when or trig[:140] or desc[:140]}}
            caps.append(entry)
            cache[mdp] = {"key": key, "entry": entry}
            if len(caps) >= cap:
                break
    # prune entries whose file vanished; persist the incremental cache (machine-local)
    if use_cache:
        cache = {p: v for p, v in cache.items() if p in seen_paths}
        try:
            with open(_scan_cache_path(), "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False)
        except Exception:
            pass
    scan_skill_dirs._scan_stats = {"parsed": parsed, "cached": cached, "total": len(caps)}
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
        cid = f"tool:{f[:-3]}"
        # I/O contract: curated when we have it (accurate), heuristic WHEN-line otherwise
        io = IO_CONTRACTS.get(cid)
        if not io:
            wm = re.search(r"WHEN(?:\s+TO\s+USE)?:?\s*\n?\s*(.+)", doc)
            io = {"send": "ver docstring/CLI", "receive": "ver docstring",
                  "apply_when": (wm.group(1)[:120] if wm else "")}
        caps.append({"id": cid, "kind": "runtime-tool", "name": f[:-3],
                     "path": f"scripts/{f}", "description": " ".join(doc.split())[:240],
                     "triggers": "", "commands": cmds, "io": io})
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
                         "triggers": "", "commands": [],
                         "io": {"send": "o rascunho da entrega",
                                "receive": f"documento estruturado nas seções {sections}",
                                "apply_when": f"ao produzir uma entrega do tipo '{name}'"}})
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
            "libs_present": sum(doc["environment"]["libraries"].values()),
            "scan": getattr(scan_skill_dirs, "_scan_stats", {})}


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
