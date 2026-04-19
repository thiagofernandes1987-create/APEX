"""
UCO-Sensor — Runner de todos os testes em ordem.
Roda: frequency-engine (88) → Marco 1 (27) → Marco 2 (30) → Marco 3 (16)
"""
import sys
import subprocess
import time
from pathlib import Path

ROOT    = Path(__file__).resolve().parent
ENGINE  = ROOT / "frequency-engine"
SENSOR  = ROOT / "sensor-api"
TESTS   = SENSOR / "tests"

VALIDATION = SENSOR / "validation"

SUITES = [
    ("FrequencyEngine (88)",  [sys.executable, str(ENGINE / "run_tests.py")],                     ENGINE),
    ("Marco 1 (27)",          [sys.executable, str(TESTS / "test_marco1.py")],                    SENSOR),
    ("Marco 2 (30)",          [sys.executable, str(TESTS / "test_marco2.py")],                    SENSOR),
    ("Marco 3 (16)",          [sys.executable, str(TESTS / "test_marco3.py")],                    SENSOR),
    ("Marco C — Real Code",   [sys.executable, str(VALIDATION / "validate_real_repos.py")],      SENSOR),
]

results = []
t_global = time.perf_counter()

print(f"\n{'═'*65}")
print("  UCO-Sensor — Full Test Suite")
print(f"{'═'*65}\n")

for name, cmd, cwd in SUITES:
    print(f"  ▶  {name}")
    print(f"{'─'*65}")
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

print(f"{'═'*65}")
print(f"  Suites: {passed}/{len(results)} passaram  |  tempo total: {total_elapsed:.1f}s")
for name, ok, elapsed in results:
    icon = "✓" if ok else "✗"
    print(f"  {icon}  {name:<30}  {elapsed:.1f}s")
print(f"{'═'*65}\n")

sys.exit(0 if failed == 0 else 1)
