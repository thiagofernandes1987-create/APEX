"""
UCO-Sensor — MonitorService  (M8.0, WBS 11.4)
==============================================
Glues the real-time pipeline together:

    FileWatcher → UCOBridge.analyze() → DeltaEngine → AlertRuleEngine
                                                          │
                                              bounded alert/event buffer
                                                          │
                                              SSE stream  (api/server.py)

The service keeps the last MetricVector per module in memory so deltas
are computed against the immediately-previous analysis, and exposes a
thread-safe bounded ``deque`` that the SSE endpoint drains.

Deleted files clear their baseline entry (a re-created file is treated
as first-sight again).

Public API
----------
    svc = MonitorService(root, interval_ms=500)
    svc.start()
    events = svc.drain_events(max_events=50)   # SSE endpoint calls this
    svc.stop()
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from .file_watcher import ChangedFile, FileWatcher
from .delta_engine import DeltaEngine, MetricDelta
from .alert_rules import Alert, AlertRuleEngine

# UCOBridge lives in sensor_core — monitor depends on it, never the reverse.
try:
    from sensor_core.uco_bridge import UCOBridge as _UCOBridge
    _BRIDGE_AVAILABLE = True
except ImportError:
    try:
        from uco_bridge import UCOBridge as _UCOBridge  # type: ignore[no-redef]
        _BRIDGE_AVAILABLE = True
    except ImportError:
        _BRIDGE_AVAILABLE = False

# Bounded buffer: oldest events are dropped under back-pressure
# (FMEA CWE-400 class — same rationale as ThreadSafetyVector's
# queue_unbounded_risk channel).
_MAX_BUFFERED_EVENTS = 1000


class MonitorService:
    """
    Owns one FileWatcher and the analysis pipeline for its root.

    Thread-safety: the watcher callback runs on the watcher thread; the
    SSE endpoint drains from the request thread.  Both the baseline dict
    and the event buffer are guarded by one lock.
    """

    def __init__(
        self,
        root: str,
        interval_ms: int = 500,
        rule_engine: Optional[AlertRuleEngine] = None,
        analyzer: Optional[Any] = None,
    ):
        self.root        = os.path.abspath(root)
        self.interval_ms = interval_ms
        self.started_at: Optional[float] = None

        self._rules    = rule_engine or AlertRuleEngine()
        self._deltas   = DeltaEngine()
        self._analyzer = analyzer or (_UCOBridge(mode="fast") if _BRIDGE_AVAILABLE else None)

        self._lock = threading.Lock()
        self._baselines: Dict[str, Any] = {}          # module_id → last MetricVector
        self._events: Deque[Dict[str, Any]] = deque(maxlen=_MAX_BUFFERED_EVENTS)
        self._alerts_total = 0

        self._watcher = FileWatcher(
            root=self.root,
            callback=self._on_change,
            interval_ms=interval_ms,
            extensions=(".py",),
        )

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._watcher.running

    def start(self) -> None:
        if self.running:
            return
        self.started_at = time.time()
        self._watcher.start()

    def stop(self) -> None:
        self._watcher.stop()

    def status(self) -> Dict[str, Any]:
        return {
            "running":        self.running,
            "root":           self.root,
            "interval_ms":    self.interval_ms,
            "started_at":     self.started_at,
            "alerts_total":   self._alerts_total,
            "events_pending": len(self._events),
            **self._watcher.stats,
        }

    # ── event consumption (SSE endpoint) ──────────────────────────────────────

    def drain_events(self, max_events: int = 100) -> List[Dict[str, Any]]:
        """Pop up to *max_events* buffered events (FIFO). Thread-safe."""
        out: List[Dict[str, Any]] = []
        with self._lock:
            while self._events and len(out) < max_events:
                out.append(self._events.popleft())
        return out

    # ── pipeline (watcher thread) ─────────────────────────────────────────────

    def _module_id(self, path: str) -> str:
        """Stable module id: path relative to root, dots for separators."""
        rel = os.path.relpath(path, self.root)
        return rel[:-3].replace(os.sep, ".") if rel.endswith(".py") else rel

    def _on_change(self, change: ChangedFile) -> None:
        """Watcher callback — analyze, diff, evaluate rules, buffer events."""
        module_id = self._module_id(change.path)

        if change.event == "deleted":
            with self._lock:
                self._baselines.pop(module_id, None)
                self._events.append({
                    "event": "file_deleted",
                    "module": module_id,
                    "timestamp": change.timestamp,
                })
            return

        if self._analyzer is None:
            return  # no UCOBridge in this environment — watcher-only mode

        try:
            with open(change.path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            mv = self._analyzer.analyze(
                source,
                module_id=module_id,
                commit_hash="live",
                timestamp=change.timestamp,
            )
        except Exception:
            return  # analysis failure must never kill the watcher thread

        with self._lock:
            prev = self._baselines.get(module_id)
            delta = self._deltas.compare(prev, mv)
            alerts = self._rules.evaluate(delta) if prev is not None else []
            self._baselines[module_id] = mv

            self._events.append({
                "event":  "metric_change",
                "module": module_id,
                "change": change.event,
                "delta":  delta.to_dict(),
                "timestamp": change.timestamp,
            })
            for alert in alerts:
                self._alerts_total += 1
                self._events.append({"event": "alert", **alert.to_dict()})
