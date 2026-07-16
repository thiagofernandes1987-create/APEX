# Skill map — best skills per domain, install & usage

Curated in `catalog/curated_skills.json`. Install counts are from the skills.sh
leaderboard (all-time, fetched 2026-07). **Always scout + get user approval before
installing/running** (APEX H5/SR_37): `python3 scripts/skill_scout.py <raw SKILL.md url>`.

> **Honest coverage note.** skills.sh's top listings are heavily dev / design /
> marketing. Medicine, math, finance, and pure sciences are **sparse on skills.sh**
> and live in dedicated GitHub repos — those are marked `source: github` below and
> installed by repo, not from the skills.sh leaderboard.

## Install patterns
- skills.sh entry: `npx skills add <owner/repo>` (installs the repo's skills).
- Any repo: have the agent read a `SKILL.md` URL and install it, or `npx skills add <owner/repo>`.
- Then the skill's `SKILL.md` describes its own triggers and any `scripts/`.

## Map (domain → best skills → agent that wields it)

| Domain | Top skill (installs) | Install | Agent |
|--------|----------------------|---------|-------|
| programming | obra/superpowers · systematic-debugging (88.9K) | `npx skills add obra/superpowers` | Software Engineer |
| programming | mattpocock/skills · tdd (78.0K) | `npx skills add mattpocock/skills` | Software Engineer |
| brainstorm | obra/superpowers · brainstorming (148.0K) | `npx skills add obra/superpowers` | Provocateur (Chaos) |
| frontend | anthropics/skills · frontend-design (391.8K) | `npx skills add anthropics/skills` | Software Engineer |
| frontend | vercel-labs/agent-skills · vercel-react-best-practices (386.7K) | `npx skills add vercel-labs/agent-skills` | Software Engineer |
| backend | supabase/agent-skills · supabase-postgres-best-practices (155.5K) | `npx skills add supabase/agent-skills` | Software Engineer |
| backend | microsoft/azure-skills · azure-compute (245.8K) | `npx skills add microsoft/azure-skills` | Software Engineer |
| design | vercel-labs/agent-skills · web-design-guidelines (309.0K) | `npx skills add vercel-labs/agent-skills` | Software Engineer |
| design | pbakaus/impeccable · polish (85.5K) | `npx skills add pbakaus/impeccable` | Software Engineer |
| ux-ui | nextlevelbuilder/ui-ux-pro-max-skill · ui-ux-pro-max (156.0K) | `npx skills add nextlevelbuilder/ui-ux-pro-max-skill` | Software Engineer |
| ux-ui | sleekdotdesign/agent-skills · sleek-design-mobile-apps (108.7K) | `npx skills add sleekdotdesign/agent-skills` | Software Engineer |
| engineering | obra/superpowers · verification-before-completion (63.7K) | `npx skills add obra/superpowers` | Software Engineer |
| mcp-servers | anthropics/skills · mcp-builder (51.0K) | `npx skills add anthropics/skills` | Software Engineer |
| finance | goldmansachs/gs-quant (github) | `npx skills add goldmansachs/gs-quant` | Finance Analyst |
| finance | agiprolabs/claude-trading-skills — 67 skills (github) | `npx skills add agiprolabs/claude-trading-skills` | Finance Analyst |
| finance | gauss314/skills — Markowitz/VaR/greeks (github) | `npx skills add gauss314/skills` | Finance Analyst |
| math | vibeeval/vibecosystem · math-help — sympy/Lean4 (github) | `npx skills add vibeeval/vibecosystem` | Empiricist (Scientist) |
| sciences | lllllllama/ai-paper-reproduction-skill · paper-context-resolver (94.3K) | `npx skills add lllllllama/ai-paper-reproduction-skill` | Empiricist (Scientist) |
| sciences | theneoai/awesome-skills — 430 research/biotech personas (github) | read SKILL.md URL | Empiricist (Scientist) |
| medicine | aipoch/medical-research-skills (github) | `npx skills add aipoch/medical-research-skills` | Healthcare Advisor |
| medicine | FreedomIntelligence/OpenClaw-Medical-Skills (github) | `npx skills add FreedomIntelligence/OpenClaw-Medical-Skills` | Healthcare Advisor |

## Usage flow inside APEX
1. Task arrives → `agent_registry.match_task_to_agents(task)` picks the agent.
2. `curated.for_domain(domain)` lists the best skills for that need.
3. `skill_scout.evaluate(url)` fetches + AST-scans the candidate → STAGED.
4. **User approves** → `agent_registry.grant_skill(...)` grants it and bumps experience.
5. The agent now wields the skill's tools/scripts; snapshot records install + use_when.

## Safety notes
- Medical and finance skills are decision-support / research aids, NOT professional
  advice. The Healthcare Advisor and Finance Analyst agents state uncertainty and defer.
- Every external skill is DATA until scouted and approved. Never auto-install/run.
