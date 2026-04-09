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


  ANTHROPIC_OFFICIAL:
    path: skills/anthropic-official/
    anchors: [algorithmic, creating, seeded, brand, guidelines, applies, canvas, design]
    sub_domains:
      general:
        path: skills/anthropic-official/general/
        anchors: [algorithmic, creating, brand, guidelines, canvas, design]
        skills:
          - skill_id: anthropic_official.algorithmic_art
            path: skills/anthropic-official/algorithmic-art/SKILL.md
            anchors: [algorithmic, creating, seeded, randomness]
            status: ADOPTED
          - skill_id: anthropic_official.brand_guidelines
            path: skills/anthropic-official/brand-guidelines/SKILL.md
            anchors: [brand, guidelines, applies, anthropic]
            status: ADOPTED
          - skill_id: anthropic_official.canvas_design
            path: skills/anthropic-official/canvas-design/SKILL.md
            anchors: [canvas, design, create, beautiful]
            status: ADOPTED
          - skill_id: anthropic_official.claude_api
            path: skills/anthropic-official/claude-api/SKILL.md
            anchors: [claude, building, powered, applications]
            status: ADOPTED
          - skill_id: anthropic_official.doc_coauthoring
            path: skills/anthropic-official/doc-coauthoring/SKILL.md
            anchors: [coauthoring, guide, users, through]
            status: ADOPTED
          - skill_id: anthropic_official.docx
            path: skills/anthropic-official/docx/SKILL.md
            anchors: [docx, skill, whenever, user]
            status: ADOPTED
          - skill_id: anthropic_official.frontend_design
            path: skills/anthropic-official/frontend-design/SKILL.md
            anchors: [frontend, design, create, distinctive]
            status: ADOPTED
          - skill_id: anthropic_official.internal_comms
            path: skills/anthropic-official/internal-comms/SKILL.md
            anchors: [internal, comms, resources, help]
            status: ADOPTED
          - skill_id: anthropic_official.mcp_builder
            path: skills/anthropic-official/mcp-builder/SKILL.md
            anchors: [builder, guide, creating, high]
            status: ADOPTED
          - skill_id: anthropic_official.pdf
            path: skills/anthropic-official/pdf/SKILL.md
            anchors: [skill, whenever, user, wants]
            status: ADOPTED
          - skill_id: anthropic_official.pptx
            path: skills/anthropic-official/pptx/SKILL.md
            anchors: [pptx, skill, time, file]
            status: ADOPTED
          - skill_id: anthropic_official.skill_creator
            path: skills/anthropic-official/skill-creator/SKILL.md
            anchors: [skill, creator, create, skills]
            status: ADOPTED
          - skill_id: anthropic_official.slack_gif_creator
            path: skills/anthropic-official/slack-gif-creator/SKILL.md
            anchors: [slack, creator, knowledge, utilities]
            status: ADOPTED
          - skill_id: anthropic_official.theme_factory
            path: skills/anthropic-official/theme-factory/SKILL.md
            anchors: [theme, factory, toolkit, styling]
            status: ADOPTED
          - skill_id: anthropic_official.web_artifacts_builder
            path: skills/anthropic-official/web-artifacts-builder/SKILL.md
            anchors: [artifacts, builder, suite, tools]
            status: ADOPTED
          - skill_id: anthropic_official.webapp_testing
            path: skills/anthropic-official/webapp-testing/SKILL.md
            anchors: [webapp, testing, toolkit, interacting]
            status: ADOPTED
          - skill_id: anthropic_official.xlsx
            path: skills/anthropic-official/xlsx/SKILL.md
            anchors: [xlsx, skill, time, spreadsheet]
            status: ADOPTED

  FINANCE:
    path: skills/finance/
    anchors: [audit, support, compliance, close, management, manage, financial, statements]
    sub_domains:
      accounting:
        path: skills/finance/accounting/
        anchors: [audit, support, close, management, financial, statements]
        skills:
          - skill_id: finance.accounting.audit_support
            path: skills/finance/accounting/audit-support/SKILL.md
            anchors: [audit, support, compliance, control]
            status: ADOPTED
          - skill_id: finance.accounting.close_management
            path: skills/finance/accounting/close-management/SKILL.md
            anchors: [close, management, manage, month]
            status: ADOPTED
          - skill_id: finance.accounting.financial_statements
            path: skills/finance/accounting/financial-statements/SKILL.md
            anchors: [financial, statements, generate, income]
            status: ADOPTED
          - skill_id: finance.accounting.journal_entry
            path: skills/finance/accounting/journal-entry/SKILL.md
            anchors: [journal, entry, prepare, entries]
            status: ADOPTED
          - skill_id: finance.accounting.journal_entry_prep
            path: skills/finance/accounting/journal-entry-prep/SKILL.md
            anchors: [journal, entry, prep, prepare]
            status: ADOPTED
          - skill_id: finance.accounting.reconciliation
            path: skills/finance/accounting/reconciliation/SKILL.md
            anchors: [reconciliation, reconcile, accounts, comparing]
            status: ADOPTED
          - skill_id: finance.accounting.sox_testing
            path: skills/finance/accounting/sox-testing/SKILL.md
            anchors: [testing, generate, sample, selections]
            status: ADOPTED
          - skill_id: finance.accounting.variance_analysis
            path: skills/finance/accounting/variance-analysis/SKILL.md
            anchors: [variance, analysis, decompose, financial]
            status: ADOPTED
      wealth_management:
        path: skills/finance/wealth-management/
        anchors: [client, report, review, financial, plan, investment]
        skills:
          - skill_id: finance.wealth_management.client_report
            path: skills/finance/wealth-management/client-report/SKILL.md
            anchors: [client, report, description, generate]
            status: ADOPTED
          - skill_id: finance.wealth_management.client_review
            path: skills/finance/wealth-management/client-review/SKILL.md
            anchors: [client, review, prep, description]
            status: ADOPTED
          - skill_id: finance.wealth_management.financial_plan
            path: skills/finance/wealth-management/financial-plan/SKILL.md
            anchors: [financial, plan, description, build]
            status: ADOPTED
          - skill_id: finance.wealth_management.investment_proposal
            path: skills/finance/wealth-management/investment-proposal/SKILL.md
            anchors: [investment, proposal, description, create]
            status: ADOPTED
          - skill_id: finance.wealth_management.portfolio_rebalance
            path: skills/finance/wealth-management/portfolio-rebalance/SKILL.md
            anchors: [portfolio, rebalance, description, analyze]
            status: ADOPTED
          - skill_id: finance.wealth_management.tax_loss_harvesting
            path: skills/finance/wealth-management/tax-loss-harvesting/SKILL.md
            anchors: [loss, harvesting, description, identify]
            status: ADOPTED
      private_equity:
        path: skills/finance/private-equity/
        anchors: [readiness, portfolio, checklist, diligence, meeting, prep]
        skills:
          - skill_id: finance.private_equity.ai_readiness
            path: skills/finance/private-equity/ai-readiness/SKILL.md
            anchors: [readiness, portfolio, description, scan]
            status: ADOPTED
          - skill_id: finance.private_equity.dd_checklist
            path: skills/finance/private-equity/dd-checklist/SKILL.md
            anchors: [checklist, diligence, description, generate]
            status: ADOPTED
          - skill_id: finance.private_equity.dd_meeting_prep
            path: skills/finance/private-equity/dd-meeting-prep/SKILL.md
            anchors: [meeting, prep, diligence, description]
            status: ADOPTED
          - skill_id: finance.private_equity.deal_screening
            path: skills/finance/private-equity/deal-screening/SKILL.md
            anchors: [deal, screening, description, quickly]
            status: ADOPTED
          - skill_id: finance.private_equity.deal_sourcing
            path: skills/finance/private-equity/deal-sourcing/SKILL.md
            anchors: [deal, sourcing, description, workflow]
            status: ADOPTED
          - skill_id: finance.private_equity.ic_memo
            path: skills/finance/private-equity/ic-memo/SKILL.md
            anchors: [memo, investment, committee, description]
            status: ADOPTED
          - skill_id: finance.private_equity.portfolio_monitoring
            path: skills/finance/private-equity/portfolio-monitoring/SKILL.md
            anchors: [portfolio, monitoring, description, track]
            status: ADOPTED
          - skill_id: finance.private_equity.returns_analysis
            path: skills/finance/private-equity/returns-analysis/SKILL.md
            anchors: [returns, analysis, description, build]
            status: ADOPTED
          - skill_id: finance.private_equity.unit_economics
            path: skills/finance/private-equity/unit-economics/SKILL.md
            anchors: [unit, economics, analysis, description]
            status: ADOPTED
          - skill_id: finance.private_equity.value_creation_plan
            path: skills/finance/private-equity/value-creation-plan/SKILL.md
            anchors: [value, creation, plan, description]
            status: ADOPTED
      market_data:
        path: skills/finance/market-data/
        anchors: [earnings, preview, funding, digest, tear, sheet]
        skills:
          - skill_id: finance.market_data.earnings_preview_beta
            path: skills/finance/market-data/earnings-preview-beta/SKILL.md
            anchors: [earnings, preview, single, generate]
            status: ADOPTED
          - skill_id: finance.market_data.funding_digest
            path: skills/finance/market-data/funding-digest/SKILL.md
            anchors: [funding, digest, generate, polished]
            status: ADOPTED
          - skill_id: finance.market_data.tear_sheet
            path: skills/finance/market-data/tear-sheet/SKILL.md
            anchors: [tear, sheet, generate, professional]
            status: ADOPTED
      fixed_income:
        path: skills/finance/fixed-income/
        anchors: [bond, futures, relative, equity, research, fixed]
        skills:
          - skill_id: finance.fixed_income.bond_futures_basis
            path: skills/finance/fixed-income/bond-futures-basis/SKILL.md
            anchors: [bond, futures, basis, analyze]
            status: ADOPTED
          - skill_id: finance.fixed_income.bond_relative_value
            path: skills/finance/fixed-income/bond-relative-value/SKILL.md
            anchors: [bond, relative, value, perform]
            status: ADOPTED
          - skill_id: finance.fixed_income.equity_research
            path: skills/finance/fixed-income/equity-research/SKILL.md
            anchors: [equity, research, generate, comprehensive]
            status: ADOPTED
          - skill_id: finance.fixed_income.fixed_income_portfolio
            path: skills/finance/fixed-income/fixed-income-portfolio/SKILL.md
            anchors: [fixed, income, portfolio, review]
            status: ADOPTED
          - skill_id: finance.fixed_income.fx_carry_trade
            path: skills/finance/fixed-income/fx-carry-trade/SKILL.md
            anchors: [carry, trade, evaluate, opportunities]
            status: ADOPTED
          - skill_id: finance.fixed_income.macro_rates_monitor
            path: skills/finance/fixed-income/macro-rates-monitor/SKILL.md
            anchors: [macro, rates, monitor, build]
            status: ADOPTED
          - skill_id: finance.fixed_income.option_vol_analysis
            path: skills/finance/fixed-income/option-vol-analysis/SKILL.md
            anchors: [option, analysis, analyze, volatility]
            status: ADOPTED
          - skill_id: finance.fixed_income.swap_curve_strategy
            path: skills/finance/fixed-income/swap-curve-strategy/SKILL.md
            anchors: [swap, curve, strategy, analyze]
            status: ADOPTED
      investment_banking:
        path: skills/finance/investment-banking/
        anchors: [buyer, list, builder, description, datapack, deal]
        skills:
          - skill_id: finance.investment_banking.buyer_list
            path: skills/finance/investment-banking/buyer-list/SKILL.md
            anchors: [buyer, list, description, build]
            status: ADOPTED
          - skill_id: finance.investment_banking.cim_builder
            path: skills/finance/investment-banking/cim-builder/SKILL.md
            anchors: [builder, description, structure, draft]
            status: ADOPTED
          - skill_id: finance.investment_banking.datapack_builder
            path: skills/finance/investment-banking/datapack-builder/SKILL.md
            anchors: [datapack, builder, build, professional]
            status: ADOPTED
          - skill_id: finance.investment_banking.deal_tracker
            path: skills/finance/investment-banking/deal-tracker/SKILL.md
            anchors: [deal, tracker, description, track]
            status: ADOPTED
          - skill_id: finance.investment_banking.merger_model
            path: skills/finance/investment-banking/merger-model/SKILL.md
            anchors: [merger, model, description, build]
            status: ADOPTED
          - skill_id: finance.investment_banking.pitch_deck
            path: skills/finance/investment-banking/pitch-deck/SKILL.md
            anchors: [pitch, deck, populates, investment]
            status: ADOPTED
          - skill_id: finance.investment_banking.process_letter
            path: skills/finance/investment-banking/process-letter/SKILL.md
            anchors: [process, letter, description, draft]
            status: ADOPTED
          - skill_id: finance.investment_banking.strip_profile
            path: skills/finance/investment-banking/strip-profile/SKILL.md
            anchors: [strip, profile, workflow, clarify]
            status: ADOPTED
          - skill_id: finance.investment_banking.teaser
            path: skills/finance/investment-banking/teaser/SKILL.md
            anchors: [teaser, description, draft, anonymous]
            status: ADOPTED
      financial_analysis:
        path: skills/finance/financial-analysis/
        anchors: [statement, model, audit, spreadsheet, clean, data]
        skills:
          - skill_id: finance.financial_analysis.3_statement_model
            path: skills/finance/financial-analysis/3-statement-model/SKILL.md
            anchors: [statement, model, complete, populate]
            status: ADOPTED
          - skill_id: finance.financial_analysis.audit_xls
            path: skills/finance/financial-analysis/audit-xls/SKILL.md
            anchors: [audit, spreadsheet, formula, accuracy]
            status: ADOPTED
          - skill_id: finance.financial_analysis.clean_data_xls
            path: skills/finance/financial-analysis/clean-data-xls/SKILL.md
            anchors: [clean, data, messy, spreadsheet]
            status: ADOPTED
          - skill_id: finance.financial_analysis.competitive_analysis
            path: skills/finance/financial-analysis/competitive-analysis/SKILL.md
            anchors: [competitive, analysis, framework, building]
            status: ADOPTED
          - skill_id: finance.financial_analysis.comps_analysis
            path: skills/finance/financial-analysis/comps-analysis/SKILL.md
            anchors: [comps, analysis, comparable, company]
            status: ADOPTED
          - skill_id: finance.financial_analysis.dcf_model
            path: skills/finance/financial-analysis/dcf-model/SKILL.md
            anchors: [model, real, discounted, cash]
            status: ADOPTED
          - skill_id: finance.financial_analysis.deck_refresh
            path: skills/finance/financial-analysis/deck-refresh/SKILL.md
            anchors: [deck, refresh, updates, presentation]
            status: ADOPTED
          - skill_id: finance.financial_analysis.ib_check_deck
            path: skills/finance/financial-analysis/ib-check-deck/SKILL.md
            anchors: [check, deck, investment, banking]
            status: ADOPTED
          - skill_id: finance.financial_analysis.lbo_model
            path: skills/finance/financial-analysis/lbo-model/SKILL.md
            anchors: [model, skill, completing, leveraged]
            status: ADOPTED
          - skill_id: finance.financial_analysis.ppt_template_creator
            path: skills/finance/financial-analysis/ppt-template-creator/SKILL.md
            anchors: [template, creator, creates, self]
            status: ADOPTED
          - skill_id: finance.financial_analysis.skill_creator
            path: skills/finance/financial-analysis/skill-creator/SKILL.md
            anchors: [skill, creator, guide, creating]
            status: ADOPTED
      equity_research:
        path: skills/finance/equity-research/
        anchors: [catalyst, calendar, earnings, analysis, preview, idea]
        skills:
          - skill_id: finance.equity_research.catalyst_calendar
            path: skills/finance/equity-research/catalyst-calendar/SKILL.md
            anchors: [catalyst, calendar, description, build]
            status: ADOPTED
          - skill_id: finance.equity_research.earnings_analysis
            path: skills/finance/equity-research/earnings-analysis/SKILL.md
            anchors: [earnings, analysis, create, professional]
            status: ADOPTED
          - skill_id: finance.equity_research.earnings_preview
            path: skills/finance/equity-research/earnings-preview/SKILL.md
            anchors: [earnings, preview, description, build]
            status: ADOPTED
          - skill_id: finance.equity_research.idea_generation
            path: skills/finance/equity-research/idea-generation/SKILL.md
            anchors: [idea, generation, description, systematic]
            status: ADOPTED
          - skill_id: finance.equity_research.initiating_coverage
            path: skills/finance/equity-research/initiating-coverage/SKILL.md
            anchors: [initiating, coverage, create, institutional]
            status: ADOPTED
          - skill_id: finance.equity_research.model_update
            path: skills/finance/equity-research/model-update/SKILL.md
            anchors: [model, update, description, financial]
            status: ADOPTED
          - skill_id: finance.equity_research.morning_note
            path: skills/finance/equity-research/morning-note/SKILL.md
            anchors: [morning, note, description, draft]
            status: ADOPTED
          - skill_id: finance.equity_research.sector_overview
            path: skills/finance/equity-research/sector-overview/SKILL.md
            anchors: [sector, overview, description, create]
            status: ADOPTED
          - skill_id: finance.equity_research.thesis_tracker
            path: skills/finance/equity-research/thesis-tracker/SKILL.md
            anchors: [thesis, tracker, description, maintain]
            status: ADOPTED

  ENGINEERING:
    path: skills/engineering/
    anchors: [architecture, create, evaluate, code, review, changes, debug, structured]
    sub_domains:
      software:
        path: skills/engineering/software/
        anchors: [architecture, create, code, review, debug, structured]
        skills:
          - skill_id: engineering.software.architecture
            path: skills/engineering/software/architecture/SKILL.md
            anchors: [architecture, create, evaluate, decision]
            status: ADOPTED
          - skill_id: engineering.software.code_review
            path: skills/engineering/software/code-review/SKILL.md
            anchors: [code, review, changes, security]
            status: ADOPTED
          - skill_id: engineering.software.debug
            path: skills/engineering/software/debug/SKILL.md
            anchors: [debug, structured, debugging, session]
            status: ADOPTED
          - skill_id: engineering.software.deploy_checklist
            path: skills/engineering/software/deploy-checklist/SKILL.md
            anchors: [deploy, checklist, deployment, verification]
            status: ADOPTED
          - skill_id: engineering.software.documentation
            path: skills/engineering/software/documentation/SKILL.md
            anchors: [documentation, write, maintain, technical]
            status: ADOPTED
          - skill_id: engineering.software.incident_response
            path: skills/engineering/software/incident-response/SKILL.md
            anchors: [incident, response, workflow, triage]
            status: ADOPTED
          - skill_id: engineering.software.standup
            path: skills/engineering/software/standup/SKILL.md
            anchors: [standup, generate, update, recent]
            status: ADOPTED
          - skill_id: engineering.software.system_design
            path: skills/engineering/software/system-design/SKILL.md
            anchors: [system, design, systems, services]
            status: ADOPTED
          - skill_id: engineering.software.tech_debt
            path: skills/engineering/software/tech-debt/SKILL.md
            anchors: [tech, debt, identify, categorize]
            status: ADOPTED
          - skill_id: engineering.software.testing_strategy
            path: skills/engineering/software/testing-strategy/SKILL.md
            anchors: [testing, strategy, design, test]
            status: ADOPTED

  DATA_SCIENCE:
    path: skills/data-science/
    anchors: [analyze, answer, data, build, dashboard, interactive, create, publication]
    sub_domains:
      analytics:
        path: skills/data-science/analytics/
        anchors: [analyze, answer, build, dashboard, create, publication]
        skills:
          - skill_id: data_science.analytics.analyze
            path: skills/data-science/analytics/analyze/SKILL.md
            anchors: [analyze, answer, data, questions]
            status: ADOPTED
          - skill_id: data_science.analytics.build_dashboard
            path: skills/data-science/analytics/build-dashboard/SKILL.md
            anchors: [build, dashboard, interactive, html]
            status: ADOPTED
          - skill_id: data_science.analytics.create_viz
            path: skills/data-science/analytics/create-viz/SKILL.md
            anchors: [create, publication, quality, visualizations]
            status: ADOPTED
          - skill_id: data_science.analytics.data_context_extractor
            path: skills/data-science/analytics/data-context-extractor/SKILL.md
            anchors: [data, context, extractor, meta]
            status: ADOPTED
          - skill_id: data_science.analytics.data_visualization
            path: skills/data-science/analytics/data-visualization/SKILL.md
            anchors: [data, visualization, create, effective]
            status: ADOPTED
          - skill_id: data_science.analytics.explore_data
            path: skills/data-science/analytics/explore-data/SKILL.md
            anchors: [explore, data, profile, dataset]
            status: ADOPTED
          - skill_id: data_science.analytics.sql_queries
            path: skills/data-science/analytics/sql-queries/SKILL.md
            anchors: [queries, write, correct, performant]
            status: ADOPTED
          - skill_id: data_science.analytics.statistical_analysis
            path: skills/data-science/analytics/statistical-analysis/SKILL.md
            anchors: [statistical, analysis, apply, methods]
            status: ADOPTED
          - skill_id: data_science.analytics.validate_data
            path: skills/data-science/analytics/validate-data/SKILL.md
            anchors: [validate, data, analysis, sharing]
            status: ADOPTED
          - skill_id: data_science.analytics.write_query
            path: skills/data-science/analytics/write-query/SKILL.md
            anchors: [write, query, optimized, dialect]
            status: ADOPTED

  LEGAL:
    path: skills/legal/
    anchors: [brief, generate, contextual, compliance, check, proposed, legal, response]
    sub_domains:
      knowledge_work:
        path: skills/legal/knowledge-work/
        anchors: [brief, generate, compliance, check, legal, response]
        skills:
          - skill_id: legal.knowledge_work.brief
            path: skills/legal/knowledge-work/brief/SKILL.md
            anchors: [brief, generate, contextual, briefings]
            status: ADOPTED
          - skill_id: legal.knowledge_work.compliance_check
            path: skills/legal/knowledge-work/compliance-check/SKILL.md
            anchors: [compliance, check, proposed, action]
            status: ADOPTED
          - skill_id: legal.knowledge_work.legal_response
            path: skills/legal/knowledge-work/legal-response/SKILL.md
            anchors: [legal, response, generate, common]
            status: ADOPTED
          - skill_id: legal.knowledge_work.legal_risk_assessment
            path: skills/legal/knowledge-work/legal-risk-assessment/SKILL.md
            anchors: [legal, risk, assessment, assess]
            status: ADOPTED
          - skill_id: legal.knowledge_work.meeting_briefing
            path: skills/legal/knowledge-work/meeting-briefing/SKILL.md
            anchors: [meeting, briefing, prepare, structured]
            status: ADOPTED
          - skill_id: legal.knowledge_work.review_contract
            path: skills/legal/knowledge-work/review-contract/SKILL.md
            anchors: [review, contract, against, organization]
            status: ADOPTED
          - skill_id: legal.knowledge_work.signature_request
            path: skills/legal/knowledge-work/signature-request/SKILL.md
            anchors: [signature, request, prepare, route]
            status: ADOPTED
          - skill_id: legal.knowledge_work.triage_nda
            path: skills/legal/knowledge-work/triage-nda/SKILL.md
            anchors: [triage, rapidly, incoming, classify]
            status: ADOPTED
          - skill_id: legal.knowledge_work.vendor_check
            path: skills/legal/knowledge-work/vendor-check/SKILL.md
            anchors: [vendor, check, status, existing]
            status: ADOPTED

  MARKETING:
    path: skills/marketing/
    anchors: [brand, voice, enforcement, discover, discovery, guideline, generation, generate]
    sub_domains:
      brand_voice:
        path: skills/marketing/brand-voice/
        anchors: [brand, voice, discover, guideline, generation]
        skills:
          - skill_id: marketing.brand_voice.brand_voice_enforcement
            path: skills/marketing/brand-voice/brand-voice-enforcement/SKILL.md
            anchors: [brand, voice, enforcement, apply]
            status: ADOPTED
          - skill_id: marketing.brand_voice.discover_brand
            path: skills/marketing/brand-voice/discover-brand/SKILL.md
            anchors: [discover, brand, discovery, orchestrate]
            status: ADOPTED
          - skill_id: marketing.brand_voice.guideline_generation
            path: skills/marketing/brand-voice/guideline-generation/SKILL.md
            anchors: [guideline, generation, generate, comprehensive]
            status: ADOPTED
      general:
        path: skills/marketing/general/
        anchors: [brand, review, campaign, plan, competitive, brief]
        skills:
          - skill_id: marketing.brand_review
            path: skills/marketing/brand-review/SKILL.md
            anchors: [brand, review, content, against]
            status: ADOPTED
          - skill_id: marketing.campaign_plan
            path: skills/marketing/campaign-plan/SKILL.md
            anchors: [campaign, plan, generate, full]
            status: ADOPTED
          - skill_id: marketing.competitive_brief
            path: skills/marketing/competitive-brief/SKILL.md
            anchors: [competitive, brief, research, competitors]
            status: ADOPTED
          - skill_id: marketing.content_creation
            path: skills/marketing/content-creation/SKILL.md
            anchors: [content, creation, draft, marketing]
            status: ADOPTED
          - skill_id: marketing.draft_content
            path: skills/marketing/draft-content/SKILL.md
            anchors: [draft, content, blog, posts]
            status: ADOPTED
          - skill_id: marketing.email_sequence
            path: skills/marketing/email-sequence/SKILL.md
            anchors: [email, sequence, design, draft]
            status: ADOPTED
          - skill_id: marketing.performance_report
            path: skills/marketing/performance-report/SKILL.md
            anchors: [performance, report, build, marketing]
            status: ADOPTED
          - skill_id: marketing.seo_audit
            path: skills/marketing/seo-audit/SKILL.md
            anchors: [audit, comprehensive, keyword, research]
            status: ADOPTED

  SALES:
    path: skills/sales/
    anchors: [account, research, company, call, prep, prepare, summary, process]
    sub_domains:
      general:
        path: skills/sales/general/
        anchors: [account, research, call, prep, summary, competitive]
        skills:
          - skill_id: sales.account_research
            path: skills/sales/account-research/SKILL.md
            anchors: [account, research, company, person]
            status: ADOPTED
          - skill_id: sales.call_prep
            path: skills/sales/call-prep/SKILL.md
            anchors: [call, prep, prepare, sales]
            status: ADOPTED
          - skill_id: sales.call_summary
            path: skills/sales/call-summary/SKILL.md
            anchors: [call, summary, process, notes]
            status: ADOPTED
          - skill_id: sales.competitive_intelligence
            path: skills/sales/competitive-intelligence/SKILL.md
            anchors: [competitive, intelligence, research, competitors]
            status: ADOPTED
          - skill_id: sales.create_an_asset
            path: skills/sales/create-an-asset/SKILL.md
            anchors: [create, asset, generate, tailored]
            status: ADOPTED
          - skill_id: sales.daily_briefing
            path: skills/sales/daily-briefing/SKILL.md
            anchors: [daily, briefing, start, prioritized]
            status: ADOPTED
          - skill_id: sales.draft_outreach
            path: skills/sales/draft-outreach/SKILL.md
            anchors: [draft, outreach, research, prospect]
            status: ADOPTED
          - skill_id: sales.forecast
            path: skills/sales/forecast/SKILL.md
            anchors: [forecast, generate, weighted, sales]
            status: ADOPTED
          - skill_id: sales.pipeline_review
            path: skills/sales/pipeline-review/SKILL.md
            anchors: [pipeline, review, analyze, health]
            status: ADOPTED
      common_room:
        path: skills/sales/common-room/
        anchors: [account, research, call, prep, compose, outreach]
        skills:
          - skill_id: sales.common_room.account_research
            path: skills/sales/common-room/account-research/SKILL.md
            anchors: [account, research, company, common]
            status: ADOPTED
          - skill_id: sales.common_room.call_prep
            path: skills/sales/common-room/call-prep/SKILL.md
            anchors: [call, prep, prepare, customer]
            status: ADOPTED
          - skill_id: sales.common_room.compose_outreach
            path: skills/sales/common-room/compose-outreach/SKILL.md
            anchors: [compose, outreach, generate, personalized]
            status: ADOPTED
          - skill_id: sales.common_room.contact_research
            path: skills/sales/common-room/contact-research/SKILL.md
            anchors: [contact, research, specific, person]
            status: ADOPTED
          - skill_id: sales.common_room.prospect
            path: skills/sales/common-room/prospect/SKILL.md
            anchors: [prospect, build, targeted, account]
            status: ADOPTED
          - skill_id: sales.common_room.weekly_prep_brief
            path: skills/sales/common-room/weekly-prep-brief/SKILL.md
            anchors: [weekly, prep, brief, generate]
            status: ADOPTED
      apollo:
        path: skills/sales/apollo/
        anchors: [enrich, lead, prospect, full, sequence, load]
        skills:
          - skill_id: sales.apollo.enrich_lead
            path: skills/sales/apollo/enrich-lead/SKILL.md
            anchors: [enrich, lead, instant, enrichment]
            status: ADOPTED
          - skill_id: sales.apollo.prospect
            path: skills/sales/apollo/prospect/SKILL.md
            anchors: [prospect, full, leads, pipeline]
            status: ADOPTED
          - skill_id: sales.apollo.sequence_load
            path: skills/sales/apollo/sequence-load/SKILL.md
            anchors: [sequence, load, find, leads]
            status: ADOPTED

  HUMAN_RESOURCES:
    path: skills/human-resources/
    anchors: [comp, analysis, analyze, draft, offer, letter, interview, prep]
    sub_domains:
      general:
        path: skills/human-resources/general/
        anchors: [comp, analysis, draft, offer, interview, prep]
        skills:
          - skill_id: human_resources.comp_analysis
            path: skills/human-resources/comp-analysis/SKILL.md
            anchors: [comp, analysis, analyze, compensation]
            status: ADOPTED
          - skill_id: human_resources.draft_offer
            path: skills/human-resources/draft-offer/SKILL.md
            anchors: [draft, offer, letter, comp]
            status: ADOPTED
          - skill_id: human_resources.interview_prep
            path: skills/human-resources/interview-prep/SKILL.md
            anchors: [interview, prep, create, structured]
            status: ADOPTED
          - skill_id: human_resources.onboarding
            path: skills/human-resources/onboarding/SKILL.md
            anchors: [onboarding, generate, checklist, first]
            status: ADOPTED
          - skill_id: human_resources.org_planning
            path: skills/human-resources/org-planning/SKILL.md
            anchors: [planning, headcount, design, team]
            status: ADOPTED
          - skill_id: human_resources.people_report
            path: skills/human-resources/people-report/SKILL.md
            anchors: [people, report, generate, headcount]
            status: ADOPTED
          - skill_id: human_resources.performance_review
            path: skills/human-resources/performance-review/SKILL.md
            anchors: [performance, review, structure, self]
            status: ADOPTED
          - skill_id: human_resources.policy_lookup
            path: skills/human-resources/policy-lookup/SKILL.md
            anchors: [policy, lookup, find, explain]
            status: ADOPTED
          - skill_id: human_resources.recruiting_pipeline
            path: skills/human-resources/recruiting-pipeline/SKILL.md
            anchors: [recruiting, pipeline, track, manage]
            status: ADOPTED

  OPERATIONS:
    path: skills/operations/
    anchors: [capacity, plan, resource, change, request, create, compliance, tracking]
    sub_domains:
      general:
        path: skills/operations/general/
        anchors: [capacity, plan, change, request, compliance, tracking]
        skills:
          - skill_id: operations.capacity_plan
            path: skills/operations/capacity-plan/SKILL.md
            anchors: [capacity, plan, resource, workload]
            status: ADOPTED
          - skill_id: operations.change_request
            path: skills/operations/change-request/SKILL.md
            anchors: [change, request, create, management]
            status: ADOPTED
          - skill_id: operations.compliance_tracking
            path: skills/operations/compliance-tracking/SKILL.md
            anchors: [compliance, tracking, track, requirements]
            status: ADOPTED
          - skill_id: operations.process_doc
            path: skills/operations/process-doc/SKILL.md
            anchors: [process, document, business, flowcharts]
            status: ADOPTED
          - skill_id: operations.process_optimization
            path: skills/operations/process-optimization/SKILL.md
            anchors: [process, optimization, analyze, improve]
            status: ADOPTED
          - skill_id: operations.risk_assessment
            path: skills/operations/risk-assessment/SKILL.md
            anchors: [risk, assessment, identify, assess]
            status: ADOPTED
          - skill_id: operations.runbook
            path: skills/operations/runbook/SKILL.md
            anchors: [runbook, create, update, operational]
            status: ADOPTED
          - skill_id: operations.status_report
            path: skills/operations/status-report/SKILL.md
            anchors: [status, report, generate, kpis]
            status: ADOPTED
          - skill_id: operations.vendor_review
            path: skills/operations/vendor-review/SKILL.md
            anchors: [vendor, review, evaluate, cost]
            status: ADOPTED

  PRODUCT_MANAGEMENT:
    path: skills/product-management/
    anchors: [competitive, brief, create, metrics, review, analyze, product, brainstorming]
    sub_domains:
      general:
        path: skills/product-management/general/
        anchors: [competitive, brief, metrics, review, product, brainstorming]
        skills:
          - skill_id: product_management.competitive_brief
            path: skills/product-management/competitive-brief/SKILL.md
            anchors: [competitive, brief, create, analysis]
            status: ADOPTED
          - skill_id: product_management.metrics_review
            path: skills/product-management/metrics-review/SKILL.md
            anchors: [metrics, review, analyze, product]
            status: ADOPTED
          - skill_id: product_management.product_brainstorming
            path: skills/product-management/product-brainstorming/SKILL.md
            anchors: [product, brainstorming, brainstorm, ideas]
            status: ADOPTED
          - skill_id: product_management.roadmap_update
            path: skills/product-management/roadmap-update/SKILL.md
            anchors: [roadmap, update, create, reprioritize]
            status: ADOPTED
          - skill_id: product_management.sprint_planning
            path: skills/product-management/sprint-planning/SKILL.md
            anchors: [sprint, planning, plan, scope]
            status: ADOPTED
          - skill_id: product_management.stakeholder_update
            path: skills/product-management/stakeholder-update/SKILL.md
            anchors: [stakeholder, update, generate, tailored]
            status: ADOPTED
          - skill_id: product_management.synthesize_research
            path: skills/product-management/synthesize-research/SKILL.md
            anchors: [synthesize, research, user, interviews]
            status: ADOPTED
          - skill_id: product_management.write_spec
            path: skills/product-management/write-spec/SKILL.md
            anchors: [write, spec, feature, problem]
            status: ADOPTED

  CUSTOMER_SUPPORT:
    path: skills/customer-support/
    anchors: [customer, escalation, package, research, multi, draft, response, professional]
    sub_domains:
      general:
        path: skills/customer-support/general/
        anchors: [customer, escalation, research, draft, response, article]
        skills:
          - skill_id: customer_support.customer_escalation
            path: skills/customer-support/customer-escalation/SKILL.md
            anchors: [customer, escalation, package, engineering]
            status: ADOPTED
          - skill_id: customer_support.customer_research
            path: skills/customer-support/customer-research/SKILL.md
            anchors: [customer, research, multi, source]
            status: ADOPTED
          - skill_id: customer_support.draft_response
            path: skills/customer-support/draft-response/SKILL.md
            anchors: [draft, response, professional, customer]
            status: ADOPTED
          - skill_id: customer_support.kb_article
            path: skills/customer-support/kb-article/SKILL.md
            anchors: [article, draft, knowledge, base]
            status: ADOPTED
          - skill_id: customer_support.ticket_triage
            path: skills/customer-support/ticket-triage/SKILL.md
            anchors: [ticket, triage, prioritize, support]
            status: ADOPTED

  KNOWLEDGE_MANAGEMENT:
    path: skills/knowledge-management/
    anchors: [digest, generate, daily, knowledge, synthesis, combines, search, connected]
    sub_domains:
      search:
        path: skills/knowledge-management/search/
        anchors: [digest, generate, knowledge, synthesis, search, connected]
        skills:
          - skill_id: knowledge_management.search.digest
            path: skills/knowledge-management/search/digest/SKILL.md
            anchors: [digest, generate, daily, weekly]
            status: ADOPTED
          - skill_id: knowledge_management.search.knowledge_synthesis
            path: skills/knowledge-management/search/knowledge-synthesis/SKILL.md
            anchors: [knowledge, synthesis, combines, search]
            status: ADOPTED
          - skill_id: knowledge_management.search.search
            path: skills/knowledge-management/search/search/SKILL.md
            anchors: [search, connected, sources, query]
            status: ADOPTED
          - skill_id: knowledge_management.search.search_strategy
            path: skills/knowledge-management/search/search-strategy/SKILL.md
            anchors: [search, strategy, query, decomposition]
            status: ADOPTED
          - skill_id: knowledge_management.search.source_management
            path: skills/knowledge-management/search/source-management/SKILL.md
            anchors: [source, management, manages, connected]
            status: ADOPTED

  PRODUCTIVITY:
    path: skills/productivity/
    anchors: [memory, management, tier, start, initialize, productivity, task, simple]
    sub_domains:
      general:
        path: skills/productivity/general/
        anchors: [memory, management, start, initialize, task, update]
        skills:
          - skill_id: productivity.memory_management
            path: skills/productivity/memory-management/SKILL.md
            anchors: [memory, management, tier, system]
            status: ADOPTED
          - skill_id: productivity.start
            path: skills/productivity/start/SKILL.md
            anchors: [start, initialize, productivity, system]
            status: ADOPTED
          - skill_id: productivity.task_management
            path: skills/productivity/task-management/SKILL.md
            anchors: [task, management, simple, shared]
            status: ADOPTED
          - skill_id: productivity.update
            path: skills/productivity/update/SKILL.md
            anchors: [update, sync, tasks, refresh]
            status: ADOPTED
      documents:
        path: skills/productivity/documents/
        anchors: [view, interactive]
        skills:
          - skill_id: productivity.documents.view_pdf
            path: skills/productivity/documents/view-pdf/SKILL.md
            anchors: [view, interactive, viewer, user]
            status: ADOPTED

  HEALTHCARE:
    path: skills/healthcare/
    anchors: [clinical, trial, protocol, fhir, developer, skill, prior, auth]
    sub_domains:
      general:
        path: skills/healthcare/general/
        anchors: [clinical, trial, fhir, developer, prior, auth]
        skills:
          - skill_id: healthcare.clinical_trial_protocol_skill
            path: skills/healthcare/clinical-trial-protocol-skill/SKILL.md
            anchors: [clinical, trial, protocol, skill]
            status: ADOPTED
          - skill_id: healthcare.fhir_developer_skill
            path: skills/healthcare/fhir-developer-skill/SKILL.md
            anchors: [fhir, developer, skill, quick]
            status: ADOPTED
          - skill_id: healthcare.prior_auth_review_skill
            path: skills/healthcare/prior-auth-review-skill/SKILL.md
            anchors: [prior, auth, review, skill]
            status: ADOPTED

  SCIENCE:
    path: skills/science/
    anchors: [clinical, trial, protocol, instrument, data, allotrope, nextflow, development]
    sub_domains:
      life_sciences:
        path: skills/science/life-sciences/
        anchors: [clinical, trial, instrument, data, nextflow, development]
        skills:
          - skill_id: science.life_sciences.clinical_trial_protocol_skill
            path: skills/science/life-sciences/clinical-trial-protocol-skill/SKILL.md
            anchors: [clinical, trial, protocol, skill]
            status: ADOPTED
          - skill_id: science.life_sciences.instrument_data_to_allotrope
            path: skills/science/life-sciences/instrument-data-to-allotrope/SKILL.md
            anchors: [instrument, data, allotrope, convert]
            status: ADOPTED
          - skill_id: science.life_sciences.nextflow_development
            path: skills/science/life-sciences/nextflow-development/SKILL.md
            anchors: [nextflow, development, core, bioinformatics]
            status: ADOPTED
          - skill_id: science.life_sciences.scientific_problem_selection
            path: skills/science/life-sciences/scientific-problem-selection/SKILL.md
            anchors: [scientific, problem, selection, skill]
            status: ADOPTED
          - skill_id: science.life_sciences.scvi_tools
            path: skills/science/life-sciences/scvi-tools/SKILL.md
            anchors: [scvi, tools, deep, learning]
            status: ADOPTED
          - skill_id: science.life_sciences.single_cell_rna_qc
            path: skills/science/life-sciences/single-cell-rna-qc/SKILL.md
            anchors: [single, cell, performs, quality]
            status: ADOPTED
      bio_research:
        path: skills/science/bio-research/
        anchors: [instrument, data, nextflow, development, scientific, problem]
        skills:
          - skill_id: science.bio_research.instrument_data_to_allotrope
            path: skills/science/bio-research/instrument-data-to-allotrope/SKILL.md
            anchors: [instrument, data, allotrope, convert]
            status: ADOPTED
          - skill_id: science.bio_research.nextflow_development
            path: skills/science/bio-research/nextflow-development/SKILL.md
            anchors: [nextflow, development, core, bioinformatics]
            status: ADOPTED
          - skill_id: science.bio_research.scientific_problem_selection
            path: skills/science/bio-research/scientific-problem-selection/SKILL.md
            anchors: [scientific, problem, selection, skill]
            status: ADOPTED
          - skill_id: science.bio_research.scvi_tools
            path: skills/science/bio-research/scvi-tools/SKILL.md
            anchors: [scvi, tools, deep, learning]
            status: ADOPTED
          - skill_id: science.bio_research.single_cell_rna_qc
            path: skills/science/bio-research/single-cell-rna-qc/SKILL.md
            anchors: [single, cell, performs, quality]
            status: ADOPTED
          - skill_id: science.bio_research.start
            path: skills/science/bio-research/start/SKILL.md
            anchors: [start, research, environment, explore]
            status: ADOPTED

  DESIGN:
    path: skills/design/
    anchors: [accessibility, review, wcag, design, critique, structured, handoff, generate]
    sub_domains:
      ux:
        path: skills/design/ux/
        anchors: [accessibility, review, design, critique, handoff, system]
        skills:
          - skill_id: design.ux.accessibility_review
            path: skills/design/ux/accessibility-review/SKILL.md
            anchors: [accessibility, review, wcag, audit]
            status: ADOPTED
          - skill_id: design.ux.design_critique
            path: skills/design/ux/design-critique/SKILL.md
            anchors: [design, critique, structured, feedback]
            status: ADOPTED
          - skill_id: design.ux.design_handoff
            path: skills/design/ux/design-handoff/SKILL.md
            anchors: [design, handoff, generate, developer]
            status: ADOPTED
          - skill_id: design.ux.design_system
            path: skills/design/ux/design-system/SKILL.md
            anchors: [design, system, audit, document]
            status: ADOPTED
          - skill_id: design.ux.research_synthesis
            path: skills/design/ux/research-synthesis/SKILL.md
            anchors: [research, synthesis, synthesize, user]
            status: ADOPTED
          - skill_id: design.ux.user_research
            path: skills/design/ux/user-research/SKILL.md
            anchors: [user, research, plan, conduct]
            status: ADOPTED
          - skill_id: design.ux.ux_copy
            path: skills/design/ux/ux-copy/SKILL.md
            anchors: [copy, write, review, microcopy]
            status: ADOPTED

  INTEGRATIONS:
    path: skills/integrations/
    anchors: [slack, messaging, guidance, search]
    sub_domains:
      slack:
        path: skills/integrations/slack/
        anchors: [slack, messaging, search]
        skills:
          - skill_id: integrations.slack.slack_messaging
            path: skills/integrations/slack/slack-messaging/SKILL.md
            anchors: [slack, messaging, guidance, composing]
            status: ADOPTED
          - skill_id: integrations.slack.slack_search
            path: skills/integrations/slack/slack-search/SKILL.md
            anchors: [slack, search, guidance, effectively]
            status: ADOPTED

  APEX_INTERNALS_PLUGINS:
    path: skills/apex-internals/
    anchors: [cowork, plugin, customizer, create]
    sub_domains:
      plugins:
        path: skills/apex-internals/plugins/
        anchors: [cowork, plugin, create]
        skills:
          - skill_id: apex_internals.plugins.cowork_plugin_customizer
            path: skills/apex_internals/plugins/cowork-plugin-customizer/SKILL.md
            anchors: [cowork, plugin, customizer, customization]
            status: ADOPTED
          - skill_id: apex_internals.plugins.create_cowork_plugin
            path: skills/apex_internals/plugins/create-cowork-plugin/SKILL.md
            anchors: [create, cowork, plugin, build]
            status: ADOPTED

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

  # ===== COMMUNITY AND ENGINEERING SKILLS (antigravity + ingested) =====

  ENGINEERING_COMMUNITY:
    path: skills/engineering/
    anchors: [experience, expert, acceptance, orchestrator, creative, create]
    total_skills: 451
    sub_domains:
      frontend_react:
        path: skills/engineering/frontend/react/
        anchors: [experience, expert, angular, modern]
        skill_count: 27
      devops_deployment:
        path: skills/engineering/devops/deployment/
        anchors: [acceptance, orchestrator, airflow, patterns]
        skill_count: 18
      testing:
        path: skills/engineering/testing/
        anchors: [creative, create, android, verification]
        skill_count: 29
      cloud_azure:
        path: skills/engineering/cloud/azure/
        anchors: [agents, build, azure, anomalydetector]
        skill_count: 43
      programming_rust:
        path: skills/engineering/programming/rust/
        anchors: [trust, metadata, azure, cosmos]
        skill_count: 18
  AI_ML:
    path: skills/ai-ml/
    anchors: [activecampaign, automation, advanced, evaluation, aegisops, autonomous]
    total_skills: 284
    sub_domains:
      llm:
        path: skills/ai-ml/llm/
        anchors: [activecampaign, automation, advanced, evaluation]
        skill_count: 82
      agents:
        path: skills/ai-ml/agents/
        anchors: [agent, evaluation, framework, manager]
        skill_count: 45
      mcp:
        path: skills/ai-ml/mcp/
        anchors: [airtable, automation, amplitude, asana]
        skill_count: 87
      embeddings:
        path: skills/ai-ml/embeddings/
        anchors: [fuzzing, bounty, azure, search]
        skill_count: 10
      rag:
        path: skills/ai-ml/rag/
        anchors: [appdeploy, deploy, azure, data]
        skill_count: 41
  SECURITY:
    path: skills/security/
    anchors: [security, audit, active, directory, alpha, vantage]
    total_skills: 60
    sub_domains:
      general:
        path: skills/security/general/
        anchors: [security, audit, anti, reversing]
        skill_count: 52
      pentesting:
        path: skills/security/pentesting/
        anchors: [active, directory, ffuf, fuzzing]
        skill_count: 4
      cryptography:
        path: skills/security/cryptography/
        anchors: [alpha, vantage, constant, time]
        skill_count: 3
      reverse_engineering:
        path: skills/security/reverse-engineering/
        anchors: [reverse, engineer]
        skill_count: 1
  COMMUNITY_GENERAL:
    path: skills/community/
    anchors: [andruia, consultant, skill, test, setup, address]
    total_skills: 414
    sub_domains:
      general:
        path: skills/community/general/
        anchors: [andruia, consultant, skill, test]
        skill_count: 414
  WEB3_BLOCKCHAIN:
    path: skills/web3/
    anchors: [andruia, niche, blockchain, developer, component, expert]
    total_skills: 14
    sub_domains:
      defi:
        path: skills/web3/defi/
        anchors: [andruia, niche, component, expert]
        skill_count: 10
      blockchain:
        path: skills/web3/blockchain/
        anchors: [blockchain, developer, spec, code]
        skill_count: 2
      nft:
        path: skills/web3/nft/
        anchors: [standards, master]
        skill_count: 1
      general:
        path: skills/web3/general/
        anchors: [web3, testing]
        skill_count: 1
  DESIGN_COMMUNITY:
    path: skills/design/
    anchors: [components, content, dialogs, layout, search, status]
    total_skills: 13
    sub_domains:
      ios_hig:
        path: skills/design/ios-hig/
        anchors: [components, content, dialogs, layout]
        skill_count: 10
      ux:
        path: skills/design/ux/
        anchors: [designer, create, comprehensive, design]
        skill_count: 3
  DATA_COMMUNITY:
    path: skills/data/
    anchors: [claimable, postgres, database, development, migrations, debug]
    total_skills: 34
    sub_domains:
      databases_sql:
        path: skills/data/databases/sql/
        anchors: [claimable, postgres, database, development]
        skill_count: 14
      databases_cache:
        path: skills/data/databases/cache/
        anchors: [debug, buttercup]
        skill_count: 1
      erp:
        path: skills/data/erp/
        anchors: [odoo, accounting, automated, connector]
        skill_count: 19
  MARKETING_COMMUNITY:
    path: skills/marketing/
    anchors: [content, creator, marketer, copy, editing, copywriting]
    total_skills: 47
    sub_domains:
      seo:
        path: skills/marketing/seo/
        anchors: [content, creator, fixing, metadata]
        skill_count: 36
      general:
        path: skills/marketing/general/
        anchors: [content, marketer, copy, editing]
        skill_count: 11
  HEALTHCARE_COMMUNITY:
    path: skills/healthcare/
    anchors: [family, health, medtech, compliance, trend, mental]
    total_skills: 14
    sub_domains:
      general:
        path: skills/healthcare/general/
        anchors: [family, health, medtech, compliance]
        skill_count: 12
      wellness:
        path: skills/healthcare/wellness/
        anchors: [sleep, analyzer, weightloss]
        skill_count: 2
  LEGAL_COMMUNITY:
    path: skills/legal/
    anchors: [accessibility, compliance, advogado, criminal, especialista, native]
    total_skills: 12
    sub_domains:
      compliance:
        path: skills/legal/compliance/
        anchors: [accessibility, compliance, food, safety]
        skill_count: 5
      brazil:
        path: skills/legal/brazil/
        anchors: [advogado, criminal, especialista]
        skill_count: 2
      contracts:
        path: skills/legal/contracts/
        anchors: [native, design, data, quality]
        skill_count: 3
      general:
        path: skills/legal/general/
        anchors: [legal, advisor, centralized, truth]
        skill_count: 2
  PRODUCTIVITY_COMMUNITY:
    path: skills/productivity/
    anchors: [avoid, writing, beautiful, prose, blog, citation]
    total_skills: 15
    sub_domains:
      writing:
        path: skills/productivity/writing/
        anchors: [avoid, writing, beautiful, prose]
        skill_count: 13
      general:
        path: skills/productivity/general/
        anchors: [concise, planning, office, productivity]
        skill_count: 2
  SALES_COMMUNITY:
    path: skills/sales/
    anchors: [hubspot, integration, linkedin, automating, sales, automator]
    total_skills: 5
    sub_domains:
      crm:
        path: skills/sales/crm/
        anchors: [hubspot, integration]
        skill_count: 1
      general:
        path: skills/sales/general/
        anchors: [linkedin, automating, sales, automator]
        skill_count: 4
  BUSINESS:
    path: skills/business/
    anchors: [business, analyst, market, sizing, startup, financial]
    total_skills: 9
    sub_domains:
      analysis:
        path: skills/business/analysis/
        anchors: [business, analyst, startup]
        skill_count: 4
      startup:
        path: skills/business/startup/
        anchors: [market, sizing, startup, analyst]
        skill_count: 5
  INTEGRATIONS_COMMUNITY:
    path: skills/integrations/
    anchors: [node, configuration, validation, expert, workflow, patterns]
    total_skills: 6
    sub_domains:
      n8n:
        path: skills/integrations/n8n/
        anchors: [node, configuration, validation, expert]
        skill_count: 3
      tavily:
        path: skills/integrations/tavily/
        anchors: [tavily, search]
        skill_count: 1
      slack:
        path: skills/integrations/slack/
        anchors: [layer, governance, slack, creator]
        skill_count: 2
  APEX_INTERNALS_COMMUNITY:
    path: skills/apex_internals/
    anchors: [bdistill, behavioral, knowledge, context, guardian]
    total_skills: 3
    sub_domains:
      knowledge:
        path: skills/apex_internals/knowledge/
        anchors: [bdistill, behavioral, knowledge]
        skill_count: 2
      cognitive:
        path: skills/apex_internals/cognitive/
        anchors: [context, guardian]
        skill_count: 1
  KNOWLEDGE_MGMT_COMMUNITY:
    path: skills/knowledge-management/
    anchors: [wiki, changelog, onboarding, researcher, vitepress]
    total_skills: 4
    sub_domains:
      wiki:
        path: skills/knowledge-management/wiki/
        anchors: [wiki, changelog, onboarding, researcher]
        skill_count: 4
  PRODUCT_MGMT_COMMUNITY:
    path: skills/product-management/
    anchors: [product, manager]
    total_skills: 2
    sub_domains:
      general:
        path: skills/product-management/general/
        anchors: [product, manager]
        skill_count: 2
  FINANCE_COMMUNITY:
    path: skills/finance/
    anchors: [churn, prevention, leiloeiro, risco, pakistan, payments]
    total_skills: 4
    sub_domains:
      payments:
        path: skills/finance/payments/
        anchors: [churn, prevention, pakistan, payments]
        skill_count: 3
      general:
        path: skills/finance/general/
        anchors: [leiloeiro, risco]
        skill_count: 1

  INTEGRATIONS_CATALOG:
    path: integrations/
    anchors: [mcp, plugin, connector, integration, external_service]
    sub_domains:
      mcp_servers:
        path: integrations/mcp-servers/
        anchors: [mcp_server, memory, filesystem, github, sequential_thinking]
        total: 166
      plugins:
        path: integrations/plugins/
        anchors: [plugin, marketplace, connector, third_party]
        total: 135
      external_plugins:
        path: integrations/external-plugins/
        anchors: [asana, slack, github, notion, salesforce, stripe, zoom]
        total: 37
      claude_commands:
        path: integrations/claude-commands/
        anchors: [slash_command, workflow_trigger, automation]
        total: 21

  ALGORITHMS_AND_SDK:
    path: algorithms/
    anchors: [sdk, api, notebook, tutorial, cli, algorithm]
    sub_domains:
      claude_agent_sdk:
        path: algorithms/claude-agent-sdk/
        anchors: [agent_sdk, multi_agent, tool_use, agent_loop]
      claude_code_cli:
        path: algorithms/claude-code-cli/
        anchors: [claude_code, cli, hooks, mcp_integration, agent_mode]
      notebooks:
        path: algorithms/notebooks/
        anchors: [jupyter, notebook, example, api_usage, rag, evals]
        total: 80
      claude_constitution:
        path: algorithms/claude-constitution/
        anchors: [constitution, model_spec, guidelines, values]
      attribution_graphs:
        path: algorithms/attribution-graphs/
        anchors: [interpretability, attribution, mechanistic, visualization]
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
- **DIFFs aplicados**: 104 (86 herdados + 12 OPP-92/103 + 6 OPP-104/109)
- **Skills registradas**: 1656 (v00.33.0)
