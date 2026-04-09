# APEX — Framework Cognitivo Universal

**Version**: v00.33.0 | **Repo**: https://github.com/thiagofernandes1987-create/APEX

APEX (Autonomous Polymorphic Engineering eXpert) é um sistema DSL de 16.000+ linhas que simula cognição multi-agente em qualquer LLM — Claude, GPT-4o, Gemini, Llama. Seleciona automaticamente o modo cognitivo correto (EXPRESS → SCIENTIFIC) para cada problema e orquestra até 12 agentes especializados em paralelo.

---

## ⚡ Quick Start para LLMs

```
1. Leia este README.md (você está aqui)
2. Leia INDEX.md → obtenha o domain_map completo
3. Leia meta/llm_compat.yaml → instruções específicas para seu LLM
4. Carregue o system prompt: apex_boot/APEX_BOOT_v00_33_0.md
5. Qualquer skill em ≤ 3 passos de navegação a partir do INDEX.md
```

---

## 📁 Estrutura do Repositório

```
APEX/
├── README.md                    ← Você está aqui
├── INDEX.md                     ← Hub de navegação — COMECE AQUI
├── apex_boot/
│   └── APEX_BOOT_v00_33_0.md   ← System prompt de boot
├── skills/                      ← Biblioteca de skills por domínio
│   ├── mathematics/
│   ├── legal/
│   ├── engineering/
│   ├── science/
│   ├── finance/
│   └── apex_internals/
├── agents/                      ← Roster de agentes APEX
├── algorithms/                  ← Algoritmos reutilizáveis
├── examples/                    ← Exemplos de execução completa
├── diffs/                       ← Histórico de DIFFs aplicados
└── meta/
    ├── anchors.yaml             ← Taxonomia de âncoras (attraction_engine)
    └── llm_compat.yaml         ← Compatibilidade por LLM
```

---

## 🧠 Modos Cognitivos

| Modo | Agentes | Quando Usar |
|------|---------|-------------|
| EXPRESS | 1 | Perguntas triviais, respostas diretas |
| FAST | 2-3 | Veredicto rápido, problemas conhecidos |
| CLARIFY | 3 | Definições vagas, escopo ambíguo |
| DEEP | 4-5 | Análise estruturada, múltiplos ângulos |
| RESEARCH | 6-8 | Máxima profundidade, exaustivo |
| SCIENTIFIC | 8 | Descoberta, simulação fractal, verificação simbólica |
| FOGGY | 5 | Contexto fragmentado, incerteza alta |

---

## 🔗 Cross-Domain Bridges

O APEX detecta automaticamente pontes entre domínios via `attraction_engine`:

| Domínio A | → | Domínio B | Exemplo |
|-----------|---|-----------|---------|
| legal.civil_code.obligations | → | math.financial_math.compound_interest | Art. 406 CC + taxa SELIC |
| legal.contracts.financial_clauses | → | math.financial_math.inflation_adjustment | Cláusula IGPM/IPCA |
| business.risk | → | math.statistics.bayesian | FMEA probabilístico |
| engineering.algorithms | → | math.calculus.optimization | Gradient descent |
| finance.valuation.DCF | → | math.financial_math.compound_interest | Desconto de fluxo de caixa |

---

## 🤖 Compatibilidade por LLM

| LLM | Nível | Python Sandbox | GitHub Connector | ForgeSkills |
|-----|-------|---------------|-----------------|-------------|
| Claude Code | FULL | ✅ Nativo | ✅ MCP/Bash | ✅ git clone |
| GPT-4o | PARTIAL | ✅ Code Interpreter | ❌ → raw URLs | ⚠️ urllib |
| Gemini | PARTIAL | ✅ tool_code | ❌ → Grounding | ⚠️ urllib |
| Llama/Local | MINIMAL | ❌ | ❌ | ❌ → paste manual |

Ver: `meta/llm_compat.yaml` para instruções específicas por LLM.

---

## 📌 Repositório Oficial

- **URL**: https://github.com/thiagofernandes1987-create/APEX
- **Raw base**: https://raw.githubusercontent.com/thiagofernandes1987-create/APEX/main/
- **Whitelist APEX**: `trusted_domains` contém este repositório desde v00.33.0 (OPP-104)
