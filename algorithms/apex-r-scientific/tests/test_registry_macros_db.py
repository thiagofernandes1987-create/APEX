import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from apex_r.contracts import GateEnvelope, GateStatus, ModuleContext
from apex_r.db import ApexDatabase
from apex_r.macros import execute_macro, get_macro, list_macros, readiness_gate
from apex_r.registry import get_module, list_modules


class RegistryAndMacroTests(unittest.TestCase):
    def test_canonical_modules_are_registered(self):
        ids = {module.module_id for module in list_modules()}
        self.assertTrue({"M0", "M1", "M2", "M2.5", "M11", "PCL"}.issubset(ids))
        self.assertEqual(get_module("m2").module_id, "M2")

    def test_macro_catalog_and_honest_blocking(self):
        ids = {macro.macro_id for macro in list_macros()}
        self.assertEqual(
            ids,
            {
                "coefficient_validation",
                "full_pipeline",
                "molecular_to_pbpk",
                "preclinical_translation",
            },
        )
        gate = readiness_gate(get_macro("full_pipeline"))
        self.assertEqual(gate.status, GateStatus.BLOCKED)
        self.assertIn("Módulos não ativos", gate.errors[0])

    def test_macro_executes_active_prefix_then_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "source.txt"
            source.write_text("evidence", encoding="utf-8")
            inputs = {
                "M1": {"paths": ["source.txt"]},
                "M2": {"kd_molar": 1e-9},
                "M0": {"design_matrix": [[1, 0], [1, 1], [1, 2]]},
                "M4": {
                    "amounts": [100.0, 20.0],
                    "transfer_rates": [[0, 0.2], [0.1, 0]],
                },
            }
            context = ModuleContext(workspace, database_path=workspace / "run.sqlite3")
            gates = execute_macro(get_macro("molecular_to_pbpk"), context, inputs)
            self.assertEqual([gate.module_id for gate in gates], ["M1", "M2", "M0", "M4", "M11"])
            self.assertTrue(all(gate.status is GateStatus.PASSED for gate in gates[:4]))
            self.assertEqual(gates[-1].status, GateStatus.BLOCKED)
            self.assertEqual(len(ApexDatabase(context.database_path).list_gate_events()), 5)


class DatabaseTests(unittest.TestCase):
    def test_initialization_recording_and_append_only_trigger(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "apex.sqlite3"
            database = ApexDatabase(path)
            database.initialize()
            event_id = database.record_gate(GateEnvelope.passed("G", "M2", "ok"))
            self.assertEqual(event_id, 1)
            self.assertEqual(len(database.list_gate_events()), 1)
            database.define_coefficient("M2.beta", "Inclinação de calibração", "1", "M2", "OLS")
            estimate_id = database.record_coefficient_estimate(
                "M2.beta", "run-1", 1.25, "OLS", "abc123", uncertainty=0.1
            )
            self.assertEqual(estimate_id, 1)
            with closing(database.connect()) as connection:
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute("UPDATE gate_event SET summary = 'alterado' WHERE event_id = 1")
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "UPDATE coefficient_estimate SET value = 2 WHERE estimate_id = 1"
                    )


if __name__ == "__main__":
    unittest.main()
