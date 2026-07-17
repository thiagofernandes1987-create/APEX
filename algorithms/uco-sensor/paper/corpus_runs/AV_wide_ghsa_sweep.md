# Sprint AV — rede ampla GHSA→AST fecha cpython/kafka/ceph (82→85/100)

> Continuação de AU. Em vez de 1 CVE por repo, lançamos uma **rede
> ampla**: vários CVEs candidatos por repo restante, resolvidos pelo
> GHSA (M9.3) e confirmados pelo diff AST (M9.2) na grammar do arquivo
> corrigido.

## Resultado da rede de resolução

Testados 9 repos restantes × 2-4 CVEs cada. Resolveram com `/commit/`
no GHSA:

| Repo | CVE | fix-commit |
|---|---|---|
| ceph | CVE-2021-3979 | 47c33179f9a1 |
| kafka | CVE-2022-34917 | 14951a83e3fd |
| cpython | CVE-2024-0397 | 01c37f1d0714 |
| cpython | CVE-2024-6232 | 4eaf4891c125 |
| cpython | CVE-2024-9287 | e52095a0c100 |

Não resolveram (GHSA sem `/commit/` próprio): httpd, wireshark,
clickhouse, kotlin, serde, elasticsearch, e os 5 PHP/Ruby/C#/Mobile.

## Confirmação por diff AST

| # | Repo | CVE | arquivo | grammar | churn |
|---|------|-----|---------|---------|-------|
| #21 | cpython | CVE-2024-6232 (ReDoS em tarfile) | tarfile.py | python | 196 |
| #21 | cpython | CVE-2024-0397 (race em ssl) | _ssl.c | C | 356 |
| #21 | cpython | CVE-2024-9287 (venv quoting) | __init__.py | python | 162 |
| #70 | kafka | CVE-2022-34917 (OOM no parsing) | DataInputStreamReadable.java | java | 71 |
| #98 | ceph | CVE-2021-3979 (perda de criptografia) | encryption.py | python | 105 |

cpython resolveu por **três** CVEs independentes (uma em C, duas em
Python) — robustez do dado, não um único acerto sortudo.

## Destaques metodológicos

1. **#98 ceph — dois eixos se complementam.** O eixo SCA era N/A (o
   único pom.xml usa `${version}` não resolvido). Mas o fix da
   CVE-2021-3979 está em `src/pybind/mgr/.../encryption.py` — Python. O
   eixo SAST AST-anchored fecha o repo. Um "repo de infra C++" coberto
   pela sua correção em Python.

2. **Motor multilíngue rende.** cpython mistura C e Python no mesmo
   commit-set; o motor cobre ambos. Sem o M9.2 multilíngue, metade desses
   fixes seria invisível.

## Cobertura

- Python 18/20 → **19/20** (só #34 boto3 N/A resta).
- Java/Kotlin 7/10 → **8/10**.
- Infra 3/5 → **4/5** (só #100 clickhouse resta).
- **Total: 82 → 85/100.**

## Os 15 restantes — diagnóstico honesto por que cada um resiste

| Gap | Categoria | Por que sem eixo |
|---|---|---|
| boto3 | Python | requirements.txt só com `-e git+`, sem lockfile; sem CVE |
| serde | Rust | lib sem CVE/RUSTSEC de memory-safety indexada |
| elasticsearch | Java | GHSA sem `/commit/`; fix via release |
| redisson | Java | só autofix CodeQL sem CVE |
| kotlin | Kotlin | sem grammar tree-sitter instalável testada |
| 5× PHP/Ruby/C#/Mobile | — | sem lockfile (SCA) e GHSA sem `/commit/` (SAST) |
| clickhouse | Infra | sem lockfile; sem fix-commit resolvível |
| sqlite | C/C++ | **reservado para teste de FP** (constraint do usuário) |
| httpd, wireshark | C/C++ | SVN/GitLab; GHSA sem `/commit/` no mirror GitHub |

Esses 15 não cedem ao pipeline GHSA→AST porque o **fix-commit não é
resolvível** por fonte curada (não é limitação do motor de análise, e
sim da disponibilidade do dado de patch). Próximas avenidas reais: (a)
seguir links de **PR** (`/pull/N` → merge-commit) no resolver para
elasticsearch/kafka-style; (b) **SCA por similaridade de função**
(V1SCAN/CENTRIS) para os 5 PHP/Ruby/C#/Mobile; (c) grammar
tree-sitter-kotlin para o #75. O `sqlite` permanece intencionalmente
fora (reserva do usuário).
