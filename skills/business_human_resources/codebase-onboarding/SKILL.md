---
skill_id: business_human_resources.codebase_onboarding
name: "codebase-onboarding"
description: "Codebase Onboarding"
version: v00.33.0
status: CANDIDATE
domain_path: business/human-resources
anchors:
  - codebase
  - onboarding
source_repo: claude-skills-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Codebase Onboarding

**Tier:** POWERFUL  
**Category:** Engineering  
**Domain:** Documentation / Developer Experience

---

## Overview

Analyze a codebase and generate onboarding documentation for engineers, tech leads, and contractors. This skill is optimized for fast fact-gathering and repeatable onboarding outputs.

## Core Capabilities

- Architecture and stack discovery from repository signals
- Key file and config inventory for new contributors
- Local setup and common-task guidance generation
- Audience-aware documentation framing
- Debugging and contribution checklist scaffolding

---

## When to Use

- Onboarding a new team member or contractor
- Rebuilding stale project docs after large refactors
- Preparing internal handoff documentation
- Creating a standardized onboarding packet for services

---

## Quick Start

```bash
# 1) Gather codebase facts
python3 scripts/codebase_analyzer.py /path/to/repo

# 2) Export machine-readable output
python3 scripts/codebase_analyzer.py /path/to/repo --json

# 3) Use the template to draft onboarding docs
# See references/onboarding-template.md
```

---

## Recommended Workflow

1. Run `scripts/codebase_analyzer.py` against the target repository.
2. Capture key signals: file counts, detected languages, config files, top-level structure.
3. Fill the onboarding template in `references/onboarding-template.md`.
4. Tailor output depth by audience:
   - Junior: setup + guardrails
   - Senior: architecture + operational concerns
   - Contractor: scoped ownership + integration boundaries

---

## Onboarding Document Template

Detailed template and section examples live in:
- `references/onboarding-template.md`
- `references/output-format-templates.md`

---

## Common Pitfalls

- Writing docs without validating setup commands on a clean environment
- Mixing architecture deep-dives into contractor-oriented docs
- Omitting troubleshooting and verification steps
- Letting onboarding docs drift from current repo state

## Best Practices

1. Keep setup instructions executable and time-bounded.
2. Document the "why" for key architectural decisions.
3. Update docs in the same PR as behavior changes.
4. Treat onboarding docs as living operational assets, not one-time deliverables.

## Diff History
- **v00.33.0**: Ingested from claude-skills-main