# Inventário & Plano de Implantação — apex-method (super skill)

Skill **apex-method** v1.43.0 — destilação completa e executável do framework APEX no formato
theneoai/awesome-skills, agora **integrada ao repositório** (`apex-method/` no repo APEX) e
auditada em estilo autópsia (ver `AUDITORIA_SKILL.md`). Este documento é o inventário integral:
checklist por marco, fluxo de funcionamento, e o **backlog do que falta acrescentar/corrigir**.

**v1.49.0 — dogfooding: o APEX auditado POR ELE MESMO.** Exercício instrumentado (contadores por chamada + timings + tracker) sobre o pipeline real. Corrigidos: (1) desperdício provado no fan-out — os 5 framings do `subagent_manifest` recomputavam contexto/rotina idênticos (context_pack 5x, compose 5x, equip_for 10x, ~956ms) → computados 1x por tarefa e compartilhados (`spawn(shared=...)`): 5→1/5→1/10→6, conteúdo byte-idêntico (zero perda de qualidade, por construção); (2) bug do express em PT — "2+2 é quanto?" retornava answer=None (só havia prefixos); sufixos PT/EN agora computam. Validados no exercício: RAG-sem-remapear (~27,7k tokens → ~200 do overview; buscas 1–2ms no nó certo), memória entre instâncias, concorrência no learning, entrada 12k/unicode, tracker corrigindo estimativas nos dois sentidos (TRIAGE 60→84; CONTEXT_PACK 350→75). Descoberta H5: caveman SINALIZADO pelo injection-scan (STAGED_RISK — correto p/ skill que altera comportamento); brainstorming STAGED limpo. Suíte: benchmark 61/61.

**v1.48.0 — índice repo-wide + drift semântico + ledger multi-dispositivo.** (1) O RAG de estado sólido agora cobre as **111 páginas do boot** (nós `boot:` com purpose do registry + cabeçalho YAML) e `reference-docs/` com capítulos (432 nós no total). (2) **Desvio semântico** (documento do autor): `sync()` calcula Jaccard entre a vizinhança de termos antiga e nova do nó re-vetorizado; < 0.30 = o SIGNIFICADO mudou → nó sinalizado (`drifted`, dim antes/depois) + recomendação de `attraction_graph.rebuild()`. (3) **Ledger multi-dispositivo**: cadeia SHA-256 POR MÁQUINA (`device_id` estável; migração retrocompatível — eventos legados verificam pelo canônico antigo); fundir bundles de N máquinas intercala N cadeias íntegras, `verify_ledger` valida cada uma, adulteração de qualquer coluna continua detectada — o pré-requisito da federação está fechado. Suíte: benchmark 61/61.

**v1.47.0 — ciclo de execução + estado sólido (documento de arquitetura do autor).** (1) RUN LOOP das rotinas: a persona RODA o fluxo, os handoffs são reescritos com o que ela REALMENTE recebeu (persistido; o send do passo seguinte acompanha), o resultado real promove/rebaixa a rotina automaticamente e falha vira vacina. (2) Cache incremental do scan de capacidades (mtime+size; tocado re-parseia, deletado é podado). (3) `token_tracker` (OPP-99): medição real por rodada/passo (proxy chars/4 declarado) calibra o `pipeline_dsm` — medido substitui estimado com ≥3 amostras (dados reais: DISSECT ~6tk vs 80 estimado). (4) **RAG de ESTADO SÓLIDO**: nós por CAPÍTULO/seção via sumário (302 nós, 147 seções), dimensão taxonômica por nó (disciplina→especialização→modo), busca com visão MACRO (dim + quem afeta via matriz de imports + o que atrai), `sync()` incremental por hash com poda em cascata e ALIAS de renomeio (fast-path por hash + cosseno ≥0.85 sobre vetores renormalizados — bug de truncamento top-48 achado e corrigido), `merge_index()` para estados divergentes entre instâncias e `overview()` determinístico (prefixo estável alinhado a prompt-caching — carregue PRIMEIRO em toda sessão). 48 scripts. Suíte: benchmark 59/59.

**v1.46.0 — rotinas: a persona sabe COMO trabalhar.** (1) Contratos de I/O por capacidade (`capability_map`: o que ENVIAR, o que RECEBER, onde APLICAR — curados para as 18 ferramentas de sustentação, heurísticos no resto). (2) **`routine_composer`**: fluxo encadeado de capacidades complementares por estágios canônicos (research→design→marketing→frontend→backend→performance→verify), handoff explícito passo a passo (o receive de N alimenta o send de N+1); candidatos de capability_map+attraction_graph+curated; learning sobe o comprovado e remove o rebaixado; estágio sem ferramenta vira GAP honesto → cascata de descoberta + H5 (validado no exemplo canônico do autor: landing page não-genérica → brainstorming→sleek-design→react-best-practices→supabase-postgres→tdd, com marketing/psicologia-das-cores e performance como gaps). Rotinas persistem por persona e VIAJAM no bundle; `record_routine_outcome` promove por resultado real; `record_feedback` transforma auditorias de outros LLMs + feedback positivo do usuário em memória com proveniência + sugestões equip/unequip/descoberta (H5 decide). `spawn()` injeta a rotina. 47 scripts. Suíte: benchmark 55/55.

**v1.45.0 — memória de ferramentas + DSM do próprio runtime + manual.** (1) `documentacao.md`: o manual narrativo (o que é, dores, quando usar, comportamento idealizado/esperado por módulo) — separado do contrato (`spec.md`) para evitar drift. (2) **`capability_map`**: o APEX aprende a TRABALHAR com as skills instaladas/aprovadas — comandos, triggers, linguagens do ambiente (probe real), bibliotecas, templates de design/documento — consultável por RAG (`how_to`), com promoção por outcomes reais (`record_use`→learning); mapear nunca executa (gates/H5). (3) **`pipeline_dsm`**: DSM real do runtime — matriz de imports exata (5 níveis paralelos, 3 ciclos lazy documentados, núcleo _tfidf/repo_bridge/config) + fluxo por modo via geodésico ([APPROX]: EXPRESS economiza ~5.1k tk, STANDARD poda 4 passos ~3.8k tk) + otimização APLICADA `context_budget(mode)` (0→2000 chars, consumida por orchestrator e agent_spawn). 46 scripts. Suíte: benchmark 54/54.

**v1.44.0 — plug-and-play + experiência→contexto (visão original do autor).** O bundle de swap agora carrega TODOS os stores duráveis — hábitos/spec-diretrizes (config+persona+preferences), agentes treinados (grants), learning validado, competence e as VACINAS (agora duráveis por default em `vaccines.db`, com o texto do erro preservado) — além da memória; `page_out(delta=True, compress=True)` exporta só o novo (cadeia `delta_of`, gzip); `page_in_session` aplica a cadeia base+deltas (varrendo `versions/` — bug de rotação achado e corrigido no smoke test); **`resume_due()`** é o gêmeo simétrico do persist_due, reportado na ENTRADA do `orchestrator.run`. **Experiência vira CONTEXTO**: `agent_spawn.context_pack(task)` monta o briefing validado (vacinas, memória, PROVEN/DEMOTED, nós do rag) injetado em todo `spawn()` e no resultado do `run()`. **Agent bundle**: `export_agent`/`import_agent` — agente treinado portátil, assinado SHA-256, instalável só com H5 (adulterado → REJECTED). Suíte: benchmark 52/52.

**v1.43.0 — design do autor pós-validação da auditoria GPT (v1.40 → 22/27 já corrigidos na v1.42).** Os 5 achados restantes viraram arquitetura: **RT-22** `orchestrator.run` agora devolve um **kernel checklist booleano** (passos code executados com evidência; passos llm com a chamada exata) e `gate()` que só dá COMPLETE com tudo True — o LLM não pula etapa; **RT-19/RT-27** novo `agent_spawn` (contrato de spawn): agente genérico assume persona REAL (AGENT.md), atrai skills/diffs/scripts reais via o novo **`attraction_graph`** (JSON de roteamento gravitacional pré-computado — busca a 1ª competência e o resto se atrai; `rebuild()` a cada inclusão), equipa/desequipa com persistência (**RT-26b**: grants persistem por DEFAULT e são revogáveis; `load()` faz auto-merge); manifesto Level-B carrega specs completas + `spawn_contract()`; **RT-09b** colisão de `ts` explícito no swap agora estende com microssegundos (nunca sobrescreve). Novos também: **`rag_index`** (RAG vetorial por nós, IDF global, mapeia o repositório em ms) e **`spec.md`** (especificação integral do sistema). Suíte: benchmark 50/50, evaluate 13/13, scenario 7/7.

**v1.41.0 — endurecimento pós-autópsia de runtime (auditoria GPT).** 12 achados adversariais
corrigidos e blindados no CI (novo teste `runtime_autopsy` no benchmark): swap recusa bundle com
hash inválido **antes** de escrever e o hash cobre todo o payload (RT-07/08); `verify_ledger`
recalcula o hash de conteúdo, detectando adulteração de qualquer coluna (RT-05); `skill_scout`
bloqueia import fora da allowlist no `evaluate` (RT-11), descobre e escaneia scripts referenciados
no `SKILL.md` (RT-13), sinaliza prompt-injection no corpo (RT-12) e recusa arquivo truncado
(RT-14); `resolve_mode` aplica piso `min_mode` e não rebaixa modo de alto risco sem flag (RT-23);
grants de skill persistem em store durável e sobrevivem ao reload (RT-26); nome de arquivo com
microssegundos evita colisão no mesmo segundo (RT-09); shape inesperado de API degrada sem exceção
(RT-15); `MemoryStore` aceita caminho relativo bare (RT-10). Suíte: benchmark 45/45, scenario 7/7.

**Modelo mental (runtime cognitivo).** A skill trata o LLM como uma **VM cognitiva** (motor de
inferência) e a si mesma como o **runtime/SO** em volta: kernel = `SKILL.md`; syscalls = os 44
`scripts/*.py`; escalonador = `geodesic_scheduler` + `project_ledger.dsm()`; processos = stances/
subagentes (Nível A/B); memória paginável e durável = `memory.py` (SQLite + Knowledge Graph);
log de integridade = ledger SHA-256; gerenciador de pacotes = `repo_bridge`+`skills_sh`; HAL =
`meta/apex_llm.yaml` (YAML; fallback `meta/llm_compat.json`). Restrição honesta: o container é **efêmero** — o `.db` local é cache de
trabalho; durabilidade real = commit git ou export `.zip` (backends do `project_ledger`/`memory`).

---

## ✅ Checklist de implantação (tudo verificado por execução)

### Marco 1 — Formato & validação
- [x] Frontmatter 100% válido contra o schema neoformat (theneoai)
- [x] SKILL.md seções § numeradas, Trigger Words, Scope & Limitations (cresceu para ~416 linhas
      com as features v1.22–1.30; o guia neoformat ≤300 é soft e foi ultrapassado conscientemente)
- [x] Conformidade SR_40 (why/when/what-if-fails) em 27/27 scripts + SKILL.md
- [x] `.skill` instalável + `.zip` da árvore de repositório (v1.17.x reconstruídos)
- [x] Versão unificada (era 1.15 no inventário × 1.16 no SKILL.md — drift corrigido)

### Marco 2 — Motores executáveis (31 scripts, 34/34 no benchmark + rubrica 13/13)
- [x] Autópsia SCIENTIFIC (4 camadas): dissect bilíngue+semântico, grant p/ roster 213, _norm — ver `AUDITORIA_CIENTIFICA.md`
- [x] Raciocínio: `orchestrator`, `mental_interpreter`, `pot`, `hypothesis_dag`, `fractal_compression`
- [x] Numérico/formal: `numeric` (RK4/Euler), `verify` (sympy, degrada sem ele), `geometry_estimator`
- [x] Bayesiano: `bayes` (beta-binomial, Ω, R_acum), `apex_st_metric`
- [x] Qualidade/segurança: `uco_gate`, `universal_code_optimizer_v4` (byte-idêntico ao autoral), `guards` (SR_36–40), `skill_scout`
- [x] Escalonamento: `geodesic_scheduler`, `verification_gate`
- [x] Menu da skill: `menu` (update/modos/research), `config` (preferências persistentes), `deep_research` (goal-like RESEARCH/SCIENTIFIC, nativo vs descobrir)
- [x] Probabilístico: `monte_carlo` (P10/P50/P90 + CV, numpy opcional; ligado ao PMI para hipóteses quantificáveis)
- [x] Marketplace: `skills_sh` (skills.sh API, filtro >=1000 installs, tier oficial, offline-safe)
- [x] Semântico opcional: `_tfidf.semantic_rank` (char-n-gram/sentence-transformers, resolve PT<->EN)
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
- [x] `mcp_registry.json` — 23 servidores MCP (os 5 dirs de integrations/ antes fora do registry foram indexados)
- [x] `module_registry.json` — 111 módulos (bate 1:1 com as páginas do boot v00.39.1)
- [x] `diffs_lib.json` — **18/18 DIFF_*** dos packs v00.33–36 (12 faltavam) + SR_42–45 + normalizações
- [x] `scripts_lib.json` — 31 scripts (massa=LOC, para a gravidade)
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
- [x] `tests/benchmark.py` — 1 teste por módulo + regressões + rodadas P1/P2/P3 (**31/31 PASS**)
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

## ✅ Rodadas de correção do backlog (P1 → P2 → P3, todas concluídas e testadas)

### P1 — qualidade de roteamento (FEITO)
- [x] **Diffs bilíngues**: campo `text_en` na `diffs_lib` — diffs agora são atraídos por
      tarefas em inglês (validado: `DIFF_ZERO_AMBIGUITY_CODE_001` puxado por tarefa EN).
- [x] **Índice nativo enriquecido**: descrição até 400 chars + trigger words; busca "bayesian"
      agora retorna resultados (antes: vazio). `repo_bridge.search_native` também varre triggers.
- [x] **Fallback de radius no `gravity.plan`**: relaxa quando o raio estrito traz <3 membros.

### P2 — segurança e fonte da verdade (FEITO)
- [x] **V-02 corrigido**: `_RestrictedUnpickler` no `apex_semantic_index.py` — pickle malicioso
      é bloqueado (validado: `posix.system` recusado), pickle legítimo carrega. Rebuild via build().
- [x] **V-03 corrigido**: sonda de rede usa host da allowlist (raw.githubusercontent) em vez de
      httpbin.org — nas 2 versões de kernel + página do probe.
- [x] **Roster generator corrigido na fonte**: `collect_awesome_agents()` varre `community-awesome`
      (o ponto cego); generator agora encontra 196 (era 163).
- [x] **Linter `executor:` (`tools/lint_executor.py`)**: preenche as 50 páginas sem executor;
      `page_manifest` sha8 regenerado (111/111 conferem) + `module_registry` sincronizado (0 vazios).
- [x] **Pin de commit**: `repo_bridge` aceita `APEX_REPO_REF`/`set_ref()` (já em v1.17).

### P3 — completude (FEITO)
- [x] **Monte Carlo real** (`scripts/monte_carlo.py`, OPP-73): P10/P50/P90 + CV, numpy opcional;
      ligado ao PMI (hipótese quantificável de menor CV vence) — nunca chama voto ponderado de MC.
- [x] **SRs documentadas**: `references/rules.md` agora mapeia as 44 SRs (não só 19) + SR_46/47.
- [x] **5 integrations/ indexados** no `mcp_registry` (claude-commands, external-plugins,
      knowledge-work, official-plugins, plugins).
- [x] **`snapshot` ligado ao `run()`**: `orchestrator.run(task, snapshot=...)` grava findings +
      milestones + skills staged no snapshot (fecha o loop C5 em código).
- [x] **`code_genetics` com SQLite opcional**: `VaccineStore(db_path=...)` persiste e promove
      vacinas entre reaberturas (validado no benchmark).

### Rodada V — skills.sh marketplace + vercel-labs/skills (FEITO)
- [x] **Descoberta skills.sh** com critério **>=1000 installs** (`scripts/skills_sh.py`):
      leaderboard/search/official via API, tier oficial, allowlist read-only, offline-safe,
      ligado ao `gravity.plan` na cascata nativa -> skills.sh -> GitHub -> H5.
- [x] **Análise vercel-labs/skills** (26k estrelas) em `references/vercel-skills-analysis.md`:
      adotados o quality-bar de installs, o tier de dono oficial (`skill_scout.trust_tier`) e a
      cascata de descoberta; rejeitados (por escopo/H5) a plumbing de CLI e auto-install.

## 🧠 Roadmap cognitivo (oportunidades P1–P3 — em discussão/desenho)

### Op1 — Memória vetorial viva entre sessões · **FEITO** (v1.26) + **Knowledge Graph B1** (v1.29)
`scripts/memory.py` → `MemoryStore`, decidido em discussão com o autor:
- **Storage:** SQLite local (`~/.apex-method/memory.db`) como padrão — stdlib, offline, arquivo
  único portável. **MongoDB como plugin opt-in** (adaptador de storage fino) para quem já roda
  um servidor; nunca padrão (quebraria offline/zero-dep/privacidade).
- **Vetores:** `_tfidf.CharEmbedder` (char-n-gram, puro-stdlib, language-robust) + hook para
  sentence-transformers; `recall(query, k)` = cosine top-k (brute-force, ok até ~10–50k).
- **SHA-256** em três usos: (1) content-addressing/dedup, (2) coluna de integridade (ecoa SR_42),
  (3) encadeamento do ledger (hash do evento anterior → log à prova de reescrita).
- **Dois tipos + chave:** *semântica* (fatos destilados) dedup por `sha256(texto_norm)`;
  *episódica* (findings de sessão) chaveada por `sha256(texto+timestamp+sessão)` — não dedup.
- **Escrita curada pelo snapshot** (não automática a cada `run()`): menos ruído.
- **Ledger de governança** (ideia do autor, ponte para a Op-P3): API neutra
  `memory.record_event(kind, subject, action, evidence)` que `code_genetics` (promoção de vacina),
  `grant_skill` (agente ganha skill), crystallization/SR_35 (diff promovido/rebaixado) e SR_47
  (regra ativada/desativada) *chamam* — memória não invade os subsistemas.
- **Seed inicial versionado** + append incremental; ligada ao `orchestrator.run` (recall no
  início) e ao `snapshot`/eventos (write). Menu ganha `memory clear|export` (retenção/privacidade).
- **B1 — Knowledge Graph (v1.29):** as memórias carregam **arestas tipadas** (`causa`, `contradiz`,
  `depende_de`, `refina`, `suporta`), então a recuperação vira **caminhada em grafo**, não só top-k.
  `relate(src,dst,rel)`/`relate_text` cria a aresta; as relações **direcionais** (`causa/depende_de/
  refina`) são mantidas **acíclicas** via o motor `hypothesis_dag` (ciclo = erro de raciocínio,
  rejeitado antes de inserir); as simétricas (`contradiz/suporta`) podem formar laços.
  `neighbors`/`walk(start, rel_types, depth)` percorrem; **`recall_graph(query, k, depth, rel)`**
  faz seed com `recall` e **expande** pelas arestas — responde "o fato E tudo que o `contradiz`",
  que um top-k por similaridade não faz. Cada aresta também vai ao ledger de governança (durável).

### Op2 — Paralelismo cognitivo · **FEITO** (v1.22–1.24)
- `concurrent_executor` (Nível A) + protocolo de fan-out de subagentes (Nível B); 3 stances
  canônicas, teto por modo, SHA-256 por stance, barrier→merge→PMI→RESTART.
- **Caos ofensivo** (`chaos_operators`): Lévy/mutação/recombinação/genius; política por modo
  (`config.exploration_policy`) — caos a partir do FOGGY, paralelismo A→B a partir do FOGGY,
  genius obrigatório em RESEARCH.
- **Abort reancorado** no mecanismo real do kernel: `rejections_streak>20` OU `var(conf)<0.03`
  (não confiança nem temperatura); troca com fase+π ou inject_skill; vacina = diagnóstico.
- **`evaluate_hypotheses`**: analista levanta 3 hipóteses → diretores especialistas dão laudo
  SHA-256 (bayes+dificuldade+RPN+diagnóstico) → barrier → merge/PMI → decisão ou RESTART;
  lacunas viram `needs_correction`.
- **Exploração maximizada (v1.28)**: antes de convergir, o painel recebe divergência real —
  (1) `subagent_hypotheses`: hipóteses geradas por Agent subagentes Level-B reais (manifesto
  `spawn_subagents` nomeia personas + framing; RESEARCH inclui genius); Claude dispara os
  subagentes e re-chama com as hipóteses deles; (2) `_chaos_expand` (FOGGY↑): mutação estrutural
  (`chaos_*`) da hipótese mais forte + `chaos_recombine` das duas mais confiantes (conf ≤ 0.30,
  SR_11) + genius obrigatório em RESEARCH. Só depois os diretores pontuam o conjunto completo.

### Op3 — Metacognição (matriz de competência) · **FEITO** (v1.24)
- `competence_matrix`: heat-map agente×domínio (T, reward do ledger, dificuldade via
  BehavioralDifficultyEstimator, rejections/variância) + diagnóstico
  **PERSONA_SWAP / INJECT_SKILL / HARD_PROBLEM**; realimenta mental_interpreter e deep_research.

### Op-P3 — aprendizado que persiste · **FEITO** (v1.32)
- `scripts/learning.py`: `LearningStore` (SQLite `~/.apex-method/learning.db`) acumula evidência
  beta-binomial por **(kind, subject, domain)** — kind ∈ persona/skill/diff/rule/vaccine — e decide
  **PROMOTE / KEEP / DEMOTE** com a camada Bayesiana do kernel (Ω 0.72/0.5, ≥3 obs).
- **Toda mudança de status vira memória durável**: `memory.record_event` (ledger SHA-256 encadeado),
  fechando o loop "promoção/rebaixamento → memória à prova de adulteração".
- **Consumo**: `best(kind, domain)` + reward durável misturado ao `competence_matrix._reward` → a
  próxima tarefa consulta o histórico validado (persona que prova → preferida; que falha → rebaixada).
- **Auto-registro**: `evaluate_hypotheses` credita cada diretor por rodada; o loop se fecha sozinho.
- `numeric.py`: `solve_ode(method="auto")` usa **scipy quando importável** (fallback RK4 stdlib);
  `capabilities()` reporta numpy/scipy/sklearn/pandas — aceleração **é do ambiente, não do LLM**.

### Gatilhos obrigatórios: piso de modo + persistência · **FEITO** (v1.39)
- **Dificuldade honesta**: `estimate_difficulty` ganhou classes não-matemáticas (security_audit 0.80,
  architecture 0.62, compliance 0.72, debugging 0.66); classe **desconhecida** → `uncertain=True` +
  bde 0.70 (nunca mais 0.5 silencioso). Corrige a causa raiz: auditoria caía em média medíocre.
- **Piso de modo** (`execution_policy.mode_floor` + `triage`): auditoria/segurança/compliance **nunca
  pulam** e rodam ≥ DEEP; `uncertain` escala + **exige as 3 personas** (`require_dissect_personas`).
- **`min_mode`** no config: piso global que **força o pipeline para toda tarefa** (`menu.py set min_mode DEEP`).
- **Gatilho de persistência**: `swap_store.page_out` (grava swap/<sessão>/ + `drive_manifest` + log),
  `menu.py persist`, e `orchestrator.run` retorna `persist_due` em DEEP+. Page-out nunca é silencioso.

### Contrato de roteamento + entrada de 3 personas · **FEITO** (v1.33–1.34)
- `scripts/execution_policy.py`: `route(subtask)` decide a **superfície** — `subprocess` (cálculo
  determinístico, sem internet) · `agent` (raciocínio) · `agent+internet` (descoberta: skills.sh/
  repos/papers/MCPs, subagente com web-tools). **Regra dura no código**: `needs_internet=True`
  **nunca** vai pro subprocess. Quem fornece as ferramentas é sempre o LLM (`provider_of_tools`).
  Manifesto verificável, **não DSL**. Verificado: nenhum MCP nem script fazia isso.
- `dissect_entry(task, mode, reliability)`: entrada das **3 personas** (architect/analyst/critic) —
  por micro: SWOT + agentes/skills/tools (melhor via `learning`) + resolução (repo→skills.sh→criar)
  + roteamento + template de documento + **governança regional** (HIPAA/GDPR/LGPD/legal/financeiro,
  detectada pelo texto). Reusa dissect/assign/gravity/learning — não reimplementa descoberta.
- **Wire MCFE + dificuldade (v1.34)**: `triage(task, reliability)` roda **antes** — tarefa **trivial
  pula o pipeline** (`orchestrator.express_check` → EXPRESS, economia de tokens); baixa dificuldade
  fica leve; **alta dificuldade** (`competence_matrix.estimate_difficulty` ≥0.85) OU **MCFE baixo**
  (R_acum <0.50) **escala o modo e joga os micros de raciocínio para `agent+internet`** (descobrir).
  Compute continua `subprocess`. Quem determina a dificuldade: `competence_matrix.estimate_difficulty`;
  quem pula o trivial: `orchestrator.express_check`.

### Robustez + adaptabilidade a qualquer LLM · **FEITO** (v1.35)
- **Portão de entrada (v1.36)**: `triage` virou a PRIMEIRA etapa do `orchestrator.run` — o
  skip do trivial (EXPRESS, economia de tokens) e o escalonamento por dificuldade/MCFE acontecem
  automaticamente, sem chamada manual; o EXPRESS passa a carregar o marcador do triage.
- **YAML de adaptabilidade** `meta/apex_llm.yaml` (autoritativo; `llm_compat.json` = fallback stdlib):
  requisitos mínimos (caps obrigatórias + janela por modo), matriz por provedor (claude/gpt/gemini/
  **deepseek**/local), **limites anti-loop** e **aceleradores opcionais**. `llm_adapter` lê YAML
  (PyYAML) com fallback JSON; ganhou `limits()` e `requirements()`.
- **Requisitos mínimos + guarda de loop**: `execution_policy.loop_guard(iteration, progress, restarts,
  reliability)` — STOP em: iterações ≥ máx (8), restarts ≥ máx (3), confiabilidade < early-exit (0.30),
  ou sem progresso por 2 rodadas (dS2 < 0.15). **O LLM nunca entra em loop.**
- **Tratamento de erro**: `orchestrator.run` **nunca levanta exceção** — falha inesperada retorna
  `ERROR_DEGRADED` com modo seguro (responder direto, sinalizar incerteza, não repetir).
- **Aceleradores** numpy/scipy/scikit-learn/sympy declarados em `requirements.txt` (opcionais — a
  skill roda em stdlib puro) + degradação documentada. `numeric.solve_ode` já usa scipy quando há.
- **Bug comportamental corrigido (teste)**: `run()` escolhia o modo só por disciplina — "navier stokes
  pde" (dificuldade 0.92) ia para STANDARD. Agora o `triage` (dificuldade + MCFE) está ligado ao
  `run()` e escala (→ SCIENTIFIC), sem nunca rebaixar um modo dirigido por disciplina. Keywords de
  ciência ampliadas (navier/stokes/pde/turbulência/fluido/reynolds).

### Relatório "runtime cognitivo" (ChatGPT) — aproveitáveis implementados
- **B1 — Knowledge Graph (v1.29):** arestas tipadas em `memory.py` + `recall_graph` (caminhada em
  grafo, guarda acíclica via `hypothesis_dag`). Ver seção Op1 acima.
- **B3 — Narrativa de runtime cognitivo (v1.29):** modelo mental kernel/syscalls/escalonador/
  processos/memória/HAL no topo do SKILL.md e deste inventário (mapa 1:1 com arquivos reais).
- **B2 — LLM Adapter (v1.30):** `meta/llm_compat.json` (contrato: exigências do kernel + janela por
  modo + matriz de capacidades por provedor claude/gpt/gemini/local + regras de degradação) +
  `scripts/llm_adapter.py` (`check`/`fits`/`degrade`/`report`). Sem subagentes → Level A; janela
  pequena → modo rebaixado; sem tool-calling/JSON → loop manual/parse best-effort; provedor
  desconhecido → baseline conservador. É o que torna "mesmo núcleo em qualquer LLM" real.
- **Descartados (honestidade):** confiar no `.db` local para durabilidade (container efêmero — só
  git/zip persiste) e sincronizar histórico interno do ChatGPT (sem API pública).

### Swap store — hierarquia de memória padrão (v1.31)
- `scripts/swap_store.py`: **um layout canônico único** para todos os usuários, materializável numa
  pasta local do PC **ou** no Google Drive. Hierarquia tipo SO: **RAM** (contexto, morre) →
  **SWAP** (este store, sobrevive ao container) → **DISCO** (git, validado e permanente).
- Árvore: `user/` (persona + preferências + arquivos de entrada — durável, do usuário) · `memory/`
  (memória validada persistente em NDJSON) · `swap/<sessão>/` (estado de trabalho efêmero,
  disposável) · `staging/` (validado, na fila do commit) · `archive/` (páginas superadas).
- `materialize(root)` cria local (idempotente, nunca sobrescreve dados); `drive_tree()` dá ao
  runtime o mesmo schema para criar no Drive (o script não toca credenciais — o Claude sobe via as
  tools do Drive, como o project_ledger prepara um commit). `export_bundle`/`import_bundle` fazem
  page-out/page-in com hash SHA-256; memória viaja como NDJSON portável (`MemoryStore.export()/
  load_rows()`), não `.db` binário.
- **Gate de promoção** (`is_validated`/`promotion_manifest`): só o que passa (PMI ADOPT **e** ledger
  íntegro **e** testes) é promovido de swap → commit; o resto fica disposável no swap.
- **Nomenclatura padrão**: `<name>-<function>-<AAAAMMDDHHMMSS+µs>-R<NN>.<ext>` (ex.:
  `memory-User-20260716183245123456-R00.json`). O timestamp com **microssegundos** (20 dígitos)
  versiona cada escrita e evita colisão em page-outs no mesmo segundo (RT-09); `R<NN>` é a
  **revisão de layout** do arquivo (sobe quando o schema muda). `latest()` sempre resolve o maior
  `(revisão, ts)`; a **pasta principal guarda a última** e as anteriores vão para `versions/`.
- **Rotação de backups**: os `KEEP_BACKUPS` (10) mais novos sobrevivem; os antigos ficam obsoletos
  (apagados no local; **listados para GC no Drive** — a API do Drive aqui não tem delete/move/update).
- **Modelo-padrão no repo** (`models/apex_structure.model.json`): fonte única do padrão, com
  instruções de build (Windows e Drive). Novos usuários **constroem a partir do modelo**, o LLM
  nunca inventa a árvore. `materialize(root)` (local) e `drive_tree()` derivam do mesmo modelo.
- **Estrutura criada no Drive do usuário** (`My Drive/APEX/`): raiz + user/memory/swap/staging/
  archive (+ `versions/`) + manifest + README + modelo + seeds versionados + sessão-exemplo. Opt-in:
  `preferences.persistence_backend = "drive-swap"`.

## 📋 Backlog remanescente (fora do escopo imediato / pesquisa)

- [x] **Embeddings/semântico FEITO**: `_tfidf.semantic_rank` adiciona backend char-n-gram
      (language-robust, puro-stdlib) + hook para sentence-transformers; `router.route(backend=...)`
      / env `APEX_ROUTER_BACKEND`. Prova: query PT "otimização de portfólio" onde o word-TF-IDF
      dá miss total (0.0) e o char acha "portfolio". (Embeddings transformer pesados seguem
      opcionais por causa da filosofia zero-dependência.)
- [x] **V-01 corrigido (repo)**: orgs reivindicáveis `apex-marketplace` e `apex-framework`
      REMOVIDAS de trusted_domains nos 2 kernels + modules.yaml + ontology fallback; test_url e
      catálogo agora apontam para o repo real. Zero URL reivindicável no boot ativo.
- [x] **Avaliação por rubrica FEITA**: `tests/evaluate.py` — 9 critérios objetivos e
      re-executáveis (13/13 = 100%); substitui a prosa auto-avaliada por checagens falsificáveis.
      (Continua auto-executado; revisão de terceiro é a única parte que, por definição, não posso
      auto-fornecer.)
- [x] **`lint_executor` referenciado no `apex_compiler`** (fase "validar" da página do compilador);
      quando o `apex_compiler.py` for versionado, basta chamá-lo — o contrato já está documentado.

## 🎯 Rodar o benchmark (para auditorias futuras)

```bash
python3 tests/benchmark.py     # 31/31 PASS esperado; gera tests/benchmark_report.json
```

Compare `benchmark_report.json` entre versões para detectar regressões. Cada linha tem
módulo, status, tempo (ms) e a métrica-chave verificada. O bloco `audit_regressions` cobre
um assert por bug corrigido na autópsia.

---

## Nada ficou de fora?

Cobertos e integrados: **pipeline + 5 modos**, **8 C / 44 SR (+46/47 documentadas) / 18 G /
7 H / 130 OPPs** (as computáveis como código, as de política documentadas+enforçadas),
**213 agentes**, **3.784 skills nativas indexadas + 430 externas + mapa skills.sh**,
**18 DIFFs**, **27 scripts**, **111 módulos**, **UCO byte-idêntico + UCO-Sensor (9 motores
indexados)**, **camada bayesiana verificada**, **gravidade/atração**, **descoberta em cascata
com aprovação humana**, **MCP registry**, **ponte para o repositório inteiro**, e o
**benchmark 31/31**. O que é serviço externo (UCO-Sensor completo, feeds OSV) está indexado
com interface; o que é terceiro está gerenciado (não copiado). O que ainda falta está
explícito no backlog acima — nada pendente ficou sem registro.
