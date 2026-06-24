"""
Pytest fixtures and global session setup for the uco-sensor test suite.

Sprint W fix (audit-5 collateral): the new path-jail in feeds requires
``UCO_FEEDS_DIR`` to be set; existing tests use ``tempfile`` (writes to
``/tmp``).  Setting ``UCO_FEEDS_DIR=/tmp`` for the test session keeps
all pre-Sprint-W tests passing without modification.

Sprint W fix (audit-1 collateral): admin-key required for any test that
calls an admin handler.  We expose ``UCO_ADMIN_KEY`` so handlers route
properly when ``auth_enabled=True`` is exercised.
"""
from __future__ import annotations

import os
import tempfile


# Path-jail root for the entire test session — tempfile.gettempdir()
# is exactly where the feeds tests already write.
os.environ.setdefault("UCO_FEEDS_DIR", tempfile.gettempdir())
os.environ.setdefault("UCO_ADMIN_KEY", "test-admin-key-do-not-use-in-prod")
