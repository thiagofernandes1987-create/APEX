# Prompt de Auditoria Independente — UCO Sensor (APEX)

> **Como usar:** cole este prompt inteiro em um LLM especializado em código
> (com acesso ao repositório APEX, branch `claude/analyze-apex-repository-BiVMP`,
> diretório `algorithms/uco-sensor/sensor-api`). O objetivo é uma auditoria
> ADVERSARIAL e independente do trabalho feito — não uma revisão gentil.

---

## Contexto do sistema a auditar

O **UCO Sensor** é um avaliador de qualidade/segurança de código (Python, ~2522
testes pytest, versão 3.65.0) cujo objetivo comercial nº1 é **encontrar bugs em
código gerado por IA** e, para um corpus de CVEs reais, produzir a análise de
degradação: **quando quebrou, como quebrou, onde quebrou, em qual versão foi
resolvido** — validando se, na versão corrigida, o sinal **parou de disparar** e
se algo **perpetuou** sem ser detectado.

### Pipeline automático a auditar (o coração do sistema — Sprint CN/CP)
    CVE --WebSearch--> GHSA --M25 resolve--> advisory(versão fixed, commit)
        --WebFetch(página do commit)--> arquivos alterados --M27 pick--> arquivo
        --M27 prior_version + raw--> par(vuln,fixed) --M24 compose--> 4 respostas
Só o 1º passo (CVE→GHSA) usa WebSearch; o resto é determinístico. Estado atual do
corpus: **9 CVEs completos 4/4** (jinja, requests, werkzeug, urllib3, Flask,
aiohttp, PyJWT, tornado, Django) de 14 registros, cobrindo 9 classes de vuln.
Persistido em `paper/corpus_runs/degradation_report_pypi.json`. O gap aos 100/100
é VOLUME (coletar mais CVEs, mecânico) + teto de dado público (alguns C/refactor
não têm as 4 respostas — proibido inventar).

Princípio inegociável do projeto: **DADOS REAIS, SEM FABRICAÇÃO**. Um
falso-positivo afirmado é PIOR que um falso-negativo. Toda alegação de detecção
deve ser reproduzível contra dado real (arquivos buscados por SHA/tag via
`raw.githubusercontent.com`; a API de commits do GitHub e o osv.dev REST estão
bloqueados por política de rede = 403).

### Módulos a auditar (mapa)
- **M7.2 `sast/taint_engine.py`** — TaintAnalyzer intra-procedural (AST Python):
  vocabulário de source/sink/sanitizer (`_is_source`, `_get_sink_meta`,
  `_is_sanitizer`, `_SANITIZER_FUNCTIONS`).
- **M17 `sast/taint_interproc.py`** — InterprocTaintAnalyzer (call-graph, taint
  cruzando funções). Gating SQL: em sink SQL só `arg[0]` (query) conta.
- **M22 `sast/taint_cfg.py`** — CFGTaintAnalyzer: taint **fluxo/caminho-sensível**
  sobre a CFG do UCO V4 (ponto-fixo forward `IN=∪OUT[preds]`,
  `OUT=(IN−KILL)∪GEN`). Reusa o vocabulário do M7.2.
- **M10 `sast/fix_localizer.py`** — FixDiffLocalizer: localiza o guard ADICIONADO
  pelo fix via diff (before/after), classifica CWE. Anti-relocação por CONTAGEM.
- **M11 `sast/guard_aware.py`** — GuardAwareScanner: detecta se um guard de
  memory-safety "parou de disparar" na versão corrigida.
- **M12 `scan/corpus_validator.py`** — orquestra M10+M11 before/after por CVE.
- **M13 `uco_core/`** — UCO V4 absorvido (CFG real via `PythonCFGBuilder`,
  `python_defs_uses`).
- **M18 `sast/fix_suggester.py`** / **M19 `apex_integration/apex_loop.py`** —
  Sensor→Corretor→Revalida (loop local, sem IA externa ainda).
- **M23 `scan/advisory_harvester.py`** — parseia advisory OSV (GitHub Advisory
  Database via raw) → registro de degradação (introduced/fixed/fix_commit/CWE).
- **M24 `scan/corpus_expander.py`** — funde M23+M10+M11 num `DegradationRecord`
  (as 4 perguntas); `expand_batch` com fetcher injetável; `narrative()`.
- **M25 `scan/advisory_resolver.py`** — auto-resolve GHSA→(ano,mês) por
  brute-force determinístico (elimina o seed manual).
- **M26 `scan/nvd_harvester.py`** — harvester NVD (cvelistV5 via raw) para
  projetos C sem GHSA (estende as 4 perguntas além do ecossistema empacotado).
- **M27 `scan/fix_file_locator.py`** — `pick_source_file` + `prior_version` +
  `build_pair`: lê a página do commit (WebFetch; `.patch` é 403) e identifica o
  arquivo alterado automaticamente, montando o par vuln/fixed por tag.
- API em `api/server.py` (endpoint `/scan-flow` expõe a camada `cfg_taint` do M22).

---

## O que auditar (seja adversarial e específico)

### 1. Anti-falso-positivo (prioridade máxima)
- Nas assinaturas de guard do M10 (`_GUARD_SIGNATURES`), a `bounds-check-call`
  (`(?i)\b\w*(check\w*(bound|overflow|range|limit)|...)\s*\(`) pode disparar em
  chamadas benignas (`check_range()` de negócio)? Ela só roda em linhas
  ADICIONADAS num diff de CVE conhecido — isso basta para o baixo-FP, ou há
  cenário de FP? Proponha um contra-exemplo real.
- O filtro anti-relocação por CONTAGEM (`fixed_counts[s] > vuln_counts[s]`)
  pode deixar passar uma relocação legítima (mesma linha reordenada) como se
  fosse adição, quando o fix duplica uma linha comum? Ou descartar um guard
  genuíno? Dê um caso.
- No M17/M22, o gating SQL "só arg[0]" perde injeção real em algum driver onde o
  perigo está em outro argumento (ex.: `executemany`, `execute(sql, ..., extra)`
  com formatação)? Verifique.
- O `int()/float()` como sanitizador FORTE: há sink onde um cast numérico NÃO
  neutraliza (ex.: o valor int volta a ser concatenado num contexto de path
  traversal / SSRF por ID numérico)? Avalie o risco.

### 2. Alegações de "dado real" (verifique, não confie)
- O M23 alega que o GitHub Advisory Database é acessível via raw e traz
  introduced/fixed/commit. **Reproduza**: busque `GHSA-h5c8-rqwp-cp95` e
  `GHSA-j8r2-6x86-q33q` via raw e confira os campos contra os testes TX95.
- O corpus (`paper/corpus_runs/degradation_report_pypi.json`) alega **9 CVEs
  completos 4/4**. **Verifique cada um**: as 4 respostas (quando/onde/como/
  qual-versão) batem com o advisory real e o diff real? O `narrative()` do M24
  não fabrica nenhum campo? Repita para jinja, requests, Flask, Django.
- O pipeline automático (M25→M27→M24) é reproduzível? Pegue um CVE PyPI NOVO
  (fora do corpus) e rode a esteira — ela responde 4/4 sem intervenção manual
  além do CVE→GHSA? Onde falha, é teto de dado público ou bug?
- **Perpetuação:** para os fixes, o M11 confirma que o sinal PAROU de disparar na
  versão corrigida, e sinaliza se algo perpetuou? Ou só assume?

### 3. Casamento antes↔depois e "perpetuação"
- O M12/M19 classifica findings em fixed / pre-existing(perpetuado) /
  introduced(regressão). O casamento de um finding "antes" com "depois" lida
  com DESLOCAMENTO DE LINHA após o patch? (Referência: método D2A,
  arXiv:2102.07995.) Se casa por linha crua, aponte o bug.

### 4. Dead code / integração
- Há função/método/constante criada e NUNCA chamada? **IMPORTANTE:** se achar,
  NÃO conclua "dead code" — investigue se é uma CHAMADA ESQUECIDA (feature não
  ligada). Liste cada caso com o diagnóstico (esquecido vs realmente morto).
- Todo módulo está integrado com os endereços/chamadas corretos? A camada
  `cfg_taint` (M22) no `/scan-flow` preserva o contrato legado?

### 5. Testes (tautologias e cobertura)
- Algum teste é tautológico (mocka o que deveria testar, ou afirma o óbvio)?
- Os fixtures dos testes de CVE são recortes REAIS do dado, ou inventados?
  (Ver TX78/TX92/TX94/TX95.)
- Há caminho de código de segurança sem teste de regressão?

### 6. Extração de potencial não-usado (o mote do projeto)
- Há sinal chegando aos motores que NÃO está sendo processado? Ex.: o advisory
  OSV tem `published`/`modified` (datas), `severity` (CVSS vector),
  `database_specific.github_reviewed` — o M23 ignora alguns. Vale capturar?
- O UCO V4 (`uco_core/universal_code_optimizer_v4.py`, ~4255 linhas) tem
  capacidade (HMC/SA optimizers, DSM, Halstead, Hamiltonian) ainda não
  aproveitada pelo Sensor? Aponte o que teria ROI.

---

## Entregável esperado da auditoria
1. Lista de **defeitos confirmados** (com arquivo:linha, cenário de falha
   concreto, e severidade), ordenada por severidade.
2. Lista de **falsos-positivos plausíveis** nas assinaturas (com contra-exemplo).
3. **Dead code** com diagnóstico esquecido-vs-morto para cada caso.
4. **Sinais não-processados** de alto ROI (o que ligar).
5. Veredito sobre a alegação de **dado real** (reproduziu? bateu?).
6. Recomendação priorizada do que corrigir ANTES de escalar o corpus a 100/100.

Reproduza tudo que puder (`cd algorithms/uco-sensor/sensor-api && python3 -m
pytest -q`). Não aceite alegação sem evidência. Reporte números honestos.
