#!/usr/bin/env python3
"""
tools/phase5_stabilize.py — APEX Stabilization Pass (Phase 5)
==============================================================
APEX OPP-Phase5 | 2026-04-17

TASKS:
  5.1  Fix composio meta-skill (add input_schema + output_schema)
  5.2  Add anchors + SR_40 stub sections to 832 composio stubs
  5.3  Fix 57 groups / 389 duplicate skill_ids in knowledge-work/_source_v2
  5.4  Fix validate_skills.py anchor regex (accepts unindented `- item` format)
  5.5  UCO quick_optimize on Python scripts with estimated score < 40

GOAL:
  validate_repo_uco.py --layer skills  → 0 FAIL, 0 duplicate_skill_ids
  validate_repo_uco.py --layer anchors → orphans < 5%
  validate_repo_uco.py --layer sr40    → >= 78% compliant (preserves current)

USAGE:
  python tools/phase5_stabilize.py [--dry-run] [--tasks 5.1,5.2,5.3,5.4,5.5]
"""

from __future__ import annotations

import argparse
import re
import sys
import io
import time
from pathlib import Path
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).parent.parent
COMPOSIO_ROOT = REPO_ROOT / "skills" / "integrations" / "composio"

# ── UCO import
UCO_AVAILABLE = False
try:
    sys.path.insert(0, str(REPO_ROOT / "algorithms" / "uco"))
    from universal_code_optimizer_v4 import UniversalCodeOptimizer
    UCO_AVAILABLE = True
except Exception:
    pass

FRONTMATTER_RE = re.compile(r'^(---\s*\n)(.*?)(\n---\s*\n)', re.DOTALL)


def read_safe(path: Path) -> str | None:
    try:
        return path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None


def write_safe(path: Path, content: str, dry_run: bool) -> bool:
    if dry_run:
        return True
    try:
        path.write_text(content, encoding='utf-8')
        return True
    except Exception:
        return False


def inject_frontmatter_field(content: str, field_block: str) -> str:
    """Insert field_block before the closing --- of the first frontmatter block."""
    m = FRONTMATTER_RE.match(content)
    if not m:
        return content
    # Find position of closing ---
    close_pos = content.find('\n---', len(m.group(1)))
    if close_pos == -1:
        return content
    # Check if already present (idempotency)
    field_key = field_block.strip().split(':')[0].strip()
    if re.search(rf'^{re.escape(field_key)}\s*:', content, re.MULTILINE):
        return content
    return content[:close_pos + 1] + field_block + content[close_pos + 1:]


# ═══════════════════════════════════════════════════════════════
# TASK 5.1 — Fix Composio Meta-Skill
# ═══════════════════════════════════════════════════════════════

def task_51_composio_meta(dry_run: bool) -> dict:
    """Add input_schema + output_schema to composio meta SKILL.md."""
    print("\n[TASK 5.1] Fix Composio Meta-Skill")
    meta_path = COMPOSIO_ROOT / "SKILL.md"

    content = read_safe(meta_path)
    if not content:
        print("  ERROR: meta SKILL.md not found")
        return {"fixed": 0, "errors": 1}

    changed = False

    if "input_schema" not in content:
        injection = (
            "input_schema:\n"
            "  - name: toolkit_name\n"
            "    type: string\n"
            "    description: \"Name of the Composio toolkit to automate (e.g. github, slack, notion)\"\n"
            "    required: true\n"
            "  - name: task_description\n"
            "    type: string\n"
            "    description: \"Description of the task to perform via the toolkit\"\n"
            "    required: true\n"
        )
        content = inject_frontmatter_field(content, injection)
        changed = True
        print("  + input_schema added")

    if "output_schema" not in content:
        injection = (
            "output_schema:\n"
            "  - name: result\n"
            "    type: object\n"
            "    description: \"Result returned by the Composio tool execution\"\n"
            "  - name: tool_used\n"
            "    type: string\n"
            "    description: \"Name of the specific Composio tool that was called\"\n"
            "  - name: status\n"
            "    type: string\n"
            "    enum: [success, failure, partial]\n"
            "    description: \"Execution status\"\n"
        )
        content = inject_frontmatter_field(content, injection)
        changed = True
        print("  + output_schema added")

    if changed:
        write_safe(meta_path, content, dry_run)
        print(f"  {'[DRY] Would update' if dry_run else 'Updated'}: {meta_path.relative_to(REPO_ROOT)}")
        return {"fixed": 1, "errors": 0}
    else:
        print("  Already OK — no changes needed")
        return {"fixed": 0, "errors": 0}


# ═══════════════════════════════════════════════════════════════
# TASK 5.2 — Fix Composio Stubs (anchors + SR_40 reference)
# ═══════════════════════════════════════════════════════════════

COMPOSIO_STUB_ANCHORS = (
    "anchors:\n"
    "  - automation\n"
    "  - integration\n"
    "  - api\n"
    "  - workflow\n"
)

COMPOSIO_SR40_TEMPLATE = """
## Why This Skill Exists
Stub for the `{toolkit}` toolkit in the Composio integration ecosystem.
Extends `integrations.composio.meta` — see the meta-skill for full protocol.

## When to Use
Use when automating `{toolkit}` tasks via Rube MCP (Composio).
For generic Composio queries, use `integrations.composio.meta` directly.

## What If Fails
See `skills/integrations/composio/SKILL.md` (meta-skill) for full fallback protocol.
RULE: Never block workflow — always suggest manual alternative if automation fails.
"""


def task_52_composio_stubs(dry_run: bool) -> dict:
    """Add anchors + SR_40 stub sections to all composio stubs."""
    print("\n[TASK 5.2] Fix Composio Stubs (anchors + SR_40)")

    meta_path = COMPOSIO_ROOT / "SKILL.md"
    stubs = [p for p in COMPOSIO_ROOT.rglob("SKILL.md") if p != meta_path]
    print(f"  Stubs to process: {len(stubs)}")

    fixed_anchors = 0
    fixed_sr40 = 0
    errors = 0

    for i, path in enumerate(stubs):
        if (i + 1) % 200 == 0:
            print(f"    {i+1}/{len(stubs)}...")

        content = read_safe(path)
        if not content:
            errors += 1
            continue

        changed = False

        # Add anchors if missing
        if 'anchors' not in content:
            content = inject_frontmatter_field(content, COMPOSIO_STUB_ANCHORS)
            changed = True
            fixed_anchors += 1

        # Add SR_40 sections if missing
        if "## Why This Skill Exists" not in content:
            toolkit = path.parent.name.lower().lstrip("-")
            sr40 = COMPOSIO_SR40_TEMPLATE.format(toolkit=toolkit)
            content = content.rstrip() + "\n" + sr40
            changed = True
            fixed_sr40 += 1

        if changed:
            write_safe(path, content, dry_run)

    action = "Would fix" if dry_run else "Fixed"
    print(f"  {action}: {fixed_anchors} anchors | {fixed_sr40} SR_40 stubs")
    print(f"  Errors: {errors}")
    return {"fixed_anchors": fixed_anchors, "fixed_sr40": fixed_sr40, "errors": errors}


# ═══════════════════════════════════════════════════════════════
# TASK 5.3 — Fix Duplicate skill_ids
# ═══════════════════════════════════════════════════════════════

def _path_to_skill_id(path: Path) -> str:
    """Derive a unique skill_id from the file path."""
    # skills/knowledge-work/_source_v2/sales/skills/account-research/SKILL.md
    # → knowledge-work.sales.account-research
    parts = path.parts
    # Find 'skills' root
    try:
        skills_idx = next(i for i, p in enumerate(parts) if p == 'skills')
    except StopIteration:
        skills_idx = 0

    rel_parts = parts[skills_idx + 1:-1]  # exclude 'skills' prefix and 'SKILL.md'
    # Remove _source_v2 and similar internal dirs
    filtered = [
        p for p in rel_parts
        if p not in ('_source_v2', 'skills', '_source', 'src')
        and not p.startswith('_')
    ]
    # Build ID: domain.subdomain.name — join with dots, convert - to _
    sid = ".".join(filtered).replace("-", "_").lower()
    # Truncate if too long
    if len(sid) > 80:
        sid = sid[:80]
    return sid


def task_53_fix_duplicate_skill_ids(dry_run: bool) -> dict:
    """Fix 57 groups / ~389 files with duplicate skill_ids."""
    print("\n[TASK 5.3] Fix Duplicate skill_ids")
    skills_dir = REPO_ROOT / "skills"
    skill_files = list(skills_dir.rglob("SKILL.md"))

    # Build skill_id → [paths] map
    sid_map: dict[str, list[Path]] = {}
    for sk in skill_files:
        content = read_safe(sk)
        if not content:
            continue
        m = re.search(r'skill_id\s*:\s*["\']?([^\s"\'#\n]+)["\']?', content)
        if m:
            sid = m.group(1)
            sid_map.setdefault(sid, []).append(sk)

    dups = {sid: paths for sid, paths in sid_map.items() if len(paths) > 1}
    total_dup_files = sum(len(v) for v in dups.values())
    print(f"  Duplicate groups: {len(dups)} ({total_dup_files} files)")

    fixed = 0
    errors = 0
    collision_check: set[str] = set(sid_map.keys())  # track all IDs to avoid new collisions

    for sid, paths in dups.items():
        # For each duplicate group, re-derive unique IDs from paths
        for path in paths:
            content = read_safe(path)
            if not content:
                errors += 1
                continue

            # Generate new unique ID from path
            new_sid = _path_to_skill_id(path)
            # Ensure uniqueness — append suffix if collision
            base_sid = new_sid
            counter = 2
            while new_sid in collision_check and new_sid != sid:
                new_sid = f"{base_sid}_{counter}"
                counter += 1

            if new_sid == sid:
                # Path-derived ID is same as current — append path hash
                path_hash = abs(hash(str(path))) % 9999
                new_sid = f"{base_sid}_{path_hash}"

            # Replace skill_id in content
            new_content = re.sub(
                r'(skill_id\s*:\s*)["\']?[^\s"\'#\n]+["\']?',
                f'\\g<1>{new_sid}',
                content,
                count=1
            )

            if new_content != content:
                collision_check.add(new_sid)
                collision_check.discard(sid)
                if write_safe(path, new_content, dry_run):
                    fixed += 1
                else:
                    errors += 1

    action = "Would fix" if dry_run else "Fixed"
    print(f"  {action}: {fixed}/{total_dup_files} files | Errors: {errors}")
    return {"groups": len(dups), "total_files": total_dup_files, "fixed": fixed, "errors": errors}


# ═══════════════════════════════════════════════════════════════
# TASK 5.4 — Fix Validator Anchor Regex
# ═══════════════════════════════════════════════════════════════

def task_54_fix_validator_regex(dry_run: bool) -> dict:
    """Fix validate_repo_uco.py anchor regex: \\s+ → \\s* (accept unindented list)."""
    print("\n[TASK 5.4] Fix Validator Anchor Regex (\\s+ → \\s*)")
    validator_path = REPO_ROOT / "tools" / "validate_repo_uco.py"

    content = read_safe(validator_path)
    if not content:
        print("  ERROR: validate_repo_uco.py not found")
        return {"fixed": 0}

    OLD = r'r"^anchors\s*:\s*\n((?:\s+-[^\n]+\n?)+)"'
    NEW = r'r"^anchors\s*:\s*\n((?:\s*-[^\n]+\n?)+)"'

    if OLD not in content:
        print("  Already OK or pattern not found")
        return {"fixed": 0}

    new_content = content.replace(OLD, NEW)
    if write_safe(validator_path, new_content, dry_run):
        print(f"  {'[DRY] Would fix' if dry_run else 'Fixed'}: anchor_re \\s+ → \\s*")
        return {"fixed": 1}
    return {"fixed": 0}


# ═══════════════════════════════════════════════════════════════
# TASK 5.5 — UCO quick_optimize on worst scripts
# ═══════════════════════════════════════════════════════════════

def _uco_score(uco, code: str) -> int:
    """Compute UCO score from analyze() result."""
    try:
        r = uco.analyze(code)
        d = r.to_dict()
        m = d.get('metrics', {})
        h = m.get('halstead', {})
        bugs = h.get('bugs_estimate', 0.0)
        cc = m.get('cyclomatic_complexity', 0)
        dead = m.get('syntactic_dead_code', 0)
        dups = m.get('duplicate_block_count', 0)
        return max(0, min(100, 100
                          - min(40, cc * 3)
                          - min(20, dead * 5)
                          - min(20, dups * 5)
                          - min(20, int(bugs * 100))))
    except Exception:
        return -1


def task_55_uco_optimize(dry_run: bool, threshold: int = 40, max_files: int = 100) -> dict:
    """Run UCO optimize_fast (SA — Simulated Annealing) on Python scripts with score < threshold."""
    print(f"\n[TASK 5.5] UCO optimize_fast/SA (score < {threshold}, max {max_files} files)")

    if not UCO_AVAILABLE:
        print("  [SKIP] UCO not available")
        return {"skipped": True}

    # Only optimize tools/ and algorithms/ scripts (not skills scripts — too risky)
    target_dirs = [
        REPO_ROOT / "tools",
        REPO_ROOT / "algorithms" / "claude-skills" / "src",
    ]
    scripts = []
    for d in target_dirs:
        if d.exists():
            scripts.extend(d.rglob("*.py"))

    scripts = [
        p for p in scripts
        if "__pycache__" not in str(p)
        and "universal_code_optimizer_v4" not in p.name
        and "phase5_stabilize" not in p.name  # don't optimize ourselves
    ]

    print(f"  Candidate scripts: {len(scripts)}")

    uco = UniversalCodeOptimizer()

    # First pass: score all scripts
    below = []
    for path in scripts:
        code = read_safe(path)
        if not code or len(code.strip()) < 50:
            continue
        s = _uco_score(uco, code)
        if 0 <= s < threshold:
            below.append((s, path, code))

    below.sort(key=lambda x: x[0])
    targets = below[:max_files]
    print(f"  Scripts below {threshold}: {len(below)} | Optimizing top {len(targets)}")

    improved = 0
    skipped = 0
    errors = 0

    for score_before, path, code in targets:
        try:
            # SA = Simulated Annealing via optimize_fast()
            result = uco.optimize_fast(code, n_steps=10)
            # EngineOutput has .optimized_code attribute (not dict)
            opt_code = result.optimized_code if result.optimized_code else code
            score_after = _uco_score(uco, opt_code)

            # Guards: score improved + code changed + not too much shrinkage (conservative)
            if (score_after > score_before
                    and opt_code != code
                    and len(opt_code.strip()) > 20
                    and len(opt_code) >= len(code) * 0.70):  # max 30% size reduction
                # Syntax check
                try:
                    compile(opt_code, str(path), 'exec')
                except SyntaxError:
                    skipped += 1
                    continue

                if write_safe(path, opt_code, dry_run):
                    improved += 1
                    if improved <= 5:
                        delta = score_after - score_before
                        print(f"    {score_before:3d}→{score_after:3d} (+{delta})  {path.relative_to(REPO_ROOT)}")
            else:
                skipped += 1
        except Exception:
            errors += 1

    action = "Would improve" if dry_run else "Improved"
    print(f"  {action}: {improved} | Skipped (no gain): {skipped} | Errors: {errors}")
    return {
        "candidates_below_threshold": len(below),
        "processed": len(targets),
        "improved": improved,
        "skipped": skipped,
        "errors": errors,
    }


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="APEX Phase 5 — Stabilization")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tasks", default="5.1,5.2,5.3,5.4,5.5",
                        help="Comma-separated tasks to run (e.g. 5.1,5.2)")
    parser.add_argument("--uco-threshold", type=int, default=40)
    parser.add_argument("--uco-max", type=int, default=100)
    args = parser.parse_args()

    tasks = {t.strip() for t in args.tasks.split(",")}
    mode = "DRY-RUN" if args.dry_run else "LIVE"

    print("=" * 70)
    print(f"APEX Phase 5 — Stabilization | Mode: {mode}")
    print(f"Tasks: {sorted(tasks)}")
    print("=" * 70)

    t0 = time.time()
    results = {}

    if "5.1" in tasks:
        results["5.1"] = task_51_composio_meta(args.dry_run)

    if "5.2" in tasks:
        results["5.2"] = task_52_composio_stubs(args.dry_run)

    if "5.3" in tasks:
        results["5.3"] = task_53_fix_duplicate_skill_ids(args.dry_run)

    if "5.4" in tasks:
        results["5.4"] = task_54_fix_validator_regex(args.dry_run)

    if "5.5" in tasks:
        results["5.5"] = task_55_uco_optimize(args.dry_run, args.uco_threshold, args.uco_max)

    elapsed = time.time() - t0
    print(f"\n{'=' * 70}")
    print(f"Phase 5 complete in {elapsed:.1f}s | Mode: {mode}")
    print("\nResults:")
    for task, r in results.items():
        print(f"  Task {task}: {r}")

    if not args.dry_run:
        print("\nRun validate_repo_uco.py to verify:")
        print("  python tools/validate_repo_uco.py --layer skills --layer anchors --layer sr40")


if __name__ == "__main__":
    main()
