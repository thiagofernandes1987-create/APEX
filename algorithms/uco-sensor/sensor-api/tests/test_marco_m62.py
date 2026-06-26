"""
Marco 62 — Sprint AB: Multi-tenant isolation + Deep-Eval quick-wins (TAB01-TAB30)
==================================================================================

Pins for Sprint AB (v3.10.0), follow-up to ``UCO_SENSOR_DEEP_EVAL.md``:

* TAB01-TAB10 — AB-1 P0: tenant_id schema isolation on snapshots
  (cross-tenant invariants, no leak, no collision).
* TAB11-TAB14 — AB-2 QW#1: marketplace ReDoS guard reuses regex_analyzer
  (catches the (X+)+ family the prior substring blocklist missed).
* TAB15-TAB18 — AB-3 QW#2: cache invalidation on _store.insert
  (no stale dashboards 30-120s after write).
* TAB19-TAB22 — AB-4 QW#3: README badges + endpoint catalogue sync.
* TAB23-TAB30 — AB-5 QW#4: charge-after-success in _billed_dispatch
  (no debit on 4xx/5xx, 2xx still debited, suspend still 423).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore


def _fresh_store():
    return SnapshotStore(":memory:")


def _mv(module_id: str, commit_hash: str = "c1", **overrides) -> MetricVector:
    """Minimal MetricVector for store insertion."""
    defaults = dict(
        module_id=module_id,
        commit_hash=commit_hash,
        timestamp=1782470000.0,
        hamiltonian=1.0,
        cyclomatic_complexity=2,
        infinite_loop_risk=0.0,
        dsm_density=0.1,
        dsm_cyclic_ratio=0.0,
        dependency_instability=0.5,
        syntactic_dead_code=0,
        duplicate_block_count=0,
        halstead_bugs=0.05,
        language="python",
        lines_of_code=42,
    )
    defaults.update(overrides)
    mv = MetricVector(**defaults)
    # Optional attributes set via setattr to match what UCOBridge does.
    mv.status = "STABLE"
    return mv


# ═══════════════════════════════════════════════════════════════════════════
# AB-1 — tenant_id schema isolation on snapshots (TAB01-TAB10)
# ═══════════════════════════════════════════════════════════════════════════

def test_TAB01_default_tenant_id_preserves_legacy_behavior():
    """Callers that don't pass tenant_id still write/read the 'default' partition."""
    s = _fresh_store()
    s.insert(_mv("utils.math"))
    hist = s.get_history("utils.math")
    assert len(hist) == 1
    assert hist[0].module_id == "utils.math"


def test_TAB02_two_tenants_isolate_same_module_id_in_history():
    s = _fresh_store()
    s.insert(_mv("utils.math", "ca"), tenant_id="acme")
    s.insert(_mv("utils.math", "cb"), tenant_id="other")
    hist_acme  = s.get_history("utils.math", tenant_id="acme")
    hist_other = s.get_history("utils.math", tenant_id="other")
    assert len(hist_acme)  == 1
    assert len(hist_other) == 1
    assert hist_acme[0].commit_hash  == "ca"
    assert hist_other[0].commit_hash == "cb"


def test_TAB03_two_tenants_same_module_and_commit_no_collision():
    """The deep-eval Finding #1's worst case: same module_id + commit_hash
    across tenants must NOT UPSERT each other (no IP cross-leak)."""
    s = _fresh_store()
    s.insert(_mv("payments.charge", "abc123", hamiltonian=1.0),
             tenant_id="acme")
    s.insert(_mv("payments.charge", "abc123", hamiltonian=99.0),
             tenant_id="other")
    h_acme  = s.get_history("payments.charge", tenant_id="acme")
    h_other = s.get_history("payments.charge", tenant_id="other")
    assert len(h_acme)  == 1
    assert len(h_other) == 1
    assert h_acme[0].hamiltonian  == 1.0
    assert h_other[0].hamiltonian == 99.0


def test_TAB04_list_modules_default_scoped_to_default_tenant():
    s = _fresh_store()
    s.insert(_mv("default.mod"))
    s.insert(_mv("acme.mod"), tenant_id="acme")
    # Default caller sees only the 'default' tenant's modules.
    assert s.list_modules() == ["default.mod"]
    assert s.list_modules(tenant_id="acme") == ["acme.mod"]


def test_TAB05_list_modules_star_lists_across_tenants():
    """Admin-only escape hatch tenant_id='*' lists everything."""
    s = _fresh_store()
    s.insert(_mv("a.mod"))
    s.insert(_mv("b.mod"), tenant_id="acme")
    all_mods = set(s.list_modules(tenant_id="*"))
    assert all_mods == {"a.mod", "b.mod"}


def test_TAB06_tenant_id_column_present_on_5_tables():
    """Schema migration must add tenant_id to all 5 product-data tables."""
    s = _fresh_store()
    with s._lock:
        cur = s._get_conn().cursor()
        for table in ("snapshots", "anomalies", "discovered_signatures",
                      "remediations", "marketplace_signatures"):
            cols = [r[1] for r in cur.execute(
                f"PRAGMA table_info({table})").fetchall()]
            assert "tenant_id" in cols, f"{table} missing tenant_id"


def test_TAB07_composite_unique_index_present_on_snapshots():
    """ux_snapshots_tenant_module_commit must exist as a UNIQUE index."""
    s = _fresh_store()
    with s._lock:
        cur = s._get_conn().cursor()
        idx = [r for r in cur.execute(
            "PRAGMA index_list(snapshots)").fetchall()
            if r[1] == "ux_snapshots_tenant_module_commit"]
        assert len(idx) == 1
        assert idx[0][2] == 1  # unique
        info = cur.execute(
            "PRAGMA index_info(ux_snapshots_tenant_module_commit)"
        ).fetchall()
        cols = [r[2] for r in info]
        assert cols == ["tenant_id", "module_id", "commit_hash"]


def test_TAB08_same_tenant_same_module_commit_still_upserts():
    """Idempotency within a tenant: re-inserting (module, commit) updates."""
    s = _fresh_store()
    s.insert(_mv("u.m", "c1", hamiltonian=1.0), tenant_id="acme")
    s.insert(_mv("u.m", "c1", hamiltonian=2.0), tenant_id="acme")
    hist = s.get_history("u.m", tenant_id="acme")
    assert len(hist) == 1
    assert hist[0].hamiltonian == 2.0


def test_TAB09_get_history_unknown_tenant_returns_empty():
    s = _fresh_store()
    s.insert(_mv("u.m"), tenant_id="acme")
    assert s.get_history("u.m", tenant_id="other") == []


def test_TAB10_tenant_id_indexes_present_for_all_5_tables():
    s = _fresh_store()
    with s._lock:
        cur = s._get_conn().cursor()
        for table in ("snapshots", "anomalies", "discovered_signatures",
                      "remediations", "marketplace_signatures"):
            indexes = [r[1] for r in cur.execute(
                f"PRAGMA index_list({table})").fetchall()]
            assert f"idx_{table}_tenant" in indexes, \
                f"{table} missing tenant index"


# ═══════════════════════════════════════════════════════════════════════════
# AB-2 — marketplace ReDoS guard reuses regex_analyzer (TAB11-TAB14)
# ═══════════════════════════════════════════════════════════════════════════

def test_TAB11_nested_quantifier_now_rejected():
    """The (a+)+ family was passing the old substring blocklist;
    regex_analyzer.Class A catches it."""
    from governance.marketplace import _has_redos_shape
    assert _has_redos_shape("(a+)+") is True


def test_TAB12_overlapping_charclass_quantifier_rejected():
    from governance.marketplace import _has_redos_shape
    # Pattern with quantified char-class group + outer quantifier — Class C
    # of regex_analyzer; was missed by the substring blocklist.
    assert _has_redos_shape("([a-z]+)*") is True


def test_TAB13_empty_string_still_safe():
    """QA-FIX-6 (v3.9.1) guarantee preserved: empty → False."""
    from governance.marketplace import _has_redos_shape
    assert _has_redos_shape("") is False
    assert _has_redos_shape(None) is False


def test_TAB14_overlong_string_still_rejected():
    """DoS-by-input-size guard preserved (len > 2000 → True)."""
    from governance.marketplace import _has_redos_shape
    assert _has_redos_shape("a" * 2001) is True


# ═══════════════════════════════════════════════════════════════════════════
# AB-3 — cache invalidation on _store.insert (TAB15-TAB18)
# ═══════════════════════════════════════════════════════════════════════════

def test_TAB15_invalidate_helper_present_in_server():
    from api import server
    assert hasattr(server, "_invalidate_module_caches")
    assert callable(server._invalidate_module_caches)


def test_TAB16_invalidate_helper_swallows_cache_import_error(monkeypatch):
    """Cache failures MUST NOT break the request — defensive try/except chain."""
    from api import server
    # Force a hostile failure: replace cache_invalidate with a raiser.
    import sensor_storage.cache as cache_mod
    def boom(*a, **kw):
        raise RuntimeError("cache backend exploded")
    monkeypatch.setattr(cache_mod, "cache_invalidate", boom)
    # Should NOT raise.
    server._invalidate_module_caches("u.m")


def test_TAB17_invalidate_called_with_module_scoped_prefixes(monkeypatch):
    """The helper must call cache_invalidate for the module-scoped families
    AND the global repo_health_score key."""
    from api import server
    import sensor_storage.cache as cache_mod
    calls = []
    def fake_invalidate(prefix: str = "") -> int:
        calls.append(prefix)
        return 0
    monkeypatch.setattr(cache_mod, "cache_invalidate", fake_invalidate)
    server._invalidate_module_caches("payments.charge")
    assert "spectral_fp:payments.charge" in calls
    assert "granger_matrix:payments.charge" in calls
    assert "repo_health_score:" in calls


def test_TAB18_cache_set_then_invalidate_then_miss():
    """End-to-end: insert a key, invalidate by prefix, verify miss."""
    from sensor_storage.cache import cache_set, cache_get, cache_invalidate
    cache_set("spectral_fp:demo:w=10", {"x": 1}, ttl=120)
    assert cache_get("spectral_fp:demo:w=10") is not None
    n = cache_invalidate("spectral_fp:demo")
    assert n >= 1
    assert cache_get("spectral_fp:demo:w=10") is None


# ═══════════════════════════════════════════════════════════════════════════
# AB-4 — README sync (TAB19-TAB22)
# ═══════════════════════════════════════════════════════════════════════════

_README = (Path(__file__).resolve().parent.parent / "README.md")


def test_TAB19_readme_version_badge_matches_v3_10_target():
    txt = _README.read_text()
    assert "version-3.10.0" in txt, "README badge must reflect target v3.10.0"
    # Legacy badge gone:
    assert "version-0.4.0" not in txt


def test_TAB20_readme_no_apex_v00_36_badge():
    """The 'APEX v00.36.0' badge was stale — removed in AB-4."""
    txt = _README.read_text()
    assert "APEX-v00.36.0" not in txt


def test_TAB21_readme_documents_multi_tenant_quickstart():
    txt = _README.read_text()
    assert "Multi-tenant SaaS quickstart" in txt
    # Mentions the key tables in the schema section.
    assert "tenant_id" in txt


def test_TAB22_readme_endpoint_table_lists_billing_invariants_marketplace():
    """The endpoint catalogue now describes the post-Sprint-Z categories."""
    txt = _README.read_text()
    for category in ("Billing", "Invariants", "Marketplace", "Multi-tenant"):
        assert category in txt, f"README endpoint table missing {category!r}"


# ═══════════════════════════════════════════════════════════════════════════
# AB-5 — charge-after-success in _billed_dispatch (TAB23-TAB30)
# ═══════════════════════════════════════════════════════════════════════════

def _stub_handler_2xx(_data):
    return 200, {"ok": True}


def _stub_handler_500(_data):
    return 500, {"error": "oops"}


def _stub_handler_400(_data):
    return 400, {"error": "bad request"}


def _stub_handler_raises(_data):
    raise RuntimeError("uncaught")


def _key_info_for(tenant_id: str):
    return {"key_prefix": f"uco_{tenant_id[:4]}", "tenant_id": tenant_id,
            "name": "test"}


def _make_paid_tenant(tid: str = "ab5acme", budget: int = 10):
    """Bootstrap a fresh store + paid tenant; rebind globals so the
    server's _store points at our isolated DB."""
    from governance.tenancy import create_tenant
    from api import server
    s = _fresh_store()
    server._store = s
    create_tenant(s, tid, plan="PRO", unit_budget=budget)
    return s


def test_TAB23_2xx_handler_charges_budget():
    from api import server
    s = _make_paid_tenant("ab5tenant1", budget=10)
    code, _ = server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant1"), "/x",
        _stub_handler_2xx, {},
    )
    assert code == 200
    t = s.get_tenant("ab5tenant1")
    assert t["units_used"] == 1


def test_TAB24_500_handler_does_not_charge_budget():
    """Deep-eval Finding #2: 500 used to drain budget. Now it must not."""
    from api import server
    s = _make_paid_tenant("ab5tenant2", budget=10)
    code, _ = server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant2"), "/x",
        _stub_handler_500, {},
    )
    assert code == 500
    t = s.get_tenant("ab5tenant2")
    assert t["units_used"] == 0, \
        "tenant must NOT be charged on 5xx (AB-5 charge-after-success)"


def test_TAB25_4xx_handler_does_not_charge_budget():
    from api import server
    s = _make_paid_tenant("ab5tenant3", budget=10)
    code, _ = server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant3"), "/x",
        _stub_handler_400, {},
    )
    assert code == 400
    t = s.get_tenant("ab5tenant3")
    assert t["units_used"] == 0


def test_TAB26_uncaught_exception_does_not_charge_budget():
    """Exception bubbles to top-level _safe_500_envelope, no debit."""
    from api import server
    s = _make_paid_tenant("ab5tenant4", budget=10)
    with pytest.raises(RuntimeError):
        server._billed_dispatch(
            "snapshot", _key_info_for("ab5tenant4"), "/x",
            _stub_handler_raises, {},
        )
    t = s.get_tenant("ab5tenant4")
    assert t["units_used"] == 0


def test_TAB27_402_returned_when_pre_quota_exhausted():
    """Pre-flight check_quota still rejects 402 before handler runs."""
    from api import server
    s = _make_paid_tenant("ab5tenant5", budget=1)
    # Burn the one unit successfully.
    code, _ = server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant5"), "/x",
        _stub_handler_2xx, {},
    )
    assert code == 200
    # Second call: quota exhausted at pre-check; handler never runs.
    handler_ran = {"n": 0}
    def must_not_run(_data):
        handler_ran["n"] += 1
        return 200, {}
    code, info = server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant5"), "/x",
        must_not_run, {},
    )
    assert code == 402
    assert handler_ran["n"] == 0
    assert info.get("error") == "quota_exceeded"


def test_TAB28_bypass_tenant_2xx_no_charge_no_count():
    """'default' (bypass) tenant passes through, units_used stays 0."""
    from api import server
    s = _fresh_store()
    server._store = s
    code, _ = server._billed_dispatch(
        "snapshot", {"key_prefix": "uco_bypass", "tenant_id": "default"},
        "/x", _stub_handler_2xx, {},
    )
    assert code == 200
    t = s.get_tenant("default")
    # Default tenant has unit_budget=0 (unlimited ENT semantics) but
    # units_used should also remain 0 — bypass debits zero units.
    assert t["units_used"] == 0


def test_TAB29_suspended_tenant_returns_423_without_handler():
    from governance.tenancy import create_tenant, suspend_tenant
    from api import server
    s = _fresh_store()
    server._store = s
    create_tenant(s, "ab5sus", plan="PRO", unit_budget=10)
    suspend_tenant(s, "ab5sus")
    handler_ran = {"n": 0}
    def must_not_run(_data):
        handler_ran["n"] += 1
        return 200, {}
    code, info = server._billed_dispatch(
        "snapshot", _key_info_for("ab5sus"), "/x",
        must_not_run, {},
    )
    assert code == 423
    assert info.get("error") == "tenant_suspended"
    assert handler_ran["n"] == 0


def test_TAB30_500_forensic_event_recorded_units_zero():
    """Non-2xx still creates a forensic usage_event with units=0 — billing
    dashboards keep visibility of failed attempts without charging."""
    from api import server
    s = _make_paid_tenant("ab5tenant6", budget=10)
    server._billed_dispatch(
        "snapshot", _key_info_for("ab5tenant6"), "/x",
        _stub_handler_500, {},
    )
    events = s.list_usage_events_for_tenant("ab5tenant6")
    # At least one forensic event with units=0 and a non-2xx status_code.
    non_billed = [e for e in events
                  if int(e["units"]) == 0
                  and 400 <= int(e["status_code"]) < 600]
    assert non_billed, ("expected ≥1 forensic event with units=0 + "
                        f"non-2xx status; got events={events}")
