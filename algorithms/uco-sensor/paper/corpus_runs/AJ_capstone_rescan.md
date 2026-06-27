# AJ — Capstone Re-scan: todos os históricos de commit re-executados em rodada única

Gerado por `paper/capstone_rescan.py`, em resposta direta ao pedido
literal do `/goal`: re-escanear todos os históricos de commit
documentados, em todos os repositórios, em uma única passada, e
consolidar quando o problema existiu, em qual commit, e quando foi
resolvido — não como edições incrementais linha-a-linha do relatório
anterior (`AF_consolidated_timeline.md`), mas como uma re-execução
completa e fresca contra o conteúdo real do GitHub.

| # | Repo | CVE/GHSA | Vulnerável (sha/data) | Corrigido (sha/data) | Findings só-no-vulnerável | Veredito desta rodada |
|---|---|---|---|---|---|---|
| 1 | `psf/requests` | CVE-2024-47081 | `7341690e` / 2025-06-01 | `96ba401c` / 2025-06-04 | SAST046 | SIGNAL |
| 2 | `psf/requests` | CVE-2023-32681 | `30222533` / 2023-05-15 | `74ea7cf7` / 2023-05-22 | SAST047 | SIGNAL |
| 3 | `scrapy/scrapy` | CVE-2022-0577 | `aa0306a1` / 2022-03-01 | `8ce01b3b` / 2022-03-01 | SAST050 | SIGNAL |
| 4 | `pallets/flask` | CVE-2023-30861 | `9532cba4` / 2023-05-01 | `8705dd39` / 2023-05-01 | SAST051 | SIGNAL |
| 5 | `celery/celery` | CVE-2021-23727 | `2d8dbc2a` / 2021-12-26 | `1f7ad7e6` / 2021-12-26 | SAST048 | SIGNAL |
| 6 | `tiangolo/fastapi` | CVE-2021-32677 | `90120dd6` / 2021-06-07 | `fa7e3c99` / 2021-06-07 | SAST049 | SIGNAL |
| 7 | `curl/curl` | CVE-2023-38545 | `09e25b9d` / 2023-10-10 | `fb4415d8` / 2023-10-11 | C01 | SIGNAL |
| 8 | `golang/go` | CVE-2023-29404 | `6d8af00a` / 2023-06-06 | `bbeb55f5` / 2023-06-06 | GO11 | SIGNAL |
| 9 | `axios/axios` | CVE-2023-45857 | `7d45ab2e` / 2023-10-22 | `96ee232b` / 2023-10-26 | JS11 | SIGNAL |
| 10 | `spring-projects/spring-framework` | CVE-2022-22965 | `1627f57f` / 2022-03-31 | `002546b3` / 2022-03-31 | JV11 | SIGNAL |
| 11 | `rust-lang/regex` | CVE-2022-24713 | `b92ffd54` / 2022-03-03 | `ae70b41d` / 2022-03-03 | — | BLIND_SPOT_OR_CONFOUNDED |
| 12 | `etcd-io/etcd` | CVE-2021-28235 | `801bb4c6` / 2023-04-06 | `8b1cd036` / 2023-04-06 | GO12 | SIGNAL |
| 13 | `tokio-rs/tokio` | CVE-2023-22466 | `5c76d070` / 2022-09-27 | `9241c3ed` / 2023-01-03 | RS01 | SIGNAL |
| 14 | `netty/netty` | CVE-2019-20444 | `cf63bc10` / 2019-12-11 | `a7c18d44` / 2019-12-11 | — | BLIND_SPOT_OR_CONFOUNDED |
| 15 | `laravel/framework` | GHSA-crmm-hgp2-wgrp | `071ac5c3` / 2026-05-14 | `cba82e4e` / 2026-05-15 | PHP05 | SIGNAL |
| 16 | `rails/rails` | CVE-2024-26143 | `723f5456` / 2024-02-21 | `4c83b331` / 2024-02-21 | — | BLIND_SPOT_OR_CONFOUNDED |
| 17 | `dotnet/runtime` | CVE-2026-45491 | `b06f62fc` / 2026-06-24 | `8c91e3b2` / 2026-06-26 | CS06 | SIGNAL |
| 18 | `git/git` | CVE-2021-21300 | `0d58fef5` / 2021-02-12 | `22539ec3` / 2021-02-12 | C05 | SIGNAL |
| 19 | `lodash/lodash` | CVE-2021-23337 | `ded9bc66` / 2020-08-13 | `3469357c` / 2021-02-20 | JS12 | SIGNAL |

## Sumário (19 casos re-escaneados nesta rodada)

- **SIGNAL** (regra dispara só no vulnerável, silencia no corrigido): 16
- **BLIND_SPOT/confounded** (nenhuma regra distingue): 3
- **FETCH_FAILED** (conteúdo não obtido nesta execução): 0

Nota: casos cujo veredito original (`AF_consolidated_timeline.md`) é
"confounded" (delta de métrica, não de SAST rule-set — `requests`
CVE-2024-35195, `django` CVE-2024-53908) não estão nesta tabela
porque este script audita exclusivamente o eixo SAST rule-set; o eixo
de métricas estruturais já foi auditado em `AC3_cve_before_after.md`
e não muda nesta rodada.