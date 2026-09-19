"""
UCO-Sensor FrequencyEngine — Detecção de Change Points
=======================================================
Detecção exata de change-points por programação dinâmica penalizada.

A versão anterior se chamava PELT, mas a regra de poda eliminava candidatos
válidos e podia retornar segmentações subótimas. A API privada _pelt é
mantida por compatibilidade, porém agora executa DP exata O(N²), adequada às
janelas curtas do UCO e verificável contra busca exaustiva.

O detector encontra o conjunto ótimo de breakpoints que minimiza o custo total
de segmentação de uma série temporal. É a resposta para: "quando exatamente
o padrão de erro começou?"

Fundamento matemático:
  Dado um sinal y = (y_1, ..., y_N), encontrar τ* = {τ_1, ..., τ_k} que
  minimize:

    V(τ) = Σ_{i=1}^{k+1} C(y_{τ_{i-1}+1 : τ_i}) + β·k

  Onde:
    C(·) = custo de ajuste de um modelo ao segmento
    β    = penalidade por breakpoint adicional (controla sensibilidade)

  Modelos de custo implementados:
    "rbf"  — alias legado para custo Gaussiano de variância:
             C = N·log(σ²). NÃO é um kernel RBF.
             Mantido para compatibilidade de configuração.
    "gaussian" — nome preferido para o mesmo custo.

    "l2"   — Least Squares: C = Σ(y_i - ȳ)² = N·σ²
             Detecta mudanças de média apenas.
             Mais rápido, menos sensível a outliers.

  O PELT usa "prunagem": se um ponto de divisão t nunca minimiza o custo
  para qualquer extensão futura, ele é eliminado da busca (O(N log N) no
  caso médio vs O(N²) da busca exaustiva).

Referências:
  Killick, R., Fearnhead, P., Eckley, I.A. (2012). Optimal Detection of
  Changepoints with a Linear Computational Cost. JASA, 107(500), 1590-1598.

  Adams, R.P., MacKay, D.J.C. (2007). Bayesian Online Changepoint Detection.
  Technical Report, University of Cambridge.
"""
from __future__ import annotations
import numpy as np
from typing import List, Optional, Dict, Tuple

from core.data_structures import MetricSignal, ChangePoint
from core.constants import CHANNEL_NAMES, MIN_SAMPLES_FOR_PELT


class ChangePointDetector:
    """
    Detecta pontos de mudança em séries temporais de métricas UCO.

    Identifica o commit onde uma anomalia começou — o dado mais acionável
    do sistema: não "há um problema", mas "o problema começou aqui".

    Parâmetros
    ----------
    model  : "rbf" (detecta mudanças de média e variância) |
             "l2"  (detecta mudanças de média apenas, mais rápido)
    penalty : β — penalidade por breakpoint.
              Maior β → menos breakpoints (apenas mudanças grandes).
              Menor β → mais breakpoints (mais sensível).
              default=1.0 é calibrado para métricas UCO normalizadas.
    min_size : tamanho mínimo de segmento em commits (evita over-segmentação)
    """

    def __init__(
        self,
        model: str = "rbf",
        penalty: float = 1.0,
        min_size: int = 3,
    ):
        self.model    = model
        self.penalty  = penalty
        self.min_size = min_size

    # ─── API pública ─────────────────────────────────────────────────────────

    def detect(
        self,
        signal: MetricSignal,
        primary_channels: List[str],
    ) -> Optional[ChangePoint]:
        """
        Detecta o breakpoint mais significativo nos canais primários da assinatura.

        Opera sobre a média dos canais primários — reduz ruído enquanto
        preserva o padrão conjunto.

        Retorna None se N < MIN_SAMPLES_FOR_PELT ou sem breakpoint detectado.
        """
        if signal.n_samples < MIN_SAMPLES_FOR_PELT:
            return None

        # Média dos canais primários (sinal composto)
        indices = [CHANNEL_NAMES.index(ch) for ch in primary_channels
                   if ch in CHANNEL_NAMES]
        if not indices:
            return None

        x = signal.data_raw[indices].mean(axis=0)  # (N,)

        # Detectar breakpoints (DP exata penalizada; nome _pelt preservado)
        breakpoints = self._pelt(x)

        if not breakpoints:
            return None

        # Breakpoint mais significativo = o com maior magnitude de mudança
        best_bp, magnitude = self._select_best_breakpoint(x, breakpoints)

        # Bounded effect-strength score, NOT a calibrated probability.
        # Previous magnitude/(2*std) clipping saturated at 1.0 for many normal
        # histories, destroying ranking information.  r/(1+r) is monotonic,
        # bounded and preserves separation without claiming probabilistic meaning.
        signal_std = float(np.std(x)) + 1e-9
        effect_ratio = max(0.0, float(magnitude) / signal_std)
        confidence = float(effect_ratio / (1.0 + effect_ratio))

        # best_bp está na grade interpolada. Projetar para o commit ORIGINAL.
        n_grid = max(1, int(signal.n_samples))
        n_src = max(1, int(signal.n_original or len(signal.commit_hashes)))
        if n_grid <= 1 or n_src <= 1:
            source_idx = 0
        else:
            source_idx = int(round(best_bp * (n_src - 1) / (n_grid - 1)))
        source_idx = max(0, min(source_idx, n_src - 1))

        commit_hash = None
        if source_idx < len(signal.commit_hashes):
            commit_hash = signal.commit_hashes[source_idx]

        return ChangePoint(
            commit_idx=source_idx,
            commit_hash=commit_hash,
            confidence=confidence,
            magnitude=magnitude,
            affected_channels=primary_channels,
            signal_idx=best_bp,
        )

    def detect_all_channels(
        self,
        signal: MetricSignal,
    ) -> Dict[str, Optional[ChangePoint]]:
        """Detecta change points em todos os canais individualmente."""
        results = {}
        for ch in CHANNEL_NAMES:
            cp = self.detect(signal, [ch])
            results[ch] = cp
        return results

    # ─── Implementação PELT ──────────────────────────────────────────────────

    def _pelt(self, x: np.ndarray) -> List[int]:
        """
        Exact penalized segmentation (compatibility name _pelt).

        We intentionally use O(N²) dynamic programming. UCO governance windows
        are bounded (typically <=200), so correctness is more valuable than an
        unverified pruning optimization. Every predecessor s with finite F[s]
        and segment length >= min_size is considered.

        Objective:
            F[t] = min_s F[s] + C(x[s:t]) + beta
        with F[0] = -beta so a signal with zero breakpoints pays no penalty.

        This routine is exact for the implemented additive segment costs.
        """
        N = len(x)
        if N < 2 * self.min_size:
            return []

        cumsum = np.cumsum(x, dtype=float)
        cumsum2 = np.cumsum(np.asarray(x, dtype=float) ** 2)

        def sum_range(lo: int, hi: int) -> float:
            return float(cumsum[hi - 1] - (cumsum[lo - 1] if lo > 0 else 0.0))

        def sum2_range(lo: int, hi: int) -> float:
            return float(cumsum2[hi - 1] - (cumsum2[lo - 1] if lo > 0 else 0.0))

        def cost(lo: int, hi: int) -> float:
            n = hi - lo
            if n <= 0:
                return 0.0
            s1 = sum_range(lo, hi)
            s2 = sum2_range(lo, hi)
            var = max(0.0, s2 / n - (s1 / n) ** 2)
            if self.model in ("rbf", "gaussian"):
                # Legacy "rbf" is a Gaussian variance/log-likelihood cost,
                # not a radial-basis-function kernel.
                return float(n * np.log(max(var, 1e-10)))
            return float(n * var)

        F = np.full(N + 1, np.inf, dtype=float)
        last = np.full(N + 1, -1, dtype=int)
        F[0] = -float(self.penalty)

        for t in range(self.min_size, N + 1):
            latest_s = t - self.min_size
            for s_idx in range(0, latest_s + 1):
                if not np.isfinite(F[s_idx]):
                    continue
                candidate = F[s_idx] + cost(s_idx, t) + self.penalty
                if candidate < F[t]:
                    F[t] = candidate
                    last[t] = s_idx

        if not np.isfinite(F[N]) or last[N] < 0:
            return []

        breakpoints: List[int] = []
        t = N
        while last[t] > 0:
            bp = int(last[t])
            breakpoints.append(bp)
            t = bp
        breakpoints.reverse()
        return breakpoints

    def _select_best_breakpoint(
        self,
        x: np.ndarray,
        breakpoints: List[int],
    ) -> Tuple[int, float]:
        """
        Dentre todos os breakpoints detectados, seleciona o de maior magnitude.
        Magnitude = |média_depois - média_antes|.
        """
        best_bp  = breakpoints[0]
        best_mag = 0.0

        for bp in breakpoints:
            if bp <= 0 or bp >= len(x):
                continue
            mean_before = float(np.mean(x[:bp]))
            mean_after  = float(np.mean(x[bp:]))
            mag = abs(mean_after - mean_before)
            if mag > best_mag:
                best_mag = mag
                best_bp  = bp

        return best_bp, best_mag
