# Sprint AZ — SCA Gradle/Cargo (elasticsearch + clickhouse) + auditoria de contagem

> Aplica o pipeline análogo ao roslyn (AY) a manifestos de versão
> resolvida que os repos restantes expõem em formatos não escaneados
> antes — e faz uma auditoria honesta da contagem acumulada.

## #100 clickhouse — FECHADO (A, limpo); categoria Infra 5/5

O root do clickhouse tem só `pyproject.toml` (por isso fora marcado N/A).
Mas `rust/workspace/Cargo.lock` é um lockfile Rust real, pinando **267
crates**. `parse_cargo_lock` (novo no M9.4) extrai cada um; 34 têm
advisory no GHSA `cargo`, **todas patched** → veredito A. Eixo SCA
validado. **Categoria Infra (96-100) fechada: 5/5.**

## #71 elasticsearch — FECHADO (E, VULNERÁVEL — true-positive)

`gradle/build.versions.toml` (catálogo de versões Gradle) resolve 13
libs. `jackson-databind`@2.15.0 cai na janela vulnerável, verificada por
range contra o GHSA `maven`:

| CVE | range | 2.15.0 dentro? |
|---|---|---|
| CVE-2026-54515 | `>= 2.8.0, < 2.18.9` | SIM (patched 2.18.9) |
| CVE-2026-54514 | `>= 2.0.0, < 2.18.8` | SIM |
| CVE-2026-54513 | `>= 2.10.0, < 2.18.8` | SIM |
| CVE-2026-54512 | `>= 2.10.0, <= 2.18.7` | SIM |

`jackson-core`@2.15.0 também em `>= 2.0.0, <= 2.18.5` (GHSA sem CVE
atribuído). True-positive, rating E. **Categoria Java/Kotlin 7/10 → 8/10.**

## #75 kotlin — adiado (anti-FP)

`gradle/versions.properties` lista `versions.gson=2.11.0`,
`versions.log4j=1.2.17.2` etc. — **nomes curtos sem o group:artifact
Maven completo**. Mapear `log4j` → `log4j:log4j` vs
`org.apache.logging.log4j:log4j-core` é ambíguo; chutar arriscaria FP.
Adiado conscientemente.

## Auditoria de contagem — correção honesta de −1 e gaps omitidos

Ao fechar a categoria Infra, recontei todas as categorias e encontrei
duas imprecisões acumuladas:

1. **Total derivado +1.** Após AY reportei 88, mas a soma real das
   categorias era 87 (a linha de total drifou +1 em relação à soma).
2. **2 gaps de JS/TS omitidos da lista de "restantes".** A tabela tratava
   `denoland/deno` como "extra" quando é o **#5 numerado**, e trocara os
   rótulos de #3 (next.js), #5 (deno) e #14 (electron). A categoria de
   fato tem 18/20 cobertos — mas os 2 gaps reais (`#4 nodejs/node`, `#12
   expressjs/express`) nunca apareciam na contagem de restantes.

**Correção:** a soma das categorias é a fonte de verdade —
18(JS/TS)+19(Py)+15(Go)+9(Rust)+8(Java)+7(C/C++)+8(PHP)+5(Infra) =
**89/100**. Com os 2 fechamentos de AZ sobre a base correta de 87, o
total exato é **89**. Restam **11**: #4 node, #12 express, #34 boto3
(N/A), #59 serde, #73 redisson, #75 kotlin, #93 jekyll, #94 signal, #83
sqlite (reservado), #84 httpd, #85 wireshark.

Integridade da contagem acima do número: prefiro corrigir o tally para
baixo e expor a omissão a manter um número inflado.

## Estado dos motores

M9.4 cobre agora 5 formatos de manifesto resolvido: composer vendorizado
(VERSION), NuGet packages.config, NuGet CPM (Packages.props×Versions.props),
Gradle build.versions.toml, e Rust Cargo.lock. Três motores (M9.2 AST /
M9.3 GHSA-resolver / M9.4 SCA-multi-manifesto) levaram a cobertura de
74 (corrigido) a **89/100** nesta sessão, com true-positives verificados
(roslyn MessagePack, elasticsearch jackson) e zero fabricação.

## Restantes — por que resistem

| Gap | Bloqueio |
|---|---|
| #4 node, #12 express | JS/TS ainda não escaneados (têm package-lock — tratável em sprint futura) |
| #34 boto3 | requirements.txt só `-e git+`, sem versão |
| #59 serde | sem CVE/RUSTSEC de memory-safety |
| #73 redisson | só autofix CodeQL, sem CVE |
| #75 kotlin | versions.properties sem coordenada Maven |
| #93 jekyll, #94 signal | sem lockfile / versão resolvida |
| #84 httpd, #85 wireshark | SVN/GitLab, GHSA sem /commit/ |
| #83 sqlite | reservado para teste de FP (constraint do usuário) |

Os mais tratáveis: **#4 node e #12 express** têm `package-lock.json`
(Node) — escaneáveis na próxima sprint, análogo aos demais JS/TS.
