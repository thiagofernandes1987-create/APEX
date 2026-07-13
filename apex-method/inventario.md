# Inventário & Plano de Implantação — apex-method (super skill)

Skill **apex-method** v1.17.0 — destilação completa e executável do framework APEX no formato
theneoai/awesome-skills. Este documento é o inventário integral, o checklist de implantação, os
marcos, e a descrição de funcionamento para qualquer pessoa entender a estrutura.

---

## ✅ Checklist de implantação (tudo verificado)

### Marco 1 — Formato & validação
- [x] Frontmatter 100% válido contra `schema/frontmatter.schema.json` do theneoai
- [x] SKILL.md ≤ 300 linhas, seções § numeradas, Trigger Words, Scope & Limitations
- [x] Conformidade SR_40 (why/when/what-if-fails) em 26/26 scripts + SKILL.md
- [x] `.skill` instalável + `.zip` da árvore de repositório

### Marco 2 — Motores executáveis (26 scripts, 27/27 no benchmark)
- [x] Raciocínio: `orchestrator`, `mental_interpreter`, `pot`, `hypothesis_dag`, `fractal_compression`
- [x] Numérico/formal: `numeric` (RK4/Euler), `verify` (sympy), `geometry_estimator`
- [x] Bayesiano: `bayes` (beta-binomial, Ω, R_acum), `apex_st_metric`
- [x] Qualidade/segurança: `uco_gate`, `universal_code_optimizer_v4` (nativizado), `guards` (SR_36–40), `skill_scout`
- [x] Escalonamento: `geodesic_scheduler`, `verification_gate`
- [x] Integração do repo: `repo_bridge` (3.784 skills nativas + 213 agentes + 111 páginas + qualquer arquivo, allowlist + ref pinável); `_tfidf` (fallback puro-python, remove a dependência rígida de sklearn)
- [x] Skills/recursos: `router`, `gravity`, `curated`, `asset_manager`, `skill_forge`, `agent_registry`, `code_genetics`, `snapshot`

### Marco 3 — Catálogos (12, dados reais)
- [x] `apex_agents_roster.json` — **213 agentes** reais do APEX (auditoria v1.17.0: os 30 community-awesome que faltavam foram adicionados)
- [x] `agents_catalog.json` — 11 personas núcleo (método + especialistas)
- [x] `skills_catalog.json` — **430 skills** externas theneoai (URLs raw fetchable)
- [x] `apex_native_skills_index.json` — **3.784 skills nativas** do repo (índice completo, busca via `repo_bridge.search_native`)
- [x] `curated_skills.json` — melhores skills por domínio (skills.sh + repos)
- [x] `managed_assets.json` — **41 assets** (2 nativos + 39 terceiros indexados)
- [x] `mcp_registry.json` — **18 servidores MCP** por domínio
- [x] `module_registry.json` — **111 módulos** do APEX (executor + propósito)
- [x] `diffs_lib.json` — 26 entradas: os **18 DIFF_*** dos packs v00.33–36 (12 faltavam) + SR_42–45 + normalizações
- [x] `scripts_lib.json` — scripts com massa=LOC para a gravidade (26 no pacote)
- [x] `algorithms_map.json` — 8 repos skills.sh de alto valor mapeados
- [x] `uco_sensor_engines.json` — 9 motores do UCO-Sensor

### Marco 4 — Busca de skills sob demanda (skills.sh + GitHub)
- [x] `repo_bridge.search_native` resolve primeiro na biblioteca nativa (3.784)
- [x] `router` roteia a necessidade → melhor skill do catálogo
- [x] `gravity.plan()` detecta lacuna → candidatos nativos + URL de busca skills.sh + URL de busca GitHub + `ASK_USER_TO_APPROVE_INSTALL` (STAGED, H5)
- [x] `skill_scout` busca (allowlist) + AST-scan de dois níveis + estágio (gate H5/SR_37)
- [x] `curated` mapeia skills.sh reais (frontend 391K, backend, design, programação, brainstorm, MCP) + repos GitHub (finanças, matemática, medicina, ciências)

### Marco 5 — Testes / benchmark
- [x] `tests/benchmark.py` — 1 teste com asserções por módulo + regressões da auditoria (27/27 PASS)
- [x] `tests/benchmark_report.json` — relatório reutilizável para auditorias futuras
- [x] Executado: **27/27 PASS em ~1.4s** (e 24/27 num ambiente SEM sklearn/sympy — o pipeline degrada em vez de morrer)

### Marco 6 — Documentação
- [x] 18 referências (`references/*.md`) — 1 por subsistema
- [x] `Auditoria.md` — autópsia independente completa (executável vs fantasioso)
- [x] Este `inventario.md`

---

## 📦 Inventário completo

### Scripts (24) — o que cada um faz, entradas → saídas
| Script | Faz | In → Out |
|---|---|---|
| `orchestrator` | ponto de entrada: express→dissect→especialistas→PMI | task → {path,mode,disciplines,specialists,pmi} |
| `mental_interpreter` | v4: n_final + fases SPECULATION/WARMUP/PLANNING/PRODUCTION | (mode,depth,curvature,p_target) → phase plan |
| `pot` | Program-of-Thought em subprocess encadeado | steps[] → outputs |
| `numeric` | RK4/Euler para sistemas ODE | (deriv,s0,dt,steps) → estado final |
| `verify` | prova/refuta identidade (sympy, C8) | (lhs,rhs) → {tag} |
| `hypothesis_dag` | DAG acíclico, cascata BFS, snapshot edge-only | node/edge → affected set |
| `fractal_compression` | poda hipóteses (4 filtros) | hyps → {kept,report} |
| `geometry_estimator` | DELTA_ERR passo-duplo + block size | (deriv,s0,dt,integrator) → n_num |
| `bayes` | beta-binomial, posterior, Ω, R_acum | (priors,likelihoods) → posterior+decisão |
| `apex_st_metric` | progresso inter-sessão + estagnação | (prev,curr) → {dS2,curvature,trigger} |
| `uco_gate` | gate de qualidade de código (SR_33) | code → {status,engine,metrics} |
| `universal_code_optimizer_v4` | UCO 9-canais espectrais (nativizado) | code → métricas |
| `guards` | SR_36–40 enforçáveis | vários → PASS/REJECT |
| `skill_scout` | fetch+AST-scan+estágio de skill externa (SR_37) | url → snapshot_entry |
| `geodesic_scheduler` | ordena steps por ΔH/tokens (SR_34) | steps → plano ordenado |
| `verification_gate` | roteia hipóteses arriscadas (P≠NP) | (hyps,mode) → {verify,skip} |
| `router` | ranqueia skills por relevância (TF-IDF) | (task,catalog) → ranking |
| `gravity` | atração/sinergia → constelação + lacunas | task → constellation+install_requests |
| `curated` | mapa das melhores skills por domínio | domain → skills |
| `asset_manager` | gerencia/roteia assets + MCPs | need → assets/mcps |
| `skill_forge` | gera SKILL.md (CANDIDATE→ADOPTED) | args → SKILL.md |
| `agent_registry` | match tarefa→agente + concede skill | task → agentes; skill → competência |
| `code_genetics` | vaccine store (erro→correção, O(1)) | (erro,fix) → promoção |
| `snapshot` | estado de sessão com proveniência | findings → bloco de contexto |

### Catálogos (11), Referências (18), Testes (1 harness + report)

Ver Marco 3 e a pasta `references/`.

---

## 🔧 Como funciona (fluxo completo, ponta a ponta)

```
   pergunta do usuário
          │
          ▼
   orchestrator.run(task)
          │
   ┌──────┴───────┐
   │ express_check │  trivial (2+2)? → responde direto, PULA o pipeline
   └──────┬───────┘
          │ não-trivial
          ▼
   dissect(task)  →  disciplinas [engineering, finance, science, ...]
          │
          ▼
   para cada disciplina:  gravity.plan(sub-tarefa)
          │                     │
          │              ┌──────┴────────────────────────┐
          │              │ constelação (biblioteca):      │
          │              │  agente + skills + diffs + script (por atração/sinergia, TF-IDF massa)
          │              │ lacuna? → skills.sh search + install request (STAGED, gate H5)
          │              │           + MCP fallback (asset_manager/mcp_registry)
          │              └───────────────────────────────┘
          ▼
   modo (mental_interpreter): SCIENTIFIC/DEEP/STANDARD;  n_final = min(n_num, n_rel, MAX)
          │
          ▼
   execução dos sub-problemas:
     • numérico → pot + numeric(RK4) + verify(sympy)
     • código   → uco_gate (SR_33) + guards.forge_load_gate (SR_37)
     • hipóteses→ hypothesis_dag (acíclico) + fractal_compression (poda)
     • ordem    → geodesic_scheduler (ΔH/tokens, custo ético ∞)
     • verificar→ verification_gate (só arriscadas, P≠NP, budget 0.25)
          │
          ▼
   PMI convergência (bayes):
     • numérico → concordância × confiança (real)
     • qualitativo → posterior bayesiano + decisão Ω (0.72/0.5)
     • R_acum gate (produto janela-20; <0.30 = EARLY_EXIT)
          │
          ▼
   snapshot (proveniência) + apex_st_metric (progresso da sessão)
          │
          ▼
   resposta + confiança [APPROX]
```

**Aprendizado entre sessões:** `code_genetics` cristaliza erro→correção; `agent_registry` acumula
experiência dos agentes ao conceder skills aprovadas; `apex_st_metric` detecta estagnação e
dispara meta-aprendizado.

**Cobertura de regras:** SR_46/47 (v00.39) documentadas em `references/rules.md`.

**Segurança em toda a cadeia:** nada de terceiro é auto-instalado ou auto-executado — tudo passa
por `skill_scout` (AST-scan) + aprovação do usuário (H5). Guards SR_36–40 enforçados.

---

## 🎯 Rodar o benchmark (para auditorias futuras)

```bash
python3 tests/benchmark.py     # 27/27 PASS esperado; gera tests/benchmark_report.json
```

Compare `benchmark_report.json` entre versões para detectar regressões. Cada linha tem
módulo, status, tempo (ms) e a métrica-chave verificada.

---

## Nada ficou de fora?

Cobertos e integrados: **pipeline + 5 modos**, **8 C / 44 SR / 18 G / 7 H / 130 OPPs** (as
computáveis como código, as de política documentadas+enforçadas), **213 agentes**, **3.784 skills nativas indexadas + 430 externas**
+ mapa skills.sh, **14 diffs**, **24 scripts**, **111 módulos** catalogados, **UCO + UCO-Sensor
(9 motores)**, **camada bayesiana**, **gravidade/atração**, **busca de skills sob demanda**,
**MCP registry**, e o **benchmark**. O que é serviço externo (UCO-Sensor completo, feeds OSV) está
indexado com interface; o que é terceiro está gerenciado (não copiado).
