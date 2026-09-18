# UCO-Sensor Formal Benchmark — preregistration v0.1

**Status:** protocol frozen before the large-scale run.  
**Target:** 1,000 distinct public GitHub repositories (minimum 500; hard cap 2,000).  
**Primary unit of independence:** repository, not file or transition.

> **Protocol amendment v0.2 — before any formal performance result was
> inspected.** The 100-repository operational pilot was used only to inspect
> corpus availability/plumbing. It showed (a) test files leaking through path
> filters and (b) insufficient temporal depth in many selected paths. Before the
> formal held-out run, the corpus definition was therefore tightened to exclude
> test-like paths, require >=14 pre-event path-touching commits, match controls
> by diff magnitude, and exclude all historical development-corpus repositories.
> No UCO AUPRC/AUROC/F1 result informed these changes.

## Research question

Does each temporal/scientific layer add out-of-sample information beyond the
simpler UCO configuration?

Nested arms:

| Arm | Features available |
|---|---|
| A — STATIC | before/after UCO static vectors, UCO quick-score delta, SAST severity deltas |
| B — +HISTORY | A + raw 9-channel OLS slopes, endpoint deltas, volatility |
| C — +SPECTRAL | B + Welch/STFT/wavelet/spectral-signature features |
| D — +CHANGEPOINT | C + exact penalized change-point evidence |
| E — +GRANGER | D + multiplicity-corrected Granger features |

The statistical classifier used to compare arms is deliberately the same
regularized logistic regression for all arms. Only the available feature set
changes. This prevents a more flexible downstream learner from being confused
with a better UCO signal.

## Event strata / ground truth

Primary corpus uses merged GitHub PRs with an explicit transition boundary:

1. **security** — CVE/GHSA in title or security-labelled PR;
2. **bugfix** — merged PR carrying a bug label;
3. **regression** — merged PR explicitly titled/labelled regression;
4. **refactor** — merged PR explicitly titled/labelled refactor;
5. **revert** — merged PR explicitly titled revert.

For every event, the exact PR base SHA and merge/head SHA define the known
boundary. The post-PR snapshot is appended explicitly as the final positive
time-series sample, so localization ground truth does not depend on Git merge
path simplification. At most one primary event per repository is used in the
principal analysis so a large monorepo cannot dominate the statistics.

Test/fixture/generated paths are excluded. PRs with more than 50 changed files
are excluded from the primary corpus; among eligible production-source files,
the largest bounded source delta (<=800 changed lines) is selected, then
negative controls are matched to its change magnitude.

Commit-message-only generic "fix" cases are **bronze** evidence and excluded
from the primary table; they may appear only in sensitivity analysis.

Known CVE fixtures already used to create/calibrate UCO rules (the historical
19-case capstone corpus) are **engineering/dev fixtures only**. Their source
repositories are excluded entirely from formal discovery, not merely the exact
CVE tuples, to make leakage control conservative.

## Controls

Each positive transition gets up to two matched negative boundaries from the
same file/repository history:

- same language and **same file**;
- a control is the real first-parent boundary `parent(commit) → commit`;
- outside ±5 path-touching commits from the labelled event;
- commit subject must not match security/fix/bug/regression/refactor/revert
  keywords;
- candidates are ranked by similarity of changed-line magnitude to the event,
  using `|log1p(lines_control) - log1p(lines_event)|`;
- controls are therefore deterministic and **size-matched**, preventing a
  trivial "large PR vs ordinary small commit" confound.

This directly addresses the AC-2 failure mode where almost any random
15-commit window happened to contain a "fix-like" commit.

## Split and leakage control

Split is deterministic by SHA-256(repo):

- train: buckets 0–5 (60%)
- development: buckets 6–7 (20%)
- test: buckets 8–9 (20%)

All events/controls from one repository stay in one split. Threshold selection
uses development only. The test split is evaluated once per frozen benchmark
commit.

The historical 19-case corpus is tagged `seed_dev=true` and is never eligible
for test metrics.

## Complete-case rule

The primary five-arm table is paired and includes only repositories with enough
valid history for **all five arms and at least one matched control**. Granger
`max_lag=3` needs 9 analyzed snapshots (`2*k+3`), while the ±5-commit
exclusion around the labelled event and the control-history requirement imply a
stricter corpus eligibility gate of **at least 14 pre-event path-touching
commits**. This depth is screened before expensive checkout/analysis.
Repositories that cannot satisfy it remain outside the formal manifest rather
than silently entering only the simpler arms.

A secondary sensitivity analysis may later report A–D on shorter histories,
but it cannot be mixed into the primary A–E headline table.

## Primary metrics

For transition-vs-control discrimination:

- **AUPRC** — primary metric;
- AUROC — secondary;
- F1 / precision / recall at threshold selected on DEV;
- Brier score for probability calibration;
- false-positive rate on matched controls.

For known-boundary localization (positive events only):

- median absolute commit error;
- Hit@1, Hit@3, Hit@5;
- no-onset rate.

Operational metrics:

- analysis wall time / event;
- clone/fetch failures;
- unsupported-language rate.

## Statistical inference

- 95% confidence intervals from repository-cluster bootstrap;
- all arm deltas are paired on the same held-out repositories;
- family of four incremental comparisons (B-A, C-B, D-C, E-D) is corrected
  with Holm-Bonferroni at alpha=0.05;
- report both statistical significance and effect size;
- no result is called an improvement when the CI for the paired delta crosses 0.

## Interpretation contract

- Spectral improvement means additional predictive information, not proof that
  software literally follows a physical process.
- Change-point accuracy is about localization of a documented repository
  transition.
- Granger is treated as a predictive lead/lag feature. Without an independently
  labelled causal channel, this benchmark does **not** establish causal truth.
- A negative ablation result is a valid result. Layers that do not improve
  held-out performance should be simplified, demoted to diagnostics, or removed.

## Scale gates

1. **Seed/dev smoke:** 19 historical CVE fixtures; validates plumbing only.
2. **Pilot:** >=100 previously unseen repositories.
3. **Formal minimum:** >=500 distinct repositories.
4. **Target:** 1,000 repositories.
5. **Expansion:** up to 2,000 only if failure rate <10% and strata remain
   sufficiently balanced.

The formal headline table MUST NOT use seed/dev smoke results.

## Execution gates

- Pilot-1 (legacy corpus selector): diagnostic only; not evidence.
- Pilot-2 must exercise the final corpus selector (production paths, temporal
  depth screen, size-matched controls) before the formal 1,000-repository run.
- No UCO thresholds, signatures, or model hyperparameters may be changed from
  Pilot-2 performance. Only execution/corpus-integrity bugs may be fixed.
