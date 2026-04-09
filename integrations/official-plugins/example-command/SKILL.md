---
skill_id: integrations.official_plugins.example_command
name: "example-command"
description: "An example user-invoked skill that demonstrates frontmatter options and the skills/<name>/SKILL.md layout"
version: v00.33.0
status: ADOPTED
domain_path: integrations/official-plugins/example-command
anchors:
  - example
  - command
  - example
  - user
  - invoked
  - skill
  - that
  - demonstrates
source_repo: claude-plugins-official
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: minimal, gemini: minimal, llama: minimal}
apex_version: v00.33.0
---

# Example Command (Skill Format)

This demonstrates the `skills/<name>/SKILL.md` layout for user-invoked slash commands. It is functionally identical to the legacy `commands/example-command.md` format — both are loaded the same way; only the file layout differs.

## Arguments

The user invoked this with: $ARGUMENTS

## Instructions

When this skill is invoked:

1. Parse the arguments provided by the user
2. Perform the requested action using allowed tools
3. Report results back to the user

## Frontmatter Options Reference

Skills in this layout support these frontmatter fields:

- **name**: Skill identifier (matches directory name)
- **description**: Short description shown in /help
- **argument-hint**: Hints for command arguments shown to user
- **allowed-tools**: Pre-approved tools for this skill (reduces permission prompts)
- **model**: Override the model (e.g., "haiku", "sonnet", "opus")

## Example Usage

```
/example-command my-argument
/example-command arg1 arg2
```

## Diff History
- **v00.33.0**: Ingested from claude-plugins-official-main