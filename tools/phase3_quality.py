"""
tools/phase3_quality.py — APEX Phase 3: Disambiguation & SR_40 Compliance
==========================================================================
APEX OPP-Phase3 | 2026-04-17

PURPOSE:
  Surgical automated fixes for disambiguation and SR_40 compliance across
  3.761 SKILL.md files. Derives all content from EXISTING frontmatter fields
  (purpose, when, what_if_fails, description, name) — no external LLM needed.

TASKS:
  3.1 — Fix 73 empty/placeholder descriptions (derive from body first line)
  3.2 — Replace 2.518 <describe your request> with skill-specific triggers
  3.3 — Generate anchors: for 1.160 skills without anchors field
  3.4 — Add SR_40 sections (Why/When/WhatIf) from existing frontmatter fields
        targeting the ~3.755 skills missing them

INVARIANTS:
  - NEVER overwrite fields that already have real content
  - Idempotent: safe to re-run
  - Composio (832 skills) handled separately by phase3_composio.py

USAGE:
  python tools/phase3_quality.py [--dry-run] [--task 3.1|3.2|3.3|3.4|all]
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
from typing import Optional

REPO_ROOT = pathlib.Path(__file__).parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

# ─────────────────────────────────────────────────────────────────────────────
# Domain → default imperative verb mapping (task 3.1 / 3.2)
# ─────────────────────────────────────────────────────────────────────────────
DOMAIN_VERB: dict[str, str] = {
    "integrations":      "Automate",
    "composio":          "Automate",
    "engineering":       "Implement",
    "anthropic-skills":  "Apply",
    "anthropic-official":"Apply",
    "community":         "Use",
    "business":          "Manage",
    "finance":           "Analyze",
    "marketing":         "Create",
    "design":            "Design",
    "ai-ml":             "Apply",
    "data":              "Analyze",
    "security":          "Audit",
    "legal":             "Review",
    "healthcare":        "Analyze",
    "science":           "Research",
    "education":         "Teach",
    "productivity":      "Automate",
    "knowledge":         "Extract",
    "web3":              "Deploy",
    "operations":        "Optimize",
    "sales":             "Track",
}

DEFAULT_VERB = "Use"

IMPERATIVE_RE = re.compile(
    r"^(automate|analyze|analyse|generate|create|build|design|convert|extract|"
    r"optimize|optimise|debug|review|validate|deploy|monitor|manage|process|"
    r"transform|implement|configure|execute|run|apply|detect|resolve|scaffold|"
    r"plan|track|search|fetch|summarize|summarise|classify|integrate|migrate|"
    r"audit|test|document|format|parse|calculate|estimate|evaluate|assess|"
    r"identify|define|map|list|find|write|edit|refactor|check|fix|patch|"
    r"generate|install|setup|set up|initialize|initialise|bootstrap|provision|"
    r"measure|report|model|simulate|predict|recommend|suggest|propose|"
    r"orchestrate|coordinate|prioritize|schedule|assign|delegate|review)\b",
    re.IGNORECASE,
)

PLACEHOLDER_RE = re.compile(
    r"<describe your request>|<[^>]{3,}>|one sentence.*skill does|"
    r"what this skill does|describe the.*request",
    re.IGNORECASE,
)

# ─────────────────────────────────────────────────────────────────────────────
# Anchor vocabulary — top-60 canonical anchors (from synergy analysis)
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL_ANCHORS: set[str] = {
    "agent", "automation", "analysis", "security", "workflow",
    "code", "api", "data", "testing", "deployment",
    "documentation", "integration", "optimization", "monitoring", "review",
    "generation", "transformation", "validation", "configuration", "debugging",
    "engineering", "business", "finance", "marketing", "design",
    "ai_ml", "llm", "research", "planning", "management",
    "architecture", "database", "cloud", "devops", "frontend",
    "backend", "mobile", "git", "cli", "infrastructure",
    "machine_learning", "data_science", "visualization", "reporting",
    "customer_success", "sales", "operations", "legal", "compliance",
    "healthcare", "science", "education", "productivity", "knowledge",
    "web3", "blockchain", "authentication", "authorization", "encryption",
    "performance", "scalability", "reliability", "observability",
}

ANCHOR_KEYWORD_MAP: dict[str, str] = {
    # programming & engineering
    "python": "code", "javascript": "code", "typescript": "code",
    "rust": "code", "golang": "code", "java": "code", "c++": "code",
    "react": "frontend", "vue": "frontend", "angular": "frontend",
    "node": "backend", "django": "backend", "fastapi": "backend",
    "sql": "database", "postgres": "database", "mysql": "database",
    "mongodb": "database", "redis": "database",
    "aws": "cloud", "azure": "cloud", "gcp": "cloud", "kubernetes": "cloud",
    "docker": "deployment", "ci/cd": "deployment", "terraform": "infrastructure",
    "git": "git", "github": "git", "gitlab": "git",
    "test": "testing", "pytest": "testing", "jest": "testing",
    "api": "api", "rest": "api", "graphql": "api", "grpc": "api",
    # AI/ML
    "llm": "llm", "claude": "llm", "gpt": "llm", "anthropic": "llm",
    "machine learning": "machine_learning", "neural": "machine_learning",
    "model": "ai_ml", "training": "machine_learning", "inference": "ai_ml",
    "agent": "agent", "workflow": "workflow", "automation": "automation",
    # business
    "revenue": "finance", "budget": "finance", "invoice": "finance",
    "sales": "sales", "crm": "sales", "lead": "sales",
    "marketing": "marketing", "campaign": "marketing", "seo": "marketing",
    "customer": "customer_success", "support": "customer_success",
    "legal": "legal", "compliance": "compliance", "gdpr": "compliance",
    "hr": "management", "hiring": "management", "team": "management",
    "security": "security", "vulnerability": "security", "pentest": "security",
    "encrypt": "encryption", "auth": "authentication",
    # data
    "data": "data", "analytics": "data_science", "dashboard": "visualization",
    "chart": "visualization", "report": "reporting",
    # ops
    "monitor": "monitoring", "alert": "monitoring", "log": "observability",
    "performance": "performance", "scale": "scalability",
    "incident": "reliability", "sre": "reliability",
    # research
    "research": "research", "hypothesis": "research", "experiment": "research",
    "document": "documentation", "write": "documentation",
    "design": "design", "ui": "design", "ux": "design",
    "web3": "web3", "blockchain": "blockchain", "defi": "web3", "nft": "web3",
}


# ─────────────────────────────────────────────────────────────────────────────
# Frontmatter helpers
# ─────────────────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def get_frontmatter_field(content: str, field: str) -> str:
    """Extract a frontmatter field value (single-line or first line of multiline)."""
    # Try quoted value
    m = re.search(rf'^{field}:\s*["\'](.+?)["\']', content, re.MULTILINE)
    if m:
        return m.group(1).strip()
    # Try unquoted
    m = re.search(rf'^{field}:\s*(.+)$', content, re.MULTILINE)
    if m:
        val = m.group(1).strip()
        if val.startswith(">"):
            # Multiline YAML block — find next non-empty indented line
            lines = content.split("\n")
            in_block = False
            for line in lines:
                if re.match(rf'^{field}:\s*>', line):
                    in_block = True
                    continue
                if in_block and line.startswith(" ") and line.strip():
                    return line.strip()
                elif in_block and not line.startswith(" "):
                    break
            return ""
        return val
    return ""


def has_frontmatter(content: str) -> bool:
    return bool(FRONTMATTER_RE.match(content))


def get_body(content: str) -> str:
    """Return content after the frontmatter block."""
    m = FRONTMATTER_RE.match(content)
    if m:
        return content[m.end():]
    return content


def first_meaningful_line(text: str) -> str:
    """First non-header, non-empty line of body text."""
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("---") \
                and not line.startswith(">") and len(line) > 15:
            # Remove markdown bold/italic
            line = re.sub(r"\*+([^*]+)\*+", r"\1", line)
            line = re.sub(r"`([^`]+)`", r"\1", line)
            return line[:200]
    return ""


def get_path_domain(path: pathlib.Path) -> str:
    try:
        rel = path.relative_to(SKILLS_ROOT)
        return rel.parts[0] if rel.parts else ""
    except ValueError:
        return ""


def infer_verb(path: pathlib.Path, desc: str = "") -> str:
    domain = get_path_domain(path)
    if domain in DOMAIN_VERB:
        return DOMAIN_VERB[domain]
    # Try to infer from description
    desc_lower = desc.lower()
    for keyword, verb in [
        ("automate", "Automate"), ("generate", "Generate"), ("analyze", "Analyze"),
        ("deploy", "Deploy"), ("debug", "Debug"), ("create", "Create"),
        ("build", "Build"), ("review", "Review"), ("monitor", "Monitor"),
    ]:
        if keyword in desc_lower:
            return verb
    return DEFAULT_VERB


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.1 — Fix empty / placeholder descriptions
# ─────────────────────────────────────────────────────────────────────────────

def fix_description(content: str, path: pathlib.Path) -> tuple[str, bool]:
    """Fix empty/placeholder description. Returns (new_content, changed)."""
    name = get_frontmatter_field(content, "name") or path.parent.name
    current_desc = get_frontmatter_field(content, "description")

    if not current_desc or PLACEHOLDER_RE.search(current_desc):
        # Try to derive from purpose, then body
        purpose = get_frontmatter_field(content, "purpose")
        body = get_body(content)
        body_line = first_meaningful_line(body)

        raw = purpose or body_line or f"Skill for {name}"
        # Ensure imperative start
        if not IMPERATIVE_RE.match(raw):
            verb = infer_verb(path, raw)
            new_desc = f"{verb} {name.replace('-', ' ')} — {raw[:120]}"
        else:
            new_desc = raw[:200]

        new_desc = new_desc.replace('"', "'")
        new_content = re.sub(
            r'^(description:\s*).*$',
            f'description: "{new_desc}"',
            content,
            count=1,
            flags=re.MULTILINE,
        )
        if new_content != content:
            return new_content, True

    return content, False


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.2 — Fix input_schema placeholder
# ─────────────────────────────────────────────────────────────────────────────

def fix_input_placeholder(content: str, path: pathlib.Path) -> tuple[str, bool]:
    """Replace <describe your request> with skill-derived trigger."""
    if "<describe your request>" not in content:
        return content, False

    name = get_frontmatter_field(content, "name") or path.parent.name
    desc = get_frontmatter_field(content, "description") or ""
    domain = get_path_domain(path)

    # Extract "Use when" clause from description if present
    use_when = ""
    m = re.search(r"[Uu]se when[:\s]+(.{10,80}?)(?:\.|,|$)", desc)
    if m:
        use_when = m.group(1).strip().rstrip(".,")

    # Build a concrete trigger
    clean_name = name.replace("-", " ").replace("_", " ")
    if use_when:
        trigger = use_when[:100]
    elif desc and len(desc) > 20:
        # Take first clause of description
        trigger = desc.split(".")[0].split(",")[0][:100].strip()
    else:
        verb = infer_verb(path)
        trigger = f"{verb.lower()} {clean_name} task"

    new_content = content.replace(
        "<describe your request>",
        trigger,
    )
    return new_content, new_content != content


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.3 — Generate anchors
# ─────────────────────────────────────────────────────────────────────────────

def generate_anchors(content: str, path: pathlib.Path) -> tuple[str, bool]:
    """Add anchors: field derived from description and path if missing."""
    if re.search(r"^anchors:", content, re.MULTILINE):
        return content, False  # already has anchors

    desc = get_frontmatter_field(content, "description") or ""
    name = get_frontmatter_field(content, "name") or path.parent.name
    domain = get_path_domain(path)

    collected: list[str] = []

    # Domain anchor
    domain_anchor = DOMAIN_VERB.get(domain, "").lower()
    for canon in CANONICAL_ANCHORS:
        if domain in canon or canon in domain:
            collected.append(canon)
            break

    # From description + name combined
    combined = (name + " " + desc).lower()
    for keyword, anchor in ANCHOR_KEYWORD_MAP.items():
        if keyword in combined and anchor not in collected:
            collected.append(anchor)
        if len(collected) >= 6:
            break

    # Ensure at least 2 anchors
    if not collected:
        verb = infer_verb(path, desc).lower()
        collected = ["automation", verb] if verb != "automation" else ["automation", "workflow"]

    collected = list(dict.fromkeys(collected))[:6]  # dedupe, max 6
    anchors_yaml = "anchors:\n" + "".join(f"  - {a}\n" for a in collected)

    # Inject before closing ---
    fm_match = FRONTMATTER_RE.match(content)
    if not fm_match:
        return content, False

    fm_end = content.rfind("---\n", 0, fm_match.end())
    if fm_end == -1:
        return content, False

    new_content = content[:fm_end] + anchors_yaml + content[fm_end:]
    return new_content, True


# ─────────────────────────────────────────────────────────────────────────────
# Task 3.4 — SR_40: Add Why / When to Use / What If Fails sections
# ─────────────────────────────────────────────────────────────────────────────

def add_sr40_sections(content: str, path: pathlib.Path) -> tuple[str, bool]:
    """Append missing SR_40 markdown sections derived from frontmatter fields."""
    has_why  = bool(re.search(r"^## Why This Skill Exists", content, re.MULTILINE | re.IGNORECASE))
    has_when = bool(re.search(r"^## When to Use", content, re.MULTILINE | re.IGNORECASE))
    has_wif  = bool(re.search(r"^## What If Fails", content, re.MULTILINE | re.IGNORECASE))

    if has_why and has_when and has_wif:
        return content, False  # already SR_40 compliant

    name = get_frontmatter_field(content, "name") or path.parent.name
    desc = get_frontmatter_field(content, "description") or f"skill for {name}"
    purpose = get_frontmatter_field(content, "purpose") or desc
    when_fm = get_frontmatter_field(content, "when") or ""
    wif_fm  = get_frontmatter_field(content, "what_if_fails") or ""
    domain  = get_path_domain(path)

    clean_name = name.replace("-", " ").replace("_", " ").title()

    sections: list[str] = []

    if not has_why:
        # Use purpose field or description, stripped of "Use when" clauses
        why_text = purpose
        if not why_text or len(why_text) < 20:
            why_text = desc
        # Remove trailing "Use when" clause if present
        why_text = re.sub(r"\s*[Uu]se when[:\s]+.+$", "", why_text).strip()
        why_text = why_text[:300] if why_text else f"Provides {clean_name} capability within the APEX skill ecosystem."
        sections.append(
            f"## Why This Skill Exists\n\n"
            f"{why_text}\n\n"
            f"<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). "
            f"Expand with domain-specific rationale. -->"
        )

    if not has_when:
        if when_fm and len(when_fm) > 15:
            when_text = when_fm[:400]
        else:
            # Extract "Use when" from description
            m = re.search(r"[Uu]se when[:\s]+(.{10,200}?)(?:\.|$)", desc)
            when_text = m.group(1).strip() if m else f"the task requires {clean_name.lower()} capabilities."
        sections.append(
            f"## When to Use\n\n"
            f"Use this skill when {when_text.lstrip('when ').lstrip('When ')}\n\n"
            f"<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->"
        )

    if not has_wif:
        if wif_fm and len(wif_fm) > 15:
            wif_text = wif_fm[:400]
        else:
            wif_text = (
                f"If this skill fails to produce the expected output: "
                f"(1) verify input completeness, "
                f"(2) retry with more specific context, "
                f"(3) fall back to the parent workflow without this skill."
            )
        sections.append(
            f"## What If Fails\n\n"
            f"{wif_text}\n\n"
            f"<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->"
        )

    if not sections:
        return content, False

    separator = "\n\n---\n\n"
    addition = separator + ("\n\n".join(sections))
    new_content = content.rstrip() + addition + "\n"
    return new_content, True


# ─────────────────────────────────────────────────────────────────────────────
# Description → imperative verb prefix (task 3.2 supplement)
# ─────────────────────────────────────────────────────────────────────────────

def fix_description_verb(content: str, path: pathlib.Path) -> tuple[str, bool]:
    """Prefix descriptions lacking an imperative verb (task 3.2 extension)."""
    desc = get_frontmatter_field(content, "description")
    if not desc:
        return content, False

    clean_desc = desc.strip().strip('"').strip("'")
    if PLACEHOLDER_RE.search(clean_desc):
        return content, False  # handled by task 3.1
    if IMPERATIVE_RE.match(clean_desc):
        return content, False  # already good

    verb = infer_verb(path, clean_desc)
    new_desc = f"{verb} — {clean_desc[:180]}"
    new_desc = new_desc.replace('"', "'")

    new_content = re.sub(
        r'^(description:\s*["\']?)(.+?)(["\']?\s*)$',
        lambda m: f'description: "{new_desc}"',
        content,
        count=1,
        flags=re.MULTILINE,
    )
    return new_content, new_content != content


# ─────────────────────────────────────────────────────────────────────────────
# Per-file pipeline
# ─────────────────────────────────────────────────────────────────────────────

def process_skill(path: pathlib.Path, tasks: set[str], dry_run: bool) -> dict:
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"error": str(e)}

    # Skip Composio — handled by phase3_composio.py
    path_str = str(path).replace("\\", "/")
    if "integrations/composio" in path_str:
        return {"skipped": "composio"}

    if not has_frontmatter(content):
        return {"skipped": "no_frontmatter"}

    changes: list[str] = []
    modified = content

    if "3.1" in tasks:
        modified, changed = fix_description(modified, path)
        if changed: changes.append("desc_fixed")

    if "3.2" in tasks:
        modified, changed = fix_input_placeholder(modified, path)
        if changed: changes.append("input_trigger_fixed")
        modified, changed = fix_description_verb(modified, path)
        if changed: changes.append("desc_verb_added")

    if "3.3" in tasks:
        modified, changed = generate_anchors(modified, path)
        if changed: changes.append("anchors_generated")

    if "3.4" in tasks:
        modified, changed = add_sr40_sections(modified, path)
        if changed: changes.append("sr40_sections_added")

    if not changes:
        return {}

    if not dry_run:
        path.write_text(modified, encoding="utf-8")

    return {"changes": changes}


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Phase 3 Quality Fixes")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--task", default="all",
                        help="Comma-separated: 3.1,3.2,3.3,3.4 or 'all'")
    args = parser.parse_args()

    tasks = {"3.1", "3.2", "3.3", "3.4"} if args.task == "all" \
        else set(args.task.split(","))

    print("=" * 70)
    print(f"APEX Phase 3 — Quality & Disambiguation")
    print(f"Tasks: {sorted(tasks)} | Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print("=" * 70)

    skill_files = list(SKILLS_ROOT.rglob("SKILL.md"))
    total = len(skill_files)
    print(f"\nProcessing {total} SKILL.md files...\n")

    counters: dict[str, int] = {
        "total": 0, "modified": 0, "skipped": 0, "errors": 0,
        "desc_fixed": 0, "input_trigger_fixed": 0, "desc_verb_added": 0,
        "anchors_generated": 0, "sr40_sections_added": 0,
    }

    for i, path in enumerate(skill_files, 1):
        if i % 1000 == 0:
            print(f"  {i}/{total}...")

        counters["total"] += 1
        result = process_skill(path, tasks, dry_run=args.dry_run)

        if "error" in result:
            counters["errors"] += 1
        elif "skipped" in result:
            counters["skipped"] += 1
        elif result.get("changes"):
            counters["modified"] += 1
            for change in result["changes"]:
                counters[change] = counters.get(change, 0) + 1
        else:
            counters["skipped"] += 1

    action = "Would modify" if args.dry_run else "Modified"
    print(f"\n{'='*70}")
    print(f"Results:")
    print(f"  {action}: {counters['modified']}/{counters['total']}")
    print(f"  desc fixed (empty/placeholder):  {counters.get('desc_fixed', 0)}")
    print(f"  input triggers replaced:          {counters.get('input_trigger_fixed', 0)}")
    print(f"  desc verb prefixed:               {counters.get('desc_verb_added', 0)}")
    print(f"  anchors generated:                {counters.get('anchors_generated', 0)}")
    print(f"  SR_40 sections added:             {counters.get('sr40_sections_added', 0)}")
    print(f"  skipped (ok/composio/no-fm):      {counters['skipped']}")
    print(f"  errors:                           {counters['errors']}")

    if args.dry_run:
        print("\nRun without --dry-run to apply.")


if __name__ == "__main__":
    main()
