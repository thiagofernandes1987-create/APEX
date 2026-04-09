---
skill_id: integrations.financial_services.plugin_catalog
name: "Financial Services Plugin Catalog -- Bloomberg/Reuters/Moody's/S&P/FactSet"
description: "Professional financial data connectors: Morningstar, S&P Global (Kensho), FactSet, Moody's, LSEG/Reuters, PitchBook, Daloopa, Aiera, Chronograph. Plus equity research, IB, PE, wealth management skills."
version: v00.33.0
status: ADOPTED
domain_path: integrations/financial-services
anchors:
  - finance
  - equity_research
  - investment_banking
  - financial_data
  - morningstar
  - sp_global
  - factset
  - moodys
  - lseg
  - pitchbook
source_repo: financial-services-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: minimal, gemini: minimal, llama: minimal}
apex_version: v00.33.0
---

# Financial Services Plugin Catalog

## Premium Financial Data MCP Servers

| Provider | URL | Data |
|----------|-----|------|
| daloopa | https://mcp.daloopa.com/server/mcp | AI-powered financial model updates |
| morningstar | https://mcp.morningstar.com/mcp | Investment research, ratings, fund data |
| sp-global | https://kfinance.kensho.com/integrations/mcp | S&P Global financial data & analytics |
| factset | https://mcp.factset.com/mcp | Financial data, analytics, portfolio management |
| moodys | https://api.moodys.com/genai-ready-data/m1/mcp | Moody's credit ratings and risk data |
| lseg | https://api.analytics.lseg.com/lfa/mcp | LSEG (Reuters) financial analytics |
| pitchbook | https://premium.mcp.pitchbook.com/mcp | Private market data, VC/PE intelligence |
| mtnewswire | https://vast-mcp.blueskyapi.com/mtnewswires | Market news wire (PR Newswire) |
| aiera | https://mcp-pub.aiera.com | AI earnings intelligence, earnings calls |
| chronograph | https://ai.chronograph.pe/mcp | Private equity portfolio analytics |

## Workflow Plugins

- **claude-in-office** (0 tools): Provision direct cloud access (Vertex AI, Bedrock, or LLM gateway) for the Claude Office add-in. Generates the customized add-in manifest, walks throu
- **equity-research** (0 tools): Equity research tools: earnings analysis, initiating coverage reports, and research workflows
- **financial-analysis** (0 tools): Core financial modeling and analysis tools: DCF, comps, LBO, 3-statement models, competitive analysis, and deck QC
- **investment-banking** (0 tools): Investment banking productivity tools: client and market insights, deck creation, financial analysis, and transaction management
- **lseg** (0 tools): Price bonds, analyze yield curves, evaluate FX carry trades, value options, and build macro dashboards using LSEG financial data and analytics.
- **sp-global** (0 tools): S&P Global - Financial data and analytics skills including company tearsheets, earnings previews, and transaction summaries
- **private-equity** (0 tools): Private equity deal sourcing and workflow tools: company discovery, CRM integration, and founder outreach
- **wealth-management** (0 tools): Wealth management and financial advisory tools: client reviews, financial planning, portfolio analysis, and client reporting

## Diff History
- **v00.33.0**: Ingested from financial-services-plugins-main.zip