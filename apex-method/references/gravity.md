# Gravitational resource composition (synergy engine)

`scripts/gravity.py` implements the "gravitational attraction to merge resources by synergy"
idea as real, deterministic math over four resource libraries.

## The bodies
Every resource is a body with a **mass**:
- **scripts** (`catalog/scripts_lib.json`) — mass = lines of code.
- **agents** (`catalog/apex_agents_roster.json`) — mass = tier weight (core agents heavier).
- **skills** (`catalog/curated_skills.json`) — mass = install count.
- **diffs** (`catalog/diffs_lib.json`) — mass = rule weight (APEX diff-packs v00.33–36).

## The forces
- **Proximity(i,j)** = cosine similarity of resource text (domain + capabilities + tags), TF-IDF.
- **Attraction F(i,j) = mass_i · mass_j · proximity(i,j)** — gravity ∝ product of masses,
  modulated by proximity. Masses are log-normalized to a comparable range.
- **Pull(task, r) = mass_r · proximity(task, r)** — a task is a body too.

## The merge (constellation)
Greedy: seed with the highest task-pull resource, then repeatedly add the resource that
maximizes `pull + synergy-to-set + diversity_bonus`, where synergy = sum of attraction to
already-chosen bodies and the bonus favors adding a NEW type. Result: a bundle that MERGES
a script + an agent + a skill + a diff-rule that reinforce each other for the task.

## Usage
```
python3 scripts/gravity.py "audit code security and check for vulnerabilities"
# -> agents: security-auditor, code-reviewer, compliance-auditor  (+ synergistic script/skill/diff)
```

## Honest caveats
- "gravity/mass" is a **weighting metaphor over similarity**, not literal physics — but the
  math is real and deterministic.
- Quality is excellent on clear-domain tasks (security, frontend) and imperfect on ambiguous
  ones (TF-IDF is lexical, so an odd agent can be pulled in). Swap in embeddings to sharpen.
- The constellation is a suggestion to compose; the pipeline + rules still govern execution,
  and any third-party resource still goes through scout + approval (H5).

## plan(task) — gap detection + skills.sh fallback + MCP

`gravity.plan(task)` extends the constellation with the full "spatial-physics" flow:
1. **Map the library** — build the constellation from existing resources (relevance floor
   drops weak matches, so it's honest when the library lacks a domain).
2. **Detect gaps** — missing roles (agent/skill/script/diff) and missing **method-skills**
   (SA, HMC, MCMC, statistical physics, …) inferred from the task.
3. **Request install** — for each gap, emit a **skills.sh search + install request** (STAGED,
   needs approval): `npx skills add <owner/repo>`.
4. **Fallbacks** — a relevant **MCP** (e.g. `science-physics-mcp`) and/or generate a CANDIDATE
   skill via `skill_forge.py`.

Worked example — "statistical physics with simulated annealing / HMC":
- library constellation: ~empty (no physics resources) → honest.
- gaps: no agent/script/diff + no SA/HMC/stat-phys method skill.
- install requests: search skills.sh for "hamiltonian monte carlo skill", "statistical physics skill".
- fallback: `integrations/science-physics-mcp` + `skill_forge create`.
Note (verified): skills.sh currently has **no** ready SA/HMC/statistical-physics skill — the
engine correctly falls back to the MCP + skill_forge rather than inventing one.
