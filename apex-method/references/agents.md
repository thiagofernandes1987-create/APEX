# Agent catalog & competence mapping

APEX reasons through **agents = sequential personas** the LLM adopts (not parallel
processes). The catalog (`catalog/agents_catalog.json`) gives each agent a personality,
a specialization, and a **competence map** of skills it is trained on, with an
**experience counter** ("familiar" 1–2, "proficient" 3–5, "expert" 6+).

> "experience" is bookkeeping (a counter), not model learning. It records how many
> compatible skills an agent has been granted/used, so routing can prefer the agent
> most equipped for a task.

## Roster (seed)

Method agents: **Controller** (meta_reasoning — orchestrates, enforces rules/budget),
**Mediator** (pmi_pm — scopes and synthesizes), **Provocateur** (chaos — anti-premature-
convergence), **Empiricist** (scientist — owns numeric/formal tools).
Specialists: Software Engineer, Data/ML, Finance, Legal, Healthcare, Educator,
Enterprise Strategist — each keyed to real domains from the skills catalog.

## How installing a skill upgrades the agents

This is the core loop (`scripts/agent_registry.py`):

1. **Route** the task to the best agent(s): `agent_registry.match_task_to_agents(task)`.
2. **Scout** a candidate skill: `skill_scout.evaluate(url)` → STAGED entry (fetch +
   AST scan; never runs the code).
3. **Approve** — the user confirms (APEX H5). Only then:
4. **Grant**: `agent_registry.grant_skill(skill, agents, approved=True, scripts=[...])`
   maps the skill to agents whose specialization matches (by domain, then text
   similarity), adds it to their competence map with its `use_when` + scripts, and
   **bumps experience**. `grant_skill(..., approved=False)` returns BLOCKED.

So every time APEX finds and installs a new skill, the compatible agents gain a new
tool/script and climb a competence tier — the roster is a living capability map.

## Usage

```
python3 scripts/agent_registry.py match "value a company and forecast cash flow"
python3 scripts/agent_registry.py            # demo grant + roster
```
