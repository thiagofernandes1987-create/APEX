import unittest

from apex_r.contracts import GateStatus
from apex_r.data import FrozenSplit, SplitPartition
from apex_r.modules.molecular_calibration import (
    CalibrationPoint,
    evaluate_molecular_calibration,
    fit_molecular_calibration,
)


def points():
    return [
        CalibrationPoint(f"r{i}", f"g{i}", "Kd", float(i), 2.0 + 3.0 * i)
        for i in range(1, 7)
    ]


def split():
    return FrozenSplit(
        "m2-split",
        "snapshot-1",
        {
            SplitPartition.TRAIN: ("r1", "r2", "r3", "r4"),
            SplitPartition.INTERNAL_TEST: ("r5", "r6"),
        },
        {f"r{i}": f"g{i}" for i in range(1, 7)},
        False,
        "scaffold",
    )


class MolecularCalibrationTests(unittest.TestCase):
    def test_fit_uses_train_and_internal_evaluation_is_exact(self):
        result = fit_molecular_calibration(points(), split(), model_id="candidate-1")
        self.assertEqual(result.gate.status, GateStatus.PASSED)
        self.assertIsNotNone(result.model)
        model = result.model
        assert model is not None
        self.assertAlmostEqual(model.fit.intercept, 2.0)
        self.assertAlmostEqual(model.fit.slope, 3.0)
        evaluation = evaluate_molecular_calibration(
            model, points(), split(), SplitPartition.INTERNAL_TEST
        )
        self.assertEqual(evaluation.gate.status, GateStatus.PASSED)
        self.assertAlmostEqual(evaluation.metrics["rmse_pk"], 0.0)
        self.assertAlmostEqual(evaluation.metrics["spearman"], 1.0)

    def test_external_partition_requires_matching_m11_protocol(self):
        external_split = FrozenSplit(
            "external-split",
            "snapshot-1",
            {
                SplitPartition.TRAIN: ("r1", "r2", "r3", "r4"),
                SplitPartition.EXTERNAL_TEST: ("r5", "r6"),
            },
            {f"r{i}": f"g{i}" for i in range(1, 7)},
            True,
            "scaffold",
        )
        result = fit_molecular_calibration(points(), external_split, model_id="candidate-1")
        assert result.model is not None
        evaluation = evaluate_molecular_calibration(
            result.model, points(), external_split, SplitPartition.EXTERNAL_TEST
        )
        self.assertEqual(evaluation.gate.status, GateStatus.BLOCKED)

    def test_mixed_endpoints_are_blocked(self):
        mixed = points()
        mixed[2] = CalibrationPoint("r3", "g3", "Ki", 3.0, 11.0)
        result = fit_molecular_calibration(mixed, split(), model_id="bad")
        self.assertEqual(result.gate.status, GateStatus.BLOCKED)
        self.assertIsNone(result.model)


if __name__ == "__main__":
    unittest.main()

