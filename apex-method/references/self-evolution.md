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

## The taxonomy itself grows (self-evolving vocabulary — two-tier, SQLite-backed)

The competence matrix is only as good as the classifier that feeds it. `taxonomy.py` ships a seed
set of bilingual (PT+EN) facet triggers, but it is **not frozen** — and it is engineered to stay
fast as the learned vocabulary grows large.

**Storage decision (v1.56): SQLite, not a monolithic document.** A JSON/XML overlay would have to be
parsed whole on every session start — O(n) load that degrades as the file grows. The overlay is a
**lookup index**, so it lives in a durable SQLite DB (`APEX_METHOD_HOME/library/taxonomy_evolved.db`,
stdlib `sqlite3`) with the term column indexed. `classify()` queries **only the current task's
tokens** (`WHERE term IN (…)`, O(len(tokens)·log n)) — it never loads the whole table. When no
overlay exists yet, `classify()` adds **zero** overhead (no DB is opened). The v1.55 JSON overlay is
migrated into the DB **once, losslessly** (its terms enter as ADOPTED; the file is renamed
`*.migrated`). XML was rejected outright: larger on disk, slower to parse, no query advantage.

**Two tiers, one unified schema** (the same conceptual fields as AGENT.md/SKILL.md):

| Tier | Table | Fields | Touched by `classify()`? |
|---|---|---|---|
| HOT (index) | `triggers` | `term, axis, facet, status, uses` | yes — only the task's tokens |
| COLD (metadata) | `term_meta` | `term, en, pt, validated_by, ts` | no |

- **Promotion gate (CANDIDATE → ADOPTED).** `evolve(task, domain, subdomain, specialties)` (called by
  `finalize` on a validated success) records each salient term as CANDIDATE, and promotes it to
  ADOPTED only after `PROMOTE_N` validations (default 2, matching the vaccine gate). `classify()`
  reads **ADOPTED only**, so a single run's tokens never pollute classification. Evolution learns
  **only from validated successes** — never reinforces an unvalidated guess.
- **Bilingual pair (LLM-validated).** `translate(term, en, pt, validated_by)` records the EN/PT pair
  in `term_meta` and **propagates the term's facets to both languages**, so a PT task and its EN
  translation attract on the same facet — the bilingual convention of AGENT.md/SKILL.md, now in the
  taxonomy. Translation is an LLM act (like authoring a skill body), not a stdlib guess.
- **Relations reuse the Knowledge Graph.** `relate_facets(src, dst, rel)` records facet↔facet
  dependency / escalation in the EXISTING KG (`memory.relate`), reusing its typed-edge vocabulary
  (`causa | depende_de | refina | contradiz | suporta`) — a subdomain that "escalates to" its
  domain is modeled as `depende_de`. No new relation language is invented.

The base seed also carries an `engineering` domain (+ structural / geotechnical / mechanical /
electrical subdomains), so out of the box a structural task classifies as `engineering/structural`
instead of the old `legal/calculus` mislabel — and the ADOPTED overlay expands coverage from there.
The DB travels with the swap/git-export like the other durable stores.

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
