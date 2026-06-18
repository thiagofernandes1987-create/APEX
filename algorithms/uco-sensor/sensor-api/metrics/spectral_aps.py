"""
Sprint F — Spectral Analysis of the APS Time Series  (v3.2.11)
================================================================
Applies signal-processing primitives to the persisted APS series of a
module to surface frequency-domain structure that no time-domain metric
exposes:

  1. **Power Spectral Density (Welch)** — energy distribution across
     frequency bands.  Three bands by fraction of Nyquist:
       LOW   [0, 1/3)   — slow degradation / long-term drift
       MID   [1/3, 2/3) — process noise / weekly cadence
       HIGH  [2/3, 1]   — fast oscillation / single-commit churn
  2. **Spectral entropy** — Shannon entropy on the normalised PSD.
     0 = single dominant frequency.  1 = white noise.  Captures
     "how predictable is the APS oscillation".
  3. **Dominant frequency** — argmax of the PSD.  ``cycle_length`` is
     ``1 / dominant_frequency`` (period in samples — i.e. commits).
  4. **Wavelet decomposition (db4 family, 3 levels via PyWavelets)** —
     coefficient energy per level.  Localises *when* in the history a
     regime change happened, while PSD only tells *which* frequency
     dominates overall.

These four signals together form a **spectral fingerprint** that lets
the caller compare modules quantitatively beyond raw APS — two modules
with identical mean APS can have radically different fingerprints, and
the dangerous ones live in the high-entropy / high-HIGH-band corner.

Design choices
--------------
- We do NOT require LEAP 4's Hamiltonian forecast — this is APS-only.
- Welch needs at least 8 samples for a sensible PSD; we gate hard
  below that and return ``status="INSUFFICIENT"``.  This matches the
  ``_MIN_SAMPLES_RELIABLE`` doctrine of the predictor module.
- Detrending is **linear** (scipy default).  We do NOT subtract the
  mean before wavelet decomposition (wavelet energy of the trend
  level is itself an informative channel).
- All numerics are JSON-safe — no NaN / inf escapes.
- Defensive throughout: any scipy/pywt failure returns a structured
  ``status="ERROR"`` payload, never raises.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


_MIN_SAMPLES = 8        # match _MIN_SAMPLES_RELIABLE from predictor.py
_WAVELET     = "db4"    # Daubechies-4 — standard for non-stationary signals
_DECOMP_LEVELS = 3


def _series_from_store(store: Any, module_id: str, window: int) -> List[float]:
    """Pull the persisted APS series for a module (oldest first, NULLs dropped)."""
    try:
        raw = store.get_aps_history(module_id, window=window)
    except Exception:
        return []
    return [float(a) for _, _, a in raw if a is not None]


def _safe(x: float) -> Optional[float]:
    """JSON-safe float — NaN/inf collapse to None."""
    if x is None:
        return None
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    return float(x)


def _band_powers(freqs: List[float], psd: List[float]) -> Dict[str, float]:
    """Sum PSD by low / mid / high band (thirds of Nyquist)."""
    if not freqs:
        return {"low": 0.0, "mid": 0.0, "high": 0.0}
    fmax = freqs[-1] if freqs[-1] > 0 else 1.0
    low, mid, high = 0.0, 0.0, 0.0
    for f, p in zip(freqs, psd):
        ratio = f / fmax
        if ratio < 1 / 3:
            low += p
        elif ratio < 2 / 3:
            mid += p
        else:
            high += p
    return {"low": float(low), "mid": float(mid), "high": float(high)}


def _spectral_entropy(psd: List[float]) -> float:
    """Shannon entropy of the *normalised* PSD, in [0, 1]."""
    total = sum(p for p in psd if p > 0)
    if total <= 0:
        return 0.0
    norm = [p / total for p in psd if p > 0]
    H = -sum(p * math.log(p) for p in norm if p > 0)
    H_max = math.log(len(norm)) if len(norm) > 1 else 1.0
    return float(H / H_max) if H_max > 0 else 0.0


def _wavelet_energy(series: List[float]) -> Dict[str, Any]:
    """
    PyWavelets multi-level decomposition.  Returns total energy per level
    (cA_n, cD_n, cD_{n-1}, ..., cD_1) — useful to localise regime shifts.

    Defensive: missing pywt / too-short series yields ``status="UNAVAILABLE"``
    without poisoning the parent payload.
    """
    try:
        import pywt
    except Exception:
        return {"status": "UNAVAILABLE", "levels": []}

    n = len(series)
    if n < 4:
        return {"status": "INSUFFICIENT", "levels": []}

    # pywt requires len >= 2^level for full decomposition; otherwise it pads.
    max_level = min(_DECOMP_LEVELS, pywt.dwt_max_level(n, _WAVELET))
    if max_level < 1:
        return {"status": "INSUFFICIENT", "levels": []}

    try:
        coeffs = pywt.wavedec(series, _WAVELET, level=max_level)
    except Exception as exc:
        return {"status": "ERROR", "error": str(exc), "levels": []}

    # coeffs = [cA_n, cD_n, cD_{n-1}, ..., cD_1]
    names = ["approximation"] + [f"detail_{max_level - i}" for i in range(max_level)]
    levels = []
    for name, c in zip(names, coeffs):
        energy = float(sum(float(x) * float(x) for x in c))
        levels.append({"level": name, "energy": _safe(energy), "n_coeffs": len(c)})
    return {"status": "OK", "levels": levels, "max_level": max_level}


def compute_aps_spectrum(
    store: Any,
    module_id: str,
    window: int = 100,
) -> Dict[str, Any]:
    """
    Compute the Welch PSD + spectral entropy + dominant frequency over the
    module's persisted APS series.

    Returns a dict with status, band powers, total power, entropy, dominant
    frequency, cycle length, and the raw arrays (capped to keep payload sane).
    """
    series = _series_from_store(store, module_id, window)
    if len(series) < _MIN_SAMPLES:
        return {
            "module_id": module_id,
            "status":    "INSUFFICIENT",
            "n_samples": len(series),
            "min_required": _MIN_SAMPLES,
        }

    try:
        import numpy as np
        from scipy.signal import welch
    except Exception as exc:
        return {
            "module_id": module_id,
            "status":    "ERROR",
            "error":     f"scipy/numpy not available: {exc}",
            "n_samples": len(series),
        }

    try:
        arr = np.asarray(series, dtype=float)
        # nperseg capped to len; small series → small windows.
        nperseg = min(len(arr), 8)
        freqs, psd = welch(arr, nperseg=nperseg, detrend="linear")
    except Exception as exc:
        return {
            "module_id": module_id,
            "status":    "ERROR",
            "error":     f"Welch PSD failed: {exc}",
            "n_samples": len(series),
        }

    freqs_l = [float(f) for f in freqs]
    psd_l   = [float(p) for p in psd]

    bands = _band_powers(freqs_l, psd_l)
    total = float(sum(psd_l))
    entropy = _spectral_entropy(psd_l)

    dom_idx = int(np.argmax(psd)) if len(psd) else 0
    dom_freq = freqs_l[dom_idx] if freqs_l else 0.0
    cycle_len = (1.0 / dom_freq) if dom_freq > 1e-9 else None

    return {
        "module_id":           module_id,
        "status":              "OK",
        "n_samples":           len(series),
        "total_power":         _safe(total),
        "band_powers":         {k: _safe(v) for k, v in bands.items()},
        "band_fractions": {
            k: _safe(v / total) if total > 1e-12 else 0.0
            for k, v in bands.items()
        },
        "spectral_entropy":    _safe(entropy),
        "dominant_frequency":  _safe(dom_freq),
        "cycle_length":        _safe(cycle_len),
        "freqs":               freqs_l,
        "psd":                 [_safe(p) for p in psd_l],
        "wavelet":             _wavelet_energy(series),
    }


def aps_fingerprint(
    store: Any,
    module_id: str,
    window: int = 100,
) -> Dict[str, Any]:
    """
    Compact, 5-channel **spectral fingerprint** suitable for module-to-module
    comparison.  Strips the raw arrays from compute_aps_spectrum; returns only
    the scalar signature.

    Channels
    --------
    band_low_fraction   ∈ [0, 1]   — slow drift share of total power
    band_mid_fraction   ∈ [0, 1]   — process-noise share
    band_high_fraction  ∈ [0, 1]   — fast oscillation share
    spectral_entropy    ∈ [0, 1]   — predictability (0 = pure tone, 1 = white noise)
    cycle_length        > 0 or None — period of the dominant frequency (in samples)

    A module deep in ``high + high_entropy`` corner is in a churning regime.
    A module dominated by ``low + low_entropy`` is degrading slowly and
    predictably.  Fingerprints cluster meaningfully under DBSCAN / k-means.
    """
    spectrum = compute_aps_spectrum(store, module_id, window=window)
    if spectrum.get("status") != "OK":
        return {
            "module_id": module_id,
            "status":    spectrum.get("status", "ERROR"),
            "n_samples": spectrum.get("n_samples", 0),
        }
    fractions = spectrum.get("band_fractions", {})
    return {
        "module_id":          module_id,
        "status":             "OK",
        "n_samples":          spectrum["n_samples"],
        "band_low_fraction":  fractions.get("low",  0.0),
        "band_mid_fraction":  fractions.get("mid",  0.0),
        "band_high_fraction": fractions.get("high", 0.0),
        "spectral_entropy":   spectrum.get("spectral_entropy"),
        "cycle_length":       spectrum.get("cycle_length"),
    }
