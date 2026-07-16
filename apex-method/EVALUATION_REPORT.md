# Evaluation Report — apex-method

> **Self-scored.** These numbers come from running the skill's own scripts against
> fixed, code-verifiable test cases. This is an internal sanity check, not an
> independent benchmark (same caveat the awesome-skills repo makes about its scores).

## Functional tests (executed, verify() objective)

| Tool | Test | Result |
|------|------|--------|
| numeric.rk4 | 2D oscillator, 2000 steps; energy must stay 1.0 | RK4 error 4.3e-7 vs Euler 1.5e2 |
| verify.verify_identity | (x+1)²=x²+2x+1 (true) / x²+x+1 (false) | VERIFIED / REFUTED (5/5 on the suite) |
| router.route | frontend task → frontend skill; new idea → brainstorm | correct (0.59 / 0.26) |
| uco_gate.gate | while-True function | REJECTED (loop_risk 0.65) |
| pot.run_chain | sum(1..100) → square | 5050 → 25502500 (chain ok) |
| skill_scout.ast_security_scan | os.system / __import__ / getattr / pickle.loads / eval | all BLOCKED (v1.1.0 fix) |
| agent_registry.match_task_to_agents | API task / valuation / challenge | engineer / finance_analyst / chaos (correct) |
| agent_registry.grant_skill | grant 4 ai-ml skills after approval | data_ml+scientist competence updated, ai-ml exp=4 |
| agent_registry (gate) | grant without approval | BLOCKED (APEX H5) |
| skill_scout (real fetch) | computer-vision-engineer SKILL.md from repo | STAGED, ast_security PASS |

## Known limitations (see SKILL.md § 12)

- Router is lexical (TF-IDF) → cross-language discovery can miss.
- AST scanner is best-effort static analysis, not a sandbox.
- Snapshot is context-resident, not cross-session disk persistence.
- "Perspectives" are sequential stances, not parallel agents.

## 8-dimension self-rubric (0–5)

| Dimension | Score | Note |
|-----------|-------|------|
| Clarity | 5 | modes + steps explicit |
| Actionability | 5 | real runnable scripts |
| Safety | 4 | scanner hardened; still static-only |
| Scope honesty | 5 | limitations stated plainly |
| Token discipline | 5 | 5 modes with budgets |
| Reusability | 4 | composes with other skills |
| Provenance | 5 | claims carry what/where/how |
| Test coverage | 4 | 6 tools tested; router cross-lang gap |
