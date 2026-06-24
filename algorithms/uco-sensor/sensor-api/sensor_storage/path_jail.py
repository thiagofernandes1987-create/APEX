"""
Sprint W fix (audit-5, HIGH) — feed path-jail
==============================================
Canonicalise + restrict filesystem paths accepted by ``/feeds/cve/load``
and ``/feeds/sast/load`` so an authenticated admin (post audit-1 fix)
cannot read arbitrary files via ``open(path)``.

Contract
--------
- If ``UCO_FEEDS_DIR`` env var is set, accepted paths MUST resolve
  inside that directory (no ``..`` escapes).
- If ``UCO_FEEDS_DIR`` is empty/unset, the safe default is to REJECT
  every filesystem-based load (caller must use inline or url payload).
- Always returns an absolute, resolved path on success.

Public API
----------
- ``check_feed_path(path) -> Optional[str]``
  Returns the canonical path on success, or ``None`` if rejected.
- ``feeds_dir() -> Optional[str]``
  Current root; ``None`` when unset.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def feeds_dir() -> Optional[str]:
    raw = os.environ.get("UCO_FEEDS_DIR", "").strip()
    if not raw:
        return None
    try:
        return str(Path(raw).resolve())
    except Exception:
        return None


def check_feed_path(path: str) -> Optional[str]:
    """
    Validate that *path* is inside the configured ``UCO_FEEDS_DIR`` root.

    Returns the canonical (absolute, symlink-resolved) path on success,
    or ``None`` when:
      • ``UCO_FEEDS_DIR`` is unset → all file-based loads disabled
      • ``path`` is empty or malformed
      • resolved path escapes the root (path-traversal attempt)
    """
    if not path or not isinstance(path, str):
        return None

    root = feeds_dir()
    if root is None:
        return None        # closed by default

    try:
        candidate = Path(path).expanduser().resolve()
    except Exception:
        return None

    root_path = Path(root)
    try:
        candidate.relative_to(root_path)
    except ValueError:
        return None        # outside root → reject
    return str(candidate)
