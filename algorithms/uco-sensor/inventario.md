# UCO Sensor — Inventário Persistente de Auditoria APEX SCIENTIFIC

> Documento durável entre sessões. Tracking de TODAS as ações da auditoria
> profunda + fixes + verificações.  Atualizar a cada step concluído.

---

## Versão atual

**v3.8.0** (Sprint Y — SaaS multi-tenant + billing, APEX SCIENTIFIC pleno via 2 workflows) ✅

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

## Próximos sprints (horizonte 180 dias)

| Sprint | Foco | Status |
|---|---|---|
| **V** | Marketplace de spectral signatures (Movimento #5 expandido) | **✅ v3.6.0** |
| **X** | CFG visualizável + hotspot overlay + port-allocator nos testes | **✅ v3.7.0** |
| **Y** ⭐ | SaaS multi-tenant + billing (APEX SCIENTIFIC pleno) | **✅ v3.8.0** |
| **Z** | Paper POPL/PLDI submission | pending → v3.9.0 |

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
