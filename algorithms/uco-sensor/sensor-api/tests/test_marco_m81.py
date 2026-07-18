"""
Marco 81 — M13: absorção do UCO V4 no pacote do sensor (`uco_core`)
===================================================================
O Universal Code Optimizer V4 deixou de ser dependência externa (import via
sys.path para `algorithms/uco`) e passou a ser parte do UCO Sensor, no pacote
interno `uco_core`. Estes testes pinam que:

1. o `uco_core` é importável de dentro do sensor (sem manipular sys.path);
2. `UniversalCodeOptimizer.analyze` funciona para Python;
3. o `UniversalAnalyzer`/CFG genérico funciona para C (corrige o diagnóstico
   errôneo da Sprint BG — o V4 NÃO retorna None para não-Python; havia sido
   invocado com kwarg errado engolido por try/except);
4. os bridges de autofix resolvem o V4 pela cópia interna.
"""
from __future__ import annotations

import uco_core


def test_T81_uco_core_absorbed_flag():
    assert uco_core.UCO_V4_ABSORBED is True
    assert "universal_code_optimizer_v4" in uco_core.UCO_V4_SOURCE


def test_T81_public_api_importable():
    from uco_core import (
        UniversalCodeOptimizer, UniversalAnalyzer, GenericCFGBuilder,
        CFG, DSMEngine, HalsteadMetrics,
    )
    assert UniversalCodeOptimizer is not None
    assert UniversalAnalyzer is not None
    assert GenericCFGBuilder is not None


def test_T81_analyze_python_returns_metrics():
    uco = uco_core.UniversalCodeOptimizer()
    r = uco.analyze("def f(x):\n    y = 1\n    return x + 1\n", language_hint="python")
    # AnalysisResult com métricas
    assert hasattr(r, "metrics")
    assert r.metrics.cyclomatic_complexity >= 1


def test_T81_generic_cfg_works_for_c():
    """Corrige BG: o V4 computa métricas C via CFG genérico (não retorna None)."""
    ua = uco_core.UniversalAnalyzer()
    r = ua.analyze("int f(int n){ if (n>0){ return 1; } return 0; }", language_hint="c")
    assert r.cfg is not None
    assert len(r.cfg.nodes) >= 2
    assert r.metrics.reachable_count >= 1
    assert r.metrics.cyclomatic_complexity >= 1


def test_T81_autofix_bridge_resolves_internal_v4():
    from sensor_core.autofix.transforms.uco_transform_bridge import _ucotx
    # uma classe de transform conhecida do V4 deve resolver pela cópia interna
    cls = _ucotx("ConstantFoldingTransform")
    assert cls is not None
