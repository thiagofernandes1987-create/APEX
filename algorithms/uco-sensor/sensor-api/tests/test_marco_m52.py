"""
Marco 52 — Sprint U: Cache Layer + ASGI Wrapper + Bench (TE01-TE30)
====================================================================

Performance overhaul.  Three deliverables:
  • Cache layer with TTL (LRU local + Redis opt-in)
  • ASGI wrapper (Starlette opt-in, delegates to legacy handlers)
  • Benchmark harness (pure-stdlib, serial + parallel modes)

Coverage layout
---------------
* TE01-TE10 — cache_get/set/invalidate, decorator, status, TTL expiry
* TE11-TE20 — heavy-handler cache integration (repo health, fingerprint,
  granger matrix), cache stats reflect requests
* TE21-TE30 — benchmark summarise/_percentile/_one_request, ASGI app
  importable + route table sane
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sensor_storage import cache as _cache
from bench.benchmark import (
    _percentile, summarise, _one_request,
)


@pytest.fixture(autouse=True)
def _reset_cache():
    _cache._reset_for_tests()
    yield
    _cache._reset_for_tests()


# ═══════════════════════════════════════════════════════════════════════════════
# TE01-TE10 — cache layer primitives
# ═══════════════════════════════════════════════════════════════════════════════

def test_TE01_get_miss_returns_None():
    assert _cache.cache_get("nope") is None


def test_TE02_set_then_get_round_trip():
    _cache.cache_set("key", {"x": 1}, ttl=60)
    assert _cache.cache_get("key") == {"x": 1}


def test_TE03_set_with_ttl_zero_expires_immediately():
    # ttl=None means no expiry; very small ttl should expire fast
    _cache.cache_set("k", "v", ttl=0.01)
    time.sleep(0.05)
    assert _cache.cache_get("k") is None


def test_TE04_invalidate_by_prefix():
    _cache.cache_set("a:1", 1)
    _cache.cache_set("a:2", 2)
    _cache.cache_set("b:1", 3)
    n = _cache.cache_invalidate("a:")
    assert n == 2
    assert _cache.cache_get("a:1") is None
    assert _cache.cache_get("b:1") == 3


def test_TE05_invalidate_all_with_empty_prefix():
    _cache.cache_set("x", 1)
    _cache.cache_set("y", 2)
    n = _cache.cache_invalidate("")
    assert n == 2


def test_TE06_status_reports_backend_and_counters():
    _cache.cache_set("k", "v")
    _cache.cache_get("k")
    _cache.cache_get("missing")
    s = _cache.cache_status()
    assert s["hits"] >= 1
    assert s["misses"] >= 1
    assert s["backend"].startswith("lru-local") or s["backend"].startswith("redis")


def test_TE07_decorator_caches_result():
    calls = {"n": 0}

    @_cache.cached(ttl=60)
    def expensive(x):
        calls["n"] += 1
        return x * 2

    assert expensive(5) == 10
    assert expensive(5) == 10
    assert calls["n"] == 1   # second call hit cache


def test_TE08_decorator_different_args_different_cache():
    @_cache.cached(ttl=60)
    def f(x):
        return x + 1

    assert f(1) == 2
    assert f(2) == 3


def test_TE09_lru_evicts_oldest_when_full():
    backend = _cache._LocalLRU(max_size=3)
    backend.set("a", 1)
    backend.set("b", 2)
    backend.set("c", 3)
    backend.set("d", 4)   # forces eviction of "a"
    assert backend.get("a") is None
    assert backend.get("d") == 4


def test_TE10_set_swallows_unserializable_silently():
    """An object that can't be JSON'd must not crash cache_set."""
    class Weird:
        pass
    _cache.cache_set("w", Weird())
    # No assertion on get — just that no exception bubbles.


# ═══════════════════════════════════════════════════════════════════════════════
# TE11-TE20 — heavy-handler cache integration
# ═══════════════════════════════════════════════════════════════════════════════

def _populated_store():
    """Build a store with enough modules + history for the heavy handlers."""
    import math
    from sensor_storage.snapshot_store import SnapshotStore
    from core.data_structures import MetricVector
    from metrics.extended_vectors import SecurityVector
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod, fn in [
        ("a", lambda i: int(5 + 10 * math.sin(2*math.pi*i/6))),
        ("b", lambda i: int(5 + 10 * math.sin(2*math.pi*i/6 + 0.5))),
    ]:
        for i in range(20):
            mv = MetricVector(mod, f"c{i:02d}", base + i,
                              hamiltonian=5.0, cyclomatic_complexity=2,
                              infinite_loop_risk=0.0, dsm_density=0.4,
                              dsm_cyclic_ratio=0.1, dependency_instability=0.2,
                              syntactic_dead_code=0, duplicate_block_count=0,
                              halstead_bugs=0.1)
            mv.security = SecurityVector(sca_vulnerable_deps=max(0, fn(i)))
            s.insert(mv)
    return s


def test_TE11_repo_health_score_hits_cache_on_second_call():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_repo_health_score()
    pre = _cache.cache_status()["hits"]
    srv.handle_repo_health_score()
    post = _cache.cache_status()["hits"]
    assert post > pre


def test_TE12_spectral_fingerprint_hits_cache_on_second_call():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_spectral_fingerprint("a")
    pre = _cache.cache_status()["hits"]
    srv.handle_spectral_fingerprint("a")
    post = _cache.cache_status()["hits"]
    assert post > pre


def test_TE13_granger_matrix_hits_cache_on_second_call():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_granger_matrix("a", max_lag=2)
    pre = _cache.cache_status()["hits"]
    srv.handle_granger_matrix("a", max_lag=2)
    post = _cache.cache_status()["hits"]
    assert post > pre


def test_TE14_different_window_different_cache_entry():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_repo_health_score(window=100)
    srv.handle_repo_health_score(window=50)
    s = _cache.cache_status()
    assert s["sets"] >= 2


def test_TE15_invalidate_endpoint_handler():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_repo_health_score()
    pre_size = _cache.cache_status()["size"]
    code, payload = srv.handle_cache_invalidate({"prefix": "repo_health_score:"})
    assert code == 200
    assert payload["invalidated"] >= 1
    assert _cache.cache_status()["size"] < pre_size


def test_TE16_status_endpoint_handler():
    import api.server as srv
    code, payload = srv.handle_cache_status()
    assert code == 200
    assert "backend" in payload
    assert "hits" in payload


def test_TE17_cache_does_not_break_handler_on_backend_failure():
    """Even if cache backend raises on get, handler must still return data."""
    import api.server as srv
    srv._store = _populated_store()
    # Force backend to a broken stub
    class BrokenBackend:
        def get(self, *_): raise RuntimeError("boom")
        def set(self, *_, **__): raise RuntimeError("boom")
        def size(self): return 0
    _cache._BACKEND = BrokenBackend()
    _cache._BACKEND_NAME = "broken-stub"
    try:
        code, payload = srv.handle_spectral_fingerprint("a")
        assert code == 200   # handler still works
    finally:
        _cache._reset_for_tests()


def test_TE18_repo_health_score_payload_unchanged_by_cache():
    """Cached value must be equal to the freshly-computed one."""
    import api.server as srv
    srv._store = _populated_store()
    code1, p1 = srv.handle_repo_health_score()
    code2, p2 = srv.handle_repo_health_score()
    assert p1 == p2


def test_TE19_granger_matrix_alpha_change_misses_cache():
    import api.server as srv
    srv._store = _populated_store()
    srv.handle_granger_matrix("a", alpha=0.05)
    s0 = _cache.cache_status()
    srv.handle_granger_matrix("a", alpha=0.10)   # different cache key
    s1 = _cache.cache_status()
    # An extra miss occurred for the new alpha
    assert s1["misses"] > s0["misses"]


def test_TE20_endpoints_registered_in_docs():
    import api.server as srv
    _, docs = srv.handle_docs()
    # Cache routes are not formally listed in /docs (kept lean) — that's
    # OK; we just confirm the heavy handlers' descriptions still exist.
    paths = {e["path"] for e in docs["endpoints"]}
    for p in ("/repo/health-score", "/spectral/fingerprint",
              "/granger/matrix"):
        assert p in paths


# ═══════════════════════════════════════════════════════════════════════════════
# TE21-TE30 — benchmark harness + ASGI importability
# ═══════════════════════════════════════════════════════════════════════════════

def test_TE21_percentile_empty_list():
    assert _percentile([], 50) == 0.0


def test_TE22_percentile_p50_of_sorted():
    assert _percentile([1.0, 2.0, 3.0], 50) == 2.0


def test_TE23_percentile_p99_of_long_list():
    """P99 with nearest-rank on N=100 lands at index round(0.99*99)=98."""
    xs = [float(i) for i in range(100)]
    assert _percentile(xs, 99) == 98.0
    assert _percentile(xs, 100) == 99.0   # P100 = max element


def test_TE24_summarise_shape():
    results = [(True, 0.01, 200), (True, 0.02, 200), (False, 0.05, 500)]
    s = summarise(results, wallclock_s=0.10)
    for k in ("n", "successes", "errors", "wall_s", "throughput",
              "p50_ms", "p95_ms", "p99_ms", "mean_ms"):
        assert k in s
    assert s["successes"] == 2
    assert s["errors"] == 1
    assert s["throughput"] == 30.0   # 3 req / 0.1s


def test_TE25_summarise_empty_results():
    s = summarise([], wallclock_s=1.0)
    assert s["n"] == 0
    assert s["mean_ms"] == 0


def test_TE26_one_request_handles_invalid_url():
    """Bad URL must NOT raise — returns (False, _, 0)."""
    ok, _, status = _one_request("http://localhost:1/should-not-exist",
                                  timeout=0.5)
    assert ok is False


def test_TE27_asgi_wrapper_can_be_imported_when_starlette_installed():
    """If starlette is unavailable, importing must raise ImportError with
    a helpful message — otherwise the module loads cleanly."""
    try:
        import starlette  # noqa: F401
    except ImportError:
        pytest.skip("starlette not installed — skipping ASGI import test")
    from asgi import app as asgi_app
    assert hasattr(asgi_app, "app")
    assert hasattr(asgi_app, "run")


def test_TE28_asgi_route_table_has_curated_endpoints_when_loadable():
    try:
        import starlette  # noqa: F401
    except ImportError:
        pytest.skip("starlette not installed — skipping route table test")
    from asgi import app as asgi_app
    # Starlette Route exposes .path
    paths = {r.path for r in asgi_app._routes}
    for must in ("/", "/health", "/docs",
                 "/repo/health-score", "/spectral/fingerprint",
                 "/granger/matrix", "/repair/hmc"):
        assert must in paths


def test_TE29_benchmark_main_returns_nonzero_on_all_errors():
    """If every request errors out, main() exits non-zero."""
    from bench.benchmark import main
    rc = main(["--url", "http://localhost:1/nope", "--n", "2"])
    assert rc != 0


def test_TE30_cache_decorator_with_custom_key_fn():
    @_cache.cached(ttl=60, key_fn=lambda x: f"custom:{x}")
    def f(x):
        return x * 10

    f(7)
    # Custom key visible in invalidation
    n = _cache.cache_invalidate("custom:")
    assert n >= 1
