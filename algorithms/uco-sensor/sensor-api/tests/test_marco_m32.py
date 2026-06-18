"""
test_marco_m32.py — Sprint A: Compound Alert (30 tests TC01-TC30)
==================================================================
Validates the Sprint A deliverable (v3.2.5 — APS×Predictor cross-correlation):

  TC01-TC06  Tier ladder + classifier policy (RED/AMBER/YELLOW/GREEN)
  TC07-TC14  Per-module compute_compound_alert (insufficient, degrading, biased, clean)
  TC15-TC20  Repo-wide ranking + tier histogram + filtering
  TC21-TC26  Priority score bounds + reason strings + dataclass round-trip
  TC27-TC30  REST endpoints /alerts/compound and /alerts/repo
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from metrics.extended_vectors import FlowVector, ThreadSafetyVector
from governance.compound_alert import (
    CompoundAlert, compute_compound_alert,
    repo_compound_alerts, repo_tier_histogram,
    _classify, _priority,
)


def _mv(module="m.mod", commit="c1", ts=1.0, h=2.0, cc=8,
        taint=0, locks=0):
    mv = MetricVector(module, commit, ts, hamiltonian=h, cyclomatic_complexity=cc)
    mv.flow          = FlowVector(taint_path_count=taint,
                                  injection_surface=taint * 0.2)
    mv.thread_safety = ThreadSafetyVector(lock_missing_count=locks)
    return mv


def _fresh_store():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
    return SnapshotStore(f.name), f.name


def _degrading(store, module="d.mod", n=12):
    """Monotonic taint + H growth — APS drops, H rises → DEGRADING_PERSISTENT."""
    for i in range(n):
        h = 1.0 + 0.5 * (1.3 ** i)
        store.insert(_mv(module=module, commit=f"c{i:02d}",
                         ts=float(i), h=h, cc=10 + i, taint=i, locks=i // 3))


def _clean(store, module="c.mod", n=8):
    """Constant clean snapshots — APS=100 forever."""
    for i in range(n):
        store.insert(_mv(module=module, commit=f"c{i:02d}",
                         ts=float(i), h=1.0, cc=5))


# ══════════════════════════════════════════════════════════════════════════════
# TC01-TC06 — Classifier policy
# ══════════════════════════════════════════════════════════════════════════════

class TestClassifier(unittest.TestCase):

    def test_TC01_RED_when_both_signals_critical(self):
        # Sprint G fix (C-2): RED fires on BIASED_UP (predictor undershoots),
        # not BIASED_DOWN.  The previous test pinned the inverted-sign bug.
        tier, reasons = _classify(
            aps_verdict="DEGRADING_PERSISTENT",
            predictor_verdict="BIASED_UP",
            aps_slope=-2.0, predictor_mae_rel=0.18,
        )
        self.assertEqual(tier, "RED")
        self.assertGreaterEqual(len(reasons), 2)

    def test_TC02_AMBER_when_only_aps_degrading(self):
        tier, _ = _classify("DEGRADING", "ACCURATE", -1.0, 0.05)
        self.assertEqual(tier, "AMBER")

    def test_TC03_AMBER_when_only_predictor_biased(self):
        tier, _ = _classify("STABLE", "BIASED_DOWN", 0.0, 0.20)
        self.assertEqual(tier, "AMBER")

    def test_TC04_YELLOW_compound_weak_signal(self):
        # Slope negative + MAE > 10% but neither verdict strong
        tier, reasons = _classify("INSUFFICIENT", "NOISY", -0.5, 0.25)
        self.assertEqual(tier, "YELLOW")
        self.assertGreater(len(reasons), 0)

    def test_TC05_GREEN_when_clean(self):
        tier, reasons = _classify("STABLE", "ACCURATE", 0.0, 0.02)
        self.assertEqual(tier, "GREEN")
        self.assertEqual(reasons, [])

    def test_TC06_RED_takes_priority_over_AMBER(self):
        # Both signals firing → RED, not AMBER.
        # Sprint G fix (C-2): RED uses BIASED_UP (undershoot), not BIASED_DOWN.
        tier, _ = _classify("DEGRADING_PERSISTENT", "BIASED_UP", -5.0, 0.5)
        self.assertEqual(tier, "RED")


# ══════════════════════════════════════════════════════════════════════════════
# TC07-TC14 — compute_compound_alert per module
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeCompoundAlert(unittest.TestCase):

    def test_TC07_insufficient_history_yields_green(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())
            alert = compute_compound_alert(store, "m.mod")
            self.assertEqual(alert.tier, "GREEN")
            self.assertEqual(alert.priority_score, 5.0)
        finally:
            os.unlink(dbf)

    def test_TC08_clean_module_stays_green(self):
        store, dbf = _fresh_store()
        try:
            _clean(store, module="c.mod", n=8)
            alert = compute_compound_alert(store, "c.mod")
            self.assertEqual(alert.tier, "GREEN")
            self.assertEqual(alert.reasons, [])
        finally:
            os.unlink(dbf)

    def test_TC09_degrading_module_escalates_to_red_or_amber(self):
        store, dbf = _fresh_store()
        try:
            _degrading(store, module="d.mod", n=12)
            alert = compute_compound_alert(store, "d.mod")
            self.assertIn(alert.tier, ("RED", "AMBER", "YELLOW"))
            self.assertGreater(alert.priority_score, 30.0)
            self.assertGreater(len(alert.reasons), 0)
        finally:
            os.unlink(dbf)

    def test_TC10_alert_carries_aps_subdict(self):
        store, dbf = _fresh_store()
        try:
            _degrading(store, n=10)
            alert = compute_compound_alert(store, "d.mod")
            for key in ("verdict", "latest", "latest_rating", "slope", "hurst"):
                self.assertIn(key, alert.aps)
        finally:
            os.unlink(dbf)

    def test_TC11_alert_carries_predictor_subdict(self):
        store, dbf = _fresh_store()
        try:
            _degrading(store, n=10)
            alert = compute_compound_alert(store, "d.mod")
            for key in ("verdict", "mae", "rmse", "bias",
                        "mae_relative", "n_evaluated"):
                self.assertIn(key, alert.predictor)
        finally:
            os.unlink(dbf)

    def test_TC12_unknown_module_yields_green(self):
        store, dbf = _fresh_store()
        try:
            alert = compute_compound_alert(store, "does-not-exist")
            self.assertEqual(alert.tier, "GREEN")
        finally:
            os.unlink(dbf)

    def test_TC13_to_dict_round_trip(self):
        store, dbf = _fresh_store()
        try:
            _degrading(store, n=10)
            d = compute_compound_alert(store, "d.mod").to_dict()
            for key in ("module_id", "n_samples", "aps", "predictor",
                        "tier", "priority_score", "reasons"):
                self.assertIn(key, d)
        finally:
            os.unlink(dbf)

    def test_TC14_n_samples_matches_aps_history(self):
        store, dbf = _fresh_store()
        try:
            _degrading(store, n=10)
            alert = compute_compound_alert(store, "d.mod")
            self.assertEqual(alert.n_samples, 10)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TC15-TC20 — Repo-wide ranking + histogram + filtering
# ══════════════════════════════════════════════════════════════════════════════

class TestRepoRanking(unittest.TestCase):

    def _multi_repo(self):
        store, dbf = _fresh_store()
        _degrading(store, module="hot.mod",  n=12)
        _degrading(store, module="warm.mod", n=8)
        _clean(store,     module="cold.mod", n=8)
        return store, dbf

    def test_TC15_repo_sorts_worst_first(self):
        store, dbf = self._multi_repo()
        try:
            alerts = repo_compound_alerts(store, include_green=True)
            scores = [a.priority_score for a in alerts]
            self.assertEqual(scores, sorted(scores, reverse=True))
        finally:
            os.unlink(dbf)

    def test_TC16_filters_green_by_default(self):
        store, dbf = self._multi_repo()
        try:
            alerts = repo_compound_alerts(store)
            self.assertTrue(all(a.tier != "GREEN" for a in alerts))
        finally:
            os.unlink(dbf)

    def test_TC17_include_green_keeps_them(self):
        store, dbf = self._multi_repo()
        try:
            alerts = repo_compound_alerts(store, include_green=True)
            self.assertGreater(sum(1 for a in alerts if a.tier == "GREEN"), 0)
        finally:
            os.unlink(dbf)

    def test_TC18_top_k_cap(self):
        store, dbf = self._multi_repo()
        try:
            alerts = repo_compound_alerts(store, include_green=True, top_k=2)
            self.assertLessEqual(len(alerts), 2)
        finally:
            os.unlink(dbf)

    def test_TC19_histogram_keys_canonical(self):
        store, dbf = self._multi_repo()
        try:
            alerts = repo_compound_alerts(store, include_green=True)
            hist = repo_tier_histogram(alerts)
            self.assertEqual(set(hist.keys()), {"RED", "AMBER", "YELLOW", "GREEN"})
            self.assertEqual(sum(hist.values()), len(alerts))
        finally:
            os.unlink(dbf)

    def test_TC20_empty_repo_yields_empty(self):
        store, dbf = _fresh_store()
        try:
            self.assertEqual(repo_compound_alerts(store), [])
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TC21-TC26 — Priority score bounds + reasons + dataclass invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestPriorityAndStructure(unittest.TestCase):

    def test_TC21_priority_bounded_to_0_100(self):
        # Extreme inputs must not exceed 100
        score = _priority("RED", aps_slope=-1000.0, predictor_mae_rel=10.0)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 100.0)

    def test_TC22_priority_RED_above_AMBER(self):
        self.assertGreater(
            _priority("RED",   -1.0, 0.20),
            _priority("AMBER", -1.0, 0.20),
        )

    def test_TC23_priority_AMBER_above_YELLOW(self):
        self.assertGreater(
            _priority("AMBER",  -1.0, 0.20),
            _priority("YELLOW", -1.0, 0.20),
        )

    def test_TC24_priority_YELLOW_above_GREEN(self):
        self.assertGreater(
            _priority("YELLOW", -1.0, 0.20),
            _priority("GREEN",  -1.0, 0.20),
        )

    def test_TC25_RED_reasons_describe_both_signals(self):
        # Sprint G fix (C-2): RED fires on BIASED_UP, not BIASED_DOWN.
        _, reasons = _classify("DEGRADING_PERSISTENT", "BIASED_UP",
                                -1.0, 0.12)
        self.assertTrue(any("APS" in r for r in reasons))
        self.assertTrue(any("Predictor" in r for r in reasons))

    def test_TC26_compound_alert_dataclass_defaults(self):
        a = CompoundAlert(module_id="x", n_samples=0)
        self.assertEqual(a.tier, "GREEN")
        self.assertEqual(a.aps, {})
        self.assertEqual(a.predictor, {})
        self.assertEqual(a.reasons, [])


# ══════════════════════════════════════════════════════════════════════════════
# TC27-TC30 — REST endpoints
# ══════════════════════════════════════════════════════════════════════════════

class TestEndpoints(unittest.TestCase):

    def setUp(self):
        import api.server as srv
        self.srv = srv
        self._orig = srv._store
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
        self.dbf = f.name
        srv._store = SnapshotStore(self.dbf)

    def tearDown(self):
        self.srv._store = self._orig
        os.unlink(self.dbf)

    def test_TC27_compound_endpoint_400_without_module(self):
        code, _ = self.srv.handle_compound_alert(None)
        self.assertEqual(code, 400)

    def test_TC28_compound_endpoint_returns_alert_shape(self):
        _degrading(self.srv._store, n=10)
        code, data = self.srv.handle_compound_alert("d.mod")
        self.assertEqual(code, 200)
        self.assertIn("tier", data)
        self.assertIn("priority_score", data)
        self.assertIn("aps", data)
        self.assertIn("predictor", data)
        self.assertIn("reasons", data)

    def test_TC29_repo_endpoint_returns_histogram_and_alerts(self):
        _degrading(self.srv._store, module="hot.mod",  n=12)
        _clean    (self.srv._store, module="cold.mod", n=8)
        code, data = self.srv.handle_repo_alerts(top_k=5)
        self.assertEqual(code, 200)
        for key in ("n_modules", "histogram", "top_module",
                    "alerts", "window", "include_green"):
            self.assertIn(key, data)
        self.assertEqual(data["n_modules"], 2)
        # default (include_green=False) → cold.mod should NOT appear
        emitted_modules = {a["module_id"] for a in data["alerts"]}
        self.assertNotIn("cold.mod", emitted_modules)

    def test_TC30_repo_endpoint_include_green_param_works(self):
        _degrading(self.srv._store, module="hot.mod",  n=12)
        _clean    (self.srv._store, module="cold.mod", n=8)
        code, data = self.srv.handle_repo_alerts(include_green=True)
        emitted_modules = {a["module_id"] for a in data["alerts"]}
        self.assertIn("cold.mod", emitted_modules)
        # histogram is computed BEFORE filter → both tiers represented
        self.assertEqual(
            sum(data["histogram"].values()),
            2,
        )


if __name__ == "__main__":
    unittest.main()
