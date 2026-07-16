# Validation methodology (reasoning-validation frameworks)

Classic engineering frameworks used here to **stress-test reasoning**, not just code. Apply the ones the mode calls for (see pipeline.md).

## FMEA — Failure Mode & Effects Analysis
Before committing to a plan/answer, list the ways it could be wrong or fail, and for each estimate: Severity, Likelihood, Detectability → RPN = S×L×D. Attack the highest-RPN items first. Every PoT program should carry a guard for its top failure mode (APEX SR_03/SR_07).

Use when: the answer has real consequences, or there are conflicting constraints.

## Ishikawa (fishbone) — root-cause analysis
For a problem/defect, enumerate candidate cause categories (method, data, tools, assumptions, environment, people) and trace each to a root cause instead of stopping at the first plausible one.

Use when: debugging, diagnosing why something went wrong, or explaining an outcome.

## Pareto — prioritization
Identify the ~20% of causes/levers responsible for ~80% of the effect and focus there. Prevents spreading effort thin.

Use when: many options compete and you need to sequence them.

## DSM — Design Structure Matrix — coupling
Lay out the components/steps as a matrix of dependencies to reveal coupling and ordering (what must precede what; where cycles exist). In SCIENTIFIC mode this guards hypothesis dependencies (APEX SR_32: dependency DAG must stay acyclic).

Use when: the problem has many interdependent parts and order matters.

## How they combine
Ishikawa finds *why*, Pareto decides *what first*, FMEA guards *what could break*, DSM orders *what depends on what*. In DEEP/SCIENTIFIC, run them explicitly and record the results in the snapshot.
