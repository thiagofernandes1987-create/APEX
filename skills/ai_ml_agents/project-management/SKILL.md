---
skill_id: ai_ml_agents.project_management
name: "pm-skills"
description: "6 project management agent skills and plugins for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. Senior PM, scrum master, Jira expert (JQL), Confluence expert, Atlassian admin, template creator. MC"
version: v00.33.0
status: CANDIDATE
domain_path: ai-ml/agents
anchors:
  - project
  - management
  - agent
  - skills
  - plugins
  - claude
source_repo: claude-skills-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Project Management Skills

6 production-ready project management skills with Atlassian MCP integration.

## Quick Start

### Claude Code
```
/read project-management/jira-expert/SKILL.md
```

### Codex CLI
```bash
npx agent-skills-cli add alirezarezvani/claude-skills/project-management
```

## Skills Overview

| Skill | Folder | Focus |
|-------|--------|-------|
| Senior PM | `senior-pm/` | Portfolio management, risk analysis, resource planning |
| Scrum Master | `scrum-master/` | Velocity forecasting, sprint health, retrospectives |
| Jira Expert | `jira-expert/` | JQL queries, workflows, automation, dashboards |
| Confluence Expert | `confluence-expert/` | Knowledge bases, page layouts, macros |
| Atlassian Admin | `atlassian-admin/` | User management, permissions, integrations |
| Atlassian Templates | `atlassian-templates/` | Blueprints, custom layouts, reusable content |

## Python Tools

6 scripts, all stdlib-only:

```bash
python3 senior-pm/scripts/project_health_dashboard.py --help
python3 scrum-master/scripts/velocity_analyzer.py --help
```

## Rules

- Load only the specific skill SKILL.md you need
- Use MCP tools for live Jira/Confluence operations when available

## Diff History
- **v00.33.0**: Ingested from claude-skills-main