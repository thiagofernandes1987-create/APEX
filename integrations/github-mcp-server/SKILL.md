---
skill_id: integrations.github_mcp_server
name: "GitHub MCP Server -- Official GitHub Integration"
description: "Official GitHub MCP server. Provides tools for repos, PRs, issues, commits, branches, actions, code search, and more. Written in Go."
version: v00.33.0
status: ADOPTED
domain_path: integrations/github-mcp-server
anchors:
  - github
  - mcp_server
  - pull_request
  - issues
  - repositories
  - code_search
  - github_actions
  - commits
source_repo: github-mcp-server
risk: safe
languages: [go]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
executor: LLM_BEHAVIOR
---

# GitHub MCP Server

## Why This Matters for APEX

The GitHub MCP server enables APEX to interact with GitHub directly:
- Read/write code in repositories
- Create/review pull requests
- Manage issues and projects
- Search code across repos
- Trigger GitHub Actions

## Integration with ForgeSkills

When apex_superrepo.boot_enabled is true, ForgeSkills uses this MCP server
to pull SKILL.md files directly from the APEX GitHub repo.

## Available Tools

```
create_or_update_file  push_files  search_repositories
create_repository      fork_repository  create_branch
list_commits           get_file_contents  create_pull_request
create_issue           search_code  get_pull_request
list_pull_requests     merge_pull_request  create_review
```

## README

[![Go Report Card](https://goreportcard.com/badge/github.com/github/github-mcp-server)](https://goreportcard.com/report/github.com/github/github-mcp-server)

# GitHub MCP Server

The GitHub MCP Server connects AI tools directly to GitHub's platform. This gives AI agents, assistants, and chatbots the ability to read repositories and code files, manage issues and PRs, analyze code, and automate workflows. All through natural language interactions.

### Use Cases

- Repository Management: Browse and query code, search files, analyze commits, and understand project structure across any repository you have access to.
- Issue & PR Automation: Create, update, and manage issues and pull requests. Let AI help triage bugs, review code changes, and maintain project boards.
- CI/CD & Workflow Intelligence: Monitor GitHub Actions workflow runs, analyze build failures, manage releases, and get insights into your development pipeline.
- Code Analysis: Examine security findings, review Dependabot alerts, understand code patterns, and get comprehensive insights into your codebase.
- Team Collaboration: Access discussions, manage notifications, analyze team activity, and streamline processes for your team.

Built for developers who want to connect their AI tools to GitHub context and capabilities, from simple natural language queries to complex multi-step agent workflows.

---

## Remote GitHub MCP Server

[![Install in VS Code](https://img.shields.io/badge/VS_Code-Install_Server-0098FF?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=github&config=%7B%22type%22%3A%20%22http%22%2C%22url%22%3A%20%22https%3A%2F%2Fapi.githubcopilot.com%2Fmcp%2F%22%7D) [![Install in VS Code Insiders](https://img.shields.io/badge/VS_Code_Insiders-Install_Server-24bfa5?style=flat-square&logo=visualstudiocode&logoColor=white)](https://insiders.vscode.dev/redirect/mcp/install?name=github&config=%7B%22type%22%3A%20%22http%22%2C%22url%22%3A%20%22ht

## Diff History
- **v00.33.0**: Ingested from github-mcp-server-main