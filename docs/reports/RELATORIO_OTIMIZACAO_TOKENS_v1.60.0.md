# 🔧 Análise de Otimização de Tokens — Cache de Resolução + DSM do Pipeline

> Análise **fundamentada em dados reais** (DSM executado, `mode_flow`, contagens do próprio kernel). Responde às duas hipóteses levantadas: (1) a auto-evolução + cache de resolução economiza tokens nos modos caros? (2) um DSM do pipeline achando loops e reposicionando validações economizaria tokens? **Resposta curta: SIM para as duas — e dá para quantificar.**

---

## 1. O que já existe (medido)

- **Auto-evolução cria a solução cristalizada.** `agent_lifecycle.finalize` (só em sucesso VALIDADO): grava learning (promove), persiste grants, **cria um nó RAG** (`rag_index.sync` re-vetoriza só o que mudou), deixa âncora de memória e **materializa** um agente genérico validado num especialista padronizado descobrível. Tudo viaja no swap.
- **A memória de escolhas** (`skill_ledger`, tier PROVEN) já responde "para este problema, a skill que funcionou foi X" e recupera entre sessões.
- **DSM do pipeline já existe** (`pipeline_dsm.module_dsm`): **55 módulos, 6 níveis, 4 ciclos, load-bearing = learning/memory/_tfidf**.

**O que FALTA (a oportunidade):** o orquestrador **não consome** essa solução cristalizada como atalho. O curto-circuito do pipeline só dispara para entrada **trivial** (EXPRESS). Um problema **DEEP/SCIENTIFIC já resolvido re-roda os 13 passos** — `mode_flow` confirma `SCIENTIFIC: skipped=[], savings_vs_naive=0`.

---

## 2. Hipótese 1 — Cache de resolução (auto-evolução) nos modos caros

**O mecanismo proposto (o que você descreveu):** para um problema já resolvido, o agente é ESSE, as skills são ESSAS, os diffs/scripts são ESSES, as validações são ESSAS → vai **direto para a solução** sem re-raciocinar todo o contexto.

**Por que economiza (o pipeline caro é fan-out de raciocínio do LLM):** o custo dos modos altos não está no runtime Python (2–380 ms), está nos **tokens de raciocínio/geração** do LLM ao longo de DISSECT → RESOLVE_SPECIALISTS → PMI_CONVERGE → SPAWN_AGENTS → RUN_STANCES → BARRIER_MERGE. Um **hit de cache de resolução** pula justamente esses passos.

**Modelo de tokens (usando os budgets declarados do próprio kernel):**

| Cenário | Caminho | Tokens (est.) |
|---|---|---|
| SCIENTIFIC "frio" (1ª vez) | 13 passos completos | **~12.000** |
| SCIENTIFIC "quente" (cache-hit) | recall da solução (~200) + **re-verificação determinística** (~800) + resposta (~1.000) | **~2.000** |

- **Economia por repetição: ~83%** (12.000 → 2.000).
- **Compondo em várias rodadas** do mesmo problema-classe (seu ponto de "várias rodadas de execução"):

| Rodadas | Sem cache | Com cache de resolução | Economia |
|---:|---:|---:|---:|
| 5 | 60.000 | 12.000 + 4×2.000 = 20.000 | **67%** |
| 10 | 120.000 | 12.000 + 9×2.000 = 30.000 | **75%** |
| 20 | 240.000 | 12.000 + 19×2.000 = 50.000 | **79%** |

**A segurança não é perdida:** o hit **ainda re-verifica** (determinístico, barato) — a solução cristalizada é reaplicada e revalidada, não "confiada cega". Se a re-verificação falhar (problema mudou), cai para o pipeline completo. É exatamente o EXPRESS já faz para aritmética, estendido para **classes de problema com solução validada + alta confiabilidade (R_acum)**.

> **Conclusão H1: SIM.** É o maior alavancador. A infraestrutura para CRIAR o cache já existe (finalize/RAG/skill_ledger); falta o **atalho de CONSUMO** no `orchestrator` (um "resolution-cache gate" no triage, ao lado do EXPRESS).

---

## 3. Hipótese 2 — DSM do pipeline: loops, gaps e reposicionamento de validações

**Os 4 ciclos (DSM real):** `agent_spawn↔orchestrator`, `capability_map↔rag_index`, `execution_policy↔orchestrator`, `pipeline_dsm↔token_tracker`. **São ciclos de IMPORT (lazy)** — quebrados por import tardio em runtime (`_cycles` os rotula como "coupling smell"). **Não são loops de execução que gastam tokens** — são dívida de acoplamento (baixa prioridade, afeta manutenção, não custo).

**Onde o token REALMENTE vaza no pipeline caro (as validações que se repetem):**

1. **Validações não são memoizadas.** `pot.run_step` calcula `code_hash` (SHA-256 do código) mas **não o usa como chave de cache** — código idêntico **re-executa** a cada rodada; `uco_gate`/`verify` idem. Numa sessão iterativa (refina → re-valida), o MESMO trecho passa pelo gate várias vezes. **Memoizar por `code_hash`** devolve o resultado sem recomputar E sem os tokens de interpretar a saída repetida.
   - *Estimativa:* ~15–30% dos tokens de validação/computação numa sessão iterativa.

2. **Validação tardia / no momento exato (seu "caminho crítico / corrente crítica").** Hoje VERIFY/PMI/BARRIER rodam **sempre e cedo**. Duas otimizações no espírito de corrente crítica:
   - **`verification_gate` já roteia "só o arriscado"** (P≠NP: verificar só hipóteses de alto risco) — mas é chamado a cada rodada. Aplicá-lo como **filtro antes** do VERIFY evita verificar o que é barato-de-checar-depois.
   - **Poda geodésica (early-exit).** O `geodesic_scheduler` **ordena** passos por ΔH/token mas **não poda**. O triage já tem gates de R_acum para ESCALAR; o simétrico — **de-escalar / abortar cedo quando a confiabilidade já convergiu** — cortaria o fan-out restante (SPAWN/RUN_STANCES/BARRIER).
     - *Estimativa:* o fan-out é ~metade do budget nos modos altos (~6.000 tk em SCIENTIFIC); convergir em ~60% dos stances poupa **~2.400 tk/rodada**.

3. **Paralelizar validações independentes.** O Level A já roda PoT em subprocessos paralelos; estender ao DSM: validações sem dependência mútua (ex.: verify de identidade × uco_gate de código) rodam no mesmo batch em vez de sequencial — ganho de **tempo** (não de token diretamente, mas reduz o risco de re-raciocínio por latência).

> **Conclusão H2: SIM, parcialmente.** Os ciclos em si não gastam tokens (são de import). Mas o **DSM aponta o alvo certo**: as **validações repetidas** (não memoizadas) e a **ausência de poda** no fan-out caro. Memoização por hash + early-exit por convergência = economia real, sem afrouxar o rigor.

---

## 4. O trade-off que você identificou (e ele é real)

O pipeline rígido **obriga o LLM a validar tudo** → evita alucinação e resposta genérica. Isso é o **valor** do APEX e não deve ser removido. A tese correta é: **manter as validações, mas fazê-las no momento exato e uma única vez por conteúdo idêntico** — como caminho crítico/corrente crítica numa obra: não se remove a inspeção, remove-se a inspeção **redundante** e coloca-se cada uma no ponto onde ela **libera** a próxima etapa.

- **Não afrouxa:** um cache-hit ainda re-verifica; a memoização só pula o que é **byte-idêntico** (mesmo `code_hash` = mesmo resultado determinístico, por definição); a poda só corta quando R_acum **já** cruzou o alvo.
- **Economiza:** 67–79% em problemas recorrentes (cache de resolução) + 15–30% em validações repetidas + ~20% no fan-out convergente.

---

## 5. Recomendação priorizada (implementável, sem quebrar o rigor)

| # | Otimização | Onde | Economia est. | Risco |
|---|---|---|---|---|
| 1 | **Resolution-cache gate** no triage (hit em problema-classe validado + R_acum alto → recall + re-verify, pula o fan-out) | `orchestrator` + `skill_ledger` (já tem a base) | **67–79%** em recorrentes | Baixo (re-verifica) |
| 2 | **Memoização de validação por `code_hash`** (PoT/uco_gate/verify) | `pot`/`uco_gate`/`verify` | 15–30% em iterativas | Muito baixo (determinístico) |
| 3 | **Poda geodésica / early-exit** por convergência de R_acum | `geodesic_scheduler` + `execution_policy` | ~20% no fan-out | Médio (calibrar o limiar) |
| 4 | Quebrar os 4 ciclos de import (higiene) | módulos acoplados | 0 tokens (manutenção) | Baixo |

**Ordem sugerida:** #2 (mais seguro, memoização determinística) → #1 (maior alavancador) → #3 (precisa calibração) → #4 (higiene).

---

## 6. Conclusão

Suas duas intuições estão **corretas e são quantificáveis**. O APEX já **constrói** o conhecimento cristalizado (auto-evolução: nós RAG, agentes promovidos, memória de escolhas) — o que falta é **consumi-lo como atalho** e **não repetir validações idênticas**. Isso não enfraquece o pipeline rígido (que é o antídoto contra alucinação): mantém todas as validações, mas as executa **no momento exato e uma vez por conteúdo**, exatamente como corrente crítica numa obra. Ganho modelado: **67–79% em problemas recorrentes**, **15–30% em validações repetidas**. Recomendo começar pela **memoização por hash** (risco ~zero) e pelo **resolution-cache gate** (maior retorno).

*Análise a partir do DSM real, `mode_flow` e das contagens do próprio kernel. Números de token são modelados sobre os budgets declarados pelo APEX (o ambiente stdlib não mede tokens do LLM diretamente).*
