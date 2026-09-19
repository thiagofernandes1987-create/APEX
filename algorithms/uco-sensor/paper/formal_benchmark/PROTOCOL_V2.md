# UCO-Sensor Formal Benchmark v2 — isolated-signal preregistration

**Frozen before inspecting any v2 performance result.**

## Why v2 exists

Audit of v1 found four confounds/omissions:

- variable history length leaked label information through `history.n` and spectral resolution;
- 84% of v1 rows were in NANO/SPARSE bands where UCO itself marks spectral classification invalid;
- PELT was evaluated at the final sample even though it requires observations on both sides of a breakpoint;
- full spectral evidence (STFT, wavelets, cross-channel coherence/phase, signature identity) was computed but not exported.

V2 changes experiment design, not UCO thresholds, based on those methodological findings.

## Unit of analysis

File-level code transition. A PR is eligible only when exactly **one production source file** is eligible after excluding tests, fixtures, generated/vendor code and oversized source diffs.

Dependency-only/SCA events are not represented by a random source file. They belong to a separate security/SCA benchmark.

## Corpus eligibility

- one primary event per repository;
- repository-disjoint deterministic 60/20/20 train/dev/test split;
- historical 19-case development repositories excluded from formal discovery;
- at least **50 pre-event path-touching commits** available;
- event and every control must yield exactly **40 analyzable snapshots**;
- at least one same-file neutral control matched by changed-line magnitude;
- control subject excludes security/fix/bug/regression/refactor/revert keywords;
- controls remain outside ±5 path-touching commits from the labelled event.

## Fixed N

All five primary arms use N=40 exactly. The sample count is **not a model feature**.

N=40 is the first UCO `THIN` band and therefore spectrally valid according to the existing adaptive calibration. Hurst remains excluded because its independent reliability gate is N>=64. A future Hurst-specific benchmark must use a separate fixed-N>=64 corpus.

## Primary ablation

| Arm | Evidence |
|---|---|
| A_STRUCTURAL_STATIC | before/after UCO structural metrics + SAST for the single source file |
| B_HISTORY_FIXED40 | A + slopes/deltas/volatility over the same 40 snapshots |
| C_SPECTRAL_FULL | B + full fixed-N spectral summaries: Welch bands, WFM/shift, norm area, STFT summaries, wavelets, temporal pattern, cross-channel coherence/phase, signature confidences/top identity/margin |
| D_ENDPOINT_CHANGE | C + robust last-snapshot deviation detector; **not PELT** |
| E_GRANGER_DIFF | D + Granger on first-differenced channel series with lag Bonferroni + matrix BH-FDR and stable log representations |

The same L2-regularized logistic regression is used in every arm. Only available evidence changes.

## Change-point separation

Retrospective PELT localization is **not** part of the A→E classification benchmark. PELT requires samples on both sides of a candidate boundary and will receive a separate symmetric pre/post-event localization experiment.

## Metrics

Primary: held-out AUPRC.

Secondary: AUROC, F1, precision, recall, FPR, Brier score.

Incremental comparisons: B-A, C-B, D-C, E-D with repository-cluster bootstrap 95% CI and Holm-Bonferroni correction.

## Integrity gates

A result is formal only if:

- >=500 repositories remain after complete-case filtering;
- every retained row has N=40;
- each retained repository has exactly one positive and >=1 control;
- no seed/dev repository enters the formal corpus;
- v2 pilot runs do not change UCO thresholds/hyperparameters after observing performance.

## Interpretation

- spectral gain means incremental predictive information, not literal physical causation;
- endpoint-change scores are effect sizes, not probabilities;
- Granger means predictive lead/lag evidence, not independently established causality;
- a null/negative layer result is valid and should trigger simplification rather than threshold chasing.
