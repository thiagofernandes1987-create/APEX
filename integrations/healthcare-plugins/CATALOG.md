---
skill_id: integrations.healthcare.plugin_catalog
name: "Healthcare Plugin Catalog -- CMS, NPI, PubMed, ICD-10"
description: "Official Anthropic healthcare connectors: CMS Coverage (Medicare), NPI Registry, PubMed biomedical literature, ICD-10 diagnostic codes."
version: v00.33.0
status: ADOPTED
domain_path: integrations/healthcare-plugins
anchors:
  - healthcare
  - cms_coverage
  - npi_registry
  - pubmed
  - icd10
  - medicare
  - clinical
source_repo: healthcare-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Healthcare Plugin Catalog

## MCP Servers

| Server | URL | Purpose |
|--------|-----|---------|
| cms-coverage | https://mcp.deepsense.ai/cms_coverage/mcp | CMS Medicare Part B coverage policies database |
| npi-registry | https://mcp.deepsense.ai/npi_registry/mcp | US National Provider Identifier (NPI) Registry |
| pubmed | https://pubmed.mcp.claude.com/mcp | PubMed biomedical literature search |
| icd10-codes | https://mcp.deepsense.ai/icd10/mcp | ICD-10-CM diagnostic codes database |

## Plugins

- **cms-coverage** (0 tools): The CMS Coverage Connector gives Claude access to Medicare Part B coverage policies from the CMS Coverage Database, incl
- **icd10-codes** (0 tools): The ICD-10 Codes Connector gives Claude access to the complete ICD-10-CM (diagnosis) and ICD-10-PCS (procedure) code set
- **npi-registry** (0 tools): The NPI Registry Connector gives Claude access to the US National Provider Identifier (NPI) Registry, containing informa
- **pubmed** (0 tools): Provides access to PubMed's biomedical citations and PubMed Central's full-text archive. Search articles, retrieve metad

## Diff History
- **v00.33.0**: Ingested from healthcare-main.zip