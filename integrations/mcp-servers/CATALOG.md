---
skill_id: integrations.mcp_servers.catalog
name: "MCP Servers Catalog — 166 Servers from 44 Configs"
description: "Complete catalog of all MCP servers found in ingested repositories. Each entry includes server name, command, and source repo."
version: v00.33.0
status: ADOPTED
domain_path: integrations/mcp-servers
anchors:
  - mcp
  - model_context_protocol
  - mcp_server
  - tool_integration
  - external_tools
  - connectors
source_repo: multiple
risk: safe
languages: [yaml]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# MCP Servers Catalog

Total: **166 MCP servers** from 44 configuration files across all ingested repos.

## When to Use

When the APEX pipeline needs to call external tools (GitHub, Slack, filesystem, memory, etc.),
consult this catalog to find the correct MCP server name and command.

## Servers by Source


### claude-code-action

- **test-server** — `bun`

### claude-plugins-official

- **discord** — `bun`
- **fakechat** — `bun`
- **imessage** — `bun`
- **telegram** — `bun`

### financial-services-plugins

- **daloopa** — ``
- **morningstar** — ``
- **sp-global** — ``
- **factset** — ``
- **moodys** — ``
- **mtnewswire** — ``
- **aiera** — ``
- **lseg** — ``
- **pitchbook** — ``
- **chronograph** — ``
- **egnyte** — ``
- **lseg** — ``
- **spglobal** — ``

### knowledge-work-plugins

- **pubmed** — ``
- **biorender** — ``
- **biorxiv** — ``
- **c-trials** — ``
- **chembl** — ``
- **synapse** — ``
- **wiley** — ``
- **owkin** — ``
- **ot** — ``
- **benchling** — ``
- **slack** — ``
- **intercom** — ``
- **hubspot** — ``
- **guru** — ``
- **atlassian** — ``
- **notion** — ``
- **ms365** — ``
- **google-calendar** — ``
- **gmail** — ``
- **snowflake** — ``
- **databricks** — ``
- **bigquery** — ``
- **hex** — ``
- **amplitude** — ``
- **amplitude-eu** — ``
- **atlassian** — ``
- **definite** — ``
- **slack** — ``
- **figma** — ``
- **linear** — ``
- **asana** — ``
- **atlassian** — ``
- **notion** — ``
- **intercom** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **linear** — ``
- **asana** — ``
- **atlassian** — ``
- **notion** — ``
- **github** — ``
- **pagerduty** — ``
- **datadog** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **notion** — ``
- **guru** — ``
- **atlassian** — ``
- **asana** — ``
- **ms365** — ``
- **google-calendar** — ``
- **gmail** — ``
- **snowflake** — ``
- **databricks** — ``
- **bigquery** — ``
- **slack** — ``
- **ms365** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **google-calendar** — ``
- **gmail** — ``
- **notion** — ``
- **atlassian** — ``
- **ms365** — ``
- **slack** — ``
- **box** — ``
- **egnyte** — ``
- **atlassian** — ``
- **ms365** — ``
- **docusign** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **canva** — ``
- **figma** — ``
- **hubspot** — ``
- **amplitude** — ``
- **amplitude-eu** — ``
- **notion** — ``
- **ahrefs** — ``
- **similarweb** — ``
- **klaviyo** — ``
- **supermetrics** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **google-calendar** — ``
- **gmail** — ``
- **notion** — ``
- **atlassian** — ``
- **asana** — ``
- **servicenow** — ``
- **ms365** — ``
- **apollo** — ``
- **notion** — ``
- **atlassian** — ``
- **box** — ``
- **figma** — ``
- **gong** — ``
- **microsoft-365** — ``
- **granola** — ``
- **common-room** — ``
- **slack** — ``
- **pdf** — `npx`
- **slack** — ``
- **linear** — ``
- **asana** — ``
- **monday** — ``
- **clickup** — ``
- **atlassian** — ``
- **notion** — ``
- **figma** — ``
- **amplitude** — ``
- **amplitude-eu** — ``
- **pendo** — ``
- **intercom** — ``
- **fireflies** — ``
- **google-calendar** — ``
- **gmail** — ``
- **similarweb** — ``
- **slack** — ``
- **notion** — ``
- **asana** — ``
- **linear** — ``
- **atlassian** — ``
- **ms365** — ``
- **monday** — ``
- **clickup** — ``
- **google-calendar** — ``
- **gmail** — ``
- **slack** — ``
- **hubspot** — ``
- **close** — ``
- **clay** — ``
- **zoominfo** — ``
- **notion** — ``
- **atlassian** — ``
- **fireflies** — ``
- **ms365** — ``
- **apollo** — ``
- **outreach** — ``
- **google-calendar** — ``
- **gmail** — ``
- **similarweb** — ``

### servers

- **mcp-docs** — ``


## Integration with APEX

```yaml
# In APEX kernel.defaults, MCP servers are configured via:
mcp_bridge:
  servers:
    memory: {command: "npx @modelcontextprotocol/server-memory"}
    filesystem: {command: "npx @modelcontextprotocol/server-filesystem"}
    github: {command: "npx @modelcontextprotocol/server-github"}
    sequentialthinking: {command: "npx @modelcontextprotocol/sequentialthinking"}
```

## Diff History
- **v00.33.0**: Ingested from 44 .mcp.json files across all repos
