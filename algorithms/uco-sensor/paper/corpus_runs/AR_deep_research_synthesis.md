# Sprint AR — Síntese da Deep Research + motor AST tree-sitter (M9.2)

> Disparada pelo pedido do usuário (`/deep-research`): "pesquisar em toda
> internet... um método de superarmos essa barreira dos 74/100... se for
> necessário um novo módulo AST, só faça". Workflow multi-agente de 5
> ângulos, 20 fontes, 77 claims extraídas. **Nota metodológica honesta:**
> a fase de verificação adversarial do workflow morreu inteira por limite
> de sessão da API de pesquisa (`You've hit your session limit · resets
> 11pm UTC`) — todos os 25 votos saíram `0-0` ("3 abstain"), o que o
> sumário rotulou erroneamente como "all claims refuted". Nenhuma claim
> foi de fato refutada; elas simplesmente não chegaram a ser verificadas.
> As 10 fontes primárias (papers USENIX/ICSE/arXiv + specs oficiais OSV/
> GHSA) foram extraídas antes do limite e são tratadas aqui como **leads
> não-verificados de alta qualidade**, não como fatos confirmados.

## Diagnóstico: por que 74/100 não é "falta de esforço", são 3 limitações de motor

| # | Bloqueio | Sintoma observado | Repos afetados |
|---|----------|-------------------|----------------|
| B1 | Adapters Tier-2 são **regex**, não AST real | fix de 1 linha → delta espectral **zero** (php-src CVE-2019-11043) | C/C++/PHP/Ruby/C# |
| B2 | SCA exige **lockfile commitado** | 6 repos sem lockfile em lugar nenhum | PHP/Ruby/C#/Mobile |
| B3 | Descoberta de fix-commit via **commit-message search** | httpd (SVN)/wireshark (GitLab) não citam CVE no commit | C/C++ + alguns |

## O que a pesquisa apontou (por ângulo)

**ANGLE 1 — detecção AST de fixes de 1 linha.** Leads: `difftastic`
(diff estrutural tree-sitter, 30+ linguagens, Dijkstra sobre a árvore),
VFFinder (arXiv:2309.01971 — AST anotada + GNN, 507 projetos C/C++),
VFDelta (arXiv:2409.16606 — subtração elemento-a-elemento de embeddings
antes/depois para realçar mudanças finas), CommitShield (ICSE 2025 —
Joern CPG + tree-sitter + LLM). **Conclusão acionável:** não precisamos
do GNN/LLM para fechar o gap imediato — basta um **parse tree-sitter real
+ diff estrutural de histograma de nós**, que é o de menor esforço e já
elimina o delta=0. ➜ **IMPLEMENTADO nesta sprint (M9.2).**

**ANGLE 2 — SCA por código-fonte (sem lockfile).** Leads: V1SCAN (USENIX
Sec 2023 — classifica código OSS reusado em C/C++, FP de 71%→4%), CENTRIS
(ICSE 2021 — assinatura por função, 91% precisão / 94% recall; reuso de
OSS *modificado* é ~20× mais comum que cópia exata, então hash-exato
perde a maioria), OSSPolice. **Conclusão:** é o caminho real para os 6
repos sem lockfile, mas exige um índice de assinaturas de função de OSS —
esforço médio-alto. Candidato para Sprint AS, não para hoje.

**ANGLE 3 — fontes de fix-commit além do commit-search.** Lead central:
**OSV schema** — `affected[].ranges[type=GIT]` com `introduced`/`fixed`
sendo **hashes de commit completos**, e `references[type=FIX]`. Validação
empírica nesta sessão: `api.osv.dev` está **bloqueado pela política de
rede do sandbox (403 no gateway)**, mas a **GitHub Advisory REST API**
(`api.github.com/advisories?cve_id=...`) é permitida e carrega os mesmos
dados upstream. Teste real: retornou GHSA para httpd (GHSA-w97h-p5ff-7q69,
70 refs) e wireshark (GHSA-mh9j-54rp-3h7j) — **porém** nenhuma das refs é
um link `/commit/` para esses projetos SVN/GitLab; só o curl (nativo
GitHub) trouxe o commit direto. **Conclusão honesta:** OSV/GHSA fecha
parte dos gaps (onde o projeto é GitHub-nativo), mas **não** resolve
httpd/wireshark especificamente — eles continuam exigindo crawl do SVN
da Apache / GitLab do Wireshark. Esforço baixo para o ganho parcial.

**ANGLE 4 — precedente científico para "spectral fingerprint" como sinal
de segurança.** Lead: "Code-centric Learning-based Just-In-Time
Vulnerability Detection" (arXiv:2304.08396) — detecção no nível de
commit/mudança a partir da estrutura do código, exatamente o
enquadramento do UCO Sensor. Dá lastro acadêmico à abordagem
CVE-anchored; reforça que o fingerprint sozinho é fraco (já documentado
em AK) e deve compor com o eixo AST.

**ANGLE 5 — suporte multilíngue.** Lead: guia oficial do Semgrep para
adicionar linguagem (pipeline tree-sitter unificado); Joern (CPG
multilíngue). **Conclusão:** o caminho de menor atrito é reusar
gramáticas tree-sitter pip-instaláveis — que é o que M9.2 faz.

## Decisão de implementação (esforço × impacto)

| Solução | Bloqueio | Esforço | Status |
|---------|----------|---------|--------|
| **Motor AST tree-sitter + diff estrutural (M9.2)** | B1 | **baixo** | ✅ **feito** |
| OSV/GHSA fix-commit resolver | B3 (parcial) | baixo | candidato Sprint AS |
| SCA por similaridade de função (V1SCAN/CENTRIS) | B2 | médio-alto | candidato Sprint AT |
| Classificador de patch (VFFinder/CommitShield) | precisão | alto | pesquisa futura |

## Entregue nesta sprint: M9.2 — AST Structural Diff

`lang_adapters/ast_structural_diff.py` + extensão de `tree_sitter_bridge`
para C/C++/PHP/Ruby/C# (gramáticas pip, `pypi.org` está na allowlist do
proxy). Assinatura = histograma de tipos de nó + profundidade; diff =
churn (soma de |Δ| por tipo) + `security_operator_delta` (operadores de
bounds-check/guard). Degradação graciosa: gramática ausente → `None`,
nunca quebra.

**Validação empírica (6 fixes C reais, antes/depois do commit de fix):**

| Repo / CVE | regex (eixo antigo) | AST churn (M9.2) | operadores de segurança movidos |
|---|---|---|---|
| php-src CVE-2019-11043 | **delta = 0** ❌ | **12** ✅ | `>`+1 (bounds), `&&`+2, binary_expr+3 |
| linux CVE-2016-5195 | detectado | 123 | `!`+6, if+6, `||`+1 |
| postgres CVE-2021-32027 | detectado | 145 | binary_expr−4, `>`−1, if−1 |
| redis CVE-2022-24834 | detectado | 26 | `>`+1, binary_expr+3, if+1 |
| ffmpeg CVE-2020-22015 | detectado | 43 | `<`+1, `>`+1, `||`+1, if+1 |
| opencv CVE-2019-7317 | detectado | 10 | — |

O ganho decisivo é o **php-src**: o eixo regex dava delta=0 (incontável);
o eixo AST mostra o operador `>` do bounds-check `pilen > slen` que É a
correção do underflow CVE-2019-11043. Isso converte php-src num dado
SAST CVE-anchored legítimo, via motor novo — **não** por fabricação.

## Impacto na cobertura

php-src (#89, categoria PHP/Ruby/C#/Mobile) passa a ter eixo SAST válido
(AST-anchored). Categoria 86-95: **4/10 → 5/10**. Cobertura total da
lista master: **74/100 → 75/100**.

Os demais 25 gaps continuam honestamente abertos — mas agora com um
roadmap pesquisado e priorizado (Sprint AS: OSV/GHSA resolver; Sprint
AT: SCA por similaridade de função) em vez de um "teto estrutural"
inerte. O motor AST também eleva a fidelidade de *todas* as análises
C/C++/PHP/Ruby/C# futuras, não só fecha um gap pontual.
