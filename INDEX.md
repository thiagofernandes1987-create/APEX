# APEX Index — Hub de Navegação

**WHY**: Este arquivo é o ponto de entrada para qualquer LLM navegando o repositório APEX.
**WHEN**: Lido automaticamente no STEP_0 de boot quando `apex_superrepo.last_known_index_session` está desatualizado.
**HOW**: Parse do bloco `domain_map` (YAML) → registrar skills como PROVISIONAL → atualizar `skill_registry`.

---

## Como Encontrar Qualquer Skill em ≤ 3 Passos

```
PASSO 1: Identifique o domínio do seu problema no domain_map abaixo
PASSO 2: Navegue para skills/{domínio}/README.md
PASSO 3: Leia o SKILL.md do skill específico
```

---

## Domain Map (machine-parseable YAML)

```yaml
domain_map:
  MATHEMATICS:
    path: skills/mathematics/
    anchors: [algebra, calculus, statistics, financial_math, optimization, linear_algebra, geometry]
    sub_domains:
      algebra:
        path: skills/mathematics/algebra/
        anchors: [equation, polynomial, matrix, variable, coefficient, roots]
        sub_domains:
          equations:
            path: skills/mathematics/algebra/equations/
            anchors: [linear, quadratic, cubic, transcendental, systems]
            skills:
              - skill: mathematics.algebra.equations.linear-systems
                path: skills/mathematics/algebra/equations/linear-systems/SKILL.md
                anchors: [linear, equation, matrix, gaussian, cramer, systems]
                status: ADOPTED
              - skill: mathematics.algebra.equations.quadratic
                path: skills/mathematics/algebra/equations/quadratic/SKILL.md
                anchors: [quadratic, discriminant, parabola, roots, formula_bhaskara]
                status: PROVISIONAL
      calculus:
        path: skills/mathematics/calculus/
        anchors: [derivative, integral, limit, optimization, differential_equation]
        sub_domains:
          optimization:
            path: skills/mathematics/calculus/optimization/
            anchors: [gradient, minimum, maximum, convex, lagrange, KKT]
            skills:
              - skill: mathematics.calculus.optimization.gradient-descent
                path: algorithms/optimization/gradient-descent/ALGORITHM.md
                anchors: [gradient, descent, learning_rate, convergence, loss_function]
                status: ADOPTED
      financial_math:
        path: skills/mathematics/financial-math/
        anchors: [compound_interest, present_value, future_value, amortization, inflation, IGPM, IPCA]
        cross_domain_bridges:
          - to: legal.civil_law.contracts.financial_clauses
            strength: 0.95
            reason: "Contratos com cláusulas de reajuste IGPM/IPCA requerem cálculo financeiro"
          - to: finance.valuation.DCF
            strength: 0.85
            reason: "DCF usa taxa de desconto composta"
        skills:
          - skill: mathematics.financial_math.compound_interest
            path: skills/mathematics/financial-math/compound-interest/SKILL.md
            anchors: [compound_interest, juros_compostos, VF, VP, taxa, periodo, SELIC, montante]
            status: ADOPTED
          - skill: mathematics.financial_math.inflation_adjustment
            path: skills/mathematics/financial-math/inflation-adjustment/SKILL.md
            anchors: [IGPM, IPCA, INPC, correcao_monetaria, indice, inflacao, fator_correcao]
            status: ADOPTED
      statistics:
        path: skills/mathematics/statistics/
        anchors: [probability, distribution, inference, regression, bayesian, hypothesis_test]
        skills:
          - skill: mathematics.statistics.bayesian
            path: skills/mathematics/statistics/bayesian/SKILL.md
            anchors: [bayesian, prior, posterior, likelihood, mcmc, omega_bayes]
            status: ADOPTED

  LEGAL:
    path: skills/legal/
    anchors: [contrato, obrigacao, responsabilidade, codigo_civil, clt, cdc, processo, artigo]
    sub_domains:
      civil_law:
        path: skills/legal/civil-law/
        anchors: [codigo_civil, contrato, obrigacao, mora, inadimplemento, responsabilidade]
        sub_domains:
          contracts:
            path: skills/legal/civil-law/contracts/
            anchors: [contrato, clausula, inadimplemento, rescisao, formacao, objeto, causa]
            sub_domains:
              financial_clauses:
                path: skills/legal/civil-law/contracts/financial-clauses/
                anchors: [IGPM, IPCA, reajuste, juros_legais, art_406_cc, correcao_monetaria, multa]
                cross_domain_bridges:
                  - to: mathematics.financial_math.compound_interest
                    strength: 0.90
                    reason: "Art. 406 CC → SELIC = taxa de juros legal = juros compostos"
                  - to: mathematics.financial_math.inflation_adjustment
                    strength: 0.95
                    reason: "Cláusula de reajuste monetário exige cálculo de índice inflacionário"
                skills:
                  - skill: legal.civil_law.contracts.financial_clauses
                    path: skills/legal/civil-law/contracts/financial-clauses/SKILL.md
                    anchors: [IGPM, IPCA, art_406_cc, juros_legais, multa, reajuste, contrato]
                    status: ADOPTED
          obligations:
            path: skills/legal/civil-law/obligations/
            anchors: [obrigacao, devedor, credor, mora, art_394_cc, inadimplemento, vencimento]
            cross_domain_bridges:
              - to: mathematics.financial_math.compound_interest
                strength: 0.85
                reason: "Art. 406 CC → juros legais = SELIC (capitalização composta)"
            skills:
              - skill: legal.civil_law.obligations
                path: skills/legal/civil-law/obligations/SKILL.md
                anchors: [obrigacao, mora, art_394_cc, art_406_cc, devedor, credor]
                status: ADOPTED
      consumer_law:
        path: skills/legal/consumer-law/
        anchors: [CDC, consumidor, fornecedor, vicio, defeito, art_18_cdc, dano_moral]
      labor_law:
        path: skills/legal/labor-law/
        anchors: [CLT, empregado, empregador, rescisao, FGTS, aviso_previo, hora_extra]
      procedural_law:
        path: skills/legal/procedural/
        anchors: [CPC, processo_civil, contestacao, recurso, prazo, sentenca, execucao]

  ENGINEERING:
    path: skills/engineering/
    anchors: [architecture, algorithms, testing, security, apis, microservices, devops]
    sub_domains:
      software:
        path: skills/engineering/software/
        anchors: [design_pattern, architecture, api, database, testing, performance]
        sub_domains:
          architecture:
            path: skills/engineering/software/architecture/
            anchors: [C4, microservices, monolith, hexagonal, DDD, CQRS, event_driven]
          algorithms:
            path: skills/engineering/software/algorithms/
            anchors: [complexity, sorting, graph, dynamic_programming, data_structure]
            cross_domain_bridges:
              - to: mathematics.calculus.optimization
                strength: 0.65
                reason: "Otimização de algoritmos usa gradiente e derivadas"
      data:
        path: skills/engineering/data/
        anchors: [ETL, pipeline, schema, SQL, NoSQL, streaming, governance]
      security:
        path: skills/engineering/security/
        anchors: [OWASP, auth, encryption, vulnerability, penetration_testing]

  SCIENCE:
    path: skills/science/
    anchors: [hypothesis, simulation, bayesian, machine_learning, llm, physics, statistics]
    sub_domains:
      ai_ml:
        path: skills/science/ai-ml/
        anchors: [supervised, unsupervised, reinforcement, neural_network, llm, fine_tuning, rag]
        sub_domains:
          llm:
            path: skills/science/ai-ml/llm/
            anchors: [prompting, agents, evaluation, safety, alignment, apex, cognitive_modes]
      physics:
        path: skills/science/physics/
        anchors: [mechanics, thermodynamics, electromagnetism, quantum, relativity]

  FINANCE:
    path: skills/finance/
    anchors: [valuation, DCF, WACC, portfolio, derivatives, risk, accounting]
    sub_domains:
      valuation:
        path: skills/finance/valuation/
        anchors: [DCF, comparable, precedent, LBO, sum_of_parts, terminal_value]
        cross_domain_bridges:
          - to: mathematics.financial_math.compound_interest
            strength: 0.85
            reason: "DCF usa VPL com taxa de desconto composta"
      risk_management:
        path: skills/finance/risk/
        anchors: [VaR, CVaR, monte_carlo, stress_test, credit_risk, market_risk]
        cross_domain_bridges:
          - to: mathematics.statistics.bayesian
            strength: 0.75
            reason: "Modelos de risco usam probabilidade bayesiana"

  APEX_INTERNALS:
    path: skills/apex_internals/
    anchors: [ForgeSkills, BDS_simplex, R_acum, cognitive_mode, DIFF_governance, attraction_engine]
    sub_domains:
      forgeskills:
        path: skills/apex_internals/forgeskills/
        skills:
          - skill: apex_internals.forgeskills
            path: skills/apex_internals/forgeskills/SKILL.md
            anchors: [ForgeSkills, dynamic_skill_forge, git_clone, AST_scan, trusted_domains]
            status: ADOPTED
      cognitive_modes:
        path: skills/apex_internals/cognitive-modes/
        anchors: [EXPRESS, FAST, DEEP, RESEARCH, SCIENTIFIC, FOGGY, CLARIFY, BDS_simplex]
```

---

## DIFF Registry

| OPP | DIFF ID | Tipo | Status | Descrição |
|-----|---------|------|--------|-----------|
| OPP-104 | DIFF_GITHUB_SUPERREPO_BOOT | PARAMETRIC | PROPOSED | GitHub super-repo como trusted_domain + boot automático |
| OPP-105 | DIFF_MULTI_LLM_ADAPTER | STRUCTURAL | PROPOSED | Adaptador multi-LLM com degradação graciosa |
| OPP-106 | DIFF_FORGESKILLS_RAPID_READER | PARAMETRIC | PROPOSED | Pipeline 4-estágios para leitura rápida de repositórios |
| OPP-107 | DIFF_HYPERBOLIC_ANCHOR_MAP | PARAMETRIC | PROPOSED | Taxonomia hierárquica completa + bridges cross-domínio |
| OPP-108 | DIFF_ZERO_AMBIGUITY_CODE | OPERATIONAL | PROPOSED | Padrão WHY/WHEN/HOW/WHAT_IF_FAILS obrigatório |
| OPP-109 | DIFF_LLM_AGNOSTIC_FORGESKILLS | PARAMETRIC | PROPOSED | ForgeSkills via urllib para LLMs sem git clone |

Ver detalhes: `diffs/v00_33_0/`

---

## Versão

- **Repo criado**: 2026-04-08
- **APEX version**: v00.33.0
- **DIFFs aplicados**: 91 (86 herdados de v00.32.1 + 5 novos)
- **Skills registradas**: 0 atualmente → populadas via ForgeSkills
