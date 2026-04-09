---
skill_id: ai_ml.agents.agent_manager_skill
name: "agent-manager-skill"
description: "'Manage multiple local CLI agents via tmux sessions (start/stop/monitor/assign) with cron-friendly scheduling.'"
version: v00.33.0
status: CANDIDATE
domain_path: ai-ml/agents/agent-manager-skill
anchors:
  - agent
  - manager
  - skill
  - manage
  - multiple
  - local
  - agents
  - tmux
  - sessions
  - start
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Agent Manager Skill

## When to Use
Use this skill when you need to:

- run multiple local CLI agents in parallel (separate tmux sessions)
- start/stop agents and tail their logs
- assign tasks to agents and monitor output
- schedule recurring agent work (cron)

## Prerequisites

Install `agent-manager-skill` in your workspace:

```bash
git clone https://github.com/fractalmind-ai/agent-manager-skill.git
```

## Common commands

```bash
python3 agent-manager/scripts/main.py doctor
python3 agent-manager/scripts/main.py list
python3 agent-manager/scripts/main.py start EMP_0001
python3 agent-manager/scripts/main.py monitor EMP_0001 --follow
python3 agent-manager/scripts/main.py assign EMP_0002 <<'EOF'
Follow teams/fractalmind-ai-maintenance.md Workflow
EOF
```

## Notes

- Requires `tmux` and `python3`.
- Agents are configured under an `agents/` directory (see the repo for examples).

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
