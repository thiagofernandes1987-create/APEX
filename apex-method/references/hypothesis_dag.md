# hypothesis_dag (deep dive)

APEX `hypothesis_dag` (v00.32.1, OPP-MAS-01, SR_32). Faithful port in
`scripts/hypothesis_dag.py`.

## What it does
A directed ACYCLIC graph of dependencies among hypotheses, anchors, and findings. When an
anchor/premise is destroyed, invalidation **cascades to all dependents** — so orphan
hypotheses don't survive after their premises are refuted (a real failure mode of dense LLM
sessions where the model can't track every dependency).

## Algorithms (faithful to spec)
- **Cascade**: BFS **O(V+E) with a mandatory visited_set** (without it, high fan-out reprocesses
  nodes → O(V×fanout)).
- **Acyclicity**: DFS **before** inserting an edge; a cycle A→B→A would make the cascade
  non-terminating, so the edge is rejected with `[DAG_CYCLE_REJECTED]`.
- **Snapshot**: edge-only `{edges:[{src,dst,type}], suspects, invalidated}` — nodes live in the
  hypothesis_tracker (context), so serialization is ~15-30 tokens vs 8000-15000 (-99%).

## API
`register(node_id, node_type, anchors_used, phase, confidence)` · `add_edge(src, dst, type)`
(False if it would cycle) · `invalidate_cascade(node_id)` → affected set ·
`compress_for_snapshot()`.

## Fallbacks
cycle → reject + `[DAG_CYCLE_REJECTED]`; >200 nodes → reset + `[DAG_RESET]`; tracker
unavailable → `[DAG_UNAVAILABLE]` (pipeline continues without cascade). FMEA RPN 6.
