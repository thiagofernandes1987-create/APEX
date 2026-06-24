# UCO Sensor — Inventário Persistente de Auditoria APEX SCIENTIFIC

> Documento durável entre sessões. Tracking de TODAS as ações da auditoria
> profunda + fixes + verificações.  Atualizar a cada step concluído.

---

## Versão atual

**v3.5.1** (Sprint W — gate-1 fixes aplicados) → **alvo: v3.5.2** ao final.

## Equipe APEX (modo SCIENTIFIC)

| Papel | Função | Status |
|---|---|---|
| Tech Lead         | Orquestração + priorização (esta sessão Claude) | ✅ |
| Architect         | Acoplamento, blast radius | ✅ gate-1 |
| Security Engineer | Auth, secrets, race conditions, ReDoS, path-traversal | ✅ gate-1 |
| Performance Eng.  | Hot paths, locks, N+1, cache invalidation | ✅ gate-1 |
| Correctness Theor.| Bugs lógicos, sign conventions, off-by-one | ⏳ gate-2 (caiu em gate-1) |
| Test Strategist   | Tautologias, mocks que escondem bugs, gaps | ⏳ gate-2 (caiu em gate-1) |
| Dead Code Hunter  | Funções/imports nunca usados, branches mortos | 🆕 gate-2 |
| Control Flow Anal.| Loops sem condição de saída, recursão sem base case | 🆕 gate-2 |
| Wiring Auditor    | Paths hardcoded, env vars, sys.path manipulation | 🆕 gate-2 |
| Debugger          | Reproduce + corrigir cada finding | conforme demanda |

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

### Gate-2 (APEX Workflow #2 — Sprint W2, alvo v3.5.2) 🚧

- [ ] Workflow lançado (5 dimensões: correctness + tests + dead-code + control-flow + wiring)
- [ ] Findings coletados + dedupe + adversarial verify
- [ ] Inventário atualizado com findings + plano de fix
- [ ] Fixes implementados
- [ ] Testes TG01-TGNN pinam cada fix
- [ ] Regressão re-rodada — alvo: zero falhas + zero novos findings significant
- [ ] Commit final + bump v3.5.2

---

## Findings sob investigação (gate-2)

_Atualizado pelo Workflow assim que retornar._

| ID | Severidade | Arquivo:Linha | Categoria | Status fix | Teste regressão |
|---|---|---|---|---|---|
| (pending workflow) |  |  |  |  |  |

---

## Métricas finais de qualidade (a atualizar)

| Métrica | Antes gate-1 | Após gate-1 | Após gate-2 (alvo) |
|---|---|---|---|
| Tests passing            | 1901 | 1931 | ≥1961 |
| LOC produção             | 39.781 | 40.592 | TBD |
| CRITICAL findings        | 1 confirmado | 0 | 0 |
| HIGH findings            | 5 confirmados | 0 | 0 |
| MEDIUM findings backlog  | 26 | 26 | TBD |
| Cobertura módulos audit  | 7 | 7 | TBD |

---

## Decisões científicas registradas

1. **Gate-1 deferiu Postgres adapter** para Sprint W via FMEA (80% perf gain do cache, não do storage).
2. **Path-jail closed-by-default** — sem `UCO_FEEDS_DIR`, todo file-load rejeitado.
3. **Admin endpoints SEMPRE exigem `UCO_ADMIN_KEY`** independente de `auth_enabled`.
4. **HMC `preserve_aps=True` por default** + APS canônico via SSOT.
5. **MEDIUM/LOW deferred para Sprint V** — não bloqueiam horizonte 180 dias.

---

## Próximos sprints após gate-2 (horizonte 180 dias)

| Sprint | Foco |
|---|---|
| V | Marketplace de spectral signatures (Movimento #5 expandido) |
| X | CFG visualizável + hotspot overlay |
| Y | SaaS multi-tenant + billing |
| Z | Paper POPL/PLDI submission |
