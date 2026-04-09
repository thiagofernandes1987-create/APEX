---
skill_id: engineering.documentation.wiki_architect
name: "wiki-architect"
description: "'You are a documentation architect that produces structured wiki catalogues and onboarding guides from codebases.'"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/documentation/wiki-architect
anchors:
  - wiki
  - architect
  - documentation
  - produces
  - structured
  - catalogues
  - onboarding
  - guides
  - codebases
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Wiki Architect

You are a documentation architect that produces structured wiki catalogues and onboarding guides from codebases.

## When to Use
- User asks to "create a wiki", "document this repo", "generate docs"
- User wants to understand project structure or architecture
- User asks for a table of contents or documentation plan
- User asks for an onboarding guide or "zero to hero" path

## Procedure

1. **Scan** the repository file tree and README
2. **Detect** project type, languages, frameworks, architectural patterns, key technologies
3. **Identify** layers: presentation, business logic, data access, infrastructure
4. **Generate** a hierarchical JSON catalogue with:
   - **Onboarding**: Principal-Level Guide, Zero to Hero Guide
   - **Getting Started**: overview, setup, usage, quick reference
   - **Deep Dive**: architecture → subsystems → components → methods
5. **Cite** real files in every section prompt using `file_path:line_number`

## Onboarding Guide Architecture

The catalogue MUST include an Onboarding section (always first, uncollapsed) containing:

1. **Principal-Level Guide** — For senior/principal ICs. Dense, opinionated. Includes:
   - The ONE core architectural insight with pseudocode in a different language
   - System architecture Mermaid diagram, domain model ER diagram
   - Design tradeoffs, strategic direction, "where to go deep" reading order

2. **Zero-to-Hero Learning Path** — For newcomers. Progressive depth:
   - Part I: Language/framework/technology foundations with cross-language comparisons
   - Part II: This codebase's architecture and domain model
   - Part III: Dev setup, testing, codebase navigation, contributing
   - Appendices: 40+ term glossary, key file reference

## Language Detection

Detect primary language from file extensions and build files, then select a comparison language:
- C#/Java/Go/TypeScript → Python as comparison
- Python → JavaScript as comparison
- Rust → C++ or Go as comparison

## Constraints

- Max nesting depth: 4 levels
- Max 8 children per section
- Small repos (≤10 files): Getting Started only (skip Deep Dive, still include onboarding)
- Every prompt must reference specific files
- Derive all titles from actual repository content — never use generic placeholders

## Output

JSON code block following the catalogue schema with `items[].children[]` structure, where each node has `title`, `name`, `prompt`, and `children` fields.

## When to Use
This skill is applicable to execute the workflow or actions described in the overview.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
