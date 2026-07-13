#!/usr/bin/env python3
"""
gravity.py — Gravitational resource composition (APEX synergy engine).

WHY THIS EXISTS:
  Picking one agent or one skill in isolation misses synergy. This engine treats every
  resource — scripts, agents, skills, diff-rules — as a body with MASS, computes the
  ATTRACTION between them, and MERGES the most synergistic ones (across types) into a
  "constellation" for a task. That is the "gravitational attraction to merge resources
  by synergy" idea, made computable.

THE MODEL (honest about what the physics vocabulary means):
  - Each resource has a MASS (script: lines of code; agent: tier weight; skill: install
    count; diff: rule weight) — a proxy for how much it can contribute.
  - PROXIMITY between two resources = cosine similarity of their text (domain + capabilities
    + tags), via TF-IDF over a shared vocabulary.
  - ATTRACTION F(i,j) = mass_i * mass_j * proximity(i,j)  — monotone in both mass and
    closeness (gravity ∝ product of masses, modulated by proximity). It is a weighted
    similarity, dressed as gravity; it is NOT literal physics, but it is real, deterministic math.
  - A task is a body too; PULL(task, r) = mass_r * proximity(task, r).
  - A CONSTELLATION is built greedily: seed with the highest task-pull resource, then add
    the resource that maximizes task-pull + synergy-to-set, favoring TYPE DIVERSITY so the
    result MERGES a script + an agent + a skill + a diff-rule that reinforce each other.

WHAT IF IT FAILS:
  If a catalog is missing it is skipped; the engine works with whatever libraries are present.
"""
import json, os, sys, math
sys.path.insert(0, os.path.dirname(__file__))
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN = True
except ImportError:                          # audit fix v1.17.0: sklearn was a HARD dependency
    from _tfidf import rank as _rank, pairwise as _pairwise
    _SKLEARN = False

HERE = os.path.dirname(__file__)
CAT = os.path.join(HERE, "..", "catalog")

# semantic_gravity_engine thresholds (OPP-169) — real APEX values, not arbitrary
ATTRACTION_RADIUS = 0.12   # computed TF-IDF cosine radius (PoC 0.08-0.20)
RELAXED_RADIUS = 0.06      # fallback radius
NEIGHBOR_COLOAD = 0.7      # co-load neighbors with score > 0.7 * max_score


def _load(name):
    try:
        return json.load(open(os.path.join(CAT, name), encoding="utf-8"))
    except Exception:
        return []


def _parse_installs(v):
    if not isinstance(v, str):
        return 1.0
    v = v.strip()
    try:
        if v.endswith("K"):
            return float(v[:-1]) * 1e3
        if v.endswith("M"):
            return float(v[:-1]) * 1e6
        return float(v)
    except Exception:
        return 1.0


def load_resources():
    """Unify scripts, agents, skills, diffs into bodies with {id,type,text,mass}."""
    R = []
    # scripts (mass = LOC)
    for s in _load("scripts_lib.json"):
        R.append({"id": s["id"], "type": "script",
                  "text": f"{s['domain']} {s['capabilities']}", "mass": float(s.get("mass", 100))})
    # agents (mass = tier weight; tier 1 core heavier)
    for a in _load("apex_agents_roster.json"):
        tier = a.get("tier", 2)
        mass = 300.0 if str(tier) in ("1", "native/cs") else 150.0
        R.append({"id": f"agent:{a['id']}", "type": "agent",
                  "text": f"{a['id']} {a.get('category','')} {' '.join(a.get('domains',[]))}", "mass": mass})
    # skills (mass = installs)
    cur = _load("curated_skills.json")
    if isinstance(cur, dict):
        for dom, skills in cur.get("domains", {}).items():
            for s in skills:
                R.append({"id": f"skill:{s['id']}", "type": "skill",
                          "text": f"{dom} {s.get('use_when','')}", "mass": _parse_installs(s.get("installs", "1"))})
    # diffs (mass = small constant; they are rules/constraints)
    for d in _load("diffs_lib.json"):
        # bilingual body text (P1 audit backlog): PT-only diff texts never attracted
        # against EN tasks — text_en makes diffs first-class constellation members
        R.append({"id": f"diff:{d['id']}", "type": "diff",
                  "text": f"{d.get('what','')} {d.get('gargalo','')} {d.get('text_en','')}",
                  "mass": 80.0})
    return R


def _normalize_mass(R):
    # log-normalize masses to a comparable 0.2–1.0 range
    masses = [r["mass"] for r in R] or [1]
    lo, hi = math.log1p(min(masses)), math.log1p(max(masses))
    span = (hi - lo) or 1.0
    for r in R:
        r["nmass"] = 0.2 + 0.8 * (math.log1p(r["mass"]) - lo) / span
    return R


_BUILD_CACHE = {}


def build(resources=None):
    """Load bodies + fit TF-IDF once per process (audit fix v1.17.0: this was refit on
    EVERY constellation() call — once per discipline in the orchestrator)."""
    if resources is None and "default" in _BUILD_CACHE:
        return _BUILD_CACHE["default"]
    R = _normalize_mass(resources or load_resources())
    texts = [r["text"] for r in R]
    if _SKLEARN:
        vec = TfidfVectorizer(ngram_range=(1, 2)).fit(texts + [" "])
        built = (R, vec, vec.transform(texts))
    else:
        built = (R, None, texts)
    if resources is None:
        _BUILD_CACHE["default"] = built
    return built


def constellation(task, budget=6, diversity_bonus=0.15):
    """Merge the most synergistic resources for a task into a cross-type constellation."""
    R, vec, X = build()
    if not R:
        return {"task": task, "constellation": [], "note": "no resources loaded"}
    nmass = [r["nmass"] for r in R]
    if _SKLEARN:
        prox = list(cosine_similarity(vec.transform([task]), X)[0])
        sim = cosine_similarity(X)                       # proximity matrix
    else:
        prox = _rank(task, X)                            # X holds the raw texts here
        sim = _pairwise(X)
    pull = [p * m for p, m in zip(prox, nmass)]          # PULL = proximity * mass

    chosen = [max(range(len(R)), key=lambda i: pull[i])]
    types = {R[chosen[0]]["type"]}
    while len(chosen) < budget:
        best, best_score = None, -1
        for i in range(len(R)):
            if i in chosen:
                continue
            # ATTRACTION to the current set = sum of gravity to chosen bodies
            synergy = sum(R[i]["nmass"] * R[j]["nmass"] * sim[i][j] for j in chosen)
            score = pull[i] + synergy + (diversity_bonus if R[i]["type"] not in types else 0)
            if score > best_score:
                best, best_score = i, score
        if best is None or best_score <= 0:
            break
        chosen.append(best)
        types.add(R[best]["type"])
    out = [{"id": R[i]["id"], "type": R[i]["type"], "pull": round(float(pull[i]), 3)} for i in chosen]
    # group by type = the merged bundle
    merged = {}
    for o in out:
        merged.setdefault(o["type"], []).append(o["id"])
    return {"task": task, "constellation": out, "merged_by_type": merged}


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "value a company and backtest a trading strategy"
    res = constellation(task)
    print(f"TASK: {res['task']}\n")
    print("MERGED CONSTELLATION (synergistic resources pulled together):")
    for t, ids in res["merged_by_type"].items():
        print(f"  {t:7}: {', '.join(ids)}")


# ── Gap detection + native-index/skills.sh/GitHub fallback + MCP surfacing ──
_load_cat = _load   # audit fix v1.17.0: was a byte-for-byte duplicate of _load


def plan(task, required_roles=None):
    """
    Build a constellation from the library, detect GAPS (missing roles for the task),
    and for each gap resolve in order: (1) the FULL native APEX index (3,784 skills,
    via repo_bridge), (2) a skills.sh search request, (3) a GitHub search request —
    each emitted as a STAGED install request the user must approve (H5), with MCP /
    skill_forge fallbacks.
    """
    con = constellation(task, budget=8)
    # relevance floor (semantic_gravity_engine): prefer the strict attraction radius,
    # relax to RELAXED_RADIUS when nothing clears it (audit fix v1.17.0: the strict
    # ATTRACTION_RADIUS constant was declared but never used)
    strong = [o for o in con["constellation"] if o["pull"] >= ATTRACTION_RADIUS]
    if len(strong) < 3:   # too few in the strict radius -> relax (semantic_gravity fallback)
        strong = [o for o in con["constellation"] if o["pull"] >= RELAXED_RADIUS]
    con["merged_by_type"] = {}
    for o in strong:
        con["merged_by_type"].setdefault(o["type"], []).append(o["id"])
    present_types = set(o["type"] for o in strong)
    # default required roles for a well-formed solution
    required_roles = required_roles or ["agent", "skill", "script", "diff"]

    # method keywords -> a dedicated "method skill" role (SA/HMC/etc.)
    method_terms = {"simulated annealing": "SA", "annealing": "SA", "hamiltonian monte carlo": "HMC",
                    "hmc": "HMC", "mcmc": "MCMC", "statistical physics": "stat-phys",
                    "monte carlo": "MC", "gradient descent": "GD"}
    wanted_methods = sorted({tag for term, tag in method_terms.items() if term in task.lower()})

    gaps, install_requests, mcp_suggestions = [], [], []

    # 1) missing resource TYPES
    for role in required_roles:
        if role not in present_types:
            gaps.append(f"no {role} in library for this task")

    # 2) missing METHOD skills (SA/HMC/stat-phys) — check catalogs, else skills.sh request
    cur = _load_cat("curated_skills.json")
    all_skill_text = ""
    if isinstance(cur, dict):
        all_skill_text = " ".join(str(s) for v in cur.get("domains", {}).values() for s in v).lower()
    for m in wanted_methods:
        long = {"SA": "simulated annealing", "HMC": "hamiltonian monte carlo",
                "MCMC": "markov chain monte carlo", "stat-phys": "statistical physics",
                "MC": "monte carlo", "GD": "gradient descent"}[m]
        if long not in all_skill_text and m.lower() not in all_skill_text:
            gaps.append(f"no method-skill for {m} ({long})")
            # 2a) FIRST look in the full native APEX index (3,784 skills) via repo_bridge
            native_hits = []
            try:
                import repo_bridge
                native_hits = [{"id": h["id"], "path": h["path"]}
                               for h in repo_bridge.search_native(long, k=3)]
            except Exception:
                pass
            install_requests.append({
                "gap": f"{m} method skill",
                "native_candidates": native_hits,   # load with repo_bridge.native_skill(path)
                "action": "ASK_USER_TO_APPROVE_INSTALL",
                "discovery": {
                    "skills_sh_search": f"https://skills.sh/?q={long.replace(' ', '+')}",
                    "github_search": ("https://github.com/search?type=repositories&q=" +
                                      long.replace(' ', '+') + "+SKILL.md"),
                    "install_command": "npx skills add <owner/repo>  # after user approval",
                },
                "status": "STAGED_needs_approval",
                "fallbacks": ["MCP: science-physics-mcp (integrations)",
                              f"generate CANDIDATE via scripts/skill_forge.py create --name {long.replace(' ','-')}"],
            })

    # 3) surface relevant MCPs
    mcps = _load_cat("mcp_registry.json")
    for mcp in mcps:
        dom = mcp.get("domain", "").lower()
        if dom and any(w in task.lower() for w in [dom, dom.split("-")[0]]):
            mcp_suggestions.append(mcp["id"])
    if ("physics" in task.lower() or "statistical" in task.lower()) and not mcp_suggestions:
        phys = [m["id"] for m in mcps if "physics" in m.get("id", "").lower()]
        mcp_suggestions += phys

    return {"task": task, "constellation": con["merged_by_type"], "gaps": gaps,
            "install_requests": install_requests, "mcp_suggestions": sorted(set(mcp_suggestions))}
