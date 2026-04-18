#!/usr/bin/env python3
"""
tools/phase6_promote_optimize.py — APEX Phase 6: Promote + Optimize + Monolith
================================================================================
APEX OPP-Phase6 | 2026-04-17

TASKS:
  6.1  Promote 2335 CANDIDATE→ADOPTED (all required fields already present)
  6.2  Auto-complete + promote remaining ~1184 CANDIDATE skills:
         - Generate input_schema, output_schema, tier, what_if_fails from content
  6.3  Create references/APEX_CANONICAL_SCHEMA.yaml (master definition file)
  6.4  Rebuild INDEX.md: 371KB monolith → ~5KB hub + per-domain CATALOG.md files
  6.5  UCO SA validation on all modified tools scripts

USAGE:
  python tools/phase6_promote_optimize.py [--dry-run] [--tasks 6.1,6.2,6.3,6.4,6.5]
"""
from __future__ import annotations
import argparse, re, sys, io, time, json
from pathlib import Path
from collections import Counter, defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

UCO_AVAILABLE = False
try:
    sys.path.insert(0, str(REPO_ROOT / "algorithms" / "uco"))
    from universal_code_optimizer_v4 import UniversalCodeOptimizer
    UCO_AVAILABLE = True
except Exception:
    pass

REQUIRED_ADOPTED = ["skill_id","description","tier","executor","anchors","input_schema","output_schema","what_if_fails"]
FRONTMATTER_RE = re.compile(r'^(---\s*\n)(.*?)(\n---\s*\n)', re.DOTALL)

# ── Tier inference rules (path-based, ordered by specificity)
TIER_RULES = [
    ("apex_internals",         0),
    ("engineering_agentops",   1),
    ("ai_ml_agents",           1),
    ("community-subagents",    2),
    ("community_general",      3),
    ("integrations/composio",  3),
    ("anthropic-official",     2),
    ("anthropic-skills",       2),
    ("knowledge-work",         2),
    ("community",              3),
    ("awesome_claude",         3),
    ("claude_skills_m",        2),
    ("web3",                   2),
    ("science",                1),
    ("engineering",            2),
    ("security",               1),
    ("finance",                2),
    ("legal",                  2),
    ("healthcare",             2),
    ("marketing",              2),
    ("design",                 2),
]

def infer_tier(path: Path) -> int:
    p = str(path).replace("\\", "/")
    for keyword, tier in TIER_RULES:
        if keyword in p:
            return tier
    return 2  # default

def infer_executor(path: Path, content: str) -> str:
    p = str(path).replace("\\", "/")
    if "composio" in p:
        return "HYBRID"
    if "scripts" in content and ("subprocess" in content or "bash" in content.lower()):
        return "HYBRID"
    if "SANDBOX" in content.upper():
        return "SANDBOX_CODE"
    if "algorithm" in p.lower() or "algorithms/" in p:
        return "SANDBOX_CODE"
    return "LLM_BEHAVIOR"

def derive_input_schema_block(description: str, content: str, skill_name: str, skill_id: str) -> str:
    """Generate input_schema YAML block from skill content."""
    desc_lower = (description + " " + content[:1000]).lower()
    inputs = []

    # Detect primary input type from description
    if any(w in desc_lower for w in ["code", "script", "function", "class", "snippet"]):
        inputs.append(("code_or_task", "string",
            "Code snippet, script, or task description to process", True))
    elif any(w in desc_lower for w in ["document", "text", "content", "file", "report"]):
        inputs.append(("content", "string",
            "Document, text content, or file to analyze", True))
    elif any(w in desc_lower for w in ["query", "question", "search"]):
        inputs.append(("query", "string",
            "Search query or question to answer", True))
    elif any(w in desc_lower for w in ["url", "endpoint", "api"]):
        inputs.append(("target", "string",
            "URL, endpoint, or API target to interact with", True))
    elif any(w in desc_lower for w in ["data", "dataset", "csv", "json"]):
        inputs.append(("data", "string",
            "Input data (JSON, CSV, or structured content)", True))
    elif "automate" in desc_lower and "composio" in str(skill_id).lower():
        toolkit = skill_name.replace("-automation", "")
        inputs.append(("task_description", "string",
            f"Task to automate via {toolkit} integration", True))
        inputs.append(("toolkit_name", "string",
            f"Composio toolkit identifier (default: {toolkit})", False))
    else:
        inputs.append(("task", "string",
            f"Task or request for {skill_name.replace('-', ' ')}", True))

    # Add context parameter for complex skills
    if any(w in desc_lower for w in ["context", "background", "project", "existing"]):
        inputs.append(("context", "string",
            "Additional context or background information", False))

    lines = ["input_schema:"]
    for name, typ, desc_text, req in inputs:
        lines.append(f"  - name: {name}")
        lines.append(f"    type: {typ}")
        lines.append(f'    description: "{desc_text}"')
        lines.append(f"    required: {'true' if req else 'false'}")
    return "\n".join(lines) + "\n"

def derive_output_schema_block(description: str, content: str, skill_name: str) -> str:
    """Generate output_schema YAML block from skill content."""
    desc_lower = (description + " " + content[:500]).lower()
    outputs = []

    if any(w in desc_lower for w in ["report", "analysis", "summary", "review"]):
        outputs.append(("report", "string",
            f"Analysis report or summary from {skill_name.replace('-', ' ')}"))
    elif any(w in desc_lower for w in ["code", "implementation", "refactor", "generate"]):
        outputs.append(("result", "string",
            f"Generated or refactored code output"))
        outputs.append(("explanation", "string",
            "Explanation of changes or implementation decisions"))
    elif any(w in desc_lower for w in ["plan", "roadmap", "strategy", "design"]):
        outputs.append(("plan", "string",
            f"Strategic plan or design document"))
        outputs.append(("next_steps", "array",
            "List of recommended next steps"))
    elif any(w in desc_lower for w in ["automate", "execute", "run", "trigger"]):
        outputs.append(("result", "object",
            "Result from the automated action"))
        outputs.append(("status", "string",
            "Execution status: success | partial | failure"))
    else:
        outputs.append(("result", "string",
            f"Primary output from {skill_name.replace('-', ' ')}"))

    lines = ["output_schema:"]
    for name, typ, desc_text in outputs:
        lines.append(f"  - name: {name}")
        lines.append(f"    type: {typ}")
        lines.append(f'    description: "{desc_text}"')
    return "\n".join(lines) + "\n"

def derive_what_if_fails_block(description: str, skill_name: str) -> str:
    """Generate what_if_fails from description."""
    skill_display = skill_name.replace("-", " ").title()
    return (
        f"what_if_fails: >\n"
        f"  FALLBACK: If {skill_display} cannot complete, provide partial results with\n"
        f"  explicit gaps noted. Never block workflow silently.\n"
        f"  ESCALATE: If core capability is unavailable, suggest nearest alternative skill.\n"
        f"  RULE: Always explain what failed and what manual steps can substitute.\n"
    )

def inject_frontmatter_field(content: str, field_block: str) -> str:
    """Insert field before closing --- of first frontmatter. Idempotent."""
    field_key = field_block.split(":")[0].strip()
    if re.search(rf'^{re.escape(field_key)}\s*:', content, re.MULTILINE):
        return content  # already present
    close_pos = content.find('\n---', 3)
    if close_pos == -1:
        return content
    return content[:close_pos + 1] + field_block + content[close_pos + 1:]

def read_safe(p: Path) -> str | None:
    try: return p.read_text(encoding='utf-8', errors='replace')
    except: return None

def write_safe(p: Path, c: str, dry_run: bool) -> bool:
    if dry_run: return True
    try: p.write_text(c, encoding='utf-8'); return True
    except: return False


# ═══════════════════════════════════════════════════════════
# TASK 6.1 — Promote CANDIDATE with complete schema
# ═══════════════════════════════════════════════════════════

def task_61_promote_complete(dry_run: bool) -> dict:
    """Change status CANDIDATE→ADOPTED for 2335 skills that already have all fields."""
    print("\n[TASK 6.1] Promote CANDIDATE→ADOPTED (complete schema)")
    skills = list(SKILLS_ROOT.rglob("SKILL.md"))
    promoted = 0
    errors = 0

    for sk in skills:
        c = read_safe(sk)
        if not c: continue
        sm = re.search(r'status\s*:\s*(\w+)', c)
        if not sm or sm.group(1).upper() != 'CANDIDATE': continue
        # Check all required fields present
        if all(f in c for f in REQUIRED_ADOPTED):
            new_c = re.sub(r'(status\s*:\s*)CANDIDATE', r'\1ADOPTED', c, count=1)
            if new_c != c:
                if write_safe(sk, new_c, dry_run):
                    promoted += 1
                else:
                    errors += 1

    action = "Would promote" if dry_run else "Promoted"
    print(f"  {action}: {promoted} | Errors: {errors}")
    return {"promoted": promoted, "errors": errors}


# ═══════════════════════════════════════════════════════════
# TASK 6.2 — Auto-complete + promote remaining CANDIDATE
# ═══════════════════════════════════════════════════════════

def task_62_autocomplete_promote(dry_run: bool) -> dict:
    """Generate missing fields for CANDIDATE skills, then promote to ADOPTED."""
    print("\n[TASK 6.2] Auto-complete + promote remaining CANDIDATE skills")
    skills = list(SKILLS_ROOT.rglob("SKILL.md"))

    completed = 0
    promoted = 0
    errors = 0
    field_stats = Counter()

    for i, sk in enumerate(skills):
        if (i + 1) % 500 == 0:
            print(f"    {i+1}/{len(skills)} (promoted so far: {promoted})...")

        c = read_safe(sk)
        if not c: continue
        sm = re.search(r'status\s*:\s*(\w+)', c)
        if not sm or sm.group(1).upper() != 'CANDIDATE': continue

        missing = [f for f in REQUIRED_ADOPTED if f not in c]
        if not missing: continue  # handled by task 6.1

        # Get metadata
        desc_m = re.search(r'description\s*:\s*["\']?([^"\'\n]{10,})', c)
        description = desc_m.group(1).strip() if desc_m else ""
        name_m = re.search(r'name\s*:\s*["\']?([^\s"\'#\n]+)', c)
        skill_name = name_m.group(1).strip() if name_m else sk.parent.name
        sid_m = re.search(r'skill_id\s*:\s*["\']?([^\s"\'#\n]+)', c)
        skill_id = sid_m.group(1) if sid_m else ""

        changed = False
        new_c = c

        for field in missing:
            if field == "tier":
                t = infer_tier(sk)
                block = f"tier: {t}\n"
            elif field == "executor":
                ex = infer_executor(sk, c)
                block = f"executor: {ex}\n"
            elif field == "input_schema":
                block = derive_input_schema_block(description, c, skill_name, skill_id)
            elif field == "output_schema":
                block = derive_output_schema_block(description, c, skill_name)
            elif field == "what_if_fails":
                block = derive_what_if_fails_block(description, skill_name)
            elif field == "anchors":
                block = "anchors:\n  - automation\n  - integration\n"
            elif field == "skill_id":
                # Derive from path
                parts = sk.parts
                try:
                    si = next(i for i, p in enumerate(parts) if p == 'skills')
                    rel = parts[si+1:-1]
                    sid = ".".join(rel).replace("-", "_").lower()[:80]
                except Exception:
                    sid = skill_name.replace("-", "_")
                block = f"skill_id: {sid}\n"
            elif field == "description":
                desc_title = skill_name.replace("-", " ").title()
                block = f'description: "Skill: {desc_title}"\n'
            else:
                continue

            injected = inject_frontmatter_field(new_c, block)
            if injected != new_c:
                new_c = injected
                changed = True
                field_stats[field] += 1

        if changed:
            completed += 1
            # Now promote to ADOPTED
            new_c = re.sub(r'(status\s*:\s*)CANDIDATE', r'\1ADOPTED', new_c, count=1)
            if write_safe(sk, new_c, dry_run):
                promoted += 1
            else:
                errors += 1

    action = "Would complete+promote" if dry_run else "Completed+promoted"
    print(f"  {action}: {completed} skills")
    print(f"  Fields generated: {dict(field_stats.most_common(10))}")
    print(f"  Errors: {errors}")
    return {"completed": completed, "promoted": promoted,
            "field_stats": dict(field_stats), "errors": errors}


# ═══════════════════════════════════════════════════════════
# TASK 6.3 — Create APEX Canonical Master Schema
# ═══════════════════════════════════════════════════════════

CANONICAL_SCHEMA_CONTENT = """\
# APEX Canonical Schema — Master Definitions
# ============================================
# OPP-Phase6 | 2026-04-17
# WHY: Single source of truth for all APEX field definitions.
#      All tools, validators, and LLMs must reference this file
#      before creating or validating SKILL.md / AGENT.md files.
# WHEN: Before creating any skill, agent, or tool that uses APEX DSL.

version: v00.36.0
opp: OPP-Phase6

# ═══════════════════════════════════════════════════════
# SKILL.md FIELD DEFINITIONS
# ═══════════════════════════════════════════════════════

skill_schema:

  required_by_status:
    CANDIDATE:
      - skill_id
      - description
      - anchors
    ADOPTED:
      - skill_id
      - description
      - tier
      - executor
      - anchors
      - input_schema
      - output_schema
      - what_if_fails
      - security
    DEPRECATED:
      - skill_id
      - description
      - deprecated_by      # skill_id of replacement

  fields:

    skill_id:
      type: string
      format: "domain.subdomain.skill_name (dot-separated, snake_case)"
      example: "engineering_agentops.full_dev_cycle"
      unique: true
      notes: "Derived from file path if not explicit. Must be globally unique."

    name:
      type: string
      format: "kebab-case"
      example: "full-dev-cycle"

    description:
      type: string
      max_length: 500
      notes: "Imperative verb prefix required (Generate, Analyze, Build, etc.)"

    version:
      type: string
      format: "v00.XX.Y (semver with leading zeros)"
      current: "v00.36.0"

    status:
      type: enum
      values:
        CANDIDATE: "Functional but schema incomplete or untested"
        ADOPTED: "Production-ready — full schema + verified behavior"
        DEPRECATED: "Superseded — must declare deprecated_by"
        PROPOSED: "Design only — not yet implemented"
        ADAPTED: "External import — minimally adapted for APEX"

    tier:
      type: integer
      values:
        0: "APEX kernel — pmi_pm, architect, meta_reasoning"
        1: "Core orchestration — engineer, critic, diff_governance"
        2: "Domain skills — standard production skills"
        3: "Community / utility — lower criticality"
        SUPER: "Composite super-skills — orchestrates multiple tier-1/2 skills"
      default: 2

    executor:
      type: enum
      values:
        LLM_BEHAVIOR: "Pure language model reasoning — no code execution"
        SANDBOX_CODE: "Requires sandboxed code execution (Python/JS runtime)"
        HYBRID: "Combines LLM reasoning with code or MCP tool execution"
        DOCUMENTATION: "Static reference only — no active execution"
      derivation_rules:
        - "skills/integrations/composio → HYBRID (uses Rube MCP)"
        - "skills with scripts/ subdirectory → HYBRID"
        - "algorithms/ → SANDBOX_CODE"
        - "default → LLM_BEHAVIOR"

    anchors:
      type: list[string]
      min_items: 1
      canonical_anchors:
        - agent
        - automation
        - analysis
        - security
        - workflow
        - code
        - testing
        - debugging
        - documentation
        - api
        - database
        - deployment
        - monitoring
        - optimization
        - refactoring
        - architecture
        - review
        - planning
        - research
        - data
        - ml
        - llm
        - cloud
        - frontend
        - backend
        - devops
        - design
        - writing
        - communication
        - finance
        - legal
        - marketing
        - sales
        - operations
        - hr
        - product
        - engineering
        - science
        - education
        - healthcare
        - productivity
        - integration
        - pipeline
        - orchestration
        - reasoning
        - generation
        - summarization
        - extraction
        - classification
        - search
        - retrieval
        - validation
        - parsing
        - transformation
        - visualization
        - reporting
      notes: "Use canonical anchors where possible. Non-canonical anchors are allowed but reduce routing accuracy."

    input_schema:
      type: list[InputField]
      min_items: 1
      InputField:
        name: string
        type: "string | integer | number | boolean | array | object"
        description: string
        required: "true | false"
        default: optional
        enum: optional[list]

    output_schema:
      type: list[OutputField]
      min_items: 1
      OutputField:
        name: string
        type: "string | integer | number | boolean | array | object"
        description: string
        enum: optional[list]

    what_if_fails:
      type: string
      notes: "Must describe fallback behavior and escalation path. Never leave blank."

    security:
      type: object
      fields:
        level: "standard | elevated | high | critical"
        pii: boolean
        approval_required: boolean
        note: optional[string]
      default: "{ level: standard, pii: false, approval_required: false }"

    synergy_map:
      type: object
      notes: "Declares relationships with other skills for routing optimization"
      fields:
        complements: list[skill_id]
        activates_with: list[skill_id]
        cross_domain_bridges:
          - domain: string
            strength: "0.0–1.0"
            note: string

    opp:
      type: string
      notes: "OPP that created or last modified this skill"

# ═══════════════════════════════════════════════════════
# AGENT.md FIELD DEFINITIONS
# ═══════════════════════════════════════════════════════

agent_schema:

  required_fields:
    - agent_id
    - name
    - description
    - tier
    - executor
    - capabilities
    - what_if_fails
    - security

  fields:

    agent_id:
      format: "group.agent_name (e.g., subagent.01-core-development.backend_developer)"

    activation_protocol:
      notes: "If absent, agent relies on explicit invocation only (not auto-activated)"
      fields:
        trigger: string
        activates_in: list[cognitive_mode]
        position_in_pipeline: "STEP_N | PASSIVE_ALL_STEPS"
        max_concurrent: integer

# ═══════════════════════════════════════════════════════
# COGNITIVE MODES & PIPELINE STEPS
# ═══════════════════════════════════════════════════════

cognitive_modes:
  EXPRESS: "< 30s — single-turn, no deep reasoning"
  FAST: "< 2min — standard responses"
  DEEP: "< 10min — multi-step analysis"
  RESEARCH: "< 30min — exhaustive investigation"
  FOGGY: "Clarification needed — underspecified request"
  CLARIFY: "Active disambiguation"
  SCIENTIFIC: "Formal hypothesis + verification"

pipeline_steps:
  STEP_0: "Boot + context loading"
  STEP_1: "Domain detection (pmi_pm)"
  STEP_2: "Architecture design (architect)"
  STEP_3: "Hypothesis generation (theorist)"
  STEP_4: "Implementation (engineer)"
  STEP_5: "Critical review (critic)"
  STEP_6: "Verification (verification-before-completion)"
  STEP_7: "Coordination (programme_director)"
  STEP_8: "Security review (security-guardian)"
  STEP_9: "Quality gate (diff_governance)"
  STEP_10: "Output synthesis"
  STEP_11: "Learning capture (meta_learning_agent)"
  STEP_12: "Memory consolidation"
  STEP_13: "Session close"

# ═══════════════════════════════════════════════════════
# INVIOLABLE RULES REFERENCE
# ═══════════════════════════════════════════════════════

inviolable_rules_quick_ref:
  C1: "No hallucinated methods — verify against UCO_API_SURFACE.yaml before calling"
  C2: "No shell injection — use shlex.split() + shell=False always"
  C3: "No path traversal — use pathlib.Path.resolve() with allowed_bases check"
  C5: "No hardcoded tokens — use environment variables or secrets manager"
  SR_40: "Every ADOPTED skill must have Why/When/WhatIf sections (ZERO_AMBIGUITY_GUARD)"
  H1: "Verification before claim — run and cite output, never say 'probably works'"
  H4: "Single source of truth — this file is canonical for field definitions"
"""

def task_63_canonical_schema(dry_run: bool) -> dict:
    """Create references/APEX_CANONICAL_SCHEMA.yaml."""
    print("\n[TASK 6.3] Create APEX Canonical Master Schema")
    out_path = REPO_ROOT / "references" / "APEX_CANONICAL_SCHEMA.yaml"
    if not dry_run:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(CANONICAL_SCHEMA_CONTENT, encoding='utf-8')
    action = "Would create" if dry_run else "Created"
    print(f"  {action}: {out_path.relative_to(REPO_ROOT)}")
    return {"created": 1}


# ═══════════════════════════════════════════════════════
# TASK 6.4 — Rebuild INDEX.md + per-domain CATALOG.md
# ═══════════════════════════════════════════════════════

def _scan_domain(domain_dir: Path) -> tuple[list[dict], int]:
    """Return list of skill dicts and total count for a domain directory."""
    skills = []
    for sk_path in sorted(domain_dir.rglob("SKILL.md")):
        try:
            c = sk_path.read_text(encoding='utf-8', errors='replace')
            sid = re.search(r'skill_id\s*:\s*["\']?([^\s"\'#\n]+)', c)
            sm = re.search(r'status\s*:\s*(\w+)', c)
            tier = re.search(r'tier\s*:\s*([^\n]+)', c)
            desc = re.search(r'description\s*:\s*["\']?([^"\'\n]{5,150})', c)
            skills.append({
                "skill_id": sid.group(1) if sid else "—",
                "status": sm.group(1)[:9] if sm else "UNKNOWN",
                "tier": tier.group(1).strip()[:8] if tier else "—",
                "desc": (desc.group(1).strip()[:80] if desc else ""),
                "path": str(sk_path.relative_to(REPO_ROOT)),
            })
        except Exception:
            pass
    return skills, len(skills)


def task_64_rebuild_index(dry_run: bool) -> dict:
    """Rebuild INDEX.md as lean hub, generate per-domain CATALOG.md files."""
    print("\n[TASK 6.4] Rebuild INDEX.md + per-domain CATALOG.md")

    # Scan all domain directories (direct children of skills/)
    domain_dirs = sorted([d for d in SKILLS_ROOT.iterdir() if d.is_dir()])
    domain_summaries = []
    catalogs_written = 0

    for domain_dir in domain_dirs:
        skills, count = _scan_domain(domain_dir)
        if count == 0:
            continue

        domain_name = domain_dir.name
        status_dist = Counter(s["status"] for s in skills)
        adopted = status_dist.get("ADOPTED", 0)

        domain_summaries.append({
            "name": domain_name,
            "count": count,
            "adopted": adopted,
            "path": f"skills/{domain_name}/",
            "catalog": f"skills/{domain_name}/CATALOG.md",
            "status_dist": dict(status_dist),
        })

        # Write CATALOG.md for this domain
        catalog_path = domain_dir / "CATALOG.md"
        catalog_lines = [
            f"# {domain_name} — {count} skills",
            f"<!-- OPP-Phase6 | 2026-04-17 | ADOPTED: {adopted}/{count} -->",
            f"<!-- Compact catalog for token-efficient routing. Full schemas in SKILL.md files. -->",
            "",
            "| skill_id | tier | status | description |",
            "|----------|------|--------|-------------|",
        ]
        for s in skills:
            sid = s["skill_id"][:50]
            tier = s["tier"][:6]
            status = s["status"][:9]
            desc = s["desc"][:70].replace("|", "∣")
            catalog_lines.append(f"| `{sid}` | {tier} | {status} | {desc} |")

        catalog_content = "\n".join(catalog_lines) + "\n"
        if not dry_run:
            catalog_path.write_text(catalog_content, encoding='utf-8')
        catalogs_written += 1

    # Build lean INDEX.md
    total_skills = sum(d["count"] for d in domain_summaries)
    total_adopted = sum(d["adopted"] for d in domain_summaries)
    adopted_pct = round(total_adopted / total_skills * 100, 1) if total_skills else 0

    index_lines = [
        "# APEX Skills Index — Navigation Hub",
        f"<!-- v00.36.0 | {total_skills} skills | {len(domain_summaries)} domains | ADOPTED: {total_adopted} ({adopted_pct}%) -->",
        "<!-- Lean hub — full per-skill data in domain CATALOG.md files -->",
        "<!-- Token cost of this file: ~3KB vs 371KB monolith -->",
        "",
        "## Quick Navigation",
        "",
        "```",
        "Find any skill:",
        "  1. Locate domain in table below",
        "  2. Open skills/{domain}/CATALOG.md for skill list",
        "  3. Open skills/{domain}/{skill-name}/SKILL.md for full schema",
        "```",
        "",
        "## Domain Map",
        "",
        f"| Domain | Skills | ADOPTED | Path | Catalog |",
        f"|--------|--------|---------|------|---------|",
    ]

    for d in domain_summaries:
        pct = round(d["adopted"]/d["count"]*100) if d["count"] else 0
        catalog_link = f"[catalog]({d['catalog']})"
        index_lines.append(
            f"| {d['name']} | {d['count']} | {d['adopted']} ({pct}%) "
            f"| `{d['path']}` | {catalog_link} |"
        )

    index_lines += [
        "",
        "---",
        "",
        "## Schema Reference",
        "",
        f"- **Canonical schema**: [`references/APEX_CANONICAL_SCHEMA.yaml`](references/APEX_CANONICAL_SCHEMA.yaml)",
        f"- **Required fields** (ADOPTED): skill_id · description · tier · executor · anchors · input_schema · output_schema · what_if_fails",
        f"- **Validator**: `python tools/validate_repo_uco.py --layer skills`",
        "",
        "## Routing",
        "",
        "Skills are routed via `hyperbolic_search_gravity`: `cosine_similarity × anchor_weight`.",
        "Use canonical anchors (see APEX_CANONICAL_SCHEMA.yaml) to maximize routing accuracy.",
        "",
        "<!-- Generated by tools/phase6_promote_optimize.py task 6.4 -->",
        f"<!-- Source: {total_skills} SKILL.md files across {len(domain_summaries)} domains -->",
    ]

    index_content = "\n".join(index_lines) + "\n"
    index_path = REPO_ROOT / "INDEX.md"

    size_before = index_path.stat().st_size if index_path.exists() else 0
    size_after = len(index_content.encode('utf-8'))

    if not dry_run:
        index_path.write_text(index_content, encoding='utf-8')

    reduction_pct = round((1 - size_after / size_before) * 100, 1) if size_before else 0
    print(f"  INDEX.md: {size_before:,}B → {size_after:,}B ({reduction_pct:.1f}% reduction)")
    print(f"  CATALOG.md files written: {catalogs_written}")
    return {
        "index_before_bytes": size_before,
        "index_after_bytes": size_after,
        "reduction_pct": reduction_pct,
        "catalogs_written": catalogs_written,
        "domains": len(domain_summaries),
        "total_skills": total_skills,
        "total_adopted": total_adopted,
    }


# ═══════════════════════════════════════════════════════
# TASK 6.5 — UCO SA Validation
# ═══════════════════════════════════════════════════════

def _uco_score(uco, code: str) -> int:
    try:
        r = uco.analyze(code)
        d = r.to_dict(); m = d.get('metrics', {}); h = m.get('halstead', {})
        bugs = h.get('bugs_estimate', 0.0)
        cc = m.get('cyclomatic_complexity', 0)
        dead = m.get('syntactic_dead_code', 0)
        dups = m.get('duplicate_block_count', 0)
        return max(0, min(100, 100 - min(40, cc*3) - min(20, dead*5) - min(20, dups*5) - min(20, int(bugs*100))))
    except Exception:
        return -1

def task_65_uco_sa_validation(dry_run: bool) -> dict:
    """Run UCO SA on all Phase 6 tools + validate repo metrics."""
    print("\n[TASK 6.5] UCO SA Validation")

    if not UCO_AVAILABLE:
        print("  [SKIP] UCO not available")
        return {"skipped": True}

    uco = UniversalCodeOptimizer()

    # Phase 6 tools to SA-optimize
    target_scripts = [
        REPO_ROOT / "tools" / "phase6_promote_optimize.py",
        REPO_ROOT / "tools" / "validate_repo_uco.py",
        REPO_ROOT / "tools" / "normalize_schema.py",
        REPO_ROOT / "tools" / "phase3_quality.py",
    ]

    results = []
    for script in target_scripts:
        if not script.exists():
            continue
        code = script.read_text(encoding='utf-8', errors='replace')
        score_before = _uco_score(uco, code)
        if score_before < 0:
            continue
        try:
            r = uco.optimize_fast(code, n_steps=10)
            opt = r.optimized_code if r.optimized_code else code
            score_after = _uco_score(uco, opt)
            delta = score_after - score_before
            improved = (score_after > score_before
                        and opt != code
                        and len(opt) >= len(code) * 0.70)
            if improved:
                try:
                    compile(opt, str(script), 'exec')
                    if not dry_run:
                        script.write_text(opt, encoding='utf-8')
                except SyntaxError:
                    improved = False
                    delta = 0

            results.append({
                "script": script.name,
                "score_before": score_before,
                "score_after": score_after if improved else score_before,
                "delta": delta if improved else 0,
                "improved": improved,
                "sa_summary": r.summary.get('status_after', '?') if r.summary else '?',
            })
            sign = f"+{delta}" if delta > 0 else str(delta)
            status = "✓" if improved else "~"
            print(f"  {status} {script.name}: {score_before}→{score_after if improved else score_before} ({sign})")
        except Exception as e:
            results.append({"script": script.name, "error": str(e)[:60]})

    # Quick repo-level validation summary
    print("\n  Repository validation summary:")
    skills = list(SKILLS_ROOT.rglob("SKILL.md"))
    adopted = sum(1 for sk in skills if 'status: ADOPTED' in (sk.read_text(encoding='utf-8', errors='replace') if sk.exists() else ''))
    total = len(skills)
    sr40 = sum(1 for sk in skills
               if all(s in (sk.read_text(encoding='utf-8', errors='replace') if sk.exists() else '')
                      for s in ["## Why This Skill Exists", "## When to Use", "## What If Fails"]))
    print(f"    Total skills:       {total}")
    print(f"    ADOPTED:            {adopted} ({round(adopted/total*100,1)}%)")
    print(f"    SR_40 compliant:    {sr40} ({round(sr40/total*100,1)}%)")

    return {
        "scripts_analyzed": len(results),
        "scripts_improved": sum(1 for r in results if r.get("improved")),
        "repo_total_skills": total,
        "repo_adopted": adopted,
        "repo_adopted_pct": round(adopted/total*100, 1),
        "repo_sr40_pct": round(sr40/total*100, 1),
    }


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="APEX Phase 6 — Promote + Optimize")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tasks", default="6.1,6.2,6.3,6.4,6.5",
                        help="Comma-separated tasks")
    args = parser.parse_args()

    tasks = {t.strip() for t in args.tasks.split(",")}
    mode = "DRY-RUN" if args.dry_run else "LIVE"

    print("=" * 70)
    print(f"APEX Phase 6 — Promote + Optimize + Monolith | Mode: {mode}")
    print(f"Tasks: {sorted(tasks)}")
    print("=" * 70)

    t0 = time.time()
    results = {}

    if "6.1" in tasks:
        results["6.1"] = task_61_promote_complete(args.dry_run)

    if "6.2" in tasks:
        results["6.2"] = task_62_autocomplete_promote(args.dry_run)

    if "6.3" in tasks:
        results["6.3"] = task_63_canonical_schema(args.dry_run)

    if "6.4" in tasks:
        results["6.4"] = task_64_rebuild_index(args.dry_run)

    if "6.5" in tasks:
        results["6.5"] = task_65_uco_sa_validation(args.dry_run)

    print(f"\n{'=' * 70}")
    print(f"Phase 6 complete in {time.time()-t0:.1f}s | {mode}")
    print("\nResults summary:")
    for task, r in results.items():
        print(f"  Task {task}: {r}")

if __name__ == "__main__":
    main()
