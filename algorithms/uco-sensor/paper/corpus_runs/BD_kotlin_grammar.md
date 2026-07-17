# Sprint BD — fecha kotlin via grammar tree-sitter-kotlin (#75); categoria Java/Kotlin 10/10

> Fecha o último gap de Java/Kotlin estendendo o motor AST (M9.2) a uma
> 7ª gramática. O kotlin tinha sido adiado em AZ (versions.properties sem
> coordenada Maven); aqui é fechado pelo **outro** eixo — SAST.

## Por que SAST, não SCA

Em AZ, `gradle/versions.properties` do kotlin usa nomes curtos
(`versions.gson=2.11.0`) sem o group:artifact Maven — adiado por risco de
FP. Em vez de forçar o SCA, fechamos pelo eixo SAST CVE-anchored, que só
faltava a gramática tree-sitter de Kotlin.

## #75 kotlin — FECHADO (SAST AST-anchored)

`tree-sitter-kotlin` (pip) instalada e adicionada ao `tree_sitter_bridge`
(`_GRAMMARS["kotlin"]`). O motor AST (M9.2) cobre agora 7 linguagens.

Fix de segurança real localizado via commit-search: `f8c587dd` — "Fix
security vulnerability in Path recursive functions **#KT-63103**",
arquivo `libraries/stdlib/jdk7/src/kotlin/io/path/PathRecursiveFunctions.kt`
(+100-8) e `PathTreeWalk.kt`. KT-63103 é a vulnerabilidade de
**symlink-following** em `Path.deleteRecursively()` / `copyRecursively()`
da stdlib do Kotlin (a função seguia symlinks, permitindo apagar/copiar
fora da árvore alvo). Diff AST kotlin:

| arquivo | nodes antes/depois | churn |
|---|---|---|
| PathRecursiveFunctions.kt | 2470 → 2992 | **526** |

churn=526 — sinal forte; o fix adicionou checagem de symlink + lógica de
travessia (novos `call_expression`, `navigation_expression`, args).

### Distinção da disciplina

Este é um fix de produção **rotulado de segurança pelo próprio
mantenedor** (commit message "Fix security vulnerability", tracker
KT-63103), tocando código real da stdlib (+100 linhas). É qualitativamente
diferente do "Copilot Autofix" de alerta CodeQL do redisson (1 linha, sem
CVE, sem rótulo de mantenedor) que rejeitei em AT. A regra: conta um fix
de segurança real, autorado e rotulado; não conta um autofix automático
sem CVE/rótulo.

## Resultado

Categoria Java/Kotlin (66-75) **9/10 → 10/10 — fechada**. Total **93 →
94/100**. **Quatro categorias fechadas:** JS/TS (20/20), Go (15/15),
Java/Kotlin (10/10), Infra (5/5).

## Restam 6/100

| Gap | Bloqueio |
|---|---|
| #34 boto3 | requirements só `-e git+`, sem versão |
| #59 serde | sem CVE/RUSTSEC de memory-safety |
| #93 jekyll | gemspec só com ranges, sem Gemfile.lock; único "fix" é bump de gemspec (não código) |
| #84 httpd | SVN, GHSA sem /commit/ |
| #85 wireshark | GitLab, GHSA sem /commit/ |
| #83 sqlite | **reservado para teste de FP (constraint do usuário)** |

Teto honesto da lista: **99/100** (sqlite fora por reserva). Dos 5
não-reservados, cada um tem bloqueio de dado real:
- boto3/serde: sem versão resolvida / sem CVE.
- jekyll: o único commit de fix encontrado (CVE-2021-28834) altera só
  `jekyll.gemspec` (+1-1, bump de dependência) — não há diff de código
  Ruby de produção para o eixo AST, e não há lockfile para o eixo SCA.
- httpd/wireshark: fix em SVN/GitLab, não no mirror GitHub; GHSA sem
  link de commit.

De 74 a 94/100 nesta sessão, com três motores (M9.2 cobrindo 7
linguagens / M9.3 / M9.4 cobrindo 8 formatos de manifesto), true-positives
verificados, dois falso-positivos barrados, e uma auditoria de contagem —
zero fabricação.
