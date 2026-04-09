---
skill_id: ai_ml_agents.finance
name: "finance-skills"
description: "Financial analyst agent skill and plugin for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. Ratio analysis, DCF valuation, budget variance, rolling forecasts. 4 Python tools (stdlib-only)."
version: v00.33.0
status: CANDIDATE
domain_path: ai-ml/agents
anchors:
  - finance
  - financial
  - analyst
  - agent
  - skill
  - plugin
source_repo: claude-skills-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Finance Skills

Production-ready financial analysis skill for strategic decision-making.

## Quick Start

### Claude Code
```
/read finance/financial-analyst/SKILL.md
```

### Codex CLI
```bash
npx agent-skills-cli add alirezarezvani/claude-skills/finance
```

## Skills Overview

| Skill | Folder | Focus |
|-------|--------|-------|
| Financial Analyst | `financial-analyst/` | Ratio analysis, DCF, budget variance, forecasting |

## Python Tools

4 scripts, all stdlib-only:

```bash
python3 financial-analyst/scripts/ratio_calculator.py --help
python3 financial-analyst/scripts/dcf_valuation.py --help
python3 financial-analyst/scripts/budget_variance_analyzer.py --help
python3 financial-analyst/scripts/forecast_builder.py --help
```

## Rules

- Load only the specific skill SKILL.md you need
- Always validate financial outputs against source data

## Diff History
- **v00.33.0**: Ingested from claude-skills-main