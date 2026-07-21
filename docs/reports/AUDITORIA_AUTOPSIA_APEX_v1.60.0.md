# 🔬 Auditoria Forense (Autópsia) — `apex-method` v1.60.0

> **Escopo:** arquivo `apexmethodv1.60.0.zip` (bundle da skill APEX Method).
> **Data:** 2026-07-20
> **Metodologia:** revisão estilo equipe de QA (Tech Lead + Devs + QA + Segurança): inventário → leitura de documentação → varredura estática de segurança → execução/validação de todos os módulos → prova de conceito (PoC) de vulnerabilidades → análise de dead code, dependências e otimizações.
> **Veredito global:** 🟢 **Código maduro e defensivo.** 68/68 testes passam. Há uma trilha de auditoria real embutida (marcadores `SEC-00x`, `RT-xx`, `AUD-xxx`). Restam **falhas residuais concretas** — a mais séria é um *path traversal* comprovado por PoC — além de oportunidades de robustez e limpeza.

---

## 1. Inventário do artefato

| Métrica | Valor |
|---|---|
| Arquivos totais | 105 |
| Scripts Python | 54 (`~18.141` LOC) |
| Documentação Markdown | 29 |
| Catálogos JSON | 20 |
| YAML / TXT | 1 / 1 |
| Maior módulo | `scripts/universal_code_optimizer_v4.py` (4.266 LOC, 188 KB) |
| Maiores catálogos | `rag_index.json` (1,2 MB), `apex_native_skills_index.json` (1,0 MB) |

**Natureza do projeto:** a skill é um "runtime cognitivo" — um pipeline de raciocínio *token-aware* com ferramentas executáveis reais (Program-of-Thought, RK4/Euler, gate de código UCO, Bayes, gravity, guards, DAG). O ponto crítico de segurança é que ela **executa código Python** (gerado por LLM em `pot.py`) e **importa artefatos externos** (skills via `skill_scout`, bundles via `swap_store`/`federation`).

---

## 2. Validação / execução dos módulos (QA dinâmico)

Ambiente: **Python 3.11.15**. Todos os 54 `.py` compilam sem erro (`py_compile` limpo).

Suíte oficial executada — `tests/benchmark.py`:

```
TOTAL   68/68   41.172,2 ms   (EXIT 0)
```

Amostra dos módulos exercitados com sucesso: `pmi_monte_carlo`, `code_genetics_sqlite`, `snapshot_wire`, `menu` (update=OK), `deep_research`, `concurrent_executor`, `memory` (KG + grafo acíclico), `swap_store` (round-trip + integridade de bundle), `execution_policy` (HARD-RULE de roteamento), `federation` (HMAC + fusão de cadeias), `catalog_determinism` (4 catálogos byte-idênticos entre rebuilds).

**Conclusão do QA dinâmico:** nenhum módulo quebrou; degradação graciosa confirmada (roda em stdlib puro sem numpy/scipy). A cobertura é ampla e determinística.

---

## 3. Achados de segurança

> Formato de cada achado: **O que · Como foi achado · Impacto · Arquivo:linha · Correção · Severidade.**

### 🔴 SEC-A · Path traversal em `make_filename` / `write_versioned` (COMPROVADO por PoC)

- **O que:** o nome lógico (`name`) é interpolado direto no nome de arquivo, sem sanitizar separadores de caminho nem `..`. Um `name` malicioso escapa do diretório-alvo.
- **Como achei:** leitura de `make_filename` → `write_versioned` → rastreamento até o restaurador `import_bundle`, seguido de **PoC executado**:
  ```python
  swap_store.make_filename('../../../../tmp/PWNED')
  # -> '../../../../tmp/PWNED-User-20260720035038-R00.json'
  # os.path.join('/home/user/.apex-method/APEX/user', fn)
  # normpath -> /home/tmp/PWNED-...json   ← ESCAPOU do diretório
  ```
- **Impacto:** escrita de arquivo arbitrária fora do diretório de swap. Vetor de entrada real: `import_bundle` itera `bundle["stores"]["user"].items()` e passa a **chave controlada pelo atacante** como `name` para `write_versioned`. Combinado com o SEC-B (integridade não autenticada), um bundle forjado pode gravar arquivos em caminhos escolhidos (ex.: sobrescrever configs, plantar arquivos em locais de autoload). Mitigado apenas pelo gate humano H5 da federação.
- **Onde:**
  - `scripts/swap_store.py:108` — `return f"{name}-{function}-{ts}-R{int(rev):02d}.{ext}"` (sem sanitização)
  - `scripts/swap_store.py:158` e `:167` — `path = os.path.join(folder, fn)` (sem `_resolved_within`)
  - `scripts/swap_store.py:550` — `for name, content in bundle["stores"]["user"].items(): write_versioned(udir, name, ...)` (fonte não confiável)
- **Correção:** sanitizar `name` no `make_filename` (rejeitar `os.sep`, `/`, `\`, `..`; aplicar `os.path.basename` + allowlist de caracteres `[A-Za-z0-9_.-]`) **e** validar o caminho final com um guard `_resolved_within(folder, fn)` antes de abrir — exatamente o padrão que `repo_bridge.py:69/87` já usa (`SEC-005`). A defesa já existe no projeto; falta aplicá-la aqui.
- **Severidade:** 🔴 **Média-Alta** (escrita arbitrária; gated por H5).

### 🟠 SEC-B · Integridade de bundle sem autenticação (SHA-256 puro)

- **O que:** `import_bundle` afirma no docstring "verify integrity … FAIL CLOSED", mas a verificação é `_bundle_sha(bundle) == bundle["sha256"]` — um **checksum**, não uma assinatura. Quem cria um bundle malicioso simplesmente recalcula o SHA-256 e o gate marca `integrity_ok=True`.
- **Como achei:** leitura de `import_bundle` e comparação com o mecanismo HMAC (opcional) da `federation.py`.
- **Impacto:** protege contra corrupção acidental, **não** contra adulteração intencional. É o pré-requisito que torna o SEC-A explorável por um bundle forjado.
- **Onde:** `scripts/swap_store.py:520` — `ok = (bundle.get("sha256") is not None and _bundle_sha(bundle) == bundle["sha256"])`.
- **Correção:** exigir HMAC/assinatura (reutilizar `APEX_FED_KEY` da federação) para bundles de origem não confiável; e ajustar o docstring para "detecção de corrupção", não "anti-tamper". SHA-256 sozinho nunca é anti-tamper.
- **Severidade:** 🟠 **Média.**

### 🟠 SEC-C · HMAC da federação desligado por padrão

- **O que:** `_fed_key()` retorna `""` quando `APEX_FED_KEY` não está definido; como o código só assina/verifica sob `if _fed_key():`, a importação de pacotes federados por padrão **não é autenticada** (apenas SHA-256).
- **Como achei:** `grep` por `hmac`/`_fed_key` + leitura das linhas de assinatura/verificação.
- **Impacto:** troca de estado entre dispositivos confia em conteúdo não autenticado; a única barreira real vira o gate humano H5.
- **Onde:** `scripts/federation.py:60-61` (`return os.environ.get("APEX_FED_KEY", "")`), assinatura em `:135-137`, verificação em `:153-155`.
- **Correção:** sinalizar de forma proeminente `UNSIGNED` no prompt de aprovação H5; considerar tornar a assinatura obrigatória para import cross-device.
- **Severidade:** 🟠 **Média** (documentado, mas o default é inseguro).

### 🟡 SEC-D · Bypasses do scanner AST via bibliotecas da própria whitelist

- **O que:** os gates estáticos (`skill_scout.ast_security_scan` e `guards.forge_load_gate`) confiam em libs científicas whitelistadas que possuem seus próprios *sinks* de execução/desserialização — invisíveis para o scanner:
  1. `numpy.load(f, allow_pickle=True)` → `.load` cai só em `REVIEW_ATTRS` e `numpy` está na whitelist ⇒ `safe=True`. **RCE via pickle.**
  2. `pandas.read_pickle(x)` → `.read_pickle` não está em nenhuma lista ⇒ totalmente invisível ⇒ `safe=True`. **RCE.**
  3. `open(p, modo_variável)` → `_write_open_mode` só detecta modo em **constante literal**; um modo em variável escapa da rejeição de escrita em disco.
- **Como achei:** análise das listas `IMPORT_WHITELIST`/`REVIEW_ATTRS`/`DESERIALIZER_RECEIVERS` e da lógica `_write_open_mode`.
- **Impacto:** *defense-in-depth* degradada. **Não** é um furo completo — o próprio código declara "best-effort static gate, NOT a sandbox — human approval is the real boundary". Mas reduz o valor do gate automático.
- **Onde:** `scripts/skill_scout.py:28` (whitelist), `:43-44` (`REVIEW_ATTRS`), `:66-80` (`_write_open_mode`); espelhado em `scripts/guards.py:48`.
- **Correção:** adicionar `read_pickle`, `np.load(allow_pickle=True)`, `joblib.load` aos *sinks* rejeitados; marcar `open()` com modo não-constante como `REVIEW`; expor no H5 o risco residual das libs whitelistadas.
- **Severidade:** 🟡 **Baixa-Média.**

### 🟡 SEC-E · Auto-update executa código *staged* sem varredura prévia

- **O que:** `menu.update(apply=True)` faz `subprocess.run([python, staged/tests/benchmark.py])` **antes** do swap, executando código do clone local staged sem passar pelo `forge_load_gate` nem pela env endurecida do `pot`.
- **Como achei:** leitura completa de `menu.update`.
- **Impacto:** se o clone local for influenciado por atacante, há execução de código durante o "update". Contido porque (a) a fonte é um clone git local do usuário e (b) o fluxo é transacional com rollback — mas não há verificação de segurança/assinatura da árvore staged.
- **Onde:** `scripts/menu.py:90-92`.
- **Correção:** rodar `guards.forge_load_gate` sobre os scripts staged (ou executar o benchmark na env scrubbed do `pot`) antes de confiar no resultado; documentar a suposição de confiança "clone local = confiável".
- **Severidade:** 🟡 **Baixa.**

### ℹ️ SEC-F · `pot.run_step` não é sandbox de segurança (por design, documentado)

- **O que:** executa Python arbitrário via `subprocess.Popen([sys.executable,"-s","-c",code])`. As proteções são env scrubbed (`_ENV_ALLOW`), CWD descartável, cap de saída (`MAX_OUTPUT_BYTES`) e kill de árvore de processos no timeout — **não** isolamento de SO.
- **Onde:** `scripts/pot.py:31-37, 71-124` (o próprio código é explícito: "NOT a security sandbox for hostile code; that still requires an OS-level container").
- **Correção:** manter o `uco_gate` sempre à frente do `run_step` e **nunca** alimentar `run_step` com código externo não vetado. `LD_LIBRARY_PATH`/`PATH` são repassados (necessário, risco baixo). Nenhuma ação obrigatória — é uma limitação assumida.
- **Severidade:** ℹ️ **Informativo.**

### ✅ Verificações de segurança que passaram (maturidade)
- **Sem segredos hardcoded** (varredura por `api_key`/`token`/`sk-`/`ghp_`/`aws_` — nada).
- **Sem `shell=True`, `os.system`, `os.popen`, `mktemp` inseguro, `/tmp` hardcoded.**
- **Sem hashing fraco** (nenhum `md5`/`sha1`).
- **Sem `pickle`/`yaml.load`** em caminho de execução; envelopes usam `json` sobre `gzip+b64` (seguro).
- **SQL 100% parametrizado** (`INSERT OR REPLACE ... VALUES(?,…)`), sem concatenação de string.
- **O único `eval`** (`orchestrator.py:45`) é aritmética com AST estritamente whitelistada (sem `Name`/`Call`/`Attribute`) e cap de expoente — seguro.
- **`repo_bridge.fetch`** é exemplar: guard contra escape por symlink (`SEC-005`), re-checagem do URL final pós-redirect para o prefixo do repo (`SEC-006`), e cap de tamanho lendo 1 byte além do limite (`SEC-007`).
- **Scanner de prompt-injection** no corpo de SKILL.md (`INJECTION_PATTERNS`, RT-12): detecta override de autoridade, exfiltração de segredos, bypass de guardrail, persona de jailbreak.

---

## 4. Comportamento e robustez

### 🟡 BEH-A · Swallow amplo de exceções em caminhos de restauração de estado
- **O que:** 34 arquivos usam `except Exception:` largo. A maioria é degradação graciosa **intencional** e legítima, mas alguns pontos de restauração engolem erros silenciosamente (`except Exception: pass`), mascarando restauração parcial/corrompida.
- **Onde (exemplos):** `scripts/swap_store.py:553-554` (restore do tier `user`), `:560` (marker `resume_due`), blocos de `_restore_stores` (grants/learning/competence).
- **Impacto:** um bundle parcialmente inválido pode ser reportado como sucesso; falhas de I/O somem.
- **Correção:** logar em nível debug em vez de `pass` silencioso nos caminhos de restauração e propagar um sinal de "restauração parcial".
- **Severidade:** 🟡 Baixa.

### ℹ️ BEH-B · Parsing frágil da saída do benchmark no update
- `menu.py:93-95` extrai `TOTAL x/y` por *string matching* do stdout. Uma mudança de formato do benchmark degrada silenciosamente para `0/1` → `REJECTED_STAGED`. **Falha segura** (não aplica update ruim), mas opaca. Sugestão: benchmark emitir um marcador JSON estruturado para o update consumir.

---

## 5. Dead code, duplicação e dependências

- **🟡 DUP-A · `_write_open_mode` duplicado** — cópia idêntica em `scripts/skill_scout.py:66` e `scripts/guards.py:48`. Violação de DRY: corrigir o gap de "modo não-literal" (SEC-D.3) em um e esquecer o outro é provável. **Correção:** extrair para um `_ast_helpers.py` compartilhado.
- **ℹ️ DEAD/PESO · `universal_code_optimizer_v4.py`** (4.266 LOC) é referenciado **apenas** por `uco_gate.py` e pelo `benchmark.py`. Não é dead code, mas é a maior superfície única de manutenção/ataque, carregado via `try/import` opcional. Opcional: modularizar.
- **✅ Dead code real:** não foram encontrados `except:` nus reais (os 3 *hits* do grep são comentários/strings) nem funções obviamente órfãs de nível de módulo relevantes; os `if __name__ == "__main__"` são self-tests úteis.
- **✅ Dependências:** `requirements.txt` está **limpo** — todas as libs são **aceleradores opcionais** (`numpy`, `scipy`, `scikit-learn`, `sympy`) com caminho de degradação para stdlib; `pandas`/`sentence-transformers`/`PyYAML` estão comentadas. **Nenhuma dependência esquecida ou vulnerável.** Ressalva de supply-chain: as versões **não são pinadas** — para um bundle distribuível, considerar *pinning* + hashes para evitar puxar uma release comprometida.

---

## 6. Oportunidades de melhoria e otimização

1. **Consolidar os dois gates AST** (`skill_scout` + `guards`) em um único motor. Hoje há duas listas de whitelist/reject paralelas que **derivam** entre si (risco de correção aplicada só em um lado).
2. **Cache do import do UCO** — `uco_gate.gate()` faz `from universal_code_optimizer_v4 import ...` a cada chamada; cachear o módulo evita reparse repetido de um arquivo de 188 KB.
3. **Sanitização centralizada de nomes de arquivo** — um único `safe_name()` resolveria SEC-A e blindaria todos os *backends* de persistência de uma vez.
4. **Assinatura obrigatória opt-in forte** para bundles/federação, encerrando SEC-B/SEC-C na raiz.
5. **Custo do benchmark** (~41 s): alguns testes dominam (`evaluate_hypotheses` 5,6 s, `solid_state_index` 3,3 s, `agent_spawn` 3,8 s). Marcar como "slow" e permitir uma suíte rápida para CI de PR.

---

## 7. Tabela priorizada de ação

| # | Achado | Severidade | Esforço | Ação |
|---|---|---|---|---|
| SEC-A | Path traversal em `make_filename`/`write_versioned` | 🔴 Média-Alta | Baixo | Sanitizar `name` + `_resolved_within` antes de abrir |
| SEC-B | Integridade de bundle sem autenticação | 🟠 Média | Médio | Exigir HMAC/assinatura; corrigir docstring |
| SEC-C | HMAC de federação off por padrão | 🟠 Média | Baixo | Marcar `UNSIGNED` no H5; assinatura obrigatória cross-device |
| SEC-D | Bypass do scanner via libs whitelistadas | 🟡 Baixa-Média | Baixo | Adicionar `read_pickle`/`np.load(allow_pickle)`/`joblib`; modo `open` não-literal |
| SEC-E | Update executa staged sem scan | 🟡 Baixa | Baixo | `forge_load_gate` sobre a árvore staged |
| BEH-A | Swallow silencioso na restauração | 🟡 Baixa | Baixo | Logar em vez de `pass` |
| DUP-A | `_write_open_mode` duplicado | 🟡 Baixa | Baixo | Extrair helper compartilhado |

---

## 8. Conclusão do Tech Lead

`apex-method` v1.60.0 é um artefato **acima da média em maturidade de segurança**: possui trilha de auditoria real embutida, gates estáticos, scanner de prompt-injection, SQL parametrizado, `repo_bridge` exemplar e 68/68 testes verdes. As ferramentas mais perigosas por natureza (`pot`, execução de skills externas) são **honestas** sobre suas fronteiras e ficam atrás de gates humanos.

O achado que exige ação imediata é o **SEC-A (path traversal comprovado)**, potencializado pelo **SEC-B (integridade não autenticada)** — juntos permitem, via bundle forjado, escrita de arquivo fora do diretório de swap. A boa notícia: **a correção já existe no próprio código** (o padrão `_resolved_within`/`SEC-005` do `repo_bridge`); basta aplicá-la aos backends de persistência. Os demais itens são endurecimento incremental e limpeza de baixo esforço.

*— Auditoria conduzida como equipe de QA (Tech Lead + Dev + QA + Segurança), com execução dinâmica dos módulos e PoC das vulnerabilidades.*
