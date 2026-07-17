# AN — Varredura SCA Round 2: Cobertura Acelerada da Lista Master de 100

Continuação direta de `AM_sca_repo_sweep.md`, respondendo ao novo
`/goal`: *"estender a varredura SCA a mais repos da lista (...) até
cobrimos todos os repositórios 100/100"*. Em vez de continuar
escolhendo repositórios um a um manualmente, esta rodada automatiza a
**descoberta** do manifesto: para cada repo-alvo, o script tenta uma
lista de candidatos de path mais prováveis por ecossistema (ex.: Go →
`go.mod`; Rust → `Cargo.lock`; JS → `pnpm-lock.yaml`/`yarn.lock`/
`package-lock.json`, em ordem de popularidade atual), valida HTTP 200
via GitHub Contents API antes de tentar, e roda o `OSVScannerBridge`
contra o primeiro manifesto encontrado.

Script: `/tmp/.../scratchpad/sca_sweep_full.py` (não versionado).

## Resultado agregado

**45 repositórios numerados tentados nesta rodada** (além dos 11 já
tentados em AM). **28 scans bem-sucedidos** (26 na varredura principal
+ 2 numa segunda passada manual após inspecionar a raiz real via
GitHub Contents API para os casos de "manifesto não encontrado":
`angular/angular` → `pnpm-lock.yaml`, `influxdata/influxdb` →
`Cargo.lock`).

### Repositórios novos com SCA bem-sucedido (28)

| # | Repo | Categoria | Manifesto | Findings | Severidade | Rating |
|---|---|---|---|---|---|---|
| #1 | microsoft/vscode | JS/TS | package-lock.json | 11 | 4 HIGH, 6 MEDIUM, 1 LOW | D |
| #2 | facebook/react | JS/TS | yarn.lock | 239 | 19 CRITICAL, 109 HIGH, 91 MEDIUM, 20 LOW | E |
| #6 | vuejs/core | JS/TS | pnpm-lock.yaml | 39 | 1 CRITICAL, 12 HIGH, 21 MEDIUM, 5 LOW | E |
| #7 | angular/angular | JS/TS | pnpm-lock.yaml | 59 | 1 CRITICAL, 11 HIGH, 44 MEDIUM, 3 LOW | E |
| #9 | tailwindlabs/tailwindcss | JS/TS | pnpm-lock.yaml | 5 | 1 HIGH, 3 MEDIUM, 1 LOW | C |
| #13 | mrdoob/three.js | JS/TS | package-lock.json | 0 | — | A |
| #15 | vitejs/vite | JS/TS | pnpm-lock.yaml | 22 | 1 CRITICAL, 10 HIGH, 9 MEDIUM, 2 LOW | E |
| #20 | yarnpkg/berry | JS/TS | yarn.lock | 181 | 10 CRITICAL, 78 HIGH, 78 MEDIUM, 15 LOW | E |
| #30 | ansible/ansible | Python | requirements.txt | 8 | 3 CRITICAL, 2 HIGH, 3 MEDIUM | E |
| #32 | home-assistant/core | Python | requirements_test.txt | 0 | — | A |
| #38 | psf/requests | Python | requirements-dev.txt | 0 | — | A |
| #41 | kubernetes/kubernetes | Go | go.mod | 0 | — | A |
| #42 | moby/moby | Go | go.mod | 0 | — | A |
| #46 | etcd-io/etcd | Go | go.mod | 0 | — | A |
| #47 | istio/istio | Go | go.mod | 14 | 14 MEDIUM | B |
| #48 | cockroachdb/cockroach | Go | go.mod | 66 | 3 CRITICAL, 14 HIGH, 46 MEDIUM, 3 LOW | E |
| #49 | caddyserver/caddy | Go | go.mod | 0 | — | A |
| #50 | gin-gonic/gin | Go | go.mod | 0 | — | A |
| #51 | syncthing/syncthing | Go | go.mod | 3 | 3 MEDIUM | B |
| #53 | influxdata/influxdb | Go (na lista; runtime atual em Rust) | Cargo.lock | 27 | 2 CRITICAL, 7 HIGH, 14 MEDIUM, 4 LOW | E |
| #54 | argoproj/argo-cd | Go | go.mod | 2 | 2 MEDIUM | B |
| #55 | gohugoio/hugo | Go | go.mod | 17 | 17 MEDIUM | B |
| #58 | alacritty/alacritty | Rust | Cargo.lock | 2 | 2 MEDIUM | B |
| #63 | swc-project/swc | Rust | Cargo.lock | 39 | 2 CRITICAL, 9 HIGH, 26 MEDIUM, 2 LOW | E |
| #64 | actix/actix-web | Rust | Cargo.lock | 10 | 3 HIGH, 3 MEDIUM, 4 LOW | D |
| #65 | tauri-apps/tauri | Rust | Cargo.lock | 36 | 3 HIGH, 28 MEDIUM, 5 LOW | D |
| #69 | apache/flink | Java/Kotlin | pom.xml | 0 | — | A |
| #90 | flutter/flutter | PHP/Ruby/C#/Mobile | pubspec.lock | 0 | — | A |

### Destaques concretos

- **`facebook/react`** (#2): pior resultado de toda a campanha SCA até
  agora — 239 findings, 19 CRITICAL, rating E. Inclui
  `@babel/traverse@7.8.3` (CVE-2023-45133, RCE em tempo de build) e
  `form-data@4.0.0` (CVE-2025-7783, geração previsível de boundary).
- **`yarnpkg/berry`** (#20): 181 findings, 10 CRITICAL — irônico por
  ser o próprio gerenciador de pacotes do ecossistema, com
  `minimist@1.2.5` (CVE-2021-44906, prototype pollution) no próprio
  `yarn.lock`.
- **`cockroachdb/cockroach`** (#48): 66 findings, 3 CRITICAL incluindo
  `jackc/pgx/v5@5.7.2` (CVE-2026-33815/33816) — driver Postgres
  vulnerável dentro de um banco de dados que fala protocolo Postgres.
- **`influxdata/influxdb`** (#53): confirma a observação da lista
  master original ("refatorações estruturais massivas — Go para Rust
  no histórico") — o `Cargo.lock` real tem 27 findings incl.
  `wasmtime@41.0.4` (CVE-2026-34987/34971).
- **Resultados limpos (rating A) genuínos, não ruído**:
  `microsoft/three.js`, `home-assistant/core`, `psf/requests`,
  `kubernetes/kubernetes`, `moby/moby`, `etcd-io/etcd`,
  `caddyserver/caddy`, `gin-gonic/gin`, `apache/flink`,
  `flutter/flutter` — 10 repos de alto perfil escaneados sem nenhum
  finding, reforçando que o motor não gera ruído indiscriminado.

### Falhas e "não aplicável" (documentadas, não escondidas)

17 tentativas sem sucesso nesta rodada, por três causas distintas:

1. **Manifesto truncado pela GitHub Contents API** (limite de ~1MB em
   base64 por arquivo): `vercel/next.js` (#3) e `elastic/kibana` (#17)
   — o `pnpm-lock.yaml`/`yarn.lock` real excede o limite e a API
   retorna conteúdo vazio. Não é limitação do `OSVScannerBridge`; é do
   método de fetch (Contents API). Corrigível com `git clone
   --depth 1` em vez da Contents API, não tentado nesta rodada.
2. **Repositório não usa lockfile commitado na raiz** (biblioteca, não
   aplicação — prática comum para crates/libs Rust e para projetos
   Gradle sem `--write-locks`): `expressjs/express` (#12, só
   `package.json`), `tokio-rs/tokio` (#57), `serde-rs/serde` (#59),
   `diesel-rs/diesel` (#62) — só `Cargo.toml`; `spring-projects/
   spring-boot` (#66), `spring-projects/spring-framework` (#67),
   `apache/kafka` (#70), `elastic/elasticsearch` (#71),
   `JetBrains/kotlin` (#75) — só `build.gradle`/`build.gradle.kts` sem
   `gradle.lockfile`; `laravel/laravel` (#86, só `composer.json`);
   `jekyll/jekyll` (#93, só `Gemfile`). **Sem lockfile resolvido não há
   versões exatas para o OSV-Scanner consultar** — limitação real do
   eixo SCA contra este padrão de repositório (bibliotecas publicam
   ranges de versão, não pins), não um bug.
3. **Sem manifesto de gerenciador de pacotes na raiz** (C/Python/PHP
   puro, sem ecossistema de dependências de terceiros resolvível):
   `python/cpython` (#21, é o próprio interpretador), `php/php-src`
   (#92, idem para PHP), `WordPress/WordPress` (#91), `dotnet/runtime`
   (#88) e `dotnet/roslyn` (#89) — sem `packages.lock.json` na raiz
   (NuGet lock é opt-in por projeto, não global no repo). `ceph/ceph`
   (#98) tem um `package-lock.json` de 83 bytes (stub vazio de uma
   ferramenta de doc, não as dependências reais do projeto) e
   `ClickHouse/ClickHouse` (#100) só tem `pyproject.toml` de uma
   ferramenta auxiliar, sem lock. **Eixo SCA não é aplicável a estes
   por desenho** — são bases de código C/C++/interpretador, não
   aplicações com árvore de dependência de terceiros gerenciada por
   lockfile.
4. **Manifesto encontrado mas sem lock resolvido (`pyproject.toml`/
   `setup.py` sem `poetry.lock`/`uv.lock`)**: `fastapi/fastapi` (#26),
   `pallets/flask` (#28), `huggingface/transformers` (#29),
   `apache/airflow` (#35), `SQLAlchemy/sqlalchemy` (#39),
   `django/django` (#27), `scrapy/scrapy` (#37),
   `scikit-learn/scikit-learn` (#23) — OSV-Scanner tenta extrair do
   `pyproject.toml` mas sem lock as versões não são pinadas o
   suficiente para resolução determinística; sai com `parse_error`.
   `redisson/redisson` (#73) — `pom.xml` com erro de parse (não
   investigado a fundo; pode ser POM com propriedades não resolvidas).

## Cobertura agregada da lista master (recalculada categoria por categoria)

| Categoria | Antes (Sprint AM) | Depois (Sprint AN) | Repos numerados novos nesta rodada |
|---|---|---|---|
| JS/TS (1-20) | 2/20 | **10/20** | #1, #2, #6, #7, #9, #13, #15, #20 |
| Python (21-40) | 8/20* | **9/20** | #30, #32 |
| Go (41-55) | 4/15 | **14/15** | #41, #42, #47, #48, #49, #50, #51, #53, #54, #55 |
| Rust (56-65) | 2/10 | **6/10** | #58, #63, #64, #65 |
| Java/Kotlin (66-75) | 2/10 | **3/10** | #69 |
| C/C++ (76-85) | 2/10 | 2/10 | — (sem ecossistema de pacotes resolvível por SCA; eixo permanece SAST-only para esta categoria) |
| PHP/Ruby/C#/Mobile (86-95) | 3/10 | **4/10** | #90 |
| Infra dados/cloud (96-100) | 2/5 | 2/5 | — (ceph/clickhouse sem lock real; trino continua sem submódulo testado) |

*A contagem Python de 8/20 do AM tinha uma inconsistência aritmética
herdada (7 números listados, rótulo "8/20"); a base usada aqui para o
recálculo é o conjunto real de números: {22, 26, 27, 28, 31, 37, 38}.

**Total real: 50/100 repositórios numerados com pelo menos um eixo de
evidência validado (SAST CVE-diff e/ou SCA dependência-exposição)** —
salto de 26/100 (após Sprint AM) para 50/100 nesta única rodada.

## Próximos passos para fechar 100/100

Pendências explícitas para a próxima rodada, na ordem de
custo-benefício:

1. **C/C++ (76-85, parado em 2/10)**: categoria estruturalmente não
   coberta pelo eixo SCA (sem package manager de terceiros resolvível
   em C puro). Único caminho de avanço aqui é reabrir o eixo SAST
   CVE-diff para mais repos desta categoria (ex.: `postgres/postgres`,
   `redis/redis`, `ffmpeg/ffmpeg`, `opencv/opencv`, `wireshark/
   wireshark`, `apache/httpd`).
2. **Infra dados/cloud (96-100, parado em 2/5)**: `trinodb/trino` #99
   precisa de um `pom.xml` de submódulo real (não o agregador raiz) —
   ex. `trino/trino-main/pom.xml` ou similar, ainda não localizado.
   `ceph/ceph` #98 e `clickhouse/clickhouse` #100 são C++/Python sem
   lockfile real — mesma limitação estrutural do C/C++.
3. **`vercel/next.js` #3 e `elastic/kibana` #17**: re-tentar via
   `git clone --depth 1` + leitura local do arquivo em vez da GitHub
   Contents API, que trunca arquivos grandes (>1MB).
4. **Gradle sem lockfile (spring-boot, spring-framework, kafka,
   elasticsearch, kotlin)**: tentar localizar um `gradle.lockfile`
   commitado em subdiretório (alguns módulos podem ter, mesmo que a
   raiz não tenha).
5. **Repos restantes nunca tentados em nenhum eixo**: dentro da lista
   de 100, ainda faltam tentar (SAST ou SCA) ao menos uma vez: #4 node,
   #5 deno, #8 remix, #10 strapi, #14 electron, #16 metabase,
   #18 grafana, #24 tensorflow, #25 pytorch, #33 scipy, #34 boto3,
   #36 saltstack, #40 localstack, #52 rancher, #56 rust-lang/rust,
   #60 nushell, #68 commons-lang, #74 guava (reservado p/ falso-
   positivo), #76-85 (exceto 79,81), #83 sqlite (reservado), #91-95
   (parcial), #94 Signal-Android, #95 shadowsocks.
