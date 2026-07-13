# APEX architecture — full macro map (from the complete audit)

Companion to the full autopsy (`auditoria.md`). Summarizes every subsystem so the skill
reflects the whole framework, including pieces earlier passes missed.

## Subsystems
- **Boot**: kernel (990 l, sha8-per-page), 111 pages `page_load`, semantic index (TF-IDF),
  superrepo boot (INDEX.md, max 50 skills/boot).
- **Rules**: 8 C (constitution: C4 [APPROX], C6 [BAYESIAN_UPDATE], C8 [FORMALISM_GATE]),
  44 SR, 18 G-guards (G6 trusted_domains), 7 H (H5 never-auto-apply). 130 OPPs.
- **Pipeline**: STEP_0..13 + STEP_SCI_01..10 + marketplace STEP_M1..M4 + STEP_P gate.
- **mental_interpreter** (v4): NL→structure intake at STEP_0/5/13; `n_final=min(n_num,n_rel)`.
- **Modes**: EXPRESS/FOGGY/DEEP/SCIENTIFIC/RESEARCH (token + agent caps).
- **Agents**: 183 (10 community categories + native + cs_*).
- **Bayesian layer**: beta_binomial/normal_vi/hmc; Omega {0.72/0.5}; R_acum product window-20,
  gates 0.50/0.30 (MCFEReliabilityMonitor). → `scripts/bayes.py`.
- **Reasoning exec**: PoT, FractalDecomposer, **hypothesis_dag** (DFS acyclicity),
  chaos_spawn. → `scripts/hypothesis_dag.py`.
- **Quality**: UCO (9-channel spectral, nativized), UCO-Sensor (OSV/SCA, taint, SAST, IaC,
  lang_adapters, governance, HMC repair — 9 engines), sympy formal.
- **Skills/attraction**: **`meta/anchors.yaml` Anchor Registry + attraction_engine** — the REAL
  gravity is anchor-overlap (more precise than the TF-IDF in `gravity.py`); skill_forge;
  resolution_cache; 3,784 native skills; 1,561 ingested (antigravity v3).
- **Evolution/learning**: **code_genetics/vaccines** (error→fix, O(1), rollback, promote at
  >0.85), crystallization_jit (class thresholds), hierarchical Bayesian, diffs (FMEA/RPN).
  → `scripts/code_genetics.py`.
- **Security**: trusted_domains, SR_37 AST-scan, H5. ⚠️ V-01 `apex-marketplace` claimable,
  V-02 pickle RCE, V-03 httpbin probe (see auditoria.md).
- **MCP**: 18 servers by domain; `meta/llm_compat.yaml` (Claude/GPT/Gemini).

## Newly nativized this pass
- `scripts/hypothesis_dag.py` — acyclic hypothesis graph (SR_32), edge-only serialization.
- `scripts/code_genetics.py` — vaccine store (error→fix, O(1), promote >0.85 after ≥2 uses).

## Known honest gap
`gravity.py` uses TF-IDF; APEX's real `attraction_engine` uses **anchor overlap** from
`meta/anchors.yaml` (sharper, language-independent). A future pass should load that registry.

## Complete module registry (deep-dive pass)

`catalog/module_registry.json` — all **111 boot-page modules** with executor + one-line purpose.
Notable modules surfaced in the deep dive:
- **semantic_gravity_engine** (tier 0, OPP-169) — the REAL gravity: TF-IDF+cosine on 3 corpora.
  This VALIDATES `gravity.py`'s TF-IDF approach (embeddings were inexecutable = "vibed gravity"
  at 38% coverage). Thresholds now calibrated to the real values: attraction_radius 0.12,
  relaxed 0.06, neighbor_coload > 0.7×max. Anchors are a complementary L3 curated layer.
- **skill_hierarchy** — the formal gravitational chain: Agent → Generic Skills → Specialized
  Skills → Knowledge Models.
- **mental_interpreter_v4** — the execution orchestrator (see mental_interpreter.md).
- **geodesic_scheduler** (ΔH/tokens step ordering), **geometry_estimator** (adaptive DELTA_ERR),
  **fractal_hypothesis_compression** / **fractal_knowledge_indexing** (fractal level mgmt),
  **merge_defensive** (isolate speculative failures), **monte_carlo_simulator** (real
  distributions), **external_critic_profile** (break circular self-eval), **ethical_barrier**
  (ethics as geodesic cost), **verification_gate** (P≠NP: invert generate/verify ratio),
  **sklearn_self_difficulty** (competence self-awareness), **apex_st_metric** (inter-session
  progress as distance in information space).
