# Sprint AW — terceiro motor: SCA de dependência vendorizada (M9.4); fecha wordpress (#91)

> Implementa o ANGLE 2 da deep research (SCA source-tree sem lockfile)
> na variante de **baixo falso-positivo**, fechando o bloqueio B2 para
> repos que vendorizam libs com versão declarada.

## O dilema do ANGLE 2 e a escolha de design

A deep research apontou V1SCAN/CENTRIS (similaridade de função) para SCA
sem manifesto. Mas o próprio V1SCAN documenta que detecção por versão
ingênua dá **~71% de falso-positivo** antes da classificação de código —
porque projetos bem mantidos *corrigem* suas cópias vendorizadas.
Confirmamos isso empiricamente: as libs do WordPress têm CVEs associadas,
mas todas em versões **anteriores** à vendorizada.

Em vez de construir o classificador de código completo (caro, e ainda
assim com FP residual), adotamos a fatia limpa: **bibliotecas
vendorizadas declaram a própria versão exata no fonte** (ex.: WordPress
embute `rmccue/requests` com uma constante `VERSION`). Isso permite SCA
correto por **contenção de range** — reportando LIMPO quando já corrigido.

## Por que um veredito limpo conta

No corpus, um scan SCA limpo já é eixo validado: `#13 three.js SCA (A,
limpo)`, `#25 pytorch SCA (A, limpo)`, etc. O valor do eixo é o tool
produzir um veredito real sobre uma versão resolvida real — não o repo
ser necessariamente vulnerável. Logo, um veredito honesto sobre as libs
vendorizadas do WordPress fecha o repo, **sem inventar vulnerabilidade**.

## Motor M9.4 — `sca/vendored_scanner.py`

- `version_in_range(ver, range)`: implementa a gramática de comparadores
  do GitHub advisory (`>= 1.6.0, < 1.8.0`, `< 1.8.0`, `= 2.0.1`, `<= 3.4`).
  Fail-safe: range vazio/não-parseável **nunca** flagra.
- `verdict_for(ver, advisories, package)`: puro; só conta hit quando a
  versão cai dentro do range *daquele pacote* (range-matching correto).
  Rating A (limpo) … E, espelhando o eixo SCA de manifesto.
- `VendoredScanner`: front-end de rede (GHSA por ecosystem+package,
  endpoint permitido) com modo offline gracioso e fetcher injetável.
- 18 testes (TX77) contra advisory GHSA **real** de `rmccue/requests`.

## #91 WordPress — FECHADO (veredito A, limpo)

Sem `composer.lock` em lugar nenhum (confirmado em AO). Libs vendorizadas
com versão declarada, checadas por range contra advisories GHSA reais:

| Lib vendorizada | versão (do fonte) | advisories GHSA | veredito |
|---|---|---|---|
| `rmccue/requests` | 2.0.17 | 1 (CVE-2021-29476, range `>=1.6.0,<1.8.0`) | **limpo** (2.0.17 fora) |
| `phpmailer/phpmailer` | 7.0.2 | 14 (CVEs 2006-2021, todas ≤6.x) | **limpo** (7.0.2 fora) |

Veredito agregado: **A — limpo**. Eixo SCA validado. Categoria
PHP/Ruby/C#/Mobile 5/10 → **6/10**. Total **85 → 86/100**.

## Os três motores agora compõem

| Motor | Bloqueio (deep research) | Fecha |
|---|---|---|
| M9.2 diff AST | B1 (sensibilidade a fix de 1 linha) | php-src, diesel, +Python/Java/C |
| M9.3 resolver GHSA | B3 (descoberta do fix-commit) | spring-boot, cpython, kafka, ceph, 5×Python |
| **M9.4 SCA vendorizado** | **B2 (SCA sem manifesto)** | **wordpress** |

## Gaps remanescentes (14) e por que resistem

- **roslyn, jekyll, signal-android, shadowsocks-windows** (#89, 93, 94,
  95): sem lockfile, sem fix-commit GHSA, e **sem lib vendorizada com
  versão declarada detectada** — o M9.4 precisa de um marcador de versão
  no fonte; estes não o expõem de forma óbvia. Próxima avenida: ampliar o
  registry de marcadores de vendor (ex.: `.csproj`/`packages.config`
  embutidos, gems vendorizadas com `.gemspec`).
- **elasticsearch, redisson, kotlin, clickhouse, serde, boto3, httpd,
  wireshark, sqlite(reservado)**: como em AV — patch não resolvível por
  fonte curada, ou reservado.

De 74 a 86/100 nesta sessão, com **três motores novos** (M9.2/M9.3/M9.4)
e zero fabricação. Cada repo fechado tem evidência verificável: fix-commit
real + churn AST, ou veredito SCA por range sobre versão resolvida real.
