# Sprint BZ — Scan de perpetuação nas versões corrigidas

> Responde diretamente à diretriz: *"compare se nas versões corrigidas se o
> programa parou de disparar e **se algo perpetuou e não foi identificado**"*.
> 100% dado real (`raw.githubusercontent.com` na versão do commit-fix), sem
> inventar. Artefato: `residual_perpetuation_artifact.json`.

## Método

Para cada CVE do corpus C, rodamos o **M11 GuardAwareScanner na versão
CORRIGIDA** (fix SHA). Um sinal que persiste na versão corrigida é um
**candidato de perpetuação**: uma construção memory-unsafe que o fix da CVE
**não tocou** — ou é um risco real não-CVE, ou um FP (bound presente mas não
reconhecido pelo M11). É o "algo perpetuou" que o objetivo pede rastrear.

## Resultado (dado real)

| Repo / CVE | sinais residuais (M11 na versão corrigida) | sites |
|---|---|---|
| php-src CVE-2019-11043 | **4** | L1276, L1295, L1666, L1672 (GA02 memcpy sem bound reconhecido) |
| ffmpeg CVE-2020-22015 | **3** | L4727 (GA01), L5834, L6155 (GA02) |
| postgres CVE-2021-32027 | **2** | L4602, L4699 (GA02) |
| redis CVE-2022-24834 | 0 | — (versão corrigida limpa p/ M11) |
| sqlite CVE-2019-19646 | 0 | — (versão corrigida limpa p/ M11) |

**9 sinais residuais totais.** Isso é exatamente o valor do "algo perpetuou":
o Sensor aponta construções que sobreviveram ao fix da CVE — antes desta
sprint, essa lista não existia.

## Enquadramento honesto (anti-overclaim)

Estes são **sinais guard-aware, NÃO bugs confirmados**. GA02 ("memcpy-family
com comprimento variável sem bound no escopo") tem FP conhecido — o bound
pode existir numa forma que o M11 não reconhece. Portanto cada site precisa de
**triagem**: (a) risco real não-CVE, ou (b) FP. A triagem é o próximo passo do
checklist — mas a **capacidade de produzir a lista de perpetuação com dado
real** é a entrega desta sprint, e é o que faltava para responder à pergunta.

## Comparação com "parou de disparar" (BM)

- **php-src**: a CVE específica (GA01 `pilen>slen`) PAROU (validado em BM);
  mas 4 GA02 memcpy PERPETUARAM (esta sprint). Os dois lados agora medidos.
- **redis/sqlite**: 0 residual — o fix deixou o arquivo limpo p/ o M11.

## Checklist — evolução
- [x] **Scan de perpetuação nas versões corrigidas + artefato** — FEITO
- [ ] Triagem dos 9 residuais (risco real não-CVE vs FP GA02) — PRÓXIMO
- [ ] Reduzir FP do GA02 (reconhecer mais formas de bound no escopo)
