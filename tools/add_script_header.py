"""
tools/add_script_header.py — APEX Phase 2 Task 2.8
====================================================
Injects APEX traceability header into Python scripts inside skills/
that don't already have one.

PURPOSE: Zero rastreabilidade script↔skill é o maior gap de qualidade
         nos 589 scripts Python. Com o header, cada script se identifica
         como parte da skill que o possui, habilitando auditoria e routing.

WHY: Nenhum dos 589 scripts Python em skills/ declara skill_id, purpose
     ou what_if_fails no cabeçalho — rastreabilidade é zero.

USAGE:
  python tools/add_script_header.py [--dry-run]
"""

from __future__ import annotations

import argparse
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

APEX_HEADER_MARKER = "skill_id:"
PHASE_MARKER = "APEX OPP-Phase2 / 2.8"


def derive_skill_id_from_script(script_path: pathlib.Path) -> str:
    """Derive skill_id by finding the parent SKILL.md and reading its skill_id."""
    # Walk up to find SKILL.md
    parent = script_path.parent
    for _ in range(4):
        skill_md = parent / "SKILL.md"
        if skill_md.exists():
            content = skill_md.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^skill_id:\s*(.+)$", content, re.MULTILINE)
            if m:
                return m.group(1).strip()
            # Derive from path
            try:
                rel = parent.relative_to(SKILLS_ROOT)
                parts = list(rel.parts)[:4]
                return ".".join(p.lower() for p in parts)
            except ValueError:
                break
        parent = parent.parent
    # Fallback: path-based
    try:
        rel = script_path.relative_to(SKILLS_ROOT)
        parts = list(rel.parts[:-1])[:4]
        return ".".join(p.lower() for p in parts)
    except ValueError:
        return script_path.stem


def build_header(script_path: pathlib.Path) -> str:
    skill_id = derive_skill_id_from_script(script_path)
    script_name = script_path.name
    return f'''"""
APEX Script Header ({PHASE_MARKER})
skill_id: {skill_id}
script_name: {script_name}
script_purpose: [TODO: one sentence — what this script does and when it is invoked]
why: [TODO: why this script exists — what problem it solves vs inline LLM reasoning]
what_if_fails: emit {{"error": "<message>", "code": 1}} to stderr; never block the parent skill.
apex_version: v00.36.0
"""
'''


def patch_script(path: pathlib.Path, dry_run: bool = False) -> bool:
    """Add APEX header to script if not already present."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    # Skip if already has APEX header
    if APEX_HEADER_MARKER in content[:500] or PHASE_MARKER in content[:500]:
        return False

    # Skip empty files
    if len(content.strip()) < 10:
        return False

    header = build_header(path)

    # If file starts with shebang, insert after it
    if content.startswith("#!"):
        first_newline = content.find("\n")
        new_content = content[:first_newline + 1] + header + content[first_newline + 1:]
    elif content.startswith('"""') or content.startswith("'''"):
        # Has existing docstring at top — insert before it
        new_content = header + content
    else:
        new_content = header + content

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Phase 2.8 — Add script headers")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"\nAPEX Phase 2.8 — Script Headers ({'DRY-RUN' if args.dry_run else 'LIVE'})")
    print(f"Root: {SKILLS_ROOT}\n")

    scripts = list(SKILLS_ROOT.rglob("*.py"))
    total = len(scripts)
    patched = 0
    skipped = 0

    for path in scripts:
        result = patch_script(path, dry_run=args.dry_run)
        if result:
            patched += 1
        else:
            skipped += 1

    action = "Would patch" if args.dry_run else "Patched"
    print(f"{action}: {patched}/{total} scripts")
    print(f"Already OK / empty: {skipped}")
    print(f"\nNext: fill in [TODO] sections in each script.")


if __name__ == "__main__":
    main()
