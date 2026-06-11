"""
UCO-Sensor — FileWatcher  (M8.0, WBS 11.1)
===========================================
Polling filesystem watcher — stdlib only, no watchdog/inotify dependency.

Design
------
* ``os.scandir`` walk every ``interval_ms`` milliseconds.
* Change detection by ``st_mtime_ns`` + ``st_size`` fingerprint.
* Runs on a daemon thread — never blocks interpreter exit.
* ``stop()`` is cooperative via ``threading.Event`` (returns within one
  poll interval).
* Files deleted between ``scandir`` and ``stat`` are tolerated
  (``FileNotFoundError`` guard — FMEA DATA failure mode).

Events
------
``created`` / ``modified`` / ``deleted`` — delivered to the callback as
:class:`ChangedFile` instances, one call per file per poll cycle.

Public API
----------
    watcher = FileWatcher(root, callback, interval_ms=500,
                          extensions=(".py",))
    watcher.start()
    ...
    watcher.stop()
"""
from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterator, Optional, Sequence, Tuple


@dataclass
class ChangedFile:
    """One filesystem change event detected by the watcher."""
    path:       str            # absolute path
    event:      str            # "created" | "modified" | "deleted"
    timestamp:  float = field(default_factory=time.time)
    size:       int   = 0      # bytes at detection time (0 for deleted)


# Fingerprint: (mtime_ns, size)
_Fingerprint = Tuple[int, int]


def _scan_tree(
    root: str,
    extensions: Sequence[str],
) -> Iterator[Tuple[str, _Fingerprint]]:
    """
    Yield ``(abs_path, fingerprint)`` for every matching file under *root*.

    Hidden directories (``.git``, ``.venv``, …) and ``__pycache__`` are
    skipped.  Files that disappear mid-scan are silently ignored.
    """
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = list(os.scandir(current))
        except (FileNotFoundError, PermissionError, NotADirectoryError):
            continue
        for entry in entries:
            name = entry.name
            try:
                if entry.is_dir(follow_symlinks=False):
                    if name.startswith(".") or name == "__pycache__":
                        continue
                    stack.append(entry.path)
                elif entry.is_file(follow_symlinks=False):
                    if extensions and not name.endswith(tuple(extensions)):
                        continue
                    st = entry.stat(follow_symlinks=False)
                    yield entry.path, (st.st_mtime_ns, st.st_size)
            except (FileNotFoundError, PermissionError):
                # File vanished between scandir and stat — tolerated.
                continue


class FileWatcher:
    """
    Polling filesystem watcher delivering :class:`ChangedFile` events.

    Parameters
    ----------
    root
        Directory tree to watch (absolute or relative).
    callback
        ``callback(changed: ChangedFile) -> None`` — invoked once per
        changed file per poll cycle, from the watcher thread.  Exceptions
        raised by the callback are swallowed (the watcher must survive).
    interval_ms
        Poll interval in milliseconds (default 500).
    extensions
        File suffixes to track (default ``(".py",)``).  Empty = all files.
    """

    def __init__(
        self,
        root: str,
        callback: Callable[[ChangedFile], None],
        interval_ms: int = 500,
        extensions: Sequence[str] = (".py",),
    ):
        self.root        = os.path.abspath(root)
        self.callback    = callback
        self.interval_ms = max(10, int(interval_ms))
        self.extensions  = tuple(extensions)

        self._snapshot: Dict[str, _Fingerprint] = {}
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._poll_count = 0
        self._events_emitted = 0

    # ── lifecycle ─────────────────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def files_watched(self) -> int:
        """Number of files in the current snapshot."""
        return len(self._snapshot)

    @property
    def stats(self) -> Dict[str, int]:
        return {
            "files_watched":  self.files_watched,
            "poll_count":     self._poll_count,
            "events_emitted": self._events_emitted,
        }

    def start(self) -> None:
        """Take the baseline snapshot and start the daemon polling thread."""
        if self.running:
            return
        # Baseline: existing files are NOT reported as "created".
        self._snapshot = dict(_scan_tree(self.root, self.extensions))
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, name=f"uco-watcher:{self.root}", daemon=True,
        )
        self._thread.start()

    def stop(self, timeout_s: float = 5.0) -> None:
        """Signal the polling thread to stop and join it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout_s)
            self._thread = None

    # ── single poll (exposed for deterministic testing) ───────────────────────

    def poll_once(self) -> int:
        """
        Run one diff cycle synchronously.  Returns the number of events
        emitted.  Used by the thread loop and directly by unit tests.
        """
        current = dict(_scan_tree(self.root, self.extensions))
        emitted = 0

        for path, fp in current.items():
            old = self._snapshot.get(path)
            if old is None:
                emitted += self._emit(ChangedFile(path=path, event="created", size=fp[1]))
            elif old != fp:
                emitted += self._emit(ChangedFile(path=path, event="modified", size=fp[1]))

        for path in self._snapshot.keys() - current.keys():
            emitted += self._emit(ChangedFile(path=path, event="deleted", size=0))

        self._snapshot = current
        self._poll_count += 1
        self._events_emitted += emitted
        return emitted

    # ── internals ─────────────────────────────────────────────────────────────

    def _emit(self, change: ChangedFile) -> int:
        try:
            self.callback(change)
        except Exception:
            pass  # callback failure must never kill the watcher thread
        return 1

    def _run(self) -> None:
        interval_s = self.interval_ms / 1000.0
        while not self._stop_event.wait(interval_s):
            self.poll_once()
