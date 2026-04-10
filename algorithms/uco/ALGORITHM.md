---
algorithm_id: apex.uco.universal_code_optimizer_v4
name: "Universal Code Optimizer v4.0 (UCO)"
description: "Análise cirúrgica + otimização multi-engine para código multi-linguagem. AST+CFG+DSM+Halstead+HMC+SA. Implementação real para uco_quality_gate (APEX OPP-68)."
version: v4.0
status: ADOPTED
opp: OPP-120
file: universal_code_optimizer_v4.py
lines: 4152
---

# Universal Code Optimizer v4.0

## Entry Point para APEX

```python
# Uso no uco_quality_gate:
import sys
sys.path.insert(0, "/path/to/algorithms/uco/")
from universal_code_optimizer_v4 import UniversalCodeOptimizer

uco = UniversalCodeOptimizer()

# Análise rápida (apenas AST — sem numpy):
result = uco.analyze(code_str)
# result.metrics.halstead_bugs, result.metrics.hamiltonian, etc.

# Otimização rápida (sem numpy — para PoT < 100 linhas):
output = uco.quick_optimize(code_str)
# output.optimized_code, output.initial_analysis, output.final_analysis
```

## Dependências

- `ast` (stdlib — sempre disponível)
- `numpy` (opcional — apenas para `optimize()` HMC; `quick_optimize()` e `analyze()` NÃO precisam)
- `pygments` (opcional — para análise multi-linguagem; fallback para Python-only sem ele)

## Disponibilidade por Runtime

| Runtime | Disponibilidade | Método |
|---------|----------------|--------|
| FULL_CLAUDE_CODE | ✅ Completo | git_clone via algorithms/uco/ |
| FULL_DEEPSEEK @sandbox | ✅ quick_optimize + analyze | numpy disponível |
| FULL_GROK | ✅ quick_optimize + analyze | sem subprocess |
| PARTIAL_CHATGPT_CI | ✅ quick_optimize + analyze | file_upload |
| MINIMAL | ❌ | LLM_BEHAVIOR fallback |
