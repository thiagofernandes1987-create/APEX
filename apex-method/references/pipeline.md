# Pipeline — reasoning methodology + operating modes

This is the APEX pipeline distilled into a reasoning discipline. It is a **method the model follows**, not a system that runs on its own. The quantum vocabulary of the original (superposition, phase, interference) is dropped; what remains is the engineering discipline.

## Operating modes (token control)

Pick the lightest mode that fits. Each mode runs a different subset of the pipeline and caps how many perspectives ("agents") to generate, so cost scales with difficulty. Budgets are from the APEX kernel.

| Mode | ~Token budget | Perspectives | Pipeline steps run | PoT / tools |
|------|---------------|--------------|--------------------|-------------|
| **EXPRESS** | ~400 | 1 | Intake → answer. No decomposition. | off |
| **STANDARD** | ~2000 | 2–3 | Intake → classify → resolve skill → reason → validate → answer | PoT if numeric |
| **FOGGY** | ~5500 | ~5 | STANDARD + **tag every assumption** (A-xxx) before reasoning; frame goal as hypothesis | PoT on |
| **DEEP** | ~8000 | up to 8 | Full pipeline + Pareto/Ishikawa/SWOT validation + chaos stance | PoT on, chaos on |
| **SCIENTIFIC** | ~12000 | up to 8 | DEEP + the 10 scientific steps (symbolic exec, RK4, error tracking, formal verify) + DSM | PoT + numeric + sympy |

Rules of thumb: default to **STANDARD**. Escalate to DEEP when the problem has conflicting constraints or high stakes; to SCIENTIFIC when there is real math/dynamics to compute; drop to EXPRESS for trivial factual asks. If a conflict/complexity signal appears mid-answer, escalate and say so.

## The pipeline (what each phase does)

1. **Intake** — restate the goal; quick complexity check; pick the mode.
2. **Classify** — what kind of problem is this; what sub-parts exist.
3. **Resolve skills** — run `router.py` against the need; if a specialized skill helps, stage it (see skill_scout).
4. **Generate perspectives** — produce genuinely different stances (see below), including a **chaos stance** whose job is to resist converging too early and surface overlooked options.
5. **Decompose + compute** — break numeric/logical sub-problems out and run them via `pot.py` (chained: output of one feeds the next); use `numeric.py` for dynamics.
6. **Validate** — apply the validation methodology (see validation.md): FMEA on the plan, Ishikawa for root cause, Pareto to prioritize, DSM for coupling.
7. **Synthesize** — the model debates the perspectives and picks the hypothesis most likely to be right; where hypotheses are quantifiable, decide by real simulation, otherwise by explicit weighted judgment (do **not** call qualitative weighting "Monte Carlo").
8. **Verify** — check code with `uco_gate.py`, math with `verify.py`.
9. **Snapshot** — write the standardized snapshot (snapshot.py format) into the context.

## On "multiple agents"

The model does not run parallel agents. It generates multiple **perspectives in sequence** and adjudicates between them. This is a debiasing discipline (especially the chaos stance), not parallel cognition. The mode's "agent" number is just the cap on how many perspectives to generate before it costs more tokens than it's worth.
