# UCO Sensor — Experimental Protocol (Sprint Z, v3.9.0)

> Companion to `paper/paper.tex` Section "Evaluation".  The protocol
> below is reproducible via `paper/reproducibility.py`; rerunning the
> script regenerates every table and figure cited in the paper.

## Corpus

Five Python OSS repositories with longitudinal git history:

| Repo | Reason | Snapshot range |
|---|---|---|
| `flask` | Mature, mid-size, well-instrumented test suite | first 200 commits 2021-2023 |
| `django` | Large, multi-team, multi-decade | first 500 commits 2019-2024 |
| `requests` | Documented "god class" anti-pattern in `sessions.py` (validates Sprint Q HMC repair) | first 200 commits 2018-2024 |
| TBD-4 | (numpy or pandas — pick by indexing complexity) | TBD |
| TBD-5 | (small library with known regression) | TBD |

## Metrics extracted per snapshot

The 9 canonical channels (Sprint H, `governance/channels.py`):
hamiltonian, cyclomatic_complexity, infinite_loop_risk, dsm_density,
dsm_cyclic_ratio, dependency_instability, syntactic_dead_code,
duplicate_block_count, halstead_bugs.

Plus extended: 96 channels via `metrics/extended_vectors.py`.

## Experiments

### E1 — Invariant violations during natural evolution

For each repo, ingest every commit; check Invariants I1-I5 at each
step.  Hypothesis: in natural evolution, I3 (HMC convergence) and I4
(propagation symmetry) hold with probability $\geq 0.99$.

Table T1: invariant satisfaction rate per repo per invariant.

### E2 — HMC repair quality on degraded snippets

For 50 hand-selected functions per repo (flagged by SAST as HIGH/CRIT),
run `hmc_repair(source, preserve_aps=True)` and measure:
- patch acceptance rate (status="OK")
- mean $\Delta H = H_{\text{final}} - H_{\text{initial}}$ (Invariant I3)
- mean $\Delta\text{APS}$
- finding regression count (Invariant I2)

Table T2: HMC repair stats per repo.

### E3 — Multi-tenant billing throughput

Benchmark `check_and_charge` (atomic chokepoint, Sprint Y SY-FIX-4)
under 1, 10, 50 concurrent threads.  Hypothesis: linear scaling up to
the SnapshotStore `_lock` ceiling.

Table T3: throughput (events/sec) by concurrency.

### E4 — Comparison against baselines

For each repo, count findings reported by:
- UCO Sensor (`/sast` + `/scan-incremental` + spectral signatures)
- SonarQube (CLI mode)
- CodeQL (query suite `python-security-extended`)
- Semgrep (registry `p/python`)

Table T4: total findings + unique-to-UCO Sensor count + false-positive
estimate via manual review of 20-sample.

## Reproducibility

Single-command regeneration:

```bash
python paper/reproducibility.py --output paper/tables/
```

Output: CSV per table, suitable for LaTeX inclusion via `\input{...}`.

### v3.9.0 status (skeleton release)

The current `reproducibility.py` produces **synthetic** rows for T1
(11 hand-crafted invariant cases) and **toy** rows for T2
(`def f(x): return x+1` × 10). T3 is real (in-process benchmark of the
`check_and_charge` chokepoint). T4 is a placeholder until corpus runs
land. Wiring the 5-repo corpus + replacing T1/T2 with corpus-derived
data is the v3.9.1 milestone (`paper/CORPUS_INTEGRATION.md` will
document the contract).

## Threats to validity

* **Corpus skew** — Python-only, 5 repos, mid-size; results may not
  generalize to multi-language monorepos.
* **HMC seed** — pre-Sprint W2 G2-1, the seed leaked globally; we
  validate post-fix that concurrent runs are independent.
* **Baseline configuration** — SonarQube/CodeQL/Semgrep tuned to
  "default" presets; aggressive custom rules can change the count.
