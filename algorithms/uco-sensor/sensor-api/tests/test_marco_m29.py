"""
test_marco_m29.py — LEAP 2: APS persistido + endpoints history/trend (30 tests TZ01-TZ30)
==========================================================================================
Validates the LEAP 2 deliverable (v3.2.2 — APS as persisted signal):

  TZ01-TZ08  Schema + insert-time APS computation + backward-compat
  TZ09-TZ16  get_aps_history helper + mv.aps_score round-trip
  TZ17-TZ24  GET /anti-pattern-score/history endpoint
  TZ25-TZ30  GET /anti-pattern-score/trend endpoint (OLS + Hurst + verdict)
"""
from __future__ import annotations

import os
import sqlite3
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
from metrics.extended_vectors import (
    FlowVector, ThreadSafetyVector, ReliabilityVector, PerformanceVector,
)


def _mv(module="demo.mod", commit="c1", ts=1000.0, taint=0, locks=0,
        bare_except=0, n_plus_one=0):
    mv = MetricVector(module, commit, ts, hamiltonian=5.0, cyclomatic_complexity=10)
    mv.flow          = FlowVector(taint_path_count=taint,
                                  injection_surface=taint * 0.2)
    mv.thread_safety = ThreadSafetyVector(lock_missing_count=locks)
    mv.reliability   = ReliabilityVector(bare_except_count=bare_except)
    mv.performance   = PerformanceVector(n_plus_one_risk=n_plus_one)
    return mv


# (DP v3.93.0/D8) Windows: SQLite mantem o arquivo aberto ate o GC fechar a
# conexao; unlink direto levanta PermissionError.  Fecha via gc + retry e, em
# ultimo caso, ignora (arquivo temp e' descartavel).  No-op em POSIX.
import gc as _gc


def _safe_unlink(path):
    for _ in range(4):
        try:
            os.unlink(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            _gc.collect()


def _fresh_store():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
    return SnapshotStore(f.name), f.name


# ══════════════════════════════════════════════════════════════════════════════
# TZ01-TZ08 — Schema + insert-time APS + backward-compat
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaAndInsert(unittest.TestCase):

    def test_TZ01_aps_score_column_exists(self):
        store, dbf = _fresh_store()
        try:
            with sqlite3.connect(dbf) as c:
                cols = [r[1] for r in c.execute("PRAGMA table_info(snapshots)")]
            self.assertIn("aps_score", cols)
        finally:
            _safe_unlink(dbf)

    def test_TZ02_aps_computed_at_insert_time(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(taint=2, locks=1))
            with sqlite3.connect(dbf) as c:
                aps, = c.execute("SELECT aps_score FROM snapshots").fetchone()
            self.assertIsNotNone(aps)
            self.assertGreater(aps, 0.0)
            self.assertLess(aps, 100.0)
        finally:
            _safe_unlink(dbf)

    def test_TZ03_clean_snapshot_persists_aps_100(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(taint=0, locks=0, bare_except=0, n_plus_one=0))
            with sqlite3.connect(dbf) as c:
                aps, = c.execute("SELECT aps_score FROM snapshots").fetchone()
            self.assertAlmostEqual(aps, 100.0)
        finally:
            _safe_unlink(dbf)

    def test_TZ04_legacy_mv_no_extended_vectors_writes_null_aps(self):
        """An mv with NO extended vectors → APS = None (UNKNOWN, NOT 100/A).

        Sprint G fix (C-1): absence of evidence must NOT score as 'no
        anti-patterns detected'.  The persisted aps_score column for a
        legacy/unscanned snapshot is NULL — quality gates downstream see
        UNKNOWN and treat it as a hard fail, not as 'A'.
        """
        store, dbf = _fresh_store()
        try:
            plain = MetricVector("legacy", "old", 50.0,
                                 hamiltonian=3.0, cyclomatic_complexity=5)
            store.insert(plain)
            hist = store.get_aps_history("legacy")
            self.assertEqual(len(hist), 1)
            self.assertIsNone(hist[0][2])
        finally:
            _safe_unlink(dbf)

    def test_TZ05_aps_proportional_to_taint(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="c1", taint=0))
            store.insert(_mv(commit="c2", taint=2))
            store.insert(_mv(commit="c3", taint=5))
            scores = [aps for _, _, aps in store.get_aps_history("demo.mod")]
            self.assertGreater(scores[0], scores[1])
            self.assertGreater(scores[1], scores[2])
        finally:
            _safe_unlink(dbf)

    def test_TZ06_aps_column_is_REAL_type(self):
        store, dbf = _fresh_store()
        try:
            with sqlite3.connect(dbf) as c:
                info = [r for r in c.execute("PRAGMA table_info(snapshots)")
                        if r[1] == "aps_score"]
            self.assertEqual(info[0][2].upper(), "REAL")
        finally:
            _safe_unlink(dbf)

    def test_TZ07_simulated_old_row_with_null_aps_loads_cleanly(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="c1"))
            with sqlite3.connect(dbf) as c:
                c.execute("UPDATE snapshots SET aps_score = NULL")
            mv = store.get_history("demo.mod")[0]
            # mv.aps_score must be None (matching legacy semantics)
            self.assertIsNone(mv.aps_score)
        finally:
            _safe_unlink(dbf)

    def test_TZ08_insert_does_not_fail_if_aps_engine_unavailable(self):
        """Guard: a missing/broken metrics module must not block insert."""
        store, dbf = _fresh_store()
        try:
            mv = MetricVector("guard", "c1", 1.0,
                              hamiltonian=1.0, cyclomatic_complexity=1)
            # Simulate broken APS engine: attach a vector that throws on to_dict
            class Bomb:
                def to_dict(self):
                    raise RuntimeError("boom")
            mv.flow = Bomb()
            store.insert(mv)   # must not raise
            self.assertEqual(len(store.get_history("guard")), 1)
        finally:
            _safe_unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TZ09-TZ16 — get_aps_history + mv.aps_score round-trip
# ══════════════════════════════════════════════════════════════════════════════

class TestAPSHistoryHelper(unittest.TestCase):

    def test_TZ09_aps_history_chronological_order(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="c1", ts=100.0))
            store.insert(_mv(commit="c2", ts=200.0))
            store.insert(_mv(commit="c3", ts=150.0))
            ts_seen = [ts for _, ts, _ in store.get_aps_history("demo.mod")]
            self.assertEqual(ts_seen, [100.0, 150.0, 200.0])
        finally:
            _safe_unlink(dbf)

    def test_TZ10_aps_history_returns_commit_ts_aps_tuple(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="abc", ts=10.0, taint=1))
            hist = store.get_aps_history("demo.mod")
            self.assertEqual(len(hist), 1)
            commit, ts, aps = hist[0]
            self.assertEqual(commit, "abc")
            self.assertEqual(ts, 10.0)
            self.assertIsInstance(aps, float)
        finally:
            _safe_unlink(dbf)

    def test_TZ11_aps_history_window_limit(self):
        store, dbf = _fresh_store()
        try:
            for i in range(5):
                store.insert(_mv(commit=f"c{i}", ts=float(i)))
            hist = store.get_aps_history("demo.mod", window=3)
            self.assertEqual(len(hist), 3)
            # Most-recent 3, returned ASC
            self.assertEqual([ts for _, ts, _ in hist], [2.0, 3.0, 4.0])
        finally:
            _safe_unlink(dbf)

    def test_TZ12_mv_aps_score_round_trips_via_get_history(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(taint=3, locks=1))
            mv = store.get_history("demo.mod")[0]
            self.assertIsNotNone(mv.aps_score)
            self.assertGreater(mv.aps_score, 0.0)
            self.assertLess(mv.aps_score, 100.0)
        finally:
            _safe_unlink(dbf)

    def test_TZ13_null_aps_returned_as_none_in_helper(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())
            with sqlite3.connect(dbf) as c:
                c.execute("UPDATE snapshots SET aps_score = NULL")
            hist = store.get_aps_history("demo.mod")
            self.assertIsNone(hist[0][2])
        finally:
            _safe_unlink(dbf)

    def test_TZ14_cross_module_isolation(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="a.mod", taint=0))
            store.insert(_mv(module="b.mod", taint=4))
            a_aps = store.get_aps_history("a.mod")[0][2]
            b_aps = store.get_aps_history("b.mod")[0][2]
            self.assertGreater(a_aps, b_aps)
        finally:
            _safe_unlink(dbf)

    def test_TZ15_empty_module_returns_empty_history(self):
        store, dbf = _fresh_store()
        try:
            self.assertEqual(store.get_aps_history("nobody"), [])
        finally:
            _safe_unlink(dbf)

    def test_TZ16_leap1_regression_extended_vectors_still_load(self):
        """LEAP 2 must not regress LEAP 1: extended vectors v2 still round-trip."""
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(taint=2))
            mv = store.get_history("demo.mod")[0]
            self.assertIsNotNone(getattr(mv, "flow", None))
            self.assertEqual(mv.flow.taint_path_count, 2)
        finally:
            _safe_unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TZ17-TZ24 — /anti-pattern-score/history endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestHistoryEndpoint(unittest.TestCase):

    def setUp(self):
        import api.server as srv
        self.srv = srv
        # Swap _store with a fresh one for isolation
        self._orig_store = srv._store
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
        self.dbf = f.name
        srv._store = SnapshotStore(self.dbf)

    def tearDown(self):
        self.srv._store = self._orig_store
        _safe_unlink(self.dbf)

    def _store(self):
        return self.srv._store

    def test_TZ17_missing_module_returns_400(self):
        code, _ = self.srv.handle_anti_pattern_score_history(None)
        self.assertEqual(code, 400)

    def test_TZ18_unknown_module_returns_404(self):
        code, _ = self.srv.handle_anti_pattern_score_history("nobody")
        self.assertEqual(code, 404)

    def test_TZ19_history_basic_shape(self):
        self._store().insert(_mv(commit="c1", ts=10.0))
        self._store().insert(_mv(commit="c2", ts=20.0))
        code, data = self.srv.handle_anti_pattern_score_history("demo.mod")
        self.assertEqual(code, 200)
        self.assertEqual(data["n_samples"], 2)
        self.assertEqual(data["n_valid"], 2)
        self.assertEqual([s["commit"] for s in data["samples"]], ["c1", "c2"])

    def test_TZ20_history_includes_null_aps_samples_by_default(self):
        self._store().insert(_mv(commit="c1", ts=10.0))
        with sqlite3.connect(self.dbf) as c:
            c.execute("UPDATE snapshots SET aps_score = NULL")
        code, data = self.srv.handle_anti_pattern_score_history("demo.mod")
        self.assertIsNone(data["samples"][0]["aps"])
        self.assertEqual(data["n_valid"], 0)

    def test_TZ21_history_samples_are_floats(self):
        self._store().insert(_mv(commit="c1", ts=10.0, taint=2))
        code, data = self.srv.handle_anti_pattern_score_history("demo.mod")
        self.assertIsInstance(data["samples"][0]["aps"], float)

    def test_TZ22_history_window_parameter(self):
        for i in range(5):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i)))
        code, data = self.srv.handle_anti_pattern_score_history(
            "demo.mod", window=3,
        )
        self.assertEqual(data["n_samples"], 3)

    def test_TZ23_history_response_carries_module_id(self):
        self._store().insert(_mv(commit="c1", ts=10.0))
        code, data = self.srv.handle_anti_pattern_score_history("demo.mod")
        self.assertEqual(data["module_id"], "demo.mod")

    def test_TZ24_history_degrading_trend_visible(self):
        for i in range(3):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i), taint=i * 2))
        code, data = self.srv.handle_anti_pattern_score_history("demo.mod")
        scores = [s["aps"] for s in data["samples"]]
        self.assertGreater(scores[0], scores[2])


# ══════════════════════════════════════════════════════════════════════════════
# TZ25-TZ30 — /anti-pattern-score/trend endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestTrendEndpoint(unittest.TestCase):

    def setUp(self):
        import api.server as srv
        self.srv = srv
        self._orig_store = srv._store
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
        self.dbf = f.name
        srv._store = SnapshotStore(self.dbf)

    def tearDown(self):
        self.srv._store = self._orig_store
        _safe_unlink(self.dbf)

    def _store(self):
        return self.srv._store

    def test_TZ25_trend_requires_min_samples(self):
        self._store().insert(_mv(commit="c1", ts=10.0))
        self._store().insert(_mv(commit="c2", ts=20.0))
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        self.assertEqual(code, 200)
        self.assertEqual(data["verdict"], "INSUFFICIENT")
        self.assertEqual(data["min_required"], 4)

    def test_TZ26_trend_detects_degradation(self):
        # Monotonic taint increase → APS decreases → slope < 0
        for i in range(8):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i), taint=i))
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        self.assertEqual(code, 200)
        self.assertLess(data["slope"], 0.0)
        self.assertIn(data["verdict"], ("DEGRADING", "DEGRADING_PERSISTENT"))

    def test_TZ27_trend_detects_improvement(self):
        # Decreasing taint → APS increases → slope > 0
        for i in range(8):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i),
                                     taint=max(0, 8 - i)))
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        self.assertEqual(code, 200)
        self.assertGreater(data["slope"], 0.0)
        self.assertEqual(data["verdict"], "IMPROVING")

    def test_TZ28_trend_stable_when_constant(self):
        for i in range(6):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i), taint=1))
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        self.assertEqual(data["verdict"], "STABLE")
        self.assertAlmostEqual(data["slope"], 0.0, places=4)

    def test_TZ29_trend_response_fields_present(self):
        for i in range(6):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i), taint=i))
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        for key in ("module_id", "n_samples", "latest_aps", "latest_rating",
                    "slope", "slope_pct", "forecast_next", "hurst", "verdict"):
            self.assertIn(key, data)
        # Hurst bounded
        self.assertGreaterEqual(data["hurst"], 0.0)
        self.assertLessEqual(data["hurst"], 1.0)

    def test_TZ30_trend_skips_null_samples(self):
        # Insert 6 valid then 2 NULL — trend must use only the 6 valid ones
        for i in range(6):
            self._store().insert(_mv(commit=f"c{i}", ts=float(i), taint=i))
        for i in range(2):
            self._store().insert(_mv(commit=f"null{i}", ts=float(100 + i)))
        with sqlite3.connect(self.dbf) as c:
            c.execute("UPDATE snapshots SET aps_score = NULL "
                      "WHERE commit_hash LIKE 'null%'")
        code, data = self.srv.handle_anti_pattern_score_trend("demo.mod")
        self.assertEqual(code, 200)
        self.assertEqual(data["n_samples"], 6)   # NULLs excluded from analysis


if __name__ == "__main__":
    unittest.main()
