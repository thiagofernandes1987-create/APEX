---
skill_id: ai_ml.mcp.dotnet_backend_patterns
name: "dotnet-backend-patterns"
description: "'Master C#/.NET patterns for building production-grade APIs, MCP servers, and enterprise backends with modern best practices (2024/2025).'"
version: v00.33.0
status: CANDIDATE
domain_path: ai-ml/mcp/dotnet-backend-patterns
anchors:
  - dotnet
  - backend
  - patterns
  - master
  - building
  - production
  - grade
  - apis
  - servers
  - enterprise
source_repo: antigravity-awesome-skills
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# .NET Backend Development Patterns

Master C#/.NET patterns for building production-grade APIs, MCP servers, and enterprise backends with modern best practices (2024/2025).

## Use this skill when

- Developing new .NET Web APIs or MCP servers
- Reviewing C# code for quality and performance
- Designing service architectures with dependency injection
- Implementing caching strategies with Redis
- Writing unit and integration tests
- Optimizing database access with EF Core or Dapper
- Configuring applications with IOptions pattern
- Handling errors and implementing resilience patterns

## Do not use this skill when

- The project is not using .NET or C#
- You only need frontend or client guidance
- The task is unrelated to backend architecture

## Instructions

- Define architecture boundaries, modules, and layering.
- Apply DI, async patterns, and resilience strategies.
- Validate data access performance and caching.
- Add tests and observability for critical flows.
- If detailed patterns are required, open `resources/implementation-playbook.md`.

## Resources

- `resources/implementation-playbook.md` for detailed .NET patterns and examples.

## Diff History
- **v00.33.0**: Ingested from antigravity-awesome-skills community repo
