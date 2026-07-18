# Validação da auditoria GPT (v1.40.0) contra o código atual — e a resposta v1.43.0

**Método:** a própria suíte adversarial do GPT (`apex_runtime_autopsy_tests.py`, 27 testes)
foi adaptada (paths + isolamento `APEX_METHOD_HOME`) e executada contra o código atual.
Nada foi aceito da prosa do relatório sem reprodução.

## 1. Veredito da validação

A auditoria do GPT é **tecnicamente correta para a v1.40.0** — mas estava **defasada**: foi
feita sobre um zip antigo. Contra a **v1.42.0**:

| Rodada | Resultado |
|---|---|
| GPT sobre v1.40.0 | 12/27 PASS |
| Mesma suíte sobre v1.42.0 | **22/27 PASS** |
| Mesma suíte sobre v1.43.0 (esta rodada) | **24/27 PASS** |

Dois testes do GPT **crasharam** contra a v1.42 porque a defesa agora age ANTES do ponto que
o teste esperava observar (prova de correção, não de falha):
- bundle adulterado → rejeitado antes de criar o banco (o teste assumia a tabela criada);
- arquivo acima do limite → `ValueError` imediato (o teste assumia truncamento silencioso).

## 2. Classificação item a item

**Já corrigidos na v1.41/v1.42 (obsoletos na auditoria):** RT-05 (ledger recalcula hash),
RT-07 (bundle fail-closed), RT-08 (hash cobre todo o payload), RT-10 (path relativo),
RT-11 (`evaluate` bloqueia import fora da allowlist), RT-12 (injection-scan do corpo),
RT-13 (scripts referenciados descobertos e escaneados), RT-14 (truncado recusado),
RT-15 (shape de API degrada), RT-23 (piso de modo; default não rebaixa SCIENTIFIC).

**Corrigidos nesta rodada (v1.43.0):**
- **RT-09b** — o default já era único (microssegundos), mas `ts` EXPLÍCITO idêntico ainda
  sobrescrevia (`swap_store.write_versioned`). Agora colisão estende o ts com sufixo de
  microssegundos: nenhuma gravação sobrescreve outra. Regressão no `t_swap_store`.
- **RT-26b** — persistência de grants era opt-in (`persist=True`); pelo design do autor
  (a memória guarda a configuração do agente), agora é **default**, `agent_registry.load()`
  faz auto-merge e `revoke_grant()`/`unequip()` desequipam durávelmente. Regressão no
  `t_runtime_autopsy`.

**Transformados em arquitetura (decisão do autor — não eram "by design" aceitáveis):**
- **RT-22** → `orchestrator.run` devolve **kernel checklist booleano** (passos code
  executados com evidência; passos llm com a chamada exata em `llm_actions`) e
  `gate()`/`complete_step()`: a execução só é COMPLETE com todos os passos `True`; caso
  contrário RETURN_TO_LLM nomeando o que falta. O SKILL.md torna o gate mandatório.
  Teste: `t_kernel_gate`.
- **RT-19/RT-27** → novo `agent_spawn`: o roster continua enxuto (design), mas o spawn monta
  o **agente totalmente executável** — persona REAL (AGENT.md), skills/diffs/scripts REAIS
  atraídos pelo grafo, grants duráveis (equipar/desequipar), histórico validado (learning),
  governança regional e template de saída, com checklist booleano de spawn
  (`spawn_ready=False` ⇒ não spawna) e `spawn_contract()` (a diretriz de como rodar).
  O manifesto Level-B (`concurrent_executor.subagent_manifest`) agora carrega a spec
  completa por entrada. Testes: `t_agent_spawn` + integração no manifesto.

**Permanecem "FAIL" no harness do GPT por limite de plataforma (declarado, não escondido):**
os 3 testes restantes exigem que o PACOTE PYTHON execute agentes LLM (`results` dentro do
manifesto, laudos dentro de `run()`, prompts dentro dos 213 registros). Um `.py` não
instancia um LLM — a fronteira agora é um **contrato executável verificado por teste**:
o host spawna a partir da spec; o gate impede o LLM de fingir que executou.

## 3. Novas capacidades pedidas pelo autor (entregues nesta rodada)

| Entrega | Arquivo(s) | O que faz |
|---|---|---|
| **JSON de roteamento gravitacional** | `scripts/attraction_graph.py` + `catalog/attraction_graph.json` | 320 nós (skills/scripts/diffs/agentes), ~2.000 arestas com pesos; `expand()` = atração em cadeia (busca a 1ª competência, o resto se atrai); `equip_for(need)`; `rebuild()` a cada inclusão. Exemplo validado: "tech leader precisa fazer auditoria de código" → tech-lead-orchestrator → security/testing/QA → python → api/backend. |
| **Contrato de spawn** | `scripts/agent_spawn.py` | spec executável + equip/unequip durável + `spawn_contract()` |
| **Checklist do kernel** | `orchestrator.KERNEL_STEPS/new_checklist/complete_step/gate` | passagem de bastão código↔LLM com gate booleano |
| **spec.md** | `spec.md` | o que é, objetivo, premissas, arquitetura, o que cada módulo faz/entrega/para quem, comportamentos esperados, roadmap |
| **RAG vetorial por nós** | `scripts/rag_index.py` + `catalog/rag_index.json` | 94 nós, IDF global char-n-gram, `search()` PT/EN mapeia qualquer pergunta ao módulo/área certa em ms |

## 4. Estado final (tudo re-executado)

```
tests/benchmark.py   50/50 PASS   (4 testes novos: attraction_graph, agent_spawn, kernel_gate, rag_index)
tests/evaluate.py    13/13 = 100%
tests/scenario.py    7/7 CLEAN, exit 0
suíte GPT (adaptada) 24/27  (3 restantes = execução de LLM dentro de .py — coberto por contrato+gate)
```

Correção colateral encontrada ao integrar: `learning._con()` agora recria o schema por
conexão — um `.db` deletado no meio da sessão não derruba mais `score()`/`best()`.
