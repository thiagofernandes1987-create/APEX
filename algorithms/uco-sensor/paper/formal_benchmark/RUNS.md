# Formal benchmark run ledger

## Final preregistered 1,000-repository run — 2026-09-19

Protocol state before launch:
- production-source paths only;
- historical development repositories excluded;
- >=14 pre-event path-touching commits screened before checkout;
- exact PR base -> merge/head boundary;
- neutral controls use real first-parent boundaries;
- controls matched to event diff magnitude;
- 5 nested arms A STATIC -> E GRANGER;
- repository-disjoint 60/20/20 split;
- >=500 effectively analyzed repositories required for formal status.

Pilot-2 result was used only as an operational/corpus-integrity gate. No UCO
thresholds, signatures, feature definitions or classifier hyperparameters were
changed from pilot performance.

The commit adding this ledger entry intentionally carries the workflow trigger
`[formal-bench-1000]` for the final run.
