#!/usr/bin/env python3
"""
Discover a repository-independent formal benchmark corpus from public GitHub PRs.

Scalable design:
- GitHub Search REST only discovers PR node IDs.
- GraphQL hydrates PR metadata + changed files in batches (no 2 REST calls/PR).
- at most one primary event per repository;
- exact merged PR boundary (base SHA -> merge/head SHA);
- query-backed event categories fixed before UCO output is observed;
- generic "fix" title matches are excluded from the primary corpus.

Requires GITHUB_TOKEN.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"
TOKEN = os.environ.get("GITHUB_TOKEN", "")
UA = "uco-sensor-formal-benchmark/0.2"

SUPPORTED_EXT = {
    ".py", ".pyw", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx",
    ".java", ".go", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp", ".cs", ".rs",
    ".rb", ".php", ".swift", ".kt", ".kts", ".scala", ".groovy", ".sh",
    ".ps1", ".lua", ".pl", ".hs", ".erl", ".ex", ".exs", ".fs", ".ml",
    ".clj", ".dart", ".jl", ".zig", ".nim", ".cr", ".d", ".vb", ".f90",
    ".sol", ".hcl", ".tf",
}
EXCLUDE_PARTS = (
    "/test/", "/tests/", "/__tests__/", "/spec/", "/testing/",
    "/functionaltest/", "/integrationtest/", "/unittest/", "/cypress/", "/e2e/",
    "/testdata/", "/vendor/", "/node_modules/", "/generated/", "/fixtures/",
    "/examples/", ".min.js", "_test.", "test_", ".test.", ".spec.", ".lock",
)

TIME_WINDOWS = (
    ("2019-01-01", "2021-12-31"),
    ("2022-01-01", "2023-12-31"),
    ("2024-01-01", "2026-09-17"),
)

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
# Repositories used in the historical 19-case development corpus are excluded
# entirely from the formal benchmark, not merely the exact CVE tuples.
EXCLUDED_REPOS = {
    "psf/requests", "scrapy/scrapy", "pallets/flask", "celery/celery",
    "tiangolo/fastapi", "curl/curl", "golang/go", "axios/axios",
    "spring-projects/spring-framework", "rust-lang/regex", "etcd-io/etcd",
    "tokio-rs/tokio", "netty/netty", "laravel/framework", "rails/rails",
    "dotnet/runtime", "git/git", "lodash/lodash",
}
# Need at least 14 pre-event path-touching commits: Granger needs 9 samples,
# controls start at index>=8, and ±5 event exclusion still leaves >=1 control.
MIN_PRE_EVENT_PATH_COMMITS = 14



def _headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": UA}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def _request_json(url: str, *, body: Optional[dict] = None, retries: int = 5):
    last = None
    payload = None if body is None else json.dumps(body).encode("utf-8")
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=payload, headers={
                    **_headers(),
                    **({"Content-Type": "application/json"} if payload else {}),
                },
                method="POST" if payload else "GET",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            last = exc
            time.sleep(min(20.0, 1.5 * (attempt + 1)))
    raise RuntimeError(f"GitHub request failed: {url}: {last}")


def search_pr_nodes(query: str, max_pages: int = 10) -> Iterable[Tuple[str, str]]:
    """Yield (node_id, repository_guess). Search REST rate is 30 req/min."""
    for page in range(1, max_pages + 1):
        params = urllib.parse.urlencode({
            "q": query,
            "per_page": 100,
            "page": page,
            "sort": "updated",
            "order": "desc",
        })
        data = _request_json(f"{API}/search/issues?{params}")
        items = data.get("items", [])
        for item in items:
            node_id = item.get("node_id")
            repo_url = item.get("repository_url", "")
            repo_guess = "/".join(repo_url.rstrip("/").split("/")[-2:])
            if node_id and repo_guess:
                yield node_id, repo_guess
        if len(items) < 100:
            return
        # Authenticated Search API is normally 30 requests/minute.
        time.sleep(2.05)


_GQL = r"""
query($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on PullRequest {
      number
      title
      url
      merged
      mergedAt
      baseRefOid
      headRefOid
      mergeCommit { oid }
      repository { nameWithOwner }
      files(first: 50) {
        totalCount
        nodes {
          path
          changeType
          additions
          deletions
        }
      }
    }
  }
}
"""


def hydrate_prs(node_ids: Sequence[str]) -> List[dict]:
    if not node_ids:
        return []
    data = _request_json(GRAPHQL, body={
        "query": _GQL,
        "variables": {"ids": list(node_ids)},
    })
    if data.get("errors"):
        raise RuntimeError("GraphQL: " + json.dumps(data["errors"])[:1200])
    return [x for x in data.get("data", {}).get("nodes", []) if x]


def choose_source_file(files: List[dict]) -> Optional[dict]:
    ranked = []
    for f in files:
        path = f.get("path", "")
        if str(f.get("changeType", "")).upper() != "MODIFIED":
            continue
        low = "/" + path.lower()
        base = Path(path).name.lower()
        if any(part in low for part in EXCLUDE_PARTS):
            continue
        if base.endswith(("test.java", "tests.java", "spec.js", "spec.ts", "test.js", "test.ts")):
            continue
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED_EXT:
            continue
        additions = int(f.get("additions", 0) or 0)
        deletions = int(f.get("deletions", 0) or 0)
        changes = additions + deletions
        if changes <= 0 or changes > 800:
            continue
        ranked.append((changes, path, additions, deletions))
    if not ranked:
        return None
    # Largest bounded production-source delta is the most defensible single
    # representative of a multi-file PR. Controls are later matched on diff size.
    ranked.sort(key=lambda x: (-x[0], x[1]))
    changes, path, additions, deletions = ranked[0]
    return {
        "path": path,
        "changes": changes,
        "additions": additions,
        "deletions": deletions,
    }


def build_event(pr: dict, event_type: str, tier: str) -> Optional[dict]:
    if not pr.get("merged"):
        return None
    repo_full = (pr.get("repository") or {}).get("nameWithOwner")
    base_sha = pr.get("baseRefOid")
    head_sha = (pr.get("mergeCommit") or {}).get("oid") or pr.get("headRefOid")
    number = pr.get("number")
    if not (repo_full and base_sha and head_sha and number):
        return None
    file_conn = pr.get("files") or {}
    if int(file_conn.get("totalCount", 0) or 0) > 50:
        return None
    files = file_conn.get("nodes") or []
    chosen = choose_source_file(files)
    if not chosen:
        return None
    return {
        "id": f"{event_type}:{repo_full}#{number}",
        "repo": repo_full,
        "path": chosen["path"],
        "file_changes": chosen["changes"],
        "file_additions": chosen["additions"],
        "file_deletions": chosen["deletions"],
        "pr_files": int(file_conn.get("totalCount", 0) or 0),
        "event_type": event_type,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "pr_number": int(number),
        "evidence_tier": tier,
        "seed_dev": False,
        "source_url": pr.get("url"),
        "label": (pr.get("title") or "").strip()[:300],
        "merged_at": pr.get("mergedAt"),
    }



def _history_depth_batch(events: Sequence[dict]) -> List[int]:
    """Return pre-event path history depth (capped at MIN_PRE_EVENT_PATH_COMMITS).

    One GraphQL request checks many repository/path/base tuples, avoiding a
    clone merely to learn that a path is too young for temporal ablation.
    """
    if not events:
        return []
    fields = []
    for i, e in enumerate(events):
        owner, name = e["repo"].split("/", 1)
        fields.append(
            f'q{i}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ '
            f'object(oid: {json.dumps(e["base_sha"])}) {{ ... on Commit {{ '
            f'history(first: {MIN_PRE_EVENT_PATH_COMMITS}, path: {json.dumps(e["path"])}) '
            f'{{ nodes {{ oid }} }} }} }} }}'
        )
    query = "query {\n" + "\n".join(fields) + "\n}"
    data = _request_json(GRAPHQL, body={"query": query})
    if data.get("errors"):
        raise RuntimeError("GraphQL history: " + json.dumps(data["errors"])[:1200])
    root = data.get("data") or {}
    depths = []
    for i in range(len(events)):
        obj = ((root.get(f"q{i}") or {}).get("object") or {})
        hist = (obj.get("history") or {}).get("nodes") or []
        depths.append(len(hist))
    return depths


def _eligible_history(events: Sequence[dict]) -> List[dict]:
    out: List[dict] = []
    for start in range(0, len(events), 20):
        batch = list(events[start:start + 20])
        depths = _history_depth_batch(batch)
        for e, depth in zip(batch, depths):
            e = dict(e)
            e["pre_event_path_commits"] = int(depth)
            if depth >= MIN_PRE_EVENT_PATH_COMMITS:
                out.append(e)
    return out


def _candidate_stream(event_type: str):
    seen_nodes = set()
    for start, end in TIME_WINDOWS:
        for base_query, tier in EVENT_QUERIES[event_type]:
            query = f"{base_query} merged:{start}..{end}"
            batch: List[str] = []
            tier_by_node: Dict[str, str] = {}
            repo_hint: Dict[str, str] = {}
            for node_id, repo in search_pr_nodes(query, max_pages=10):
                if node_id in seen_nodes:
                    continue
                seen_nodes.add(node_id)
                batch.append(node_id)
                tier_by_node[node_id] = tier
                repo_hint[node_id] = repo
                if len(batch) >= 40:
                    prs = hydrate_prs(batch)
                    for pr in prs:
                        yield pr, tier
                    batch.clear()
                    tier_by_node.clear()
                    repo_hint.clear()
            if batch:
                prs = hydrate_prs(batch)
                for pr in prs:
                    yield pr, tier


def discover(target_repos: int) -> List[dict]:
    categories = list(EVENT_QUERIES)
    quota = max(1, target_repos // len(categories))
    events: List[dict] = []
    seen_repos = set(EXCLUDED_REPOS)
    rejected_repos = set()

    def collect(event_type: str, wanted: int) -> int:
        accepted = 0
        pending: List[dict] = []
        pending_repos = set()

        def flush() -> int:
            nonlocal pending, pending_repos, accepted
            if not pending:
                return 0
            batch = pending
            pending = []
            pending_repos = set()
            try:
                eligible = _eligible_history(batch)
            except Exception as exc:
                print(f"[history-screen-error] {event_type}: {exc}", flush=True)
                for e in batch:
                    rejected_repos.add(e["repo"])
                return 0
            eligible_repos = {e["repo"] for e in eligible}
            for e in batch:
                if e["repo"] not in eligible_repos:
                    rejected_repos.add(e["repo"])
            n_new = 0
            for event in eligible:
                if accepted >= wanted or len(events) >= target_repos:
                    break
                if event["repo"] in seen_repos:
                    continue
                seen_repos.add(event["repo"])
                events.append(event)
                accepted += 1
                n_new += 1
                print(
                    f"[{len(events):04d}/{target_repos}] {event_type:<10} "
                    f"{event['repo']}#{event['pr_number']} {event['path']} "
                    f"history={event['pre_event_path_commits']}",
                    flush=True,
                )
            return n_new

        for pr, tier in _candidate_stream(event_type):
            if accepted >= wanted or len(events) >= target_repos:
                break
            event = build_event(pr, event_type, tier)
            if not event:
                continue
            if event["repo"] in seen_repos or event["repo"] in rejected_repos or event["repo"] in pending_repos:
                continue
            pending.append(event)
            pending_repos.add(event["repo"])
            if len(pending) >= 20:
                flush()
        if accepted < wanted and pending:
            flush()
        return accepted

    # Balanced first pass.
    for event_type in categories:
        collect(event_type, quota)
        if len(events) >= target_repos:
            break

    # Fill shortfall without changing the evidence definitions.
    if len(events) < target_repos:
        for event_type in categories:
            need = target_repos - len(events)
            if need <= 0:
                break
            collect(event_type, need)

    return events


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-repos", type=int, default=100)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    if not TOKEN:
        raise SystemExit("GITHUB_TOKEN is required for formal discovery")

    t0 = time.perf_counter()
    events = discover(args.target_repos)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n")
    counts = {}
    for e in events:
        counts[e["event_type"]] = counts.get(e["event_type"], 0) + 1
    summary = {
        "requested": args.target_repos,
        "discovered": len(events),
        "distinct_repos": len({e["repo"] for e in events}),
        "by_type": counts,
        "elapsed_s": round(time.perf_counter() - t0, 2),
        "output": str(out),
    }
    print(json.dumps(summary, indent=2), flush=True)
    # Formal scale requires at least 500; discovery itself succeeds if it can
    # build a useful pilot, while evaluate.py decides formal vs pilot.
    return 0 if len(events) >= min(args.target_repos, 100) else 2


if __name__ == "__main__":
    raise SystemExit(main())
