# Sprint BM — Execução do CorpusValidator (M12) sobre pares CVE reais

> Objetivo: produzir o artefato de degradação por-repo com **dado real** —
> onde/como/qual-versão (M10) + parou-de-disparar (M11) + o que perpetuou —
> e mapear honestamente onde o sensor ainda não rastreia. Artefato
> persistido em `corpus_validation_artifact.json`.

## Método (100% dado real, sem inventar)

Para cada CVE: `fetcher = raw.githubusercontent.com` busca o arquivo na
versão **vulnerável (commit-pai)** e **corrigida (commit-fix)**. O M12 roda:
- **M10 FixDiffLocalizer** → linha + classe do guard que o fix adicionou;
- **M11 GuardAwareScanner** → dispara na versão vulnerável e casa por chave
  `(rule_id, variáveis-do-guard)`; "parou de disparar" = a mesma chave some
  na versão corrigida; "perpetuou" = a mesma chave persiste.

## Resultado (6 pares C/C++)

| CVE | repo | M10 localiza | M11 disparou→parou | perpetuou | status |
|---|---|---|---|---|---|
| **CVE-2019-11043** | **php-src** | **SIM L1212** | **SIM (GA01 pilen,slen)** | 4 (outros sites) | **tracked ✓** |
| CVE-2022-24834 | redis | sim (L145 size_t) | não (classe = widening) | 0 | tracked |
| CVE-2020-22015 | ffmpeg | sim (L2168 EINVAL) | não | 3 | tracked |
| CVE-2019-19646 | sqlite | sim (L647 clamp) | não | 0 | tracked |
| CVE-2016-5195 | linux | não (race condition) | não | 0 | not_tracked |
| CVE-2021-32027 | postgres | não (recálculo len) | não | 3 | not_tracked |

**Sumário:** total=6, tracked=4, m10_localized=4, m11_stopped_firing=1,
not_tracked=2, fetch_error=0.

## Leitura honesta

- **php-src é o caso-ouro completo:** o M11 detecta o underflow
  (`env_path_info + pilen - slen` sem `pilen > slen`) **sem conhecer o
  fix**, aponta L1212, e **para de disparar** na versão corrigida (o fix
  adiciona o guard). Isso é o "rastrear bug conhecido + validar que parou"
  no seu sentido pleno.
- **redis/ffmpeg/sqlite:** o M10 localiza onde/como/versão (âncora no diff),
  mas o M11 não cobre a classe *sem âncora* — redis é widening de tipo
  (`int`→`size_t`), ffmpeg é early-return, sqlite é clamp. São classes que o
  M11 (GA01 subtração / GA02 memcpy) ainda não modela. **Miss honesto,
  listado no checklist.**
- **linux/postgres (not_tracked):** o fix não adiciona guard reconhecível
  (Dirty COW é race-condition; postgres é recálculo de comprimento). Nem M10
  nem M11 se aplicam — e isso está **corretamente reportado como
  not_tracked**, não mascarado.
- **"perpetuou":** os counts (php-src 4, ffmpeg 3, postgres 3) são findings
  GA01 em **outros sites do mesmo arquivo** que persistem — não são a CVE.
  Precisam de triagem (podem ser FP de subtração benigna ou riscos reais
  não-CVE). Registrado para a rodada de precisão.

## Bloqueio conhecido (honesto)

Rodar o M12 sobre os ~40 pares SAST de Python/JS/Java/Rust exige o **SHA do
commit-pai**, obtido da API de commits do GitHub — que neste ambiente está
**bloqueada (403)** junto com `github.com/...patch` e o protocolo git; só
`raw.githubusercontent.com` passa (aceita SHA/tag). Para os 6 C acima eu
tinha os SHAs-pai no contexto. Alternativas para desbloquear (checklist):
usar **tags de release** como "vulnerável" (raw aceita tag) ou capturar os
pais quando a API voltar.

## Checklist — evolução

- [x] **M12 rodado sobre pares reais + artefato persistido**
      (`corpus_validation_artifact.json`) *(esta sprint)*
- [x] Validação before/after com dado real (php-src: detect+resolve completo)
- [ ] Cobrir classes redis(widening)/ffmpeg(early-return)/sqlite(clamp) no M11
- [ ] Triagem dos "perpetuou" (FP vs risco real não-CVE)
- [ ] Rodar M12 nos pares Python/JS via tags de release (contornar API 403)
- [ ] Taint fonte→sink (Python) validado before/after num par de
      path-traversal/injection

De cobertura 100/100 para **rastreio validado com artefato real**: 4/6 C
rastreados, 1 caso-ouro completo (php-src detect→resolve), limites honestos
mapeados. Zero fabricação.

---
## Correção (Sprint CA, v3.50.0) — FP de deslocamento de linha no M10

Auditoria posterior revelou que **sqlite e ffmpeg eram FALSAS localizações**:
o guard reportado (sqlite `iCol>=BMS ? BMS-1 : iCol`; ffmpeg `AVERROR(EINVAL)`)
**já existia na versão vulnerável** — o difflib o via como "insert" só porque o
fix inseriu linhas acima (deslocamento). Confirmado: `AVERROR(EINVAL)` aparece
25× no ffmpeg vulnerável; o clamp do sqlite está no vulnerável (V635).

Correção no `FixDiffLocalizer`: um guard só conta se seu conteúdo NÃO existe já
no vulnerável. **Sumário corrigido e honesto: total=6, tracked=2 (php-src,
redis), m10_localized=2, m11_stopped_firing=1, not_tracked=4.** php-src segue
como caso-ouro completo. Isto é exatamente "algo que perpetuou e não foi
identificado" — uma afirmação errada, agora corrigida. +1 teste TX78.
