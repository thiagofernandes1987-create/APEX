"""
UCO-Sensor FrequencyEngine — Orquestrador Principal
=====================================================
FrequencyEngine: executa o pipeline completo transmissor → receptor.

Pipeline:
  MetricVector[] → MetricSignalBuilder → MetricSignal
                → SpectralAnalyzer   → List[SpectralProfile]
                → FrequencyClassifier → ClassificationResult
                → [opcional] DBSCANDiscovery → List[SignatureCandidate]

Uso básico:
  engine = FrequencyEngine()
  result = engine.analyze(history, module_id="auth.login")
  print(result.plain_english)
"""
from __future__ import annotations
import time
import numpy as np
from typing import List, Optional

from core.data_structures import (
    MetricVector, MetricSignal, SpectralProfile,
    ClassificationResult, SignatureCandidate
)
from transmitter.metric_signal_builder import MetricSignalBuilder
from receptor.spectral_analyzer import SpectralAnalyzer
from receptor.frequency_classifier import FrequencyClassifier
from receptor.error_signatures import ErrorSignatureLibrary
from receptor.change_point_detector import ChangePointDetector
from discovery.dbscan_discovery import DBSCANDiscovery


class FrequencyEngine:
    """
    Motor principal do UCO-Sensor.

    Integra transmissor e receptor em um único pipeline coeso.
    Todos os componentes são instanciados com defaults sensatos e
    podem ser substituídos para customização.

    Parâmetros
    ----------
    window_fn        : função de janelamento do transmissor ("hann"|"hamming"|"blackman")
    wavelet          : wavelet para análise multi-resolução ("db4"|"haar")
    wav_levels       : número de níveis da decomposição wavelet
    pelt_penalty     : penalidade de regularização do PELT
    min_confidence   : confidence mínima para classificar vs UNKNOWN_PATTERN
    verbose          : imprimir resumo de cada análise
    """

    def __init__(
        self,
        window_fn: str = "hann",
        wavelet: str = "db4",
        wav_levels: int = 5,
        pelt_penalty: float = 2.5,
        min_confidence: float = 0.28,
        verbose: bool = False,
    ):
        self.builder    = MetricSignalBuilder(window_fn=window_fn)
        self.analyzer   = SpectralAnalyzer(wavelet=wavelet, wav_levels=wav_levels)
        self.library    = ErrorSignatureLibrary()
        self.detector   = ChangePointDetector(penalty=pelt_penalty, min_size=4)
        self.classifier = FrequencyClassifier(
            library=self.library,
            cp_detector=self.detector,
            min_confidence=min_confidence,
        )
        self.dbscan     = DBSCANDiscovery()
        self.verbose    = verbose

    # ─── API principal ────────────────────────────────────────────────────────

    def analyze(
        self,
        history: List[MetricVector],
        module_id: Optional[str] = None,
    ) -> Optional[ClassificationResult]:
        """
        Executa pipeline completo sobre histórico de MetricVectors.

        Retorna None se N < MIN_SAMPLES_FOR_SPECTRAL (5).
        """
        t0 = time.perf_counter()

        # Garantir module_id consistente
        if module_id and history:
            for mv in history:
                mv.module_id = module_id

        # 1. Transmissor: MetricVector[] → MetricSignal
        signal = self.builder.build(history, verbose=self.verbose)
        if signal is None:
            return None

        # 2. Receptor: MetricSignal → List[SpectralProfile]
        profiles = self.analyzer.analyze_full(signal)

        # 3. Classificação: profiles + signal → ClassificationResult
        result = self.classifier.classify(profiles, signal)

        elapsed_ms = (time.perf_counter() - t0) * 1000
        result.analysis_timestamp = time.time()

        if self.verbose:
            self._print_result(result, elapsed_ms)

        return result

    def analyze_batch(
        self,
        module_histories: dict,   # {module_id: List[MetricVector]}
    ) -> dict:                    # {module_id: ClassificationResult}
        """Analisa múltiplos módulos e retorna dict de resultados."""
        results = {}
        for module_id, history in module_histories.items():
            r = self.analyze(history, module_id=module_id)
            if r is not None:
                results[module_id] = r
        return results

    def discover_new_signatures(
        self,
        module_histories: dict,   # {module_id: List[MetricVector]}
    ) -> List[SignatureCandidate]:
        """
        Roda pipeline até SpectralProfiles para todos os módulos e
        executa DBSCAN discovery em busca de padrões novos.
        """
        all_profile_sets = []
        all_module_ids   = []

        for module_id, history in module_histories.items():
            signal = self.builder.build(history)
            if signal is None:
                continue
            profiles = self.analyzer.analyze_full(signal)
            all_profile_sets.append(profiles)
            all_module_ids.append(module_id)

        # Embeddings das assinaturas existentes para filtro de novidade
        existing_embs = [sig.embedding for sig in self.library.signatures]
        existing_arr = np.array(existing_embs) if existing_embs else None

        candidates = self.dbscan.discover(
            all_profile_sets,
            existing_embeddings=existing_arr,
            module_ids=all_module_ids,
        )

        if self.verbose:
            print(self.dbscan.summary(candidates))

        return candidates

    # ─── Impressão de resultados ──────────────────────────────────────────────

    def _print_result(self, r: ClassificationResult, elapsed_ms: float) -> None:
        SEV_COLOR = {"INFO": "\033[94m", "WARNING": "\033[93m", "CRITICAL": "\033[91m"}
        RESET = "\033[0m"
        color = SEV_COLOR.get(r.severity, "")

        print(f"\n{'='*65}")
        print(f"  UCO-Sensor FrequencyEngine — {r.module_id}")
        print(f"{'='*65}")
        print(f"  {color}[{r.severity}]{RESET} {r.primary_error}")
        print(f"  Confidence   : {r.primary_confidence:.1%}")
        print(f"  Severity Score: {r.severity_score:.3f}")
        print(f"  Banda dominante: {r.dominant_band} — {r.band_description[:60]}")

        if r.change_point:
            cp = r.change_point
            print(f"  Onset detectado: commit idx {cp.commit_idx} "
                  f"({cp.commit_hash[:8] if cp.commit_hash else 'N/A'}) "
                  f"| confiança {cp.confidence:.1%}")

        print(f"\n  {r.plain_english[:120]}...")

        if r.hypotheses:
            print(f"\n  Top-3 hipóteses:")
            for i, h in enumerate(r.hypotheses[:3]):
                print(f"    {i+1}. {h.error_type:<38} conf={h.confidence:.1%}")

        if r.suggested_transforms:
            print(f"\n  Transforms sugeridos: {r.suggested_transforms}")
            print(f"  ΔH potencial: {r.potential_delta_h:+.1f}")

        print(f"\n  Commits analisados: {r.n_commits_analyzed} | "
              f"Latência: {elapsed_ms:.1f}ms")
        print(f"{'='*65}\n")
