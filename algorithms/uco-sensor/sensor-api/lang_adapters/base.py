"""
UCO-Sensor — LanguageAdapter Protocol
======================================
Interface que cada adaptador de linguagem deve implementar.

O pipeline espectral (FrequencyEngine) é agnóstico de linguagem —
recebe MetricVector com 9 canais. O adaptador faz a ponte entre
código-fonte bruto e esse vetor numérico.

Arquitetura:
  UCOBridgeRegistry.analyze(source, ext)
    → seleciona adapter por extensão
    → adapter.compute_metrics(source) → MetricVector
    → FrequencyEngine.analyze(history) → ClassificationResult

Para adicionar uma nova linguagem:
  1. Criar adapter em lang_adapters/<lingua>.py
  2. Implementar LanguageAdapter
  3. Registrar em UCOBridgeRegistry.REGISTRY
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


class LanguageAdapter(ABC):
    """
    Interface base para adaptadores de linguagem UCO.

    Cada adaptador recebe código-fonte como string e produz
    um MetricVector com os 9 canais UCO preenchidos.
    """

    #: Extensões de arquivo suportadas por este adaptador
    EXTENSIONS: tuple[str, ...] = ()

    #: Nome legível da linguagem
    LANGUAGE: str = "unknown"

    @abstractmethod
    def compute_metrics(
        self,
        source: str,
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
    ) -> MetricVector:
        """
        Analisa source code e retorna MetricVector.

        Deve ser thread-safe (instâncias compartilhadas entre requests).
        Não deve lançar exceções — retornar vetor mínimo em caso de erro.
        """
        ...

    def supports(self, extension: str) -> bool:
        """True se o adaptador suporta a extensão (ex: '.js', 'js')."""
        ext = extension.lower().lstrip(".")
        return any(e.lstrip(".") == ext for e in self.EXTENSIONS)
