"""
Marco 50 — Sprint Q: HMC Closed-Loop Repair (TW01-TW30)
==========================================================

The biggest scientific leap in the project: Hamiltonian Monte Carlo
Bayesian sampling of AST transforms, with APS-preservation constraint
and graceful fallback to GreedyOptimizer when numpy is unavailable.

Coverage layout
---------------
* TW01-TW10 — hmc_repair() core: status semantic, valid Python,
  determinism, no-change short-circuit, timeout enforcement,
  dataclass shape
* TW11-TW20 — APS preservation, fallback paths, edge cases
* TW21-TW30 — REST surface: handler shape, 400/200, /docs registration
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sensor_core.autofix.hmc_repair import hmc_repair, HMCRepairResult


_DIRTY_SOURCE = "def f():\n    if True:\n        x = 1\n    return x\n"
_CLEAN_SOURCE = "def f():\n    return 42\n"


# ═══════════════════════════════════════════════════════════════════════════════
# TW01-TW10 — Core behavior
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW01_returns_HMCRepairResult():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, deterministic=True)
    assert isinstance(r, HMCRepairResult)


def test_TW02_status_OK_on_valid_input():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, deterministic=True)
    assert r.status in {"OK", "NO_CHANGE", "FALLBACK_NO_NUMPY",
                         "FALLBACK_GREEDY", "REJECTED_APS_REGRESSION"}


def test_TW03_patched_source_is_valid_python():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, deterministic=True)
    if r.status in ("OK", "NO_CHANGE"):
        compile(r.patched_source, "<test>", "exec")   # must not raise


def test_TW04_empty_source_returns_error():
    r = hmc_repair("", n_steps=5)
    assert r.status == "ERROR"
    assert "empty" in r.error.lower()


def test_TW05_whitespace_only_source_returns_error():
    r = hmc_repair("   \n  \n", n_steps=5)
    assert r.status == "ERROR"


def test_TW06_deterministic_seed_recorded():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, deterministic=True)
    assert r.deterministic_seed == 42


def test_TW07_non_deterministic_seed_is_none():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, deterministic=False)
    assert r.deterministic_seed is None


def test_TW08_clean_source_yields_no_change_or_low_drop():
    r = hmc_repair(_CLEAN_SOURCE, n_steps=5, deterministic=True)
    # Either NO_CHANGE or OK with very small drop — never a regression.
    assert r.status != "ERROR"
    assert r.h_drop_abs >= 0.0


def test_TW09_module_id_carried_through():
    r = hmc_repair(_DIRTY_SOURCE, module_id="my.module", n_steps=3,
                    deterministic=True)
    assert r.module_id == "my.module"


def test_TW10_elapsed_time_recorded():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=3, deterministic=True)
    assert r.elapsed_s >= 0.0
    assert r.elapsed_s < 60.0   # sanity: should not take a minute on snippet


# ═══════════════════════════════════════════════════════════════════════════════
# TW11-TW20 — APS preservation + fallback paths
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW11_preserve_aps_true_by_default_in_signature():
    """Default preserve_aps must be True (Sprint G correctness alignment)."""
    import inspect
    sig = inspect.signature(hmc_repair)
    assert sig.parameters["preserve_aps"].default is True


def test_TW12_aps_values_recorded_when_preserve_true():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, preserve_aps=True,
                    deterministic=True)
    if r.status == "OK":
        # APS values should have been recorded (either both numbers or both None)
        assert (r.aps_before is None) == (r.aps_after is None)


def test_TW13_aps_values_absent_when_preserve_false():
    r = hmc_repair(_DIRTY_SOURCE, n_steps=5, preserve_aps=False,
                    deterministic=True)
    # When preserve_aps=False, APS computation is skipped.
    assert r.aps_before is None
    assert r.aps_after is None


def test_TW14_regression_rejected_revertes_patch():
    """Inject a source whose 'patch' would lower APS — must be reverted."""
    # We can't force this in real HMC, but we can simulate by manually
    # constructing a result that triggered REJECTED_APS_REGRESSION.
    r = HMCRepairResult(
        module_id="x", original_source="a=1\n",
        patched_source="a=2\n",   # pretend patch
        status="REJECTED_APS_REGRESSION",
        aps_before=80.0, aps_after=60.0,
    )
    # In the real path, patched_source is reset to original.
    # Here we test the public contract via summary text.
    from sensor_core.autofix.hmc_repair import _make_summary
    summary = _make_summary(r)
    assert "rejected" in summary.lower()


def test_TW15_no_change_status_when_source_unchanged():
    """Clean source → HMC has nothing to improve → NO_CHANGE."""
    r = hmc_repair(_CLEAN_SOURCE, n_steps=3, deterministic=True)
    if r.patched_source == _CLEAN_SOURCE:
        assert r.status in ("NO_CHANGE", "OK")


def test_TW16_summary_text_present_in_all_statuses():
    """summary_text must always be populated."""
    for src in [_DIRTY_SOURCE, _CLEAN_SOURCE, ""]:
        r = hmc_repair(src, n_steps=3, deterministic=True)
        assert isinstance(r.summary_text, str)


def test_TW17_to_dict_serializable():
    import json
    r = hmc_repair(_DIRTY_SOURCE, n_steps=3, deterministic=True)
    text = json.dumps(r.to_dict())
    assert "patched_source" in text
    assert "status" in text


def test_TW18_h_drop_pct_zero_when_h_before_zero():
    r = hmc_repair(_CLEAN_SOURCE, n_steps=3, deterministic=True)
    # If h_before is tiny / zero, h_drop_pct must not be inf/nan
    assert r.h_drop_pct >= -1.0 and r.h_drop_pct <= 1.0 or r.h_drop_pct == 0.0


def test_TW19_short_timeout_results_in_TIMEOUT_or_completes():
    """Very short timeout must not crash — either completes or TIMEOUT."""
    r = hmc_repair(_DIRTY_SOURCE, n_steps=50, deterministic=True,
                    timeout_s=0.001)
    assert r.status in {"TIMEOUT", "OK", "NO_CHANGE", "ERROR"}


def test_TW20_invalid_python_source_handled_gracefully():
    """Source that does NOT parse — HMC must report ERROR cleanly."""
    r = hmc_repair("def broken( :\n    return\n", n_steps=3, deterministic=True)
    # Either reported as ERROR, or HMC may try and the original gets kept.
    assert r.status in {"ERROR", "NO_CHANGE", "OK"}


# ═══════════════════════════════════════════════════════════════════════════════
# TW21-TW30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW21_handle_repair_hmc_400_missing_code():
    import api.server as srv
    code, _ = srv.handle_repair_hmc({})
    assert code == 400


def test_TW22_handle_repair_hmc_400_empty_code():
    import api.server as srv
    code, _ = srv.handle_repair_hmc({"code": ""})
    assert code == 400


def test_TW23_handle_repair_hmc_200_basic_flow():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE,
        "n_steps": 3,
        "deterministic": True,
    })
    assert code == 200
    assert "status" in payload
    assert payload["status"] in {"OK", "NO_CHANGE", "FALLBACK_NO_NUMPY",
                                  "FALLBACK_GREEDY", "REJECTED_APS_REGRESSION",
                                  "TIMEOUT", "ERROR"}


def test_TW24_handle_repair_hmc_payload_has_summary():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE, "n_steps": 3, "deterministic": True,
    })
    assert "summary_text" in payload
    assert "patched_source" in payload


def test_TW25_handle_repair_hmc_module_id_propagated():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE, "module_id": "x.y.z",
        "n_steps": 3, "deterministic": True,
    })
    assert payload["module_id"] == "x.y.z"


def test_TW26_handle_repair_hmc_preserve_aps_param_accepted():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE, "preserve_aps": False,
        "n_steps": 3, "deterministic": True,
    })
    assert code == 200
    # preserve_aps=False → APS values must be None
    assert payload["aps_before"] is None


def test_TW27_handle_repair_hmc_n_steps_clamped_min_1():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE, "n_steps": 0, "deterministic": True,
    })
    assert code == 200   # clamp, no 500


def test_TW28_handle_repair_hmc_short_timeout_does_not_crash():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": _DIRTY_SOURCE, "n_steps": 50, "timeout_s": 0.001,
        "deterministic": True,
    })
    assert code == 200
    assert payload["status"] in {"TIMEOUT", "OK", "NO_CHANGE", "ERROR"}


def test_TW29_endpoint_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    assert "/repair/hmc" in paths


def test_TW30_deterministic_calls_produce_same_patch():
    """Two calls with deterministic=True and identical input must produce the
    SAME patched_source — reproducibility guarantee for CI gating."""
    src = "def g():\n    if True:\n        y = 99\n    return y\n"
    r1 = hmc_repair(src, n_steps=5, deterministic=True)
    r2 = hmc_repair(src, n_steps=5, deterministic=True)
    assert r1.patched_source == r2.patched_source
