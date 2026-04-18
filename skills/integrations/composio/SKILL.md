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
input_schema:
  - name: toolkit_name
    type: string
    description: "Name of the Composio toolkit to automate (e.g. github, slack, notion)"
    required: true
  - name: task_description
    type: string
    description: "Description of the task to perform via the toolkit"
    required: true
output_schema:
  - name: result
    type: object
    description: "Result returned by the Composio tool execution"
  - name: tool_used
    type: string
    description: "Name of the specific Composio tool that was called"
  - name: status
    type: string
    enum: [success, failure, partial]
    description: "Execution status"
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
