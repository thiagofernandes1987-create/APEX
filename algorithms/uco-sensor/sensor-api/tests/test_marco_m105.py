"""
Marco M105 — Scientific hardening invariants
============================================
Pins properties found by the 2026-09 technical audit:
- changepoint segmentation must equal an exact dynamic-programming oracle;
- interpolated signal coordinates must map back to original commits;
- spectral frequencies must remain in cycles/commit when n_interp changes;
- Hurst from short histories must not be used as a decision amplifier;
- Granger matrix significance must use multiplicity control;
- HMC latent-policy q=0 must be neutral rather than "almost all transforms on".
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
import pytest

_FREQ = Path(__file__).resolve().parents[2] / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from transmitter.metric_signal_builder import MetricSignalBuilder
from receptor.change_point_detector import ChangePointDetector
from receptor.spectral_analyzer import SpectralAnalyzer

from governance.granger_causality import _benjamini_hochberg
from sensor_core.predictor import (
    DegradationPredictor,
    _MIN_SAMPLES_RELIABLE,
)
from uco_core.universal_code_optimizer_v4 import HMCCodeObjective


def _mv(i: int, *, h: float, cc: float = 2.0) -> MetricVector:
    return MetricVector(
        module_id="m",
        commit_hash=f"c{i:03d}",
        timestamp=1_700_000_000.0 + i * 86_400.0,
        hamiltonian=float(h),
        cyclomatic_complexity=int(cc),
        infinite_loop_risk=0.0,
        dsm_density=0.1,
        dsm_cyclic_ratio=0.0,
        dependency_instability=0.1,
        syntactic_dead_code=0,
        duplicate_block_count=0,
        halstead_bugs=0.01,
    )


def _seg_cost(x: np.ndarray, lo: int, hi: int, model: str) -> float:
    seg = np.asarray(x[lo:hi], dtype=float)
    if not len(seg):
        return 0.0
    var = max(0.0, float(np.var(seg)))
    if model in ("rbf", "gaussian"):
        return float(len(seg) * math.log(max(var, 1e-10)))
    return float(len(seg) * var)


def _exact_oracle(x: np.ndarray, model: str, penalty: float, min_size: int):
    """Independent O(N^2) DP oracle; returns (breakpoints, objective)."""
    n = len(x)
    F = [float("inf")] * (n + 1)
    prev = [-1] * (n + 1)
    F[0] = -penalty
    for t in range(min_size, n + 1):
        for s in range(0, t - min_size + 1):
            if not math.isfinite(F[s]):
                continue
            val = F[s] + _seg_cost(x, s, t, model) + penalty
            if val < F[t]:
                F[t] = val
                prev[t] = s
    bps = []
    t = n
    while t >= 0 and prev[t] > 0:
        bps.append(prev[t])
        t = prev[t]
    bps.reverse()
    return bps, F[n]


def _objective(x, bps, model, penalty):
    cuts = [0] + list(bps) + [len(x)]
    return sum(_seg_cost(x, a, b, model) for a, b in zip(cuts, cuts[1:])) + penalty * len(bps)


@pytest.mark.parametrize("model", ["l2", "rbf", "gaussian"])
def test_m105_01_changepoint_matches_exact_oracle(model):
    rng = np.random.default_rng(20260918)
    for n in range(8, 16):
        for _ in range(20):
            x = rng.normal(0.0, 1.0, n)
            # Include regime shifts, not just stationary noise.
            if n >= 10 and rng.random() < 0.7:
                x[n // 2 :] += rng.normal(1.5, 0.4)
            penalty = float(rng.choice([0.5, 1.0, 2.0, 3.0]))
            det = ChangePointDetector(model=model, penalty=penalty, min_size=2)
            got = det._pelt(x)
            _oracle_bps, oracle_obj = _exact_oracle(x, model, penalty, 2)
            got_obj = _objective(x, got, model, penalty)
            assert got_obj == pytest.approx(oracle_obj, abs=1e-8), (
                model, n, penalty, got, _oracle_bps, got_obj, oracle_obj
            )


def test_m105_02_grid_index_projects_to_original_commit():
    hist = [_mv(i, h=0.0 if i < 5 else 8.0) for i in range(10)]
    signal = MetricSignalBuilder(n_interp=32, window_fn="none").build(hist)
    assert signal is not None
    cp = ChangePointDetector(model="l2", penalty=1.0, min_size=2).detect(signal, ["H"])
    assert cp is not None
    assert cp.signal_idx is not None
    assert 0 <= cp.commit_idx < len(hist)
    assert cp.commit_hash == hist[cp.commit_idx].commit_hash
    # Step is at source commit 5; allow one commit due segment-boundary convention.
    assert abs(cp.commit_idx - 5) <= 1


def test_m105_03_builder_preserves_real_timestamps_and_commit_sample_rate():
    hist = [_mv(i, h=float(i)) for i in range(10)]
    signal = MetricSignalBuilder(n_interp=32, window_fn="none").build(hist)
    assert signal is not None
    assert signal.timestamps[0] == pytest.approx(hist[0].timestamp)
    assert signal.timestamps[-1] == pytest.approx(hist[-1].timestamp)
    assert signal.sample_rate == pytest.approx(31.0 / 9.0)
    assert signal.data_unscaled is not None
    # Legacy data_raw is standardized; unscaled retains metric units.
    assert signal.data_unscaled[0, 0] == pytest.approx(0.0)
    assert signal.data_unscaled[0, -1] == pytest.approx(9.0)


def test_m105_04_dominant_frequency_is_stable_across_interpolation_density():
    # 1 cycle every 8 commits => 0.125 cycles/commit.
    n = 64
    hist = [_mv(i, h=10.0 + math.sin(2.0 * math.pi * i / 8.0)) for i in range(n)]
    s64 = MetricSignalBuilder(n_interp=64, window_fn="hann").build(hist)
    s128 = MetricSignalBuilder(n_interp=128, window_fn="hann").build(hist)
    assert s64 is not None and s128 is not None
    p64 = SpectralAnalyzer().analyze_channel(s64, 0)
    p128 = SpectralAnalyzer().analyze_channel(s128, 0)
    assert p64.dominant_freq == pytest.approx(0.125, abs=0.03)
    assert p128.dominant_freq == pytest.approx(0.125, abs=0.03)
    assert p64.dominant_freq == pytest.approx(p128.dominant_freq, abs=0.02)


def test_m105_05_short_history_hurst_is_non_decisional_for_predictor(monkeypatch):
    # Force an extreme H estimate. With N below the reliability gate it must not
    # upgrade MEDIUM slope risk to HIGH.
    import sensor_core.predictor as predictor_mod

    monkeypatch.setattr(predictor_mod, "hurst_rs", lambda values: 0.99)
    n = min(20, _MIN_SAMPLES_RELIABLE - 1)
    # Choose a linear series whose slope/current ratio is around 6%/snapshot.
    vals = [(-1.4 + 0.6 * i) for i in range(n)]
    hist = [_mv(i, h=v) for i, v in enumerate(vals)]
    fc = DegradationPredictor().predict(hist)
    assert fc.hurst_exponent == pytest.approx(0.99)
    assert fc.risk_level == "MEDIUM"


def test_m105_06_hurst_reliability_gate_is_not_tiny():
    assert _MIN_SAMPLES_RELIABLE >= 64


def test_m105_07_benjamini_hochberg_known_values():
    q = _benjamini_hochberg([0.001, 0.01, 0.03, 0.2])
    assert q == pytest.approx([0.004, 0.02, 0.04, 0.2], abs=1e-12)


def test_m105_08_hmc_zero_latent_policy_is_neutral():
    obj = HMCCodeObjective(analyzer=None)
    q = np.zeros(len(obj.transforms), dtype=float)
    policy = obj.decode_policy(q)
    assert policy["aggression"] == pytest.approx(0.5)
    assert policy["active"] == []


def test_m105_09_hmc_policy_activates_only_positive_latents_at_zero_threshold():
    obj = HMCCodeObjective(analyzer=None)
    q = np.array([1.0 if i % 2 == 0 else -1.0 for i in range(len(obj.transforms))])
    policy = obj.decode_policy(q)
    expected = [i for i in range(len(obj.transforms)) if i % 2 == 0]
    assert sorted(policy["active"]) == expected
