"""
UCO-Sensor FrequencyEngine — Detecção de Change Points
=======================================================
Implementação do algoritmo PELT (Pruned Exact Linear Time) em numpy puro.

O PELT encontra o conjunto ótimo de breakpoints que minimiza o custo total
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
    "rbf"  — Radial Basis Function: C = N·log(σ²), onde σ² = variância do segmento
             Equivalente a log-likelihood negativo de uma Gaussiana.
             Detecta mudanças de média E variância.

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

        # Detectar breakpoints
        breakpoints = self._pelt(x)

        if not breakpoints:
            return None

        # Breakpoint mais significativo = o com maior magnitude de mudança
        best_bp, magnitude = self._select_best_breakpoint(x, breakpoints)

        # Confiança baseada na magnitude normalizada pelo std do sinal
        signal_std = float(np.std(x)) + 1e-9
        confidence = float(np.clip(magnitude / (2.0 * signal_std), 0.0, 1.0))

        commit_hash = None
        if best_bp < len(signal.commit_hashes):
            commit_hash = signal.commit_hashes[best_bp]

        return ChangePoint(
            commit_idx=best_bp,
            commit_hash=commit_hash,
            confidence=confidence,
            magnitude=magnitude,
            affected_channels=primary_channels,
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
        PELT: Pruned Exact Linear Time changepoint detection.

        Algoritmo dinâmico que encontra o particionamento ótimo de x.

        Estado:
          F[t] = custo mínimo de segmentar x[0:t]
          last[t] = último breakpoint que deu F[t]
          cands = set de candidatos a último breakpoint para posição atual

        Prunagem: candidato s é eliminado se
          F[s] + C(x[s:t]) + β ≥ F[t]  para todo t ≥ t_atual
        Isso garante que s nunca será ótimo para nenhuma extensão futura.
        """
        N = len(x)
        if N < 2 * self.min_size:
            return []

        # Pré-computar somas e somas de quadrados para cálculo O(1) de custo
        cumsum   = np.cumsum(x)
        cumsum2  = np.cumsum(x ** 2)

        def sum_range(lo: int, hi: int) -> float:
            """Soma de x[lo:hi]"""
            return float(cumsum[hi-1] - (cumsum[lo-1] if lo > 0 else 0.0))

        def sum2_range(lo: int, hi: int) -> float:
            """Soma de x[lo:hi]²"""
            return float(cumsum2[hi-1] - (cumsum2[lo-1] if lo > 0 else 0.0))

        def cost(lo: int, hi: int) -> float:
            """
            Custo de segmentar x[lo:hi] como um único segmento.

            modelo "rbf" (RBF/Gaussiano):
              C = n · log(σ²) onde σ² = variância do segmento
              Equivalente a -2·log-likelihood de N(μ, σ²) com μ,σ estimados.
              C → -∞ quando σ² → 0, então usamos max(σ², ε).

            modelo "l2" (Least Squares):
              C = n·σ² = Σ(x_i - x̄)² = soma quadrática dos resíduos
            """
            n = hi - lo
            if n <= 0:
                return 0.0
            s1 = sum_range(lo, hi)
            s2 = sum2_range(lo, hi)
            var = s2 / n - (s1 / n) ** 2
            if self.model == "rbf":
                return n * np.log(max(var, 1e-10))
            else:  # l2
                return max(0.0, n * var)

        # DP principal
        F    = np.full(N + 1, np.inf)
        last = np.full(N + 1, -1, dtype=int)
        F[0] = -self.penalty   # caso base: custo de sinal vazio

        cands = [0]   # candidatos a último breakpoint

        for t in range(self.min_size, N + 1):
            # Melhor segmentação até t
            best_cost = np.inf
            best_last = -1

            for s in cands:
                if t - s < self.min_size:
                    continue
                c = F[s] + cost(s, t) + self.penalty
                if c < best_cost:
                    best_cost = c
                    best_last = s

            F[t]    = best_cost
            last[t] = best_last

            # Prunagem: remover candidatos que nunca serão ótimos
            new_cands = []
            for s in cands:
                if t - s < self.min_size:
                    new_cands.append(s)
                    continue
                # Manter s se existe t' > t onde s pode ser ótimo
                # Condição de prunagem: F[s] + C(s,t) + β ≥ F[t]
                # Se isso vale, s é subótimo para t e todo t' > t
                if F[s] + cost(s, t) + self.penalty < F[t] + 1e-10:
                    new_cands.append(s)

            # Adicionar t como novo candidato
            if t + self.min_size <= N:
                new_cands.append(t)
            cands = new_cands

        # Reconstruir breakpoints percorrendo ponteiros `last`
        breakpoints = []
        t = N
        while last[t] > 0:
            breakpoints.append(last[t])
            t = last[t]
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
