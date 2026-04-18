"""
UCO-Sensor FrequencyEngine — Analisador Espectral
===================================================
SpectralAnalyzer: computa espectro completo de cada canal do MetricSignal.

Para cada canal (9 canais individuais + 5 pares cruzados = 14 perfis):
  1. PSD via método de Welch — estimativa robusta de densidade espectral
  2. STFT — localização tempo-frequência (quando surgiu cada frequência)
  3. Wavelet db4 5 níveis — energia multi-resolução
  4. Entropia espectral — diferencia periódico de ruído
  5. Energia por banda (ULF/LF/MF/HF/UHF)
  6. Padrão temporal inferido
  7. Para pares: coerência + phase lag

Fundamentos:
  Welch (1967): estimativa PSD por média de periodogramas sobrepostos.
    Reduz variância em fator N_seg vs FFT direta. Ideal para sinais curtos.
  
  STFT: janela deslizante de FFT. Revela quando uma frequência aparece.
    Resolução tempo-frequência governa pelo princípio de Heisenberg:
    Δt × Δf ≥ 1/(4π) — não se pode ter ambos indefinidamente precisos.
  
  Cross-Spectral Density: S_xy(f) = X*(f)·Y(f)
    Coerência: γ²(f) = |S_xy(f)|² / (S_xx(f)·S_yy(f)) ∈ [0,1]
    Phase lag: φ(f) = angle(S_xy(f)) → lag em commits = φ/(2πf)
"""
from __future__ import annotations
import numpy as np
from scipy.signal import welch, stft as scipy_stft, coherence, csd
from scipy.stats import entropy as scipy_entropy, linregress
from typing import List, Dict, Optional

from core.data_structures import MetricSignal, SpectralProfile
from core.constants import (
    CHANNEL_NAMES, FREQ_BANDS, BAND_NAMES, N_CHANNELS,
    DIAGNOSTIC_PAIRS, MIN_NPERSEG, MIN_SAMPLES_FOR_WAVELET,
)
from receptor.wavelet_engine import wavelet_band_energies, wavelet_level_to_band


import warnings
warnings.filterwarnings("ignore", category=RuntimeWarning, module="scipy")

class SpectralAnalyzer:
    """
    Receptor: análise espectral completa de um MetricSignal.

    Parâmetros
    ----------
    wavelet     : wavelet para decomposição multi-resolução
    wav_levels  : número de níveis da decomposição wavelet
    welch_nperseg_ratio : tamanho do segmento Welch = N // ratio
    stft_nperseg_ratio  : tamanho do segmento STFT  = N // ratio
    """

    def __init__(
        self,
        wavelet: str = "db4",
        wav_levels: int = 5,
        welch_nperseg_ratio: int = 3,
        stft_nperseg_ratio: int = 4,
    ):
        self.wavelet = wavelet
        self.wav_levels = wav_levels
        self.welch_ratio = welch_nperseg_ratio
        self.stft_ratio  = stft_nperseg_ratio

    # ─── API pública ─────────────────────────────────────────────────────────

    def analyze_full(self, signal: MetricSignal) -> List[SpectralProfile]:
        """
        Análise espectral completa: 9 canais individuais + pares diagnósticos.
        Retorna lista de SpectralProfile (até 14 perfis).
        """
        profiles: List[SpectralProfile] = []

        # 9 canais individuais
        for i in range(N_CHANNELS):
            p = self.analyze_channel(signal, i)
            profiles.append(p)

        # 5 pares diagnósticos
        for ch_a, ch_b, _ in DIAGNOSTIC_PAIRS:
            if ch_a in CHANNEL_NAMES and ch_b in CHANNEL_NAMES:
                p = self.analyze_cross_channel(signal, ch_a, ch_b)
                profiles.append(p)

        return profiles

    def analyze_channel(
        self, signal: MetricSignal, channel_idx: int
    ) -> SpectralProfile:
        """Análise espectral completa de um único canal."""
        x = signal.data[channel_idx]
        x_raw = signal.data_raw[channel_idx]   # sem janela — para estatísticas
        name = signal.channel_names[channel_idx]
        N = len(x)

        # ── 1. PSD via Welch ──────────────────────────────────────────────
        nperseg = max(MIN_NPERSEG, N // self.welch_ratio)
        nperseg = min(nperseg, N // 2)
        freqs, psd = welch(x, fs=1.0, nperseg=nperseg, window='hann',
                           noverlap=nperseg // 2, scaling='density')

        # Frequência dominante
        dom_idx = int(np.argmax(psd))
        dominant_freq  = float(freqs[dom_idx])
        dominant_power = float(psd[dom_idx])

        # ── 2. Entropia espectral (Shannon) ──────────────────────────────
        psd_norm = psd / (psd.sum() + 1e-12)
        spec_entropy = float(scipy_entropy(psd_norm + 1e-15))
        # Normalizar para [0, 1] dividindo pelo máximo teórico log(K)
        spec_entropy_normalized = spec_entropy / (np.log(len(psd)) + 1e-12)
        spec_entropy_normalized = float(np.clip(spec_entropy_normalized, 0.0, 1.0))

        # ── 2b. f_w (Weighted Mean Frequency) — CSL Lozovsky & Churkin 2024 ─
        #  f_w = centro de massa espectral = Σ(f·PSD) / Σ(PSD)
        #  Sinal saudável: energia distribuída em frequências variadas → f_w ≈ 0.25 (Nyquist/2)
        #  Degradação: energia migra para ULF/LF → f_w cai → fw_shift > 0
        #
        #  Regra diagnóstica (transposta do CSL, ASTM D6760):
        #    fw_shift > 0.20  →  espectro perdeu componentes de alta frequência
        #    fw_shift > 0.40  →  degradação estrutural severa (equivalente a -6dB de energia)
        fw_baseline = 0.25  # ponto médio do intervalo de Nyquist [0, 0.5]
        fw_atual = float(np.sum(freqs * psd) / (np.sum(psd) + 1e-12))
        fw_shift_val = (fw_baseline - fw_atual) / (fw_baseline + 1e-12)
        fw_shift_val = float(np.clip(fw_shift_val, -2.0, 2.0))

        # A_n (Normalized Spectrum Area) — energia atual relativa ao sinal janelado
        # Proxy de baseline: std do sinal normalizado ≈ 1.0 para sinal saudável
        # A_n = energia_atual / energia_baseline
        # A baseline aqui é o sinal windowed médio (std ≈ 1 após z-score)
        psd_sum = float(np.trapezoid(psd, freqs))
        # Baseline espectral: sinal gaussiano normalizado → energia ≈ 0.5·N/fs
        psd_baseline_ref = max(0.5 * N / max(1.0, float(signal.sample_rate)), 1e-10)
        norm_area_val = float(np.clip(psd_sum / psd_baseline_ref, 0.0, 5.0))

        # ── 3. Energia por banda ──────────────────────────────────────────
        band_energies, band_energies_rel, dominant_band = \
            self._compute_band_energies(freqs, psd)

        # ── 4. STFT — localização tempo-frequência ───────────────────────
        stft_freqs, stft_times, stft_mag = self._compute_stft(x, N)

        # ── 5. Wavelet — energia multi-resolução ─────────────────────────
        if N >= MIN_SAMPLES_FOR_WAVELET:
            wav_energies = wavelet_band_energies(x, wavelet=self.wavelet,
                                                 level=self.wav_levels)
            wav_names = [wavelet_level_to_band(i, len(wav_energies)-1)
                         for i in range(len(wav_energies))]
        else:
            wav_energies = np.zeros(self.wav_levels + 1)
            wav_names    = ["ULF"] * (self.wav_levels + 1)

        # ── 6. Padrão temporal ───────────────────────────────────────────
        temporal_pattern = self._infer_temporal_pattern(
            x_raw, psd, freqs, spec_entropy_normalized, dominant_band
        )

        # ── 7. Estatísticas do sinal ─────────────────────────────────────
        slope, _, _, _, _ = linregress(np.arange(len(x_raw)), x_raw)

        return SpectralProfile(
            module_id=signal.module_id,
            channel=name,
            frequencies=freqs,
            power_spectrum=psd,
            dominant_freq=dominant_freq,
            dominant_power=dominant_power,
            spectral_entropy=spec_entropy_normalized,
            stft_freqs=stft_freqs,
            stft_times=stft_times,
            stft_magnitude=stft_mag,
            wavelet_energies=wav_energies,
            wavelet_level_names=wav_names,
            band_energies=band_energies,
            band_energies_relative=band_energies_rel,
            dominant_band=dominant_band,
            temporal_pattern=temporal_pattern,
            coherence=None,
            phase_lag_commits=None,
            signal_mean=float(x_raw.mean()),
            signal_std=float(x_raw.std()),
            signal_trend=float(slope),
            weighted_mean_freq=fw_atual,
            fw_shift=fw_shift_val,
            norm_spectrum_area=norm_area_val,
            # raw_std: std bruto antes de z-score — preservado do signal.channel_stds
            # Permite weighting de cross-coerência por signal strength no _rule_score()
            raw_std=float(signal.channel_stds[channel_idx]),
        )

    def analyze_cross_channel(
        self,
        signal: MetricSignal,
        ch_a: str,
        ch_b: str,
    ) -> SpectralProfile:
        """
        Análise cruzada entre dois canais: coerência espectral + phase lag.

        Coerência γ²(f) ≈ 1: os canais co-variam nessa frequência.
        Phase lag > 0: ch_a lidera ch_b por `lag` commits.
        Phase lag < 0: ch_b lidera ch_a.
        """
        idx_a = CHANNEL_NAMES.index(ch_a)
        idx_b = CHANNEL_NAMES.index(ch_b)
        xa = signal.data[idx_a]
        xb = signal.data[idx_b]
        N = len(xa)
        nperseg = max(MIN_NPERSEG, N // self.welch_ratio)
        nperseg = min(nperseg, N // 2)

        # Coerência espectral
        freqs, coh = coherence(xa, xb, fs=1.0, nperseg=nperseg,
                               window='hann', noverlap=nperseg // 2)
        coh = np.where(np.isfinite(coh), coh, 0.0)  # NaN → 0 (sinal constante = sem coerência)

        # Cross-spectral density → phase lag
        _, pxy = csd(xa, xb, fs=1.0, nperseg=nperseg,
                     window='hann', noverlap=nperseg // 2)

        peak_idx = int(np.argmax(coh))
        peak_freq = float(freqs[peak_idx])
        if peak_freq > 1e-9:
            phase = float(np.angle(pxy[peak_idx]))
            phase_lag = phase / (2.0 * np.pi * peak_freq)
        else:
            phase_lag = 0.0

        # Energia da coerência por banda (= coerência média na banda)
        band_energies_coh: Dict[str, float] = {}
        for band, (f_lo, f_hi) in FREQ_BANDS.items():
            mask = (freqs >= f_lo) & (freqs < f_hi)
            if mask.any():
                band_energies_coh[band] = float(coh[mask].mean())
            else:
                band_energies_coh[band] = 0.0

        total_coh = sum(band_energies_coh.values()) + 1e-12
        band_coh_rel = {b: v / total_coh for b, v in band_energies_coh.items()}
        dominant_band = max(band_energies_coh, key=band_energies_coh.get)

        # Entropia da coerência
        coh_valid = coh[np.isfinite(coh)]
        if len(coh_valid) > 0:
            coh_norm = coh_valid / (coh_valid.sum() + 1e-12)
            coh_entropy = float(scipy_entropy(coh_norm + 1e-15))
            coh_entropy /= (np.log(len(coh_valid)) + 1e-12)
        else:
            coh_entropy = 0.5
        coh_entropy = float(np.clip(coh_entropy, 0.0, 1.0))

        # PSD dummy (usar PSD do canal A para o campo obrigatório)
        _, psd_a = welch(xa, fs=1.0, nperseg=nperseg, window='hann',
                         noverlap=nperseg // 2)

        stft_f, stft_t, stft_mag = self._compute_stft(xa, N)

        # Wavelet energies da média dos dois canais
        x_mean = (xa + xb) / 2.0
        if N >= MIN_SAMPLES_FOR_WAVELET:
            wav_e = wavelet_band_energies(x_mean, wavelet=self.wavelet,
                                          level=self.wav_levels)
            wav_n = [wavelet_level_to_band(i, len(wav_e)-1) for i in range(len(wav_e))]
        else:
            wav_e = np.zeros(self.wav_levels + 1)
            wav_n = ["ULF"] * (self.wav_levels + 1)

        return SpectralProfile(
            module_id=signal.module_id,
            channel=f"cross:{ch_a}_{ch_b}",
            frequencies=freqs,
            power_spectrum=psd_a,
            dominant_freq=peak_freq,
            dominant_power=float(coh.max()),
            spectral_entropy=coh_entropy,
            stft_freqs=stft_f,
            stft_times=stft_t,
            stft_magnitude=stft_mag,
            wavelet_energies=wav_e,
            wavelet_level_names=wav_n,
            band_energies=band_energies_coh,
            band_energies_relative=band_coh_rel,
            dominant_band=dominant_band,
            temporal_pattern="cross_channel",
            coherence=coh,
            phase_lag_commits=phase_lag,
            signal_mean=float(xa.mean()),
            signal_std=float(xa.std()),
            signal_trend=0.0,
        )

    # ─── Métodos auxiliares ───────────────────────────────────────────────────

    def _compute_band_energies(
        self,
        freqs: np.ndarray,
        psd: np.ndarray,
    ) -> tuple:
        """
        Integra PSD sobre cada banda de frequência.
        Retorna (energias_absolutas, energias_relativas, banda_dominante).
        """
        band_e: Dict[str, float] = {}
        for band, (f_lo, f_hi) in FREQ_BANDS.items():
            mask = (freqs >= f_lo) & (freqs < f_hi)
            band_e[band] = float(psd[mask].sum()) if mask.any() else 0.0

        total = sum(band_e.values()) + 1e-12
        band_e_rel = {b: v / total for b, v in band_e.items()}
        dominant = max(band_e, key=band_e.get)
        return band_e, band_e_rel, dominant

    def _compute_stft(
        self, x: np.ndarray, N: int
    ) -> tuple:
        """STFT com segmento adaptado ao tamanho do sinal."""
        nperseg_stft = max(4, N // self.stft_ratio)
        nperseg_stft = min(nperseg_stft, N // 2)
        try:
            f, t, Zxx = scipy_stft(x, fs=1.0, nperseg=nperseg_stft,
                                    window='hann', noverlap=nperseg_stft // 2)
            return f, t, np.abs(Zxx)
        except Exception:
            return np.array([0.0]), np.array([0.0]), np.zeros((1, 1))

    def _infer_temporal_pattern(
        self,
        x_raw: np.ndarray,
        psd: np.ndarray,
        freqs: np.ndarray,
        entropy: float,
        dominant_band: str,
    ) -> str:
        """
        Infere o padrão temporal do sinal a partir de características espectrais.

        Regras (em ordem de prioridade):

        stable:      entropy > 0.85 AND dominant_band não HF/UHF
                     → sinal essencialmente ruído, sem padrão estruturado

        spike:       entropy < 0.35 AND dominant_band in HF/UHF
                     → energia concentrada em alta frequência = evento súbito

        monotone:    entropy < 0.30 AND slope significativamente positivo/negativo
                     AND dominant_band in ULF/LF
                     → tendência secular sem reversão

        step:        ponto de mudança detectável via variância de segmentos
                     AND dominant_band in MF/HF
                     → degrau abrupto mas mantido (não spike transitório)

        oscillating: múltiplos picos de similar amplitude na PSD
                     AND entropy em 0.4–0.7
                     → variação rítmica (refatoração em progresso)

        correlated_rise: entropy moderada + trend positivo + dominant_band LF/MF
                         → crescimento gradual multi-canal
        """
        slope, _, _, _, _ = linregress(np.arange(len(x_raw)), x_raw)
        trend_strong = abs(slope) > 0.07  # calibrado para degradação gradual em OSS

        # Estabilidade do sinal: std da segunda metade vs primeira metade
        mid = len(x_raw) // 2
        half_ratio = (np.std(x_raw[mid:]) + 1e-9) / (np.std(x_raw[:mid]) + 1e-9)

        # Número de picos na PSD
        sorted_psd = np.sort(psd)[::-1]
        if len(sorted_psd) > 2 and sorted_psd[0] > 1e-10:
            peak_ratio = sorted_psd[1] / sorted_psd[0]  # 2º pico relativo ao 1º
        else:
            peak_ratio = 0.0

        # Regras
        if entropy > 0.85:
            return "stable"

        if entropy < 0.35 and dominant_band in ("HF", "UHF"):
            if half_ratio > 1.5:   # variância aumentou na segunda metade
                return "spike"
            return "step"

        if entropy < 0.30 and trend_strong and dominant_band in ("ULF", "LF"):
            return "monotone"

        if 0.35 < entropy < 0.70 and peak_ratio > 0.6:
            return "oscillating"

        if trend_strong and dominant_band in ("ULF", "LF", "MF"):
            return "correlated_rise"

        if dominant_band in ("HF", "UHF") and half_ratio > 1.2:
            return "step"

        # ── Override: trend + fw_shift → correlated_rise ───────────────
        # Sinal com trend forte E fw_shift alto é degradação estrutural gradual,
        # não "stable". A entropia alta vem do step LF que ocupa toda a janela.
        # Sem esse override, GOD_CLASS e TECH_DEBT ficam "stable" em séries curtas.
        if trend_strong:
            return "correlated_rise"
        return "stable"
