# Classificação do APEX (notas 0–10) + caminho para um framework cognitivo

Avaliação após a autópsia científica completa (prompt v00.39.1 + skill apex-method v1.21.0).
Notas são **realistas e justificadas por evidência executável** (benchmark, boot integrity,
rubrica objetiva) — não otimismo. Escala: 0 = ausente · 5 = funcional com ressalvas · 8 = sólido
e testado · 10 = estado da arte comprovado.

## 1. Notas por aspecto

| # | Aspecto | Nota | Justificativa (evidência) |
|---|---|---:|---|
| 1 | **Pipeline / máquina de estados** | 8.5 | STEP_0→13 + STEP_SCI, express-check real, modos com orçamento; testado ponta a ponta. Perde 1.5 por partes serem instrução ao LLM, não código. |
| 2 | **Controle de custo por modo** | 9.0 | EXPRESS→SCIENTIFIC com teto de agentes e `n_final=min(n_num,n_rel,MAX)` real; agora com modos prediletos persistidos. |
| 3 | **Camada bayesiana** | 9.5 | beta-binomial, Ω (0.72/0.5), R_acum janela-20 — matematicamente correta e reproduzida (0.75→ADOPT). O ativo mais forte. |
| 4 | **Motores numéricos (PoT/RK4/sympy)** | 9.0 | subprocess isolado encadeado, RK4 erro ~1e-8, verify formal; degradam sem sympy. |
| 5 | **Monte Carlo real** | 8.5 | P10/P50/P90+CV, ligado ao PMI, numpy opcional. Honesto (só quando codável). |
| 6 | **UCO / qualidade de código** | 8.0 | 9 canais espectrais, gate SR_33 real; −2 porque o limiar é de snippet, sem sinal de módulo. |
| 7 | **UCO-Sensor (SAST/SCA/taint)** | 6.5 | autoral e potente, mas roda como serviço — indexado, não embarcável inteiro. |
| 8 | **Governança (8C/44SR/18G/7H)** | 7.5 | SR_36–40 enforçadas em código; o resto é política (LLM_BEHAVIOR). Agora 44 SRs documentadas. |
| 9 | **Sistema de agentes (213)** | 7.0 | roteamento por competência sólido; −3 porque são **personas sequenciais**, não paralelismo cognitivo. |
| 10 | **Gravidade / atração de recursos** | 7.5 | TF-IDF×massa real + fallback char-n-gram bilíngue; −2.5 por ainda ser lexical, não embeddings profundos. |
| 11 | **Descoberta de skills (nativa/skills.sh/GitHub)** | 8.5 | cascata com critério ≥1000 installs, tier oficial, H5; degradação offline. |
| 12 | **Integração do repositório** | 9.0 | 3.784 skills + 213 agentes + 111 páginas endereçáveis via `repo_bridge`, allowlist+pin. |
| 13 | **Segurança (supply-chain, sandbox)** | 8.0 | V-01/V-02/V-03 corrigidas, AST-scan+H5; −2 porque o scan é best-effort, não sandbox. |
| 14 | **Aprendizado entre sessões** | 6.0 | code_genetics (SQLite opcional) + apex_st_metric reais; mas o "aprendizado" é bookkeeping, não atualização de pesos. |
| 15 | **Persistência / memória** | 5.5 | snapshot vive no contexto; sem memória vetorial viva entre sessões (o índice é build-time). |
| 16 | **Multiagente paralelo real** | 3.0 | é perspectiva **sequencial** + ThreadPool só na execução de subprocessos; sem concorrência cognitiva. |
| 17 | **Testabilidade / reprodutibilidade** | 9.5 | benchmark 31→34, rubrica 13/13, boot 111/111 sha8, ambiente-limpo — tudo executável. |
| 18 | **Honestidade epistêmica** | 9.5 | separa 🟢real/🔵LLM/🟣metáfora; `[APPROX]`, `[CONJECTURA_FORMAL]`; anti-pattern de "Monte Carlo qualitativo". |
| 19 | **Documentação / rastreabilidade** | 8.5 | 18 refs + inventário + 2 auditorias + diffs FMEA/RPN; −1.5 por drift histórico já corrigido. |
| 20 | **Vocabulário quântico (retórica)** | 2.0 | superposição/interferência/decoerência = decorativo; não computa. Peso morto conceitual. |

**Média ponderada realista: ≈ 7.5/10** — um framework de **engenharia de raciocínio** sólido
e testável, puxado para baixo por três coisas: multiagente que não é paralelo (16), memória viva
ausente (15) e retórica quântica (20).

## 2. O que falta para virar um FRAMEWORK COGNITIVO (não só de raciocínio)

Hoje o APEX é um **motor de raciocínio disciplinado**. Para ser *cognitivo* no sentido pleno,
faltam cinco capacidades — nenhuma é retórica, todas são construíveis:

1. **Memória viva entre sessões (nota 15 → alvo 9).** Um store vetorial persistente (episódico +
   semântico) que é *lido e atualizado* a cada sessão, não reconstruído em build-time. Sem isso
   não há continuidade cognitiva — só re-leitura de snapshot.
2. **Paralelismo cognitivo real (nota 16 → alvo 8).** Hoje as "perspectivas" são sequenciais.
   Cognição precisa de agentes que rodem de fato concorrentes (múltiplas chamadas LLM em paralelo
   com merge) — o `entropy_weighted_merge` já existe; falta o executor concorrente de *geração*.
3. **Auto-modelo / metacognição executável.** O `apex_st_metric` mede estagnação, mas falta um
   modelo explícito de "o que eu sei / não sei / erro sistematicamente" que realimente o
   planejamento (o `sklearn_self_difficulty` do repo é o embrião).
4. **Aprendizado que muda comportamento (nota 14 → alvo 8).** code_genetics guarda erro→correção,
   mas não altera priors/políticas de forma persistente e medível. Falta o loop
   experiência→política com validação estatística viva.
5. **Grounding perceptual / ferramentas do mundo.** Um framework cognitivo age sobre o mundo
   (web, código, dados) em ciclo perceber→agir→observar. O `deep_research` (novo) é o primeiro
   passo real disso — falta fechar o ciclo com execução e observação de efeito.

**Resumo:** falta **memória viva + concorrência real + metacognição + aprendizado que persiste +
ciclo perceber-agir**. Com isso, sai de "raciocínio governado" (7.5) para "cognição" (9+).

## 3. Oportunidades de melhoria identificadas (priorizadas)

| Prioridade | Oportunidade | Estado |
|---|---|---|
| P1 | Memória vetorial viva entre sessões (episódica+semântica) | aberto (pesquisa) |
| P1 | Executor de geração concorrente (paralelismo cognitivo) | aberto |
| P2 | Embeddings reais (substituir TF-IDF lexical de vez) | mitigado (char-n-gram); transformer opcional |
| P2 | Metacognição executável (auto-modelo de competência) | embrião no repo (sklearn_self_difficulty) |
| P2 | UCO como serviço embutível parcial (SAST leve inline) | aberto |
| P3 | Aprendizado que altera priors com validação estatística | code_genetics é a base |
| P3 | Remover/segregar o vocabulário quântico decorativo | cosmético |
| ✅ | dissect bilíngue + semântico · grant p/ 213 · menu (update/modos/research) | **FEITO nesta rodada** |

*Documento produzido durante a auditoria; notas revisáveis contra o benchmark e a rubrica.*
