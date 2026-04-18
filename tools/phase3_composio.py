"""
tools/phase3_composio.py — APEX Phase 3: Composio Meta-Skill Consolidation
============================================================================
APEX OPP-Phase3 | 2026-04-17

PROBLEM:
  832 SKILL.md in skills/integrations/composio/ are semantically identical:
    "Automate <toolkit> tasks via Rube MCP (Composio). Always search tools first."
  They inflate the index, create routing noise, and are functionally a single
  parametrized skill.

SOLUTION (surgical):
  1. Create ONE meta-skill: skills/integrations/composio/SKILL.md
     Full APEX DSL schema, parametrized by toolkit_name.
  2. Each existing stub gets a minimal 3-field update:
     - extends: integrations.composio.meta
     - toolkit: <toolkit-name>
     - A comment pointing to the meta-skill
  Existing content is NOT deleted — stubs remain browsable.

WHY NOT DELETE:
  Stubs serve as entry points for direct toolkit-name routing. The meta-skill
  handles generic "automate with composio" queries; stubs handle specific
  "automate ably" queries.

USAGE:
  python tools/phase3_composio.py [--dry-run]
"""

from __future__ import annotations

import argparse
import pathlib
import re

REPO_ROOT = pathlib.Path(__file__).parent.parent
COMPOSIO_ROOT = REPO_ROOT / "skills" / "integrations" / "composio"

META_SKILL_CONTENT = """\
---
name: composio-automation
skill_id: integrations.composio.meta
description: "Automate any third-party API task via Rube MCP (Composio). Parametrize by toolkit_name to target a specific integration."
version: v00.36.0
status: ADOPTED
tier: 2
executor: HYBRID
parameter: toolkit_name
anchors:
  - automation
  - integration
  - api
  - workflow
  - agent
synergy_map:
  complements: [integrations.composio.meta, workflow_automation, agent_orchestration]
  activates_with: [mcp_bridge_v2, forgeskills_rapid_reader]
  cross_domain_bridges:
    - domain: engineering
      strength: 0.85
      note: "Composio skills are engineering-facing API wrappers"
    - domain: business
      strength: 0.70
      note: "Many toolkits target business workflows (CRM, email, calendar)"
requires:
  mcp: [rube]
security:
  level: standard
  pii: false
  approval_required: false
  note: "Individual toolkits may have higher security requirements — check toolkit SKILL.md"
what_if_fails: >
  FALLBACK 1: If RUBE_SEARCH_TOOLS unavailable, check Rube MCP connection at https://rube.app/mcp.
  FALLBACK 2: If toolkit connection fails, use RUBE_MANAGE_CONNECTIONS to reconnect.
  FALLBACK 3: If toolkit not available in Rube, use direct API calls with official SDK.
  RULE: Never block workflow — always suggest manual alternative if automation fails.
opp: OPP-Phase3-composio-consolidation
---

# Composio Automation — Meta-Skill

Automate any third-party API integration via [Rube MCP](https://rube.app/mcp) using
Composio's toolkit ecosystem. Replace `{toolkit_name}` with the target integration.

**Available toolkits**: 800+ integrations including GitHub, Slack, Notion, Jira, Salesforce,
HubSpot, Google Workspace, Linear, Asana, and more.

## Why This Skill Exists

Composio provides 800+ pre-built API integrations accessible through a single MCP endpoint.
This meta-skill enables the APEX router to handle *any* Composio toolkit request through one
canonical entry point, eliminating the routing noise of 832 identical skill stubs.
Use toolkit-specific stubs (`integrations.composio.<toolkit>`) for direct toolkit routing.

## When to Use

Use this skill when:
- Automating tasks in a third-party tool available in Composio's toolkit catalog
- The specific toolkit name is known (pass as `toolkit_name` parameter)
- The workflow requires connecting multiple Composio integrations
- Looking up available tools for a specific integration before calling them

## What If Fails

1. **Rube MCP unavailable**: Verify MCP server is configured at `https://rube.app/mcp`
2. **Toolkit not found**: Run `RUBE_SEARCH_TOOLS toolkit=<name>` to verify availability
3. **Connection error**: Use `RUBE_MANAGE_CONNECTIONS` to reconnect the specific toolkit
4. **Rate limited**: Implement exponential backoff; check Composio dashboard for limits

## Standard Protocol

```
1. VERIFY: Confirm Rube MCP is active (RUBE_SEARCH_TOOLS responds)
2. CONNECT: RUBE_MANAGE_CONNECTIONS with toolkit = {toolkit_name}
3. DISCOVER: RUBE_SEARCH_TOOLS to get current tool schemas for this toolkit
4. EXECUTE: Call the specific tool with parameters from RUBE_SEARCH_TOOLS output
5. HANDLE: Check return status; implement fallback if tool fails
```

## Parametrized Usage

```yaml
# When routing to a specific toolkit, pass:
skill: integrations.composio.meta
parameter:
  toolkit_name: "github"   # or slack, notion, jira, salesforce, etc.
```

## Toolkit Index

For toolkit-specific details, see individual stubs:
`skills/integrations/composio/<toolkit-name>/SKILL.md`

Each stub declares:
```yaml
extends: integrations.composio.meta
toolkit: <toolkit-name>
```

## Slash Commands (via Rube MCP)

| Command | Description |
|---------|-------------|
| `RUBE_SEARCH_TOOLS` | Discover available tools for a toolkit |
| `RUBE_MANAGE_CONNECTIONS` | Connect/disconnect toolkit |
| `RUBE_EXECUTE_TOOL` | Execute a specific tool |

## Diff History
- **v00.36.0**: Created via OPP-Phase3-composio-consolidation
  (replaced 832 identical stubs with parametrized meta-skill)
"""


def update_stub(path: pathlib.Path, dry_run: bool) -> bool:
    """Add extends + toolkit fields to an existing Composio stub."""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    # Skip if already updated
    if "extends: integrations.composio.meta" in content:
        return False

    # Extract toolkit name from path
    toolkit = path.parent.name.lower()
    # Clean up leading dash or number prefixes (e.g., -21risk-automation → 21risk-automation)
    toolkit = toolkit.lstrip("-")

    # Add extends + toolkit to frontmatter
    FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    fm_match = FRONTMATTER_RE.match(content)
    if not fm_match:
        return False

    fm_end = content.rfind("---\n", 0, fm_match.end())
    if fm_end == -1:
        return False

    injection = (
        f"extends: integrations.composio.meta\n"
        f"toolkit: {toolkit}\n"
        f"# Phase3: This stub routes to the meta-skill. "
        f"See skills/integrations/composio/SKILL.md for full protocol.\n"
    )
    new_content = content[:fm_end] + injection + content[fm_end:]

    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="APEX Phase 3 Composio Consolidation")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print(f"\nAPEX Phase 3 — Composio Consolidation ({'DRY-RUN' if args.dry_run else 'LIVE'})")
    print(f"Root: {COMPOSIO_ROOT}\n")

    # Step 1: Create meta-skill
    meta_path = COMPOSIO_ROOT / "SKILL.md"
    if meta_path.exists():
        print(f"  Meta-skill already exists: {meta_path}")
    else:
        if not args.dry_run:
            meta_path.write_text(META_SKILL_CONTENT, encoding="utf-8")
        print(f"  {'[DRY] Would create' if args.dry_run else 'Created'}: {meta_path}")

    # Step 2: Update stubs
    stubs = [
        p for p in COMPOSIO_ROOT.rglob("SKILL.md")
        if p != meta_path
    ]
    print(f"  Stubs to update: {len(stubs)}")

    updated = 0
    for path in stubs:
        if update_stub(path, dry_run=args.dry_run):
            updated += 1

    action = "Would update" if args.dry_run else "Updated"
    print(f"  {action}: {updated}/{len(stubs)} stubs")
    print(f"\nDone. Meta-skill: skills/integrations/composio/SKILL.md")


if __name__ == "__main__":
    main()
