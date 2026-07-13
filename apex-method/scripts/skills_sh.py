#!/usr/bin/env python3
"""
skills_sh.py — skills.sh marketplace discovery with a popularity quality bar.

WHY THIS EXISTS:
  The skill could search GitHub and the native library, but the richest source of
  battle-tested skills is the skills.sh leaderboard (Vercel's `npx skills` registry,
  ~26k-star CLI), which ranks skills by TOTAL INSTALLS. This module queries that
  registry, applies a MIN-INSTALLS quality bar (default 1000 — the same bar the
  official `find-skills` skill recommends), and returns STAGED install candidates.
  It NEVER installs anything: it surfaces `npx skills add owner/repo` for the user
  to approve (H5), and any fetched code still goes through skill_scout's AST gate.

WHEN TO USE:
  At skill-resolution time, as the marketplace tier of the discovery cascade
  (native index → skills.sh → GitHub), especially for popular, cross-agent skills.

HOW IT WORKS:
  GET https://skills.sh/api/v1/skills?view={trending|hot}&per_page=N   (by installs)
  GET https://skills.sh/api/v1/skills?q={query}                       (fuzzy/semantic)
  GET https://skills.sh/api/v1/skills/official                        (first-party set)
  Results are filtered to installs >= min_installs and returned ranked. Read-only
  JSON only; skills.sh is on a DISCOVERY allowlist distinct from any code-exec path.

WHAT IF IT FAILS:
  - network blocked / non-allowlisted host -> {"status":"OFFLINE"|"REFUSED_HOST"};
    callers fall back to the native index + GitHub search (nothing crashes).
  - API shape drift -> best-effort field extraction; unknown fields ignored.
"""
import json
import sys
import urllib.parse
import urllib.request

API_HOSTS = ("skills.sh", "www.skills.sh")   # discovery allowlist (read-only JSON)
API_BASE = "https://skills.sh/api/v1"
MIN_INSTALLS_DEFAULT = 1000                  # the find-skills quality bar (>= 1K installs)
OFFICIAL_OWNERS = ("vercel-labs", "anthropics", "vercel", "openai", "modelcontextprotocol")


def _host_ok(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc
    return host in API_HOSTS


def _get(url: str, timeout: int = 15):
    if not _host_ok(url):
        return {"status": "REFUSED_HOST", "url": url}
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "apex-method-skill/discovery"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if not _host_ok(r.geturl()):
                return {"status": "REFUSED_REDIRECT", "url": r.geturl()}
            return {"status": "OK", "data": json.loads(r.read().decode("utf-8", errors="replace"))}
    except Exception as e:
        return {"status": "OFFLINE", "reason": str(e)[:140]}


def _installs(item: dict) -> int:
    for k in ("installs", "install_count", "total_installs", "downloads"):
        v = item.get(k)
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str) and v.replace(",", "").isdigit():
            return int(v.replace(",", ""))
    return 0


def _norm(item: dict) -> dict:
    owner = item.get("owner") or (item.get("repo", "/").split("/")[0])
    name = item.get("name") or item.get("slug") or item.get("id", "?")
    repo = item.get("repo") or (f"{owner}/{name}" if owner else name)
    return {"id": f"{owner}/{name}" if owner else name,
            "name": name, "owner": owner, "repo": repo,
            "installs": _installs(item),
            "description": (item.get("description") or "")[:200],
            "official": owner in OFFICIAL_OWNERS,
            "install_command": f"npx skills add {repo}",
            "url": item.get("url") or f"https://skills.sh/{repo}"}


def _extract_list(payload) -> list:
    if isinstance(payload, list):
        return payload
    for k in ("skills", "data", "results", "items"):
        if isinstance(payload.get(k), list):
            return payload[k]
    return []


def leaderboard(view: str = "trending", per_page: int = 25, min_installs: int = MIN_INSTALLS_DEFAULT):
    """Top skills by installs (view: trending|hot|all-time), filtered to >= min_installs."""
    r = _get(f"{API_BASE}/skills?view={urllib.parse.quote(view)}&per_page={int(per_page)}")
    if r["status"] != "OK":
        return {"status": r["status"], "candidates": [], "note": r.get("reason", "")}
    items = [_norm(x) for x in _extract_list(r["data"])]
    kept = sorted([i for i in items if i["installs"] >= min_installs],
                  key=lambda i: -i["installs"])
    return {"status": "OK", "view": view, "min_installs": min_installs,
            "candidates": kept, "below_bar": len(items) - len(kept)}


def search(query: str, per_page: int = 25, min_installs: int = MIN_INSTALLS_DEFAULT):
    """Search skills.sh (fuzzy/semantic), keeping only those over the install bar."""
    r = _get(f"{API_BASE}/skills?q={urllib.parse.quote(query)}&per_page={int(per_page)}")
    if r["status"] != "OK":
        return {"status": r["status"], "query": query, "candidates": []}
    items = [_norm(x) for x in _extract_list(r["data"])]
    kept = sorted([i for i in items if i["installs"] >= min_installs],
                  key=lambda i: -i["installs"])
    return {"status": "OK", "query": query, "min_installs": min_installs, "candidates": kept}


def official():
    """The curated first-party set (installs bar not applied — official is pre-trusted)."""
    r = _get(f"{API_BASE}/skills/official")
    if r["status"] != "OK":
        return {"status": r["status"], "candidates": []}
    return {"status": "OK", "candidates": [_norm(x) for x in _extract_list(r["data"])]}


def install_requests(query: str, min_installs: int = MIN_INSTALLS_DEFAULT, k: int = 5):
    """Discovery → STAGED install requests (H5). Never installs; surfaces the command."""
    res = search(query, min_installs=min_installs)
    if res["status"] != "OK":
        # offline fallback: give the user the ready-to-run discovery commands
        return {"status": res["status"], "requests": [{
            "gap": query, "action": "ASK_USER_TO_APPROVE_INSTALL",
            "discovery": {"skills_sh_url": f"https://skills.sh/?q={urllib.parse.quote(query)}",
                          "cli": f"npx skills find {query}",
                          "criterion": f"prefer installs >= {min_installs} + official owners"},
            "status": "STAGED_needs_approval"}]}
    reqs = []
    for c in res["candidates"][:k]:
        reqs.append({"gap": query, "skill": c["id"], "installs": c["installs"],
                     "official": c["official"], "action": "ASK_USER_TO_APPROVE_INSTALL",
                     "install_command": c["install_command"], "url": c["url"],
                     "status": "STAGED_needs_approval"})
    return {"status": "OK", "min_installs": min_installs, "requests": reqs}


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "trending"
    out = leaderboard() if q == "trending" else search(q)
    if out["status"] != "OK":
        print(f"[skills.sh {out['status']}] — offline fallback discovery:")
        print(json.dumps(install_requests(q if q != "trending" else "popular"), indent=2))
    else:
        for c in out["candidates"][:15]:
            flag = " [official]" if c["official"] else ""
            print(f"{c['installs']:>9,}  {c['id']}{flag} — {c['description'][:70]}")
