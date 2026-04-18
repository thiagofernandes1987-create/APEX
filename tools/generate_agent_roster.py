#!/usr/bin/env python3
"""
tools/generate_agent_roster.py — APEX OPP-153/OPP-154: Generate community_agent_roster.yaml
=============================================================================================
APEX OPP-153 + OPP-154 | 2026-04-17

PROBLEM:
  163 AGENT.md files exist on disk but are NOT registered in the boot's
  community_agent_roster. Without registration, these agents are never activated
  by meta_reasoning — they exist but can't be called automatically.

    - 140 community-subagents (OPP-153): agents/community-subagents/categories/**
    - 23 cs_ personas     (OPP-154): agents/cs_*/AGENT.md

SOLUTION:
  1. Scan all AGENT.md files in the two groups
  2. Derive activates_when[] from agent_id, category, capabilities, description
  3. Generate agents/community_agent_roster.yaml — machine-readable roster
  4. Generate references/OPP-153-register-subagents.md — formal OPP document

USAGE:
  python tools/generate_agent_roster.py [--dry-run] [--output PATH]
"""

from __future__ import annotations
import argparse
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO_ROOT = Path(__file__).parent.parent
SUBAGENTS_ROOT = REPO_ROOT / "agents" / "community-subagents" / "categories"
CS_ROOT = REPO_ROOT / "agents"

# ── Domain activation map: category → activates_when domains
CATEGORY_DOMAIN_MAP = {
    "01-core-development":    ["code", "engineering", "backend", "frontend", "api", "fullstack"],
    "02-language-specialists":["code", "engineering", "backend", "frontend"],
    "03-infrastructure":      ["devops", "cloud", "deployment", "infrastructure", "operations"],
    "04-quality-security":    ["testing", "security", "code_review", "debugging", "quality"],
    "05-data-ai":             ["data", "ml", "ai", "database", "analytics", "llm"],
    "06-developer-experience":["devops", "engineering", "tooling", "documentation", "dx"],
    "07-specialized-domains": ["specialized", "domain_expert"],
    "08-business-product":    ["business", "product", "marketing", "sales", "legal"],
    "09-meta-orchestration":  ["orchestration", "coordination", "workflow", "multi_agent"],
    "10-research-analysis":   ["research", "analysis", "intelligence", "competitive"],
}

# ── Keyword-to-domain inference for fine-grained activates_when
KEYWORD_DOMAIN_MAP = {
    "security":      "security",
    "test":          "testing",
    "frontend":      "frontend",
    "backend":       "backend",
    "api":           "api",
    "database":      "database",
    "cloud":         "cloud",
    "devops":        "devops",
    "docker":        "devops",
    "kubernetes":    "devops",
    "ml":            "ml",
    "machine":       "ml",
    "ai":            "ai",
    "llm":           "llm",
    "data":          "data",
    "analytics":     "analytics",
    "marketing":     "marketing",
    "product":       "product",
    "business":      "business",
    "research":      "research",
    "analysis":      "analysis",
    "orchestr":      "orchestration",
    "workflow":      "workflow",
    "performance":   "performance",
    "refactor":      "refactoring",
    "debug":         "debugging",
    "monitor":       "monitoring",
    "finance":       "finance",
    "legal":         "legal",
    "startup":       "startup",
    "mobile":        "mobile",
    "ios":           "mobile",
    "android":       "mobile",
    "python":        "code",
    "javascript":    "code",
    "typescript":    "code",
    "react":         "frontend",
    "angular":       "frontend",
    "vue":           "frontend",
    "golang":        "code",
    "rust":          "code",
    "java":          "code",
    "csharp":        "code",
    "dotnet":        "code",
    "php":           "code",
    "ruby":          "code",
    "swift":         "mobile",
    "kotlin":        "mobile",
    "sql":           "database",
    "terraform":     "infrastructure",
    "aws":           "cloud",
    "azure":         "cloud",
    "gcp":           "cloud",
    "git":           "engineering",
    "documentation": "documentation",
    "readme":        "documentation",
    "seo":           "marketing",
    "content":       "marketing",
    "sales":         "sales",
    "customer":      "sales",
    "game":          "specialized",
    "blockchain":    "specialized",
    "embedded":      "specialized",
    "fintech":       "finance",
    "quant":         "finance",
    "risk":          "risk",
    "iot":           "specialized",
}


def extract_activates_when(agent_id: str, name: str, category: str,
                            capabilities: list[str], description: str) -> list[str]:
    """Derive activates_when from agent metadata."""
    domains = set(CATEGORY_DOMAIN_MAP.get(category, []))

    # From agent name and capabilities
    combined = f"{agent_id} {name} {' '.join(capabilities)} {description}".lower()
    for keyword, domain in KEYWORD_DOMAIN_MAP.items():
        if keyword in combined:
            domains.add(domain)

    return sorted(domains)


def parse_agent_md(path: Path) -> dict | None:
    """Extract frontmatter fields from AGENT.md."""
    try:
        content = path.read_text(encoding='utf-8', errors='replace')
    except Exception:
        return None

    # Extract first frontmatter block (between first --- pair)
    fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not fm_match:
        return None
    fm = fm_match.group(1)

    def get_field(key: str) -> str | None:
        m = re.search(rf'^{key}\s*:\s*(.+)$', fm, re.MULTILINE)
        return m.group(1).strip().strip('"\'') if m else None

    def get_list_field(key: str) -> list[str]:
        m = re.search(rf'^{key}\s*:\s*\n((?:\s+-[^\n]+\n?)+)', fm, re.MULTILINE)
        if not m:
            return []
        return [re.sub(r'^\s*-\s*', '', line).strip().strip('"\'')
                for line in m.group(1).splitlines() if line.strip()]

    return {
        "agent_id": get_field("agent_id"),
        "name": get_field("name") or path.parent.name,
        "description": get_field("description") or "",
        "version": get_field("version") or "v00.37.0",
        "status": get_field("status") or "ADOPTED",
        "tier": get_field("tier") or "2",
        "category": get_field("category") or "",
        "capabilities": get_list_field("capabilities"),
        "path": str(path.relative_to(REPO_ROOT)),
    }


def collect_subagents() -> list[dict]:
    """Collect all community-subagent AGENT.md files."""
    agents = []
    for agent_path in sorted(SUBAGENTS_ROOT.rglob("AGENT.md")):
        data = parse_agent_md(agent_path)
        if not data:
            continue
        # Extract category from path
        rel = agent_path.relative_to(SUBAGENTS_ROOT)
        category = rel.parts[0] if len(rel.parts) > 1 else ""
        data["category"] = category
        data["group"] = "community-subagents"
        data["activates_when"] = extract_activates_when(
            data.get("agent_id", ""),
            data["name"],
            category,
            data["capabilities"],
            data["description"],
        )
        agents.append(data)
    return agents


def collect_cs_agents() -> list[dict]:
    """Collect cs_ persona AGENT.md files."""
    agents = []
    for agent_path in sorted(CS_ROOT.glob("cs_*/AGENT.md")):
        data = parse_agent_md(agent_path)
        if not data:
            continue
        data["group"] = "cs-personas"
        data["activates_when"] = extract_activates_when(
            data.get("agent_id", ""),
            data["name"],
            "cs-personas",
            data["capabilities"],
            data["description"],
        )
        agents.append(data)
    return agents


def generate_roster_yaml(subagents: list[dict], cs_agents: list[dict]) -> str:
    """Generate the community_agent_roster.yaml content."""
    lines = [
        "# community_agent_roster.yaml",
        "# APEX OPP-153 + OPP-154 | 2026-04-17",
        "# Auto-generated by tools/generate_agent_roster.py",
        "# WHY: 163 agents existed on disk without registration in the boot's roster.",
        "#      Without this roster, meta_reasoning cannot activate them automatically.",
        "# FORMAT: Each entry maps agent_id → activates_when[] domains.",
        "#         meta_reasoning emits [COMMUNITY_AGENT_ACTIVATED: {agent}] when",
        "#         request domain matches any activates_when entry.",
        "",
        f"version: v00.36.0",
        f"opp: OPP-153",
        f"total_agents: {len(subagents) + len(cs_agents)}",
        "",
        "# ═══════════════════════════════════════════════════════",
        "# COMMUNITY SUBAGENTS (OPP-153)",
        f"# {len(subagents)} agents across 10 categories",
        "# ═══════════════════════════════════════════════════════",
        "community_subagent_roster:",
    ]

    # Group by category
    by_category: dict[str, list[dict]] = {}
    for a in subagents:
        cat = a.get("category", "unknown")
        by_category.setdefault(cat, []).append(a)

    for cat in sorted(by_category.keys()):
        lines.append(f"")
        lines.append(f"  # {cat}")
        for a in by_category[cat]:
            agent_id = a.get("agent_id") or f"subagent.{a['name'].replace('-', '_')}"
            name = a["name"]
            activates = a.get("activates_when", [])
            lines.append(f"  - agent_id: {agent_id}")
            lines.append(f"    name: {name}")
            lines.append(f"    path: {a['path']}")
            if activates:
                lines.append(f"    activates_when:")
                for d in activates:
                    lines.append(f"      - {d}")
            lines.append(f"    tier: {a.get('tier', 2)}")
            lines.append(f"    max_concurrent: 1")

    lines += [
        "",
        "# ═══════════════════════════════════════════════════════",
        "# CS PERSONA AGENTS (OPP-154)",
        f"# {len(cs_agents)} persona agents (formerly SKILL-based personas)",
        "# ═══════════════════════════════════════════════════════",
        "cs_agent_roster:",
    ]

    for a in cs_agents:
        agent_id = a.get("agent_id") or f"community.{a['name'].replace('-', '_')}"
        name = a["name"]
        activates = a.get("activates_when", [])
        lines.append(f"")
        lines.append(f"  - agent_id: {agent_id}")
        lines.append(f"    name: {name}")
        lines.append(f"    path: {a['path']}")
        if activates:
            lines.append(f"    activates_when:")
            for d in activates:
                lines.append(f"      - {d}")
        lines.append(f"    tier: {a.get('tier', 2)}")
        lines.append(f"    max_concurrent: 1")

    lines += [
        "",
        "# ═══════════════════════════════════════════════════════",
        "# ACTIVATION PROTOCOL",
        "# ═══════════════════════════════════════════════════════",
        "activation_protocol:",
        "  trigger: meta_reasoning at STEP_1 (pmi_pm domain detection)",
        "  max_concurrent_community: 2",
        "  priority: domain_expert_first",
        "  fallback: engineer (base agent)",
        "  emit_on_activation: '[COMMUNITY_AGENT_ACTIVATED: {agent_id} | domain: {domain}]'",
        "  emit_on_fallback: '[SUBAGENT_FALLBACK: {agent_id}]'",
    ]

    return "\n".join(lines) + "\n"


def generate_opp_document(subagents: list[dict], cs_agents: list[dict]) -> str:
    """Generate OPP-153 formal document."""
    by_category: dict[str, list[dict]] = {}
    for a in subagents:
        by_category.setdefault(a.get("category", "?"), []).append(a)

    cat_table = "\n".join(
        f"| `{cat}` | {len(agents)} |"
        for cat, agents in sorted(by_category.items())
    )

    return f"""# OPP-153 — Register Community Subagents in Boot Roster
## OPP-154 — Register CS Persona Agents in Boot Roster

**OPP**: OPP-153 / OPP-154
**Version**: v00.36.0
**Date**: 2026-04-17
**Status**: IMPLEMENTED
**Priority**: HIGH
**Author**: APEX Pipeline (auto-generated via tools/generate_agent_roster.py)

---

## Problem Statement

**{len(subagents) + len(cs_agents)} agents exist on disk but are NOT registered in the boot's `community_agent_roster`.**

Without registration, `meta_reasoning` cannot activate these agents automatically.
They exist as AGENT.md files but are invisible to the APEX activation pipeline.

### Breakdown

| Group | Count | Location |
|-------|-------|----------|
| community-subagents | {len(subagents)} | `agents/community-subagents/categories/` |
| cs-personas | {len(cs_agents)} | `agents/cs_*/` |
| **Total unregistered** | **{len(subagents) + len(cs_agents)}** | |

### Community Subagents by Category

| Category | Agents |
|----------|--------|
{cat_table}

### CS Persona Agents ({len(cs_agents)})

{chr(10).join(f'- `{a["name"]}`' for a in cs_agents)}

---

## Root Cause

- APEX boot v00.36.0 `community_agent_roster` only lists the 9 `community_*` base agents explicitly.
- The 140 community-subagents (created via OPP-150) were added to disk but never received a boot-level `activates_when` mapping.
- The 23 cs_ persona agents were converted from SKILL.md files to AGENT.md but never mapped to the activation pipeline.

---

## Solution

### OPP-153: community-subagents
1. Scan `agents/community-subagents/categories/**/AGENT.md`
2. Derive `activates_when[]` from: category, agent_id, capabilities, description
3. Write `agents/community_agent_roster.yaml` with full roster

### OPP-154: cs-personas
1. Scan `agents/cs_*/AGENT.md`
2. Derive `activates_when[]` from agent description and capabilities
3. Append to `community_agent_roster.yaml` under `cs_agent_roster:`

### Activation Rule (for boot integration)
```yaml
# Add to APEX boot kernel.community_activation:
community_agent_roster_file: agents/community_agent_roster.yaml
activation_trigger: meta_reasoning.STEP_1 (domain detection)
max_concurrent: 2  # 1 domain expert + 1 orchestrator
fallback: engineer
```

---

## Files Changed

| File | Change |
|------|--------|
| `agents/community_agent_roster.yaml` | NEW — machine-readable roster with `activates_when` mappings |
| `tools/generate_agent_roster.py` | NEW — generator script (idempotent, re-runnable) |
| `references/OPP-153-register-subagents.md` | NEW — this document |

---

## Activation Protocol

```
STEP 1: pmi_pm detects domain from user request
STEP 2: meta_reasoning checks community_agent_roster.yaml
          → finds agent where domain in activates_when[]
          → emits [COMMUNITY_AGENT_ACTIVATED: {{agent_id}} | domain: {{domain}}]
STEP 3: Agent activated as specialist alongside base engineer
          → MAX 2 concurrent community agents
STEP 4: On failure: emit [SUBAGENT_FALLBACK: {{agent_id}}] + use base agent
```

---

## Impact

- **Before**: 163 agents exist but 0 are auto-activated by meta_reasoning
- **After**: 163 agents registered with `activates_when` mappings → auto-activated by domain
- **Coverage**: Adds domain-expert coverage for: code, testing, security, data, ml, devops, cloud, business, product, research, and 20+ language-specific domains

---

## Verification

```bash
python tools/generate_agent_roster.py --dry-run
# Expected: {len(subagents)} subagents + {len(cs_agents)} cs agents = {len(subagents) + len(cs_agents)} total
```

---

## Diff History
- **v00.36.0**: OPP-153/154 implemented — `community_agent_roster.yaml` generated; {len(subagents) + len(cs_agents)} agents registered
"""


def main():
    parser = argparse.ArgumentParser(description="Generate APEX community_agent_roster.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=None, help="Output YAML path (default: agents/community_agent_roster.yaml)")
    args = parser.parse_args()

    print(f"\nAPEX OPP-153/154 — Agent Roster Generator ({'DRY-RUN' if args.dry_run else 'LIVE'})")
    print(f"Root: {REPO_ROOT}\n")

    # Collect agents
    print("  Collecting community-subagents...")
    subagents = collect_subagents()
    print(f"  Found: {len(subagents)} community-subagents")

    print("  Collecting cs_ persona agents...")
    cs_agents = collect_cs_agents()
    print(f"  Found: {len(cs_agents)} cs persona agents")

    total = len(subagents) + len(cs_agents)
    print(f"  Total: {total} agents to register\n")

    # Generate roster YAML
    roster_yaml = generate_roster_yaml(subagents, cs_agents)
    roster_path = Path(args.output) if args.output else REPO_ROOT / "agents" / "community_agent_roster.yaml"

    if not args.dry_run:
        roster_path.write_text(roster_yaml, encoding='utf-8')
        print(f"  Written: {roster_path}")
    else:
        print(f"  [DRY] Would write: {roster_path} ({len(roster_yaml)} chars)")

    # Generate OPP document
    opp_content = generate_opp_document(subagents, cs_agents)
    opp_path = REPO_ROOT / "references" / "OPP-153-register-subagents.md"

    if not args.dry_run:
        opp_path.write_text(opp_content, encoding='utf-8')
        print(f"  Written: {opp_path}")
    else:
        print(f"  [DRY] Would write: {opp_path}")

    print(f"\nDone. {total} agents registered.")

    # Stats
    by_cat: dict[str, int] = {}
    for a in subagents:
        by_cat[a.get("category", "?")] = by_cat.get(a.get("category", "?"), 0) + 1
    print("\n  community-subagents by category:")
    for cat, cnt in sorted(by_cat.items()):
        print(f"    {cat}: {cnt}")
    print(f"\n  cs_agents: {len(cs_agents)}")


if __name__ == "__main__":
    main()
