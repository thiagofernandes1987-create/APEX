#!/usr/bin/env python3
"""
tools/import_zip_skills.py — Import skills from external zip repos into APEX
=============================================================================
APEX OPP-Phase5 | 2026-04-17

Imports SKILL.md files from external zip repositories into the appropriate
skills/ domain directory, applying APEX normalization (executor, skill_id,
status, security, SR_40 sections via phase3_quality patterns).

USAGE:
  python tools/import_zip_skills.py <zip_path> [<zip_path2> ...] [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

# Domain mapping: zip stem → skills/ subdomain
ZIP_DOMAIN_MAP = {
    "ui-ux-pro-max-skill-main": "design",
    "azure-skills-main":        "engineering_cloud_azure",
    "soultrace-skill-main":     "community_general",
    "agent-skills-main":        "engineering_agentops",
}

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
SR40_SECTIONS = ["## Why This Skill Exists", "## When to Use", "## What If Fails"]

APEX_NORMALIZATION_FIELDS = {
    "executor":   "LLM_BEHAVIOR",
    "status":     "CANDIDATE",
    "security":   "{ level: standard, pii: false, approval_required: false }",
}


def extract_skill_files(zip_path: Path) -> list[tuple[str, str]]:
    """Return list of (relative_path, content) for all SKILL.md in zip."""
    results = []
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.endswith("SKILL.md") and not name.endswith("/"):
                try:
                    content = zf.read(name).decode('utf-8', errors='replace')
                    results.append((name, content))
                except Exception:
                    pass
    return results


def infer_skill_name(zip_path_in_zip: str) -> str:
    """Extract skill folder name from zip path."""
    parts = Path(zip_path_in_zip).parts
    # Find the part before SKILL.md
    if len(parts) >= 2:
        return parts[-2]
    return "unknown"


def normalize_skill_content(content: str, skill_name: str, domain: str) -> str:
    """Apply APEX normalization: executor, status, security, SR_40, skill_id."""
    # Check if frontmatter exists
    fm_match = FRONTMATTER_RE.match(content)
    if not fm_match:
        return content  # no frontmatter — skip normalization

    # Add missing fields
    injections = []

    # skill_id
    if 'skill_id' not in content:
        sid = f"{domain}.{skill_name.replace('-', '_').lower()}"
        injections.append(f"skill_id: {sid}\n")

    # executor
    if 'executor' not in content:
        # Heuristic: if skill has scripts → HYBRID, else LLM_BEHAVIOR
        exec_val = "HYBRID" if "scripts/" in content or "```bash" in content else "LLM_BEHAVIOR"
        injections.append(f"executor: {exec_val}\n")

    # status
    if 'status' not in content:
        injections.append("status: CANDIDATE\n")

    # security
    if 'security' not in content:
        injections.append("security: { level: standard, pii: false, approval_required: false }\n")

    # version
    if 'version' not in content:
        injections.append("version: v00.36.0\n")

    # anchors — derive from name + domain
    if 'anchors' not in content:
        domain_anchors = {
            "design":                  ["design", "frontend", "engineering"],
            "engineering_cloud_azure": ["cloud", "engineering", "devops"],
            "community_general":       ["agent", "automation"],
            "engineering_agentops":    ["engineering", "agent", "orchestration"],
        }
        anchors = domain_anchors.get(domain, ["engineering"])
        anchor_block = "anchors:\n" + "".join(f"  - {a}\n" for a in anchors)
        injections.append(anchor_block)

    # Inject all fields before closing ---
    if injections:
        close_pos = content.find('\n---', len('---\n'))
        if close_pos != -1:
            injection_str = "".join(injections)
            content = content[:close_pos + 1] + injection_str + content[close_pos + 1:]

    # Add SR_40 sections if missing
    missing_sections = [s for s in SR40_SECTIONS if s not in content]
    if missing_sections:
        sr40_block = f"""
## Why This Skill Exists
<!-- TODO: describe why this skill was created and what problem it solves -->
Provides specialized `{skill_name}` capability to the APEX system.

## When to Use
<!-- TODO: describe when to invoke this skill vs alternatives -->
Use this skill when working with `{skill_name}` tasks in the `{domain}` domain.

## What If Fails
<!-- TODO: describe fallback behavior -->
FALLBACK: Use a related skill in the `{domain}` domain.
RULE: Never block workflow — always suggest manual alternative.
"""
        content = content.rstrip() + "\n" + sr40_block

    return content


def import_zip(zip_path: Path, domain: str, dry_run: bool) -> dict:
    """Import all SKILL.md files from a zip into skills/{domain}/."""
    target_dir = SKILLS_ROOT / domain
    skill_files = extract_skill_files(zip_path)

    imported = 0
    skipped = 0
    errors = 0

    for zip_internal_path, content in skill_files:
        skill_name = infer_skill_name(zip_internal_path)
        dest = target_dir / skill_name / "SKILL.md"

        # Skip if already exists (idempotent)
        if dest.exists():
            skipped += 1
            continue

        # Normalize
        normalized = normalize_skill_content(content, skill_name, domain)

        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(normalized, encoding='utf-8')

        imported += 1

    return {"imported": imported, "skipped": skipped, "errors": errors}


def main():
    parser = argparse.ArgumentParser(description="Import zip skill repos into APEX")
    parser.add_argument("zips", nargs="*", help="Zip file paths")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Default to the 4 known zips if none specified
    default_zips = [
        (Path(r"C:\Users\Thiag\Downloads\ui-ux-pro-max-skill-main.zip"), "design"),
        (Path(r"C:\Users\Thiag\Downloads\azure-skills-main.zip"),        "engineering_cloud_azure"),
        (Path(r"C:\Users\Thiag\Downloads\soultrace-skill-main.zip"),     "community_general"),
        (Path(r"C:\Users\Thiag\Downloads\agent-skills-main.zip"),        "engineering_agentops"),
    ]

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\nAPEX Zip Import | Mode: {mode}")
    print("=" * 60)

    total_imported = 0
    total_skipped = 0

    for zip_path, domain in default_zips:
        if not zip_path.exists():
            print(f"  SKIP (not found): {zip_path.name}")
            continue

        with zipfile.ZipFile(zip_path) as zf:
            skill_count = sum(1 for n in zf.namelist() if n.endswith("SKILL.md"))

        print(f"\n{zip_path.stem}")
        print(f"  Domain:      skills/{domain}/")
        print(f"  SKILL.md:    {skill_count}")

        result = import_zip(zip_path, domain, args.dry_run)
        action = "Would import" if args.dry_run else "Imported"
        print(f"  {action}: {result['imported']} | Skipped (exists): {result['skipped']}")

        total_imported += result["imported"]
        total_skipped += result["skipped"]

    print(f"\n{'=' * 60}")
    print(f"Total: {total_imported} imported | {total_skipped} already existed")

    if not args.dry_run:
        print("\nNext: run python tools/phase3_quality.py to apply SR_40 + anchors")
        print("      run python tools/normalize_schema.py to normalize executor/security")


if __name__ == "__main__":
    main()
