---
skill_id: engineering.testing.dbt_transformation_patterns
name: "dbt-transformation-patterns"
description: "'Production-ready patterns for dbt (data build tool) including model organization, testing strategies, documentation, and incremental processing.'"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/testing/dbt-transformation-patterns
anchors:
  - transformation
  - patterns
  - production
  - ready
  - data
  - build
  - tool
  - model
  - organization
  - testing
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# dbt Transformation Patterns

Production-ready patterns for dbt (data build tool) including model organization, testing strategies, documentation, and incremental processing.

## Use this skill when

- Building data transformation pipelines with dbt
- Organizing models into staging, intermediate, and marts layers
- Implementing data quality tests and documentation
- Creating incremental models for large datasets
- Setting up dbt project structure and conventions

## Do not use this skill when

- The project is not using dbt or a warehouse-backed workflow
- You only need ad-hoc SQL queries
- There is no access to source data or schemas

## Instructions

- Define model layers, naming, and ownership.
- Implement tests, documentation, and freshness checks.
- Choose materializations and incremental strategies.
- Optimize runs with selectors and CI workflows.
- If detailed patterns are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed dbt patterns and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
