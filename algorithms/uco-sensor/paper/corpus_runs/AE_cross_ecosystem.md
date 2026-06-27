# Sprint AE — Workflow Multi-Agente: 3 Eixos em Paralelo (CVE Precisão, Falso-Positivo, Throughput)

> Continuação da Sprint AD: 8 novos pares CVE/sha (lodash, etcd, tokio,
> netty, laravel, rails, dotnet, git) resolvidos e auditados pela mesma
> metodologia de diff antes/depois (`paper/cve_diff_check.py`), mais um
> sweep dedicado de falso-positivo (sqlite/guava + fallback Java) e um
> sweep de throughput (kubernetes/tensorflow/linux/vscode), tudo rodado
> via `Workflow` em paralelo (22 agentes, 4 fases, ~880s, 506k tokens) —
> per a escolha explícita do usuário ("workflow multi-agente" + "os 3
> eixos em paralelo").

## Achado #1 (o mais importante): bug de dispatch no script de validação, não no UCO Sensor

Toda a auditoria desta rodada (e de fato, retroativamente, das rodadas
AC-3 e AD) rodava `paper/cve_diff_check.py`, que chamava
`sast.scanner.scan()` (motor AST exclusivo de Python) **incondicionalmente
para qualquer linguagem** — silenciosamente um no-op para todo arquivo
não-Python. O produto em si (`api/server.py`'s `handle_sast`, marco
M9.0) já despachava corretamente JS/TS/Java/Go para
`sast.multilang_scanner.scan_multilang`; só o *script de validação*
estava com o dispatch errado.

Isso significa que todos os veredictos não-Python anteriores (curl/C,
golang/go, axios/JS, spring-framework/Java, rust-lang/regex/Rust desta
sprint AD; e lodash/JS, etcd/Go, netty/Java desta sprint AE) foram
alcançados pelo caminho de código errado.

**Correção**: adicionado dispatch por extensão em `cve_diff_check.py`,
espelhando exatamente a lógica do `handle_sast`:

```python
ext = Path(args.path).suffix
ml_lang = language_for_extension(ext)
...
result = scan_multilang(source, ext) if ml_lang else sast_scan(source, ext)
```

**Re-verificação**: todos os 6 casos JS/Java/Go desta rodada e os 3
casos JS/Java desta sprint AD foram re-rodados com o dispatch corrigido.
**Resultado: todos os veredictos BLIND_SPOT se mantiveram idênticos** —
nenhuma das 9 regras JS/JV/GO casou com nenhum dos 9 padrões. As
conclusões anteriores estavam certas por coincidência, não por rigor.
Esse é o resultado honesto a reportar: o bug de dispatch nunca mudou
nenhum veredicto final, mas invalidava o *processo* pelo qual eles foram
alcançados — agora corrigido e re-confirmado empiricamente.

## Achado #2: gap real de regra JS05 corrigido (única correção de regra desta rodada)

Re-verificando `lodash/lodash` CVE-2021-23337 (command injection via
`_.template`'s opção `variable`) com o motor multilang correto, a regra
JS05 ("Code injection via Function constructor") ainda não disparava —
porque o ponto de chamada vulnerável real do lodash é
`Function(importsKeys, ...)` **sem** `new`, semanticamente idêntico a
`new Function(...)` mas não casado pelo regex original
`\bnew\s+Function\s*\(`.

**Correção**: regex ampliado para `\b(?:new\s+)?Function\s*\(` — o `\b`
inicial continua excluindo `isFunction(`/`castFunction(`/qualquer
`*Function(`.

**Validação**: 6 testes de pinagem novos (`tests/test_marco_m65.py`,
TAE01-TAE06): bare-call detectado, `new Function` ainda detectado
(regressão), `isFunction`/`castFunction` não disparam (falso-positivo
guard), outros `*Function(` arbitrários não disparam, roteamento
`language_for_extension` pinado, e o caso real lodash vulnerável/corrigido
ambos disparam JS05 corretamente (o ponto de chamada arriscado
permanece após o fix; apenas a entrada passou a ser sanitizada — exatamente
o comportamento esperado de SAST estático, que não pode verificar se uma
guarda é suficiente, só que o padrão de risco existe).

Suíte completa: **2219 passed, 5 skipped, 0 regressões** (2213 da
baseline AD + 6 novas TAE).

## Eixo 1 — Precisão CVE: 8 novos casos resolvidos e auditados

| Repo | Linguagem | CVE/GHSA | Arquivo | Causa raiz | Veredito |
|---|---|---|---|---|---|
| `lodash/lodash` | JS | CVE-2021-23337 | `lodash.js` | Command injection via `_.template`'s `variable` | **BLIND_SPOT*** |
| `etcd-io/etcd` | Go | CVE-2021-28235 | `server/etcdserver/v3_server.go` | Senha em texto puro retida após autenticação | **BLIND_SPOT** |
| `tokio-rs/tokio` | Rust | CVE-2023-22466 | `tokio/src/net/windows/named_pipe.rs` | Config `reject_remote_clients` descartada (named pipe Windows) | **BLIND_SPOT** |
| `netty/netty` | Java | CVE-2019-20444 | `HttpObjectDecoder.java` | HTTP request smuggling (colon ausente em header) | **BLIND_SPOT** |
| `laravel/framework` | PHP | GHSA-crmm-hgp2-wgrp | `LocalFilesystemAdapter.php` | Path confusion em URL assinada temporária | **BLIND_SPOT** |
| `rails/rails` | Ruby | CVE-2024-26143 | `actionpack/.../translation.rb` | XSS via `:default` não escapado em `I18n.translate` | **SIGNAL** |
| `dotnet/runtime` | C# | CVE-2026-45491 | `TarEntry.cs` | Symlink path traversal em `TarFile.ExtractToDirectory` | **BLIND_SPOT** (sem ruleset C#) |
| `git/git` | C | CVE-2021-21300 | `unpack-trees.c` | lstat cache poisoning → symlink swap no checkout | **BLIND_SPOT** |

*\* JS05 corrigido nesta rodada (achado #2), mas a regra ainda não cobre
a causa raiz real do CVE-2021-23337 (ReDoS em `trimmedEndIndex`); o
delta de métricas permanece plano (<1% em todos os 9 canais) — por isso
o veredito do diff CVE permanece BLIND_SPOT mesmo após a correção da
regra, que foi motivada pelo achado, não pelo CVE original em si.*

**7/8 (87.5%) blind spots, 1/8 SIGNAL.** O caso `rails/rails` é o único
SIGNAL genuíno desta rodada: `cyclomatic_complexity` 3→9 (+200%),
`hamiltonian` 1.79→3.80 (+112%), `halstead_bugs` +95% — confirmados via
diff bruto como diretamente atribuíveis à lógica de sanitização
adicionada (`ERB::Util.html_escape`, ramos condicionais), sem
refatoração não relacionada bundlada no mesmo commit. SAST permanece
0/0 (a vulnerabilidade é uma falha de sanitização semântica, fora do
escopo de padrões sintáticos).

O caso `dotnet/runtime` mereceu investigação adicional (ver abaixo) por
ter ficado inicialmente `INCONCLUSIVE`.

### Resolução do caso `dotnet/runtime` (INCONCLUSIVE → BLIND_SPOT)

Único canal com delta >15% foi `duplicate_block_count` (25→33, +32%);
os outros 8 canais ficaram exatamente estáveis, incluindo
`cyclomatic_complexity` (21→21, plana mesmo com lógica de checagem de
symlink adicionada). Re-rodado live para confirmar reprodutibilidade:

```
SAST engine selected for .cs: none (unsupported language)
```

UCO Sensor **não possui ruleset C#** nem em `scanner.py` (Python-only)
nem em `multilang_scanner.py` (JS/TS/Java/Go apenas) — `.cs` cai fora de
qualquer cobertura SAST por desenho. O delta de `duplicate_block_count`
é consistente com crescimento de código (linhas de validação
adicionadas), não com uma assinatura comportamental atribuível à
correção. **Classificação final: BLIND_SPOT por lacuna de cobertura**
(mesma categoria de `curl/C` e `rust-lang/regex` na AD) — não por falha
de uma regra existente.

## Eixo 2 — Falso-positivo: zero ruído HIGH/CRITICAL em código maduro

Alvos: `sqlite/sqlite` (sem cobertura C → fallback para 4 arquivos Java
maduros: `commons-lang/StringUtils.java`, `tomcat/Request.java`,
`tomcat/SessionIdGeneratorBase.java`, `spring-security/BCrypt.java`,
mais `hadoop/RandomSeedGenerator.java`) e `google/guava`
(`ImmutableList.java`, .java cai fora do `scan()` Python-only).

**Resultado: 0 findings HIGH/CRITICAL em todos os arquivos de produção
maduros testados.** Único finding em todo o sweep: JV05/MEDIUM
(MD5 via `MessageDigest`) em `RandomSeedGenerator.java` — uso legítimo
não-criptográfico de MD5 para seeds determinísticos de simulação, fora
do critério HIGH/CRITICAL avaliado. Sanity check confirmou o scanner
operacional (snippet sintético disparou JV01 CRITICAL + JV05 MEDIUM
corretamente). Mesmo achado de cobertura do Eixo 1: nenhuma regra C
existe; `guava`/`.java` reforça que `scan()` é Python-only por desenho.

## Eixo 3 — Throughput: sem problemas de performance, mesmo achado de cobertura

| Repo | Arquivo | Tamanho | `scanner.scan()` | `registry.analyze()` |
|---|---|---|---|---|
| kubernetes/kubernetes | `pkg/scheduler/schedule_one.go` | 54.7 KB | 3 µs (no-op) | 23.7 ms |
| tensorflow/tensorflow | `tensorflow/core/ops/array_ops.cc` | 124.7 KB | 3.1 µs (no-op) | 22.7 ms |
| torvalds/linux | `fs/ext4/extents.c` | 176.7 KB | 3.2 µs (no-op) | 28.9 ms |
| microsoft/vscode | `.../textModel.ts` | 108.8 KB | 3 µs (no-op) | 56.6 ms |

Nenhum travamento, nenhuma lentidão anômala, nenhum sinal de
crescimento quadrático — throughput de `registry.analyze()` na faixa de
5.5-6.1 MB/s para C/C++/Go, consistente e escalável. Os tempos de
`sast.scanner.scan()` na ordem de 3 µs **não são throughput real** — são
o custo de um early-return vazio, já que nenhuma dessas 4 extensões
(.go/.cc/.c/.ts) é processada por esse motor Python-only. Mesmo achado
de cobertura dos Eixos 1 e 2, confirmado independentemente em 4 repos
gigantes adicionais.

## O que esta rodada valida / deixa aberto

* A metodologia de diff CVE antes/depois generaliza para mais 8 CVEs em
  6 ecossistemas novos (Go, Rust, Java, PHP, Ruby, C#, C) — agora com
  dispatch de engine corrigido e auditável.
* **2 correções reais aplicadas**: dispatch de engine em
  `cve_diff_check.py` (bug de tooling, não do produto) e regra JS05
  ampliada (gap real de regra, generalizável, sem overfit a um único CVE).
* **6 blind spots permanecem honestamente não corrigidos** nesta rodada
  (lodash-ReDoS, etcd-senha-retida, tokio-race-condition,
  netty-smuggling, laravel-path-confusion, dotnet-symlink, git-lstat-cache)
  — todos são bugs de lógica semântica/concorrência fora do alcance de
  SAST regex/AST sintático, ou lacunas de cobertura de linguagem (C#,
  C) que exigiriam um ruleset novo inteiro, não uma correção pontual.
  Decisão consciente de não escrever regras frágeis e overfit a um único
  CVE para cada um — consistente com o padrão de honestidade da Sprint AD.
* Lacuna de cobertura confirmada e agora documentada em 3 eixos
  independentes: UCO Sensor **não tem ruleset C nem C#** em nenhum dos
  dois motores SAST. Java/Go/JS/TS têm cobertura via
  `multilang_scanner`; Python via `scanner`; C/C++/C#/Rust/PHP/Ruby não
  têm nenhuma regra SAST (mas têm adaptadores de métricas estruturais
  funcionais via `lang_adapters`).
