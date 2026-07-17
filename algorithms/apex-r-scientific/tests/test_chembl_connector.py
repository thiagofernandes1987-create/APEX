import json
import tempfile
import unittest
from pathlib import Path

from apex_r.connectors.chembl import (
    ChemblActivityQuery,
    _validate_api_url,
    audit_activity_pages,
    fetch_activity_pages,
    normalize_activity_page,
)
from apex_r.contracts import GateStatus


def page(next_url=None):
    return {
        "activities": [
            {
                "activity_id": 123,
                "molecule_chembl_id": "CHEMBL25",
                "target_chembl_id": "CHEMBL204",
                "standard_type": "Kd",
                "standard_relation": "=",
                "standard_value": "10",
                "standard_units": "nM",
                "assay_chembl_id": "CHEMBL-A1",
                "document_chembl_id": "CHEMBL-D1",
                "pchembl_value": "8.0",
                "canonical_smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
            }
        ],
        "page_meta": {"next": next_url},
    }


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.payload


class ChemblConnectorTests(unittest.TestCase):
    def test_query_is_typed_and_url_encoded(self):
        query = ChemblActivityQuery("CHEMBL204", "Kd", "nM", 100)
        self.assertIn("activity.json", query.url())
        self.assertIn("standard_type=Kd", query.url())
        with self.assertRaises(ValueError):
            ChemblActivityQuery("CHEMBL204", "mixed")

    def test_pagination_rejects_untrusted_host(self):
        with self.assertRaises(ValueError):
            _validate_api_url("https://example.com/chembl/api/data/activity.json")

    def test_normalization_preserves_endpoint_and_provenance(self):
        records = normalize_activity_page(page(), "snapshot-1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].endpoint, "Kd")
        self.assertEqual(records[0].source_record_id, "123")
        self.assertAlmostEqual(records[0].value_molar, 1e-8)

    def test_fetch_writes_raw_page_with_injected_transport(self):
        def opener(_request, timeout):
            self.assertEqual(timeout, 5)
            return FakeResponse(page())

        with tempfile.TemporaryDirectory() as directory:
            paths = fetch_activity_pages(
                ChemblActivityQuery("CHEMBL204", "Kd", limit=10),
                Path(directory),
                max_records=10,
                timeout_seconds=5,
                opener=opener,
            )
            self.assertEqual(len(paths), 1)
            self.assertTrue(paths[0].is_file())

    def test_audit_accepts_complete_typed_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.json"
            payload = page()
            payload["page_meta"]["total_count"] = 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_activity_pages(
                [path], ChemblActivityQuery("CHEMBL204", "Kd", limit=10)
            )
            self.assertEqual(audit.gate.status, GateStatus.PASSED)
            self.assertEqual(audit.unique_activities, 1)
            self.assertEqual(audit.records_with_structure, 1)

    def test_audit_rejects_partial_or_duplicate_acquisition(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "page.json"
            payload = page("/chembl/api/data/activity.json?offset=1")
            payload["activities"].append(dict(payload["activities"][0]))
            payload["page_meta"]["total_count"] = 3
            path.write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_activity_pages(
                [path], ChemblActivityQuery("CHEMBL204", "Kd", limit=10)
            )
            self.assertEqual(audit.gate.status, GateStatus.FAILED)
            self.assertTrue(any("duplicados" in error for error in audit.gate.errors))

    def test_fetch_resolves_relative_official_pagination(self):
        calls = []

        def opener(request, timeout):
            calls.append(request.full_url)
            if len(calls) == 1:
                return FakeResponse(page("/chembl/api/data/activity.json?offset=1"))
            return FakeResponse(page())

        with tempfile.TemporaryDirectory() as directory:
            paths = fetch_activity_pages(
                ChemblActivityQuery("CHEMBL204", "Kd", limit=1),
                Path(directory),
                max_records=2,
                opener=opener,
            )
            self.assertEqual(len(paths), 2)
            self.assertEqual(calls[1], "https://www.ebi.ac.uk/chembl/api/data/activity.json?offset=1")


if __name__ == "__main__":
    unittest.main()
