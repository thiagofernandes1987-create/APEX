#!/usr/bin/env python3
"""
Execute one shard of the UCO formal benchmark.

Each labelled event produces:
- one positive row at the documented transition;
- up to two same-file negative control boundaries from the earlier history.

Rows contain nested feature groups A..E. The evaluator decides which nested
groups are visible to each ablation arm; this runner never looks at labels when
computing UCO features.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = Path(__file__).resolve().parent
UCO_ROOT = HERE.parents[1]
SENSOR = UCO_ROOT / "sensor-api"
FREQ = UCO_ROOT / "frequency-engine"
for p in (str(SENSOR), str(FREQ)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lang_adapters.registry import get_registry
from core.constants import CHANNEL_NAMES
from transmitter.metric_signal_builder import MetricSignalBuilder
from receptor.spectral_analyzer import SpectralAnalyzer
from receptor.error_signatures import ErrorSignatureLibrary
from receptor.change_point_detector import ChangePointDetector
from governance.channels import CHANNELS as G_CHANNELS, series as channel_series
from governance.granger_causality import granger_pair, _benjamini_hochberg
from sast.scanner import scan as py_sast_scan
from sast.multilang_scanner import scan_multilang, language_for_extension

TOKEN = os.environ.get("GITHUB_TOKEN", "")
API = "https://api.github.com"
EVENT_WORDS = re.compile(
    r"\b(cve|ghsa|security|vulnerab|exploit|fix|bug|regression|refactor|revert)\b",
    re.I,
)
ATTRS = {
    "H": "hamiltonian",
    "CC": "cyclomatic_complexity",
    "ILR": "infinite_loop_risk",
    "DSM_d": "dsm_density",
    "DSM_c": "dsm_cyclic_ratio",
    "DI": "dependency_instability",
    "dead": "syntactic_dead_code",
    "dups": "duplicate_block_count",
    "bugs": "halstead_bugs",
}
SEV = {"LOW": 1.0, "MEDIUM": 2.0, "HIGH": 4.0, "CRITICAL": 8.0}


def _run(cmd: Sequence[str], cwd: Optional[Path] = None, timeout: int = 180) -> str:
    p = subprocess.run(
        list(cmd), cwd=str(cwd) if cwd else None,
        capture_output=True, text=True, timeout=timeout,
    )
    if p.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {p.stderr.strip()[:1200]}")
    return p.stdout


def _gh_json(url: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "uco-sensor-formal-benchmark/0.1",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode("utf-8"))


def resolve_sha(repo: str, sha: str) -> str:
    if len(sha) >= 40:
        return sha
    data = _gh_json(f"{API}/repos/{repo}/commits/{sha}")
    return data["sha"]


def init_repo(work: Path, repo: str, head_sha: str, base_sha: str, depth: int) -> None:
    _run(["git", "init", "-q", str(work)])
    _run(["git", "-C", str(work), "remote", "add", "origin",
          f"https://github.com/{repo}.git"])
    # Fetch exact anchors; partial clone avoids downloading unrelated blobs.
    for sha in (head_sha, base_sha):
        try:
            _run([
                "git", "-C", str(work), "fetch", "-q", "--filter=blob:none",
                f"--depth={depth}", "origin", sha,
            ], timeout=300)
        except Exception:
            # Some servers reject filter for a particular object negotiation.
            _run([
                "git", "-C", str(work), "fetch", "-q",
                f"--depth={depth}", "origin", sha,
            ], timeout=300)


def git_show(work: Path, sha: str, path: str) -> Optional[str]:
    p = subprocess.run(
        ["git", "-C", str(work), "show", f"{sha}:{path}"],
        capture_output=True, timeout=60,
    )
    if p.returncode:
        return None
    return p.stdout.decode("utf-8", errors="replace")


def path_history(work: Path, head_sha: str, path: str, limit: int) -> List[dict]:
    out = _run([
        "git", "-C", str(work), "log", head_sha, f"--max-count={limit}",
        "--format=%H%x09%ct%x09%s", "--", path,
    ])
    rows = []
    for line in out.splitlines():
        parts = line.split("\t", 2)
        if len(parts) == 3:
            rows.append({"sha": parts[0], "ts": float(parts[1]), "subject": parts[2]})
    rows.reverse()
    return rows


def quick_score(mv) -> float:
    # Existing /diff product score, reused rather than inventing a new static score.
    h = float(mv.hamiltonian)
    cc = float(mv.cyclomatic_complexity)
    return max(0.0, 100.0 - min(h * 2.0, 60.0) - min((cc - 1.0) * 2.0, 30.0))


def sast_features(source: str, path: str) -> Dict[str, float]:
    ext = Path(path).suffix.lower()
    try:
        if ext in (".py", ".pyw", ".pyi"):
            fs = py_sast_scan(source, ext).findings
        elif language_for_extension(ext):
            fs = scan_multilang(source, ext).findings
        else:
            fs = []
    except Exception:
        fs = []
    out = {"total": float(len(fs)), "weighted": 0.0}
    for s in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
        n = sum(1 for f in fs if f.severity == s)
        out[s.lower()] = float(n)
        out["weighted"] += SEV[s] * n
    return out


def analyze_source(source: str, path: str, sha: str, ts: float):
    return get_registry().analyze(
        source=source,
        file_extension=Path(path).suffix.lower(),
        module_id=path,
        commit_hash=sha,
        timestamp=ts,
    )


def history_vectors(work: Path, rows: List[dict], path: str) -> List:
    vecs = []
    for r in rows:
        src = git_show(work, r["sha"], path)
        if src is None or not src.strip():
            continue
        try:
            vecs.append(analyze_source(src, path, r["sha"], r["ts"]))
        except Exception:
            continue
    return vecs


def static_group(before_mv, after_mv, before_src: str, after_src: str, path: str) -> Dict[str, float]:
    out: Dict[str, float] = {}
    qb, qa = quick_score(before_mv), quick_score(after_mv)
    out.update({
        "quick_before": qb, "quick_after": qa, "quick_delta": qa - qb,
        "risk_after": 100.0 - qa,
    })
    for ch, attr in ATTRS.items():
        b = float(getattr(before_mv, attr))
        a = float(getattr(after_mv, attr))
        out[f"before_{ch}"] = b
        out[f"after_{ch}"] = a
        out[f"delta_{ch}"] = a - b
    sb, sa = sast_features(before_src, path), sast_features(after_src, path)
    for key in sorted(set(sb) | set(sa)):
        out[f"sast_before_{key}"] = float(sb.get(key, 0.0))
        out[f"sast_after_{key}"] = float(sa.get(key, 0.0))
        out[f"sast_delta_{key}"] = float(sa.get(key, 0.0) - sb.get(key, 0.0))
    return out


def _ols_slope(y: np.ndarray) -> float:
    if len(y) < 2:
        return 0.0
    x = np.arange(len(y), dtype=float)
    x -= x.mean()
    den = float(np.dot(x, x))
    return float(np.dot(x, y - y.mean()) / den) if den > 0 else 0.0


def history_group(vecs: List) -> Dict[str, float]:
    out: Dict[str, float] = {"n": float(len(vecs))}
    if not vecs:
        return out
    for ch, attr in ATTRS.items():
        y = np.asarray([float(getattr(v, attr)) for v in vecs], dtype=float)
        out[f"slope_{ch}"] = _ols_slope(y)
        out[f"delta_{ch}"] = float(y[-1] - y[0])
        out[f"std_{ch}"] = float(np.std(y))
        out[f"madiff_{ch}"] = float(np.mean(np.abs(np.diff(y)))) if len(y) > 1 else 0.0
    return out


def spectral_group(vecs: List) -> Tuple[Dict[str, float], object, list]:
    out: Dict[str, float] = {}
    signal = MetricSignalBuilder().build(vecs)
    if signal is None:
        return out, None, []
    profiles = SpectralAnalyzer().analyze_full(signal)
    for p in profiles:
        if "cross:" in p.channel:
            continue
        ch = p.channel
        out[f"{ch}_dominant_freq"] = float(p.dominant_freq)
        out[f"{ch}_entropy"] = float(p.spectral_entropy)
        out[f"{ch}_wmf"] = float(p.weighted_mean_freq)
        out[f"{ch}_fw_shift"] = float(p.fw_shift)
        out[f"{ch}_raw_std"] = float(p.raw_std)
        for band, value in p.band_energies_relative.items():
            out[f"{ch}_band_{band}"] = float(value)
    matches = ErrorSignatureLibrary().match(profiles, min_confidence=0.0, signal=signal)
    if matches:
        out["top_signature_confidence"] = float(matches[0].confidence)
        out["n_signature_matches"] = float(len(matches))
    return out, signal, profiles


def changepoint_group(signal) -> Dict[str, float]:
    if signal is None:
        return {"detected": 0.0}
    cp = ChangePointDetector(model="l2", penalty=1.0, min_size=3).detect(
        signal, list(CHANNEL_NAMES)
    )
    if cp is None:
        return {"detected": 0.0}
    return {
        "detected": 1.0,
        "confidence": float(cp.confidence),
        "magnitude": float(cp.magnitude),
        "position": float(cp.commit_idx / max(1, signal.n_original - 1)),
        "commit_idx": float(cp.commit_idx),
        "affected_n": float(len(cp.affected_channels)),
        "signal_idx": float(cp.signal_idx if cp.signal_idx is not None else -1),
    }


def granger_group(vecs: List, max_lag: int = 3) -> Dict[str, float]:
    if len(vecs) < 2 * max_lag + 3:
        return {"available": 0.0}
    pvals, rows = [], []
    for a in G_CHANNELS:
        xa = channel_series(vecs, a)
        for b in G_CHANNELS:
            if a == b:
                continue
            yb = channel_series(vecs, b)
            r = granger_pair(xa, yb, max_lag=max_lag, alpha=0.05)
            pvals.append(float(r.p_value))
            rows.append((a, b, r))
    qs = _benjamini_hochberg(pvals)
    sig = [(a, b, r, q) for (a, b, r), q in zip(rows, qs) if q < 0.05]
    fvals = [float(r.f_statistic) for _, _, r, _ in sig]
    lags = [float(r.best_lag) for _, _, r, _ in sig]
    return {
        "available": 1.0,
        "significant_n": float(len(sig)),
        "min_q": float(min(qs) if qs else 1.0),
        "max_f": float(max(fvals) if fvals else 0.0),
        "mean_lag": float(np.mean(lags) if lags else 0.0),
        "into_H_n": float(sum(1 for a, b, r, q in sig if b == "H")),
        "out_H_n": float(sum(1 for a, b, r, q in sig if a == "H")),
    }


def feature_row(
    *,
    event: dict,
    work: Path,
    before_sha: str,
    after_sha: str,
    hist_rows: List[dict],
    label: int,
    row_kind: str,
) -> Optional[dict]:
    before_src = git_show(work, before_sha, event["path"])
    after_src = git_show(work, after_sha, event["path"])
    if not before_src or not after_src:
        return None
    try:
        before_ts = float(_run(["git", "-C", str(work), "show", "-s", "--format=%ct", before_sha]).strip())
        after_ts = float(_run(["git", "-C", str(work), "show", "-s", "--format=%ct", after_sha]).strip())
        bmv = analyze_source(before_src, event["path"], before_sha, before_ts)
        amv = analyze_source(after_src, event["path"], after_sha, after_ts)
    except Exception:
        return None

    vecs = history_vectors(work, hist_rows, event["path"])
    spectral, signal, _ = spectral_group(vecs)
    cp = changepoint_group(signal)
    gran = granger_group(vecs)
    return {
        "event_id": event["id"],
        "repo": event["repo"],
        "path": event["path"],
        "event_type": event["event_type"],
        "evidence_tier": event["evidence_tier"],
        "seed_dev": bool(event.get("seed_dev", False)),
        "row_kind": row_kind,
        "label": int(label),
        "before_sha": before_sha,
        "after_sha": after_sha,
        "n_history": len(vecs),
        "features": {
            "static": static_group(bmv, amv, before_src, after_src, event["path"]),
            "history": history_group(vecs),
            "spectral": spectral,
            "changepoint": cp,
            "granger": gran,
        },
        "localization": {
            # The labelled event is the last boundary in the constructed
            # positive window. Controls do not enter localization metrics.
            "gold_idx": max(0, len(vecs) - 1) if label else None,
            "pred_idx": int(cp["commit_idx"]) if label and cp.get("detected") else None,
        },
    }


def neutral_controls(rows: List[dict], event_head: str, n: int = 2) -> List[Tuple[int, int]]:
    if len(rows) < 10:
        return []
    try:
        event_i = next(i for i, r in enumerate(rows) if r["sha"] == event_head)
    except StopIteration:
        event_i = len(rows) - 1
    candidates = []
    for i in range(1, len(rows)):
        # Primary ablation is complete-case: Granger(max_lag=3) requires
        # at least 9 snapshots (2*k+3). Do not create a control that makes
        # the E arm unavailable merely because it sits too early in history.
        if i < 8:
            continue
        if abs(i - event_i) <= 5:
            continue
        if EVENT_WORDS.search(rows[i]["subject"] or ""):
            continue
        candidates.append((i - 1, i))
    # deterministic spread: earliest then latest eligible, no RNG.
    if not candidates:
        return []
    picks = [candidates[0]]
    if n > 1 and candidates[-1] != candidates[0]:
        picks.append(candidates[-1])
    return picks[:n]


def process_event(event: dict, history_window: int) -> List[dict]:
    event = dict(event)
    event["base_sha"] = resolve_sha(event["repo"], event["base_sha"])
    event["head_sha"] = resolve_sha(event["repo"], event["head_sha"])
    with tempfile.TemporaryDirectory(prefix="uco-bench-") as td:
        work = Path(td) / "repo"
        init_repo(work, event["repo"], event["head_sha"], event["base_sha"],
                  depth=max(80, history_window * 3))
        rows = path_history(work, event["head_sha"], event["path"], history_window)
        if len(rows) < 9:
            raise RuntimeError(
                f"insufficient path history for complete 5-arm ablation: {len(rows)} < 9"
            )

        # Positive window ends at the labelled transition head.
        pos_hist = rows[-history_window:]
        out = []
        pos = feature_row(
            event=event, work=work,
            before_sha=event["base_sha"], after_sha=event["head_sha"],
            hist_rows=pos_hist, label=1, row_kind="event",
        )
        if pos:
            out.append(pos)

        for a, b in neutral_controls(rows, event["head_sha"], n=2):
            # History available up to the control boundary only.
            hist = rows[: b + 1][-history_window:]
            ctl = feature_row(
                event=event, work=work,
                before_sha=rows[a]["sha"], after_sha=rows[b]["sha"],
                hist_rows=hist, label=0, row_kind="matched-control",
            )
            if ctl:
                out.append(ctl)
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--history-window", type=int, default=40)
    ap.add_argument("--shard-index", type=int, default=0)
    ap.add_argument("--shard-count", type=int, default=1)
    args = ap.parse_args()

    events = json.loads(Path(args.manifest).read_text())
    events = [
        e for i, e in enumerate(events)
        if i % max(1, args.shard_count) == args.shard_index
    ]
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    ok_events = failed = 0
    rows_written = 0
    with Path(args.output).open("w", encoding="utf-8") as fh:
        for i, e in enumerate(events, 1):
            t0 = time.perf_counter()
            try:
                rows = process_event(e, args.history_window)
                for row in rows:
                    row["wall_s"] = round(time.perf_counter() - t0, 4)
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    rows_written += 1
                if rows:
                    ok_events += 1
                    print(f"[ok {i}/{len(events)}] {e['repo']} rows={len(rows)}")
                else:
                    failed += 1
                    print(f"[empty {i}/{len(events)}] {e['repo']}")
            except Exception as exc:
                failed += 1
                print(f"[fail {i}/{len(events)}] {e['repo']}: "
                      f"{type(exc).__name__}: {exc}")

    print(json.dumps({
        "events_requested": len(events),
        "events_ok": ok_events,
        "events_failed": failed,
        "rows_written": rows_written,
        "output": args.output,
    }, indent=2))
    return 0 if ok_events else 2


if __name__ == "__main__":
    raise SystemExit(main())
