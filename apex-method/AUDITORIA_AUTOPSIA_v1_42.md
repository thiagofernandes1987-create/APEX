# Auditoria "Autópsia" — apex-method v1.41.0 → v1.42.0

**Alvo:** `apex-method/` (origin/main, v1.41.0) — 41 scripts, 12 catálogos, 3 suítes de teste,
19 references, SKILL.md.
**Ambiente da auditoria:** Windows 11 · Python 3.14.3 · numpy/scipy/pandas/PyYAML presentes ·
scikit-learn AUSENTE · sympy ausente no início (instalado durante a auditoria para validar o
caminho formal completo).
**Método:** nada aceito sem execução. Linha de base executada primeiro (benchmark + evaluate +
scenario), cada falha reproduzida isoladamente até a causa raiz, cada correção validada por
re-execução. Varredura estática (py_compile, grep de `open()` sem encoding, `expanduser`,
comandos Unix em subprocess, consistência catálogo⇄scripts) + varredura dinâmica (as 3 suítes).
**Data:** 2026-07-17.

---

## 1. Sumário executivo

A v1.41.0 estava **quebrada em qualquer máquina Windows e em qualquer Python ≥ 3.12** — não por
bugs no motor cognitivo (a matemática bayesiana, o PoT, o DAG, os gates de segurança e a memória
estão sólidos e reverificados), mas por uma classe de defeito que as auditorias anteriores nunca
cobriram: **o harness de testes e 3 pontos do runtime assumiam Linux/macOS e Python antigo**.
O pior achado é de **integridade de dados do usuário**: as suítes de teste apagavam e corrompiam
os bancos REAIS de `~/.apex-method/` — exatamente a "memória viva entre sessões" que a skill
promete preservar.

| Suíte | Antes (v1.41, este ambiente) | Depois (v1.42) |
|---|---|---|
| `tests/benchmark.py` | **42/45 FAIL** (verify, gravity, orchestrator) | **46/46 PASS** (+1 teste novo) |
| `tests/evaluate.py` | **8.8/13 = 67.7%** (exit 1) | **13/13 = 100%** (exit 0) |
| `tests/scenario.py` | 7/7 limpos, mas **crash + exit 1** no veredito | **7/7 + exit 0** |

**10 achados**: 2 críticos (dados do usuário), 2 altos (roteamento/validade de teste),
5 médios, 1 baixo — **todos corrigidos e validados por execução**. Nenhuma vulnerabilidade de
segurança nova; todos os gates (SR_37, AST scan, allowlists, ledger SHA-256, bundle hash)
reverificados e funcionando.

---

## 2. Achados (ONDE · O QUE · COMO ACHEI · CORREÇÃO)

Severidade: 🔴 crítico · 🟠 alto · 🟡 médio · 🔵 baixo · 🟢 informativo.

### F-01 🔴 Os testes APAGAVAM os bancos de dados reais do usuário

- **Onde:** `tests/scenario.py` (`s_parallel`, ~L119), `tests/benchmark.py`
  (`t_competence_matrix` ~L481, `t_evaluate_hypotheses` ~L497).
- **O que:** para "limpar o estado", os testes executavam
  `os.remove(os.path.expanduser("~/.apex-method/competence.db"))` e o mesmo para `learning.db` —
  destruindo o aprendizado durável REAL do usuário (Op-P3) a cada rodada de teste. A skill vende
  "aprendizado que persiste entre sessões"; a própria suíte o deletava.
- **Como achei:** `grep -rn "expanduser" tests/` durante a varredura estática, confirmado ao vivo:
  após rodar `scenario.py`, os `.db` do home foram removidos e recriados com dados de teste.
- **Correção:** hook de isolamento **`APEX_METHOD_HOME`** honrado por TODOS os stores duráveis
  (`config`, `agent_registry`, `competence_matrix`, `concurrent_executor`, `learning`, `memory`,
  `menu`, `project_ledger`, `swap_store`). As 3 suítes setam
  `os.environ.setdefault("APEX_METHOD_HOME", tempfile.mkdtemp(...))` ANTES de qualquer import;
  as limpezas de teste apagam apenas os caminhos isolados (`cm._COMPETENCE_DB`, `lrn.DB_DEFAULT`).
  Default sem a env: comportamento idêntico ao anterior (`~/.apex-method`).

### F-02 🔴 Redirecionamento de HOME não funciona no Windows → testes corrompiam a config real

- **Onde:** `tests/benchmark.py`, `t_runtime_autopsy` (blocos RT-23 ~L892 e RT-26 ~L906).
- **O que:** os testes trocavam `os.environ["HOME"]` para um tempdir e recarregavam o módulo. Mas
  no Windows (Python ≥ 3.8) `os.path.expanduser("~")` **ignora `HOME` e usa `USERPROFILE`** —
  então RT-23 gravava `min_mode="DEEP"` na config REAL (`~/.apex-method/config.json`) NO MEIO da
  suíte, e RT-26 gravava um grant de teste (`demo/frontend`) no `agent_grants.json` real. Efeito
  cascata: com `min_mode=DEEP` ativo, `orchestrator.run("2+2")` deixava de ser EXPRESS →
  `t_orchestrator` FALHAVA (o dict de erro do baseline mostra exatamente "2+2" em
  FULL_PIPELINE/DEEP). O `t_execution_policy` (que roda depois) resetava o `min_mode`, mascarando
  a causa — o teste passava isolado e falhava na suíte.
- **Como achei:** `t_orchestrator` passou em isolamento mas falhou na suíte completa → suspeita de
  poluição de estado → prova direta:
  `os.environ['HOME']='C:/fake'; os.path.expanduser('~')` → `C:\Users\Thiag`; e o
  `agent_grants.json` com 6 registros `demo/frontend` presente no home real.
- **Correção:** RT-23/RT-26 agora redirecionam via **`APEX_METHOD_HOME`** (honrada em qualquer SO)
  com save/restore correto; a suíte inteira já roda num home isolado (F-01). O
  `agent_grants.json` vazado (só lixo de teste) foi removido do home real.

### F-03 🟠 `gravity.plan()` retornava constelação vazia sem sklearn (raio calibrado errado)

- **Onde:** `scripts/gravity.py`, `plan()` L191–196; constantes L42–44.
- **O que:** os raios absolutos `ATTRACTION_RADIUS=0.12` / `RELAXED_RADIUS=0.06` foram calibrados
  sobre scores do TF-IDF do **sklearn**. Com o fallback puro-Python (`_tfidf`), os pulls saem
  menores (0.03–0.05 para uma tarefa de segurança com `security-auditor` no catálogo) — TUDO caía
  abaixo de 0.06 → constelação `{}` + 4 gaps falsos ("no agent in library...") → o orchestrator
  perdia todos os especialistas. Quebra direta da alegação "o núcleo funciona sem sklearn"
  (inventario Marco 2) e dos testes `t_gravity`/`t_orchestrator`.
- **Como achei:** benchmark baseline FAIL `gravity: assert {}` → reproduzi:
  `gravity.constellation(...)` retornava corpos com pulls 0.034–0.053; `plan()` zerava tudo.
- **Correção:** terceiro fallback **relativo** usando a constante `NEIGHBOR_COLOAD=0.7` — que
  estava **declarada e nunca usada** (dead constant) e é exatamente a regra de co-load do
  `semantic_gravity_engine` (OPP-169): mantém corpos com `pull ≥ 0.7 × max_pull`, com piso
  `RELAXED_RADIUS/3` para que uma tarefa realmente alienígena continue gerando o vazio honesto.
  Validado: tarefa de segurança → 4 agentes + script; "compose a symphony" → quase-vazio.

### F-04 🟠 Simulação de "ambiente limpo" morta em Python ≥ 3.12

- **Onde:** `tests/evaluate.py`, `c_clean_env()` (critério peso 2).
- **O que:** o bloqueador de imports usava `find_module`/`load_module` — protocolo legado
  **removido do Python 3.12**. Em Python moderno o bloqueador não bloqueia NADA: numpy/scipy
  importavam normalmente, o assert `engine=='stdlib'` do Monte Carlo falhava (critério 0/2), e —
  pior — numa máquina sem numpy o critério "passaria" sem ter testado degradação alguma
  (falso verde). O critério que valida a promessa central "roda em stdlib puro" estava vazio.
- **Como achei:** evidência truncada do evaluate (`AssertionError`) → reproduzi o subprocess com
  stderr completo → provei com um bloqueador mínimo que `import numpy` passa pelo `find_module`
  no 3.14.
- **Correção:** bloqueador reescrito com **`find_spec`** (MetaPathFinder atual) que levanta
  `ImportError` para sklearn/sympy/numpy/scipy. Validado: critério 1.0 e o bloqueio agora é real
  (o subprocess degrada para `engine=stdlib` e `CONJECTURA_FORMAL`).

### F-05 🟡 `t_verify` exigia sympy — contradizendo o contrato de degradação declarado

- **Onde:** `tests/benchmark.py`, `t_verify` L63–68; `scripts/verify.py` (correto, sem mudança).
- **O que:** sympy é acelerador **opcional** declarado (`requirements.txt`, `apex_llm.yaml`:
  "degrade: verify marks CONJECTURE") e `verify.py` degrada corretamente — mas o teste assertava
  `FORMAL_VERIFIED`/`FORMAL_REFUTED` incondicionalmente. Resultado: o "full pass" do benchmark era
  inalcançável em ambiente stdlib, contradizendo o próprio inventário.
- **Como achei:** baseline FAIL `verify: CONJECTURA_FORMAL ... sympy not installed`.
- **Correção:** o teste agora valida o CONTRATO: sem sympy exige `CONJECTURA_FORMAL` (degradação
  declarada); com sympy exige VERIFIED/REFUTED. Ambos os ramos validados por execução (instalei
  sympy e re-rodei: `FORMAL_VERIFIED`/`FORMAL_REFUTED` ok, 46/46 nos dois cenários).

### F-06 🟡 Encoding cp1252 do Windows quebrava as 3 suítes

- **Onde:** `tests/evaluate.py` (`c_sr40_selfcompliance` lia scripts sem `encoding=` →
  `UnicodeDecodeError`, critério zerado); `tests/scenario.py` (print final `✅/❌` →
  `UnicodeEncodeError` → **crash com exit 1 DEPOIS de 7/7 limpos** — o exit code mentia);
  `tests/benchmark.py` (5 `open()` sem encoding).
- **Como achei:** evidência `UnicodeDecodeError: 'charmap'` no evaluate; traceback do scenario.
- **Correção:** `encoding="utf-8"` em todas as leituras/escritas de texto dos testes +
  `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` no topo dos 3 harnesses.

### F-07 🟡 `menu.py update --apply` usava `cp -r` (comando Unix) — quebrado no Windows

- **Onde:** `scripts/menu.py` L79: `subprocess.run(["cp", "-r", src + "/.", ROOT], check=True)`.
- **O que:** no Windows não existe `cp` → `FileNotFoundError` → o auto-update da skill nunca
  funcionou nesta plataforma (o erro era engolido pelo `except` e reportado como
  `applied: False`).
- **Como achei:** `grep -n "subprocess.run(\[" scripts/` na varredura de portabilidade.
- **Correção:** `shutil.copytree(src, ROOT, dirs_exist_ok=True)` — portátil e equivalente.

### F-08 🟡 `taxonomy.py` entregue como módulo ÓRFÃO (nunca chamado) e fora do catálogo

- **Onde:** `scripts/taxonomy.py` (169 linhas, classificador de facetas canônicas EN com triggers
  bilíngues PT/EN — a "camada de atração independente de idioma" pedida pelo autor);
  `catalog/scripts_lib.json`; `SKILL.md` L50.
- **O que:** três inconsistências: (1) **nenhum** script importava `taxonomy` — a chamada foi
  esquecida (o mesmo padrão de defeito F-fluxo das auditorias anteriores: implementado ≠ ligado);
  (2) ausente do `scripts_lib.json` — a própria rubrica acusava `symdiff=['taxonomy']` e o
  gravity nunca o carregava como corpo; (3) `SKILL.md`/`inventario.md` diziam "40 scripts" com 41
  no disco.
- **Como achei:** critério `c_catalog_consistency` = 0 no evaluate baseline + `grep -rln taxonomy
  scripts tests` → zero chamadores.
- **Correção:** (1) registrado no catálogo (`script:taxonomy`, mass 170); (2) **ligado** como
  primeiro fallback do `orchestrator.dissect` — sem hit de keyword, as facetas canônicas mapeiam
  domínio→disciplina antes do char-n-gram (validado: "calcule a moda e a mediana da amostra" →
  `math`, antes caía no default); (3) bullet novo no §2 do SKILL.md + contagens 40→41; (4) teste
  novo `t_taxonomy` no benchmark (classify + atração cross-language PT↔EN 0.786 > stub T-Mobile
  0.0 + wiring do dissect).

### F-09 🔵 `learning.py` violava o próprio linter SR_40 (sem seção WHEN)

- **Onde:** `scripts/learning.py`, docstring.
- **O que:** o zero-ambiguity linter (SR_40) exige why/when/what-if-fails; `learning.py` não tinha
  "WHEN". Invisível até agora porque o critério SR_40 do evaluate crashava no Windows (F-06) —
  um bug escondia o outro.
- **Como achei:** após corrigir F-06, o critério reportou 40/41; loop de lint identificou o
  arquivo.
- **Correção:** seção "WHEN TO USE" adicionada. 41/41 + SKILL.md ok → critério 1.0.

### F-10 🟢 Segurança: nenhuma vulnerabilidade nova; todos os gates reverificados

Verificação executada (não confiada em documentação):
- **AST scan dois níveis** (`skill_scout`): `os.system`/`exec`/`eval`/`__import__`/
  `pickle.loads` → REJEITADOS; `json.loads` → aceito (FP antigo continua corrigido); import fora
  da whitelist → `safe=False` (AUD-004 mantido); prompt-injection no corpo → FLAGGED (RT-12);
  scripts referenciados descobertos e escaneados (RT-13); arquivo truncado → recusado (RT-14).
- **Forge gate SR_37** (`guards`): `getattr` dinâmico (`'sys'+'tem'`) → REJECTED.
- **`repo_bridge`**: path traversal (`../etc/passwd`) → recusado; allowlist
  `raw.githubusercontent.com/<repo>` + redirect checado na URL FINAL; ref pinável
  (`APEX_REPO_REF`).
- **`skills_sh`**: allowlist read-only `skills.sh`; nada auto-instala (H5); shape inesperado da
  API degrada sem exceção (RT-15).
- **Ledger SHA-256** (`memory`): edição de qualquer coluna → `content hash mismatch` (RT-05);
  **bundle de swap** adulterado → REJEITADO antes de qualquer escrita (RT-07/08).
- Único vetor de escrita indevida encontrado nesta rodada foi **interno** (os próprios testes,
  F-01/F-02) — corrigido.

### F-11 🟢 Dependências (estado medido, não declarado)

| Dependência | Status no ambiente | Comportamento validado |
|---|---|---|
| stdlib puro | — | núcleo completo funciona (bloqueio real via find_spec, F-04) |
| numpy/scipy | presentes | `solve_ode` backend=scipy; Monte Carlo engine=numpy |
| scikit-learn | **ausente** | `_tfidf` fallback OK em router/gravity/agent_registry (com F-03 corrigido) |
| sympy | ausente → **instalado na auditoria** | degradação CONJECTURA_FORMAL E caminho FORMAL_VERIFIED/REFUTED, ambos validados |
| pandas / PyYAML | presentes | `apex_llm.yaml` lido via YAML (autoritativo) |

---

## 3. Observação sobre dados residuais no home do usuário

Rodadas ANTIGAS das suítes (antes desta correção) já haviam destruído/populado
`~/.apex-method/{memory,competence,learning}.db` com dados de teste — isso não é recuperável.
O `agent_grants.json` vazado (100% lixo de teste `demo/frontend`) foi removido nesta auditoria;
`config.json` foi verificado limpo (`min_mode: null`). Se você não tem memória real valiosa
nesses `.db`, recomendo apagá-los uma vez para partir de um estado limpo — a partir da v1.42
os testes **nunca mais tocam** o home real.

---

## 4. Arquivos alterados (v1.42.0)

| Arquivo | Mudança |
|---|---|
| `scripts/config.py` · `agent_registry.py` · `competence_matrix.py` · `concurrent_executor.py` · `learning.py` · `memory.py` · `project_ledger.py` · `swap_store.py` | hook `APEX_METHOD_HOME` (F-01/F-02); `learning.py` também ganhou a seção WHEN (F-09) |
| `scripts/gravity.py` | fallback relativo `NEIGHBOR_COLOAD × max_pull` com piso honesto (F-03) |
| `scripts/menu.py` | `shutil.copytree` no update (F-07); `persist()` usa `memory.DB_DEFAULT` (F-01) |
| `scripts/orchestrator.py` | `dissect` ganha o fallback de facetas via `taxonomy` (F-08) |
| `tests/benchmark.py` | isolamento + RT-23/26 via `APEX_METHOD_HOME` + t_verify contratual + encodings + stdout utf-8 + teste novo `t_taxonomy` (F-01/02/05/06/08) |
| `tests/evaluate.py` | bloqueador `find_spec` + encodings + isolamento (F-04/F-06) |
| `tests/scenario.py` | isolamento (sem deleção do home real) + stdout utf-8 (F-01/F-06) |
| `catalog/scripts_lib.json` | +`script:taxonomy` (40 → 41 entradas, 1:1 com `scripts/`) (F-08) |
| `SKILL.md` · `inventario.md` | versão 1.42.0; contagem 41 scripts; bullet do taxonomy (F-08) |

## 5. Estado final verificável

```
python tests/benchmark.py   # 46/46 PASS  (com e sem sympy — os dois ramos validados)
python tests/evaluate.py    # 13/13 = 100%, exit 0
python tests/scenario.py    # 7/7 CLEAN, exit 0
```

**Veredito:** o motor cognitivo da v1.41 estava correto; a camada de portabilidade e a higiene
dos testes não. A v1.42 fecha os 10 achados com prova de execução em Windows/Python 3.14, e a
suíte agora é incapaz — por construção — de tocar os dados reais do usuário.

*Auditoria conduzida em estilo autópsia (baseline → reprodução → causa raiz → correção →
re-validação). Fim.*
