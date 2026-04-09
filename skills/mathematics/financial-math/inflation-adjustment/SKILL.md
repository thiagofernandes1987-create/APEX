---
skill_id: mathematics.financial_math.inflation_adjustment
name: "Correção Monetária / Inflation Adjustment"
description: "Calcula fator de correção monetária por IGPM, IPCA, INPC, IPCA-E. Atualiza valores pelo índice acumulado entre duas datas. Integrado com Art. 406 CC e contratos civis."
version: v00.33.0
status: ADOPTED
domain_path: mathematics/financial-math/inflation-adjustment
anchors:
  - IGPM
  - IPCA
  - INPC
  - IPCA_E
  - correcao_monetaria
  - fator_correcao
  - indice_inflacionario
  - reajuste_monetario
  - inflacao
  - variacao_acumulada
  - FGV
  - IBGE
  - correcao_judicial
cross_domain_bridges:
  - anchor: art_406_cc
    domain: legal.civil_law.contracts.financial_clauses
    strength: 0.90
    reason: "Correção monetária de dívidas civis segue índices oficiais por determinação legal e jurisprudencial"
  - anchor: compound_interest
    domain: mathematics.financial_math.compound_interest
    strength: 0.85
    reason: "Montante total = capital corrigido monetariamente + juros compostos sobre capital corrigido"
  - anchor: aluguel
    domain: legal.civil_law.contracts.financial_clauses
    strength: 0.95
    reason: "Contratos de aluguel reajustam por IGPM ou IPCA anualmente (Lei 8.245/91)"
  - anchor: precatorio
    domain: legal.procedural_law
    strength: 0.80
    reason: "Precatórios são corrigidos por IPCA-E (STF RE 870.947)"
risk: safe
languages: [python, dsl]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: partial}
apex_version: v00.33.0
diff_link: diffs/v00_33_0/OPP-107_hyperbolic_anchors.yaml
date_added: "2026-04-08"
---

# Correção Monetária / Inflation Adjustment

## Why This Skill Exists

Correção monetária é obrigatória em qualquer análise financeira ou jurídica brasileira que
envolva valores ao longo do tempo. Sem correção monetária, R$ 1.000 de 2015 comparado com
R$ 1.000 de 2025 produz análise errada — a inflação acumulada IPCA no período foi ~75%.

**Por que existem múltiplos índices?**
- **IGPM (FGV)**: Contratos de aluguel, contratos empresariais
- **IPCA (IBGE)**: Meta de inflação do Banco Central, contratos civis gerais
- **INPC (IBGE)**: Salários, benefícios previdenciários, dívidas civis (padrão jurisprudencial)
- **IPCA-E (IBGE)**: Precatórios e dívidas judiciais (STF RE 870.947/2017)

**Por que este skill e não uma estimativa manual?**
Índices inflacionários são compostos — a variação de cada mês é aplicada sobre o acumulado
do mês anterior. Estimativa linear (`capital × (1 + taxa_total/100)`) erra para períodos longos.
A fórmula correta é o produto dos fatores mensais: `∏(1 + taxa_mes_i/100)`.

---

## When to Use

- Atualizar valor de dívida da data do vencimento até hoje
- Reajustar aluguel pelo IGPM/IPCA acumulado dos últimos 12 meses
- Calcular correção de precatório (IPCA-E)
- Comparar valores em datas diferentes em termos reais
- Qualquer problema com "valor em reais + duas datas + índice de correção"

**Âncoras de ativação**:
`IGPM`, `IPCA`, `INPC`, `correção monetária`, `atualização monetária`, `reajuste`,
`índice inflacionário`, `corrigido pela inflação`, `valores reais`, `deflacionar`

---

## Anchors (Hyperbolic Attraction)

```
MATHEMATICS
└── financial_math
    └── inflation_adjustment          ← VOCÊ ESTÁ AQUI
        ├── ATRAI: compound_interest  [força: 0.85]
        │           → capital corrigido + juros sobre capital corrigido
        ├── ATRAI: amortization       [força: 0.70]
        │           → parcelas em atraso precisam de correção
        └── BRIDGE → legal.civil_law.contracts.financial_clauses [força: 0.90]
                    → IGPM/IPCA em cláusulas contratuais
```

---

## Algorithm

### Fórmula Principal

```
fator_correcao = indice_final / indice_base

valor_corrigido = valor_original × fator_correcao

Onde:
  indice_base  = valor do índice na data inicial (base do contrato ou inadimplemento)
  indice_final = valor do índice na data de cálculo
  fator_correcao > 1.0 sempre (inflação positiva no Brasil)
```

### Python Implementation (SANDBOX_CODE)

```python
# WHY: A fórmula de correção monetária é uma DIVISÃO de índices, não soma de taxas.
#      fator = indice_final / indice_base é matematicamente equivalente ao produto
#      acumulado dos fatores mensais (∏(1+i_k)) mas muito mais simples de calcular
#      quando se tem os valores dos índices nas datas.
# WHEN: Sempre que o problema envolver atualização de valor entre duas datas.
# HOW: Buscar indice_base e indice_final nas tabelas oficiais → dividir.
# WHAT_IF_FAILS: Se índice indisponível → usar IPCA estimado com [APPROX].

def inflation_adjustment(
    valor_original: float,
    indice_base: float,
    indice_final: float,
    indice_nome: str = "IPCA"
) -> dict:
    """
    WHY: Divisão de índices é O(1) e exata. Não requer tabela mensal se índices disponíveis.
    WHEN: Chamado quando as duas datas e o índice são conhecidos.
    HOW: fator = indice_final / indice_base → valor_corrigido = valor * fator.
    WHAT_IF_FAILS: Validar indice_base > 0. Se fator < 1 → deflação (incomum no Brasil).
    """
    if indice_base <= 0:
        return {"status": "ERROR", "reason": "indice_base deve ser > 0"}

    fator = indice_final / indice_base
    valor_corrigido = valor_original * fator
    variacao_pct = (fator - 1.0) * 100

    return {
        "status": "OK",
        "valor_original": round(valor_original, 2),
        "valor_corrigido": round(valor_corrigido, 2),
        "fator_correcao": round(fator, 6),
        "variacao_pct": round(variacao_pct, 2),
        "indice": indice_nome,
        "formula": f"fator = {indice_final:.4f} / {indice_base:.4f} = {fator:.6f}",
        "resultado_label": f"[SANDBOX_EXECUTED: {indice_nome} {variacao_pct:+.2f}% | fator = {fator:.4f} | R$ {valor_original:.2f} → R$ {valor_corrigido:.2f}]"
    }


def inflation_adjustment_from_rate(
    valor_original: float,
    taxa_acumulada_pct: float,
    indice_nome: str = "IPCA"
) -> dict:
    """
    WHY: Quando não se tem os valores absolutos do índice, usar a variação percentual
         acumulada diretamente. Ex: IPCA acumulado 12 meses = 4,83%.
    WHEN: Chamado quando há variação % disponível mas não os índices absolutos.
    HOW: fator = 1 + taxa_acumulada/100 → mesmo resultado que divisão de índices.
    WHAT_IF_FAILS: Declarar [APPROX] se taxa foi estimada pelo LLM.
    """
    fator = 1.0 + taxa_acumulada_pct / 100.0
    valor_corrigido = valor_original * fator

    return {
        "status": "OK",
        "valor_original": round(valor_original, 2),
        "valor_corrigido": round(valor_corrigido, 2),
        "fator_correcao": round(fator, 6),
        "variacao_pct": round(taxa_acumulada_pct, 2),
        "indice": indice_nome,
        "formula": f"fator = 1 + {taxa_acumulada_pct}/100 = {fator:.6f}",
        "nota": "[APPROX] se taxa foi estimada — verificar fonte oficial"
    }


# FALLBACK sem Python
# WHY: Cálculo manual com math.pow não é necessário — é multiplicação simples.
# WHEN: Python indisponível (LLM PARTIAL/MINIMAL).
def inflation_adjustment_simple(valor: float, taxa_pct: float) -> float:
    """Fallback puro stdlib."""
    return round(valor * (1.0 + taxa_pct / 100.0), 2)
```

### LLM_BEHAVIOR (quando Python indisponível)

```
STEP 1: Identificar indice (IGPM, IPCA, INPC, IPCA-E)
STEP 2: Identificar data_base e data_calculo
STEP 3: Buscar taxa_acumulada_pct do índice entre as datas
        - Fonte: FGV (IGPM), IBGE (IPCA/INPC/IPCA-E)
        - Se taxa não disponível: declarar [APPROX] com estimativa
STEP 4: fator = 1 + taxa_acumulada / 100
STEP 5: valor_corrigido = valor_original × fator
STEP 6: Declarar [APPROX] se taxa foi estimada
```

---

## Índices de Referência

| Índice | Órgão | Uso Principal | Periodicidade |
|--------|-------|---------------|---------------|
| IGPM | FGV | Contratos de aluguel, contratos empresariais | Mensal (dia 30) |
| IPCA | IBGE | Meta inflação BCB, contratos civis, poupança | Mensal (~dia 12) |
| INPC | IBGE | Salários, previdência, dívidas civis (padrão) | Mensal (~dia 12) |
| IPCA-E | IBGE | Precatórios (STF RE 870.947), dívidas judiciais | Mensal |
| INCC | FGV | Contratos de imóveis em construção | Mensal |

### Jurisprudência

```
STF RE 870.947 (2017): Precatórios corrigidos por IPCA-E + juros de poupança
STJ EREsp 727.842: INPC para dívidas civis em geral (anterior a IPCA-E)
Contratos de aluguel: Lei 8.245/91 — reajuste pelo índice pactuado (normalmente IGPM ou IPCA)
```

---

## Examples

### Exemplo 1 — Reajuste de Aluguel por IGPM

**Contexto**: Aluguel atual R$ 3.500. IGPM-FGV acumulado últimos 12 meses: 7,45%.

```python
resultado = inflation_adjustment_from_rate(
    valor_original=3500.0,
    taxa_acumulada_pct=7.45,
    indice_nome="IGPM-FGV"
)
# valor_corrigido = R$ 3.760,75
# fator = 1.0745
# variacao = +7.45%
```

### Exemplo 2 — Correção de Dívida Civil por INPC

**Contexto**: Dívida de R$ 25.000 venceu em Jan/2023. Calcular correção até Abr/2026.
INPC acumulado Jan/2023 a Abr/2026 (estimativa): 18,3%.

```python
resultado = inflation_adjustment_from_rate(
    valor_original=25000.0,
    taxa_acumulada_pct=18.3,
    indice_nome="INPC"
)
# valor_corrigido = R$ 29.575
# fator = 1.183
# [APPROX] — verificar INPC exato no IBGE para o período
```

### Exemplo 3 — Cálculo Completo de Dívida (Correção + Juros)

```
TOTAL = inflation_adjustment + compound_interest SOBRE capital corrigido

1. capital_corrigido = inflation_adjustment(25000, INPC_acumulado=18.3%)
   → R$ 29.575

2. juros_sobre_corrigido = compound_interest(29575, SELIC=10.75%, n=39 meses)
   → R$ 39.418,72

3. TOTAL = R$ 39.418,72 (+ multa se houver)

Bases: Art. 406 CC (SELIC), INPC-IBGE, Art. 394 CC (mora desde vencimento)
[APPROX] — verificar INPC e SELIC exatos nas fontes oficiais
```

---

## Cross-Domain Integration

```
QUANDO problema menciona dívida vencida com correção monetária:
  PIPELINE: inflation_adjustment → compound_interest
  ORDEM: sempre corrigir primeiro, depois aplicar juros sobre capital corrigido
  RAZÃO: Juros incidem sobre o capital em valor real (corrigido), não nominal

QUANDO problema menciona reajuste de aluguel:
  PIPELINE: legal.civil_law.contracts.financial_clauses → inflation_adjustment
  ÍNDICE_PADRÃO: IGPM se não especificado em contratos comerciais
  ÍNDICE_PADRÃO: IPCA se não especificado em contratos residenciais (pós-2022)
```

---

## What If Fails

| Falha | Ação |
|-------|------|
| Índice não especificado | Perguntar. Default: IPCA para dívidas civis, IGPM para aluguéis |
| Taxa acumulada desconhecida | [APPROX] com estimativa + recomendação de verificação na fonte |
| Período parcial (ex: 15 dias) | Interpolar linearmente: taxa_proporcional = taxa_mensal × (15/30) |
| fator < 1.0 (deflação) | Incomum no Brasil. Verificar se datas estão corretas. |
| Dois índices conflitantes | Usar o índice contratado. Se ausente no contrato: IPCA por padrão civil |

---

## Diff History
- **v00.33.0** (OPP-107): Criado com bridges cross-domain + integração legal-financeira
