# Sprint AC-2 — Corpus Validation across 8 OSS Repositories

> Companion to `requests_report.md` (Sprint AC-1). Same methodology
> (`paper/corpus_runner.py`, GitHub API shadow-replay, 50-80 commits
> per repo, one representative core sub-directory each — see table
> below). Raw data: `paper/corpus_runs/{repo}_report.json`.
>
> **This round's most important result is negative**: it identifies a
> methodology flaw in AC-1's headline "precision" claim, found via a
> new control script (`paper/corpus_baseline_check.py`). Reporting it
> honestly rather than only the positive numbers is the point of this
> exercise.

## Corpus

| Repo | Subdir analyzed | Commits fetched | Local commits replayed | Files analyzed |
|---|---|---|---|---|
| `pallets/flask` | `src/flask` | 60 | 57 | 11 |
| `django/django` | `django/core/handlers` | 60 | 60 | 4 |
| `fastapi/fastapi` | `fastapi` | 60 | 50 | 3 |
| `matplotlib/matplotlib` | `lib/matplotlib/axes` | 60 | 54 | 2 |
| `celery/celery` | `celery/app` | 60 | 60 | 4 |
| `scrapy/scrapy` | `scrapy/core` | 60 | 24 | 4 |
| `pandas-dev/pandas` | `pandas/core/indexes` | 60 | 60 | 5 |
| `psf/requests` | `src/requests` (AC-1) | 80 | 80 | 11 |
| **Total** | | **460** | **445** | **44** |

## 1. Severity distribution — reach (E1)

**0 CRITICAL / 34 WARNING / 10 INFO across 44 files, 8 unrelated mature
codebases.**

This is consistent (UCO never over-fires CRITICAL on well-maintained
code) but it cuts both ways: zero CRITICAL across 44 files from 8
different teams/domains (web frameworks, async APIs, plotting, task
queues, crawling, dataframes, HTTP) could mean the classifier correctly
recognizes these as not-yet-critical, **or** it could mean the
CRITICAL threshold is calibrated too high to ever fire on real-world
code and only triggers on synthetic/injected pathological cases (as
used in the existing test suite). We have no positive-control repo in
this sample to distinguish the two — see "Recommendations".

## 2. Pattern diversity — a concern

| Pattern | Files | % of 44 |
|---|---|---|
| `COGNITIVE_COMPLEXITY_EXPLOSION` | 24 | 55% |
| `GOD_CLASS_FORMATION` | 7 | 16% |
| `TECH_DEBT_ACCUMULATION` | 3 | 7% |
| `AI_CODE_BOMB` | 3 | 7% |
| `DEAD_CODE_DRIFT` | 3 | 7% |
| `REFACTORING_IN_PROGRESS` | 2 | 5% |
| `DEPENDENCY_CYCLE_INTRODUCTION` | 1 | 2% |
| `LOOP_RISK_INTRODUCTION` | 1 | 2% |

More than half of all flagged files across 8 structurally different
codebases got the *same* primary classification. That's either a
genuinely common failure mode in mature OSS (plausible — large old
modules accumulate cognitive complexity almost universally) or a sign
that `FrequencyEngine`'s classifier has a strong prior/attractor toward
this one pattern and under-discriminates the others. Can't tell which
from this data alone; flagging as an open question for Sprint AC-3 or
a dedicated classifier-calibration audit.

## 3. SAST point-in-time findings (E4, partial)

132 total findings across 8 repos' latest snapshots, 0 HIGH/CRITICAL,
no manual false-positive triage performed yet (still the single biggest
gap vs. the full `experiments.md` E4 protocol — needs human review of
a 20-sample to produce a real precision number).

## 4. Onset → fix correlation: **methodology correction**

AC-1 reported "3/3 (100%) of resolved onset commits have a real fix
commit within 15 commits downstream" as evidence the onset signal is
meaningful. Scaling to 8 repos: **20/20 (100%) still corroborate** —
which initially looks like a strong result, but a new control check
(`corpus_baseline_check.py`) shows it isn't:

| Check | Result |
|---|---|
| P(any random 15-commit window on the file contains a fix-like commit) | **94–100%** in every repo |
| Mean distance-to-nearest-fix, anchored at UCO onset commits | 2.5 commits (n=20, pooled) |
| Mean distance-to-nearest-fix, anchored at random commits (control) | 1.2 commits (n=20, pooled) |
| Onset beats random control | **False in 5/7 measurable repos** |

In other words: in an actively maintained repo, a fix-like commit
(loose keyword match: fix/bug/error/regression/etc.) shows up within 15
commits of *almost any* starting point — including random ones, which
were on average *closer* to a fix-commit than UCO's onset points. The
"100%" correlation is mostly measuring the base rate of the corpus, not
a property of UCO's onset detection. **AC-1's framing of this as
evidence of precision should be retracted** — it isn't wrong data, it's
an uninformative metric.

This is a real, useful finding from this round: it shows the
*difference* between "the number looks good" and "the number means
something," and prevents shipping an overclaimed precision metric into
the paper's E1/E4 tables.

## Recommendations for Sprint AC-3

1. **Fix or retire the onset-fix correlation metric.** Either (a)
   tighten the keyword list and require it to be specific to the
   flagged pattern category (e.g. "complexity"/"refactor"/"simplify"
   for `COGNITIVE_COMPLEXITY_EXPLOSION`, not generic "fix"), or (b)
   anchor on structured signals (linked GitHub Issues/PRs, CVE
   references) instead of commit-message keywords, or (c) run a proper
   statistical test (permutation test against many random anchors, not
   N=1 sample) with a reported p-value instead of a raw count.
2. **Add a positive control.** Run the same pipeline against a
   repository/snapshot with a *known*, well-documented severe defect
   (e.g. a historical CVE-introducing commit in a smaller project) to
   check whether CRITICAL ever fires at all outside synthetic tests.
3. **Manual triage of the 132 SAST findings** (or a 20-sample) to get
   a real false-positive rate — this is the actual missing piece of
   protocol E4's Table T4.
4. **Investigate the COGNITIVE_COMPLEXITY_EXPLOSION concentration** —
   either via FrequencyEngine threshold/feature review, or by checking
   whether the 96-channel extended vectors (not used by this MVP,
   which only feeds the 9 canonical channels via lang_adapters) would
   diversify the classification.

## What this round validates

* The shadow-replay method (GitHub API → local git → existing
  `GitHistoryScanner`/`sast.scanner`, zero modification to sensor
  code) works reliably across 8 structurally different repos, 460
  upstream commits, with no crashes after the one bug fixed in AC-1.
* UCO Sensor never produced a CRITICAL false-alarm storm or crashed on
  any of the 44 real-world files across very different domains —
  basic robustness validated at this scale.
* The corpus-runner + baseline-check pair is reusable infrastructure
  for future rounds, not a one-off script.
