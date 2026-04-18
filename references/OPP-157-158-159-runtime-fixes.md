# OPP-157 — Boot Verification Gate
## OPP-158 — pmi_pm Mandatory Enforcement
## OPP-159 — UCO Runtime Digest

**OPP**: OPP-157 / OPP-158 / OPP-159
**Version**: v00.37.0
**Date**: 2026-04-18
**Status**: IMPLEMENTED
**Priority**: CRITICAL
**Source**: Análise consolidada Claude + DeepSeek (2026-04-18)

---

## Contexto

Três gaps críticos identificados em análise imparcial do comportamento real do APEX
durante execução (não análise estática):

| GAP | Descrição | Severidade |
|-----|-----------|-----------|
| GAP-01 | Boot sem verificação de carregamento real | HIGH |
| GAP-02 | pmi_pm sem enforcement obrigatório | HIGH |
| GAP-03 | UCO não influencia decisões LLM em runtime | MEDIUM |

---

## OPP-157: Boot Verification Gate

**Problema**: O LLM executava assumindo que o boot estava carregado, sem verificar.
**Solução**: STEP_0 agora DEVE emitir `[BOOT_VERIFIED: hash | lines: n | version: v]`.
**Gate**: STEP_1 bloqueado até [BOOT_VERIFIED] confirmado.

```
[BOOT_VERIFIED: a3f8c21b | lines: 20500 | version: v00.37.0 | agents: 15+163]
```

---

## OPP-158: pmi_pm Mandatory Gate

**Problema**: pmi_pm era descritivo — nunca emitia output de scoping explícito.
**Solução**: Qualquer tarefa com efeito colateral requer [SCOPE_CONFIRMED] antes de tool calls.

```
[SCOPE_CONFIRMED]
Task:          Executar Phase 7a repository fixes
Phase:         Phase 7 / OPP-158
Risk:          MEDIUM
Preconditions: OK (boot verified, phase6 complete, dry-run available)
Plan:          1. FIX-1 activates_when → 2. FIX-2 primary_domain → 3. FIX-3 state → 4. FIX-4 lock
Rollback:      git revert HEAD
```

---

## OPP-159: UCO Runtime Digest

**Problema**: UCO scores existem no repo mas são invisíveis ao LLM durante inferência.
**Solução**: meta/uco_runtime_digest.yaml gerado por validate_repo_uco.py --digest.
**Integração**: meta_reasoning emite [UCO_LOW_QUALITY_WARNING] para skills com score < 40.

```bash
# Gerar digest:
python tools/validate_repo_uco.py --digest
# Output: meta/uco_runtime_digest.yaml
```

---

## Files Changed

| File | Change |
|------|--------|
| `apex_boot/apex_v00_36_0_master_full.txt` | +OPP-157 + OPP-158 + OPP-159 DIFF blocks |
| `references/OPP-157-158-159-runtime-fixes.md` | NEW — este documento |
| `apex_state.yaml` | Updated: GAP-01/02/03 → FIXED |

---

## Impact

| Antes | Depois |
|-------|--------|
| Boot assumido, nunca verificado | STEP_0 emite [BOOT_VERIFIED] ou [BOOT_UNVERIFIED] |
| "continuar" → execução imediata | "continuar" → pmi_pm scope → [SCOPE_CONFIRMED] → execução |
| UCO score invisível em runtime | UCO digest consultado por meta_reasoning em STEP_1 |
