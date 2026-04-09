---
skill_id: engineering.architecture.architecture_patterns
name: "architecture-patterns"
description: "'Master proven backend architecture patterns including Clean Architecture, Hexagonal Architecture, and Domain-Driven Design to build maintainable, testable, and scalable systems.'"
version: v00.33.0
status: CANDIDATE
domain_path: engineering/architecture/architecture-patterns
anchors:
  - architecture
  - patterns
  - master
  - proven
  - backend
  - clean
  - hexagonal
  - domain
  - driven
  - design
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Architecture Patterns

Master proven backend architecture patterns including Clean Architecture, Hexagonal Architecture, and Domain-Driven Design to build maintainable, testable, and scalable systems.

## Use this skill when

- Designing new backend systems from scratch
- Refactoring monolithic applications for better maintainability
- Establishing architecture standards for your team
- Migrating from tightly coupled to loosely coupled architectures
- Implementing domain-driven design principles
- Creating testable and mockable codebases
- Planning microservices decomposition

## Do not use this skill when

- You only need small, localized refactors
- The system is primarily frontend with no backend architecture changes
- You need implementation details without architectural design

## Instructions

1. Clarify domain boundaries, constraints, and scalability targets.
2. Select an architecture pattern that fits the domain complexity.
3. Define module boundaries, interfaces, and dependency rules.
4. Provide migration steps and validation checks.
5. For workflows that must survive failures (payments, order fulfillment, multi-step processes), use durable execution at the infrastructure layer — frameworks like DBOS persist workflow state, providing crash recovery without adding architectural complexity.

Refer to `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Related Skills

Works well with: `event-sourcing-architect`, `saga-orchestration`, `workflow-automation`, `dbos-*`

## Resources

- `resources/implementation-playbook.md` for detailed patterns, checklists, and templates.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
