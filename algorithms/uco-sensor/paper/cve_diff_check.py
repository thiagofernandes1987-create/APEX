"""
UCO Sensor — CVE Before/After Diff Check (Sprint AC-3)
=========================================================
Direct answer to "did UCO Sensor actually catch the bug, comparing the
vulnerable commit to the fixed commit" — as opposed to AC-1/AC-2's
generic onset-vs-fix-keyword correlation (shown there to be
non-discriminative).

Given a (owner, repo, path, vulnerable_sha, fixed_sha) tuple for a
*documented* CVE/GHSA fix, this script:

  1. Fetches the file content at both commits via GitHub Contents API.
  2. Runs `sast.scanner.scan` on both and diffs the finding sets.
  3. Runs the lang_adapters MetricVector analysis on both and diffs
     the 9 canonical channels.

It does NOT try to guess whether a diff "means" detection — it prints
both finding sets and both metric vectors side by side so a human can
judge. (Sprint AC-3 found, for two real requests.py CVEs, that neither
SAST nor the structural metrics changed in any diagnostic way — see
`paper/corpus_runs/AC3_cve_before_after.md`.)

Usage
-----
    python paper/cve_diff_check.py \\
        --owner psf --repo requests --path requests/sessions.py \\
        --vulnerable-sha f2629e9e3c7ce3c3c8c025bcd8db551101cbc773 \\
        --fixed-sha 0106aced5faa299e6ede89d1230bd6784f2c3660
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from base64 import b64decode
from pathlib import Path

_SENSOR_API = Path(__file__).resolve().parent.parent / "sensor-api"
if str(_SENSOR_API) not in sys.path:
    sys.path.insert(0, str(_SENSOR_API))

_GITHUB_API = "https://api.github.com"


def _fetch(owner: str, repo: str, path: str, ref: str) -> str:
    url = f"{_GITHUB_API}/repos/{owner}/{repo}/contents/{path}?ref={ref}"
    req = urllib.request.Request(url, headers={"User-Agent": "uco-sensor-cve-check"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return b64decode(data["content"]).decode("utf-8", errors="replace")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--path", required=True)
    ap.add_argument("--vulnerable-sha", required=True)
    ap.add_argument("--fixed-sha", required=True)
    args = ap.parse_args()

    from sast.scanner import scan as sast_scan
    from lang_adapters.registry import get_registry

    registry = get_registry()
    channels = [
        "hamiltonian", "cyclomatic_complexity", "infinite_loop_risk",
        "dsm_density", "dsm_cyclic_ratio", "dependency_instability",
        "syntactic_dead_code", "duplicate_block_count", "halstead_bugs",
    ]

    for label, ref in [("VULNERABLE", args.vulnerable_sha), ("FIXED", args.fixed_sha)]:
        source = _fetch(args.owner, args.repo, args.path, ref)
        result = sast_scan(source, Path(args.path).suffix)
        mv = registry.analyze(
            source=source, file_extension=Path(args.path).suffix,
            module_id=Path(args.path).name, commit_hash=ref, timestamp=0,
        )
        print(f"\n=== {label} ({ref[:12]}) — {len(result.findings)} SAST findings ===")
        for f in result.findings:
            print(f"  L{f.line:4d} {f.rule_id} [{f.severity}] {f.title}")
        print("  -- metrics --")
        for c in channels:
            print(f"  {c}: {round(getattr(mv, c, None), 4) if isinstance(getattr(mv, c, None), float) else getattr(mv, c, None)}")


if __name__ == "__main__":
    main()
