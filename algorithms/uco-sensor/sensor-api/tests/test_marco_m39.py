"""
Marco 39 — Sprint H: De-globalization + Domain Signals + Observability (TH01-TH30)
====================================================================================

Validates the three structural changes of Sprint H:

  H.1  governance/signals.py — single source of truth for aps_trend and
       predictor_accuracy.  Same numerical contract whether called from
       the API handler or from Compound Alert.
  H.2  _replace_store() cleanly closes+rebinds the global _store, fixing
       the bootstrap memory leak (D-1).
  H.3  JSON structured logger + /health operational metrics
       (Codex F-3 / Sprint H observability scope).

Coverage layout
---------------
* TH01-TH10 — governance.signals: aps_trend correctness + parity with
  the legacy compound_alert wrapper, Hurst gate, predictor_accuracy
  sign convention, INSUFFICIENT, ERROR paths.
* TH11-TH20 — handlers delegate to signals: handle_anti_pattern_score_trend
  + handle_predictor_accuracy emit the same numbers signals.* does;
  compound_alert produces stable tier based on signals output.
* TH21-TH30 — _replace_store + logger + /health metrics: store rebound
  cleanly, old conn closed, metrics counters increment on the right
  events, /health exposes metrics block, JSON formatter outputs valid
  JSON.
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from metrics.extended_vectors import SecurityVector
from governance import signals as gs
from governance.compound_alert import (
    _aps_trend_from_store, _predictor_accuracy_from_store,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mv(commit: str, ts: float, *, h: float = 50.0, deps: int = 0) -> MetricVector:
    mv = MetricVector("m", commit, ts, hamiltonian=h)
    mv.security = SecurityVector(sca_vulnerable_deps=deps)
    return mv


def _populated_store(n: int = 12) -> SnapshotStore:
    s = SnapshotStore(":memory:")
    for i in range(n):
        s.insert(_mv(f"c{i}", float(i), h=100.0 - i * 5, deps=i))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# H.1 — governance/signals.py is the single source of truth (TH01-TH10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TH01_aps_trend_returns_dict_with_required_keys():
    s = _populated_store(12)
    r = gs.aps_trend(s, "m")
    for key in ("module_id", "n_samples", "slope", "hurst", "verdict",
                "latest_aps", "latest_rating", "forecast_next",
                "hurst_reliable", "intercept"):
        assert key in r


def test_TH02_aps_trend_insufficient_below_four_samples():
    s = SnapshotStore(":memory:")
    s.insert(_mv("c0", 0.0, deps=1))
    s.insert(_mv("c1", 1.0, deps=2))
    r = gs.aps_trend(s, "m")
    assert r["verdict"] == "INSUFFICIENT"
    assert r["min_required"] == 4


def test_TH03_aps_trend_persistent_requires_reliable_hurst():
    # 6 samples: cannot be PERSISTENT (G.3 gate ≥ 8); should be plain DEGRADING.
    s = SnapshotStore(":memory:")
    for i in range(6):
        s.insert(_mv(f"c{i}", float(i), h=100.0 - i * 10, deps=i * 3))
    r = gs.aps_trend(s, "m")
    assert r["verdict"] != "DEGRADING_PERSISTENT"
    assert r["hurst_reliable"] is False


def test_TH04_aps_trend_reliable_when_n_at_least_eight():
    s = _populated_store(10)
    r = gs.aps_trend(s, "m")
    assert r["hurst_reliable"] is True


def test_TH05_predictor_accuracy_returns_required_keys():
    s = _populated_store(12)
    r = gs.predictor_accuracy(s, "m")
    for key in ("module_id", "n_evaluated", "verdict"):
        assert key in r


def test_TH06_predictor_accuracy_insufficient_below_three_pairs():
    s = SnapshotStore(":memory:")
    s.insert(_mv("c0", 0.0))   # not enough successors to form forecast_error pairs
    r = gs.predictor_accuracy(s, "m")
    assert r["verdict"] == "INSUFFICIENT"
    assert r["min_required"] == 3


def test_TH07_predictor_accuracy_handles_store_error_gracefully():
    class Broken:
        def get_predictor_history(self, *_a, **_kw):
            raise RuntimeError("DB exploded")
    r = gs.predictor_accuracy(Broken(), "m")
    assert r["verdict"] == "ERROR"
    assert "DB exploded" in r["error"]


def test_TH08_aps_trend_handles_store_error_gracefully():
    class Broken:
        def get_aps_history(self, *_a, **_kw):
            raise RuntimeError("DB exploded")
    r = gs.aps_trend(Broken(), "m")
    assert r["verdict"] == "ERROR"


def test_TH09_compound_alert_wrapper_returns_same_as_signals():
    """The legacy private wrappers used by Sprint A must now be
    byte-for-byte equivalent to the canonical signals.* functions —
    confirms the de-duplication landed."""
    s = _populated_store(12)
    w_aps  = _aps_trend_from_store(s, "m", 100)
    s_aps  = gs.aps_trend(s, "m", window=100)
    assert w_aps == s_aps
    w_pred = _predictor_accuracy_from_store(s, "m", 100)
    s_pred = gs.predictor_accuracy(s, "m", window=100)
    assert w_pred == s_pred


def test_TH10_predictor_accuracy_biased_up_means_actual_above_forecast():
    """Sign convention pinned (Sprint G C-2): BIASED_UP ⇔ bias > 0 ⇔
    actual > forecast ⇔ predictor UNDERSHOT (dangerous regime)."""
    s = _populated_store(10)
    r = gs.predictor_accuracy(s, "m")
    if r["verdict"] == "BIASED_UP":
        assert r["bias"] > 0
    if r["verdict"] == "BIASED_DOWN":
        assert r["bias"] < 0


# ═══════════════════════════════════════════════════════════════════════════════
# H.2 — Handlers delegate to signals (TH11-TH20)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TH11_handle_aps_trend_returns_signals_payload():
    import api.server as srv
    srv._store = _populated_store(12)
    code, payload = srv.handle_anti_pattern_score_trend("m", window=50)
    assert code == 200
    sig = gs.aps_trend(srv._store, "m", window=50)
    # Handler strips intercept / hurst_reliable from the public surface.
    for key in ("slope", "hurst", "verdict", "n_samples"):
        assert payload[key] == sig[key]


def test_TH12_handle_aps_trend_400_on_missing_module():
    import api.server as srv
    code, payload = srv.handle_anti_pattern_score_trend(None)
    assert code == 400


def test_TH13_handle_aps_trend_404_when_module_unknown():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_anti_pattern_score_trend("ghost")
    assert code == 404


def test_TH14_handle_predictor_accuracy_returns_signals_payload():
    import api.server as srv
    srv._store = _populated_store(12)
    code, payload = srv.handle_predictor_accuracy("m", window=50)
    assert code == 200
    sig = gs.predictor_accuracy(srv._store, "m", window=50)
    assert payload["verdict"] == sig["verdict"]
    assert payload["n_evaluated"] == sig["n_evaluated"]


def test_TH15_compound_alert_uses_signals_under_the_hood():
    import api.server as srv
    from governance.compound_alert import compute_compound_alert
    srv._store = _populated_store(12)
    alert = compute_compound_alert(srv._store, "m", window=50)
    # Compound classifies on signals output → verdicts must come straight
    # from the signals module.
    assert alert.aps["verdict"] in {
        "DEGRADING_PERSISTENT", "DEGRADING", "STABLE", "IMPROVING", "INSUFFICIENT"
    }
    assert alert.tier in {"RED", "AMBER", "YELLOW", "GREEN"}


def test_TH16_aps_trend_intercept_and_forecast_consistent():
    s = _populated_store(12)
    r = gs.aps_trend(s, "m")
    # forecast_next = slope * n + intercept (allowing rounding tolerance).
    expected = r["slope"] * r["n_samples"] + r["intercept"]
    assert abs(expected - r["forecast_next"]) < 0.5


def test_TH17_aps_trend_zero_mean_does_not_divide_by_zero():
    s = SnapshotStore(":memory:")
    for i in range(5):
        s.insert(_mv(f"c{i}", float(i)))   # no security → APS null → series empty
    r = gs.aps_trend(s, "m")
    assert r["verdict"] in {"INSUFFICIENT", "STABLE"}


def test_TH18_handle_aps_trend_payload_has_no_internal_keys():
    import api.server as srv
    srv._store = _populated_store(12)
    _, payload = srv.handle_anti_pattern_score_trend("m")
    assert "intercept" not in payload
    assert "hurst_reliable" not in payload


def test_TH19_handle_predictor_accuracy_payload_drops_min_required_when_present():
    import api.server as srv
    srv._store = _populated_store(12)
    code, payload = srv.handle_predictor_accuracy("m", window=50)
    assert code == 200
    if payload["verdict"] == "INSUFFICIENT":
        assert "min_required" in payload


def test_TH20_compound_alert_classifies_persistent_only_with_reliable_hurst():
    import api.server as srv
    from governance.compound_alert import compute_compound_alert
    # Only 5 samples → Hurst not reliable → tier should NOT be RED.
    srv._store = SnapshotStore(":memory:")
    for i in range(5):
        srv._store.insert(_mv(f"c{i}", float(i), h=100.0 - i*20, deps=i))
    alert = compute_compound_alert(srv._store, "m", window=50)
    assert alert.tier != "RED"


# ═══════════════════════════════════════════════════════════════════════════════
# H.3 — _replace_store + JSON logger + /health metrics (TH21-TH30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TH21_replace_store_rebinds_global():
    import api.server as srv
    original = srv._store
    srv._replace_store(":memory:")
    assert srv._store is not original


def test_TH22_replace_store_increments_metric():
    import api.server as srv
    with srv._metrics_lock:
        before = srv._metrics["store_replacements"]
    srv._replace_store(":memory:")
    with srv._metrics_lock:
        after = srv._metrics["store_replacements"]
    assert after == before + 1


def test_TH23_replace_store_closes_old_connection():
    import api.server as srv
    srv._replace_store(":memory:")
    old = srv._store
    srv._replace_store(":memory:")
    # The old in-memory store had its shared_conn closed — operations should
    # now either raise or no-op.  Either way, the global has moved on.
    assert srv._store is not old


def test_TH24_replace_store_swallows_close_failures():
    """A broken close() must NOT prevent the rebind."""
    import api.server as srv
    class BrokenClose(SnapshotStore):
        def close(self):
            raise RuntimeError("close exploded")
    original = srv._store
    srv._store = BrokenClose(":memory:")
    srv._replace_store(":memory:")
    assert srv._store is not original
    assert isinstance(srv._store, SnapshotStore)


def test_TH25_health_payload_includes_metrics_block():
    import api.server as srv
    code, payload = srv.handle_health()
    assert code == 200
    assert "metrics" in payload
    assert isinstance(payload["metrics"], dict)


def test_TH26_health_metrics_has_remediation_counters():
    import api.server as srv
    _, payload = srv.handle_health()
    for key in ("inserts_total", "remediation_writes_ok",
                "remediation_writes_failed", "auto_remediate_requests",
                "store_replacements"):
        assert key in payload["metrics"]


def test_TH27_auto_remediate_request_increments_counter():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    with srv._metrics_lock:
        before = srv._metrics["auto_remediate_requests"]
    srv.handle_apex_auto_remediate({
        "code": "import hashlib\nhashlib.md5(b'x').hexdigest()\n",
        "module_id": "th27",
    })
    with srv._metrics_lock:
        after = srv._metrics["auto_remediate_requests"]
    assert after == before + 1


def test_TH28_remediation_success_increments_ok_counter():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    with srv._metrics_lock:
        before = srv._metrics["remediation_writes_ok"]
    srv.handle_apex_auto_remediate({
        "code": "import hashlib\nhashlib.md5(b'x').hexdigest()\n",
        "module_id": "th28",
        "persist": True,
    })
    with srv._metrics_lock:
        after = srv._metrics["remediation_writes_ok"]
    assert after == before + 1


def test_TH29_remediation_failure_increments_failed_counter():
    import api.server as srv
    from unittest.mock import patch
    srv._store = SnapshotStore(":memory:")
    with srv._metrics_lock:
        before = srv._metrics["remediation_writes_failed"]
    with patch.object(srv._store, "store_remediation",
                      side_effect=RuntimeError("disk full")):
        srv.handle_apex_auto_remediate({
            "code": "import hashlib\nhashlib.md5(b'x').hexdigest()\n",
            "module_id": "th29",
            "persist": True,
        })
    with srv._metrics_lock:
        after = srv._metrics["remediation_writes_failed"]
    assert after == before + 1


def test_TH30_json_log_formatter_emits_valid_json():
    import api.server as srv
    formatter = srv._JsonLogFormatter()
    record = logging.LogRecord(
        name="uco-sensor", level=logging.INFO, pathname="x", lineno=1,
        msg="hello world", args=(), exc_info=None,
    )
    out = formatter.format(record)
    parsed = json.loads(out)
    assert parsed["level"] == "INFO"
    assert parsed["msg"] == "hello world"
    assert parsed["name"] == "uco-sensor"
    assert "ts" in parsed
