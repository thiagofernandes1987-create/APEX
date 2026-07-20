#!/usr/bin/env python3
"""
github_skills.py — GitHub-native skill discovery (trusted vendors + stars + semantic search).

WHY THIS EXISTS:
  skills.sh is a convenient index ("already filtered to what IS a skill"), but it is a single
  network dependency that a locked-down environment can block (measured: 403 CONNECT policy denial).
  The underlying truth lives on GitHub: a skill is a repo/subdir with a `SKILL.md` (name +
  description + when-to-use). This module discovers skills DIRECTLY from GitHub — ranked by a
  TRUSTED-VENDOR allowlist (anthropics, vercel-labs, microsoft, supabase, openai, ...), by STARS
  (popularity), and by SEMANTIC match to the task — so discovery survives without skills.sh.

WHEN TO USE:
  As the marketplace tier of the discovery cascade when skills.sh is blocked/undesired, or to
  prefer first-party vendor skills. Local-installed skills (~/.claude/skills) still come first.

HOW IT WORKS:
  1. ENUMERATE candidate SKILL.md files from trusted-vendor skill-hub repos:
       - primary : GitHub git-tree API (repos/{o}/{r}/git/trees/{ref}?recursive=1) — needs API access
       - fallback: parse the repo README (raw) for skill-directory links — works with raw-only access
  2. FETCH each SKILL.md via skill_scout.fetch_text (raw allowlist, redirect re-check, size cap).
  3. PARSE (skill_scout.parse_skill_md) -> name + description.
  4. RANK semantically (_tfidf.semantic_rank: query vs description) and by stars + trust tier.
  5. Return STAGED candidates. Nothing is installed or executed: run skill_scout.evaluate() on a
     pick to AST-scan it, then the H5 human gate approves `npx skills add owner/repo`.

WHAT IF IT FAILS:
  - GitHub API blocked          -> falls back to README enumeration (raw); if that too is offline,
                                   returns {"status":"OFFLINE"} and the caller uses local/native tiers.
  - a repo/README unreachable   -> that vendor is skipped, others still return (best-effort).
  - API shape drift / bad JSON  -> ignored per-item; never raises.
"""
import json
import re
import urllib.request
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
import skill_scout
import _tfidf

# Trusted skill-hub repos (curated seed; "what IS a skill" == has SKILL.md). NOTE: vercel-labs/skills
# is the CLI (`npx skills`), NOT a skill collection — the actual skills live in vercel-labs/agent-skills.
SKILL_HUBS = [
    {"owner": "anthropics", "repo": "skills", "ref": "main", "prefix": "skills/"},
    {"owner": "vercel-labs", "repo": "agent-skills", "ref": "main", "prefix": "skills/"},
    {"owner": "microsoft", "repo": "skills", "ref": "main", "prefix": "skills/"},  # catalog layout: needs tree API
]

# The exact skill-container directories the `npx skills` CLI walks (from vercel-labs/skills README,
# "Skill Discovery"). We adopt the SAME list so the git-tree walk finds skills wherever the ecosystem
# convention puts them — flat `skills/<name>/SKILL.md` and catalog `skills/<cat>/<name>/SKILL.md`.
CONTAINER_DIRS = ("", "skills/", "skills/.curated/", "skills/.experimental/", "skills/.system/",
                  ".claude/skills/", ".agents/skills/", "data/skills/")

# Verified individual skills (raw-fetchable) — the always-available fallback so discovery returns a
# real list even when the GitHub API AND README enumeration are both blocked (as in a locked sandbox).
CURATED_SKILLS = [
    # anthropics/skills — verified live (HTTP 200), 2026-07
    "anthropics/skills/main/skills/pdf/SKILL.md",
    "anthropics/skills/main/skills/docx/SKILL.md",
    "anthropics/skills/main/skills/pptx/SKILL.md",
    "anthropics/skills/main/skills/xlsx/SKILL.md",
    "anthropics/skills/main/skills/mcp-builder/SKILL.md",
    "anthropics/skills/main/skills/brand-guidelines/SKILL.md",
    "anthropics/skills/main/skills/canvas-design/SKILL.md",
    "anthropics/skills/main/skills/webapp-testing/SKILL.md",
    "anthropics/skills/main/skills/slack-gif-creator/SKILL.md",
    "anthropics/skills/main/skills/frontend-design/SKILL.md",
    "anthropics/skills/main/skills/algorithmic-art/SKILL.md",
    "anthropics/skills/main/skills/skill-creator/SKILL.md",
    # vercel-labs/agent-skills — verified live (HTTP 200)
    "vercel-labs/agent-skills/main/skills/web-design-guidelines/SKILL.md",
    "vercel-labs/agent-skills/main/skills/writing-guidelines/SKILL.md",
]
TRUSTED_VENDORS = skill_scout.OFFICIAL_OWNERS
GH_API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"


def _api_get(path, timeout=15):
    """GitHub API GET with graceful degradation. Returns parsed JSON or None (blocked/offline)."""
    req = urllib.request.Request(GH_API + path, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "apex-method-discovery",
        "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if r.status != 200:
                return None
            return json.loads(r.read(2_000_000).decode("utf-8", "replace"))
    except Exception:
        return None


def repo_stars(owner, repo):
    """Stargazers count for popularity ranking, or None when the API is unavailable."""
    d = _api_get(f"/repos/{owner}/{repo}")
    return d.get("stargazers_count") if isinstance(d, dict) else None


def _skillmd_urls_via_api(hub):
    """Enumerate SKILL.md paths via the git-tree API (primary). None if API blocked."""
    d = _api_get(f"/repos/{hub['owner']}/{hub['repo']}/git/trees/{hub['ref']}?recursive=1")
    if not isinstance(d, dict) or not isinstance(d.get("tree"), list):
        return None
    out = []
    for e in d["tree"]:
        p = e.get("path", "")
        if p.endswith("SKILL.md"):
            out.append(f"{RAW}/{hub['owner']}/{hub['repo']}/{hub['ref']}/{p}")
    return out


def _skillmd_urls_via_readme(hub):
    """Fallback (raw-only): parse the repo README for skill-directory links -> <dir>/SKILL.md.
    Works in environments where the GitHub API is blocked but raw.githubusercontent is reachable."""
    readme = f"{RAW}/{hub['owner']}/{hub['repo']}/{hub['ref']}/README.md"
    try:
        md = skill_scout.fetch_text(readme)
    except Exception:
        return []
    dirs = set()
    # markdown links to skill dirs, e.g. [docx](./skills/docx) or (skills/docx)
    for m in re.findall(r"\]\((?:\./)?(" + re.escape(hub["prefix"]) + r"[A-Za-z0-9_-]+)/?\)", md):
        dirs.add(m.strip("/"))
    # github tree links: .../tree/<ref>/<path>
    for m in re.findall(r"github\.com/" + re.escape(hub["owner"] + "/" + hub["repo"])
                        + r"/tree/[^/]+/(" + re.escape(hub["prefix"]) + r"[A-Za-z0-9_/-]+)", md):
        dirs.add(m.strip("/"))
    return [f"{RAW}/{hub['owner']}/{hub['repo']}/{hub['ref']}/{d}/SKILL.md" for d in sorted(dirs)]


def find_by_owner(owner, ref="main", timeout=15):
    """The CLI's `--owner` mechanism: enumerate an org/user's repos via the GitHub API and collect
    every SKILL.md across them. Returns a list of raw SKILL.md URLs, or [] when the API is blocked
    (this sandbox blocks external-owner API access — the curated/hub tiers cover that case)."""
    repos = _api_get(f"/users/{owner}/repos?per_page=100&sort=updated")
    if not isinstance(repos, list):
        return []
    urls = []
    for r in repos:
        name = r.get("name")
        if not name:
            continue
        urls.extend(_skillmd_urls_via_api({"owner": owner, "repo": name,
                                           "ref": r.get("default_branch") or ref, "prefix": ""}) or [])
    return urls


def _candidates(hubs, owners=None):
    """All candidate SKILL.md raw URLs: curated (always) + hub enumeration (API tree -> README
    fallback) + optional owner-wide enumeration (API). De-duplicated, order-stable."""
    urls = [f"{RAW}/{p}" for p in CURATED_SKILLS]          # always-available baseline
    for hub in hubs:
        got = _skillmd_urls_via_api(hub)
        if got is None:                       # API blocked -> raw README enumeration (best-effort)
            got = _skillmd_urls_via_readme(hub)
        urls.extend(got or [])
    for owner in (owners or []):
        urls.extend(find_by_owner(owner))
    return list(dict.fromkeys(urls))          # de-dup, keep order


def search(query, hubs=None, owners=None, min_stars=0, k=5, max_fetch=40):
    """Discover trusted-vendor skills on GitHub, ranked by SEMANTIC match + stars + trust tier.
    `owners` (list of GitHub orgs/users) triggers the CLI-style owner-wide enumeration via the API.

    Returns {"status": "OK"|"OFFLINE", "query", "results": [ranked staged candidates]}.
    Never installs or executes anything — each result is a staged pointer for skill_scout.evaluate
    + the H5 approval gate."""
    hubs = hubs or SKILL_HUBS
    urls = _candidates(hubs, owners=owners)[:max_fetch]
    if not urls:
        return {"status": "OFFLINE", "query": query, "results": [],
                "reason": "no candidates (GitHub API blocked and README enumeration offline)"}
    parsed = []
    for u in urls:
        try:
            meta = skill_scout.parse_skill_md(skill_scout.fetch_text(u))
        except Exception:
            continue
        if meta.get("name") in (None, "?") and not meta.get("description"):
            continue
        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+)/([^/]+)/", u)
        owner, repo = (m.group(1), m.group(2)) if m else ("?", "?")
        parsed.append({"source": u, "owner": owner, "repo": repo,
                       "name": meta.get("name"), "description": meta.get("description", ""),
                       "trust_tier": skill_scout.trust_tier(u)})
    if not parsed:
        return {"status": "OFFLINE", "query": query, "results": [],
                "reason": "candidates found but none fetchable/parseable"}
    # semantic ranking: query vs each description (char-n-gram; language-robust, no heavy deps).
    # semantic_rank returns (scores, backend_used).
    scores, _backend = _tfidf.semantic_rank(query, [p["description"] or p["name"] or "" for p in parsed])
    # stars (best-effort; None when API blocked) — cached per repo
    star_cache = {}
    for p, s in zip(parsed, scores):
        p["semantic"] = round(float(s), 4)
        rk = (p["owner"], p["repo"])
        if rk not in star_cache:
            star_cache[rk] = repo_stars(*rk)
        p["stars"] = star_cache[rk]
        p["trusted"] = p["owner"].lower() in {v.lower() for v in TRUSTED_VENDORS}
    # filter by stars bar (only when stars known), then rank: semantic first, stars/trust as tiebreak
    ranked = [p for p in parsed if (p["stars"] is None or p["stars"] >= min_stars)]
    ranked.sort(key=lambda p: (p["semantic"], (p["stars"] or 0), p["trusted"]), reverse=True)
    return {"status": "OK", "query": query, "candidates_scanned": len(parsed),
            "results": ranked[:k], "gate": "each pick still needs skill_scout.evaluate + H5"}


def discover(query, k=3, **kw):
    """search() + run skill_scout.evaluate (AST security scan) on the top-k picks — the full
    'find -> semantic rank -> safe stage' flow. Still never installs; H5 remains the boundary."""
    res = search(query, k=k, **kw)
    if res["status"] != "OK":
        return res
    for r in res["results"]:
        try:
            ev = skill_scout.evaluate(r["source"])
            r["scan_status"] = ev.get("status")
            r["ast_security"] = (ev.get("checks") or {}).get("ast_security")
        except Exception as e:
            r["scan_status"] = f"SCAN_ERROR: {str(e)[:50]}"
    return res


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "work with pdf files: extract text and fill forms"
    out = search(q)
    print(f"STATUS {out['status']} | query: {q}")
    for r in out.get("results", []):
        print(f"  [{r['semantic']:.3f}] {r['owner']}/{r['repo']} :: {r['name']} "
              f"(★{r.get('stars')}, {r['trust_tier']})")
