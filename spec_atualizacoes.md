# spec_atualizacoes.md — APEX v1.62.0

**Data:** 2026-07-21 | **Branch:** `claude/apex-skill-analysis-upuizg` | **Benchmark:** 72/72 PASS | **Regressões v1.62:** 19/19 PASS

Este documento registra o que foi implementado no ciclo v1.62, o que falta implementar,
e o estado atual do sistema. Cada item implementado tem evidência executável (teste ou
comando reproduzível) — nada aqui é declarado sem verificação.

---

## 1. Contexto: a auditoria que originou este ciclo

A auditoria empírica de 2026-07-21 (experimentos reais sobre a v1.61 instalada, não
simulações) provou **uma causa raiz sob três sintomas** — vocabulário de reconhecimento
esparso na camada taxonomy/competence_matrix:

| Sintoma medido (v1.61) | Evidência |
|---|---|
| Tarefas frontend/web classificavam `domain=None` | `taxonomy.classify("criar landing page com glassmorphism")` → None |
| Paráfrases do mesmo problema perdiam o cache por 0.03–0.04 | prior 0.56–0.59 vs threshold 0.6; reconhecimento 3/7 |
| Threshold não podia baixar: piso cosine ~0.5 para qualquer texto | "bolo de cenoura" → prior 0.55 contra skill de RK4 (5/5 falsos positivos @0.5) |
| `UNKNOWN_CLASS` → DEEP indiscriminado | "corrigir typo no README" → DEEP (~8k tokens) |

As análises externas (2× Manus, 1× GPT) foram trianguladas: os relatórios do Manus eram
**simulações roleplay** (fórmulas declaradas no próprio texto) e suas recomendações em
maioria já existiam no código; da análise do GPT foi aproveitado o conceito do
**barramento único de eventos** (implementado neste ciclo como `event_bus`).

---

## 2. IMPLEMENTADO neste ciclo (v1.62)

### 2.1 Organização do repositório
- **README.md reescrito** — `apex-method/` como fonte canônica; estrutura com status
  (ativo/biblioteca/legado); README antigo preservado em `docs/README_legacy_v00.39.md`.
- **Relatórios soltos movidos** da raiz para `docs/reports/` (6 arquivos v1.60.0).
- **`algorithms/THIRD_PARTY.md`** — manifesto dos 42 repositórios de terceiros
  vendorizados (~390 MB), com origem provável de cada um.
- **INDEX.md regenerado** — `tools/generate_index.py` agora lê a versão do
  `apex-method/SKILL.md` (fonte única) em vez de constante hardcoded (estava v00.36.0).

### 2.2 Padronização da biblioteca de skills (3.784 skills)
- **`tools/skill_standardizer.py`** (novo) — varredura + reparo cirúrgico de frontmatter.
- Diagnóstico: 1.261 skills não-conformes — 129 descrições **destruídas na importação**
  (block-scalar YAML virou literal `"Use — >"`), 1.069 curtas demais, 63 sem descrição,
  60 sem nome. Skill sem descrição real é **invisível para o router/gravity**.
- Reparo aplicado: **1.174 descrições reais recuperadas do corpo** das skills + 60 nomes.
- Conformidade: **2.523 → 3.690 OK (97,5%)**. Relatório determinístico em
  `tools/skill_standardizer_report.json`.

### 2.3 Taxonomy enriquecida (a correção da causa raiz)
- **`apex-method/catalog/taxonomy_extra_seed.json`** (novo, ~390 termos) — gerado por
  **`tools/mine_taxonomy_vocab.py`** (novo) a partir de duas fontes:
  - **Curado PT+EN** para os gaps provados: frontend/web (landing, glassmorphism, css3,
    animação…), docs, devops, mathematics (rk4, oscilador…), intents `fix_small`
    (typo, ajustar, corrigir…) e `explain`, verbos incrementais em `build`.
  - **Minerado do scorecard OpenClaw** (arquivo fornecido pelo usuário): vocabulário de
    agent-infra, automation, observability, devops — com filtros anti-ruído
    (frequência ≥2 na surface, document-frequency ≤2 no corpus, filtro morfológico
    -ed/-ly/-ing, denylist final).
- `taxonomy.py` mescla o seed nas tabelas-base em import-time (determinístico,
  fallback silencioso — sem o seed, comportamento v1.61 intacto).
- Novos subdomínios: `agent-infra`, `automation`, `observability`, `devops`, `docs`.
- **Medido:** landing page PT/EN → `software/frontend/web` ✓; typo → `software/docs/
  fix_small` ✓; controle negativo (bolo de cenoura) → tudo None ✓ (sem chute).

### 2.4 Cache de resolução híbrido (recall + facet gate)
- `orchestrator.resolution_check` ganhou **Tier 2**: banda `0.5 ≤ prior < 0.6` aceita
  SOMENTE com concordância de facets contra o problema lembrado (mesmo domain não-None
  + `facet_score ≥ 0.5`). `skill_ledger.worked_for` agora carrega o texto do problema
  do melhor hit para viabilizar a comparação.
- **Medido:** reconhecimento de paráfrases **3/7 → 7/7**, falsos positivos **0/5**
  (obrigatório). Hit carrega `tier: prior|facet` + `reverify_required: True` (a
  re-verificação continua obrigatória — reuso nunca é confiança cega).

### 2.5 Triage taxonomy-informed (fim do DEEP indiscriminado)
- `execution_policy.triage`: quando o estimador retorna `UNKNOWN_CLASS`, consulta a
  taxonomy ANTES de escalar: edição incremental reconhecida (`fix_small` + domain) →
  STANDARD sem personas; tarefa reconhecida (domain+intent) → STANDARD + 3 personas
  dissect; genuinamente irreconhecível → DEEP (conservador, inalterado).
- **Floors preservados:** audit/security/compliance e `min_mode` continuam vencendo por
  último (testado: "auditoria de segurança" permanece DEEP).
- **Medido:** "corrigir typo no README" DEEP→STANDARD; "ajustar cor do botão"
  DEEP→STANDARD; "2+2" continua EXPRESS skip; irreconhecível continua DEEP.
- Economia estimada: ~6k tokens por tarefa cotidiana que antes caía em DEEP (~8k → ~2k).

### 2.6 Event bus de avaliação contínua (proposta do GPT, unificada)
- **`apex-method/scripts/event_bus.py`** (novo, 56º syscall) — barramento único:
  `emit()` (SQLite, best-effort, nunca levanta exceção), `new_trace()`, `trace()`,
  `evaluate(trace_id)` (o registro de avaliação por execução: latência, cache hit/miss
  + tier, modo, validação, módulos), `recent_traces()`, `export_jsonl()` (exporters
  externos OTEL/LangSmith).
- **`orchestrator.run` auto-instrumenta** cada execução (run_started/triage/cache/mode/
  run_finished + `trace_id` no resultado) — o ciclo de avaliação **não depende de o LLM
  lembrar** de instrumentar (a falha estrutural apontada na auditoria).

### 2.7 Servidor MCP do APEX (a visão "skills como corpo")
- **`integrations/apex-mcp-server/`** (novo) — MCP stdio stdlib-only, 11 tools:
  - Leitura: `apex_classify`, `apex_triage`, `apex_resolution_check`, `apex_recall`,
    `apex_worked_for`, `apex_route`, `apex_learning_best`, `apex_trace_evaluate`.
  - **Mutação com gate H5 na borda**: `apex_equip`, `apex_unequip`,
    `apex_record_outcome` — retornam `BLOCKED` sem `approved: true` explícito.
- Smoke test real (subprocesso stdio): `test_server.py` — **7/7 PASS**, incluindo
  BLOCKED sem aprovação e grant durável com aprovação.
- Instalação: `claude mcp add apex -- python3 .../integrations/apex-mcp-server/server.py`.

### 2.8 Testes
- **`apex-method/tests/test_regressions_v162.py`** (novo) — 19 checks que travam cada
  correção medida (R1 taxonomy, R2 cache híbrido + falso-positivo, R3 triage + floors,
  R4 event bus). **19/19 PASS.**
- **`tests/benchmark.py`: 72/72 PASS** — incluindo o `routine_composer` que falhava:
  o teste assumia que "marketing" nunca teria capability no host; corrigido para
  assertar o invariante real (todo estágio ou é preenchido ou vira gap honesto).
- `docs_current` guard forçou a atualização das contagens (55→56 syscalls) em
  SKILL.md/spec.md + catalogação do `event_bus` em `scripts_lib.json` — o guard
  funcionou como projetado.

---

## 2.9 Ciclo de debug adversarial (QA+Dev+TechLead, 2026-07-21)

Loop quebrar→corrigir→validar→repetir contra o kernel v1.62. 3 rounds de ataque
(inputs hostis, memória/persistência/spawn, loop paramétrico multi-disciplina).
**4 bugs reais encontrados e corrigidos**, 1 regressão introduzida por correção e
imediatamente pega pelo benchmark e corrigida:

| # | Bug | Causa | Correção | Trava |
|---|---|---|---|---|
| B1 | `taxonomy.classify(42)` → AttributeError | `_tokens` fazia `(text or "").lower()`, mas `42 or ""` = 42 | coerção defensiva a str | R5 |
| B2 | event bus emitia `gate=None` sempre | emit lia `.get("status")`; o gate retorna `pass`/`action` | emite `gate_pass`/`gate_action` | R5 |
| B3 | "sistema de EDOs com RK4" → software | vocabulário math só no subdomain; "sistema" vencia o eixo domain | termos numéricos elevados ao eixo DOMAIN (+ dedup de chave dupla no seed) | R5 |
| B4 | resolução de agente retornava `[]` para TODA tarefa em português | `match_task_to_ext_agents` era lexical-only (TF-IDF), a fraqueza cross-language que a própria §12 documenta | fallback char-n-gram (`semantic_rank`) com piso de confiança 0.10 | R5 |
| REG | correção de B4 surfou persona errada (startup_cto @0.053 para eng. estrutural) | fallback sem piso violava §10 (hit de baixa confiança) | piso 0.10 → abaixo disso `[]` e o lifecycle sintetiza o especialista | benchmark agent_lifecycle |

**Resultados medidos no loop (o que o Manus simulou, feito de verdade):**
- Reconhecimento de domínio: **6/6** (era 5/6 antes de B3).
- Cache hit em variação paramétrica (mesmo problema, só mudando dt/steps/tolerância):
  **5/5 = 100%** com o cache híbrido — o relatório do Manus alegava degradação a 7%.
- `orchestrator.run` resistiu a 10 inputs hostis (None/int/dict/gigante/unicode/injeção)
  sem levantar exceção (contrato ERROR_DEGRADED).
- Ledger SHA-256 **detectou adulteração direta no SQLite** (`content hash mismatch`).
- Promoção/demoção (beta-binomial), spawn contract (recusa nome pelado) e page_out
  resistiram.

**Achado honesto (não é bug):** o roster de 213 agentes é majoritariamente EN e
enviesado a software/tech. Engenharia estrutural, jurídico e matemática pura **não têm
persona forte** — corretamente caem no caminho de síntese (`agent_lifecycle` fabrica o
especialista). O piso de confiança agora garante que o kernel prefira sintetizar o
especialista certo a surfar um agente errado.

Regressões permanentes: `tests/test_regressions_v162.py` passou de 19 → **28 checks**.

## 2.10 Ciclo v1.63 — corpus, tradução, cobertura e base compartilhada (2026-07-21)

Continuação do loop QA+Dev+TechLead, agora com os dados alimentando taxonomy/gravity/MCP.

**Enriquecimento da taxonomy pela "memória" real (corpus).** O swap efêmero da sessão anterior
morreu com o container; a memória durável de verdade é o corpus rotulado. `mine_corpus_taxonomy.py`
(novo) minera vocabulário de **3.784 skills (category+desc+triggers) + 213 agentes (domains)**,
com fold de acento (NFKD) e filtros anti-ruído (DF entre facets, morfologia, denylist) →
`catalog/taxonomy_corpus_seed.json` (~520 termos). Precisão de classificação: **10/10** em 8
domínios + 2 controles negativos. Novos domínios reconhecidos: healthcare (FHIR/clínico),
marketing (campanha/leads).

**Translate-before-dissect (pedido do autor, baixo custo/alto ROI).** `translation.py` (novo):
gloss PT→EN determinístico e offline (stdlib), idempotente para inglês, aplicado ANTES de
classificar/rotear. Wired em `dissect` (aditivo) e em `match_task_to_ext_agents`. Fecha a fraqueza
cross-language que a §12 documentava.

**Coverage sweep — "um problema por skill", feito honestamente.** Spawnar 3.784 subagentes LLM é
inviável; `coverage_sweep.py` (novo) exercita o CAMINHO de roteamento determinístico para CADA
skill (problema-proxy da descrição) e mede reachability, órfãs e distribuição por disciplina.

| Métrica | Antes | Depois |
|---|---|---|
| Reconhecimento de domínio (3.784 skills) | 67,3% | **88,4%** |
| Skills órfãs (invisíveis ao roteamento) | 1.236 | **437** |

Causa raiz das órfãs: o índice `apex_native_skills_index.json` estava **stale** — ainda com as
descrições destruídas na importação, embora o skill_standardizer já as tivesse corrigido nos
SKILL.md. `refresh_skills_index.py` (novo) re-sincroniza do SKILL.md e sintetiza descrição
roteável de labels reais (id+category+anchors) quando o SKILL.md também é lixo (~900 skills, 24%,
têm banner de versão no lugar de descrição — problema de qualidade de dados honesto).

**MCP como base de conhecimento compartilhada.** `knowledge_base.py` (novo) + 6 tools MCP novas
(`apex_kb_summary/popularity/ranking/agent_status/vaccines/load_state`). Distinção honesta:
**popularidade = cobertura real medida**; **ranking de sucesso = learning (beta-binomial), cresce
com runs validados**. `catalog/knowledge_base_seed.json` é a base que viaja no repo;
`load_state()` hidrata uma instância nova com os estados de sucesso herdados (gate H5 no MCP).

**Bug novo corrigido (B5).** `orchestrator.dissect` mapeava `software→engineering` mas a taxonomy
retorna `domain="engineering"` (v1.56) para tarefas estruturais — "engineering" faltava em
`_FACET2DISC`, então caíam no fallback semântico e viravam "legal". Corrigido + keywords de
security (pentest/sast/owasp) adicionadas. Travado em R6.

MCP: 11 → **17 tools** (7→10 smoke checks). Regressões: 28 → **40 checks**. Benchmark **72/72**.
Syscalls: 56 → **58** (translation, knowledge_base).

## 3. FALTA IMPLEMENTAR (backlog priorizado)

| # | Item | Por quê | Esforço |
|---|---|---|---|
| 1 | **Reescrever SKILL.md em formato enxuto** (~150 linhas: quickstart imperativo nas primeiras 20, glossário H5/PMI/MCFE/SR_*, 1 exemplo mínimo, resto delegado a `references/`) | Hoje: 736 linhas ≈ 15k tokens injetados por ativação; causa comprovada de uso superficial/encenado da skill por agentes | médio |
| 2 | **Decisão sobre `algorithms/` (~390 MB)** — migrar para submodules ou remover do working tree (manifesto já existe) | Clone de 550 MB; terceiros misturados com código próprio | baixo (decisão do dono) |
| 3 | **Remover binários commitados** — `Full Bundle/apex_FULL.part_*`, `apex-method-v1.61.0.skill` na raiz | Higiene; histórico já preserva | baixo (decisão do dono) |
| 4 | **Consolidação N→1 do Knowledge Compiler** — `agent_materializer` cristaliza 1 experiência; falta compilar N experiências do mesmo domínio numa skill densa | Reduz tokens de contexto; completa a ideia do GPT | médio |
| 5 | **Emissões do event_bus nos demais módulos** (gravity, verify, uco_gate, agent_spawn, learning → promotion/demotion) | Hoje só o orchestrator emite; o vocabulário de actions já prevê promotion/demotion/validation | baixo |
| 6 | **Pipeline/Cost optimizer data-driven** — usar `evaluate()` acumulado para EV/token por modo e "pular fase inútil por domínio" | Requer volume de traces reais (agora coletáveis) | alto |
| 7 | **Adoção do modelo de maturidade M0–M5 do OpenClaw** para skills/agentes (mapear CANDIDATE/ADOPTED/PROVEN → M1/M2/M4 com promotion_bar explícito) | Governança mais legível; conceito minerado do scorecard | baixo |
| 8 | **94 descrições ainda curtas** na biblioteca (de 1.261 originais) — colheita do corpo produziu <40 chars | Cauda longa; revisar manualmente ou com LLM | baixo |
| 9 | **Publicar o MCP server** no marketplace/registry MCP + testar com cliente real de ponta a ponta | Alcance da visão "equipar/desequipar de fora" | médio |

## 4. Decisões pendentes do dono do repositório

1. `algorithms/`: submodules, remoção, ou manter como está? (item 3.2)
2. `Full Bundle/` e `.skill` na raiz: remover? (item 3.3)
3. SKILL.md enxuto: aprovar a reescrita? (item 3.1 — maior ROI individual restante)

---

## 5. Estado atual (verificável)

```
apex-method v1.62.0
├── benchmark:            72/72 PASS   (python3 tests/benchmark.py)
├── regressões v1.62:     19/19 PASS   (python3 tests/test_regressions_v162.py)
├── MCP smoke:            7/7 PASS     (python3 integrations/apex-mcp-server/test_server.py)
├── syscalls:             56 (novo: event_bus)
├── taxonomy:             base + seed de ~390 termos (catalog/taxonomy_extra_seed.json)
├── cache de resolução:   híbrido 2-tier (prior 0.6 | facet-gate 0.5–0.6), 7/7 / 0 FP
├── triage:               taxonomy-informed; floors audit/security intactos
└── biblioteca de skills: 3.784 skills, 97,5% conformes (era 66,7%)
```

Métricas medidas antes → depois (mesmos cenários de teste, `test_regressions_v162.py`):

| Métrica | v1.61 | v1.62 |
|---|---|---|
| Reconhecimento de paráfrase no cache | 3/7 | **7/7** |
| Falsos positivos no cache | 0/5 (@0.6) | **0/5** (mantido com banda 0.5) |
| Classificação frontend PT/EN | domain=None | **software/frontend/web** |
| "corrigir typo no README" | DEEP (~8k tk) | **STANDARD** (~2k tk) |
| Skills com frontmatter válido | 66,7% | **97,5%** |
| Benchmark | 71/72 | **72/72** |
| Avaliação por execução | dependia do LLM chamar finalize | **automática (event_bus)** |
```
