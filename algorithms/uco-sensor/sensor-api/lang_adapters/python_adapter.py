"""
UCO-Sensor — Python Adapter
=============================
Adaptador para Python que envolve UCOBridge (análise AST nativa)
como um LanguageAdapter padrão.

Delegação completa ao UCOBridge — que usa ast.parse para produzir
todos os 9 canais UCO com alta fidelidade para Python.
"""
from __future__ import annotations
import time
from typing import Optional
import sys
from pathlib import Path

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


class PythonAdapter(LanguageAdapter):
    """
    Adaptador UCO para Python (.py, .pyw, .pyi).

    Delega análise ao UCOBridge (ast.parse nativo do Python 3),
    que já implementa todos os 9 canais com suporte completo a:
      - CC via if/elif/for/while/except/assert/comprehensions/&&/||
      - ILR: while True sem break incondicional no top-level do body
      - DI: max_methods_per_class / 20 (GAP-R01)
      - DSM_d: imports / (funções × 2)
      - dead: código após return/raise no mesmo bloco
      - dups: Level 1 (linhas repetidas) + Level 2 (blocos de 3 linhas)
      - H: Halstead effort / LOC × 0.01
      - bugs: volume / 3000
    """

    EXTENSIONS = (".py", ".pyw", ".pyi")
    LANGUAGE   = "python"

    def __init__(self, mode: str = "full"):
        """
        Args:
            mode: "fast" | "full" | "minimal" — modo de análise UCOBridge.
                  "full" é o default para máxima fidelidade.
        """
        self._mode = mode
        self._bridge = None  # lazy init

    def _get_bridge(self):
        if self._bridge is None:
            # Import lazy para evitar circular/import-time crash
            _SENSOR = Path(__file__).resolve().parent.parent
            if str(_SENSOR) not in sys.path:
                sys.path.insert(0, str(_SENSOR))
            from sensor_core.uco_bridge import UCOBridge
            self._bridge = UCOBridge(mode=self._mode)
        return self._bridge

    def compute_metrics(
        self,
        source: str,
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
        file_extension: str = ".py",
    ) -> MetricVector:
        if timestamp is None:
            timestamp = time.time()

        bridge = self._get_bridge()
        mv = bridge.analyze(
            source,
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=timestamp,
        )
        return mv
