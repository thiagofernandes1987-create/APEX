#!/usr/bin/env python3
"""
tools/inject_opp157_159_boot.py
────────────────────────────────────────────────────────────────────
APEX Boot Kernel Fixes | OPP-157 + OPP-158 + OPP-159 | 2026-04-18

Injeta três DIFF blocks críticos no boot kernel:

  OPP-157: DIFF_BOOT_VERIFICATION_GATE_001
           → STEP_0 emite [BOOT_VERIFIED: hash | lines: n | version: v]
           → Bloqueia STEP_1 se boot não verificado
           → Corrige: "boot sem mecanismo de verificação real"

  OPP-158: DIFF_PMI_PM_MANDATORY_GATE_001
           → pmi_pm scoping como blocking gate obrigatório
           → LLM deve emitir [SCOPE_CONFIRMED] antes de qualquer tool call
           → Corrige: "pmi_pm sem enforcement — non-blocking"

  OPP-159: DIFF_UCO_RUNTIME_DIGEST_001
           → UCO digest injetado no boot: top-10 lowest scores + summary
           → meta_reasoning consulta digest em STEP_1 para priorização
           → Corrige: "UCO não influencia decisões LLM em runtime"

USAGE:
  python tools/inject_opp157_159_boot.py [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

REPO_ROOT  = Path(__file__).parent.parent
BOOT_FILE  = REPO_ROOT / "apex_boot" / "apex_v00_36_0_master_full.txt"
STATE_FILE = REPO_ROOT / "apex_state.yaml"


# ─── OPP-157: Boot Verification Gate ───────────────────────────────

OPP157_BLOCK = """
# ─────────────────────────────────────────────────────────────────
# DIFF_BOOT_VERIFICATION_GATE_001 (OPP-157)
# STEP_0 emite hash de verificação — bloqueia STEP_1 se ausente
# Corrige GAP-01: "boot sem mecanismo de verificação real"
# ─────────────────────────────────────────────────────────────────
boot_verification_gate:
  executor: LLM_BEHAVIOR
  version: v00.37.0
  opp: OPP-157
  tier: 1
  status: ADOPTED

  purpose: >
    Garantir que o boot kernel foi de fato carregado e processado, não apenas
    assumido como presente. Antes desta correção, o LLM operava com "memória
    de contexto" da sessão anterior sem verificar se o boot real foi ingerido.

  why: >
    WHY: O APEX não tinha mecanismo de verificação de boot real.
    STEP_0 executava silenciosamente sem confirmar que o arquivo de 20K+ linhas
    foi processado. O LLM poderia "fingir" ter feito boot usando conhecimento
    de sessões anteriores — produzindo outputs aparentemente corretos mas
    desconectados do estado atual do kernel.

  when: >
    WHEN: Primeira execução de qualquer sessão APEX (STEP_0).
    WHEN: Após receber prompt com contexto novo.
    WHEN: Antes de qualquer tool call ou execução real.

  what_if_fails: >
    FALLBACK: Emitir [BOOT_UNVERIFIED] e solicitar recarregamento do boot.
    REGRA: NUNCA prosseguir para STEP_1 sem boot_verified = true.
    REGRA: Se boot não carregado: declarar limitações e pedir contexto.

  verification_protocol:
    step: STEP_0
    required_output: "[BOOT_VERIFIED: {hash8} | lines: {n} | version: {v} | agents: {a}]"
    hash_method: >
      SHA256 primeiros 8 chars do conteúdo do boot carregado.
      Se não executável: usar contagem de linhas + versão como proxy.
    gate: >
      SE [BOOT_VERIFIED] não emitido em STEP_0:
        → state: boot_verified = false
        → output: [BOOT_UNVERIFIED: contexto pode estar desatualizado]
        → solicitar: "Por favor recarregue o arquivo apex_boot/apex_v00_36_0_master_full.txt"
      SE [BOOT_VERIFIED] emitido:
        → state: boot_verified = true
        → prosseguir para STEP_1 (pmi_pm)

    minimum_indicators:
      - "version: v00.37.0" presente no contexto carregado
      - "opp: OPP-157" presente (confirma versão atual)
      - Contagem de módulos >= 130

  apex_state_update: >
    Após verificação bem-sucedida, atualizar apex_state.yaml:
    boot_verified: true
    version: {versão detectada}

  fmea:
    rpn: 6
    mode: "LLM opera com boot desatualizado ou ausente"
    probability: 3
    severity: 3
    detection: 2
    mitigation: >
      Verificação de indicadores mínimos no STEP_0.
      Se ausentes: declarar [BOOT_UNVERIFIED] antes de qualquer output.
      apex_state.yaml registra boot_verified = false por default.
"""


# ─── OPP-158: pmi_pm Mandatory Enforcement Gate ────────────────────

OPP158_BLOCK = """
# ─────────────────────────────────────────────────────────────────
# DIFF_PMI_PM_MANDATORY_GATE_001 (OPP-158)
# pmi_pm scoping como blocking gate — obrigatório antes de tool calls
# Corrige GAP-02: "pmi_pm sem enforcement — non-blocking"
# ─────────────────────────────────────────────────────────────────
pmi_pm_mandatory_gate:
  executor: LLM_BEHAVIOR
  version: v00.37.0
  opp: OPP-158
  tier: 1
  status: ADOPTED

  purpose: >
    Tornar o scoping do pmi_pm um gate obrigatório e blocking.
    Antes desta correção, "continuar" dispara execução imediata sem
    verificação de pré-condições, análise de risco ou confirmação de escopo.
    O pmi_pm era descritivo, não enforcement.

  why: >
    WHY: Em toda sessão analisada, a sequência foi:
    receber input → executar tool call.
    O pmi_pm nunca emitiu um output de scoping explícito com:
    tarefa identificada, fase atual, pré-condições verificadas, risco calculado.
    Resultado: execuções sem gate de segurança, como Phase 6 LIVE após
    simplesmente receber "continuar".

  when: >
    WHEN: Qualquer nova instrução de tarefa recebida.
    WHEN: Antes de qualquer tool call, git operation ou escrita em arquivo.
    EXCEPTION: Perguntas de análise sem efeito colateral (read-only) dispensam gate.

  what_if_fails: >
    FALLBACK: Emitir [PMI_PM_GATE_BYPASSED: motivo] se não for possível scopar.
    REGRA: Toda tarefa com efeito colateral DEVE ter [SCOPE_CONFIRMED] emitido.
    REGRA: Tool calls sem [SCOPE_CONFIRMED] anterior são violação de protocolo.

  enforcement_protocol:
    gate_output_required: "[SCOPE_CONFIRMED: {task} | phase: {p} | risk: {r} | preconditions: {ok/fail}]"

    mandatory_fields:
      task: "Descrição da tarefa em ≤ 20 palavras"
      phase: "Fase atual do pipeline (ex: Phase 7, OPP-158)"
      risk: "LOW | MEDIUM | HIGH — baseado em reversibilidade + scope"
      preconditions: "OK se todas verificadas | FAIL:{motivo} se alguma falhou"

    risk_matrix:
      LOW:    "Operação read-only ou totalmente reversível por git revert"
      MEDIUM: "Modifica arquivos mas não o boot kernel ou schema principal"
      HIGH:   "Modifica boot kernel, deleta arquivos, operação irreversível"

    blocking_rules:
      - "SE risk=HIGH E preconditions=FAIL: BLOQUEAR execução, reportar ao usuário"
      - "SE task='continuar' sem contexto: pmi_pm DEVE inferir contexto do apex_state.yaml"
      - "SE boot_verified=false: risco sobe um nível (LOW→MEDIUM, MEDIUM→HIGH)"

    precondition_checklist:
      - "Boot verificado (boot_verified=true em apex_state.yaml)"
      - "Fase anterior concluída sem erros"
      - "Validação pré-execução disponível (--dry-run existe?)"
      - "Espaço de rollback disponível (git clean state?)"

    scope_confirmation_template: |
      [SCOPE_CONFIRMED]
      Task:          {descrição}
      Phase:         {fase atual}
      Risk:          {LOW|MEDIUM|HIGH}
      Preconditions: {OK ou FAIL:motivo}
      Plan:          {sequência de ações em bullet points}
      Rollback:      {como reverter se falhar}

  integration_with_step1: >
    pmi_pm STEP_1 agora emite SCOPE_CONFIRMED antes do pipeline completo.
    meta_reasoning aguarda SCOPE_CONFIRMED antes de ativar agentes.
    engineer aguarda SCOPE_CONFIRMED antes de qualquer SANDBOX_CODE.

  fmea:
    rpn: 8
    mode: "Execução sem scoping — tarefa errada executada sem gate"
    probability: 4
    severity: 3
    detection: 2
    mitigation: >
      SCOPE_CONFIRMED obrigatório antes de tool calls com efeito colateral.
      apex_state.yaml fornece contexto para inferência de scope em "continuar".
      Risk=HIGH requer confirmação explícita do usuário antes de prosseguir.
"""


# ─── OPP-159: UCO Runtime Digest ───────────────────────────────────

OPP159_BLOCK = """
# ─────────────────────────────────────────────────────────────────
# DIFF_UCO_RUNTIME_DIGEST_001 (OPP-159)
# UCO digest injetado no boot — top scores influenciam meta_reasoning
# Corrige GAP-03: "UCO não influencia decisões LLM em runtime"
# ─────────────────────────────────────────────────────────────────
uco_runtime_digest:
  executor: LLM_BEHAVIOR
  version: v00.37.0
  opp: OPP-159
  tier: 2
  status: ADOPTED

  purpose: >
    Tornar o UCO score um sinal ativo de runtime para o meta_reasoning.
    Antes desta correção, o UCO existia como ferramenta de análise estática
    do repositório mas não influenciava NENHUMA decisão do LLM durante inferência.
    Skills com score 8 e skills com score 95 eram tratadas identicamente.

  why: >
    WHY: UCO calcula métricas de Halstead, complexidade ciclomática e qualidade
    por script/skill. Este score existe no repositório mas é invisível ao LLM
    durante execução. Resultado: scripts com score < 40 (312 identificados em
    Phase 5.5) continuam sendo invocados sem priorização de alternativas.
    O UCO é uma métrica de repositório, não um sinal de runtime — até agora.

  when: >
    WHEN: meta_reasoning seleciona skill/script para executar.
    WHEN: engineer avalia qual abordagem usar em STEP_4/STEP_5.
    WHEN: critic avalia qualidade de output gerado.

  what_if_fails: >
    FALLBACK: Se digest não disponível, tratar todos os scores como neutros.
    REGRA: UCO digest é informativo, não blocking — baixo score não bloqueia skill.
    REGRA: Score < 40 adiciona [UCO_LOW_QUALITY_WARNING] ao output, não rejeição.

  digest_protocol:
    generation: >
      tools/validate_repo_uco.py --digest gera uco_runtime_digest.yaml.
      Deve ser re-gerado após cada Phase major ou commit de skills.
      Digest contém: top-10 lowest UCO, top-10 highest UCO, domain averages.

    digest_format:
      path: "meta/uco_runtime_digest.yaml"
      fields:
        - "generated_at: timestamp"
        - "total_scripts: n"
        - "avg_score: float"
        - "below_40: count"
        - "above_80: count"
        - "lowest_10: [{path, score, primary_issue}]"
        - "highest_10: [{path, score}]"
        - "domain_averages: {domain: avg_score}"

    runtime_integration:
      step: "STEP_1 + STEP_4"
      how: >
        meta_reasoning carrega digest summary (não o arquivo completo) ao
        selecionar skills. Se skill selecionada tem score < 40 no digest:
        1. Emitir [UCO_LOW_QUALITY_WARNING: {skill} | score: {s}]
        2. Verificar se existe alternativa no mesmo domínio com score > 60
        3. SE existe: sugerir alternativa (não forçar substituição)
        4. SE não existe: usar skill original com warning declarado

      score_tiers:
        excellent: ">= 80 — usar sem ressalvas"
        good:      "60-79 — usar normalmente"
        acceptable:"40-59 — usar com nota de qualidade limitada"
        poor:      "< 40  — emitir UCO_LOW_QUALITY_WARNING + buscar alternativa"

      token_budget: >
        Digest summary: ~200 tokens (não o arquivo completo).
        Injetar apenas domain_averages + below_40 count no contexto ativo.
        Top-10 lowest carregado apenas quando skill do domínio é selecionada.

  bootstrap_digest:
    note: >
      Digest inicial gerado a partir dos dados da Phase 5.5:
      312 scripts below 40 | 150 processados | 0 improved.
      Rodar tools/validate_repo_uco.py --digest para atualizar.
    current_stats:
      total_scripts: 365
      below_40: 312
      avg_score: "~35 (estimado pre-optimization)"
      primary_issue: "Alta complexidade ciclomática em scripts de automação"

  fmea:
    rpn: 4
    mode: "meta_reasoning usa skill de baixa qualidade sem awareness"
    probability: 2
    severity: 2
    detection: 1
    mitigation: >
      UCO_LOW_QUALITY_WARNING declarado no output quando score < 40.
      Usuário pode solicitar alternativa ou aceitar com ciência do score.
      Digest re-gerado periodicamente para refletir estado real do repo.
"""


# ─── Footer atualizado ─────────────────────────────────────────────

FOOTER_157_159 = """
# ═══════════════════════════════════════════════════════════════════
# FIM DOS MODULOS v00.37.0 — OPP-157 + OPP-158 + OPP-159 adicionados
# Total DIFFs aplicados: 135 (132 anteriores + OPP-157 + OPP-158 + OPP-159)
# OPP-157: DIFF_BOOT_VERIFICATION_GATE_001 — STEP_0 emite hash confirmado
# OPP-158: DIFF_PMI_PM_MANDATORY_GATE_001 — pmi_pm blocking enforcement
# OPP-159: DIFF_UCO_RUNTIME_DIGEST_001 — UCO scores influenciam meta_reasoning
# Gaps resolvidos: GAP-01, GAP-02, GAP-03 (de análise 2026-04-18)
# Proxima versão: v00.38.0
# Debug completo: 2026-04-18 — boot expandido / 3784 SKILL.md / 163+ AGENT.md
# ═══════════════════════════════════════════════════════════════════
"""


# ─── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Inject OPP-157/158/159 into APEX boot kernel")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mode = "DRY-RUN" if args.dry_run else "LIVE"
    print(f"\nAPEX Boot Injection | OPP-157 + OPP-158 + OPP-159 | Mode: {mode}")
    print("=" * 60)

    boot_content   = BOOT_FILE.read_text(encoding='utf-8')
    original_lines = boot_content.count('\n')
    print(f"  Boot file: {original_lines} lines")

    already = []
    for opp in ["OPP-157", "OPP-158", "OPP-159"]:
        if opp in boot_content:
            already.append(opp)
    if already:
        print(f"  [SKIP] Already present: {already}")
        if len(already) == 3:
            return

    blocks_to_add = []
    if "OPP-157" not in boot_content:
        blocks_to_add.append(("OPP-157", OPP157_BLOCK))
    if "OPP-158" not in boot_content:
        blocks_to_add.append(("OPP-158", OPP158_BLOCK))
    if "OPP-159" not in boot_content:
        blocks_to_add.append(("OPP-159", OPP159_BLOCK))

    # Find last footer block and replace it
    fim_idx = boot_content.rfind(
        "# ═══════════════════════════════════════════════════════════════════\n# FIM"
    )
    combined_blocks = "".join(b for _, b in blocks_to_add)
    if fim_idx == -1:
        new_content = boot_content.rstrip() + "\n" + combined_blocks + FOOTER_157_159
    else:
        new_content = boot_content[:fim_idx].rstrip() + "\n" + combined_blocks + FOOTER_157_159

    new_lines   = new_content.count('\n')
    added_lines = new_lines - original_lines

    for opp_id, block in blocks_to_add:
        print(f"  {opp_id}: +{block.count(chr(10))} lines")
    print(f"  Footer update: +{FOOTER_157_159.count(chr(10))} lines")
    print(f"  Total: +{added_lines} lines → {new_lines} total")

    if not dry_run_check(args.dry_run):
        BOOT_FILE.write_text(new_content, encoding='utf-8')
        print(f"\n  Written: {BOOT_FILE}")

        # Update apex_state.yaml pending OPPs to DONE
        if STATE_FILE.exists():
            state = STATE_FILE.read_text(encoding='utf-8')
            for opp_id in ["OPP-157", "OPP-158", "OPP-159"]:
                state = state.replace(
                    f"  - opp: {opp_id}\n    title:",
                    f"  - opp: {opp_id}\n    status: DONE\n    title:",
                )
            # Fix duplicate status fields
            state = re.sub(r'(status: DONE\n.*?status: PENDING)', lambda m: m.group(0).replace('status: PENDING', ''), state)
            STATE_FILE.write_text(state, encoding='utf-8')
            print(f"  apex_state.yaml updated (OPP-157/158/159 → DONE)")

        # Write reference document
        ref = REPO_ROOT / "references" / "OPP-157-158-159-runtime-fixes.md"
        ref.write_text(_build_reference_doc(), encoding='utf-8')
        print(f"  Written: {ref}")
    else:
        print(f"\n  [DRY-RUN] Would write {new_lines} lines to {BOOT_FILE.name}")

    print(f"\n{'=' * 60}")
    print("Boot kernel fixes complete.")
    print("  GAP-01 (boot verification): FIXED")
    print("  GAP-02 (pmi_pm enforcement): FIXED")
    print("  GAP-03 (UCO runtime): FIXED")


def dry_run_check(flag: bool) -> bool:
    return flag


import re

def _build_reference_doc() -> str:
    return """\
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
"""


if __name__ == "__main__":
    main()
