# mental_interpreter_v4 (deep dive) — the execution orchestrator

APEX `mental_interpreter_v4` (v00.32.0, OPP-75) replaces v3 for DEEP/RESEARCH/SCIENTIFIC
(v3 stays for EXPRESS/FAST/CLARIFY). It is the module that turns an intent into a sized,
verified execution plan. Nativized core in `scripts/mental_interpreter.py`.

## Four phases
1. **SPECULATION** (new in v4; activates when mode ∈ {DEEP,RESEARCH,SCIENTIFIC} AND
   fractal_depth ≥ 2): generate N PoT programs with **stances** (optimistic / pessimistic /
   neutral) → pass each through the **UCO quality gate** → execute in **parallel**
   (ThreadPoolExecutor) → **entropy_weighted_merge** the snapshots → register merged
   hypotheses in the **hypothesis_dag**. Emits PARALLEL_POT_COMPLETE / PARTIAL.
2. **WARMUP** (from v3): run N_WARM_BLOCKS to observe the problem's "field geometry".
3. **PLANNING** (from v3): compute block size before executing —
   `n_final = max(MIN_SIZE, min(n_num, n_rel, MAX_SIZE))`
   where `n_num` = numerical limit (curvature, GeometryEstimator) and `n_rel` = statistical
   limit (ReliabilityEstimator.optimal_size_for_target(P_target, ε)).
4. **PRODUCTION** (from v3): fixed subprocess pipeline; **error_evolution_loop** on failure
   (diagnose → patch → re-execute, rollback if stderr doesn't shrink).

## Components
MentalInterpreter (orchestrator), TrajectoryVerifier (GAP/DUPLICATE/RETROGRADE/negative
checks), MCFEAdapter (ESCALATE fallback, MAX_RETRIES 4, MIN_PROGRESS 0.15), + v4:
SpeculationPhase, UCOGateWrapper, SharedWarmupCache.

## New pipeline steps (v3→v4)
- STEP_0: reset R_acum=1.0, restore reliability_state from snapshot.
- STEP_5: dynamic replanning when R_acum < WARNING (0.50).
- STEP_13: save reliability_state, print RELIABILITY_REPORT.

## What's real here
`n_final`, `entropy_weighted_merge`, the UCO gate, parallel execution, and the hypothesis_dag
are all real computations (in this skill). The per-stance PoT *generation* is the LLM's job
(SpeculationPhase); the skill supplies the machinery around it.
