import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from apex_r.contracts import GateStatus
from apex_r.data import (
    AffinityMeasurement,
    ContentAddressedStore,
    FrozenSplit,
    LicenseClass,
    SourceDefinition,
    SplitPartition,
    build_local_snapshot,
    write_snapshot_manifest,
)
from apex_r.db import ApexDatabase
from apex_r.modules.validation import (
    CriterionOperator,
    EvidenceLayer,
    MetricCriterion,
    MetricObservation,
    ValidationProtocol,
    evaluate_protocol,
    promotion_readiness,
)


def internal_protocol() -> ValidationProtocol:
    return ValidationProtocol(
        protocol_id="B-M2-INTERNAL",
        version="1.0",
        module_id="M2",
        layer=EvidenceLayer.INTERNAL,
        dataset_snapshot_id="snapshot-1",
        split_id="split-1",
        criteria=(
            MetricCriterion("rmse_pk", CriterionOperator.LTE, 1.5),
            MetricCriterion("spearman", CriterionOperator.GTE, 0.7),
        ),
        minimum_sample_size=50,
        preregistered=True,
    )


class ValidationTests(unittest.TestCase):
    def test_protocol_passes_only_when_all_criteria_and_sample_size_pass(self):
        outcome = evaluate_protocol(
            internal_protocol(),
            {
                "rmse_pk": MetricObservation(1.2, 60),
                "spearman": MetricObservation(0.76, 60),
            },
        )
        self.assertEqual(outcome.gate.status, GateStatus.PASSED)
        self.assertEqual(outcome.candidate_evidence_label, "INTERNALLY_VALIDATED")

        failed = evaluate_protocol(
            internal_protocol(),
            {
                "rmse_pk": MetricObservation(1.2, 40),
                "spearman": MetricObservation(0.76, 60),
            },
        )
        self.assertEqual(failed.gate.status, GateStatus.FAILED)

    def test_unregistered_protocol_is_blocked(self):
        protocol = ValidationProtocol(
            **{**internal_protocol().__dict__, "preregistered": False}
        )
        outcome = evaluate_protocol(protocol, {})
        self.assertEqual(outcome.gate.status, GateStatus.BLOCKED)

    def test_synthetic_data_cannot_claim_external_validation(self):
        with self.assertRaises(ValueError):
            ValidationProtocol(
                protocol_id="bad",
                version="1",
                module_id="M2",
                layer=EvidenceLayer.EXTERNAL,
                dataset_snapshot_id="s",
                split_id="x",
                criteria=(MetricCriterion("rmse", CriterionOperator.LTE, 1.5),),
                minimum_sample_size=10,
                preregistered=True,
                external_set_locked=True,
                synthetic_data=True,
            )
        with self.assertRaises(ValueError):
            ValidationProtocol(
                protocol_id="bad-internal",
                version="1",
                module_id="M2",
                layer=EvidenceLayer.INTERNAL,
                dataset_snapshot_id="s",
                split_id="x",
                criteria=(MetricCriterion("rmse", CriterionOperator.LTE, 1.5),),
                minimum_sample_size=10,
                preregistered=True,
                synthetic_data=True,
            )

    def test_promotion_is_never_automatic(self):
        outcome = evaluate_protocol(
            internal_protocol(),
            {"rmse_pk": MetricObservation(1.0, 60), "spearman": MetricObservation(0.8, 60)},
        )
        gate = promotion_readiness([outcome], [EvidenceLayer.INTERNAL])
        self.assertEqual(gate.status, GateStatus.NEEDS_REVIEW)


class DataTests(unittest.TestCase):
    def test_snapshot_store_manifest_and_database_are_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw.csv"
            raw.write_text("compound,target,value\na,b,1\n", encoding="utf-8")
            source = SourceDefinition(
                "local-test", "Local test", "1", "MIT", LicenseClass.OPEN, redistribution_allowed=True
            )
            snapshot = build_local_snapshot(
                source,
                [raw],
                store=ContentAddressedStore(root / "store"),
                retrieved_at="2026-07-17T00:00:00+00:00",
            )
            self.assertEqual(len(snapshot.snapshot_id), 64)
            self.assertTrue(Path(snapshot.files[0].stored_locator).is_file())
            manifest = root / "manifest.json"
            write_snapshot_manifest(snapshot, manifest)
            write_snapshot_manifest(snapshot, manifest)

            database = ApexDatabase(root / "apex.sqlite3")
            database.initialize()
            database.record_snapshot(snapshot)
            with closing(database.connect()) as connection:
                self.assertEqual(connection.execute("SELECT count(*) FROM source_snapshot").fetchone()[0], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("UPDATE source_snapshot SET status='REJECTED'")

    def test_affinity_preserves_endpoint_type_and_normalizes_unit(self):
        record = AffinityMeasurement("r1", "s1", "src1", "c1", "t1", "Kd", "=", 10, "nM")
        self.assertAlmostEqual(record.value_molar, 1e-8)
        with self.assertRaises(ValueError):
            AffinityMeasurement("r2", "s1", "src2", "c1", "t1", "mixed", "=", 1, "nM")

    def test_split_detects_group_leakage_and_accepts_locked_external(self):
        leaking = FrozenSplit(
            "split-bad",
            "snapshot",
            {SplitPartition.TRAIN: ("r1",), SplitPartition.EXTERNAL_TEST: ("r2",)},
            {"r1": "same-scaffold", "r2": "same-scaffold"},
            True,
            "scaffold",
        )
        self.assertEqual(leaking.validation_gate().status, GateStatus.FAILED)
        valid = FrozenSplit(
            "split-good",
            "snapshot",
            {SplitPartition.TRAIN: ("r1",), SplitPartition.EXTERNAL_TEST: ("r2",)},
            {"r1": "g1", "r2": "g2"},
            True,
            "scaffold",
        )
        self.assertEqual(valid.validation_gate().status, GateStatus.PASSED)


if __name__ == "__main__":
    unittest.main()
