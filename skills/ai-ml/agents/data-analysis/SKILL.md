---
skill_id: ai_ml_agents.data_analysis
name: "Workspace Data Analyst"
description: "Analyze CSV files in the workspace and summarize insights."
version: v00.33.0
status: CANDIDATE
domain_path: ai-ml/agents
anchors:
  - data
  - analysis
  - analyze
  - files
  - workspace
  - summarize
source_repo: voltagent
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

When analyzing CSV data:

1. Load the file and inspect headers.
2. Summarize totals, averages, and outliers.
3. Provide a short insight summary and recommended next steps.

## Diff History
- **v00.33.0**: Ingested from voltagent