# Sprint AT — resolver GHSA de fix-commit (M9.3); fecha spring-boot (#66)

> Operacionaliza o ANGLE 3 da deep research (Sprint AR): localizar o
> commit de correção real a partir do banco de vulnerabilidades, em vez
> de adivinhá-lo por busca de mensagem de commit. Ataca o bloqueio **B3**
> (descoberta de fix-commit), distinto de B1 (sensibilidade do motor, já
> resolvido em AR/AS).

## O problema B3, precisamente

A busca por mensagem de commit (`<CVE-ID> repo:owner/name`) só funciona
quando o projeto cita o CVE na mensagem. Confirmado nesta sessão que
**falha** para vários repos Java GitHub-nativos:

| Repo | CVE testado | commit-search |
|---|---|---|
| spring-boot | CVE-2023-20883 | 0 resultados |
| kafka | CVE-2023-25194 | 0 resultados |
| elasticsearch | CVE-2024-23450 | 0 resultados |

## A solução: `references` do GHSA

O GitHub Advisory (`api.github.com/advisories?cve_id=...`, endpoint
permitido pelo proxy — `api.osv.dev` está bloqueado, mas o GHSA carrega
o mesmo dado upstream do OSV) traz uma lista `references` que muitas
vezes contém o `/commit/<sha>` direto:

| CVE | GHSA | tem `/commit/` no repo-alvo? |
|---|---|---|
| **CVE-2023-20883** (spring-boot) | GHSA-xf96-w227-r7c4 | **SIM** → `418dd1ba...` |
| CVE-2023-25194 (kafka) | GHSA-26f8-x7cc-wqpc | não |
| CVE-2024-31141 (kafka) | GHSA-2x2g-32r7-p4x8 | não |
| CVE-2024-23450 (elasticsearch) | GHSA-w5gg-2q56-6h4f | não |
| CVE-2022-1471 (snakeyaml) | GHSA-mjmj-j48q-9wg2 | sim (bitbucket — dep) |

Ou seja: o resolver fecha o subconjunto onde o GHSA curou o link do
commit. Não é bala de prata (kafka/elasticsearch ainda exigiriam crawl
de PR ou release-diff), mas é o de menor esforço e já fecha spring-boot.

## Módulo M9.3 — `sast/ghsa_fix_resolver.py`

- `extract_fix_commits(advisory, repo=...)`: parsing puro (regex
  `github.com/<repo>/commits?/<sha>`), filtra por repo-alvo (descarta
  fix-links de dependências, como o bitbucket do snakeyaml acima), dedup,
  tolera os dois shapes de `references` (REST list[str] e OSV
  list[{"url"}]). Nunca levanta.
- `GHSAFixResolver`: front-end de rede com modo offline gracioso
  (`available()` falso sem token/fetcher → `resolve` devolve `None`) e
  `fetcher` injetável para teste sem rede.
- 9 testes (TX76) contra payload GHSA **real** de CVE-2023-20883.

## #66 spring-boot — FECHADO

CVE-2023-20883 (DoS via welcome-page handler). Fix-commit `418dd1ba...`
resolvido pelo GHSA, pai `cc2bb7cade62`. Diff AST Java
(`WebMvcAutoConfiguration.java`): nodes 6079→6257, **churn=180**
(`formal_parameter`+11, `type_identifier`+20). Eixo SAST CVE-anchored
legítimo, com o fix-commit localizado por fonte de dados (GHSA), não por
adivinhação.

## Disciplina mantida (o que NÃO foi contado)

O redisson (#73) tem um commit "Potential fix for code scanning alert
no. 13" (Copilot Autofix, comparação de tipo estreito, 1 linha). É um
fix de segurança real e o motor AST o detectaria — **mas não tem CVE
associado** (0 advisories no repo). Contá-lo diluiria o critério
"CVE-anchored". Foi explicitamente descartado.

## Resultado

Java/Kotlin **6/10 → 7/10**. Total **76 → 77/100**. Restam 23/100.
O resolver GHSA (M9.3) agora é infraestrutura reutilizável para todas as
futuras tentativas de localizar fix-commit — combina com o motor AST
(M9.2) para formar o pipeline "resolve-commit → diff-AST" em qualquer
das 6 linguagens já cobertas.
