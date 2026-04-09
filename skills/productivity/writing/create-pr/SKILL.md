---
skill_id: productivity.writing.create_pr
name: "create-pr"
description: "Alias for sentry-skills:pr-writer. Use when users explicitly ask for 'create-pr' or reference the legacy skill name. Redirects to the canonical PR writing workflow."
version: v00.33.0
status: CANDIDATE
domain_path: productivity/writing/create-pr
anchors:
  - create
  - alias
  - sentry
  - skills
  - writer
  - users
  - explicitly
  - reference
  - legacy
  - skill
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Alias: create-pr

This skill name is kept for compatibility.

## When to Use

- The user explicitly asks for `create-pr` or refers to the legacy skill name.
- You need to redirect pull request creation work to the canonical `sentry-skills:pr-writer` workflow.
- The task is specifically about writing or updating a pull request rather than general git operations.

Use `sentry-skills:pr-writer` as the canonical skill for creating and editing pull requests.

If invoked via `create-pr`, run the same workflow and conventions documented in `sentry-skills:pr-writer`.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
