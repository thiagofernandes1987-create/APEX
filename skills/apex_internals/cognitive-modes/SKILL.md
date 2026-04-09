---
skill_id: apex_internals.cognitive_modes
name: "Cognitive Modes — BDS Simplex Mode Selector"
description: "Documenta os 7 modos cognitivos do APEX e como o BDS Simplex seleciona o modo certo. Inclui EXPRESS, FAST, CLARIFY, DEEP, RESEARCH, SCIENTIFIC, FOGGY."
version: v00.33.0
status: ADOPTED
domain_path: apex_internals/cognitive-modes
anchors:
  - cognitive_mode
  - BDS_simplex
  - wE
  - wD
  - wK
  - EXPRESS
  - FAST
  - CLARIFY
  - DEEP
  - RESEARCH
  - SCIENTIFIC
  - FOGGY
  - R_acum
  - mode_selection
  - epistemic_uncertainty
risk: safe
languages: [dsl]
llm_compat: {claude: full, gpt4o: full, gemini: full, llama: full}
apex_version: v00.33.0
---

# Cognitive Modes — BDS Simplex

## Why This Skill Exists

O APEX não usa o mesmo "modo" para todos os problemas. Um problema trivial ("quanto é 2+2?")
e uma descoberta científica ("modelar propagação de ondas em meio dispersivo") requerem
processos radicalmente diferentes.

O **BDS Simplex** (Barycentric Difficulty Simplex) seleciona o modo cognitivo correto
baseado em 3 dimensões de dificuldade — não na preferência do LLM.

## BDS Simplex — 3 Vértices

```
         K
        /|\
       / | \
      /  |  \
     /   |   \
    E────────D

E = epistemic uncertainty (incerteza do domínio)
D = density/coupling (acoplamento lógico dos requisitos)
K = knowledge gap (distância entre problema e skills no registry)

wE = E_raw / (E_raw + D_raw + K_raw)
wD = D_raw / (...)
wK = K_raw / (...)

Vértice dominante (wX > 0.5) → sugere o modo
```

## Mode Selection Map

| Modo | Agentes | Trigger | Token Budget |
|------|---------|---------|-------------|
| EXPRESS | 1 | Problema trivial, resposta direta | 500 |
| FAST | 2-3 | Veredicto rápido, domínio conhecido | 2.000 |
| CLARIFY | 3 | wE alto, definição vaga do problema | 3.500 |
| DEEP | 4-5 | Análise estruturada multi-perspectiva | 8.000 |
| RESEARCH | 6-8 | Máxima profundidade, exaustivo | 12.000 |
| SCIENTIFIC | 8 | Descoberta, simulação fractal, verificação simbólica | 12.000 |
| FOGGY | 5 | wE > 0.5 AND Effective_CFI > 0.6 | 6.000 |

## Mode Details

### EXPRESS
```
Quando: Problemas triviais, perguntas factuais simples
Agentes: pmi_pm apenas (define e responde)
Skip: pré_mortem gate (G1)
Exemplo: "Qual a capital do Brasil?"
```

### FAST
```
Quando: Problema conhecido, risco baixo, veredicto necessário
Agentes: pmi_pm + critic (ou engineer)
Exemplo: "Qual padrão de design usar para este caso simples?"
```

### CLARIFY
```
Quando: Problema ambíguo, definição vaga, escopo incerto
Agentes: pmi_pm + architect + researcher
Foco: Perguntas antes de resolver
Exemplo: "Quero melhorar meu sistema" (sem detalhes)
```

### DEEP
```
Quando: Problema real com múltiplas perspectivas, risco moderado
Agentes: 4-5 (pmi_pm + architect + engineer + critic + meta_reasoning)
Inclui: UCO gate, hipótese DAG, R_acum monitoring
Exemplo: Análise de arquitetura de software
```

### RESEARCH
```
Quando: Domínio com K alto (knowledge gap), evidências escassas
Agentes: 6-8 incluindo researcher + bayesian_curator
Inclui: External Critic Profile, Sequential Thinking, evidência chain
Exemplo: Pesquisa científica, análise de mercado nova
```

### SCIENTIFIC
```
Quando: Descoberta, hipóteses competindo, simulação necessária
Agentes: 8 incluindo scientist_agent (auto-spawned)
Inclui: fractal_cognitive_simulator, symbolic_executor, Monte Carlo
Steps: STEP_SCI_01 a STEP_SCI_10 obrigatórios em ordem (SR_06)
Exemplo: Modelagem matemática, análise estatística avançada
```

### FOGGY
```
Quando: wE > 0.5 AND Effective_CFI > 0.6 (contexto fragmentado)
Agentes: 5 incluindo ANCHOR_DESTROYER (se first_principles_ratio < 0.3)
Objetivo: Recuperar contexto e reduzir incerteza antes de prosseguir
Exemplo: Problema com informações contraditórias ou incompletas
```

## R_acum — Reliability Monitor

```
R_acum = ∏(1 - p_fail_blk) para todos os blocos executados
         (janela deslizante N=20 blocos)

Thresholds:
  R_acum < 0.50 → RELIABILITY_WARNING + replanning obrigatório
  R_acum < 0.30 → EARLY_EXIT forçado (status PARTIAL)

Monitorado em: DEEP, RESEARCH, SCIENTIFIC
Enforcement: MCFEReliabilityMonitor (primário), meta_reasoning (secundário)
Rule: SR_10
```

## LLM_BEHAVIOR — Seleção Manual de Modo

```
Se o BDS Simplex não está disponível (LLM MINIMAL):

PASSO 1: Avaliar a dificuldade
  - O domínio é novo/incerto? → wE alto → FOGGY ou CLARIFY
  - Há muitas partes interdependentes? → wD alto → DEEP ou RESEARCH  
  - Preciso de conhecimento externo? → wK alto → RESEARCH

PASSO 2: Selecionar modo
  - Pergunta trivial + domínio conhecido → EXPRESS
  - Problema técnico claro → DEEP
  - Pesquisa com incerteza → RESEARCH ou SCIENTIFIC
  - Ambíguo/incompleto → CLARIFY ou FOGGY

PASSO 3: Declarar modo escolhido
  [COGNITIVE_MODE: DEEP | wE≈0.2 wD≈0.6 wK≈0.2 | APPROX]
```

## Diff History
- **v00.33.0**: Criado para documentação dos modos cognitivos no super-repo
