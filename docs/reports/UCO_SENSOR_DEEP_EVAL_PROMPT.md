# Prompt — Avaliação Profunda do UCO Sensor (debate multi-agente + relatório .md acionável)

> **Como usar este prompt:** cole o bloco inteiro abaixo (das linhas `# 1. CONTEXTO` até `# FIM DO PROMPT`) em um LLM com acesso ao código (Claude Code, Cursor Composer, Codex CLI, Aider, OpenAI o1/o3 com ferramentas, Gemini Code Assist). O LLM deve gerar **um único arquivo `UCO_SENSOR_DEEP_EVAL.md`** no diretório `algorithms/uco-sensor/` do repositório.
>
> O prompt está calibrado para gerar um relatório de **~3000-8000 palavras** com 30+ findings debatidos, fontes citadas linha-a-linha, ROI quantificado por item e transcrições de debate em anexo.

---

# 1. CONTEXTO

Você está auditando o **UCO Sensor** (`v3.9.1`), uma plataforma de análise espectral de qualidade de código.

**Localização do código:** `algorithms/uco-sensor/` neste repositório. Os pontos de partida obrigatórios para sua leitura inicial são (nesta ordem):

1. `algorithms/uco-sensor/inventario.md` — estado vivo + histórico de sprints + decisões científicas registradas + backlog deferred. **LEIA POR INTEIRO** antes de qualquer análise.
2. `algorithms/uco-sensor/UCO_SENSOR_ROADMAP.md` — WBS técnico + marcos M0-M60.
3. `algorithms/uco-sensor/sensor-api/CHANGELOG.md` — últimos 5 sprints (v3.7.0 → v3.9.1) com fixes detalhados, deferred backlog explícito, decisões registradas.
4. `algorithms/uco-sensor/sensor-api/README.md` — overview operacional + variáveis de ambiente.

**Arquitetura em uma frase:** REST API + Python lib que persiste **9 canais primários + 96 canais estendidos** de métricas de código ao longo do tempo (snapshots), aplica **PELT change-point**, **Granger causality F-test**, **DBSCAN signature discovery**, **HMC Bayesian repair**, **spectral fingerprint via Welch PSD**, e expõe **76+ endpoints REST** com **multi-tenant + unit-budget billing** (Sprint Y) e **5 invariantes formais executáveis** (Sprint Z).

**Stack:** Python 3.11+, SQLite (snapshots/anomalies/api_keys/remediations/discovered_signatures/marketplace_signatures/tenants/usage_events), opcional Redis cache, opcional Starlette ASGI, opcional tree-sitter para multi-lang SAST, scipy/numpy/PyWavelets.

**Métricas atuais que você deve confirmar lendo o repo:**
- 2145 testes passando, 0 falhas
- 76+ endpoints REST (18 com unit-budget billing wired)
- 8 tabelas SQLite
- 5 invariantes formais (I1-I5 em `governance/invariants.py`)
- 4 artefatos de paper (`paper/{paper.tex, references.bib, experiments.md, reproducibility.py}`)
- Backlog deferred conhecido: hot-row contention `tenants.units_used` (v3.9.2), N+1 em `recompute_derived_pending`, expansão de corpus para experimentos do paper (v3.9.2)

---

# 2. SUA MISSÃO

Conduzir uma **avaliação profunda** com saída em **um único relatório .md detalhado** cobrindo, no mínimo:

| # | Dimensão | Saída esperada |
|---|---|---|
| 1 | **Quantificação do estado atual** | Health score 0-100 composto + breakdown por subsistema |
| 2 | **Falhas de segurança** | Findings inéditos (não duplicar gate-1/gate-2/QA Loop já registrados) |
| 3 | **Novos canais de métrica** | Propostas + canais "capturados mas não calculados" (dormant) que dão alto ROI ativar |
| 4 | **Melhorias de scanners (SAST/SCA/IaC)** | Regras novas + cobertura faltante |
| 5 | **Novos scanners** | Categorias não cobertas (ex.: license compliance, secrets-in-history, container-image SBOM) |
| 6 | **Tecnologias emergentes para sinergia** | LSP, eBPF, SBOM (CycloneDX/SPDX), OPA/Rego, SLSA, RAG embeddings sobre canais espectrais, etc. |
| 7 | **Quick-wins alto ROI** | Items que entregam ≥5x valor por hora investida |
| 8 | **Reflexão arquitetural** | Tensões estruturais (acoplamento, dívida técnica oculta, evolvabilidade) |
| 9 | **Roadmap proposto** | v3.9.2 / v4.0.0 / v4.1.0 com priorização justificada |
| 10 | **Debate transcripts (anexo)** | Para cada P0/P1 finding, registro da contraposição entre agentes |

---

# 3. EQUIPE DE AGENTES — DEBATE OBRIGATÓRIO

Você deve operar como **7 agentes especializados em paralelo**, cada um com lente distinta. Nenhum finding entra no relatório principal **sem passar pelo "challenge round"** descrito na §4.

| Agente | Lente | Critério primário |
|---|---|---|
| 🏛️ **Architect** | Acoplamento, blast radius, evolvabilidade, abstrações vazadas | "Posso trocar a implementação X sem cascata?" |
| 🔒 **Security Engineer** | OWASP top-10, supply-chain, secrets, AuthN/AuthZ, multi-tenant isolation, ReDoS, SSRF | "Um caller anônimo / cross-tenant pode obter X que não deveria?" |
| ⚡ **Performance Engineer** | Hot paths, N+1, locks, cache eficiência, perfil de I/O, memory | "Sob 1000 RPS isto serializa em qual ponto?" |
| 📊 **Data Scientist** | Sinais informativos vs ruído, canais correlacionados redundantes, gaps de cobertura métrica | "Qual canal posso DESLIGAR sem perder sinal? Qual canal está dormente?" |
| 🧪 **SAST/SCA Specialist** | Regras faltando, false-positive rate, cobertura por linguagem, taxonomia CWE | "Qual classe de vulnerabilidade um competidor (CodeQL/Semgrep) flagga e nós não?" |
| 🚀 **Innovation Strategist** | Tecnologias emergentes 2025-2026 aplicáveis (LLM-as-judge, eBPF tracing, SBOM SLSA, embeddings vetoriais, OPA policy) | "O que adicionado em 4 dias multiplica capacidade em 3x?" |
| 🎯 **Product / Customer Voice** | Onboarding atrito, time-to-first-value, API ergonomia, ausências óbvias, naming, docs | "O cliente novo consegue ir de zero a primeira insight em < 30 min?" |

---

# 4. PROTOCOLO DE DEBATE

**Para CADA finding proposto por um agente:**

### 4.1 Challenge round (obrigatório)

Selecione 2 outros agentes (escolhidos pela maior relevância adversarial — ex.: Architect contesta Security via "isto é teoria, qual é a probabilidade real?"; Data Scientist contesta Innovation via "este canal duplica info do canal X já existente?").

Cada um dos 2 contestadores deve:
- **Tentar refutar** o finding com pelo menos 1 argumento técnico concreto.
- **Propor reformulação** (downgrade de severity, mudança de escopo, alternativa mais barata) OU **confirmar** com reasoning próprio.

### 4.2 Verdict

- **CONFIRMED**: ≥1 contestador confirma após tentativa séria de refutar.
- **DOWNGRADED**: ambos contestadores confirmam mas reduzem severity ou escopo.
- **REFUTED**: ambos contestadores apresentam refutação coerente — finding vai para anexo "Refuted" com motivo.

### 4.3 Anti-conluio

- Nunca pareie o mesmo agente como contestador na maioria dos findings (espalhar carga).
- Force pelo menos uma rodada de **adversarial steelman**: "qual é o MELHOR argumento de quem discorda?".

---

# 5. ANTI-ALUCINAÇÃO — RESTRIÇÕES DURAS

Findings que violem QUALQUER uma destas regras **devem ser deletados**, não apenas downgradeados:

1. **Citação obrigatória `file:line`**. Sem isso = especulação = remover.
2. **Sem APIs inventadas**. Antes de propor "use `governance.foo.bar()`", `grep` para confirmar que existe ou marcar explicitamente como "(módulo a criar)".
3. **Sem dependências fantasma**. "Use libX" só vale se libX está em `pyproject.toml` OU se você explicitamente diz "(nova dep, adicionar)".
4. **Impacto quantificado**. "Melhora performance" sem número = remover. Use unidades: ms, MB, % cov, # falsos positivos, # tenants suportados, etc. Se for estimativa, marque **`(estimado)`**.
5. **Distinção verificado vs hipótese**. Marque cada claim como **`[VERIFICADO]`** (leu o código), **`[HIPÓTESE]`** (precisa validação) ou **`[BENCHMARK NECESSÁRIO]`** (mensurável mas não medido).
6. **Não duplicar trabalho já feito**. Cheque `inventario.md` + `CHANGELOG.md` ANTES de propor. Itens já em backlog deferred não contam como achados novos — referencie-os.

---

# 6. FORMATO DE OUTPUT — `UCO_SENSOR_DEEP_EVAL.md`

### 6.1 Estrutura obrigatória

```markdown
# UCO Sensor — Avaliação Profunda (debate multi-agente)

> Gerado em: <data>
> Modelo: <nome do LLM>
> Sessão: <hash/run-id>
> Versão auditada: v3.9.1
> Rounds de debate executados: <N>
> Loop convergiu: <SIM / NÃO + motivo>

## §1. Executive Summary (≤ 250 palavras)
3 frases sobre estado atual + 3 sobre maior risco + 3 sobre maior oportunidade.

## §2. Quantitative Health Score
| Dimensão | Score 0-100 | Justificativa em 1 frase |
|---|---|---|
| Architecture coupling | | |
| Security posture | | |
| Test coverage adequacy | | |
| Performance headroom | | |
| Documentation completeness | | |
| Channel utilization | | |
| Innovation readiness | | |
| **COMPOSITE** | | (média ponderada com pesos justificados) |

## §3. Findings P0/P1 (CONFIRMED após debate)
Para CADA finding (mínimo 8, máximo 20):

### Finding #N — <título curto>
- **Categoria**: Security / Performance / Architecture / Channel / Scanner / Innovation / Product
- **Severidade**: P0 (crítico, blocker) | P1 (alto, sprint corrente)
- **ROI estimado**: <1-5 ★★★★★>
- **Effort estimado**: <S / M / L em pessoa-dias>
- **Owner sugerido**: <agente que descobriu>
- **POR QUÊ** (motivação técnica/negócio em 2-4 frases):
- **COMO IDENTIFICOU** (passo-a-passo da análise, com `file:line`):
- **COMO SUGERE FAZER** (plano de implementação em 3-7 bullets concretos):
- **IMPACTO** (quantificado, com unidade):
  - Antes: ...
  - Depois (estimado): ...
- **DEBATE** (resumo do challenge round):
  - 🏛️ Architect: <stance + argumento>
  - 🔒 Security: <stance + argumento>
  - ⚡ Perf / 📊 Data / 🧪 SAST / 🚀 Innov / 🎯 Product: <stance>
  - **Resolução**: <CONFIRMED por Y a X; ou DOWNGRADED por…>

## §4. Quick-Wins (alto ROI, ≤ 1 dia cada)
Tabela curta, 10-20 items:
| # | Item | ROI | Effort | Arquivo:linha | Justificativa em 1 linha |

## §5. Novos Canais de Métrica
Para CADA proposta (mínimo 5):
- **Nome**: ex. `git_blame_age_skew`
- **Categoria**: existing-but-dormant / novo
- **Sinal**: o que detecta
- **Fórmula matemática**:
- **Fonte de dados** (já existe ou precisa adicionar?):
- **Correlação esperada com canais existentes**: alta/baixa (justificar)
- **Custo de implementação**: LOC + dependências
- **Esforço de back-fill**: snapshots existentes podem retro-calcular?
- **Debate** (Data Scientist vs Architect):

## §6. Novos Scanners / Melhorias de Scanners Existentes
Subseções: **SAST**, **SCA**, **IaC**, **(novos)**.

Para cada item:
- Que classe de defeito cobre
- 3 exemplos concretos de regra/padrão
- Cobertura atual estimada (%)
- Cobertura pós-implementação (%)
- Comparação com competidores (Semgrep, CodeQL, SonarQube, Snyk, Bandit)

## §7. Tecnologias Emergentes — Synergy Map
Para CADA tecnologia (mínimo 4):
- **Nome + versão estável atual**:
- **O que adiciona** (1 frase):
- **Como se integra ao UCO** (módulo/endpoint/canal específico):
- **Maturidade**: experimental | beta | production-ready
- **Custo (LOC + dep)**:
- **Multiplicador esperado**: ex. "3x na descoberta de race conditions"
- **Debate** (Innovation vs Architect):

## §8. Reflexão Arquitetural — Tensões Estruturais
3-5 parágrafos densos sobre o que NÃO está bem mas tampouco é um bug discreto:
- Acoplamentos perigosos
- Abstrações vazando
- Dívida técnica oculta
- Riscos evolutivos (ex.: "v5.0 vai exigir reescrever X porque…")

## §9. Roadmap Proposto
| Versão | Foco | Items (links para §3) | Effort total | Riscos |
|---|---|---|---|---|
| v3.9.2 | | | | |
| v4.0.0 | | | | |
| v4.1.0 | | | | |
| v5.0.0 | | | | |

## §10. Métricas de Validação do Próprio Relatório
- Findings raw propostos antes do debate: N
- Findings CONFIRMED: N
- Findings DOWNGRADED: N
- Findings REFUTED: N (ver anexo)
- Citações `file:line` totais:
- Citações que verificam (rodando `grep`/`Read` agora): >95% sample
- Hipóteses não validadas: N (todas marcadas)

---

## Anexo A — Refuted Findings (motivo da refutação)
Para CADA finding REFUTED:
- Quem propôs:
- Quem refutou + argumento decisivo:
- Por que vale registrar mesmo refutado (para histórico anti-padrão):

## Anexo B — Debate Transcripts Completos
Para os top-5 findings mais controversos, transcrição completa (200-500 palavras cada) do debate.

## Anexo C — Verificações Pendentes
Lista de claims marcados [HIPÓTESE] ou [BENCHMARK NECESSÁRIO] que o time deveria validar antes de agir.
```

### 6.2 Critérios de qualidade do relatório

O relatório só é **aceitável** se:
- [ ] ≥ 30 findings totais (CONFIRMED + DOWNGRADED + REFUTED somados)
- [ ] ≥ 8 P0/P1 CONFIRMED com debate completo
- [ ] ≥ 10 quick-wins com `file:line`
- [ ] ≥ 5 novos canais propostos
- [ ] ≥ 3 tecnologias emergentes com integration path concreto
- [ ] 100% dos findings principais têm `file:line`
- [ ] 100% têm marca `[VERIFICADO]`/`[HIPÓTESE]`/`[BENCHMARK NECESSÁRIO]`
- [ ] Inventário foi lido (citar pelo menos 3 itens do backlog deferred ali registrados)
- [ ] Tamanho 3000-8000 palavras (denso, sem floreio)
- [ ] Toda recomendação tem impacto quantificado (sem "melhora X" sem número)

---

# 7. EXECUÇÃO — INSTRUÇÃO PASSO-A-PASSO PARA O LLM

1. **Leia primeiro** (na ordem, completos):
   - `algorithms/uco-sensor/inventario.md`
   - `algorithms/uco-sensor/UCO_SENSOR_ROADMAP.md`
   - `algorithms/uco-sensor/sensor-api/CHANGELOG.md` (primeiras 300 linhas)
   - `algorithms/uco-sensor/sensor-api/README.md`
2. **Mapeie a árvore** com `find algorithms/uco-sensor/sensor-api -name "*.py" | head -50` para localizar módulos.
3. **Para cada um dos 7 agentes**, faça uma passagem dedicada de exploração (use `grep`/`Read` extensivamente). Não confie em memória; cite linhas.
4. **Compile findings brutos** por agente (15-30 por agente).
5. **Execute o challenge round** descrito em §4 para cada finding candidato P0/P1.
6. **Dedupe** entre agentes (mesmo finding visto por dois agentes = um único item com co-owners).
7. **Loop de convergência** (opcional, recomendado): após escrever a §3, execute uma 2ª passada do agente que mais discordou e ofereça-lhe a chance de derrubar mais 2 findings. Pare quando uma rodada inteira não derruba nada (K=1 dry round suficiente).
8. **Escreva o relatório** seguindo a §6.1 EXATAMENTE.
9. **Auto-valide** contra a checklist da §6.2; corrija lacunas.
10. **Salve** em `algorithms/uco-sensor/UCO_SENSOR_DEEP_EVAL.md`.

---

# 8. TONE & STYLE

- **Direto, técnico, sem hype.** Evite "incrível", "revolucionário", "game-changer". Use números.
- **Português OU inglês, escolha um e mantenha.** O repo usa PT-BR em docs operacionais e EN em código/CHANGELOG.
- **Foco em acionabilidade.** Cada finding deve responder "o que eu faço amanhã de manhã?".
- **Honest assessment.** Se um subsistema está sólido, diga "este subsistema está sólido, não há findings de valor"; não fabrique problemas.
- **Reconheça incertezas.** "Não consegui validar X porque exige benchmark" é melhor que afirmação infundada.

---

# 9. ANTI-PATTERNS A EVITAR

- ❌ "Considerar usar microserviços" (sem análise de tradeoffs específicos).
- ❌ "Adicionar logging" (genérico — diga ONDE e POR QUÊ).
- ❌ "Aumentar cobertura de testes" (sem identificar caminho de código não coberto).
- ❌ "Refatorar para SOLID" (vago — qual princípio está sendo violado em qual classe).
- ❌ "Usar AI/ML/LLM" como recomendação sem caso de uso concreto + dataset + métrica de sucesso.
- ❌ Citar competidor sem identificar 1 capability concreta deles que faltaria aqui.
- ❌ "Considerar Rust/Go para performance" sem identificar bottleneck que justifica reescrita.

---

# 10. ENTREGA FINAL

Quando terminar, responda APENAS com:

```
Relatório gerado em: algorithms/uco-sensor/UCO_SENSOR_DEEP_EVAL.md
Estatísticas:
  - Palavras: <N>
  - Findings CONFIRMED: <N>
  - Findings DOWNGRADED: <N>
  - Findings REFUTED: <N>
  - Quick-wins: <N>
  - Novos canais: <N>
  - Tecnologias emergentes: <N>
  - Rounds de debate executados: <N>
  - Loop convergiu: <SIM/NÃO>
  - Health score composite: <0-100>
```

**FIM DO PROMPT.**
