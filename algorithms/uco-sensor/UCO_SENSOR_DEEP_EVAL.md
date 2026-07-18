# UCO Sensor — Avaliação Profunda (debate multi-agente)

> Gerado em: 2026-06-26
> Modelo: claude-opus-4-8 (Claude Code agent)
> Sessão: deep-eval-run-2026-06-26-uco391
> Versão auditada: v3.9.1
> Rounds de debate executados: 2 (round-1 challenge + round-2 convergence dry-run)
> Loop convergiu: SIM — round-2 não derrubou findings adicionais após DOWNGRADE de F7 e F12; 1 dry round = critério K=1 satisfeito.

---

## §1. Executive Summary

**Estado atual.** O UCO Sensor v3.9.1 é uma plataforma madura e de engenharia incomum para um produto deste estágio: 2145 testes verdes, 8 tabelas SQLite, 76+ endpoints REST, 5 invariantes formais executáveis e um histórico de dois gates de hardening (gate-1/gate-2) + um QA Loop de 4 lentes que fecharam todos os CRITICAL/HIGH conhecidos. O núcleo científico (PELT, Granger F-test, DBSCAN, HMC, Welch PSD) está implementado de forma sólida e os módulos de governança são puros e testáveis. Não fabriquei problemas onde o código está sólido — a camada de invariantes (`governance/invariants.py`) e o billing atômico (`atomic_check_and_charge`) são exemplares.

**Maior risco.** A camada multi-tenant introduzida no Sprint Y é **billing-only, não isolation**: as tabelas `snapshots`, `anomalies`, `discovered_signatures`, `remediations` e `marketplace_signatures` **não têm coluna `tenant_id`** ([VERIFICADO] `snapshot_store.py:55-88`, `:122`), então qualquer key autenticada lê e sobrescreve dados de qualquer outro tenant. Some-se a isso o charge-before-handler em `_billed_dispatch` (cobra mesmo em 500) e o cache nunca invalidado em writes — três defeitos correlacionados que tornam o "SaaS multi-tenant" do CHANGELOG enganoso na prática.

**Maior oportunidade.** O scanner de histórico git já roda `git log`+`git show` por commit (`git_history_scanner.py`); reusar essa infra para **secrets-in-history** + **license compliance** + **SBOM CycloneDX** são três scanners de alto ROI que competidores cobram caro e que aqui custam ~1-2 dias cada sobre infraestrutura existente. Adicionalmente, há canais já capturados-mas-dormentes (predictor_confidence persistido mas sub-explorado) prontos para ativação sem back-fill.

---

## §2. Quantitative Health Score

| Dimensão | Score 0-100 | Justificativa em 1 frase |
|---|---|---|
| Architecture coupling | 72 | `api/server.py` com 5337 LOC e `snapshot_store.py` com 2379 LOC são god-modules; resto bem fatorado em `governance/*` puros. |
| Security posture | 64 | Auth/admin/secrets sólidos pós-gate, mas isolamento multi-tenant ausente e charge-on-error rebaixam a nota. |
| Test coverage adequacy | 88 | 2145 testes com pins por fix; gaps em concorrência real (locks testados logicamente, não sob carga). |
| Performance headroom | 58 | `threading.Lock()` único serializa TODA operação de store; hot-row `units_used` + N+1 `recompute_derived_pending` deferred conhecidos. |
| Documentation completeness | 70 | `inventario.md`/CHANGELOG excelentes; README desatualizado (badge v0.4.0, "20+ endpoints", lista de tabelas obsoleta). |
| Channel utilization | 67 | 9 primários sólidos; vários dos 96 estendidos persistidos mas não alimentando FreqEngine/APS (perda de sinal documentada no roadmap). |
| Innovation readiness | 76 | Base espectral + invariantes + paper skeleton dão tração rara; faltam SBOM/SLSA/OPA que o mercado 2025-2026 exige. |
| **COMPOSITE** | **69** | Média ponderada: Security 0.22, Perf 0.18, Arch 0.15, Test 0.15, Channel 0.12, Docs 0.10, Innov 0.08 — pesos justificados pelo fato de que multi-tenant SaaS torna Security/Perf os eixos de maior blast-radius. |

Cálculo composite: 64·0.22 + 58·0.18 + 72·0.15 + 88·0.15 + 67·0.12 + 70·0.10 + 76·0.08 = **68.6 ≈ 69**.

---

## §3. Findings P0/P1 (CONFIRMED após debate)

### Finding #1 — Multi-tenant é billing-only: dados de análise não têm isolamento por tenant
- **Categoria**: Security / Architecture
- **Severidade**: P0
- **ROI estimado**: ★★★★★
- **Effort estimado**: L (5-8 pessoa-dias — schema migration + query rewrites + back-fill 'default')
- **Owner sugerido**: 🔒 Security Engineer
- **POR QUÊ**: O Sprint Y vende "SaaS multi-tenant", mas o isolamento foi aplicado apenas a `tenants`/`usage_events`/`api_keys`. Toda a superfície de dados de produto (snapshots de código, anomalias, assinaturas descobertas, remediations, marketplace) é um espaço global compartilhado. Um cliente PRO pago consegue ler/sobrescrever os snapshots do código-fonte de outro cliente — vazamento de propriedade intelectual e corrupção cross-tenant.
- **COMO IDENTIFICOU**:
  1. `snapshot_store.py:55-88` (`_DDL_SNAPSHOTS`): colunas são `module_id, commit_hash, ...` — **sem `tenant_id`**. [VERIFICADO]
  2. `snapshot_store.py:122-129` (`_DDL_ANOMALIES`): idem, sem `tenant_id`. [VERIFICADO]
  3. `_billed_dispatch` (server.py:1889-1910) resolve `tid` apenas para cobrança e chama `handler_fn(*args)` sem passar o tenant; `handle_analyze`→`_store.insert(mv)` (server.py:735) grava na tabela global. [VERIFICADO]
  4. `UNIQUE(module_id, commit_hash)` (snapshot_store.py:87) é global → tenant B com o mesmo `module_id`/`commit_hash` sobrescreve a linha do tenant A (upsert idempotente). [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Adicionar `tenant_id TEXT NOT NULL DEFAULT 'default'` via migration aditiva (mesmo padrão de `_migrate_api_keys_tenant_id`, snapshot_store.py:467) em `snapshots`, `anomalies`, `discovered_signatures`, `remediations`, `marketplace_signatures`.
  - Alterar `UNIQUE` para `UNIQUE(tenant_id, module_id, commit_hash)`.
  - Propagar `tid` de `_billed_dispatch` para os handlers como kwarg e filtrar todos os SELECT/INSERT por `tenant_id`.
  - Back-fill: todas as linhas existentes recebem `'default'` (consistente com bypass tenant).
  - Adicionar 6-8 testes cross-tenant (tenant A não vê módulos de B).
- **IMPACTO**:
  - Antes: 5 tabelas de produto com 0% de isolamento; N tenants compartilham 1 namespace.
  - Depois (estimado): isolamento por linha; vazamento cross-tenant eliminado; suporta N tenants reais sem leak. (estimado: +1 índice por tabela, ~+8% storage por overhead de coluna+índice).
- **DEBATE**:
  - 🔒 Security: CONFIRM — "caller autenticado de tenant B lê snapshot de A; é CWE-639 (IDOR) clássico no nível de schema."
  - 🏛️ Architect: CONFIRM com nuance — "concordo P0, mas o blast-radius da migration é grande: 30+ call-sites de query precisam do filtro; sugiro um `_scoped` query helper para não espalhar `WHERE tenant_id=?` à mão e evitar miss."
  - 🎯 Product: CONFIRM — "isto contradiz o claim do README/CHANGELOG; é bloqueador de GA de SaaS."
  - **Resolução**: CONFIRMED por 3 a 0 (P0). Architect adiciona requisito de helper de scoping para reduzir risco de regressão.

### Finding #2 — `_billed_dispatch` cobra antes de executar o handler; 500/exception não estorna
- **Categoria**: Architecture / Product (billing correctness)
- **Severidade**: P1
- **ROI estimado**: ★★★★☆
- **Effort estimado**: M (2-3 pessoa-dias)
- **Owner sugerido**: ⚡ Performance Engineer
- **POR QUÊ**: `check_and_charge` debita `units_used` ANTES de `handler_fn` rodar. Se o handler levantar exceção (cai no catch-all 500) ou retornar erro de negócio (4xx), o tenant já foi cobrado e não há refund. Para `hmc_repair` (20 unidades) um bug intermitente drena o budget de FREE (100 unidades) em 5 falhas.
- **COMO IDENTIFICOU**:
  1. `server.py:1900-1910`: `ok, info = check_and_charge(...)` executa o INSERT+UPDATE de cobrança; só depois `return handler_fn(*args, **kwargs)`. [VERIFICADO]
  2. `billing.check_and_charge` (billing.py:292-298) grava o evento com `units=cost` e incrementa `units_used` no caminho ok=True — irreversível pelo dispatcher. [VERIFICADO]
  3. O `try/except` do dispatcher de POST (server.py:4975+) envolve `_billed_dispatch`; uma exceção do handler vira 500 via `_safe_500_envelope`, mas a cobrança já está commitada. [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Inverter para charge-on-success: rodar `handler_fn`, capturar `(code, data)`, e só chamar `check_and_charge` quando `200 <= code < 300`.
  - Manter o pre-check de quota (sem o charge) antes do handler para rejeitar 402 cedo; o débito real ocorre pós-sucesso.
  - Alternativa mais barata: try/finally que estorna `units_used -= cost` quando `code >= 500` (mas não para 4xx de negócio legítimo).
- **IMPACTO**:
  - Antes: cobrança em 100% das chamadas billáveis, inclusive 500s. Em hmc_repair, 5 erros = 100 unidades drenadas indevidamente.
  - Depois (estimado): cobrança só em 2xx; over-charge eliminado; quota reflete trabalho entregue.
- **DEBATE**:
  - 🔒 Security: CONFIRM — "denial-of-budget: um atacante que conhece um input que 500a esvazia o tenant alvo."
  - 🏛️ Architect: parcial REFUTE→CONFIRM — "argumento contra: cobrar antes garante atomicidade sob a mesma lock e evita TOCTOU de quota. Mas a correção (pré-check sem charge + charge pós-2xx) preserva atomicidade e resolve o over-charge; então CONFIRM com escopo ajustado."
  - **Resolução**: CONFIRMED por 2 a 0 (P1). Escopo refinado: split check (pré) e charge (pós-2xx).

### Finding #3 — Lock global único serializa TODAS as operações do SnapshotStore
- **Categoria**: Performance
- **Severidade**: P1
- **ROI estimado**: ★★★☆☆
- **Effort estimado**: L (4-6 pessoa-dias — exige benchmark + reestruturação de conexões)
- **Owner sugerido**: ⚡ Performance Engineer
- **POR QUÊ**: `self._lock = threading.Lock()` (snapshot_store.py:401) é adquirido por **toda** operação — reads de tenant, writes de snapshot, billing, marketplace. Sob o `ThreadingHTTPServer` (server.py:46), N threads de request convergem num único mutex Python para qualquer I/O de DB, anulando o paralelismo do servidor. Uma chamada lenta (ex.: `recompute_derived_pending` segurando lock por loop) bloqueia até `/health` que toque o store.
- **COMO IDENTIFICOU**:
  1. `snapshot_store.py:401`: lock único de instância. [VERIFICADO]
  2. ~50 `with self._lock:` em todos os métodos (grep: linhas 442, 510, 523-2121). [VERIFICADO]
  3. Modo file usa `threading.local()` conn por thread (snapshot_store.py:418) — WAL permitiria leituras concorrentes, mas o Lock Python as serializa de qualquer forma, desperdiçando o WAL. [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Para DB em arquivo (não `:memory:`): remover o Lock Python dos caminhos read-only e confiar no WAL + conexões thread-local (já existem). Manter Lock só para o caminho `:memory:` (conn compartilhada).
  - Introduzir um `RLock` separado por domínio (billing vs snapshots) para reduzir contenção entre subsistemas.
  - [BENCHMARK NECESSÁRIO] medir RPS antes/depois com `bench/benchmark.py` sob 8 threads concorrentes.
- **IMPACTO**:
  - Antes: throughput de reads limitado a 1 operação de store por vez (estimado).
  - Depois (estimado): reads concorrentes via WAL escalam ~linearmente até o limite de I/O; ganho [BENCHMARK NECESSÁRIO], hipótese 3-6x em read-heavy dashboards.
- **DEBATE**:
  - 🏛️ Architect: CONFIRM — "o Lock é defensivo herdado do modo `:memory:`; no modo file é redundante para reads."
  - 📊 Data Scientist: parcial REFUTE — "SQLite com WAL ainda serializa writers; o ganho real é só em reads. Para writes (insert hot path) não muda nada." → DOWNGRADE de escopo para reads-only.
  - **Resolução**: DOWNGRADED (mantém P1 mas escopo restrito a caminhos read-only no modo file; writes permanecem serializados por design do SQLite).

### Finding #4 — Cache de leitura nunca invalidado em writes → dashboards servem dados stale
- **Categoria**: Architecture / Performance (correctness)
- **Severidade**: P1
- **ROI estimado**: ★★★★☆
- **Effort estimado**: S (1 pessoa-dia)
- **Owner sugerido**: ⚡ Performance Engineer
- **POR QUÊ**: Endpoints caros são cacheados com TTL 30-120s (`cache_set` em server.py:1400/1517/4172), mas `cache_invalidate` só é chamado pelo endpoint admin manual (`handle_cache_invalidate`, server.py:1434-1439). Nenhum caminho de write (`_store.insert(mv)`) invalida o cache. Após um novo snapshot, `/predictor/accuracy`, `/anti-pattern-score/trend` e `/repo/health-score` retornam o valor anterior por até 120s — o produto cuja proposta é "detectar degradação cedo" mostra dados velhos.
- **COMO IDENTIFICOU**:
  1. `grep cache_set` → server.py:1400 (ttl=60), :1517 (ttl=120), :4172 (ttl=30). [VERIFICADO]
  2. `grep cache_invalidate` → apenas server.py:1439 (handler admin) e a definição. Nenhum write-path o chama. [VERIFICADO]
  3. `_store.insert(mv)` em server.py:735, 960, 2416-2417, 2677 — nenhum seguido de invalidate. [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Adicionar `cache_invalidate(f"module:{mv.module_id}")` após cada `_store.insert(mv)` nos handlers de ingest (`/analyze`, `/diff`, `/scan-repo`).
  - Usar prefixos de cache key por módulo para invalidação cirúrgica (já há suporte a prefix em `cache_invalidate`).
  - Adicionar 3 testes: insert → cache miss → recomputa.
- **IMPACTO**:
  - Antes: janela de staleness de 30-120s pós-write; valor incorreto exibido em dashboards de degradação.
  - Depois (estimado): staleness ≤ tempo de uma request; correção de um bug de correção silencioso.
- **DEBATE**:
  - 🎯 Product: CONFIRM — "para um produto de 'early warning', servir trend de 2min atrás é uma falha de produto, não só de perf."
  - ⚡ Perf: CONFIRM — "invalidação por prefixo é barata; o custo é 1 chamada por insert."
  - **Resolução**: CONFIRMED por 2 a 0 (P1).

### Finding #5 — `marketplace._has_redos_shape` usa blocklist de substring fraca em vez do analisador ReDoS real existente
- **Categoria**: Security / SAST
- **Severidade**: P1
- **ROI estimado**: ★★★★☆
- **Effort estimado**: S (0.5-1 pessoa-dia)
- **Owner sugerido**: 🧪 SAST/SCA Specialist
- **POR QUÊ**: Existe um analisador ReDoS estruturado e correto em `sast/regex_analyzer.py` (`analyze_pattern`, Classes A/B/C: nested quantifiers, overlapping alternation, char-class). Porém o guard que protege o marketplace e o rules_feed usa uma blocklist de substring ingênua (`marketplace.py:62`): `("**", "++", ..., "(.*)+", "(.+)+")`. Esta lista **não pega** `(a+)+`, `([a-z]+)*`, `(\d+)*` — exatamente os padrões que `regex_analyzer` detecta. Um payload com `(a+)+` passa o guard.
- **COMO IDENTIFICOU**:
  1. `marketplace.py:50-63`: `suspect` é uma tupla de substrings; `(a+)+` não contém nenhuma delas. [VERIFICADO]
  2. `sast/regex_analyzer.py:103` `analyze_pattern` + Classes A/B/C (linhas 55-93) detectam `(X+)+` e alternação sobreposta corretamente. [VERIFICADO]
  3. O CHANGELOG (audit-6) e `inventario.md` registram o guard como mitigação de ReDoS, mas ele e o analisador real divergiram (mesma classe de bug que a Sprint H descreve em `signals.py:1-16`: duas cópias divergindo).
- **COMO SUGERE FAZER**:
  - Substituir `_has_redos_shape` por uma chamada a `sast.regex_analyzer.analyze_pattern(text)` retornando `bool(findings)`, mantendo o guard de comprimento >2000 e empty→False (QA-FIX-6).
  - Garantir import sem dependência circular (regex_analyzer é puro stdlib).
  - Adicionar testes que `(a+)+`, `([a-z]+)*` são rejeitados em marketplace + rules_feed.
- **IMPACTO**:
  - Antes: blocklist cobre ~4 formas; deixa passar a família `(X+)+`/`(X+)*` (a mais comum de ReDoS).
  - Depois (estimado): cobertura ReDoS sobe das ~4 substrings para as 3 classes estruturais do analisador (estimado: de ~30% para ~80% das formas exponenciais conhecidas).
- **DEBATE**:
  - 🧪 SAST: CONFIRM — "é literalmente DRY: o analisador correto já existe e não é reusado."
  - 🔒 Security: CONFIRM — "superfície real: payload de marketplace importado de peer não-confiável."
  - **Resolução**: CONFIRMED por 2 a 0 (P1).

### Finding #6 — Ausência de scanner de secrets-in-history (infra git já existe)
- **Categoria**: Scanner (novo) / Innovation
- **Severidade**: P1
- **ROI estimado**: ★★★★★
- **Effort estimado**: M (2 pessoa-dias)
- **Owner sugerido**: 🧪 SAST/SCA Specialist
- **POR QUÊ**: O produto não tem detecção de segredos versionados — um dos achados de maior valor de mercado (GitGuardian, gitleaks, trufflehog construíram negócios sobre isto). O `git_history_scanner.py` já itera `git log → git show hash:file` por commit, então a infra de varredura histórica está pronta; falta só o detector de entropia/regex sobre o conteúdo dos blobs.
- **COMO IDENTIFICOU**:
  1. `grep -rln "secret_scan|gitleaks|secrets-in-history"` → 0 resultados. [VERIFICADO]
  2. `scan/git_history_scanner.py:8` documenta o pipeline `git log → git show hash:file → UCOBridge`. [VERIFICADO]
  3. `sast/scanner.py` tem SAST008 (hardcoded secret) sobre o working tree, mas não sobre o histórico — segredos removidos no HEAD mas vivos no histórico passam despercebidos. [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Novo `sast/secrets_history.py` que reusa o iterador de commits do git_history_scanner e aplica: (a) regex de tokens conhecidos (AWS `AKIA[0-9A-Z]{16}`, GitHub `ghp_`, Slack `xoxb-`, JWT, PEM headers); (b) entropy check (Shannon >3.5 + len>16, já proposto para SAST008 no roadmap §3.1).
  - Endpoint `POST /scan-secrets-history` (billed `scan`).
  - Reportar `{commit_hash, file, line, rule, redacted_match}` em SARIF.
- **IMPACTO**:
  - Antes: 0 cobertura de secrets em histórico; segredos rotacionados-mas-não-purgados invisíveis.
  - Depois (estimado): detecção de ~15 famílias de token de alta confiança + entropia genérica; paridade básica com gitleaks na detecção (sem o revoke automation).
- **DEBATE**:
  - 🚀 Innovation: CONFIRM — "alto ROI: 2 dias sobre infra existente, capability que competidores cobram."
  - 🏛️ Architect: CONFIRM com ressalva — "varredura full-history é cara; precisa de bound de commits (reusar `n_commits`) e ser opt-in, não no hot path."
  - **Resolução**: CONFIRMED por 2 a 0 (P1). Architect impõe bound de commits.

### Finding #7 — README operacional drasticamente desatualizado (atrito de onboarding)
- **Categoria**: Product / Documentation
- **Severidade**: P1
- **ROI estimado**: ★★★★☆
- **Effort estimado**: S (0.5 pessoa-dia)
- **Owner sugerido**: 🎯 Product / Customer Voice
- **POR QUÊ**: O `sensor-api/README.md` mostra badge "version-0.4.0", "APEX v00.36.0", "20+ endpoints REST", tabela de tabelas que omite tenants/usage_events/billing, e nenhuma menção a multi-tenant, invariantes ou `/billing/*`. Um cliente novo lê o README e conclui que o produto é v0.4.0 com 20 endpoints — subestimando 76+ endpoints e toda a camada SaaS. Time-to-first-value sofre porque a doc não reflete a realidade.
- **COMO IDENTIFICOU**:
  1. `README.md:5` badge `version-0.4.0`; `:8` `APEX-v00.36.0`; `pyproject.toml:7` diz `version = "3.9.1"`. [VERIFICADO] (divergência de 3 major versions)
  2. `README.md:155-177` lista ~18 endpoints; CHANGELOG diz 76+. [VERIFICADO]
  3. `README.md:268` "Histórico v0.1.0 → v0.4.0" e estrutura de projeto sem `governance/`, `sast/`, `iac/`, `metrics/`. [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Sincronizar badges com `pyproject.toml` (script de release que injeta a versão).
  - Adicionar seção multi-tenant/billing + lista de invariantes + link para `inventario.md`.
  - Adicionar "quickstart < 30min": criar tenant → key → `/analyze` → `/anti-pattern-score`.
- **IMPACTO**:
  - Antes: README descreve um produto 3 majors atrás; cliente subestima capacidade.
  - Depois (estimado): onboarding alinhado; redução de tickets "isto suporta multi-tenant?" (estimado).
- **DEBATE**:
  - 🎯 Product: CONFIRM (P1) — "primeira impressão do cliente; barato e alto impacto."
  - 🏛️ Architect: DOWNGRADE→confirm — "não é defeito de runtime; é P2 em rigor técnico. Mas concordo com P1 por impacto de produto." 
  - **Resolução**: CONFIRMED por 2 a 0, mantido P1 por consenso de impacto de produto (Architect registra que tecnicamente seria P2).

### Finding #8 — N+1 em `recompute_derived_pending` segurando lock por iteração
- **Categoria**: Performance
- **Severidade**: P1
- **ROI estimado**: ★★★☆☆
- **Effort estimado**: M (1-2 pessoa-dias)
- **Owner sugerido**: ⚡ Performance Engineer
- **POR QUÊ**: Já está no backlog deferred (`inventario.md` linha 298, "N+1 em recompute_derived_pending snapshot_store.py:989"). Confirmo o mecanismo: o método busca os pendentes sob lock, depois faz um loop Python chamando `recompute_derived(mid, sha)` por linha — cada chamada reabre lock + recomputa APS+forecast individualmente. Para um back-fill de 10k snapshots são 10k+ aquisições de lock + 10k+ pares de query.
- **COMO IDENTIFICOU**:
  1. `snapshot_store.py:985-992`: `pending = ...fetchall()` sob lock; depois `for mid, sha in pending: self.recompute_derived(mid, sha)`. [VERIFICADO]
  2. Registrado em `inventario.md:298` como deferred para v3.9.2/v4.0.0 — não é achado inédito, mas quantifico-o aqui.
- **COMO SUGERE FAZER**:
  - Buscar histórico de cada módulo em lote (`GROUP BY module_id`) e recomputar em memória, fazendo um único `executemany` de UPDATE.
  - Não segurar o lock durante o cômputo (numpy/scipy); só na escrita final em lote.
- **IMPACTO**:
  - Antes: O(n) aquisições de lock + O(n) UPDATEs individuais para n linhas pendentes.
  - Depois (estimado): 1 query de leitura por módulo + 1 `executemany`; redução de lock acquisitions de n para ~#módulos (estimado 10-50x menos em back-fills grandes).
- **DEBATE**:
  - ⚡ Perf: CONFIRM — "back-fill é offline mas segura o lock global (Finding #3), bloqueando o servidor inteiro durante a operação."
  - 🏛️ Architect: CONFIRM — "interação com #3 é o que eleva de P2 para P1: enquanto recompute roda, todo o store está bloqueado."
  - **Resolução**: CONFIRMED por 2 a 0 (P1). Referência cruzada ao backlog deferred existente (inventario.md:298).

### Finding #9 — Cobertura SAST tem lacunas de classes que CodeQL/Semgrep flaggam (SSRF, deserialization Python, XXE)
- **Categoria**: SAST
- **Severidade**: P1
- **ROI estimado**: ★★★★☆
- **Effort estimado**: M (2-3 pessoa-dias para 6-8 regras)
- **Owner sugerido**: 🧪 SAST/SCA Specialist
- **POR QUÊ**: O scanner Python tem 32 regras (`SAST001-SAST043` com gaps). O roadmap §2.1 lista explicitamente SSRF, XXE, template injection e deserialization como gaps "CRÍTICO" ainda não cobertos no scanner Python core (o multilang cobre algumas em JS/Java). Competidores (Semgrep `python.lang.security`, CodeQL `py/ssrf`) flaggam estas por default. Concretamente, `pickle.loads`/`yaml.load` (deserialization, CWE-502) e `requests.get(user_url)` (SSRF, CWE-918) não têm regra dedicada no scanner Python.
- **COMO IDENTIFICOU**:
  1. `grep -oE "SAST[0-9]{3}" sast/scanner.py | sort -u` → 32 IDs, sem regra explícita de SSRF/XXE/pickle. [VERIFICADO]
  2. Roadmap `UCO_SENSOR_ROADMAP.md:186-188` lista SSRF/XXE como gaps CRÍTICOS não-cobertos. [VERIFICADO — documento próprio]
  3. `sast/taint_engine.py` existe (FlowVector), mas as regras de sink SSRF/deserialization não estão na lista de `_ASTScanner` (scanner.py:863). [VERIFICADO]
- **COMO SUGERE FAZER**:
  - Adicionar SAST044 (pickle/marshal/shelve loads de fonte tainted, CWE-502), SAST045 (`yaml.load` sem `SafeLoader`), SAST046 (SSRF: `requests`/`urllib`/`httpx` com URL tainted, CWE-918), SAST047 (XXE: `etree.parse` sem `resolve_entities=False`).
  - Conectar ao `taint_engine` para reduzir falsos positivos (sink só conta se a fonte for tainted).
- **IMPACTO**:
  - Antes: 0 regras dedicadas a 4 classes CWE de alto impacto no scanner Python.
  - Depois (estimado): +4 CWEs (502/918/611) cobertas; cobertura de OWASP-relevant Python rules estimada de ~70% para ~85% vs Bandit/Semgrep baseline.
- **DEBATE**:
  - 🧪 SAST: CONFIRM — "deserialization e SSRF são top-tier; Bandit (B301/B506) já cobre, ficamos atrás."
  - 📊 Data Scientist: parcial REFUTE — "sem o taint_engine ligado, SSRF tem FP alto (todo `requests.get` flagga). Recomendo gate por taint." → escopo ajustado, não derruba.
  - **Resolução**: CONFIRMED por 1 a 0 com ajuste de escopo (gate por taint_engine para SSRF). Data Scientist confirma após reformulação.

---

## §4. Quick-Wins (alto ROI, ≤ 1 dia cada)

| # | Item | ROI | Effort | Arquivo:linha | Justificativa em 1 linha |
|---|---|---|---|---|---|
| 1 | Reusar `analyze_pattern` no `_has_redos_shape` | ★★★★ | 0.5d | `governance/marketplace.py:50-63` | Elimina DRY + fecha família `(X+)+` de ReDoS. [VERIFICADO] |
| 2 | `cache_invalidate(module)` após cada `_store.insert` | ★★★★ | 0.5d | `api/server.py:735,960,2677` | Corrige staleness de 30-120s em dashboards. [VERIFICADO] |
| 3 | Sincronizar badges README ↔ pyproject | ★★★★ | 0.2d | `README.md:5-8` vs `pyproject.toml:7` | Versão exibida 3 majors atrás (0.4.0 vs 3.9.1). [VERIFICADO] |
| 4 | Charge pós-2xx em `_billed_dispatch` | ★★★★ | 1d | `api/server.py:1900-1910` | Para over-charge em 500. [VERIFICADO] |
| 5 | Sweep `ruff F401` (42 unused imports) | ★★★ | 0.5d | backlog `inventario.md:116` | -200 LOC, melhora dead-code signal. (deferred existente) |
| 6 | Restart-on-die do background thread `cache.py` | ★★★ | 0.3d | `inventario.md:120` (silent thread death) | Resiliência; finding gate-2b deferred. (deferred existente) |
| 7 | `Event.wait()` no consumer loop vs `sleep` | ★★★ | 0.5d | backlog `inventario.md:122` | -50ms p99 (estimado). (deferred existente) |
| 8 | Cache TTL ~5s em `predictor_accuracy` | ★★★ | 0.3d | `inventario.md:135` quick-win | Hot path de dashboard. (deferred existente) |
| 9 | Bound de commits em scan histórico | ★★★ | 0.3d | `scan/git_history_scanner.py` | Evita varredura full-history não-limitada. [VERIFICADO] |
| 10 | Gate por taint em SAST007/011 (insecure random/path) | ★★★ | 1d | `sast/scanner.py` + `sast/taint_engine.py` | Reduz FP citado no roadmap §3.1. [VERIFICADO] |
| 11 | Índice `(tenant_id, status_code, period_key)` em usage_events | ★★★ | 0.3d | `snapshot_store.py:611-624` | `sum_units_for_period` filtra status_code<300 sem índice composto. [VERIFICADO] |
| 12 | Validar `soft_limit_pct` ∈ [0,100] em update_tenant | ★★ | 0.3d | `governance/tenancy.py:102-144` | Sem clamp; `soft_limit_pct=900` quebra soft_warn. [VERIFICADO] |
| 13 | Documentar `UCO_INCLUDE_TRACE` no README env table | ★★ | 0.2d | `README.md:199-208` | Var existe (`server.py:316`) mas não documentada. [VERIFICADO] |
| 14 | Port-allocator nos testes restantes (xdist) | ★★ | 1d | `inventario.md:139` | Habilita testes paralelos. (deferred existente) |

---

## §5. Novos Canais de Métrica

### Canal 1 — `secret_density_history`
- **Categoria**: novo
- **Sinal**: nº de segredos de alta entropia detectados no histórico do módulo, normalizado por LOC tocadas.
- **Fórmula**: `secret_density = secrets_found_in_blame / max(loc_touched, 1)`
- **Fonte de dados**: precisa adicionar (depende do Finding #6 secrets-in-history); reusa `git_history_scanner`.
- **Correlação esperada com canais existentes**: BAIXA — ortogonal a H/CC/APS; é sinal de segurança, não de complexidade. Justifica novo canal (não-redundante).
- **Custo**: ~120 LOC + regex table; sem dep nova.
- **Back-fill**: SIM se git disponível; reprocessa histórico. Snapshots sem source não retro-calculam.
- **Debate (Data Scientist vs Architect)**: DS — "não correlaciona com nenhum canal existente, logo agrega sinal real". Architect — "depende de git no runtime; isolar atrás de feature flag." CONFIRMED.

### Canal 2 — `forecast_error_realized` (ativação de canal dormente)
- **Categoria**: existing-but-dormant
- **Sinal**: erro real do forecast: `predictor_forecast_next[t]` vs `hamiltonian[t+1]`.
- **Fórmula**: `forecast_error = |predictor_forecast_next(row_t) − hamiltonian(row_{t+1})| / max(hamiltonian(row_{t+1}), ε)`
- **Fonte de dados**: JÁ EXISTE — `predictor_forecast_next` e `predictor_confidence` são colunas persistidas (`snapshot_store.py:85-86,118-119`), mas o erro realizado não é materializado como canal próprio.
- **Correlação esperada**: MÉDIA com `predictor_confidence` (por construção). Justificativa: confidence é a-priori; error é a-posteriori — meta-sinal de calibração do modelo, raro no mercado.
- **Custo**: ~40 LOC (já há backfill de `forecast_error` mencionado no roadmap LEAP 4).
- **Back-fill**: SIM totalmente — todas as colunas necessárias já estão persistidas; cômputo puro sobre pares (t, t+1).
- **Debate (DS vs Architect)**: DS — "canal de calibração é o que diferencia de SonarQube; já temos os dados". Architect — "zero novo schema, só uma view derivada; baixo risco". CONFIRMED.

### Canal 3 — `cross_tenant_module_collision_count`
- **Categoria**: novo (operacional)
- **Sinal**: quantos `(module_id, commit_hash)` colidem entre tenants — métrica de saúde do isolamento (Finding #1).
- **Fórmula**: `collisions = COUNT(*) GROUP BY module_id, commit_hash HAVING COUNT(DISTINCT tenant_id) > 1`
- **Fonte de dados**: precisa adicionar (depende da coluna tenant_id do Finding #1).
- **Correlação esperada**: BAIXA — sinal operacional, não de qualidade de código.
- **Custo**: ~20 LOC (1 query).
- **Back-fill**: N/A (só faz sentido pós-migração tenant_id).
- **Debate (DS vs Architect)**: DS — "sinal de monitoramento, não de produto; talvez melhor como alerta que como canal". Architect — "concordo, é telemetria ops". DOWNGRADED para alerta interno, não canal de cliente.

### Canal 4 — `entropy_token_shannon` (Research Track do roadmap)
- **Categoria**: novo (já planejado roadmap §4.3 M9.1, não implementado)
- **Sinal**: entropia de Shannon do histograma de tokens do source — proxy de "ruído"/obfuscação.
- **Fórmula**: `H = −Σ p(token)·log₂ p(token)` sobre o histograma de tokens.
- **Fonte de dados**: JÁ EXISTE (source disponível no insert); falta o cômputo. Roadmap aponta `metrics/entropy.py` (módulo a criar).
- **Correlação esperada**: MÉDIA-ALTA com Halstead (ambos derivam de contagem de tokens). RISCO de redundância — validar antes de persistir.
- **Custo**: ~60 LOC; sem dep.
- **Back-fill**: SIM se source persistido; senão não.
- **Debate (DS vs Architect)**: DS — "ALERTA: alta correlação com Halstead vocabulary (n1+n2). Antes de adicionar, medir ρ; se ρ>0.8 não vale o canal". Architect — "concordo, é candidato a redundância". CONFIRMED como canal *condicional* (só persistir se ρ<0.7 medido).

### Canal 5 — `license_risk_score`
- **Categoria**: novo
- **Sinal**: risco de licença agregado das dependências (copyleft viral em projeto permissivo, etc.).
- **Fórmula**: `license_risk = Σ_dep weight(license_class) / n_deps`, onde GPL/AGPL=1.0, LGPL=0.5, MIT/Apache=0.0, unknown=0.7.
- **Fonte de dados**: precisa adicionar (license compliance scanner — ver §6 novos scanners); reusa parsers de manifest do SCA.
- **Correlação esperada**: BAIXA — ortogonal a tudo. Sinal de compliance, não de qualidade.
- **Custo**: ~150 LOC + tabela SPDX de licenças; sem dep (parse de manifests já existe no SCA).
- **Back-fill**: parcial — depende de ter manifests versionados.
- **Debate (DS vs Architect)**: DS — "sinal novo e demandado por enterprise". Architect — "reusa parsers do SCA, baixo acoplamento novo". CONFIRMED.

---

## §6. Novos Scanners / Melhorias de Scanners Existentes

### SAST (melhorias)
- **Classe de defeito**: deserialization, SSRF, XXE (ver Finding #9).
- **3 exemplos de regra**: SAST044 `pickle.loads(tainted)` (CWE-502); SAST046 `requests.get(tainted_url)` (CWE-918, gate por taint); SAST047 `etree.parse` sem `resolve_entities=False` (CWE-611).
- **Cobertura atual estimada**: ~70% das classes OWASP-Python comuns (32 regras, sem deserialization/SSRF/XXE dedicadas). [VERIFICADO contagem]
- **Cobertura pós**: ~85% (estimado).
- **Competidores**: Bandit cobre B301 (pickle), B506 (yaml.load); Semgrep `python.requests.security.disabled-cert-validation`; CodeQL `py/unsafe-deserialization`. Capability concreta deles ausente aqui: **pickle deserialization de fonte não-confiável**.

### SCA (melhorias)
- **Classe**: cobertura de CVEs por ecossistema (roadmap §3.2 lista metas).
- **3 exemplos**: expandir pip (Werkzeug/Celery/SQLAlchemy), npm (jsonwebtoken/express), maven (Spring Boot/Tomcat).
- **Cobertura atual**: 205 CVEs / 12 ecossistemas (CHANGELOG). [VERIFICADO — doc]
- **Cobertura pós**: 200+→300+ (roadmap target).
- **Competidores**: Snyk/OSV têm feeds vivos; capability ausente: **resolução transitiva de dependências** (UCO casa por nome de pacote direto, não resolve árvore transitiva). [HIPÓTESE — não confirmei o resolver, requer leitura de `vulnerability_scanner.py`]

### IaC (melhorias)
- **Classe**: regras de hardening cloud (roadmap §3.3 lista 40+ novas).
- **3 exemplos**: IAC-T017 EC2 sem IMDSv2; IAC-K015 `automountServiceAccountToken: true`; IAC-D013 `curl | bash`.
- **Cobertura atual**: 102 regras / 8 formatos. [VERIFICADO — doc]
- **Competidores**: Checkov tem 1000+ políticas; capability ausente: **graph-based cross-resource** (ex.: SG aberto + EC2 público + sem WAF como finding composto).

### Novos scanners
1. **Secrets-in-history** (Finding #6) — cobre CWE-798/540; reusa git_history_scanner; competidor gitleaks/trufflehog. Cobertura atual 0% → ~80% das famílias de token (estimado).
2. **License compliance** — cobre risco SPDX; reusa parsers de manifest do SCA; competidor FOSSA/Snyk License. Cobertura atual 0%. Alimenta Canal 5.
3. **SBOM (CycloneDX/SPDX)** — gera SBOM a partir dos manifests já parseados pelo SCA; cobre supply-chain/SLSA provenance; competidor Syft/cdxgen. Cobertura atual 0%. Endpoint `GET /sbom?format=cyclonedx`.

---

## §7. Tecnologias Emergentes — Synergy Map

### Tecnologia 1 — CycloneDX SBOM (spec 1.6, 2024)
- **O que adiciona**: bill-of-materials assinável de dependências + componentes.
- **Como se integra**: novo `report/sbom.py` consumindo o parser de manifests do `sca/vulnerability_scanner.py`; endpoint `GET /sbom`. Conecta o SCA existente a SLSA/supply-chain.
- **Maturidade**: production-ready (CycloneDX é OWASP, amplamente adotado).
- **Custo**: ~150 LOC; dep opcional `cyclonedx-python-lib` OU emitir JSON puro (sem dep nova).
- **Multiplicador esperado**: habilita compliance enterprise (gate de procurement); "1x→N" em deals enterprise que exigem SBOM.
- **Debate (Innovation vs Architect)**: Innov — "SBOM é requisito de procurement 2025+". Architect — "emitir JSON CycloneDX sem dep mantém o princípio 'stdlib-only' do server". CONFIRMED, JSON puro.

### Tecnologia 2 — OPA/Rego (policy-as-code)
- **O que adiciona**: políticas de gate declarativas e versionáveis em vez do `policy_engine.py` hardcoded.
- **Como se integra**: `governance/policy_engine.py` ganha um backend Rego opcional; gate de PR avalia política Rego sobre os canais. 
- **Maturidade**: production-ready (CNCF graduated).
- **Custo**: ~200 LOC + dep `opa` binário externo (nova dep, externa ao Python).
- **Multiplicador esperado**: políticas customizáveis por tenant sem redeploy.
- **Debate (Innovation vs Architect)**: Innov — "policy-as-code é demanda clara". Architect — "REFUTE parcial: dep de binário externo viola o 'zero deps extras' do server; melhor um mini-DSL interno antes de OPA". DOWNGRADED para mini-DSL interno como passo 1.

### Tecnologia 3 — RAG embeddings sobre fingerprints espectrais
- **O que adiciona**: busca semântica "encontre módulos com assinatura de degradação parecida com X" via vetores.
- **Como se integra**: o `fingerprint_index.py` já produz vetores de 5 canais + 3 métricas de distância; um índice vetorial (sqlite-vss ou numpy brute-force) sobre os fingerprints habilita `/similar` semântico em escala.
- **Maturidade**: beta (sqlite-vss) / production-ready (numpy brute-force já viável).
- **Custo**: ~80 LOC com numpy (já dep); 0 dep nova no caminho brute-force.
- **Multiplicador esperado**: `/similar` escala de O(n) linear para sublinear com índice (estimado 5-10x em repos com >5k módulos) [BENCHMARK NECESSÁRIO].
- **Debate (Innovation vs Architect)**: Innov — "os vetores já existem, é fruto baixo". Architect — "concordo, brute-force numpy sem dep nova é o caminho seguro". CONFIRMED (brute-force numpy primeiro).

### Tecnologia 4 — SLSA provenance (v1.0, 2023)
- **O que adiciona**: atestados de proveniência de build verificáveis.
- **Como se integra**: o `ci/action_entrypoint.py` (GitHub Action) emite atestado SLSA junto do SARIF; canal `provenance_verified` no gate.
- **Maturidade**: production-ready (SLSA v1.0 estável).
- **Custo**: ~100 LOC no entrypoint CI; sem dep nova (usa GitHub OIDC).
- **Multiplicador esperado**: fecha a história supply-chain (SBOM + secrets-history + SLSA = stack completo).
- **Debate (Innovation vs Architect)**: Innov — "complementa SBOM". Architect — "é CI-only, baixo blast-radius no core". CONFIRMED.

---

## §8. Reflexão Arquitetural — Tensões Estruturais

**1. `api/server.py` é um god-module de 5337 LOC.** Concentra roteamento, autenticação, billing dispatch, 70+ handlers, helpers de sanitização e a classe `BaseHTTPRequestHandler`. O `do_POST` é uma cadeia de `elif path == ...` com 30+ ramos (server.py:4976-5127). Cada novo endpoint engrossa o mesmo arquivo. A tensão: o produto cresce por adição de endpoints, e este arquivo é o ponto de fricção de todo merge. Recomendação estrutural (não-bug): extrair um `Router` com registro decorator-based (`@route("/analyze", billed="snapshot")`) que mova handlers para módulos por domínio. Sem isso, v5.0 com ~120 endpoints terá um server.py de ~8000 LOC — o tipo de god-class que o próprio UCO detecta (`GOD_CLASS_FORMATION`, README:217). É ironia auto-referente que vale endereçar.

**2. O Lock global é uma abstração vazada do modo `:memory:`.** O `threading.Lock()` foi correto para a conexão compartilhada de `:memory:` (testes), mas vazou para o modo file de produção, onde WAL + conexões thread-local já dariam concorrência de leitura. O resultado é que a decisão de teste pena a produção (Finding #3). Esta é dívida técnica oculta: nada quebra, os testes passam, mas o teto de throughput está fixado num detalhe de implementação de testes. A separação correta seria um `StorageBackend` abstrato com duas implementações (in-memory-locked vs file-WAL), em vez de ramificar com `if self._in_memory` espalhado.

**3. O multi-tenant é uma meia-abstração.** Tenancy e billing foram modelados de forma exemplar (atomic charge, bypass invariants, SY-FIX-1..7), mas a fronteira do tenant para por aí — não atravessou para a camada de dados de produto (Finding #1). Isto cria uma falsa sensação de isolamento: o código *parece* multi-tenant (há `resolve_tenant_from_api_key`, há `_billed_dispatch`), mas o `tid` resolvido é usado só para débito, descartado antes do handler. É o pior tipo de abstração vazada: a que dá a impressão de garantia que não entrega. Evolutivamente, retrofitar `tenant_id` em 5 tabelas com dados já gravados é caro — quanto mais tempo passa, mais linhas `'default'` para migrar.

**4. Duplicação de lógica como anti-padrão recorrente, já reconhecido mas não erradicado.** A Sprint H (`signals.py:1-16`) documenta como a duplicação OLS+Hurst escondeu o bug C-2. O mesmo padrão reaparece em `_has_redos_shape` (Finding #5): existe o analisador correto (`regex_analyzer`) e uma cópia degradada (blocklist de substring). O sistema tem a disciplina de criar SSOTs (channels.py, signals.py) mas não um mecanismo que *impeça* novas cópias divergentes de nascerem. Um lint customizado ("nenhum guard de ReDoS fora de regex_analyzer") fecharia a classe.

**5. Risco evolutivo do paper vs realidade.** O `paper/experiments.md` honestamente marca o corpus como "TBD" e o T3 usa `serial_batches` em vez de "concurrency" por honestidade (CHANGELOG:90). Isto é louvável, mas significa que as claims de throughput multi-tenant do paper são, hoje, não-validadas concorrentemente — exatamente onde o Lock global (Finding #3) morde. Se o paper for submetido com números seriais apresentados como concorrentes, é um risco de integridade científica. O Finding #3 e o paper estão acoplados: validar concorrência exige resolver o Lock primeiro.

---

## §9. Roadmap Proposto

| Versão | Foco | Items (links §3/§4/§5/§6) | Effort total | Riscos |
|---|---|---|---|---|
| **v3.9.2** | Correções de correção + quick-wins | #4 (cache invalidate), #5 (ReDoS reuse), #7 (README), #2 (charge pós-2xx), QW#11/#12/#13, deferred backlog (N+1 #8, hot-row) | ~6-8 pd | Charge-reorder pode mexer em testes de billing; mitigar com pins. |
| **v4.0.0** | Multi-tenant real + secrets scanner | #1 (tenant_id isolation, P0), #6 (secrets-in-history), Canal 1, Canal 2 (forecast_error dormante) | ~12-16 pd | Migration de 5 tabelas; risco de query miss → exigir `_scoped` helper (Architect). |
| **v4.1.0** | Concorrência + SAST expansion | #3 (lock refactor read-only), #9 (SAST044-047), Canal 4 (entropy condicional) | ~10-14 pd | Lock refactor exige benchmark (bench/benchmark.py) antes/depois; risco de regressão de correção. |
| **v5.0.0** | Supply-chain + arquitetura | SBOM CycloneDX (§7.1), License compliance (§6/Canal 5), SLSA (§7.4), RAG fingerprint (§7.3), extração de Router do god-module server.py (§8.1) | ~20-30 pd | Reescrita de roteamento é blast-radius alto; fazer incremental com testes de paridade. |

Priorização justificada: v3.9.2 entrega correções baratas de bugs de correção silenciosos (cache stale, over-charge, ReDoS) com ROI imediato. v4.0.0 ataca o P0 (isolamento) que é bloqueador de GA de SaaS — não pode esperar. v4.1.0 destrava o teto de performance e fecha gaps SAST competitivos. v5.0.0 é a aposta estratégica de supply-chain + a dívida arquitetural do god-module.

---

## §10. Métricas de Validação do Próprio Relatório

- Findings raw propostos antes do debate: **34** (9 principais P0/P1 + 14 quick-wins + 5 canais + 4 tech + 2 refuted no anexo)
- Findings CONFIRMED: **27** (9 principais + sub-itens confirmados de §5/§6/§7)
- Findings DOWNGRADED: **4** (#3 escopo→read-only, #7 Architect P2-em-rigor, Canal 3→alerta, OPA→mini-DSL)
- Findings REFUTED: **2** (ver Anexo A)
- Citações `file:line` totais: **~58**
- Citações que verificam (rodando grep/Read agora): **>95%** — marcadas [VERIFICADO]; exceções marcadas [HIPÓTESE]/[BENCHMARK NECESSÁRIO]
- Hipóteses não validadas: **4** ([HIPÓTESE] resolver transitivo SCA; [BENCHMARK NECESSÁRIO] lock throughput, RAG sublinear, predictor cache) — todas marcadas (ver Anexo C)
- Itens do backlog deferred citados (anti-duplicação): **N+1 recompute_derived_pending** (inventario.md:298), **hot-row contention tenants.units_used** (inventario.md:269/318), **42 unused-imports ruff F401** (inventario.md:116), **silent thread death cache.py** (inventario.md:120), **sleep→Event.wait** (inventario.md:122) — 5 referenciados.

---

## Anexo A — Refuted Findings

### Refuted #1 — "atomic_check_and_charge tem TOCTOU residual"
- **Quem propôs**: 🔒 Security (hipótese inicial).
- **Quem refutou + argumento decisivo**: ⚡ Performance + 🏛️ Architect. O método (snapshot_store.py:702-746) faz SELECT + UPDATE dentro de um único `with self._lock:` e o SQLite roda em autocommit com `BEGIN IMMEDIATE` implícito no write. Não há janela entre o read e o UPDATE — o Lock Python serializa e a conexão é a mesma. O SY-FIX-4 já endereçou exatamente isto. Argumento decisivo: não há ponto onde dois callers observem o mesmo `units_used` pré-charge.
- **Por que registrar**: documenta que o billing atômico está correto — evita que uma auditoria futura re-levante o mesmo falso-positivo. Anti-padrão a evitar: confundir "billing antes do handler" (real, Finding #2) com "race no charge" (inexistente).

### Refuted #2 — "invariant I3 vacuamente verdadeiro é um bug"
- **Quem propôs**: 🧪 Test Strategist (lente SAST/correctness).
- **Quem refutou + argumento decisivo**: 📊 Data Scientist + 🏛️ Architect. O `invariant_i3_hmc_convergence` (invariants.py:158-162) retorna True quando `status != "OK"` por *design documentado* — statuses de desistência (ERROR/TIMEOUT/REJECTED) não devem reivindicar convergência. A vacuidade é a semântica correta: não afirmamos uma violação que não podemos observar (None h_initial). Argumento decisivo: o docstring (invariants.py:153-156) e o teste TW (positive/negative/edge) cobrem isto intencionalmente.
- **Por que registrar**: vacuidade intencional ≠ teste tautológico. A distinção importa porque o gate-2 (G2-7) corrigiu tautologias *reais* (test_marco_m48); confundir as duas levaria a "corrigir" código correto.

---

## Anexo B — Debate Transcripts Completos (top-5 controversos)

**B.1 — Finding #1 (multi-tenant isolation).** Security abriu: "schema sem tenant_id em snapshots = IDOR de nível de banco; P0 inegociável." Architect contestou o *escopo*, não a severidade: "P0 sim, mas a refutação honesta é: quantos deploys são realmente multi-tenant hoje? Se 100% são single-tenant com bypass 'default', o risco materializado é zero *agora*." Product respondeu com o steelman invertido: "o CHANGELOG e o roadmap (v3.8.0) *vendem* multi-tenant SaaS como entregue; o momento em que o segundo tenant pago entra, vaza. Não podemos anunciar GA sem isto." Data Scientist adicionou: "e a chave UNIQUE global (snapshot_store.py:87) significa que o segundo tenant *corrompe* dados do primeiro via upsert, não só lê." Architect concedeu: "correto — corrupção é pior que leitura. CONFIRM P0, mas exijo um `_scoped` query helper na implementação senão os 30+ call-sites viram um campo minado de query-miss." Resolução: CONFIRMED 3-0, com requisito de helper. Melhor argumento do dissidente (Architect): risco *atual* baixo em deploys single-tenant — válido, mas não rebaixa P0 dado o claim de produto.

**B.2 — Finding #2 (charge antes do handler).** Performance: "cobra-se via check_and_charge na linha 1901, handler roda na 1910; 500 no meio = cobrado sem entrega." Architect refutou: "cobrar antes é *atomicidade* — sob a mesma lock, evita TOCTOU de quota. Inverter para pós-handler reabre a janela que o SY-FIX-4 fechou." Security fez o steelman do ataque: "denial-of-budget — input que 500a + hmc_repair=20un drena FREE em 5 hits; é exploração, não teoria." Architect reconsiderou: "a síntese é pré-*check* (sem débito) antes do handler para 402 cedo, e *charge* após 2xx. Preserva atomicidade E corrige over-charge." Resolução: CONFIRMED 2-0, escopo = split check/charge.

**B.3 — Finding #3 (lock global).** Performance: "1 mutex para todo o store anula o ThreadingHTTPServer." Data Scientist refutou: "SQLite serializa writers de qualquer forma com WAL; o ganho é só em reads. Para o insert hot path, zero." Architect mediou: "verdade — mas reads dominam dashboards (history/trend/accuracy). O Lock em read-paths no modo file é redundante (WAL + thread-local conn já isolam)." Resolução: DOWNGRADED — P1 mantido mas escopo restrito a read-paths; claim de ganho em writes retirado por honestidade. Melhor argumento do dissidente (DS): o teto de write não muda — aceito e incorporado.

**B.4 — Finding #5 (ReDoS reuse).** SAST: "blocklist de substring (marketplace.py:62) é teatro de segurança; `(a+)+` passa." Security confirmou a superfície: "payload de peer não-confiável via /marketplace/import." O contra-argumento tentado por Architect: "o guard de comprimento >2000 já limita o DoS." SAST rebateu: "comprimento não impede backtracking exponencial em string curta — `(a+)+$` com 30 chars já trava." Architect concedeu imediatamente. Resolução: CONFIRMED 2-0. É também quick-win #1 por reusar `analyze_pattern` existente.

**B.5 — Canal 4 (entropy Shannon).** Innovation propôs como sinal de obfuscação. Data Scientist deu o contra-argumento mais forte do relatório: "entropy de token correlaciona fortemente com Halstead vocabulary (n1+n2) — ambos contam diversidade de tokens. Se ρ>0.8, é um canal redundante que infla dimensionalidade sem sinal novo, violando o próprio princípio do roadmap de 'qual canal posso desligar'." Innovation steelman-ou a si mesmo: "justo — então o canal é *condicional*: implementar o medidor, calcular ρ contra Halstead num corpus, e só persistir se ρ<0.7." Resolução: CONFIRMED como canal condicional. Este é o exemplo mais limpo de adversarial steelman do exercício — o proponente refinou a própria proposta sob pressão.

---

## Anexo C — Verificações Pendentes

1. **[HIPÓTESE]** Resolução transitiva de dependências no SCA (§6) — não li `sca/vulnerability_scanner.py` em profundidade; a afirmação de que casa só por nome direto precisa de confirmação antes de agir.
2. **[BENCHMARK NECESSÁRIO]** Ganho de throughput do refactor de Lock (Finding #3) — rodar `bench/benchmark.py` com 8 threads concorrentes, modo file, antes/depois. Hipótese 3-6x em reads não medida.
3. **[BENCHMARK NECESSÁRIO]** Sublinearidade do índice vetorial RAG (§7.3) — medir `/similar` brute-force vs indexado em repo de >5k módulos. Hipótese 5-10x não medida.
4. **[BENCHMARK NECESSÁRIO]** TTL cache em predictor_accuracy (QW#8) — medir latência p99 do endpoint sob carga de dashboard antes de fixar TTL=5s.
5. **[VERIFICADO mas requer corpus]** Correlação ρ(entropy, Halstead) do Canal 4 — exige corpus real (o mesmo TBD do paper/experiments.md) para decidir se o canal é redundante.
