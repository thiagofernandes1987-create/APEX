"""
Marco M106 — Benchmark-v2 isolation invariants
==============================================
Pins corrections from the first formal benchmark audit:
- endpoint-only change detection is separate from retrospective PELT;
- changepoint strength stays bounded without clipping saturation;
- Granger can operate on first differences and preserves tiny p-values;
- formal evaluator rejects variable-N / unpaired repository groups.
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
import pytest

_UCO = Path(__file__).resolve().parents[2]
_FREQ = _UCO / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from transmitter.metric_signal_builder import MetricSignalBuilder
from receptor.endpoint_change_detector import EndpointChangeDetector
from receptor.change_point_detector import ChangePointDetector
import governance.granger_causality as gc


def _mv(i: int, *, h: float = 1.0, cc: float = 2.0) -> MetricVector:
    return MetricVector(
        module_id="m", commit_hash=f"c{i:03d}",
        timestamp=1_700_000_000.0 + i * 86_400.0,
        hamiltonian=float(h), cyclomatic_complexity=int(cc),
        infinite_loop_risk=0.0, dsm_density=0.1, dsm_cyclic_ratio=0.0,
        dependency_instability=0.1, syntactic_dead_code=0,
        duplicate_block_count=0, halstead_bugs=0.01,
    )


def test_m106_01_endpoint_flat_signal_is_neutral():
    hist = [_mv(i, h=5.0) for i in range(40)]
    sig = MetricSignalBuilder(n_interp=40, window_fn="none").build(hist)
    result = EndpointChangeDetector().detect(sig)
    assert result.n_prior == 39
    assert result.max_robust_z == pytest.approx(0.0)
    assert result.affected_channels == []


def test_m106_02_endpoint_spike_is_detected_without_pelt_future_samples():
    hist = [_mv(i, h=5.0) for i in range(39)] + [_mv(39, h=20.0)]
    sig = MetricSignalBuilder(n_interp=40, window_fn="none").build(hist)
    result = EndpointChangeDetector().detect(sig)
    assert result.max_robust_z > 3.5
    assert "H" in result.affected_channels


def test_m106_03_changepoint_strength_does_not_clip_to_one():
    hist = [_mv(i, h=0.0 if i < 20 else 20.0) for i in range(40)]
    sig = MetricSignalBuilder(n_interp=40, window_fn="none").build(hist)
    cp = ChangePointDetector(model="l2", penalty=1.0, min_size=3).detect(sig, ["H"])
    assert cp is not None
    assert 0.0 < cp.confidence < 1.0


def test_m106_04_granger_difference_reduces_effective_sample_count():
    x = [float(i) for i in range(80)]
    y = [0.0] + x[:-1]
    r = gc.granger_pair(x, y, max_lag=3, difference=True)
    assert r.n_samples == 79
    assert 0.0 <= r.p_value <= 1.0


def test_m106_05_granger_preserves_sub_micro_pvalue_precision(monkeypatch):
    # Isolate the serialization/rounding contract from OLS geometry.
    calls = {"n": 0}

    def fake_ols(X, y):
        calls["n"] += 1
        # restricted RSS > unrestricted RSS for every lag
        rss = 10.0 if calls["n"] % 2 == 1 else 5.0
        return [0.0] * (len(X[0]) if X else 0), rss

    monkeypatch.setattr(gc, "_ols_solve", fake_ols)
    monkeypatch.setattr(gc, "_f_survival", lambda f, df1, df2: 1.23456789e-8)
    x = [float(i) for i in range(80)]
    y = [float((i * 3 + 1) % 11) for i in range(80)]
    r = gc.granger_pair(x, y, max_lag=3)
    assert r.best_lag > 0
    assert r.p_value > 0.0
    assert r.p_value != round(r.p_value, 6)



def _load_evaluator():
    path = _UCO / "paper" / "formal_benchmark" / "evaluate.py"
    spec = importlib.util.spec_from_file_location("uco_bench_eval_v2", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_m106_06_evaluator_rejects_variable_n_and_unpaired_repos():
    ev = _load_evaluator()
    rows = [
        {"repo": "ok/r", "label": 1, "n_history": 40},
        {"repo": "ok/r", "label": 0, "n_history": 40},
        {"repo": "bad/n", "label": 1, "n_history": 39},
        {"repo": "bad/n", "label": 0, "n_history": 40},
        {"repo": "bad/unpaired", "label": 1, "n_history": 40},
    ]
    kept, info = ev.enforce_complete_fixed_rows(rows)
    assert {r["repo"] for r in kept} == {"ok/r"}
    assert info["retained_repos"] == 1
    assert info["dropped_repos"] == 2
    assert info["wrong_n_rows"] == 1


def test_m106_07_v2_arm_names_do_not_claim_pelt_or_full_static():
    ev = _load_evaluator()
    assert "D_ENDPOINT_CHANGE" in ev.ARMS
    assert "D_CHANGEPOINT" not in ev.ARMS
    assert "A_STRUCTURAL_STATIC" in ev.ARMS
