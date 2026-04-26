"""
UCO-Sensor — GitHub Actions Entrypoint (M4.4)
==============================================
Standalone script invoked by action.yml composite steps.

Responsibilities:
  1. Scan the repository (RepoScanner)
  2. SAST-scan all Python files (sast.scanner)
  3. Build SARIF 2.1.0 output (report.sarif.SARIFBuilder)
  4. Write GitHub Actions output variables to $GITHUB_OUTPUT
  5. Write SARIF file to specified path
  6. Exit 0/1 based on fail_on_critical / fail_on_gate_fail settings

Environment variables (injected by action.yml):
  UCO_SCAN_PATH       — directory to scan (default ".")
  UCO_MAX_FILES       — max files to scan (default 500, 0=unlimited)
  UCO_INCLUDE_TESTS   — "true"|"false" (default "false")
  UCO_SARIF_OUTPUT    — output SARIF path (default "uco-sensor.sarif")
  UCO_POLICY_FILE     — path to custom policy YAML (default = use UCO default)
  UCO_FAIL_CRITICAL   — "true"|"false" (default "true")
  UCO_FAIL_GATE       — "true"|"false" (default "true")
  UCO_GATE_THRESHOLD  — minimum gate score to pass (default 70)

Usage (from action.yml):
  python "${{ github.action_path }}/algorithms/uco-sensor/sensor-api/ci/action_entrypoint.py"
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# ── Path bootstrap ────────────────────────────────────────────────────────────
_CI_DIR     = Path(__file__).resolve().parent
_SENSOR_DIR = _CI_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_SENSOR_DIR), str(_ENGINE_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports (deferred so --help works without dependencies) ───────────────────

def _main() -> int:
    """Run scan and return exit code (0=pass, 1=fail)."""
    # ── Read config from environment ──────────────────────────────────────────
    scan_path       = os.environ.get("UCO_SCAN_PATH",      ".")
    max_files_str   = os.environ.get("UCO_MAX_FILES",      "500")
    include_tests   = os.environ.get("UCO_INCLUDE_TESTS",  "false").lower() == "true"
    sarif_output    = os.environ.get("UCO_SARIF_OUTPUT",   "uco-sensor.sarif")
    policy_file     = os.environ.get("UCO_POLICY_FILE",    "")
    fail_critical   = os.environ.get("UCO_FAIL_CRITICAL",  "true").lower() == "true"
    fail_gate       = os.environ.get("UCO_FAIL_GATE",      "true").lower() == "true"
    gate_threshold  = int(os.environ.get("UCO_GATE_THRESHOLD", "70"))
    github_output   = os.environ.get("GITHUB_OUTPUT",      ".uco_outputs")
    max_files       = int(max_files_str) if max_files_str.isdigit() else 500

    root = Path(scan_path).resolve()
    if not root.exists() or not root.is_dir():
        print(f"[UCO-Sensor] ERROR: scan path '{scan_path}' is not a directory", file=sys.stderr)
        return 1

    print(f"[UCO-Sensor] Scanning: {root}", flush=True)
    t0 = time.time()

    # ── Repo scan ─────────────────────────────────────────────────────────────
    from scan.repo_scanner import RepoScanner

    scanner = RepoScanner(
        root=str(root),
        commit_hash=os.environ.get("GITHUB_SHA", f"ci_{int(time.time())}"),
        store=None,              # no persistence in CI
        max_files=max_files,
        include_tests=include_tests,
        exclude=[],
        top_n=50,
        max_workers=4,
    )
    try:
        scan_result = scanner.scan()
    except Exception as exc:
        print(f"[UCO-Sensor] Scan failed: {exc}", file=sys.stderr)
        return 1

    elapsed = time.time() - t0
    d = scan_result.to_dict()

    # ── SARIF construction ────────────────────────────────────────────────────
    from report.sarif import SARIFBuilder
    from sast.scanner import scan as sast_scan

    builder = SARIFBuilder(
        tool_version=os.environ.get("UCO_VERSION", "1.0.0"),
        repo=os.environ.get("GITHUB_REPOSITORY", ""),
    )

    file_results = d.get("file_results", [])
    total_debt   = 0

    for fr in file_results:
        path    = fr.get("path", "unknown")
        content = fr.get("_source", "")       # populated only when persist=False
        status  = fr.get("status", "STABLE")
        metrics = fr.get("metrics", {})
        fps     = fr.get("function_profiles", [])

        # UCO channel findings for non-STABLE files
        if status in ("CRITICAL", "WARNING"):
            h  = metrics.get("hamiltonian", 0)
            cc = metrics.get("cyclomatic_complexity", 0)
            if h > 20 or cc > 15:
                builder.add_uco_finding(
                    file_uri=path,
                    rule_id="UCO001",
                    message=(
                        f"UCO {status}: H={h:.2f}, CC={cc} — "
                        f"ILR={metrics.get('infinite_loop_risk', 0):.2f}, "
                        f"bugs={metrics.get('halstead_bugs', 0):.2f}"
                    ),
                    severity=status,
                    line=1,
                )

        # Function-level UCO findings
        if fps:
            builder.add_uco_findings_from_profiles(path, fps)

        # SAST scan if source available and Python file
        if content and path.endswith(".py"):
            try:
                sast_res = sast_scan(content, file_extension=".py")
                builder.add_sast_findings(path, sast_res)
                total_debt += sast_res.total_debt_minutes
            except Exception:
                pass

    sarif_doc = builder.build()

    # Write SARIF file
    if sarif_output:
        sarif_path = Path(sarif_output)
        sarif_path.parent.mkdir(parents=True, exist_ok=True)
        sarif_path.write_text(json.dumps(sarif_doc, indent=2, default=str), encoding="utf-8")
        print(f"[UCO-Sensor] SARIF written: {sarif_path} ({builder.result_count()} findings)",
              flush=True)

    # ── Compute gate score ────────────────────────────────────────────────────
    uco_score   = d.get("uco_score", 0.0)
    status_str  = d.get("status", "STABLE")
    crit_count  = d.get("critical_count", 0)
    warn_count  = d.get("warning_count", 0)
    n_scanned   = d.get("files_scanned", 0)

    print(
        f"[UCO-Sensor] Status={status_str} Score={uco_score:.1f} "
        f"Critical={crit_count} Warning={warn_count} "
        f"Files={n_scanned} Debt={total_debt}min "
        f"({elapsed:.1f}s)",
        flush=True,
    )

    # ── Write GitHub Actions outputs ──────────────────────────────────────────
    outputs = {
        "uco_score":     f"{uco_score:.1f}",
        "status":        status_str,
        "critical_count": str(crit_count),
        "warning_count":  str(warn_count),
        "files_scanned":  str(n_scanned),
        "sarif_file":     sarif_output,
        "debt_minutes":   str(total_debt),
    }
    if github_output:
        out_path = Path(github_output)
        with out_path.open("a", encoding="utf-8") as fh:
            for key, val in outputs.items():
                fh.write(f"{key}={val}\n")

    # ── Gate evaluation ───────────────────────────────────────────────────────
    fail = False
    if fail_critical and status_str == "CRITICAL":
        print(f"[UCO-Sensor] ❌ CRITICAL detected — gate FAILED", flush=True)
        fail = True
    if fail_gate and uco_score < gate_threshold:
        print(
            f"[UCO-Sensor] ❌ Score {uco_score:.1f} < threshold {gate_threshold} — gate FAILED",
            flush=True,
        )
        fail = True
    if not fail:
        print(f"[UCO-Sensor] ✅ Quality gate PASSED (score={uco_score:.1f})", flush=True)

    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(_main())
