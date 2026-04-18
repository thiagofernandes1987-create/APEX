---
name: lemon_squeezy-automation
description: "Automate Lemon Squeezy tasks via Rube MCP (Composio): products, orders, subscriptions, checkouts, and digital sales. Always search tools first for current schemas."
requires:
  mcp: [rube]
executor: HYBRID
skill_id: integrations.composio.lemon_squeezy-automation
status: CANDIDATE
security: {level: standard, pii: false, approval_required: false}
extends: integrations.composio.meta
toolkit: lemon_squeezy-automation
# Phase3: This stub routes to the meta-skill. See skills/integrations/composio/SKILL.md for full protocol.
anchors:
  - automation
  - integration
  - api
  - workflow
---

# Lemon Squeezy Automation via Rube MCP

Automate Lemon Squeezy operations through Composio's Lemon Squeezy toolkit via Rube MCP.

**Toolkit docs**: [composio.dev/toolkits/lemon_squeezy](https://composio.dev/toolkits/lemon_squeezy)

## Prerequisites

- Rube MCP must be connected (RUBE_SEARCH_TOOLS available)
- Active Lemon Squeezy connection via `RUBE_MANAGE_CONNECTIONS` with toolkit `lemon_squeezy`
- Always call `RUBE_SEARCH_TOOLS` first to get current tool schemas

## Setup

**Get Rube MCP**: Add `https://rube.app/mcp` as an MCP server in your client configuration. No API keys needed — just add the endpoint and it works.

1. Verify Rube MCP is available by confirming `RUBE_SEARCH_TOOLS` responds
2. Call `RUBE_MANAGE_CONNECTIONS` with toolkit `lemon_squeezy`
3. If connection is not ACTIVE, follow the returned auth link to complete setup
4. Confirm connection status shows ACTIVE before running any workflows

## Tool Discovery

Always discover available tools before executing workflows:

```
RUBE_SEARCH_TOOLS: queries=[{"use_case": "products, orders, subscriptions, checkouts, and digital sales", "known_fields": ""}]
```

This returns:
- Available tool slugs for Lemon Squeezy
- Recommended execution plan steps
- Known pitfalls and edge cases
- Input schemas for each tool

## Core Workflows

### 1. Discover Available Lemon Squeezy Tools

```
RUBE_SEARCH_TOOLS:
  queries:
    - use_case: "list all available Lemon Squeezy tools and capabilities"
```

Review the returned tools, their descriptions, and input schemas before proceeding.

### 2. Execute Lemon Squeezy Operations

After discovering tools, execute them via:

```
RUBE_MULTI_EXECUTE_TOOL:
  tools:
    - tool_slug: "<discovered_tool_slug>"
      arguments: {<schema-compliant arguments>}
  memory: {}
  sync_response_to_workbench: false
```

### 3. Multi-Step Workflows

For complex workflows involving multiple Lemon Squeezy operations:

1. Search for all relevant tools: `RUBE_SEARCH_TOOLS` with specific use case
2. Execute prerequisite steps first (e.g., fetch before update)
3. Pass data between steps using tool responses
4. Use `RUBE_REMOTE_WORKBENCH` for bulk operations or data processing

## Common Patterns

### Search Before Action
Always search for existing resources before creating new ones to avoid duplicates.

### Pagination
Many list operations support pagination. Check responses for `next_cursor` or `page_token` and continue fetching until exhausted.

### Error Handling
- Check tool responses for errors before proceeding
- If a tool fails, verify the connection is still ACTIVE
- Re-authenticate via `RUBE_MANAGE_CONNECTIONS` if connection expired

### Batch Operations
For bulk operations, use `RUBE_REMOTE_WORKBENCH` with `run_composio_tool()` in a loop with `ThreadPoolExecutor` for parallel execution.

## Known Pitfalls

- **Always search tools first**: Tool schemas and available operations may change. Never hardcode tool slugs without first discovering them via `RUBE_SEARCH_TOOLS`.
- **Check connection status**: Ensure the Lemon Squeezy connection is ACTIVE before executing any tools. Expired OAuth tokens require re-authentication.
- **Respect rate limits**: If you receive rate limit errors, reduce request frequency and implement backoff.
- **Validate schemas**: Always pass strictly schema-compliant arguments. Use `RUBE_GET_TOOL_SCHEMAS` to load full input schemas when `schemaRef` is returned instead of `input_schema`.

## Quick Reference

| Operation | Approach |
|-----------|----------|
| Find tools | `RUBE_SEARCH_TOOLS` with Lemon Squeezy-specific use case |
| Connect | `RUBE_MANAGE_CONNECTIONS` with toolkit `lemon_squeezy` |
| Execute | `RUBE_MULTI_EXECUTE_TOOL` with discovered tool slugs |
| Bulk ops | `RUBE_REMOTE_WORKBENCH` with `run_composio_tool()` |
| Full schema | `RUBE_GET_TOOL_SCHEMAS` for tools with `schemaRef` |

> **Toolkit docs**: [composio.dev/toolkits/lemon_squeezy](https://composio.dev/toolkits/lemon_squeezy)

## Why This Skill Exists
Stub for the `lemon_squeezy-automation` toolkit in the Composio integration ecosystem.
Extends `integrations.composio.meta` — see the meta-skill for full protocol.

## When to Use
Use when automating `lemon_squeezy-automation` tasks via Rube MCP (Composio).
For generic Composio queries, use `integrations.composio.meta` directly.

## What If Fails
See `skills/integrations/composio/SKILL.md` (meta-skill) for full fallback protocol.
RULE: Never block workflow — always suggest manual alternative if automation fails.
