---
skill_id: business_intelligence.deal_due_diligence
name: deal-due-diligence
description: >
  Orquestra due diligence completo para deals M&A, parcerias ou investimentos.
  Paraleliza análise financeira + análise jurídica + análise de risco operacional.
  Resolve o gap crítico entre finance e legal onde atualmente as skills existem mas
  não se comunicam. Output: relatório integrado com go/no-go recommendation e
  deal structure.
version: v00.36.0
status: ADOPTED
tier: SUPER
executor: LLM_BEHAVIOR
domain_path: business_intelligence/deal_due_diligence
risk: high
opp: OPP-Phase4-super-skills
anchors:
  - due_diligence
  - m_and_a
  - investment
  - financial_analysis
  - legal_compliance
  - risk_assessment
  - deal_structure
  - valuation
  - contracts
  - regulatory
  - parallel_analysis
  - recommendation
input_schema:
  - name: target_company
    type: string
    description: "Nome ou descrição da empresa/ativo alvo"
    required: true
  - name: deal_type
    type: string
    enum: [acquisition, merger, investment, partnership, licensing]
    description: "Tipo de transação"
    required: true
  - name: financial_data
    type: string
    description: "Path ou conteúdo dos dados financeiros (balanços, DRE, fluxo de caixa)"
    required: false
  - name: legal_documents
    type: array
    description: "Contratos, estatutos, IP filings a revisar"
    required: false
  - name: deal_value_usd
    type: number
    description: "Valor estimado do deal em USD"
    required: false
output_schema:
  - name: financial_analysis
    type: object
    description: "Análise financeira: valuation, métricas, projeções, red flags"
  - name: legal_analysis
    type: object
    description: "Análise jurídica: riscos contratuais, IP issues, compliance gaps"
  - name: risk_matrix
    type: object
    description: "Matriz de riscos integrada (financeiro + legal + operacional)"
  - name: recommendation
    type: string
    enum: [go, no_go, conditional_go]
    description: "Recomendação final com condições se conditional_go"
  - name: deal_structure_proposal
    type: string
    description: "Estrutura de deal recomendada com proteções identificadas"
synergy_map:
  complements:
    - finance.financial-analysis
    - finance.investment-banking
    - legal.contracts
    - legal.compliance
    - operations.risk-assessment
  cross_domain_bridges:
    - domain: finance
      strength: 0.95
      note: "Core financial analysis — valuation, DCF, multiples, red flags"
    - domain: legal
      strength: 0.92
      note: "Contract review, IP issues, regulatory compliance mapping"
    - domain: operations
      strength: 0.85
      note: "Operational risk integration into consolidated risk matrix"
orchestration:
  - phase: "1a"
    skill: finance.financial-analysis
    parallel_with: "1b, 2a, 2b"
    note: "Executar em paralelo com análise jurídica"
    strength: 0.95
  - phase: "1b"
    skill: finance.investment-banking
    parallel_with: "1a, 2a, 2b"
    strength: 0.90
  - phase: "2a"
    skill: legal.contracts
    parallel_with: "1a, 1b, 2b"
    condition: "legal_documents disponíveis"
    strength: 0.92
  - phase: "2b"
    skill: legal.compliance
    parallel_with: "1a, 1b, 2a"
    strength: 0.88
  - phase: 3
    skill: operations.risk-assessment
    gate: "Aguarda fases 1 e 2 — integra todos os findings"
    strength: 0.85
security:
  level: high
  pii: true
  approval_required: true
  note: "Financial and legal data are highly sensitive — handle with strict access controls"
what_if_fails: >
  Se dados financeiros insuficientes: solicitar ao usuário antes de prosseguir.
  Se análise jurídica encontra risco crítico: immediate escalation para advogado humano.
  Se divergência entre análise financeira e legal: reportar conflito explicitamente.
  Se deal_value_usd > $10M: sempre recomendar revisão humana do relatório antes de decisão.
---

# Deal Due Diligence — Super-Skill

Due diligence completo e paralelo para qualquer tipo de transação de negócios,
com análise financeira + jurídica + operacional convergindo em uma recomendação
integrada e fundamentada.

## Why This Skill Exists

O repositório APEX tem skills robustas em `finance` (análise financeira, investment banking)
e em `legal` (contratos, compliance), mas estas skills **nunca se comunicam** — são invocadas
em silos separados, forçando o usuário a integrar manualmente os findings. Em due diligence
real, isso cria risco: um red flag financeiro pode ser compensado por proteções contratuais,
ou um risco legal pode não aparecer até que o contexto financeiro seja claro. Esta super-skill
fecha o gap crítico `finance ↔ legal` com paralelismo declarativo e síntese integrada.

## When to Use

Use esta skill quando:
- Avaliando aquisição, merger, investimento, parceria ou licenciamento
- Precisar de uma recomendação go/no-go fundamentada com risk matrix
- Quiser paralelizar análise financeira e jurídica (economiza tempo)
- Deal value > $100K (abaixo disso, use as skills individuais diretamente)

**Não use** para: avaliações internas de performance (use `finance.financial-analysis` isolado),
ou review simples de contrato único (use `legal.contracts` isolado).

## What If Fails

| Situação | Ação |
|----------|------|
| Dados financeiros ausentes | Solicitar ao usuário; nunca interpolar sem dados |
| Risco jurídico crítico (ex: litígio ativo) | Immediate escalation para advogado humano |
| Divergência finance × legal | Reportar conflito explicitamente no risk_matrix |
| Deal value > $10M | Recomendar revisão humana obrigatória do relatório |
| Compliance gap regulatório crítico | no_go automático ou conditional_go com prazo fixo |

## Orchestration Protocol

```
FASE 1 [PARALELO]:
  ├── 1a: finance.financial-analysis
  │     → Valuation (DCF + múltiplos)
  │     → Análise de balanço, DRE, fluxo de caixa
  │     → Identificação de red flags financeiros
  │
  ├── 1b: finance.investment-banking
  │     → Benchmarks de deals similares
  │     → Estrutura de deal sugerida
  │     → Ranges de valuation de mercado
  │
  ├── 2a: legal.contracts [se legal_documents disponíveis]
  │     → Revisão de contratos existentes
  │     → IP e propriedade intelectual
  │     → Cláusulas restritivas e passivos ocultos
  │
  └── 2b: legal.compliance [sempre]
        → Mapa regulatório da jurisdição
        → Aprovações necessárias e timeline
        → Exposição GDPR/LGPD/setorial

FASE 2 [SEQUENCIAL — aguarda fase 1]:
  operations.risk-assessment
  → Integra todos os findings das fases paralelas
  → Cria risk_matrix consolidada
  → Gera recommendation (go/no_go/conditional_go)
  → Propõe deal_structure_proposal com proteções
```

## Deal Type Risk Profiles

| deal_type | Fases Críticas | Risk Default |
|-----------|---------------|--------------|
| acquisition | 1a, 1b, 2a, 2b, 3 | high |
| merger | 1a, 1b, 2a, 2b, 3 | high |
| investment | 1a, 1b, 2b, 3 | medium |
| partnership | 2a, 2b, 3 | medium |
| licensing | 2a, 2b | low |

## Diff History
- **v00.36.0**: Criado via OPP-Phase4-super-skills — fecha gap Finance ↔ Legal no APEX
