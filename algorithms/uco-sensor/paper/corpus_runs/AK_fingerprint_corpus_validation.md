# AK — Validação do Fingerprint Espectral contra Corpus Maior (19 pares)

Resposta direta ao pedido do usuário: *"rodar contra um corpus maior (uns
15-20 pares vulnerável/corrigido já catalogados nesta sessão) e testaria
especificamente o cenário que mais preocupa um fingerprint aproximado:
dois arquivos diferentes mas do mesmo autor/linter/estilo podem ter
similaridade espuriamente alta."*

## Metodologia

Script: `/tmp/.../scratchpad/fp_corpus_validation.py` (não versionado —
ferramenta de validação, não produto). Reutiliza os 19 pares
vulnerável/corrigido já catalogados em `paper/capstone_rescan.py`
(`CASES`), buscando o conteúdo real via GitHub Contents API nos SHAs
exatos já validados nesta sessão. Para cada arquivo, calcula
`code_spectral_fingerprint.fingerprint()` (PSD Welch + energia wavelet
sobre o sinal "comprimento de linha"). Três comparações:

1. **Mesmo arquivo, vuln vs. corrigido** (a comparação para a qual o
   fingerprint foi desenhado) — n=19.
2. **Mesmo projeto, arquivo diferente** (`requests-1`
   `src/requests/utils.py` vs. `requests-2` `requests/sessions.py`,
   ambos `psf/requests`, CVEs e funções totalmente diferentes) — o
   confound explicitamente temido pelo usuário — n=4 (cruzando
   vuln/fixed dos dois lados).
3. **Baseline: projetos diferentes, arquivos diferentes** — todos os
   pares cruzados entre os 19 casos, exceto os já cobertos no item 2 —
   n=170.

## Resultado

| Comparação | n | média cosine sim. | min | max |
|---|---|---|---|---|
| Mesmo arquivo (vuln vs. corrigido) | 19 | **0.9969** | 0.9578 (scrapy) | 1.0000 |
| Mesmo projeto, arquivo diferente (requests-1 vs requests-2) | 4 | **0.9503** | 0.9463 | 0.9546 |
| Baseline — projetos diferentes | 170 | **0.9575** | 0.8183 | 0.9975 |

## Diagnóstico — o confound SOBREVIVE ao corpus maior

O cenário temido pelo usuário se confirma, e de forma mais grave do que
a hipótese original: a similaridade "mesmo projeto, arquivo diferente"
(0.9503) não apenas rivaliza com a similaridade "mesmo arquivo, vuln vs.
corrigido" (0.9969) — ela é estatisticamente **indistinguível do
baseline aleatório entre projetos completamente não relacionados**
(0.9575, n=170, intervalo 0.82–0.998).

Pior: o caso `scrapy` (mesmo arquivo, vuln vs. corrigido) tem
similaridade 0.9578 — **dentro do próprio intervalo do baseline entre
projetos não relacionados**. Ou seja, para pelo menos 1 dos 19 casos, o
fingerprint não consegue, na prática, diferenciar "mesma versão do
mesmo arquivo, diff trivial" de "dois arquivos de dois projetos
quaisquer".

Causa raiz provável: o sinal de entrada (`source_to_signal`) é apenas a
sequência de comprimentos de linha, normalizada por z-score. Esse sinal
captura sobretudo o "ritmo" de formatação (largura média de linha,
variância de indentação) — uma propriedade compartilhada por qualquer
código razoavelmente bem formatado (PEP8/gofmt/prettier/rustfmt), não
uma "impressão digital" do conteúdo semântico do arquivo. Por isso o
baseline entre projetos não relacionados já fica acima de 0.95: a
maioria dos arquivos de código profissional tem distribuição de
comprimento de linha parecida o suficiente para colapsar a métrica.

## Conclusão e próximo passo autorizado

Conforme o critério explícito do usuário — *"Se isso sobreviver a um
corpus maior, aí sim vale aprofundar features (histograma de tokens,
shape de AST) em vez de só comprimento de linha"* — o confound
**sobreviveu**. Logo, aprofundar features (histograma de tokens,
shape de AST) passa a ser justificado e fica registrado como próximo
passo, fora do escopo imediato deste checkpoint, dado o volume das
demais pendências (#67 SCA, #68 cobertura dos 100 repositórios).

**Recomendação honesta**: o MVP atual (`code_spectral_fingerprint.py`)
não deve ser usado como sinal autônomo de "mesmo arquivo/versão" em
produção — serve apenas como uma segunda dimensão fraca, correlacionada
principalmente com estilo de formatação, não com semântica de código.
Não é uma alternativa a hash exato de SCA nem uma melhoria sobre as
regras SAST/CWE já existentes no UCO Sensor.
