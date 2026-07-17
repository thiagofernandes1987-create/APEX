# Bayesian layer (`scripts/bayes.py`) — APEX bayesian_curator, made computable

The APEX kernel specifies a real probabilistic framework that was executed as `LLM_BEHAVIOR`
(the bayesian_curator estimated it in-context). This module computes it exactly. Parameters
are taken verbatim from `kernel.defaults.bayesian` and the SR_10 reliability gate.

## What was in the prompt (verified in the master kernel)
- Model classes: `beta_binomial` (class_1), `normal_vi` (class_2), `hmc_cognitive` (class_3).
- `learning_rate: 0.05`, `filter_threshold: 0.4`.
- **Omega thresholds** `{adopt: 0.72, review: 0.5}` — decision over the posterior.
- Hierarchical updating cadence (every session / every 10 / every 30).
- **R_acum** (SR_10): accumulated reliability = **product of per-block reliabilities over a
  sliding window N=20**, with `p_eff = p_base + α·ε`; gates **< 0.50 → replan**,
  **< 0.30 → EARLY_EXIT (PARTIAL)**. Enforced by MCFEReliabilityMonitor.

## What this module computes (all verified against hand math)
- `beta_binomial_update(a,b,successes,trials)` — conjugate posterior Beta(a+k, b+n-k), mean,
  sd, 90% CI. (Beta(1,1)+8/10 → mean 0.75, exact.)
- `omega_decision(mean)` — ADOPT ≥0.72 / REVIEW ≥0.5 / REJECT.
- `posterior_over_hypotheses(priors, likelihoods)` — P(H|E) ∝ P(E|H)·P(H), normalized;
  dominant hypothesis + Shannon entropy + Omega decision. (A=0.741 dominant, exact.)
- `filter_priors(components, 0.4)` — G5: drop weak priors before resolution.
- `r_acum(reliabilities, window=20)` — the reliability product + gate status/action.

## How it's wired
`orchestrator.pmi_converge` now uses this layer: numeric candidates → real agreement×confidence;
qualitative candidates → a **real Bayesian posterior** over answers (confidence as likelihood,
uniform prior) + the **Omega decision**; and **R_acum** gates the whole result (a run of only
moderately-confident blocks multiplies to low reliability and triggers EARLY_EXIT — faithful to
APEX's conservative design).

## Honest boundary
The MATH is exact and verifiable. The BELIEFS fed in (priors, likelihoods, per-block
confidences) are supplied by the LLM's judgment — so the posterior is only as good as those
inputs. That's the honest division: computation is real; the degrees of belief are estimates.
