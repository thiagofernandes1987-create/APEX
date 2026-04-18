---
name: "business-growth-skills"
description: "Manage — 4 business growth agent skills and plugins for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. Customer success (health scoring, churn), sales engineer (RFP), revenue operations "
version: 1.1.0
author: Alireza Rezvani
license: MIT
tags:
  - business
  - customer-success
  - sales
  - revenue-operations
  - growth
agents:
  - claude-code
  - codex-cli
  - openclaw
executor: LLM_BEHAVIOR
skill_id: business.business-growth
status: CANDIDATE
security: {level: standard, pii: false, approval_required: false}
anchors:
  - business
  - llm
  - agent
  - finance
  - sales
  - customer_success
---

# Business & Growth Skills

4 production-ready skills for customer success, sales, and revenue operations.

## Quick Start

### Claude Code
```
/read business-growth/customer-success-manager/SKILL.md
```

### Codex CLI
```bash
npx agent-skills-cli add alirezarezvani/claude-skills/business-growth
```

## Skills Overview

| Skill | Folder | Focus |
|-------|--------|-------|
| Customer Success Manager | `customer-success-manager/` | Health scoring, churn prediction, expansion |
| Sales Engineer | `sales-engineer/` | RFP analysis, competitive matrices, PoC planning |
| Revenue Operations | `revenue-operations/` | Pipeline analysis, forecast accuracy, GTM metrics |
| Contract & Proposal Writer | `contract-and-proposal-writer/` | Proposal generation, contract templates |

## Python Tools

9 scripts, all stdlib-only:

```bash
python3 customer-success-manager/scripts/health_score_calculator.py --help
python3 revenue-operations/scripts/pipeline_analyzer.py --help
```

## Rules

- Load only the specific skill SKILL.md you need
- Use Python tools for scoring and metrics, not manual estimates

---

## Why This Skill Exists

Manage — 4 business growth agent skills and plugins for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. Customer success (health scoring, churn), sales engineer (RFP), revenue operations

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires business growth skills capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
