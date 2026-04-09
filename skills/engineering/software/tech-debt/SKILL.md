---
skill_id: engineering.software.tech_debt
name: "tech-debt"
description: "Identify, categorize, and prioritize technical debt. Trigger with 'tech debt', 'technical debt audit', 'what should we refactor', 'code health', or when the user asks about code quality, refactoring p"
version: v00.33.0
status: ADOPTED
domain_path: engineering/software/tech-debt
anchors:
  - tech
  - debt
  - identify
  - categorize
  - prioritize
  - technical
  - trigger
  - audit
  - refactor
  - code
  - health
  - user
source_repo: knowledge-work-plugins-main
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: partial, gemini: partial, llama: minimal}
apex_version: v00.33.0
---

# Tech Debt Management

Systematically identify, categorize, and prioritize technical debt.

## Categories

| Type | Examples | Risk |
|------|----------|------|
| **Code debt** | Duplicated logic, poor abstractions, magic numbers | Bugs, slow development |
| **Architecture debt** | Monolith that should be split, wrong data store | Scaling limits |
| **Test debt** | Low coverage, flaky tests, missing integration tests | Regressions ship |
| **Dependency debt** | Outdated libraries, unmaintained dependencies | Security vulns |
| **Documentation debt** | Missing runbooks, outdated READMEs, tribal knowledge | Onboarding pain |
| **Infrastructure debt** | Manual deploys, no monitoring, no IaC | Incidents, slow recovery |

## Prioritization Framework

Score each item on:
- **Impact**: How much does it slow the team down? (1-5)
- **Risk**: What happens if we don't fix it? (1-5)
- **Effort**: How hard is the fix? (1-5, inverted — lower effort = higher priority)

Priority = (Impact + Risk) x (6 - Effort)

## Output

Produce a prioritized list with estimated effort, business justification for each item, and a phased remediation plan that can be done alongside feature work.

## Diff History
- **v00.33.0**: Ingested from knowledge-work-plugins-main — auto-converted to APEX format
