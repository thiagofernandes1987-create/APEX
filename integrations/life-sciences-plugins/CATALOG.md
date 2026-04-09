---
skill_id: integrations.life_sciences.plugin_catalog
name: "Life Sciences Plugin Catalog -- Genomics, Clinical, Chemistry"
description: "Scientific research connectors: PubMed, BioRxiv, ChEMBL (drug db), ClinicalTrials.gov, Open Targets (drug discovery), Synapse, Owkin AI biology, BioRender, 10x Genomics, Wiley Scholar Gateway."
version: v00.33.0
status: ADOPTED
domain_path: integrations/life-sciences-plugins
anchors:
  - life_sciences
  - genomics
  - drug_discovery
  - clinical_trials
  - bioinformatics
  - chembl
  - pubmed
source_repo: life-sciences-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Life Sciences Plugin Catalog

## MCP Servers

| Server | URL |
|--------|-----|
| pubmed | https://pubmed.mcp.claude.com/mcp |
| biorender | https://mcp.services.biorender.com/mcp |
| biorxiv | https://mcp.deepsense.ai/biorxiv/mcp |
| clinical-trials | https://mcp.deepsense.ai/clinical_trials/mcp |
| chembl | https://mcp.deepsense.ai/chembl/mcp |
| synapse | https://mcp.synapse.org/mcp |
| wiley-scholar | https://connector.scholargateway.ai/mcp |
| owkin | https://mcp.k.owkin.com/mcp |
| open-targets | https://mcp.platform.opentargets.org/mcp |

## Plugins

- **10x-genomics**: 10x Genomics Cloud MCP server for accessing analysis data and workflows
- **biorender**: BioRender MCP server for creating and accessing scientific illustrations
- **biorxiv**: Access to bioRxiv and medRxiv preprint data. The bioRxiv Connector gives Claude access to bioRxiv and medRxiv preprint s
- **chembl**: Access to the ChEMBL Database. The ChEMBL Connector gives Claude access to the ChEMBL Database, a manually curated resou
- **clinical-trials**: Access ClinicalTrials.gov data. The Clinical Trials Connector gives Claude access to ClinicalTrials.gov, the NIH/NLM reg
- **medidata**: Medidata's MCP provides tools for Platform Help and Predictive Site Ranking. Platform Help allows users to query Medidat
- **open-targets**: Drug target discovery and prioritisation platform. The Open Targets Platform is a comprehensive tool that supports syste
- **owkin**: Interact with AI agents built for biology. Owkin build AI agents for biology to accelerate drug discovery and de-risk cl
- **pubmed**: PubMed MCP server for searching biomedical literature and research articles
- **synapse**: Synapse.org MCP server by Sage Bionetworks for collaborative research data management
- **tooluniverse**: Democratizing AI scientists with ToolUniverse
- **wiley-scholar-gateway**: Scholar Gateway MCP server by Wiley for accessing academic research and publications

## Diff History
- **v00.33.0**: Ingested from life-sciences-main.zip