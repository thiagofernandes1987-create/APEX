# APEX v00.39.1 — Paged Microkernel Distribution

> **Arquitetura:** MICROKERNEL + PAGED COGNITION
> **Kernel:** v00.39.0 · sha8 `56c87491` · master sha8 `a3124099`
> **Compilado:** 2026-06-11 por `apex_compiler v2.1 LEAN` (OPP-163+171)
> **Resolve:** GAP-06 (monólito boot 20K+ linhas vs context window — OPP-161)

## O que mudou em relação ao v00.37.0 (monólito)

| Aspecto | v00.37.0 (monólito) | v00.39.1 (paged) |
|---|---|---|
| Boot | 1 arquivo `.txt` de ~20.173 linhas | `apex_boot_kernel.yaml` (~13K tokens, 991 linhas) |
| Carregamento de módulos | Tudo em contexto de uma vez | `page_load(key)` sob demanda |
| Páginas | — | 111 páginas em `pages/<key>.yaml` |
| Integridade | sha8 do arquivo único | sha8 por página vs `page_manifest` do kernel |
| Seleção de regras | Todas carregadas | `rule_salience_scheduler` top-K (OPP-166) |

## Protocolo de boot (STEP_0)

1. Emitir `[BOOT_VERIFIED: {sha8} | kernel v00.39.0]` (OPP-157)
2. Executar `apex_runtime_probe` → `APEX_SESSION_CAPS` (OPP-119)
3. `llm_runtime_adapter` define profile (SR_39)
4. `rule_salience_scheduler` seleciona top-K regras da tarefa (OPP-166)
5. Demais módulos: `page_load(key)` sob demanda — NUNCA assumir conteúdo de página não carregada

## Conteúdo

```
apex_boot_kernel.yaml     # kernel lean — ponto de entrada do boot
pages/                    # 111 páginas carregáveis sob demanda
apex_semantic_index.py    # índice semântico (resolução de skills/páginas)
apex_semantic_index.pkl   # índice pré-computado
validation_report.json    # ["clean"] — validação da distribuição
```

## Boot verificado nesta sessão

```
[BOOT_VERIFIED: 56c87491 | kernel v00.39.0 | profile: FULL_CLAUDE_CODE
 | probe: ast+git+numpy+scipy+sqlite3+threads ✓]
```
