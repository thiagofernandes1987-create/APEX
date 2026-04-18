---
name: "runbook-generator"
description: "Implement — Runbook Generator"
executor: HYBRID
skill_id: engineering.cs-engineering.runbook-generator
status: ADOPTED
security: {level: standard, pii: false, approval_required: false}
anchors:
  - engineering
tier: 2
input_schema:
  - name: code_or_task
    type: string
    description: "Code snippet, script, or task description to process"
    required: true
  - name: context
    type: string
    description: "Additional context or background information"
    required: false
output_schema:
  - name: result
    type: string
    description: "Generated or refactored code output"
  - name: explanation
    type: string
    description: "Explanation of changes or implementation decisions"
---

# Runbook Generator

**Tier:** POWERFUL  
**Category:** Engineering  
**Domain:** DevOps / Site Reliability Engineering

---

## Overview

Generate operational runbooks quickly from a service name, then customize for deployment, incident response, maintenance, and rollback workflows.

## Core Capabilities

- Runbook skeleton generation from a CLI
- Standard sections for start/stop/health/rollback
- Structured escalation and incident handling placeholders
- Reference templates for deployment and incident playbooks

---

## When to Use

- A service has no runbook and needs a baseline immediately
- Existing runbooks are inconsistent across teams
- On-call onboarding requires standardized operations docs
- You need repeatable runbook scaffolding for new services

---

## Quick Start

```bash
# Print runbook to stdout
python3 scripts/runbook_generator.py payments-api

# Write runbook file
python3 scripts/runbook_generator.py payments-api --owner platform --output docs/runbooks/payments-api.md
```

---

## Recommended Workflow

1. Generate the initial skeleton with `scripts/runbook_generator.py`.
2. Fill in service-specific commands and URLs.
3. Add verification checks and rollback triggers.
4. Dry-run in staging.
5. Store runbook in version control near service code.

---

## Reference Docs

- `references/runbook-templates.md`

---

## Common Pitfalls

- Missing rollback triggers or rollback commands
- Steps without expected output checks
- Stale ownership/escalation contacts
- Runbooks never tested outside of incidents

## Best Practices

1. Keep every command copy-pasteable.
2. Include health checks after every critical step.
3. Validate runbooks on a fixed review cadence.
4. Update runbook content after incidents and postmortems.

---

## Why This Skill Exists

Implement — Runbook Generator

<!-- SR_40: auto-generated from frontmatter `purpose`/`description` (OPP-Phase3). Expand with domain-specific rationale. -->

## What If Fails

If this skill fails to produce the expected output: (1) verify input completeness, (2) retry with more specific context, (3) fall back to the parent workflow without this skill.

<!-- SR_40: auto-generated from frontmatter `what_if_fails` (OPP-Phase3). -->
