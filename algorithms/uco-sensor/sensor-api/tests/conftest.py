"""
Pytest fixtures and global session setup for the uco-sensor test suite.

Notes
-----
* Sprint W (audit-5 collateral): ``UCO_FEEDS_DIR`` is required by the
  path-jail introduced in feeds.  Default to ``tempfile.gettempdir()``.
* Sprint W (audit-1 collateral): admin-key needed for admin handlers.
* Sprint W2 (gate-2 G2-6): see ``isolated_store`` opt-in fixture below.
"""
from __future__ import annotations

import os
import tempfile

import pytest


os.environ.setdefault("UCO_FEEDS_DIR", tempfile.gettempdir())
os.environ.setdefault("UCO_ADMIN_KEY", "test-admin-key-do-not-use-in-prod")


@pytest.fixture
def isolated_store():
    """Sprint W2 (gate-2 G2-6) — opt-in fresh server store.

    Legacy tests ``import _store`` directly from ``api.server`` and rely
    on the shared module-level instance: replacing it autouse breaks them.
    New tests that exercise admin endpoints should request this fixture
    to guarantee isolation from peer tests.
    """
    from api import server as _srv
    from sensor_storage.snapshot_store import SnapshotStore
    prev = _srv._store
    _srv._store = SnapshotStore(":memory:")
    try:
        yield _srv._store
    finally:
        try:
            _srv._store.close()
        except Exception:
            pass
        _srv._store = prev
