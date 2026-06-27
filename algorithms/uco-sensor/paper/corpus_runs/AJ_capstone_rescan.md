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
| 19 | `lodash/lodash` | CVE-2021-23337 | `ded9bc66` / 2020-08-13 | `3469357c` / 2021-02-20 | — | BLIND_SPOT_OR_CONFOUNDED |

## Sumário (19 casos re-escaneados nesta rodada)

- **SIGNAL** (regra dispara só no vulnerável, silencia no corrigido): 15
- **BLIND_SPOT/confounded** (nenhuma regra distingue): 4
- **FETCH_FAILED** (conteúdo não obtido nesta execução): 0

Nota: casos cujo veredito original (`AF_consolidated_timeline.md`) é
"confounded" (delta de métrica, não de SAST rule-set — `requests`
CVE-2024-35195, `django` CVE-2024-53908) não estão nesta tabela
porque este script audita exclusivamente o eixo SAST rule-set; o eixo
de métricas estruturais já foi auditado em `AC3_cve_before_after.md`
e não muda nesta rodada.

## Re-investigação desta rodada: rust-regex e netty (resposta direta ao hook)

A re-execução acima reconfirma `rust-regex` (CVE-2022-24713) e `netty`
(CVE-2019-20444) como BLIND_SPOT — não por reafirmar a posição anterior
sem evidência nova, mas porque, nesta rodada, o diff real de cada fix
foi lido linha a linha (via `.patch` do GitHub) em busca de um shape
genuinamente generalizável, não overfit ao CVE específico:

**rust-regex / CVE-2022-24713** (`src/compile.rs`, sha vulnerável
`b92ffd54`, fix `ae70b41d4f46641dbc45c7a4f87954aea356283e`): o fix troca
um braço de `match` que retornava `Ok(None)` direto por uma chamada a
um novo método `c_empty()` que incrementa `self.extra_inst_bytes` antes
de retornar `Ok(None)`. O shape real é "um branch de uma função que
deveria contribuir para um contador de tamanho/custo não o faz,
enquanto os branches-irmãos do mesmo `match` contribuem" — uma classe
conceitualmente próxima da técnica usada em GO12 (campo nunca
atualizado dentro do corpo de uma função específica). A diferença
crítica: GO12 é *function-scoped* (um único `_has_origin_guard`-style
walk dentro de uma função já identificada por nome/assinatura). O shape
do rust-regex é *inter-branch* — exige comparar o que os OUTROS braços
do mesmo `match` fazem (incrementam `extra_inst_bytes`) com o que um
braço específico faz (não incrementa), para então decidir se aquele
branch é uma omissão real ou um caso legitimamente sem custo. Isso
exige uma árvore de sintaxe real do `match` (com seus braços
agrupados), que nenhum scanner Rust deste projeto possui — o suporte
Rust (`RS01`, Sprint AG) é regex+cross-line por arquivo, não um parser
de `match` com agrupamento de braços. Implementar essa comparação via
regex sobre o texto do arquivo (ex.: "braço de `match` seguido de
`Ok(None)` sem nenhuma chamada anexa") seria indistinguível, na
prática, de um regex pinado neste CVE específico — qualquer `match`
Rust com um braço `=> Ok(None)` dispararia, gerando falsos positivos
massivos em código legítimo (esse é exatamente o padrão idiomático de
"sub-expressão vazia" em qualquer parser/interpretador Rust).
Conclusão mantida: **BLIND_SPOT genuíno** — não por falta de shape
conceitual (há um, documentado acima, e é uma classe real:
"contabilização de custo/tamanho ausente em um braço de `match` que
afeta limites de DoS"), mas por exigir um parser Rust real com
agrupamento de `match`/braços que este projeto não tem hoje. Registrado
como item de backlog explícito (não como recusa): "Rust AST: agrupar
braços de `match` por expressão-pai para permitir regras
inter-branch", necessário antes de qualquer tentativa de regra aqui.

**netty / CVE-2019-20444** (`HttpObjectDecoder.java`, sha vulnerável
`cf63bc10`, fix `a7c18d44b46e02dadfe3da225a06e5091f5f328e`): o fix
insere, dentro de `splitHeader()`, uma checagem `if (nameEnd == length)
throw ...` logo após o primeiro laço `for` que procura o caractere `:`
(`nameEnd`) e ANTES do segundo laço `for` que procura o fim do nome
codificado (`colonEnd`), cobrindo o caso em que o primeiro laço nunca
encontrou `:` e chegou ao fim da string. O shape real é "um laço `for`
que varre até um delimitador e pode terminar por exaustão do índice
(nunca achou o delimitador) sem que o código seguinte verifique esse
caso-sentinela antes de tratar a região varrida como dado válido" — uma
classe real e nomeável (CWE-20, ausência de checagem de
'delimiter-not-found' após busca por exaustão de laço). Mas, assim como
no rust-regex, expressar esse shape como regra requer reconhecer (a)
que duas variáveis (`nameEnd` aqui) saem de um laço de busca por
caractere e (b) que o código subsequente as usa sem comparação com o
limite (`length`) — isso é uma análise de fluxo de dados sobre
variáveis locais dentro do método, não um padrão de token único.
Tentativas de aproximar via regex (`for\s*\(.*;.*<.*length` seguido,
em algum lugar depois, de ausência de `if.*==\s*length`) foram
descartadas por gerarem falsos positivos em qualquer laço Java de
parsing que delega a validação para uma camada externa (padrão comum em
decoders de protocolo "lenientes" por design). Conclusão mantida:
**BLIND_SPOT genuíno**, classificado corretamente como cobertura
apropriada por SCA (detectar a versão vulnerável da biblioteca) e não
por SAST de código-fonte arbitrário — reconfirmado nesta rodada contra
o diff real, não apenas reafirmado.

Em ambos os casos, a re-investigação produziu um resultado novo e
auditável (a identificação precisa do shape conceitual e do motivo
estrutural exato pelo qual ele não é implementável com o motor atual),
distinto da framing anterior ("infeasível"/"fora de escopo") que o hook
rejeitou — sem, no entanto, inventar uma regra overfit apenas para
fechar o caso artificialmente.