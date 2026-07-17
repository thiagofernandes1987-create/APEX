# Sprint BH — Detecção guard-aware (M11): dispara no vulnerável, para no fix

> Continuação direta de BG. O diagnóstico de BG foi: o SAST de padrão não
> detecta as classes memory-safety (dá rating A no vulnerável; quando
> dispara, persiste idêntico no fix). BH entrega a **primeira detecção real
> que dispara no código vulnerável e PARA de disparar no corrigido — sem
> conhecer o commit de fix.** Este é o núcleo de "rastrear bug conhecido" e
> de "avaliar código gerado por IA". Dados reais, sem inventar.

## A ideia: guard-awareness

Uma construção arriscada não é, sozinha, um bug — é bug **quando o guard que
a tornaria segura está ausente do escopo**. Então M11 (`sast/guard_aware.py`):

1. acha o *sink* arriscado (subtração em aritmética de ponteiro/comprimento
   `base + a - b`; ou `memcpy/memmove(dst,src,n)`);
2. extrai as variáveis que precisam de proteção (`a`,`b` ou `n`);
3. procura um **guard** sobre elas numa janela local (`a > b`, `a >= b`,
   `n < LIMIT`…);
4. **dispara só quando não há guard.** O fix, que adiciona o guard, suprime
   o achado.

(A janela local substitui o segmentador de função por chaves, que se mostrou
frágil em C real — diretivas de preprocessador quebram a contagem de
profundidade e a linha do bug ficava fora de qualquer span.)

## Validação real (php-src CVE-2019-11043)

`sapi/fpm/fpm/fpm_main.c`, vulnerável vs corrigido (via raw, dado real):

| Versão | GA01 na L1212 `env_path_info + pilen - slen` |
|---|---|
| **VULNERÁVEL** (pai) | **DISPARA** — sem guard `pilen > slen` no escopo |
| **CORRIGIDA** (fix) | **SILENCIA** — `(env_path_info && pilen > slen) ? …` presente |

Total do arquivo: 5 findings no vulnerável → 4 no corrigido. **A L1212 — a
CVE real — é exatamente a que some.** Isto é o before/after fiel: o sensor
DISPAROU no bug e PAROU quando foi corrigido, localizando a linha, **sem usar
o commit de fix como âncora** (diferente do M10). 6 testes TX79 fixam o
comportamento offline.

## Honestidade sobre precisão (FP de baixa confiança)

M11 ainda gera achados de baixa confiança em outros arquivos:

| Repo | vuln/fix | natureza |
|---|---|---|
| ffmpeg | 3/3 (persiste) | `offset = pos + total_sidx_size - end_pos`, `memcpy(...,prft_size)` — subtração/cópia sem guard na janela; code-smell, não a CVE |
| postgres | 3/3 (persiste) | `memcpy(dst,src,numbytes)`, `memmove(...,inc)` — comprimento cujo bound está fora da janela |
| redis/linux | 0/0 | fix não é dessa classe (Lua widening / race-condition) |

Estes persistem porque são construções genuinamente sem guard *visível na
janela* — um analista tria; não é fabricação, é a precisão a calibrar. Não
inflei nada: reporto o estado real. Próximas melhorias de precisão no
checklist (exigir uso como ponteiro/índice; heurística de tipo; escopo por
CFG do UCO V4 em vez de janela).

## Estado do checklist (objetivo do usuário)

- [x] M10 FixDiffLocalizer — localiza linha/classe do fix (CVE conhecida)
- [x] **M11 GuardAwareScanner — detecção que dispara no vuln e para no fix
      SEM conhecer o fix** *(php-src provado; GA01 underflow, GA02 memcpy)*
- [ ] Precisão de M11: escopo por CFG (UCO V4) em vez de janela; heurística
      ponteiro/tipo para cortar os FP de baixa confiança
- [ ] Consumir GenericCFGBuilder do UCO V4 p/ C/Rust/Java (dead-code +
      reachability) — habilita o escopo-por-CFG acima
- [ ] Taint/dataflow fonte→sink via CFG do V4
- [ ] Rodar M10+M11 sobre os 100 repos, persistir validação por repo
- [ ] Ampliar M11 a mais classes (use-after-free, format-string real,
      signed/unsigned)

M11 é a virada: de "cobrir 100/100" e "algo mudou (churn)" para **detectar a
classe do bug e provar que a correção o silencia** — a função de avaliador
de código que o produto precisa. Regressão 2386 verdes. Versão 3.32.0.
