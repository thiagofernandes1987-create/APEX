---
skill_id: integrations.mcp_reference_servers
name: "MCP Reference Servers -- Official Implementations"
description: "Official reference implementations of MCP servers. Includes: memory, filesystem, github, sequentialthinking, brave-search, fetch, sqlite, and more."
version: v00.33.0
status: ADOPTED
domain_path: integrations/mcp-reference-servers
anchors:
  - mcp_server
  - reference_implementation
  - memory_server
  - filesystem_server
  - github_server
  - sequential_thinking
  - brave_search
  - sqlite
source_repo: servers-main
risk: safe
languages: [python, typescript]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# MCP Reference Servers

## Why This Matters for APEX

These are the **canonical MCP server implementations** that APEX's MCPBridge (OPP-96)
connects to. The APEX kernel.defaults mcp_bridge config maps these servers.

## Key Servers

| Server | Purpose | APEX Usage |
|--------|---------|-----------|
| memory | Persistent KG via JSON | APEX Knowledge Graph (OPP-97) |
| filesystem | File I/O | ForgeSkills file access |
| github | GitHub API | Pull skills from super-repo |
| sequentialthinking | Step-by-step reasoning | RESEARCH/SCIENTIFIC modes |
| fetch | HTTP requests | External API calls |
| brave-search | Web search | researcher agent |
| sqlite | Local database | skill_registry persistence |

## Source README

# Model Context Protocol servers

This repository is a collection of *reference implementations* for the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP), as well as references to community-built servers and additional resources.

> [!IMPORTANT]
> If you are looking for a list of MCP servers, you can browse published servers on [the MCP Registry](https://registry.modelcontextprotocol.io/). The repository served by this README is dedicated to housing just the small number of reference servers maintained by the MCP steering group.

> [!WARNING]
> The servers in this repository are intended as **reference implementations** to demonstrate MCP features and SDK usage. They are meant to serve as educational examples for developers building their own MCP servers, not as production-ready solutions. Developers should evaluate their own security requirements and implement appropriate safeguards based on their specific threat model and use case.

The servers in this repository showcase the versatility and extensibility of MCP, demonstrating how it can be used to give Large Language Models (LLMs) secure, controlled access to tools and data sources.
Typically, each MCP server is implemented with an MCP SDK:

- [C# MCP SDK](https://github.com/modelcontextprotocol/csharp-sdk)
- [Go MCP SDK](https://github.com/modelcontextprotocol/go-sdk)
- [Java MCP SDK](https://github.com/modelcontextprotocol/java-sdk)
- [Kotlin MCP SDK](https://github.com/modelcontextprotocol/kotlin-sdk)
- [PHP MCP SDK](https://github.com/modelcontextprotocol/php-sdk)
- [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Ruby MCP SDK](https://github.com/modelcontextprotocol/ruby-sdk)
- [Rust MCP SDK](https://github.com/modelcontextprotocol/rust-sdk)
- [Swift MCP SDK](https://github.com/modelcontextprotocol/swift-sdk)
- [TypeScript MCP SDK](https://github.com/modelcontextprotocol/typescript-sdk)

## 🌟 Reference Servers

These servers aim to demonstrate MCP features and the offic

## Diff History
- **v00.33.0**: Ingested from servers-main