# documentacao.md — APEX Method: o manual

> **Papel deste documento:** o manual narrativo — o que é o APEX, que dores resolve, quando
> vale a pena usá-lo, o que foi **idealizado** para cada módulo e qual o **comportamento
> esperado** de cada um. O contrato técnico de engenharia (entregas → para quem, invariantes)
> vive no `spec.md`; o kernel operacional que o LLM segue é o `SKILL.md`; o histórico de
> versões/auditorias, no `inventario.md`. Para achar qualquer coisa:
> `python scripts/rag_index.py "sua pergunta"` · para saber COMO usar qualquer capacidade:
> `python scripts/capability_map.py "sua pergunta"`.

---

## 1. O que é o APEX

O APEX Method é um **runtime cognitivo**: um sistema operacional fino em volta de um LLM.
A premissa: o LLM é uma **VM cognitiva** excelente em inferência, síntese e julgamento — e
ruim em aritmética exata, disciplina de processo, memória entre sessões e autoavaliação. O
APEX não tenta "reprogramar" o modelo com prompts; ele **cerca** o modelo com um kernel
(`SKILL.md`), 46 syscalls executáveis (`scripts/*.py`), catálogos, memória durável e gates
verificáveis, de modo que:

- o que é **computável** é computado (PoT em subprocesso, RK4, Bayes, Monte Carlo real);
- o que é **verificável** é verificado (UCO no código, sympy na matemática, hashes em tudo);
- o que é **aprendido** persiste (vacinas, learning, grants, memória com grafo) e volta como
  **contexto** nas janelas futuras — a tese central: *contexto vence prompt*;
- o que é **crítico** não é pulável (triage, piso de modo, kernel checklist + gate).

## 2. Que dores ele resolve

| Dor (sem APEX) | Resposta do APEX |
|---|---|
| LLM "chuta" aritmética e algoritmos de cabeça | PoT em subprocesso isolado, RK4/scipy, verificação simbólica — número computado, não estimado |
| Cada sessão começa do zero (gênio amnésico) | memória swap **plug-and-play**: hábitos, specs-diretriz, agentes treinados, vacinas e memória viajam num bundle assinado e voltam em qualquer máquina (`resume_due`) |
| Skill instalada vira texto morto redescoberto a cada uso | **mapa de capacidades**: comandos, triggers, linguagens e templates de cada skill/ferramenta mapeados e consultáveis por RAG (`how_to`) — e a competência de usá-la é PROMOVIDA por outcomes reais |
| Custo de token explode em tarefa simples (ou rigor some em tarefa difícil) | modos com orçamento + triage + piso de modo + **DSM do pipeline**: EXPRESS corta ~5.1k tokens estimados; STANDARD poda 4 passos (~3.8k); contexto injetado é dimensionado por modo (0 no EXPRESS) |
| O LLM diz que seguiu o processo, mas pulou etapas | **kernel checklist booleano + gate**: passos de código voltam com evidência; passos do LLM voltam com a chamada exata; o gate devolve ao LLM até tudo ser `True` |
| "Multi-agente" que é só rótulo | contrato de spawn: agente genérico assume persona REAL (AGENT.md), atrai skills/diffs/scripts pelo grafo gravitacional, equipa/desequipa com persistência, e vira **artefato portátil** (agent bundle assinado, instalável com H5) |
| Código/skill da internet executado no impulso | conteúdo externo é DADO até ser vetado: allowlists, AST-scan 2 níveis, scan de prompt-injection, arquivo truncado recusado, aprovação humana H5 sempre |
| Respostas confiantes sem lastro | honestidade epistêmica com marcadores (`[APPROX]`, `[CONJECTURA_FORMAL]`, `[SIMULATED]`), proveniência ONDE/COMO em cada achado, ledger SHA-256 à prova de adulteração |

## 3. Quando vale a pena usar (e quando não)

**Use quando:** a tarefa é multi-etapas ou de alto risco; há matemática/dinâmica real;
auditoria/segurança/compliance (o piso de modo força ≥ DEEP); projetos que atravessam
sessões/máquinas; quando você quer agentes especializados que melhoram com o uso; quando o
custo de estar errado supera o custo de alguns milhares de tokens de processo.

**Não use (o próprio APEX se recusa a burocratizar):** perguntas triviais — o triage responde
em EXPRESS (~400 tokens) e pula o pipeline inteiro; conversas exploratórias leves; qualquer
coisa onde o processo custaria mais que o valor da resposta (STANDARD poda os passos de
fan-out pesado por decisão do escalonador geodésico).

## 4. Arquitetura idealizada (e o que cada camada deve realizar)

```
        ┌────────────────────────── KERNEL (SKILL.md) ──────────────────────────┐
        │ disciplina, modos com orçamento, regras invioláveis, gate mandatório │
        └──────┬────────────────────────────────────────────────────────┬──────┘
 ENTRADA       │                                                        │  HAL
 orchestrator.run ── triage ── dissect ── especialistas ── modo ── plano│  apex_llm.yaml
        │  (checklist: código executa e PROVA; LLM recebe o bastão)     │  llm_adapter
        ▼                                                               ▼
 ROTEAMENTO: taxonomy (facetas PT/EN) → router/gravity → attraction_graph (pré-computado)
        ▼
 AGENTES: agent_registry (roster) → agent_spawn (persona real + equipamento + CONTEXTO
          validado injetado) → concurrent_executor (Level A subprocessos / Level B manifesto)
        ▼
 DECISÃO: bayes (posterior, Ω, R_acum) + verification_gate + fractal_compression + PMI
        ▼
 MEMÓRIA: memory (semântica/episódica + Knowledge Graph + ledger) · learning · vacinas ·
          grants · capability_map — tudo pagina via swap_store (plug-and-play, delta+gzip,
          resume_due) para pasta local / pendrive (APEX_HOME) / Drive → consolida via commit
```

Comportamento idealizado do todo: **nenhuma sessão começa fria, nenhuma etapa crítica é
pulada, nenhum número é chutado, nada externo roda sem vetting, e toda experiência bem-
sucedida vira insumo de auto-evolução** (vacina → contexto; outcome → promoção; grant →
agente mais capaz; descoberta → grafo maior).

## 5. Módulos — o que foi idealizado e o comportamento esperado

### 5.1 Entrada, modos e disciplina

**`orchestrator`** — *idealizado como:* o único ponto de entrada que executa o fluxo na
sequência correta sem depender da boa vontade do LLM. *Comportamento esperado:* `run()`
nunca levanta exceção (degrada para `ERROR_DEGRADED`); trivial → EXPRESS; devolve
`kernel_checklist` com os passos de código já executados **com evidência** e `llm_actions`
com a chamada exata de cada passo do LLM; `gate()` só declara COMPLETE com tudo `True`;
anexa `resume_due` (swap mais novo que o local) e `context_pack` (dimensionado pelo DSM).

**`execution_policy`** — *idealizado:* o contrato que impede dois erros fatais — descoberta
rodando no sandbox selado e tarefa crítica rodando em modo raso. *Esperado:*
`needs_internet=True` NUNCA roteia para subprocess; auditoria/segurança/compliance têm piso
DEEP; classe de dificuldade desconhecida escala e exige as 3 personas de dissect;
`loop_guard` para o runtime em 8 iterações/3 restarts/estagnação.

**`mental_interpreter` / `geodesic_scheduler` / `verification_gate`** — *idealizado:* dimensionar
e ordenar o trabalho pelo valor por token. *Esperado:* `n_final = max(MIN, min(n_num, n_rel,
MAX))`; passos ordenados por ΔH/token com rollback >115%; só hipóteses arriscadas vão à
verificação cara (P≠NP), com poda prematura.

**`config` / `menu` / `llm_adapter`** — *idealizado:* preferências do usuário persistentes e
portabilidade entre provedores. *Esperado:* `resolve_mode` nunca rebaixa um modo forte
silenciosamente; `menu.py update` funciona em Windows (shutil); `degrade()` anuncia Level
B→A, modo capado e loop manual conforme a matriz do `apex_llm.yaml`.

### 5.2 Roteamento e composição

**`taxonomy`** — *idealizado:* atração por SIGNIFICADO, não por palavra (o problema
"moda"→T-Mobile). *Esperado:* PT e EN caem nas mesmas facetas canônicas; primeiro fallback
do `dissect`.

**`router` / `gravity`** — *idealizado:* achar a skill/constelação certa e ser HONESTO
quando não há. *Esperado:* stubs demotados; `NO_RELIABLE_SKILL` abaixo do piso; constelação
com raio absoluto → relaxado → relativo (co-load), vazio honesto para tarefa alienígena;
lacunas viram pedidos STAGED (H5) na cascata nativo → skills.sh → GitHub.

**`attraction_graph`** — *idealizado (pedido do autor):* o JSON de roteamento onde tudo que
se completa se atrai — busca a 1ª competência e o resto vem por atração, sem redescoberta.
*Esperado:* ~320 nós, ~2k arestas com pesos gravitacionais; `expand()` em cadeia com decay;
`rebuild()` a cada inclusão (mesmo gatilho do `rag_index` e do `capability_map` — as três
memórias crescem juntas).

**`repo_bridge` / `skills_sh` / `curated` / `asset_manager` / `skill_forge`** — *idealizado:*
todo o super-repositório endereçável com segurança. *Esperado:* allowlist + redirect checado
+ traversal recusado + ref pinável; marketplace com barra ≥1000 installs; nada auto-instala.

### 5.3 Agentes que aprendem

**`agent_registry`** — *esperado:* roster enxuto; grants **persistem por default**,
sobrevivem a reload (`load()` auto-merge) e são revogáveis (`revoke_grant`).

**`agent_spawn`** — *idealizado:* o diferencial do APEX — não equipar mil skills, e sim
spawnar agentes que **chegam treinados**. *Esperado:* `spawn()` monta persona real +
equipamento atraído + grants + histórico + governança + template + **context pack** (a
experiência validada injetada na janela); `spawn_ready=False` não spawna; `export_agent`/
`import_agent` movem o agente treinado entre máquinas com assinatura SHA-256 e gate H5
(adulterado → REJECTED).

**`concurrent_executor` / `chaos_operators` / `competence_matrix` / `learning`** —
*esperado:* Level A com speedup real medido; manifesto Level-B com specs completas +
contrato; caos propõe mas nunca decide sozinho (SR_11); diagnóstico PERSONA_SWAP /
INJECT_SKILL / HARD_PROBLEM; promote/demote beta-binomial (Ω 0.72/0.5, ≥3 obs) espelhado no
ledger.

### 5.4 Memória, experiência e contexto

**`memory`** — *esperado:* semântica deduplicada por conteúdo, episódica distinta, grafo
tipado acíclico (ciclo direcional REJEITADO), ledger encadeado que detecta edição de
QUALQUER coluna, export NDJSON portátil.

**`code_genetics` (vacinas)** — *idealizado:* toda falha corrigida vira imunidade. *Esperado
(v1.44):* store durável por default (`vaccines.db`), texto da lição preservado, promoção só
com prova (≥2 usos, >0.85), e `relevant(task)` alimenta o contexto de janelas futuras.

**`capability_map`** — *idealizado (pedido do autor, item 2):* o APEX não só ACHA skills —
ele **aprende a trabalhar** com o que está instalado: mapeia comandos, triggers, linguagens
presentes (probe real do ambiente), bibliotecas importáveis e templates de design/documento
a seguir. *Esperado:* `how_to("como faço X?")` responde com a capacidade + comandos exatos
via RAG por nós; **mapear ≠ executar** (comandos são dados; execução segue nos gates);
`record_use(id, success)` promove/demota a competência de uso no learning — "sei extrair o
máximo de X" é conquistado, nunca assumido; `rebuild()` a cada instalação aprovada.

**`swap_store`** — *idealizado:* a memória como formato de distribuição plug-and-play (a
ideia original: nunca começar do zero — hábitos, specs, rotinas, agentes treinados, quem se
conecta com quem). *Esperado:* bundle carrega TODOS os stores; delta encadeado + gzip;
`page_in_session` aplica base+deltas verificando cada elo; adulteração → REJECTED antes de
qualquer escrita; `resume_due()` avisa na entrada; funciona igual em pasta local, pendrive
(`APEX_HOME=E:\APEX`) e Drive (manifesto append-only); consolidação final = commit no repo.

**`learning` / `project_ledger` / `snapshot` / `apex_st_metric`** — *esperado:* histórico
validado consultado no início de cada tarefa; inventário vivo com DSM de micros (caminho
crítico + lotes paralelos) e gate de conclusão; snapshot com proveniência; estagnação
detectada (2× FLAT → meta-aprendizado).

### 5.4.1 Infraestrutura da memória swap (padrão canônico — verificado 20/20)

O que é salvo, onde, com que nomes, quais hashes sobrevivem e como se restaura. **Um único
padrão**, idêntico em pasta local, pendrive e Drive.

**O que persiste (o "estado promovido" — DB + JSON):**
- **DB SQLite:** `memory.db` (episódica/semântica + **Knowledge Graph** + **ledger** SHA-256),
  `learning.db` (promovido/rebaixado por Bayes beta-binomial), `competence.db`, `vaccines.db`,
  overlay de `taxonomy` (CANDIDATE→ADOPTED), roster crescido (`grown_agents.json`).
- **JSON:** `agent_grants.json` (quem equipou qual skill/script), `config.json` (hábitos/modos),
  persona/preferences (tier `user`). `collect_stores()` reúne TODOS num bundle.
- Um **bundle** (JSON) por page-out carrega tudo isso + a memória em NDJSON; `page_out(delta=True)`
  exporta só o novo (cadeia `delta_of`), `compress=True` = gzip+b64 (~10× menor no trânsito).

**Padrão de pastas** (`materialize()` cria idêntico em qualquer backend):
```
APEX/
  user/            persona, preferences, config            (+ user/versions/)
  memory/          memory.ndjson, knowledge_graph, ledger  (+ memory/versions/)
  swap/<sessão>/   session-*.json (cabeçalho) + bundle-*.json (+ versions/)
  archive/         páginas de swap superadas
```
Regra: a **pasta MAIN** sempre tem o LATEST; versões antigas vão para `versions/`.

**Nomenclatura de arquivos** (colisão impossível — RT-09/09b):
`<name>-<function>-<YYYYMMDDHHMMSS+micros>-R<NN>.<ext>` (UTC, ordenável, microssegundos).
`name`/`function`/`ext` são sanitizados ao charset canônico → **sem path traversal** (C-01).

**Backups / rotação:** `KEEP_BACKUPS = 10` — os **10 mais novos** de cada tipo sobrevivem em
`versions/`; os mais antigos são coletados (no Drive, que é append-only, são **listados** para GC,
pois não há API de delete).

**Quais hashes sobrevivem (integridade):**
- **bundle:** SHA-256 sobre o payload inteiro; `import_bundle` recomputa e **FALHA FECHADO** se não
  bater (adulterado → REJECTED antes de qualquer escrita). Com `APEX_FED_KEY` setada, exige **HMAC**
  (C-02 — hash puro é anti-corrupção, não anti-tamper).
- **ledger:** cadeia SHA-256 **por dispositivo**; fundir bundles de N máquinas intercala N cadeias
  íntegras; editar qualquer coluna quebra a cadeia (`verify_ledger` detecta).
- **memória/vacinas:** content-addressing SHA-256 (dedup).

**Backends de durabilidade (`config.persist_backend`):**
- `drive-swap` — o runtime (Claude) sobe o `drive_manifest` via as ferramentas de Drive (append-only).
- `local` — a cópia em `<APEX_HOME>/swap/...` já é o artefato durável (pasta local ou pendrive
  `APEX_HOME=E:\APEX`).
- `git` — consolidação por commit no repo. `zip` — export `.zip` (via `project_ledger`).

**As três vias de restauração** (todas passam por `import_bundle`, mesmo fail-closed):
1. **Drive** — baixa os arquivos de `APEX/swap/<sessão>/` e aplica a cadeia.
2. **Pasta local / pendrive** — o usuário copia a pasta `APEX/` para onde for e o sistema lê dela.
3. **Usuário envia ZIP** — `page_in_session` aplica base+deltas do conteúdo enviado.
`resume_due()` avisa NA ENTRADA da sessão que há swap mais novo que o estado local.

**Como alimenta o resto:** o estado promovido restaurado volta ao `learning` (promovido/rebaixado),
ao overlay do `taxonomy` (facetas ADOPTED), ao roster/grants (agentes), e o `rag_index`/`gravity`
re-sincronizam (`rebuild()`), seguindo o **padrão de dados que o agente compreende** (nó com
path+resumo, corpo do skill/diff sob demanda). `skill_ledger` grava a **proveniência das escolhas**
(problema→skill→agente→resolveu?→promovida?→repo→comandos) nesses mesmos stores, então ela viaja no
swap e vira o **tier PROVEN** da cascata na sessão seguinte.

### 5.5 Segurança (comportamento esperado em uma linha cada)

`skill_scout`: allowlist raw.githubusercontent, redirect final checado, truncado recusado,
AST 2 níveis (RCE rejeita; import fora da whitelist ≠ safe; `numpy.load(allow_pickle)`/
`pandas.read_pickle`/`open` de modo não-literal rejeitados — C-04), scripts referenciados
descobertos e escaneados (só path-qualified — N-04), prompt-injection sinalizado. `guards`:
SR_36–40 executáveis; `getattr` dinâmico rejeitado. `uco_gate`: juiz determinístico antes de
todo subprocesso. Fronteira real: **H5 — aprovação humana**; o scanner é gate estático
best-effort, não sandbox.

**Cascata de descoberta (ordem, cada tier com sua qualidade):**
`PROVEN (skill_ledger, 0.98 — lembro que resolveu)` → `LOCAL (local_discovery, 0.95 — já
instalada, sem H5)` → `native (índice 3.784)` → `skills.sh (marketplace, H5)` → `github
(github_skills — fornecedores confiáveis + estrelas + semântica, H5)`. Flags `discovery_local`
/ `discovery_github` (default True). Nada instala sozinho: cada candidato externo passa por
`skill_scout.evaluate` (AST scan) + **H5**. As skills LOCAIS e PROVEN já são confiáveis (não
precisam de instalação/gate).

### 5.6 Mapa e auto-conhecimento

**`rag_index`** — *idealizado:* mapear o repositório inteiro em nós vetoriais para nunca
re-ler 16k arquivos. *Esperado:* ~145 nós (módulos, catálogos, referências, áreas do repo,
**capacidades**) com IDF global; consulta PT/EN em ms; `rebuild()` junto com o grafo.

**`pipeline_dsm`** — *idealizado (pedido do autor, item 3):* virar o DSM do APEX para dentro
dele mesmo. *Esperado:* matriz de imports EXATA (níveis paralelos, ciclos, núcleo de
sustentação) + fluxo por modo `[APPROX]` via geodésico (rodar/pular/economia) + a otimização
APLICADA: `context_budget(mode)` — 0 chars no EXPRESS até 2000 no RESEARCH.

## 6. O que o DSM revelou (execução real, 2026-07-18)

- **46 módulos, 5 níveis topológicos** — o núcleo carrega em lotes paralelos.
- **Núcleo de sustentação (fan-in):** `_tfidf` (7), `repo_bridge` (7), `config` (6) — mudanças
  neles exigem a suíte completa.
- **3 ciclos de import:** `agent_spawn↔orchestrator`, `capability_map↔rag_index`,
  `execution_policy↔orchestrator`. São **lazy imports dentro de funções** (seguros em
  runtime, sem ciclo de load) — acoplamento deliberado e agora documentado; quebrá-los
  exigiria um módulo de interfaces, custo que hoje não se paga.
- **Fluxo por modo (estimativas `[APPROX]`):** EXPRESS roda 1/13 passos (economia ~5.160
  tokens vs pipeline cheio); STANDARD roda 9/13 (poda SPAWN/STANCES pesados, ~3.800);
  FOGGY+ rodam tudo — o rigor é o produto nesses modos. Contexto por modo: 0 / 500 / 900 /
  1300 / 1600 / 2000 chars.

## 7. Roteiro de escala (o plano do autor)

1. **Skill do Claude** (estado atual): instalável, suítes 54/54–13/13–7/7.
2. **Portabilidade GPT/Gemini/Ollama:** o frontmatter do `SKILL.md` já é YAML; o
   `apex_llm.yaml` + `llm_adapter` já degradam por provedor (sem subagentes → Level A; janela
   pequena → modo capado; sem tool-calling → loop manual). O que falta por host é só o
   adapter de spawn (o contrato já está pronto em `spawn_contract()`).
3. **Memória antes do commit:** swap em pasta local/pendrive (`APEX_HOME`) ou Drive
   (manifesto append-only) → gate de promoção (PMI + ledger + testes) → **consolidação via
   commit** no repositório — o disco definitivo é o git.
4. **Federação (visão):** bundles são conjuntos mescláveis por construção (conteúdo
   endereçado); agentes treinados e pacotes de conhecimento validado circulam com assinatura
   e H5 — experiências bem-sucedidas de cada instância viram conteúdo de auto-evolução de
   todas.

## 8. Como validar este documento

```
python tests/benchmark.py                      # 1 teste por módulo + regressões
python tests/evaluate.py                       # rubrica objetiva
python tests/scenario.py                       # comportamento fim a fim
python scripts/pipeline_dsm.py                 # o DSM ao vivo
python scripts/capability_map.py "como ...?"   # a memória de ferramentas
```
