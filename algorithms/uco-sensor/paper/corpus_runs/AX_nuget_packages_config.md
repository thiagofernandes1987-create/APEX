# Sprint AX — M9.4 aplicado a packages.config NuGet; fecha shadowsocks-windows (#95)

> Continuação de AW. Ao ampliar o registry de marcadores de manifesto do
> motor M9.4, descobrimos que dois dos repos antes marcados "sem
> lockfile" na verdade expõem versões resolvidas — só num formato que os
> code-searches de AO não procuraram.

## A lacuna nos code-searches de AO

Sprint AO confirmou "sem lockfile" buscando `composer.lock`,
`Gemfile.lock`, `gradle.lockfile`, `packages.lock.json`. Mas o NuGet
**old-style** usa `packages.config` — um XML que pina versões exatas
(`<package id="X" version="Y.Z" />`). Para fins de SCA, isso é
equivalente a um lockfile: versões resolvidas, escaneáveis.

## #95 shadowsocks-windows — FECHADO (A, limpo)

`shadowsocks-csharp/packages.config` (o projeto principal) declara **35
pacotes NuGet** com versão fixa. M9.4 checou cada um por contenção de
range contra advisories GHSA (ecosystem `nuget`):

| Pacote (com advisories GHSA) | versão | advisories | veredito |
|---|---|---|---|
| Newtonsoft.Json | 13.0.3 | 2 | limpo (CVEs afetam <13.0.1) |
| Google.Protobuf | 3.27.2 | 2 | limpo |
| System.Net.Http | 4.3.4 | 5 | limpo (afetam <4.3.4) |
| System.Security.Cryptography.X509Certificates | 4.3.2 | 1 | limpo |
| + 31 pacotes sem advisory | — | 0 | limpo |

Veredito agregado: **A — limpo**. Os 4 pacotes com CVE conhecida estão
todos em versão já corrigida (range-matching confirma). Eixo SCA
validado. Categoria PHP/Ruby/C#/Mobile 6/10 → **7/10**, total **86 →
87/100**.

## #89 roslyn — near-miss honesto (adiado, não forçado)

roslyn usa **Central Package Management**: `Directory.Packages.props`
lista pacotes mas com versão indireta `Version="$(FooVersion)"`, onde
`$(FooVersion)` é definido em `eng/Versions.props`. É resolvível
seguindo a indireção de propriedades MSBuild — mas a resolução robusta
(há herança e condicionais MSBuild) merece lógica dedicada, não um regex
apressado que arriscaria versão errada → FP. **Adiado** conscientemente,
registrado como avenida concreta para uma sprint futura.

jekyll (#93): só `jekyll.gemspec` com ranges de versão (não pinado) e
sem `Gemfile.lock` — sem versão resolvida para SCA. signal-android
(#94): sem lockfile gradle. Ambos seguem gaps honestos.

## Resultado

Total **86 → 87/100**. O motor M9.4 agora cobre `composer` (libs
vendorizadas com VERSION) e `nuget` (`packages.config`). Restam 13/100.
A próxima avenida de menor esforço é a resolução de Central Package
Management para fechar o roslyn (#89). De 74 a 87 nesta sessão, com três
motores e zero fabricação.
