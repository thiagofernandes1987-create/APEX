"""
UCO-Sensor FrequencyEngine — Analisador de Propagação de Sinal
===============================================================
PropagationAnalyzer: computa a impressão digital de propagação entre canais.

Fundamento físico (CSL transposição):
  No CSL, defeitos diferentes têm velocidades de propagação de onda distintas.
  Um vazio total reflete a onda instantaneamente (sem propagação).
  Uma inclusão de solo causa atenuação gradual ao longo da profundidade.

  Para métricas de código:
    - "Velocidade alta" = mudança simultânea em múltiplos canais (evento agudo)
    - "Velocidade baixa" = propagação cascateada ao longo de commits (degradação crônica)

Três padrões mensuráveis (descobertos empiricamente):

  ISOLATED (spread=0, n=1):
    Um único canal se move. Os outros ficam estáveis.
    Analogia CSL: spike de ruído pontual — sem propagação lateral.
    Tipos: LOOP_RISK (ILR isolado), DEAD_CODE_DRIFT (dead isolado)

  SIMULTANEOUS (spread ≤ 2):
    Múltiplos canais disparam ao mesmo tempo (mesmo commit ou commits adjacentes).
    Analogia CSL: ruptura total — onda colapsa em todos os caminhos ao mesmo tempo.
    Tipos: AI_CODE_BOMB (dead+dups+ILR juntos), DEP_CYCLE (DSM_c+DI juntos),
           COGNITIVE_EXPLOSION (CC+H juntos), REFACTORING (H+CC juntos)

  CASCADED_SLOW (spread > 10):
    Canais disparam em sequência ao longo de muitos commits.
    Analogia CSL: propagação em meio heterogêneo — cada camada responde com delay.
    Tipos: GOD_CLASS (DI→CC→DSM_d, spread≈21), TECH_DEBT (bugs→CC→H, spread≈45)

Poder diagnóstico principal:
  GOD_CLASS vs COGNITIVE_EXPLOSION (o problema mais difícil):
    GOD_CLASS   → CASCADED_SLOW, DI lidera CC por ~16 commits
    COGNITIVE   → SIMULTANEOUS,  CC e H disparam juntos em ≤2 commits
  → onset_spread sozinho resolve essa ambiguidade!
"""
from __future__ import annotations
import numpy as np
from typing import List, Dict, Optional, Tuple

from core.data_structures import MetricSignal, PropagationFingerprint
from core.constants import CHANNEL_NAMES
from receptor.change_point_detector import ChangePointDetector


class PropagationAnalyzer:
    """
    Computa PropagationFingerprint a partir de MetricSignal.

    Algoritmo:
      1. Para cada canal primário da assinatura detectada, rodar PELT individualmente
      2. Registrar o commit_idx de cada onset
      3. Calcular onset_spread = max(onset_idx) - min(onset_idx)
      4. Classificar em ISOLATED / SIMULTANEOUS / CASCADED_FAST / CASCADED_SLOW
      5. Computar propagation_velocity = n_channels / spread

    Parâmetros
    ----------
    pelt_penalty : penalidade de regularização do PELT. 2.5 calibrado para dados reais.
    simultaneous_threshold : spread em commits para considerar "simultâneo" (default: 2)
    cascaded_fast_threshold: spread mínimo para CASCADED_FAST (default: 3)
    cascaded_slow_threshold : spread mínimo para CASCADED_SLOW (default: 10)
    """

    SIMULTANEOUS_THRESH  = 2
    CASCADED_FAST_THRESH = 3
    CASCADED_SLOW_THRESH = 10

    def __init__(self, pelt_penalty: float = 2.5):
        self.cp_detector = ChangePointDetector(
            model="rbf",
            penalty=pelt_penalty,
            min_size=4,
        )

    # ─── API pública ─────────────────────────────────────────────────────────

    def compute(
        self,
        signal: MetricSignal,
        primary_channels: List[str],
    ) -> PropagationFingerprint:
        """
        Computa a impressão digital de propagação para os canais primários.

        Parâmetros
        ----------
        signal           : MetricSignal normalizado e janelado
        primary_channels : canais da assinatura detectada (ex: ["CC","DSM_d","DI"])
        """
        # Detectar onset individual por canal
        onsets: Dict[str, Optional[int]] = {}
        for ch in primary_channels:
            if ch in CHANNEL_NAMES:
                cp = self.cp_detector.detect(signal, [ch])
                onsets[ch] = cp.commit_idx if cp else None

        # Filtrar canais com onset detectado
        valid = {ch: idx for ch, idx in onsets.items() if idx is not None}

        return self._build_fingerprint(valid, primary_channels)

    def compute_all(
        self,
        signal: MetricSignal,
    ) -> Dict[str, PropagationFingerprint]:
        """
        Computa fingerprint para grupos pré-definidos de canais.
        Útil para comparar múltiplas assinaturas candidatas.
        """
        # Grupos diagnósticos baseados nas assinaturas
        groups = {
            "bomb_group":   ["dead", "dups", "ILR"],
            "god_group":    ["CC", "DSM_d", "DI"],
            "cycle_group":  ["DSM_c", "DI"],
            "debt_group":   ["H", "CC", "bugs"],
            "single_ILR":   ["ILR"],
            "single_dead":  ["dead"],
            "cog_group":    ["CC", "H"],
        }
        return {name: self.compute(signal, channels)
                for name, channels in groups.items()}

    # ─── Construção do fingerprint ────────────────────────────────────────────

    def _build_fingerprint(
        self,
        valid: Dict[str, int],   # {channel: onset_commit_idx}
        all_channels: List[str],
    ) -> PropagationFingerprint:

        n = len(valid)

        if n == 0:
            return PropagationFingerprint(
                propagation_pattern="NO_ONSET",
                onset_spread_commits=0,
                channel_onset_order=[],
                channel_onset_indices=[],
                leading_channel=None,
                lagging_channel=None,
                n_channels_activated=0,
                propagation_velocity=0.0,
            )

        if n == 1:
            ch, idx = list(valid.items())[0]
            return PropagationFingerprint(
                propagation_pattern="ISOLATED",
                onset_spread_commits=0,
                channel_onset_order=[ch],
                channel_onset_indices=[idx],
                leading_channel=ch,
                lagging_channel=None,
                n_channels_activated=1,
                propagation_velocity=float("inf"),   # onset puro — sem propagação
            )

        # Ordenar por onset
        ordered = sorted(valid.items(), key=lambda x: x[1])
        order_names   = [ch  for ch, _  in ordered]
        order_indices = [idx for _, idx in ordered]

        spread   = order_indices[-1] - order_indices[0]
        leading  = order_names[0]
        lagging  = order_names[-1]
        velocity = n / max(1, spread)

        # Classificar padrão
        if spread <= self.SIMULTANEOUS_THRESH:
            pattern = "SIMULTANEOUS"
        elif spread <= self.CASCADED_FAST_THRESH:
            pattern = "CASCADED_FAST"
        elif spread <= self.CASCADED_SLOW_THRESH:
            pattern = "CASCADED_SLOW"
        else:
            pattern = "CASCADED_SLOW"  # spread > 10 = lento por definição

        return PropagationFingerprint(
            propagation_pattern=pattern,
            onset_spread_commits=spread,
            channel_onset_order=order_names,
            channel_onset_indices=order_indices,
            leading_channel=leading,
            lagging_channel=lagging,
            n_channels_activated=n,
            propagation_velocity=round(velocity, 4),
        )

    # ─── Funções diagnósticas auxiliares ─────────────────────────────────────

    def discriminate_god_vs_cognitive(
        self,
        signal: MetricSignal,
    ) -> str:
        """
        Discriminador especializado para GOD_CLASS vs COGNITIVE_EXPLOSION.

        Este é o par mais difícil de distinguir por análise espectral sozinha.
        A propagação resolve de forma definitiva:

          GOD_CLASS   → spread ≥ 10  (DI lidera CC por ~16 commits)
          COGNITIVE   → spread ≤ 2   (CC e H disparam juntos)

        Retorna: "GOD_CLASS_FORMATION" | "COGNITIVE_COMPLEXITY_EXPLOSION" | "AMBIGUOUS"
        """
        fp_god = self.compute(signal, ["CC", "DSM_d", "DI"])
        fp_cog = self.compute(signal, ["CC", "H"])

        # GOD_CLASS: CC, DSM_d e DI com onset cascateado
        if fp_god.onset_spread_commits >= 8:
            return "GOD_CLASS_FORMATION"

        # COGNITIVE: CC e H simultâneos
        if fp_cog.onset_spread_commits <= 2 and fp_cog.n_channels_activated >= 1:
            return "COGNITIVE_COMPLEXITY_EXPLOSION"

        return "AMBIGUOUS"

    def propagation_score_for_signature(
        self,
        fp: PropagationFingerprint,
        expected_pattern: str,
        expected_spread_min: int = 0,
        expected_spread_max: int = 999,
    ) -> float:
        """
        Score de compatibilidade entre fingerprint observado e padrão esperado.

        Retorna [0.0, 1.0] — usado como feature adicional no FrequencyClassifier.

        expected_pattern: "ISOLATED" | "SIMULTANEOUS" | "CASCADED_SLOW"
        """
        if fp.propagation_pattern == "NO_ONSET":
            return 0.0

        # Compatibilidade de padrão (peso maior)
        pattern_score = 1.0 if fp.propagation_pattern == expected_pattern else 0.0

        # Compatibilidade parcial (padrões adjacentes)
        if pattern_score == 0.0:
            adjacent = {
                "ISOLATED":       ["SIMULTANEOUS"],
                "SIMULTANEOUS":   ["ISOLATED", "CASCADED_FAST"],
                "CASCADED_FAST":  ["SIMULTANEOUS", "CASCADED_SLOW"],
                "CASCADED_SLOW":  ["CASCADED_FAST"],
            }
            if fp.propagation_pattern in adjacent.get(expected_pattern, []):
                pattern_score = 0.4

        # Compatibilidade de spread
        spread = fp.onset_spread_commits
        if expected_spread_min <= spread <= expected_spread_max:
            spread_score = 1.0
        else:
            # Penalidade proporcional ao desvio
            deviation = min(
                abs(spread - expected_spread_min),
                abs(spread - expected_spread_max)
            )
            spread_score = max(0.0, 1.0 - deviation / 20.0)

        return 0.70 * pattern_score + 0.30 * spread_score
