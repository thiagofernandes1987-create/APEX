# Auditoria "Autópsia" da Skill apex-method — v1.16.0 → v1.17.0

**Alvo:** pacotes enviados `apexmethod.skill` + `apexmethodneoformat.zip` (conteúdo idêntico,
layouts diferentes: plano vs árvore theneoai), auditados contra o repositório APEX integral
(v00.37 master de 20.496 linhas + boot v00.39.1 de 111 páginas).
**Método:** nenhuma alegação aceita sem validação concreta — toda contagem foi re-derivada
programaticamente do repo, todo bug foi reproduzido ao vivo antes de ser reportado, e toda
correção tem teste de regressão no benchmark.
**Data:** 2026-07-13.

---

## 1. Sumário executivo

A skill é uma destilação genuína e majoritariamente honesta do APEX: os 24 motores rodavam
(24/24 com dependências instaladas), o UCO embarcado é **byte-idêntico** ao autoral do repo,
a matemática bayesiana confere, e os 3 riscos do repo (V-01 pickle/V-02 marketplace/V-03
probe) **não** foram herdados. Porém a autópsia encontrou: **2 alegações de inventário falsas**
(cobertura de agentes e de skills nativas), **1 dependência oculta que matava o ponto de
entrada**, **9 bugs reproduzidos**, **4 itens de dead code**, **3 fraquezas de segurança**
e **5 chamadas esquecidas** (fluxo documentado ≠ fluxo executado). Tudo corrigido em v1.17.0;
benchmark ampliado de 24 para 27 testes, **27/27 PASS** — e o núcleo agora passa até num
ambiente sem sklearn/sympy.

## 2. Alegações do inventário vs realidade medida

| Alegação (inventario v1.15/1.16) | Medido no repo | Veredito |
|---|---|---|
| "183 agentes reais do APEX" (= todos) | **213 únicos** (219 AGENT.md; 30 de `community-awesome` ausentes do roster — mesmo ponto cego do `tools/generate_agent_roster.py`, que só varre `community-subagents` + `cs_*`) | 🔴 FALSO → corrigido: roster com 213 |
| "430 skills reais" + "Nada ficou de fora" | as 430 são TODAS de `theneoai/awesome-skills`; **0 das 3.784 skills nativas** do repo estavam indexadas | 🔴 FALSO → corrigido: `apex_native_skills_index.json` (3.784) + `repo_bridge` |
| "14 diffs (packs v00.33–36)" | packs reais contêm **18 DIFF_***; a lib tinha 6 DIFF_* + 8 itens mistos (12 DIFFs faltavam) | 🟠 INCOMPLETO → corrigido: 18/18 |
| "111 módulos" | 111 páginas em `apex_boot/v00_39_1/pages` — bate 1:1 com `module_registry.json` | 🟢 EXATO |
| "41 assets" | 41 diretórios em `algorithms/` — cobertura 1:1 | 🟢 EXATO |
| "18 MCPs" | 18 entradas; 5 dirs de `integrations/` (claude-commands, external-plugins, knowledge-work, official-plugins, plugins) fora do mcp_registry mas citados em apex-assets.md | 🟡 OK com nota |
| "24/24 PASS" | verdadeiro **somente** com sklearn+sympy instalados; num ambiente limpo: **19/24**, com o orchestrator (ponto de entrada) morrendo em ModuleNotFoundError | 🟠 ENGANOSO → corrigido: fallback `_tfidf.py` + verify degradável |
| "8C/44SR/18G/7H documentadas+enforçadas" | SR_36–40 enforçadas de verdade; refs citam 19/44 SRs e 2/18 Gs; **SR_46/47 (v00.39) ausentes** | 🟠 PARCIAL → SR_46/47 documentadas |
| UCO "nativizado" | `diff` = vazio vs `algorithms/uco/universal_code_optimizer_v4.py` | 🟢 FIEL |
| Matemática bayesiana | Beta(1,1)+8/10→0.75→ADOPT; posterior A=0.7407; gates R_acum — reproduzidos | 🟢 CORRETA |
| Versão | SKILL.md dizia 1.16.0, inventario dizia 1.15.0 | 🟠 DRIFT → unificado 1.17.0 |
| guards.md "all 18 scripts pass SR_40" | eram 24 scripts | 🟠 DRIFT → corrigido |

## 3. Bugs encontrados (todos reproduzidos ao vivo antes de corrigir)

| ID | Onde | Bug | Prova | Correção |
|---|---|---|---|---|
| B-01 | router/gravity/agent_registry/orchestrator | sklearn como dependência RÍGIDA — ponto de entrada crashava em ambiente limpo | benchmark 19/24 sem sklearn | `_tfidf.py` (TF-IDF+cosine puro stdlib) como fallback |
| B-02 | skill_scout + guards | `.loads()` em REJECT irrestrito → **`json.loads` rejeitava qualquer skill legítima** (FP crítico no fluxo de descoberta) | scan de `json.loads` → REJECTED | reject só para receivers deserializadores (pickle/marshal/dill/shelve/yaml/joblib); resto vira REVIEW |
| B-03 | orchestrator.`_safe_arith` | `9**9**9` congela o processo (bignum ilimitado no caminho EXPRESS) | hang >2s reproduzido | expoente literal ≤64 obrigatório |
| B-04 | orchestrator.`express_check` | case-sensitive: "What is 2+2?" não caía no caminho aritmético | retornava `answer: None` | lowercase antes do strip |
| B-05 | orchestrator.`pmi_converge` | candidato numérico com answer não-numérica → ValueError não tratado | crash reproduzido | degrada o candidato para qualitativo |
| B-06 | curated.`best_for_task` | parser de installs lia "1.2M" como 1.2 e "391K" como 391 → ordenação por popularidade invertida | teste unitário | parser correto (K=1e3, M=1e6) |
| B-07 | mental_interpreter.`optimal_size_for_target` | `ceil` onde a desigualdade exige `floor`: p=0.9, ε=0.05 → n=3 → confiabilidade acumulada 0.857 **< alvo 0.9** | verificação aritmética | `floor` + regressão `(1-ε)^n ≥ p` |
| B-08 | fractal_compression | hipótese já podada continuava dominando outras (estado de `a` nunca checado) | inspeção + teste | `a["state"] != "ACTIVE" → continue` |
| B-09 | hypothesis_dag.`register` | o reset >200 nós apagava o próprio log de eventos antes de gravar `[DAG_RESET]` | inspeção | preserva `events` através do reset |

## 4. Segurança

**Não herdado do repo (verificado):** sem `pickle.load` (V-02), sem dependência da org
`apex-marketplace` (V-01 — aparece só numa string de demo), sem sonda fora da allowlist (V-03).

| ID | Fraqueza | Correção |
|---|---|---|
| S-01 | `fetch_text` seguia **redirects para fora da allowlist** (host só era checado na URL inicial) | re-checa o host da URL FINAL (`r.geturl()`); + cap de 2MB |
| S-02 | `forge_load_gate` (SR_37) não via `getattr` dinâmico — `getattr(os, 's'+'ystem')` passava pelo gate estrito | `getattr` com nome não-literal = REJECT |
| S-03 | fetch sem pin de commit = confiança num branch móvel (classe V-01) | `repo_bridge` aceita `APEX_REPO_REF`/`set_ref()` para pinar sha |

Limite honesto (mantido no SKILL.md): o scanner AST é um gate estático best-effort, não um
sandbox; a fronteira real continua sendo a aprovação humana (H5).

## 5. Dead code e chamadas esquecidas

- **Dead code removido/ativado:** `ATTRACTION_RADIUS` e `NEIGHBOR_COLOAD` declarados e nunca
  usados (o radius estrito agora é usado com fallback relaxado); `_load_cat` duplicata
  byte-a-byte de `_load` (virou alias); `import re` sem uso em `gravity.plan`; função interna
  `score()` morta em `curated.best_for_task`; `flatten`/`sigmoid_grad` órfãs no UCO
  (mantidas — o arquivo é espelho fiel do autoral do repo, drift proposital = falso "fiel").
- **Chamadas esquecidas (fluxo do inventário ≠ código):** o diagrama prometia
  `mental_interpreter` no cálculo do modo — nunca era chamado (agora `run()` devolve
  `phase_plan` com `n_final`); `bayes.filter_priors` (G5) implementado e jamais invocado
  (agora aplicado no PMI quando candidatos trazem `prior`); `snapshot`/`apex_st_metric` no
  fim do fluxo são passos do LLM, não do código — documentado como tal. `pot.run_parallel`,
  `numeric.rk4_trajectory`, `guards.zero_ambiguity_lint_*` e `curated.preassign` são API
  pública documentada (não são dead code).

## 6. Integração do repositório completo + descoberta de skills (novo em v1.17.0)

- **`scripts/repo_bridge.py`** — TODO o repo endereçável pela skill: 3.784 skills nativas
  (`search_native`/`native_skill`), 213 agentes (`agent`), 111 páginas de boot (`page`),
  qualquer arquivo (`fetch`) — clone local quando existe, senão GitHub raw com allowlist,
  checagem de redirect, cap de tamanho, ref pinável e recusa de path traversal.
- **`catalog/apex_native_skills_index.json`** — índice completo gerado do repo (3.784
  entradas: id, categoria, path, descrição).
- **Descoberta em cascata com aprovação:** `gravity.plan()` agora resolve lacunas na ordem
  (1) biblioteca nativa → (2) busca skills.sh (URL pronta) → (3) busca GitHub (URL pronta),
  emitindo `ASK_USER_TO_APPROVE_INSTALL`: Claude apresenta o candidato e **só instala
  (`npx skills add owner/repo`) após aprovação explícita do usuário** (H5). Nada é
  auto-instalado ou auto-executado.

## 7. Verificação final

```
python3 tests/benchmark.py    # 27/27 PASS (~1.4s)
```

- 24 testes originais + `repo_bridge` + `_tfidf` + `audit_regressions` (um assert por bug).
- Em ambiente simulado SEM sklearn/sympy: orchestrator, router, gravity, agent_registry e
  verify continuam funcionando (degradação declarada, não crash).
- SKILL.md: 245 linhas (≤300), frontmatter neoformat válido, SR_40 auto-conformidade mantida.
