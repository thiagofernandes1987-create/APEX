# UCO Sensor — Inventário Persistente de Auditoria APEX SCIENTIFIC

> Documento durável entre sessões. Tracking de TODAS as ações da auditoria
> profunda + fixes + verificações.  Atualizar a cada step concluído.

---

## ⚠️ Standing instructions (ler ANTES de qualquer trabalho)

Instruções permanentes registradas pelo usuário — **sempre obedecer**, nesta
ordem, em toda sessão futura:

1. **APEX SCIENTIFIC pleno por default** (`/loop` de sessões anteriores) —
   DSM + Ishikawa + Pareto 80/20 + FMEA antes de toda decisão não-trivial;
   uso de **workflows multi-agente** (design panel + multi-dim review +
   adversarial verify) onde a complexidade justifica.
2. **Sempre re-ler este inventário ANTES de iniciar trabalho em nova sessão.**
   Procurar última task in-progress + última versão entregue + checklists
   abertos. Nunca pular fases.
3. **Todo horizonte/sprint começa com WBS + checklist explícito** (seção
   "Sprint NN — WBS" abaixo). Atualizar a cada step concluído.
4. **Achados novos entram no checklist do sprint correspondente** (ou criam
   sub-checklist) — nunca soltos. Se gerar > 30 items, criar checklist
   macro com ponteiros para per-sprint.
5. **Se teste falhar:** tentar continuar de onde parou. Se impossível,
   reiniciar a suíte completa e atualizar o checklist com motivo + step.
6. **Push direto para `main`** está bloqueado pela proxy policy 403 — sempre
   gerar bundle incremental e entregar via SendUserFile.

---

## Versão atual

**v3.9.1** (QA Loop 4-lentes + 2-round convergence — QA-FIX-1..6 + Round 2 migration sweep) ✅

---

## 📋 Macro checklist (horizonte 180d)

Todo horizonte tem um checklist macro + per-sprint detalhado. Quando
um sprint cresce > 30 items, ele vira sub-checklist linkado abaixo.

| Horizonte / Sprint | WBS | Status | Versão |
|---|---|---|---|
| **Horizonte 30d (entregue)** | Sprints K-P (PELT, Propagation, SAST feed, DBSCAN signatures) | ✅ | v3.4.1 |
| **Horizonte 90d (entregue)** | Sprints R, S, Q, T, U (RCA, Granger, HMC, VS Code, Cache/ASGI) | ✅ | v3.5.0 |
| **Gate-1 hardening (entregue)** | Sprint W (audit-1..6) | ✅ | v3.5.1 |
| **Gate-2 deep audit (entregue)** | Sprint W2 (G2-1..G2-8 + stress) — [checklist gate-2](#gate-2-checklist) | ✅ | v3.5.2 |
| **Horizonte 180d (COMPLETO)** 🏁 | V (Marketplace) → X (CFG) → Y (SaaS multi-tenant) → Z (Paper + invariants) | ✅ 100% | v3.6.0 → v3.7.0 → v3.8.0 → v3.9.0 |
| **Sprint Z — Paper + invariants + v3.8.1** | [Checklist Z](#sprint-z-wbs) | ✅ | v3.9.0 |
| **v3.8.1 follow-up** | [Backlog Workflow #2](#v381-backlog) — 5/6 fechados em v3.9.0 | ✅ | v3.9.0 (1 deferred → v3.9.2) |
| **v3.9.1 QA Loop** | 4-lentes (QA+Product+Eng+Security) × 2-round convergence — [Checklist QA Loop](#qa-loop-v391) | ✅ | v3.9.1 |
| **Sprint AA — UCO Deep Integration** | Integração total `algorithms/uco/` → uco-sensor — [Checklist AA](#sprint-aa-wbs) | 🔄 em andamento | v3.10.0 (alvo) |

## Equipe APEX (modo SCIENTIFIC)

| Papel | Função | Status |
|---|---|---|
| Tech Lead         | Orquestração + priorização                            | ✅ gate-1 + gate-2 |
| Architect         | Acoplamento, blast radius                              | ✅ gate-1 |
| Security Engineer | Auth, secrets, race conditions, ReDoS, path-traversal | ✅ gate-1 + gate-2 |
| Performance Eng.  | Hot paths, locks, N+1, cache invalidation              | ✅ gate-1 |
| Correctness Theor.| Bugs lógicos, sign conventions, off-by-one             | ✅ gate-2 (G2-1..G2-5) |
| Test Strategist   | Tautologias, mocks que escondem bugs, gaps            | ✅ gate-2 (G2-6/G2-7) |
| Dead Code Hunter  | Funções/imports nunca usados, branches mortos          | ✅ gate-2 (50 findings LOW, deferred) |
| Control Flow Anal.| Loops sem condição de saída, recursão sem base case   | ✅ gate-2 (2 findings LOW, deferred) |
| Wiring Auditor    | Paths hardcoded, env vars, sys.path manipulation       | ✅ gate-2 (G2-8 HIGH + 3 MED corrigidos) |
| Debugger          | Reproduce + corrigir cada finding                      | ✅ on demand |

---

## Checklist de auditoria

### Gate-1 (APEX Workflow #1 — Sprint W, v3.5.1) ✅

- [x] Baseline: 1901 tests passing, 39.781 LOC produção
- [x] Workflow 5-dim paralelo lançado (architect/security/performance/correctness/tests)
- [x] **6 CRITICAL/HIGH** confirmados e corrigidos:
  - [x] audit-1 CRITICAL — Auth bypass por default → `_authenticate` exige admin key sempre
  - [x] audit-2 HIGH — `hmc_repair._compute_aps` shadow formula → delegação à SSOT
  - [x] audit-3 HIGH — Channels duplicados granger+propagation → `governance/channels.py`
  - [x] audit-4 HIGH — `recompute_derived` leak target.actual → filtro estrito-prior
  - [x] audit-5 HIGH — Path-traversal feeds → `sensor_storage/path_jail.py`
  - [x] audit-6 HIGH — ReDoS injection sast rules → guard estático de quantificadores
- [x] 30 testes TF01-TF30 pinam cada fix
- [x] Regressão: 1931 tests passing, 0 falhas
- [x] Commit `cf8d7386` (v3.5.1)

### Gate-2 (APEX Workflow #2 — Sprint W2, v3.5.2) ✅

- [x] Workflow 5-dim paralelo lançado (correctness + tests + dead-code + control-flow + wiring)
- [x] Gate-2a (correctness/tests): 7 findings dedupe → 5 HIGH/MED corrigidos
- [x] Gate-2b (dead-code/control-flow/wiring relançado): 63 findings → 1 HIGH + 3 MED corrigidos
- [x] **8 HIGH/MEDIUM** confirmados e corrigidos:
  - [x] **G2-1** HIGH — `hmc_repair` numpy RNG state leak → save/restore via `get_state()`/`set_state()` em try/finally
  - [x] **G2-2** HIGH — `hmc_repair` broken summary access (dataclass) → helper `_summary_get()`
  - [x] **G2-3** HIGH — `hmc_repair` APS clip saturation → guard `_no_severity_regression()` defence-in-depth
  - [x] **G2-4** HIGH — `signals.predictor_accuracy` mean_h denominator mismatch → filtra subset
  - [x] **G2-5** HIGH — `granger_causality` rss_u≈0 silently skipped → handle noiseless causation
  - [x] **G2-6** MED — `tests/conftest.py` `isolated_store` opt-in fixture
  - [x] **G2-7** MED — `test_marco_m48.py` TJ11/TJ12/TJ16 vacuous-cond → unconditional asserts
  - [x] **G2-8** HIGH — `validation/analyze_real_history.py` hardcoded `/home/claude` → `__file__`-relative
- [x] 3 MEDIUM (env-var docs) corrigidos via README.md
- [x] 21 testes TG01-TG21 pinam cada fix gate-2
- [x] 30 testes TS01-TS30 stress + parameter sweep (signals/scanners/store/RCA)
- [x] Regressão: 1992 tests passing (+61), 0 falhas
- [x] CHANGELOG.md atualizado com seção [3.5.2]
- [x] Bump pyproject.toml + api/server.py para 3.5.2

---

## Findings deferred (LOW — Sprint V/X)

| Categoria | Count | Disposição |
|---|---|---|
| unused-import                | 42 | Sweep automatizado em Sprint V (ruff `F401`) |
| orphan-method (constructors) | 7  | Documentar como public-API ou remover em Sprint V |
| undocumented_env_var (LOW)   | 2  | Já cobertos pela seção README de v3.5.2 |
| syspath_mutation (defensive) | 2  | Refator para `importlib` em Sprint X |
| orphan-class                 | 1  | `UCOUnusedVarTransformer` removal em Sprint V |
| silent thread death loop     | 1  | `cache.py` background thread → adicionar restart-on-die |
| sleep-based polling          | 1  | Substituir por `Event.wait()` em Sprint V |
| hardcoded_host (test only)   | 1  | OK em testes (`127.0.0.1`), deferred |
| hardcoded_port               | 1  | Substituir por port-allocator em Sprint X |
| hardcoded_path_docs          | 1  | Docs apenas; deferred |

**Total LOW deferred:** 59 — todos triados, nenhum bloqueia o horizonte 180d.

---

## Quick-wins de alto ROI identificados (próximo sprint)

| Item | Estimativa | ROI | Notas |
|---|---|---|---|
| Cache `predictor_accuracy` outputs (cache TTL ~5s) | 1h | Alto | endpoint hot path em dashboards |
| Background-thread restart wrapper em `cache.py`     | 2h | Alto | finding gate-2b; resiliência operacional |
| `Event.wait()` no consumer loop em vez de `sleep`   | 1h | Médio | redução de latência ~50ms p99 |
| Sweep `ruff F401` para 42 unused-imports            | 30min | Médio | -200 LOC, melhora coverage signal |
| Remover 7 orphan classmethod constructors           | 1h | Médio | dead code drift fechado |
| Port-allocator nos testes (em vez de 19084 hard)   | 1h | Médio | habilita testes paralelos via xdist |

---

## Métricas finais de qualidade

| Métrica | Antes gate-1 | Após gate-1 | **Após gate-2 (v3.5.2)** |
|---|---|---|---|
| Tests passing            | 1901  | 1931 | **1992** (+91 total) |
| Falhas                   | 0     | 0    | **0** |
| LOC produção             | 39.781| 40.592 | ~40.900 |
| CRITICAL findings        | 1 conf| 0    | **0** |
| HIGH findings            | 5 conf| 0    | **0** |
| MEDIUM findings backlog  | 26    | 26   | 23 (-3 fechados via README) |
| LOW findings backlog     | n/a   | n/a  | 59 (triados, deferred) |
| Cobertura módulos audit  | 7     | 7    | 14 (signals + granger + hmc + iac + sast + store + RCA + propagation + changepoints + conftest + validation + …) |

---

## Decisões científicas registradas

1. **Gate-1 deferiu Postgres adapter** para Sprint W via FMEA (80% perf gain do cache, não do storage).
2. **Path-jail closed-by-default** — sem `UCO_FEEDS_DIR`, todo file-load rejeitado.
3. **Admin endpoints SEMPRE exigem `UCO_ADMIN_KEY`** independente de `auth_enabled`.
4. **HMC `preserve_aps=True` por default** + APS canônico via SSOT.
5. **G2-1 save/restore numpy RNG** > thread-local RNG (minimally-invasive; preserva API do UCO core).
6. **G2-6 isolated_store é opt-in** — autouse fixture quebrava 3 legacy tests que `import _store` direto; opt-in via marker é minimamente invasivo.
7. **LOW findings (59) deferred para Sprint V** — não bloqueiam horizonte 180 dias; sweep automatizável.
8. **MEDIUM/LOW deferred para Sprint V** — não bloqueiam horizonte 180 dias.

---

## Próximos sprints (horizonte 180 dias) — 🏁 COMPLETO

| Sprint | Foco | Status |
|---|---|---|
| **V** | Marketplace de spectral signatures (Movimento #5 expandido) | **✅ v3.6.0** |
| **X** | CFG visualizável + hotspot overlay + port-allocator nos testes | **✅ v3.7.0** |
| **Y** ⭐ | SaaS multi-tenant + billing (APEX SCIENTIFIC pleno) | **✅ v3.8.0** |
| **Z** 🏁 | Paper POPL/PLDI skeleton + 5 formal invariants + v3.8.1 backlog | **✅ v3.9.0** |

### Próximo horizonte (sugestões — aguardar direção do usuário)

| Versão | Foco proposto |
|---|---|
| v3.9.1 | Corpus integration (5 OSS repos reais; T1/T2 reproducibility com dados reais; baselines T4 SonarQube/CodeQL/Semgrep/Infer) |
| v3.9.2 | Hot-row contention fix (sharded counters em `tenants.units_used`) |
| v4.0.0 | Multi-language SAST expansion (Ruby, Rust, Kotlin, Swift via tree-sitter) |
| v4.1.0 | Real-time SSE dashboard sobre `governance/*` |

---

## Sprint Y (v3.8.0) — APEX SCIENTIFIC pleno

### Workflows multi-agente executados

| # | Tipo | Saída |
|---|---|---|
| #1 | Design panel | 3 MVPs avaliados; vencedor `unit-budget-billing` 82/100 STRONG_PICK; síntese final grafted ideas de runners-up (`BYPASS_TENANTS` hardcoded, `TenantSuspended` exception, `Retry-After` header) |
| #2 | Multi-dim review (security/correctness/perf) com 2-vote adversarial verify | 27 raw findings; 2 CRITICAL + 2 HIGH 2/2-verificados → SY-FIX-1..7 aplicados em mesma release |

### Fixes aplicados nesta release

| ID | Severidade | Onde | Issue |
|---|---|---|---|
| SY-FIX-1 | CRIT | snapshot_store.validate_key | Não retornava tenant_id → todo auth virava bypass |
| SY-FIX-2 | HIGH | snapshot_store.create_key | Sem parâmetro tenant_id |
| SY-FIX-3 | CRIT | api/server.py | check_and_charge nunca chamado dos handlers |
| SY-FIX-4 | HIGH | billing.check_and_charge | TOCTOU race → atomic_check_and_charge novo |
| SY-FIX-5 | MED | tenancy.update_tenant | BYPASS_TENANTS invariant quebrável via PATCH |
| SY-FIX-6 | HIGH | billing.check_quota | unit_budget=0 em non-ENT virava ilimitado |
| SY-FIX-7 | HIGH | billing.reset_period_if_rolled | Race entre concurrent rollers |

### Deferred para v3.8.1 (achados Workflow #2 não-bloqueantes)

* Expand billing wiring para 16 handlers billable restantes
* N+1 em list_usage_periods (12 round-trips por chamada)
* Hot-row contention em tenants.units_used
* Index coverage gaps em usage_events reads
* prune_old_events sem VACUUM
* Soft-warn integer truncation

### Métricas pós-Sprint Y

| Métrica | v3.7.0 | **v3.8.0** |
|---|---|---|
| Tests passing | 2052 | **2089** (+37) |
| Falhas | 0 | **0** |
| Endpoints REST | 66+ | **76+** (+10) |
| Tables SQLite | 6 | **8** (+tenants, +usage_events) |
| CRITICAL findings ativos | 0 | **0** (2 found + 2 fixed na mesma release) |
| HIGH findings ativos | 0 | **0** (4 found + 4 fixed) |

---

<a id="gate-2-checklist"></a>
## Gate-2 — checklist detalhado (v3.5.2, executado)

WBS executado:
- [x] Workflow APEX gate-2 (5 dimensões em paralelo)
- [x] Coletar findings + dedupe + adversarial verify
- [x] Atualizar inventário com findings
- [x] Implementar fixes G2-1..G2-8 (3 HIGH `hmc_repair`, 2 HIGH `signals`/`granger`, 2 MED `conftest`/`test_marco_m48`, 1 HIGH `validation`)
- [x] Testes TG01-TG21 (gate-2 pins)
- [x] Testes TS01-TS30 (stress + parameter sweep)
- [x] Regressão zero falhas
- [x] CHANGELOG + commit `e3beab13`

---

<a id="sprint-z-wbs"></a>
## Sprint Z (v3.9.0) — WBS executado ✅

Foco: **Paper POPL/PLDI submission** + v3.8.1 backlog fixes (empacotados juntos).

WBS executado:
- [x] APEX SCIENTIFIC scoping inline (DSM/Ishikawa/Pareto/FMEA registrado em chat)
- [x] (Workflow #1 design panel **dispensado** — estrutura de paper é well-understood, não justificava agentes; decisão registrada)
- [x] Implementação:
  - [x] `paper/paper.tex` — LaTeX skeleton ACM article (sections, theorem env, bibliography)
  - [x] `paper/references.bib` — 7 entries skeleton (SonarQube, CodeQL, Infer, Neal HMC, Granger, PELT, Welch)
  - [x] `paper/experiments.md` — protocolo reprodutível para E1-E4 sobre corpus 5 OSS
  - [x] `paper/reproducibility.py` — script standalone que regenera T1/T2/T3/T4 CSVs
  - [x] `governance/invariants.py` — 5 invariantes I1-I5 como executable spec + `assert_invariant` + `InvariantViolation`
- [x] v3.8.1 backlog (5/6 dos deferred Workflow #2 Sprint Y):
  - [x] Expand `_billed_dispatch` para 18 handlers (era 3)
  - [x] N+1 fix em `list_usage_periods` via `sum_units_by_period_and_kind`
  - [x] Novo índice `idx_usage_tenant_occurred`
  - [x] `prune_old_events(vacuum=True)` opcional + `SnapshotStore.vacuum()`
  - [x] `soft_warn` float arithmetic
  - [ ] **Hot-row contention** deferred para v3.9.2 (exige benchmark formal)
- [x] Workflow #2 (multi-dim review): soundness + experimental + billing-wiring × 2-vote verify → 25 findings, 1 HIGH + 1 HIGH + 1 LOW confirmados
- [x] SZ-FIX-1 (I1 strict checker) + SZ-FIX-2 (I2 unified `_get_sev`) + SZ-FIX-3 (T1 real cases)
- [x] Tests TW01-TW36 (5 invariantes × 3 testes + v3.8.1 verifications + paper reproducibility smoke + SZ-FIX pins)
- [x] Bump v3.8.0 → v3.9.0 + CHANGELOG + roadmap + inventario + commit + bundle

---

<a id="qa-loop-v391"></a>
## QA Loop v3.9.1 — executado ✅

Tech Leader nível mestre rodou padrão EXPLORAR→REPORTAR→REVISAR→CORRIGIR→RE-EXPLORAR
com 4 lentes (🧪 QA + 🎯 Product + ⚙️ Engineering + 🔒 Security) sobre superfície v3.9.0.

**Round 1**: 6 fixes confirmados aplicados:
- [x] QA-FIX-1 **CRIT** — `_safe_500_envelope` (strip traceback default; `UCO_INCLUDE_TRACE=1` para dev)
- [x] QA-FIX-2 **HIGH** — typed `_qp_int`/`_qp_float` + `_QueryParamError` → 400 envelope
- [x] QA-FIX-3 MED — `_validate_period_key` strict YYYY-MM regex em `/tenants/{id}/usage`
- [x] QA-FIX-4 MED — `.strip()` tenant_id em handlers `get`/`suspend`/`reactivate`
- [x] QA-FIX-5 MED — `_sanitize_for_echo` (cap 64 + strip `\r\n\t` + non-printable)
- [x] QA-FIX-6 MED — `_has_redos_shape("")` → False (empty não é regex shape)

**Round 2 RE-EXPLORE** (4 lentes convergence check): 3/4 DRY; 🔒 Security catched **incomplete migration of QA-FIX-2** (helpers existiam mas nenhum call-site chamava). Fix Round 2:
- [x] Sweep regex migrou **71 sites** (`63 int + 8 float`) para `_qp_int/_qp_float`

**Loop convergiu em 2 rounds**. Métricas: 2125 → 2145 tests (+20 TQA01-TQA20), 0 falhas, 0 leak paths restantes.

**Backlog deferido** (MED/LOW não-bloqueantes da Round 1 — entram em v3.9.2 ou v4.0.0):
- N+1 em `recompute_derived_pending` (snapshot_store.py:989)
- `threading.local` growth em `_webhook_depth` (server.py:2203)
- 26+ MED/LOW de surface coherence, onboarding gaps, dead code

---

<a id="v381-backlog"></a>
## v3.8.1 backlog — achados Workflow #2 Sprint Y deferred

Findings do Workflow #2 que não bloquearam release Sprint Y mas devem
entrar em v3.8.1 (idealmente junto com Sprint Z):

- [ ] **Expand billing wiring** para 16 handlers billable restantes (atualmente
  só `/analyze`, `/repair/hmc`, `/scan-incremental` têm `_billed_dispatch`).
  Faltam: `/repair`, `/apex/auto-remediate`, `/sast`, `/gate`, `/scan-sca`,
  `/scan-iac`, `/scan-flow`, `/scan-performance`, `/scan-architecture`,
  `/scan-test-quality`, `/scan-thread-safety`, `/signatures/discover`,
  `/feeds/cve/load`, `/feeds/sast/load`, `/marketplace/publish`, `/scan-repo`.
- [ ] **N+1 em `list_usage_periods`** — substituir loop por uma SQL
  agregação única (`SELECT period_key, event_kind, SUM(units) ... GROUP BY`).
- [ ] **Hot-row contention `tenants.units_used`** — avaliar sharded counters
  ou ler-side aggregation; benchmark antes/depois.
- [ ] **Index coverage gaps** em `usage_events`: `idx_usage_tenant_occurred`
  para ORDER BY occurred_at + coverage para sum-by-kind.
- [ ] **`prune_old_events` sem VACUUM** — adicionar VACUUM opcional via
  parâmetro + agendar em manutenção noturna.
- [ ] **Soft-warn integer truncation** — usar `unit_budget * soft_pct / 100.0`
  com float para evitar off-by-near-1% em budgets grandes.

---

## Sprint V (v3.6.0) — execução

### APEX SCIENTIFIC scoping registrado

| Etapa | Saída |
|---|---|
| DSM (Design Structure Matrix) | marketplace toca: signature_library, api/server, store (tabela nova), auth |
| Ishikawa | causa-raiz: signatures locais não fan-out → impossível compartilhar entre orgs |
| Pareto 80/20 | publish + list + pull + import (PKI signing / multi-tenant / billing → Y/Z) |
| FMEA | 4 failure modes mitigados: ReDoS payload, duplicate id, no-auth, store flood |

### Implementação

* `governance/marketplace.py` — 150 LOC novos (publish_signature, pull_signature, list_marketplace, import_signature, canonical_payload_hash, _has_redos_shape, _payload_passes_guards).
* `sensor_storage/snapshot_store.py` — tabela `marketplace_signatures` + 5 CRUD methods + `_marketplace_row_to_dict`.
* `api/server.py` — 4 handlers REST + 4 entradas em `/docs` + roteamento POST (admin) + GET.
* `tests/test_marco_m56.py` — 30 testes TV01-TV30.
* `pyproject.toml` + `api/server.py` SensorConfig.version + `CHANGELOG.md` + roadmap atualizados.

### Métricas pós-Sprint V

| Métrica | v3.5.2 | **v3.6.0** |
|---|---|---|
| Tests passing | 1992 | **2022** (+30) |
| Falhas        | 0    | **0** |
| Endpoints     | 60+  | **64+** (+4 marketplace) |
| Tables SQLite | 5    | **6** |

---

<a id="sprint-aa-wbs"></a>
## Sprint AA — UCO Deep Integration (v3.10.0) — WBS

### Auditoria do estado real (2026-06-26) — antes de planejar

Lido `algorithms/uco/universal_code_optimizer_v4.py` (4152 LOC) linha a linha
nas seções relevantes. Achado central: **o `UCOBridge` (sensor_core/uco_bridge.py)
NÃO chama o motor `analyze()` do UCO core.** Ele reimplementa do zero, via AST
visitor próprio (`_UCOVisitor`), os 9 canais (H, CC, ILR, DSM_d, DSM_c, DI, dead,
dups, bugs) — com fórmulas calibradas e 2145 testes pinados. Apenas dois pontos
hoje tocam o UCO core de fato:

1. `sensor_core/autofix/transforms/uco_transform_bridge.py` (Sprint K) — 4 dos
   9 `CodeTransform` do core bridged (SAST040-043).
2. `sensor_core/autofix/hmc_repair.py` (Sprint Q) — já chama `optimize()` HMC
   completo (numpy) com fallback gracioso para `optimize_fast()` (SA) quando
   numpy indisponível. **AA-6 (optimize completo HMC+SA) já está pronto** —
   removido do escopo deste sprint.

### DSM (acoplamento)

`uco_bridge.py` ↔ `algorithms/uco/` (path sys.path injection) ↔ `channels.py`
(SSOT 9 canais) ↔ `policy_engine.py`/`trend_engine.py`/`signals.py` (consomem
os 9 canais) ↔ `api/server.py` (`_billed_dispatch`, billing por endpoint) ↔
`sensor_core/autofix/transforms/` (5 transforms órfãos do core).

### Ishikawa (causa-raiz do gap)

Os dois motores evoluíram em paralelo: o core (`universal_code_optimizer_v4.py`)
ganhou CFG real (Tarjan SCC), DSM com reciprocidade/ciclos via grafo verdadeiro,
`weighted_complexity`, `smoothing_factor` (momentum K), `branching_factor`,
`max_depth` — nenhum desses chegou ao sensor porque o `UCOBridge` foi escrito
antes (ou em paralelo) e nunca foi atualizado para consumir o motor mais novo.
Substituir o `UCOBridge` inteiro pelo motor do core é **alto risco** (fórmulas
diferentes, 2145 testes pinados na calibração atual). Decisão: **integração em
camadas (tiered)**, não substituição.

### Pareto 80/20 — o que entra neste sprint

| Item | ROI | Risco | Decisão |
|---|---|---|---|
| AA-1: Bridge dos 5 transforms órfãos | Alto / mecânico | Baixo (aditivo) | ✅ entra |
| AA-2: Novo módulo `uco_deep_bridge.py` (canais novos: dsm_reciprocity, weighted_complexity, smoothing_factor, branching_factor, max_depth, node/edge/reachable/unreachable counts) | Alto (canais "capturados mas não calculados" reais) | Médio | ✅ entra |
| AA-3: Endpoint opt-in `mode=deep` (não substitui o fast path) | Médio-alto | Baixo (aditivo, billing próprio) | ✅ entra |
| AA-4: Multi-linguagem via pygments (`GenericCFGBuilder`/`GenericDSMCollector`) para JS/Go/Java | Médio | Médio (motor genérico ainda não validado em produção) | ✅ entra (escopo: piloto JS) |
| `detect_patterns()` do core (heurística regex crua) | Baixo | — | ❌ fora — sensor já tem detectores AST superiores |
| Substituir `UCOBridge` pelo motor do core | — | Alto (quebra 2145 testes calibrados) | ❌ fora — rejeitado |

### FMEA

| Modo de falha | Mitigação |
|---|---|
| `mode=deep` muda canais default e quebra Granger/trend/policy que esperam 9 canais fixos | Canais novos são **aditivos** em `channels.py`; `series()` só lê os 9 originais por padrão — novos canais opt-in via novo `DEEP_CHANNELS` tuple separado |
| numpy ausente quebra deep mode | `uco_deep_bridge` usa apenas `analyze()` (não requer numpy, confirmado em `UCO_API_SURFACE.yaml`) — só o autofix `optimize()` HMC requer numpy, e isso já tem fallback (Sprint Q) |
| Custo de billing não gated → deep mode usado de graça | `_billed_dispatch` com unit cost próprio (mais caro que `/analyze` fast) |
| pygments ausente no runtime → multi-lang CFG quebra import | Mesmo padrão do core: `_PygmentsMixin` já é defensivo; sensor side precisa de try/except no boundary do novo módulo |

### Checklist AA (WBS)

- [x] AA-1: Bridge dos 5 transforms órfãos do UCO core (concluído — ver nota
      abaixo: apenas 2 mapeados a SAST novo, 3 são cosméticos)
      (`AdjacentDuplicateBlockRemoval`, `DuplicateAdjacentControlBlockMerger`,
      `BracketWhitespaceNormalizer`, `ConstantFoldingTransform`,
      `EmptyBlockRemover`)
- [ ] AA-2: `sensor_core/uco_deep_bridge.py` — wrapper de
      `UniversalCodeOptimizer.analyze()` expondo canais novos
      (`dsm_reciprocity`, `weighted_complexity`, `smoothing_factor`,
      `branching_factor`, `max_depth`, `node_count`, `edge_count`,
      `reachable_count`, `unreachable_count`) como atributos extras do
      `MetricVector` (padrão `getattr` já usado, sem quebrar schema)
- [ ] AA-3: `DEEP_CHANNELS` em `channels.py` (SSOT separado, aditivo) +
      endpoint `mode=deep` em `/analyze` roteando para `uco_deep_bridge`,
      billed via `_billed_dispatch` com novo `UNIT_COSTS["analyze_deep"]`
- [ ] AA-4: Piloto multi-linguagem JS via `GenericCFGBuilder`/
      `GenericDSMCollector` (pygments) integrado a `lang_adapters/javascript.py`
- [ ] AA-5: `tests/test_marco_m61.py` — TUC01-TUC30 (transforms órfãos,
      canais deep, endpoint deep, piloto JS)
- [ ] AA-6: ~~Expor optimize() HMC completo~~ — **já implementado** (Sprint Q,
      `hmc_repair.py`), confirmado nesta auditoria, removido do escopo
- [ ] AA-7: Workflow multi-dim review (novo endpoint + billing surface =
      gatilho do framework condicional para ceremônia pesada)
- [ ] AA-8: CHANGELOG + version bump v3.10.0 + regressão completa + release

### AA-1 — nota de execução (concluído)

Das 5 classes órfãs, apenas 2 detectam um defeito real e ganharam SAST rule
nova: **SAST044** (Adjacent Duplicate Statement, detector texto em
`sast/scanner.py::_check_adjacent_duplicate_lines`) e **SAST045**
(Unsimplified Constant Expression, detector AST em `visit_Assign`) — ambas
wired em `SAST_TO_TRANSFORM` (11 → 13 entradas). As outras 3
(`DuplicateAdjacentControlBlockMerger`, `BracketWhitespaceNormalizer`,
`EmptyBlockRemover`) são puramente cosméticas — sem achado de qualidade
associado — e foram bridged como transforms chamáveis diretamente, sem
rule SAST (decisão documentada no docstring do módulo: não fabricar
findings falsos para formatação). 16 novos testes (TUC01-TUC16,
`tests/test_marco_m61.py`) + 1 teste legado atualizado
(`test_TN30` → 13 entradas). Regressão completa: **2161 passing, 0
falhas** (de 2145).

### Recomendação arquitetural — "UCO como módulo de deep search"

Sim — **manter o `UCOBridge` atual como tier rápido (default, zero-dep,
calibrado, 2145 testes)** e tratar o motor completo do `algorithms/uco/`
como um **tier opcional "deep"** (CFG real com Tarjan SCC, DSM com
reciprocidade verdadeira, multi-linguagem via pygments), acionado por
`mode=deep` e cobrado com unit cost mais alto. Isso evita: (a) reescrever
2145 testes pinados na calibração atual, (b) duas fórmulas de Hamiltonian
divergentes colidindo no mesmo canal, (c) dependência rígida em numpy/pygments
no caminho rápido usado por CI/PR gates.
