# APEX Bootstrap — Instruções para LLMs

**LEIA ESTE ARQUIVO PRIMEIRO ao iniciar qualquer sessão APEX.**

---

## STEP 0 — Identificar seu LLM e Capacidades

```
SE você tem ferramentas Bash, Read, Write, Glob, Grep → você é Claude Code (FULL)
SE você tem code_interpreter mas não Bash → você é GPT-4o (PARTIAL)
SE você tem tool_code Python mas não file system → você é Gemini (PARTIAL)
SENÃO → você é LLM puro (MINIMAL)
```

Registre em `session_metadata.llm_runtime = {FULL|PARTIAL|MINIMAL}`.

---

## STEP 1 — Carregar Index do Repositório

**Se url_access = true:**
```
Fetch: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/INDEX.md
Parse: bloco domain_map (YAML entre ```yaml e ```)
Registrar: todas as skills listadas como status PROVISIONAL no skill_registry
Log: [SUPERREPO_BOOT: {n} skills registradas | checksum: {sha}]
```

**Se url_access = false:**
```
Usar snapshot.skill_registry_state (última versão conhecida)
Se snapshot vazio → usar apenas skills do genome interno
Log: [SUPERREPO_BOOT: OFFLINE — usando snapshot local]
```

---

## STEP 2 — Carregar Instruções Específicas do Seu LLM

```
Fetch: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/meta/llm_compat.yaml
Ler seção do seu LLM detectado no STEP 0
Aplicar restrições e fallbacks listados
```

---

## STEP 3 — Pronto para Receber Problema

O APEX está pronto. Aguardar input do usuário para iniciar pipeline STEP_1 (pmi_pm scoping).

---

## Navegação Rápida de Skills

```
Problema matemático → skills/mathematics/
Problema jurídico  → skills/legal/
Problema de código → skills/engineering/software/
Problema financeiro → skills/finance/
Problema científico → skills/science/
Problema sobre o APEX → skills/apex_internals/
```

**Para qualquer skill**: leia o SKILL.md correspondente.
O frontmatter YAML tem `anchors` e `cross_domain_bridges` — eles ativam o `attraction_engine`.

---

## ForgeSkills — Carregar Skills Externas

**Claude (FULL)**:
```bash
# git clone automático via dynamic_skill_forge
# Ativado quando: skill_requested AND repo_url IN trusted_domains
# Requer: SR_37 AST scan obrigatório
```

**GPT-4o / Gemini (PARTIAL)**:
```python
# Usar fetch via urllib (OPP-109 — llm_agnostic_forgeskills)
import urllib.request
url = "https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/skills/{dominio}/{skill}/SKILL.md"
with urllib.request.urlopen(url, timeout=10) as r:
    content = r.read().decode()
# Parsear frontmatter YAML → registrar no skill_registry
```

**Llama / Local (MINIMAL)**:
```
Cole o conteúdo do SKILL.md diretamente no contexto.
Descreva o comportamento da skill como texto estruturado.
```

---

## Regras Críticas Neste Repositório

1. **G6**: Acesso a URLs SOMENTE se domínio em `trusted_domains`. Este repo está whitelistado desde OPP-104.
2. **SR_37**: Todo código clonado DEVE passar por AST scan antes de exec/importlib.
3. **SR_39**: Todo SANDBOX_CODE DEVE ter WHY/WHEN/HOW/WHAT_IF_FAILS.
4. **H5**: NUNCA auto-aplicar DIFFs — confirmação explícita obrigatória.
5. **C7**: Se `snapshot.capabilities.url_access = false` → não tentar fetch externo.

---

## URL Padrão para Fetch Direto

```
Base raw: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/
Exemplos:
  INDEX.md        → {base}INDEX.md
  SKILL compound  → {base}skills/mathematics/financial-math/compound-interest/SKILL.md
  Agent pmi_pm    → {base}agents/pmi_pm/AGENT.md
  LLM compat      → {base}meta/llm_compat.yaml
  Anchor taxonomy → {base}meta/anchors.yaml
```
