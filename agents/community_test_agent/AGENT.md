---
agent_id: community.test_agent
name: "test-agent"
description: "---"
version: v00.33.0
status: CANDIDATE
source_repo: claude-agent-sdk-python
apex_version: v00.33.0
tier: 3
executor: "LLM_BEHAVIOR"
capabilities:
  - test_execution
  - simple_qa
  - sdk_testing
input_schema:
  question: "str"
output_schema:
  answer: "str"
what_if_fails: >
  FALLBACK: Se pergunta fora do escopo, responder o que for possível e indicar limitações.
---

# test-agent

---
name: test-agent
description: A simple test agent for SDK testing
tools: Read
---

# Test Agent

You are a simple test agent. When asked a question, provide a brief, helpful answer.


## Diff History
- **v00.33.0**: Ingested from claude-agent-sdk-python-main
