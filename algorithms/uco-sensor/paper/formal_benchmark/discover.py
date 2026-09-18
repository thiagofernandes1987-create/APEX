#!/usr/bin/env python3
"""
Discover a repository-independent formal benchmark corpus from public GitHub PRs.

Primary design constraints:
- at most one primary event per repository;
- explicit merged PR boundary (base SHA -> merge/head SHA);
- event categories are query-backed, not inferred after looking at UCO output;
- generic "fix" title matches are intentionally excluded from the primary corpus;
- only modified source files supported by UCO are admitted.

Requires GITHUB_TOKEN for practical rate limits.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional

API = "https://api.github.com"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
UA = "uco-sensor-formal-benchmark/0.1"

SUPPORTED_EXT = {
    ".py", ".pyw", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".go", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".cs", ".rs",
    ".rb", ".php", ".swift", ".kt", ".kts", ".scala", ".groovy", ".sh",
    ".ps1", ".lua", ".pl", ".hs", ".erl", ".ex", ".exs", ".fs", ".ml",
    ".clj", ".dart", ".jl", ".zig", ".nim", ".cr", ".d", ".vb", ".f90",
    ".sol", ".hcl", ".tf",
}
EXCLUDE_PARTS = (
    "/test/", "/tests/", "/spec/", "/vendor/", "/node_modules/", "/generated/",
    "/fixtures/", "/examples/", ".min.js", "_test.", "test_", ".lock",
)

# Split across time to prevent "latest popular repos only" sampling.
TIME_WINDOWS = (
    ("2019-01-01", "2021-12-31"),
    ("2022-01-01", "2023-12-31"),
    ("2024-01-01", "2026-09-17"),
)

# The query itself is part of the preregistered evidence definition.
EVENT_QUERIES = {
    "security": [
        ('"CVE-" in:title is:pr is:merged', "gold"),
        ('"GHSA-" in:title is:pr is:merged', "gold"),
        ('label:security is:pr is:merged', "gold"),
    ],
    "bugfix": [
        ("label:bug is:pr is:merged", "silver"),
    ],
    "regression": [
        ("regression in:title is:pr is:merged", "silver"),
    ],
    "refactor": [
        ("refactor in:title is:pr is:merged", "silver"),
    ],
    "revert": [
        ("revert in:title is:pr is:merged", "gold"),
    ],
}


def _headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def gh_get(url: str, *, search: bool = False, retries: int = 4):
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=_headers())
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                # Search API is rate-limited separately; a small delay keeps a
                # 1,000-repo discovery run polite and reproducible.
                if search:
                    time.sleep(2.05)
                return data
        except Exception as exc:
            last = exc
            time.sleep(2.0 * (attempt + 1))
    raise RuntimeError(f"GitHub GET failed after {retries} attempts: {url}: {last}")


def search_prs(query: str, max_pages: int = 10) -> Iterable[dict]:
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "order": "desc",
        })
        data = gh_get(f"{API}/search/issues?{params}", search=True)
        items = data.get("items", [])
        if not items:
            return
        yield from items
        if len(items) < 100:
            return


def choose_source_file(files: List[dict]) -> Optional[str]:
    ranked = []
    for f in files:
        path = f.get("filename", "")
        if f.get("status") != "modified":
            continue
        low = "/" + path.lower()
        if any(part in low for part in EXCLUDE_PARTS):
            continue
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXT:
            continue
        changes = int(f.get("changes", 0) or 0)
        if changes <= 0 or changes > 1200:
            continue
        ranked.append((changes, path))
    if not ranked:
        return None
    # Prefer a substantive but bounded source change.
    ranked.sort(key=lambda x: (abs(x[0] - 80), x[1]))
    return ranked[0][1]


def build_event(item: dict, event_type: str, tier: str) -> Optional[dict]:
    pr_url = item.get("pull_request", {}).get("url")
    if not pr_url:
        return None
    pr = gh_get(pr_url)
    if not pr.get("merged_at"):
        return None

    base_sha = (pr.get("base") or {}).get("sha")
    head_sha = pr.get("merge_commit_sha") or (pr.get("head") or {}).get("sha")
    repo_full = (pr.get("base") or {}).get("repo", {}).get("full_name")
    number = pr.get("number")
    if not (base_sha and head_sha and repo_full and number):
        return None

    files = gh_get(f"{pr_url}/files?per_page=100")
    path = choose_source_file(files if isinstance(files, list) else [])
    if not path:
        return None

    title = (pr.get("title") or "").strip()
    return {
        "id": f"{event_type}:{repo_full}#{number}",
        "repo": repo_full,
        "path": path,
        "event_type": event_type,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "pr_number": int(number),
        "evidence_tier": tier,
        "seed_dev": False,
        "source_url": pr.get("html_url"),
        "label": title[:300],
        "merged_at": pr.get("merged_at"),
    }


def discover(target_repos: int) -> List[dict]:
    if target_repos < 1:
        return []
    categories = list(EVENT_QUERIES)
    quota = max(1, target_repos // len(categories))
    events: List[dict] = []
    seen_repos = set()

    # First pass: try to preserve category diversity.
    for event_type in categories:
        got = 0
        for start, end in TIME_WINDOWS:
            if got >= quota:
                break
            for base_query, tier in EVENT_QUERIES[event_type]:
                if got >= quota:
                    break
                query = f"{base_query} merged:{start}..{end}"
                for item in search_prs(query, max_pages=10):
                    if got >= quota or len(events) >= target_repos:
                        break
                    repo_url = item.get("repository_url", "")
                    repo_guess = "/".join(repo_url.rstrip("/").split("/")[-2:])
                    if not repo_guess or repo_guess in seen_repos:
                        continue
                    try:
                        event = build_event(item, event_type, tier)
                    except Exception as exc:
                        print(f"[skip] {repo_guess}: {type(exc).__name__}: {exc}")
                        continue
                    if not event or event["repo"] in seen_repos:
                        continue
                    seen_repos.add(event["repo"])
                    events.append(event)
                    got += 1
                    print(f"[{len(events):04d}/{target_repos}] {event_type:<10} "
                          f"{event['repo']}#{event['pr_number']} {event['path']}")
                if len(events) >= target_repos:
                    break

    # Second pass: fill any shortfall without changing evidence definitions.
    if len(events) < target_repos:
        for event_type in categories:
            for start, end in TIME_WINDOWS:
                for base_query, tier in EVENT_QUERIES[event_type]:
                    query = f"{base_query} merged:{start}..{end}"
                    for item in search_prs(query, max_pages=10):
                        if len(events) >= target_repos:
                            break
                        repo_url = item.get("repository_url", "")
                        repo_guess = "/".join(repo_url.rstrip("/").split("/")[-2:])
                        if not repo_guess or repo_guess in seen_repos:
                            continue
                        try:
                            event = build_event(item, event_type, tier)
                        except Exception:
                            continue
                        if not event or event["repo"] in seen_repos:
                            continue
                        seen_repos.add(event["repo"])
                        events.append(event)
                    if len(events) >= target_repos:
                        break
                if len(events) >= target_repos:
                    break
            if len(events) >= target_repos:
                break

    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-repos", type=int, default=100)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    events = discover(args.target_repos)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n")
    counts = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    print(json.dumps({
        "requested": args.target_repos,
        "discovered": len(events),
        "distinct_repos": len({e["repo"] for e in events}),
        "by_type": counts,
        "output": str(out),
    }, indent=2))
    return 0 if len(events) >= min(args.target_repos, 10) else 2


if __name__ == "__main__":
    raise SystemExit(main())
