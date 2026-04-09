---
skill_id: integrations.claude_commands.catalog
name: "Claude Slash Commands Catalog — 21 Commands"
description: "All slash commands found in ingested repositories. These are user-invocable commands that trigger specific workflows in Claude Code."
version: v00.33.0
status: ADOPTED
domain_path: integrations/claude-commands
anchors:
  - slash_command
  - claude_command
  - user_invocable
  - workflow_trigger
  - automation
source_repo: multiple
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: minimal, llama: minimal}
apex_version: v00.33.0
---

# Claude Slash Commands Catalog

Total: **21 slash commands** across all ingested repos.

## Commands by Repo


### claude-agent-sdk-python

- `/commit` — ---
- `/generate-changelog` — ---

### claude-agent-sdk-typescript

- `/label-issue` — ---

### claude-code

- `/commit-push-pr` — ---
- `/dedupe` — ---
- `/triage-issue` — ---

### claude-code-action

- `/commit-and-pr` — Let's commit the changes. Run tests, typechecks, and format checks. Then commit,
- `/label-issue` — ---
- `/review-pr` — ---

### claude-code-security-review

- `/security-review` — ---

### claude-cookbooks

- `/add-registry` — ---
- `/link-review` — ---
- `/model-check` — ---
- `/notebook-review` — ---
- `/review-issue` — ---
- `/review-pr-ci` — ---
- `/review-pr` — ---
- `/budget-impact` — ---
- `/slash-command-test` — ---
- `/strategic-brief` — ---
- `/talent-scan` — ---


## Sub-Agents Found

The following sub-agents were found in `.claude/agents/` directories:

- **test-agent** (claude-agent-sdk-python): ---
- **code-quality-reviewer** (claude-code-action): ---
- **documentation-accuracy-reviewer** (claude-code-action): ---
- **performance-reviewer** (claude-code-action): ---
- **security-code-reviewer** (claude-code-action): ---
- **test-coverage-reviewer** (claude-code-action): ---
- **code-reviewer** (claude-cookbooks): ---
- **financial-analyst** (claude-cookbooks): ---
- **recruiter** (claude-cookbooks): ---


## How to Use in APEX

Slash commands are user-invocable skills. When a user calls `/commit`, `/review-pr`, etc.,
Claude Code executes the corresponding `.claude/commands/{name}.md` workflow.

In APEX, these map to `ForgeSkills` entries with `user_invocable: true`.

## Diff History
- **v00.33.0**: Ingested from .claude/commands/ directories across all repos
