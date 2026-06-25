#!/usr/bin/env python3
"""
UCO Sensor — Paper Reproducibility Script (Sprint Z, v3.9.0)
==============================================================

Regenerates every table and figure cited in ``paper/paper.tex`` from
the live `uco-sensor` codebase + a local corpus checkout.

Usage:
    python paper/reproducibility.py --output paper/tables/
    python paper/reproducibility.py --output paper/tables/ --quick   # subset

Tables produced (per experiment in ``paper/experiments.md``):
    T1.csv  — invariant satisfaction rate per repo per invariant
    T2.csv  — HMC repair stats per repo
    T3.csv  — multi-tenant billing throughput by concurrency
    T4.csv  — baselines comparison

This script is intentionally **standalone** (no test framework
dependency) so reviewers can run it without installing pytest.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Make the sensor importable regardless of cwd.
_HERE = Path(__file__).resolve().parent
_SENSOR_API = _HERE.parent / "sensor-api"
_FREQ = _HERE.parent.parent.parent / "algorithms" / "uco-sensor" / "frequency-engine"
for _p in (_SENSOR_API, _FREQ):
    if _p.exists() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ─── T1: Invariant satisfaction (synthetic, no corpus needed) ───────────────

def table_t1_invariants(output_dir: Path, *, quick: bool) -> None:
    from governance.invariants import (
        invariant_i1_aps_preserved,
        invariant_i2_no_severity_regression,
        invariant_i3_hmc_convergence,
        invariant_i4_propagation_symmetry,
        invariant_i5_period_reset_idempotent,
    )

    # Synthetic cases: stand-ins for repo-derived data when corpus is absent.
    # Sprint Z (LOW from Workflow #2): I2 now exercises real-data cases,
    # not just the (None,None) short-circuit.
    from types import SimpleNamespace
    def _scan(*sevs):
        return SimpleNamespace(findings=[SimpleNamespace(severity=s) for s in sevs])
    cases = [
        ("synthetic-aps-equal",      "I1", invariant_i1_aps_preserved(0.5, 0.5), True),
        ("synthetic-aps-up",         "I1", invariant_i1_aps_preserved(0.3, 0.7), True),
        ("synthetic-aps-down",       "I1", invariant_i1_aps_preserved(0.7, 0.3), False),
        ("synthetic-aps-unmeasured", "I1", invariant_i1_aps_preserved(0.5, None), False),  # SZ-FIX-1
        ("synthetic-sev-vacuous",    "I2", invariant_i2_no_severity_regression(None, None), True),
        ("synthetic-sev-stable",     "I2", invariant_i2_no_severity_regression(_scan("HIGH","LOW"), _scan("HIGH","LOW")), True),
        ("synthetic-sev-regression", "I2", invariant_i2_no_severity_regression(_scan("LOW"), _scan("LOW","CRITICAL")), False),
        ("synthetic-sev-improved",   "I2", invariant_i2_no_severity_regression(_scan("HIGH","HIGH"), _scan("LOW")), True),
        ("synthetic-hmc-ok",         "I3", invariant_i3_hmc_convergence(10.0, 5.0, "OK"), True),
        ("synthetic-hmc-fail",       "I3", invariant_i3_hmc_convergence(5.0, 10.0, "OK"), False),
        ("synthetic-hmc-error",      "I3", invariant_i3_hmc_convergence(5.0, 10.0, "ERROR"), True),
        ("synthetic-prop-sym",       "I4", invariant_i4_propagation_symmetry(0.123, 0.123), True),
        ("synthetic-prop-asym",      "I4", invariant_i4_propagation_symmetry(0.123, 0.124), False),
        ("synthetic-reset-ok",       "I5", invariant_i5_period_reset_idempotent(True, False), True),
        ("synthetic-reset-bad",      "I5", invariant_i5_period_reset_idempotent(True, True), False),
    ]
    out = output_dir / "T1.csv"
    with out.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "invariant", "checker_returned", "expected", "agrees"])
        for case_id, inv, got, exp in cases:
            w.writerow([case_id, inv, got, exp, got == exp])
    print(f"  T1.csv  ({len(cases)} cases)")


# ─── T2: HMC repair stats (toy source — extend with real corpus) ────────────

def table_t2_hmc_repair(output_dir: Path, *, quick: bool) -> None:
    from sensor_core.autofix.hmc_repair import hmc_repair
    n_attempts = 3 if quick else 10
    rows: List[Dict[str, Any]] = []
    src = "def f(x):\n    return x + 1\n"
    for i in range(n_attempts):
        try:
            r = hmc_repair(src, module_id=f"toy{i}",
                           n_steps=2, burn_in=0, deterministic=True)
            rows.append({
                "attempt": i, "status": r.status,
                "h_before": getattr(r, "h_before", None),
                "h_final":  getattr(r, "h_final", None),
            })
        except Exception as exc:
            rows.append({"attempt": i, "status": f"EXC:{exc!r}",
                         "h_before": None, "h_final": None})
    out = output_dir / "T2.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["attempt", "status", "h_before", "h_final"])
        w.writeheader()
        w.writerows(rows)
    print(f"  T2.csv  ({len(rows)} attempts)")


# ─── T3: Billing throughput micro-bench ─────────────────────────────────────

def table_t3_billing_throughput(output_dir: Path, *, quick: bool) -> None:
    from sensor_storage.snapshot_store import SnapshotStore
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge

    rows: List[Dict[str, Any]] = []
    # NOTE — measured SERIALLY (single-thread loop) under the SnapshotStore
    # GIL/lock combination.  True concurrent scaling needs threaded callers;
    # this baseline establishes the per-call ceiling.  Column named
    # `serial_batches` to avoid misleading a paper reviewer.
    serial_batches = [1] if quick else [1, 10, 50]
    n_per = 200 if quick else 1000
    for sb in serial_batches:
        s = SnapshotStore(":memory:")
        create_tenant(s, "bench", plan="ENT")
        t0 = time.perf_counter()
        for i in range(n_per * sb):
            check_and_charge(s, "bench", "snapshot", endpoint="/x")
        dt = time.perf_counter() - t0
        rows.append({
            "serial_batches": sb,
            "total_events":   n_per * sb,
            "wall_seconds":   round(dt, 4),
            "events_per_sec": round((n_per * sb) / dt, 1),
        })
    out = output_dir / "T3.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["serial_batches", "total_events",
                                            "wall_seconds", "events_per_sec"])
        w.writeheader()
        w.writerows(rows)
    print(f"  T3.csv  ({len(rows)} serial-batch sizes)")


# ─── T4: Baseline comparison (placeholder — full corpus deferred) ───────────

def table_t4_baselines(output_dir: Path, *, quick: bool) -> None:
    rows = [
        {"tool": "uco-sensor", "findings": "TBD", "unique_to_tool": "TBD"},
        {"tool": "sonarqube",  "findings": "TBD", "unique_to_tool": "TBD"},
        {"tool": "codeql",     "findings": "TBD", "unique_to_tool": "TBD"},
        {"tool": "semgrep",    "findings": "TBD", "unique_to_tool": "TBD"},
    ]
    out = output_dir / "T4.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["tool", "findings", "unique_to_tool"])
        w.writeheader()
        w.writerows(rows)
    print(f"  T4.csv  (placeholder — extend with real corpus run)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default="paper/tables/",
                   help="output directory for the CSVs")
    p.add_argument("--quick", action="store_true",
                   help="run subset (faster, for CI smoke)")
    args = p.parse_args()

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Writing tables to {out_dir.resolve()}")
    table_t1_invariants(out_dir, quick=args.quick)
    table_t2_hmc_repair(out_dir, quick=args.quick)
    table_t3_billing_throughput(out_dir, quick=args.quick)
    table_t4_baselines(out_dir, quick=args.quick)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
