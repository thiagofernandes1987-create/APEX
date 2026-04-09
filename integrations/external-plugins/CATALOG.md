---
skill_id: integrations.external_plugins.official_catalog
name: "Official External Plugins Catalog"
description: "All official Anthropic-verified external plugins for Claude. Includes Asana, Discord, GitHub, Notion, Salesforce, Slack, Stripe, Zoom, and more."
version: v00.33.0
status: ADOPTED
domain_path: integrations/external-plugins
anchors:
  - external_plugin
  - official_plugin
  - third_party_integration
  - marketplace
  - connector
source_repo: claude-plugins-official
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: minimal, gemini: minimal, llama: minimal}
apex_version: v00.33.0
---

# Official External Plugins Catalog

Total: **37 official plugins** from claude-plugins-official-main.

## Plugins

- **agent-sdk-dev**: Claude Agent SDK Development Plugin
- **asana**: Asana project management integration. Create and manage tasks, search projects, update assignments, 
- **claude-code-setup**: Analyze codebases and recommend tailored Claude Code automations such as hooks, skills, MCP servers,
- **claude-md-management**: Tools to maintain and improve CLAUDE.md files - audit quality, capture session learnings, and keep p
- **code-review**: Automated code review for pull requests using multiple specialized agents with confidence-based scor
- **code-simplifier**: Agent that simplifies and refines code for clarity, consistency, and maintainability while preservin
- **commit-commands**: Streamline your git workflow with simple commands for committing, pushing, and creating pull request
- **context7**: Upstash Context7 MCP server for up-to-date documentation lookup. Pull version-specific documentation
- **discord**: Discord channel for Claude Code — messaging bridge with built-in access control. Manage pairing, all
- **example-plugin**: A comprehensive example plugin demonstrating all Claude Code extension options including commands, a
- **explanatory-output-style**: Adds educational insights about implementation choices and codebase patterns (mimics the deprecated 
- **fakechat**: Localhost iMessage-style web chat for Claude Code — test surface with file upload and edits. No toke
- **feature-dev**: Comprehensive feature development workflow with specialized agents for codebase exploration, archite
- **firebase**: Google Firebase MCP integration. Manage Firestore databases, authentication, cloud functions, hostin
- **frontend-design**: Frontend design skill for UI/UX implementation
- **github**: Official GitHub MCP server for repository management. Create issues, manage pull requests, review co
- **gitlab**: GitLab DevOps platform integration. Manage repositories, merge requests, CI/CD pipelines, issues, an
- **greptile**: AI code review agent for GitHub and GitLab. View and resolve Greptile's PR review comments directly 
- **hookify**: Easily create hooks to prevent unwanted behaviors by analyzing conversation patterns
- **imessage**: iMessage channel for Claude Code — reads chat.db directly, sends via AppleScript. Built-in access co
- **laravel-boost**: Laravel development toolkit MCP server. Provides intelligent assistance for Laravel applications inc
- **learning-output-style**: Interactive learning mode that requests meaningful code contributions at decision points (mimics the
- **linear**: Linear issue tracking integration. Create issues, manage projects, update statuses, search across wo
- **math-olympiad**: Solve competition math (IMO, Putnam, USAMO) with adversarial verification that catches what self-ver
- **mcp-server-dev**: Skills for designing and building MCP servers that work seamlessly with Claude — guides you through 
- **playground**: Creates interactive HTML playgrounds — self-contained single-file explorers with visual controls, li
- **playwright**: Browser automation and end-to-end testing MCP server by Microsoft. Enables Claude to interact with w
- **plugin-dev**: Plugin development toolkit with skills for creating agents, commands, hooks, MCP integrations, and c
- **pr-review-toolkit**: Comprehensive PR review agents specializing in comments, tests, error handling, type design, code qu
- **ralph-loop**: Continuous self-referential AI loops for interactive iterative development, implementing the Ralph W
- **security-guidance**: Security reminder hook that warns about potential security issues when editing files, including comm
- **serena**: Semantic code analysis MCP server providing intelligent code understanding, refactoring suggestions,
- **skill-creator**: Create new skills, improve existing skills, and measure skill performance. Use when users want to cr
- **slack**: Slack workspace integration. Search messages, access channels, read threads, and stay connected with
- **supabase**: Supabase MCP integration for database operations, authentication, storage, and real-time subscriptio
- **telegram**: Telegram channel for Claude Code — messaging bridge with built-in access control. Manage pairing, al
- **terraform**: The Terraform MCP Server provides seamless integration with Terraform ecosystem, enabling advanced a

## Diff History
- **v00.33.0**: Ingested from claude-plugins-official-main