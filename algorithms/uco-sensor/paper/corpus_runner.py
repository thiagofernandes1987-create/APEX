"""
UCO Sensor — Corpus Runner (Sprint AC-1, v3.10.0 follow-up)
=============================================================
First *real* execution of the protocol in `experiments.md` (E1/E4),
replacing the synthetic/toy rows produced by `reproducibility.py` with
data extracted from an actual OSS repository's commit history.

Environment constraint
-----------------------
This sandbox blocks `git clone`/`git fetch` over the git smart-HTTP
protocol (proxy returns 403 for any non-APEX repo), but allows plain
HTTPS to `api.github.com` and `codeload.github.com`. So instead of a
real `git clone`, this module:

  1. Pulls the commit list + per-file content at each commit via the
     GitHub REST API (Contents API), restricted to one package
     sub-directory to keep request volume sane.
  2. *Replays* those snapshots, in chronological order, as real commits
     into a fresh local git repository ("shadow repo") — each replayed
     commit reuses the original SHA's date/subject as the local commit
     message/date.
  3. Hands the shadow repo to the existing, unmodified
     `scan.git_history_scanner.GitHistoryScanner` — so the temporal
     analysis pipeline (FrequencyEngine, Hurst, onset detection) runs
     exactly as it would against a real clone.
  4. Cross-references each file's detected onset_commit against the
     *real* upstream commit messages for fix/bug/security keywords
     touching that same file, as a cheap proxy for "did UCO flag decay
     before/around when maintainers actually had to fix it".
  5. Runs `sast.scanner.scan` against the latest snapshot of every file
     for a point-in-time SAST finding count (separate from the temporal
     signal).

This is intentionally a *single-repo, modest-sample* MVP (Sprint AC-1).
Scaling to the full 5-repo/200-500-commit corpus from `experiments.md`
is Sprint AC-2+, gated on this MVP producing a sane, honest report.

Usage
-----
    python paper/corpus_runner.py \\
        --owner psf --repo requests --subdir src/requests \\
        --max-commits 80 --workdir /tmp/corpus_requests \\
        --output paper/corpus_runs/requests_report.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from base64 import b64decode
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_SENSOR_API = Path(__file__).resolve().parent.parent / "sensor-api"
if str(_SENSOR_API) not in sys.path:
    sys.path.insert(0, str(_SENSOR_API))

_GITHUB_API = "https://api.github.com"
_FIX_KEYWORDS = (
    "fix", "bug", "security", "vulnerab", "cve", "exploit", "crash",
    "leak", "race", "deadlock", "overflow", "injection", "regression",
    "patch", "broken", "error", "fail",
)


# ─── GitHub API plumbing ───────────────────────────────────────────────────

def _gh_get(url: str, retries: int = 3) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "uco-sensor-corpus-runner"})
    last_exc: Optional[Exception] = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last_exc = e
        except Exception as e:
            last_exc = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GitHub API failed for {url}: {last_exc}")


@dataclass
class CommitMeta:
    sha: str
    date: str
    subject: str
    is_fixlike: bool = field(init=False)

    def __post_init__(self) -> None:
        low = self.subject.lower()
        self.is_fixlike = any(k in low for k in _FIX_KEYWORDS)


def fetch_commits(owner: str, repo: str, subdir: str, max_commits: int) -> List[CommitMeta]:
    """Newest→oldest from the API, returned oldest→newest for replay."""
    commits: List[CommitMeta] = []
    page = 1
    while len(commits) < max_commits:
        per_page = min(100, max_commits - len(commits))
        url = (f"{_GITHUB_API}/repos/{owner}/{repo}/commits"
               f"?path={subdir}&per_page={per_page}&page={page}")
        batch = _gh_get(url)
        if not batch:
            break
        for c in batch:
            commits.append(CommitMeta(
                sha=c["sha"],
                date=c["commit"]["author"]["date"],
                subject=c["commit"]["message"].splitlines()[0],
            ))
        if len(batch) < per_page:
            break
        page += 1
    return list(reversed(commits))


def list_files_at_ref(owner: str, repo: str, subdir: str, ref: str) -> List[str]:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{subdir}?ref={ref}"
    items = _gh_get(url) or []
    return [it["name"] for it in items if it.get("type") == "file" and it["name"].endswith(".py")]


def fetch_file_at_ref(owner: str, repo: str, subdir: str, filename: str, ref: str) -> Optional[str]:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{subdir}/{filename}?ref={ref}"
    data = _gh_get(url)
    if not data or "content" not in data:
        return None
    try:
        return b64decode(data["content"]).decode("utf-8", errors="replace")
    except Exception:
        return None


# ─── Shadow repo replay ─────────────────────────────────────────────────────

def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root)] + list(args),
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def build_shadow_repo(
    workdir: Path,
    owner: str,
    repo: str,
    subdir: str,
    commits: List[CommitMeta],
    files: List[str],
) -> int:
    """Replays `files` content at each commit into a fresh local git repo.

    Returns the number of commits actually created (commits that produced
    no diff vs the previous snapshot are skipped, mirroring real history
    where a commit may have touched the path for reasons outside `files`).
    """
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)
    _git(workdir, "init", "-q")
    _git(workdir, "config", "user.email", "corpus-runner@uco-sensor.local")
    _git(workdir, "config", "user.name", "UCO Sensor Corpus Runner")

    created = 0
    for cm in commits:
        changed = False
        for fname in files:
            content = fetch_file_at_ref(owner, repo, subdir, fname, cm.sha)
            target = workdir / fname
            if content is None:
                if target.exists():
                    target.unlink()
                    changed = True
                continue
            prev = target.read_text(encoding="utf-8") if target.exists() else None
            if prev != content:
                target.write_text(content, encoding="utf-8")
                changed = True
        if not changed:
            continue
        _git(workdir, "add", "-A")
        status = _git(workdir, "status", "--porcelain")
        if not status.strip():
            continue
        date_iso = cm.date.replace("Z", "+00:00")
        env_date = date_iso
        subprocess.run(
            ["git", "-C", str(workdir), "commit", "-q", "-m", f"{cm.subject}\n\nupstream-sha:{cm.sha}",
             "--date", env_date],
            check=True,
            env={"GIT_AUTHOR_DATE": env_date, "GIT_COMMITTER_DATE": env_date,
                 "PATH": __import__("os").environ.get("PATH", "")},
        )
        created += 1
    return created


def _upstream_sha_for_local_commit(workdir: Path, local_hash: str) -> Optional[str]:
    msg = _git(workdir, "show", "-s", "--format=%B", local_hash)
    for line in msg.splitlines():
        if line.startswith("upstream-sha:"):
            return line.split(":", 1)[1].strip()
    return None


# ─── Analysis ───────────────────────────────────────────────────────────────

def run_history_scan(workdir: Path, n_commits: int):
    from scan.git_history_scanner import GitHistoryScanner
    scanner = GitHistoryScanner(str(workdir), n_commits=n_commits, min_commits=5, max_workers=4)
    return scanner.scan(verbose=False)


def run_sast_snapshot(workdir: Path, files: List[str]) -> Dict[str, list]:
    from sast.scanner import scan as sast_scan
    out: Dict[str, list] = {}
    for fname in files:
        fp = workdir / fname
        if not fp.exists():
            continue
        try:
            source = fp.read_text(encoding="utf-8")
            result = sast_scan(source, ".py")
            out[fname] = [
                {"rule_id": f.rule_id, "severity": f.severity, "line": f.line, "title": f.title}
                for f in result.findings
            ]
        except Exception as e:
            out[fname] = [{"error": str(e)}]
    return out


def correlate_onset_with_fixes(
    workdir: Path,
    history_result,
    commits: List[CommitMeta],
) -> List[dict]:
    """For each file UCO flagged with an onset_commit, check whether the
    *real* upstream history contains a fix-like commit touching that file
    within a window after the onset — a cheap true-positive proxy."""
    by_sha = {c.sha: c for c in commits}
    correlations = []
    for r in history_result.file_results:
        if not r.onset_commit:
            continue
        upstream_onset = _upstream_sha_for_local_commit(workdir, r.onset_commit)
        if not upstream_onset or upstream_onset not in by_sha:
            continue
        onset_idx = [c.sha for c in commits].index(upstream_onset)
        window = commits[onset_idx:onset_idx + 15]
        fix_commits = [c for c in window if c.is_fixlike]
        correlations.append({
            "file": r.path,
            "severity": r.severity,
            "primary_error": r.primary_error,
            "hurst": round(r.hurst, 3),
            "onset_upstream_sha": upstream_onset[:12],
            "onset_subject": by_sha[upstream_onset].subject,
            "fixlike_commits_within_15_after_onset": [
                {"sha": c.sha[:12], "subject": c.subject} for c in fix_commits
            ],
            "has_corroborating_fix": len(fix_commits) > 0,
        })
    return correlations


# ─── Report ─────────────────────────────────────────────────────────────────

def build_report(
    owner: str, repo: str, subdir: str,
    commits: List[CommitMeta], n_replayed: int,
    history_result, sast_findings: Dict[str, list],
    correlations: List[dict],
) -> dict:
    total_sast = sum(len(v) for v in sast_findings.values() if v and "error" not in v[0])
    return {
        "repo": f"{owner}/{repo}", "subdir": subdir,
        "upstream_commits_fetched": len(commits),
        "local_commits_replayed": n_replayed,
        "files_analyzed": history_result.n_files,
        "temporal": history_result.to_dict(),
        "sast_point_in_time": {
            "total_findings": total_sast,
            "by_file": sast_findings,
        },
        "onset_fix_correlation": correlations,
        "summary": {
            "critical_files": len(history_result.critical_files),
            "warning_files": len(history_result.warning_files),
            "files_with_corroborating_fix": sum(1 for c in correlations if c["has_corroborating_fix"]),
            "files_with_onset_but_no_corroborating_fix": sum(
                1 for c in correlations if not c["has_corroborating_fix"]
            ),
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--subdir", required=True)
    ap.add_argument("--max-commits", type=int, default=80)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    workdir = Path(args.workdir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    print(f"[1/5] Fetching up to {args.max_commits} commits for {args.owner}/{args.repo}:{args.subdir} ...")
    commits = fetch_commits(args.owner, args.repo, args.subdir, args.max_commits)
    print(f"      {len(commits)} commits fetched.")

    print(f"[2/5] Listing files at HEAD of sample ...")
    files = list_files_at_ref(args.owner, args.repo, args.subdir, commits[-1].sha)
    print(f"      {len(files)} .py files: {files}")

    print(f"[3/5] Replaying snapshots into shadow repo at {workdir} ...")
    n_replayed = build_shadow_repo(workdir, args.owner, args.repo, args.subdir, commits, files)
    print(f"      {n_replayed} local commits created.")

    print(f"[4/5] Running GitHistoryScanner + SAST snapshot ...")
    history_result = run_history_scan(workdir, n_commits=n_replayed)
    sast_findings = run_sast_snapshot(workdir, files)

    print(f"[5/5] Correlating onset commits with upstream fix-like commits ...")
    correlations = correlate_onset_with_fixes(workdir, history_result, commits)

    report = build_report(
        args.owner, args.repo, args.subdir, commits, n_replayed,
        history_result, sast_findings, correlations,
    )
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport written to {output}")
    print(history_result.summary())


if __name__ == "__main__":
    main()
