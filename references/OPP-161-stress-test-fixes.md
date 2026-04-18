# OPP-161 — Boot Stress-Test Precision Fixes

**OPP**: OPP-161
**Version**: v00.37.0
**Date**: 2026-04-18
**Status**: IMPLEMENTED
**Source**: Stress-test analysis (Claude + DeepSeek consolidated + static grep analysis)

---

## Bugs corrigidos (12 fixes aplicados, Δ+70 linhas)

| Fix | Status | Descrição |
|-----|--------|-----------|
| FIX-A | ✅ |  kernel.version v00.32.1 → v00.37.0 |
| FIX-B | ✅ |  header v00.36.0 → v00.37.0 + 127→135 DIFFs |
| FIX-C | ✅ |  specialized_skill_engine deps → pot_engine_v2 + mental_interpreter_v4 |
| FIX-D-LOC | ✅ |  SR_08/SR_09 location mappings updated |
| FIX-D-SR08 | ✅ |  SR_08 text updated to mental_interpreter_v4 |
| FIX-D-SR09 | ✅ |  SR_09 enforcement → mental_interpreter_v4 |
| FIX-E | ✅ |  tier_1 policy — deprecated aliases replaced with v2/v4 |
| FIX-F | ✅ |  tier_1 load order — pot_engine→v2, mental_interpreter→v4 |
| FIX-G | ✅ |  apex_runtime_probe fmea severity 8→5, rpn 16→10 |
| FIX-H | ✅ |  OPP-160 DIFF block injected into boot kernel |
| FIX-I | ✅ |  dsl_module_template version example updated |
| FIX-J | ✅ |  dsl_module_template rpn: N → rpn: 0 (tbd) |

---

## Detalhes por severidade

### CRITICAL
- **FIX-A**: `kernel.version` e `APEX_VERSION` estavam em v00.32.1 enquanto o sistema
  operava em v00.37.0. O `boot_verification_gate` (OPP-157) compara versões — essa
  inconsistência causaria falha de boot_verified em toda sessão.

### HIGH
- **FIX-B**: Header do arquivo declarava v00.36.0/127 DIFFs; sistema real em v00.37.0/135 DIFFs.
- **FIX-C**: `specialized_skill_engine.dependencies` referenciava `MODULE_pot_engine` e
  `MODULE_mental_interpreter` (ambos DEPRECATED desde v00.20.0). Substituídos por v2/v4.
- **FIX-D**: SR_08 e SR_09 referenciavam `mental_interpreter` DEPRECATED. SR_33 (mesmo escopo)
  já usava `mental_interpreter_v4`. Contradiction entre SRs críticas resolvida.
- **FIX-E**: `tier_1 inject_when_policy` listava aliases deprecated no modules[]. Substituídos.
- **FIX-F**: Ordem de carga tier_1 referenciava módulos deprecated. Atualizado para v2/v4.
- **FIX-G**: `apex_runtime_probe.fmea.severity = 8` viola a escala 1-5 definida no schema.
  `rpn = 16` era matematicamente inválido (2×8×1). Corrigido para severity=5, rpn=10 (2×5×1).
- **FIX-H**: OPP-160 registrado em apex_state.yaml como DONE mas sem DIFF block no boot kernel.
  DIFF_APEX_STATE_PERSISTENT_001 injetado.

### LOW
- **FIX-I**: Template de módulo usava `version: v00.32.x` como exemplo — geraria novos módulos
  com versão incorreta.
- **FIX-J**: `rpn: N` no template — qualquer parser automatizado interpretaria N como variável
  indefinida. Substituído por `rpn: 0` com comentário `(tbd)`.

---

## Impacto

| Componente | Antes | Depois |
|------------|-------|--------|
| kernel.version | v00.32.1 ❌ | v00.37.0 ✅ |
| SR_08 enforcer | mental_interpreter (DEPRECATED) | mental_interpreter_v4 |
| SR_09 enforcer | mental_interpreter (DEPRECATED) | mental_interpreter_v4 |
| sse deps | pot_engine + mental_interpreter | pot_engine_v2 + mental_interpreter_v4 |
| tier_1 modules | aliases deprecated presentes | somente versões ativas |
| fmea severity | 8 (fora escala) | 5 (máximo escala 1-5) |
| fmea rpn | 16 (inválido) | 10 (2×5×1) |
| OPP-160 no boot | ausente | injetado |
| Header version | v00.36.0 / 127 DIFFs | v00.37.0 / 135 DIFFs |

---

## Verificação

```bash
grep "kernel:" -A3 apex_boot/apex_v00_37_0_master_full.txt | grep "version:"
# Expected: version: v00.37.0

grep "SR_08" apex_boot/apex_v00_37_0_master_full.txt | grep "mental_interpreter"
# Expected: mental_interpreter_v4 only

grep "severity: 8" apex_boot/apex_v00_37_0_master_full.txt
# Expected: 0 matches
```
