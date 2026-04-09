---
skill_id: integrations.mcp_servers.master_catalog
name: "Master MCP Server Catalog -- All Integrated Services"
description: "Complete catalog of all MCP servers available to APEX across all domains: healthcare, finance, marketing, engineering, productivity, life sciences, sales, data.",
version: v00.33.0
status: ADOPTED
domain_path: integrations/mcp-servers
anchors:
  - mcp_server
  - integration
  - connector
  - external_service
  - api
source_repo: multiple
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Master MCP Server Catalog

Total: **65 unique MCP servers** across all domains.

| Server | URL | Domain |
|--------|-----|--------|
| ahrefs | https://api.ahrefs.com/mcp/mcp | marketing |
| aiera | https://mcp-pub.aiera.com | finance |
| amplitude | https://mcp.amplitude.com/mcp | data |
| amplitude-eu | https://mcp.eu.amplitude.com/mcp | data |
| apollo | https://mcp.apollo.io/mcp | partner-built |
| apollo | https://api.apollo.io/mcp | sales |
| asana | https://mcp.asana.com/v2/mcp | design |
| atlassian | https://mcp.atlassian.com/v1/mcp | customer-support |
| bigquery | https://bigquery.googleapis.com/mcp | data |
| biorender | https://mcp.services.biorender.com/mcp | general |
| biorxiv | https://mcp.deepsense.ai/biorxiv/mcp | general |
| box | https://mcp.box.com | legal |
| canva | https://mcp.canva.com/mcp | marketing |
| chembl | https://mcp.deepsense.ai/chembl/mcp | general |
| chronograph | https://ai.chronograph.pe/mcp | finance |
| clay | https://api.clay.com/v3/mcp | sales |
| clickup | https://mcp.clickup.com/mcp | product-management |
| clinical-trials | https://mcp.deepsense.ai/clinical_trials/mcp | general |
| close | https://mcp.close.com/mcp | sales |
| cms-coverage | https://mcp.deepsense.ai/cms_coverage/mcp | general |
| common-room | https://mcp.commonroom.io/mcp | partner-built |
| daloopa | https://mcp.daloopa.com/server/mcp | finance |
| datadog | https://mcp.datadoghq.com/mcp | engineering |
| definite | https://api.definite.app/v3/mcp/http | data |
| docusign | https://mcp.docusign.com/mcp | legal |
| egnyte | https://mcp-server.egnyte.com/mcp | legal |
| factset | https://mcp.factset.com/mcp | finance |
| figma | https://mcp.figma.com/mcp | design |
| fireflies | https://api.fireflies.ai/mcp | product-management |
| github | https://api.github.com/mcp | engineering |
| gmail | https://gmail.mcp.claude.com/mcp | customer-support |
| gong | https://mcp.gong.io/mcp | partner-built |
| google-calendar | https://gcal.mcp.claude.com/mcp | customer-support |
| granola | https://mcp.granola.ai/mcp | partner-built |
| guru | https://mcp.api.getguru.com/mcp | customer-support |
| hex | https://app.hex.tech/mcp | data |
| hubspot | https://mcp.hubspot.com/anthropic | customer-support |
| icd10-codes | https://mcp.deepsense.ai/icd10/mcp | general |
| intercom | https://mcp.intercom.com/mcp | customer-support |
| klaviyo | https://mcp.klaviyo.com/mcp | marketing |
| linear | https://mcp.linear.app/mcp | design |
| lseg | https://api.analytics.lseg.com/lfa/mcp/server-cl | finance |
| monday | https://mcp.monday.com/mcp | product-management |
| moodys | https://api.moodys.com/genai-ready-data/m1/mcp | finance |
| morningstar | https://mcp.morningstar.com/mcp | finance |
| ms365 | https://microsoft365.mcp.claude.com/mcp | customer-support |
| mtnewswire | https://vast-mcp.blueskyapi.com/mtnewswires | finance |
| notion | https://mcp.notion.com/mcp | customer-support |
| npi-registry | https://mcp.deepsense.ai/npi_registry/mcp | general |
| open-targets | https://mcp.platform.opentargets.org/mcp | general |
| outreach | https://mcp.outreach.io/mcp | sales |
| owkin | https://mcp.k.owkin.com/mcp | general |
| pagerduty | https://mcp.pagerduty.com/mcp | engineering |
| pendo | https://app.pendo.io/mcp/v0/shttp | product-management |
| pitchbook | https://premium.mcp.pitchbook.com/mcp | finance |
| pubmed | https://pubmed.mcp.claude.com/mcp | general |
| servicenow | https://mcp.servicenow.com/mcp | operations |
| similarweb | https://mcp.similarweb.com | marketing |
| similarweb | https://mcp.similarweb.com/mcp | product-management |
| slack | https://mcp.slack.com/mcp | customer-support |
| sp-global | https://kfinance.kensho.com/integrations/mcp | finance |
| supermetrics | https://mcp.supermetrics.com/mcp | marketing |
| synapse | https://mcp.synapse.org/mcp | general |
| wiley-scholar | https://connector.scholargateway.ai/mcp | general |
| zoominfo | https://mcp.zoominfo.com/mcp | sales |

## Diff History
- **v00.33.0**: Consolidated from healthcare, life-sciences, knowledge-work, financial-services ZIPs