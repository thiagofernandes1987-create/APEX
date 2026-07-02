# Sprint BG — Diagnóstico de detecção + FixDiffLocalizer (M10)

> Disparada pela reformulação do objetivo: não basta "cobrir 100/100" —
> o UCO Sensor precisa **rastrear o bug conhecido de verdade**: quando,
> como, onde quebrou e em qual versão foi resolvido, e **validar se, na
> versão corrigida, o sensor parou de disparar** (e se algo perpetuou).
> Dados 100% reais (GitHub via raw), zero fabricação.

## Diagnóstico honesto: o que os motores atuais NÃO fazem

Rodei os 3 motores (`registry.analyze` MetricVector, SAST scanner, UCO V4
`analyze`) nas versões **vulnerável (pai do fix)** vs **corrigida** de 6
CVEs C/C++ reais. Resultado cru:

| Repo / CVE | halstead_bugs (vuln→fix) | SAST (vuln→fix) | UCO V4 bugs |
|---|---|---|---|
| php-src CVE-2019-11043 | 11.418 → 11.418 (Δ0) | A/0 → A/0 | **None** |
| linux CVE-2016-5195 | 14.309 → 14.518 | A/0 → A/0 | None |
| postgres CVE-2021-32027 | 26.273 → 26.412 | **E/3 (C02,C03) → E/3 (idêntico)** | None |
| redis CVE-2022-24834 | 9.718 → 9.793 | A/0 → A/0 | None |
| ffmpeg CVE-2020-22015 | 67.982 → 68.052 | A/0 → A/0 | None |
| opencv CVE-2019-7317 | 8.972 → 8.954 | A/0 → A/0 | None |

**Três problemas expostos:**

1. **O SAST de padrão não detecta as classes de memory-safety** (integer
   underflow, OOB, use-after-free): dá rating A (0 findings) na maioria.
   Quando dispara (postgres C02 buffer-overflow / C03 format-string), é por
   padrão genérico e **persiste idêntico antes e depois do fix** — logo não
   sabe dizer "disparou antes / parou depois".
2. **`halstead_bugs` não distingue** vulnerável de corrigido (Δ ~0, e às
   vezes sobe no fix porque o fix adiciona código).
3. **UCO V4 `analyze()` retorna `bugs=None`/`score=None` para não-Python** —
   sua análise profunda (Halstead/score) é baseada em AST do Python. O
   `GenericCFGBuilder` (via Pygments) existe mas o pipeline de bugs/score não
   o consome para C/Rust/Java. **Potencial subutilizado.**

Ou seja: hoje o M9.2 (diff AST) só diz que *algo mudou* (churn) — não
localiza o bug, não classifica, não valida que parou. Isso é o gap real:
"ter engenharia top e não rastrear bugs conhecidos".

## Entregue: M10 — FixDiffLocalizer (`sast/fix_localizer.py`)

Para a **validação de CVE-conhecida**, o caminho honesto e de dado-real é
ancorar no diff do fix: o diff é ground-truth de onde/como o bug foi
corrigido. `FixDiffLocalizer.localize(vuln_src, fixed_src)`:

1. computa o diff (difflib) entre as duas revisões;
2. extrai as linhas **adicionadas** que contêm construção de segurança
   (bounds-check, null-guard, type-widening, early-return, safe-copy,
   `unsafe`), com a **linha exata** e classe CWE inferida;
3. valida **presente-no-fix / ausente-no-vuln** — o "parou de disparar"
   fiel: o guard que faltava na versão vulnerável está na corrigida.

### Resultado real (7 pares C/C++)

| Repo / CVE | guards | linha localizada | classe |
|---|---|---|---|
| **php-src** CVE-2019-11043 | 2 | **L1212** `(env_path_info && pilen > slen) ? …` | CWE-190/125 + CWE-476 |
| **redis** CVE-2022-24834 | 4 | **L145** `size_t index;` (widening do overflow Lua cjson) | CWE-190 |
| **ffmpeg** CVE-2020-22015 | 1 | **L2168** `return AVERROR(EINVAL);` | CWE-20 |
| **sqlite** CVE-2019-19646 | 1 | **L647** `iCol>=BMS ? BMS-1 : iCol` (clamp) | CWE-190/125 |
| linux CVE-2016-5195 | 0 | — (Dirty COW é race-condition, não guard) | miss honesto |
| postgres CVE-2021-32027 | 0 | — (recálculo de comprimento, não guard) | miss honesto |
| opencv CVE-2019-7317 | 0 | — (mudança de 1 linha no libpng vendorizado) | miss honesto |

**4/7 localizados com linha + classe exatas**, validados
presente-no-fix/ausente-no-vuln. O php-src — que dava churn AST mas nenhuma
localização — agora aponta **L1212, o bounds-check `pilen > slen`**, que É a
correção da CVE-2019-11043. Os 3 misses são honestos (fixes que não
adicionam guard: race condition, recálculo, libpng). 5 testes TX78 (fixtures
offline reproduzindo o padrão php-src). Regressão 2380 verdes.

## O que o M10 NÃO é (honestidade)

O M10 valida CVE **conhecida** (usa o commit de fix como âncora). Ele **não**
detecta bug desconhecido — isso é papel do SAST/taint (que hoje não cobre as
classes memory-safety, ver checklist). Para o caso de uso "avaliador de
vibe-coding" (achar bug em código gerado por IA sem conhecer o fix), o
checklist abaixo lista o que falta construir.

## Checklist — o que criar para o objetivo pleno

- [x] **M10 FixDiffLocalizer** — localiza linha/classe do fix + valida
      before/after (CVE conhecida). *(feito nesta sprint)*
- [ ] **Ampliar assinaturas de guard** do M10 para cobrir race-condition
      (locking) e recálculo-de-comprimento (linux/postgres misses) — com
      cuidado anti-FP.
- [ ] **Regras SAST de memory-safety** que disparam no VULNERÁVEL e NÃO no
      fix: pointer-arithmetic com subtração não-checada (underflow),
      `memcpy`/`alloca` sem bound, signed/unsigned mismatch. Meta: o "parou
      de disparar" de verdade, sem conhecer o fix.
- [ ] **Consumir o GenericCFGBuilder do UCO V4** para C/Rust/Java: dead-code
      e reachability por CFG genérico (hoje só Python usa o pipeline
      profundo). Extrair o potencial do V4.
- [ ] **Taint/dataflow real** usando `CFG.reachable_from_entry` + uses/defs
      do V4 para rastrear fonte→sink (o motor de fluxo de dados que o
      objetivo pede ampliar).
- [ ] **Persistir validação por repo** (quando/como/onde/versão) num artefato
      estruturado navegável.
- [ ] **Rodar M10 sobre os 100 repos** (não só os 7 C) — Python/JS/Java/Rust
      já têm os pares de fix-commit resolvidos nos relatórios AR–BF.

De 100/100 de cobertura para **rastreio localizado e validado** — o M10 é o
primeiro passo real nessa direção, com dado verificável e sem fabricação.
