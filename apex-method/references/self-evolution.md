# Self-Evolution — the auto-evolutive prompt library (v1.54)

APEX does not stay static between sessions. A problem the runtime solves **grows the library**:
an agent that started generic becomes a standardized specialist, the skills forged for it are kept,
the diffs/scripts promoted with it persist, and the mistakes made are remembered so they are not
repeated. This document is the contract for that loop — the behaviour Claude must follow and the
files that make it real.

## The closed loop (per problem)

```
dissect ──► competence matrix ──► find-or-create agent ──► validate/equip ──► execute ──► EVOLVE
(orchestr.) (taxonomy:            (agent_registry roster/  (discovery         (host)      (finalize)
             discipline→           repo; else SYNTHESIZE     cascade: native →
             subdomain→            a generic persona)        skills.sh → GitHub;
             specialization)                                 else skill_forge)
```

Modules: `agent_lifecycle.run(task)` drives steps 1–5 and returns an executable spec; the **host**
executes step 6 (the Level-B subagent); `agent_lifecycle.finalize(...)` runs steps 7–8.

## Generic → specialist (materialization)

When the roster has no adequate agent, `agent_spawn.spawn(..., synthesize=True)` fabricates a
**generic** persona from the task's canonical facets — honest about being synthesized. If that
generic agent then produces a **validated** result, `finalize` calls
`agent_materializer.materialize(...)`, which:

1. **Renders standardized artifacts** in the SAME layout the APEX repo uses (one layout per object
   type). `AGENT.md` carries the canonical frontmatter — `agent_id`, `name`, `version`, `status`,
   `anchors`, `activates_in`, `capabilities`, `input_schema`, `output_schema`, `what_if_fails`,
   `security`, `primary_domain` — plus an honest `origin: grown_from_generic_spawn` provenance.
   Each forged/promoted skill is rendered as `SKILL.md` (`skill_id`, `domain_path`, `anchors`,
   `risk`, `llm_compat`).
2. **Writes them to a durable grown-library** under `APEX_METHOD_HOME/library/{agents,skills}`.
3. **Registers the specialist** in the roster overlay (`agent_registry.register_grown_agent`),
   anchored on the facets **and the salient task terms** — so the SAME (or a similar) task
   re-matches this specialist next session instead of re-synthesizing a generic one.

**Next session** `agent_registry.load_ext_roster()` merges the shipped 213-agent roster with the
grown overlay, so `agent_lifecycle.resolve_agent(task)` finds the grown specialist
(`synthesize=False`) with no rebuild of the 1 MB catalog. The generic that solved a problem is now
a permanent, discoverable engineer.

### Consolidating into the repo (cross-session, cross-machine)

The container is ephemeral, so the durable library survives a recycle only via the **swap** (below)
or a **git commit**. `agent_materializer.consolidate_to_repo(repo_root, commit=False)` copies the
grown artifacts into the repo's standard folders (`agents/grown/…`, `skills/grown/…`) and STAGES a
git commit. It never auto-commits — the human reviews and approves (H5). Committed, the grown
specialists become part of the shipped library for every future clone.

## The swap memory carries what was promoted, demoted, AND what went wrong

`swap_store.page_out(session_id)` bundles the durable stores; `page_in_session(dir)` restores them
on a fresh machine with an integrity check. The bundle carries, and the round-trip preserves:

| Store | What it holds | Why it matters next session |
|---|---|---|
| `grants` | abilities **promoted** to each agent (equip) | the agent keeps its equipment |
| `learning` | **promote/demote** history (beta-binomial Ω) | proven skills resurface; **demoted** ones are avoided |
| `competence` | per-session competence signals | metacognition (persona-swap / inject-skill) |
| `vaccines` | **error → why/fix** lessons (`error` + `fix` columns) | the exact mistake and its root cause are remembered |
| `memory` + `ledger` | validated facts + SHA-chained governance log | durable, tamper-evident provenance |

Learning from failure is explicit. `agent_lifecycle.finalize(..., validated=False, error=…, why=…)`
(or `record_failure` directly) records a **demotion** + a **vaccine** with the error text and WHY it
was wrong. `agent_spawn.context_pack(task)` then surfaces these to every future spawn as
`LESSONS (validated error→fix)` and `DEMOTED (do NOT default to)`. So a mistake made once — e.g.
"used E=210 GPa for concrete" → "concrete uses E_cs = αe·5600·√fck (NBR 6118)" — is carried forward
and not committed again. This is the honest other half of promotion: **the library learns from
audits and failures, not only from successes.**

## Gates (non-negotiable)

- **Nothing auto-installs or auto-equips.** Discovery and skill-forge are STAGED; the human approves
  (H5) before install/equip.
- **The library evolves ONLY on a validated success.** An unvalidated run never promotes (no
  reputation poisoning) — but it DOES learn from a diagnosed failure.
- **The repo is written only via `consolidate_to_repo`**, which stages a commit for human approval;
  it never commits on its own.
- **Provenance is honest.** A grown agent's `AGENT.md` records that it was grown from a generic
  spawn and validated, not hand-authored.

## What Claude must do

1. Prefer `agent_lifecycle.run(task)` for any task that may need a specialist the roster lacks.
2. Refuse to use a spec whose `spawn_ready` is False (or `status == BLOCKED_UNKNOWN_AGENT`) — pick a
   real agent or synthesize.
3. After executing a subagent, call `finalize(...)` with the honest outcome: `validated=True` on
   success (which promotes and, for a grown agent, materializes it), or `validated=False, error=…,
   why=…` on failure (which teaches the lesson without promoting).
4. When the grown library is worth keeping across machines, offer `consolidate_to_repo` — and let
   the human approve the commit.
