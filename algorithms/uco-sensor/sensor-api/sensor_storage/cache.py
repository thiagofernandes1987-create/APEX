"""
Sprint U — Cache Layer (v3.5.0)
================================
Pluggable cache for expensive read endpoints.  Two backends, both
optional and chosen automatically at process start:

  • **In-memory LRU** (default) — pure Python, zero dependencies, OK
    for single-process deployments and dev.
  • **Redis** — opt-in via ``UCO_REDIS_URL`` env var (e.g.
    ``redis://localhost:6379/0``).  Production-grade, shared across
    multiple ASGI workers.

Public API
----------
- ``cache_get(key) -> Optional[Any]``
- ``cache_set(key, value, *, ttl=None) -> None``
- ``cache_invalidate(prefix="") -> int``
- ``cache_status() -> Dict[str, Any]`` — hits / misses / size / backend
- ``@cached(ttl=N, key_fn=...)`` decorator

Contract
--------
* All operations swallow backend errors silently (cache MUST never
  break the request).  ``cache_get`` returns None on failure;
  ``cache_set`` is a no-op on failure.
* TTL defaults to 60s; pass ``ttl=None`` to skip expiry entirely.
* Keys are normalised to strings; values are JSON-serialisable.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

_log = logging.getLogger("uco-sensor.cache")


# ─── Module-local counters (exposed via /health) ─────────────────────────────

_metrics_lock = threading.Lock()
_metrics: Dict[str, int] = {
    "hits":     0,
    "misses":   0,
    "sets":     0,
    "evictions": 0,
}


def _bump(name: str, n: int = 1) -> None:
    with _metrics_lock:
        _metrics[name] = _metrics.get(name, 0) + int(n)


# ─── In-memory LRU backend ───────────────────────────────────────────────────

class _LocalLRU:
    """Thread-safe TTL+LRU cache.  Pure stdlib."""

    def __init__(self, max_size: int = 1024):
        self._max_size = max_size
        self._lock = threading.Lock()
        # key → (value_json, expires_at_or_None, inserted_at)
        self._store: Dict[str, Tuple[str, Optional[float], float]] = {}

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value_json, expires_at, _ = entry
            if expires_at is not None and time.time() > expires_at:
                self._store.pop(key, None)
                _bump("evictions")
                return None
            # Promote (LRU) — re-insert at the end
            self._store.pop(key)
            self._store[key] = entry
        try:
            return json.loads(value_json)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        try:
            payload = json.dumps(value, default=str)
        except Exception:
            return
        expires_at = (time.time() + ttl) if ttl else None
        with self._lock:
            self._store[key] = (payload, expires_at, time.time())
            # LRU eviction
            while len(self._store) > self._max_size:
                self._store.pop(next(iter(self._store)))
                _bump("evictions")

    def invalidate(self, prefix: str = "") -> int:
        with self._lock:
            if not prefix:
                n = len(self._store)
                self._store.clear()
                return n
            to_drop = [k for k in self._store if k.startswith(prefix)]
            for k in to_drop:
                self._store.pop(k, None)
            return len(to_drop)

    def size(self) -> int:
        with self._lock:
            return len(self._store)


# ─── Redis backend (opt-in via UCO_REDIS_URL) ────────────────────────────────

class _RedisCache:
    """Thin wrapper around redis-py.  Always swallows errors."""

    def __init__(self, url: str):
        import redis  # type: ignore
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._client.ping()   # raise here if unreachable; caller wraps

    def get(self, key: str) -> Optional[Any]:
        try:
            raw = self._client.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            return None

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        try:
            payload = json.dumps(value, default=str)
            if ttl:
                self._client.setex(key, int(ttl), payload)
            else:
                self._client.set(key, payload)
        except Exception:
            return

    def invalidate(self, prefix: str = "") -> int:
        try:
            if not prefix:
                # FLUSHDB is dangerous in shared Redis; instead match-and-delete.
                pattern = "*"
            else:
                pattern = f"{prefix}*"
            n = 0
            for k in self._client.scan_iter(match=pattern, count=500):
                self._client.delete(k)
                n += 1
            return n
        except Exception:
            return 0

    def size(self) -> int:
        try:
            return int(self._client.dbsize() or 0)
        except Exception:
            return 0


# ─── Backend selection ───────────────────────────────────────────────────────

_BACKEND: Optional[Any] = None
_BACKEND_NAME: str = "uninitialized"


def _init_backend() -> None:
    """Resolve the active backend lazily on first use."""
    global _BACKEND, _BACKEND_NAME
    if _BACKEND is not None:
        return
    redis_url = os.environ.get("UCO_REDIS_URL", "").strip()
    if redis_url:
        try:
            _BACKEND = _RedisCache(redis_url)
            _BACKEND_NAME = f"redis:{redis_url}"
            _log.info("cache: using Redis %s", redis_url)
            return
        except Exception as exc:
            _log.warning("cache: Redis %s unreachable (%s) — falling back to LRU", redis_url, exc)
    _BACKEND = _LocalLRU(max_size=int(os.environ.get("UCO_CACHE_MAX_SIZE", "1024")))
    _BACKEND_NAME = "lru-local"
    _log.info("cache: using in-memory LRU")


def _backend() -> Any:
    if _BACKEND is None:
        _init_backend()
    return _BACKEND


# ─── Public API ──────────────────────────────────────────────────────────────

def cache_get(key: str) -> Optional[Any]:
    try:
        v = _backend().get(key)
    except Exception:
        v = None
    if v is None:
        _bump("misses")
    else:
        _bump("hits")
    return v


def cache_set(key: str, value: Any, *, ttl: Optional[float] = 60) -> None:
    try:
        _backend().set(key, value, ttl=ttl)
        _bump("sets")
    except Exception:
        pass


def cache_invalidate(prefix: str = "") -> int:
    try:
        return _backend().invalidate(prefix)
    except Exception:
        return 0


def cache_status() -> Dict[str, Any]:
    """Snapshot of operational counters + backend identity."""
    with _metrics_lock:
        m = dict(_metrics)
    try:
        size = _backend().size()
    except Exception:
        size = 0
    total = m["hits"] + m["misses"]
    hit_rate = (m["hits"] / total) if total else 0.0
    return {
        "backend":   _BACKEND_NAME,
        "size":      size,
        "hits":      m["hits"],
        "misses":    m["misses"],
        "sets":      m["sets"],
        "evictions": m["evictions"],
        "hit_rate":  round(hit_rate, 4),
    }


def cached(ttl: Optional[float] = 60,
           key_fn: Optional[Callable[..., str]] = None):
    """
    Decorator that caches a function's return value.

    Parameters
    ----------
    ttl : seconds (default 60); None = no expiry
    key_fn : callable(*args, **kwargs) → cache key.  Default: function
             name + repr(args) + sorted-repr(kwargs).
    """
    def _decor(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def _wrap(*args, **kwargs):
            if key_fn is None:
                key = f"{fn.__module__}.{fn.__name__}:{args}:{sorted(kwargs.items())}"
            else:
                try:
                    key = key_fn(*args, **kwargs)
                except Exception:
                    return fn(*args, **kwargs)
            cached_value = cache_get(key)
            if cached_value is not None:
                return cached_value
            result = fn(*args, **kwargs)
            cache_set(key, result, ttl=ttl)
            return result
        return _wrap
    return _decor


# ─── Test/dev helpers ────────────────────────────────────────────────────────

def _reset_for_tests() -> None:
    """Wipe backend + counters.  ONLY for tests."""
    global _BACKEND, _BACKEND_NAME
    _BACKEND = None
    _BACKEND_NAME = "uninitialized"
    with _metrics_lock:
        for k in _metrics:
            _metrics[k] = 0
