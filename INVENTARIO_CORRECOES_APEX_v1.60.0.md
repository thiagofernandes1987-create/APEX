# 🗂️ Inventário de Correções + Validação de QA — `apex-method` v1.60.0

> **Propósito:** consolidar, num único inventário acionável, (1) a prova de que **todos os módulos executam corretamente** e (2) a lista priorizada de correções a implementar, cada uma com arquivo:linha, evidência (PoC quando aplicável), correção-alvo, esforço e status.
> **Passe de QA:** equipe simulada (Tech Lead + Dev + QA + Segurança). Nada aceito sem execução.
> **Data:** 2026-07-20 · **Ambiente:** Python 3.11.15 · stdlib puro (sem numpy/scipy/sklearn/sympy).
> **Documento-mãe:** `AUDITORIA_AUTOPSIA_APEX_v1.60.0.md` (autópsia completa).

---

## Parte A — Matriz de validação (todos os módulos executam?)

Executado nesta ordem, em `APEX_METHOD_HOME` isolado (sem tocar dados reais):

| Verificação | Resultado | Veredito |
|---|---|---|
| `py_compile` de todos os `.py` | 54/54 compilam | ✅ |
| **Import** de cada módulo de `scripts/` | **51/51 importam** sem erro de import-time | ✅ |
| **Self-test `__main__`** de cada módulo | **50/51 rc=0**; `skill_forge.py` rc=2 = argparse exige subcomando (`create`/`promote`), **não é bug** (`create --help` → rc=0) | ✅ |
| `tests/benchmark.py` | **68/68 PASS** (41,2 s, exit 0) | ✅ |
| `tests/evaluate.py` (rubrica ponderada) | **13/13 = 100%** (exit 0) | ✅ |
| `tests/scenario.py` (auditoria comportamental E2E) | **7/7 CLEAN · 0 anomalias** (exit 0) | ✅ |

**Cobertura do benchmark (amostra):** roteamento do entry-gate, PoT Monte Carlo, code_genetics + SQLite, memory (KG + grafo acíclico), execution_policy (HARD-RULE), swap_store (round-trip + integridade), federation (HMAC + fusão de cadeias), rag_index/solid_state_index (427 nós), agent_spawn/lifecycle/materializer, catalog_determinism (4 catálogos byte-idênticos entre rebuilds).

**Conclusão da Parte A:** 🟢 **Todos os módulos executam como planejado.** A skill roda em stdlib puro com degradação graciosa. Nenhuma regressão. Este é o baseline sobre o qual as correções abaixo serão aplicadas.

---

## Parte B — Debug: observações do passe da equipe

Durante a execução, além dos achados de segurança da autópsia, o passe de debug registrou:

- **DBG-1 (QA/UX):** `python skill_forge.py` sem argumentos sai com `rc=2` (uso do argparse). Correto para CLI, mas um bare-run poderia imprimir o help com `rc=0` (consistência com os demais `__main__` que são self-tests). *Cosmético.*
- **DBG-2 (Dev):** os dois gates AST (`skill_scout` e `guards`) têm **cegueiras idênticas** — confirmado por PoC (ver C-04). Isso é sintoma direto da duplicação de código (C-07): a mesma falha vive em dois lugares.
- **DBG-3 (Tech Lead):** a documentação chama o hash SHA-256 de bundle/agente de **"assinatura"** (`documentacao.md:137,220`, `inventario.md`), o que é impreciso — um hash não autenticado não é assinatura (ver C-02). Risco de falsa sensação de segurança.
- **DBG-4 (Segurança):** o restaurador `_restore_stores`/`import_bundle` acessa chaves do bundle direto (`r["sha"]`, `bundle["stores"]["user"]`) dentro de `except Exception: pass` amplos — um bundle malformado é **silenciosamente** ignorado (ver C-06).

Nenhuma dessas observações quebrou execução; são precondições/qualidade que alimentam as correções.

---

## Parte C-STATUS — Execução das correções (ciclos 1–3) ✅

> Ciclo aplicado conforme solicitado: **Corrigir → testar (Dev+QA+Tech Lead, todos os módulos + fluxo da SKILL.md) → identificar novas ocorrências → atualizar inventário → corrigir → repetir**. Portão de regressão a cada ciclo: `benchmark 68/68 · evaluate 13/13 (100%) · scenario 7/7 CLEAN`.

| ID | Ciclo | Status | Evidência de fechamento |
|---|---|---|---|
| **C-07** | 1 | ✅ RESOLVIDO | `_ast_helpers.py` compartilhado; duplicação eliminada |
| **C-01** | 1 | ✅ RESOLVIDO | `make_filename` sanitiza + guard `commonpath` em `write_versioned`; PoC de traversal agora **contido** no swap dir |
| **C-04** | 1 | ✅ RESOLVIDO | `numpy.load(allow_pickle)`, `pandas.read_pickle`, `open()` modo não-literal → **safe=False / REJECTED** nos 2 gates; controles preservados |
| **C-02** | 2 | ✅ RESOLVIDO | HMAC exigido quando `APEX_FED_KEY` setada; bundle forjado (sha recomputado) → **REJECTED**; sem chave = retrocompat |
| **C-03** | 2 | ✅ RESOLVIDO | `import_pack` expõe `UNSIGNED/SIGNED` proeminente no gate H5 |
| **C-06** | 2 | ✅ RESOLVIDO | `import_bundle` retorna `warnings[]` por-arquivo em vez de swallow silencioso |
| **C-05** | 3 | ✅ RESOLVIDO (revisado) | benchmark staged roda com **ambiente scrubbed** (não herda segredos). *Abordagem de scan com forge gate descartada: reprovava 43/52 scripts legítimos* |
| **C-08** | 3 | ✅ RESOLVIDO | parse do resultado via regex `\d+/\d+` (degrada seguro) |
| **C-09** | 3 | ✅ RESOLVIDO | `skill_forge` sem subcomando → help + rc=0 (self-tests 50/51 → **52/52**) |

### Novas ocorrências encontradas DURANTE os ciclos (loop de descoberta)

| ID | Ciclo | Severidade | Ocorrência | Correção | Status |
|---|---|---|---|---|---|
| **N-01** | 1 | 🟡 Médio | `_ast_helpers.py` novo não registrado em `catalog/scripts_lib.json` (quebrou consistência 1:1 — padrão F-08) | Entrada `script:_ast_helpers` adicionada ao catálogo | ✅ RESOLVIDO |
| **N-02** | 2 | 🟠 Alto (teste) | **Testes flaky** `agent_lifecycle`/`agent_materializer` (evaluate 66/68 intermitente): não-hermético — o especialista materializado persistia no overlay de roster e quebrava o precondition `no roster match → synthesize` em home reusado | `_wipe_grown_roster()` no início dos 2 testes | ✅ RESOLVIDO (fresh=determinístico; reuse agora 68/68) |

**Estado final do loop (ciclos 1–3):** após 3 ciclos, o portão de regressão é atingido de forma **estável e determinística** (evaluate deixou de oscilar). Matriz de módulos pós-correção: **52/52 importam · 52/52 self-tests rc=0**.

### Ciclo 4 — QA dirigido pelos MODOS OPERACIONAIS (EXPRESS · STANDARD · FOGGY · DEEP · SCIENTIFIC · RESEARCH)

Harness `mode_qa.py` exercitou a skill através de **cada modo** da SKILL.md, validando o contrato de cada um (seleção de modo, política de exploração `chaos/parallelism/genius`, budgets de token, persistência, kernel checklist) + consistência doc↔código dos budgets.

| Modo | Verificação | Resultado |
|---|---|---|
| consistência | `MODE_TOKENS`/`MODE_LADDER`/`VALID_MODES` (doc vs código) | ✅ 6 modos coerentes |
| EXPRESS | trivial → skip pipeline, chaos off, output_budget | ✅ |
| STANDARD | tarefa reconhecida de baixa dificuldade fica leve, parallelism A | ✅ |
| FOGGY | `min_mode` força piso; chaos on, parallelism B | ✅ |
| DEEP | multi-disciplina → DEEP, phase_plan, chaos | ✅ |
| SCIENTIFIC | math/dynamics → SCIENTIFIC, persist_due, kernel steps | ✅ |
| RESEARCH | `deep_research` loop, genius stance, persist_due, stop_reason | ✅ |

**Resultado final: 0 issues** (após classificar N-03 abaixo).

| ID | Ciclo | Severidade | Ocorrência | Correção | Status |
|---|---|---|---|---|---|
| **N-03** | 4 | 🔵 Baixo (doc) | O harness inicialmente marcou "tarefa de código simples → DEEP em vez de STANDARD". Investigação: `estimate_difficulty` retorna `uncertain=True` (→ DEEP) para tarefas cuja classe **não é reconhecida** (Jaccard < 0.10 vs. `DIFFICULTY_REFS`, que só contém classes difíceis). **Não é bug** — é escalação conservadora **intencional e travada por teste** (`benchmark.py:709` exige que "escrever um poema" seja `uncertain`). O resíduo real é uma **lacuna de documentação**: a SKILL.md dizia "Default STANDARD" sem revelar que classes não-reconhecidas escalam para DEEP. | Nota de "conservative escalation" na SKILL.md §1.1 + expectativa do harness corrigida (usar tarefa reconhecida) | ✅ RESOLVIDO (doc; sem mudança de código — alterá-la quebraria o comportamento intencional/testado) |

**Estado ao fim do ciclo 4:** modos operacionais validados (0 issues), regressão verde (68/68 · 13/13 · 7/7). **Ponto fixo atingido — nenhuma ocorrência acionável de código restante.**

### Ciclo 5 — STRESS TEST em tempo real (skill completa rodando com problemas reais)

Dois harness em tempo real dirigidos por modos + subsistemas duráveis, com **validação de resultados reais** (não só "rodou") e timings.

**Passe 1 — `stress.py` (problemas reais, todos os subsistemas):**

| Área | O que rodou (real) | Resultado |
|---|---|---|
| Compute | PoT chain (20! mod p exato), RK4 (`y(1)` err < 1e-3 vs e⁻²), Monte Carlo (média ~1.0, 20k it), verify identity | ✅ |
| Modos | EXPRESS (aritmética exata), STANDARD, FOGGY, DEEP (multi-disciplina), SCIENTIFIC (EDO+prova), RESEARCH (loop) | ✅ |
| Memória persistente | remember + KG edge + ledger SHA-256 → **page-out → home NOVO → page-in** → recall sobrevive + ledger re-verifica | ✅ |
| Agentes | resolve→spawn(AgentSpec)→finalize(validated)→**materializado**→overlay durável→**sessão 2 acha sem re-síntese** (promoção durável) | ✅ |
| Cache | scan (parse 3) → re-scan (cached 3) → touch (reparse 1) → delete (prune) | ✅ |
| Learning | promote@3 sucessos + demote sustained-fail (excluído do best) | ✅ |
| Throughput | **50 `orchestrator.run` back-to-back sem crash — 8.6 runs/s** | ✅ |

**Passe 2 — `stress2.py` (adversarial / edge / failure modes):**

| Vetor | Resultado |
|---|---|
| Inputs malformados (`""`/`None`/`int`/`dict`/20k chars/unicode/prompt-injection) → `run()` nunca levanta | ✅ |
| Express edge: `9**9**9` sem hang (cap de expoente), `1/0` tratado | ✅ |
| PoT sandbox: loop infinito **morto no timeout**, crash capturado, **segredo do pai scrubbed**, saída **capada** | ✅ |
| Concorrência: stance que crasha **não derruba** a rodada paralela | ✅ |
| Memória: 200 idênticos → **dedup=1**; **guarda de ciclo do KG** bloqueia A→B→C→A | ✅ |
| Bundle **adulterado → REJECTED** (C-02 em ação); bundle limpo aceito | ✅ |
| Cadeia de **deltas** (base+delta) reconstruída no page-in | ✅ |

**Resultado do ciclo 5: 0 ocorrências de código.** As únicas falhas encontradas foram **bugs no próprio harness** (uso incorreto das APIs `solve_ode`/`simulate`/`verify_identity`/`page_out`) — corrigidos no harness, **não eram defeitos da skill**. Regressão pós-stress: **68/68 · 13/13 (100%) · 7/7 CLEAN**.

**Estado ao fim do ciclo 5:** a skill roda a pipeline completa em tempo real sobre problemas reais, resiste a inputs adversariais e mantém integridade dos subsistemas duráveis sob carga. **Ponto fixo confirmado — nenhuma ocorrência acionável restante após 5 ciclos.**

### Ciclo 6 — Descoberta de skills em REDE (skills.sh + GitHub, tempo real)

Testadas as duas vias de descoberta em rede que faltavam.

| Via | Resultado medido | Diagnóstico |
|---|---|---|
| **skills.sh** | `leaderboard/search/official` → **OFFLINE** | **Não é bug do APEX** — o proxy do ambiente bloqueia `skills.sh:443` (`403 CONNECT, policy denial`). APEX **degradou corretamente** para OFFLINE (contrato de degradação OK). |
| **GitHub** (`raw.githubusercontent.com`) | HTTP 200 — fetch/parse/AST-scan/staging **executaram ao vivo** | Via funcional; **revelou N-04** (abaixo). |

| ID | Ciclo | Severidade | Ocorrência | Correção | Status |
|---|---|---|---|---|---|
| **N-04** | 6 | 🟠 Alto (usabilidade) | `skill_scout.extract_code_refs` (RT-13) capturava **nomes de arquivo nus mencionados em prosa** (ex.: "pot.py") e resolvia contra o diretório do SKILL.md (`…/pot.py`) em vez do path real (`…/scripts/pot.py`). Os **11 refs-phantom davam 404** → `evaluate` fail-close → **REJECTED_UNSAFE de uma skill OFFICIAL limpa**. Tornava a descoberta GitHub inutilizável para skills bem-documentadas. Comprovado ao vivo no próprio SKILL.md do APEX. | `extract_code_refs` passa a seguir só **refs path-qualified** (contêm `/`) e URLs; nomes nus de prosa são ignorados (código realmente distribuído continua coberto por refs com path + `code_urls` explícitos). | ✅ RESOLVIDO — refs phantom-404 **11 → 0** (todos os 52 refs resolvem para arquivos reais/HTTP 200); benchmark **68/68**. |

**Nota:** após o fix, o SKILL.md do APEX ainda fica `REJECTED_UNSAFE`, mas agora por **motivos reais** (seus scripts usam `subprocess`/`__import__`/`.spawn()`/import opcional) — o scanner estrito sinaliza para revisão humana. É a **mesma limitação documentada do C-05** (gate estático best-effort; H5 é a fronteira real), comportamento **intencional**, não defeito.

**Estado ao fim do ciclo 6:** descoberta em rede validada nas duas vias; skills.sh degrada corretamente sob bloqueio de rede; GitHub funcional com N-04 corrigido. Regressão **68/68 · 13/13 (100%) · 7/7 CLEAN**.

### Ciclo 7 — Descoberta GitHub-nativa (fornecedores confiáveis + estrelas + busca semântica)

Nova capacidade que substitui a dependência do skills.sh, resolvendo o problema levantado: **descobrir skills direto no GitHub**.

| ID | Ciclo | Tipo | Entrega | Status |
|---|---|---|---|---|
| **N-05** | 7 | Melhoria (capacidade nova) | `scripts/github_skills.py` — descoberta GitHub-nativa: **fornecedores confiáveis** (allowlist ampliada: anthropics, vercel-labs, microsoft, supabase, openai, google, huggingface…), **estrelas** (popularidade via API repo-scoped, degrada quando indisponível), **busca semântica** (`_tfidf` query↔descrição). Enumera SKILL.md via git-tree API (primário) ou parse de README raw (fallback). Alimenta `skill_scout.evaluate` (AST scan) + gate H5. | ✅ ENTREGUE + testado |

**Validação AO VIVO (contra o GitHub real, raw):**
- `"extract text and tables from pdf files"` → **pdf** ranqueado #1 (0.273); pptx/docx/xlsx abaixo ✅
- `"create and edit powerpoint presentations"` → **pptx** #1 ✅
- `"build spreadsheets with formulas"` → **xlsx** #1 ✅
- `discover()` completo: pdf → **STAGED (ast=PASS)** via `skill_scout.evaluate`; degradação limpa → **OFFLINE** quando nada enumera.

**Por que resolve o problema do skills.sh:** não depende do host `skills.sh` (bloqueado por política de rede aqui); usa `raw.githubusercontent.com` (liberado) + API repo-scoped quando disponível; "o que É skill" = presença de `SKILL.md` em hub confiável; ranqueia por relevância semântica real. **Estrelas** e a **API de árvore** ativam automaticamente onde o ambiente permite a API do GitHub (aqui degradam para o caminho raw+README).

**Nota de ambiente:** a **busca global** do GitHub (`search/code`) e a **API de outros donos** estão bloqueadas neste sandbox ("session bound to configured repositories"); o módulo foi desenhado para isso — degrada para enumeração via README raw (validada ao vivo). Em um deploy com API/token liberados, o caminho primário (git-tree + estrelas + busca por `filename:SKILL.md`) entra sozinho.

Teste `t_github_skills` (hermético, `fetch_text`/`_api_get` mockados) no benchmark: **69/69**. Consistência catálogo↔scripts mantida (`github_skills` registrado em `scripts_lib.json`).

**Refino (investigação do repo `vercel-labs/skills`):** analisando o código/README da CLI deles, o mecanismo ficou claro — **não é mágica semântica**:
- `vercel-labs/skills` é a **CLI** (`npx skills`), NÃO uma coleção de skills; as skills reais ficam em `vercel-labs/agent-skills` (meu seed apontava para o repo errado — **corrigido**).
- A descoberta deles usa **(a) skills.sh** (crawler+índice hospedado no servidor) e **(b) a API do GitHub** para enumerar repos de um owner e **caminhar uma lista fixa de diretórios-container** (`skills/`, `skills/.curated/`, `skills/.system/`, `.claude/skills/`, raiz…), layout flat e catálogo. Eles **não parseiam README**.
- **"Como eles conseguem e a gente não":** eles dependem da **API do GitHub + servidor skills.sh** — ambos **bloqueados neste sandbox** para repos externos ("session bound to configured repositories"). Não é deficiência do nosso código; é acesso de rede.

**Ajustes aplicados ao `github_skills.py`:** seed correto (`vercel-labs/agent-skills`); adotada a **mesma lista `CONTAINER_DIRS`** da CLI para o walk via git-tree; `find_by_owner()` = o mecanismo `--owner` deles (API, degrada p/ 0 quando bloqueada); **`CURATED_SKILLS`** = baseline verificado que **sempre** retorna lista real via raw, mesmo com API+README bloqueados. Lista ao vivo agora: query de frontend → `vercel-labs/agent-skills/web-design-guidelines` #1, seguida das skills `anthropics/skills`.

**Estado ao fim do ciclo 7:** descoberta GitHub-nativa entregue, testada e validada ao vivo; mecanismo do skills.sh/vercel esclarecido e replicado no que o ambiente permite. Regressão **69/69 · 13/13 (100%) · 7/7 CLEAN**.

### Ciclo 8 — `CURATED_SKILLS` ampliado (verificado ao vivo) + fiação na cascata automática

**(a) Catálogo curado verificado ao vivo** (HTTP 200, 2026-07) — **14 skills reais** de 2 fornecedores confiáveis:
- `anthropics/skills`: pdf, docx, pptx, xlsx, **mcp-builder, brand-guidelines, canvas-design, webapp-testing, slack-gif-creator, frontend-design, algorithmic-art, skill-creator** (12)
- `vercel-labs/agent-skills`: web-design-guidelines, **writing-guidelines** (2)
- `microsoft/skills` adicionado como **hub** (layout de catálogo — enumera via git-tree API onde disponível).
- Prova de ranking: query "slack bot + gif + mcp" → **slack-gif-creator (0.306)** e **mcp-builder (0.215)** no topo.

**(b) Fiação na cascata automática do orquestrador** (`deep_research`, invocado por `orchestrator`/`menu`):
- Nova função `_resolve_github(need)` + tier na cascata: **native → skills.sh → github**.
- Flag de config `discovery_github` (default `True`; testes desligam = herméticos).
- `_hit_quality`: hit github de fornecedor confiável = 0.7 (staged forte, abaixo de instalado 0.9).
- **Validação ao vivo:** `research('create a pdf report and a powerpoint deck', source='both')` → **2 skills GitHub staged automaticamente** (OFFICIAL, com `npx skills add ...`) — pela cascata, sem chamada manual.
- Teste `t_deep_research` estendido: assere que o **tier github está fiado** na cascata (mockado = hermético).

**Estado ao fim do ciclo 8:** descoberta GitHub-nativa **fiada na cascata automática** com catálogo curado verificado. Regressão **69/69 · 13/13 (100%) · 7/7 CLEAN**.

### Ciclo 9 — Cascata ABERTA: tier LOCAL-first (skills instaladas + MCPs)

Novo `scripts/local_discovery.py` — mapeia o que **já está instalado** no ambiente e o coloca como **tier 0** da cascata (antes de native → skills.sh → github), pois é custo zero, sem rede, sem gate de instalação.

**Cobre os três pontos pedidos:**
1. **Skills locais** — varre `~/.claude/skills`, `/mnt/skills/{public,examples}`, o projeto e `APEX_LOCAL_SKILLS`, caminhando os **diretórios-container completos** da convenção da CLI (`skills/`, `skills/.curated`, `.claude/skills`, `.agents/skills`, `data/skills`, `.continue/skills`…), layout flat e catálogo. **35 skills mapeadas ao vivo** (dedup por nome das 41 pastas), parseadas com `skill_scout.parse_skill_md`, ranqueadas semanticamente.
2. **MCPs vivos** — lê `mcpServers` das configs padrão (`.mcp.json`, `~/.claude.json` projects, `.claude/settings*.json`) + env `APEX_MCP_SERVERS`; expõe `mcp__<server>__*` para os agentes. (0 aqui — nenhum MCP persistido no config; degrada limpo.)
3. **Diretórios-container completos** — a lista `CONTAINER_DIRS` da CLI.

**Fiação na cascata** (`deep_research`):
- `_resolve_local(need)` como **tier 0**; flag `discovery_local` (default `True`; testes desligam = herméticos).
- `_hit_quality`: hit local = **0.95** (o tier mais forte — já instalado, sem H5).
- **Validação ao vivo:** `research('create a pdf report and edit a word document', source='both')` → resolveu com **skills LOCAIS** (docx, canvas-design, doc-coauthoring) e **TARGET_REACHED em 1 rodada** — as instaladas venceram, sem precisar do marketplace/github.
- Teste `t_deep_research` estendido: assere tier local fiado (mockado = hermético). Registrado em `scripts_lib.json`.

**Cascata final:** `LOCAL (instaladas + MCPs) → native (índice) → skills.sh (marketplace) → github (fornecedores confiáveis)`. Regressão **69/69 · 13/13 (100%) · 7/7 CLEAN**.

### Ciclo 10 — Memória das ESCOLHAS (proveniência) recuperável entre sessões

Antes de expandir mais a cascata: o runtime precisa **lembrar das próprias escolhas**. Novo `scripts/skill_ledger.py` grava a proveniência de cada decisão (os 7 campos) e a recupera em outras sessões via swap.

**Os 7 campos:** problema/necessidade · skill usada · agente que usou · resolveu? · foi promovida? · repositório · comandos (+ o que cada um faz).

**Como persiste (sem nova encanação — reusa os stores que o swap já captura):**
- `memory.remember` (semântica + meta) → `recall(problema)` acha a escolha [swap: memory]
- aresta de KG `problema --resolved_by/attempted--> skill` [swap: knowledge_graph]
- evento no ledger de governança SHA-256 (tamper-evident) [swap: ledger]
- `learning.record_outcome` → promove/rebaixa a skill por taxa de sucesso [swap: stores.learning]

**APIs:** `record(...)` grava; `recall(problema)` devolve escolhas passadas (7 campos + status de learning); `worked_for(task)` = **prior de atração** (skills que já resolveram problema similar — exclui falhas).

**Prova ao vivo (cross-session):** Sessão 1 grava 3 escolhas → page-out → **home NOVO** → page-in → Sessão 2 recupera problema/skill/resolveu/promoção/repo **e os comandos + o que cada um faz**; `worked_for('document editing')` → docx (1.0) e pdf (1.0).

**Fiação na atração/cascata:** novo **tier -1 PROVEN** no `deep_research` (`_resolve_proven` via `skill_ledger.worked_for`), qualidade **0.98** — "eu lembro que essa skill resolveu isso" é o sinal mais forte, acima de LOCAL (0.95). Gated por `discovery_local` (hermético nos testes).

**Cascata agora:** `PROVEN (lembrado) → LOCAL (instaladas + MCPs) → native → skills.sh → github`. Teste `t_skill_ledger` (hermético): grava 7 campos + recupera cross-session + prior exclui falhas. Registrado em `scripts_lib.json`. Regressão **70/70 · 13/13 (100%) · 7/7 CLEAN**.

### Ciclo 11 — Verificação da infraestrutura de swap + documentação atualizada

**(a) Verificação ao vivo da infraestrutura de swap (`verify_swap.py`): 20/20 PASS.**

| Área | Verificado |
|---|---|
| Padrão de pastas/nomenclatura/backups | árvore canônica materializada; nomes ao padrão; `KEEP_BACKUPS=10` rotaciona (13 versões → ≤10 sobrevivem em `versions/`) |
| Estado promovido (DB + JSON) | `learning.db` (PROMOTED capturado), `agent_grants.json`, `collect_stores` reúne tudo |
| Hashes que sobrevivem | bundle SHA-256 recomputa (tamper-evident); ledger `verify_ledger` ok |
| Backends | local (on-disk), drive-manifest, `compress` (gzip+b64), zip (`project_ledger`) |
| Restauração cross-session | page-in em home NOVO → **skill promovida restaurada**, memória + ledger re-verificam |
| Alimenta | taxonomia (overlay CANDIDATE→ADOPTED), gravidade (constelação), RAG por nós |

**(b) Documentação atualizada** (estava defasada):
- Contagem **51/46 → 55 scripts** (SKILL.md + spec.md; SR_40 confirma "55/55").
- 4 módulos novos (`_ast_helpers`, `github_skills`, `local_discovery`, `skill_ledger`) — **eram 0 docs** → adicionados às tabelas do `spec.md` e às linhas-resumo de arquitetura.
- `documentacao.md` §5.4.1 nova: **infraestrutura de swap completa** — o que persiste (DB+JSON), padrão de pastas, nomenclatura, `KEEP_BACKUPS=10`, quais hashes sobrevivem (bundle SHA-256/HMAC + ledger por-dispositivo), backends (drive/local/zip/git), **as 3 vias de restauração** (Drive / pasta-pendrive / ZIP do usuário) e como o estado promovido re-alimenta learning/taxonomia/gravity/RAG.
- Cascata de descoberta documentada na §5.5. `requirements.txt` conferido: **atual** (módulos novos são stdlib puro, sem novas deps).

Regressão **70/70 · 13/13 (100%) · 7/7 CLEAN**.

---

## Parte C — Inventário de correções (priorizado) — *referência original*

Severidade: 🔴 crítico · 🟠 alto · 🟡 médio · 🔵 baixo · 🟢 informativo.
Status: **NOVO** (achado nesta auditoria) · **CONHECIDO** (documentado antes) · **PoC** (comprovado por execução).

| ID | Correção | Sev. | Status | Arquivo:linha | Esforço |
|---|---|---|---|---|---|
| **C-01** | Path traversal em `make_filename`/`write_versioned` | 🔴 | NOVO · **PoC** | `swap_store.py:108,158,167,550` | Baixo |
| **C-02** | Integridade de bundle é hash não autenticado (chamado de "assinatura") | 🟠 | CONHECIDO¹ | `swap_store.py:520`; docs | Médio |
| **C-03** | HMAC de federação desligado por padrão | 🟠 | CONHECIDO | `federation.py:60-61` | Baixo |
| **C-04** | Bypass dos gates AST via libs whitelistadas / modo `open` variável | 🟡 | NOVO · **PoC** | `skill_scout.py:43,66`; `guards.py:48` | Baixo |
| **C-05** | Auto-update executa árvore staged sem varredura de segurança | 🟡 | NOVO | `menu.py:90-92` | Baixo |
| **C-06** | Swallow silencioso de exceções na restauração de estado | 🟡 | NOVO | `swap_store.py:553,560`; `_restore_stores` | Baixo |
| **C-07** | `_write_open_mode` duplicado (DRY) — a mesma falha em 2 arquivos | 🔵 | NOVO | `skill_scout.py:66` + `guards.py:48` | Baixo |
| **C-08** | Parsing frágil de `TOTAL x/y` no update | 🟢 | NOVO | `menu.py:93-95` | Baixo |
| **C-09** | `skill_forge` bare-run rc=2 (UX) | 🟢 | NOVO | `skill_forge.py` (`__main__`) | Trivial |

¹ *Parcial: a existência do hash é documentada, mas caracterizada erroneamente como "assinatura"; a fragilidade anti-tamper NÃO estava identificada.*

### Detalhe das correções

#### C-01 🔴 Path traversal em `make_filename`/`write_versioned` — **NOVO, PoC**
- **Estado atual:** o nome lógico é interpolado direto (`swap_store.py:108`: `f"{name}-{function}-{ts}-R{...}.{ext}"`) e usado em `os.path.join(folder, fn)` sem validação (`:158`, `:167`). Vetor: `import_bundle` passa a chave de `bundle["stores"]["user"]` (não confiável) como `name` (`:550`).
- **Evidência (PoC executado):** `make_filename('../../../../tmp/PWNED')` → `'../../../../tmp/PWNED-User-…json'`; `normpath` resolve para **`/home/tmp/PWNED-…json`** — fora do diretório de swap.
- **Correção-alvo:** função `safe_name()` central — `os.path.basename` + allowlist `[A-Za-z0-9_.-]`, rejeitando `..`/separadores; e guard `_resolved_within(folder, fn)` antes de `open()` (reusar o padrão `SEC-005` já existente em `repo_bridge.py:69/87`).
- **Aceite:** um bundle com chave `../x` deve ser **REJECTED**; PoC acima deve falhar.

#### C-02 🟠 Integridade de bundle = hash não autenticado — **CONHECIDO (parcial)**
- **Estado atual:** `swap_store.py:520` compara `_bundle_sha(bundle) == bundle["sha256"]`. SHA-256 detecta corrupção, **não** adulteração intencional (autor malicioso recalcula o hash). Docstring afirma "FAIL CLOSED on tamper"; docs chamam de "assinatura".
- **Correção-alvo:** exigir HMAC (reusar `APEX_FED_KEY`) ou assinatura para bundles de origem não confiável; corrigir docstring e docs para "detecção de corrupção" onde não há chave. Fecha, com C-01, o caminho de exploração.
- **Aceite:** com `APEX_FED_KEY` setada, um bundle sem HMAC válido é REJECTED; texto "assinatura" só onde há autenticação real.

#### C-03 🟠 HMAC de federação off por padrão — **CONHECIDO**
- **Estado atual:** `federation.py:60-61` → `""` quando `APEX_FED_KEY` ausente; assinatura/verificação puladas.
- **Correção-alvo:** marcar `UNSIGNED` de forma proeminente no prompt de aprovação H5; considerar assinatura obrigatória para import cross-device.
- **Aceite:** import de pacote não assinado surge no H5 rotulado `UNSIGNED`.

#### C-04 🟡 Bypass dos gates AST — **NOVO, PoC**
- **Estado atual (PoC executado, ambos os gates):**

  | Payload | `skill_scout.safe` | `forge.verdict` |
  |---|---|---|
  | `numpy.load(f, allow_pickle=True)` | `True` ❌ | `ACCEPTED` ❌ |
  | `pandas.read_pickle(x)` | `True` ❌ | `ACCEPTED` ❌ |
  | `open(p, m)` (modo variável) | `True` ❌ | `ACCEPTED` ❌ |
  | *controle* `os.system` | `False` ✅ | `REJECTED` ✅ |
  | *controle* `pickle.loads` | `False` ✅ | `REJECTED` ✅ |

- **Correção-alvo:** adicionar `read_pickle`, `np.load(allow_pickle=True)`, `joblib.load` aos *sinks* rejeitados; marcar `open()` com modo **não-constante** como REVIEW (hoje só constante literal é vista); aplicar nos DOIS gates (ver C-07).
- **Aceite:** as três linhas ❌ acima passam a `safe=False` / `REJECTED`; os controles seguem rejeitados; benchmark segue 68/68.

#### C-05 🟡 Update executa staged sem scan — **NOVO**
- **Estado atual:** `menu.py:90-92` roda `benchmark.py` da árvore staged via subprocess antes do swap, sem `forge_load_gate` nem env endurecida.
- **Correção-alvo:** rodar `guards.forge_load_gate` sobre os scripts staged (ou executar o benchmark na env scrubbed do `pot`) antes de confiar no resultado; documentar a suposição "clone local = confiável".

#### C-06 🟡 Swallow silencioso na restauração — **NOVO**
- **Estado atual:** `import_bundle`/`_restore_stores` engolem exceções com `except Exception: pass` (`swap_store.py:553,560` e blocos de grants/learning/competence), mascarando restauração parcial/corrompida.
- **Correção-alvo:** logar em nível debug em vez de `pass` e propagar um sinal de "restauração parcial" no dict de retorno.

#### C-07 🔵 `_write_open_mode` duplicado — **NOVO**
- **Estado atual:** cópia idêntica em `skill_scout.py:66` e `guards.py:48` → C-04 precisa ser corrigido em dois lugares (fonte do DBG-2).
- **Correção-alvo:** extrair para `scripts/_ast_helpers.py` compartilhado e importar nos dois gates.

#### C-08 🟢 Parsing frágil `TOTAL x/y` — **NOVO**
- `menu.py:93-95` extrai `TOTAL x/y` por string. Falha segura (→ `REJECTED_STAGED`), mas opaca. Sugestão: benchmark emitir marcador JSON estruturado.

#### C-09 🟢 `skill_forge` bare-run — **NOVO**
- `python skill_forge.py` sem args → rc=2. Opcional: imprimir help com rc=0 quando sem subcomando.

---

## Parte D — Plano de execução das correções (ordem sugerida)

1. **C-07** (extrair helper) — habilita corrigir C-04 uma vez só.
2. **C-01 + C-04** (path traversal + bypasses) — as duas correções de segurança de maior valor/menor esforço; ambas têm PoC e critério de aceite objetivo.
3. **C-02 + C-03** (autenticação de bundle/federação) — fecha a cadeia de exploração de C-01 e corrige a caracterização "assinatura".
4. **C-05 + C-06** (update seguro + fim do swallow silencioso).
5. **C-08 + C-09** (robustez/UX cosméticos).

**Portão de regressão para cada correção:** `benchmark.py` deve seguir **68/68**, `evaluate.py` **13/13**, `scenario.py` **7/7 CLEAN**, e os PoCs de C-01/C-04 devem passar a falhar (comportamento seguro). Nenhuma correção pode tocar os dados reais em `~/.apex-method` (usar `APEX_METHOD_HOME` isolado, como as suítes já fazem desde v1.42).

### Ciclo 12 — Último recurso da cascata: o LLM CRIA skills (skill_forge)

Novo tier final: quando **nada existe** (sem PROVEN, sem LOCAL, native não achou, marketplace falhou, GitHub falhou), o runtime propõe que o **LLM crie a skill** via `skill_forge`.

- `_resolve_forge(need, domain)` no `deep_research`: **proposta STAGED** (`action: LLM_CREATE_SKILL` + nome kebab + descrição + comando `skill_forge.py create ...`) — **não escreve arquivo**; adoção é do LLM atrás do H5.
- **Gatilho preciso:** dispara só quando **não há hit forte (≥0.6)** — um stub offline do marketplace (0.55) conta como "marketplace falhou". `_hit_quality` forge = **0.4**. Flag `discovery_forge` (default True).
- **Validado ao vivo:** necessidade inédita + tiers vazios → forge dispara; com hit forte (local acha pdf) → forge **não** dispara. Teste `t_deep_research` estendido (hermético).

**Cascata final completa:** `PROVEN (0.98) → LOCAL (0.95) → native → skills.sh → GitHub (0.7) → FORGE (0.4, LLM cria — último recurso)`. Regressão **70/70 · 13/13 (100%) · 7/7 CLEAN**.

---

*Inventário produzido após execução e debug completos de todos os módulos. Pronto para a fase de correção (aguardando aprovação para implementar, começando por C-07 → C-01/C-04).*
