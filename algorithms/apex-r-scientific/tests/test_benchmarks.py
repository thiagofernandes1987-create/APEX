import tempfile
import unittest
from pathlib import Path

from apex_r.benchmarks import (
    list_benchmarks,
    run_benchmark,
    run_verification_suite,
    write_benchmark_report,
)
from apex_r.contracts import GateStatus


class BenchmarkTests(unittest.TestCase):
    def test_verification_benchmarks_pass(self):
        for benchmark_id in (
            "B-VERIFY-CORE",
            "B-VERIFY-M11",
            "B-VERIFY-M2-CAL",
            "B-VERIFY-CHEMBL-QC",
        ):
            with self.subTest(benchmark_id=benchmark_id):
                self.assertEqual(run_benchmark(benchmark_id).gate.status, GateStatus.PASSED)

    def test_real_benchmarks_are_registered_and_blocked(self):
        ids = {definition.benchmark_id for definition in list_benchmarks()}
        self.assertTrue({"B-M2", "B-CAUSAL", "B-M4", "B-M6", "B-M8", "B-PCL"}.issubset(ids))
        self.assertEqual(run_benchmark("B-M2").gate.status, GateStatus.BLOCKED)

    def test_verification_report_is_immutable(self):
        report = run_verification_suite(run_id="fixed-run")
        self.assertEqual(report["status"], "PASSED")
        self.assertEqual(len(report["outcomes"]), 4)
        self.assertTrue(all(item["run_id"] == "fixed-run" for item in report["outcomes"]))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "benchmark.json"
            write_benchmark_report(report, destination)
            self.assertTrue(destination.is_file())
            with self.assertRaises(FileExistsError):
                write_benchmark_report(report, destination)


if __name__ == "__main__":
    unittest.main()
