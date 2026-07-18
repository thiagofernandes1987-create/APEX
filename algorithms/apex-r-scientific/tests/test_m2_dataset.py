import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from apex_r.contracts import GateStatus
from apex_r.m2_dataset import build_chembl_m2_dataset, write_m2_dataset_build


RDKIT_AVAILABLE = importlib.util.find_spec("rdkit") is not None


@unittest.skipUnless(RDKIT_AVAILABLE, "RDKit é um extra opcional")
class M2DatasetTests(unittest.TestCase):
    def _page(self, path: Path) -> None:
        smiles = (
            "c1ccccc1",
            "Cc1ccccc1",
            "c1ccncc1",
            "c1ccc2ccccc2c1",
            "C1CCCCC1",
            "c1ccoc1",
        )
        activities = []
        for index, structure in enumerate(smiles, start=1):
            activities.append(
                {
                    "activity_id": index,
                    "molecule_chembl_id": f"CHEMBL{index}",
                    "molecule_pref_name": None,
                    "target_chembl_id": "CHEMBL251",
                    "target_organism": "Homo sapiens",
                    "standard_type": "Ki",
                    "standard_relation": "=",
                    "standard_value": str(index * 10),
                    "standard_units": "nM",
                    "canonical_smiles": structure,
                    "assay_chembl_id": f"A{index}",
                    "document_chembl_id": f"D{index}",
                    "assay_type": "B",
                    "potential_duplicate": 0,
                    "data_validity_comment": None,
                }
            )
        path.write_text(
            json.dumps(
                {"activities": activities, "page_meta": {"total_count": 6, "next": None}}
            ),
            encoding="utf-8",
        )

    def test_build_normalizes_pk_and_prevents_scaffold_leakage(self):
        from rdkit import rdBase

        with tempfile.TemporaryDirectory() as directory:
            page = Path(directory) / "page.json"
            self._page(page)
            build = build_chembl_m2_dataset(
                [page],
                source_snapshot_id="snapshot-real",
                target_chembl_id="CHEMBL251",
                endpoint="Ki",
                unit="nM",
                split_salt="fixed-v1",
                expected_rdkit_version=str(rdBase.rdkitVersion),
            )
            self.assertEqual(build.gate.status, GateStatus.PASSED)
            self.assertIsNotNone(build.dataset)
            self.assertIsNotNone(build.split)
            self.assertEqual(build.split.validation_gate().status, GateStatus.PASSED)
            self.assertAlmostEqual(build.dataset["records"][0]["p_activity"], 8.0)

    def test_build_is_version_locked_and_outputs_are_immutable(self):
        from rdkit import rdBase

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / "page.json"
            self._page(page)
            blocked = build_chembl_m2_dataset(
                [page],
                source_snapshot_id="snapshot-real",
                target_chembl_id="CHEMBL251",
                endpoint="Ki",
                unit="nM",
                split_salt="fixed-v1",
                expected_rdkit_version="0.0.0",
            )
            self.assertEqual(blocked.gate.status, GateStatus.BLOCKED)
            build = build_chembl_m2_dataset(
                [page],
                source_snapshot_id="snapshot-real",
                target_chembl_id="CHEMBL251",
                endpoint="Ki",
                unit="nM",
                split_salt="fixed-v1",
                expected_rdkit_version=str(rdBase.rdkitVersion),
            )
            dataset_path = root / "dataset.json"
            split_path = root / "split.json"
            write_m2_dataset_build(build, dataset_path, split_path)
            with self.assertRaises(FileExistsError):
                write_m2_dataset_build(build, dataset_path, split_path)


if __name__ == "__main__":
    unittest.main()
