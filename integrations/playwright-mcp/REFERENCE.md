---
skill_id: integrations.playwright_mcp
name: "Playwright MCP -- Browser Automation"
description: "Reference documentation for Playwright MCP -- Browser Automation. Source: playwright-mcp-main"
version: v00.33.0
status: CANDIDATE
domain_path: integrations/playwright-mcp
anchors:
  - playwright
  - playwright_mcp
source_repo: playwright-mcp-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Playwright MCP -- Browser Automation

Source: `playwright-mcp-main` (83 files)

## README

## Playwright MCP

A Model Context Protocol (MCP) server that provides browser automation capabilities using [Playwright](https://playwright.dev). This server enables LLMs to interact with web pages through structured accessibility snapshots, bypassing the need for screenshots or visually-tuned models.

### Playwright MCP vs Playwright CLI

This package provides MCP interface into Playwright. If you are using a **coding agent**, you might benefit from using the [CLI+SKILLS](https://github.com/microsoft/playwright-cli) instead.

- **CLI**: Modern **coding agents** increasingly favor CLI–based workflows exposed as SKILLs over MCP because CLI invocations are more token-efficient: they avoid loading large tool schemas and verbose accessibility trees into the model context, allowing agents to act through concise, purpose-built commands. This makes CLI + SKILLs better suited for high-throughput coding agents that must balance browser automation with large codebases, tests, and reasoning within limited context windows.<br>**Learn more about [Playwright CLI with SKILLS](https://github.com/microsoft/playwright-cli)**.

- **MCP**: MCP remains relevant for specialized agentic loops that benefit from persistent state, rich introspection, and iterative reasoning over page structure, such as exploratory automation, self-healing tests, or long-running autonomous workflows where maintaining continuous browser context outweighs token cost concerns.

### Key Features

- **Fast and lightweight*

## Diff History
- **v00.33.0**: Ingested from playwright-mcp-main