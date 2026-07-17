# Sprint BB — fecha redisson via SCA Maven; um falso-positivo de parsing evitado

> Fecha #73 redisson e — mais importante — documenta um **falso-positivo
> que a disciplina pegou** antes de virar dado no corpus.

## #73 redisson — FECHADO (A, limpo)

redisson é Maven. `redisson/pom.xml` declara 24 dependências com versão
inline. M9.4 (`parse_maven_pom` + `scan_package` maven) checou cada uma
contra o GHSA; 6 têm advisory (commons-compress 1.28.0, snappy-java
1.1.10.8, snakeyaml 2.6, protobuf-java 4.34.1, lz4-java, fory-core),
**todas patched** → veredito A. Eixo SCA validado. Categoria Java/Kotlin
8/10 → **9/10**, total **91 → 92/100**.

## O falso-positivo (e por que NÃO foi contado)

A primeira tentativa usou um regex guloso:
`<dependency>.*?<groupId>..<artifactId>..<version>..`. Em `re.DOTALL`,
o `.*?` **cruza fronteiras de `<dependency>`** e pareia o artefato de um
bloco com a `<version>` do bloco seguinte. Resultado inicial (errado):

| (falso) pacote | (falsa) versão | (falso) CVE |
|---|---|---|
| io.netty:netty-transport-native-kqueue | 1.1.1 | CVE-2026-45536 |
| org.assertj:assertj-core | 2.12.6 | CVE-2026-24400 |

Sinais de alarme que levaram à verificação:
1. **netty 1.1.1** é implausível — netty usa 4.1.x. Versão suspeita.
2. Inspeção do `pom.xml`: ambos os blocos têm `<scope>provided</scope>`
   ou `<scope>test</scope>` e **nenhum `<version>` inline** — são
   geridos pelo BOM/parent. As versões `1.1.1`/`2.12.6` pertenciam a
   blocos vizinhos (um plugin e o rxjava/assertj adjacente).

Correção: `parse_maven_pom` agora parseia **por bloco** e só aceita a
versão se ela está *dentro do mesmo `<dependency>`*. Com isso, os 2
fantasmas somem (sem versão inline → não escaneados, nunca chutados) e o
veredito real do redisson é **limpo**. Teste de regressão
`test_T77_parse_maven_pom_per_block_no_version_bleed` pina esse
comportamento.

## Princípio

Este é o segundo FP que a disciplina anti-fabricação barrou nesta sessão
(o primeiro foi o autofix-CodeQL do redisson, descartado em AT por não
ser CVE-anchored). A regra: **um sinal implausível dispara verificação
manual da fonte antes de virar dado**. Prefiro um parser mais restritivo
(que perde deps geridas por BOM) a um permissivo que inventa
vulnerabilidades. O M9.4 sempre falha em direção a "limpo/desconhecido",
nunca a "vulnerável por engano".

## Estado

Total **92/100**. Restam 8: #34 boto3 (N/A), #59 serde (sem CVE), #75
kotlin (sem coordenada Maven), #93 jekyll / #94 signal (sem versão
resolvida), #84 httpd / #85 wireshark (SVN/GitLab), #83 sqlite
(reservado p/ FP). Teto honesto da lista: **99/100** (sqlite fora por
reserva do usuário). Java/Kotlin agora 9/10 (só kotlin resta).

O motor M9.4 cobre 7 formatos de manifesto: composer-vendorizado,
packages.config, CPM MSBuild, Gradle build.versions.toml, Cargo.lock,
package-lock.json, e pom.xml (por-bloco). De 74 a 92/100 nesta sessão,
três motores, zero fabricação — com dois falso-positivos explicitamente
barrados.
