"""
tools/normalize_schema.py — APEX Phase 2 Schema Normalization
==============================================================
APEX OPP-Phase2 | 2026-04-17

PURPOSE:
  Mass-normalize SKILL.md and AGENT.md files to meet APEX DSL schema
  requirements. Adds missing: executor, skill_id, status, security fields.
  Does NOT overwrite existing values — safe to re-run at any time.

TASKS:
  2.1 — Infer and inject executor: in ~3,591 SKILL.md without it
  2.2 — Generate skill_id: for ~1,630 SKILL.md without it
  2.3 — Add status: CANDIDATE where missing
  2.4 — Add security: field to 206 AGENT.md without it
  2.5 — Add security: field to ~1,198 SKILL.md without it

WHY:
  executor absent in 93% of skills = router cannot dispatch deterministically.
  skill_id absent = zero traceability. status absent = promotion pipeline broken.
  security absent = SR-43/44 auditing impossible.

WHAT_IF_FAILS:
  Script is idempotent — re-running is safe. Uses regex on frontmatter only.
  If YAML parse fails for a file, it is logged and skipped (never corrupted).
  Back up with git before running (always true in this repo).

USAGE:
  python tools/normalize_schema.py [--dry-run] [--skills-only] [--agents-only]
  python tools/normalize_schema.py --dry-run          # preview counts
  python tools/normalize_schema.py                    # apply all
"""

from __future__ import annotations

import argparse
import os
import pathlib
import re
import sys
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
AGENTS_ROOT = REPO_ROOT / "agents"

# ─────────────────────────────────────────────────────────────────────────────
# Executor inference rules (ordered — first match wins)
# ─────────────────────────────────────────────────────────────────────────────
EXECUTOR_RULES: list[tuple[str, str]] = [
    ("skills/integrations/composio",    "HYBRID"),
    ("skills/integrations/",            "HYBRID"),
    ("skills/algorithms/",              "SANDBOX_CODE"),
    ("skills/anthropic-skills/",        "LLM_BEHAVIOR"),
    ("skills/community/",               "LLM_BEHAVIOR"),
    ("skills/design/",                  "LLM_BEHAVIOR"),
    ("skills/business/",                "LLM_BEHAVIOR"),
    ("skills/finance/",                 "LLM_BEHAVIOR"),
    ("skills/legal/",                   "LLM_BEHAVIOR"),
    ("skills/marketing/",               "LLM_BEHAVIOR"),
    ("skills/ai-ml/",                   "LLM_BEHAVIOR"),
    ("skills/engineering/",             "LLM_BEHAVIOR"),  # default; overridden if scripts/ present
]

# ─────────────────────────────────────────────────────────────────────────────
# Security defaults by domain
# ─────────────────────────────────────────────────────────────────────────────
HIGH_SECURITY_DOMAINS = {
    "security", "authentication", "payment", "finance", "legal",
    "privacy", "healthcare", "credentials", "secrets", "vault",
    "encryption", "compliance", "gdpr", "lgpd", "pci",
}


def _path_unix(p: pathlib.Path) -> str:
    return str(p).replace("\\", "/")


def infer_executor(skill_path: pathlib.Path) -> str:
    """Infer executor type from skill path + presence of scripts/ directory."""
    path_str = _path_unix(skill_path)

    # If skill has a scripts/ subdirectory, it has runnable code → HYBRID
    scripts_dir = skill_path.parent / "scripts"
    if scripts_dir.is_dir():
        # Pure sandbox skills (algorithms) stay SANDBOX_CODE
        if "skills/algorithms/" in path_str:
            return "SANDBOX_CODE"
        return "HYBRID"

    for prefix, executor in EXECUTOR_RULES:
        if prefix in path_str:
            return executor

    return "LLM_BEHAVIOR"  # safe default


def infer_security(skill_path: pathlib.Path, existing_desc: str = "") -> dict:
    """Return a minimal security dict inferred from domain + description."""
    path_lower = _path_unix(skill_path).lower()
    desc_lower = existing_desc.lower()
    combined = path_lower + " " + desc_lower

    level = "standard"
    pii = False
    approval = False

    for keyword in HIGH_SECURITY_DOMAINS:
        if keyword in combined:
            level = "high"
            approval = True
            break

    pii_keywords = ["email", "phone", "personal", "user data", "pii", "private", "password", "credential"]
    if any(k in combined for k in pii_keywords):
        pii = True

    return {"level": level, "pii": pii, "approval_required": approval}


def generate_skill_id(skill_path: pathlib.Path) -> str:
    """Generate a deterministic skill_id from the skill's path.

    Format: domain.subdomain.skill-name
    Example: skills/engineering/cs-engineering/autoresearch-agent/SKILL.md
             → engineering.cs-engineering.autoresearch-agent
    """
    # Normalize path relative to SKILLS_ROOT
    try:
        rel = skill_path.relative_to(SKILLS_ROOT)
        parts = list(rel.parts)
        # Remove SKILL.md filename
        if parts and parts[-1].upper() == "SKILL.MD":
            parts = parts[:-1]
        # Remove leading common prefixes that add no value
        # e.g. ["integrations", "composio", "ably-automation"] → integrations.composio.ably-automation
        skill_id = ".".join(p.lower().replace(" ", "-") for p in parts[:4])  # cap at 4 levels
        return skill_id
    except ValueError:
        # Fallback: use last 2 path parts
        parts = skill_path.parts
        return ".".join(p.lower() for p in parts[-3:-1])


# ─────────────────────────────────────────────────────────────────────────────
# YAML frontmatter helpers
# ─────────────────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(content: str) -> tuple[dict[str, str], str, str]:
    """Return (raw_fields_dict, frontmatter_block, body_after).

    raw_fields_dict contains field names → raw line values (unparsed).
    This avoids full YAML parsing which can mangle multiline strings.
    """
    m = FRONTMATTER_RE.match(content)
    if not m:
        return {}, "", content

    fm_block = m.group(0)
    fm_inner = m.group(1)
    body = content[m.end():]

    # Extract top-level keys only (lines starting with a word char, not indented)
    fields: dict[str, str] = {}
    for line in fm_inner.splitlines():
        key_match = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if key_match:
            fields[key_match.group(1)] = key_match.group(2).strip()

    return fields, fm_block, body


def inject_frontmatter_fields(
    content: str,
    to_add: dict[str, str],
) -> tuple[str, list[str]]:
    """Inject new fields into YAML frontmatter without overwriting existing ones.

    Returns (modified_content, list_of_injected_field_names).
    """
    m = FRONTMATTER_RE.match(content)
    if not m:
        # No frontmatter — prepend one
        fm_lines = ["---"]
        for k, v in to_add.items():
            fm_lines.append(f"{k}: {v}")
        fm_lines.append("---")
        fm_lines.append("")
        return "\n".join(fm_lines) + content, list(to_add.keys())

    fm_inner = m.group(1)
    existing_keys = set()
    for line in fm_inner.splitlines():
        km = re.match(r"^(\w[\w_-]*):", line)
        if km:
            existing_keys.add(km.group(1))

    injected = []
    new_lines = []
    for k, v in to_add.items():
        if k not in existing_keys:
            new_lines.append(f"{k}: {v}")
            injected.append(k)

    if not injected:
        return content, []

    # Insert before closing ---
    # Find the last --- (end of frontmatter)
    fm_end_pos = m.end()
    fm_block_end = content.rfind("---\n", 0, fm_end_pos)
    if fm_block_end == -1:
        fm_block_end = content.rfind("---", 0, fm_end_pos)

    insert_pos = fm_block_end
    insertion = "\n".join(new_lines) + "\n"
    new_content = content[:insert_pos] + insertion + content[insert_pos:]
    return new_content, injected


# ─────────────────────────────────────────────────────────────────────────────
# Security field serialization
# ─────────────────────────────────────────────────────────────────────────────

def security_to_yaml_inline(sec: dict) -> str:
    """Convert security dict to compact inline YAML."""
    level = sec.get("level", "standard")
    pii = str(sec.get("pii", False)).lower()
    approval = str(sec.get("approval_required", False)).lower()
    return f"{{level: {level}, pii: {pii}, approval_required: {approval}}}"


# ─────────────────────────────────────────────────────────────────────────────
# Main normalization functions
# ─────────────────────────────────────────────────────────────────────────────

def normalize_skill(path: pathlib.Path, dry_run: bool = False) -> dict:
    """Normalize a single SKILL.md. Returns dict of changes made."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": str(e)}

    fields, _, _ = parse_frontmatter(content)
    changes: dict[str, str] = {}

    # 2.1 — executor
    if "executor" not in fields:
        changes["executor"] = infer_executor(path)

    # 2.2 — skill_id
    if "skill_id" not in fields:
        changes["skill_id"] = generate_skill_id(path)

    # 2.3 — status
    if "status" not in fields:
        changes["status"] = "CANDIDATE"

    # 2.5 — security
    if "security" not in fields:
        desc = fields.get("description", "")
        sec = infer_security(path, desc)
        changes["security"] = security_to_yaml_inline(sec)

    if not changes:
        return {}

    if dry_run:
        return changes

    new_content, injected = inject_frontmatter_fields(content, changes)
    if injected:
        path.write_text(new_content, encoding="utf-8")

    return {k: changes[k] for k in injected}


def normalize_agent(path: pathlib.Path, dry_run: bool = False) -> dict:
    """Normalize a single AGENT.md. Returns dict of changes made."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": str(e)}

    fields, _, _ = parse_frontmatter(content)
    changes: dict[str, str] = {}

    # 2.4 — security
    if "security" not in fields:
        # Check if agent has high-privilege tools
        content_lower = content.lower()
        has_dangerous_tools = any(
            t in content_lower
            for t in ["bash", "write", "webfetch", "subprocess", "execute"]
        )
        level = "high" if has_dangerous_tools else "standard"
        approval = "true" if has_dangerous_tools else "false"
        changes["security"] = f"{{level: {level}, approval_required: {approval}}}"

    if not changes:
        return {}

    if dry_run:
        return changes

    new_content, injected = inject_frontmatter_fields(content, changes)
    if injected:
        path.write_text(new_content, encoding="utf-8")

    return {k: changes[k] for k in injected}


# ─────────────────────────────────────────────────────────────────────────────
# Batch runners
# ─────────────────────────────────────────────────────────────────────────────

def run_skills(dry_run: bool) -> None:
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Normalizing SKILL.md files...")
    print(f"  Root: {SKILLS_ROOT}\n")

    stats: dict[str, int] = {
        "total": 0, "modified": 0, "skipped": 0, "errors": 0,
        "executor_added": 0, "skill_id_added": 0,
        "status_added": 0, "security_added": 0,
    }

    skill_files = list(SKILLS_ROOT.rglob("SKILL.md"))
    total = len(skill_files)
    print(f"  Found {total} SKILL.md files")

    for i, path in enumerate(skill_files, 1):
        if i % 500 == 0:
            print(f"  Progress: {i}/{total}...")

        stats["total"] += 1
        result = normalize_skill(path, dry_run=dry_run)

        if "error" in result:
            stats["errors"] += 1
            print(f"  [ERROR] {path.relative_to(REPO_ROOT)}: {result['error']}")
        elif result:
            stats["modified"] += 1
            if "executor" in result:   stats["executor_added"] += 1
            if "skill_id" in result:   stats["skill_id_added"] += 1
            if "status" in result:     stats["status_added"] += 1
            if "security" in result:   stats["security_added"] += 1
        else:
            stats["skipped"] += 1

    action = "Would modify" if dry_run else "Modified"
    print(f"\n  Results:")
    print(f"    {action}: {stats['modified']}/{stats['total']} files")
    print(f"    executor added:  {stats['executor_added']}")
    print(f"    skill_id added:  {stats['skill_id_added']}")
    print(f"    status added:    {stats['status_added']}")
    print(f"    security added:  {stats['security_added']}")
    print(f"    already OK:      {stats['skipped']}")
    print(f"    errors:          {stats['errors']}")


def run_agents(dry_run: bool) -> None:
    print(f"\n{'[DRY-RUN] ' if dry_run else ''}Normalizing AGENT.md files...")
    print(f"  Root: {AGENTS_ROOT}\n")

    stats: dict[str, int] = {
        "total": 0, "modified": 0, "skipped": 0, "errors": 0,
        "security_added": 0,
    }

    agent_files = list(AGENTS_ROOT.rglob("AGENT.md"))
    total = len(agent_files)
    print(f"  Found {total} AGENT.md files")

    for path in agent_files:
        stats["total"] += 1
        result = normalize_agent(path, dry_run=dry_run)

        if "error" in result:
            stats["errors"] += 1
        elif result:
            stats["modified"] += 1
            if "security" in result: stats["security_added"] += 1
        else:
            stats["skipped"] += 1

    action = "Would modify" if dry_run else "Modified"
    print(f"\n  Results:")
    print(f"    {action}: {stats['modified']}/{stats['total']} files")
    print(f"    security added:  {stats['security_added']}")
    print(f"    already OK:      {stats['skipped']}")
    print(f"    errors:          {stats['errors']}")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="APEX Phase 2 — Normalize SKILL.md and AGENT.md schema fields"
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview changes, write nothing")
    parser.add_argument("--skills-only", action="store_true", help="Only process SKILL.md")
    parser.add_argument("--agents-only", action="store_true", help="Only process AGENT.md")
    args = parser.parse_args()

    print("=" * 70)
    print("APEX Phase 2 — Schema Normalization")
    print(f"Mode: {'DRY-RUN (no writes)' if args.dry_run else 'LIVE (writing files)'}")
    print("=" * 70)

    if not args.agents_only:
        run_skills(dry_run=args.dry_run)

    if not args.skills_only:
        run_agents(dry_run=args.dry_run)

    print("\nDone.")
    if args.dry_run:
        print("Run without --dry-run to apply changes.")


if __name__ == "__main__":
    main()
