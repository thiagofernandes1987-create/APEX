# fractal_hypothesis_compression · geometry_estimator · apex_st_metric

## fractal_compression (`scripts/fractal_compression.py`)
Prunes the hypothesis space at each fractal-level transition (after STEP_5, before MCFE
recomputes H). Four filters: **dominance** (H_A beats H_B by >10 conf, >= evidence, uncontradicted),
**similarity_merge** (jaccard of anchors > 0.80 AND conf diff < 15 -> merge, max+5),
**skill_refutation** (skill-pruned -> -20 conf; < 40 -> refuted), **absurdity_prune** (invariant
violation -> discard). Never drops below 2 hypotheses. In: hypotheses[{id,confidence,evidence_level,
anchors}], pruned_by_skill{id->reason}. Out: {kept, report [FHC:...], events}.

## geometry_estimator (`scripts/geometry_estimator.py`)
Adaptive numerical error per block via **step-doubling**: DELTA_ERR = |integrator(dt) -
integrator(dt/2 twice)| x 0.1. optimal_block_size = eps/(DELTA_ERR x |x|) clamped [5,30]. This is
the **n_num** that bounds mental_interpreter's n_final. Verified: RK4 err ~8.9e-8 -> block 30;
Euler err ~8.4e-4 -> block 5 (Euler less precise, smaller safe block).

## apex_st_metric (`scripts/apex_st_metric.py`)
Inter-session progress as distance in information space: **dS2 = a|dMCFE|2 + b|dInfo|2 + g|dCoh|2**
(a=1.0, b=0.5, g=0.8), ALL POSITIVE (a distance, not a displacement — fixes the PATCH_C6 sign bug
where -g|dCoh|2 made coherence reduce progress). Curvature: FLAT<0.02 (stagnation, trigger
meta_learning if 2+ consecutive), LOW<0.10, MEDIUM<0.30, HIGH>=0.30. In: prev/curr snapshot
{mcfe,info,coh}. Out: {dS2, curvature, trigger_meta_learning}.
