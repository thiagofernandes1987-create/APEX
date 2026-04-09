---
skill_id: algorithms.claude_agent_sdk.python
name: "Claude Agent SDK -- Python"
description: "Official Anthropic SDK for building multi-agent systems. Provides agent loops, tool use, subagent spawning, session management."
version: v00.33.0
status: ADOPTED
domain_path: algorithms/claude-agent-sdk
anchors:
  - agent_sdk
  - multi_agent
  - subagent
  - tool_use
  - agent_loop
  - session
  - anthropic_sdk
source_repo: claude-agent-sdk-python
risk: safe
languages: [python]
llm_compat: {claude: full, gpt4o: minimal, gemini: minimal, llama: minimal}
apex_version: v00.33.0
---

# Claude Agent SDK (Python)

## Why This Skill Exists

Official Anthropic library for production multi-agent systems.

## Installation

```bash
pip install claude-agent-sdk
```

## Core Usage Pattern

```python
# WHY: Agent SDK handles loop, tool dispatch, response management
# WHEN: Building multi-step autonomous agents with tool use
# HOW: Create agent, define tools, run with prompt
# WHAT_IF_FAILS: Check API key, tool schema, context window

import anthropic
from claude_agent_sdk import Agent, tool

@tool
def search(query: str) -> str:
    """Search for information."""
    return f"Results for: {query}"

agent = Agent(model="claude-opus-4-6", tools=[search])
result = agent.run("Research APEX framework")
print(result.final_response)
```

## Source README

# Claude Agent SDK for Python

Python SDK for Claude Agent. See the [Claude Agent SDK documentation](https://platform.claude.com/docs/en/agent-sdk/python) for more information.

## Installation

```bash
pip install claude-agent-sdk
```

**Prerequisites:**

- Python 3.10+

**Note:** The Claude Code CLI is automatically bundled with the package - no separate installation required! The SDK will use the bundled CLI by default. If you prefer to use a system-wide installation or a specific version, you can:

- Install Claude Code separately: `curl -fsSL https://claude.ai/install.sh | bash`
- Specify a custom path: `ClaudeAgentOptions(cli_path="/path/to/claude")`

## Quick Start

```python
import anyio
from claude_agent_sdk import query

async def main():
    async for message in query(prompt="What is 2 + 2?"):
        print(message)

anyio.run(main)
```

## Basic Usage: query()

`query()` is an async function for querying Claude Code. It returns an `AsyncIterator` of response messages. See [src/claude_agent_sdk/query.py](src/claude_agent_sdk/query.py).

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, TextBlock

# Simple query
async for message in query(prompt="Hello Claude"):
    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text)

# With options
options = ClaudeAgentOptions(
    system_prompt="You are a helpful assistant",
    max_turns=1
)

async for message in query(prompt="Tell me a joke", options=options):
    print(message)
```

### Using Tools

By default, Claude has access to the full [Claude Code toolset](https://code.claude.com/docs/en/settings#tools-available-to-claude) (Read, Write, Edit, Bash, and others). `allowed_tools` is a permission allowlist: listed tools are auto-approved, and unlisted tools fall through to `permission_mode` and `can_use_tool` for a decision. It does not remove tools from Claude's toolset. To block specific tools, use `disallowed_tools`. See the [permissions guide](https://platform.claude.com/docs/en/agent-sdk/permissions) for the full evaluation order.

```python
options = ClaudeAgentOptions(
    allowed_tools=["Read", "Write", "Bash"],  # auto-approve these tools
    permission_mode='acceptEdits'  # auto-accept file edits
)

async for message in query(
    prompt="Create a hello.py file",
    options=options
):
    # Process tool use and results
    pass
```

### Working Directory

`

## Diff History
- **v00.33.0**: Ingested from claude-agent-sdk-python-main