# Sprint AU — pipeline GHSA→AST fecha 5 repos Python (77→82/100)

> Primeira aplicação em lote do pipeline construído nas três sprints
> anteriores: **resolve-commit (M9.3, resolver GHSA) → diff-AST (M9.2,
> tree-sitter)**. Alvo: os gaps da categoria Python (21-40), que estava
> 13/20.

## Identificação dos gaps Python

Cobertos antes (13): #22, 24, 25, 26, 27, 28, 30, 31, 32, 35, 37, 38, 40.
Faltavam (7 slots): #21 cpython, #23 scikit-learn, #29 transformers,
#33 scipy, #34 boto3 (já N/A), #36 salt, #39 sqlalchemy.

## Método (sem adivinhação de commit)

Para cada repo, rodamos `GHSAFixResolver.resolve(cve, repo=...)` —
que lê as `references` do GitHub Advisory e extrai o `/commit/<sha>` do
repo-alvo. Quando resolvido, buscamos o arquivo antes/depois e rodamos
`ASTStructuralDiff.diff` na gramática apropriada.

Resultado da resolução GHSA:

| Repo | CVE | resolveu fix-commit? |
|---|---|---|
| cpython | CVE-2023-24329, CVE-2022-45061 | **não** (GHSA sem `/commit/`) |
| scikit-learn | CVE-2024-5206 | sim → `70ca21f1` |
| transformers | CVE-2023-6730 | sim → `1d63b0ec` |
| scipy | CVE-2023-25399 | sim → `9b652119` |
| salt | CVE-2024-22232 | sim → `e0cdb80b` |
| sqlalchemy | CVE-2019-7164 | sim → `30307c46` |

## Confirmação por diff AST (churn não-nulo)

| # | Repo | CVE | arquivo | grammar | churn | sec-ops |
|---|------|-----|---------|---------|-------|---------|
| #23 | scikit-learn | CVE-2024-5206 (vazamento de dado sensível no TfidfVectorizer) | text.py | python | 28 | — |
| #29 | transformers | CVE-2023-6730 (deserialização insegura) | tokenization_transfo_xl.py | python | 117 | if+2 |
| #33 | scipy | CVE-2023-25399 (buffer em ndimage) | nd_image.c | **C** | 7 | — |
| #36 | salt | CVE-2024-22232 (path traversal em roots) | roots.py | python | 213 | `==`+1, if+6 |
| #39 | sqlalchemy | CVE-2019-7164 (SQL injection via order_by) | elements.py | python | 188 | ternário+1 |

Destaque: o scipy tem o fix num arquivo **C** (`nd_image.c`) — coberto
porque o motor M9.2 já suporta C. Mostra o valor de ter o motor
multilíngue: um "repo Python" cujo fix está na extensão nativa ainda é
analisável.

## #21 cpython — gap honesto remanescente

As CVEs do cpython testadas (CVE-2023-24329 urllib bypass,
CVE-2022-45061 IDNA DoS) não trazem `/commit/` nas `references` do GHSA
(o fix do cpython entra via bpo/gh-issue + backports, sem link direto de
commit no advisory). Permanece sem eixo — não forçado. #34 boto3 segue
N/A (sem lockfile real).

## Resultado

Categoria Python **13/20 → 18/20**. Total da lista master **77 → 82/100**
— maior salto desde a introdução do segundo eixo (SCA). Cinco repos
fechados com fix-commit de fonte curada (GHSA) e churn AST mensurável,
zero fabricação. Restam 18/100, com o pipeline GHSA→AST agora provado
em escala e reutilizável para qualquer dos demais gaps que tenham
advisory com link de commit.
