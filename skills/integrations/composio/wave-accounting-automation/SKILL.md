---
name: Wave Accounting Automation
description: "Wave Accounting toolkit is not currently available as a native integration. No Wave-specific tools were found in the Composio platform. This skill is a placeholder pending future integration."
category: accounting
requires:
  mcp:
    - rube
executor: HYBRID
skill_id: integrations.composio.wave-accounting-automation
status: CANDIDATE
security: {level: standard, pii: false, approval_required: false}
extends: integrations.composio.meta
toolkit: wave-accounting-automation
# Phase3: This stub routes to the meta-skill. See skills/integrations/composio/SKILL.md for full protocol.
anchors:
  - automation
  - integration
  - api
  - workflow
---

# Wave Accounting Automation

> **Note:** The Wave Accounting toolkit (`wave_accounting`) does not currently have native tools available in the Composio platform. Searches for Wave Accounting-specific tools return results from other accounting/invoicing platforms (Stripe, Zoho Invoice) instead.

**Toolkit docs:** [composio.dev/toolkits/wave_accounting](https://composio.dev/toolkits/wave_accounting)

---

## Status

This integration is **not yet available** with native Wave Accounting tools. When Wave Accounting tools become available in Composio, this skill file will be updated with real tool slugs, workflows, and pitfalls.

For accounting and invoicing automation needs, consider these alternatives that are available today:
- **Stripe** -- Payment processing, invoicing, and subscription management
- **Zoho Invoice** -- Invoice creation, payment tracking, and contact management
- **QuickBooks** -- Full accounting suite with invoicing and expense tracking
- **FreshBooks** -- Cloud accounting with time tracking and invoicing

---

## Setup

1. Add the Composio MCP server to your client configuration:
   ```
   https://rube.app/mcp
   ```
2. Check back for Wave Accounting integration availability.

---

*Powered by [Composio](https://composio.dev)*

## Why This Skill Exists
Stub for the `wave-accounting-automation` toolkit in the Composio integration ecosystem.
Extends `integrations.composio.meta` — see the meta-skill for full protocol.

## When to Use
Use when automating `wave-accounting-automation` tasks via Rube MCP (Composio).
For generic Composio queries, use `integrations.composio.meta` directly.

## What If Fails
See `skills/integrations/composio/SKILL.md` (meta-skill) for full fallback protocol.
RULE: Never block workflow — always suggest manual alternative if automation fails.
