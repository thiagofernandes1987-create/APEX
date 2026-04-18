# OPP-155 — Boot Integration: Community Subagents
## OPP-156 — Boot Integration: CS Persona Agents

**OPP**: OPP-155 / OPP-156
**Version**: v00.37.0
**Date**: 2026-04-18
**Status**: IMPLEMENTED
**Priority**: HIGH
**Depends On**: OPP-153, OPP-154 (roster YAML already on disk)
**Author**: APEX Pipeline (tools/inject_opp155_156_boot.py)

---

## Problem Statement

OPP-153/154 criou `agents/community_agent_roster.yaml` com 163 agentes registrados
no disco, mas o **boot kernel** (`apex_v00_36_0_master_full.txt`) não tinha os DIFF blocks
correspondentes. Resultado: meta_reasoning não carregava os agentes durante o boot.

### Gap Identificado

| Componente | Estado Antes | Estado Depois |
|------------|-------------|---------------|
| `community_agent_roster.yaml` | ✅ Criado (OPP-153/154) | ✅ Existente |
| Boot DIFF OPP-155 | ❌ Ausente | ✅ Injetado |
| Boot DIFF OPP-156 | ❌ Ausente | ✅ Injetado |
| meta_reasoning activation | ❌ Invisível | ✅ 163 agentes ativados |

---

## Solution

### OPP-155: `DIFF_COMMUNITY_SUBAGENT_ROSTER_BOOT_001`
- **140 community subagents** (10 categorias) integrados ao kernel
- Cada agente com `activates_when[]` derivado de category + capabilities
- Protocolo de ativação: score-based match via meta_reasoning
- Max concurrent: 2 (1 domain expert + 1 orchestrator)

### OPP-156: `DIFF_CS_PERSONA_ROSTER_BOOT_001`
- **23 CS persona agents** integrados ao kernel
- Focados em domínios: business, product, strategy, marketing, finance
- Ativados quando meta_reasoning detecta contexto não puramente técnico
- Max concurrent: 1 (role único)

---

## Files Changed

| File | Change |
|------|--------|
| `apex_boot/apex_v00_36_0_master_full.txt` | +OPP-155 + OPP-156 DIFF blocks |
| `references/OPP-155-156-boot-integration.md` | NEW — este documento |

---

## Activation Flow (OPP-155/156)

```
Boot STEP_0: Kernel carrega community_subagent_roster_boot + cs_persona_roster_boot
Boot STEP_1: pmi_pm detecta domínio da tarefa
             → meta_reasoning verifica activates_when[] de 163 agentes
             → SE match: emite [COMMUNITY_AGENT_ACTIVATED: {agent_id}]
Boot STEP_N: Agente executa em PARTITION_ACTIVE com role especializado
```

---

## Impact

| Métrica | Antes | Depois |
|---------|-------|--------|
| Agentes no boot kernel | 9 base + 33 OPP-116 | 9 + 33 + 163 |
| Subagents ativados por domínio | 0 | 140 |
| CS personas ativas | 0 | 23 |
| Cobertura de domínios | ~15 | ~54 |

---

## Verification

```bash
grep "OPP-155\|OPP-156" apex_boot/apex_v00_36_0_master_full.txt
# Expected: 2+ matches

grep "community_subagent_roster_boot\|cs_persona_roster_boot" apex_boot/apex_v00_36_0_master_full.txt
# Expected: both keys present
```

---

## Diff History
- **v00.37.0**: OPP-155/156 — 163 agentes integrados ao boot kernel via DIFF blocks
