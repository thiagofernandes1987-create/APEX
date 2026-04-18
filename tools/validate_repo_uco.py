#!/usr/bin/env python3
"""
tools/validate_repo_uco.py — Validação Completa do Repositório APEX com UCO
=============================================================================
APEX OPP-Phase4 | 2026-04-17

Executa 4 camadas de validação:
  1. UCO.analyze() em todos os scripts Python — Halstead, cyclomatic, bugs, score
  2. SKILL.md schema validation — campos obrigatórios, skill_id único, executor
  3. Anchor validation — cobertura de canonical anchors, orphans sem anchors
  4. SR_40 compliance — presença de Why/When/WhatIf sections

USAGE:
  python tools/validate_repo_uco.py [--layer {uco,skills,anchors,sr40,all}]
                                    [--threshold SCORE] [--sample N] [--output FILE]
"""

from __future__ import annotations

import argparse
import re
import sys
import io
import json
import time
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).parent.parent

# ── UCO import (stdlib-only fallback se não disponível)
UCO_AVAILABLE = False
try:
    import sys as _sys
    _sys.path.insert(0, str(REPO_ROOT / "algorithms" / "uco"))
    from universal_code_optimizer_v4 import UniversalCodeOptimizer
    UCO_AVAILABLE = True
except Exception as _e:
    print(f"  [WARN] UCO não disponível: {_e}  — usando análise stdlib fallback")

# ── Canonical anchors (from phase3_quality.py)
CANONICAL_ANCHORS = {
    "agent", "automation", "analysis", "security", "workflow", "code",
    "testing", "debugging", "documentation", "api", "database", "deployment",
    "monitoring", "optimization", "refactoring", "architecture", "review",
    "planning", "research", "data", "ml", "llm", "cloud", "frontend",
    "backend", "devops", "design", "writing", "communication", "finance",
    "legal", "marketing", "sales", "operations", "hr", "product",
    "engineering", "science", "education", "healthcare", "productivity",
    "integration", "pipeline", "orchestration", "reasoning", "generation",
    "summarization", "extraction", "classification", "search", "retrieval",
    "validation", "parsing", "transformation", "visualization", "reporting",
}

SR40_SECTIONS = ["## Why This Skill Exists", "## When to Use", "## What If Fails"]
REQUIRED_ADOPTED = ["skill_id", "description", "tier", "executor", "anchors",
                    "input_schema", "output_schema", "what_if_fails"]


# ═══════════════════════════════════════════════════════════════
# LAYER 1 — UCO Script Analysis
# ═══════════════════════════════════════════════════════════════

def analyze_scripts_uco(sample: int = 0, threshold: int = 60, use_sa: bool = True) -> dict:
    """use_sa=True: also runs optimize_fast (SA) on worst scripts to show improvement potential."""
    """Run UCO.analyze() on Python scripts. Returns summary + failures."""
    print("\n[LAYER 1] UCO Script Analysis")
    print("  Collecting Python scripts...")

    scripts = list(REPO_ROOT.rglob("*.py"))
    # Exclude: __pycache__, .git, test fixtures, the UCO source itself
    scripts = [
        p for p in scripts
        if "__pycache__" not in str(p)
        and ".git" not in str(p)
        and "universal_code_optimizer_v4" not in p.name
    ]

    total = len(scripts)
    if sample and sample < total:
        import random
        random.seed(42)
        scripts = random.sample(scripts, sample)
        print(f"  Sampling {sample}/{total} scripts (seed=42)")
    else:
        print(f"  Processing all {total} scripts...")

    if not UCO_AVAILABLE:
        print("  [SKIP] UCO not available — running stdlib fallback (complexity heuristic)")
        return _fallback_script_analysis(scripts, threshold)

    uco = UniversalCodeOptimizer()
    results = []
    low_score = []
    high_bugs = []
    scores = []
    errors = 0

    for i, path in enumerate(scripts):
        if (i + 1) % 100 == 0:
            print(f"    {i+1}/{len(scripts)}...")
        try:
            code = path.read_text(encoding='utf-8', errors='replace')
            if len(code.strip()) < 10:
                continue
            r = uco.analyze(code)
            d = r.to_dict()
            m = d.get('metrics', {})
            h = m.get('halstead', {})
            bugs = h.get('bugs_estimate', 0.0)
            cc = m.get('cyclomatic_complexity', 0)
            dead = m.get('syntactic_dead_code', 0)
            dups = m.get('duplicate_block_count', 0)
            H = h.get('difficulty', 0.0)
            # Compute quality score 0-100
            score = max(0, min(100, 100
                        - min(40, cc * 3)
                        - min(20, dead * 5)
                        - min(20, dups * 5)
                        - min(20, int(bugs * 100))))
            scores.append(score)
            entry = {
                "path": str(path.relative_to(REPO_ROOT)),
                "score": score,
                "bugs": round(bugs, 4),
                "complexity": cc,
                "H": round(H, 2),
                "dead_code_count": dead,
                "duplicates_count": dups,
            }
            results.append(entry)
            if score < threshold:
                low_score.append(entry)
            if bugs >= 0.1:
                high_bugs.append(entry)
        except Exception:
            errors += 1

    avg_score = sum(scores) / len(scores) if scores else 0
    below_threshold = len(low_score)

    print(f"  Analyzed: {len(results)} | Errors: {errors}")
    print(f"  Avg score: {avg_score:.1f} | Below {threshold}: {below_threshold}")
    print(f"  High-bug scripts (bugs>=0.1): {len(high_bugs)}")

    # Top 10 worst
    worst = sorted(low_score, key=lambda x: x['score'])[:10]
    if worst:
        print(f"\n  Top 10 lowest scores (< {threshold}):")
        for r in worst:
            print(f"    score={r['score']:3d} bugs={r['bugs']:.3f} H={r['H']:6.1f}  {r['path']}")

    # SA improvement potential on top-5 worst (read-only, diagnostic)
    sa_gains = []
    if use_sa and UCO_AVAILABLE and worst:
        print(f"\n  SA improvement potential (optimize_fast, read-only):")
        for entry in worst[:5]:
            try:
                code = (REPO_ROOT / entry['path']).read_text(encoding='utf-8', errors='replace')
                sa_result = uco.optimize_fast(code, n_steps=5)
                opt = sa_result.optimized_code if sa_result.optimized_code else code
                # Recompute score for optimized code
                r2 = uco.analyze(opt)
                d2 = r2.to_dict()
                m2 = d2.get('metrics', {})
                h2 = m2.get('halstead', {})
                bugs2 = h2.get('bugs_estimate', 0.0)
                cc2 = m2.get('cyclomatic_complexity', 0)
                dead2 = m2.get('syntactic_dead_code', 0)
                dups2 = m2.get('duplicate_block_count', 0)
                score2 = max(0, min(100, 100
                            - min(40, cc2 * 3)
                            - min(20, dead2 * 5)
                            - min(20, dups2 * 5)
                            - min(20, int(bugs2 * 100))))
                delta = score2 - entry['score']
                sa_gains.append(delta)
                sign = "+" if delta >= 0 else ""
                print(f"    {entry['score']:3d} → {score2:3d} ({sign}{delta:+d})  {entry['path'][:60]}")
            except Exception:
                pass
        if sa_gains:
            avg_gain = sum(sa_gains) / len(sa_gains)
            print(f"  Avg SA gain on top-5 worst: {avg_gain:+.1f} pts")

    return {
        "total_scripts": total,
        "analyzed": len(results),
        "errors": errors,
        "avg_score": round(avg_score, 2),
        "below_threshold": below_threshold,
        "threshold": threshold,
        "high_bugs": len(high_bugs),
        "worst": worst,
        "sa_avg_gain_top5": round(sum(sa_gains) / len(sa_gains), 2) if sa_gains else None,
        "all_results": results,
    }


def _fallback_script_analysis(scripts: list, threshold: int) -> dict:
    """Stdlib-only: count lines, rough complexity via re."""
    results = []
    for path in scripts:
        try:
            code = path.read_text(encoding='utf-8', errors='replace')
            lines = code.count('\n')
            # Rough complexity: count if/for/while/try branches
            branches = len(re.findall(r'\b(if|elif|for|while|try|except|with)\b', code))
            score = max(0, 100 - max(0, branches - 10) * 2 - max(0, lines - 200) // 10)
            results.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "score": min(100, score),
                "lines": lines,
                "branches": branches,
            })
        except Exception:
            pass

    low = [r for r in results if r['score'] < threshold]
    avg = sum(r['score'] for r in results) / len(results) if results else 0

    print(f"  Analyzed (fallback): {len(results)} | Below {threshold}: {len(low)}")
    print(f"  Avg estimated score: {avg:.1f}")

    worst = sorted(low, key=lambda x: x['score'])[:10]
    if worst:
        print(f"\n  Top 10 lowest estimated scores:")
        for r in worst:
            print(f"    score={r['score']:3d} branches={r.get('branches',0):3d}  {r['path']}")

    return {
        "total_scripts": len(scripts),
        "analyzed": len(results),
        "errors": 0,
        "avg_score": round(avg, 2),
        "below_threshold": len(low),
        "threshold": threshold,
        "mode": "fallback",
        "worst": worst,
    }


# ═══════════════════════════════════════════════════════════════
# LAYER 2 — SKILL.md Schema Validation
# ═══════════════════════════════════════════════════════════════

def validate_skills_schema() -> dict:
    """Validate SKILL.md files for required fields, skill_id uniqueness, executor."""
    print("\n[LAYER 2] SKILL.md Schema Validation")
    skills_dir = REPO_ROOT / "skills"
    skill_files = list(skills_dir.rglob("SKILL.md"))
    total = len(skill_files)
    print(f"  Processing {total} SKILL.md files...")

    results = []
    skill_ids = []
    executor_missing = []
    status_counts = Counter()
    tier_counts = Counter()

    for sk in skill_files:
        try:
            content = sk.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        status_m = re.search(r'status\s*:\s*(\w+)', content)
        status = status_m.group(1).upper() if status_m else "UNKNOWN"
        sid_m = re.search(r'skill_id\s*:\s*["\']?([^\s"\'#\n]+)["\']?', content)
        sid = sid_m.group(1) if sid_m else None
        tier_m = re.search(r'tier\s*:\s*([^\n]+)', content)
        tier = tier_m.group(1).strip() if tier_m else "NONE"
        has_executor = 'executor' in content

        required = REQUIRED_ADOPTED if status == "ADOPTED" else ["skill_id", "description", "anchors"]
        missing = [f for f in required if f not in content]

        status_counts[status] += 1
        tier_counts[tier] += 1
        if sid:
            skill_ids.append(sid)
        if not has_executor and status == "ADOPTED":
            executor_missing.append(str(sk.relative_to(REPO_ROOT)))

        results.append({
            "path": str(sk.relative_to(REPO_ROOT)),
            "skill_id": sid,
            "status": status,
            "tier": tier,
            "missing": missing,
            "ok": len(missing) == 0,
        })

    ok = sum(1 for r in results if r["ok"])
    fail = sum(1 for r in results if not r["ok"])
    dup_sids = {k: v for k, v in Counter(skill_ids).items() if v > 1}

    print(f"  Total: {total} | OK: {ok} | FAIL: {fail}")
    print(f"  Duplicate skill_ids: {len(dup_sids)}")
    print(f"  ADOPTED without executor: {len(executor_missing)}")
    print(f"  Status distribution: {dict(status_counts.most_common(5))}")
    print(f"  Tier distribution: {dict(tier_counts.most_common(5))}")

    fail_details = [r for r in results if not r["ok"]][:20]
    if fail_details:
        print(f"\n  First 20 failures:")
        for r in fail_details:
            print(f"    [{r['status']}] {r['path']}: faltam {r['missing']}")

    if dup_sids:
        print(f"\n  Duplicate skill_ids (first 10):")
        for sid, cnt in list(dup_sids.items())[:10]:
            print(f"    {sid} x{cnt}")

    return {
        "total": total,
        "ok": ok,
        "fail": fail,
        "duplicate_skill_ids": len(dup_sids),
        "executor_missing_in_adopted": len(executor_missing),
        "status_distribution": dict(status_counts),
        "tier_distribution": dict(tier_counts),
        "fail_rate_pct": round(fail / total * 100, 1) if total else 0,
    }


# ═══════════════════════════════════════════════════════════════
# LAYER 3 — Anchor Validation
# ═══════════════════════════════════════════════════════════════

def validate_anchors() -> dict:
    """Validate anchor coverage and canonical anchor usage."""
    print("\n[LAYER 3] Anchor Validation")
    skills_dir = REPO_ROOT / "skills"
    skill_files = list(skills_dir.rglob("SKILL.md"))
    total = len(skill_files)

    no_anchors = []
    non_canonical = Counter()
    canonical_usage = Counter()
    # \s*-\s+  requires space after dash → excludes --- YAML delimiters
    anchor_re = re.compile(r'^anchors\s*:\s*\n((?:\s*-\s+[^\n]+\n?)+)', re.MULTILINE)

    for sk in skill_files:
        try:
            content = sk.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        m = anchor_re.search(content)
        if not m:
            no_anchors.append(str(sk.relative_to(REPO_ROOT)))
            continue

        anchor_block = m.group(1)
        anchors = re.findall(r'-\s*([^\n#]+)', anchor_block)
        anchors = [a.strip().strip('"\'').lower() for a in anchors if a.strip()]

        for anchor in anchors:
            if anchor in CANONICAL_ANCHORS:
                canonical_usage[anchor] += 1
            else:
                non_canonical[anchor] += 1

    orphan_pct = len(no_anchors) / total * 100 if total else 0
    canonical_coverage = len(canonical_usage)
    unused_canonical = CANONICAL_ANCHORS - set(canonical_usage.keys())

    print(f"  Total skills: {total}")
    print(f"  Without anchors (orphans): {len(no_anchors)} ({orphan_pct:.1f}%)")
    print(f"  Canonical anchors used: {canonical_coverage}/{len(CANONICAL_ANCHORS)}")
    print(f"  Unused canonical anchors: {sorted(unused_canonical)[:10]}")
    print(f"  Non-canonical anchors (top 10): {non_canonical.most_common(10)}")
    print(f"  Top 10 canonical by usage: {canonical_usage.most_common(10)}")

    return {
        "total_skills": total,
        "orphan_count": len(no_anchors),
        "orphan_pct": round(orphan_pct, 1),
        "canonical_coverage": canonical_coverage,
        "total_canonical": len(CANONICAL_ANCHORS),
        "unused_canonical": sorted(unused_canonical),
        "top_anchors": canonical_usage.most_common(15),
        "non_canonical_top10": non_canonical.most_common(10),
    }


# ═══════════════════════════════════════════════════════════════
# LAYER 4 — SR_40 Compliance
# ═══════════════════════════════════════════════════════════════

def validate_sr40() -> dict:
    """Check SR_40 [ZERO_AMBIGUITY_GUARD] compliance: Why/When/WhatIf sections."""
    print("\n[LAYER 4] SR_40 Compliance Check")
    skills_dir = REPO_ROOT / "skills"
    skill_files = list(skills_dir.rglob("SKILL.md"))
    total = len(skill_files)
    # Exclude composio stubs (they extend meta-skill)
    non_composio = [
        p for p in skill_files
        if "composio" not in str(p).lower()
        or p.parent.parent.name.lower() == "composio"
    ]

    compliant = 0
    partial = 0
    missing_all = 0
    section_counts = Counter()

    for sk in non_composio:
        try:
            content = sk.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue

        found = sum(1 for s in SR40_SECTIONS if s in content)
        section_counts[found] += 1

        if found == 3:
            compliant += 1
        elif found > 0:
            partial += 1
        else:
            missing_all += 1

    checked = len(non_composio)
    compliance_pct = compliant / checked * 100 if checked else 0

    print(f"  Checked (non-composio): {checked}")
    print(f"  Full SR_40 (3/3 sections): {compliant} ({compliance_pct:.1f}%)")
    print(f"  Partial (1-2 sections): {partial}")
    print(f"  No SR_40 sections: {missing_all}")
    print(f"  Section count distribution: {dict(section_counts)}")

    return {
        "checked": checked,
        "compliant": compliant,
        "compliance_pct": round(compliance_pct, 1),
        "partial": partial,
        "missing_all": missing_all,
        "section_distribution": dict(section_counts),
    }


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="APEX Repo Full Validation with UCO")
    parser.add_argument("--layer", default="all",
                        choices=["uco", "skills", "anchors", "sr40", "all"])
    parser.add_argument("--threshold", type=int, default=60,
                        help="UCO score threshold (default: 60)")
    parser.add_argument("--sample", type=int, default=0,
                        help="Sample N scripts for UCO (0 = all)")
    parser.add_argument("--output", default=None,
                        help="Output JSON report file path")
    args = parser.parse_args()

    print("=" * 70)
    print("APEX Repository Full Validation — UCO + Schema + Anchors + SR_40")
    print(f"Repo: {REPO_ROOT}")
    print(f"UCO available: {UCO_AVAILABLE}")
    print("=" * 70)

    t0 = time.time()
    report = {"timestamp": "2026-04-17", "uco_available": UCO_AVAILABLE}

    if args.layer in ("uco", "all"):
        report["layer1_uco"] = analyze_scripts_uco(sample=args.sample, threshold=args.threshold)

    if args.layer in ("skills", "all"):
        report["layer2_skills"] = validate_skills_schema()

    if args.layer in ("anchors", "all"):
        report["layer3_anchors"] = validate_anchors()

    if args.layer in ("sr40", "all"):
        report["layer4_sr40"] = validate_sr40()

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"Validation complete in {elapsed:.1f}s")

    # Summary
    print("\n▶ SUMMARY:")
    if "layer1_uco" in report:
        l1 = report["layer1_uco"]
        print(f"  Scripts: {l1['analyzed']} analyzed | avg score: {l1.get('avg_score','N/A')} | "
              f"below {l1['threshold']}: {l1['below_threshold']}")
    if "layer2_skills" in report:
        l2 = report["layer2_skills"]
        print(f"  Skills:  {l2['total']} total | OK: {l2['ok']} | FAIL: {l2['fail']} "
              f"({l2['fail_rate_pct']}%) | dup_ids: {l2['duplicate_skill_ids']}")
    if "layer3_anchors" in report:
        l3 = report["layer3_anchors"]
        print(f"  Anchors: {l3['orphan_count']} orphans ({l3['orphan_pct']}%) | "
              f"canonical coverage: {l3['canonical_coverage']}/{l3['total_canonical']}")
    if "layer4_sr40" in report:
        l4 = report["layer4_sr40"]
        print(f"  SR_40:   {l4['compliant']}/{l4['checked']} ({l4['compliance_pct']}%) compliant")

    if args.output:
        out = Path(args.output)
        # Remove non-serializable UCO result details if huge
        if "layer1_uco" in report and "all_results" in report["layer1_uco"]:
            del report["layer1_uco"]["all_results"]
        out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"\n  Report saved: {out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
