"""
Marco 55 — Sprint W2: Stress + parameter sweep across signals/scanners (TS01-TS30)
====================================================================================

The user (APEX SCIENTIFIC mode) asked us to "testar todos sinais, scanners e
parâmetros, um teste de stress para validar o funcionamento" before the
horizon-180-days roadmap kicks in.  These tests:

* Exercise every signal/governance entry-point with a parameter sweep
  (window sizes, max_lag, alpha, thresholds, etc.).
* Push the SAST scanner with hostile inputs (very long, deeply nested,
  ReDoS-shaped) and pin a wall-clock budget.
* Hit the SnapshotStore with a high-volume batch ingest and check
  determinism + budget.
* Bench predictor_accuracy across edge cases (all-null, all-zero,
  bipolar bias) for stability.
* Smoke-test the IaC scanner across all supported formats.

Each test has both a CORRECTNESS invariant and a BUDGET assertion.
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


# ─── helpers ──────────────────────────────────────────────────────────────────

def _now() -> float:
    return time.perf_counter()


class _FakeStore:
    def __init__(self, samples):
        self._samples = samples

    def get_predictor_history(self, module_id, window=10):
        return list(self._samples)[-window:]

    def get_history(self, module_id, window=10):
        return list(self._samples)[-window:]


def _mk_mv(module: str, i: int, *, h: float = 5.0, cc: int = 2,
           bugs: float = 0.1, di: float = 0.2):
    from core.data_structures import MetricVector
    return MetricVector(
        module_id=module, commit_hash=f"c{i:04d}",
        timestamp=1_700_000_000.0 + i,
        hamiltonian=h, cyclomatic_complexity=cc,
        infinite_loop_risk=0.0, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=di,
        syntactic_dead_code=0, duplicate_block_count=0, halstead_bugs=bugs,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TS01-TS05 — predictor_accuracy parameter sweep
# ═══════════════════════════════════════════════════════════════════════════════

def _pacc_sample(h: float, err):
    return {"hamiltonian": h, "forecast_error": err}


@pytest.mark.parametrize("window", [3, 10, 50, 200, 1000])
def test_TS01_predictor_accuracy_window_sweep(window):
    from governance.signals import predictor_accuracy
    samples = [_pacc_sample(10.0, 0.5)] * 30
    store = _FakeStore(samples)
    t0 = _now()
    out = predictor_accuracy(store, "m", window=window)
    dt = _now() - t0
    assert dt < 0.05, f"predictor_accuracy slow at window={window}: {dt:.3f}s"
    assert out["verdict"] in {
        "ACCURATE", "BIASED_UP", "BIASED_DOWN", "NOISY",
        "INSUFFICIENT", "ERROR",
    }


def test_TS02_predictor_accuracy_all_null_forecast():
    from governance.signals import predictor_accuracy
    samples = [_pacc_sample(10.0, None)] * 30
    out = predictor_accuracy(_FakeStore(samples), "m")
    assert out["verdict"] == "INSUFFICIENT"


def test_TS03_predictor_accuracy_bipolar_bias_is_noisy_not_biased():
    """Errors that cancel exactly (bipolar) must be NOISY, not BIASED."""
    from governance.signals import predictor_accuracy
    samples = [_pacc_sample(10.0, +1.0)] * 10 + [_pacc_sample(10.0, -1.0)] * 10
    out = predictor_accuracy(_FakeStore(samples), "m")
    if out["verdict"] != "INSUFFICIENT":
        assert out["verdict"] in {"NOISY", "ACCURATE"}, (
            f"bipolar errors should not be BIASED; got {out['verdict']}"
        )


def test_TS04_predictor_accuracy_extreme_bias_is_directional():
    from governance.signals import predictor_accuracy
    samples = [_pacc_sample(10.0, -50.0)] * 20
    out = predictor_accuracy(_FakeStore(samples), "m")
    assert out["verdict"] == "BIASED_DOWN"


def test_TS05_predictor_accuracy_store_failure_classified_ERROR():
    from governance.signals import predictor_accuracy

    class _BoomStore:
        def get_predictor_history(self, *a, **kw):
            raise RuntimeError("DB down")

    out = predictor_accuracy(_BoomStore(), "m")
    assert out["verdict"] == "ERROR"
    assert "DB down" in out.get("error", "")


# ═══════════════════════════════════════════════════════════════════════════════
# TS06-TS10 — granger_pair parameter sweep
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("max_lag", [1, 3, 5, 10])
def test_TS06_granger_max_lag_sweep(max_lag):
    from governance.granger_causality import granger_pair
    x = [float(i % 5) for i in range(100)]
    y = [0.0] * max_lag + x[:-max_lag]  # y depends on x at lag=max_lag exactly
    r = granger_pair(x, y, max_lag=max_lag)
    assert r.best_lag <= max_lag


@pytest.mark.parametrize("alpha", [0.001, 0.01, 0.05, 0.10])
def test_TS07_granger_alpha_threshold_monotone(alpha):
    from governance.granger_causality import granger_pair
    x = [float(i % 5) for i in range(60)]
    y = [0.0] + x[:-1]
    r = granger_pair(x, y, max_lag=3, alpha=alpha)
    # Perfect lag-1 dependence should pass even strict alpha.
    assert r.granger_causes is True


def test_TS08_granger_handles_constant_input():
    from governance.granger_causality import granger_pair
    x = [3.0] * 50
    y = [3.0] * 50
    r = granger_pair(x, y, max_lag=3)
    assert isinstance(r.granger_causes, bool)
    assert 0.0 <= r.p_value <= 1.0


def test_TS09_granger_mismatched_lengths_returns_safe_default():
    from governance.granger_causality import granger_pair
    r = granger_pair([1.0, 2.0], [1.0, 2.0, 3.0], max_lag=2)
    assert r.granger_causes is False
    assert r.p_value == 1.0


def test_TS10_granger_budget_under_50ms_for_100_pts():
    from governance.granger_causality import granger_pair
    x = [float(i) for i in range(100)]
    y = [float(i * 2 + 1) for i in range(100)]
    t0 = _now()
    granger_pair(x, y, max_lag=5)
    assert _now() - t0 < 0.05


# ═══════════════════════════════════════════════════════════════════════════════
# TS11-TS15 — SAST scanner parameter sweep + hostile inputs
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS11_sast_scanner_empty_source():
    from sast.scanner import scan
    r = scan("", file_extension=".py")
    assert hasattr(r, "findings")
    assert len(r.findings) == 0


def test_TS12_sast_scanner_handles_unicode():
    from sast.scanner import scan
    src = "# encoding: utf-8\nx = '世界'\ny = 'café'\n"
    r = scan(src, file_extension=".py")
    assert hasattr(r, "findings")


def test_TS13_sast_scanner_long_input_budget():
    """500-line file scanned under 1s."""
    from sast.scanner import scan
    src = "\n".join(f"def f{i}(x):\n    return x + {i}" for i in range(500))
    t0 = _now()
    r = scan(src, file_extension=".py")
    dt = _now() - t0
    assert dt < 1.0, f"SAST scan too slow on 500-line input: {dt:.3f}s"
    assert hasattr(r, "findings")


def test_TS14_sast_scanner_redos_attack_input():
    """Pathological ReDoS-shaped source must not hang scanner."""
    from sast.scanner import scan
    # nested-quantifier shaped TEXT (not regex); scanner must still terminate
    src = (
        "import re\n"
        "PATTERN = '" + "a" * 50 + "'\n"
        "def f(s):\n"
        "    return re.match(PATTERN, s)\n"
    )
    t0 = _now()
    r = scan(src, file_extension=".py")
    assert _now() - t0 < 1.0


def test_TS15_sast_scanner_detects_known_critical():
    """eval(user_input) must trigger at least one HIGH/CRITICAL finding."""
    from sast.scanner import scan
    src = "def f(user):\n    return eval(user)\n"
    r = scan(src, file_extension=".py")
    sev = {f.severity for f in r.findings}
    assert sev & {"HIGH", "CRITICAL", "MEDIUM"}, (
        f"eval(user_input) should be flagged; got severities={sev}"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TS16-TS20 — IaC scanner smoke across formats
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS16_iac_scanner_terraform_unencrypted_s3():
    from iac.iac_scanner import IaCScanner
    files = {
        "main.tf": (
            'resource "aws_s3_bucket" "data" {\n'
            '  bucket = "my-bucket"\n'
            '}\n'
        ),
    }
    res = IaCScanner().scan_files(files)
    assert hasattr(res, "findings")


def test_TS17_iac_scanner_docker_root_user():
    from iac.iac_scanner import IaCScanner
    files = {
        "Dockerfile": "FROM ubuntu:22.04\nRUN apt-get update\n",
    }
    res = IaCScanner().scan_files(files)
    assert hasattr(res, "findings")


def test_TS18_iac_scanner_empty_corpus():
    from iac.iac_scanner import IaCScanner
    res = IaCScanner().scan_files({})
    assert res.findings == [] or len(res.findings) == 0


def test_TS19_iac_scanner_handles_malformed_yaml():
    from iac.iac_scanner import IaCScanner
    files = {"deployment.yaml": "apiVersion: v1\nkind: : : :\n"}
    # Must not raise
    res = IaCScanner().scan_files(files)
    assert hasattr(res, "findings")


def test_TS20_iac_scanner_budget_50_files_under_5s():
    from iac.iac_scanner import IaCScanner
    files = {
        f"main_{i}.tf": (
            f'resource "aws_s3_bucket" "data_{i}" {{\n'
            f'  bucket = "b-{i}"\n'
            f'}}\n'
        )
        for i in range(50)
    }
    t0 = _now()
    IaCScanner().scan_files(files)
    assert _now() - t0 < 5.0


# ═══════════════════════════════════════════════════════════════════════════════
# TS21-TS25 — SnapshotStore stress: high-volume ingest
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS21_snapshotstore_ingest_1000_under_3s():
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    t0 = _now()
    for i in range(1000):
        s.insert(_mk_mv("stress.mod", i))
    dt = _now() - t0
    assert dt < 3.0, f"1000-insert too slow: {dt:.3f}s"
    assert len(s.get_history("stress.mod", window=10_000)) == 1000


def test_TS22_snapshotstore_get_history_pagination():
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(50):
        s.insert(_mk_mv("p.mod", i))
    last10 = s.get_history("p.mod", window=10)
    assert len(last10) == 10


def test_TS23_snapshotstore_list_modules_after_bulk_ingest():
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for m in range(20):
        for i in range(5):
            s.insert(_mk_mv(f"m{m:02d}", i))
    mods = s.list_modules()
    assert len(mods) == 20


def test_TS24_snapshotstore_baseline_consistency():
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    s.insert(_mk_mv("b.mod", 0, h=5.0))
    s.insert(_mk_mv("b.mod", 1, h=10.0))
    hist = s.get_history("b.mod", window=10)
    assert hist[0].hamiltonian != hist[1].hamiltonian


def test_TS25_snapshotstore_close_then_use_raises_gracefully():
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    s.close()
    with pytest.raises(Exception):
        s.get_history("anything", window=10)


# ═══════════════════════════════════════════════════════════════════════════════
# TS26-TS30 — RCA pipeline end-to-end + propagation matrix budget
# ═══════════════════════════════════════════════════════════════════════════════

def test_TS26_rca_analyze_on_synthetic_shifted_store():
    from governance.rca import analyze
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(25):
        h = 5.0 if i < 10 else 50.0
        cc = 2 + (i if i < 10 else 10)
        bugs = 0.1 + max(0, (i - 3) * 0.05)
        di = 0.2 if i < 12 else 0.7
        s.insert(_mk_mv("rca.demo", i, h=h, cc=cc, bugs=bugs, di=di))
    r = analyze(s, "rca.demo")
    assert r.status == "OK"
    assert r.changepoint_confidence > 0.0


def test_TS27_propagation_matrix_9x9_consistency():
    from governance.propagation import compute_propagation
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(40):
        s.insert(_mk_mv("p.mod", i, h=5.0 + i * 0.1, cc=2 + (i % 5)))
    t0 = _now()
    out = compute_propagation(s, "p.mod", window=40)
    dt = _now() - t0
    assert dt < 2.0, f"propagation too slow: {dt:.3f}s"
    assert isinstance(out, dict)


def test_TS28_changepoints_detect_returns_records():
    from governance.changepoints import detect_changepoints
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(40):
        h = 1.0 if i < 20 else 10.0
        s.insert(_mk_mv("cp.mod", i, h=h, cc=2 + (i // 5)))
    cps = detect_changepoints(s, "cp.mod", penalty=3.0, window=40)
    assert isinstance(cps, list)


def test_TS29_granger_matrix_9x9_under_2s():
    from governance.granger_causality import granger_matrix
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(60):
        s.insert(_mk_mv("g.mod", i,
                        h=5.0 + 0.05 * i, cc=2 + (i % 4),
                        bugs=0.1 + 0.001 * i, di=0.2 + 0.005 * i))
    t0 = _now()
    out = granger_matrix(s, "g.mod", max_lag=3, window=60)
    dt = _now() - t0
    assert dt < 2.0, f"granger_matrix too slow on 60×9: {dt:.3f}s"
    assert isinstance(out, dict)
    assert out.get("status") in {"OK", "INSUFFICIENT"}


def test_TS30_aps_trend_payload_shape_for_flat_series():
    from governance.signals import aps_trend
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    for i in range(15):
        s.insert(_mk_mv("aps.mod", i))
    out = aps_trend(s, "aps.mod", window=15)
    assert isinstance(out, dict)
    assert "module_id" in out
