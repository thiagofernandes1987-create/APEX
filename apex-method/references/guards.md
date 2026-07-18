# Enforceable guards SR_36–SR_40 (`scripts/guards.py`)

The APEX inviolable guards, implemented as real PASS/REJECT checks (not LLM_BEHAVIOR).

- **SR_36 [JIT_CRYSTALLIZATION_GUARD]** — per-class ΔH thresholds: class_1=0.02, class_2=0.05,
  class_3=0.08, resolution_cache=0.05, code_genetics=0.0, hypothesis_dag=0.0. A single flat
  threshold (e.g. 0.05 for all) is a VIOLATION (discards valid class_1 updates).
  `crystallization_guard(class_, delta_h)`, `validate_thresholds(...)`.
- **SR_37 [DYNAMIC_FORGE_SECURITY_GUARD]** — before loading an external skill: AST scan;
  imports outside whitelist = REJECT; exec/eval/__import__ = REJECT; dangerous attr calls =
  REJECT; clone HTTPS + allowlist only. `forge_load_gate(code, url)` (stricter than the
  general two-tier scan — non-whitelist imports are hard-rejected here).
- **SR_38 [EXTERNAL_CRITIC_INJECTION_GUARD]** — the external critic must run BEFORE
  meta_reasoning at STEP_12 (injecting it after neutralizes the historical evidence).
  `external_critic_order(step_sequence)`.
- **SR_39 [LLM_RUNTIME_GUARD]** — detect the runtime before any SANDBOX_CODE; simulated output
  must be marked `[SIMULATED]` (MINIMAL) or `[SANDBOX_PARTIAL: {module}]` (PARTIAL).
  `runtime_guard()`.
- **SR_40 [ZERO_AMBIGUITY_GUARD]** — every SANDBOX_CODE module documents why/when/what-if-fails;
  every SKILL.md has Why/When/What-if-fails sections. `zero_ambiguity_lint_module/skill(...)`.

## Self-compliance
The SR_40 linter was run against this skill's own scripts and SKILL.md. It initially FAILED on
several files; those were fixed, and now **all 27 scripts + SKILL.md pass SR_40** — the skill
practices the guard it enforces. (Count updated in the v1.17.0 audit; the old text said 18.)
