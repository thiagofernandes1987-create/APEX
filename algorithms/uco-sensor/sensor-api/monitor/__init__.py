"""
UCO-Sensor — monitor package  (M8.0)
=====================================
Real-time monitoring: filesystem watcher, metric delta engine,
alert rules, and the orchestrating MonitorService.

Exports
-------
ChangedFile      — dataclass describing one filesystem change event
FileWatcher      — polling watcher (stdlib-only, daemon thread)
MetricDelta      — per-channel delta between two MetricVectors
DeltaEngine      — computes MetricDelta from consecutive snapshots
Alert            — one triggered alert (rule, severity, message)
AlertRuleEngine  — evaluates deltas/vectors against threshold rules
MonitorService   — watcher → analyze → delta → alerts pipeline
"""
from .file_watcher import ChangedFile, FileWatcher
from .delta_engine import MetricDelta, DeltaEngine
from .alert_rules import Alert, AlertRuleEngine
from .service import MonitorService

__all__ = [
    "ChangedFile",
    "FileWatcher",
    "MetricDelta",
    "DeltaEngine",
    "Alert",
    "AlertRuleEngine",
    "MonitorService",
]
