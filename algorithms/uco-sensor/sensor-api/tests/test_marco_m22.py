"""
test_marco_m22.py — M7.7 ThreadSafetyVector + APS (30 tests, TT01–TT30)
========================================================================
Validates all components delivered in FASE 6b (M7.7 → v3.0.0):

  • ThreadSafetyResult / ThreadSafetyVector dataclass basics     (TT01–TT05)
  • global_shared_state_count + lock_missing_count               (TT06–TT10)
  • daemon_thread_risk + queue_unbounded_risk                    (TT11–TT15)
  • asyncio_blocking_call + shared_mutable_default               (TT16–TT20)
  • rating, repr, round-trip, REST endpoint                      (TT21–TT25)
  • Anti-Pattern Score (APS): table, compute, grade, endpoint    (TT26–TT30)
"""
from __future__ import annotations

import sys
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace

# ── Path setup (mirror pyproject testpaths) ──────────────────────────────────
_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from metrics.thread_safety_analyzer import (
    ThreadSafetyAnalyzer, ThreadSafetyResult,
)
from metrics.extended_vectors import ThreadSafetyVector
from metrics.anti_pattern_score import (
    compute_aps, rate_aps, aps_from_metric_vector,
    APS_COMPONENTS, APS_WEIGHT_SUM,
)


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _analyze(source: str, module_id: str = "") -> ThreadSafetyResult:
    return ThreadSafetyAnalyzer().analyze(textwrap.dedent(source), module_id=module_id)


def _vector(source: str, module_id: str = "") -> ThreadSafetyVector:
    return ThreadSafetyVector.from_analyzer(
        _analyze(source, module_id), module_id=module_id,
    )


# ══════════════════════════════════════════════════════════════════════════════
# TT01–TT05 — Dataclass basics
# ══════════════════════════════════════════════════════════════════════════════

class TestThreadSafetyDataclass(unittest.TestCase):

    def test_tt01_default_values(self):
        """TT01 — ThreadSafetyResult defaults are all zero."""
        r = ThreadSafetyResult()
        self.assertEqual(r.global_shared_state_count, 0)
        self.assertEqual(r.lock_missing_count, 0)
        self.assertEqual(r.daemon_thread_risk, 0)
        self.assertEqual(r.queue_unbounded_risk, 0)
        self.assertEqual(r.asyncio_blocking_call, 0)
        self.assertEqual(r.shared_mutable_default, 0)

    def test_tt02_vector_default_rating_is_A(self):
        """TT02 — Empty ThreadSafetyVector → rating ``A``."""
        v = ThreadSafetyVector()
        self.assertEqual(v.thread_safety_rating(), "A")
        self.assertEqual(v.total_issues, 0)

    def test_tt03_from_analyzer_maps_all_channels(self):
        """TT03 — from_analyzer() maps every channel verbatim."""
        r = ThreadSafetyResult(
            global_shared_state_count=1, lock_missing_count=2,
            daemon_thread_risk=3, queue_unbounded_risk=4,
            asyncio_blocking_call=5, shared_mutable_default=6,
        )
        v = ThreadSafetyVector.from_analyzer(r, module_id="m")
        self.assertEqual(v.global_shared_state_count, 1)
        self.assertEqual(v.shared_mutable_default, 6)
        self.assertEqual(v.module_id, "m")
        self.assertEqual(v.total_issues, 21)

    def test_tt04_to_dict_contains_rating_and_totals(self):
        """TT04 — to_dict() includes ``thread_safety_rating`` and ``total_issues``."""
        v = ThreadSafetyVector(lock_missing_count=2)
        d = v.to_dict()
        self.assertIn("thread_safety_rating", d)
        self.assertIn("total_issues", d)
        self.assertEqual(d["total_issues"], 2)

    def test_tt05_from_dict_round_trip(self):
        """TT05 — from_dict(to_dict()) round-trips every channel."""
        v = ThreadSafetyVector(
            global_shared_state_count=1, lock_missing_count=1,
            daemon_thread_risk=0, queue_unbounded_risk=1,
            asyncio_blocking_call=2, shared_mutable_default=0,
            module_id="x.y",
        )
        v2 = ThreadSafetyVector.from_dict(v.to_dict())
        self.assertEqual(v2.lock_missing_count, 1)
        self.assertEqual(v2.asyncio_blocking_call, 2)
        self.assertEqual(v2.module_id, "x.y")


# ══════════════════════════════════════════════════════════════════════════════
# TT06–TT10 — global_shared_state_count + lock_missing_count
# ══════════════════════════════════════════════════════════════════════════════

class TestGlobalSharedAndLockMissing(unittest.TestCase):

    def test_tt06_global_mutation_in_thread_target_is_flagged(self):
        """TT06 — ``global X`` mutated in Thread target → global_shared_state_count=1."""
        r = _analyze("""
            from threading import Thread
            counter = 0
            def worker():
                global counter
                counter += 1
            Thread(target=worker).start()
        """)
        self.assertEqual(r.global_shared_state_count, 1)
        self.assertEqual(r.lock_missing_count, 1)

    def test_tt07_lock_in_function_suppresses_lock_missing(self):
        """TT07 — Same pattern but with ``Lock()`` keeps lock_missing_count=0."""
        r = _analyze("""
            from threading import Thread, Lock
            counter = 0
            lock = Lock()
            def worker():
                global counter
                with lock:
                    counter += 1
            Thread(target=worker).start()
        """)
        self.assertEqual(r.global_shared_state_count, 1)
        self.assertEqual(r.lock_missing_count, 0)

    def test_tt08_function_not_used_as_thread_target_is_not_flagged(self):
        """TT08 — Mutating ``global`` in a non-Thread function is not flagged."""
        r = _analyze("""
            counter = 0
            def normal():
                global counter
                counter += 1
            normal()
        """)
        self.assertEqual(r.global_shared_state_count, 0)
        self.assertEqual(r.lock_missing_count, 0)

    def test_tt09_explicit_lock_acquire_release_counts_as_sync(self):
        """TT09 — ``lock.acquire()`` / ``lock.release()`` qualify as synchronisation."""
        r = _analyze("""
            from threading import Thread, Lock
            counter = 0
            lock = Lock()
            def worker():
                global counter
                lock.acquire()
                counter += 1
                lock.release()
            Thread(target=worker).start()
        """)
        self.assertEqual(r.lock_missing_count, 0)

    def test_tt10_process_target_also_counted(self):
        """TT10 — ``Process(target=fn)`` triggers the same detection as Thread."""
        r = _analyze("""
            from multiprocessing import Process
            counter = 0
            def worker():
                global counter
                counter += 1
            Process(target=worker).start()
        """)
        self.assertEqual(r.global_shared_state_count, 1)


# ══════════════════════════════════════════════════════════════════════════════
# TT11–TT15 — daemon_thread_risk + queue_unbounded_risk
# ══════════════════════════════════════════════════════════════════════════════

class TestDaemonAndQueue(unittest.TestCase):

    def test_tt11_daemon_thread_without_join_flagged(self):
        """TT11 — ``Thread(daemon=True)`` without any ``.join()`` in module → risk=1."""
        r = _analyze("""
            from threading import Thread
            def w(): pass
            Thread(target=w, daemon=True).start()
        """)
        self.assertEqual(r.daemon_thread_risk, 1)

    def test_tt12_join_anywhere_suppresses_daemon_risk(self):
        """TT12 — Any ``.join()`` in the module conservatively suppresses the flag."""
        r = _analyze("""
            from threading import Thread
            def w(): pass
            t = Thread(target=w, daemon=True)
            t.start()
            t.join()
        """)
        self.assertEqual(r.daemon_thread_risk, 0)

    def test_tt13_unbounded_queue_flagged(self):
        """TT13 — ``Queue()`` with no maxsize → queue_unbounded_risk=1."""
        r = _analyze("""
            from queue import Queue
            q = Queue()
        """)
        self.assertEqual(r.queue_unbounded_risk, 1)

    def test_tt14_bounded_queue_not_flagged(self):
        """TT14 — ``Queue(maxsize=100)`` (kwarg) is not flagged."""
        r = _analyze("""
            from queue import Queue
            q = Queue(maxsize=100)
        """)
        self.assertEqual(r.queue_unbounded_risk, 0)

    def test_tt15_positional_maxsize_not_flagged(self):
        """TT15 — ``Queue(100)`` (positional) is also not flagged."""
        r = _analyze("""
            from queue import Queue
            q = Queue(100)
        """)
        self.assertEqual(r.queue_unbounded_risk, 0)


# ══════════════════════════════════════════════════════════════════════════════
# TT16–TT20 — asyncio_blocking_call + shared_mutable_default
# ══════════════════════════════════════════════════════════════════════════════

class TestAsyncioAndSharedCollections(unittest.TestCase):

    def test_tt16_time_sleep_in_async_function_flagged(self):
        """TT16 — ``time.sleep`` in ``async def`` → asyncio_blocking_call=1."""
        r = _analyze("""
            import time
            async def f():
                time.sleep(0.1)
                return 1
        """)
        self.assertEqual(r.asyncio_blocking_call, 1)

    def test_tt17_requests_get_in_async_function_flagged(self):
        """TT17 — ``requests.get`` in ``async def`` is a blocking call."""
        r = _analyze("""
            import requests
            async def fetch():
                return requests.get("https://api")
        """)
        self.assertEqual(r.asyncio_blocking_call, 1)

    def test_tt18_blocking_call_in_sync_function_not_flagged(self):
        """TT18 — ``time.sleep`` in a regular ``def`` is fine."""
        r = _analyze("""
            import time
            def f():
                time.sleep(0.1)
        """)
        self.assertEqual(r.asyncio_blocking_call, 0)

    def test_tt19_module_collection_mutation_in_thread_target_flagged(self):
        """TT19 — Module-level list mutated in Thread target → shared_mutable_default=1."""
        r = _analyze("""
            from threading import Thread
            SHARED = []
            def worker():
                SHARED.append(1)
            Thread(target=worker).start()
        """)
        self.assertEqual(r.shared_mutable_default, 1)

    def test_tt20_dict_mutation_in_thread_target_flagged(self):
        """TT20 — ``dict.update`` on a module dict in Thread target is flagged."""
        r = _analyze("""
            from threading import Thread
            CACHE = {}
            def worker():
                CACHE.update({"k": 1})
            Thread(target=worker).start()
        """)
        self.assertEqual(r.shared_mutable_default, 1)


# ══════════════════════════════════════════════════════════════════════════════
# TT21–TT25 — rating, repr, round-trip, REST
# ══════════════════════════════════════════════════════════════════════════════

class TestRatingAndEndpoint(unittest.TestCase):

    def test_tt21_rating_E_for_many_issues(self):
        """TT21 — total_issues ≥ 6 → rating E."""
        v = ThreadSafetyVector(
            global_shared_state_count=1, lock_missing_count=1,
            daemon_thread_risk=1, queue_unbounded_risk=1,
            asyncio_blocking_call=1, shared_mutable_default=1,
        )
        self.assertEqual(v.thread_safety_rating(), "E")

    def test_tt22_rating_E_for_lock_missing_3_plus(self):
        """TT22 — lock_missing_count ≥ 3 forces rating E even if total < 6."""
        v = ThreadSafetyVector(lock_missing_count=3)
        self.assertEqual(v.thread_safety_rating(), "E")

    def test_tt23_rating_ladder_for_total_issues(self):
        """TT23 — Rating ladder follows total_issues bucket."""
        self.assertEqual(ThreadSafetyVector().thread_safety_rating(), "A")
        self.assertEqual(ThreadSafetyVector(queue_unbounded_risk=1).thread_safety_rating(), "B")
        self.assertEqual(ThreadSafetyVector(queue_unbounded_risk=2).thread_safety_rating(), "C")
        self.assertEqual(ThreadSafetyVector(queue_unbounded_risk=4).thread_safety_rating(), "D")

    def test_tt24_repr_includes_rating_and_counts(self):
        """TT24 — __repr__ exposes rating, total issues, lock_missing, daemon."""
        v = ThreadSafetyVector(lock_missing_count=2, daemon_thread_risk=1)
        rep = repr(v)
        self.assertIn("rating=", rep)
        self.assertIn("issues=3", rep)
        self.assertIn("lock_missing=2", rep)

    def test_tt25_scan_thread_safety_endpoint(self):
        """TT25 — POST /scan-thread-safety returns 200 + summary + vector."""
        from api.server import handle_scan_thread_safety
        src = textwrap.dedent("""
            from threading import Thread
            from queue import Queue
            counter = 0
            def worker():
                global counter
                counter += 1
            Thread(target=worker).start()
            q = Queue()
        """)
        code, data = handle_scan_thread_safety({"code": src, "module_id": "demo"})
        self.assertEqual(code, 200)
        self.assertIn("thread_safety_vector", data)
        self.assertEqual(data["summary"]["global_shared_state_count"], 1)
        self.assertEqual(data["summary"]["queue_unbounded_risk"], 1)
        self.assertIn("thread_safety_rating", data["summary"])


# ══════════════════════════════════════════════════════════════════════════════
# TT26–TT30 — Anti-Pattern Score (APS)
# ══════════════════════════════════════════════════════════════════════════════

class TestAntiPatternScore(unittest.TestCase):

    def test_tt26_components_table_total_weight(self):
        """TT26 — APS_COMPONENTS has 17 entries summing to 130."""
        self.assertEqual(len(APS_COMPONENTS), 17)
        self.assertEqual(APS_WEIGHT_SUM, 130)

    def test_tt27_empty_signals_yield_perfect_100(self):
        """TT27 — A dict with all zeros (or no keys) → APS = 100."""
        self.assertAlmostEqual(compute_aps({}), 100.0)
        zeros = {k: 0 for k in APS_COMPONENTS}
        self.assertAlmostEqual(compute_aps(zeros), 100.0)

    def test_tt28_pathological_signals_yield_zero(self):
        """TT28 — Every signal far past its threshold → APS = 0."""
        worst = {k: 999_999 for k in APS_COMPONENTS}
        self.assertAlmostEqual(compute_aps(worst), 0.0)

    def test_tt29_rate_ladder(self):
        """TT29 — rate_aps follows the documented A/B/C/D/E thresholds."""
        self.assertEqual(rate_aps(95), "A")
        self.assertEqual(rate_aps(85), "B")
        self.assertEqual(rate_aps(70), "C")
        self.assertEqual(rate_aps(50), "D")
        self.assertEqual(rate_aps(30), "E")

    def test_tt30_aps_from_metric_vector_uses_attribute_paths(self):
        """TT30 — aps_from_metric_vector pulls signals via dotted attribute access."""
        mv = SimpleNamespace(
            flow=SimpleNamespace(taint_path_count=2, injection_surface=0.5),
            security=SimpleNamespace(sca_vulnerable_deps=0, iac_misconfig_count=0),
            reliability=SimpleNamespace(
                bare_except_count=0, resource_leak_risk=0,
                mutable_default_arg_count=0, inconsistent_return_count=0,
            ),
            performance=SimpleNamespace(
                n_plus_one_risk=0, quadratic_nested_loop_count=0,
                string_concat_in_loop=0,
            ),
            maintainability=SimpleNamespace(
                missing_docstring_ratio=0.0, long_function_ratio=0.0,
                cognitive_cc_hotspot=0,
            ),
            thread_safety=SimpleNamespace(
                lock_missing_count=1, asyncio_blocking_call=0,
                global_shared_state_count=0,
            ),
        )
        out = aps_from_metric_vector(mv)
        # taint(30) + injection(15) + lock(10) = 55 violation weight → score = 100*(1-55/130) ≈ 57.69
        self.assertLess(out["aps"], 70.0)
        self.assertGreater(out["aps"], 50.0)
        self.assertEqual(out["rating"], "D")
        self.assertIn("components", out)
        self.assertAlmostEqual(out["components"]["taint_path_count"], 1.0)
        self.assertAlmostEqual(out["components"]["lock_missing_count"], 1.0)


if __name__ == "__main__":
    unittest.main()
