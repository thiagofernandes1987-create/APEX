# spec.md — APEX Method: especificação do sistema

> Fonte única de intenção: **o que é**, **por que existe**, **como funciona**, **o que cada
> módulo faz e entrega (e para quem)**, **comportamentos esperados** e **comportamento
> planejado**. Complementa o `SKILL.md` (kernel operacional que o LLM segue) e o
> `inventario.md` (checklist de implantação/histórico). Para localizar qualquer coisa:
> `python scripts/rag_index.py "<pergunta>"`.

---

## 1. O que é

O **apex-method** é um **runtime cognitivo**: um sistema operacional fino em volta de um LLM.
O LLM é a **VM cognitiva** (inferência, síntese, julgamento); a skill é o **SO** que agenda
trabalho determinístico em código real, guarda memória durável, governa segurança e força
disciplina de raciocínio. Não é um prompt que "reprograma" o modelo — é um kernel
(`SKILL.md`) + 58 syscalls (`scripts/*.py`) + catálogos + contratos verificáveis.

**Objetivo:** transformar raciocínio de LLM em engenharia auditável — respostas **computadas
e verificadas** (PoT, RK4, Bayes, gates), com custo controlado por modo, memória que
sobrevive à sessão, agentes especializados que **aprendem e se aprimoram** equipando skills,
e nenhuma etapa crítica pulável silenciosamente.

## 2. Premissas do repositório

1. **Nada aceito sem execução.** Toda alegação carrega ONDE/COMO/evidência; benchmark,
   rubrica e cenários são re-executáveis (`tests/`).
2. **Zero-dependência no núcleo.** Roda em stdlib puro; numpy/scipy/sklearn/sympy/PyYAML são
   *aceleradores opcionais* com degradação declarada (`meta/apex_llm.yaml`).
3. **Conteúdo externo é DADO até ser vetado.** Allowlists, AST-scan em dois níveis,
   scan de prompt-injection, e o gate humano **H5**: nada se instala/executa sozinho.
4. **O container é efêmero.** Durabilidade real = git/zip/Drive; `~/.apex-method/*` é cache
   de trabalho paginável (swap). Testes NUNCA tocam o home real (`APEX_METHOD_HOME`).
5. **Honestidade epistêmica.** 🟢 computado / 🔵 julgamento do LLM / marcadores `[APPROX]`,
   `[CONJECTURA_FORMAL]`, `[SIMULATED]`. "Monte Carlo" só quando há simulação real.
6. **Portabilidade entre modelos.** O kernel não depende de um provedor; `llm_adapter`
   degrada capacidades (Level B→A, modo capado) de forma anunciada.
7. **Não pular etapas.** Triage decide o modo; piso de modo para auditoria/segurança;
   o **kernel checklist + gate** (RT-22) devolve ao LLM até tudo estar `True`.

## 3. A ideia central (o diferencial)

Não é equipar milhares de skills do GitHub — é ter **agentes que aprendem**: um agente
genérico, ao ser spawnado, **assume uma persona real** (AGENT.md), **atrai por
especialização** as skills/diffs/scripts que se completam (grafo gravitacional
pré-computado), **equipa** habilidades aprovadas (persistidas na memória de grants) e pode
**desequipar** o que foi rebaixado. A correlação entre a biblioteca inteira e a memória do
que cada agente equipou é o que produz spawns cada vez mais capazes — auto-evolução com
governança.

## 4. Arquitetura (mapa OS → arquivo)

| Camada | Arquivo(s) | Papel |
|---|---|---|
| Kernel / método | `SKILL.md` | disciplina + orçamentos por modo que o LLM segue |
| Syscalls | 58 `scripts/*.py` | trabalho determinístico fora da cabeça do LLM |
| Entrada | `orchestrator.run` + `execution_policy.triage` | triage → dissect → resolve → modo → **checklist/gate** |
| Roteamento | `taxonomy` → `router`/`gravity` → **`attraction_graph`** | facetas canônicas → atração lexical → grafo pré-computado |
| Agentes | `agent_registry` + **`agent_spawn`** + `concurrent_executor` | roster enxuto → spec executável no spawn → fan-out A/B |
| Memória | `memory` (SQLite+KG+ledger) + `swap_store` + `learning` + `skill_ledger` + `code_genetics` + `project_ledger` | episódica/semântica; page-out PLUG-AND-PLAY (todos os stores, delta+gzip, resume_due; backends drive/local/zip/git); promote/demote; **proveniência das escolhas recuperável cross-session**; vacinas duráveis; inventário vivo |
| Descoberta | `local_discovery` + `skills_sh` + `github_skills` (via `deep_research`) | cascata PROVEN→LOCAL→native→skills.sh→github; instaladas + MCPs primeiro; fornecedores confiáveis + estrelas + semântica |
| Segurança | `skill_scout` + `_ast_helpers` + `guards` + `repo_bridge` | allowlists, AST 2 níveis (sinks de libs whitelistadas cobertos), injection-scan, H5 |
| Numérico | `pot`, `numeric`, `verify`, `monte_carlo`, `geometry_estimator` | computa em subprocesso; prova ou marca conjectura |
| Bayes/decisão | `bayes`, `verification_gate`, `fractal_compression`, `hypothesis_dag` | posterior, Ω, R_acum, poda, DAG acíclico |
| Meta | `competence_matrix`, `apex_st_metric`, `mental_interpreter`, `geodesic_scheduler`, `chaos_operators` | dificuldade, estagnação, n_final, ordem ΔH/token, exploração |
| HAL | `meta/apex_llm.yaml` + `llm_adapter` | requisitos mínimos, matriz por provedor, anti-loop |
| Mapa | **`rag_index`** + **`capability_map`** + **`pipeline_dsm`** + `catalog/*.json` | recuperação por nós; memória de ferramentas (how_to); DSM do runtime + orçamento de contexto por modo |

### Fluxo canônico (com passagem de bastão)

```
tarefa → triage (código)      trivial? → EXPRESS e fim
       → dissect (código)     keywords → facetas (taxonomy) → char-n-gram
       → assign_specialists   gravity/attraction_graph por disciplina (código)
       → modo + phase_plan    resolve_mode nunca rebaixa piso (código)
       → KERNEL CHECKLIST     código marca o que executou; llm_actions dizem a chamada exata
   LLM → spawn (agent_spawn.spawn → specs completas; spawn_ready=False não spawna)
   LLM → stances/subagentes → evaluate_hypotheses (barrier+merge+diretores, código adjudica)
   LLM → verify (uco_gate/verify/verification_gate)
 código→ pmi_converge (candidates) → snapshot → gate()  — só COMPLETE com tudo True
   LLM → page_out (modos pesados) — nunca silencioso
```

## 5. Módulos — o que faz, o que entrega, para quem

### Entrada e orquestração
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `orchestrator` | ponto de entrada `run()`; nunca levanta exceção; **kernel checklist + gate (RT-22)**; **`resolution_check` = curto-circuito por solução lembrada (prior≥0.6) + re-verificação** | plano executado parcial + `llm_actions` + gate → **LLM host** |
| `execution_policy` | triage (skip/escala), piso de modo, superfícies (subprocess/agent/agent+internet), 3 personas de dissect, loop_guard; **`fanout_plan` = poda geodésica ao quórum quando prior≥target** | roteamento por micro + governança regional → orchestrator/LLM |
| `mental_interpreter` | fórmula `n_final`, fases SPECULATION→PRODUCTION, entropy merge | tamanho de bloco + plano de fases → orchestrator |
| `menu` / `config` | update portátil (shutil), modos preferidos, min_mode, persist | preferências persistidas → todos os módulos |

### Roteamento e composição
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `taxonomy` | facetas canônicas EN com triggers PT/EN; `facet_score` independente de idioma; **v1.63 seed do corpus real (3.784 skills + 213 agentes)** | classificação por significado → dissect/router |
| `translation` | **v1.63 translate-before-dissect**: gloss PT→EN determinístico (stdlib, idempotente p/ EN) da entrada ANTES de classificar/rotear — baixo custo, alto ROI cross-language | entrada normalizada → dissect/router/match de agentes |
| `knowledge_base` | **v1.63 base compartilhada**: popularidade por disciplina (cobertura real), ranking de sucesso (learning), vacinas, promoções, `load_state()` (hidrata estados de sucesso); servida pelo MCP | base consultável/carregável → qualquer instância do APEX + MCP |
| `router` | ranking lexical de skills + demote de stubs + piso de confiança | skill certa ou NO_RELIABLE_SKILL → resolução de skills |
| `gravity` | massa×proximidade; constelação por tarefa; `plan()` com gaps → cascata de descoberta | constelação + pedidos STAGED (H5) → assign_specialists |
| **`attraction_graph`** | **JSON de roteamento pré-computado**: arestas gravitacionais top-K por corpo; `expand()` = atração em cadeia; `equip_for()` | super-estrutura sem re-descoberta → **agent_spawn**/LLM; `rebuild()` a cada inclusão |
| `curated` / `asset_manager` / `repo_bridge` / `skills_sh` / `skill_forge` | mapa curado; 41 assets+23 MCPs; ponte p/ repo inteiro (3.784 skills, 213 agentes, 111 páginas); marketplace ≥1000 installs; gerador de skills | recursos endereçáveis → descoberta em cascata |

### Agentes
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `agent_registry` | 11 personas núcleo + roster 213; match por tarefa; **grants persistem por default e são revogáveis (RT-26b)**; `load()` auto-merge | competência durável → spawn/roteamento |
| **`agent_spawn`** | **contrato de spawn (RT-19/27)**: persona real + skills/diffs/scripts atraídos + grants + histórico + governança + template + checklist; `equip`/`unequip`; **`context_pack(task)`** (experiência validada → contexto injetado em todo spawn e no run()); **`export_agent`/`import_agent`** (agente treinado portátil, SHA-256 + H5) | AgentSpec executável + briefing + agent bundle → **host LLM (Agent tool)** |
| `concurrent_executor` | Level A (subprocessos paralelos, barrier, merge, PMI, restart); manifesto Level-B **com specs completas**; diretores com laudos SHA-256 | rodada adjudicada ou RESTART → LLM |
| `agent_lifecycle` | loop fechado dissect→matrix→resolve→equip→spec→`finalize` (só sucesso validado promove/evolui/materializa; aprende de falha via vacina) | ciclo de vida do agente → roster crescido |
| `agent_materializer` | cristaliza um agente genérico validado num especialista padronizado (`AGENT.md`) descobrível na sessão seguinte | biblioteca auto-evolutiva → resolve_agent |
| `federation` | pacotes de conhecimento entre instâncias (só o validado viaja; procedência = cadeia de ledger; HMAC opcional; import só com H5) | conhecimento portátil entre máquinas |
| `routine_composer` | rotinas multi-passo encadeadas (handoffs aprendidos, auto-PROMOTE@3, reuso) que viajam no swap | fluxos reutilizáveis → orchestrator |
| `chaos_operators` / `competence_matrix` / `learning` | Lévy/mutação/genius; heat-map + diagnóstico PERSONA_SWAP/INJECT_SKILL/HARD_PROBLEM; promote/demote beta-binomial com ledger | exploração + metacognição + memória de desempenho → painel/spawn |

### Memória e persistência
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `memory` | SQLite episódica/semântica, dedup SHA-256, Knowledge Graph tipado acíclico, ledger encadeado tamper-evident, export NDJSON | recall/recall_graph + eventos de governança → todo o runtime |
| `swap_store` | hierarquia RAM→SWAP→DISCO; nomes versionados (colisão impossível, RT-09/09b); bundle com hash total fail-closed; gate de promoção | page-out/page-in íntegros → sessões futuras/Drive/git |
| `project_ledger` | inventário vivo MACRO+micros, DSM (caminho crítico + lotes paralelos), gate de conclusão, abandono justificado | retomada exata de projetos → sessões futuras |
| `snapshot` | estado padronizado com proveniência WHAT/WHERE/HOW/confiança | bloco re-emitível → contexto do LLM |
| `token_tracker` | custo de tokens medido vs estimado por passo (≥3 amostras → substitui a estimativa); alimenta o `mode_flow`/orçamentos | calibração real do orçamento → pipeline_dsm |
| `event_bus` | **v1.62** — barramento único de telemetria cognitiva: `orchestrator.run` auto-instrumenta cada execução (`run_started`/`triage`/`cache_hit\|miss`/`mode_decision`/`run_finished`, SQLite + `trace_id` no resultado); `evaluate(trace_id)` é o registro de avaliação por execução; `export_jsonl` alimenta exporters externos (OTEL/LangSmith) | avaliação contínua + tracing → learning/MCP |
| `pipeline_dsm` | Design Structure Matrix dos módulos; **`classify_cycles` rotula cada ciclo de import `lazy` (seguro) vs `top_level` (risco real)**; `real_cycles`; caminho crítico/lotes | ordem/risco de dependência honesto → project_ledger/otimização |

### Segurança
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `skill_scout` | fetch allowlist + redirect na URL final + recusa truncado; AST 2 níveis (reject RCE / review); descobre e escaneia scripts referenciados (só path-qualified, N-04); injection-scan do corpo; trust tier | STAGED/REJECTED + entrada de snapshot → gate H5 |
| `_ast_helpers` | primitivas de scan compartilhadas (open-mode, deserializer RCE sink) usadas por `skill_scout` + `guards` (fim da duplicação, C-07) | classificação de risco → os dois gates |
| `guards` | SR_36..40 executáveis (crystallization, forge gate estrito, ordem do crítico, runtime guard, zero-ambiguidade) | PASS/REJECT → forja/pipeline |
| `uco_gate` / `universal_code_optimizer_v4` | juiz objetivo de código gerado (Hamiltoniano, loop risk, dead code); **memoização por `sha256(uco_path\x00code)`** (veredito determinístico cacheado, O-16-2) | gate SR_33 → antes de todo subprocesso |

### Numérico e decisão
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| `pot` / `numeric` / `verify` / `monte_carlo` | subprocessos encadeados; RK4/scipy; prova simbólica ou conjectura; P10/P50/P90+CV reais | números exatos → PMI/resposta |
| `bayes` | beta-binomial, posterior, Ω (0.72/0.5), R_acum janela-20 | decisão ADOPT/REVIEW/REJECT → PMI/learning |
| `hypothesis_dag` / `fractal_compression` / `verification_gate` / `geometry_estimator` / `geodesic_scheduler` / `apex_st_metric` | DAG acíclico com cascata; poda; verificação só do arriscado (P≠NP); DELTA_ERR; ordem ΔH/token; progresso dS² | espaço de hipóteses controlado → modos DEEP+ |

### Mapa e pesquisa
| Módulo | O que faz | Entrega → para quem |
|---|---|---|
| **`rag_index`** | índice vetorial **por nós** (92+) com IDF global char-n-gram; `search()` PT/EN | nó certo (path+resumo) em ms → LLM/deep_research |
| `deep_research` | loop RESEARCH iterativo: dissect → agentes → **cascata de descoberta PROVEN(0.98)→LOCAL(0.95)→native→skills.sh→GitHub(0.7)→FORGE(0.4)** (LLM cria skill só em último recurso) → estagnação/R_acum | pesquisa objetivo-dirigida → usuário |
| `local_discovery` | tier LOCAL-first: skills JÁ instaladas (`~/.claude/skills`, `/mnt/skills`, container-dirs da CLI) + MCPs vivos (`mcpServers`) — custo zero, sem H5 | inventário instalado + `mcp__server__*` → cascata/agentes |
| `github_skills` | descoberta GitHub-nativa: fornecedores confiáveis + estrelas + busca semântica; git-tree API onde disponível, README/curated onde não | candidatos STAGED (H5) → `skill_scout.evaluate` |
| `skill_ledger` | **memória das ESCOLHAS** (7 campos: problema/skill/agente/resolveu?/promovida?/repo/comandos); grava em memory+KG+ledger+learning; `worked_for()`=prior de atração (super-amostra o pool antes de filtrar → skill provado nunca soterrado sob histórico, O-16-1) | escolhas recuperáveis via swap → tier PROVEN + resolution-cache |
| `llm_adapter` | contrato HAL: check/fits/degrade/limits por provedor | plano de degradação anunciado → orchestrator |
| `_tfidf` | TF-IDF puro + char-n-gram + hook sentence-transformers; **`_fold` NFKD dobra acentos (RAG-PT: PT não fragmenta em acento e alinha com cognatos EN)** + memoização de verificação | fallback sempre-disponível → router/gravity/memory |

## 6. Comportamentos esperados (contratos verificáveis)

1. `orchestrator.run` **nunca** levanta exceção (ERROR_DEGRADED seguro).
2. Tarefa trivial → EXPRESS (~400 tokens); auditoria/segurança/compliance **nunca** pulam e
   rodam ≥ DEEP; `min_mode` é piso duro; modo forte nunca é rebaixado silenciosamente.
3. O **gate do kernel** só retorna COMPLETE com todos os passos `True`; caso contrário
   RETURN_TO_LLM com os passos faltantes e a chamada exata de cada um.
4. Nenhum spawn sem spec: `spawn_ready=False` ⇒ não spawna (conserta o item do checklist).
5. Descoberta nunca roda no sandbox selado (`needs_internet ⇒ agent+internet`).
6. Instalação/execução externa exige H5; grants sobrevivem a reload e são revogáveis.
7. Bundle adulterado ⇒ REJECTED **antes** de qualquer escrita; ledger detecta edição de
   qualquer coluna; toda gravação de swap é uma versão nova (nunca sobrescreve).
8. Sem sympy ⇒ `CONJECTURA_FORMAL`; sem sklearn ⇒ `_tfidf`; sem subagentes ⇒ Level A —
   sempre anunciado, nunca silencioso.
9. Loop guard: máx. 8 iterações, 3 restarts, early-exit R_acum<0.30, estagnação 2 rodadas.
10. Suites (`benchmark` 72/72, `evaluate` 13/13, `scenario` 7/7 CLEAN) verdes em Windows/Linux,
    Python ≥3.10, com ou sem aceleradores.
11. **Economia de tokens sem afrouxar o rigor (v1.61):** o resolution-cache só curto-circuita
    com solução **validada** lembrada (prior≥0.6) e **sempre re-verifica**; solução que falhou
    nunca curto-circuita; memoização é byte-exata (chave completa: gate inclui `uco_path`,
    verify não cacheia sympy-ausente/exceção); a poda de fan-out nunca vai abaixo do quórum (3)
    e só ocorre com o prior ≥ target. Todos os curto-circuitos são desligáveis por config.

## 7. Comportamento planejado (roadmap honesto)

| Item | Estado |
|---|---|
| Adapter Level-B nativo por host (Claude Agent tool / outros) executando o manifesto | contrato pronto (`spawn_contract`); execução é do host |
| Embeddings transformer opcionais no `rag_index`/`memory` | hook existe; char-n-gram é o piso zero-dep |
| `attraction_graph` incremental (atualizar só as arestas do corpo novo) | `rebuild()` completo hoje; incremental é otimização futura |
| ~~Bundle plug-and-play (todos os stores) + delta+gzip + resume_due~~ | **ENTREGUE v1.44** |
| ~~Agent bundle (agente treinado portátil) + context pack~~ | **ENTREGUE v1.44 (protótipo)** |
| Rotina automática: descoberta aprovada → `equip()` → `rebuild()` → nó no `rag_index` | passos existem; encadeamento automático planejado |
| Designs padrão (ABNT etc.) como templates plugáveis por deliverable no spawn | `TEMPLATES` existe; biblioteca de templates a expandir |
| UCO-Sensor embutível parcial (SAST leve inline) | indexado como serviço |

## 8. Onde validar cada afirmação

```
python tests/benchmark.py    # 1 teste por módulo + regressões RT-*
python tests/evaluate.py     # rubrica objetiva 13 critérios
python tests/scenario.py     # auditoria comportamental fim a fim
python scripts/rag_index.py "sua pergunta"          # mapa do repositório
python scripts/attraction_graph.py "sua necessidade" # a cadeia que se atrai
```
