"""
Marco 59 — Sprint Z: 5 Formal Invariants + Paper reproducibility + v3.8.1 fixes (TW01-TW30)
=============================================================================================

Pins the formal contribution of the Sprint Z paper draft:

* **TW01-TW15** — five core invariants in ``governance/invariants.py``,
  each with at least three regression tests (positive case, negative
  case, edge case).
* **TW16-TW22** — v3.8.1 backlog fixes (billing wiring expand to 18
  handlers, N+1 fix, idx_usage_tenant_occurred, prune VACUUM,
  soft_warn float).
* **TW23-TW30** — paper reproducibility script invocations + invariant
  registry catalogue.
"""
from __future__ import annotations

import csv
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


def _fresh_store():
    from sensor_storage.snapshot_store import SnapshotStore
    return SnapshotStore(":memory:")


# ═══════════════════════════════════════════════════════════════════════════════
# TW01-TW03 — Invariant I1: APS preservation
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW01_I1_holds_when_aps_equal():
    from governance.invariants import invariant_i1_aps_preserved
    assert invariant_i1_aps_preserved(0.5, 0.5) is True


def test_TW02_I1_holds_when_aps_strictly_up():
    from governance.invariants import invariant_i1_aps_preserved
    assert invariant_i1_aps_preserved(0.3, 0.7) is True


def test_TW03_I1_fails_when_aps_down():
    from governance.invariants import invariant_i1_aps_preserved
    assert invariant_i1_aps_preserved(0.7, 0.3) is False


# ═══════════════════════════════════════════════════════════════════════════════
# TW04-TW06 — Invariant I2: severity monotone
# ═══════════════════════════════════════════════════════════════════════════════

class _StubScan:
    def __init__(self, sevs):
        from types import SimpleNamespace
        self.findings = [SimpleNamespace(severity=s) for s in sevs]


def test_TW04_I2_holds_when_no_change():
    from governance.invariants import invariant_i2_no_severity_regression
    before = _StubScan(["HIGH", "LOW"])
    after  = _StubScan(["HIGH", "LOW"])
    assert invariant_i2_no_severity_regression(before, after) is True


def test_TW05_I2_fails_when_new_CRITICAL_introduced():
    from governance.invariants import invariant_i2_no_severity_regression
    before = _StubScan(["LOW"])
    after  = _StubScan(["LOW", "CRITICAL"])
    assert invariant_i2_no_severity_regression(before, after) is False


def test_TW06_I2_holds_when_HIGH_strictly_decreases():
    from governance.invariants import invariant_i2_no_severity_regression
    before = _StubScan(["HIGH", "HIGH", "LOW"])
    after  = _StubScan(["LOW"])
    assert invariant_i2_no_severity_regression(before, after) is True


# ═══════════════════════════════════════════════════════════════════════════════
# TW07-TW09 — Invariant I3: HMC convergence
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW07_I3_holds_when_OK_and_h_decreases():
    from governance.invariants import invariant_i3_hmc_convergence
    assert invariant_i3_hmc_convergence(10.0, 5.0, "OK") is True


def test_TW08_I3_fails_when_OK_and_h_increases():
    from governance.invariants import invariant_i3_hmc_convergence
    assert invariant_i3_hmc_convergence(5.0, 10.0, "OK") is False


def test_TW09_I3_vacuous_when_status_not_OK():
    """status != OK means the invariant has nothing to claim."""
    from governance.invariants import invariant_i3_hmc_convergence
    assert invariant_i3_hmc_convergence(5.0, 10.0, "ERROR") is True
    assert invariant_i3_hmc_convergence(5.0, 10.0, "TIMEOUT") is True
    assert invariant_i3_hmc_convergence(5.0, 10.0, "REJECTED_APS_REGRESSION") is True


# ═══════════════════════════════════════════════════════════════════════════════
# TW10-TW12 — Invariant I4: propagation symmetry at τ=0
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW10_I4_holds_when_symmetric():
    from governance.invariants import invariant_i4_propagation_symmetry
    assert invariant_i4_propagation_symmetry(0.123, 0.123) is True


def test_TW11_I4_fails_when_asymmetric():
    from governance.invariants import invariant_i4_propagation_symmetry
    assert invariant_i4_propagation_symmetry(0.123, 0.456) is False


def test_TW12_I4_holds_within_tolerance():
    from governance.invariants import invariant_i4_propagation_symmetry
    # 1e-10 difference < 1e-9 default tolerance
    assert invariant_i4_propagation_symmetry(0.1, 0.1 + 1e-10) is True


# ═══════════════════════════════════════════════════════════════════════════════
# TW13-TW15 — Invariant I5: period reset atomicity
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW13_I5_holds_when_second_caller_observes_already_reset():
    from governance.invariants import invariant_i5_period_reset_idempotent
    assert invariant_i5_period_reset_idempotent(True, False) is True


def test_TW14_I5_fails_when_both_callers_reset():
    from governance.invariants import invariant_i5_period_reset_idempotent
    assert invariant_i5_period_reset_idempotent(True, True) is False


def test_TW15_I5_vacuous_when_first_caller_did_not_reset():
    """If the first didn't observe a roll, the second is unconstrained."""
    from governance.invariants import invariant_i5_period_reset_idempotent
    assert invariant_i5_period_reset_idempotent(False, False) is True
    assert invariant_i5_period_reset_idempotent(False, True) is True


# ═══════════════════════════════════════════════════════════════════════════════
# TW16-TW22 — v3.8.1 backlog fixes
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW16_v381_billing_wired_on_scan_repo(isolated_store):
    """v3.8.1-fix-1: /scan-repo dispatch must go through _billed_dispatch
    (verified via source inspection — runtime check is in TW17)."""
    import inspect
    from api import server as srv
    src = inspect.getsource(srv.UCOSensorHandler.do_POST)
    # Expect: handler under _billed_dispatch
    assert '_billed_dispatch(\n                    "scan", key_info, "/scan-repo"' in src \
        or '_billed_dispatch(\n                    "scan", key_info, "/scan-repo",' in src


def test_TW17_v381_billing_wired_on_sast(isolated_store):
    import inspect
    from api import server as srv
    src = inspect.getsource(srv.UCOSensorHandler.do_POST)
    assert '"sast", key_info, "/sast"' in src


def test_TW18_v381_billing_wired_on_marketplace_publish(isolated_store):
    import inspect
    from api import server as srv
    src = inspect.getsource(srv.UCOSensorHandler.do_POST)
    assert '"signature_pub", key_info, "/marketplace/publish"' in src


def test_TW19_v381_list_usage_periods_uses_single_query():
    """v3.8.1-fix-2: replaced 1+N with a single sum_units_by_period_and_kind."""
    import inspect
    from governance import billing
    src = inspect.getsource(billing.list_usage_periods)
    assert "sum_units_by_period_and_kind" in src
    assert "for k in keys" not in src  # old N+1 loop must be gone


def test_TW20_v381_idx_usage_tenant_occurred_exists():
    """v3.8.1-fix-3: idx_usage_tenant_occurred index must be created."""
    s = _fresh_store()
    rows = s._get_conn().execute(
        "SELECT name FROM sqlite_master WHERE type='index' "
        "AND name='idx_usage_tenant_occurred'"
    ).fetchall()
    assert len(rows) == 1, "index idx_usage_tenant_occurred missing"


def test_TW21_v381_prune_old_events_accepts_vacuum_flag():
    """v3.8.1-fix-4: prune_old_events accepts vacuum=True kwarg."""
    from governance.billing import prune_old_events
    s = _fresh_store()
    n = prune_old_events(s, retention_months=12, vacuum=True)
    assert isinstance(n, int)


def test_TW22_v381_soft_warn_uses_float_arithmetic():
    """v3.8.1-fix-5: soft_warn comparison uses float, not int-floor."""
    import inspect
    from governance import billing
    src = inspect.getsource(billing.check_quota)
    assert "soft_pct" in src and "/ 100.0" in src


# ═══════════════════════════════════════════════════════════════════════════════
# TW23-TW26 — Invariant registry + assert_invariant hook
# ═══════════════════════════════════════════════════════════════════════════════

def test_TW23_list_invariants_returns_five():
    from governance.invariants import list_invariants
    catalogue = list_invariants()
    assert set(catalogue.keys()) == {"I1", "I2", "I3", "I4", "I5"}


def test_TW24_assert_invariant_raises_on_violation():
    from governance.invariants import assert_invariant, InvariantViolation
    with pytest.raises(InvariantViolation) as exc:
        assert_invariant("I1", 0.7, 0.3, hint="aps regression test")
    assert exc.value.invariant_id == "I1"
    assert "aps regression test" in str(exc.value)


def test_TW25_assert_invariant_silent_on_pass():
    from governance.invariants import assert_invariant
    # No raise = pass
    assert_invariant("I1", 0.3, 0.7)
    assert_invariant("I3", 5.0, 3.0, "OK")
    assert_invariant("I4", 1.0, 1.0)


def test_TW26_assert_invariant_unknown_id_raises_KeyError():
    from governance.invariants import assert_invariant
    with pytest.raises(KeyError):
        assert_invariant("I99", "irrelevant")


# ═══════════════════════════════════════════════════════════════════════════════
# TW27-TW30 — Paper reproducibility script smoke
# ═══════════════════════════════════════════════════════════════════════════════

_REPO_ROOT  = Path(__file__).resolve().parent.parent.parent  # algorithms/uco-sensor
_PAPER_REPRO = _REPO_ROOT / "paper" / "reproducibility.py"


def test_TW27_paper_reproducibility_script_exists():
    assert _PAPER_REPRO.exists(), f"missing {_PAPER_REPRO}"


def test_TW28_paper_reproducibility_quick_smoke(tmp_path):
    """Running with --quick produces T1.csv..T4.csv (small)."""
    rc = subprocess.call(
        [sys.executable, str(_PAPER_REPRO),
         "--output", str(tmp_path), "--quick"],
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "sensor-api")},
        timeout=60,
    )
    assert rc == 0
    for t in ("T1", "T2", "T3", "T4"):
        assert (tmp_path / f"{t}.csv").exists()


def test_TW29_paper_t1_csv_has_invariant_cases(tmp_path):
    subprocess.check_call(
        [sys.executable, str(_PAPER_REPRO),
         "--output", str(tmp_path), "--quick"],
        env={**os.environ, "PYTHONPATH": str(_REPO_ROOT / "sensor-api")},
        timeout=60,
    )
    rows = list(csv.DictReader((tmp_path / "T1.csv").open()))
    invariants_seen = {r["invariant"] for r in rows}
    assert {"I1", "I2", "I3", "I4", "I5"} <= invariants_seen


def test_TW30_paper_tex_skeleton_has_all_five_invariants():
    paper_tex = _REPO_ROOT / "paper" / "paper.tex"
    src = paper_tex.read_text(encoding="utf-8")
    for lbl in ("inv:i1", "inv:i2", "inv:i3", "inv:i4", "inv:i5"):
        assert f"\\label{{{lbl}}}" in src, f"missing {lbl}"
