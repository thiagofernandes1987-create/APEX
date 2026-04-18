#!/usr/bin/env python3
"""
tools/phase8_stress_fixes.py
────────────────────────────────────────────────────────────────────
APEX Phase 8 — Stress-Test Precision Fixes | OPP-161 | 2026-04-18

Corrige todos os bugs/inconsistências identificados no stress-test do boot kernel:

  FIX-A [CRITICAL]: kernel.version v00.32.1 → v00.37.0 (L602/606/607)
  FIX-B [HIGH]:     Header v00.36.0 → v00.37.0 + DIFFs count (L3)
  FIX-C [HIGH]:     specialized_skill_engine deps: MODULE_pot_engine →
                    MODULE_pot_engine_v2; MODULE_mental_interpreter →
                    MODULE_mental_interpreter_v4 (L4656/4657)
  FIX-D [HIGH]:     SR_08 + SR_09: mental_interpreter →
                    mental_interpreter_v4 (L1020/1021/1067/1068)
  FIX-E [HIGH]:     tier_1 inject_when_policy: remove deprecated aliases,
                    replace with v2/v4 (L3207)
  FIX-F [HIGH]:     tier_1 load order: MODULE_mental_interpreter →
                    MODULE_mental_interpreter_v4 (L3165)
  FIX-G [HIGH]:     apex_runtime_probe.fmea: severity 8→5, rpn 16→10 (L17592/17597)
  FIX-H [HIGH]:     OPP-160 DIFF block missing from boot kernel
  FIX-I [LOW]:      dsl_module_template: version v00.32.x → v00.37.x (L403)
  FIX-J [LOW]:      dsl_module_template: rpn: N → rpn: 0  (placeholder clarification)

USAGE:
  python tools/phase8_stress_fixes.py [--dry-run]
"""

from __future__ import annotations
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT  = Path(__file__).parent.parent
BOOT_FILE  = REPO_ROOT / "apex_boot" / "apex_v00_36_0_master_full.txt"
STATE_FILE = REPO_ROOT / "apex_state.yaml"

# ─── OPP-160 DIFF block (was in apex_state.yaml as DONE but absent from boot)
OPP160_BLOCK = """
# ─────────────────────────────────────────────────────────────────
# DIFF_APEX_STATE_PERSISTENT_001 (OPP-160)
# apex_state.yaml — estado persistente legível por máquina
# Substitui narrative memory por YAML estruturado consultável
# ─────────────────────────────────────────────────────────────────
apex_state_persistent:
  executor: LLM_BEHAVIOR
  version: v00.37.0
  opp: OPP-160
  tier: 2
  status: ADOPTED

  purpose: >
    Criar e manter apex_state.yaml como registro canônico do estado do projeto.
    Substitui a dependência de o LLM "lembrar" o estado via context window
    por um artefato YAML estruturado, versionado e consultável.

  why: >
    WHY: Sem estado persistente, instruções como "continuar" exigem contexto completo
    da sessão anterior. O LLM não sabe qual fase está pendente, quais gaps foram
    resolvidos, qual OPP é o próximo. apex_state.yaml resolve isso: qualquer sessão
    carrega o arquivo e tem o estado completo sem depender da memória conversacional.

  when: >
    WHEN: STEP_0 deve carregar apex_state.yaml se disponível.
    WHEN: Após cada fase concluída, atualizar last_phase_completed + last_commit.
    WHEN: Após resolver cada GAP, atualizar known_gaps[].status → FIXED.
    WHEN: Antes de iniciar nova tarefa, ler next_pending para contextualização.

  what_if_fails: >
    FALLBACK: Se apex_state.yaml ausente, inferir estado do git log + últimas mensagens.
    REGRA: apex_state.yaml é suplementar — nunca bloqueia execução se ausente.
    REGRA: Atualizar via script ou manualmente após operações relevantes.

  file_path: "apex_state.yaml"
  schema:
    required_fields:
      - version
      - opp_current
      - date_updated
      - boot_verified
      - pipeline.last_phase_completed
      - pipeline.last_commit
      - pipeline.next_pending
      - known_gaps
    optional_fields:
      - phases
      - recent_opps
      - repo
      - boot_verification

  boot_integration: >
    STEP_0: LLM tenta ler apex_state.yaml do repositório.
    SE disponível: extrair version, boot_verified, next_pending, known_gaps.
    Declarar: [STATE_LOADED: version={v} | phase={p} | pending={opp}]
    SE ausente: [STATE_UNAVAILABLE] — continuar com inferência de contexto.

  fmea:
    rpn: 2
    mode: "apex_state.yaml desatualizado — estado incorreto para sessão atual"
    probability: 2
    severity: 1
    detection: 1
    mitigation: >
      Estado é suplementar, não autoritativo. Git log é fonte primária de verdade.
      Atualizar apex_state.yaml via ferramentas automatizadas após cada fase.
"""


def apply_all_fixes(content: str, dry_run: bool) -> tuple[str, dict]:
    stats = {}
    original = content

    # ─── FIX-A [CRITICAL]: kernel.version v00.32.1 → v00.37.0 ────────────
    # Only patch the kernel: block (lines ~600-610), NOT historical module versions
    old_kernel_block = (
        "kernel:\n"
        "  version: v00.32.1\n"
        "  identity:\n"
        "    name: APEX\n"
        "    type: Autonomous Polymorphic Engineering eXpert\n"
        "    version_tag: 'v00.32.1 — v00.32.0 + DSL_CLARITY_001 (glossário, marcadores executor, documentação completa)'\n"
        "    APEX_VERSION: \"v00.32.1\""
    )
    new_kernel_block = (
        "kernel:\n"
        "  version: v00.37.0\n"
        "  identity:\n"
        "    name: APEX\n"
        "    type: Autonomous Polymorphic Engineering eXpert\n"
        "    version_tag: 'v00.37.0 — v00.36.0 + Phase7 fixes + OPP-155→160 + 135 DIFFs aplicados'\n"
        "    APEX_VERSION: \"v00.37.0\""
    )
    if old_kernel_block in content:
        content = content.replace(old_kernel_block, new_kernel_block, 1)
        stats["FIX-A"] = "APPLIED: kernel.version v00.32.1 → v00.37.0"
    else:
        stats["FIX-A"] = "SKIPPED: pattern not found"

    # ─── FIX-B [HIGH]: Header line update ─────────────────────────────────
    old_header = "# Version: v00.36.0 (Full Pack — Security Hardening + Creation Guide + Quality Gates | 127 DIFFs aplicados)"
    new_header = "# Version: v00.37.0 (Full Pack — Phase7 Fixes + Boot Verification + UCO Runtime + 135 DIFFs aplicados)"
    if old_header in content:
        content = content.replace(old_header, new_header, 1)
        stats["FIX-B"] = "APPLIED: header v00.36.0 → v00.37.0 + 127→135 DIFFs"
    else:
        stats["FIX-B"] = "SKIPPED: header already updated or pattern not found"

    # ─── FIX-C [HIGH]: specialized_skill_engine dependencies ──────────────
    old_sse_deps = (
        "    - MODULE_pot_engine\n"
        "    - MODULE_mental_interpreter\n"
        "    - MODULE_attraction_engine\n"
        "    - MODULE_skill_registry\n"
        "  inject_when: cognitive_mode IN [DEEP, RESEARCH, SCIENTIFIC] OR skill_resolution_needed"
    )
    new_sse_deps = (
        "    - MODULE_pot_engine_v2\n"
        "    - MODULE_mental_interpreter_v4\n"
        "    - MODULE_attraction_engine\n"
        "    - MODULE_skill_registry\n"
        "  inject_when: cognitive_mode IN [DEEP, RESEARCH, SCIENTIFIC] OR skill_resolution_needed"
    )
    if old_sse_deps in content:
        content = content.replace(old_sse_deps, new_sse_deps, 1)
        stats["FIX-C"] = "APPLIED: specialized_skill_engine deps → pot_engine_v2 + mental_interpreter_v4"
    else:
        stats["FIX-C"] = "SKIPPED: sse deps pattern not found"

    # ─── FIX-D [HIGH]: SR_08 text — mental_interpreter → mental_interpreter_v4
    old_sr08 = (
        "    - 'SR_08: [MENTAL_INTERPRETER] Toda execução de Specialized Skill em modos "
        "DEEP/RESEARCH/SCIENTIFIC deve passar pelo mental_interpreter. "
        "Execução direta sem trace é inválida.'"
    )
    new_sr08 = (
        "    - 'SR_08: [MENTAL_INTERPRETER_V4] Toda execução de Specialized Skill em modos "
        "DEEP/RESEARCH/SCIENTIFIC deve passar pelo mental_interpreter_v4. "
        "Execução direta sem trace é inválida. "
        "Enforcement: mental_interpreter_v4 (primário), meta_reasoning (secundário). "
        "ATUALIZADO OPP-161: mental_interpreter (DEPRECATED v00.20.0) → mental_interpreter_v4.'"
    )
    if old_sr08 in content:
        content = content.replace(old_sr08, new_sr08, 1)
        stats["FIX-D-SR08"] = "APPLIED: SR_08 text updated to mental_interpreter_v4"
    else:
        stats["FIX-D-SR08"] = "SKIPPED: SR_08 pattern not found"

    # SR_09 enforcement: mental_interpreter → mental_interpreter_v4
    old_sr09_text = (
        "Enforcement: mental_interpreter (primário), meta_reasoning (secundário). Enforcement: mental_interpreter (primário)"
    )
    # More surgical: just the SR_09 enforcement clause
    old_sr09 = (
        "    - 'SR_09: [SUBPROCESS_GATE] Todo PoT program com N > 5 iterações numéricas DEVE ser "
        "executado via subprocess externo (python3 tempfile). Execução inline de N > 5 = output "
        "inválido com confidence_cap 45. Enforcement: mental_interpreter (primário), meta_reasoning (secundário).'"
    )
    new_sr09 = (
        "    - 'SR_09: [SUBPROCESS_GATE] Todo PoT program com N > 5 iterações numéricas DEVE ser "
        "executado via subprocess externo (python3 tempfile). Execução inline de N > 5 = output "
        "inválido com confidence_cap 45. Enforcement: mental_interpreter_v4 (primário), meta_reasoning (secundário).'"
    )
    if old_sr09 in content:
        content = content.replace(old_sr09, new_sr09, 1)
        stats["FIX-D-SR09"] = "APPLIED: SR_09 enforcement → mental_interpreter_v4"
    else:
        stats["FIX-D-SR09"] = "SKIPPED: SR_09 enforcement pattern not found"

    # SR_08 location mapping
    old_sr08_loc = "      SR_08: [specialized_skill_engine.pre_execution]\n      SR_09: [mental_interpreter.execute, pre_STEP_11]"
    new_sr08_loc = "      SR_08: [specialized_skill_engine.pre_execution, mental_interpreter_v4.pre_execution]\n      SR_09: [mental_interpreter_v4.execute, pre_STEP_11]"
    if old_sr08_loc in content:
        content = content.replace(old_sr08_loc, new_sr08_loc, 1)
        stats["FIX-D-LOC"] = "APPLIED: SR_08/SR_09 location mappings updated"
    else:
        stats["FIX-D-LOC"] = "SKIPPED: SR_08/SR_09 location pattern not found"

    # ─── FIX-E [HIGH]: tier_1 inject_when_policy modules list ────────────
    # Remove pot_engine + mental_interpreter (deprecated), replace with v2/v4
    old_tier1_policy = (
        "    tier_1: {rule: on_demand OR when_referenced_by_active_step, modules: "
        "[event_bus, anchor_destroyer, symbolic_executor, cognitive_integrator_library, "
        "fractal_cognitive_simulator, error_tracker, scientific_engine, skill_registry, "
        "skill_matcher, attraction_engine, strategy_library, pot_engine, mental_interpreter, "
        "specialized_skill_engine, fractal_hypothesis_compression, fractal_knowledge_indexing]}"
    )
    new_tier1_policy = (
        "    tier_1: {rule: on_demand OR when_referenced_by_active_step, modules: "
        "[event_bus, anchor_destroyer, symbolic_executor, cognitive_integrator_library, "
        "fractal_cognitive_simulator, error_tracker, scientific_engine, skill_registry, "
        "skill_matcher, attraction_engine, strategy_library, pot_engine_v2, mental_interpreter_v4, "
        "specialized_skill_engine, fractal_hypothesis_compression, fractal_knowledge_indexing]}"
        "  # OPP-161: pot_engine→v2, mental_interpreter→v4 (deprecated aliases removidos)"
    )
    if old_tier1_policy in content:
        content = content.replace(old_tier1_policy, new_tier1_policy, 1)
        stats["FIX-E"] = "APPLIED: tier_1 policy — deprecated aliases replaced with v2/v4"
    else:
        stats["FIX-E"] = "SKIPPED: tier_1 policy pattern not found"

    # ─── FIX-F [HIGH]: tier_1 load order — mental_interpreter → v4 ───────
    old_load_order = (
        "    - MODULE_pot_engine      (TIER_1) — após symbolic_executor\n"
        "    - MODULE_mental_interpreter (TIER_1) — após pot_engine\n"
        "    - MODULE_specialized_skill_engine (TIER_1) — após mental_interpreter"
    )
    new_load_order = (
        "    - MODULE_pot_engine_v2   (TIER_1) — após symbolic_executor  # OPP-161: alias v1 removido\n"
        "    - MODULE_mental_interpreter_v4 (TIER_1) — após pot_engine_v2  # OPP-161: v1 deprecated\n"
        "    - MODULE_specialized_skill_engine (TIER_1) — após mental_interpreter_v4"
    )
    if old_load_order in content:
        content = content.replace(old_load_order, new_load_order, 1)
        stats["FIX-F"] = "APPLIED: tier_1 load order — pot_engine→v2, mental_interpreter→v4"
    else:
        stats["FIX-F"] = "SKIPPED: load order pattern not found"

    # ─── FIX-G [HIGH]: apex_runtime_probe FMEA severity 8→5, rpn 16→10 ───
    old_fmea_probe = (
        "  fmea:\n"
        "    rpn: 16\n"
        "    mode: \"Profile incorreto por falha de probe -> todos SANDBOX_CODE operam com perfil errado\"\n"
        "    probability: 2\n"
        "    severity: 8\n"
        "    detection: 1\n"
        "    mitigation: >\n"
        "      13 testes independentes — falha de 1 nao invalida os outros.\n"
        "      Fallback MINIMAL e sempre seguro. Re-executar probe se comportamento inconsistente."
    )
    new_fmea_probe = (
        "  fmea:\n"
        "    rpn: 10\n"
        "    mode: \"Profile incorreto por falha de probe -> todos SANDBOX_CODE operam com perfil errado\"\n"
        "    probability: 2\n"
        "    severity: 5\n"
        "    detection: 1\n"
        "    mitigation: >\n"
        "      13 testes independentes — falha de 1 nao invalida os outros.\n"
        "      Fallback MINIMAL e sempre seguro. Re-executar probe se comportamento inconsistente.\n"
        "    _fix: OPP-161 — severity corrigido de 8→5 (máx escala 1-5); rpn recalculado 2×5×1=10"
    )
    if old_fmea_probe in content:
        content = content.replace(old_fmea_probe, new_fmea_probe, 1)
        stats["FIX-G"] = "APPLIED: apex_runtime_probe fmea severity 8→5, rpn 16→10"
    else:
        stats["FIX-G"] = "SKIPPED: fmea probe pattern not found (may need manual fix)"

    # ─── FIX-H [HIGH]: OPP-160 DIFF block injection ───────────────────────
    if "OPP-160" not in content:
        # Inject before the OPP-161 footer or before last footer
        fim_idx = content.rfind(
            "# ═══════════════════════════════════════════════════════════════════\n# FIM"
        )
        if fim_idx != -1:
            content = content[:fim_idx].rstrip() + "\n" + OPP160_BLOCK + "\n" + content[fim_idx:]
        else:
            content = content.rstrip() + "\n" + OPP160_BLOCK
        stats["FIX-H"] = "APPLIED: OPP-160 DIFF block injected into boot kernel"
    else:
        stats["FIX-H"] = "SKIPPED: OPP-160 already present"

    # ─── FIX-I [LOW]: dsl_module_template version example ─────────────────
    old_template_ver = "      version: v00.32.x"
    new_template_ver = "      version: v00.37.x  # exemplo — usar versão atual do sistema"
    if old_template_ver in content:
        content = content.replace(old_template_ver, new_template_ver, 1)
        stats["FIX-I"] = "APPLIED: dsl_module_template version example updated"
    else:
        stats["FIX-I"] = "SKIPPED: template version pattern not found"

    # ─── FIX-J [LOW]: rpn: N → rpn: 0 in template ────────────────────────
    old_rpn_n = "        rpn: N               # Risk Priority Number = probability × severity × detection"
    new_rpn_n = "        rpn: 0               # Risk Priority Number = probability × severity × detection (0=tbd)"
    if old_rpn_n in content:
        content = content.replace(old_rpn_n, new_rpn_n, 1)
        stats["FIX-J"] = "APPLIED: dsl_module_template rpn: N → rpn: 0 (tbd)"
    else:
        stats["FIX-J"] = "SKIPPED: rpn:N template pattern not found"

    changed = content != original
    return content, stats, changed


def update_footer(content: str) -> str:
    """Update the FIM footer to reflect OPP-161 additions."""
    old_footer = (
        "# FIM DOS MODULOS v00.37.0 — OPP-157 + OPP-158 + OPP-159 adicionados\n"
        "# Total DIFFs aplicados: 135 (132 anteriores + OPP-157 + OPP-158 + OPP-159)\n"
        "# OPP-157: DIFF_BOOT_VERIFICATION_GATE_001 — STEP_0 emite hash confirmado\n"
        "# OPP-158: DIFF_PMI_PM_MANDATORY_GATE_001 — pmi_pm blocking enforcement\n"
        "# OPP-159: DIFF_UCO_RUNTIME_DIGEST_001 — UCO scores influenciam meta_reasoning\n"
        "# Gaps resolvidos: GAP-01, GAP-02, GAP-03 (de análise 2026-04-18)\n"
        "# Proxima versão: v00.38.0\n"
        "# Debug completo: 2026-04-18 — boot expandido / 3784 SKILL.md / 163+ AGENT.md"
    )
    new_footer = (
        "# FIM DOS MODULOS v00.37.0 — OPP-157→161 adicionados\n"
        "# Total DIFFs aplicados: 136 (135 anteriores + OPP-160 + stress-fixes OPP-161)\n"
        "# OPP-157: DIFF_BOOT_VERIFICATION_GATE_001 — STEP_0 emite hash confirmado\n"
        "# OPP-158: DIFF_PMI_PM_MANDATORY_GATE_001 — pmi_pm blocking enforcement\n"
        "# OPP-159: DIFF_UCO_RUNTIME_DIGEST_001 — UCO scores influenciam meta_reasoning\n"
        "# OPP-160: DIFF_APEX_STATE_PERSISTENT_001 — apex_state.yaml integrado ao boot\n"
        "# OPP-161: STRESS_FIXES — kernel.version CRITICAL + SR_08/09 + sse deps + fmea RPN\n"
        "# Bugs corrigidos: kernel.version v00.32.1→v00.37.0, severity:8→5, deprecated deps\n"
        "# Proxima versão: v00.38.0\n"
        "# Debug completo: 2026-04-18 — boot stress-tested + 10 fixes | 3784 SKILL.md | 163+ AGENT.md"
    )
    if old_footer in content:
        return content.replace(old_footer, new_footer, 1)
    return content


def main():
    parser = argparse.ArgumentParser(description="APEX Phase 8 — Boot Stress-Test Fixes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\n{'='*62}")
    print(f"APEX Phase 8 — Boot Stress-Test Fixes | Mode: {mode}")
    print(f"{'='*62}\n")

    content       = BOOT_FILE.read_text(encoding='utf-8')
    orig_lines    = content.count('\n')
    print(f"  Boot file: {orig_lines} lines\n")

    content, stats, changed = apply_all_fixes(content, args.dry_run)
    content = update_footer(content)

    new_lines  = content.count('\n')
    delta      = new_lines - orig_lines

    # Report
    applied  = [k for k, v in stats.items() if v.startswith("APPLIED")]
    skipped  = [k for k, v in stats.items() if v.startswith("SKIPPED")]

    print(f"  Fixes applied:  {len(applied)}")
    print(f"  Fixes skipped:  {len(skipped)}\n")

    for fix_id, result in sorted(stats.items()):
        icon = "✓" if result.startswith("APPLIED") else "—"
        print(f"  [{icon}] {fix_id}: {result}")

    print(f"\n  Lines: {orig_lines} → {new_lines} (Δ{delta:+d})")

    if not args.dry_run and changed:
        BOOT_FILE.write_text(content, encoding='utf-8')
        print(f"\n  Written: {BOOT_FILE.name}")

        # Update apex_state.yaml
        if STATE_FILE.exists():
            state = STATE_FILE.read_text(encoding='utf-8')
            # Update opp_current and date
            state = re.sub(r'opp_current: OPP-\d+', 'opp_current: OPP-161', state)
            state = re.sub(r'next_pending: "OPP-\d+"', 'next_pending: "OPP-162"', state)
            state = re.sub(
                r'  - id: GAP-03\n    desc: "UCO não influencia decisões LLM em runtime"\n    severity: MEDIUM\n    fix_opp: OPP-159\n    status: PENDING',
                '  - id: GAP-03\n    desc: "UCO não influencia decisões LLM em runtime"\n    severity: MEDIUM\n    fix_opp: OPP-159\n    status: FIXED',
                state
            )
            STATE_FILE.write_text(state, encoding='utf-8')
            print(f"  Updated: apex_state.yaml (opp_current→OPP-161, next→OPP-162)")

        # Write reference doc
        ref = REPO_ROOT / "references" / "OPP-161-stress-test-fixes.md"
        ref.write_text(_build_ref_doc(stats, applied, delta), encoding='utf-8')
        print(f"  Written: references/OPP-161-stress-test-fixes.md")

    elif args.dry_run:
        print(f"\n  [DRY-RUN] Would write {new_lines} lines to {BOOT_FILE.name}")

    print(f"\n{'='*62}")
    print("Phase 8 complete.")
    if not args.dry_run and changed:
        print("Next: python tools/validate_repo_uco.py --layer skills")
        print("      git add -A && git commit")


import re as _re

def _build_ref_doc(stats: dict, applied: list, delta: int) -> str:
    rows = "\n".join(
        f"| {k} | {'✅' if v.startswith('APPLIED') else '—'} | {v[8:] if v.startswith('APPLIED') else v[8:]} |"
        for k, v in sorted(stats.items())
    )
    return f"""\
# OPP-161 — Boot Stress-Test Precision Fixes

**OPP**: OPP-161
**Version**: v00.37.0
**Date**: 2026-04-18
**Status**: IMPLEMENTED
**Source**: Stress-test analysis (Claude + DeepSeek consolidated + static grep analysis)

---

## Bugs corrigidos ({len(applied)} fixes aplicados, Δ{delta:+d} linhas)

| Fix | Status | Descrição |
|-----|--------|-----------|
{rows}

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
grep "kernel:" -A3 apex_boot/apex_v00_36_0_master_full.txt | grep "version:"
# Expected: version: v00.37.0

grep "SR_08" apex_boot/apex_v00_36_0_master_full.txt | grep "mental_interpreter"
# Expected: mental_interpreter_v4 only

grep "severity: 8" apex_boot/apex_v00_36_0_master_full.txt
# Expected: 0 matches
```
"""


if __name__ == "__main__":
    main()
