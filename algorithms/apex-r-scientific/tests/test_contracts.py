import unittest

from apex_r.contracts import GateEnvelope, GateStatus


class GateEnvelopeTests(unittest.TestCase):
    def test_failed_gate_requires_explicit_error(self):
        with self.assertRaises(ValueError):
            GateEnvelope("G", "M2", GateStatus.FAILED, "Falhou")

    def test_passed_gate_rejects_errors(self):
        with self.assertRaises(ValueError):
            GateEnvelope("G", "M2", GateStatus.PASSED, "Passou", errors=("erro",))

    def test_serialization_uses_status_string(self):
        gate = GateEnvelope.passed("G", "M2", "Passou", metrics={"x": 1})
        self.assertEqual(gate.to_dict()["status"], "PASSED")


if __name__ == "__main__":
    unittest.main()

