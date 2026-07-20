# ⚖️ Avaliação Honesta e Imparcial — `apex-method` v1.60.0

> Escrita após uma bateria extensa de testes reais nesta sessão: auditoria de segurança, execução de todos os módulos, stress test (real + adversarial), teste por modos operacionais, verificação da memória swap, e construção/validação da cascata de descoberta. **Nada afirmado sem observação.** O avaliador não é o autor da skill — a intenção é ser justo, não elogioso.

---

## 1. Veredito em uma linha

Uma skill **ambiciosa e bem-engenheirada** — um "runtime cognitivo" que entrega de verdade nos fundamentos (computação exata, memória persistente, descoberta segura, degradação honesta) — mas que **paga um preço em complexidade** e cujo valor depende fortemente de o LLM invocá-la corretamente. **Nota global: 7,8 / 10.**

---

## 2. Como ela se comporta (observado)

- **Roda em stdlib puro.** Neste runtime não havia numpy/scipy/sklearn/sympy e mesmo assim **70/70** testes passam. A degradação é real e honesta (verify vira `CONJECTURA_FORMAL` em vez de blefar; RAG cai para char-n-gram).
- **Determinística e resiliente.** `orchestrator.run` nunca levanta (contrato de erro), resiste a inputs malformados (`None`/int/dict/20k chars/unicode/prompt-injection), o PoT mata loop infinito no timeout, captura crash, faz scrub de segredos e capa a saída. Throughput medido: **8,6 runs/s**, 50 execuções sem crash.
- **Memória persistente que funciona de verdade.** Provei o ciclo page-out → **home novo** → page-in: memória, ledger, aprendizado promovido e as escolhas (`skill_ledger`) sobrevivem entre "máquinas". Compressão ~2,7×.
- **Não é perfeita "de fábrica".** Durante os testes encontrei **bugs reais** na versão distribuída: path traversal (C-01, PoC), bypasses do scanner AST (C-04, PoC), testes flaky (N-02), e over-rejection na descoberta GitHub (N-04). Todos corrigidos e testados — mas existiam.

---

## 3. Pontos fortes

1. **Computação exata e verificável** — PoT encadeado, RK4 (erro < 1e-3 vs analítico), Monte Carlo, verificação simbólica. É a razão de ser da skill e ela cumpre.
2. **Economia de tokens real nos caminhos comuns** — EXPRESS ~99%, STANDARD ~73% vs "rodar tudo". A maioria do tráfego real economiza.
3. **Memória/atração plug-and-play** — estado promovido (agentes/skills/diffs) num bundle assinado que restaura por Drive / pasta-pendrive / ZIP. Infraestrutura verificada 20/20 (pastas, nomenclatura, backups, hashes que sobrevivem).
4. **Segurança madura** — allowlists, AST 2 níveis, injection-scan, gate humano H5, SQL parametrizado, sem segredos, sem `shell=True`. Trilha de auditoria embutida (SEC/RT/AUD).
5. **Portabilidade e honestidade** — funciona offline, degrada sem mentir, e cada ferramenta documenta seu modo de falha.
6. **Suíte de testes forte** — 70 testes + rubrica ponderada + auditoria comportamental E2E; hermética e determinística (após correções).

## 4. Pontos fracos

1. **Complexidade / over-engineering.** 55 módulos e um vocabulário pesado (gravity, geodesic, fractal, `apex_st_metric`, "constelação", "curvatura"). Parte disso agrega; parte é **cerimônia** cujo ganho marginal é difícil de justificar. A superfície de manutenção é grande.
2. **Dependência do LLM.** Muito do "orquestrador" são **instruções que o LLM precisa seguir**, não código que força o comportamento. O Python é real (PoT, memória, guards), mas a disciplina de modos/passagem-de-bastão depende do modelo cooperar.
3. **Economia de tokens some nos modos caros.** De FOGGY para cima a economia vs naïve é **0** — os modos altos rodam o plano completo. O overhead de proveniência/checklist também consome tokens.
4. **Qualidade semântica limitada sem aceleradores.** O fallback char-n-gram ranqueia bem em inglês, mas **fraco em português** (scores ≤ 0,13); a gravidade tem raios calibrados para sklearn e puxa poucos corpos no fallback.
5. **Over-escalação de modo.** Tarefas de classe não-reconhecida escalam para DEEP por design conservador (documentado, testado) — mas na prática infla o custo de tarefas simples não-familiares.
6. **Higiene de catálogos.** Índices derivados guardam caminhos absolutos e alternam `measured/estimated` — churn não-portátil entre máquinas.
7. **Dependência de rede em tiers de descoberta.** skills.sh e a API de busca do GitHub são bloqueáveis (foram, neste sandbox); a skill degrada para curated/raw, mas a descoberta "rica" precisa de rede/token.

## 5. Oportunidades de melhoria

- **Poda geodésica dentro de DEEP/SCIENTIFIC** (early-exit por confiança) para render economia também nos modos caros.
- **Aceleradores opcionais on-demand** (sympy → sklearn) via instalador opt-in, resolvendo RAG-PT e calibração de gravidade sem quebrar a portabilidade.
- **Simplificação/consolidação**: fundir os dois gates AST (feito, C-07), unificar métricas exóticas pouco usadas, e cachear fetches de descoberta (hoje refaz 14 requests por busca).
- **Normalizar catálogos** (paths relativos) para determinismo entre máquinas.
- **Ampliar `DIFFICULTY_REFS`** com âncoras de tarefas simples para reduzir over-escalação.

---

## 6. Notas (0 a 10)

| Dimensão | Nota | Justificativa (observada) |
|---|---:|---|
| **Arquitetura** | **8,0** | Modular, coerente, degrada bem, reusa plumbing; mas over-engineered e parcialmente dependente do LLM |
| **Estabilidade** | **8,5** | 70/70, nunca-levanta, resiste a adversarial; −1,0 pelos bugs reais achados na versão distribuída (corrigidos) |
| **Desempenho** | **7,5** | Runtime rápido (2–380 ms), compute exato; RAG-PT fraco, alguns testes pesados, ranking limitado sem sklearn |
| **Consumo de tokens** | **7,5** | Economia real e alta nos caminhos comuns; zero nos modos caros + overhead de proveniência |
| **Custo-benefício** | **7,0** | Alto valor em math/audit/multi-step com memória; a cerimônia e a dependência do LLM diluem o retorno em tarefas simples |
| **Segurança** | **8,0** | Gates maduros, H5, sem segredos; limites inerentes do scanner estático + bugs achados |
| **Documentação** | **7,5** | Extensa (spec/doc/inventário/refs); estava defasada (contagens, módulos novos) até esta sessão |
| **Testes / QA** | **8,5** | Suíte forte, hermética, determinística; rubrica + cenários E2E |
| **GLOBAL (ponderada)** | **7,8** | Fundamentos sólidos e honestos; complexidade e dependência do LLM são o teto |

---

## 7. Para quem vale a pena

- **Vale muito:** trabalho de engenharia/ciência multi-passo, math/dinâmica real, auditorias, análise de causa-raiz, e qualquer fluxo que se beneficie de **memória entre sessões** e **computação verificável**.
- **Vale pouco:** tarefas triviais/pontuais (onde o EXPRESS já resolve e o resto é peso morto) ou ambientes que não conseguem sustentar a disciplina de modos.

## 8. Conclusão

`apex-method` é um artefato **acima da média** em maturidade, honestidade técnica e disciplina de testes — entrega computação exata, memória persistente comprovada e descoberta segura, tudo rodando em stdlib puro com degradação franca. Seus limites são **complexidade** (muita máquina para o retorno em casos simples), **dependência do LLM** (o runtime é seguido, não imposto) e **qualidade semântica** sem aceleradores. Corrigidos os bugs desta sessão, é uma base **confiável e previsível**; as melhorias listadas são de afinação e simplificação, não de reconstrução. **7,8 / 10 — sólida, ambiciosa, e honesta sobre o que é.**

*Avaliação conduzida a partir de execução real instrumentada ao longo de toda a sessão.*
