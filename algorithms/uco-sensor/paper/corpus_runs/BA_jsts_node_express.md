# Sprint BA — fecha os 2 gaps de JS/TS (node + express); categoria 20/20

> Fecha os 2 gaps de JS/TS que a auditoria de AZ tinha exposto (#4 node,
> #12 express), fechando a categoria. Aplica o pipeline já existente a
> formatos de manifesto/CVE que esses repos expõem.

## #4 nodejs/node — FECHADO (A, limpo)

O root do `nodejs/node` não tem lockfile, mas as ferramentas de build
têm: `tools/lint-md/package-lock.json` é um lockfile npm v3 real,
resolvendo **155 pacotes**. `parse_package_lock` (novo no M9.4) extrai
cada `node_modules/<name>@version`; 6 têm advisory no GHSA `npm`, **todos
patched** → veredito A. Eixo SCA validado (como qualquer SCA limpo do
corpus).

## #12 expressjs/express — FECHADO (SAST AST-anchored)

`express` é biblioteca: ship `package.json` com ranges, **sem
`package-lock.json`** committado — então o eixo SCA não se aplica. Via
SAST CVE-anchored: o resolver GHSA (M9.3) localizou o fix-commit de
`CVE-2024-29041` (open redirect em `res.location` — o `Location` header
não sanitizava a URL), commit `0867302d`. Diff AST JS (M9.2) em
`lib/response.js`:

| CVE | arquivo | churn | sec-ops |
|---|---|---|---|
| CVE-2024-29041 | lib/response.js | **171** | `if`+2, `||`+1, binary_expr+4, paren+2 |
| CVE-2024-43796 | lib/response.js | 9 | (validação cruzada) |

churn=171 é sinal forte — o fix adicionou normalização/validação de URL
(novos `if`, `||`, expressões). Dado SAST CVE-anchored legítimo, com
fix-commit de fonte curada (GHSA).

## Resultado

Categoria JS/TS (1-20) **18/20 → 20/20 — fechada**. Total **89 →
91/100**. Quatro categorias fechadas: JS/TS, Go (15/15), Infra (5/5); e
Python 19/20 só com #34 boto3 N/A.

O motor M9.4 cobre agora **6 formatos** de manifesto resolvido:
composer-vendorizado, NuGet packages.config, NuGet CPM, Gradle
build.versions.toml, Rust Cargo.lock, npm package-lock.json.

## Restam 9/100

| Gap | Bloqueio |
|---|---|
| #34 boto3 | requirements.txt só `-e git+`, sem versão |
| #59 serde | sem CVE/RUSTSEC de memory-safety |
| #73 redisson | só autofix CodeQL, sem CVE |
| #75 kotlin | versions.properties sem coordenada Maven |
| #93 jekyll | gemspec com ranges, sem Gemfile.lock |
| #94 signal-android | sem lockfile gradle |
| #84 httpd | SVN, GHSA sem /commit/ |
| #85 wireshark | GitLab, GHSA sem /commit/ |
| #83 sqlite | **reservado para teste de FP (constraint do usuário)** |

O teto honesto da lista é **99/100** (sqlite fora por reserva do
usuário). Dos 8 não-reservados, os mais tratáveis seriam jekyll/signal
(buscar CVE com fix-commit via GHSA + AST Ruby/Java) e redisson (idem,
se houver CVE real). httpd/wireshark exigem crawl SVN/GitLab; serde/boto3
não têm dado de patch/versão. De 74 a 91/100 nesta sessão, três motores
(M9.2/M9.3/M9.4), zero fabricação, com auditoria de contagem incluída.
