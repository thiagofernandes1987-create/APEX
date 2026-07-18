"""
Marco 70 — Sprint AI: extensão aditiva da CFG do UCO core + avaliação
dataflow/taint-tracking real para netty
=======================================================================

Pedido do usuário: "Crie então o motor dataflow/taint-tracking real e
verifique se com o UCO v4 se é possível encontrar netty via HMC ou SA,
[...] ou verifique a possibilidade de criarmos algo híbrido com o UCO V4
e UCO sensor [...] OU SE EXISTE ALGUMA BIBLIOTECA OU ALGO OPENSOURCE [...]".

Achados (Sprint AI):

1. ``algorithms/uco/universal_code_optimizer_v4.py::PythonCFGBuilder`` já
   constrói uma CFG real (entry/exit, if/for/while/try, back-edges) com
   defs/uses por nó — mas só para ``ast.Assign`` (metadata
   ``python_defs_uses``). Estendido (aditivamente, zero regressão) para
   também expor ``uses`` em ``ast.Return`` e no fallback genérico (que
   cobre ``ast.Expr`` — chamadas soltas como ``os.system(cmd)``), para
   que motores de dataflow consigam correlacionar variáveis tainted que
   alcançam um sink sem reimplementar a coleta de uses.
2. O projeto **já tem** um motor de dataflow/taint-tracking real e
   intraprocedural — ``sast/taint_engine.py::TaintAnalyzer`` (M7.2,
   pré-existente), com merge de branches (if/try/for/while),
   sources/sinks/sanitizers tipados e SAST040-045. Já integrado em
   ``uco_bridge.py`` e exposto via API. Não precisou ser recriado.
3. HMC e SA (``universal_code_optimizer_v4.py``) são confirmados como
   otimizadores de busca de autofix (Hamiltonian Monte Carlo / Simulated
   Annealing sobre o mesmo "Hamiltoniano de qualidade de código") — não
   são detectores. Propagation (``governance/propagation.py``) é
   correlação cruzada com defasagem sobre séries temporais de métricas
   — não analisa um único diff de código. Nenhum dos três é aplicável a
   netty CVE-2019-20444 (Java, bug interno de parsing em
   ``HttpObjectDecoder.java``, sem shape de source→sink).
4. Empiricamente (``paper/cve_diff_check.py`` contra os SHAs reais),
   nenhum dos 9 canais de métrica cruza o threshold de 15% entre
   vulnerável e corrigido — sem sinal estrutural. Cobertura correta para
   netty = SCA (Grype/Trivy/OSV-Scanner/Dependency-Check), não SAST.

Este arquivo fixa o comportamento aditivo da extensão da CFG (item 1) e
a presença do TaintAnalyzer (item 2).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_UCO_PATH = Path(__file__).resolve().parents[3] / "uco"
if str(_UCO_PATH) not in sys.path:
    sys.path.insert(0, str(_UCO_PATH))

# (DT/Achado #9) Este teste valida o UCO V4 ORIGINAL do monorepo
# (`algorithms/uco/universal_code_optimizer_v4.py`), que NÃO existe num checkout
# isolado só do `uco-sensor`.  Antes o `import` de topo abortava a COLETA INTEIRA
# do pytest (ModuleNotFoundError → "1 error during collection", 0 testes rodam)
# fora do monorepo.  `importorskip` pula só este módulo, graciosamente.
_uco_v4 = pytest.importorskip(
    "universal_code_optimizer_v4",
    reason="requer o monorepo completo (algorithms/uco/); ausente em checkout isolado",
)
PythonCFGBuilder = _uco_v4.PythonCFGBuilder

from sast.taint_engine import TaintAnalyzer  # noqa: E402


def _defs_uses(src: str):
    b = PythonCFGBuilder()
    g = b.build(src)
    return g.metadata.get("python_defs_uses", {})


# ── CFG defs/uses extension ────────────────────────────────────────────────

def test_TAM01_assign_node_has_defs_and_uses():
    du = _defs_uses("x = y + 1\n")
    assert any(d["defs"] == {"x"} and d["uses"] == {"y"} for d in du.values())


def test_TAM02_bare_call_statement_exposes_uses_no_defs():
    du = _defs_uses("os.system(cmd)\n")
    matches = [d for d in du.values() if "cmd" in d["uses"]]
    assert matches
    assert all(d["defs"] == set() for d in matches)
    assert any("os" in d["uses"] for d in matches)


def test_TAM03_return_statement_exposes_uses_no_defs():
    du = _defs_uses("def f(x):\n    return x\n")
    matches = [d for d in du.values() if "x" in d["uses"]]
    assert matches
    assert all(d["defs"] == set() for d in matches)


def test_TAM04_cfg_build_still_succeeds_with_branches_and_loops():
    src = (
        "def f(x):\n"
        "    if x:\n"
        "        for i in range(x):\n"
        "            os.system(i)\n"
        "    return x\n"
    )
    b = PythonCFGBuilder()
    g = b.build(src)
    assert g.entry is not None and g.exit is not None
    assert len(g.reachable_from_entry()) > 1


def test_TAM05_no_regression_in_existing_assign_metadata_shape():
    du = _defs_uses("a = 1\nb = a\n")
    shapes = list(du.values())
    assert {"defs", "uses"} <= set(shapes[0].keys())


# ── Pre-existing real taint engine (M7.2) — confirms it already exists ─────

def test_TAM06_taint_engine_detects_command_injection():
    src = (
        "import os\n"
        "def run():\n"
        "    cmd = os.environ['CMD']\n"
        "    os.system(cmd)\n"
    )
    result = TaintAnalyzer().analyze(src)
    assert any(f.rule_id == "SAST041" for f in result.flows)


def test_TAM07_taint_engine_silent_when_sanitized():
    src = (
        "import os\n"
        "from urllib.parse import quote\n"
        "def run():\n"
        "    cmd = quote(os.environ['CMD'])\n"
        "    os.system(cmd)\n"
    )
    result = TaintAnalyzer().analyze(src)
    assert not any(f.rule_id == "SAST041" for f in result.flows)


def test_TAM08_taint_engine_tracks_through_branch_merge():
    src = (
        "def run(flag):\n"
        "    if flag:\n"
        "        cmd = input()\n"
        "    else:\n"
        "        cmd = 'ls'\n"
        "    os.system(cmd)\n"
    )
    result = TaintAnalyzer().analyze(src)
    assert any(f.rule_id == "SAST041" for f in result.flows)
