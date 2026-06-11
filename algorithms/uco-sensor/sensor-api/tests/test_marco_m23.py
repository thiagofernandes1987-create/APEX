"""
test_marco_m23.py — M8.0 Real-Time Monitoring (30 tests, TM01–TM30)
====================================================================
Validates all components delivered in FASE 7 (M8.0 → v3.1.0):

  • ChangedFile + FileWatcher polling lifecycle                  (TM01–TM08)
  • DeltaEngine: ΔH, ΔCC, epsilon guards, extended vectors       (TM09–TM16)
  • AlertRuleEngine: all 5 rules + suppression guards            (TM17–TM24)
  • MonitorService pipeline + REST endpoints + SSE format        (TM25–TM30)
"""
from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import time
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

from monitor.file_watcher import ChangedFile, FileWatcher
from monitor.delta_engine import DeltaEngine, MetricDelta, _safe_pct
from monitor.alert_rules import Alert, AlertRuleEngine
from monitor.service import MonitorService


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _mv(h=0.0, cc=0, ilr=0.0, sast_crit=0, sast_high=0,
        bare_except=0, leaks=0, module_id="m", ts=0.0):
    """Build a MetricVector-shaped namespace for delta tests."""
    return SimpleNamespace(
        module_id=module_id,
        timestamp=ts,
        hamiltonian=h,
        cyclomatic_complexity=cc,
        infinite_loop_risk=ilr,
        security=SimpleNamespace(sast_critical=sast_crit, sast_high=sast_high),
        reliability=SimpleNamespace(bare_except_count=bare_except,
                                    resource_leak_risk=leaks),
    )


class _Collector:
    """Callback sink for FileWatcher tests."""
    def __init__(self):
        self.events = []
    def __call__(self, change: ChangedFile):
        self.events.append(change)
    def by_event(self, kind: str):
        return [e for e in self.events if e.event == kind]


# ══════════════════════════════════════════════════════════════════════════════
# TM01–TM08 — FileWatcher
# ══════════════════════════════════════════════════════════════════════════════

class TestFileWatcher(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.sink = _Collector()
        self.watcher = FileWatcher(self.root, self.sink, interval_ms=50)

    def tearDown(self):
        self.watcher.stop()
        self.tmp.cleanup()

    def _write(self, name: str, content: str) -> str:
        path = os.path.join(self.root, name)
        with open(path, "w") as fh:
            fh.write(content)
        return path

    def test_tm01_baseline_files_not_reported_as_created(self):
        """TM01 — Files existing before start() produce no events."""
        self._write("pre.py", "x = 1")
        self.watcher.start()
        self.watcher.poll_once()
        self.assertEqual(self.sink.events, [])

    def test_tm02_created_file_detected(self):
        """TM02 — A new .py file yields one 'created' event."""
        self.watcher.start()
        self._write("new.py", "x = 1")
        self.watcher.poll_once()
        created = self.sink.by_event("created")
        self.assertEqual(len(created), 1)
        self.assertTrue(created[0].path.endswith("new.py"))

    def test_tm03_modified_file_detected(self):
        """TM03 — Changing content+mtime yields one 'modified' event."""
        path = self._write("mod.py", "x = 1")
        self.watcher.start()
        time.sleep(0.01)
        with open(path, "w") as fh:
            fh.write("x = 2  # changed")
        os.utime(path)  # force mtime tick
        self.watcher.poll_once()
        self.assertEqual(len(self.sink.by_event("modified")), 1)

    def test_tm04_deleted_file_detected(self):
        """TM04 — Removing a tracked file yields one 'deleted' event."""
        path = self._write("dead.py", "x = 1")
        self.watcher.start()
        os.unlink(path)
        self.watcher.poll_once()
        deleted = self.sink.by_event("deleted")
        self.assertEqual(len(deleted), 1)
        self.assertEqual(deleted[0].size, 0)

    def test_tm05_non_matching_extension_ignored(self):
        """TM05 — Non-.py files are invisible to the watcher."""
        self.watcher.start()
        self._write("notes.txt", "hello")
        self.watcher.poll_once()
        self.assertEqual(self.sink.events, [])

    def test_tm06_hidden_and_pycache_dirs_skipped(self):
        """TM06 — .git/ and __pycache__/ subtrees are not scanned."""
        os.makedirs(os.path.join(self.root, ".git"))
        os.makedirs(os.path.join(self.root, "__pycache__"))
        self.watcher.start()
        with open(os.path.join(self.root, ".git", "x.py"), "w") as fh:
            fh.write("a = 1")
        with open(os.path.join(self.root, "__pycache__", "y.py"), "w") as fh:
            fh.write("b = 2")
        self.watcher.poll_once()
        self.assertEqual(self.sink.events, [])

    def test_tm07_thread_lifecycle_start_stop(self):
        """TM07 — start() spawns a daemon thread; stop() joins it."""
        self.watcher.start()
        self.assertTrue(self.watcher.running)
        self.assertTrue(self.watcher._thread.daemon)
        self.watcher.stop()
        self.assertFalse(self.watcher.running)

    def test_tm08_callback_exception_does_not_kill_watcher(self):
        """TM08 — A raising callback is swallowed; polling continues."""
        def bomb(change):
            raise RuntimeError("boom")
        watcher = FileWatcher(self.root, bomb, interval_ms=50)
        watcher.start()
        self._write("kaboom.py", "x = 1")
        emitted = watcher.poll_once()   # must not raise
        self.assertEqual(emitted, 1)
        watcher.stop()


# ══════════════════════════════════════════════════════════════════════════════
# TM09–TM16 — DeltaEngine
# ══════════════════════════════════════════════════════════════════════════════

class TestDeltaEngine(unittest.TestCase):

    def setUp(self):
        self.engine = DeltaEngine()

    def test_tm09_h_delta_and_pct(self):
        """TM09 — ΔH and h_pct computed from consecutive vectors."""
        d = self.engine.compare(_mv(h=4.0), _mv(h=6.0))
        self.assertAlmostEqual(d.h_delta, 2.0)
        self.assertAlmostEqual(d.h_pct, 0.5)

    def test_tm10_first_sight_has_zero_pct(self):
        """TM10 — prev=None → all *_before=0 and pct=0 (no noise on first sight)."""
        d = self.engine.compare(None, _mv(h=10.0, cc=20))
        self.assertAlmostEqual(d.h_before, 0.0)
        self.assertAlmostEqual(d.h_pct, 0.0)
        self.assertAlmostEqual(d.cc_pct, 0.0)

    def test_tm11_epsilon_guard_near_zero_baseline(self):
        """TM11 — Baseline ≈ 0 uses ε floor: 0.001→0.002 is NOT +100%."""
        pct = _safe_pct(0.001, 0.002)
        self.assertLess(pct, 0.01)  # ε=0.5 floor → 0.001/0.5 = 0.2% not 100%

    def test_tm12_cc_delta(self):
        """TM12 — ΔCC fields populated."""
        d = self.engine.compare(_mv(cc=10), _mv(cc=16))
        self.assertAlmostEqual(d.cc_delta, 6.0)
        self.assertAlmostEqual(d.cc_pct, 0.6)

    def test_tm13_security_delta_from_security_vector(self):
        """TM13 — security_delta = Δ(sast_critical + sast_high)."""
        d = self.engine.compare(
            _mv(sast_crit=1, sast_high=1),
            _mv(sast_crit=2, sast_high=2),
        )
        self.assertAlmostEqual(d.security_before, 2.0)
        self.assertAlmostEqual(d.security_after, 4.0)
        self.assertAlmostEqual(d.security_delta, 2.0)

    def test_tm14_reliability_delta_from_reliability_vector(self):
        """TM14 — reliability_delta = Δ(bare_except + resource_leak)."""
        d = self.engine.compare(_mv(bare_except=0, leaks=0), _mv(bare_except=2, leaks=1))
        self.assertAlmostEqual(d.reliability_delta, 3.0)

    def test_tm15_missing_extended_vectors_default_to_zero(self):
        """TM15 — Vectors without .security/.reliability attrs → deltas 0."""
        bare_prev = SimpleNamespace(module_id="m", timestamp=0.0,
                                    hamiltonian=1.0, cyclomatic_complexity=1,
                                    infinite_loop_risk=0.0)
        bare_curr = SimpleNamespace(module_id="m", timestamp=1.0,
                                    hamiltonian=1.0, cyclomatic_complexity=1,
                                    infinite_loop_risk=0.0)
        d = self.engine.compare(bare_prev, bare_curr)
        self.assertAlmostEqual(d.security_delta, 0.0)
        self.assertAlmostEqual(d.reliability_delta, 0.0)

    def test_tm16_to_dict_round_trip_keys(self):
        """TM16 — to_dict() exposes every channel needed by SSE consumers."""
        d = self.engine.compare(_mv(h=1.0), _mv(h=2.0))
        keys = set(d.to_dict().keys())
        expected = {"module_id", "h_before", "h_after", "h_delta", "h_pct",
                    "cc_before", "cc_after", "cc_delta", "cc_pct",
                    "ilr_before", "ilr_after",
                    "security_delta", "reliability_delta", "timestamp"}
        self.assertTrue(expected.issubset(keys))


# ══════════════════════════════════════════════════════════════════════════════
# TM17–TM24 — AlertRuleEngine
# ══════════════════════════════════════════════════════════════════════════════

class TestAlertRules(unittest.TestCase):

    def setUp(self):
        self.rules  = AlertRuleEngine()
        self.deltas = DeltaEngine()

    def _alerts(self, prev, curr):
        return self.rules.evaluate(self.deltas.compare(prev, curr))

    def test_tm17_h_spike_warning(self):
        """TM17 — ΔH=+25% with |ΔH|≥1 → RULE-H-SPIKE WARNING."""
        alerts = self._alerts(_mv(h=10.0), _mv(h=12.5))
        spike = [a for a in alerts if a.rule == "RULE-H-SPIKE"]
        self.assertEqual(len(spike), 1)
        self.assertEqual(spike[0].severity, "WARNING")

    def test_tm18_h_spike_critical_above_50pct(self):
        """TM18 — ΔH=+60% → RULE-H-SPIKE CRITICAL."""
        alerts = self._alerts(_mv(h=10.0), _mv(h=16.0))
        spike = [a for a in alerts if a.rule == "RULE-H-SPIKE"]
        self.assertEqual(spike[0].severity, "CRITICAL")

    def test_tm19_h_spike_suppressed_by_min_abs_guard(self):
        """TM19 — +40% on tiny baseline (0.5→0.7, |Δ|=0.2 < 1.0) is suppressed."""
        alerts = self._alerts(_mv(h=0.5), _mv(h=0.7))
        self.assertEqual([a for a in alerts if a.rule == "RULE-H-SPIKE"], [])

    def test_tm20_ilr_high_critical(self):
        """TM20 — ILR_after=0.8 > 0.7 → RULE-ILR-HIGH CRITICAL."""
        alerts = self._alerts(_mv(ilr=0.1), _mv(ilr=0.8))
        ilr = [a for a in alerts if a.rule == "RULE-ILR-HIGH"]
        self.assertEqual(len(ilr), 1)
        self.assertEqual(ilr[0].severity, "CRITICAL")

    def test_tm21_new_sast_finding_critical(self):
        """TM21 — security_delta>0 → RULE-SAST-NEW CRITICAL."""
        alerts = self._alerts(_mv(sast_crit=0), _mv(sast_crit=1))
        sast = [a for a in alerts if a.rule == "RULE-SAST-NEW"]
        self.assertEqual(len(sast), 1)
        self.assertEqual(sast[0].severity, "CRITICAL")

    def test_tm22_cc_spike_needs_both_pct_and_abs(self):
        """TM22 — ΔCC +50% but only +2 absolute (< 5) is suppressed."""
        alerts = self._alerts(_mv(cc=4), _mv(cc=6))
        self.assertEqual([a for a in alerts if a.rule == "RULE-CC-SPIKE"], [])
        # +60% AND +6 absolute → fires
        alerts2 = self._alerts(_mv(cc=10), _mv(cc=16))
        self.assertEqual(len([a for a in alerts2 if a.rule == "RULE-CC-SPIKE"]), 1)

    def test_tm23_reliability_regression_warning(self):
        """TM23 — reliability_delta>0 → RULE-REL-REGRESS WARNING."""
        alerts = self._alerts(_mv(bare_except=0), _mv(bare_except=2))
        rel = [a for a in alerts if a.rule == "RULE-REL-REGRESS"]
        self.assertEqual(len(rel), 1)
        self.assertEqual(rel[0].severity, "WARNING")

    def test_tm24_stable_code_produces_no_alerts(self):
        """TM24 — Identical vectors → zero alerts."""
        alerts = self._alerts(_mv(h=5.0, cc=10, ilr=0.2), _mv(h=5.0, cc=10, ilr=0.2))
        self.assertEqual(alerts, [])


# ══════════════════════════════════════════════════════════════════════════════
# TM25–TM30 — MonitorService + endpoints + SSE format
# ══════════════════════════════════════════════════════════════════════════════

class TestMonitorServiceAndEndpoints(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()
        # Ensure no singleton leaks across tests
        import api.server as srv
        with srv._monitor_lock:
            if srv._monitor is not None:
                srv._monitor.stop()
                srv._monitor = None

    def _write(self, name: str, content: str) -> str:
        path = os.path.join(self.root, name)
        with open(path, "w") as fh:
            fh.write(textwrap.dedent(content))
        return path

    def test_tm25_service_pipeline_emits_metric_change(self):
        """TM25 — created file → analyze → metric_change event buffered."""
        svc = MonitorService(self.root, interval_ms=50)
        svc.start()
        self._write("mod.py", "def f():\n    return 1\n")
        svc._watcher.poll_once()
        svc.stop()
        events = svc.drain_events()
        kinds = [e["event"] for e in events]
        self.assertIn("metric_change", kinds)

    def test_tm26_service_emits_alert_on_degradation(self):
        """TM26 — Big H jump between two writes produces an 'alert' event."""
        path = self._write("vict.py", "def f():\n    return 1\n")
        svc = MonitorService(self.root, interval_ms=50)
        svc.start()
        # First analysis: simple function (baseline)
        os.utime(path)
        svc._watcher.poll_once()
        # Second: drastically more complex (H spike + ILR risk)
        with open(path, "w") as fh:
            fh.write(textwrap.dedent("""
                def f(a, b, c, d):
                    while True:
                        for i in range(100):
                            for j in range(100):
                                if a and b or c and d:
                                    try:
                                        x = eval("1+1")
                                    except:
                                        pass
            """))
        os.utime(path)
        svc._watcher.poll_once()
        svc.stop()
        events = svc.drain_events()
        kinds = [e["event"] for e in events]
        self.assertIn("alert", kinds)

    def test_tm27_deleted_file_clears_baseline(self):
        """TM27 — Deletion emits file_deleted and clears the module baseline."""
        path = self._write("gone.py", "x = 1\n")
        svc = MonitorService(self.root, interval_ms=50)
        svc.start()
        os.utime(path)
        svc._watcher.poll_once()
        self.assertEqual(len(svc._baselines), 1)
        os.unlink(path)
        svc._watcher.poll_once()
        svc.stop()
        self.assertEqual(len(svc._baselines), 0)
        kinds = [e["event"] for e in svc.drain_events()]
        self.assertIn("file_deleted", kinds)

    def test_tm28_monitor_start_stop_endpoints(self):
        """TM28 — POST /monitor/start → 200; double start → 409; stop → 200."""
        from api.server import handle_monitor_start, handle_monitor_stop, handle_monitor_status
        code, data = handle_monitor_start({"root": self.root, "interval_ms": 50})
        self.assertEqual(code, 200)
        self.assertTrue(data["started"])

        code2, data2 = handle_monitor_start({"root": self.root})
        self.assertEqual(code2, 409)

        code3, data3 = handle_monitor_status()
        self.assertEqual(code3, 200)
        self.assertTrue(data3["running"])

        code4, data4 = handle_monitor_stop({})
        self.assertEqual(code4, 200)
        self.assertTrue(data4["stopped"])

    def test_tm29_monitor_start_validates_root(self):
        """TM29 — Nonexistent root → 400."""
        from api.server import handle_monitor_start
        code, data = handle_monitor_start({"root": "/nonexistent/xyz"})
        self.assertEqual(code, 400)

    def test_tm30_sse_format_frame(self):
        """TM30 — _sse_format produces a valid SSE frame (event: + data: + blank)."""
        from api.server import _sse_format
        frame = _sse_format("alert", {"rule": "RULE-H-SPIKE", "value": 0.42})
        text = frame.decode("utf-8")
        self.assertTrue(text.startswith("event: alert\n"))
        self.assertIn('data: {"rule": "RULE-H-SPIKE"', text)
        self.assertTrue(text.endswith("\n\n"))


if __name__ == "__main__":
    unittest.main()
