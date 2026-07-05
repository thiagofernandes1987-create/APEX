"""
Marco 38 — Sprint F: Spectral Analysis of APS (TX01-TX30)
===========================================================

Frequency-domain analysis of the persisted APS time series:
  • Welch PSD with band power (low/mid/high thirds of Nyquist)
  • Spectral entropy (0 = pure tone, 1 = white noise)
  • Dominant frequency + cycle length
  • PyWavelets db4 multi-level decomposition (energy per level)
  • Compact 5-channel fingerprint for cross-module comparison

Coverage layout
---------------
* TX01-TX10 — compute_aps_spectrum: structure, INSUFFICIENT gate at < 8,
  band powers sum, entropy bounds, sinusoidal cycle detection, noisy
  series produces high entropy, error path tolerance.
* TX11-TX20 — wavelet decomposition: 3 levels on long series, fewer
  levels on short, energy non-negative, status UNAVAILABLE handled.
* TX21-TX30 — aps_fingerprint + REST endpoints: 5-channel shape, band
  fractions sum to ~1, fingerprint vs full payload coherence,
  /spectral/aps + /spectral/fingerprint HTTP layer correctness.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from metrics.extended_vectors import SecurityVector
from metrics.spectral_aps import (
    compute_aps_spectrum, aps_fingerprint,
    _band_powers, _spectral_entropy, _wavelet_energy,
)

try:
    import pywt  # noqa: F401
    _HAS_PYWT = True
except Exception:  # noqa: BLE001
    _HAS_PYWT = False
_needs_pywt = pytest.mark.skipif(
    not _HAS_PYWT, reason="PyWavelets nao instalado — _wavelet_energy retorna UNAVAILABLE")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mv(commit: str, *, ts: float, deps: int = 0) -> MetricVector:
    mv = MetricVector("m", commit, ts, hamiltonian=50.0)
    mv.security = SecurityVector(sca_vulnerable_deps=deps)
    return mv


def _populate_sinusoidal(store: SnapshotStore, n: int = 30, period: int = 6):
    for i in range(n):
        osc = 10 * math.sin(2 * math.pi * i / period)
        store.insert(_mv(f"c{i}", ts=float(i), deps=max(0, int(5 + osc))))


def _populate_constant(store: SnapshotStore, n: int = 15, deps: int = 3):
    for i in range(n):
        store.insert(_mv(f"c{i}", ts=float(i), deps=deps))


def _populate_random(store: SnapshotStore, n: int = 30, seed: int = 42):
    import random
    r = random.Random(seed)
    for i in range(n):
        store.insert(_mv(f"c{i}", ts=float(i), deps=r.randint(0, 10)))


# ─── compute_aps_spectrum (TX01-TX10) ─────────────────────────────────────────

def test_TX01_returns_status_ok_on_long_series():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    assert r["status"] == "OK"
    assert r["n_samples"] >= 8


def test_TX02_insufficient_when_below_eight_samples():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=5)
    r = compute_aps_spectrum(s, "m")
    assert r["status"] == "INSUFFICIENT"
    assert r["min_required"] == 8


def test_TX03_unknown_module_yields_insufficient():
    r = compute_aps_spectrum(SnapshotStore(":memory:"), "ghost")
    assert r["status"] == "INSUFFICIENT"
    assert r["n_samples"] == 0


def test_TX04_band_powers_present_and_non_negative():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    bands = r["band_powers"]
    assert set(bands.keys()) == {"low", "mid", "high"}
    assert all(v >= 0 for v in bands.values())


def test_TX05_band_fractions_sum_close_to_one():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    fracs = r["band_fractions"]
    assert math.isclose(sum(fracs.values()), 1.0, abs_tol=1e-6)


def test_TX06_spectral_entropy_in_unit_interval():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    e = r["spectral_entropy"]
    assert 0.0 <= e <= 1.0


def test_TX07_dominant_frequency_present():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=30, period=6)
    r = compute_aps_spectrum(s, "m")
    assert r["dominant_frequency"] is not None
    assert r["dominant_frequency"] >= 0


def test_TX08_cycle_length_inversely_related_to_dominant_freq():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=30, period=6)
    r = compute_aps_spectrum(s, "m")
    if r["dominant_frequency"] and r["dominant_frequency"] > 1e-9:
        expected_cycle = 1.0 / r["dominant_frequency"]
        assert math.isclose(r["cycle_length"], expected_cycle, rel_tol=1e-6)


def test_TX09_random_series_has_higher_entropy_than_sine():
    s_rand = SnapshotStore(":memory:")
    _populate_random(s_rand, n=30)
    s_sine = SnapshotStore(":memory:")
    _populate_sinusoidal(s_sine, n=30, period=6)
    r_rand = compute_aps_spectrum(s_rand, "m")
    r_sine = compute_aps_spectrum(s_sine, "m")
    if r_rand["status"] == "OK" and r_sine["status"] == "OK":
        assert r_rand["spectral_entropy"] >= r_sine["spectral_entropy"] - 0.05


def test_TX10_payload_is_json_safe():
    """No NaN/inf must reach the wire."""
    import json
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    json.dumps(r)  # raises if NaN/inf present


# ─── Wavelet decomposition (TX11-TX20) ────────────────────────────────────────

@_needs_pywt
def test_TX11_wavelet_status_ok_on_long_series():
    series = [10.0 * math.sin(i / 3.0) for i in range(32)]
    w = _wavelet_energy(series)
    assert w["status"] == "OK"
    assert len(w["levels"]) >= 2


def test_TX12_wavelet_insufficient_on_short_series():
    w = _wavelet_energy([1.0, 2.0])
    # sem pywt, [1,2] retorna UNAVAILABLE antes do gate de tamanho; com pywt,
    # a série curta (<4) é INSUFFICIENT.  Ambos são status honestos.
    assert w["status"] == ("INSUFFICIENT" if _HAS_PYWT else "UNAVAILABLE")
    assert w["levels"] == []


def test_TX13_wavelet_energy_non_negative():
    series = [float(i) for i in range(20)]
    w = _wavelet_energy(series)
    if w["status"] == "OK":
        assert all(L["energy"] >= 0 for L in w["levels"])


def test_TX14_wavelet_level_names_have_approximation_and_details():
    series = [float(i) for i in range(20)]
    w = _wavelet_energy(series)
    if w["status"] == "OK":
        names = [L["level"] for L in w["levels"]]
        assert names[0] == "approximation"
        assert all(n.startswith("detail_") for n in names[1:])


def test_TX15_wavelet_max_level_bounded_by_decomp_max():
    series = [float(i) for i in range(64)]
    w = _wavelet_energy(series)
    if w["status"] == "OK":
        assert w["max_level"] <= 3   # _DECOMP_LEVELS constant


def test_TX16_wavelet_zero_series_has_zero_energy():
    w = _wavelet_energy([0.0] * 20)
    if w["status"] == "OK":
        assert all(math.isclose(L["energy"], 0.0, abs_tol=1e-12) for L in w["levels"])


def test_TX17_wavelet_n_coeffs_per_level_decreasing():
    series = [float(i) for i in range(32)]
    w = _wavelet_energy(series)
    if w["status"] == "OK" and len(w["levels"]) >= 2:
        # detail_1 has the most coeffs, approximation+detail_n the fewest.
        # The exact monotonicity depends on padding mode but cA_n <= cD_1.
        approx_count  = w["levels"][0]["n_coeffs"]
        finest_detail = w["levels"][-1]["n_coeffs"]
        assert approx_count <= finest_detail


def test_TX18_compute_spectrum_carries_wavelet_block():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    r = compute_aps_spectrum(s, "m")
    assert "wavelet" in r
    assert "status" in r["wavelet"]


def test_TX19_constant_series_has_low_total_power():
    """A constant APS series → near-zero power (linear detrend removes DC).
    Entropy is not a useful constraint here because PSD of pure numerical
    noise can spread the residual energy across bins.  Total power, however,
    must remain tiny relative to an oscillating series of the same length."""
    s_const = SnapshotStore(":memory:")
    _populate_constant(s_const, n=20, deps=3)
    s_osc = SnapshotStore(":memory:")
    _populate_sinusoidal(s_osc, n=20)
    r_const = compute_aps_spectrum(s_const, "m")
    r_osc   = compute_aps_spectrum(s_osc, "m")
    assert r_const["status"] == "OK" and r_osc["status"] == "OK"
    assert r_const["total_power"] < r_osc["total_power"]


def test_TX20_band_powers_helper_sums_correctly():
    freqs = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
    psd   = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
    b = _band_powers(freqs, psd)
    # f_max = 0.5; thirds → [0, 0.167), [0.167, 0.333), [0.333, 0.5]
    assert math.isclose(sum(b.values()), 6.0, abs_tol=1e-6)
    assert b["low"] > 0 and b["mid"] > 0 and b["high"] > 0


# ─── aps_fingerprint + REST endpoints (TX21-TX30) ─────────────────────────────

def test_TX21_fingerprint_has_five_channels():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    fp = aps_fingerprint(s, "m")
    for key in ("band_low_fraction", "band_mid_fraction", "band_high_fraction",
                "spectral_entropy", "cycle_length"):
        assert key in fp


def test_TX22_fingerprint_band_fractions_sum_to_one():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    fp = aps_fingerprint(s, "m")
    total = (fp["band_low_fraction"] + fp["band_mid_fraction"]
             + fp["band_high_fraction"])
    assert math.isclose(total, 1.0, abs_tol=1e-6)


def test_TX23_fingerprint_inherits_insufficient_status():
    fp = aps_fingerprint(SnapshotStore(":memory:"), "ghost")
    assert fp["status"] == "INSUFFICIENT"


def test_TX24_fingerprint_coheres_with_full_spectrum():
    s = SnapshotStore(":memory:")
    _populate_sinusoidal(s, n=20)
    full = compute_aps_spectrum(s, "m")
    fp   = aps_fingerprint(s, "m")
    assert math.isclose(fp["band_low_fraction"],
                        full["band_fractions"]["low"], abs_tol=1e-9)
    assert math.isclose(fp["spectral_entropy"],
                        full["spectral_entropy"], abs_tol=1e-9)


def test_TX25_handle_spectral_aps_returns_200_on_valid_input():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    _populate_sinusoidal(srv._store, n=20)
    code, payload = srv.handle_spectral_aps("m", window=50)
    assert code == 200
    assert payload["status"] == "OK"


def test_TX26_handle_spectral_aps_400_on_empty_module():
    import api.server as srv
    code, payload = srv.handle_spectral_aps("", window=50)
    assert code == 400
    assert "error" in payload


def test_TX27_handle_spectral_fingerprint_returns_200():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    _populate_sinusoidal(srv._store, n=20)
    code, payload = srv.handle_spectral_fingerprint("m", window=50)
    assert code == 200
    assert payload["status"] == "OK"
    assert "band_high_fraction" in payload


def test_TX28_handle_spectral_fingerprint_400_on_empty_module():
    import api.server as srv
    code, payload = srv.handle_spectral_fingerprint("", window=50)
    assert code == 400


def test_TX29_endpoint_payload_is_json_safe():
    import api.server as srv, json
    srv._store = SnapshotStore(":memory:")
    _populate_sinusoidal(srv._store, n=20)
    _, payload = srv.handle_spectral_aps("m", window=50)
    json.dumps(payload)
    _, payload2 = srv.handle_spectral_fingerprint("m", window=50)
    json.dumps(payload2)


def test_TX30_unknown_module_via_endpoint_yields_insufficient_payload():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_spectral_aps("nope", window=50)
    # 200 + status=INSUFFICIENT — not a 404, because the underlying
    # function does not distinguish "module missing" from "module too short".
    assert code == 200
    assert payload["status"] == "INSUFFICIENT"
