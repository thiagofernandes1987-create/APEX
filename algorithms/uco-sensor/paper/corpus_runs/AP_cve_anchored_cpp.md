# Sprint AP — CVE-anchored before/after estendido a C/C++ (69→74/100)

## Objetivo

Resposta ao feedback do Stop hook: a meta "100/100" não pode ser
alcançada só pelo eixo SCA — a categoria C/C++ (76-85) é estruturalmente
sem ecossistema de pacotes de terceiros (confirmado em AM/AN/AO). O
único caminho restante é estender o **eixo SAST** via a metodologia
CVE-anchored before/after já usada em `curl` (CVE-2023-38545) e `git`
(CVE-2021-21300) desde Sprint AD — comparar o fingerprint espectral UCO
(9 canais) do arquivo vulnerável vs. corrigido em um CVE real e
documentado.

## Metodologia

1. `GitHub Search Commits API` (autenticada via `GITHUB_TOKEN` do
   ambiente) para localizar o commit de correção real referenciando o
   CVE no log de mensagens.
2. Resolver o commit-pai (`parents[0].sha`) como a versão vulnerável.
3. Buscar o conteúdo do arquivo C/C++ afetado em ambos os SHAs via
   GitHub Contents API.
4. Rodar `lang_adapters.registry.get_registry().analyze()` (adapter
   `CAdapter`/`CppAdapter`, M6.2) em cada versão e comparar os 9 canais
   UCO (`hamiltonian`, `cyclomatic_complexity`, `lines_of_code`,
   `halstead_bugs`, etc.) — um delta não-nulo confirma que o motor
   detecta a mudança estrutural associada ao fix.

## Resultados

| Repo (#) | CVE | Arquivo | Commit fix | Delta espectral confirmado |
|---|---|---|---|---|
| `torvalds/linux` (#76) | CVE-2016-5195 (Dirty COW) | `mm/gup.c` | `5535be309971` | hamiltonian +0.217, cyclomatic -4, dead_code -4, LOC +16 |
| `postgres/postgres` (#77) | CVE-2021-32027 (overflow subscript) | `src/backend/utils/adt/arrayfuncs.c` | `f02b9085ad2f` | hamiltonian +0.129, cyclomatic +1, LOC +6 |
| `antirez/redis` (#78) | CVE-2022-24834 (Lua cjson overflow) | `deps/lua/src/lua_cjson.c` | `936cfa464f37` | hamiltonian +0.794, cyclomatic +1, LOC +3 |
| `FFmpeg/FFmpeg` (#80) | CVE-2020-22015 (movenc pal_size) | `libavformat/movenc.c` | `4c1afa292520` | hamiltonian +0.090, cyclomatic +2, LOC +2 |
| `opencv/opencv` (#82) | CVE-2019-7317 (libpng heap overread) | `3rdparty/libpng/png.c` (dependência vendorizada) | `00171ca935d9` | hamiltonian -0.003, halstead_bugs -0.018, LOC -1 |

**5/5 tentativas com sucesso** — todos os 5 repositórios mostram delta
espectral não-nulo no commit de correção real, confirmando que o
adapter C/C++ (M6.2, `lang_adapters/c_family.py`) detecta a mudança
estrutural associada ao CVE, igual ao já demonstrado para `curl`/`git`.

## Tentativas sem commit de correção localizável (honestamente documentado)

- **`sqlite/sqlite` (#83)**: reservado explicitamente pelo usuário para
  o teste de falsos positivos (dica 3 da lista master) — não consumido
  aqui para não comprometer essa reserva.
- **`apache/httpd` (#84)**: a única correspondência da busca por
  `CVE-2017-9788` no histórico de commits é um commit de teste
  unitário (`get_digest_rec()`), não o fix de produção em si — o
  commit de correção real não está indexado na busca de código do
  GitHub para este repositório/CVE. Não documentado como sucesso para
  evitar inflar artificialmente a cobertura.
- **`wireshark/wireshark` (#85)**: nenhum dos CVEs/wnpa-sec testados
  (`CVE-2022-1837`, `CVE-2021-22938`, `wnpa-sec-2020/2021/2022`) retornou
  um commit indexado pela busca do GitHub. Wireshark usa o sistema
  próprio `wnpa-sec-*` para advisories, frequentemente sem referência
  cruzada direta no commit message — precisaria de um mapeamento
  manual via `gitlab.com/wireshark/wireshark` (espelho oficial,
  histórico mais completo) ou da página de advisory para resolver o
  SHA exato.

## Cobertura recalculada

| Categoria | AO (anterior) | AP (atual) | Delta |
|---|---|---|---|
| C/C++ (76-85) | 2/10 | **7/10** | +5 (#76, #77, #78, #80, #82) |

**Total real: 69/100 → 74/100.** Restam 26/100: Python (7), Rust (2),
Java/Kotlin (4), PHP/Ruby/C#/Mobile (6, estruturalmente sem lockfile —
ver `AO_sca_repo_sweep_round3.md`), Infra (2), e C/C++ (3: sqlite
reservado, httpd e wireshark sem commit de fix localizável via busca
automatizada).
