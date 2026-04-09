---
skill_id: engineering_cloud_azure.azure_cloud_migrate
name: "azure-cloud-migrate"
description: "Assess and migrate cross-cloud workloads to Azure with migration reports and code conversion. Supports AWS Lambda→Functions and GCP Cloud Run→Container Apps. WHEN: migrate Lambda to Azure Functions, m"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/cloud/azure
anchors:
  - azure
  - cloud
  - migrate
  - assess
  - cross
  - workloads
source_repo: skills-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Azure Cloud Migrate

> This skill handles **assessment and code migration** of existing cloud workloads to Azure.

## Rules

1. Follow phases sequentially — do not skip
2. Generate assessment before any code migration
3. Load the scenario reference and follow its rules
4. Use `mcp_azure_mcp_get_bestpractices` and `mcp_azure_mcp_documentation` MCP tools
5. Use the latest supported runtime for the target service
6. Destructive actions require `ask_user` — [global-rules](references/services/functions/global-rules.md)

## Migration Scenarios

| Source | Target | Reference |
|--------|--------|-----------|
| AWS Lambda | Azure Functions | [lambda-to-functions.md](references/services/functions/lambda-to-functions.md) ([assessment](references/services/functions/assessment.md), [code-migration](references/services/functions/code-migration.md)) |
| GCP Cloud Run | Azure Container Apps | [cloudrun-to-container-apps.md](references/services/container-apps/cloudrun-to-container-apps.md) |

> No matching scenario? Use `mcp_azure_mcp_documentation` and `mcp_azure_mcp_get_bestpractices` tools.

## Output Directory

All output goes to `<source-folder>-azure/` at workspace root. Never modify the source directory.

## Steps

1. **Create** `<source-folder>-azure/` at workspace root
2. **Assess** — Analyze source, map services, generate report using scenario-specific assessment guide
3. **Migrate** — Convert code/config using scenario-specific migration guide
4. **Ask User** — "Migration complete. Test locally or deploy to Azure?"
5. **Hand off** to azure-prepare for infrastructure, testing, and deployment

Track progress in `migration-status.md` — see [workflow-details.md](references/workflow-details.md).

## Diff History
- **v00.33.0**: Ingested from skills-main