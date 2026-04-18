# OPP-153 — Register Community Subagents in Boot Roster
## OPP-154 — Register CS Persona Agents in Boot Roster

**OPP**: OPP-153 / OPP-154
**Version**: v00.36.0
**Date**: 2026-04-17
**Status**: IMPLEMENTED
**Priority**: HIGH
**Author**: APEX Pipeline (auto-generated via tools/generate_agent_roster.py)

---

## Problem Statement

**163 agents exist on disk but are NOT registered in the boot's `community_agent_roster`.**

Without registration, `meta_reasoning` cannot activate these agents automatically.
They exist as AGENT.md files but are invisible to the APEX activation pipeline.

### Breakdown

| Group | Count | Location |
|-------|-------|----------|
| community-subagents | 140 | `agents/community-subagents/categories/` |
| cs-personas | 23 | `agents/cs_*/` |
| **Total unregistered** | **163** | |

### Community Subagents by Category

| Category | Agents |
|----------|--------|
| `01-core-development` | 11 |
| `02-language-specialists` | 29 |
| `03-infrastructure` | 16 |
| `04-quality-security` | 15 |
| `05-data-ai` | 13 |
| `06-developer-experience` | 14 |
| `07-specialized-domains` | 12 |
| `08-business-product` | 12 |
| `09-meta-orchestration` | 10 |
| `10-research-analysis` | 8 |

### CS Persona Agents (23)

- `content-strategist`
- `cs-agile-product-owner`
- `cs-ceo-advisor`
- `cs-content-creator`
- `cs-cto-advisor`
- `cs-demand-gen-specialist`
- `cs-engineering-lead`
- `cs-financial-analyst`
- `cs-growth-strategist`
- `cs-product-analyst`
- `cs-product-manager`
- `cs-product-strategist`
- `cs-project-manager`
- `cs-quality-regulatory`
- `cs-senior-engineer`
- `cs-ux-researcher`
- `cs-workspace-admin`
- `devops-engineer`
- `finance-lead`
- `growth-marketer`
- `product-manager`
- `solo-founder`
- `startup-cto`

---

## Root Cause

- APEX boot v00.36.0 `community_agent_roster` only lists the 9 `community_*` base agents explicitly.
- The 140 community-subagents (created via OPP-150) were added to disk but never received a boot-level `activates_when` mapping.
- The 23 cs_ persona agents were converted from SKILL.md files to AGENT.md but never mapped to the activation pipeline.

---

## Solution

### OPP-153: community-subagents
1. Scan `agents/community-subagents/categories/**/AGENT.md`
2. Derive `activates_when[]` from: category, agent_id, capabilities, description
3. Write `agents/community_agent_roster.yaml` with full roster

### OPP-154: cs-personas
1. Scan `agents/cs_*/AGENT.md`
2. Derive `activates_when[]` from agent description and capabilities
3. Append to `community_agent_roster.yaml` under `cs_agent_roster:`

### Activation Rule (for boot integration)
```yaml
# Add to APEX boot kernel.community_activation:
community_agent_roster_file: agents/community_agent_roster.yaml
activation_trigger: meta_reasoning.STEP_1 (domain detection)
max_concurrent: 2  # 1 domain expert + 1 orchestrator
fallback: engineer
```

---

## Files Changed

| File | Change |
|------|--------|
| `agents/community_agent_roster.yaml` | NEW — machine-readable roster with `activates_when` mappings |
| `tools/generate_agent_roster.py` | NEW — generator script (idempotent, re-runnable) |
| `references/OPP-153-register-subagents.md` | NEW — this document |

---

## Activation Protocol

```
STEP 1: pmi_pm detects domain from user request
STEP 2: meta_reasoning checks community_agent_roster.yaml
          → finds agent where domain in activates_when[]
          → emits [COMMUNITY_AGENT_ACTIVATED: {agent_id} | domain: {domain}]
STEP 3: Agent activated as specialist alongside base engineer
          → MAX 2 concurrent community agents
STEP 4: On failure: emit [SUBAGENT_FALLBACK: {agent_id}] + use base agent
```

---

## Impact

- **Before**: 163 agents exist but 0 are auto-activated by meta_reasoning
- **After**: 163 agents registered with `activates_when` mappings → auto-activated by domain
- **Coverage**: Adds domain-expert coverage for: code, testing, security, data, ml, devops, cloud, business, product, research, and 20+ language-specific domains

---

## Verification

```bash
python tools/generate_agent_roster.py --dry-run
# Expected: 140 subagents + 23 cs agents = 163 total
```

---

## Diff History
- **v00.36.0**: OPP-153/154 implemented — `community_agent_roster.yaml` generated; 163 agents registered
