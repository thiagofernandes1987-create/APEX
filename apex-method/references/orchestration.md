# Orchestration — the full APEX flow (`scripts/orchestrator.py`)

Single entry point that runs the flow exactly as intended.

## The flow

1. **EXPRESS CHECK** (`express_check`) — trivial input skips the whole pipeline.
   - Pure arithmetic ("2+2") is computed directly (safe AST, no eval) → answer, done.
   - Short one-line factual questions → answer directly, no pipeline bureaucracy.

2. **DISSECT BY DISCIPLINE** (`dissect`) — a hard problem is split into the disciplines it
   touches (engineering, frontend, security, data-ai, finance, math, science, legal, healthcare),
   using word-boundary keyword matching. Multiple disciplines ⇒ hard problem ⇒ deeper mode.

3. **ASSIGN SPECIALISTS** (`assign_specialists`) — each discipline gets a specialized
   **agent + its skills + diffs** via the gravity engine (`gravity.plan`), which also detects
   **gaps** and emits **skills.sh install requests** + **MCP** fallbacks per discipline.

4. **MODE** — SCIENTIFIC if math/science present; DEEP if multi-discipline; else STANDARD.

5. **PMI CONVERGENCE** (`pmi_converge`) — the PMI agent decides among candidate sub-answers:
   - **numeric candidates** → real convergence: agreement across independent solutions ×
     mean confidence = reliability (e.g. 3/3 agree, conf 0.85 → reliability 0.85).
   - **qualitative candidates** → transparent weighted vote of confidences, labeled
     "weighted-judgment (not physical Monte Carlo)" — honest about what the number means.

## Usage
```
python3 scripts/orchestrator.py "2+2"                     # -> EXPRESS, answer 4
python3 scripts/orchestrator.py "build a secure trading backend and value the portfolio"
# -> FULL_PIPELINE, disciplines [engineering, finance, ...], specialists per discipline
```
`orchestrator.run(task, candidates=[...])` also returns the PMI decision when candidate
sub-answers are supplied.

## Honest boundary
The orchestrator is a **method + routing scaffold**. The EXPRESS math and the numeric PMI
convergence are real computations. Discipline routing is lexical (word-boundary), so it is
good but not perfect. The qualitative PMI "convergence" is weighted judgment, not simulation.
