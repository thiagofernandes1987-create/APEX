# Analysis: vercel-labs/skills + skills.sh — what APEX can reuse

Requested audit of https://github.com/vercel-labs/skills and the skills.sh marketplace,
with a **≥1000-install quality bar** for anything considered adoptable. Findings below are
from the live repo/registry (July 2026); the concrete adoptions are already wired into the
skill (see "Adopted").

## What vercel-labs/skills is

The open **`npx skills`** CLI — a package manager for agent skills across 70+ coding agents
(Claude Code, Cursor, Codex, Cline, …). **~26,000 stars**, TypeScript. A skill is a folder
with a `SKILL.md` (YAML frontmatter: `name` + `description` required) plus optional files —
the same neoformat convention apex-method already targets. Commands: `add`, `use`, `find`,
`list`, `update`, `remove`, `init`.

`skills.sh` is its registry/leaderboard: ~670k skills listed (June 2026), ranked by **total
installs** (anonymous CLI telemetry). Top skill `vercel-labs/find-skills` ~2.0M installs;
`anthropics/frontend-design` ~531.8k. API: `GET https://skills.sh/api/v1/skills?view=trending`,
`?q=<query>` (fuzzy/semantic), `/api/v1/skills/official`.

`vercel-labs/agent-skills` is Vercel's first-party collection (8 skills): vercel-optimize,
react-best-practices (40+ rules / 8 categories), web-design-guidelines (100+ rules),
writing-guidelines, react-native-guidelines, react-view-transitions, composition-patterns,
vercel-deploy-claimable. They are **checklist-driven audit skills** — impact-prioritized rule
sets with context-aware triggers.

## Reusable ideas — and what we did with each

| Idea from vercel-labs/skills | Verdict | Action in apex-method |
|---|---|---|
| **Leaderboard ranked by installs** as the popularity signal | Adopt | `scripts/skills_sh.py` queries the real API (`trending`/`hot`/search/official) |
| **≥1000-install quality bar** (the find-skills convention) | Adopt | default `min_installs=1000` filter; below-bar skills dropped |
| **Official-owner trust tier** (vercel-labs/anthropics pre-trusted) | Adopt | `skill_scout.trust_tier()` marks OFFICIAL vs COMMUNITY (still AST-scanned) |
| **Discovery cascade** (leaderboard → search → verify) | Adopt | wired into `gravity.plan`: native index → skills.sh (≥1000) → GitHub → H5 |
| **`npx skills add owner/repo`** install UX | Adopt | emitted as the STAGED install command (never auto-run) |
| Checklist-driven audit skills (40+/100+ rules) | Already have | APEX validation.md (FMEA/Ishikawa/Pareto/DSM) is the same pattern; vercel's per-domain rule packs are good candidates to *install* via the flow above |
| Symlink-vs-copy install, 70+ agent dir mapping | Out of scope | that is CLI plumbing; the skill only stages + asks for approval |

## Safety stance (unchanged)

skills.sh is on a **read-only discovery allowlist** (JSON listings only), separate from any
code-exec path. The trust tier and install count are **ranking signals, not gates**: every
fetched skill still goes through `skill_scout`'s AST scan and the H5 human-approval gate before
anything installs or runs. Nothing here weakens SR_37/H5.

## Not adopted (and why)

- The CLI's agent-directory mapping and symlink logic — apex-method is a skill, not a CLI; it
  discovers and stages, it does not manage installs on disk.
- Auto-installing top-leaderboard skills — forbidden by H5; popularity never bypasses approval.

Sources: github.com/vercel-labs/skills, github.com/vercel-labs/agent-skills, skills.sh/docs/api.
