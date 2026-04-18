---
skill_id: knowledge_management.wiki.wiki_changelog
name: "wiki-changelog"
description: "'Generate structured changelogs from git history. Use when user asks \'what changed recently\', \'generate a changelog\', \'summarize commits\' or user wants to understand recent development activity."
version: v00.33.0
status: CANDIDATE
domain_path: knowledge-management/wiki/wiki-changelog
anchors:
  - wiki
  - changelog
  - generate
  - structured
  - changelogs
  - history
  - user
  - asks
  - changed
  - recently
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
executor: LLM_BEHAVIOR
security: {level: standard, pii: false, approval_required: false}
---

# Wiki Changelog

Generate structured changelogs from git history.

## When to Use
- User asks "what changed recently", "generate a changelog", "summarize commits"
- User wants to understand recent development activity

## Procedure

1. Examine git log (commits, dates, authors, messages)
2. Group by time period: daily (last 7 days), weekly (older)
3. Classify each commit: Features (🆕), Fixes (🐛), Refactoring (🔄), Docs (📝), Config (🔧), Dependencies (📦), Breaking (⚠️)
4. Generate concise user-facing descriptions using project terminology

## Constraints

- Focus on user-facing changes
- Merge related commits into coherent descriptions
- Use project terminology from README
- Highlight breaking changes prominently with migration notes

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
