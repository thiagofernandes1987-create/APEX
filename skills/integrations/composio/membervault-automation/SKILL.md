---
name: membervault-automation
description: "Automate Membervault tasks via Rube MCP (Composio). Always search tools first for current schemas."
requires:
  mcp: [rube]
executor: HYBRID
skill_id: integrations.composio.membervault-automation
status: CANDIDATE
security: {level: high, pii: false, approval_required: true}
extends: integrations.composio.meta
toolkit: membervault-automation
# Phase3: This stub routes to the meta-skill. See skills/integrations/composio/SKILL.md for full protocol.
anchors:
  - automation
  - integration
  - api
  - workflow
---

# Membervault Automation via Rube MCP

Automate Membervault operations through Composio's Membervault toolkit via Rube MCP.

**Toolkit docs**: [composio.dev/toolkits/membervault](https://composio.dev/toolkits/membervault)

## Prerequisites

- Rube MCP must be connected (RUBE_SEARCH_TOOLS available)
- Active Membervault connection via `RUBE_MANAGE_CONNECTIONS` with toolkit `membervault`
- Always call `RUBE_SEARCH_TOOLS` first to get current tool schemas

## Setup

**Get Rube MCP**: Add `https://rube.app/mcp` as an MCP server in your client configuration. No API keys needed — just add the endpoint and it works.

1. Verify Rube MCP is available by confirming `RUBE_SEARCH_TOOLS` responds
2. Call `RUBE_MANAGE_CONNECTIONS` with toolkit `membervault`
3. If connection is not ACTIVE, follow the returned auth link to complete setup
4. Confirm connection status shows ACTIVE before running any workflows

## Tool Discovery

Always discover available tools before executing workflows:

```
RUBE_SEARCH_TOOLS
queries: [{use_case: "Membervault operations", known_fields: ""}]
session: {generate_id: true}
```

This returns available tool slugs, input schemas, recommended execution plans, and known pitfalls.

## Core Workflow Pattern

### Step 1: Discover Available Tools

```
RUBE_SEARCH_TOOLS
queries: [{use_case: "your specific Membervault task"}]
session: {id: "existing_session_id"}
```

### Step 2: Check Connection

```
RUBE_MANAGE_CONNECTIONS
toolkits: ["membervault"]
session_id: "your_session_id"
```

### Step 3: Execute Tools

```
RUBE_MULTI_EXECUTE_TOOL
tools: [{
  tool_slug: "TOOL_SLUG_FROM_SEARCH",
  arguments: {/* schema-compliant args from search results */}
}]
memory: {}
session_id: "your_session_id"
```

## Known Pitfalls

- **Always search first**: Tool schemas change. Never hardcode tool slugs or arguments without calling `RUBE_SEARCH_TOOLS`
- **Check connection**: Verify `RUBE_MANAGE_CONNECTIONS` shows ACTIVE status before executing tools
- **Schema compliance**: Use exact field names and types from the search results
- **Memory parameter**: Always include `memory` in `RUBE_MULTI_EXECUTE_TOOL` calls, even if empty (`{}`)
- **Session reuse**: Reuse session IDs within a workflow. Generate new ones for new workflows
- **Pagination**: Check responses for pagination tokens and continue fetching until complete

## Quick Reference

| Operation | Approach |
|-----------|----------|
| Find tools | `RUBE_SEARCH_TOOLS` with Membervault-specific use case |
| Connect | `RUBE_MANAGE_CONNECTIONS` with toolkit `membervault` |
| Execute | `RUBE_MULTI_EXECUTE_TOOL` with discovered tool slugs |
| Bulk ops | `RUBE_REMOTE_WORKBENCH` with `run_composio_tool()` |
| Full schema | `RUBE_GET_TOOL_SCHEMAS` for tools with `schemaRef` |

---
*Powered by [Composio](https://composio.dev)*

## Why This Skill Exists
Stub for the `membervault-automation` toolkit in the Composio integration ecosystem.
Extends `integrations.composio.meta` — see the meta-skill for full protocol.

## When to Use
Use when automating `membervault-automation` tasks via Rube MCP (Composio).
For generic Composio queries, use `integrations.composio.meta` directly.

## What If Fails
See `skills/integrations/composio/SKILL.md` (meta-skill) for full fallback protocol.
RULE: Never block workflow — always suggest manual alternative if automation fails.
