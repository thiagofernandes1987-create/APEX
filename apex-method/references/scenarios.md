# Worked scenarios (end to end)

## Scenario A — new idea → frontend build
1. Mode: STANDARD. Route the need: `python3 scripts/router.py "new idea explore options"`
   → brainstorm/ideation ranks first (divergent exploration).
2. Idea becomes a UI task → `router.py "frontend ux ui react component"`
   → frontend-design ranks first (~0.59).
3. Scout: `python3 scripts/skill_scout.py <raw SKILL.md url>` → parses structure,
   AST-scans shipped code, returns a STAGED snapshot_entry.
4. Add the entry to `snapshot.skills_staged` (id, use_when, call signature). Ask the
   user before installing. Nothing runs without approval.

## Scenario B — multidimensional math (SCIENTIFIC)
1. Mode: SCIENTIFIC. Decompose into PoT steps; integrate with `numeric.rk4`.
2. Validate against a conserved quantity or closed form (`validate_conserved`).
3. Gate any generated code with `uco_gate.gate` before running.
4. Verify algebraic claims with `verify.verify_identity`.
5. Snapshot the milestones + findings (with provenance).

## Scenario C — audit / autopsy
1. Mode: DEEP. Ishikawa for root cause, FMEA for failure modes, Pareto to prioritize.
2. For any code involved, run `uco_gate`; for any external artifact, `skill_scout` (never
   execute — evaluate as data).
3. Record each finding as what / where / how / confidence in the snapshot.
