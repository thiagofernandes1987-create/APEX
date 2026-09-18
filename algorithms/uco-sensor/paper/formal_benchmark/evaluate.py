#!/usr/bin/env python3
"""
Evaluate nested UCO ablation arms on repository-disjoint splits.

Uses the same regularized logistic-regression learner for every arm. The only
difference is which feature groups are visible, so deltas quantify incremental
information in UCO layers rather than downstream model flexibility.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np

ARMS = {
    "A_STATIC": ("static",),
    "B_HISTORY": ("static", "history"),
    "C_SPECTRAL": ("static", "history", "spectral"),
    "D_CHANGEPOINT": ("static", "history", "spectral", "changepoint"),
    "E_GRANGER": ("static", "history", "spectral", "changepoint", "granger"),
}


def split_repo(repo: str) -> str:
    bucket = int(hashlib.sha256(repo.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket <= 5:
        return "train"
    if bucket <= 7:
        return "dev"
    return "test"


def read_rows(patterns: Sequence[str]) -> List[dict]:
    files: List[str] = []
    for p in patterns:
        files.extend(glob.glob(p))
    rows = []
    for path in sorted(set(files)):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
    return rows


def flat_features(row: dict, groups: Sequence[str]) -> Dict[str, float]:
    out: Dict[str, float] = {}
    nested = row.get("features", {})
    for group in groups:
        for k, v in (nested.get(group) or {}).items():
            try:
                x = float(v)
            except (TypeError, ValueError):
                continue
            if math.isfinite(x):
                out[f"{group}.{k}"] = x
    return out


def matrix(rows: List[dict], groups: Sequence[str], columns: List[str] | None = None):
    dicts = [flat_features(r, groups) for r in rows]
    if columns is None:
        columns = sorted({k for d in dicts for k in d})
    X = np.zeros((len(rows), len(columns)), dtype=float)
    for i, d in enumerate(dicts):
        for j, c in enumerate(columns):
            X[i, j] = d.get(c, 0.0)
    y = np.asarray([int(r["label"]) for r in rows], dtype=int)
    return X, y, columns


def choose_threshold(y: np.ndarray, p: np.ndarray) -> float:
    if len(y) == 0:
        return 0.5
    candidates = sorted(set([0.5] + [float(x) for x in p]))
    best = (0.0, 0.5)
    for t in candidates:
        pred = p >= t
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(1e-12, precision + recall)
        if f1 > best[0]:
            best = (f1, t)
    return float(best[1])


def metric_block(y: np.ndarray, p: np.ndarray, threshold: float) -> dict:
    from sklearn.metrics import (
        average_precision_score, roc_auc_score, brier_score_loss,
        precision_score, recall_score, f1_score,
    )
    if len(set(y.tolist())) < 2:
        return {"n": int(len(y)), "error": "single-class split"}
    pred = (p >= threshold).astype(int)
    return {
        "n": int(len(y)),
        "positives": int(y.sum()),
        "controls": int((y == 0).sum()),
        "auprc": float(average_precision_score(y, p)),
        "auroc": float(roc_auc_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "fpr": float(((pred == 1) & (y == 0)).sum() / max(1, (y == 0).sum())),
    }


def fit_arm(train: List[dict], dev: List[dict], test: List[dict], groups: Sequence[str]):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    Xtr, ytr, cols = matrix(train, groups)
    Xd, yd, _ = matrix(dev, groups, cols)
    Xt, yt, _ = matrix(test, groups, cols)
    if len(cols) == 0 or len(set(ytr.tolist())) < 2:
        raise RuntimeError("insufficient train data/features for arm")

    model = Pipeline([
        ("scale", StandardScaler()),
        ("clf", LogisticRegression(
            C=1.0, penalty="l2", class_weight="balanced",
            max_iter=2000, random_state=20260918,
        )),
    ])
    model.fit(Xtr, ytr)
    pd = model.predict_proba(Xd)[:, 1] if len(dev) else np.array([])
    pt = model.predict_proba(Xt)[:, 1] if len(test) else np.array([])
    threshold = choose_threshold(yd, pd) if len(dev) else 0.5
    return {
        "columns": cols,
        "dev": metric_block(yd, pd, threshold) if len(dev) else {"n": 0},
        "test": metric_block(yt, pt, threshold) if len(test) else {"n": 0},
        "test_probs": pt.tolist(),
    }


def bootstrap_arm_deltas(
    test_rows: List[dict],
    probs_by_arm: Dict[str, np.ndarray],
    *,
    n_boot: int,
) -> dict:
    from sklearn.metrics import average_precision_score

    repos = sorted({r["repo"] for r in test_rows})
    indices = {repo: [i for i, r in enumerate(test_rows) if r["repo"] == repo] for repo in repos}
    rng = np.random.default_rng(20260918)
    pairs = list(zip(list(ARMS)[1:], list(ARMS)[:-1]))
    samples = {f"{new}-{old}": [] for new, old in pairs}

    for _ in range(n_boot):
        chosen = rng.choice(repos, size=len(repos), replace=True)
        idx = [i for repo in chosen for i in indices[repo]]
        y = np.asarray([int(test_rows[i]["label"]) for i in idx], dtype=int)
        if len(set(y.tolist())) < 2:
            continue
        for new, old in pairs:
            pn = probs_by_arm[new][idx]
            po = probs_by_arm[old][idx]
            d = float(average_precision_score(y, pn) - average_precision_score(y, po))
            samples[f"{new}-{old}"].append(d)

    out = {}
    for name, vals in samples.items():
        a = np.asarray(vals, dtype=float)
        if not len(a):
            out[name] = {"error": "no bootstrap samples"}
            continue
        p_left = float(np.mean(a <= 0))
        p_right = float(np.mean(a >= 0))
        out[name] = {
            "mean_delta_auprc": float(np.mean(a)),
            "ci95": [float(np.quantile(a, 0.025)), float(np.quantile(a, 0.975))],
            "p_two_sided_bootstrap": min(1.0, 2.0 * min(p_left, p_right)),
            "n_boot": int(len(a)),
        }
    return out


def holm_bonferroni(deltas: dict, alpha: float = 0.05) -> dict:
    valid = [(k, v["p_two_sided_bootstrap"]) for k, v in deltas.items()
             if "p_two_sided_bootstrap" in v]
    ordered = sorted(valid, key=lambda kv: kv[1])
    m = len(ordered)
    rejected = {}
    still = True
    for rank, (name, p) in enumerate(ordered, 1):
        cutoff = alpha / max(1, m - rank + 1)
        reject = bool(still and p <= cutoff)
        rejected[name] = {"p": p, "holm_cutoff": cutoff, "reject_h0": reject}
        if not reject:
            still = False
    return rejected


def localization(rows: List[dict]) -> dict:
    errors = []
    missing = 0
    for r in rows:
        if int(r["label"]) != 1:
            continue
        loc = r.get("localization") or {}
        g, p = loc.get("gold_idx"), loc.get("pred_idx")
        if g is None or p is None:
            missing += 1
            continue
        errors.append(abs(int(g) - int(p)))
    if not errors:
        return {"n": 0, "no_onset": missing}
    a = np.asarray(errors)
    return {
        "n": int(len(errors)),
        "no_onset": int(missing),
        "median_abs_commit_error": float(np.median(a)),
        "mean_abs_commit_error": float(np.mean(a)),
        "hit_at_1": float(np.mean(a <= 1)),
        "hit_at_3": float(np.mean(a <= 3)),
        "hit_at_5": float(np.mean(a <= 5)),
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# UCO-Sensor Formal Benchmark — ablation report",
        "",
        f"Formal held-out result: **{'YES' if report['formal'] else 'NO — ' + report['formal_reason']}**",
        "",
        f"Rows: {report['n_rows']} | repositories: {report['n_repos']} | "
        f"seed-dev rows: {report['seed_dev_rows']}",
        (
            "Corpus coverage: "
            + (
                f"{report['corpus_coverage']['analyzed_repos']}/"
                f"{report['corpus_coverage']['expected_repos']} repositories"
                if report.get("corpus_coverage", {}).get("expected_repos")
                else "manifest not supplied"
            )
        ),
        "",
        "## Held-out discrimination",
        "",
        "| Arm | AUPRC | AUROC | F1 | Precision | Recall | FPR | Brier |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        m = report["arms"].get(arm, {}).get("test", {})
        if "error" in m or not m.get("n"):
            lines.append(f"| {arm} | — | — | — | — | — | — | — |")
        else:
            lines.append(
                f"| {arm} | {m['auprc']:.4f} | {m['auroc']:.4f} | {m['f1']:.4f} | "
                f"{m['precision']:.4f} | {m['recall']:.4f} | {m['fpr']:.4f} | {m['brier']:.4f} |"
            )
    lines += ["", "## Incremental AUPRC (repository-cluster bootstrap)", ""]
    for name, d in report.get("deltas", {}).items():
        if "error" in d:
            lines.append(f"- {name}: {d['error']}")
        else:
            ci = d["ci95"]
            h = report.get("holm", {}).get(name, {})
            lines.append(
                f"- **{name}**: Δ={d['mean_delta_auprc']:+.4f}, "
                f"95% CI [{ci[0]:+.4f}, {ci[1]:+.4f}], "
                f"p≈{d['p_two_sided_bootstrap']:.4f}, "
                f"Holm reject={h.get('reject_h0', False)}"
            )
    if report.get("matching"):
        m = report["matching"]
        lines += [
            "",
            "## Control matching diagnostics",
            "",
            f"- matched controls: {m.get('n_controls', 0)}",
            f"- median control/event changed-line ratio: {m.get('median_size_ratio', 0):.3f}",
            f"- median |log1p(size) distance|: {m.get('median_log_distance', 0):.3f}",
        ]

    if report.get("strata"):
        lines += ["", "## Held-out AUPRC by event stratum", ""]
        lines += ["| Stratum | " + " | ".join(ARMS.keys()) + " |"]
        lines += ["|---|" + "|".join(["---:"] * len(ARMS)) + "|"]
        for etype, arms in sorted(report["strata"].items()):
            vals = []
            for arm in ARMS:
                v = arms.get(arm, {})
                vals.append(f"{v['auprc']:.4f}" if "auprc" in v else "—")
            lines.append("| " + etype + " | " + " | ".join(vals) + " |")

    loc = report["localization"]
    lines += [
        "",
        "## Change-point localization",
        "",
        f"- evaluable positives: {loc.get('n', 0)}",
        f"- no onset: {loc.get('no_onset', 0)}",
    ]
    if loc.get("n"):
        lines += [
            f"- median absolute commit error: {loc['median_abs_commit_error']:.2f}",
            f"- Hit@1: {loc['hit_at_1']:.3f}",
            f"- Hit@3: {loc['hit_at_3']:.3f}",
            f"- Hit@5: {loc['hit_at_5']:.3f}",
        ]
    lines += [
        "",
        "## Interpretation guard",
        "",
        "Granger is evaluated only as incremental predictive lead/lag information. "
        "This report does not treat statistical Granger edges as independently "
        "validated causal truth.",
    ]
    return "\n".join(lines) + "\n"


def matching_diagnostics(rows: List[dict]) -> dict:
    ratios = []
    distances = []
    for r in rows:
        if int(r.get("label", 0)) != 0:
            continue
        m = r.get("matching") or {}
        e = m.get("event_change_lines")
        c = m.get("control_change_lines")
        d = m.get("size_log_distance")
        try:
            if float(e) > 0 and float(c) > 0:
                ratios.append(float(c) / float(e))
            if d is not None:
                distances.append(float(d))
        except (TypeError, ValueError):
            continue
    return {
        "n_controls": len(ratios),
        "median_size_ratio": float(np.median(ratios)) if ratios else 0.0,
        "median_log_distance": float(np.median(distances)) if distances else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", nargs="+", required=True, help="JSONL paths/globs")
    ap.add_argument("--json-out", required=True)
    ap.add_argument("--md-out", required=True)
    ap.add_argument("--bootstrap", type=int, default=500)
    ap.add_argument("--include-seed", action="store_true")
    ap.add_argument("--min-formal-repos", type=int, default=500)
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    rows_all = read_rows(args.input)
    seed_n = sum(1 for r in rows_all if r.get("seed_dev"))
    rows = rows_all if args.include_seed else [r for r in rows_all if not r.get("seed_dev")]
    # Seed smoke has no formal claim but still validates the complete learning path.
    if not rows and rows_all:
        rows = rows_all

    analyzed_repos = {r["repo"] for r in rows}
    expected_events = expected_repos = None
    if args.manifest:
        manifest = json.loads(Path(args.manifest).read_text())
        expected_events = len(manifest)
        expected_repos = len({e["repo"] for e in manifest})
    has_seed = any(r.get("seed_dev") for r in rows)
    formal = (
        not args.include_seed
        and not has_seed
        and len(analyzed_repos) >= args.min_formal_repos
    )
    if formal:
        formal_reason = "formal corpus gate satisfied"
    elif has_seed or args.include_seed:
        formal_reason = "seed/dev corpus"
    else:
        formal_reason = (
            f"below formal corpus gate "
            f"({len(analyzed_repos)}/{args.min_formal_repos} analyzed repositories)"
        )

    for r in rows:
        r["split"] = split_repo(r["repo"])
    train = [r for r in rows if r["split"] == "train"]
    dev = [r for r in rows if r["split"] == "dev"]
    test = [r for r in rows if r["split"] == "test"]

    report = {
        "formal": formal,
        "formal_reason": formal_reason,
        "n_rows": len(rows),
        "n_repos": len({r["repo"] for r in rows}),
        "seed_dev_rows": seed_n,
        "min_formal_repos": args.min_formal_repos,
        "corpus_coverage": {
            "expected_events": expected_events,
            "expected_repos": expected_repos,
            "analyzed_repos": len(analyzed_repos),
            "repo_coverage": (
                len(analyzed_repos) / expected_repos
                if expected_repos else None
            ),
        },
        "splits": {
            "train_rows": len(train), "dev_rows": len(dev), "test_rows": len(test),
            "train_repos": len({r["repo"] for r in train}),
            "dev_repos": len({r["repo"] for r in dev}),
            "test_repos": len({r["repo"] for r in test}),
        },
        "arms": {},
    }

    probs = {}
    for arm, groups in ARMS.items():
        fitted = fit_arm(train, dev, test, groups)
        probs[arm] = np.asarray(fitted.pop("test_probs"), dtype=float)
        report["arms"][arm] = fitted

    # Descriptive held-out metrics by preregistered event class. Thresholds are
    # still selected globally on DEV; no stratum-specific tuning is performed.
    strata = {}
    event_types = sorted({r["event_type"] for r in test})
    for etype in event_types:
        idx = [i for i, r in enumerate(test) if r["event_type"] == etype]
        y = np.asarray([int(test[i]["label"]) for i in idx], dtype=int)
        strata[etype] = {}
        for arm in ARMS:
            threshold = float(report["arms"][arm]["test"].get("threshold", 0.5))
            p = probs[arm][idx]
            strata[etype][arm] = metric_block(y, p, threshold)
    report["strata"] = strata

    report["matching"] = matching_diagnostics(test)
    report["localization"] = localization(test)
    report["deltas"] = bootstrap_arm_deltas(test, probs, n_boot=args.bootstrap)
    report["holm"] = holm_bonferroni(report["deltas"])

    Path(args.json_out).write_text(json.dumps(report, indent=2) + "\n")
    Path(args.md_out).write_text(to_markdown(report))
    print(to_markdown(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
