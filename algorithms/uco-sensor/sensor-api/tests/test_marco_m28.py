"""
test_marco_m28.py — LEAP 1 Persistence Sprint (30 tests TP01-TP30)
==================================================================
Validates the SnapshotStore round-trip for nine vectors previously dropped
on every scan since M7.2 (v3.2.1 — Persistence Sprint):

  TP01-TP05  Single-vector round-trip (security/velocity/flow/reliability/maintainability)
  TP06-TP09  Single-vector round-trip (performance/architecture/test_quality/thread_safety)
  TP10-TP15  Schema invariants (DDL columns, migration idempotent, NULL on missing mv attrs)
  TP16-TP20  Backward-compat (old row missing column, partial vectors, get_history shape)
  TP21-TP25  APS history (now actually computable post-persistence)
  TP26-TP30  Multi-snapshot ordering + cross-module isolation + serializer no-op cases
"""
from __future__ import annotations

import json
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
    SecurityVector, VelocityVector, FlowVector, ReliabilityVector,
    MaintainabilityVector, PerformanceVector, ArchitectureVector,
    TestQualityVector, ThreadSafetyVector,
)
from metrics.anti_pattern_score import aps_from_metric_vector


def _mv(module_id="demo.mod", commit="c1", ts=1000.0, **attrs):
    mv = MetricVector(module_id, commit, ts, hamiltonian=5.0,
                      cyclomatic_complexity=10)
    for k, v in attrs.items():
        setattr(mv, k, v)
    return mv


def _fresh_store():
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return SnapshotStore(f.name), f.name


# ══════════════════════════════════════════════════════════════════════════════
# TP01-TP09 — single-vector round-trip across all nine LEAP-1 vectors
# ══════════════════════════════════════════════════════════════════════════════

class TestSingleVectorRoundTrip(unittest.TestCase):

    def _roundtrip(self, attr, vector):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(**{attr: vector}))
            mv2 = store.get_history("demo.mod")[0]
            v2 = getattr(mv2, attr, None)
            self.assertIsNotNone(v2, f"{attr} did not round-trip")
            self.assertEqual(type(v2).__name__, type(vector).__name__)
            self.assertEqual(v2.to_dict(), vector.to_dict())
        finally:
            os.unlink(dbf)

    def test_TP01_security_roundtrip(self):
        self._roundtrip("security",
                        SecurityVector(sast_critical=1, sast_high=2, sca_vulnerable_deps=3))

    def test_TP02_velocity_roundtrip(self):
        self._roundtrip("velocity",
                        VelocityVector(hamiltonian_velocity=0.5,
                                       degradation_hurst=0.62, n_snapshots=12))

    def test_TP03_flow_roundtrip(self):
        self._roundtrip("flow",
                        FlowVector(taint_path_count=2, injection_surface=0.45,
                                   taint_source_count=4))

    def test_TP04_reliability_roundtrip(self):
        self._roundtrip("reliability",
                        ReliabilityVector(bare_except_count=3,
                                          resource_leak_risk=1, regex_redos_risk=2))

    def test_TP05_maintainability_roundtrip(self):
        self._roundtrip("maintainability",
                        MaintainabilityVector(missing_docstring_ratio=0.6,
                                              long_function_ratio=0.2,
                                              cognitive_cc_hotspot=15))

    def test_TP06_performance_roundtrip(self):
        self._roundtrip("performance",
                        PerformanceVector(n_plus_one_risk=2,
                                          quadratic_nested_loop_count=3,
                                          string_concat_in_loop=1))

    def test_TP07_architecture_roundtrip(self):
        self._roundtrip("architecture",
                        ArchitectureVector(fan_in=5, fan_out=8,
                                           coupling_between_objects=7,
                                           lack_of_cohesion=0.42))

    def test_TP08_test_quality_roundtrip(self):
        self._roundtrip("test_quality",
                        TestQualityVector(n_test_functions=10,
                                          assertion_density=2.5,
                                          dead_test_count=1,
                                          flaky_test_risk=2))

    def test_TP09_thread_safety_roundtrip(self):
        self._roundtrip("thread_safety",
                        ThreadSafetyVector(lock_missing_count=2,
                                           daemon_thread_risk=1,
                                           asyncio_blocking_call=3))


# ══════════════════════════════════════════════════════════════════════════════
# TP10-TP15 — schema invariants + migration idempotence
# ══════════════════════════════════════════════════════════════════════════════

class TestSchemaAndMigration(unittest.TestCase):

    def test_TP10_new_column_exists_in_schema(self):
        store, dbf = _fresh_store()
        try:
            with sqlite3.connect(dbf) as c:
                cols = [r[1] for r in c.execute("PRAGMA table_info(snapshots)")]
            self.assertIn("extended_vectors_v2_json", cols)
            self.assertIn("extended_vectors_json",    cols)  # M7.0 still there
            self.assertIn("advanced_vector_json",     cols)
            self.assertIn("diagnostic_vector_json",   cols)
        finally:
            os.unlink(dbf)

    def test_TP11_migration_idempotent_on_existing_db(self):
        store, dbf = _fresh_store()
        try:
            # second open() must not raise on re-running ALTER TABLE
            store2 = SnapshotStore(dbf)
            store2.insert(_mv())
            self.assertEqual(len(store2.get_history("demo.mod")), 1)
        finally:
            os.unlink(dbf)

    def test_TP12_mv_with_no_extended_v2_attrs_persists_null(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())   # no extra attrs at all
            with sqlite3.connect(dbf) as c:
                row = c.execute(
                    "SELECT extended_vectors_v2_json FROM snapshots"
                ).fetchone()
            self.assertIsNone(row[0])
        finally:
            os.unlink(dbf)

    def test_TP13_v2_column_is_json_object_when_present(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(flow=FlowVector(taint_path_count=1)))
            with sqlite3.connect(dbf) as c:
                row = c.execute(
                    "SELECT extended_vectors_v2_json FROM snapshots"
                ).fetchone()
            payload = json.loads(row[0])
            self.assertIn("flow", payload)
            self.assertEqual(payload["flow"]["taint_path_count"], 1)
        finally:
            os.unlink(dbf)

    def test_TP14_attrs_tuple_is_complete_and_ordered(self):
        # LEAP 1 contract: exactly these nine attrs, in canonical order.
        self.assertEqual(
            SnapshotStore._EXTENDED_V2_ATTRS,
            ("security", "velocity", "flow", "reliability", "maintainability",
             "performance", "architecture", "test_quality", "thread_safety"),
        )

    def test_TP15_existing_m70_columns_still_round_trip(self):
        """Regression guard: LEAP 1 must not regress M7.0 persistence."""
        from metrics.extended_vectors import HalsteadVector, AdvancedVector
        store, dbf = _fresh_store()
        try:
            mv = _mv()
            mv.halstead = HalsteadVector(volume=100.0, difficulty=4.0)
            mv.advanced = AdvancedVector(cognitive_cc_total=20,
                                         sqale_debt_minutes=120)
            store.insert(mv)
            mv2 = store.get_history("demo.mod")[0]
            self.assertEqual(mv2.halstead.volume, 100.0)
            self.assertEqual(mv2.advanced.sqale_debt_minutes, 120)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TP16-TP20 — backward compatibility
# ══════════════════════════════════════════════════════════════════════════════

class TestBackwardCompat(unittest.TestCase):

    def test_TP16_partial_payload_round_trips_only_present_keys(self):
        store, dbf = _fresh_store()
        try:
            mv = _mv(flow=FlowVector(taint_path_count=1),
                     performance=PerformanceVector(n_plus_one_risk=3))
            # other 7 attrs intentionally absent
            store.insert(mv)
            mv2 = store.get_history("demo.mod")[0]
            self.assertIsNotNone(getattr(mv2, "flow", None))
            self.assertIsNotNone(getattr(mv2, "performance", None))
            # Vectors NOT attached must remain absent / None after round-trip
            self.assertIsNone(getattr(mv2, "security", None))
            self.assertIsNone(getattr(mv2, "test_quality", None))
        finally:
            os.unlink(dbf)

    def test_TP17_legacy_row_null_column_loads_cleanly(self):
        """A row written by old code (NULL column) must deserialize without error."""
        store, dbf = _fresh_store()
        try:
            store.insert(_mv())
            # Force the column to NULL even if insert ever changes default
            with sqlite3.connect(dbf) as c:
                c.execute("UPDATE snapshots SET extended_vectors_v2_json = NULL")
            mv2 = store.get_history("demo.mod")[0]
            self.assertIsNone(getattr(mv2, "flow", None))
            self.assertEqual(mv2.hamiltonian, 5.0)
        finally:
            os.unlink(dbf)

    def test_TP18_get_history_preserves_chronological_order(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(commit="c1", ts=100.0,
                             flow=FlowVector(taint_path_count=1)))
            store.insert(_mv(commit="c2", ts=200.0,
                             flow=FlowVector(taint_path_count=2)))
            store.insert(_mv(commit="c3", ts=150.0,
                             flow=FlowVector(taint_path_count=3)))
            hist = store.get_history("demo.mod")
            self.assertEqual([m.timestamp for m in hist], [100.0, 150.0, 200.0])
            self.assertEqual([m.flow.taint_path_count for m in hist], [1, 3, 2])
        finally:
            os.unlink(dbf)

    def test_TP19_cross_module_isolation(self):
        store, dbf = _fresh_store()
        try:
            store.insert(_mv("mod.a", flow=FlowVector(taint_path_count=1)))
            store.insert(_mv("mod.b", flow=FlowVector(taint_path_count=99)))
            self.assertEqual(store.get_history("mod.a")[0].flow.taint_path_count, 1)
            self.assertEqual(store.get_history("mod.b")[0].flow.taint_path_count, 99)
        finally:
            os.unlink(dbf)

    def test_TP20_corrupt_one_vector_does_not_lose_the_rest(self):
        """If one vector's serialized form is bad, the others must still load."""
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(flow=FlowVector(taint_path_count=1),
                             reliability=ReliabilityVector(bare_except_count=2)))
            with sqlite3.connect(dbf) as c:
                payload = json.loads(c.execute(
                    "SELECT extended_vectors_v2_json FROM snapshots").fetchone()[0])
                # Inject a deliberately wrong payload for ``flow``
                payload["flow"] = {"this_key_does_not_exist": True}
                c.execute("UPDATE snapshots SET extended_vectors_v2_json = ?",
                          (json.dumps(payload),))
            mv2 = store.get_history("demo.mod")[0]
            # reliability survives; flow is best-effort (still constructible with defaults)
            self.assertIsNotNone(getattr(mv2, "reliability", None))
            self.assertEqual(mv2.reliability.bare_except_count, 2)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TP21-TP25 — APS history (the headline LEAP-1 dividend)
# ══════════════════════════════════════════════════════════════════════════════

class TestAPSHistoryNowPossible(unittest.TestCase):

    def _full_mv(self, commit, ts, taint=0, locks=0):
        mv = _mv(commit=commit, ts=ts)
        mv.flow          = FlowVector(taint_path_count=taint, injection_surface=taint * 0.2)
        mv.reliability   = ReliabilityVector()
        mv.maintainability = MaintainabilityVector()
        mv.performance   = PerformanceVector()
        mv.architecture  = ArchitectureVector()
        mv.test_quality  = TestQualityVector()
        mv.thread_safety = ThreadSafetyVector(lock_missing_count=locks)
        mv.security      = SecurityVector()
        return mv

    def test_TP21_aps_identical_before_and_after_persistence(self):
        store, dbf = _fresh_store()
        try:
            mv = self._full_mv("c1", 100.0, taint=2, locks=1)
            aps1 = aps_from_metric_vector(mv)
            store.insert(mv)
            mv2 = store.get_history("demo.mod")[0]
            aps2 = aps_from_metric_vector(mv2)
            self.assertEqual(aps1["aps"], aps2["aps"])
            self.assertEqual(aps1["rating"], aps2["rating"])
        finally:
            os.unlink(dbf)

    def test_TP22_aps_history_trend_now_computable(self):
        """Three snapshots → three persisted APS scores in chronological order."""
        store, dbf = _fresh_store()
        try:
            store.insert(self._full_mv("c1", 100.0, taint=0, locks=0))   # clean
            store.insert(self._full_mv("c2", 200.0, taint=2, locks=1))   # regressed
            store.insert(self._full_mv("c3", 300.0, taint=4, locks=2))   # worse
            scores = [aps_from_metric_vector(m)["aps"] for m in store.get_history("demo.mod")]
            self.assertEqual(len(scores), 3)
            # Monotonically degrading APS (more taint/locks → lower score)
            self.assertGreater(scores[0], scores[1])
            self.assertGreater(scores[1], scores[2])
        finally:
            os.unlink(dbf)

    def test_TP23_clean_snapshot_yields_100(self):
        store, dbf = _fresh_store()
        try:
            store.insert(self._full_mv("c1", 100.0, taint=0, locks=0))
            mv2 = store.get_history("demo.mod")[0]
            self.assertAlmostEqual(aps_from_metric_vector(mv2)["aps"], 100.0)
        finally:
            os.unlink(dbf)

    def test_TP24_aps_components_match_after_persistence(self):
        store, dbf = _fresh_store()
        try:
            mv = self._full_mv("c1", 100.0, taint=3, locks=1)
            store.insert(mv)
            mv2 = store.get_history("demo.mod")[0]
            comp1 = aps_from_metric_vector(mv)["components"]
            comp2 = aps_from_metric_vector(mv2)["components"]
            self.assertEqual(comp1, comp2)
        finally:
            os.unlink(dbf)

    def test_TP25_thread_safety_signal_survives(self):
        """Persistence specifically unlocks ThreadSafety contribution to APS."""
        store, dbf = _fresh_store()
        try:
            mv = self._full_mv("c1", 100.0, taint=0, locks=5)
            store.insert(mv)
            mv2 = store.get_history("demo.mod")[0]
            self.assertEqual(mv2.thread_safety.lock_missing_count, 5)
            # lock_missing has weight 10 in APS → noticeable score impact
            self.assertLess(aps_from_metric_vector(mv2)["aps"], 95.0)
        finally:
            os.unlink(dbf)


# ══════════════════════════════════════════════════════════════════════════════
# TP26-TP30 — serializer/deserializer edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestSerializerEdges(unittest.TestCase):

    def test_TP26_serialize_extended_v2_empty_returns_none(self):
        self.assertIsNone(SnapshotStore._serialize_extended_v2(_mv()))

    def test_TP27_serialize_extended_v2_partial_keys_only(self):
        mv = _mv(flow=FlowVector(taint_path_count=2))
        out = SnapshotStore._serialize_extended_v2(mv)
        self.assertIsNotNone(out)
        payload = json.loads(out)
        self.assertEqual(set(payload.keys()), {"flow"})

    def test_TP28_security_vector_from_dict_now_exists(self):
        # LEAP 1 added from_dict to SecurityVector / VelocityVector
        sv = SecurityVector(sast_critical=2)
        sv2 = SecurityVector.from_dict(sv.to_dict())
        self.assertEqual(sv2.sast_critical, 2)

    def test_TP29_velocity_vector_from_dict_now_exists(self):
        vv = VelocityVector(hamiltonian_velocity=0.42)
        vv2 = VelocityVector.from_dict(vv.to_dict())
        self.assertAlmostEqual(vv2.hamiltonian_velocity, 0.42)

    def test_TP30_unknown_fields_in_payload_ignored(self):
        # Robust against schema evolution: extra keys must not crash from_dict
        store, dbf = _fresh_store()
        try:
            store.insert(_mv(flow=FlowVector(taint_path_count=1)))
            with sqlite3.connect(dbf) as c:
                payload = json.loads(c.execute(
                    "SELECT extended_vectors_v2_json FROM snapshots").fetchone()[0])
                payload["flow"]["future_field_xyz"] = "ignored"
                c.execute("UPDATE snapshots SET extended_vectors_v2_json = ?",
                          (json.dumps(payload),))
            mv2 = store.get_history("demo.mod")[0]
            self.assertEqual(mv2.flow.taint_path_count, 1)
        finally:
            os.unlink(dbf)


if __name__ == "__main__":
    unittest.main()
