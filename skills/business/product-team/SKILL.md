---
name: "product-skills"
description: "Manage — 10 product agent skills and plugins for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. PM toolkit (RICE), agile PO, product strategist (OKR), UX researcher, UI design system, co"
version: 1.1.0
author: Alireza Rezvani
license: MIT
tags:
  - product
  - product-management
  - ux
  - ui
  - saas
  - agile
agents:
  - claude-code
  - codex-cli
  - openclaw
executor: LLM_BEHAVIOR
skill_id: business.product-team
status: ADOPTED
security: {level: standard, pii: false, approval_required: false}
anchors:
  - business
  - llm
  - agent
  - research
  - design
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
output_schema:
  - name: result
    type: string
    description: "Generated or refactored code output"
  - name: explanation
    type: string
    description: "Explanation of changes or implementation decisions"
---

# Product Team Skills

8 production-ready product skills covering product management, UX/UI design, and SaaS development.

## Quick Start

### Claude Code
```
/read product-team/product-manager-toolkit/SKILL.md
```

### Codex CLI
```bash
npx agent-skills-cli add alirezarezvani/claude-skills/product-team
```

## Skills Overview

| Skill | Folder | Focus |
|-------|--------|-------|
| Product Manager Toolkit | `product-manager-toolkit/` | RICE prioritization, customer discovery, PRDs |
| Agile Product Owner | `agile-product-owner/` | User stories, sprint planning, backlog |
| Product Strategist | `product-strategist/` | OKR cascades, market analysis, vision |
| UX Researcher Designer | `ux-researcher-designer/` | Personas, journey maps, usability testing |
| UI Design System | `ui-design-system/` | Design tokens, component docs, responsive |
| Competitive Teardown | `competitive-teardown/` | Systematic competitor analysis |
| Landing Page Generator | `landing-page-generator/` | Conversion-optimized pages |
| SaaS Scaffolder | `saas-scaffolder/` | Production SaaS boilerplate |

## Python Tools

9 scripts, all stdlib-only:

```bash
python3 product-manager-toolkit/scripts/rice_prioritizer.py --help
python3 product-strategist/scripts/okr_cascade_generator.py --help
```

## Rules

- Load only the specific skill SKILL.md you need
- Use Python tools for scoring and analysis, not manual judgment

---

## Why This Skill Exists

Manage — 10 product agent skills and plugins for Claude Code, Codex, Gemini CLI, Cursor, OpenClaw. PM toolkit (RICE), agile PO, product strategist (OKR), UX researcher, UI design system, co

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## When to Use

Use this skill when the task requires product skills capabilities.

<!-- SR_40: auto-generated from frontmatter `when`/`description` (OPP-Phase3). -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
