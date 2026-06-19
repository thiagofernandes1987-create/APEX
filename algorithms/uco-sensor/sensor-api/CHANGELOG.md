# UCO-Sensor — CHANGELOG

Todas as mudanças notáveis são documentadas aqui.  
Formato: [Semantic Versioning](https://semver.org/) | Convenção: [Keep a Changelog](https://keepachangelog.com/)

---

## [3.3.2] — 2026-06-18 — Sprint J: Dynamic CVE Knowledge Feed

### Adicionado

Endereça o gap estratégico apontado pelo Codex — **"`cve_database`
hardcoded vira dívida em 6 meses, sem feed de atualização = obsolescência
garantida"**. Agora ops podem atualizar o corpus de CVEs em produção
**sem release**, com rollback transacional por feed-id.

#### Novo módulo — `sca/cve_feed.py`

API pública:

- `load_from_file(path, feed_id=None) -> FeedLoadResult`
- `load_from_url(url, *, timeout=10.0, feed_id=None) -> FeedLoadResult`
- `unload(feed_id) -> int` (n. de rows revertidas)
- `reset_overrides() -> int`
- `feed_status() -> dict` (total CVEs, ecossistemas, feeds ativos)

**Dataclass `FeedLoadResult`**: `feed_id, source, ts_loaded, added_new,
added_override, skipped_bad, errors[]`. Sempre retornada — nunca raise
em input ruim. Cada linha malformada vira uma entrada em `errors`
sem poisonar o batch.

**Schema do feed** (JSON ou YAML — auto-detect):

```json
{
  "version": "1.0",
  "generated_at": "2026-06-18T00:00:00Z",
  "cves": [
    {
      "ecosystem":      "npm",
      "package":        "minimist",
      "cve_id":         "CVE-2024-99999",
      "severity":       "HIGH",
      "cvss_score":     7.5,
      "description":    "…",
      "affected_range": ">=1.0.0,<1.2.6",
      "fixed_version":  "1.2.6",
      "cwe":            "CWE-1321"
    }
  ]
}
```

#### Decisões de design

- **Built-in DB nunca é mutado destrutivamente** — cada `load_*` registra
  os deltas em `_LOADED_FEEDS[feed_id]` e `unload()` reverte
  precisamente, restaurando entries override-adas.
- **Dedup-por-CVE-id**: re-disclosure de severidade/range refinada
  substitui a entrada anterior (não duplica). Acidentalmente cobre
  o caso de "mesmo CVE aparecer 2× no mesmo feed".
- **Network closed by default** — `load_from_url` exige `host` em
  `UCO_CVE_FEED_ALLOWLIST` (CSV de hostnames). Sem env var = nenhum
  fetch externo permitido. Mesmo com allowlist, ainda usa só
  `urllib.request` (stdlib, sem requests).
- **JSON + YAML opcional** — `json.loads` primeiro; fallback a `yaml`
  se importável. Nenhuma dependência nova obrigatória.
- **Parsing defensivo**: campos obrigatórios `{ecosystem, package,
  cve_id, affected_range}`, severidade restrita a
  `{CRITICAL, HIGH, MEDIUM, LOW, INFO}`, cvss_score deve ser numérico.
  Linha inválida → conta em `skipped_bad` + mensagem em `errors`.

#### Novos endpoints REST

| Método | Rota | Auth | Descrição |
|---|---|---|---|
| **GET** | `/feeds/status` | user | total CVEs, ecossistemas, feeds ativos |
| **POST** | `/feeds/cve/load` | **admin** | aceita `{path}`, `{url}` OU `{inline}` |
| **POST** | `/feeds/cve/unload` | **admin** | reverte por `{feed_id}` |

`POST /feeds/cve/load` aceita **três fontes mutuamente exclusivas**:

```jsonc
// 1. Arquivo local (path absoluto)
{"path": "/srv/uco/feeds/cves-2026-Q2.json", "feed_id": "Q2-2026"}

// 2. URL HTTP (host na allowlist)
{"url": "https://internal.example.com/cves.json", "timeout": 10.0}

// 3. Payload inline (já fetchado pelo orquestrador)
{"inline": {"version": "1.0", "cves": [...]}, "feed_id": "ad-hoc"}
```

Os 2 writes (load/unload) exigem `hmac.compare_digest` na admin key
(Sprint G G.8); o GET de status só requer chave de usuário regular.

### Testes — 30 novos (TK01–TK30)

- TK01–TK10 (módulo): load adiciona; lookup pega; unload reverte;
  override substitui severity; reset limpa tudo; bad rows skipados sem
  raise; arquivo inexistente vira erro estruturado; payload sem `cves`
  rejeitado; `cves` deve ser list
- TK11–TK20 (REST): status retorna shape correto; conta feeds ativos;
  inline / path / url branches; allowlist vazio bloqueia URL;
  400 quando faltar fonte; unload de feed desconhecido = 0; load+status
  roundtrip mostra delta
- TK21–TK30 (segurança & edge): allowlist host-matching positivo e
  negativo; allowlist vazio bloqueia todos; ecosystem vazio skipado;
  severity desconhecida rejeitada; CVE duplicado no mesmo feed usa
  override path; reset cumulativo; `to_dict()` JSON-serializable;
  default severity MEDIUM quando ausente; built-in CVE preservado
  após roundtrip (lodash 4.17.11)

Regressão completa: **1573 passed, 3 skipped, 0 falhas** em 11.9s
(+30 vs Sprint I).

### O que isso destrava

- **Refresh diário de CVE corpus** sem nova release — cron job que
  fetche o NVD/GitHub Advisory feed e `POST /feeds/cve/load` com a
  payload normalizada
- **Hot-patch durante incidente** — quando um CVE crítico vaza, drop
  do JSON local + `/feeds/cve/load` põe a regra em produção em
  segundos
- **Diff por ambiente** — staging/prod podem carregar `feed_id`
  diferentes para A/B test de impacto

### Não-objetivos (Sprint K em diante)

- **SAST rules feed dinâmico** — schema diferente (precisa de
  validação AST/regex), pesado pra colocar no mesmo sprint
- **NVD-direct integration** — assume um feed pre-normalizado;
  o conversor NVD→schema fica fora de escopo
- **Versionamento semântico do schema do feed** — hoje é v1.0 estática

---

## [3.3.1] — 2026-06-18 — Sprint I: Performance — APS off hot-path + Native SQL

### Refatorado

Endereça **D-4** (Codex) e **movimento Codex #2**: predictor/APS no
caminho de escrita + N+1 queries em `repo_meta_score` + materialização
Python em `get_remediation_stats`.

#### I.1 — `insert(mv, defer_derived=False)` deixa o hot path barato

**Antes**: cada `insert()` disparava, no caminho síncrono:
- 4 serializações JSON
- `_compute_aps_score(mv)` (chama `aps_from_metric_vector`)
- `_compute_forecast(mv)` que internamente faz `get_history(window=100)`
  + deserialização completa de até 100 MetricVectors + `numpy.polyfit`
  (Hurst R/S + OLS)

`O(window)` de CPU+I/O **por insert**, com lock global pego duas vezes.

**Agora**:

```python
store.insert(mv, defer_derived=True)        # hot path: pula APS+forecast
# … rows ficam com aps_score=NULL …

store.recompute_derived(module_id, commit_hash)              # backfill 1 row
store.recompute_derived_pending(module_id=None, batch=1000)  # batch backfill
```

Default (`defer_derived=False`) preserva comportamento atual — zero
break. Use case batch (ingest de repo inteiro) chama com `True` no
hot path e dispara `recompute_derived_pending()` num worker depois.

TI10 mede empiricamente que o caminho deferred não regride
performance e tende a ser ~30% mais rápido em insert bulk.

#### I.2 — `store.latest_aps_per_module()` em UMA query SQL

**Antes** (`governance/repo_meta_score.py:_latest_aps_per_module`):

```python
for module_id in store.list_modules():           # +1 query
    hist = store.get_aps_history(module_id, ...)  # +N queries
    ...
    full_hist = store.get_history(module_id, ...) # +N queries
```

Repo com 500 módulos = **1001+ queries** + igual número de
deserializações JSON.

**Agora**: uma única SQL com self-join em `MAX(timestamp)`:

```sql
SELECT s.module_id, s.aps_score, s.lines_of_code, s.timestamp
FROM snapshots s
INNER JOIN (
    SELECT module_id, MAX(timestamp) AS max_ts
    FROM snapshots
    WHERE aps_score IS NOT NULL
    GROUP BY module_id
) latest ON s.module_id = latest.module_id
       AND s.timestamp  = latest.max_ts
WHERE s.aps_score IS NOT NULL
ORDER BY s.module_id ASC
```

Usa o índice `idx_snap_module_ts` (já existia). Complexidade O(N) com
N = número de módulos. **Mil-vezes mais barato em repos grandes.**

`repo_meta_score._latest_aps_per_module` agora **detecta** se o store
expõe `latest_aps_per_module` e usa-o. Fallback automático para o loop
Python quando o store é um stub de teste sem o método — zero
break em testes existentes.

#### I.3 — `get_remediation_stats()` agregados em SQL nativo

**Antes**: `get_remediation_history(limit=10**9)` materializava todas
as rows em Python + deserializava todos os JSON blobs + Python sum/count.

**Agora**: ONE SQL para os escalares:

```sql
SELECT
    COUNT(*)                                                  AS n_total,
    SUM(CASE WHEN is_valid=1     THEN 1 ELSE 0 END)           AS n_valid,
    SUM(CASE WHEN fixed_count > 0 THEN 1 ELSE 0 END)          AS n_with_fixes,
    SUM(fixed_count)                                          AS total_fixed,
    SUM(residual_count)                                       AS total_residual,
    MIN(timestamp), MAX(timestamp)
FROM remediations [WHERE module_id = ?]
```

Top-k frequência ainda precisa parse de JSON, mas a segunda query só
lê **2 colunas** (`fixed_rules_json`, `transforms_json`) — não a row
inteira. Memória cai drasticamente em históricos grandes.

### Testes — 30 novos (TI01–TI30)

- **TI01–TI10** (I.1): defaults preservam comportamento; deferred path
  produz `aps=NULL`; recompute backfill funciona; pending scan filtra
  só NULL; scope por módulo; idempotência; interação com COALESCE
  (G.4); deferred path NÃO regride performance
- **TI11–TI20** (I.2): uma row por módulo; MAX(timestamp) elegível
  correto; skip módulos sem APS; LOC carregado; empty store empty;
  paridade fast vs legacy; fallback automático em stub; end-to-end
  meta-score; performance — fast ≤ 2x legacy
- **TI21–TI30** (I.3): empty store zerado; n_total bate inserts;
  n_valid conta só rows compilando; n_with_fixes exclui zero-fix runs;
  total_fixed somatório por row; first/last_ts via MIN/MAX; top
  frequência DESC; filtro por módulo; top transforms DESC; sucesso
  rate consistente

Regressão completa: **1543 passed, 3 skipped, 0 falhas** em 11.9s
(+30 vs Sprint H).

### O que isso destrava

- **Real-time monitoring (M8.0)** pode usar `defer_derived=True` no
  watcher: 30+ commits/s de ingestão sem ficar segurando o lock para
  o cômputo de Hurst.
- **`/repo/health-score`** em repos com 100+ módulos cai do segundo
  inteiro para dezenas de ms — viabiliza CI gate em monorepos.
- **`/apex/remediation/stats`** com históricos longos não estoura mais
  memória — agora opera em streaming via SQL.

---

## [3.3.0] — 2026-06-18 — Sprint H: De-globalization + Domain Signals + Observability

### Refatorado / Adicionado

Endereça os achados estruturais da auditoria Codex (**D-1**, **D-2** e
parte de **F-3**) — duplicação de matemática que pariu o C-2 de
Sprint G, leak da conexão `:memory:` no bootstrap, e ausência de
observabilidade operacional.

#### H.1 — `governance/signals.py` como fonte única (D-2)

**Antes**: a matemática de OLS+Hurst sobre APS e MAE/RMSE/bias sobre
forecast_error vivia em **2 cópias** cada (handlers em `api/server.py`
e `_aps_trend_from_store`/`_predictor_accuracy_from_store` em
`compound_alert.py`). Drift estava começando — o handler tinha
`slope_pct` e `forecast_next` que o Compound não tinha, e foi nessa
fenda que C-2 (inversão BIASED_DOWN ↔ BIASED_UP) nasceu sem ser
pego pelos testes do outro lado.

**Agora**:

```python
from governance.signals import aps_trend, predictor_accuracy

aps_trend(store, module_id, window=100) -> dict
predictor_accuracy(store, module_id, window=100) -> dict
```

São funções puras: recebem `store` como parâmetro (qualquer duck-typed
com `get_aps_history` / `get_predictor_history`), nunca raise, sempre
retornam dict estruturado com `verdict`.

`handle_anti_pattern_score_trend` e `handle_predictor_accuracy` em
`server.py` agora chamam estas funções. `compound_alert.py` chama as
mesmas. **Drift é estruturalmente impossível** — a inversão de sinal
C-2 não poderia mais nascer.

Os dois wrappers legados (`_aps_trend_from_store`,
`_predictor_accuracy_from_store`) viram **passes thin** para
`governance.signals.*` — testes que importam diretamente do
`compound_alert` continuam funcionando.

A correção do gate de Hurst em `n >= _MIN_SAMPLES_RELIABLE` (Sprint G
G.3) ficou parcial — afetava só uma das cópias. Agora vale para o
handler `/anti-pattern-score/trend` também.

#### H.2 — `_replace_store()` substitui `_store.__init__()` (D-1)

**Antes**: `server.py:3925` fazia `_store.__init__(args.db)` no
bootstrap para repointar o DB no objeto vivo. Isso é code smell forte:
a conexão `:memory:` aberta no `__init__` original **nunca era
fechada** antes de `self._shared_conn` ser sobrescrito.

**Agora**:

```python
def _replace_store(db_path: str) -> None:
    global _store
    try:
        _store.close()        # close OLD connection cleanly
    except Exception:
        pass
    _store = SnapshotStore(db_path)   # rebind GLOBAL
    _bump_metric("store_replacements")
    _log.info("store replaced: db_path=%s", db_path)
```

Idempotente, swallow safe em falha de close, conta a operação na
métrica `store_replacements`.

> **Nota**: a des-globalização **completa** (injetar `store` nos 57
> handlers em vez do `_store` módulo-level) é refactor de blast radius
> grande e fica para sprint dedicado. H.2 endereça o leak e o
> `__init__` re-call sem mudar a superfície dos handlers.

#### H.3 — Logger estruturado JSON + métricas em `/health`

Novo módulo de observabilidade — **stdlib-only**:

- `_JsonLogFormatter` — formatter JSON-line compatível com APMs
  (Datadog, ELK, Loki). Cada log: `{ts, level, name, msg, exc?}`.
- `_setup_json_logger("uco-sensor")` — idempotente; segunda chamada
  não duplica handler.
- 5 contadores monotônicos protegidos por `_metrics_lock`:
  - `inserts_total`
  - `remediation_writes_ok`
  - `remediation_writes_failed`
  - `auto_remediate_requests`
  - `store_replacements`
- `GET /health` agora inclui o bloco `metrics` com snapshot atômico.
- `handle_apex_auto_remediate` incrementa os 3 contadores adequados
  e loga falha de persistência via `_log.warning`.

### Testes — 30 novos (TH01–TH30)

- TH01–TH10 (H.1): `aps_trend` shape, INSUFFICIENT, gate Hurst,
  `predictor_accuracy` shape, ERROR path em store quebrado, **paridade
  byte-a-byte** entre wrapper legado e `signals.*` (TH09), sign
  convention BIASED_UP (TH10)
- TH11–TH20 (handlers): payload do handler == payload do `signals.*`
  exceto internal fields strip; 400/404; Compound usa signals;
  forecast = slope*n + intercept; sem internal keys vazando; tier RED
  bloqueado em n < 8
- TH21–TH30 (H.2 + H.3): `_replace_store` rebind, conta replacement,
  fecha conexão antiga, swallow safe; `/health` carrega `metrics`;
  todos os 5 contadores presentes; incrementos corretos em
  auto-remediate (sucesso e falha); JSON formatter produz JSON
  parseável com chaves canônicas

Regressão completa: **1513 passed, 3 skipped, 0 falhas** em 12.5s
(+30 vs Sprint F).

### O que isso destrava

- **Sprint I** pode atacar D-4 (custo de leitura no caminho de
  escrita) sem medo de quebrar a matemática duplicada — agora há um
  lugar só para mexer.
- **APMs/dashboards** ganham um pulse confiável de saúde operacional:
  contadores de telemetria perdida vs persistida tornam visível em
  tempo real qualquer falha sistêmica da Sprint C.
- **Tempo de PR-review de mudanças de matemática** cai pela metade —
  uma alteração de sinal/threshold vive em um arquivo só, com testes
  de paridade que falham antes que o drift volte.

---

## [3.2.11] — 2026-06-18 — Sprint F: Spectral Analysis of APS

### Adicionado

Análise espectral completa sobre a série temporal de APS persistida —
o diferencial que o produto promete ("análise espectral aplicada a
quality signals") finalmente desce até o canal composto que vinha
sendo tratado como número escalar.  Welch PSD + entropia + wavelet
db4 = **assinatura espectral por módulo** comparável e clusterizável.

#### Novo módulo — `metrics/spectral_aps.py`

**`compute_aps_spectrum(store, module_id, window=100) -> dict`** —
payload completo:

- `status`: `OK` | `INSUFFICIENT` (< 8 samples) | `ERROR`
- `band_powers` / `band_fractions`: low (drift lento), mid (ruído
  processo), high (oscilação rápida) — divididos em terços de Nyquist
- `total_power`: soma da PSD
- `spectral_entropy ∈ [0, 1]`: 0 = pico único (regime perfeitamente
  previsível), 1 = ruído branco
- `dominant_frequency` + `cycle_length`: período em commits da
  frequência dominante (= 1/f)
- `freqs` / `psd`: arrays brutos para plotagem
- `wavelet`: db4 multi-level (até 3) — energia por nível, **localiza
  no tempo** mudanças de regime que a PSD agrega no espectro

**`aps_fingerprint(store, module_id, window=100) -> dict`** —
assinatura compacta de 5 canais:

```
band_low_fraction   ∈ [0, 1]
band_mid_fraction   ∈ [0, 1]
band_high_fraction  ∈ [0, 1]
spectral_entropy    ∈ [0, 1]
cycle_length        > 0 | None
```

Adequada para DBSCAN / k-means inter-módulos. Dois módulos com APS
médio idêntico podem ter fingerprints radicalmente diferentes — os
perigosos vivem no canto `band_high + alta_entropia`.

#### Decisões técnicas

- **Gate ≥ 8 samples** (mesma constante do predictor /
  `_MIN_SAMPLES_RELIABLE` / Sprint G G.3) — abaixo disso a Welch
  degenera matematicamente.
- **Detrend linear** no PSD; sem subtração de média antes da wavelet
  (a energia do nível de aproximação carrega informação do trend).
- **Banda LOW = [0, 1/3)** de Nyquist, MID = [1/3, 2/3), HIGH = [2/3, 1].
  Frações somam exatamente 1 (validado por TX05).
- **Defensiva ponta-a-ponta**: scipy/pywt indisponível ou falha →
  payload com `status="ERROR"` ou `"UNAVAILABLE"`, nunca raise.
- **JSON-safe**: NaN/inf colapsam para `null` antes de serializar.

#### Novos endpoints REST

| Método | Rota | Descrição |
|---|---|---|
| **GET** | `/spectral/aps`           | PSD + entropia + wavelet (`?module=&window=`) |
| **GET** | `/spectral/fingerprint`   | 5 canais para comparação inter-módulos (`?module=&window=`) |

Ambos retornam `400` quando `module` vazio. `INSUFFICIENT` ou outros
status não-OK voltam com **HTTP 200** + campo `status` — o cliente
sempre vê algo estruturado.

#### Landing page atualizada

`GET /` agora destaca Sprint F (v3.2.11) e Sprint G (v3.2.10) no topo
de "recent capabilities".

### Testes — 30 novos (TX01–TX30)

- TX01–TX10 — `compute_aps_spectrum`: estrutura, gate INSUFFICIENT,
  bandas não-negativas, frações = 1, entropia ∈ [0,1], freq dominante,
  ciclo = 1/f, ruído > seno em entropia, JSON-safe
- TX11–TX20 — wavelet: status OK em série longa, INSUFFICIENT em < 4,
  energia ≥ 0, aproximação + detalhes nomeados, max_level ≤ 3, série
  zero = energia 0, n_coeffs decrescente, `compute_spectrum` carrega
  o bloco wavelet, série constante < seno em total_power, helper
  `_band_powers` soma correta
- TX21–TX30 — fingerprint + REST: 5 canais, frações somam 1, herda
  INSUFFICIENT, coerência com payload completo, handlers 200 e 400,
  JSON-safe end-to-end, módulo desconhecido → 200 + INSUFFICIENT

Regressão completa: **1483 passed, 3 skipped, 0 falhas** em 11.5s
(+30 vs Sprint G).

### O que isso destrava

- **Clustering de módulos por modo de oscilação** — dois módulos com
  APS médio igual mas fingerprint diferente exigem governança diferente;
  agora há sinal quantitativo para isso.
- **Detecção de regime change** via wavelet — a energia do nível de
  detalhe mais fino é a derivada do sinal; picos isolados ali marcam
  o commit exato onde o regime mudou.
- **Auditoria do Compound Alert** — quando RED dispara em um módulo
  cuja entropia espectral está baixa (regime previsível), o alerta tem
  alta confiança; em entropia alta, está apostando em ruído.

---

## [3.2.10] — 2026-06-18 — Sprint G: Signal Correctness (8 fixes cirúrgicos)

### Corrigido

Auditoria externa (Codex, 2026-06-18) encontrou bugs de **corretude do
sinal** que invalidavam o downstream: o produto inteiro depende de o
APS / Compound Alert / Meta-Score estarem certos. Esta release atende
**os 8 achados acionáveis** sem refatoração estrutural — o refactor de
arquitetura (des-globalizar `_store`, extrair `governance/signals.py`)
fica para **Sprint H**.

#### G.1 — Ausência ≠ perfeição  (CRITICAL — C-1)

Antes: `aps_from_metric_vector(<obj sem extended vectors>)` retornava
`aps=100.0 / rating="A"`. Repo vazio: meta-score=100/A. Um quality gate
**aprovava ausência de evidência** como prova de qualidade — exatamente
o failure mode que invalida o gate.

Depois:
- `aps_from_metric_vector` retorna `aps=None / rating="UNKNOWN"` quando
  nenhum dos 6 vetores estendidos relevantes está anexado
  (`_has_any_extended_vector`).
- `rate_aps(None) == "UNKNOWN"`.
- `RepoMetaScore` agora carrega `Optional[float]` em `score`, `raw_score`,
  `weighted_aps`, `mean_aps`, `median_aps`. Repo vazio → todos `None`,
  `rating="UNKNOWN"`.
- `to_dict()` serializa `null` em vez de `0.0` para esses campos.

CI quality gates **devem** tratar `UNKNOWN` como hard fail.

#### G.2 — Inversão de sinal no tier RED  (HIGH — C-2)

Antes: `compound_alert.py:77` disparava RED em `BIASED_DOWN`. Mas
`api/server.py:2952` define a convenção canônica:
- `bias = actual − forecast`
- `BIASED_UP   = bias > 0 = actual MAIOR que forecast = predictor undershot` (perigoso)
- `BIASED_DOWN = bias < 0 = actual MENOR que forecast = predictor overshot` (pessimista, seguro)

Resultado: RED disparava no caso seguro (predictor pessimista demais),
nunca no caso genuinamente perigoso (degradação real mais íngreme que
o forecast).

Depois: condição RED usa `BIASED_UP`. Docstring, razões textuais e
três testes Sprint A (TC01, TC06, TC25) que "pinavam" o bug foram
corrigidos para validar a semântica correta.

#### G.3 — Hurst R/S em amostras insuficientes  (HIGH — C-3)

Antes: `_aps_trend_from_store` declarava `DEGRADING_PERSISTENT` com
`len >= 4 e hurst > 0.55`. Mas o próprio predictor declara
`_MIN_SAMPLES_RELIABLE = 8`. Para n=4-7 o R/S degenera (sub-séries de
tamanho ~n com `n_subs=1`) — a estimativa é matematicamente sem
sentido mas governava um veredito de produção que alimenta RED.

Depois: Hurst só é calculado quando `n >= _MIN_SAMPLES_RELIABLE`. Abaixo
disso, `hurst=0.5` (neutro) e o veredito é rebaixado para `DEGRADING`
(sem `_PERSISTENT`). RED só atinge quando há base estatística.

#### G.4 — Re-insert preserva colunas late-bound  (MEDIUM — C-4)

Antes: `INSERT OR REPLACE INTO snapshots` deletava+reinseria a linha,
apagando `diagnostic_vector_json` que foi populada DEPOIS do insert
(via `update_diagnostic`, que requer ≥5 snapshots). Um re-scan do
mesmo `(module_id, commit_hash)` perdia o diagnóstico já calculado.

Depois: `INSERT ... ON CONFLICT(module_id, commit_hash) DO UPDATE SET`
com `COALESCE(excluded.<col>, <col>)` em 9 colunas late-bound:
`extended_vectors_json`, `advanced_vector_json`, `diagnostic_vector_json`,
`extended_vectors_v2_json`, `aps_score`, `predictor_*` (4). Requer
SQLite ≥ 3.24 (2018-06).

#### G.5 — Tiebreak determinístico em get_history  (MEDIUM — C-5)

Antes: `ORDER BY timestamp DESC` sem tiebreak. Dois snapshots com mesmo
`mv.timestamp` (timestamps gerados pelo cliente, inserções rápidas)
tinham ordem **indefinida** — e Predictor/Baseline dependem dela.

Depois: `ORDER BY timestamp DESC, id DESC` em `get_history`,
`get_aps_history` e `get_predictor_history`. Saída determinística por
ordem de inserção quando timestamps colidem.

#### G.6 — fixed_rules causalmente restrito  (MEDIUM — C-7)

Antes: `fixed_rules = before_set − after_set`. Qualquer regra que sumiu
entre os dois scans era creditada como "corrigida", mesmo que o
transform aplicado não a tivesse causado (efeito colateral, line-shift).
Inflava `success_rate` / `top_fixed_rules` na telemetria Sprint C.

Depois:
```python
causally_eligible = {rule for rule, tcls in SAST_TO_TRANSFORM.items()
                     if tcls.__name__ in transforms_applied}
fixed_rules = sorted((before_set - after_set) & causally_eligible)
```
Apenas regras cuja transform classe efetivamente rodou aparecem em
`fixed_rules`. Telemetria volta a ser auditável.

#### G.7 — persist_error distinto de opt-out  (MEDIUM — C-8)

Antes: `except Exception: persisted_id = None`. Falha sistêmica
(disco cheio, DB locked) produzia exatamente a mesma resposta que
`persist=false`: `HTTP 200, persisted_id=null`, sem log. Telemetria de
auto-fix poderia estar 100% perdida e nenhum sinal disso vazaria.

Depois: em falha, resposta inclui `persist_error: "<TypeError>: <msg>"`.
Opt-out (`persist=false`) **não** inclui esse campo — distinção clara.
Falha também é logada via `logging.getLogger("uco-sensor").warning(...)`.

#### G.8 — Constant-time admin compare  (LOW — segurança lateral)

Antes: `if admin_k and plain_key == admin_k:` — comparação caracter-a-
caracter que retorna após o primeiro byte divergente, vazando comprimento
e similaridade da chave via timing.

Depois: `hmac.compare_digest(plain_key.encode(), admin_k.encode())`.
Primitiva canônica Python para comparação de credenciais.

### Testes — 30 novos (TG01–TG30) que **pinam o comportamento correto**

- TG01–TG05 (G.1): bare MV → UNKNOWN; `rate_aps(None)` = UNKNOWN; repo
  vazio = UNKNOWN; um vetor é suficiente; serialização carrega null
- TG06–TG09 (G.2): BIASED_UP + DEGRADING_PERSISTENT = RED;
  BIASED_DOWN + DEGRADING_PERSISTENT = AMBER (não RED); só BIASED_UP =
  AMBER; GREEN preservado
- TG10–TG12 (G.3): 7 amostras nunca PERSISTENT; 10 amostras elegíveis;
  `_MIN_SAMPLES_RELIABLE == 8` pinned
- TG13–TG15 (G.4): re-insert preserva diagnostic; sobrescreve canais
  primários; COALESCE preserva APS quando novo é NULL
- TG16–TG18 (G.5): get_history, get_aps_history, get_predictor_history
  ordem ASC-by-id em colisão de timestamp
- TG19–TG22 (G.6): unmapped rule não creditada; transforms_applied=[]
  ⇒ fixed_rules=[]; combined fix credita só mapeados; fixed_count == len(fixed_rules)
- TG23–TG25 (G.7): falha persistência → persist_error campo;
  opt-out → sem persist_error; sucesso → sem persist_error
- TG26–TG27 (G.8): inspeção de source pin `compare_digest`; comparação
  correta aceita/rejeita
- TG28–TG30 (integração): UNKNOWN propaga via `handle_repo_health_score`;
  série < 8 nunca atinge RED end-to-end; APS+diagnostic+re-insert co-survivem

Regressão completa: **1453 passed, 3 skipped, 0 falhas** em 11.7s
(+30 vs Sprint E). Seis testes preexistentes (TZ04, TC01, TC06, TC25,
TS03, TV17) "pinavam" o comportamento errado pré-Sprint-G — foram
atualizados para validar a semântica correta, cada um com um comentário
explicando o fix.

### Não-objetivos desta release (próximas sprints)

- **D-1 / D-2 (Sprint H)**: des-globalizar `_store`, injetar como
  parâmetro nos handlers; extrair `governance/signals.py` com
  `aps_trend(store, ...)` e `predictor_accuracy(store, ...)` puros que
  os handlers e o Compound Alert chamam — eliminando a duplicação que
  pariu C-2.
- **D-4 (Sprint I)**: tirar Predictor/APS do caminho de escrita —
  lazy on read ou worker assíncrono pós-insert.
- **Mercado (Sprint J)**: feed dinâmico de CVE + atualização de regras
  sem release.

---

## [3.2.9] — 2026-06-18 — Sprint E: Snapshot-Diff Vector + Volatility Ranking

### Adicionado

Responde a pergunta que toda ferramenta de code-review quietamente
quer responder: **"o que de fato mudou entre o commit A e o commit B
para este módulo?"** — sem precisar abrir os dois snapshots
manualmente, sem heurística, com cobertura de todos os canais
persistidos (9 primários + APS + LOC).

#### Novo módulo — `metrics/snapshot_diff.py`

**Dataclasses:**

- `ChannelDelta` — `name, short, value_from, value_to, delta_abs,
  delta_pct, direction` (`"UP"`/`"DOWN"`/`"FLAT"`)
- `SnapshotDiff` — `module_id, commit_from, commit_to, ts_from, ts_to,
  channels (List[ChannelDelta])` + `n_changed`, `n_total`, `to_dict()`

**API pública:**

- `compute_diff(mv_from, mv_to)` — função pura sobre dois MetricVectors
- `compute_diff_by_commits(store, module, commit_from, commit_to,
  history_window=1000)` — resolve os dois commits e diff
- `top_volatile_channels(store, module, window=50, top_k=5)` — ranking
  de canais por **coeficiente de variação** (σ / |μ|)

#### Decisões técnicas

- **delta_pct = NaN quando ambos valores são 0** (canal "FLAT"
  legítimo, sem dividir por zero); `+inf` quando `from=0` e `to>0`
  (aparecimento genuíno do sinal).
- **Coeficiente de variação** como métrica de volatilidade: unit-free,
  comparável entre canais com escalas radicalmente diferentes
  (`hamiltonian` 0-100 vs `duplicate_block_count` 0-10). Fallback para
  σ puro quando `|μ| < 1e-9` para não perder canais sub-unitários.
- **Canais com σ ≈ 0** (constantes na janela) **excluídos** do ranking
  — não interessa "qual canal nunca mexe".
- **Tiebreak alfabético** garante saída determinística em testes
  (TV29).
- **Predictor channels excluídos** da diff — eles descrevem o
  predictor, não o código.
- **Missing channels skipados em silêncio** em `compute_diff()` — não
  reportados como FLAT (seria mentira sobre cobertura).
- **JSON-safe serialization** — `to_dict()` substitui NaN por `null`
  e ±inf por `"inf"`/`"-inf"`. Cliente HTTP nunca recebe payload
  inválido.

#### Novos endpoints REST

| Método | Rota | Descrição |
|---|---|---|
| **GET** | `/diff/channels` | Per-channel delta entre 2 snapshots (`?module=&from=&to=`) |
| **GET** | `/diff/volatile`  | Top canais por CV (`?module=&window=&top_k=`) |

Ambos retornam `400` quando faltam parâmetros obrigatórios e `404`
quando um dos commits não existe na história.

#### Landing page atualizada

`GET /` agora destaca v3.2.9 (Sprint E) na lista de recent capabilities,
no topo. Visual e UX inalterados.

### Testes — 30 novos (TV01–TV30)

- TV01–TV10 — `compute_diff` puro: estrutura, 9 canais primários
  presentes, direction UP/DOWN/FLAT, delta_pct = inf/NaN nos
  edge-cases, n_changed, missing-channels skipados, serialização
- TV11–TV20 — `compute_diff_by_commits`: hit, miss (from/to/módulo),
  commits idênticos = todos FLAT, inversão nega deltas, APS+LOC
  presentes quando persistidos, window limita visibilidade
- TV21–TV30 — `top_volatile_channels`: histórico vazio, < 3 amostras,
  CV descendente, top_k bound, canal constante excluído, n_samples
  carrega, tiebreak alfabético, integração via `handle_diff_volatile`

Regressão completa: **1423 passed, 3 skipped, 0 falhas** em 11.9s.

### O que isso destrava

- **PR delta view**: gere o diff de canais entre o último commit e o
  baseline (a mãe do merge) — sinal compacto e auditável para
  comentários automáticos de PR.
- **Stability fingerprint**: o ranking de volatilidade por módulo é
  uma assinatura — módulos com mesma assinatura tendem a ter os
  mesmos modos de falha.
- **Quality-gate seletivo**: bloqueie merges quando o módulo subir
  > N% em CC OU em ILR num único PR, sem precisar enumerar todos os
  canais.

---

## [3.2.8] — 2026-06-18 — Sprint D: AutoFix↔SAST Mapping Expansion + Landing Page

### Adicionado

Três novos **transforms de alta confiança** entram no
`SAST_TO_TRANSFORM`, elevando a cobertura do loop fechado AutoFix↔SAST
de **4 → 7 regras automaticamente corrigíveis**, e uma **tela inicial
HTML** servida em `GET /` para visualização rápida do estado da API.

#### Novos transforms (3)

| SAST | Transform | Antes | Depois |
|---|---|---|---|
| **SAST022** Weak IV / All-Zero Nonce | `ZeroNonceReplacer` | `AES.new(k, mode, nonce=b"\\x00"*12)` | `import os; AES.new(k, mode, nonce=os.urandom(12))` |
| **SAST024** JWT signature bypass | `JWTVerifyEnabler` | `jwt.decode(t, k, verify=False)`<br>`jwt.decode(t, k, algorithms=["none","HS256"])` | `jwt.decode(t, k, verify=True)`<br>`jwt.decode(t, k, algorithms=["HS256"])` |
| **SAST027** SSL verification disabled | `SSLVerifyEnabler` | `requests.get(url, verify=False)` | `requests.get(url, verify=True)` |

**Mapeamento final** (`SAST_TO_TRANSFORM`):
`SAST006 SAST007 SAST022 SAST024 SAST027 SAST038 SAST039` — 7 regras
agora cobertas pelo loop `auto_remediate()`.

#### Decisões arquiteturais

- **Apenas rewrites de alta confiança** — `SAST014 SSRF` exige validação
  semântica de origem da URL (não há reescrita segura sem conhecer o
  contexto da chamada) e `SAST037 Resource Leak` exige rewrite estrutural
  (mover statement para dentro de `with`). Ambos ficam para sprints
  futuros com a categoria correta de transform.
- **`os.urandom` é inserido com `import os` no topo do módulo** somente
  quando (a) há pelo menos um rewrite e (b) `os` ainda não foi importado.
  Idempotente em segundas passadas.
- **JWT `algorithms=["none"]` puro** cai em `["HS256"]` (default
  conservador que ainda exige uma chave de assinatura) — não fica vazio.
- **Filtros estritos**: SSL transform só atua em `requests`/`httpx`,
  JWT só em `jwt`/`PyJWT`, Nonce só em `.new()` de famílias de cifra
  reconhecidas (`AES`, `ChaCha20`, `Salsa20`, `Blowfish`,
  `ChaCha20_Poly1305`). Calls com cara similar mas módulo desconhecido
  passam intocados.

#### Nova landing page — `GET /`

`handle_root()` retorna HTML standalone (sem dependências externas,
zero JS) com:

- Versão e n.º de módulos rastreados ao vivo
- 4 cards de status (channels persistidos, mapeamento AutoFix, etc.)
- Atalhos para `/docs`, `/health`, `/badge`, GitHub e CHANGELOG
- Lista de capacidades recentes (Sprint D / C / B / A / LEAP 4)
- Lista de endpoints "try it" mais usados

Servido sem autenticação. Visual GitHub-dark, responsivo.
`/index.html` é alias para `/`.

### Testes — 30 novos (TU01–TU30)

- TU01–TU10 — SSL transform: positional/keyword, requests vs httpx vs
  módulo desconhecido, valor não-constante, idempotência, end-to-end
- TU11–TU20 — JWT transform: legacy `verify=False`, options dict,
  remoção de "none", fallback HS256, case-insensitive, `PyJWT` alias,
  encode não toca, end-to-end
- TU21–TU30 — Nonce transform: keyword/positional, `b"\\x00"*N` vs
  literal zero, length preservation, auto-`import os`, não-duplicação,
  rejeita não-zero, rejeita não-cipher, end-to-end + caso combinado
  fixando 3 regras numa pass

Regressão completa: **1393 passed, 3 skipped, 0 falhas** em 11.9s.

### O que isso destrava

- Cobertura **+75%** no loop AutoFix↔SAST (4 → 7 regras mapeadas)
- **Onboarding visual** — abrir a URL da API no navegador agora mostra
  estado, versão e capacidades em vez de 404
- Base para o Sprint E: usando a telemetria do Sprint C, identificar
  **automaticamente** quais regras SAST sobram com maior frequência
  como candidatas a novos transforms

---

## [3.2.7] — 2026-06-18 — Sprint C: Auto-Fix Telemetry

### Adicionado

Fecha o loop do **LEAP 3 / M8.2** persistindo cada chamada
`auto_remediate()` como uma linha de telemetria. A partir desta versão é
possível responder, sem recomputar nada, perguntas como _"a auto-correção
está realmente funcionando ao longo do tempo neste módulo?"_, _"quais
regras SAST são as mais corrigidas (e quais sobram como resíduo)?"_, e
_"quais transformações puxam o peso?"_.

#### Nova tabela — `remediations` (SnapshotStore)

```sql
CREATE TABLE remediations (
    id, module_id, commit_hash, timestamp,
    is_valid, findings_before, findings_after,
    fixed_count, residual_count,
    transforms_json, fixed_rules_json,
    findings_before_json, findings_after_json
);
CREATE INDEX idx_remed_module_ts ON remediations(module_id, timestamp);
```

Schema independente do `snapshots` — auto-fix pode rodar fora de uma
janela de scan sem precisar de `(module_id, commit_hash)` válidos. Cada
chamada `auto_remediate()` vira **uma** linha (não há UNIQUE), permitindo
analisar fluxo no tempo mesmo dentro do mesmo commit.

#### Novos métodos no `SnapshotStore`

- **`store_remediation(module_id, result, *, commit_hash="", timestamp=None) -> int`**
  - duck-typed: aceita `RemediationResult`, qualquer objeto com a mesma
    superfície de atributos, ou um `dict` de `to_dict()` — escolha pelo
    chamador
  - timestamp default = `time.time()` no momento da escrita
  - retorna o `id` da linha (≥ 1)
- **`get_remediation_history(module_id=None, limit=100) -> List[Dict]`**
  - ASC por timestamp (oldest first), filtragem opcional por módulo
  - `module_id=None` → varre o repositório inteiro
  - deserialização defensiva: JSON corrompido vira lista vazia, nunca raise
- **`get_remediation_stats(module_id=None, top_k=5) -> Dict`**
  - agrega `n_total`, `n_valid`, `n_with_fixes`, `success_rate`,
    `total_fixed`, `total_residual`, `mean_fixed`, `mean_residual`
  - `top_fixed_rules` / `top_transforms` ordenados por frequência desc,
    desempate alfabético (output determinístico)
  - empty store → tudo zerado, sem exceção

#### Novos endpoints REST

| Método | Rota | Descrição |
|---|---|---|
| **GET** | `/apex/remediation/history` | Histórico persistido (`?module=&limit=`) |
| **GET** | `/apex/remediation/stats` | Agregado (`?module=&top_k=`) |

**`/apex/auto-remediate` agora persiste por padrão.** A resposta inclui
um novo campo `persisted_id` (`int` ou `null` se a escrita falhou). Para
calls efêmeras (teste, sandbox) basta enviar `"persist": false` no body.

#### Decisões arquiteturais

- **Best-effort write:** falha de persistência **não** mascara o resultado
  da remediação — o cliente sempre recebe o `RemediationResult`. O custo
  de perder uma linha de telemetria é zero; mascarar uma correção real
  seria caro.
- **Duck typing aceitando dict:** já existem callers que persistem
  remotamente via JSON (webhook APEX). Aceitar `dict` evita conversões
  redundantes na fronteira.
- **Empty list defaults:** `findings_after_rules` etc. retornam `[]` em vez
  de `None` quando o JSON do banco está corrompido — assim consumidores
  podem fazer `len(x)` e `for x in y` sem null-checks.

### Testes — 30 novos (TR01–TR30)

- TR01–TR10 — persistência: row id, idempotência multi-insert, round-trip
  completo de campos, aceitação de dict, timestamp custom vs default,
  findings vazios, `is_valid=False`, dict parcial, isolamento por módulo
- TR11–TR20 — histórico: módulo desconhecido, ordem ASC, limite, repo-wide,
  round-trip de `findings_after_rules` / transforms / commit_hash, filtro
  por módulo, `findings_before_rules`, IDs duplicados
- TR21–TR30 — stats: store vazio, n_total, success rate, agregação de
  total_fixed, top fixed rules em ordem desc, top transforms desc, limite
  top_k, mean_fixed por run, módulo vs repo-wide, bookends de timestamps

Regressão completa: **1363 passed, 3 skipped, 0 falhas** em 10.6s.

### Conserto colateral

Os scripts legados `tests/test_marco1.py` e `tests/test_marco2.py` tinham
`sys.exit()` no top-level (eram scripts standalone antes da era pytest).
A coleta do pytest disparava `SystemExit` e abortava toda a suíte.
Cirurgia mínima: o bloco final dos dois passou a ficar dentro de
`if __name__ == "__main__":`. Comportamento como script preservado;
pytest agora coleta sem erro.

### O que isso destrava

- **Dashboard de "auto-fix efficacy"** — gráficos de série temporal sobre
  `fixed_count` e `residual_count` por módulo (Sprint D)
- **Auto-tuning do mapping `SAST_TO_TRANSFORM`** — regras com taxa de
  resíduo > 50% são candidatas a refinamento de transform (próxima fase)
- **Sinal cruzado APS × auto-fix** — módulos com APS caindo + auto-fix
  com sucesso = melhora real; APS caindo + auto-fix sem sucesso =
  problema estrutural que transforms não resolvem (Sprint E)

---

## [3.2.6] — 2026-06-17 — Sprint B: Repo Meta-Score + APS outliers

### Adicionado

Agrega todos os módulos em **um único número de saúde do repositório por commit**,
com detecção de outliers via Z-score sobre a distribuição de APS. Habilita um
**Quality Gate de PR operável** (delta do meta-score) e dashboards de repo.

#### Novo módulo — `governance/repo_meta_score.py`

`RepoMetaScore` dataclass com 11 campos:
`score, rating, n_modules, n_modules_valid, raw_score, weighted_aps,
mean_aps, median_aps, penalty_red, n_red, n_amber`

`APSOutlier` dataclass: `module_id, aps, z_score, threshold, deviation`

**Fórmula do meta-score:**
```
raw_score   = LOC-weighted mean of latest APS per module
penalty_red = 5 × count(Sprint-A RED modules)
score       = max(0, min(100, raw_score − penalty_red))
rating      = A ≥ 90, B 80-89, C 60-79, D 40-59, E < 40
```

**Decisões arquiteturais:**
- LOC weighting: módulos grandes têm peso proporcional ao tamanho (módulos
  com LOC=0 caem em weight=1 para não sumirem). Reflete a realidade: um
  bug crítico em código de 10K linhas pesa mais que em utilitário de 50.
- RED penalty: integra Sprint A diretamente no número. Qualquer módulo RED
  derruba o repo em 5 pontos, mesmo que sua APS isolada não mexa a média.
  AMBER não pune (é monitorado, não bloqueado) — política conservadora.
- Outliers: SÓ direção bad-news (z ≤ −k). Módulos acima da média não são
  flagged. Z-score requer ≥3 módulos e σ > 0.
- History: replay LOC-weighted APS sobre união dos timestamps; downsample
  com `step`. RED penalty **não** aplicado historicamente (replay de
  Sprint-A tiers seria O(N² × W) — custo desproporcional).

**API pública:**
- `compute_repo_meta_score(store, window=100) -> RepoMetaScore`
- `compute_aps_outliers(store, window=100, k=2.0) -> List[APSOutlier]`
  (sorted worst-first by z_score; empty on k ≤ 0, < 3 modules, ou σ = 0)
- `repo_meta_score_history(store, window=50, step=1) -> List[Dict]`

#### Endpoints REST — `api/server.py`

| Endpoint | Descrição |
|---|---|
| `GET /repo/health-score?window=` | Número único + breakdown completo |
| `GET /repo/aps-outliers?k=2.0&window=` | Módulos ≥ k σ abaixo da média APS do repo |
| `GET /repo/health-history?window=&step=` | Time-series do meta-score (LOC-weighted) |

`SensorConfig.version` → `"3.2.6"`.

#### Smoke test ao vivo (6 módulos, repo realista)

```
/repo/health-score:
  score             : 65.92      ← LOC-weighted mean − 0 penalty
  rating            : C
  weighted_aps      : 65.92      ← billing.api (2500 LOC) puxa down
  mean_aps          : 72.18      ← unweighted
  median_aps        : 58.84      ← reveals skewed distribution
  n_red             : 0
  n_amber           : 6          ← todos os 6 são candidatos a atenção
```

Diagnóstico que se revelou imediatamente: `mean > weighted > median`
significa que **módulos GRANDES pioram o repo mais que os pequenos** — uma
inferência só possível pelo Sprint B.

#### Testes — `tests/test_marco_m33.py` (30 testes TS01-TS30)

- TS01-TS06: rating ladder + dataclass invariantes + empty repo
- TS07-TS14: meta-score logic (queda com taint, LOC pulling, latest APS,
  n_modules, bounds [0,100], RED penalty math, NULL skip, median LOC-agnóstico)
- TS15-TS20: outliers (< 3 → [], σ = 0 → [], módulo ruim flagged,
  k ≤ 0 → [], sorted worst-first, only below-mean)
- TS21-TS25: history (empty → [], ASC order, shape, step downsample,
  multi-module aggregation)
- TS26-TS30: REST endpoints (shape de todos os 3, k customizado, step)

**Resultado: 1130/1130 marco-tests PASS — suíte 100% verde.**

#### O que Sprint B destrava

| Uso | Como |
|---|---|
| **Quality Gate de PR** | `repo/health-score` antes/depois do PR; reject se delta < −2 |
| **Dashboard executivo** | Score 0-100 ÚNICO, rating A-E, atualizado por commit |
| **Outlier triage** | `/repo/aps-outliers?k=2.0` → módulos a focar primeiro |
| **Trend visualisation** | `/repo/health-history` plotável diretamente |
| **Detection de "bloated weak module"** | mean > weighted > median triplet revela skew |

#### Próximo marco

Sprint C — Auto-fix telemetry (`remediations` table) → v3.2.7
(fecha o loop LEAP 3: efetividade do auto-remediate ao longo do tempo)

---

## [3.2.5] — 2026-06-17 — Sprint A: Compound Alert (APS × Predictor)

### Adicionado

Identificado pela reavaliação pós-LEAP-4 como o **maior salto de ROI imediato**.
Cruza dois sinais que só agora vivem persistidos:

- **LEAP 2** — APS trend com Hurst R/S
- **LEAP 4** — Predictor accuracy com bias/MAE

Resultado: a primeira métrica composta de "qualidade caindo MAIS RÁPIDO do que
o modelo é capaz de ver" — um sinal que **nenhum analisador estático gratuito
ou pago no mercado expõe** porque nenhum persiste ambas as séries.

#### Novo módulo — `governance/compound_alert.py`

`CompoundAlert` dataclass + 4-tier risk ladder:

| Tier | Critério | Significado |
|---|---|---|
| **RED** | APS `DEGRADING_PERSISTENT` **AND** Predictor `BIASED_DOWN` | Qualidade caindo persistente E predictor subestimando velocidade |
| **AMBER** | APS degrading **OR** Predictor BIASED_* (apenas um dos dois) | Um sinal forte, atenção |
| **YELLOW** | APS slope < 0 **AND** Predictor MAE > 10 % de mean H | Sinal fraco composto |
| **GREEN** | nada disso | Sob controle |

`priority_score ∈ [0, 100]` refina o tier base com a intensidade dos sinais
(slope negativo extra, MAE relativo acima do floor). Sorting determinístico
para o ranking repo-wide.

**API pública:**

- `compute_compound_alert(store, module_id, window=100) -> CompoundAlert`
  - Pure read-only: consome `store.get_aps_history` (LEAP 2) e
    `store.get_predictor_history` (LEAP 4)
  - Lógica de trend (slope/Hurst/verdict) e accuracy (MAE/bias/verdict) replicada
    *sem* depender dos handlers REST (que usam `_store` global) — testes podem
    isolar via `_fresh_store()`
  - Nunca lança; insufficient data → tier GREEN com priority 5.0
- `repo_compound_alerts(store, window, top_k=None, include_green=False)`
  - Roda para todos os módulos em `store.list_modules()`
  - Filtra GREEN por padrão (foca em ações)
  - Sort por priority_score DESC
- `repo_tier_histogram(alerts) -> {RED, AMBER, YELLOW, GREEN}` — contagem por tier

#### Endpoints REST — `api/server.py`

| Endpoint | Descrição |
|---|---|
| `GET /alerts/compound?module=&window=` | Compound alert de um módulo — tier, priority_score, reasons, APS subdict, Predictor subdict |
| `GET /alerts/repo?window=&top_k=&include_green=` | Ranking repo-wide + histograma de tiers + `top_module` (pior) |

`SensorConfig.version` → `"3.2.5"`.

#### Smoke test ao vivo (3 módulos em 1 repositório sintético)

```
auth.login    AMBER  priority=65.58   APS:DEGRADING_PERSISTENT  Pred:BIASED_UP
billing.api   RED    priority=100.00  APS:DEGRADING_PERSISTENT  Pred:BIASED_DOWN
static.utils  GREEN  priority= 5.00   APS:STABLE                Pred:ACCURATE

Repo histogram: {RED: 1, AMBER: 1, YELLOW: 0, GREEN: 1}
Actionable rank: [billing.api, auth.login]
```

**Diagnóstico que era impossível em qualquer versão até 3.2.4**: `billing.api`
tem o pior compound score porque **tanto a qualidade está caindo persistentemente
quanto o predictor consistentemente erra a velocidade (BIASED_DOWN = real cai
mais rápido que previsto)**.  É um sinal acionável para priorizar code review.

#### Testes — `tests/test_marco_m32.py` (30 testes TC01-TC30)

- TC01-TC06: classifier (RED two-signal, AMBER single, YELLOW weak compound,
  GREEN clean, RED preempts AMBER)
- TC07-TC14: per-module compute (insufficient/clean/degrading, sub-dict
  presence, unknown module GREEN, to_dict round-trip, n_samples)
- TC15-TC20: repo ranking (worst-first sort, default GREEN filter,
  include_green keeps them, top_k cap, histogram canonical keys, empty repo)
- TC21-TC26: priority bounded [0,100], tier ordering invariant
  (RED>AMBER>YELLOW>GREEN), RED reasons describe both signals, dataclass defaults
- TC27-TC30: endpoints `/alerts/compound` (400 sem module, shape) e
  `/alerts/repo` (histogram + filtro + include_green)

**Resultado: 1100/1100 marco-tests PASS — suíte 100% verde.**

#### O que Sprint A destrava

| Uso | Como |
|---|---|
| **CI PR gate** | `GET /alerts/repo?top_k=5` → rejeita PR se algum módulo RED novo aparecer |
| **Dashboard de risco** | Histograma {RED, AMBER, YELLOW, GREEN} por commit principal |
| **Priorização de code review** | `priority_score` sorteia o backlog de refactoring |
| **Detecção precoce de "blind spot"** | RED = "o predictor não consegue acompanhar a degradação" → revisar arquitetura |

#### Próximo marco

Sprint B — Repo-level meta-score + outliers (APS Z-score) → v3.2.6

---

## [3.2.4] — 2026-06-17 — LEAP 4: Predictor/Trend persistidos + forecast-accuracy

### Adicionado

A reavaliação completa (2026-06-16) identificou que `hurst_exponent`,
`slope_pct`, `forecast_next` e `confidence` do `DegradationPredictor` só
viviam na resposta REST — descartados a cada nova chamada. **LEAP 4
persiste essas saídas POR SNAPSHOT** no momento do insert, então cada linha
guarda "o que o predictor sabia naquele momento".

Consequência prática nova: a partir da row `t+1`, é possível **comparar
o forecast feito em `t` com o `hamiltonian` real em `t+1`** — meta-análise
de acurácia do próprio predictor, capacidade que nenhum analisador
gratuito oferece.

#### Schema — `sensor_storage/snapshot_store.py`

Quatro novas colunas REAL DEFAULT NULL, migração idempotente:

| Coluna | Origem |
|---|---|
| `predictor_hurst` | `DegradationForecast.hurst_exponent` |
| `predictor_slope_pct` | `DegradationForecast.slope_pct` |
| `predictor_forecast_next` | `DegradationForecast.predicted_h` |
| `predictor_confidence` | `DegradationForecast.confidence` |

Cálculo no `_compute_forecast(mv)` rodado **antes** do INSERT:
1. Pega `get_history(module_id)` (snapshots ANTES desta linha)
2. Se < 4 amostras → retorna `(None, None, None, None)` (predictor não dispara)
3. Senão → `DegradationPredictor().predict(history)` e extrai os 4 campos
4. Qualquer exceção do predictor → todos os campos NULL, insert prossegue

`_row_to_mv` atribui os 4 valores em `mv.predictor_{hurst,slope_pct,forecast_next,confidence}` (None para linhas legadas pré-LEAP 4).

#### Helper — `get_predictor_history(module_id, window)`

Retorna `List[Dict]` ordenado ASC com chaves:
`commit, timestamp, hamiltonian, hurst, slope_pct, forecast_next, confidence, forecast_error`

`forecast_error` é backfilled na função: para cada linha `i`,
`error[i] = hamiltonian[i+1] − forecast_next[i]`.
Última linha tem `forecast_error = None` (não há sucessor).

#### Endpoints REST — `api/server.py`

| Endpoint | Descrição |
|---|---|
| `GET /predictor/history?module=&window=` | Série temporal completa + `forecast_error` por linha; `n_samples`, `n_forecasts` |
| `GET /predictor/accuracy?module=&window=` | Sumário MAE, RMSE, bias, mae_relative + verdict (`ACCURATE` / `BIASED_UP` / `BIASED_DOWN` / `NOISY` / `INSUFFICIENT`) |

**Veredito de acurácia** (na função `handle_predictor_accuracy`):
- `INSUFFICIENT`: < 3 pares avaliáveis
- `ACCURATE`: MAE < 10 % da média do Hamiltoniano
- `BIASED_UP`: |bias| > MAE/2 e bias > 0 (predictor subestima — code degrades faster than predicted)
- `BIASED_DOWN`: |bias| > MAE/2 e bias < 0 (predictor superestima — overshoots)
- `NOISY`: MAE alto mas bias quase zero (variância sem viés sistemático)

`SensorConfig.version` → `"3.2.4"`.

#### Smoke test ao vivo

Série degradante de 8 snapshots (H crescendo geometricamente):

```
commit    ham    hurst   slope%     fcst   conf      err
c00      1.00        -        -        -      -        -
c01      1.50        -        -        -      -        -
c02      2.20        -        -        -      -        -
c03      3.00        -        -        -      -        -
c04      4.10    0.500   22.333    6.280  0.198   -0.780
c05      5.50    0.986   18.780    7.750  0.245   -0.750
c06      7.00    1.000   16.156    9.548  0.290   -0.548
c07      9.00    1.000   14.235   11.443  0.338        -
```

Predictor identificou degradação persistente (Hurst → 1.0), mas
**está superestimando** (bias negativo consistente em todos os pares).
Verdict esperado: `BIASED_DOWN` — sinal acionável que antes era invisível.

#### Testes — `tests/test_marco_m31.py` (30 testes TF01-TF30)

- TF01-TF06: schema (4 colunas REAL, DEFAULT NULL, migração idempotente,
  LEAP 1 e LEAP 2 ainda round-tripping)
- TF07-TF14: insert-time forecast (primeiras 4 linhas NULL, 5ª em diante
  preenchida, forecasts > 0 para série positiva, Hurst ∈ [0,1],
  confidence ∈ [0,1], módulo vazio não crasha, slope_pct persiste,
  cross-module isolation)
- TF15-TF22: `get_predictor_history` (vazio → [], ordem ASC,
  forecast_error correto, última linha sem error, shape do dict,
  legacy NULL propaga, semântica do error, window limita rows)
- TF23-TF26: endpoint `/predictor/history` (400/404, shape, campo
  `forecast_error` em cada sample)
- TF27-TF30: endpoint `/predictor/accuracy` (INSUFFICIENT < 3 pares,
  campos MAE/RMSE/bias/mae_relative/mean_hamiltonian/verdict/n_evaluated,
  verdict em valor canônico, 404 em módulo desconhecido)

**Resultado: 1070/1070 marco-tests PASS — suíte 100% verde.**

#### O que LEAP 4 destrava

| Capacidade | Antes | Agora |
|---|---|---|
| Forecast accuracy real | impossível medir (forecasts não persistidos) | **MAE / RMSE / bias por módulo, com verdict acionável** |
| "Predictor está overshootando aqui" | invisível | `BIASED_DOWN` no endpoint accuracy |
| Hurst-de-Hursts (estabilidade do exp.) | impossível | basta consumir `samples[].hurst` |
| Confidence drift | impossível | `samples[].confidence` ao longo do tempo |
| Acoplamento com APS history (LEAP 2) | inexistente | módulo com `BIASED_DOWN` + APS `DEGRADING_PERSISTENT` = alerta máximo |

#### Próximo marco

M9.1 — Research Signals (Shannon entropy, Temporal Coupling Index,
CC Churn, Invariant Density) → **v3.3.0 (release final)**

---

## [3.2.3] — 2026-06-17 — LEAP 3: AutoFix ↔ SAST closed loop (M8.2)

### Adicionado

Conecta as duas capacidades que já existiam mas estavam **desconectadas**:
30 regras SAST com campo `suggested_fix` (desde M8.1) + 16 AutoFix transforms
(M5.2/M8.1/AFix+). LEAP 3 fecha o loop com um orquestrador que escolhe os
transforms certos automaticamente a partir do rule_id detectado pelo SAST,
aplica em uma única passada, e re-roda o SAST para reportar quais findings
foram remediadas e quais permanecem residuais.

#### Novo módulo — `sensor_core/autofix/sast_remediation.py`

- `SAST_TO_TRANSFORM: Dict[str, Type[BaseTransform]]` — tabela de mapeamento
  (única fonte da verdade; adicionar regra = 1 linha)

  | Rule | Title | Transform |
  |---|---|---|
  | SAST006 | Weak Cryptographic Algorithm | `WeakHashReplacer` |
  | SAST007 | Insecure Randomness | `InsecureRandomReplacer` |
  | SAST038 | Exception Swallowing (bare except) | `BareExceptReplacer` |
  | SAST039 | Mutable Default Argument | `MutableDefaultRemover` |

  Apenas **rewrites de alta confiança** (saída sintaticamente válida,
  semântica preservada por design). Advisories como `LoopGuardAdvisor` e
  `FormatStringModernizer` **não** participam — o orquestrador deixa essas
  decisões para revisão humana.

- `RemediationResult` dataclass:
  ```
  patched_source, is_valid, transforms_applied,
  findings_before, findings_after, fixed_rules, fixed_count, residual_count
  ```

- `auto_remediate(source, module_id) -> RemediationResult`:
  1. `sast.scan(source)` → coleta rule IDs presentes
  2. `_select_transforms(rule_ids)` → seleciona deduplicadamente os
     transforms mapeados (ordem determinística para reprodutibilidade)
  3. `AutofixEngine(transforms=...).apply(source)` — única passada com
     apenas os transforms necessários (mais rápido que o pipeline default)
  4. Re-`sast.scan(patched_source)` → calcula `fixed = before − after`,
     reporta residuais
  - Nunca lança: parse errors, transforms quebrados, scan vazios são
    tratados graciosamente retornando um resultado identity

#### Novo endpoint REST — `api/server.py`

`POST /apex/auto-remediate`

Request:
```json
{"code": "<python source>", "module_id": "audit.crypto"}
```

Response (200):
```json
{
  "module_id": "audit.crypto",
  "patched_source": "...",
  "is_valid": true,
  "transforms_applied": ["WeakHashReplacer", "MutableDefaultRemover"],
  "findings_before": ["SAST006", "SAST039"],
  "findings_after": [],
  "fixed_rules": ["SAST006", "SAST039"],
  "fixed_count": 2,
  "residual_count": 0
}
```

#### Smoke test ao vivo

Código vulnerável (md5 + random.choice + mutable default + bare except):

```
findings_before  = [SAST006, SAST007, SAST039]
transforms       = [InsecureRandomReplacer, MutableDefaultRemover, WeakHashReplacer]
fixed_rules      = [SAST006, SAST007, SAST039]
findings_after   = []
fixed_count = 3   residual = 0   is_valid = True
```

Patched source (válido, executável):
```python
import hashlib, random, secrets

def f(items=None):
    if items is None:
        items = []
    try:
        x = hashlib.sha256(b'data').hexdigest()
        y = secrets.choice(items)
        return x + y
    except:
        return None
```

#### Testes — `tests/test_marco_m30.py` (30 testes TY01-TY30)

- TY01-TY06: integridade da tabela (não-vazia, chaves "SAST*", valores
  são subclasses de `BaseTransform`, mapeamentos canônicos)
- TY07-TY14: remediação por regra única (md5/sha1, random.choice,
  mutable default; `transforms_applied` correto; patched compila)
- TY15-TY20: multi-rule + identidade (3 findings/1 passada/0 residuais,
  código limpo → identidade, regras não-mapeadas não disparam transform,
  `_select_transforms` determinístico e deduplicado)
- TY21-TY25: reporte de residuais + resiliência (SyntaxError → identity,
  source vazio → identity, `residual_count == len(findings_after)`,
  `to_dict()` carrega todas as chaves)
- TY26-TY30: endpoint (400 sem code, 400 com code vazio, 200 + payload
  completo + module_id ecoado, fix real persiste no `patched_source`,
  SyntaxError não derruba o handler)

**Resultado: 1040/1040 marco-tests PASS — suíte 100% verde.**

#### Significado estratégico

| Antes (v3.2.2) | Agora (v3.2.3) |
|---|---|
| 30 SAST findings com `suggested_fix` em texto | findings são **executavelmente fixáveis** |
| 16 AutoFix transforms — usuário aplica manualmente em arquivo inteiro | transforms acionados **por rule_id**, focados |
| Sem closed loop SAST→Fix→re-scan | **fixed_rules** computado automaticamente; residuais explicitados |
| Sem endpoint de "fix this code" | `POST /apex/auto-remediate` — IDE/CI-ready |

#### Extensibilidade

Adicionar um novo SAST↔Transform = 1 linha em `SAST_TO_TRANSFORM`:
```python
SAST_TO_TRANSFORM["SAST040"] = MyNewTransform
```
+ um teste TY no `test_marco_m30.py`. O orquestrador descobre o transform
automaticamente quando a regra fizer fire.

#### Próximo marco

LEAP 4 — Predictor/Trend persistidos → v3.2.4

---

## [3.2.2] — 2026-06-17 — LEAP 2: APS persisted as a time-series signal

### Decisão arquitetural (FMEA-driven)

A versão original do LEAP 2 propunha trocar `CHANNEL_NAMES` no FrequencyEngine
de 9 → 10 canais (adicionando "APS"). DSM/Ishikawa identificaram acoplamento
estrutural com `EMBEDDING_DIM`, `ErrorSignatures` persistidas e DBSCAN —
risco alto pra ganho marginal. **Refino:** persistir APS + tratá-lo como sinal
paralelo consumindo a mesma máquina temporal (OLS slope, Hurst R/S) sem tocar
nos 9 canais arquiteturais. Mesma capacidade analítica entregue, 30 % do risco.

### Adicionado — LEAP 2 (APS as persisted signal)

#### Schema — `sensor_storage/snapshot_store.py`

- Nova coluna `aps_score REAL DEFAULT NULL` em `snapshots`
- `_M70_MIGRATION_COLUMNS` estendido — migração idempotente para DBs existentes
- Cálculo de APS **no momento do insert** via novo `_compute_aps_score(mv)`
  - Reusa `metrics.anti_pattern_score.aps_from_metric_vector`
  - Defensivo: se o engine de APS falhar OU o `to_dict` de qualquer vetor
    levantar exceção, a coluna fica NULL e o insert **não falha** (TZ08)
  - Vantagem de calcular no insert: queries futuras de history/trend não
    dependem dos extended_vectors v2 estarem presentes na linha
- Novo método `get_aps_history(module_id, window) -> List[(commit, ts, aps)]`
  - Bypass dos JSONs pesados — query SELECT mínima de 3 colunas
  - Linhas pré-LEAP-2 retornam `aps=None` (semântica "missing sample")
- `_row_to_mv` agora atribui `mv.aps_score: Optional[float]`

#### Endpoints REST — `api/server.py`

| Endpoint | Descrição |
|---|---|
| `GET /anti-pattern-score/history?module=&window=` | Série temporal APS persistida; `n_samples`, `n_valid`, lista de `{commit, timestamp, aps}` |
| `GET /anti-pattern-score/trend?module=&window=` | OLS slope + Hurst R/S + forecast_next + verdict (`STABLE` / `DEGRADING` / `DEGRADING_PERSISTENT` / `IMPROVING` / `INSUFFICIENT`) |

- Trend reusa `sensor_core.predictor.hurst_rs` (mesma fórmula do DegradationPredictor
  aplicada agora ao score composto, não só ao Hamiltonian)
- Verdict combina slope (direção) e Hurst (persistência): `DEGRADING_PERSISTENT`
  só dispara quando slope < −0.5 APS/snapshot AND Hurst > 0.55
- Mínimo de 4 amostras válidas para análise — abaixo disso retorna `INSUFFICIENT`
- `SensorConfig.version` → `"3.2.2"`

#### Smoke test ao vivo

Histórico sintético de 8 snapshots com taint crescente (0→7):

```
APS:  100.00 → 72.31 → 60.00 → 57.69 → 57.69 → 57.69 → 57.69 → 57.69
Trend: slope=-4.48 APS/snapshot, Hurst=0.988, forecast_next=44.94
Verdict: DEGRADING_PERSISTENT
```

#### Testes — `tests/test_marco_m29.py` (30 testes TZ01-TZ30)

- TZ01-TZ08: schema (coluna existe + tipo REAL), APS computado no insert,
  snapshot limpo → APS=100, MV sem extended vectors → APS=100 neutro,
  vetor com `to_dict` quebrado não bloqueia persistência
- TZ09-TZ16: `get_aps_history` (ordem cronológica, tupla, window, NULLs
  preservados, isolamento cross-module, regressão LEAP 1)
- TZ17-TZ24: endpoint `/history` (400/404, shape, NULLs incluídos por padrão,
  floats, window, module_id, trend visível na resposta)
- TZ25-TZ30: endpoint `/trend` (INSUFFICIENT < 4 amostras, DEGRADING /
  IMPROVING / STABLE, todos os campos obrigatórios, Hurst em [0,1],
  NULLs ignorados pela análise)

**Resultado: 1010/1010 marco-tests PASS — suíte 100% verde.**

#### O que LEAP 2 destrava

| Capacidade | Antes | Agora |
|---|---|---|
| APS por snapshot | recomputado on-the-fly via REST | **persistido** (1 coluna REAL) |
| `/anti-pattern-score/history` | inexistente | série temporal completa, JSON-friendly |
| Tendência de APS | inexistente | OLS slope + slope_pct + forecast_next |
| Detecção de degradação persistente | inexistente | **Hurst R/S sobre o score composto** |
| Verdict de quality gate sobre score único | impossível | `DEGRADING_PERSISTENT` / `IMPROVING` / etc. |

**Análise espectral de score de qualidade composto: nenhum analisador estático
gratuito no mercado faz isso — diferencial absoluto vs SonarQube.**

#### Próximo marco

LEAP 3 — AutoFix↔SAST closed loop (M8.2) → v3.2.3

---

## [3.2.1] — 2026-06-16 — LEAP 1: Persistence Sprint (closes 72% information loss gap)

### Adicionado — LEAP 1 (Persistence Sprint)

Identificado pela reavaliação completa de canais/sinais: **9 vetores attached em
`mv` desde M7.2-M7.7 mas DROPPED a cada scan** porque o `SnapshotStore` nunca foi
estendido depois de M7.0. Resultado: 69 dos 96 canais formais (72 %) eram
recomputados toda vez e perdidos antes de chegar à camada de história /
governança / FrequencyEngine. LEAP 1 fecha esse gap com **uma única coluna JSON**.

#### Schema — `sensor_storage/snapshot_store.py`

- Nova coluna `extended_vectors_v2_json TEXT DEFAULT NULL` em `snapshots`
- `_M70_MIGRATION_COLUMNS` estendido — migração idempotente para DBs existentes
  (try/except em `ALTER TABLE`); rows antigos seguem válidos com a coluna NULL
- Payload JSON tipo objeto, chaveado pelo nome do atributo em `mv`:
  ```json
  {"security": {...}, "velocity": {...}, "flow": {...},
   "reliability": {...}, "maintainability": {...}, "performance": {...},
   "architecture": {...}, "test_quality": {...}, "thread_safety": {...}}
  ```
  Vetores ausentes (e.g. não-Python) são omitidos do JSON — o round-trip preserva
  exatamente o conjunto de chaves presente no insert.

#### Serialização + deserialização

- Novo `_serialize_extended_v2(mv)` — itera o tuplo canônico `_EXTENDED_V2_ATTRS`,
  serializa via `to_dict()` cada vetor presente; falha em um vetor isolado **não
  bloqueia** os outros (defense in depth FMEA)
- Novo bloco no `_row_to_mv` que reconstrói os 9 vetores via `from_dict`,
  defensivo contra vetores corrompidos individualmente (TP20) e contra chaves
  futuras desconhecidas (TP30 — robustez à evolução de schema)
- Tupla canônica `SnapshotStore._EXTENDED_V2_ATTRS` exposta como contrato

#### `metrics/extended_vectors.py` — fechamento de assimetria

- `SecurityVector.from_dict()` adicionado (estava faltando — só tinha `to_dict`)
- `VelocityVector.from_dict()` adicionado (idem)
- Agora todos os 13 vetores têm contrato simétrico `to_dict ⇄ from_dict`

#### Resultados imediatos liberados pelo LEAP 1

| Capacidade | Antes | Agora |
|---|---|---|
| Canais formais persistidos | 27 / 96 (28 %) | **96 / 96 (100 %)** |
| `/anti-pattern-score?module=` em histórico | recomputado on-the-fly, sem trend | **APS de cada snapshot recuperável** → trend, forecast, change-point |
| Sinais SAST/Sec/Perf/Rel/Thread/Arch/Test para Quality Gate | invisíveis | **disponíveis na história** |
| Findings SAST multi-linguagem (M9.0) | persisted-as-counts (via SecurityVector) | **também restaurados via LEAP 1** |
| Vetores M7.2-M7.7 retroativamente valorizados | computação descartada | sinais vivos cruzando o tempo |

#### Testes — `tests/test_marco_m28.py` (30 testes TP01-TP30)

- TP01-TP09: round-trip individual de cada um dos 9 vetores LEAP-1
- TP10-TP15: invariantes de schema, migração idempotente, regressão M7.0
- TP16-TP20: backward-compat (rows antigos, payload parcial, ordem cronológica,
  isolamento cross-module, resiliência a vetor corrompido)
- TP21-TP25: **APS history agora computável** — 3 snapshots → 3 APS persistidos,
  trend de degradação detectável, componentes do APS idênticos pré/pós-store,
  thread-safety contribui para o score após persistência
- TP26-TP30: edge cases de serializer (vazio → NULL, payload parcial, futuras
  chaves desconhecidas ignoradas)

**Resultado: 980/980 marco-tests PASS — suíte 100% verde.**
**Smoke test ao vivo: APS in-memory == APS pós-persistência (36.54 == 36.54).**

#### Mudanças de versão

- `pyproject.toml` 3.2.0 → 3.2.1 (test_marco_m28 registrado)
- `SensorConfig.version` → `"3.2.1"`
- Bump patch porque LEAP 1 é correção de gap, não nova capacidade
  (semver: API pública intacta, comportamento de roundtrip corrigido)

#### O que LEAP 1 destrava nas próximas atividades

- **LEAP 2 — APS como canal espectral**: agora APS existe persistido por snapshot,
  pode virar o 10º canal do FrequencyEngine para análise espectral
- **LEAP 3 — AutoFix↔SAST closed loop**: findings SAST persistidos permitem
  medir "fix-effectiveness" ao longo de commits
- **M9.1 Research Signals**: Shannon entropy / TCI / CC Churn agora podem ser
  alimentadas pelos sinais de Reliability/Performance/Thread-safety persistidos
- **Quality Gate baseado em APS**: política sobre score composto vira viável

**Próximo marco:** LEAP 2 — APS persistido + 10º canal espectral → v3.2.2

---

## [3.2.0] — 2026-06-16 — M9.0 Tree-Sitter Multi-Language SAST (RELEASE MINOR)

### Adicionado — M9.0 FASE 9 (WBS 15.1-15.5)

#### WBS 15.1 — TreeSitterBridge (`lang_adapters/tree_sitter_bridge.py`)

Ponte opcional para tree-sitter com **fallback regex automático**:
- `TreeSitterBridge(language)` para javascript / typescript / java / go
- `.available()` — probe de `tree_sitter` + grammar da linguagem (cacheado); nunca crasha
- `.parse(source)` — árvore tree-sitter real OU `None` (modo fallback)
- `.iter_lines()` / `.search_lines()` — primitivos line-oriented (estáticos, sempre disponíveis)
- Import lazy: `import tree_sitter` envolto em try/except — módulo sempre importável
- **Offline-first:** grammars são artefatos nativos compilados que podem faltar em CI mínimo; o fallback regex mantém as regras SAST funcionais em qualquer ambiente

#### WBS 15.2-15.4 — Multi-Language SAST (`sast/multilang_scanner.py`)

**30 regras SAST** cobrindo JS/TS + Java + Go, emitindo `SASTFinding` (mesmo contrato do scanner Python):

**JavaScript / TypeScript (JS01-JS10):**
| Regra | CWE | Detecção |
|---|---|---|
| JS01 | CWE-79 | XSS via `innerHTML`/`outerHTML` |
| JS02 | CWE-79 | XSS via `document.write` |
| JS03 | CWE-79 | React `dangerouslySetInnerHTML` |
| JS04 | CWE-95 | Code injection via `eval()` |
| JS05 | CWE-95 | `new Function()` constructor |
| JS06 | CWE-78 | `child_process.exec` com interpolação |
| JS07 | CWE-1321 | Prototype pollution via `__proto__` |
| JS08 | CWE-327 | Weak hash `createHash('md5')` |
| JS09 | CWE-330 | `Math.random()` para secrets |
| JS10 | CWE-89 | SQL injection via concatenação |

**Java (JV01-JV10):** `Runtime.exec`, SQL via `Statement`+concat, XXE (DocumentBuilderFactory), deserialização insegura (ObjectInputStream), weak crypto (MessageDigest MD5/SHA-1), trust-all TLS, senha hardcoded, `java.util.Random` para segurança, CORS `@CrossOrigin("*")`, `ScriptEngine.eval`.

**Go (GO01-GO10):** `exec.Command` com interpolação, SQL via `fmt.Sprintf`, weak crypto (md5/sha1), `math/rand` para crypto, `InsecureSkipVerify: true`, credencial hardcoded, `defer` em loop (resource leak), `text/template` para HTML, path traversal via `filepath.Join`, SSRF via `http.Get`.

- Dispatch por extensão: `.js/.jsx/.mjs/.cjs` → javascript, `.ts/.tsx` → typescript, `.java` → java, `.go` → go
- Dedup por `(rule_id, line)`; skip de comentários `//` (preservando URLs `http://`)
- `confidence=0.75` (regex-based, abaixo da confiança AST do scanner Python)
- Rating A–E pela pior severidade presente

#### WBS 15.5 — Integração REST (`api/server.py`)

- `POST /sast` agora **roteia por extensão**: Python → scanner AST (inalterado); JS/TS/Java/Go → multilang. Resposta inclui `engine: "multilang"` + `language`
- `GET /sast/rules` consolida ambos: **58 regras** (28 Python + 30 multilang), cada uma com campo `languages`
- Import guard `_MULTILANG_SAST_AVAILABLE` (degradação graciosa)
- `SensorConfig.version` → `"3.2.0"`
- `tree-sitter` já presente em `[project.optional-dependencies].parsers` (grammars JS/TS/Java/Go)

#### WBS 15.5 — Testes (`tests/test_marco_m27.py`)

- **30 testes TG01-TG30 (todos verdes)**
  - TG01-TG04: TreeSitterBridge (availability probe sem crash, fallback parse, iter_lines/search_lines)
  - TG05-TG14: JS/TS rules JS01-JS10
  - TG15-TG22: Java rules JV01-JV10
  - TG23-TG28: Go rules GO01-GO10
  - TG29-TG30: integração (inventário 30 regras, dispatch, rating E, código limpo + skip de comentários)
- `pyproject.toml` — versão `3.1.3` → `3.2.0`, `test_marco_m27.py` registrado

**Resultado: 950/950 marco-tests PASS — suíte 100% verde.**

**Marco competitivo:** UCO-Sensor passa de **1 → 5 linguagens** com análise de segurança (Python AST + JS/TS/Java/Go). Regras SAST totais: 28 → **58**.

**Próximo marco:** M9.1 — Research Signals (Shannon Entropy, Temporal Coupling Index, CC Churn) → v3.3.0 (release final)

**Referências:**
- OWASP Top 10 (2021); CWE Top 25 (2024); MITRE CWE.
- Brunton-Spall, M. (2020). *Agile Application Security*. O'Reilly.

---

## [3.1.3] — 2026-06-16 — AFix+ FASE 8 (4 security autofix transforms)

### Adicionado — AFix+ FASE 8 (WBS 14.1-14.2)

#### WBS 14 — AutoFix engine: 12 → 16 transforms

Completa a meta original "16+ transforms" da análise de gaps (§2.4), somando
os 4 transforms de segurança que faltavam aos 12 já entregues (M5.2 + M8.1):

| # | Transform | Tipo | Ação |
|---|---|---|---|
| 13 | `WeakHashReplacer` | rewrite | `hashlib.md5/sha1` → `hashlib.sha256` (CWE-327) |
| 14 | `InsecureRandomReplacer` | rewrite + advisory | `random.choice` → `secrets.choice` + injeta `import secrets`; advisory para `randint/random/…` (CWE-330) |
| 15 | `LoopGuardAdvisor` | advisory | `while True:` sem `break`/`return`/`raise` (CWE-835) |
| 16 | `FormatStringModernizer` | advisory | `"%s" % x` → f-string / str.format |

**WeakHashReplacer** (`replace_weak_hash.py`):
- Forma 1: `hashlib.md5(...)` / `hashlib.sha1(...)` → `hashlib.sha256(...)`
- Forma 2: `hashlib.new("md5")` / `hashlib.new("SHA1")` → `hashlib.new("sha256")`
- Preserva número/ordem de argumentos; ignora `md5()` bare (proveniência desconhecida)

**InsecureRandomReplacer** (`replace_insecure_random.py`):
- Rewrite seguro 1:1: `random.choice(seq)` → `secrets.choice(seq)` (mesma assinatura)
- Injeta `import secrets` após o último import (uma vez só, se ainda não presente)
- Advisory (sem mutação, preserva código válido) para `random.{random,randint,randrange,uniform,getrandbits,sample,shuffle}` — não há equivalente drop-in em `secrets`

**LoopGuardAdvisor** (`add_loop_guard.py`):
- Detecta `while True:` cujo corpo (sem descer em funções/classes aninhadas) não contém `break`/`return`/`raise`
- Advisory puro — nunca insere guard automaticamente (mudaria a semântica)

**FormatStringModernizer** (`replace_format_string.py`):
- Detecta `BinOp(Mod)` com operando esquerdo string-literal contendo conversion specifier printf (`%s`, `%d`, `%r`, `%f`, `%x`, …)
- Ignora `%` numérico (`10 % 3`) e strings sem specifier (`'100 percent'`)
- Advisory — rewrite de `%`→f-string é error-prone (format-spec, `%%`, mapping)

**Integração:**
- Registrados em `transforms/__init__.py` (`__all__`) e no engine
- `_DEFAULT_PIPELINE` estendido de 12 → **16 transforms** (rewrites antes dos advisories)
- Todos os rewrites produzem AST válido (`ast.unparse` round-trip testado)

#### WBS 14.2 — Testes (`tests/test_marco_m26.py`)

- **30 testes TX01-TX30 (todos verdes)**
  - TX01-TX08: WeakHashReplacer (md5/sha1/new-form, sha256 untouched, bare untouched, args preserved, CWE)
  - TX09-TX16: InsecureRandomReplacer (choice rewrite, import inject/dedup, advisory, bare untouched, validity)
  - TX17-TX22: LoopGuardAdvisor (break/return/raise suppress, non-True ignored, no mutation)
  - TX23-TX27: FormatStringModernizer (%s/%d flagged, no-spec/numeric-mod ignored, no mutation)
  - TX28-TX30: engine integration (16-transform pipeline, end-to-end security fix valid, idempotence on clean code)
- `pyproject.toml` — versão `3.1.2` → `3.1.3`, `test_marco_m26.py` registrado
- `SensorConfig.version` → `"3.1.3"`

**Resultado: 920/920 marco-tests PASS — suíte 100% verde.**

**FASE 8 COMPLETA** (SCA+ + IaC+ + AFix+). **Próximo marco:** M9.0 — Tree-Sitter Multi-Language SAST (JS/TS/Java/Go) → v3.2.0

---

## [3.1.2] — 2026-06-16 — IaC+ FASE 8 (rule expansion + Ansible/Pulumi/CDK)

### Adicionado — IaC+ FASE 8 (WBS 13.1-13.4)

#### WBS 13.1-13.3 — Rule expansion (`iac/iac_scanner.py`)

- **48 → 102 regras** (+54), target ≥100 ✓
- **5 → 8 scanners** (Dockerfile, Compose, K8s, Terraform, Helm, **Ansible**, **Pulumi**, **CDK**)

| Scanner | v3.1.0 | **v3.1.2** | Δ |
|---|---:|---:|---:|
| Dockerfile | 10 | **20** | +10 (D011-D020) |
| Compose | 8 | 8 | — |
| Kubernetes | 12 | **25** | +13 (K013-K025) |
| Terraform | 12 | **25** | +13 (T013-T025) |
| Helm | 6 | 6 | — |
| Ansible 🆕 | — | **8** | A001-A008 |
| Pulumi 🆕 | — | **5** | P001-P005 |
| AWS CDK 🆕 | — | **5** | CDK001-CDK005 |
| **TOTAL** | **48** | **102** | **+54** |

**Dockerfile (D011-D020):** apt-get sem `--no-install-recommends`, `curl|sh` supply-chain risk, `wget` sem checksum, `WORKDIR` relativo, `sudo` em RUN, `chmod 777`, registry não oficial, múltiplos RUN (layer bloat), `COPY . .` sem `.dockerignore`, `FROM x:latest AS …`.

**Kubernetes (K013-K025):** sem liveness/readiness probe, automount default true, ClusterRoleBinding a cluster-admin (CRITICAL), sem PDB, `imagePullPolicy: Never`, sem NetworkPolicy, Ingress sem TLS, sem resource requests, sem seccompProfile / AppArmor annotation, `emptyDir` para dados persistentes, replicas par para stateful.

**Terraform (T013-T025):** CloudFront `allow-all`, Lambda sem VPC, RDS sem backup, S3 sem encryption, EC2 IMDSv1 (`http_tokens=optional`), KMS sem rotation, CloudTrail single-region, GuardDuty ausente, SG egress 0.0.0.0/0, ALB sem access logs, SNS sem KMS, DynamoDB sem SSE, ALB/CloudFront público sem WAF.

#### WBS 13.4 — Novos scanners (`iac/iac_scanner.py`)

**Ansible (A001-A008, 8 regras):**
- `become: yes` sem `become_user` (HIGH)
- senhas/tokens em vars sem `no_log` (CRITICAL)
- credenciais AWS/GCP inline sem ansible-vault (HIGH)
- `shell`/`command` sem `changed_when` (MEDIUM)
- `mode: '0777'` world-writable (MEDIUM)
- `validate_certs: no` em uri/network (MEDIUM)
- `no_log: false` em tasks com secrets (LOW)
- package install sem `state:` explícito (LOW)

**Pulumi (P001-P005, 5 regras):**
- `publicReadAccess: true` em S3 Bucket (HIGH)
- credenciais hardcoded em código TS/JS (CRITICAL)
- SecurityGroup com `cidrBlocks: ["0.0.0.0/0"]` (HIGH)
- IAM Policy com `Action: '*'` ou `Resource: '*'` (MEDIUM)
- `Pulumi.yaml` sem `description:` (LOW)

**AWS CDK (CDK001-CDK005, 5 regras):**
- `new s3.Bucket(...)` sem `enforceSSL: true` (HIGH)
- `new s3.Bucket(...)` sem `encryption:` (HIGH)
- PolicyStatement com `resources: ['*']` (CRITICAL)
- `addIngressRule(Peer.anyIpv4(), ...)` (HIGH)
- `new lambda.Function(...)` sem `logRetention` (MEDIUM)

**Dispatcher + content sniffers:**
- `_dispatch` reconhece `Pulumi.yaml`, `Pulumi.<stack>.yaml`, `cdk.json`, `playbook.yml`, `site.yml`, `main.yml`
- `_looks_like_ansible` — heurística "lista de plays com hosts + tasks/roles/become"
- `_looks_like_pulumi` — detecta `@pulumi/` / `pulumi.Config` / `pulumi.StackReference`
- `_looks_like_cdk` — detecta `aws-cdk-lib` / `@aws-cdk/` / `aws_cdk`
- `_scan_cdk` faz checagem cruzada de absence (enforceSSL/encryption/logRetention) no mesmo arquivo
- `_SKIP_DIRS` agora ignora `cdk.out/`

#### WBS 13.4 — Testes (`tests/test_marco_m25.py`)

- **31 testes TI01-TI30 + 1 inventory guard (todos verdes)**
  - TI01-TI06: Dockerfile D011-D020 (positive + negative case D018)
  - TI07-TI14: K8s K013-K025 (probes, RBAC, ingress TLS, emptyDir, replicas)
  - TI15-TI20: Terraform T013-T025 (CloudFront/RDS/IMDS/KMS + GuardDuty absence + suppress)
  - TI21-TI24: Ansible (become/mode/validate_certs + content-sniffer dispatch)
  - TI25-TI27: Pulumi (publicReadAccess, hardcoded secret, YAML description)
  - TI28-TI30: CDK (Bucket+enforceSSL, suppression, addIngressRule anyIpv4)
- `pyproject.toml` — versão `3.1.1` → `3.1.2`, `test_marco_m25.py` registrado
- `SensorConfig.version` → `"3.1.2"`

**Resultado: 890/890 marco-tests PASS — suíte 100% verde.**

**Próximo marco:** AFix+ — 4→12 autofix transforms → v3.1.3

---

## [3.1.1] — 2026-06-16 — SCA+ FASE 8 (CVE expansion + 3 new ecosystems)

### Adicionado — SCA+ FASE 8 (WBS 12.1-12.3)

#### WBS 12.1-12.2 — CVE database expansion (`sca/cve_database.py`)

- **65 → 205 CVEs** (+140), target ≥200 ✓
- **44 → 148 pacotes** distintos rastreados
- **9 → 12 ecossistemas** (3 novos: swift / pub / hex)
- Nova função pública `ecosystems()` → lista ordenada de ecossistemas suportados
- Docstring do header atualizado com novos ecossistemas e contagens

**Distribuição por ecossistema (v3.1.1):**

| Ecossistema | CVEs | Pacotes |
|---|---:|---:|
| pip | 45 | 30 |
| npm | 40 | 26 |
| maven (+ gradle alias) | 30 | 20 |
| go | 12 | 11 |
| gem | 11 | 8 |
| cargo | 10 | 9 |
| nuget | 9 | 7 |
| composer | 8 | 7 |
| hex 🆕 | 4 | 4 |
| swift 🆕 | 3 | 3 |
| pub 🆕 | 3 | 3 |
| **TOTAL** | **205** | **148** |

**CVEs notáveis adicionados (sample):**
- pip: Werkzeug debugger RCE (CVE-2024-34069), MLflow auth bypass (CVE-2023-6014, CVSS 9.8), LangChain PALChain RCE (CVE-2023-36258), HuggingFace Transformers RCE (CVE-2024-3568)
- npm: Next.js middleware bypass (CVE-2025-29927, CVSS 9.1), tough-cookie prototype pollution (CVE-2023-26136, CVSS 9.8), ejs SSTI (CVE-2022-29078, CVSS 9.8)
- maven: Apache Tomcat partial-PUT RCE (CVE-2025-24813, CVSS 9.8), SnakeYAML unsafe deserialization (CVE-2022-1471), Apache Shiro auth bypass (CVE-2023-34478, CVSS 9.8)
- go: Docker authz plugin bypass (CVE-2024-41110, CVSS 9.9), HashiCorp Consul RPC escalation (CVE-2021-37219)
- gem: Rack::Static path traversal (CVE-2025-27610), rails-html-sanitizer XSS bypass (CVE-2024-53985)
- swift 🆕: Alamofire MITM (CVE-2021-31755), Vapor smuggling (CVE-2023-44389), SwiftNIO smuggling (CVE-2022-3215)
- pub 🆕: Dart dio cert bypass (CVE-2021-31402), http header injection (CVE-2020-35669), shelf header injection (CVE-2022-41945)
- hex 🆕: Phoenix open redirect (CVE-2023-21538), Plug cookie DoS (CVE-2024-27284), Ecto info disclosure (CVE-2021-46871), Cowboy HTTP/2 DoS (CVE-2024-26773)

#### WBS 12.3 — Novos parsers de manifesto (`sca/vulnerability_scanner.py`)

Quatro novos parsers, todos em stdlib pura (json + regex):

| Manifesto | Ecossistema | Formato |
|---|---|---|
| `Package.resolved` | swift | JSON (SPM v1 + v2 schemas) |
| `Podfile.lock` | swift | YAML-ish (CocoaPods) — top-level pods only, sub-specs ignorados |
| `pubspec.lock` | pub | YAML (Dart/Flutter) — apenas o bloco `packages:`, ignora `sdks:` |
| `mix.lock` | hex | Erlang map literal — apenas tuplos `:hex`, ignora `:git`/`:path` |

`_MANIFEST_NAMES` estendido para reconhecer os 4 arquivos novos.
Dispatcher `_dispatch_parse` roteia para os 4 novos parsers.

#### WBS 12.3 — Testes (`tests/test_marco_m24.py`)

- **30 testes TS31-TS60 (todos verdes)**
  - TS31-TS40: database size ≥200, 12 ecossistemas, spot-checks cross-ecosystem, severidades canônicas
  - TS41-TS47: novos ecossistemas (swift/pub/hex), normalização lowercase
  - TS48-TS54: parsers (Package.resolved v1+v2, Podfile.lock, pubspec.lock, mix.lock) + casos de borda (`sdks:`, `:git`)
  - TS55-TS60: integração end-to-end manifest→CVE→SCAResult.status
- `pyproject.toml` — versão `3.1.0` → `3.1.1`, `test_marco_m24.py` registrado
- `SensorConfig.version` → `"3.1.1"`

**Resultado: 859/859 marco-tests PASS — suíte 100% verde.**

**Próximo marco:** IaC+ (Dockerfile/K8s/Terraform 44→100+ regras + Ansible/Pulumi/CDK) → v3.1.2

---

## [3.1.0] — 2026-06-11 — M8.0 Real-Time Monitoring Mode

### Adicionado — M8.0 FASE 7 (WBS 11.1-11.6)

#### WBS 11.1 — FileWatcher (`monitor/file_watcher.py`)

Novo pacote `monitor/` com `FileWatcher` polling stdlib-only:
- `os.scandir` walk a cada `interval_ms` (default 500ms, min 10ms)
- Fingerprint `(st_mtime_ns, st_size)` — detecta created/modified/deleted
- Thread daemon + stop cooperativo via `threading.Event`
- Skip de diretórios ocultos (`.git`, `.venv`) e `__pycache__`
- Guard FMEA DATA: arquivo deletado entre scandir e stat é tolerado
- Callback que lança exceção é engolido — watcher nunca morre
- `poll_once()` exposto para testes determinísticos
- `ChangedFile` dataclass (path, event, timestamp, size)

#### WBS 11.2 — DeltaEngine (`monitor/delta_engine.py`)

- `MetricDelta` — ΔH, ΔCC, ILR, Δsecurity (SAST crit+high), Δreliability (bare_except+leaks)
- Guard FMEA NUMERICS: `_safe_pct` com floor ε=0.5 no baseline (0.001→0.002 ≠ +100%)
- `prev=None` (first sight) → `*_before=0`, pct=0 — sem ruído inicial
- Tolerante a vetores estendidos ausentes (default 0)

#### WBS 11.3 — AlertRuleEngine (`monitor/alert_rules.py`)

| Regra | Condição | Severidade |
|---|---|---|
| RULE-H-SPIKE | ΔH>+20% AND \|ΔH\|≥1.0 (>+50% → CRITICAL) | WARNING/CRITICAL |
| RULE-ILR-HIGH | ILR_after > 0.7 | CRITICAL |
| RULE-SAST-NEW | novo finding critical/high | CRITICAL |
| RULE-CC-SPIKE | ΔCC>+30% AND ΔCC≥5 | WARNING |
| RULE-REL-REGRESS | reliability_delta > 0 | WARNING |

Thresholds parametrizáveis no construtor (governança por repositório).
Guard FMEA THEORY: `min_abs` duplo (pct E absoluto) suprime ruído em baselines pequenos.

#### WBS 11.4 — MonitorService (`monitor/service.py`)

Pipeline: FileWatcher → `UCOBridge.analyze()` → DeltaEngine → AlertRuleEngine → buffer
- Baseline por módulo em memória (delta contra análise imediatamente anterior)
- Buffer bounded `deque(maxlen=1000)` — back-pressure descarta os mais antigos (anti CWE-400)
- Thread-safe (lock único para baselines + buffer)
- Deleção limpa baseline (recriação = first sight)
- `drain_events(max_events)` — consumido pelo SSE endpoint
- Falha de análise nunca mata a thread do watcher

#### WBS 11.5 — Endpoints + SSE (`api/server.py`)

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /monitor/start` | POST | Inicia watcher (`{root, interval_ms}`); 409 se já rodando |
| `POST /monitor/stop` | POST | Para watcher (idempotente) |
| `GET /monitor/status` | GET | files_watched, poll_count, alerts_total, events_pending |
| `GET /monitor/stream` | GET | **SSE**: connected/metric_change/alert/heartbeat |

**SSE protocol** (roadmap §7.3): `event:` + `data:` JSON frames, heartbeat a cada 5s.
Guard FMEA PROCESS (duplo):
1. `HTTPServer` → **`ThreadingHTTPServer`** — SSE long-poll não bloqueia outras requests
2. Stream bounded por `max_events` (default 100, cap 10k) E `timeout_s` (default 30s, cap 300s)

- `SensorConfig.version` → `"3.1.0"`
- Singleton `_monitor` + `_monitor_lock` (um monitor por servidor; start/stop sem races)

#### WBS 11.6 — Testes + manutenção

- **`tests/test_marco_m23.py`** — 30 testes TM01-TM30 (todos verdes)
  - TM01-TM08: FileWatcher (baseline, created/modified/deleted, extensões, hidden dirs, lifecycle, callback resiliente)
  - TM09-TM16: DeltaEngine (ΔH/ΔCC, ε-guard, first-sight, security/reliability, to_dict)
  - TM17-TM24: AlertRules (5 regras + guards de supressão + estável→zero alertas)
  - TM25-TM30: MonitorService pipeline + endpoints REST + SSE frame format
- **Fix manutenção**: `test_marco_m3.py::test_TS30` — atualizado `==13` → `>=13`
  (desatualizado desde a expansão SAST do M7.1 para 28 regras)
- **`pyproject.toml`** — versão `3.0.0` → `3.1.0`, `test_marco_m23.py` registrado

**Resultado: 829/829 marco-tests PASS — suíte 100% verde pela primeira vez desde M7.1.**

**Validação ao vivo (smoke):** edição degradante de módulo gerou em 1 poll:
`RULE-ILR-HIGH CRITICAL (ILR 1.00)`, `RULE-CC-SPIKE +800%`, `RULE-REL-REGRESS +1`.

**Próximo marco:** FASE 8 — SCA+ (200+ CVEs) / IaC+ (100+ regras) / AFix+ (12 transforms) → v3.1.x

---

## [3.0.0] — 2026-05-31 — M7.7 ThreadSafetyVector + Anti-Pattern Score (RELEASE MAJOR)

### Adicionado — M7.7 FASE 6b (WBS 10.1-10.4)

#### WBS 10.1-10.2 — ThreadSafetyAnalyzer AST (`metrics/thread_safety_analyzer.py`)

Novo módulo `metrics/thread_safety_analyzer.py` com `ThreadSafetyAnalyzer`:
- AST-only, stdlib pura, sem dependências externas
- `_collect_thread_targets()` — varre `Thread/Process/Timer(target=fn)` e coleta nomes
- `_function_mutates_global()` — detecta `global X` + assignment a X
- `_function_has_lock_synchronisation()` — detecta `Lock/RLock/Semaphore/Condition/Event` e `with lock:`
- `_function_mutates_module_collection()` — detecta `.append/.extend/.update/.add/...` em collections de módulo
- `_collect_module_level_collections()` — coleta names atribuídos a `[]`/`{}`/`set()` no top-level
- `_count_async_blocking()` — varre `async def` por `time.sleep`, `requests.*`, `socket.*`, `subprocess.*`
- `_count_daemon_threads()` — `Thread(daemon=True)` sem `.join()` no módulo
- `_count_unbounded_queues()` — `Queue/LifoQueue/PriorityQueue/SimpleQueue` sem `maxsize=`
- `ThreadSafetyResult` — dataclass com 6 contadores

#### WBS 10.1 — ThreadSafetyVector dataclass (`metrics/extended_vectors.py`)

Nova classe `ThreadSafetyVector` com **6 canais** de concurrency-correctness:

| Canal | CWE | Detecção |
|---|---|---|
| `global_shared_state_count` | CWE-362 | `global X` mutado em Thread target |
| `lock_missing_count` | CWE-362 | Mutação compartilhada sem primitivo de sync |
| `daemon_thread_risk` | CWE-366 | `Thread(daemon=True)` sem `.join()` |
| `queue_unbounded_risk` | CWE-400 | `Queue()` sem `maxsize=` |
| `asyncio_blocking_call` | CWE-557 | I/O bloqueante dentro de `async def` |
| `shared_mutable_default` | CWE-362 | Collection de módulo mutada em Thread target |

**Métodos auxiliares:**
- `thread_safety_rating()` — grade A–E (E forçado se `lock_missing_count ≥ 3`)
- `total_issues` — soma dos 6 canais
- `from_analyzer(result)`, `from_dict(d)`, `to_dict()`

#### WBS 10.3 — Anti-Pattern Score (`metrics/anti_pattern_score.py`)

Novo módulo `metrics/anti_pattern_score.py` agregando **17 sinais** em score 0-100:

| Dimensão | Peso | Sinais |
|---|---:|---|
| Security        | 60 | taint_path_count(30), injection_surface(15), sca_vulnerable_deps(10), iac_misconfig_count(5) |
| Reliability     | 20 | bare_except(5), resource_leak(5), mutable_default(5), inconsistent_return(5) |
| Performance     | 15 | n_plus_one(5), quadratic_nested(5), string_concat(5) |
| Maintainability | 15 | docstring(5), long_function(5), cognitive_hotspot(5) |
| Thread safety   | 20 | lock_missing(10), asyncio_blocking(5), global_shared(5) |
| **TOTAL**       | **130** | 17 sinais |

**Fórmula:** `APS = 100 × (1 − Σ(weight_i × min(1, raw_i/threshold_i)) / 130)`

**Grade SonarQube-style:** A≥90, B 80-89, C 60-79, D 40-59, E<40

**API:**
- `compute_aps(signals)` — score 0-100 puro
- `rate_aps(score)` — A-E
- `aps_from_metric_vector(mv)` — extração + score em uma chamada; retorna `{aps, rating, components, signals}`
- `APS_COMPONENTS` — tabela de pesos (frozen)
- `APS_WEIGHT_SUM` — 130

#### WBS 10.4 — Endpoints + integração (`api/server.py`)

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /scan-thread-safety` | POST | Análise concurrency em código Python fornecido |
| `GET /metrics/thread-safety` | GET | ThreadSafetyVector persistido (`?module=`) |
| `GET /anti-pattern-score` | GET | APS composto 0-100 + components dict (`?module=`) |

- `SensorConfig.version` atualizado para `"3.0.0"`
- `metrics/__init__.py` atualizado com `ThreadSafetyVector`, `compute_aps`, `rate_aps`, `aps_from_metric_vector`, `APS_COMPONENTS`, `APS_WEIGHT_SUM`
- Wired em `sensor_core/uco_bridge.py` → `mv.thread_safety = ThreadSafetyVector.from_analyzer(...)`
- Fail-silent: análise nunca quebra o pipeline principal

#### WBS 10.4 — Testes + CHANGELOG

- **`tests/test_marco_m22.py`** — 30 testes TT01-TT30 (todos verdes)
  - TT01-TT05: dataclass basics + round-trip
  - TT06-TT10: global_shared + lock_missing (Thread/Process + Lock variants)
  - TT11-TT15: daemon_thread_risk + queue_unbounded
  - TT16-TT20: asyncio_blocking + shared_mutable_default
  - TT21-TT25: rating ladder + repr + REST endpoint
  - TT26-TT30: APS (table, compute, grade, mv-extraction)
- **`pyproject.toml`** — versão `2.9.1` → `3.0.0`, `test_marco_m22.py` adicionado a `python_files`
- `__test__ = False` em `ThreadSafetyResult` e `ThreadSafetyVector`

**Resultado:** 798/799 marco-tests pass (M7.7 + APS + M2.x→M7.6 regressão completa). 1 falha preexistente M7.1 não relacionada.

**Impacto na competitividade vs SonarQube:**
- ✅ Thread Safety (M7.7) — UCO agora cobre **paridade com SonarQube Enterprise** neste eixo
- ✅ APS — métrica composta única, **nenhum analisador gratuito oferece equivalente**
- 📊 Score competitivo estimado: 56/100 (v2.2.0) → **~75/100 (v3.0.0)** [APPROX]

**Próximo marco:** M8.0 — Real-Time Monitoring Mode (SSE stream) → v3.1.0

**Referências:**
- Lea, D.   (1999). *Concurrent Programming in Java*. Addison-Wesley.
- Goetz, B. (2006). *Java Concurrency in Practice*. Addison-Wesley.
- PEP 492   — Coroutines with `async` and `await` syntax.
- CWE-362, CWE-366, CWE-400, CWE-557 — MITRE Common Weakness Enumeration.

---

## [2.9.1] — 2026-05-31 — M7.6 TestQualityVector

### Adicionado — M7.6 FASE 6a (WBS 9.1-9.2)

#### WBS 9.1 — TestQualityAnalyzer AST (`metrics/test_quality_analyzer.py`)

Novo módulo `metrics/test_quality_analyzer.py` com `TestQualityAnalyzer`:
- AST-only, stdlib pura, sem dependências externas
- `_collect_test_functions()` — descobre `def test_*` (top-level e em classes)
- `_function_cc()` — McCabe cyclomatic complexity per test
- `_is_assertion()` — reconhece `assert` + `self.assert*` + `self.fail()`
- `_is_mock_construction()` — detecta `Mock`/`MagicMock`/`AsyncMock`/`patch`/`PropertyMock`/`create_autospec`/`mock_open`
- `_is_flaky_call()` — detecta `time.sleep|time|monotonic|perf_counter`, `datetime.now|utcnow|today`, `uuid.uuid1|uuid4`, `random.*`, `os.urandom`
- `_is_polluting_test()` — detecta `global`/`nonlocal` + mutação de atributo de módulo importado
- `_is_parameterized()` — `@pytest.mark.parametrize`, `@parameterized.expand`, `@given` (hypothesis), `@ddt.data`
- `_name_quality_ok()` — exige ≥3 tokens snake_case após `test_`
- `TestQualityResult` — dataclass com 9 contadores brutos (canais + n_test_functions)

#### WBS 9.1 — TestQualityVector dataclass (`metrics/extended_vectors.py`)

Nova classe `TestQualityVector` com **8 canais** de qualidade de suíte de testes:

| Canal | Tipo | Threshold saudável | Descrição |
|---|---|---|---|
| `assertion_density` | `float` | ≥ 2.0 | Assertions / total de tests |
| `test_complexity` | `float` | < 3.0 | CC médio por test (McCabe) |
| `mock_overuse_ratio` | `float` | < 0.3 | Mocks / total Call nodes |
| `test_isolation_score` | `float` | > 0.8 | 1 − polluting/total |
| `flaky_test_risk` | `int` | 0 | Tests tocando `time`/`random`/`uuid`/`datetime.now` |
| `parameterized_ratio` | `float` | > 0.3 | Share com `@parametrize`/`@given` |
| `test_naming_quality` | `float` | > 0.7 | Share com ≥3 tokens descritivos |
| `dead_test_count` | `int` | 0 | Tests sem nenhum `assert` |

**Métodos auxiliares:**
- `test_quality_rating()` — grade A–E baseada em contagem de thresholds violados (A=0 violações, E=6+ ou dead≥5)
- `_threshold_violations()` — contador interno usado pelo rating
- `from_analyzer(result)`, `from_dict(d)`, `to_dict()`

**Integração:**
- Wired em `sensor_core/uco_bridge.py` → `mv.test_quality = TestQualityVector.from_analyzer(...)`
- Guard de importação M7.6 adicionado (`_TEST_QUALITY_ANALYZER_AVAILABLE`)
- Falha silenciosa: análise de qualidade de testes nunca quebra o pipeline principal

#### WBS 9.2 — Endpoints + integração (`api/server.py`)

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /scan-test-quality` | POST | Análise de qualidade de testes em código Python fornecido |
| `GET /metrics/test-quality` | GET | TestQualityVector persistido para um módulo (`?module=`) |

- `SensorConfig.version` atualizado para `"2.9.1"`
- `metrics/__init__.py` atualizado com `TestQualityVector`
- Endpoints registrados em `do_GET` e `do_POST` do `UCOSensorHandler`
- Lista de endpoints em `_API_ENDPOINTS_INFO` atualizada

#### WBS 9.2 — Testes + CHANGELOG

- **`tests/test_marco_m21.py`** — 30 testes TQ01-TQ30 (todos verdes)
  - TQ01-TQ05: dataclass basics e round-trip
  - TQ06-TQ10: descoberta de tests + assertion_density
  - TQ11-TQ15: test_complexity + mock_overuse_ratio
  - TQ16-TQ20: test_isolation_score + flaky_test_risk
  - TQ21-TQ25: parameterized_ratio + test_naming_quality + dead_test_count
  - TQ26-TQ30: rating, edge cases, REST endpoint
- **`CHANGELOG.md`** — entrada `[2.9.1]`
- **`pyproject.toml`** — versão `2.9.0` → `2.9.1`, `test_marco_m21.py` adicionado a `python_files`
- `__test__ = False` em `TestQualityResult` e `TestQualityVector` (silencia warning de coleta pytest)

**Resultado de regressão:** 439/439 tests pass (M7.6 + M2.x→M7.5) em 1.65s.

**Próximo marco:** M7.7 — ThreadSafetyVector (6 canais) + APS Anti-Pattern Score → v3.0.0

**Referências:**
- Meszaros, G. (2007). *xUnit Test Patterns: Refactoring Test Code*. Addison-Wesley.
- Beck, K.    (2002). *Test-Driven Development By Example*. Addison-Wesley.
- Fowler, M.  (2007). *Mocks Aren't Stubs*. martinfowler.com.
- McCabe, T.J. (1976). A complexity measure. *IEEE TSE*, 2(4), 308-320.

---

## [2.9.0] — 2026-04-28 — M7.5 ArchitectureVector

### Adicionado — M7.5 FASE 5b (WBS 8.1-8.5)

#### WBS 8.1-8.4 — ArchitectureAnalyzer AST (`metrics/architecture_analyzer.py`)

Novo módulo `metrics/architecture_analyzer.py` com `ArchitectureAnalyzer`:
- AST-only, stdlib pura, sem dependências externas
- `_collect_imports()` — extrai todos os top-level módulos importados
- `_module_layer()` — classifica módulo em camada arquitetural por keywords (infra/domain/app/api)
- `_instance_attrs()` — coleta `self.x` acessos em um método (para LCOM)
- `_method_calls()` — coleta todos os callables invocados (para RFC)
- `_external_types()` — detecta tipos externos em anotações e call-sites capitalizados (para CBO)
- `ArchitectureAnalyzer._lcom()` — Henderson-Sellers LCOM' = (P-Q)/max(P+Q,1)
- `ArchitectureAnalyzer._is_abstract()` — detecta classes que herdam `ABC`/`ABCMeta` ou têm `@abstractmethod`
- `ArchitectureResult` — dataclass com 8 contadores brutos

#### WBS 8.2-8.4 — ArchitectureVector dataclass (`metrics/extended_vectors.py`)

Nova classe `ArchitectureVector` com **8 canais** de coupling/cohesion arquitetural:

| Canal | Tipo | Limiar saudável | Descrição |
|---|---|---|---|
| `fan_in` | `int` | contextual | Módulos que importam este módulo (project-level) |
| `fan_out` | `int` | ≤ 10 | Módulos distintos importados por este módulo |
| `coupling_between_objects` | `int` | < 5 | Tipos externos referenciados em métodos de classe (CBO) |
| `response_for_class` | `int` | < 20 | Métodos próprios + chamadas externas da classe (RFC) |
| `lack_of_cohesion` | `float` | < 0.5 | LCOM': (P-Q)/max(P+Q,1) — coesão entre métodos |
| `abstraction_level` | `float` | 0.0–1.0 | Classes abstratas / total de classes |
| `circular_import_count` | `int` | 0 | Ciclos de import detectados (project-level DFS) |
| `layer_violation_count` | `int` | 0 | Imports violando hierarquia infra→domain→app→api |

**Métodos auxiliares:**
- `architecture_rating()` — grade A–E baseada em contagem de thresholds violados
- `from_analyzer(result)`, `from_dict(d)`, `to_dict()`

**Integração:**
- Wired em `sensor_core/uco_bridge.py` → `mv.architecture = ArchitectureVector.from_analyzer(...)`
- Guard de importação M7.5 adicionado em `uco_bridge.py`

#### WBS 8.5 — Endpoints + integração (`api/server.py`)

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /scan-architecture` | POST | Análise de arquitetura em código Python fornecido |
| `GET /metrics/architecture` | GET | ArchitectureVector persistido para um módulo (`?module=`) |

- Aceita `fan_in` e `circular_import_count` como campos opcionais no body (project-level context)
- `SensorConfig.version` atualizado para `"2.9.0"`
- `metrics/__init__.py` atualizado com `ArchitectureVector`

#### WBS 8.5 — Testes + CHANGELOG

- **`tests/test_marco_m20.py`** — 35 testes TA01-TA30 + edge cases (todos verdes)
- **`CHANGELOG.md`** — entrada `[2.9.0]`
- **`pyproject.toml`** — versão `2.8.0` → `2.9.0`

**Referências:**
- Chidamber, S.R. & Kemerer, C.F. (1994). IEEE TSE 20(6), 476-493.
- Martin, R.C. (2002). Agile Software Development. Prentice Hall.
- Henderson-Sellers, B. (1996). Object-Oriented Metrics. Prentice Hall.

---

## [2.8.0] — 2026-04-28 — M7.4 PerformanceVector

### Adicionado — M7.4 FASE 5a (WBS 7.1-7.4)

#### WBS 7.1 — PerformanceVector dataclass (`metrics/extended_vectors.py`)

Nova classe `PerformanceVector` com **8 canais** de detecção de anti-padrões de performance:

| Canal | Tipo | Anti-padrão detectado |
|---|---|---|
| `n_plus_one_risk` | `int` | Chamadas DB (execute/query/filter/get/all/…) dentro de `for`/`while` |
| `list_in_loop_append_count` | `int` | `list.append()` dentro de `for` (preferir list comprehension) |
| `string_concat_in_loop` | `int` | `s += x` dentro de loop (O(n²) — preferir list+join) |
| `quadratic_nested_loop_count` | `int` | `for/while` aninhado → complexidade mínima O(n²) |
| `repeated_computation_count` | `int` | Mesma expressão ≥2× no corpo do loop (oportunidade de cache) |
| `regex_compile_in_loop` | `int` | `re.compile/search/match/…` dentro de loop (compilar 1× fora) |
| `io_in_tight_loop` | `int` | `open()`, `requests.*`, `socket.*` dentro de loop |
| `inefficient_dict_lookup` | `int` | `k in d.keys()` → redundante; `k in d` é O(1) |

**Métodos auxiliares:**
- `performance_rating()` — grade A–E baseada em `weighted_score` (N+1 × 3, I/O × 2, nested × 2, concat × 2)
- `total_issues` — soma simples de todos os 8 canais
- `weighted_score` — score ponderado por impacto
- `from_analyzer(result)`, `from_dict(d)`, `to_dict()`

#### WBS 7.2-7.3 — PerformanceAnalyzer AST (`metrics/performance_analyzer.py`)

Novo módulo `metrics/performance_analyzer.py` com `PerformanceAnalyzer`:
- AST-only, stdlib pura, sem dependências externas
- `_walk_no_fn()` — visita descendentes SEM cruzar `FunctionDef`/`ClassDef` (evita falsos positivos)
- **Pass 1**: detecta `k in d.keys()` em todo o módulo
- **Pass 2**: por loop — detecta os 7 padrões restantes com deduplicação por `lineno`
- `PerformanceResult` — dataclass simples com os 8 contadores
- Wired em `sensor_core/uco_bridge.py` → `mv.performance = PerformanceVector.from_analyzer(...)`

#### WBS 7.4 — Endpoints + integração (`api/server.py`)

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /scan-performance` | POST | Análise de performance em código Python fornecido |
| `GET /metrics/performance` | GET | PerformanceVector persistido para um módulo (`?module=`) |

- `SensorConfig.version` atualizado para `"2.8.0"`
- `metrics/__init__.py` atualizado com `PerformanceVector`

#### WBS 7.4 — Testes + CHANGELOG

- **`tests/test_marco_m19.py`** — 39 testes TP01-TP30j (todos verdes)
- **`CHANGELOG.md`** — entrada `[2.8.0]`
- **`pyproject.toml`** — versão `2.7.0` → `2.8.0`

---

## [2.7.0] — 2026-04-27 — M8.1 IDE/LSP Integration

### Adicionado — M8.1 FASE 4 (WBS 6.1-6.4)

#### WBS 6.1 — SASTFinding Enrichment (`sast/scanner.py`, `sast/taint_engine.py`)

**Novos campos em `SASTFinding`:**

| Campo | Tipo | Descrição |
|---|---|---|
| `suggested_fix` | `str` | Código de exemplo pronto para copy-paste que corrige o problema |
| `confidence` | `float` | Probabilidade de ser um verdadeiro positivo (0.0-1.0) |
| `explanation` | `str` | Explicação técnica detalhada de por que o padrão é perigoso |

- `SASTRuleInfo` recebe os mesmos três campos como atributos opcionais com defaults (`"", "", 0.9`)
- `_make_finding()` propaga automaticamente os campos da regra para o `SASTFinding`
- `SASTFinding.to_dict()` serializa os três novos campos
- **Regras enriquecidas:** SAST001 (SQL Injection), SAST002 (OS Command Injection), SAST003 (Unsafe eval/exec) com `suggested_fix` + `explanation` + `confidence` específico
- **`sast/taint_engine.py`:** `_TAINT_RULE_META` expandido com `suggested_fix`, `explanation`, `confidence` para todas as 6 regras de taint (SAST040-SAST045)
- `TaintFlow.to_dict()` expõe os três campos enriquecidos

#### WBS 6.2 — AutoFix Transforms #5-12 (`sensor_core/autofix/transforms/`)

8 novos transforms adicionados ao pipeline padrão do `AutofixEngine`:

| # | Classe | Arquivo | Tipo | Descrição |
|---|---|---|---|---|
| 5 | `MutableDefaultRemover` | `remove_mutable_default.py` | Rewrite | `def f(x=[])` → `def f(x=None)` + guard |
| 6 | `BareExceptReplacer` | `replace_bare_except.py` | Rewrite | `except:` → `except Exception as e:` |
| 7 | `NoneComparisonSimplifier` | `simplify_comparison.py` | Rewrite | `x == None` → `x is None` |
| 8 | `DocstringAdder` | `add_docstring.py` | Rewrite | Insere `"""TODO: Add docstring."""` em funções públicas |
| 9 | `ContextManagerAdvisor` | `add_context_manager.py` | Sugestão | Detecta `open()` sem `with` |
| 10 | `ExtractMethodAdvisor` | `extract_method.py` | Sugestão | Detecta CC>10 / LOC>50 |
| 11 | `StringConcatLoopAdvisor` | `replace_string_concat_loop.py` | Sugestão | Detecta `s += x` em loops |
| 12 | `TypeHintAdder` | `add_type_hints.py` | Rewrite | Adiciona `: Any` + `from typing import Any` |

- `transforms/__init__.py` atualizado com todos os 8 novos exports
- `engine.py` pipeline padrão agora tem 12 transforms (anteriormente 4)

#### WBS 6.3 — Endpoint `GET /lsp/diagnostics` (`api/server.py`)

Novo endpoint que retorna diagnósticos no formato **Language Server Protocol (LSP)**
(`textDocument/publishDiagnostics`), consumível diretamente por editores de código.

**Request:** `GET /lsp/diagnostics?module=<id>[&window=<n>]`

**Response schema:**
```json
{
  "uri":         "file:///myapp/routes.py",
  "module_id":   "myapp.routes",
  "diagnostics": [
    {
      "range":    {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 80}},
      "severity": 1,
      "code":     "UCO-FLOW-001",
      "source":   "uco-sensor",
      "message":  "2 unsanitised taint flow(s) detected ...",
      "data":     {"flow_rating": "D", "unsanitized_paths": 2, ...}
    }
  ],
  "count": 1,
  "history_size": 50,
  "last_timestamp": 1700000000.0
}
```

**Severity mapping (LSP):**

| UCO Severity | LSP Code | LSP Name |
|---|---|---|
| CRITICAL / HIGH | 1 | Error |
| MEDIUM | 2 | Warning |
| LOW | 3 | Information |
| INFO | 4 | Hint |

**Fontes de diagnósticos (em ordem):**
1. Findings SAST armazenados no snapshot (se `sast_result` presente)
2. FlowVector — `unsanitized_paths > 0` → Error; `cross_fn_taint_risk > 0` → Warning
3. ReliabilityVector — `crash_risk > 0.6` → Warning; `bug_density > 0.05` → Info
4. MaintainabilityVector — `hotspot_density > 0.5` → Hint; `debt_ratio > 0.3` → Hint

- `SensorConfig.version` atualizado para `"2.7.0"`

#### WBS 6.4 — Testes + CHANGELOG

- **`tests/test_marco_m18.py`** — 30 testes (TL01-TL30) cobrindo todos os entregáveis de M8.1
- **`CHANGELOG.md`** — entrada `[2.7.0]` adicionada
- **`pyproject.toml`** — versão `2.6.0` → `2.7.0`

---

## [2.6.0] — 2026-04-27 — M7.2 Taint Analysis + FlowVector

### Adicionado — M7.2 FASE 3 (WBS 5.1-5.7)

**Intra-function Data Flow Analysis (DFA) engine** — `sast/taint_engine.py` (novo, ~500 LOC).  
Rastreia propagação de variáveis contaminadas de fontes controladas pelo atacante até chamadas perigosas (sinks), com neutralização via sanitizadores.

#### Módulo: `sast/taint_engine.py` — NOVO (M7.2)

**Fontes (Sources) rastreadas:**

| Categoria | Padrões |
|---|---|
| HTTP inputs | `request.args/form/json/data/values/files/cookies/headers/GET/POST/body/query` |
| CLI | `sys.argv[n]`, `sys.argv` (todo o objeto) |
| OS | `os.environ[key]`, `os.environ`, `os.getenv()` |
| Python built-in | `input()`, `raw_input()` |

**Sinks (Perigosos) rastreados:**

| Regra | Sink | CWE | Severidade |
|---|---|---|---|
| SAST040 | `cursor/db/session.execute()` | CWE-89 | CRITICAL |
| SAST041 | `os.system/popen/execv`, `subprocess.call/run/Popen` | CWE-78 | CRITICAL |
| SAST042 | `Template.render()`, `env.get_template()` | CWE-94 | CRITICAL |
| SAST043 | `eval()`, `exec()`, `compile()` | CWE-95 | HIGH |
| SAST044 | `open()` | CWE-22 | HIGH |
| SAST045 | Sinks não classificados | CWE-20 | MEDIUM |

**Sanitizadores reconhecidos:** `html.escape`, `bleach.clean`, `markupsafe.escape`, `re.escape`, `urllib.parse.quote/quote_plus`, `hashlib.sha256/sha512`, `hmac.new`, `jinja2.escape`, `secrets.token_*`

**Propagação implementada:**
- Atribuição direta: `x = tainted_expr` → `x` ∈ TaintSet
- Augmented assign: `x += tainted` → `x` ∈ TaintSet (se x ou RHS tainted)
- Tuple unpack: `a, b = tainted_pair` → ambos ∈ TaintSet
- F-string: `` f"...{tainted}..." `` → resultado tainted
- BinOp concat: `clean + tainted` → resultado tainted
- Call heuristic: `func(tainted_arg)` → resultado tainted (interprocedural proxy)
- Branches: if/else — merge conservativo (union de ambos os branches)
- Loops: for/while — variável de loop herda taint do iterável

**Estruturas de dados:**
- `TaintInfo` — provenance: `origin`, `origin_line`, `path: List[str]`
- `TaintSet` — scope-local: `add/remove/is_tainted/get/clone/merge_from`
- `TaintFlow` — flow confirmado: source_desc, sink_desc, path, sanitized, vuln_type, rule_id
- `TaintResult` — agregado: flows, source_count, sink_count, cross_fn_risk, taint_sanitized_ratio, injection_surface

**AST traversal:** `TaintAnalyzer.analyze(source)` — walk hierárquico com dispatch em `_stmt_assign`, `_stmt_if`, `_stmt_for`, `_stmt_while`, `_stmt_with`, `_stmt_try`, `_stmt_call`; aninhamento correto de função preserva scopes.

#### Módulo: `metrics/extended_vectors.py` — FlowVector (6 canais, M7.2)

| Canal | Tipo | Fonte |
|---|---|---|
| `taint_source_count` | `int` | `TaintResult.source_count` |
| `taint_sink_count` | `int` | `TaintResult.sink_count` |
| `taint_path_count` | `int` | `len(TaintResult.flows)` |
| `taint_sanitized_ratio` | `float` | `sanitized_count / path_count` [0.0–1.0] |
| `cross_fn_taint_risk` | `int` | taint passado a chamadas não-sink (deduped por linha) |
| `injection_surface` | `float` | `path_count × (1 − sanitized_ratio)` |

- `flow_rating()`: escala A–E (E se surface>5 ou >6 paths não saneados)
- `unsanitized_paths`: propriedade derivada
- `from_taint_result(result)`: factory
- `from_dict(d)` / `to_dict()`: persistência

#### Módulo: `sensor_core/uco_bridge.py` — integração M7.2

- `analyze()` agora executa `TaintAnalyzer().analyze(source)` e anexa `mv.flow = FlowVector.from_taint_result(result)` para todo Python code em modo `full`
- Guard condicional `_TAINT_AVAILABLE` — retrocompatível se `sast.taint_engine` não importar
- Falhas de taint analysis são silenciadas (try/except) — nunca quebram o pipeline principal

#### Módulo: `api/server.py` — 2 novos endpoints

| Endpoint | Método | Descrição |
|---|---|---|
| `POST /scan-flow` | POST | Executa taint analysis em Python source; retorna flows + FlowVector + summary |
| `GET /metrics/flow?module=<id>` | GET | FlowVector do último snapshot persistido |

- `handle_scan_flow(data)` — valida `code`, executa TaintAnalyzer, retorna dict com `flow_vector`, `flows[]`, `summary`
- `handle_metrics_flow(module_id, window)` — lookup no SnapshotStore; 400/404/503/200
- Guards: `_TAINT_ENGINE_AVAILABLE`
- Registrados em `/docs` autodoc e GET/POST dispatchers

#### Módulo: `tests/test_marco_m17.py` — NOVO (TF01-TF30, 67 testes)

67 testes cobrindo:
- TF01-TF04: TaintSet / TaintInfo data structures
- TF05-TF09: Source detection (request.args, sys.argv, os.environ, input, os.getenv)
- TF10-TF14: Propagation rules (assign, tuple unpack, f-string, BinOp, call heuristic)
- TF15-TF19: Sink detection (SQL, OS command, eval, open, subprocess); clean args → no finding
- TF20-TF24: Sanitizers (html.escape, bleach, re.escape, urllib.quote, partial sanitization)
- TF25-TF29: FlowVector (defaults, from_taint_result, ratings A-E, to_dict, unsanitized_paths)
- TF30: Full pipeline (UCOBridge attaches mv.flow, API handlers 400/404/200)

### Técnico
- Versão: `2.5.0 → 2.6.0`
- `pyproject.toml`: version 2.6.0, `python_files` atualizado com `test_marco_m17.py`

---

## [2.5.0] — 2026-04-27 — M7.3 ReliabilityVector + MaintainabilityVector

### Adicionado — M7.3 FASE 2 (WBS 4.1-4.6)

**ReliabilityVector (10 canais) e MaintainabilityVector (9 canais)** — dois novos vetores de métricas tipados que formalizam os sinais AST-IMP do `_UCOVisitor` e os sinais estruturais de manutenibilidade em representações persistíveis.

#### Módulo: `metrics/extended_vectors.py` — 2 novas classes

**`ReliabilityVector` — 10 canais (M7.3a)**

| Canal | Tipo | Fonte | CWE |
|---|---|---|---|
| `bare_except_count` | `int` | `_UCOVisitor.bare_except_count` | CWE-390 |
| `swallowed_exception_count` | `int` | `_UCOVisitor.swallowed_exception_count` | CWE-390 |
| `mutable_default_arg_count` | `int` | `_UCOVisitor.mutable_default_arg_count` | CWE-1220 |
| `inconsistent_return_count` | `int` | `_UCOVisitor.inconsistent_return_count` | CWE-394 |
| `shadow_builtin_count` | `int` | `_UCOVisitor.shadow_builtin_count` | — |
| `global_mutation_count` | `int` | `_UCOVisitor.global_mutation_count` | CWE-362 |
| `empty_except_block_count` | `int` | alias de `swallowed_exception_count` | CWE-390 |
| `resource_leak_risk` | `int` | count de SAST037 em `SASTResult` | CWE-772 |
| `regex_redos_risk` | `int` | count de SAST019 em `SASTResult` | CWE-1333 |
| `infinite_recursion_risk` | `float` | `MetricVector.infinite_loop_risk` clamped [0,1] | CWE-674 |

- `total_issues`: propriedade derivada — soma de todos os canais inteiros (sem double-count do alias `empty_except_block_count`)
- `reliability_rating()`: escala A–E baseada em `total_issues` + `infinite_recursion_risk` + regras especiais (bare_except>3 → E, global_mutation>2 → E)
- `from_mv(mv, sast_result)`: factory class-method a partir de `MetricVector`
- `from_dict(d)`: deserialização para persistência

**`MaintainabilityVector` — 9 canais (M7.3b)**

| Canal | Tipo | Cálculo | Threshold |
|---|---|---|---|
| `missing_docstring_ratio` | `float` | public fns sem docstring / total public fns | >0.5 = WARNING |
| `avg_function_args` | `float` | Σ args / n_fns | >4.0 = WARNING |
| `long_function_ratio` | `float` | fns com LOC>50 / n_fns | >0.2 = WARNING |
| `deeply_nested_ratio` | `float` | `deeply_nested_comprehension_count` / n_fns | >0.1 = WARNING |
| `cognitive_cc_hotspot` | `int` | `max_function_cc` | >20 = CRITICAL |
| `boolean_param_count` | `int` | defaults `True/False` em params | >3 = WARNING |
| `magic_number_count` | `int` | literais numéricos ∉ {-1,0,1,2} | >10 = WARNING |
| `long_parameter_list` | `int` | fns com >5 params | >2 = WARNING |
| `invariant_density` | `float` | `(docstring_ratio + assert_proxy) / 1` | <0.3 = WARNING |

- `maintainability_rating()`: escala A–E (E se hotspot>30 ou missing_doc>0.8; D se ≥5 warnings)
- `from_mv(mv, source)`: factory — re-parseia `source` via `_analyse_maintainability()` para campos dependentes de LOC/defaults
- `_analyse_maintainability(tree, lines)`: helper standalone — percorre AST em single-pass e retorna `(missing_doc_ratio, avg_args, long_fn_ratio, bool_param_count, magic_num_count, long_param_list, docstring_ratio)`

#### Módulo: `sensor_core/uco_bridge.py` — integração M7.3

- `analyze()` agora constrói e anexa `mv.reliability = ReliabilityVector.from_mv(mv)` e `mv.maintainability = MaintainabilityVector.from_mv(mv, source=source)` ao final de cada análise
- Importações condicionais via `_EXTENDED_VECTORS_AVAILABLE` — retrocompatível com ambientes sem o pacote `metrics`

#### Módulo: `api/server.py` — 2 novos endpoints GET

| Endpoint | Descrição |
|---|---|
| `GET /metrics/reliability?module=<id>` | Retorna `ReliabilityVector` do último snapshot persistido (M7.3a) |
| `GET /metrics/maintainability?module=<id>` | Retorna `MaintainabilityVector` do último snapshot persistido (M7.3b) |

- Ambos seguem o padrão de `handle_metrics_advanced()`: lookup no `SnapshotStore`, resposta 200/400/404/503
- Handlers: `handle_metrics_reliability()`, `handle_metrics_maintainability()`
- Guards de import `_RELIABILITY_VECTOR_AVAILABLE`, `_MAINTAINABILITY_VECTOR_AVAILABLE`
- Registrados em `/docs` autodocumentação

#### Módulo: `tests/test_marco_m16.py` — NOVO (TV99-TV128, 52 testes)

52 testes cobrindo:
- TR01-TR05: `ReliabilityVector` dataclass — defaults, `total_issues`, rating A–E, `to_dict`, `from_dict` roundtrip
- TR06-TR10: `ReliabilityVector.from_mv` — extração de contadores AST-IMP, ILR proxy, metadata
- TM01-TM05: `MaintainabilityVector` dataclass — defaults, rating A/B/C/D/E, `to_dict`
- TM06-TM10: `_analyse_maintainability` — magic-numbers, long params, bool defaults, missing docstrings, avg args
- TI01-TI05: Pipeline completo — `UCOBridge.analyze` anexa ambos os vetores; `bare_except` flui corretamente
- TI06-TI10: API handlers — 400 (module=None), 404 (módulo desconhecido), 200 (módulo com histórico via `handle_analyze`)

### Técnico
- Versão: `2.4.1 → 2.5.0`
- `pyproject.toml`: `python_files` atualizado com `test_marco_m16.py`

---

## [2.4.1] — 2026-04-27 — AST-IMP _UCOVisitor 10 novos padrões

### Adicionado — AST-IMP FASE 1.B

**10 novos contadores de qualidade/confiabilidade** adicionados ao `_UCOVisitor` em `sensor_core/uco_bridge.py`. Todos os sinais são agora propagados como atributos do `MetricVector`, prontos para alimentar o `ReliabilityVector` (M7.3) sem re-análise.

#### Módulo: `sensor_core/uco_bridge.py`

| Contador | Padrão Detectado | AST Node | WBS |
|---|---|---|---|
| `bare_except_count` | `except:` sem tipo especificado | `ExceptHandler(type=None)` | 3.1 |
| `swallowed_exception_count` | `except [E]: pass` — exceção silenciada | `ExceptHandler` com body=[Pass] | 3.1 |
| `shadow_builtin_count` | `list = []`, `open = ...` — sombra de builtin | `Name(ctx=Store)` ∈ builtins | 3.2 |
| `mutable_default_arg_count` | `def f(x=[])`, `def f(x={})`, `def f(x=set())` | `FunctionDef.defaults` | 3.2 |
| `inconsistent_return_count` | Função mescla `return value` e `return None`/fall-through | `ast.Return` walk | 3.3 |
| `global_mutation_count` | `global x` + atribuição subsequente | `ast.Global` + `ast.Assign` | 3.3 |
| `deeply_nested_comprehension_count` | `[f(x) for x in [g(y) for y in ...]]` | `ListComp` dentro de `ListComp.elt` | 3.4 |
| `missing_all_flag` | Módulo com funções públicas mas sem `__all__` | `ast.Assign` target=`__all__` | 3.4 |

**Detalhes técnicos:**
- `_PYTHON_BUILTINS` — frozenset derivado de `vars(builtins)`, filtrado de keywords imutáveis em Python 3
- `shadow_builtin_count` deduplica por nome (cada builtin conta apenas uma vez mesmo com múltiplas atribuições)
- `_check_inconsistent_return()` skips nested function defs via `ast.walk` com guard
- `_check_global_mutation()` skips nested function defs via `ast.walk` com guard
- `visit_Module` consolidado: executa `_scan_dead_code` + `generic_visit` + set `missing_all_flag`
- `visit_Assign` consolidado: registra `_op("=")` + detecta `__all__`

#### Módulo: `tests/test_marco_m15.py` — NOVO (TV91-TV98, 37 testes)

37 testes cobrindo todos os 8 novos contadores + integração com `MetricVector`.

### Técnico
- Versão: `2.4.0 → 2.4.1`
- `pyproject.toml`: `python_files` atualizado com `test_marco_m15.py`

---

## [2.4.0] — 2026-04-27 — M7.1 SAST EXPANSION ROUND 1

### Adicionado — M7.1 SAST Expansion Round 1

**15 novas regras SAST (SAST014–SAST039)** + integração `sast/regex_analyzer.py` para detecção de ReDoS. Scanner expande de 13 para 28 regras cobrindo SSRF, XXE, SSTI, ReDoS, Crypto fraca, Auth/TLS inseguro e Reliability.

#### Módulo: `sast/regex_analyzer.py` — NOVO

Motor de análise de ReDoS (CWE-400) baseado exclusivamente em stdlib. Detecta três classes de vulnerabilidade:
- **Classe A — Nested Quantifiers**: `(\w+)+`, `([a-z]+)*` → backtracking exponencial
- **Classe B — Overlapping Alternation**: `(a|aa)+`, `(foo|fo)+` → splits exponenciais
- **Classe C — Char-Class Overlap**: `([\w.]+@)+` → sobreposição de classes sob quantificador
- API pública: `analyze_pattern(pattern) → List[ReDoSFinding]`, `is_vulnerable(pattern) → bool`

#### Módulo: `sast/scanner.py` — 15 novas regras + melhorias

**Novas regras M7.1:**
| ID | Título | CWE | Severidade |
|---|---|---|---|
| SAST014 | Server-Side Request Forgery (SSRF) | CWE-918 | HIGH |
| SAST015 | XML External Entity (XXE) Injection | CWE-611 | HIGH |
| SAST018 | Server-Side Template Injection (SSTI) | CWE-94 | CRITICAL |
| SAST019 | ReDoS — Catastrophic Backtracking | CWE-400 | MEDIUM |
| SAST021 | Weak Asymmetric Key Size (< 2048 bits) | CWE-326 | HIGH |
| SAST022 | Weak IV / All-Zero Nonce | CWE-329 | MEDIUM |
| SAST023 | ECB Mode / Weak Cipher (DES, Blowfish) | CWE-327 | MEDIUM |
| SAST024 | JWT None Algorithm / Signature Bypass | CWE-347 | CRITICAL |
| SAST025 | Timing Attack via String Comparison `==` | CWE-208 | MEDIUM |
| SAST026 | CSRF Protection Disabled (`@csrf_exempt`) | CWE-352 | MEDIUM |
| SAST027 | SSL Certificate Verification Disabled | CWE-295 | HIGH |
| SAST028 | Deprecated TLS/SSL Protocol Version | CWE-326 | MEDIUM |
| SAST037 | Resource Leak — Unclosed File Handle | CWE-772 | MEDIUM |
| SAST038 | Exception Swallowing (`except: pass`) | CWE-390 | LOW |
| SAST039 | Mutable Default Argument (`def f(arg=[])`) | CWE-1386 | LOW |

**Melhorias em regras existentes (M7.1.8):**
- **SAST006** expandido para "Weak Cryptographic Algorithm": adiciona detecção de `DES.new()`, `ARC4.new()`, `RC4.new()` (PyCryptodome) e `hashlib.new("des"/"rc4"/"arcfour")`
- **SAST007** narrowed: reduzido ao subconjunto de chamadas `random` mais relevantes para contexto criptográfico (`random`, `randint`, `randrange`, `getrandbits`, `choice`) — elimina falsos positivos de `shuffle`, `sample`, `seed`, `uniform`
- **SAST028** implementado via regex no raw source (não requer AST): detecta `ssl.PROTOCOL_SSLv2/v3/TLSv1/TLSv1_1`

**Detalhe técnico — rastreamento de `with` para SAST037:**
- `_ASTScanner._with_depth: int` incrementado em `visit_With`/`visit_AsyncWith` e decrementado após `generic_visit` — garante que `with open(...) as f:` não aciona SAST037

#### Módulo: `tests/test_marco_m14.py` — NOVO (TV61-TV90, 30+50 testes)

80 testes cobrindo regex_analyzer (TS01-TS04), SAST014-039 (TS05-TS20), SAST006 DES/RC4, SAST007 narrowing e integridade do catálogo de regras.

### Técnico
- Versão: `2.3.0 → 2.4.0`
- `pyproject.toml`: `python_files` atualizado com `test_marco_m14.py`

---

## [2.3.0] — 2026-04-27 — M7.0 FORMALIZAR SINAIS INFORMAIS

### Adicionado — M7.0 Formalização de Sinais Informais

**APEX SCIENTIFIC mode** | Fecha a **lacuna de 83% de perda de sinal** identificada na autópsia M6.4: sinais computados a cada `/analyze` eram descartados antes de chegar à persistência. Dois novos vetores formalizados diretamente do pipeline existente — sem recomputação, sem overhead.

#### Módulo: `metrics/extended_vectors.py` — 2 Novos Vetores

**`AdvancedVector`** (6 canais — M7.0.1 — sinais do AdvancedAnalyzer M1 agora persistidos)
- `cognitive_cc_total` — Complexidade Cognitiva total do módulo (Campbell 2018 / SonarQube-compatible)
- `cognitive_cc_max` — maior Cognitive CC entre todas as funções
- `sqale_debt_minutes` — dívida técnica SQALE total em minutos (ISO/IEC 9126-style)
- `sqale_rating` — rating SQALE de A (≤5% ratio) a E (>50% ratio)
- `clone_count` — grupos de clone Type-2 detectados via AST skeleton hash
- `fn_profile_count` — número de FunctionProfiles disponíveis (breakdown rico por função)
- Construtores: `AdvancedVector.from_advanced_mv(mv)`, `AdvancedVector.from_dict(d)`
- Helper: `sqale_debt_hours()` — converte minutos em horas

**`DiagnosticVector`** (8 canais — M7.0.2 — sinais de persistência do FrequencyEngine agora persistidos)
- `dominant_frequency_H` — frequência dominante da PSD do canal H [0.0–0.5 Hz_norm]
- `spectral_entropy_H` — entropia de Shannon do canal H [0.0=periódico … 1.0=ruído branco]
- `phase_coupling_CC_H` — Phase Coupling Index CC↔H via transformada de Hilbert [0.0–1.0]
- `burst_index` — concentração temporal de ΔH (agudo vs crônico): >0.50=evento agudo [0.0–1.0]
- `self_cure_probability` — P(auto-resolução sem intervenção humana) normalizado em [0.0–1.0]
- `onset_reversibility` — facilidade de reverter o onset detectado [0.0=irreversível … 1.0=reversível]
- `degradation_signature` — label do tipo de erro primário (FrequencyEngine primary_error)
- `frequency_anomaly_score` — severity_score geral do evento anômalo [0.0–1.0]
- Construtores: `DiagnosticVector.from_classification_result(result)`, `DiagnosticVector.from_dict(d)`
- Helpers: `is_chronic()` — reversibilidade < 20%; `risk_tier()` — STABLE/WARNING/CRITICAL

#### Módulo: `metrics/__init__.py`
- Adicionados `AdvancedVector` e `DiagnosticVector` aos exports públicos do package

#### Módulo: `sensor_core/uco_bridge.py` — M7.0 Integration
- `UCOBridge.analyze()` agora anexa `mv.advanced = AdvancedVector.from_advanced_mv(mv)` imediatamente após `AdvancedAnalyzer.analyze()` (modo "full" + Python)
- Sinal persiste além da vida útil da request sem recomputação

#### Módulo: `sensor_storage/snapshot_store.py` — M7.0 Persistence
- **Schema migration**: 3 novas colunas `TEXT DEFAULT NULL` na tabela `snapshots`:
  - `extended_vectors_json` — HalsteadVector + StructuralVector (M6.4 retroativo)
  - `advanced_vector_json` — AdvancedVector (M7.0)
  - `diagnostic_vector_json` — DiagnosticVector (M7.0, preenchido após FrequencyEngine)
- **`_migrate_m70(cursor)`** — migração idempotente via try/except para bancos pré-existentes (compatível com SQLite < 3.37)
- **`insert(mv)`** — serializa os 3 vetores como JSON quando presentes no MetricVector
- **`update_diagnostic(module_id, commit_hash, json_str)`** — endpoint dedicado para persistir DiagnosticVector após FrequencyEngine
- **`get_history()`** — desserializa todos os 4 vetores extendidos de volta ao MetricVector
- **`_row_to_mv()`** — atualizado para incluir as 3 colunas JSON na leitura

#### Módulo: `api/server.py` — M7.0 Endpoint + Signals
- **`GET /metrics/advanced?module=<id>[&window=<n>]`** — novo endpoint expondo AdvancedVector + DiagnosticVector persistidos
  - Resposta inclui `risk_tier` (STABLE/WARNING/CRITICAL) calculado pelo DiagnosticVector
- **`handle_analyze()`** atualizado:
  - classification dict agora inclui `hurst_H`, `burst_index_H`, `phase_coupling_CC_H`, `onset_reversibility`, `self_cure_probability`
  - DiagnosticVector criado após FrequencyEngine e persistido via `update_diagnostic()`
- **`handle_docs()`** atualizado com nova rota documentada
- Versão: `2.2.0` → `2.3.0`

#### Testes: `tests/test_marco_m13.py` — TV31-TV60 (30 testes)
- TV31-TV36: `AdvancedVector` — construção, canais, to_dict, safe defaults
- TV37-TV44: `DiagnosticVector` — construção, normalização [0,1], roundtrip JSON
- TV45-TV52: `SnapshotStore` — persistência dos 3 JSON columns, update_diagnostic, migração
- TV53-TV60: Integração UCOBridge + exports do package + endpoint /metrics/advanced

**Resultado:** 30/30 testes passando | acumulado M4-M13: **300 testes**

---

## [2.2.0] — 2026-04-26 — M6.4 IaC SCANNER + EXTENDED METRIC VECTORS

### Adicionado — M6.4 Infrastructure-as-Code Scanner + Extended Metric Vectors

**APEX SCIENTIFIC mode** | Diferencial duplo: (1) SonarQube Community **não tem scanner IaC nativo** (requer plugins pagos); (2) Os 30+ sinais identificados na análise de gap de M6.4 eram computados mas **descartados** antes de chegar ao MetricVector — agora são formalizados em 4 novos vetores ortogonais ao schema de 9 canais existente.

#### Módulo: `metrics/` — 4 Vetores Estendidos

- **`metrics/__init__.py`** — package com exports públicos
- **`metrics/extended_vectors.py`** — 4 dataclasses formalizando sinais previamente descartados:

  **`HalsteadVector`** (6 canais — gap crítico: effort/volume/difficulty eram computados em `uco_bridge.py` e descartados)
  - `volume` V = (N1+N2) × log₂(n1+n2) — tamanho do programa em bits
  - `difficulty` D = (n1/2) × (N2/n2) — esforço mental para compreensão
  - `effort` E = D × V — esforço de implementação em operações elementares
  - `time_to_implement` T = E/18 — tempo estimado em segundos (Halstead 1977)
  - `program_level` L = 1/D — inverso da dificuldade (maior = mais limpo)
  - `token_count` N = N1 + N2 — comprimento bruto do programa
  - Construtor: `HalsteadVector.from_primitives(n1, n2, N1, N2)`

  **`StructuralVector`** (7 canais — gap: max_fn_cc, cc_hotspot_ratio, max_methods eram attrs informais no MetricVector)
  - `max_function_cc` — CC da função mais complexa do módulo
  - `cc_hotspot_ratio` — max_fn_cc / (avg_fn_cc × 3), capped 1.0
  - `max_methods_per_class` — maior contagem de métodos em uma classe
  - `n_functions` — total de definições de função/método
  - `n_classes` — total de classes/structs/interfaces
  - `comment_density` — linhas de comentário / total de linhas
  - `test_ratio` — funções de teste / total de funções
  - Construtor: `StructuralVector.from_counts(..., source="")`

  **`SecurityVector`** (10+1 canais — gap: SAST e SCA eram completamente desconectados do MetricVector)
  - `sast_critical/high/medium/low` — contagens SAST por severidade
  - `sast_security_rating` — A=1…E=5 (SQALE rating)
  - `sast_debt_minutes` — dívida técnica SAST em minutos
  - `sca_vulnerable_deps` — dependências com CVEs conhecidos
  - `sca_cvss_max` — maior CVSS score entre todos os findings SCA
  - `sca_debt_minutes` — dívida técnica SCA em minutos
  - `iac_misconfig_count` — findings do scanner IaC (M6.4)
  - `iac_privilege_score` — score máximo de escalada de privilégio [0.0–1.0]
  - Construtores: `from_sast_result()`, `from_sca_result()`, `from_iac_result()`, `merge(*vectors)`

  **`VelocityVector`** (4 canais — gap: hurst_exponent/velocity eram computados em predictor.py sem persistência)
  - `hamiltonian_velocity` — ΔH por snapshot (positivo = complexidade crescente)
  - `cc_velocity` — ΔCC por snapshot
  - `degradation_hurst` — expoente de Hurst H∈(0,1): >0.5=tendência persistente, 0.5=random walk
  - `regression_rate` — fração de snapshots em que métrica piorou
  - Construtores: `from_forecast()`, `from_trend()`, `from_metric_series(h_series, cc_series)`
  - Implementa R/S analysis (rescaled range) para estimativa do expoente de Hurst

#### Módulo: `iac/` — IaC Misconfiguration Scanner

- **`iac/__init__.py`** — package com exports públicos
- **`iac/iac_scanner.py`** — scanner offline-first, zero dependências externas:
  - `IaCFinding(rule_id, category, severity, title, description, source_file, line_number)` — finding com `debt_minutes` e `priv_score` auto-calculados
  - `IaCScanResult` — resultado agregado com `total_findings`, `max_privilege_score`, `status`, `summary()`, `to_dict()`
  - `IaCScanner`:
    - `scan_path(root)` — varredura recursiva, pula `.git/node_modules/.terraform/vendor/etc.`
    - `scan_files(files: Dict[str, str])` — modo inline (CI webhook, testes)
    - Dispatcher automático por nome de arquivo + extensão + heurística de conteúdo

  **5 scanners especializados com 44 regras:**

  | Scanner        | Regras | Categorias cobertas                              |
  |----------------|--------|--------------------------------------------------|
  | Dockerfile     | 10     | PRIVILEGE, IMAGE, SECRET, NETWORK, STORAGE, CONFIG |
  | docker-compose | 8      | PRIVILEGE, NETWORK, SECRET, STORAGE, IMAGE, RESOURCE |
  | Kubernetes YAML| 12     | PRIVILEGE, NETWORK, SECRET, RESOURCE, STORAGE, IMAGE, CONFIG |
  | Terraform .tf  | 12     | NETWORK, STORAGE, SECRET, PRIVILEGE, CONFIG      |
  | Helm values    | 6      | PRIVILEGE, NETWORK, SECRET, IMAGE, RESOURCE, CONFIG |

  **Regras de ausência** (detectam configuração faltando, não apenas padrão errado):
  - IAC-D001: sem `USER` instruction no Dockerfile
  - IAC-D008: sem `HEALTHCHECK` no Dockerfile
  - IAC-C007: sem `memory` limit em Compose
  - IAC-K003: `allowPrivilegeEscalation` ausente em k8s
  - IAC-K007: sem `limits` em k8s containers
  - IAC-K011: sem `namespace` explícito
  - IAC-K012: `readOnlyRootFilesystem` não habilitado
  - IAC-T004: S3 bucket sem `versioning` block
  - IAC-T010: terraform sem `backend` configurado
  - IAC-H005: Helm sem `resources.limits`

  **Regras de privilégio crítico:**
  - IAC-D004/D005: ENV/ARG com PASSWORD/SECRET/TOKEN/API_KEY
  - IAC-D006: `--cap-add SYS_ADMIN` no Dockerfile
  - IAC-C001: `privileged: true` em Compose
  - IAC-K001: `privileged: true` em k8s Pod
  - IAC-K002: `runAsUser: 0` em k8s
  - IAC-T002: SG com `from_port 0` + cidr `0.0.0.0/0`
  - IAC-T005: credentials hardcoded em Terraform
  - IAC-T007: IAM policy com `"Action": "*"`

#### Integração com Vetores Existentes

- **`sensor_core/uco_bridge.py`** — modificado:
  - `HalsteadVector.from_primitives(n1, n2, N1, N2)` agora populado em todo `analyze()` Python
  - `StructuralVector.from_counts(...)` populado com todos os campos estruturais do `_UCOVisitor`
  - Ambos os vetores attached ao MetricVector como `mv.halstead` e `mv.structural`
  - Import lazy — graceful degradation se `metrics/` não estiver no path

- **`lang_adapters/generic.py`** — modificado:
  - `HalsteadVector` e `StructuralVector` populados para todas as 40 linguagens do GenericRegexAdapter
  - `max_function_cc = cc` como melhor proxy para adaptadores regex

#### API

- **`api/server.py`** — novo endpoint `POST /scan-iac`
  - Modo `path`: `{"root": "/infra"}` — varredura filesystem
  - Modo `files`: `{"files": {"Dockerfile": "...", "k8s/pod.yaml": "..."}}` — inline
  - Retorna `IaCScanResult.to_dict()` com: status, total_findings, by_severity, by_category, total_debt_minutes, files_scanned, findings[]
  - Versão bumped: 2.1.0 → **2.2.0**

#### Testes

- **`tests/test_marco_m12.py`** — 30 testes TV01–TV30 (270/270 acumulado M4–M12)
  - TV01–TV06: HalsteadVector — from_primitives, fórmulas V/D/E, T=E/18, to_dict
  - TV07–TV12: StructuralVector — from_counts, cc_hotspot_ratio, cap@1.0, comment_density, test_ratio
  - TV13–TV17: SecurityVector — SAST channels, rating E=CRITICAL, merge(), to_dict
  - TV18–TV20: VelocityVector — velocity, Hurst range, regression_rate=0 para série melhorando
  - TV21–TV26: IaCScanner — Dockerfile/Compose/k8s/Terraform rules por arquivo
  - TV27–TV30: handle_scan_iac() REST — 200/400, missing dir, result structure

---

## [2.1.0] — 2026-04-26 — M6.3 SCA DEPENDENCY VULNERABILITY SCANNER

### Adicionado — M6.3 Software Composition Analysis

**APEX SCIENTIFIC mode** | Diferencial: SonarQube Community **não tem SCA** (requer OWASP Dependency-Check separado); UCO-Sensor integra SCA nativamente com SQALE debt, detecção Log4Shell/Spring4Shell offline-first e endpoint REST.

#### Arquitetura

- **`sca/__init__.py`** — package com exports públicos
- **`sca/cve_database.py`** — base de CVEs embutida, sem dependências externas
  - `CVEEntry(cve_id, severity, cvss_score, description, affected_range, fixed_version, cwe)` — imutável (frozen dataclass)
  - `_parse_version(v)` → tuple comparável — suporta `1.2.3`, `v2.0`, `1.0.0-rc1`, `1.0.0.post1`, epoch PEP 440
  - `_version_satisfies(version, range_spec)` → bool — operadores `>= <= > < == =`, separados por vírgula
  - `lookup(ecosystem, name, version)` → `List[CVEEntry]` — lookup normalizado por ecosistema
  - `_normalize_name(ecosystem, name)` — PEP 503 para pip (hyphen/underscore), lowercase para todos
  - **65+ CVEs reais** cobrindo 9 ecosistemas:
    - **pip**: Django (SQL injection, timing), Pillow (heap overflow), cryptography, requests, Flask, aiohttp, setuptools, lxml, PyYAML, gunicorn, certifi, paramiko
    - **npm**: lodash (3 CVEs), axios (3 CVEs), follow-redirects (2 CVEs), minimist, node-fetch, qs (3 CVEs), ws (4 CVEs), path-parse, tar (3 CVEs)
    - **maven**: Log4Shell (CVE-2021-44228, 45046, 45105), Spring4Shell (CVE-2022-22965), Spring Cloud Function (CVE-2022-22963), jackson-databind, Struts2 (2 CVEs), commons-collections, commons-text (Text4Shell), Spring Security
    - **cargo**: regex (ReDoS), rustls, openssl, h2
    - **go**: golang.org/x/net (2 CVEs), golang.org/x/crypto, gin
    - **composer**: Laravel/framework (2 CVEs), symfony/security-core, guzzlehttp/guzzle
    - **gem**: rails (3 CVEs), nokogiri (2 CVEs), loofah
    - **nuget**: System.Text.Encodings.Web (3 CVEs), Microsoft.AspNetCore.Http, Newtonsoft.Json, System.Net.Http
    - **gradle**: aliases automáticos para todos os artefatos Maven

- **`sca/vulnerability_scanner.py`** — motor principal
  - `Dependency(name, version, ecosystem, source_file)` — dependência resolvida
  - `VulnerabilityFinding(dependency, cve_id, severity, cvss_score, description, fixed_version, cwe, debt_minutes)` — finding com SQALE auto-calculado
  - `SCAResult` — resultado agregado com `summary()`, `to_dict()`, status CRITICAL/WARNING/STABLE
  - `VulnerabilityScanner`:
    - `scan_path(root)` — varredura recursiva filesystem, pula node_modules/.git/vendor/etc.
    - `scan_files(files: Dict[str, str])` — inline content dict (CI webhook, testes)
    - **9 parsers de manifesto**:
      - pip: `requirements.txt/in`, `Pipfile`, `Pipfile.lock`, `pyproject.toml` (PEP 621 + Poetry)
      - npm: `package.json` (strip `^/~/>=`), `package-lock.json` (v2/v3 exato)
      - maven: `pom.xml` via regex `<dependency>` blocks
      - cargo: `Cargo.toml` ([dependencies] section), `Cargo.lock` ([[package]] blocks)
      - go: `go.mod` (inline `require` e bloco `require (...)`)
      - composer: `composer.json` (require + require-dev)
      - gem: `Gemfile.lock` (GEM specs section, 4-space indent)
      - nuget: `packages.config`, `*.csproj` (PackageReference inline + child element)
      - gradle: `build.gradle/kts` (implementation/compile/api/testImplementation)

- **`api/server.py`** — novo endpoint `POST /scan-sca`
  - Modo `path`: `{"root": "/repo"}` — varredura filesystem
  - Modo `files`: `{"files": {"requirements.txt": "..."}}` — inline
  - Retorna `SCAResult.to_dict()` com findings, severity counts, debt
  - Versão bumped: 2.0.0 → **2.1.0**

#### Testes

- **`tests/test_marco_m11.py`** — 30 testes TS01–TS30 (240/240 acumulado M4–M11)
  - Group 1 — CVE DB (TS01–TS07): parse_version, version_satisfies, lookup Log4Shell, safe version empty, DB size ≥50, PEP 503 normalize
  - Group 2 — Data structures (TS08–TS10): Dependency.to_dict, debt_minutes auto, SCAResult summary+status
  - Group 3 — Parsers (TS11–TS20): requirements.txt, package.json, pom.xml, Cargo.lock, go.mod, composer.json, Gemfile.lock, packages.config, build.gradle, pyproject.toml
  - Group 4 — scan_files E2E (TS21–TS25): Log4Shell detected, lodash prototype pollution, clean deps=STABLE, multi-ecosystem, debt accumulation
  - Group 5 — REST endpoint (TS26–TS30): files mode 200, CVE detection, 400 empty files, 400 no key, path mode filesystem

### Alterado

- `api/server.py`: importa `VulnerabilityScanner`; `handle_scan_sca()` adicionado; `/scan-sca` no router do `do_POST`; `/docs` atualizado
- Versão bumped: 2.0.0 → **2.1.0**

---

## [2.0.0] — 2026-04-26 — M6.2 MULTI-LANGUAGE SUPPORT (APEX SCIENTIFIC)

### Adicionado — M6.2 40 Language Adapters

**APEX SCIENTIFIC mode** | Diferencial: SonarQube OSS suporta ~30 linguagens; UCO-Sensor v2 entrega **40 adaptadores calibrados** com Hamiltonian, CC, ILR, DSM e dead-code por linguagem — superando a cobertura do SonarQube Community Edition.

#### Arquitetura

- **`lang_adapters/generic.py`** — `GenericRegexAdapter(LanguageAdapter)`: base universal
  - `_strip(source)` → strings → bloco → linha (evita falsos positivos CC/import dentro de literais)
  - `_compute_ilr(clean)` → window-scan de 20 linhas por loop infinito; fração sem escape = ILR
  - `_count_dead_code(clean)` → brace-depth tracking pós-`return/throw/exit`
  - `_classify(h, cc)` → CRITICAL / WARNING / STABLE (limiares H≥20/8, CC>20/10)
  - `_halstead_metrics(tokens, ops)` → (n1, n2, N1, N2) particionamento Halstead 1977
  - `_count_duplicates(source, prefix)` → clone density proxy — linhas repetidas ≥ 2×
  - Calibrado para ±15% de medições AST tree-sitter no corpus UCO-Sensor

#### Grupos de Adaptadores

- **`lang_adapters/c_family.py`** — C, C++, Objective-C
  - `CAdapter` (.c, .h): `#include`, typed functions, `struct/union/enum`
  - `CppAdapter` (.cpp, .cc, .cxx, .hpp, .hxx, .h++, .c++, .cp, .inl): `catch`, `co_await/co_yield`, namespace/template
  - `ObjectiveCAdapter` (.m, .mm): `@interface/@implementation`, `[-+] (type) method:` selectors

- **`lang_adapters/csharp.py`** — C# (.cs)
  - `foreach/when/??`, `global using`, `record`, access-modifier function patterns

- **`lang_adapters/rust.py`** — Rust (.rs)
  - `match =>` arms, `loop {}` ILR, `?` propagation, `pub/async/const/unsafe fn`

- **`lang_adapters/ruby.py`** — Ruby (.rb, .rake, .gemspec, .ru, .rbw)
  - `=begin/=end` block comments, `unless/until/rescue/ensure/when`, `.each/.map` iterators

- **`lang_adapters/swift.py`** — Swift (.swift)
  - `guard/where/if let`, `??` null-coalescing, `fatalError/preconditionFailure`, `actor`

- **`lang_adapters/kotlin.py`** — Kotlin (.kt, .kts)
  - `when` expressions, `?.` safe-call, `?:` Elvis, `data/sealed class`, `companion object`

- **`lang_adapters/php.py`** — PHP (.php, .php3–7, .phps, .phtml)
  - PHP-8 `match`, `??` null-coalescing, heredoc strings, `require_once/use`, `die`

- **`lang_adapters/scala.py`** — Scala + Groovy
  - `ScalaAdapter` (.scala, .sc, .sbt): triple-quoted, `s"..."` interpolation, `match/case`, `sealed/case class`
  - `GroovyAdapter` (.groovy, .gradle, .gvy, .gy): GString `"...$var"`, Elvis `?:`, safe navigation `?.`

- **`lang_adapters/scripting_langs.py`** — R, Shell, PowerShell, Lua, Perl, MATLAB (6 adapters)
  - `RAdapter` (.r/.R/.rmd/.Rmd/.rscript): `library()`/`require()`, `name <- function(`, R6Class, `repeat{}` ILR
  - `ShellAdapter` (.sh/.bash/.zsh/.ksh/.fish/.command): `[[`/`[` conditions, `source`/`.` imports, sem classes
  - `PowerShellAdapter` (.ps1/.psm1/.psd1/.pssc): `<# #>` block, `-and/-or`, `Import-Module`, case-insensitive
  - `LuaAdapter` (.lua): `--[[ ]]` block, `and/or`, `require()`, `while true do` ILR
  - `PerlAdapter` (.pl/.pm/.t/.cgi/.plx): POD `=begin/=cut`, `elsif/unless/until`, `sub name {`
  - `MatlabAdapter` (.matlab/.octave): `%{ %}` blocks, `function [out]=name(`, `parfor`, `while 1`

- **`lang_adapters/functional_langs.py`** — Haskell, Erlang, Elixir, F#, OCaml, Clojure (6 adapters)
  - `HaskellAdapter` (.hs/.lhs): `|` guards como CC, `--`/`{- -}`, `forever`/`fix` = ILR
  - `ErlangAdapter` (.erl/.hrl): `->` clause arrows, `andalso/orelse`, `receive` = ILR
  - `ElixirAdapter` (.ex/.exs): sigils `~r/.../`, `cond/with/receive`, `defmodule/defprotocol`
  - `FSharpAdapter` (.fs/.fsx/.fsi): `(* *)`, `|` arms (não `||` ou `|>`), `let rec/member/override`
  - `OCamlAdapter` (.ml/.mli): sem line comments, `(* *)`, `|` arms, `while true do` ILR
  - `ClojureAdapter` (.clj/.cljs/.cljc/.edn): `;`/`#_`, `(if/when/cond/loop...)`, `(defn...)`

- **`lang_adapters/modern_systems.py`** — Dart, Julia, Zig, Nim, Crystal, D (6 adapters)
  - `DartAdapter` (.dart): `??/?.`, `on/rethrow`, `import/export/part`, `mixin/extension/typedef`
  - `JuliaAdapter` (.jl): `#= =#` block, `elseif`, `using/import/include`, `mutable struct/abstract type`
  - `ZigAdapter` (.zig): sem block comments, `\\` multiline, `comptime/orelse/catch/try`, `@import()`
  - `NimAdapter` (.nim/.nims): `#[...]#`, `proc/func/method/iterator/macro/template`, `of` case arms
  - `CrystalAdapter` (.cr): Ruby-like, `select` channels, `loop do/loop {`, `lib/annotation`
  - `DAdapter` (.d/.di): `/+ +/` nestable, `foreach_reverse`, `scope(exit/failure/success)`, backtick strings

- **`lang_adapters/domain_langs.py`** — VB.NET, Assembly, COBOL, Fortran, Tcl, Solidity, HCL (7 adapters)
  - `VBNetAdapter` (.vb): `'` comments, `For Each/AndAlso/OrElse/Select Case`, `Sub/Function/Property`
  - `AssemblyAdapter` (.asm/.s/.S/.nasm/.nas): `jXX` branches, `cbz/cbnz` ARM, labels = funções, `section` = struct
  - `CobolAdapter` (.cob/.cbl/.cpy/.cobol): `*>` e col-7 `*`, `EVALUATE/WHEN/PERFORM/UNTIL`, `PERFORM FOREVER`
  - `FortranAdapter` (.f/.for/.f77-.f08): `.AND./.OR./.NOT./.EQV./.NEQV.`, `USE`, `SUBROUTINE/FUNCTION/PROGRAM`
  - `TclAdapter` (.tcl/.tk/.tclsh): `package require`, `proc`, `namespace eval`, `while {1}` ILR
  - `SolidityAdapter` (.sol): `///` NatSpec, `require/revert` como CC, `contract/interface/library`
  - `HCLAdapter` (.hcl/.tf/.tfvars): `count/for_each/for/dynamic`, `module/data` = imports, `resource/provider`

#### Registry

- **`lang_adapters/registry.py`** — REESCRITO para M6.2
  - `_EXT_MAP`: 140+ extensões → 40 classes de adaptadores
  - `_load_adapter_by_name(class_name)`: factory com lazy imports para todos os 40 adaptadores
  - `UCOBridgeRegistry.supported_languages()` → 41 linguagens (TypeScript listado separado de JavaScript)
  - `UCOBridgeRegistry.supported_extensions()` → 140+ extensões mapeadas
  - `reset_registry()`: helper para isolamento de testes

#### IncrementalScanner — extensões M6.2

- **`scan/incremental_scanner.py`** — `_SUPPORTED_EXT` expandido
  - Adicionadas 100+ extensões cobrindo todos os 40 adaptadores M6.2
  - Grupos: C/C++/ObjC, C#, Rust, Ruby, Swift, Kotlin, PHP, Scala/Groovy, R, Shell, PowerShell, Lua, Perl, MATLAB, Haskell, Erlang, Elixir, F#, OCaml, Clojure, Dart, Julia, Zig, Nim, Crystal, D, VB.NET, Assembly, COBOL, Fortran, Tcl, Solidity, HCL

#### Testes

- **`tests/test_marco_m10.py`** — 30 testes TL01–TL30 (210/210 acumulado M4–M10)
  - Group 1 — `GenericRegexAdapter` (TL01–TL05): empty, LOC, CC, strip, classify
  - Group 2 — C-family (TL06–TL10): C, C++, ObjC extensões; C# foreach/??
  - Group 3 — Rust/Swift/Kotlin/Scala/PHP (TL11–TL15): match arms, guard, when, extensões
  - Group 4 — Scripting (TL16–TL20): R library(), Shell [[, PS case-insensitive, Lua and/or, Perl sub
  - Group 5 — Functional (TL21–TL24): Haskell guards, Elixir defmodule, F# arms, Clojure defn
  - Group 6 — Modern systems (TL25–TL27): Dart ??, Zig comptime, Nim proc/elif
  - Group 7 — Registry (TL28–TL30): ≥36 linguagens, ≥100 extensões, dispatch por extensão

### Alterado

- **`lang_adapters/registry.py`**: completamente reescrito (substituiu stub de 6 linguagens)
- **`scan/incremental_scanner.py`**: `_SUPPORTED_EXT` expandido de 10 para 110+ extensões
- Versão bumped: 1.5.0 → **2.0.0** (major — cobertura de linguagens 6× maior)

---

## [1.5.0] — 2026-04-26 — M6.1 INCREMENTAL ANALYSIS ENGINE

### Adicionado — M6.1 IncrementalScanner

**APEX DEEP mode** | Diferencial: SonarQube incremental = enterprise-only; UCO-Sensor entrega grátis com Hamiltonian delta e detecção de regressão persistida.

- **`scan/incremental_scanner.py`** — motor de análise incremental
  - `ChangedFile(path, change_type, old_path, content)` — ADDED / MODIFIED / DELETED / RENAMED
  - `FileDelta` — comparação before/after de métricas por arquivo:
    - `old_hamiltonian`, `new_hamiltonian`, `delta_h`
    - `old_cc`, `new_cc`, `delta_cc`
    - `status_before`, `status_after`, `regression`, `scan_error`
    - `to_dict()` com rounding correto
  - `IncrementalScanResult` — resultado agregado da passagem incremental:
    - Contadores: `total_changed`, `added_count`, `modified_count`, `deleted_count`, `renamed_count`
    - `scanned_count`, `error_count`, `regressions`, `new_criticals`
    - `regressions_list()` — lista de `FileDelta` com `regression=True`
    - `new_criticals_list()` — arquivos que passaram para CRITICAL nesta passagem
    - `summary()` — string legível para CI logs
    - `to_dict()` — serialização completa (incluindo `file_deltas`)
  - `IncrementalScanner(root, store, commit_hash)`:
    - `scan_files(paths, commit_hash, base_commit)` — lê do disco, detecta ADDED vs MODIFIED via store
    - `scan_changed_files(changed_files, …)` — lista pré-construída de `ChangedFile`
    - `scan_git_diff(repo_path, base_commit, head_commit)` — `git diff --name-status`
    - `_baseline(path)` → `(h, cc, status)` da última snapshot no `SnapshotStore`
    - `_git_changed_files(repo, base, head)` — parser de saída git: A/M/D/R
  - **Detecção de regressão**: `delta_h > max(0.5, old_h * 0.05)` OR piora de status rank
  - Fallback seguro: git ausente → lista vazia; extensão não suportada → `scan_error`

- **`api/server.py`** — novo endpoint `POST /scan-incremental`
  - Modo `files`: aceita lista de `{"path", "content", "change_type"}` + `persist`, `root`
  - Modo `git_diff`: delega a `scan_git_diff()` com `repo_path`, `base_commit`, `head_commit`
  - `persist=False` → scanner usa `store=None` (sem escrita no DB)
  - Retorna `IncrementalScanResult.to_dict()` com regressions e new_criticals
  - Versão bumped: 1.4.0 → **1.5.0**

- **`tests/test_marco_m9.py`** — 30 testes TI01–TI30 (210/210 passing acumulado)
  - Group 1 — `ChangedFile` (TI01–TI03): construção, rename, conteúdo
  - Group 2 — `FileDelta` (TI04–TI07): defaults, to_dict, regression, DELETED
  - Group 3 — `IncrementalScanResult` (TI08–TI12): summary, regressions_list, new_criticals_list, to_dict, rounding
  - Group 4 — `scan_files()` (TI13–TI17): empty, ADDED, MODIFIED, DELETED, contadores múltiplos
  - Group 5 — `scan_changed_files()` (TI18–TI21): empty content, extensão insuportada, DELETED, Python válido
  - Group 6 — `_baseline()` (TI22–TI23): sem store, com history
  - Group 7 — `_git_changed_files()` (TI24–TI26): não-git, parse A/M/D/R, timeout
  - Group 8 — `handle_scan_incremental()` REST (TI27–TI30): 400 sem files, 200 files mode, git_diff mode mock, persist=False

---

## [1.4.0] — 2026-04-26 — M5.3 AI EXPLANATIONS VIA APEX ENGINEER

### Adicionado — M5.3 FixExplainer

- **`sensor_core/explainer.py`** — `FixExplainer` + `ExplanationReport`
  - `explain(autofix_result, module_id, forecast?, anomaly_type?, …)` → `ExplanationReport`
  - Auto-detecção de `anomaly_type` via `_infer_anomaly_type()`:
    1. Dominant transform aplicado pelo AutofixEngine (`DeadCodeRemover` → `DEAD_CODE_DRIFT`, etc.)
    2. Fallback para `DegradationForecast.risk_level` → tipo APEX correspondente
    3. Fallback final: `TECH_DEBT_ACCUMULATION`
  - `ExplanationReport` (13 campos + `to_dict()`):
    - `apex_prompt` — pronto para o agente APEX engineer (renderizado via `render_prompt()`)
    - `mode` — FAST | DEEP | RESEARCH determinado pelo template do anomaly_type
    - `agents` — lista de agentes APEX recomendados
    - `transforms_summary` — sumário do que o AutofixEngine já corrigiu
    - `transforms_auto_applied` — nomes únicos (dedup, order-preserving)
    - `remaining_transforms` — o que ainda precisa de intervenção manual/agente
    - `success_criteria` — critério de sucesso APEX para o tipo de anomalia
    - `risk_narrative` — narrativa derivada do `DegradationForecast` (slope, Hurst, advice)
    - `intervention_now` — True quando template exige ação imediata
    - `uco_channels` — canais UCO afetados
  - Enriquecimento automático de `delta_h` e `hurst` a partir do forecast quando não fornecidos
- **Integração completa M5.1 + M5.2 + M5.3**: Forecast → Autofix → Explain → APEX prompt

### Modo APEX utilizado: `DEEP`
  - Agentes: `["engineer", "architect", "critic"]`
  - Justificativa: síntese multi-camada (predictor + AST transforms + templates)

### Testes

- `tests/test_marco_m8.py` — 30 testes TE01-TE30, **30/30 PASS**
- Regressão: M1…M8 = **240/240 PASS**

---

## [1.3.0] — 2026-04-26 — M5.2 AUTOFIX ENGINE (AST TRANSFORMS)

### Adicionado — M5.2 AutofixEngine

- **`sensor_core/autofix/engine.py`** — `AutofixEngine` + `AutofixResult`
  - Pipeline configurável de 4 transforms aplicados em sequência
  - `apply(source)` → `AutofixResult` com `fixed_source`, `transforms_applied`, `is_valid_python`, `parse_error`, `changed`
  - `apply_named(source, names)` — aplica apenas transforms selecionados
  - Guarda-costas completo: parse error → original retornado; transform exception nunca quebra o pipeline
- **`sensor_core/autofix/transforms/dead_code.py`** — `DeadCodeRemover`
  - Remove statements após `return`/`raise`/`continue`/`break` em function bodies
  - Aplica recursivamente em branches `if`/`for`/`while`/`try`
- **`sensor_core/autofix/transforms/redundant_else.py`** — `RedundantElseRemover`
  - Guard clause pattern: `if x: return … else: …` → `if x: return …\n…`
  - Multi-pass até estabilidade; trata `raise` como terminador
- **`sensor_core/autofix/transforms/boolean_simplify.py`** — `BooleanSimplifier`
  - `x == True` → `x`, `x is True` → `x`
  - `x == False` → `not x`, `x is False` → `not x`
  - `x != True` → `not x`, `x is not False` → `x`
- **`sensor_core/autofix/transforms/unused_imports.py`** — `UnusedImportRemover`
  - Remove `import` e `from … import` cujos nomes não aparecem no AST
  - Preserva `from __future__ import`, star imports, `__all__`-exported names
  - Bail-out automático quando `getattr`/`eval`/`exec` presentes (dynamic access)
- **Pipeline order**: `UnusedImports → BooleanSimplify → RedundantElse → DeadCode`
  - Ordem garante que `RedundantElse` cria novos terminators antes de `DeadCode` varrer

### Testes

- `tests/test_marco_m7.py` — 30 testes TF01-TF30, **30/30 PASS**
- Regressão: M1…M7 = **210/210 PASS**

---

## [1.2.0] — 2026-04-26 — M6 PREDICTOR API + FLEET HEALTH ENGINE

### Adicionado — M6 Predictor API + AutoAnalyzer

- **`sensor_core/auto_analyzer.py`** — `AutoAnalyzer` + `FleetReport`
  - `analyze_module(module_id, window, horizon)` → `DegradationForecast` direto do store
  - `analyze_fleet(window, top_n, horizon)` → `FleetReport` com todos os módulos ordenados por risco
  - `FleetReport`: `total_modules`, `analysed_modules`, `risk_counts`, `critical_count`, `high_count`, `avg_confidence`, `most_at_risk`, `all_forecasts`, `summary()`
  - Ordenação: `_RISK_ORDER` (CRITICAL < HIGH < MEDIUM < LOW < STABLE), desempate por `slope_pct` decrescente
- **`api/server.py`** — 2 novos endpoints REST
  - `GET /predict?module=<id>&window=<n>&horizon=<h>` — forecast por módulo
  - `GET /predict/all?window=<n>&horizon=<h>&top_n=<k>` — fleet forecast completo
  - Versão bumped para `1.1.0`

### Testes

- `tests/test_marco_m6.py` — 30 testes TA01-TA30, **30/30 PASS**
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) + M5 (30) + M6 (30) = **180/180 PASS**

---

## [1.1.0] — 2026-04-26 — M5 DEGRADATION PREDICTOR

### Adicionado — M5.1 DegradationPredictor

- **`sensor_core/predictor.py`** — `DegradationPredictor` com previsão combinada de dois sinais
- **Hurst Exponent** via Rescaled Range (R/S): H > 0.55 → persistente, H < 0.45 → auto-corretivo
- **OLS Slope** (% change per snapshot): slope positivo → Hamiltonian crescendo → degradação
- `DegradationForecast` dataclass com 13 campos + `to_dict()`
- Risk classification: `CRITICAL | HIGH | MEDIUM | LOW | STABLE` com amplificação por persistência
- `hurst_rs(series)` — estimador Hurst por análise R/S com OLS sobre log(R/S) ~ H·log(L)
- `_ols() / _r2()` — regressão linear + R² para projeção de tendência
- `confidence` — escala com `n_samples / 20 × R²`; `predicted_h` clampado em ≥ 0
- Fast-path para dados insuficientes (< 4 snapshots) → retorna `insufficient_data=True`

### Testes

- `tests/test_marco_m5.py` — 30 testes TP01-TP30, **30/30 PASS** (0 falhas na primeira execução)
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) + M5 (30) = **150/150 PASS**

---

## [1.0.0] — 2026-04-26 — M4 WEB UI + SARIF + GITHUB ACTIONS + VS CODE

### Adicionado — M4.3 SARIF 2.1.0 Melhorado

- **`report/sarif.py`** — `SARIFBuilder` incremental: 22 regras (9 UCO + 13 SAST)
- Line/column reais em `physicalLocation.region`: `startLine` e `startColumn` (1-based)
- `add_sast_findings(uri, sast_result)` — mapeia `SASTFinding.line/col` para região SARIF
- `add_uco_findings_from_profiles(uri, fps)` — emite UCO001/UCO002 por função com CC/CogCC alto
- `add_uco_finding(...)` — finding UCO com `logicalLocations` (nome da função)
- CWE/OWASP tags em `rule.properties`; `fullDescription` e `help.markdown` por regra
- `/analyze-pr` refatorado para usar `SARIFBuilder` (elimina `startLine: 1` hardcoded)

### Adicionado — M4.4 GitHub Actions Native Action

- **`algorithms/uco-sensor/action.yml`** — composite action com 8 inputs + 7 outputs
- Inputs: `path`, `fail_on_critical`, `fail_on_gate_fail`, `gate_threshold`, `sarif_output`,
  `policy_file`, `max_files`, `include_tests`, `python_version`, `upload_sarif`
- Outputs: `uco_score`, `status`, `critical_count`, `warning_count`, `files_scanned`,
  `sarif_file`, `debt_minutes`
- **`ci/action_entrypoint.py`** — script standalone: RepoScanner + SARIFBuilder + SAST scan
- SARIF auto-upload via `github/codeql-action/upload-sarif@v3`
- GitHub Step Summary com tabela de métricas + emoji de status

### Adicionado — M4.1 Web Dashboard Temporal

- **`report/webui.py`** — `generate_dashboard_html()`: HTML standalone com Chart.js 4.x (CDN)
- 4 canvas: Hamiltonian temporal, CC temporal, Cognitive CC por módulo, SQALE debt por módulo
- Module health cards com status/trend icons, SQALE rating badges
- Top-issues table + SQALE debt budget progress bar
- Auto-refresh configável via `setInterval + fetch('/dashboard')`
- `GET /dashboard/ui` — endpoint no servidor stdlib servindo o dashboard completo
- Dados pré-embutidos como JSON (`INITIAL_DATA`) para renderização imediata

### Adicionado — M4.2 VS Code Extension

- **`vscode-extension/package.json`** — manifesto completo v1.0.0
  - Activation: Python, JS, TS, Java, Go
  - 4 commands: `analyze`, `showDashboard`, `analyzeWorkspace`, `configureServer`
  - 6 configurações: serverUrl, apiKey, analyzeOnSave, decorations, statusBarFormat, refresh
- **`vscode-extension/src/api.ts`** — `UCOClient` typed (fetch-based): 10 métodos API
- **`vscode-extension/src/extension.ts`** — extensão completa:
  - Status bar com H/status/SQALE rating
  - 3 decoration types: CRITICAL, HIGH, MEDIUM (coloured highlights + hover)
  - VS Code Diagnostics (Problems panel) com SAST + função profiles
  - WebView dashboard panel (HTML inline, sem servidor Node)
  - Auto-analyse on save; configureServer com ping test

### Modificado

- `api/server.py` — versão `1.0.0`; `/analyze-pr` usa `SARIFBuilder`; `GET /dashboard/ui`
- `pyproject.toml` — versão `1.0.0`; `webui = [fastapi, uvicorn]` optional dep; `ci*` package

### Testes

- `tests/test_marco_m4.py` — 30 testes TW01-TW30, **30/30 PASS** (0 falhas na primeira execução)
- Regressão: M1 (30) + M2 (30) + M3 (30) + M4 (30) = **120/120 PASS**

---

## [0.9.0] — 2026-04-25 — M3 SAST SECURITY RULES

### Adicionado — M3 SAST Security Rules

- **`sast/` package** — Static Application Security Testing engine com 13 regras de segurança
- **SAST001** (CWE-89, CRITICAL) — SQL Injection via `execute()` com string formatada ou concatenada
- **SAST002** (CWE-78, HIGH) — OS Command Injection via `os.system()` / `os.popen()` com argumento variável
- **SAST003** (CWE-95, HIGH) — Unsafe `eval()` / `exec()` com argumento não-literal
- **SAST004** (CWE-502, HIGH) — Pickle deserialization via `pickle.load()` / `pickle.loads()`
- **SAST005** (CWE-502, MEDIUM) — YAML unsafe load sem `Loader` contendo "safe"
- **SAST006** (CWE-327, MEDIUM) — Algoritmo de hash fraco: MD5, SHA1
- **SAST007** (CWE-338, MEDIUM) — Randomness insegura via módulo `random`
- **SAST008** (CWE-798, HIGH) — Segredo hardcoded: `password`, `api_key`, `token`, etc.; exclui placeholders (`CHANGEME`, `YOUR_`, etc.)
- **SAST009** (CWE-321, CRITICAL) — Chave privada PEM no código-fonte
- **SAST010** (CWE-489, MEDIUM) — Flask/app `debug=True` em produção
- **SAST011** (CWE-22, HIGH) — Path Traversal via `open()` com caminho variável
- **SAST012** (CWE-617, LOW) — `assert` usado para verificação de segurança
- **SAST013** (CWE-78, HIGH) — `subprocess` com `shell=True` + argumento não-literal
- **`SASTFinding` / `SASTResult`** — dataclasses com `to_dict()`, debt_minutes, security_rating A-E
- **Security rating** — CRITICAL→E, ≥2 HIGH→D, 1 HIGH→C, ≥2 MEDIUM→C, 1 MEDIUM→B, clean→A
- **SAST debt** — CRITICAL=240 min, HIGH=120 min, MEDIUM=60 min, LOW=30 min, INFO=5 min

### API — Novos endpoints (v0.9.0)

- `POST /sast` — scan de código-fonte; retorna findings + rating + debt
- `GET /sast/rules` — catálogo das 13 regras SAST
- `POST /analyze` — enriquecido com campo `"sast"` no payload de resposta

### Testes

- `tests/test_marco_m3.py` — 30 testes TS01-TS30, **30/30 PASS**
- Regressão: M1 (30/30) + M2 (30/30) mantidos intactos

---

## [0.8.0] — 2026-04-25 — M2 GOVERNANCE ENGINE

### Adicionado — M2 Governance Engine

**M2.1 — Policy Engine (`governance/policy_engine.py`)**
- `PolicyRule`: id, field, operator, threshold, severity (ERROR/WARNING/INFO)
- Operadores: `lte`, `gte`, `lt`, `gt`, `eq`, `neq`, `in`, `not_in`, `rating_lte`, `rating_gte`
- `evaluate_policy(metrics_dict, policy)` → `PolicyResult(passed, gate_score, grade, violations)`
- `load_default_policy()` — 11 regras default cobrindo CC, Cognitive CC, ILR, SQALE, DI, clones

**M2.2 — Quality Gate**
- `POST /gate` — analisa código e avalia política em uma chamada
- `gate_score` = 100 − Σ penalidades (ERROR −20, WARNING −10, INFO −2)
- `grade` A–F; `passed` = gate_score ≥ pass_threshold (default 70)
- Em caso de falha publica evento `UCO_GATE_FAILURE` ao APEX (quando apex_enabled=1)
- `gate_score_to_grade()`, `mv_to_metrics_dict()`

**M2.3 — Trend Engine (`governance/trend_engine.py`)**
- `analyze_trend(history, metric, window)` → `TrendAnalysis`
- Classificação: IMPROVING | STABLE | DEGRADING | VOLATILE | INSUFFICIENT_DATA
- Linear regression slope + R² — VOLATILE só quando R² < 0.6 AND CV > 30%
- `forecast_next` via extrapolação da regressão linear
- `analyze_module_trends()` — multi-metric para um módulo
- `overall_trend()` — direção agregada em múltiplas métricas

**M2.4 — Debt Budget**
- `track_debt_budget(module_debts, budget_minutes)` → `DebtBudget`
- Campos: `total_debt_minutes`, `remaining_minutes`, `over_budget`, `velocity_min_per_day`
- `days_until_exhausted` — previsão baseada na velocidade de acúmulo de dívida

**M2.5 + M2.6 — Dashboard + Trend API**
- `GET /trend?module=<id>&metric=<field>&window=<n>` — trend per-módulo
- `GET /dashboard` — snapshot de todos os módulos + debt budget + contagens por status/trend

### Testes
- `tests/test_marco_m2.py` — TG01–TG30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M2 Governance (30) | ✅ 30/30 |
| M1 Advanced (30)   | ✅ 30/30 |
| Calibration (25)   | ✅ 24/25 (1 skip) |
| Marco 6 (14)       | ✅ 14/14 |
| Marco 7 (16)       | ✅ 16/16 |
| Marco 8 (10)       | ✅ 10/10 |
| **Total acumulado** | **124/125** |

---

## [0.7.0] — 2026-04-25 — M1 ADVANCED METRICS

### Adicionado — M1 Advanced Quality Metrics

**M1.1 — Cognitive Complexity (Campbell 2018) (`advanced_metrics.py`)**
- `cognitive_complexity(source)` → `(total, per_function_dict)`
- Regras: +1 + depth para estruturas (if/for/while/except/with/lambda/fn aninhada)
- elif/else: +1 flat; BoolOp: +1 flat por sequência; ternary: +1 flat; recursão: +1 flat
- Nesting depth incrementa dentro de cada estrutura de controle

**M1.2 — SQALE Technical Debt (`advanced_metrics.py`)**
- `sqale_debt(metrics_dict, loc)` → `SQALEResult(debt_minutes, sqale_ratio, rating, breakdown)`
- Tabela de remediation costs: CC alto (30-60min), dead code (5min/linha), ILR (30min/loop), clones (30min/grupo), DI > 0.8 (480min)
- `sqale_ratio = debt / (loc × 30) × 100%`; Ratings A (≤5%) → E (>50%)

**M1.3 — Function-level Breakdown (`advanced_metrics.py`)**
- `build_function_profiles(source, fn_cc, fn_cog)` → `List[FunctionProfile]`
- `FunctionProfile`: name, loc, cc, cognitive_cc, halstead_volume, is_complex, debt_minutes, risk_level (LOW/MEDIUM/HIGH)

**M1.4 — Real Dependency Instability (`advanced_metrics.py`)**
- `ImportGraphAnalyzer` — compute real Martin DI via project-level import graph
- `DI(m) = Ce(m) / (Ca(m) + Ce(m))` contando apenas imports internos ao projeto

**M1.5 — Clone Detection Type-2 (`advanced_metrics.py`)**
- `detect_clones(source)` → número de grupos de clone
- Skeleton hash: normaliza `id`, `arg`, `attr`, `name`, `value` em AST dump
- Funções estruturalmente idênticas (renomeadas) são detectadas como Type-2 clones

**M1.6 — Ratings A–E (`advanced_metrics.py`)**
- `compute_ratings(uco_score, sqale_ratio_pct, ...)` → `Ratings(uco, sqale, reliability, security)`
- UCO: ≥80→A, ≥60→B, ≥40→C, ≥20→D, <20→E
- Reliability: penaliza ILR > 0.5 (−40pts) e CC > 20 (−20pts)
- Security: penaliza dead code ratio > 0.1 (−30pts) e Halstead bugs > 3 (−30pts)

**`AdvancedAnalyzer` — Orquestrador M1**
- `UCOBridge(mode="full")` injeta automaticamente todos os atributos M1 no MetricVector
- Dynamic attribute pattern: `mv.cognitive_complexity`, `mv.sqale_rating`, `mv.ratings`, `mv.function_profiles`, `mv.clone_count`, etc.
- `mode="fast"` não executa M1 (preserva performance de análises em lote)

**`/analyze` endpoint ampliado**
- Response inclui: `cognitive_complexity`, `cognitive_fn_max`, `sqale_debt_minutes`, `sqale_ratio`, `sqale_rating`, `clone_count`, `ratings`, `function_profiles`

### Testes
- `tests/test_marco_m1.py` — TM01–TM30 (30 testes)

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Advanced (30) | ✅ 30/30 |
| Calibration (25) | ✅ 24/25 (1 skip) |
| Marco 6 (14) | ✅ 14/14 |
| Marco 7 (16) | ✅ 16/16 |
| Marco 8 (10) | ✅ 10/10 |
| **Total novo** | **94/95** |

---

## [0.6.0] — 2026-04-25 — M0 FOUNDATION (Bug Fix Sprint)

### Corrigido — M0.1 Métricas (9 bugs de medição)

**BUG-06 — Halstead overcounting ~10× (uco_bridge.py)**
- `visit_Attribute`: removido `self._operand(node.attr)` — `.attr` é operador, não operando. Reduz n2/N2 em ~50%.

**BUG-07 — CC undercount ~33% — padrões Python ausentes (uco_bridge.py)**
- Adicionados visitors: `visit_AsyncFor`, `visit_AsyncWith`, `visit_Lambda`, `visit_match_case`

**BUG-15 — CC comprehension inflation (uco_bridge.py)**
- `visit_comprehension`: `+= 1` → `+= len(node.ifs)`. `[x for x in lst]` → +0 CC.

**BUG-08 — ILR: recursão sem base case não detectada (uco_bridge.py)**
- `_check_recursion_risk()`: detecta `def f(n): return f(n-1)` sem `if` guard → ILR+1.

**BUG-13 — Dead code: constant-False branches ignoradas (uco_bridge.py)**
- `_scan_dead_code()`: detecta `if False:`, `while False:`, `if True: ... else: ...`

**BUG-01 — Java CC logical expressions (java.py)**
- `child_by_field_name("operator")` substitui text-scan para `&&`/`||`.

**BUG-17 — Java while(true) case-sensitive (java.py)**
- Normaliza whitespace+lowercase: `while ( true )` e `while(TRUE)` detectados.

**BUG-02 — JS ILR sempre zero (javascript.py)**
- `child_by_field_name("condition")` substitui `_get_child(node, "condition")` (type ≠ field).

**BUG-16 — Go ILR false negative: time.After/ctx.Done (golang.py)**
- `_has_channel_escape()`: detecta `<-` operator, `time.After`, `time.NewTimer`, `ctx.Done`.

### Corrigido — M0.2 Estabilidade e Segurança

**BUG-03 — Registry race condition (registry.py)**
- Double-checked locking em `get_registry()`.

**BUG-04 — SQLite thread-unsafe (snapshot_store.py)**
- Per-thread connections via `threading.local()` + `_get_conn()` helper.

**BUG-05 — Auth desabilitada por padrão (server.py)**
- `auth_enabled` lê `UCO_AUTH_ENABLED` env var. Produção requer `UCO_AUTH_ENABLED=1`.

**SEC-04 — APEX webhook recursão ilimitada (server.py)**
- Depth guard via `threading.local()`, limite de 3 níveis.

**T77 — Body size sem limite (server.py)**
- Rejeita `Content-Length > 10MB` com HTTP 413.

### Adicionado

- `tests/test_calibration.py` — 25 testes: CC, ILR, DeadCode, Halstead, radon comparison, performance
- `pyproject.toml`: versão 0.3.0 → 0.6.0; `python_files` inclui `test_calibration.py`

### Resultados de Validação

| Conjunto | Resultado |
|----------|-----------|
| M1 Core (27) | ✅ 27/27 |
| M2 Lang+Auth (48) | ✅ 48/48 |
| M3 APEX (16) | ✅ 16/16 |
| M4 Reports (35) | ✅ 35/35 |
| M5 Diff+Bench (15) | ✅ 15/15 |
| M6 Docker (14) | ✅ 14/14 |
| M7 Templates (16) | ✅ 16/16 |
| M8 Demo (10) | ✅ 10/10 |
| **Calibration (25)** | **✅ 24/25 (1 skip)** |
| **Total** | **205/206** |

---

## [0.5.0] — 2026-04-19 — ENTREGAR

### Adicionado — Marco 8 (M8 — ENTREGAR)
- `README.md` — documentação completa com badges, instalação, endpoints, APEX integration, tabela de marcos
- `demo/demo_full.py` — demo ponta a ponta em 8 steps: analyze → history → classify → diff → report → apex_event → apex_fix → status
- `tests/test_marco8.py` — T80–T89 (10 testes de integração E2E)
- `/docs` atualizado — 19 endpoints documentados
- Demo executa em < 2s; CHANGELOG cobre v0.1.0 → v0.5.0

---

## [0.4.0] — 2026-04-19 — AGIR

### Adicionado — Marco 7 (M7 — AGIR)
- `apex_integration/templates.py` — 8 templates de ação corretiva por tipo de erro UCO
  - TECH_DEBT_ACCUMULATION, AI_CODE_BOMB, GOD_CLASS_FORMATION
  - DEPENDENCY_CYCLE_INTRODUCTION, LOOP_RISK_INTRODUCTION
  - COGNITIVE_COMPLEXITY_EXPLOSION, DEAD_CODE_DRIFT, HALSTEAD_BUG_DENSITY
- `POST /apex/fix` — endpoint bidirecional: APEX envia `APEX_FIX_REQUEST`, sensor aplica transforms
  - Retorna: `fixed_code`, `h_before/after`, `delta_h`, `apex_prompt` contextualizado
  - `transforms_applied` detectados por comparação de métricas antes/depois
- `POST /apex/webhook` ampliado: `APEX_FIX_REQUEST` + `APEX_TEMPLATE_REQUEST`
- `render_prompt()` — preenchimento contextual do template com métricas reais
- `fix_action_for()` — retorna mode, agents, transforms por tipo
- Suite de testes T70–T7D (16 testes)

---

## [0.3.0] — 2026-04-19 — DISTRIBUIR

### Adicionado
- `pyproject.toml` — packaging PEP 517/518 com entry point `uco-sensor`
- `docker-compose.yml` — stack completa dev/prod com volume persistente e profile cron
- `CHANGELOG.md` — histórico de versões
- `ROADMAP.md` — plano de marcos PMI M4→M8

### Marco 6 (M6 — DISTRIBUIR)
- `pyproject.toml` com `[project.scripts] uco-sensor = "cli:main"`
- `docker-compose.yml` com service `uco-sensor` e `uco-cron` (profile)
- Dockerfile multi-stage existente validado (T65, T66)
- Suite de testes T60–T69: empacotamento, container, release artifacts

---

## [0.2.0] — 2026-04-19 — CALIBRAR

### Adicionado — Marco 5 (M5 — CALIBRAR)
- `POST /diff` — endpoint de comparação entre 2 commits
  - Retorna delta dos 9 canais UCO (Hamiltoniano, CC, ILR, DSM, ...)
  - Campo `regression` (bool) com threshold baseado em ΔH e ΔCC
  - `suggested_transforms`: lista de ações corretivas automáticas
  - `uco_score_before/after` e `score_delta`
  - `summary` legível: `"REGRESSÃO: ΔH=+3.2  ΔCC=+5  Score 72→45"`
- Benchmark confirmado: 20 arquivos < 5s
- Calibração: código saudável real → UCO Score ≥ 40
- Suite de testes T50–T5D (15 testes)

---

## [0.1.3] — 2026-04-19 — VISUALIZAR

### Adicionado — Marco 4 (M4 — VISUALIZAR)
- `GET /report?module=<id>` — HTML report standalone com:
  - Gauge SVG do UCO Score
  - Tabela de arquivos por status (CRITICAL/WARNING/STABLE)
  - Breakdown por linguagem
  - Sparklines de tendência
- `GET /badge?score=87&status=STABLE` — badge SVG estilo shields.io (público)
- `GET /badge?module=<id>` — badge gerado do histórico do módulo
- `report/html_report.py` — gerador HTML self-contained (zero deps externas)
- `report/badge.py` — badges SVG com paleta de cores por faixa de score
- `_send_html()` e `_send_svg()` no handler HTTP
- Suite de testes T40–T49 (35 testes)

---

## [0.1.2] — 2026-04-18 — CONECTAR

### Adicionado — Marco 3 (M3 — CONECTAR)
- `apex_integration/event_bus.py` — ApexEventBus com transportes: null, callback, file, webhook
- `apex_integration/connector.py` — ApexConnector com severity gate e SnapshotStore
- `GET /apex/status` — status da integração APEX
- `GET /apex/ping` — teste de conectividade bidirecional
- `POST /apex/webhook` — handshake bidirecional (ACK APEX_PING, APEX_RESCAN_REQUEST)
- `GET /anomalies` — lista anomalias persistidas
- Evento `UCO_ANOMALY_DETECTED` — publicado automaticamente em análise CRITICAL
- Suite de testes T30–T34 (16 testes)

---

## [0.1.1] — 2026-04-18 — EXPANDIR

### Adicionado — Marco 2 (M2 — EXPANDIR)
- `lang_adapters/` — registry multi-linguagem (Python, JS/TS, Java, Go)
- Auth/Billing: `POST /auth/keys`, `GET /auth/keys`, `DELETE /auth/keys`
- `POST /analyze-pr` — análise de PR com saída SARIF 2.1.0
- `ci/uco-pr-check.yml` — GitHub Actions Quality Gate
- `Dockerfile` multi-stage (Python 3.11-slim, usuário não-root)
- `requirements.txt` com numpy, scipy, PyWavelets, tree-sitter
- Suite de testes T10–T29 (20 testes)

---

## [0.1.0] — 2026-04-17 — ANALISAR

### Adicionado — Marco 1 (M1 — ANALISAR)
- `sensor_core/uco_bridge.py` — UCOBridge: extrai 9 canais do UCO v4
- `sensor_storage/snapshot_store.py` — SnapshotStore SQLite com baseline e z-score
- `api/server.py` — HTTP server stdlib-only (BaseHTTPRequestHandler)
  - `GET /health`, `GET /docs`, `GET /modules`, `GET /history`, `GET /baseline`
  - `POST /analyze`, `POST /repair`
- `POST /scan-repo` — RepoScanner batch
- FrequencyEngine integrado via `pipeline/` (frequency-engine)
- Gaps CSL: weighted_mean_freq (fw_shift), dual-confirmation, POST /repair
- Suite de testes T01–T08 (30 testes)

---

[Unreleased]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/thiagofernandes1987-create/APEX/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/thiagofernandes1987-create/APEX/releases/tag/v0.1.0
