"""
UCO-Sensor — UCO Core (M13: absorção do Universal Code Optimizer V4)
====================================================================
O motor **Universal Code Optimizer V4** deixou de ser uma dependência externa
(`algorithms/uco/universal_code_optimizer_v4.py`, acessada via manipulação de
``sys.path``) e passou a ser **parte do pacote do UCO Sensor**.  Esta é a
absorção pedida: o V4 agora é um módulo interno, versionado com o sensor.

O arquivo `universal_code_optimizer_v4.py` neste pacote é uma cópia fiel do
V4 (4255 linhas, stdlib + pygments/numpy opcionais).  Todo o sensor deve
importar daqui — não mais do caminho externo:

    from uco_core import UniversalCodeOptimizer, UniversalAnalyzer
    from uco_core import GenericCFGBuilder, CFG, DSMEngine, HalsteadMetrics

Capacidades expostas (antes subutilizadas):
* ``UniversalCodeOptimizer.analyze()`` — H, bugs, complexity, dead_code,
  duplicates, score (Python profundo; stdlib-only).
* ``UniversalAnalyzer`` / ``GenericCFGBuilder`` — CFG por linguagem (Python
  nativo; genérico via Pygments para C/Rust/Java/…), base para o escopo-por-
  CFG do M11 e para taint/dataflow.
* ``DSMEngine`` — matriz de estrutura de dependências.
* ``HalsteadMetrics`` / ``FeatureExtractor`` / ``HamiltonianScorer``.
* HMC/Greedy/SA optimizers.
"""
from __future__ import annotations

from .universal_code_optimizer_v4 import (  # noqa: F401
    UniversalCodeOptimizer,
    UniversalAnalyzer,
    AnalysisResult,
    GenericCFGBuilder,
    PythonCFGBuilder,
    CFG,
    CFGNode,
    DSMEngine,
    DSMResult,
    HalsteadMetrics,
    AnalysisMetrics,
    FeatureExtractor,
    HamiltonianScorer,
    detect_language,
)

__all__ = [
    "UniversalCodeOptimizer",
    "UniversalAnalyzer",
    "AnalysisResult",
    "GenericCFGBuilder",
    "PythonCFGBuilder",
    "CFG",
    "CFGNode",
    "DSMEngine",
    "DSMResult",
    "HalsteadMetrics",
    "AnalysisMetrics",
    "FeatureExtractor",
    "HamiltonianScorer",
    "detect_language",
]

# Versão do V4 absorvido (rastreada junto ao sensor).
UCO_V4_ABSORBED = True
UCO_V4_SOURCE = "universal_code_optimizer_v4.py (4255 LOC, absorvido em Sprint BJ)"
