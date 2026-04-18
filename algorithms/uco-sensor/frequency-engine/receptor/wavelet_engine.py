"""
UCO-Sensor FrequencyEngine — Motor Wavelet (numpy puro)
========================================================
Implementação da Discrete Wavelet Transform (DWT) sem dependências externas.

Algoritmo de Mallat (1989) — Fast Wavelet Transform:
  1. Convolui o sinal com filtro passa-baixa (h0) → coeficientes de aproximação
  2. Convolui o sinal com filtro passa-alta  (h1) → coeficientes de detalhe
  3. Faz downsampling por 2 (decimação) de ambos
  4. Repete recursivamente sobre os coeficientes de aproximação

Resultado: árvore de coeficientes onde cada nível captura uma oitava de frequência.

Para N=64 amostras com 5 níveis:
  Nível 0 (approx): frequências < 0.5/2^5 = 0.016 (ULF)
  Nível 1 (d5):     frequências 0.016–0.031
  Nível 2 (d4):     frequências 0.031–0.063 (LF)
  Nível 3 (d3):     frequências 0.063–0.125 (MF)
  Nível 4 (d2):     frequências 0.125–0.250 (HF)
  Nível 5 (d1):     frequências 0.250–0.500 (UHF)

Referência:
  Mallat, S.G. (1989). A theory for multiresolution signal decomposition:
  the wavelet representation. IEEE TPAMI, 11(7), 674-693.
  
  Daubechies, I. (1992). Ten Lectures on Wavelets. SIAM.
"""
from __future__ import annotations
import numpy as np
from typing import List, Tuple

from core.constants import DB4_H0, DB4_H1, HAAR_H0, HAAR_H1


# ─── Implementação DWT 1D ────────────────────────────────────────────────────

def _dwt_single_level(
    signal: np.ndarray,
    h0: np.ndarray,   # filtro low-pass (scaling/approximation)
    h1: np.ndarray,   # filtro high-pass (wavelet/detail)
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Um nível de DWT via convolução + decimação (downsampling por 2).

    A periodicização (periodic extension) evita artefatos de borda e garante
    reconstrução perfeita. Para análise (não reconstrução), mode='wrap' é
    equivalente a extensão periódica.

    Parâmetros
    ----------
    signal : ndarray (N,)
    h0 : ndarray — filtro low-pass
    h1 : ndarray — filtro high-pass

    Retorna
    -------
    approx : ndarray (N//2,)  — coeficientes de aproximação (baixas freqs)
    detail : ndarray (N//2,)  — coeficientes de detalhe    (altas freqs)
    """
    # Extensão periódica para lidar com bordas
    n_filter = len(h0)
    pad = n_filter - 1
    x_padded = np.concatenate([signal[-pad:], signal, signal[:pad]])

    # Convolução full + decimação (pegar cada 2 amostras)
    approx = np.convolve(x_padded, h0, mode='full')
    detail = np.convolve(x_padded, h1, mode='full')

    # Alinhamento: pegar amostras alinhadas com a grade original
    start = pad
    approx = approx[start: start + len(signal)][::2]
    detail = detail[start: start + len(signal)][::2]

    return approx, detail


def wavedec(
    signal: np.ndarray,
    wavelet: str = "db4",
    level: int = 5,
) -> List[np.ndarray]:
    """
    Decomposição wavelet multi-nível (análoga a pywt.wavedec).

    Retorna lista [approx, detail_coarser, ..., detail_finest]:
      coeffs[0]  = coeficientes de aproximação no nível mais baixo
      coeffs[1]  = coeficientes de detalhe no nível 'level' (mais baixas freqs dos detalhes)
      ...
      coeffs[-1] = coeficientes de detalhe no nível 1 (mais altas freqs)

    Parâmetros
    ----------
    signal  : ndarray (N,)
    wavelet : "db4" (Daubechies 4, 8 coefs) | "haar" (Haar, 2 coefs)
    level   : número de níveis de decomposição. Limitado por floor(log2(N)).

    Nota sobre Daubechies 4:
      db4 tem suporte compacto de largura 7 (2*4-1=7) e 4 momentos nulos.
      Isso significa que polinômios de grau ≤ 3 são representados exatamente
      pelos coeficientes de aproximação — ideal para tendências suaves em
      métricas de código que mudam gradualmente.
    """
    if wavelet == "db4":
        h0 = np.array(DB4_H0, dtype=np.float64)
        h1 = np.array(DB4_H1, dtype=np.float64)
    elif wavelet == "haar":
        h0 = np.array(HAAR_H0, dtype=np.float64)
        h1 = np.array(HAAR_H1, dtype=np.float64)
    else:
        raise ValueError(f"Wavelet '{wavelet}' não suportada. Use 'db4' ou 'haar'.")

    max_level = int(np.floor(np.log2(len(signal) / (len(h0) - 1)))) if len(h0) > 2 else \
                int(np.floor(np.log2(len(signal))))
    max_level = max(1, max_level)
    level = min(level, max_level)

    details = []
    approx = signal.astype(np.float64).copy()

    for _ in range(level):
        if len(approx) < len(h0):
            break
        approx, detail = _dwt_single_level(approx, h0, h1)
        details.append(detail)

    # Retornar na ordem: [approx, d_coarse, ..., d_fine]
    coeffs = [approx] + list(reversed(details))
    return coeffs


def wavelet_band_energies(
    signal: np.ndarray,
    wavelet: str = "db4",
    level: int = 5,
) -> np.ndarray:
    """
    Calcula energia em cada nível de decomposição wavelet.

    A energia de cada conjunto de coeficientes é proporcional à energia
    do sinal nas frequências correspondentes (Parseval para wavelet):
      E_nivel_k = sum(|d_k|^2)

    Retorna array de shape (level+1,) com energias normalizadas [0,1].
    O primeiro elemento é energia da aproximação (ULF).
    Os seguintes são dos detalhes, do mais grosseiro ao mais fino.
    """
    coeffs = wavedec(signal, wavelet=wavelet, level=level)

    energies = np.array([np.sum(c**2) for c in coeffs])
    total = energies.sum()
    if total > 1e-12:
        energies /= total
    return energies


def wavelet_level_to_band(level_idx: int, total_levels: int) -> str:
    """
    Mapeia índice de nível wavelet para banda de frequência.

    level_idx=0 → approx → ULF
    level_idx=1 → detalhe coarser → entre ULF e LF
    ...
    level_idx=total_levels → detalhe finest → UHF
    """
    band_map = ["ULF", "LF", "LF", "MF", "HF", "UHF"]
    if level_idx < len(band_map):
        return band_map[level_idx]
    return "UHF"
