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

---

*Inventário produzido após execução e debug completos de todos os módulos. Pronto para a fase de correção (aguardando aprovação para implementar, começando por C-07 → C-01/C-04).*
