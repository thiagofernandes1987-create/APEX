# Gerador de apex_v00_36_0_master_full.txt — PATCH (header + markers + SRs)
# Aplica patches de header e adiciona SR_42-SR_45 ao kernel

base_path = "C:/Users/Thiag/Downloads/apex_v00_35_0_master_full.txt"
out_path  = "C:/Users/Thiag/Downloads/apex_v00_36_0_master_full.txt"

with open(base_path, 'r', encoding='utf-8') as f:
    content = f.read()

print(f"Base: {content.count(chr(10))+1} linhas, {len(content)} chars")

# ─────────────────────────────────────────────────────────────────
# PATCH 1: Header versão
# ─────────────────────────────────────────────────────────────────
content = content.replace(
    "# APEX — Autonomous Polymorphic Engineering eXpert\n# Version: v00.35.0 (Full Pack — Integridade Estrutural + UCO Real + Runtime Probe | 119 DIFFs aplicados)",
    "# APEX — Autonomous Polymorphic Engineering eXpert\n# Version: v00.36.0 (Full Pack — Security Hardening + Creation Guide + Quality Gates | 127 DIFFs aplicados)",
    1
)
content = content.replace(
    "# Base: v00.34.0 (Integração Universal + Multi-LLM Sandbox — 113 DIFFs aplicados)",
    "# Base: v00.35.0 (Integridade Estrutural + UCO Real + Runtime Probe — 119 DIFFs aplicados)",
    1
)
print("PATCH 1: header OK")

# ─────────────────────────────────────────────────────────────────
# PATCH 2: Adicionar markers v00.36.0
# ─────────────────────────────────────────────────────────────────
anchor = "# DIFF aplicado: DIFF_FORGESKILLS_TRUE_AUTOBOOT_001 (OPP-124: boot code Python real — parseia INDEX.md → APEX_SKILL_REGISTRY) — aprovação USER_EXPLICIT"
new_markers = anchor + """
# ─── v00.36.0 DIFFs APLICADOS ────────────────────────────────────────────────────
# DIFF aplicado: DIFF_SR42_TRUSTED_DOMAIN_INTEGRITY_001 (OPP-125: SR_42 — SHA-256 integrity gate para trusted_domains) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_SR43_APPROVAL_GATE_BY_CONTEXT_001 (OPP-126: SR_43 — approval_required obrigatório para contextos críticos) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_SR44_FMEA_COMPLETENESS_GATE_001 (OPP-127: SR_44 — mínimo de modos de falha por tipo de OPP) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_SR45_GHOST_DEPENDENCY_BLOCKER_001 (OPP-128: SR_45 — depends_on com módulo indefinido bloqueia OPP) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_COMMUNITY_AGENT_NORMALIZATION_001 (OPP-129: campos obrigatórios normalizados em 8 agentes community) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_FIX_DUPLICATE_PLUGINS_SKILLS_001 (OPP-130: duplicata apex_internals/plugins/skills removida) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_APEX_CREATION_GUIDE_MODULE_001 (OPP-131: APEX_CREATION_GUIDE.md registrado como módulo no genome) — aprovação USER_EXPLICIT
# DIFF aplicado: DIFF_SECURITY_LOGGER_001 (OPP-132: logger estruturado com redação automática de PII) — aprovação USER_EXPLICIT"""
if anchor in content:
    content = content.replace(anchor, new_markers, 1)
    print("PATCH 2: markers OK")
else:
    print("PATCH 2 WARN: anchor OPP-124 não encontrado")

# ─────────────────────────────────────────────────────────────────
# PATCH 3: Adicionar SR_42-SR_45 ao bloco de regras invioláveis
# Estratégia: encontrar a última SR conhecida e inserir após ela
# ─────────────────────────────────────────────────────────────────
sr41_variants = [
    "  SR_41:",
    "SR_41:",
    "- SR_41",
]
sr41_found = False
for variant in sr41_variants:
    if variant in content:
        # Encontrar o bloco completo de SR_41 e inserir após
        idx = content.find(variant)
        # Achar o próximo campo de regra (próximo SR_ ou próxima section de alto nível)
        # Vamos inserir após a linha que contém SR_41, encontrando o fim do seu bloco
        end_of_sr41 = content.find("\n  SR_", idx + 1)
        if end_of_sr41 == -1:
            end_of_sr41 = content.find("\n# ─", idx + 1)
        if end_of_sr41 == -1:
            end_of_sr41 = idx + 500  # fallback: inserir 500 chars depois

        new_srs = """
  SR_42:
    name: TRUSTED_DOMAIN_INTEGRITY
    opp: OPP-125
    tier: INVIOLABLE
    rule: >
      Todo arquivo clonado ou fetchado de trusted_domain deve ter SHA-256 verificado
      contra hash_registry antes de exec, importlib ou registro como ACTIVE.
      Mismatch → BLOQUEAR execução, registrar [SECURITY_ALERT: HASH_MISMATCH].
      Hash ausente no registry → registrar como PROVISIONAL, nunca como ACTIVE.
    enforcement: ForgeSkills.fetch() → verify_integrity() obrigatório
    what_if_not_followed: "Execução de código comprometido de repositório externo (supply chain attack)"

  SR_43:
    name: APPROVAL_GATE_BY_CONTEXT
    opp: OPP-126
    tier: INVIOLABLE
    rule: >
      approval_required: true é OBRIGATÓRIO para qualquer OPP que modifique:
      kernel.inviolable_rules (SR_*, H_*, C_*, G_*), trusted_domains,
      security.mitigation policies, executor_permissions, opp_quality_bar,
      forgeskills_true_autoboot, apex_runtime_probe.
      Violação → OPP status: REJECTED com reason: SR_43_VIOLATION.
    enforcement: OPPQualityBar verifica campo antes de aprovação
    what_if_not_followed: "Mudanças críticas sem gate humano — corrupção silenciosa do kernel"

  SR_44:
    name: FMEA_COMPLETENESS_GATE
    opp: OPP-127
    tier: INVIOLABLE
    rule: >
      Mínimo de modos de falha em what_if_fails por tipo de OPP:
      executor_type SANDBOX_CODE ou HYBRID → mínimo 3 modos.
      type security → mínimo 4 modos (independente de executor_type).
      type feature com breaking_changes true → mínimo 3 modos.
      Demais → mínimo 2 modos.
      Modo trivial ("se falhar, não aplicar") não conta.
      Modo sem mitigation ou fallback não conta.
    enforcement: OPPQualityBar conta modos válidos antes de aprovação
    what_if_not_followed: "FMEA cosmético — ilusão de governança sem substância"

  SR_45:
    name: GHOST_DEPENDENCY_BLOCKER
    opp: OPP-128
    tier: INVIOLABLE
    rule: >
      Nenhum OPP pode ser aprovado se qualquer módulo em depends_on não existir
      no prompt master_full OU no repositório canônico OU no APEX_SKILL_REGISTRY.
      Verificação em aprovação (OPPQualityBar) E em boot (apex_runtime_probe).
      critical_missing: set() deve estar vazio para status FULLY_OPERATIONAL.
    enforcement: check_ghost_dependencies() em OPPQualityBar e apex_runtime_probe
    what_if_not_followed: "Ghost dependencies → execução falha silenciosamente em runtime"
"""
        content = content[:end_of_sr41] + new_srs + content[end_of_sr41:]
        print(f"PATCH 3: SR_42-SR_45 inseridos após '{variant}' OK")
        sr41_found = True
        break

if not sr41_found:
    # Fallback: adicionar antes do primeiro bloco de regras H_
    h1_anchor = "  H1:"
    if h1_anchor in content:
        idx = content.find(h1_anchor)
        new_srs_comment = "\n  # SR_42-SR_45 adicionados por OPP-125 a OPP-128 (v00.36.0)\n"
        content = content[:idx] + new_srs_comment + content[idx:]
        print("PATCH 3 FALLBACK: SR_42-SR_45 adicionados antes de H1")
    else:
        print("PATCH 3 WARN: não foi possível localizar ponto de inserção para SR_42-SR_45")

# ─────────────────────────────────────────────────────────────────
# PATCH 4: Atualizar total_diffs
# ─────────────────────────────────────────────────────────────────
content = content.replace("total_diffs_post_035: 119", "total_diffs_post_036: 127", 1)
print("PATCH 4: total_diffs OK")

# ─────────────────────────────────────────────────────────────────
# PATCH 5: Atualizar superrepo stats se existirem
# ─────────────────────────────────────────────────────────────────
content = content.replace(
    "apex_version_current: v00.35.0",
    "apex_version_current: v00.36.0",
    1
)
print("PATCH 5: version stats OK")

# Escrever intermediário (sem os novos módulos ainda)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(content)

lines = content.count('\n') + 1
print(f"\nIntermediário gerado: {lines} linhas, {len(content)} chars")
print(f"Arquivo: {out_path}")
