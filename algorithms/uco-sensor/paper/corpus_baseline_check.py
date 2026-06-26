"""
UCO Sensor — Corpus Baseline / Control Check (Sprint AC-2)
=============================================================
`corpus_runner.py`'s ``onset_fix_correlation`` reports whether a
fix-like commit appears within 15 commits after a detected onset.
Sprint AC-2 found that metric alone is **not discriminative**: in an
actively-maintained OSS repo, almost *any* 15-commit window on a file
contains something matching the fix-keyword heuristic. This script
makes that explicit by computing:

  1. ``P(window)`` — probability that a random window of W consecutive
     commits on the file's commit-filtered history contains a fix-like
     commit (the "noise floor" the correlation metric must beat).
  2. A controlled comparison: mean distance-to-nearest-fix-like-commit
     anchored at UCO's onset commits vs. anchored at random commits.
     If onset-anchored distance is not meaningfully *smaller* than the
     random control, the onset signal carries no demonstrated
     fix-prediction value yet.

Requires the shadow repo + report JSON already produced by
`corpus_runner.py` for the same repo (same `--workdir`/`--output`).

Usage
-----
    python paper/corpus_baseline_check.py \\
        --workdir /tmp/corpus_requests --report paper/corpus_runs/requests_report.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import subprocess
from pathlib import Path

_FIX_KEYWORDS = (
    "fix", "bug", "security", "vulnerab", "cve", "exploit", "crash",
    "leak", "race", "deadlock", "overflow", "injection", "regression",
    "patch", "broken", "error", "fail",
)


def _is_fixlike(subject: str) -> bool:
    low = subject.lower()
    return any(k in low for k in _FIX_KEYWORDS)


def _upstream_order(workdir: Path) -> list:
    raw = subprocess.run(
        ["git", "-C", str(workdir), "log", "--format=%H%x01%B%x02", "--reverse"],
        capture_output=True, text=True,
    ).stdout
    out = []
    for chunk in raw.split("\x02"):
        if "\x01" not in chunk:
            continue
        _, body = chunk.split("\x01", 1)
        for line in body.splitlines():
            if line.startswith("upstream-sha:"):
                out.append(line.split(":", 1)[1].strip())
    return out


def run(workdir: Path, report_path: Path, window: int = 15, seed: int = 42) -> dict:
    subjects = subprocess.run(
        ["git", "-C", str(workdir), "log", "--format=%s", "--reverse"],
        capture_output=True, text=True,
    ).stdout.strip().splitlines()
    fixlike = [_is_fixlike(s) for s in subjects]
    n = len(subjects)

    windows = max(0, n - window + 1)
    hits = sum(1 for i in range(windows) if any(fixlike[i:i + window]))
    p_window = hits / windows if windows else float("nan")

    upstream_order = _upstream_order(workdir)
    pos = {sha: i for i, sha in enumerate(upstream_order)}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    onset_positions = []
    for c in report.get("onset_fix_correlation", []):
        for sha in upstream_order:
            if sha.startswith(c["onset_upstream_sha"]):
                onset_positions.append(pos[sha])
                break

    def dist_to_fix(i: int) -> int:
        for d in range(n - i):
            if fixlike[i + d]:
                return d
        return n - i

    onset_dists = [dist_to_fix(i) for i in onset_positions]

    random.seed(seed)
    candidates = [i for i in range(n) if i not in set(onset_positions)]
    k = min(len(onset_positions), len(candidates))
    random_sample = random.sample(candidates, k) if k else []
    random_dists = [dist_to_fix(i) for i in random_sample]

    return {
        "n_commits": n,
        "fixlike_fraction": round(sum(fixlike) / n, 3) if n else None,
        "p_window_has_fix": round(p_window, 3),
        "onset_count": len(onset_positions),
        "onset_mean_dist": round(statistics.mean(onset_dists), 2) if onset_dists else None,
        "onset_median_dist": statistics.median(onset_dists) if onset_dists else None,
        "random_mean_dist": round(statistics.mean(random_dists), 2) if random_dists else None,
        "random_median_dist": statistics.median(random_dists) if random_dists else None,
        "onset_beats_random": (
            statistics.mean(onset_dists) < statistics.mean(random_dists)
            if onset_dists and random_dists else None
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--report", required=True)
    ap.add_argument("--window", type=int, default=15)
    args = ap.parse_args()
    result = run(Path(args.workdir), Path(args.report), window=args.window)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
