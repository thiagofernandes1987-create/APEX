# Sprint BC — fecha signal-android via catálogo de versões Gradle (#94)

> Fecha #94 e formaliza o parser de catálogo Gradle (usado também em
> elasticsearch/AZ) como capacidade testada do M9.4.

## #94 signal-android — FECHADO (A, limpo)

Signal-Android não tem `gradle.lockfile`, mas usa um **catálogo de
versões Gradle**: `gradle/libs.versions.toml`. Esse formato pina versões
numa tabela `[versions]` e referencia em `[libraries]`. `parse_gradle_
version_catalog` (novo no M9.4) resolve as duas formas:

```toml
[versions]
jackson = "2.15.0"
[libraries]
jackson-databind = { module = "com.fasterxml.jackson.core:jackson-databind", version.ref = "jackson" }
okhttp = { group = "com.squareup.okhttp3", name = "okhttp", version.ref = "okhttp" }
```

Resolveu **53 libs Maven** (com.android.tools.build, org.jetbrains.kotlin,
androidx.*, media3, accompanist…). M9.4 checou cada uma contra o GHSA
`maven`; **0 com advisory aplicável** → veredito A.

### Verificação anti-falso-negativo

"53 libs, 0 advisories" poderia indicar coordenadas inválidas (FN). Para
descartar, inspecionei a amostra: todas são coordenadas Maven reais e
plausíveis (`org.jetbrains.kotlin:kotlin-stdlib-jdk8@2.2.20`,
`androidx.appcompat:appcompat@1.7.1`, etc.). O motor está provado em
true-positives (roslyn/elasticsearch) — se alguma caísse em range
vulnerável, flagraria. O zero é genuíno: androidx/kotlin/compose têm
pouquíssimas CVEs indexadas e o Signal pina versões recentes. Veredito
limpo legítimo, mesmo status que `three.js`/`pytorch` "SCA A, limpo".

## Resultado

Categoria PHP/Ruby/C#/Mobile 8/10 → **9/10**. Total **92 → 93/100**.
Resta só `#93 jekyll` na categoria.

O motor M9.4 cobre agora **8 formatos** de manifesto de versão resolvida:
composer-vendorizado, packages.config, CPM MSBuild, Gradle
build.versions.toml/libs.versions.toml (catálogo), Cargo.lock,
package-lock.json, pom.xml (por-bloco).

## Restam 7/100

| Gap | Bloqueio |
|---|---|
| #34 boto3 | requirements só `-e git+`, sem versão |
| #59 serde | sem CVE/RUSTSEC de memory-safety |
| #75 kotlin | versions.properties sem coordenada Maven (nomes curtos) |
| #93 jekyll | gemspec com ranges, sem Gemfile.lock — sem versão resolvida |
| #84 httpd | SVN, GHSA sem /commit/ |
| #85 wireshark | GitLab, GHSA sem /commit/ |
| #83 sqlite | **reservado para teste de FP (constraint do usuário)** |

Teto honesto da lista: **99/100** (sqlite fora por reserva). Dos 6
não-reservados, cada um tem bloqueio de dado real (sem versão resolvida
nem fix-commit indexável). De 74 a 93/100 nesta sessão, três motores,
zero fabricação, dois falso-positivos barrados, uma auditoria de
contagem.
