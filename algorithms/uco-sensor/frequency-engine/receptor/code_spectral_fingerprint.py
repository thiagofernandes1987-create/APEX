"""
Code Spectral Fingerprint — versão mínima (MVP)
=================================================
Resposta ao pedido do usuário ("consegue esboçar como adaptar o
spectral_analyzer.py/wavelet_engine.py... para criar espectros gerados
por código... com poder de análise semelhante a um SCA?" → "sim, versão
mínima, iniciar antes de aprimorar").

Diferença em relação a `spectral_analyzer.py`/`SpectralAnalyzer`: aquele
módulo opera sobre um `MetricSignal` — uma série temporal de métricas de
software *através de commits* (uma métrica, N pontos = N commits). Este
módulo opera sobre o *conteúdo de um único arquivo de código-fonte*,
convertendo-o em um sinal 1D (não há eixo de commits) e reaproveitando
diretamente `welch()` do scipy e `wavelet_band_energies()` de
`wavelet_engine.py` — sem instanciar `SpectralAnalyzer`/`MetricSignal`,
que pressupõem o eixo de commits.

Objetivo do MVP: um "fingerprint" numérico de um arquivo que seja
estável sob mudanças cosméticas pequenas (mesma versão, diff trivial) e
sensível a mudanças estruturais reais (versão diferente da
dependência) — o mesmo objetivo que hash-matching de SCA, mas via
similaridade vetorial em vez de igualdade exata de hash. NÃO é uma
substituição de SCA por hash; é uma segunda dimensão (similaridade
aproximada) que um hash exato não oferece. Validação real (não apenas
afirmada) fica em `tests/test_code_spectral_fingerprint.py`, usando os
pares vulnerável/corrigido já buscados nesta sessão (scrapy, flask).

Pipeline (deliberadamente simples — refinamento fica para depois):
  1. `source_to_signal(source)`: 1 amostra por linha não-vazia =
     comprimento da linha (rstrip). Sinal "esqueleto" puramente
     estrutural — não depende de tokenização/parsing por linguagem,
     funciona para qualquer texto.
  2. PSD via `scipy.signal.welch` (mesmos parâmetros-base de
     `SpectralAnalyzer`) + energia de banda (ULF/LF/MF/HF/UHF).
  3. Energia wavelet via `wavelet_band_energies()` (reuso direto, sem
     modificação).
  4. Fingerprint = concatenação [bandas PSD relativas, bandas wavelet],
     normalizado por L2 → vetor unitário comparável por similaridade
     de cosseno.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import welch

from core.constants import FREQ_BANDS, MIN_NPERSEG
from receptor.wavelet_engine import wavelet_band_energies

_MIN_LINES_FOR_WAVELET = 8


def source_to_signal(source: str) -> np.ndarray:
    """Converte código-fonte em sinal 1D: comprimento de cada linha não-vazia."""
    lines = [ln.rstrip() for ln in source.splitlines()]
    lengths = np.array([float(len(ln)) for ln in lines if ln.strip()], dtype=float)
    if lengths.size == 0:
        return np.zeros(1, dtype=float)
    mean = lengths.mean()
    std = lengths.std()
    if std < 1e-9:
        return lengths - mean
    return (lengths - mean) / std


def _band_energies_from_psd(freqs: np.ndarray, psd: np.ndarray) -> np.ndarray:
    total = float(psd.sum()) + 1e-12
    energies = []
    for low, high in FREQ_BANDS.values():
        mask = (freqs >= low) & (freqs < high)
        energies.append(float(psd[mask].sum()) / total)
    return np.array(energies, dtype=float)


def fingerprint(source: str, welch_ratio: int = 3, wav_levels: int = 5) -> np.ndarray:
    """
    Vetor de fingerprint espectral de um arquivo de código-fonte.

    Retorna um vetor unitário (norma L2 = 1) combinando energia de
    banda via Welch e energia de banda via wavelet. Arquivos
    estruturalmente parecidos (mesma versão, diff cosmético pequeno)
    devem ter cosine similarity alta; arquivos estruturalmente
    diferentes (versões/funções diferentes), baixa — isso é o que os
    testes validam empiricamente, não uma garantia teórica.
    """
    x = source_to_signal(source)
    N = len(x)

    if N >= 2 * MIN_NPERSEG:
        nperseg = max(MIN_NPERSEG, N // welch_ratio)
        nperseg = min(nperseg, N // 2)
        freqs, psd = welch(x, fs=1.0, nperseg=nperseg, window="hann",
                           noverlap=nperseg // 2, scaling="density")
        psd_bands = _band_energies_from_psd(freqs, psd)
    else:
        psd_bands = np.zeros(len(FREQ_BANDS), dtype=float)

    if N >= _MIN_LINES_FOR_WAVELET:
        wav_bands = wavelet_band_energies(x, wavelet="db4", level=wav_levels)
    else:
        wav_bands = np.zeros(wav_levels + 1, dtype=float)

    vec = np.concatenate([psd_bands, wav_bands])
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        return vec
    return vec / norm


def cosine_similarity(fp_a: np.ndarray, fp_b: np.ndarray) -> float:
    """Similaridade de cosseno entre dois fingerprints (já normalizados ou não)."""
    a, b = np.asarray(fp_a, dtype=float), np.asarray(fp_b, dtype=float)
    if a.shape != b.shape:
        n = min(len(a), len(b))
        a, b = a[:n], b[:n]
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))
