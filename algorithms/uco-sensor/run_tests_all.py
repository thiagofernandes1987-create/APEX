"""
UCO-Sensor — canonical full regression runner.

Single source of truth for local/CI validation:
  1) FrequencyEngine dedicated regression suite
  2) ALL sensor-api pytest tests (test_marco*, calibration, future tests)
  3) Real-code validation harness

Do not enumerate individual Marcos here: that silently went stale as the
project grew from M3 to M105+.
"""
import sys
import subprocess
import time
from pathlib import Path

ROOT       = Path(__file__).resolve().parent
ENGINE     = ROOT / "frequency-engine"
SENSOR     = ROOT / "sensor-api"
VALIDATION = SENSOR / "validation"

SUITES = [
    (
        "FrequencyEngine",
        [sys.executable, str(ENGINE / "run_tests.py")],
        ENGINE,
    ),
    (
        "Sensor API — full pytest",
        [sys.executable, "-m", "pytest", "tests", "-q"],
        SENSOR,
    ),
    (
        "Real-code validation",
        [sys.executable, str(VALIDATION / "validate_real_repos.py")],
        SENSOR,
    ),
]

results = []
t_global = time.perf_counter()

print(f"\n{'═'*72}")
print("  UCO-Sensor — Canonical Full Regression")
print(f"{'═'*72}\n")

for name, cmd, cwd in SUITES:
    print(f"  ▶  {name}")
    print(f"{'─'*72}")
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd))
    elapsed = time.perf_counter() - t0
    ok = proc.returncode == 0
    results.append((name, ok, elapsed))
    status = "\033[92m✓ PASS\033[0m" if ok else "\033[91m✗ FAIL\033[0m"
    print(f"\n  {status}  {name}  ({elapsed:.1f}s)\n")

total_elapsed = time.perf_counter() - t_global
passed = sum(1 for _, ok, _ in results if ok)
failed = len(results) - passed

print(f"{'═'*72}")
print(f"  Suites: {passed}/{len(results)} passed | total: {total_elapsed:.1f}s")
for name, ok, elapsed in results:
    icon = "✓" if ok else "✗"
    print(f"  {icon}  {name:<34} {elapsed:.1f}s")
print(f"{'═'*72}\n")

sys.exit(0 if failed == 0 else 1)
