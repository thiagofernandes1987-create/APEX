"""
test_marco_m33.py — Sprint B: Repo meta-score + APS outliers (30 tests TS01-TS30)
==================================================================================
Validates the Sprint B deliverable (v3.2.6 — single repo-level number):

  TS01-TS06  Rating ladder + dataclass invariants + empty repo
  TS07-TS14  compute_repo_meta_score logic (weighted mean, LOC weighting, RED penalty)
  TS15-TS20  compute_aps_outliers (k-σ threshold, edge cases, ranking)
  TS21-TS25  repo_meta_score_history (time-series, downsampling, empty)
  TS26-TS30  REST endpoints /repo/{health-score,aps-outliers,health-history}
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
from governance.repo_meta_score import (
    RepoMetaScore, APSOutlier,
    compute_repo_meta_score, compute_aps_outliers,
    repo_meta_score_history, _rate,
)


def _mv(module="m.mod", commit="c1", ts=1.0, h=2.0, loc=100,
        taint=0, locks=0):
    mv = MetricVector(module, commit, ts, hamiltonian=h, cyclomatic_complexity=10)
    mv.lines_of_code = loc
    mv.flow          = FlowVector(taint_path_count=taint,
                                  injection_surface=taint * 0.2)
    mv.thread_safety = ThreadSafetyVector(lock_missing_count=locks)
    return mv


def _fresh_store():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False); f.close()
    return SnapshotStore(f.name), f.name


# ══════════════════════════════════════════════════════════════════════════════
# TS01-TS06 — Rating + dataclass + empty repo
# ══════════════════════════════════════════════════════════════════════════════

class TestBasics(unittest.TestCase):

    def test_TS01_rate_ladder(self):
        self.assertEqual(_rate(95.0), "A")
        self.assertEqual(_rate(85.0), "B")
        self.assertEqual(_rate(70.0), "C")
        self.assertEqual(_rate(50.0), "D")
        self.assertEqual(_rate(30.0), "E")

    def test_TS02_dataclass_to_dict_keys(self):
        meta = RepoMetaScore(
            score=80.0, rating="B", n_modules=10, n_modules_valid=8,
            raw_score=85.0, weighted_aps=85.0,
            mean_aps=80.0, median_aps=82.0,
            penalty_red=5, n_red=1, n_amber=2,
        )
        d = meta.to_dict()
        for k in ("score", "rating", "n_modules", "n_modules_valid",
                  "raw_score", "weighted_aps", "mean_aps", "median_aps",
                  "penalty_red", "n_red", "n_amber"):
            self.assertIn(k, d)

    def test_TS03_empty_repo_yields_a_grade(self):
        store, dbf = _fresh_store()
        try:
            meta = compute_repo_meta_score(store)
            self.assertEqual(meta.rating, "A")
            self.assertEqual(meta.n_modules_valid, 0)
        finally:
            os.unlink(dbf)

    def test_TS04_repo_with_only_clean_modules_scores_high(self):
        store, dbf = _fresh_store()
        try:
            for i in range(3):
                # Inserts with no extended vectors → APS=100 each
                store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
            meta = compute_repo_meta_score(store)
            self.assertGreaterEqual(meta.score, 90.0)
            self.assertEqual(meta.rating, "A")
        finally:
            os.unlink(dbf)

    def test_TS05_outlier_dataclass_to_dict(self):
        o = APSOutlier(module_id="m", aps=20.0, z_score=-2.5,
                       threshold=-2.0, deviation=-50.0)
        d = o.to_dict()
        for k in ("module_id", "aps", "z_score", "threshold", "deviation"):
            self.assertIn(k, d)

    def test_TS06_rating_boundaries(self):
        self.assertEqual(_rate(90.0), "A")
        self.assertEqual(_rate(89.99), "B")
        self.assertEqual(_rate(60.0), "C")
        self.assertEqual(_rate(40.0), "D")
        self.assertEqual(_rate(39.99), "E")


# ══════════════════════════════════════════════════════════════════════════════
# TS07-TS14 — compute_repo_meta_score logic
# ══════════════════════════════════════════════════════════════════════════════

class TestRepoMetaScore(unittest.TestCase):

    def test_TS07_score_falls_with_taint(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="bad", commit="c1", h=1.0,
                             taint=5, locks=3))
            store.insert(_mv(module="good", commit="c1", h=1.0))
            meta = compute_repo_meta_score(store)
            self.assertLess(meta.weighted_aps, 100.0)
            self.assertEqual(meta.n_modules_valid, 2)
        finally:
            os.unlink(dbf)

    def test_TS08_loc_weighting_favours_big_modules(self):
        store, dbf = _fresh_store()
        try:
            # Tiny clean module + huge dirty module
            store.insert(_mv(module="tiny", commit="c1", h=1.0, loc=10))
            store.insert(_mv(module="huge", commit="c1", h=1.0, loc=10000,
                             taint=5))
            meta = compute_repo_meta_score(store)
            # weighted_aps should be PULLED DOWN by the huge dirty module
            # despite tiny being perfect (100)
            self.assertLess(meta.weighted_aps, meta.mean_aps)
        finally:
            os.unlink(dbf)

    def test_TS09_uses_latest_aps_per_module(self):
        store, dbf = _fresh_store()
        try:
            # Two snapshots for one module — only the latest must count
            store.insert(_mv(module="m", commit="c1", ts=1.0, h=1.0, taint=5))
            store.insert(_mv(module="m", commit="c2", ts=2.0, h=1.0))
            meta = compute_repo_meta_score(store)
            # Latest is clean → meta should be high
            self.assertAlmostEqual(meta.weighted_aps, 100.0)
        finally:
            os.unlink(dbf)

    def test_TS10_n_modules_counts_all(self):
        store, dbf = _fresh_store()
        try:
            for i in range(5):
                store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
            self.assertEqual(compute_repo_meta_score(store).n_modules, 5)
        finally:
            os.unlink(dbf)

    def test_TS11_score_bounded_to_0_100(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="m", commit="c1", h=1.0,
                             taint=99, locks=99))
            meta = compute_repo_meta_score(store)
            self.assertGreaterEqual(meta.score, 0.0)
            self.assertLessEqual(meta.score, 100.0)
        finally:
            os.unlink(dbf)

    def test_TS12_red_penalty_drags_score_down(self):
        """A RED-tier compound alert must reduce the repo score."""
        store, dbf = _fresh_store()
        try:
            # Sustained degradation on this module → likely RED in Sprint A
            for i in range(12):
                store.insert(_mv(
                    module="hot", commit=f"c{i:02d}", ts=float(i),
                    h=1.0 + 0.5 * (1.3 ** i), taint=i, locks=i // 3,
                ))
            meta = compute_repo_meta_score(store)
            # If RED hit, the score must be strictly below the raw score
            if meta.n_red > 0:
                self.assertLess(meta.score, meta.raw_score)
                self.assertEqual(meta.penalty_red, 5 * meta.n_red)
        finally:
            os.unlink(dbf)

    def test_TS13_modules_without_aps_skipped(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="m", commit="c1", h=1.0))
            import sqlite3
            with sqlite3.connect(dbf) as c:
                c.execute("UPDATE snapshots SET aps_score = NULL")
            meta = compute_repo_meta_score(store)
            self.assertEqual(meta.n_modules_valid, 0)
        finally:
            os.unlink(dbf)

    def test_TS14_median_independent_of_loc(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="tiny", commit="c1", h=1.0, loc=10))
            store.insert(_mv(module="huge", commit="c1", h=1.0, loc=10000))
            meta = compute_repo_meta_score(store)
            # Both clean → median should be 100 regardless of LOC
            self.assertAlmostEqual(meta.median_aps, 100.0)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TS15-TS20 — compute_aps_outliers
# ══════════════════════════════════════════════════════════════════════════════

class TestOutliers(unittest.TestCase):

    def test_TS15_too_few_modules_returns_empty(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(module="m1", commit="c1", h=1.0))
            store.insert(_mv(module="m2", commit="c1", h=1.0))
            self.assertEqual(compute_aps_outliers(store), [])
        finally:
            os.unlink(dbf)

    def test_TS16_identical_apses_no_outliers(self):
        """When σ = 0, the function returns []."""
        store, dbf = _fresh_store()
        try:
            for i in range(5):
                store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
            self.assertEqual(compute_aps_outliers(store), [])
        finally:
            os.unlink(dbf)

    def test_TS17_low_aps_module_flagged(self):
        store, dbf = _fresh_store()
        try:
            # Four clean + one heavily degraded
            for i in range(4):
                store.insert(_mv(module=f"clean{i}", commit="c1", h=1.0))
            store.insert(_mv(module="bad", commit="c1", h=1.0,
                             taint=5, locks=5))
            outliers = compute_aps_outliers(store, k=1.0)
            ids = {o.module_id for o in outliers}
            self.assertIn("bad", ids)
        finally:
            os.unlink(dbf)

    def test_TS18_zero_or_negative_k_returns_empty(self):
        store, dbf = _fresh_store()
        try:
            for i in range(5):
                store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
            self.assertEqual(compute_aps_outliers(store, k=0.0), [])
            self.assertEqual(compute_aps_outliers(store, k=-1.0), [])
        finally:
            os.unlink(dbf)

    def test_TS19_outliers_sorted_worst_first(self):
        store, dbf = _fresh_store()
        try:
            for i in range(4):
                store.insert(_mv(module=f"clean{i}", commit="c1", h=1.0))
            store.insert(_mv(module="bad1", commit="c1", h=1.0, taint=3))
            store.insert(_mv(module="bad2", commit="c1", h=1.0,
                             taint=5, locks=3))
            outliers = compute_aps_outliers(store, k=0.5)
            zs = [o.z_score for o in outliers]
            self.assertEqual(zs, sorted(zs))   # ascending = worst first
        finally:
            os.unlink(dbf)

    def test_TS20_outliers_only_below_mean(self):
        """Only negative-z outliers are reported."""
        store, dbf = _fresh_store()
        try:
            for i in range(4):
                store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
            store.insert(_mv(module="bad", commit="c1", h=1.0,
                             taint=5, locks=3))
            outliers = compute_aps_outliers(store, k=0.5)
            for o in outliers:
                self.assertLessEqual(o.z_score, 0.0)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TS21-TS25 — repo_meta_score_history
# ══════════════════════════════════════════════════════════════════════════════

class TestHistory(unittest.TestCase):

    def test_TS21_empty_store_returns_empty(self):
        store, dbf = _fresh_store()
        try:
            self.assertEqual(repo_meta_score_history(store), [])
        finally:
            os.unlink(dbf)

    def test_TS22_history_chronological_ascending(self):
        store, dbf = _fresh_store()
        try:
            for i in range(6):
                store.insert(_mv(module="m", commit=f"c{i}",
                                 ts=float(i), h=1.0 + i * 0.2))
            ts_seen = [r["timestamp"] for r in repo_meta_score_history(store)]
            self.assertEqual(ts_seen, sorted(ts_seen))
        finally:
            os.unlink(dbf)

    def test_TS23_each_record_has_canonical_keys(self):
        store, dbf = _fresh_store()
        try:
            for i in range(4):
                store.insert(_mv(module="m", commit=f"c{i}",
                                 ts=float(i), h=1.0))
            for rec in repo_meta_score_history(store):
                for k in ("timestamp", "score", "n_modules_valid"):
                    self.assertIn(k, rec)
        finally:
            os.unlink(dbf)

    def test_TS24_step_downsamples(self):
        store, dbf = _fresh_store()
        try:
            for i in range(10):
                store.insert(_mv(module="m", commit=f"c{i}",
                                 ts=float(i), h=1.0))
            full = repo_meta_score_history(store, step=1)
            half = repo_meta_score_history(store, step=2)
            self.assertLess(len(half), len(full))
        finally:
            os.unlink(dbf)

    def test_TS25_multi_module_each_point_aggregates(self):
        store, dbf = _fresh_store()
        try:
            for i in range(4):
                store.insert(_mv(module="a", commit=f"a{i}",
                                 ts=float(i), h=1.0))
                store.insert(_mv(module="b", commit=f"b{i}",
                                 ts=float(i + 0.5), h=1.0))
            for rec in repo_meta_score_history(store):
                self.assertGreaterEqual(rec["n_modules_valid"], 1)
                self.assertLessEqual(rec["n_modules_valid"], 2)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TS26-TS30 — REST endpoints
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

    def test_TS26_health_score_endpoint_shape(self):
        for i in range(3):
            self.srv._store.insert(_mv(module=f"m{i}", commit="c1", h=1.0))
        code, data = self.srv.handle_repo_health_score()
        self.assertEqual(code, 200)
        for key in ("score", "rating", "n_modules", "n_modules_valid",
                    "raw_score", "weighted_aps", "mean_aps", "median_aps",
                    "penalty_red", "n_red", "n_amber"):
            self.assertIn(key, data)

    def test_TS27_aps_outliers_endpoint_shape(self):
        for i in range(4):
            self.srv._store.insert(_mv(module=f"clean{i}", commit="c1", h=1.0))
        self.srv._store.insert(_mv(module="bad", commit="c1", h=1.0,
                                   taint=5, locks=3))
        code, data = self.srv.handle_repo_aps_outliers(k=1.0)
        self.assertEqual(code, 200)
        for key in ("k", "window", "n_modules", "n_outliers", "outliers"):
            self.assertIn(key, data)

    def test_TS28_health_history_endpoint_shape(self):
        for i in range(3):
            self.srv._store.insert(_mv(module="m", commit=f"c{i}",
                                       ts=float(i), h=1.0))
        code, data = self.srv.handle_repo_health_history()
        self.assertEqual(code, 200)
        for key in ("n_points", "window", "step", "samples"):
            self.assertIn(key, data)

    def test_TS29_outliers_with_custom_k(self):
        for i in range(4):
            self.srv._store.insert(_mv(module=f"clean{i}", commit="c1", h=1.0))
        self.srv._store.insert(_mv(module="bad", commit="c1", h=1.0,
                                   taint=5, locks=3))
        code, data = self.srv.handle_repo_aps_outliers(k=0.5)
        self.assertEqual(data["k"], 0.5)
        self.assertGreater(data["n_outliers"], 0)

    def test_TS30_health_history_step_param(self):
        for i in range(8):
            self.srv._store.insert(_mv(module="m", commit=f"c{i}",
                                       ts=float(i), h=1.0))
        code, full = self.srv.handle_repo_health_history(step=1)
        code, half = self.srv.handle_repo_health_history(step=2)
        self.assertLess(half["n_points"], full["n_points"])


if __name__ == "__main__":
    unittest.main()
