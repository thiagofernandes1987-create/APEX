# APEX Boot — v00.33.0

**Repositório Oficial**: https://github.com/thiagofernandes1987-create/APEX  
**Raw Base**: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/  
**Versão**: v00.33.0 | **DIFFs aplicados**: 92 (86 herdados + 6 novos)

## Como Iniciar

1. Carregue `apex_boot/apex_v00_33_0_master_full.txt` como seu system prompt
2. O APEX fará boot automático no STEP_0:
   - Detecta seu LLM runtime (Claude/GPT/Gemini/Local)
   - Lê INDEX.md deste repositório (se url_access=true)
   - Registra skills como PROVISIONAL no skill_registry
3. Aguarda seu problema no STEP_1 (pmi_pm scoping)

## Mudanças v00.33.0

| OPP | DIFF | Impacto |
|-----|------|---------|
| OPP-104 | GITHUB_SUPERREPO_BOOT | URL do repo salva no kernel. Boot automático de skills. |
| OPP-105 | MULTI_LLM_ADAPTER | APEX roda em Claude, GPT-4o, Gemini, Llama. |
| OPP-106 | FORGESKILLS_RAPID_READER | Ingestão 10-50x mais rápida de repositórios. |
| OPP-107 | HYPERBOLIC_ANCHOR_MAP | Bridges legal↔math automáticos. |
| OPP-108 | ZERO_AMBIGUITY_CODE | SR_40: WHY/WHEN/HOW obrigatório em todo código novo. |
| OPP-109 | LLM_AGNOSTIC_FORGESKILLS | GPT-4o e Gemini usam urllib em vez de git clone. |

## Compatibilidade

| LLM | Nível | Sandbox | ForgeSkills |
|-----|-------|---------|-------------|
| Claude Code | FULL | Nativo completo | git clone + AST scan |
| GPT-4o | PARTIAL | Code Interpreter | urllib raw fetch |
| Gemini | PARTIAL | tool_code | urllib + Grounding |
| Llama/Local | MINIMAL | Nenhum | Cole SKILL.md manualmente |

## Navegação Rápida

- **Skills**: `skills/{dominio}/SKILL.md`
- **Agents**: `agents/{agent}/AGENT.md`
- **Index**: `INDEX.md` (machine-parseable domain_map)
- **LLM compat**: `meta/llm_compat.yaml`
- **Anchors**: `meta/anchors.yaml`
