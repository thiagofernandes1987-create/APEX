# Inventário & Plano de Implantação — apex-method (super skill)

Skill **apex-method** v1.17.1 — destilação completa e executável do framework APEX no formato
theneoai/awesome-skills, agora **integrada ao repositório** (`apex-method/` no repo APEX) e
auditada em estilo autópsia (ver `AUDITORIA_SKILL.md`). Este documento é o inventário integral:
checklist por marco, fluxo de funcionamento, e o **backlog do que falta acrescentar/corrigir**.

---

## ✅ Checklist de implantação (tudo verificado por execução)

### Marco 1 — Formato & validação
- [x] Frontmatter 100% válido contra o schema neoformat (theneoai)
- [x] SKILL.md ≤ 300 linhas (245), seções § numeradas, Trigger Words, Scope & Limitations
- [x] Conformidade SR_40 (why/when/what-if-fails) em 26/26 scripts + SKILL.md
- [x] `.skill` instalável + `.zip` da árvore de repositório (v1.17.x reconstruídos)
- [x] Versão unificada (era 1.15 no inventário × 1.16 no SKILL.md — drift corrigido)

### Marco 2 — Motores executáveis (26 scripts, 27/27 no benchmark)
- [x] Raciocínio: `orchestrator`, `mental_interpreter`, `pot`, `hypothesis_dag`, `fractal_compression`
- [x] Numérico/formal: `numeric` (RK4/Euler), `verify` (sympy, degrada sem ele), `geometry_estimator`
- [x] Bayesiano: `bayes` (beta-binomial, Ω, R_acum), `apex_st_metric`
- [x] Qualidade/segurança: `uco_gate`, `universal_code_optimizer_v4` (byte-idêntico ao autoral), `guards` (SR_36–40), `skill_scout`
- [x] Escalonamento: `geodesic_scheduler`, `verification_gate`
- [x] Skills/recursos: `router`, `gravity`, `curated`, `asset_manager`, `skill_forge`, `agent_registry`, `code_genetics`, `snapshot`
- [x] Integração do repo: `repo_bridge` (3.784 skills nativas + 213 agentes + 111 páginas + qualquer arquivo)
- [x] Resiliência: `_tfidf` (fallback puro-Python — o núcleo funciona SEM sklearn/sympy instalados)

### Marco 3 — Catálogos (12, dados reais re-derivados do repo)
- [x] `apex_agents_roster.json` — **213 agentes** (auditoria: os 30 `community-awesome` que faltavam foram adicionados)
- [x] `agents_catalog.json` — 11 personas núcleo (método + especialistas + PMI)
- [x] `apex_native_skills_index.json` — **3.784 skills nativas** do repo (antes: ZERO indexadas)
- [x] `skills_catalog.json` — 430 skills externas theneoai (URLs raw fetchable, 3/3 amostradas OK)
- [x] `curated_skills.json` — melhores skills por domínio (skills.sh + repos)
- [x] `managed_assets.json` — 41 assets (cobertura 1:1 com `algorithms/`)
- [x] `mcp_registry.json` — 18 servidores MCP por domínio
- [x] `module_registry.json` — 111 módulos (bate 1:1 com as páginas do boot v00.39.1)
- [x] `diffs_lib.json` — **18/18 DIFF_*** dos packs v00.33–36 (12 faltavam) + SR_42–45 + normalizações
- [x] `scripts_lib.json` — 26 scripts (massa=LOC, para a gravidade)
- [x] `algorithms_map.json` — 8 repos skills.sh de alto valor mapeados
- [x] `uco_sensor_engines.json` — 9 motores do UCO-Sensor

### Marco 4 — Integração TOTAL do repositório APEX
- [x] `repo_bridge.fetch(path)` — qualquer arquivo do repo (clone local ou GitHub raw allowlisted)
- [x] `repo_bridge.search_native(query)` + `native_skill(path)` — as 3.784 skills nativas
- [x] `repo_bridge.agent(id)` — qualquer AGENT.md dos 213; `page(key)` — qualquer uma das 111 páginas
- [x] Segurança da ponte: allowlist de host, checagem de redirect na URL FINAL, cap de 2MB,
      recusa de path traversal, ref pinável (`APEX_REPO_REF`) contra branch móvel
- [x] Conteúdo buscado é DADO até ser vetado (SR_37/H5 continuam valendo antes de executar)

### Marco 5 — Descoberta de skills sob demanda (nativa → skills.sh → GitHub)
- [x] `repo_bridge.search_native` resolve PRIMEIRO na biblioteca nativa (3.784)
- [x] `router` roteia a necessidade → melhor skill do catálogo externo (com fallback sem sklearn)
- [x] `gravity.plan()` detecta lacuna → candidatos nativos + URL de busca **skills.sh** + URL de
      busca **GitHub** + `ASK_USER_TO_APPROVE_INSTALL` (STAGED — o usuário aprova, nada auto-instala)
- [x] `skill_scout` fetch (allowlist) + AST-scan de dois níveis + estágio no snapshot (gate H5/SR_37)
- [x] FP crítico corrigido: `json.loads` não é mais rejeitado (só deserializadores reais:
      pickle/marshal/dill/shelve/yaml/joblib)

### Marco 6 — Testes / benchmark
- [x] `tests/benchmark.py` — 1 teste com asserções por módulo + regressões da auditoria (**27/27 PASS**)
- [x] Regressão por bug: um assert para cada um dos 10 bugs corrigidos
- [x] Ambiente limpo simulado (sem sklearn/sympy): núcleo continua vivo, degradação declarada
- [x] `tests/benchmark_report.json` — relatório reutilizável para auditorias futuras

### Marco 7 — Auditoria autópsia (v1.16.0 → v1.17.1)
- [x] 2 alegações falsas de inventário corrigidas (183→213 agentes; 0→3.784 skills nativas)
- [x] 10 bugs reproduzidos ao vivo e corrigidos (cada um com teste):
      sklearn rígido matando o orchestrator · FP `json.loads` · DoS `9**9**9` no EXPRESS ·
      express case-sensitive · crash do PMI com numérico inválido · ordenação de installs
      ("1.2M"→1.2) · ceil/floor no n_rel (confiabilidade abaixo do alvo) · hipótese podada
      dominando · `[DAG_RESET]` apagando o próprio log · **caos envenenando o R_acum**
      (divergência proposital ≠ cadeia não-confiável; o caos segue no debate, sai do gate)
- [x] 3 fraquezas de segurança fechadas (redirect fora da allowlist; `getattr` dinâmico furando
      SR_37; fetch sem pin de commit)
- [x] Dead code tratado (radius não usados → ativados; `_load_cat` duplicado; `score()` morta)
- [x] Chamadas esquecidas ligadas (`mental_interpreter` no run(); `filter_priors`/G5 no PMI)
- [x] SR_46/47 (exclusivas do v00.39) documentadas em `references/rules.md`
- [x] V-01/V-02/V-03 do repositório verificados como NÃO herdados pela skill

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
   dissect(task) → disciplinas [engineering, finance, science, ...]
          │
          ▼
   para cada disciplina: gravity.plan(sub-tarefa)
          │        constelação: agente + skills + diffs + script (atração TF-IDF × massa)
          │        lacuna? → search_native (3.784) → skills.sh URL → GitHub URL
          │                  → ASK_USER_TO_APPROVE_INSTALL (H5) + fallback MCP/skill_forge
          ▼
   modo + phase_plan (mental_interpreter): n_final = max(MIN, min(n_num, n_rel, MAX))
          │
          ▼
   execução dos sub-problemas:
     • numérico → pot (encadeado: saída→entrada) + numeric(RK4) + verify(sympy)
     • código   → uco_gate (SR_33) + guards.forge_load_gate (SR_37)
     • hipóteses→ hypothesis_dag (acíclico) + fractal_compression (poda)
     • ordem    → geodesic_scheduler (ΔH/token, custo ético ∞)
     • verificar→ verification_gate (só arriscadas, P≠NP, budget 25%)
          │
          ▼
   PMI convergência (bayes):
     • numérico → concordância × confiança (real)
     • qualitativo → posterior bayesiano + decisão Ω (0.72/0.5) + G5 filter_priors
     • R_acum gate (janela 20; <0.30 = EARLY_EXIT) — stance do caos EXCLUÍDA do gate
          │
          ▼
   snapshot (checklist + marcos + proveniência WHAT/WHERE/HOW/[APPROX])
   + apex_st_metric (progresso; 2× FLAT → meta-aprendizado)
          │
          ▼
   resposta + confiança [APPROX]  — releitura do snapshot obrigatória ao retomar sessão
```

**Multi-agentes (honesto):** personas sequenciais com competência/experiência; o caos existe
para impedir convergência prematura (SR_11: nunca vira achado principal sem corroboração);
o LLM debate; o PMI decide com matemática real. Paralelismo genuíno só na EXECUÇÃO
(ThreadPoolExecutor sobre subprocessos PoT já gerados — 3×0.4s medidos em 0.42s).

---

## 📋 Backlog — o que falta acrescentar ou corrigir (pontos levantados nas auditorias)

### P1 — Alto impacto na qualidade
- [ ] **Roteamento por embeddings reais** (substituir/complementar TF-IDF): a atração é lexical
      e cruza mal PT↔EN — no teste ponta a ponta, disciplinas ficaram sem agente atraído e
      nenhum diff foi puxado (textos dos diffs em PT, tarefa em EN). Alternativas: embeddings
      locais, ou normalizar todos os textos de catálogo para EN, ou índice bilíngue.
- [ ] **Enriquecer o índice nativo**: descrições truncadas em 110 chars fazem buscas como
      "bayesian" retornarem vazio; gerar índice com descrição completa + trigger words + tags
      (custo: ~1–2MB de catálogo, aceitável).
- [ ] **Traduzir/normalizar os textos da `diffs_lib`** para que diffs participem de verdade da
      constelação gravitacional.

### P2 — Segurança e fonte da verdade (a maioria no REPOSITÓRIO, não na skill)
- [ ] **V-01 (repo)**: org `apex-marketplace` reivindicável em trusted_domains → registrar a
      org ou remover; pin por sha.
- [ ] **V-02 (repo)**: `apex_semantic_index.pkl` desserializado com `pickle.load` (RCE se
      trocado) → reconstruir via `build()` a partir de texto.
- [ ] **V-03 (repo)**: sonda de rede usa `httpbin.org`, fora da própria allowlist G6 → sondar
      host permitido.
- [ ] **Corrigir `tools/generate_agent_roster.py` na fonte**: varrer também `community-awesome`
      (o ponto cego que gerou o roster incompleto herdado pela skill).
- [ ] **`executor:` ausente em 40+ páginas** do boot (viola SR_40) → linter no compilador.
- [ ] **Pin de commit por padrão no `repo_bridge`**: hoje `APEX_REPO_REF` default é `main`
      (branch móvel); ao estabilizar, publicar um sha/tag recomendado no SKILL.md.

### P3 — Completude e polimento
- [ ] **Monte Carlo real como script**: portar o `monte_carlo_simulator` (módulo SAND do repo)
      para `scripts/`, para que hipóteses QUANTIFICÁVEIS no PMI sejam decididas por simulação
      codável (mantendo a regra: ponderação qualitativa nunca se chama "Monte Carlo").
- [ ] **Documentar as 25 SRs restantes**: `references/rules.md` cobre a essência + SR_46/47,
      mas 19/44 SRs são citadas nominalmente; enumerar as demais (mesmo as 🔵 de política).
- [ ] **5 diretórios de `integrations/` fora do `mcp_registry`** (claude-commands,
      external-plugins, knowledge-work, official-plugins, plugins) → indexar ou justificar.
- [ ] **Wire opcional de `snapshot`/`apex_st_metric` no `orchestrator.run()`**: hoje o fim do
      fluxo (snapshot + métrica de progresso) é disciplina do LLM; um parâmetro
      `run(..., snapshot=...)` fecharia o loop em código.
- [ ] **EVALUATION_REPORT independente**: o atual é auto-avaliado (declarado no próprio
      arquivo); uma avaliação externa com rubrica fecharia o ciclo de qualidade.
- [ ] **Persistência opcional do `code_genetics`** (SQLite como no APEX completo; hoje é
      dict de sessão com persistência externa via snapshot).

---

## 🎯 Rodar o benchmark (para auditorias futuras)

```bash
python3 tests/benchmark.py     # 27/27 PASS esperado; gera tests/benchmark_report.json
```

Compare `benchmark_report.json` entre versões para detectar regressões. Cada linha tem
módulo, status, tempo (ms) e a métrica-chave verificada. O bloco `audit_regressions` cobre
um assert por bug corrigido na autópsia.

---

## Nada ficou de fora?

Cobertos e integrados: **pipeline + 5 modos**, **8 C / 44 SR (+46/47 documentadas) / 18 G /
7 H / 130 OPPs** (as computáveis como código, as de política documentadas+enforçadas),
**213 agentes**, **3.784 skills nativas indexadas + 430 externas + mapa skills.sh**,
**18 DIFFs**, **26 scripts**, **111 módulos**, **UCO byte-idêntico + UCO-Sensor (9 motores
indexados)**, **camada bayesiana verificada**, **gravidade/atração**, **descoberta em cascata
com aprovação humana**, **MCP registry**, **ponte para o repositório inteiro**, e o
**benchmark 27/27**. O que é serviço externo (UCO-Sensor completo, feeds OSV) está indexado
com interface; o que é terceiro está gerenciado (não copiado). O que ainda falta está
explícito no backlog acima — nada pendente ficou sem registro.
