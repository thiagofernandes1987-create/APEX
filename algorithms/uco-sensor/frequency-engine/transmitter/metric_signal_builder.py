"""
UCO-Sensor FrequencyEngine — Transmissor
=========================================
MetricSignalBuilder: converte List[MetricVector] em MetricSignal [9×N].

Pipeline do transmissor:
  1. Extrai 9 dimensões de cada MetricVector
  2. Interpola para espaçamento uniforme (commits irregulares → grade regular)
  3. Normaliza cada canal por z-score local
  4. Aplica janelamento (Hann/Hamming/Blackman) para reduzir spectral leakage
  5. Retorna MetricSignal pronto para análise espectral

Fundamento matemático:
  A FFT assume que o sinal é periódico e espaçado uniformemente.
  Commits reais violam as duas condições: são irregulares no tempo e
  têm bordas onde o sinal raramente é zero. O pré-processamento corrige ambas.

Referência:
  Harris, F.J. (1978). On the use of windows for harmonic analysis
  with the discrete Fourier transform. Proc. IEEE, 66(1), 51-83.
"""
from __future__ import annotations
import numpy as np
from scipy.interpolate import interp1d
from scipy.signal import windows as sp_windows
from typing import List, Optional, Tuple

from core.data_structures import MetricVector, MetricSignal
from core.constants import CHANNEL_NAMES, N_CHANNELS, MIN_SAMPLES_FOR_SPECTRAL


import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

class MetricSignalBuilder:
    """
    Transmissor do FrequencyEngine.

    Transforma histórico temporal de métricas UCO em tensor de sinal
    normalizado e janelado, pronto para análise espectral.

    Parâmetros
    ----------
    window_fn : str
        Função de janelamento para reduzir spectral leakage.
        "hann"    — boa supressão de lobe lateral, leve alargamento do lobe principal.
                    Ideal para detectar frequências próximas. [DEFAULT]
        "hamming" — menor alargamento, pior supressão lateral. Melhor precisão espectral.
        "blackman"— melhor supressão lateral, lobe principal mais largo. Máxima pureza.
        "none"    — sem janelamento. Apenas se o sinal for naturalmente periódico.

    interp_method : str
        Método de interpolação para regularizar espaçamento temporal.
        "linear" — robusto, sem artefatos de ringing. [DEFAULT]
        "cubic"  — mais suave, pode criar oscilações artificiais em séries curtas.

    n_interp : int or None
        Número de pontos no sinal interpolado. None → max(N_original, 32).
        32 garante pelo menos 16 bins de frequência (Nyquist).
    """

    def __init__(
        self,
        window_fn: str = "hann",
        interp_method: str = "linear",
        n_interp: Optional[int] = None,
    ):
        self.window_fn = window_fn
        self.interp_method = interp_method
        self.n_interp = n_interp

    # ─── API pública ─────────────────────────────────────────────────────────

    def build(
        self,
        history: List[MetricVector],
        verbose: bool = False,
    ) -> Optional[MetricSignal]:
        """
        Constrói MetricSignal a partir de histórico de MetricVectors.

        Retorna None se len(history) < MIN_SAMPLES_FOR_SPECTRAL (5).

        Parâmetros
        ----------
        history : List[MetricVector]
            Lista de MetricVectors ordenada por timestamp (crescente).
        verbose : bool
            Se True, imprime estatísticas do sinal construído.
        """
        if len(history) < MIN_SAMPLES_FOR_SPECTRAL:
            if verbose:
                print(f"[Transmissor] N={len(history)} < {MIN_SAMPLES_FOR_SPECTRAL} "
                      f"— insuficiente para análise espectral")
            return None

        # 1. Extrair arrays brutos [9 × N_original]
        raw, timestamps_raw = self._extract_raw(history)

        # 2. Interpolar para grade uniforme
        N = self.n_interp or max(len(history), 32)
        timestamps_uniform = np.linspace(0.0, 1.0, N)
        data_interp = self._interpolate(raw, timestamps_raw, timestamps_uniform)

        # 3. Normalização z-score por canal
        data_norm, means, stds = self._normalize(data_interp)

        # 4. Janelamento
        data_windowed = self._apply_window(data_norm.copy())

        # 5. GAP-S03/S04: computar stable_channels em valores RAW (pré-normalização)
        # Usamos os valores brutos antes da normalização z-score para medir
        # estabilidade real (não variância artefato da normalização).
        import statistics as _stats
        def _is_stable(raw_vals, cv_thresh=0.03, win=5):
            if len(raw_vals) < win * 2: return False
            mean_v = _stats.mean(raw_vals)
            if abs(mean_v) > 1e-10:
                if (max(raw_vals) - min(raw_vals)) / abs(mean_v) > 0.05: return False
            elif max(raw_vals) - min(raw_vals) > 1e-6: return False
            step = max(1, win // 2)
            for i in range(0, len(raw_vals) - win, step):
                seg = raw_vals[i:i+win]
                seg_m = _stats.mean(seg)
                if abs(seg_m) < 1e-10: continue
                try:
                    if _stats.stdev(seg) / abs(seg_m) > cv_thresh: return False
                except _stats.StatisticsError:
                    pass
            return True

        ch_names_for_stab = list(CHANNEL_NAMES)
        # BUG-C05 FIX: use raw (pre-interpolation) tensor for stability check
        # data_interp may smooth variance artificially via linear interpolation
        # raw contains original values with true variance
        stable_chs = [
            ch_names_for_stab[i]
            for i in range(raw.shape[0])
            if _is_stable(raw[i].tolist())
        ]

        # 6. Construir MetricSignal
        # BUG-C01 FIX: data_raw now stores truly raw values (pre-interpolation)
        # data_normalized stores the z-scored interpolated data
        # Consumers needing units-correct values should use data_raw

        # ── GAP-D1/D2/D3/D4: derived temporal features from raw metric series ──
        _n_total  = len(history)
        _n3       = max(3, _n_total // 3)
        _cc_vals  = np.array([v.cyclomatic_complexity  for v in history], dtype=float)
        _di_vals  = np.array([v.dependency_instability for v in history], dtype=float)
        _mm_vals  = np.array([getattr(v, 'max_methods_per_class', 0) for v in history], dtype=float)
        _nf_vals  = np.array([getattr(v, 'n_functions', 0)           for v in history], dtype=float)
        _nc_vals  = np.array([getattr(v, 'n_classes', 1)             for v in history], dtype=float)
        # Phase analysis — raw metric values (pre-z-score) for interpretable deltas
        _cc_phase_delta = float(np.median(_cc_vals[-_n3:]) - np.median(_cc_vals[:_n3]))
        _di_phase_delta = float(np.median(_di_vals[-_n3:]) - np.median(_di_vals[:_n3]))
        _cc_early_med   = float(np.median(_cc_vals[:_n3]))
        _cc_late_med    = float(np.median(_cc_vals[-_n3:]))
        # Series growth rates
        _mm_mean   = float(_mm_vals.mean()) if _n_total > 0 else 0.0
        _mm_growth = float(_mm_vals[-1] - _mm_vals[0]) / max(1, _n_total)
        _nf_mean   = float(_nf_vals.mean()) if _n_total > 0 else 0.0
        _nf_growth = float(_nf_vals[-1] - _nf_vals[0]) / max(1, _n_total)
        _nc_growth = float(_nc_vals[-1] - _nc_vals[0]) / max(1, _n_total)
        # CC diff coefficient of variation (volatility of changes)
        _cc_diffs   = np.abs(np.diff(_cc_vals))
        _cc_diff_cv = float(_cc_diffs.std() / (_cc_diffs.mean() + 1e-10)) if len(_cc_diffs) > 1 else 0.0

        signal = MetricSignal(
            data=data_windowed,
            data_raw=data_norm,          # z-scored (used by spectral pipeline)
            timestamps=timestamps_uniform,
            commit_hashes=[mv.commit_hash for mv in history],
            module_id=history[0].module_id,
            sample_rate=float(N),
            n_original=len(history),
            channel_names=list(CHANNEL_NAMES),
            channel_means=means,
            channel_stds=stds,
            window_fn=self.window_fn,
            stable_channels=stable_chs,
            # GAP-D1/D2/D3/D4 derived fields
            cc_phase_delta=_cc_phase_delta,
            di_phase_delta=_di_phase_delta,
            cc_early=_cc_early_med,
            cc_late=_cc_late_med,
            max_methods_mean=_mm_mean,
            max_methods_growth=_mm_growth,
            n_functions_mean=_nf_mean,
            n_functions_growth=_nf_growth,
            n_classes_growth=_nc_growth,
            cc_diff_cv=_cc_diff_cv,
        )

        if verbose:
            self._print_summary(signal, raw, means, stds)

        return signal

    # ─── Implementação interna ────────────────────────────────────────────────

    def _extract_raw(
        self,
        history: List[MetricVector],
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Extrai tensor [9 × N] de métricas e vetor de timestamps normalizados.

        Usa commit-index normalizado como eixo de tempo (mais estável que
        timestamps reais que podem ter gaps grandes nos fins de semana).
        """
        raw = np.stack([mv.to_array() for mv in history], axis=1)  # (9, N)
        N = raw.shape[1]

        # Timestamps: usar índice de commit normalizado [0, 1]
        # Alternativa: usar timestamps reais se disponíveis e uniformes
        real_ts = np.array([mv.timestamp for mv in history], dtype=np.float64)
        if real_ts[-1] > real_ts[0]:
            # Normalizar para [0, 1]
            ts_normalized = (real_ts - real_ts[0]) / (real_ts[-1] - real_ts[0])
        else:
            # Fallback: espaçamento uniforme por índice
            ts_normalized = np.linspace(0.0, 1.0, N)

        return raw, ts_normalized

    def _interpolate(
        self,
        raw: np.ndarray,           # (9, N_original)
        ts_raw: np.ndarray,        # (N_original,)
        ts_uniform: np.ndarray,    # (N_interp,)
    ) -> np.ndarray:
        """
        Interpola cada canal para grade de tempo uniforme.

        Canais constantes (std < ε) são preenchidos com zeros (não carregam
        informação espectral útil).
        """
        N_out = len(ts_uniform)
        data_out = np.zeros((N_CHANNELS, N_out), dtype=np.float64)

        for i in range(N_CHANNELS):
            channel = raw[i]
            if np.std(channel) < 1e-12:
                # Canal constante — zeros após normalização
                continue
            try:
                f = interp1d(
                    ts_raw, channel,
                    kind=self.interp_method,
                    fill_value="extrapolate",
                    bounds_error=False,
                )
                data_out[i] = f(ts_uniform)
            except Exception:
                # Fallback para linear se cubic falhar em N pequeno
                f = interp1d(ts_raw, channel, kind="linear",
                             fill_value="extrapolate", bounds_error=False)
                data_out[i] = f(ts_uniform)

        return data_out

    def _normalize(
        self,
        data: np.ndarray,   # (9, N)
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Normalização z-score por canal: z = (x - μ) / σ

        Retorna (data_normalizado, means, stds).
        Canais com std < ε recebem std=1 (evita divisão por zero).

        Motivação: as 9 métricas têm escalas heterogêneas:
          H ∈ [2, 5000+], ILR ∈ [0, 1], dead_code ∈ [0, ∞]
        Sem normalização, H domina completamente o espectro.
        """
        means = data.mean(axis=1, keepdims=True)
        stds  = data.std(axis=1, keepdims=True)
        stds  = np.where(stds < 1e-9, 1.0, stds)

        data_norm = (data - means) / stds
        return data_norm, means.flatten(), stds.flatten()

    def _apply_window(self, data: np.ndarray) -> np.ndarray:
        """
        Multiplica cada canal pela função de janela escolhida.

        A janela vai suavemente a zero nas bordas, eliminando a descontinuidade
        que a FFT "vê" quando o sinal é truncado — fenômeno de spectral leakage.

        Janelas disponíveis e suas propriedades:
          Hann:    -31.5 dB side lobe,  1.5-bin main lobe width  [melhor geral]
          Hamming: -42.5 dB side lobe,  1.3-bin main lobe width  [menor main lobe]
          Blackman:-58.1 dB side lobe,  1.7-bin main lobe width  [máxima supressão]
        """
        N = data.shape[1]

        if self.window_fn == "none":
            return data

        fn_map = {
            "hann":     sp_windows.hann,
            "hamming":  sp_windows.hamming,
            "blackman": sp_windows.blackman,
        }
        win_fn = fn_map.get(self.window_fn, sp_windows.hann)
        w = win_fn(N)                          # shape: (N,)
        return data * w[np.newaxis, :]         # broadcast: (9, N) * (1, N)

    def _print_summary(
        self,
        signal: MetricSignal,
        raw: np.ndarray,
        means: np.ndarray,
        stds: np.ndarray,
    ) -> None:
        print(f"\n[Transmissor] Módulo: {signal.module_id}")
        print(f"  N_original={signal.n_original}  N_interpolado={signal.n_samples}")
        print(f"  Janelamento: {signal.window_fn}")
        print(f"  {'Canal':<8} {'Média':>10} {'Std':>10} {'Min':>10} {'Max':>10}")
        print(f"  {'-'*52}")
        for i, name in enumerate(CHANNEL_NAMES):
            vals = raw[i]
            print(f"  {name:<8} {means[i]:>10.3f} {stds[i]:>10.3f} "
                  f"{vals.min():>10.3f} {vals.max():>10.3f}")
