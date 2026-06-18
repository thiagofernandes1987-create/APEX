"""
test_marco_m31.py — LEAP 4: Predictor/Trend persisted (30 tests TF01-TF30)
==========================================================================
Validates the LEAP 4 deliverable (v3.2.4 — predictor outputs persisted at
insert time so forecast accuracy becomes measurable over commits):

  TF01-TF06  Schema + migration + columns exist (REAL type, all 4 fields)
  TF07-TF14  _compute_forecast logic at insert time + insufficient-history guard
  TF15-TF22  get_predictor_history helper + forecast_error backfill + LEAP 1/2 regression
  TF23-TF26  /predictor/history endpoint
  TF27-TF30  /predictor/accuracy endpoint (verdict ladder)
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
from metrics.extended_vectors import FlowVector


def _mv(module="m.mod", commit="c1", ts=1.0, h=2.0, cc=8):
    return MetricVector(module, commit, ts, hamiltonian=h, cyclomatic_complexity=cc)


def _fresh_store():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
    return SnapshotStore(f.name), f.name


def _degrading_series(store, module="m.mod", n=8):
    """Monotonic H growth — predictor will detect persistent degradation."""
    hams = [1.0 + 0.5 * (1.2 ** i) for i in range(n)]
    for i, h in enumerate(hams):
        store.insert(_mv(module=module, commit=f"c{i:02d}",
                         ts=float(i), h=h, cc=10 + i))
    return hams


# ══════════════════════════════════════════════════════════════════════════════
# TF01-TF06 — Schema invariants
# ══════════════════════════════════════════════════════════════════════════════

class TestSchema(unittest.TestCase):

    def test_TF01_four_predictor_columns_present(self):
        store, dbf = _fresh_store()
        try:
            with sqlite3.connect(dbf) as c:
                cols = [r[1] for r in c.execute("PRAGMA table_info(snapshots)")]
            for col in ("predictor_hurst", "predictor_slope_pct",
                        "predictor_forecast_next", "predictor_confidence"):
                self.assertIn(col, cols)
        finally:
            os.unlink(dbf)

    def test_TF02_predictor_columns_are_REAL(self):
        store, dbf = _fresh_store()
        try:
            with sqlite3.connect(dbf) as c:
                info = {r[1]: r[2] for r in c.execute(
                    "PRAGMA table_info(snapshots)") if r[1].startswith("predictor_")}
            for col, typ in info.items():
                self.assertEqual(typ.upper(), "REAL", f"{col} type {typ}")
        finally:
            os.unlink(dbf)

    def test_TF03_default_null_keeps_legacy_rows_valid(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())
            with sqlite3.connect(dbf) as c:
                row = c.execute(
                    "SELECT predictor_hurst, predictor_slope_pct, "
                    "predictor_forecast_next, predictor_confidence "
                    "FROM snapshots").fetchone()
            # Single snapshot → predictor cannot fire → all NULL
            self.assertEqual(row, (None, None, None, None))
        finally:
            os.unlink(dbf)

    def test_TF04_migration_idempotent_on_reopen(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())
            # Reopen — _migrate_m70 must be idempotent (no exception)
            store2 = SnapshotStore(dbf)
            store2.insert(_mv(commit="c2", ts=2.0))
            self.assertEqual(len(store2.get_history("m.mod")), 2)
        finally:
            os.unlink(dbf)

    def test_TF05_leap1_extended_vectors_still_round_trip(self):
        store, dbf = _fresh_store()
        try:
            mv = _mv()
            mv.flow = FlowVector(taint_path_count=3)
            store.insert(mv)
            mv2 = store.get_history("m.mod")[0]
            self.assertIsNotNone(getattr(mv2, "flow", None))
            self.assertEqual(mv2.flow.taint_path_count, 3)
        finally:
            os.unlink(dbf)

    def test_TF06_leap2_aps_score_still_persists(self):
        store, dbf = _fresh_store()
        try:
            mv = _mv()
            mv.flow = FlowVector(taint_path_count=2)
            store.insert(mv)
            mv2 = store.get_history("m.mod")[0]
            self.assertIsNotNone(mv2.aps_score)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TF07-TF14 — Insert-time forecast computation
# ══════════════════════════════════════════════════════════════════════════════

class TestInsertForecast(unittest.TestCase):

    def test_TF07_first_three_rows_have_null_predictor(self):
        store, dbf = _fresh_store()
        try:
            for i in range(3):
                store.insert(_mv(commit=f"c{i}", ts=float(i),
                                 h=1.0 + i))
            for mv in store.get_history("m.mod"):
                self.assertIsNone(mv.predictor_hurst)
                self.assertIsNone(mv.predictor_forecast_next)
        finally:
            os.unlink(dbf)

    def test_TF08_fifth_row_onwards_has_forecast(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=6)
            mvs = store.get_history("m.mod")
            # rows 0-3: insufficient history → NULL; rows 4+: have forecast
            self.assertIsNone(mvs[0].predictor_hurst)
            self.assertIsNone(mvs[3].predictor_hurst)
            self.assertIsNotNone(mvs[4].predictor_hurst)
            self.assertIsNotNone(mvs[4].predictor_forecast_next)
        finally:
            os.unlink(dbf)

    def test_TF09_forecast_in_reasonable_bounds(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=8)
            mvs = store.get_history("m.mod")
            forecasts = [m.predictor_forecast_next for m in mvs
                         if m.predictor_forecast_next is not None]
            # Forecasts should be non-negative for monotonic positive series
            for f in forecasts:
                self.assertGreater(f, 0.0)
        finally:
            os.unlink(dbf)

    def test_TF10_hurst_in_unit_interval(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=8)
            for mv in store.get_history("m.mod"):
                if mv.predictor_hurst is not None:
                    self.assertGreaterEqual(mv.predictor_hurst, 0.0)
                    self.assertLessEqual(mv.predictor_hurst, 1.0)
        finally:
            os.unlink(dbf)

    def test_TF11_confidence_in_unit_interval(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=8)
            for mv in store.get_history("m.mod"):
                if mv.predictor_confidence is not None:
                    self.assertGreaterEqual(mv.predictor_confidence, 0.0)
                    self.assertLessEqual(mv.predictor_confidence, 1.0)
        finally:
            os.unlink(dbf)

    def test_TF12_insert_with_no_module_id_still_works(self):
        """Defensive guard: missing module_id must not crash insert."""
        store, dbf = _fresh_store()
        try:
            mv = _mv(module="")
            store.insert(mv)   # must not raise
            with sqlite3.connect(dbf) as c:
                n = c.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
            self.assertEqual(n, 1)
        finally:
            os.unlink(dbf)

    def test_TF13_slope_pct_persists(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=6)
            mvs = store.get_history("m.mod")
            slope_pcts = [m.predictor_slope_pct for m in mvs
                          if m.predictor_slope_pct is not None]
            self.assertGreater(len(slope_pcts), 0)
            # For degrading series, slope_pct should be > 0 (H rising)
            for s in slope_pcts:
                self.assertGreater(s, 0.0)
        finally:
            os.unlink(dbf)

    def test_TF14_cross_module_predictor_isolation(self):
        store, dbf = _fresh_store()
        try:
            # Module A: 6 degrading snapshots
            _degrading_series(store, module="a.mod", n=6)
            # Module B: only 2 snapshots — its predictor cannot fire
            store.insert(_mv(module="b.mod", commit="x1", ts=0.0))
            store.insert(_mv(module="b.mod", commit="x2", ts=1.0))
            a_hurst_some = any(
                m.predictor_hurst is not None for m in store.get_history("a.mod")
            )
            b_hurst_none = all(
                m.predictor_hurst is None for m in store.get_history("b.mod")
            )
            self.assertTrue(a_hurst_some)
            self.assertTrue(b_hurst_none)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TF15-TF22 — get_predictor_history helper + forecast_error
# ══════════════════════════════════════════════════════════════════════════════

class TestPredictorHistory(unittest.TestCase):

    def test_TF15_empty_module_returns_empty(self):
        store, dbf = _fresh_store()
        try:
            self.assertEqual(store.get_predictor_history("nobody"), [])
        finally:
            os.unlink(dbf)

    def test_TF16_records_ordered_ascending(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=6)
            ts = [r["timestamp"] for r in store.get_predictor_history("m.mod")]
            self.assertEqual(ts, sorted(ts))
        finally:
            os.unlink(dbf)

    def test_TF17_forecast_error_backfilled_correctly(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=8)
            rows = store.get_predictor_history("m.mod")
            for i in range(len(rows) - 1):
                fcst = rows[i]["forecast_next"]
                if fcst is not None:
                    expected = round(rows[i + 1]["hamiltonian"] - fcst, 6)
                    self.assertEqual(rows[i]["forecast_error"], expected)
        finally:
            os.unlink(dbf)

    def test_TF18_last_row_has_no_forecast_error(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=6)
            last = store.get_predictor_history("m.mod")[-1]
            self.assertIsNone(last["forecast_error"])
        finally:
            os.unlink(dbf)

    def test_TF19_record_shape_keys(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=5)
            rec = store.get_predictor_history("m.mod")[0]
            for key in ("commit", "timestamp", "hamiltonian", "hurst",
                        "slope_pct", "forecast_next", "confidence",
                        "forecast_error"):
                self.assertIn(key, rec)
        finally:
            os.unlink(dbf)

    def test_TF20_legacy_null_predictor_propagates(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="c1", ts=1.0))
            with sqlite3.connect(dbf) as c:
                c.execute("UPDATE snapshots SET predictor_hurst = NULL, "
                          "predictor_forecast_next = NULL")
            rec = store.get_predictor_history("m.mod")[0]
            self.assertIsNone(rec["hurst"])
            self.assertIsNone(rec["forecast_next"])
        finally:
            os.unlink(dbf)

    def test_TF21_forecast_error_uses_next_actual(self):
        """Direct semantics check: error = actual_next - forecast_at_row."""
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=6)
            rows = store.get_predictor_history("m.mod")
            firing_idx = next(
                i for i, r in enumerate(rows) if r["forecast_next"] is not None
            )
            actual_next = rows[firing_idx + 1]["hamiltonian"]
            forecast    = rows[firing_idx]["forecast_next"]
            self.assertAlmostEqual(
                rows[firing_idx]["forecast_error"],
                actual_next - forecast, places=4,
            )
        finally:
            os.unlink(dbf)

    def test_TF22_window_parameter_limits_rows(self):
        store, dbf = _fresh_store()
        try:
            _degrading_series(store, n=10)
            rows = store.get_predictor_history("m.mod", window=4)
            self.assertEqual(len(rows), 4)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TF23-TF26 — /predictor/history endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestHistoryEndpoint(unittest.TestCase):

    def setUp(self):
        import api.server as srv
        self.srv = srv
        self._orig_store = srv._store
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
        self.dbf = f.name
        srv._store = SnapshotStore(self.dbf)

    def tearDown(self):
        self.srv._store = self._orig_store
        os.unlink(self.dbf)

    def test_TF23_missing_module_400(self):
        code, _ = self.srv.handle_predictor_history(None)
        self.assertEqual(code, 400)

    def test_TF24_unknown_module_404(self):
        code, _ = self.srv.handle_predictor_history("nobody")
        self.assertEqual(code, 404)

    def test_TF25_history_shape(self):
        _degrading_series(self.srv._store, n=6)
        code, data = self.srv.handle_predictor_history("m.mod")
        self.assertEqual(code, 200)
        self.assertEqual(data["module_id"], "m.mod")
        self.assertEqual(data["n_samples"], 6)
        self.assertGreaterEqual(data["n_forecasts"], 1)
        self.assertIn("samples", data)
        self.assertEqual(len(data["samples"]), 6)

    def test_TF26_history_contains_forecast_error_field(self):
        _degrading_series(self.srv._store, n=6)
        code, data = self.srv.handle_predictor_history("m.mod")
        for sample in data["samples"]:
            self.assertIn("forecast_error", sample)


# ══════════════════════════════════════════════════════════════════════════════
# TF27-TF30 — /predictor/accuracy endpoint
# ══════════════════════════════════════════════════════════════════════════════

class TestAccuracyEndpoint(unittest.TestCase):

    def setUp(self):
        import api.server as srv
        self.srv = srv
        self._orig_store = srv._store
        f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
        self.dbf = f.name
        srv._store = SnapshotStore(self.dbf)

    def tearDown(self):
        self.srv._store = self._orig_store
        os.unlink(self.dbf)

    def test_TF27_insufficient_when_too_few_evaluable_pairs(self):
        # Only 2 snapshots — no forecast pairs at all
        self.srv._store.insert(_mv(commit="c1", ts=1.0))
        self.srv._store.insert(_mv(commit="c2", ts=2.0))
        code, data = self.srv.handle_predictor_accuracy("m.mod")
        self.assertEqual(code, 200)
        self.assertEqual(data["verdict"], "INSUFFICIENT")
        self.assertEqual(data["min_required"], 3)

    def test_TF28_accuracy_summary_fields(self):
        _degrading_series(self.srv._store, n=10)
        code, data = self.srv.handle_predictor_accuracy("m.mod")
        self.assertEqual(code, 200)
        for key in ("mae", "rmse", "bias", "mae_relative",
                    "mean_hamiltonian", "verdict", "n_evaluated"):
            self.assertIn(key, data)
        self.assertGreaterEqual(data["mae"], 0.0)
        self.assertGreaterEqual(data["rmse"], 0.0)

    def test_TF29_verdict_is_one_of_canonical_values(self):
        _degrading_series(self.srv._store, n=10)
        code, data = self.srv.handle_predictor_accuracy("m.mod")
        self.assertIn(data["verdict"],
                      ("ACCURATE", "BIASED_UP", "BIASED_DOWN", "NOISY",
                       "INSUFFICIENT"))

    def test_TF30_accuracy_404_on_unknown_module(self):
        code, _ = self.srv.handle_predictor_accuracy("nobody")
        self.assertEqual(code, 404)


if __name__ == "__main__":
    unittest.main()
