# Sprint AC-1 — Corpus Validation MVP: `psf/requests`

> **Correção (Sprint AC-2, ver `AC2_summary.md` §4):** a seção "Correlação
> onset → fix real" abaixo, que reportou 3/3 (100%) como evidência de
> precisão, foi invalidada por um teste de controle subsequente. A
> probabilidade de uma janela aleatória de 15 commits conter um commit
> "fix-like" é de 94-100% neste e em outros 7 repositórios testados — ou
> seja, o "100%" mede a taxa-base do corpus, não uma propriedade real da
> detecção de onset do UCO. Mantendo o texto original abaixo por
> integridade do histórico, mas **não trate isso como evidência de
> precisão** sem reler a correção.

> Primeira execução **real** (não sintética) do protocolo E1/E4 de
> `paper/experiments.md`, usando dados reais via GitHub API em vez de
> `git clone` (bloqueado neste sandbox). Metodologia em
> `paper/corpus_runner.py`.

## Metodologia

1. 80 commits reais que tocaram `src/requests/` (mais antigo → mais
   recente), obtidos via GitHub REST API (`/commits?path=...`).
2. Conteúdo de cada um dos 19 arquivos `.py` em cada um desses 80
   commits, obtido via Contents API.
3. **Replay** desses snapshots em um repositório git local "shadow"
   (80 commits locais reais, com data/mensagem originais preservadas
   via `upstream-sha:<sha>` no corpo do commit).
4. `scan.git_history_scanner.GitHistoryScanner` (não modificado) rodado
   contra o shadow repo — pipeline real: `git log` → `git show` →
   `UCOBridge`/lang_adapters → `FrequencyEngine`.
5. `sast.scanner.scan` rodado contra o snapshot mais recente de cada
   arquivo (achados pontuais, sem componente temporal).
6. Correlação: para cada `onset_commit` detectado pelo UCO Sensor,
   verificamos se a mensagem do commit "real" correspondente (via
   `upstream-sha`) é seguida (≤15 commits) por algum commit com
   linguagem de fix/bug/security — proxy barato de "o decaimento que o
   UCO sinalizou correspondeu a algo que os maintainers de fato tiveram
   que corrigir depois".

Este runner é genérico — não há nada hardcoded para `requests`. Pode
ser reaplicado a `flask`, `django` etc. trocando `--owner/--repo/--subdir`.

## Resultados — análise temporal (E1)

| Arquivo | Severidade | Padrão primário | Hurst | Onset upstream | Confiança |
|---|---|---|---|---|---|
| `sessions.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.844 | — | 0.685 |
| `models.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.723 | `e50e5945294f` | 0.686 |
| `adapters.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.979 | `18ed4216e262` | 0.742 |
| `utils.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.972 | — | 0.755 |
| `compat.py` | WARNING | GOD_CLASS_FORMATION | 0.976 | — | 0.740 |
| `_types.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.884 | — | 0.759 |
| `exceptions.py` | WARNING | COGNITIVE_COMPLEXITY_EXPLOSION | 0.979 | — | 0.644 |
| `__init__.py` | WARNING | TECH_DEBT_ACCUMULATION | 0.932 | `561e4b6889f5` | 0.542 |
| `packages.py` / `status_codes.py` / `__version__.py` | INFO | DEAD_CODE_DRIFT / GOD_CLASS_FORMATION | — | — | baixa |

**0 arquivos CRITICAL, 8 WARNING.** Nenhum falso-negativo grosseiro
óbvio: `sessions.py` — citado explicitamente em `experiments.md` como
"documented god-class anti-pattern" — foi de fato sinalizado, embora
classificado como `COGNITIVE_COMPLEXITY_EXPLOSION` em vez de
`GOD_CLASS_FORMATION` (achado relacionado, taxonomia diverge — ver
"Limitações" abaixo).

## Correlação onset → fix real (proxy de precisão)

3 dos 8 arquivos WARNING tinham `onset_commit` detectável (os outros 5
não tiveram onset_commit resolvido pelo `ChangePoint` — não é um
problema do runner, é o `FrequencyEngine` não encontrando um ponto de
mudança claro dentro da janela de 80 commits, comum quando o decaimento
é gradual/sem mudança de regime nítida).

Dos 3 com onset resolvido, **100% (3/3)** têm um commit de
fix/bug/segurança real nos 15 commits seguintes ao onset no mesmo
arquivo — incluindo um caso direto:

> `adapters.py` onset → 4 commits depois: **"Add more tests to prevent
> regression of CVE 2024 47081"**.

Isso é evidência (amostra pequena, N=3) de que o sinal de onset não é
ruído — está temporalmente alinhado com decisões reais de manutenção.

## SAST pontual (E4, parcial)

17 achados reais no snapshot mais recente de `src/requests/`:

| Regra | Severidade | Achados | Observação |
|---|---|---|---|
| SAST038 Exception Swallowing | LOW | 6 | `compat.py`, `models.py`, `sessions.py`, `utils.py` (×2) |
| SAST044 Adjacent Duplicate Statement | LOW | 3 | `models.py` |
| SAST025 Timing Attack via String Comparison | MEDIUM | 3 | `auth.py` |
| SAST006 Weak Cryptographic Algorithm | MEDIUM | 3 | `auth.py` |
| SAST042 No-Op Self-Assignment | LOW | 2 | `compat.py` |

Nenhum achado HIGH/CRITICAL — esperado para um projeto maduro e bem
mantido como `requests`. SAST025/SAST006 em `auth.py` (comparação de
hash/timing em auth digest) merecem revisão manual — podem ser
falsos-positivos (uso interno controlado) ou achados reais de baixo
risco; não foram triados manualmente nesta rodada (E4 completo exige
isso, ver Limitações).

## Bug real encontrado durante a execução

O próprio `corpus_runner.py` quebrou na primeira tentativa:
`'SASTFinding' object has no attribute 'message'` — `SASTFinding` usa
`title`/`description`, não `message`. Corrigido no script. Não é um
bug do `uco-sensor` core, é um bug de integração do runner novo — mas
documentando porque achados "reais" só apareceram após o fix.

## Limitações desta rodada (honestas)

* **N=1 repositório, 80 commits** — não é o corpus completo de 5 repos
  / 200-500 commits do `experiments.md`. É um MVP para validar que o
  *método* (shadow-replay via API) funciona antes de escalar.
* **Taxonomia onset**: `sessions.py` foi sinalizado como complexidade
  cognitiva, não "god class" — pode ser uma diferença legítima de
  classificação (a métrica relevante mudou) ou um gap de
  generalização do classificador; não investigado a fundo aqui.
* **5/8 arquivos WARNING sem onset resolvido** — o `ChangePoint` não
  convergiu dentro da janela de 80 commits; precisaria de janela maior
  para esses casos.
* **Sem comparação com SonarQube/CodeQL/Semgrep** (E4 completo) — essas
  ferramentas não estão disponíveis neste ambiente; E4 nesta rodada é
  "UCO Sensor apenas", não comparativo.
* **Sem revisão manual de falso-positivo** (a tabela T4 do protocolo
  pede revisão manual de 20 amostras) — com apenas 17 achados totais,
  triagem manual é viável e é o próximo passo natural, não feito ainda.

## Próximo passo sugerido

Se este MVP validar a abordagem para você, Sprint AC-2 escalaria para:
`flask` e `django` (já listados em `experiments.md`), com mais commits
(150-200) e triagem manual dos achados SAST para estimar taxa de falso
positivo real — fechando T1/T4 do protocolo com dados de corpus em vez
de sintéticos.
