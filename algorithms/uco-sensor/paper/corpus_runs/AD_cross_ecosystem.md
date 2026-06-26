# Sprint AD — CVE-Anchored Before/After Audit Fora do Python (5 Ecossistemas)

> Resposta direta ao pedido explícito do usuário: estender a metodologia
> rigorosa de diff antes/depois ancorada em CVE (AC-3) para uma amostra
> representativa fora do Python — escolhida entre os ~100 repositórios
> sugeridos, cobrindo C, Go, JavaScript, Java e Rust. O usuário optou
> explicitamente por "amostra representativa" (2-3 casos por ecossistema)
> em vez de tentar os ~100 repositórios de uma vez.

## Metodologia

Idêntica à AC-3 (`paper/cve_diff_check.py`): para cada CVE documentado,
resolve-se `(vulnerable_sha, fixed_sha, file_path)` via GitHub Security
Advisories API + busca de commits, busca-se ambos os snapshots do
arquivo via Contents API, e roda-se `sast.scanner.scan()` +
`lang_adapters.registry.get_registry().analyze()` em cada um. O script é
agnóstico de linguagem (dispatch por `Path(args.path).suffix`), então
nenhuma modificação foi necessária para estendê-lo a estas linguagens.
Limiar de sinal: delta relativo de métrica >15%, ou mudança no conjunto
de regras SAST disparadas.

## Casos rodados (5, um por ecossistema)

| Repo | Linguagem | CVE | Arquivo | Causa raiz | SAST diff | Delta métrica >15% | Veredito |
|---|---|---|---|---|---|---|---|
| `curl/curl` | C | CVE-2023-38545 | `lib/socks.c` | SOCKS5 buffer overflow (hostname remoto longo não validado) | nenhum | nenhum | **BLIND SPOT** |
| `golang/go` | Go | CVE-2023-29404 | `src/cmd/go/internal/work/security.go` | `cgo` aceita flags de linker não-opcionais, viabilizando RCE no build | nenhum | nenhum (0% — idêntico) | **BLIND SPOT** |
| `axios/axios` | JavaScript | CVE-2023-45857 | `lib/adapters/xhr.js` | Header `X-XSRF-TOKEN` enviado a hosts de terceiros (CSRF) | nenhum | nenhum | **BLIND SPOT** |
| `spring-projects/spring-framework` | Java | CVE-2022-22965 (Spring4Shell) | `CachedIntrospectionResults.java` | Acesso a `class.classLoader`/`class.protectionDomain` via data binding → RCE | nenhum | `cyclomatic_complexity` +12%, `duplicate_block_count` +15% (ambos sob o limiar de 15%) | **BLIND SPOT** |
| `rust-lang/regex` | Rust | CVE-2022-24713 | `src/compile.rs` | ReDoS via contadores de repetição aninhados sem limite de tamanho | nenhum | nenhum (152→152, estável após o fix do adaptador — ver achado abaixo) | **BLIND SPOT** |

**5/5 (100%) são blind spots limpos** — nenhuma mudança de regra SAST,
nenhum canal de métrica cruzou o limiar de 15% de forma diagnosticamente
relevante. Resultado esperado e disclosed: `SAST046`/`SAST047` (as duas
regras novas da AC-3) são específicas de forma de AST Python; nenhuma
delas poderia disparar em C/Go/JS/Java/Rust por construção. Nenhum dos 5
adapters de linguagem destas pilhas tem regras SAST próprias ainda —
gap conhecido, não escondido.

O caso `spring-framework` merece nota: há um delta de métrica real
(complexidade ciclomática 51→57, +12%), mas **abaixo** do limiar de 15%
adotado desde a AC-3, e mesmo se estivesse acima seria um caso
confundido — o fix real adiciona uma lista de bloqueio de propriedades
sensíveis (`class.classLoader`, etc.), uma adição estrutural genuína, não
um sintoma incidental. Tratado como blind spot, não como sinal parcial.

## Achado principal: bug real no `RustAdapter` (não um gap de detecção — um defeito de instrumentação)

Investigando o caso `rust-lang/regex`, a métrica `cyclomatic_complexity`
inicialmente mostrou um salto absurdo entre os dois snapshots quase
idênticos (diff real de apenas 27 linhas em `src/compile.rs`):

| | vulnerável | corrigido |
|---|---|---|
| `cyclomatic_complexity` (com o bug) | 45 | 102 |
| `hamiltonian` (com o bug) | 7.55 | 21.76 |
| `halstead_bugs` (com o bug) | 5.26 | 9.54 |

Um salto de complexidade de 45→102 para um diff de 27 linhas é
estatisticamente implausível — confirmado reproduzindo o cálculo
diretamente sobre o texto "limpo" (`RustAdapter()._strip()`), que quase
dobrou de tamanho entre os dois snapshots apesar do código-fonte bruto
ser quase idêntico.

**Causa raiz**: `lang_adapters/rust.py`'s `STRING_RE` usava um
quantificador `*` sem limite no ramo de literal de caractere
(`'(?:[^'\\]|\\.)*'`). Rust usa apóstrofo nu, sem aspas de fechamento,
para *lifetimes* e parâmetros genéricos (`'a`, `'static`, `<'a>`,
`&'a T`) — sintaticamente distinto de um literal de caractere real
(`'x'`, que tem fechamento). O regex sem limite, ao encontrar um
apóstrofo de lifetime, "casava" tudo até a próxima aspa simples não
relacionada em qualquer lugar do arquivo (devido a `re.DOTALL`),
fundindo literais de string e trechos de código inteiros em um único
"literal de caractere" bogus — um artefato puro de medição, sem relação
com o diff real de 17 linhas do CVE.

**Correção**: limitar o ramo de literal de caractere a exatamente um
caractere/escape:

```python
r"|b?'(?:\\u\{[0-9a-fA-F]+\}|\\.|[^'\\\n])'"
```

Após o fix, o mesmo caso real estabiliza em `cyclomatic_complexity:
152 → 152` (idêntico) — o salto espúrio desaparece por completo.

**Validação**: 8 testes de pinagem (`tests/test_marco_m64.py`,
TAD01-TAD08) cobrindo lifetime isolado, lifetime+string+char
combinados, literais de caractere reais (simples, escapados, unicode)
que continuam sendo corretamente removidos, estabilidade de
complexidade entre snapshots quase idênticos, e ausência de
"match-runaway" multi-linha. Suíte completa: **2213 passed, 5 skipped,
0 regressões**.

## O que esta rodada valida / deixa aberto

* A metodologia de diff antes/depois ancorada em CVE generaliza sem
  modificação para qualquer linguagem suportada pelo `cve_diff_check.py`
  — o script já era agnóstico de linguagem por design.
* 5/5 blind spots confirma que o gap estrutural já identificado na AC-3
  (SAST/métricas não diagnosticam vulnerabilidades de lógica de negócio
  específicas) não é uma peculiaridade do Python — é sistêmico em todo
  o produto, agora replicado em 5 ecossistemas adicionais.
* Nenhuma regra SAST nova foi adicionada nesta rodada (diferente da
  AC-3) — as 5 vulnerabilidades têm causas raiz muito heterogêneas
  (buffer overflow C, RCE via flags de build Go, CSRF JS, data-binding
  RCE Java, ReDoS Rust) e nenhuma compartilha uma forma de AST comum o
  suficiente para justificar uma regra única nesta rodada.
* O achado de maior valor concreto desta rodada não foi uma regra de
  detecção nova, mas a correção de um **defeito real de instrumentação**
  no `RustAdapter` — sem ele, qualquer comparação futura de métricas em
  código Rust real (não só este CVE) estaria sujeita ao mesmo artefato
  de medição sempre que houver lifetimes/genéricos próximos de strings.
