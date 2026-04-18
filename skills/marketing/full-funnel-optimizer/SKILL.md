---
skill_id: growth_engine.full_funnel_optimizer
name: full-funnel-optimizer
description: >
  Orquestra otimização do funil completo de crescimento: pesquisa competitiva →
  segmentação com dados → criação de campanha → execução multi-canal → análise A/B →
  iteração baseada em evidência. Resolve o gap entre marketing (estratégia), sales
  (execução) e data (métricas). Resultado: ciclo de crescimento fechado e iterável.
version: v00.36.0
status: ADOPTED
tier: SUPER
executor: LLM_BEHAVIOR
domain_path: growth_engine/full_funnel_optimizer
risk: safe
opp: OPP-Phase4-super-skills
anchors:
  - growth
  - funnel
  - campaign
  - segmentation
  - ab_testing
  - analytics
  - competitive_intelligence
  - content_strategy
  - sales_pipeline
  - data_driven
  - conversion
  - iteration
input_schema:
  - name: growth_objective
    type: string
    description: "Objetivo de crescimento: acquisition, activation, retention, revenue, referral"
    required: true
  - name: target_audience
    type: string
    description: "Segmento ou persona alvo"
    required: true
  - name: current_metrics
    type: object
    description: "Métricas atuais: CAC, LTV, conversion rates, churn"
    required: false
  - name: budget_usd
    type: number
    description: "Budget disponível para campanhas"
    required: false
  - name: channels
    type: array
    description: "Canais disponíveis: email, ads, content, social, outbound"
    required: false
    default: ["content", "email"]
output_schema:
  - name: competitive_landscape
    type: object
    description: "Mapa competitivo: posicionamento, gaps, oportunidades"
  - name: campaign_plan
    type: object
    description: "Plano de campanha com messaging, canais, timeline, budget allocation"
  - name: ab_test_design
    type: object
    description: "Design de testes A/B com hipóteses, variáveis, sample size"
  - name: analytics_dashboard_spec
    type: object
    description: "Especificação do dashboard de métricas para monitorar a campanha"
  - name: iteration_recommendations
    type: array
    description: "Próximas iterações baseadas em dados das últimas execuções"
synergy_map:
  complements:
    - marketing.competitive-brief
    - marketing.campaign-plan
    - marketing.brand-voice
    - marketing.ab-test-setup
    - marketing.analytics-tracking
    - sales.call-summary
  cross_domain_bridges:
    - domain: data
      strength: 0.88
      note: "Data queries feed segmentation and A/B test analysis"
    - domain: sales
      strength: 0.85
      note: "Sales feedback loop refines messaging and qualification criteria"
    - domain: business_content
      strength: 0.82
      note: "Content creation skills produce campaign assets"
orchestration:
  - phase: 1
    skill: marketing.competitive-brief
    gate: "competitive_landscape com diferenciadores e gaps identificados"
    call_always: true
    strength: 0.92
  - phase: 2
    skill: marketing.campaign-plan
    gate: "campaign_plan com messaging, canais, timeline e budget allocation"
    strength: 0.90
  - phase: 3
    skill: marketing.brand-voice
    gate: "brand voice guidelines aplicados em todos os assets"
    condition: "durante criação de conteúdo"
    strength: 0.85
  - phase: 4
    skill: marketing.ab-test-setup
    gate: "ab_test_design com hipóteses, variáveis e sample size"
    strength: 0.88
  - phase: 5
    skill: marketing.analytics-tracking
    gate: "analytics_dashboard_spec configurado antes do lançamento"
    strength: 0.85
  - phase: 6
    skill: sales.call-summary
    gate: "iteration_recommendations baseadas em feedback de sales"
    condition: "após primeiras conversões"
    strength: 0.80
security:
  level: standard
  pii: true
  approval_required: false
  note: "Campaign data may include PII (email lists, user segments) — handle per GDPR/LGPD"
what_if_fails: >
  Se métricas atuais não disponíveis: usar benchmarks do setor como baseline.
  Se budget insuficiente: priorizar canais de maior ROI (tipicamente content + email).
  Se A/B test sem resultado estatisticamente significativo: aumentar sample size.
  Se sales feedback negativo recorrente: revisar messaging antes de nova campanha.
---

# Full Funnel Optimizer — Super-Skill

Ciclo completo de crescimento: da inteligência competitiva à iteração baseada em dados,
fechando o loop `marketing → campanha → A/B testing → analytics → sales → refinamento`.

## Why This Skill Exists

O APEX tem skills de marketing, sales e data excelentes, mas sem pipeline que as conecte.
O resultado é estratégia sem execução, execução sem medição, ou medição sem iteração.
O gap mais crítico é `marketing ↔ data ↔ sales`: marketing cria campanhas sem dados de
performance, sales executa sem saber o que está convertendo, e data gera métricas que
ninguém usa para refinar a estratégia. Esta super-skill fecha o loop com um pipeline de
6 fases iterativo e data-driven.

## When to Use

Use esta skill quando:
- Lançando uma nova campanha de aquisição, retenção ou referral
- Quiser otimizar um funil existente com evidência (A/B testing sistemático)
- Precisar de inteligência competitiva antes de definir messaging
- Quiser fechar o loop entre marketing e sales com dados

**Não use** para: campanhas táticas pontuais (use `marketing.campaign-plan` isolado),
ou análise de métricas retrospectiva sem plano de ação (use `marketing.analytics-tracking` isolado).

## What If Fails

| Situação | Ação |
|----------|------|
| Métricas atuais ausentes | Usar benchmarks do setor; documentar baseline assumption |
| Budget < $1K/mês | Focar exclusivamente em content + email (ROI máximo) |
| A/B test sem significância estatística | Aumentar sample size; não tomar decisão sem dados |
| Sales feedback negativo recorrente | Revisar messaging completo antes de nova campanha |
| Canal bloqueado/indisponível | Redistribuir budget para canais alternativos |

## Orchestration Protocol

```
PHASE 1: marketing.competitive-brief [SEMPRE]
  → Analisa concorrentes no segmento do target_audience
  → Identifica diferenciadores e gaps de posicionamento
  → Output: competitive_landscape
  → GATE: oportunidades de diferenciação identificadas

PHASE 2: marketing.campaign-plan
  → Define messaging baseado em competitive_landscape
  → Aloca budget por canal (channels[])
  → Cria timeline de execução
  → Output: campaign_plan
  → GATE: campaign_plan aprovado

PHASE 3: marketing.brand-voice [durante criação de conteúdo]
  → Define ou aplica voice guidelines
  → Garante consistência em todos os assets
  → Output: assets com brand voice aplicado

PHASE 4: marketing.ab-test-setup
  → Por elemento de campanha: cria hipótese testável
  → Define variantes (A/B ou multivariado)
  → Calcula sample size para significância estatística
  → Output: ab_test_design
  → GATE: hipóteses formuladas antes do lançamento

PHASE 5: marketing.analytics-tracking [antes do lançamento]
  → Configura eventos de tracking por canal
  → Cria dashboard de métricas (CAC, LTV, conversion, churn)
  → Define alertas para anomalias
  → Output: analytics_dashboard_spec
  → GATE: tracking ativo antes de qualquer spend

PHASE 6: sales.call-summary [após primeiras conversões]
  → Consolida feedback de calls de sales
  → Identifica objeções recorrentes
  → Refina messaging e qualification criteria
  → Output: iteration_recommendations[]
  → Loop: retorna para PHASE 2 com novos insights
```

## AARRR Funnel Mapping

| growth_objective | Fases Prioritárias | Métricas Chave |
|-----------------|-------------------|----------------|
| acquisition | 1, 2, 5 | CAC, traffic, leads |
| activation | 2, 3, 4 | activation rate, time-to-value |
| retention | 3, 4, 5, 6 | churn, LTV, NPS |
| revenue | 2, 4, 5, 6 | MRR, ARPU, expansion |
| referral | 3, 4, 5 | viral coefficient, NPS |

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — fecha loop marketing ↔ data ↔ sales
