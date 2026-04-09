---
skill_id: community.general.changelog_automation
name: "changelog-automation"
description: "'Automate changelog generation from commits, PRs, and releases following Keep a Changelog format. Use when setting up release workflows, generating release notes, or standardizing commit conventions.'"
version: v00.33.0
status: CANDIDATE
domain_path: community/general/changelog-automation
anchors:
  - changelog
  - automation
  - automate
  - generation
  - commits
  - releases
  - following
  - keep
  - format
  - setting
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Changelog Automation

Patterns and tools for automating changelog generation, release notes, and version management following industry standards.

## Use this skill when

- Setting up automated changelog generation
- Implementing conventional commits
- Creating release note workflows
- Standardizing commit message formats
- Managing semantic versioning

## Do not use this skill when

- The project has no release process or versioning
- You only need a one-time manual release note
- Commit history is unavailable or unreliable

## Instructions

- Select a changelog format and versioning strategy.
- Enforce commit conventions or labeling rules.
- Configure tooling to generate and publish notes.
- Review output for accuracy, completeness, and wording.
- If detailed examples are required, open `resources/implementation-playbook.md`.

## Safety

- Avoid exposing secrets or internal-only details in release notes.

## Resources

- `resources/implementation-playbook.md` for detailed patterns, templates, and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
