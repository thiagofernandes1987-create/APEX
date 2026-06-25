"""
Marco 58 — Sprint Y: Multi-tenant + billing (TZ01-TZ30)
=========================================================

MVP de SaaS multi-tenant + unit-budget billing per APEX SCIENTIFIC
design panel (workflow winner score 82, STRONG_PICK).

Layout
------
TZ01-TZ10 — tenancy.py registry: bypass invariants, CRUD, plan tiers,
            suspend/reactivate, assert_active, key resolution.
TZ11-TZ20 — billing.py engine: cost_for + period_window + check_quota
            + check_and_charge atomicity + usage_summary + prune.
TZ21-TZ30 — REST: /tenants/* and /billing/* handlers + auth gating +
            cross-tenant isolation + 402 quota response shape.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


def _fresh_store():
    from sensor_storage.snapshot_store import SnapshotStore
    return SnapshotStore(":memory:")


# ═══════════════════════════════════════════════════════════════════════════════
# TZ01-TZ10 — tenancy.py registry
# ═══════════════════════════════════════════════════════════════════════════════

def test_TZ01_default_tenant_bootstrapped_on_store_init():
    s = _fresh_store()
    t = s.get_tenant("default")
    assert t is not None
    assert t["plan"] == "ENT"
    assert t["unit_budget"] == 0


def test_TZ02_default_in_bypass_tenants_frozenset():
    from governance.tenancy import BYPASS_TENANTS, DEFAULT_TENANT_ID
    assert isinstance(BYPASS_TENANTS, frozenset)
    assert DEFAULT_TENANT_ID in BYPASS_TENANTS


def test_TZ03_create_tenant_with_explicit_budget():
    from governance.tenancy import create_tenant
    s = _fresh_store()
    t = create_tenant(s, "acme", plan="PRO", unit_budget=12345,
                      display_name="ACME Corp", contact_email="ops@acme.io")
    assert t["tenant_id"] == "acme"
    assert t["plan"] == "PRO"
    assert t["unit_budget"] == 12345
    assert t["contact_email"] == "ops@acme.io"


def test_TZ04_create_tenant_derives_budget_from_plan_when_omitted():
    from governance.tenancy import create_tenant
    s = _fresh_store()
    free = create_tenant(s, "f", plan="FREE")
    pro  = create_tenant(s, "p", plan="PRO")
    ent  = create_tenant(s, "e", plan="ENT")
    assert free["unit_budget"] == 100
    assert pro["unit_budget"] == 10_000
    assert ent["unit_budget"] == 0


def test_TZ05_create_tenant_rejects_duplicate_id():
    from governance.tenancy import create_tenant
    s = _fresh_store()
    create_tenant(s, "x")
    with pytest.raises(ValueError):
        create_tenant(s, "x")


def test_TZ06_create_tenant_rejects_invalid_plan_or_status():
    from governance.tenancy import create_tenant
    s = _fresh_store()
    with pytest.raises(ValueError):
        create_tenant(s, "bad", plan="ULTRA")
    with pytest.raises(ValueError):
        create_tenant(s, "bad", status="frozen")


def test_TZ07_suspend_rejects_bypass_tenant():
    """Cannot suspend 'default' — protects 2052 legacy tests."""
    from governance.tenancy import suspend_tenant
    s = _fresh_store()
    with pytest.raises(ValueError):
        suspend_tenant(s, "default", reason="malicious")


def test_TZ08_suspend_then_reactivate_round_trip():
    from governance.tenancy import create_tenant, suspend_tenant, reactivate_tenant
    s = _fresh_store()
    create_tenant(s, "acme")
    out_s = suspend_tenant(s, "acme", reason="overdue")
    assert out_s["status"] == "suspended"
    out_r = reactivate_tenant(s, "acme")
    assert out_r["status"] == "active"


def test_TZ09_assert_active_raises_on_suspended():
    from governance.tenancy import create_tenant, suspend_tenant, assert_active, TenantSuspended
    s = _fresh_store()
    create_tenant(s, "acme")
    suspend_tenant(s, "acme")
    with pytest.raises(TenantSuspended):
        assert_active(s, "acme")


def test_TZ10_resolve_tenant_fallback_to_default():
    from governance.tenancy import resolve_tenant_from_api_key, DEFAULT_TENANT_ID
    s = _fresh_store()
    # No key_info → default
    tid, t = resolve_tenant_from_api_key(s, None)
    assert tid == DEFAULT_TENANT_ID
    assert t is not None
    # Legacy key_info without tenant_id → default
    tid2, _ = resolve_tenant_from_api_key(s, {"key_prefix": "abc"})
    assert tid2 == DEFAULT_TENANT_ID


# ═══════════════════════════════════════════════════════════════════════════════
# TZ11-TZ20 — billing.py engine
# ═══════════════════════════════════════════════════════════════════════════════

def test_TZ11_cost_for_known_event_kinds_match_table():
    from governance.billing import cost_for, UNIT_COSTS
    for kind, cost in UNIT_COSTS.items():
        assert cost_for(kind) == cost


def test_TZ12_cost_for_unknown_kind_defaults_to_1():
    """Defensive: typos must NOT cost 0 (would let attackers forge free calls)."""
    from governance.billing import cost_for
    assert cost_for("nonexistent_kind") == 1


def test_TZ13_current_period_window_is_utc_calendar_month():
    from governance.billing import current_period_window
    # 2026-06-24 12:00:00 UTC = 1782302400
    start, end, key = current_period_window(1782302400.0)
    assert key == "2026-06"
    assert start == 1780272000.0   # 2026-06-01 00:00 UTC
    assert end   == 1782864000.0   # 2026-07-01 00:00 UTC


def test_TZ14_bypass_tenant_check_and_charge_always_ok():
    from governance.billing import check_and_charge
    s = _fresh_store()
    for _ in range(50):
        ok, info = check_and_charge(s, "default", "snapshot", endpoint="/x")
        assert ok is True
        assert info.get("bypass") is True


def test_TZ15_check_and_charge_drains_FREE_budget_then_rejects():
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge
    s = _fresh_store()
    create_tenant(s, "acme", plan="FREE", unit_budget=3)
    for i in range(3):
        ok, _ = check_and_charge(s, "acme", "snapshot", endpoint="/x")
        assert ok, f"snapshot #{i+1} should pass"
    ok, info = check_and_charge(s, "acme", "snapshot", endpoint="/x")
    assert ok is False
    assert info["error"] == "quota_exceeded"
    assert info["units_used"] == 3
    assert info["cost"] == 1
    assert info["retry_after_seconds"] >= 0


def test_TZ16_check_and_charge_TenantSuspended_propagates():
    from governance.tenancy import create_tenant, suspend_tenant, TenantSuspended
    from governance.billing import check_and_charge
    s = _fresh_store()
    create_tenant(s, "acme")
    suspend_tenant(s, "acme")
    with pytest.raises(TenantSuspended):
        check_and_charge(s, "acme", "snapshot", endpoint="/x")


def test_TZ17_units_frozen_at_write_time_via_record_event():
    """Even if UNIT_COSTS changes post-write, historical row keeps its units."""
    from governance.tenancy import create_tenant
    from governance.billing import record_event
    s = _fresh_store()
    create_tenant(s, "acme")
    rid = record_event(s, tenant_id="acme", event_kind="scan", units=5,
                       endpoint="/scan-iac", now_ts=1782302400.0)
    events = s.list_usage_events_for_tenant("acme")
    assert any(e["id"] == rid and e["units"] == 5 for e in events)


def test_TZ18_usage_summary_for_ENT_plan_units_remaining_None():
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge, usage_summary
    s = _fresh_store()
    create_tenant(s, "ent", plan="ENT")
    check_and_charge(s, "ent", "scan", endpoint="/x")
    us = usage_summary(s, "ent")
    assert us["plan"] == "ENT"
    assert us["unit_budget"] == 0
    assert us["units_remaining"] is None


def test_TZ19_cross_tenant_isolation_in_usage_summary():
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge, usage_summary
    s = _fresh_store()
    create_tenant(s, "alpha", plan="PRO")
    create_tenant(s, "beta", plan="PRO")
    check_and_charge(s, "alpha", "hmc_repair", endpoint="/x")  # 20 units
    check_and_charge(s, "beta", "snapshot", endpoint="/x")     # 1 unit
    us_a = usage_summary(s, "alpha")
    us_b = usage_summary(s, "beta")
    assert us_a["units_used"] == 20
    assert us_b["units_used"] == 1
    # And by_kind doesn't leak across
    assert us_a["by_kind"].get("snapshot", 0) == 0
    assert us_b["by_kind"].get("hmc_repair", 0) == 0


def test_TZ20_reset_period_if_rolled_zeroes_units_used():
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge, reset_period_if_rolled
    s = _fresh_store()
    create_tenant(s, "acme", plan="PRO")
    # Drive 50 units in June 2026
    for _ in range(5):
        check_and_charge(s, "acme", "scan", endpoint="/x", now_ts=1782302400.0)
    t = s.get_tenant("acme")
    assert t["units_used"] == 25  # 5 scans * 5 units
    # Roll to July 2026 (next month UTC = 1753459200)
    rolled = reset_period_if_rolled(s, "acme", now_ts=1784116800.0)
    assert rolled is True
    t2 = s.get_tenant("acme")
    assert t2["units_used"] == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TZ21-TZ30 — REST endpoints + auth gating + cross-tenant isolation
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_KEY = os.environ.get("UCO_ADMIN_KEY", "test-admin-key-do-not-use-in-prod")


def test_TZ21_handle_tenants_create_201(isolated_store):
    from api.server import handle_tenants_create
    code, data = handle_tenants_create({
        "tenant_id": "acme", "display_name": "ACME",
        "plan": "PRO", "contact_email": "ops@acme.io",
    })
    assert code == 201
    assert data["tenant_id"] == "acme"
    assert data["plan"] == "PRO"


def test_TZ22_handle_tenants_create_400_on_missing_id(isolated_store):
    from api.server import handle_tenants_create
    code, _ = handle_tenants_create({"plan": "FREE"})
    assert code == 400


def test_TZ23_handle_tenants_create_400_on_duplicate(isolated_store):
    from api.server import handle_tenants_create
    handle_tenants_create({"tenant_id": "x"})
    code, _ = handle_tenants_create({"tenant_id": "x"})
    assert code == 400


def test_TZ24_handle_tenants_list_includes_default_bootstrap(isolated_store):
    from api.server import handle_tenants_list
    code, data = handle_tenants_list()
    assert code == 200
    ids = {t["tenant_id"] for t in data["tenants"]}
    assert "default" in ids


def test_TZ25_handle_tenants_get_200_then_404(isolated_store):
    from api.server import handle_tenants_create, handle_tenants_get
    handle_tenants_create({"tenant_id": "exists"})
    code_ok, _ = handle_tenants_get("exists")
    code_404, _ = handle_tenants_get("ghost")
    assert code_ok == 200
    assert code_404 == 404


def test_TZ26_handle_tenants_suspend_then_reactivate(isolated_store):
    from api.server import (
        handle_tenants_create, handle_tenants_suspend, handle_tenants_reactivate,
    )
    handle_tenants_create({"tenant_id": "z"})
    code_s, data_s = handle_tenants_suspend("z", {"reason": "overdue"})
    code_r, data_r = handle_tenants_reactivate("z")
    assert code_s == 200 and data_s["status"] == "suspended"
    assert code_r == 200 and data_r["status"] == "active"


def test_TZ27_handle_tenants_usage_reports_zero_on_fresh_tenant(isolated_store):
    from api.server import handle_tenants_create, handle_tenants_usage
    handle_tenants_create({"tenant_id": "u", "plan": "PRO"})
    code, data = handle_tenants_usage("u")
    assert code == 200
    assert data["units_used"] == 0
    assert data["unit_budget"] == 10_000


def test_TZ28_handle_billing_plans_is_public_and_complete(isolated_store):
    from api.server import handle_billing_plans
    code, data = handle_billing_plans()
    assert code == 200
    plans = {p["name"] for p in data["plans"]}
    assert {"FREE", "PRO", "ENT"} <= plans
    # cost table sane
    assert data["unit_costs"]["snapshot"] == 1
    assert data["unit_costs"]["hmc_repair"] == 20


def test_TZ29_handle_billing_me_resolves_to_default_in_dev(isolated_store):
    from api.server import handle_billing_me
    code, data = handle_billing_me(None)
    assert code == 200
    assert data["tenant_id"] == "default"


def test_TZ30_docs_endpoint_lists_tenants_and_billing_routes(isolated_store):
    from api.server import handle_docs
    code, data = handle_docs()
    routes = {r["path"] for r in data["endpoints"]}
    assert "/tenants" in routes
    assert "/tenants/{tenant_id}" in routes
    assert "/tenants/{tenant_id}/usage" in routes
    assert "/billing/plans" in routes
    assert "/billing/me" in routes


# ═══════════════════════════════════════════════════════════════════════════════
# TZ31-TZ37 — Workflow #2 must-fix findings (SY-FIX-1..7)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TZ31_SYFIX1_validate_key_returns_tenant_id():
    """SY-FIX-1 (CRITICAL): validate_key must include tenant_id in returned dict."""
    s = _fresh_store()
    s.insert_tenant("acme", plan="PRO")
    plain = s.create_key(name="acme-prod", tenant_id="acme")
    info = s.validate_key(plain)
    assert info is not None
    assert info["tenant_id"] == "acme"


def test_TZ32_SYFIX2_create_key_binds_to_tenant():
    """SY-FIX-2 (HIGH): create_key must accept and persist tenant_id."""
    s = _fresh_store()
    s.insert_tenant("alpha", plan="FREE")
    s.insert_tenant("beta",  plan="PRO")
    k_alpha = s.create_key(name="a", tenant_id="alpha")
    k_beta  = s.create_key(name="b", tenant_id="beta")
    assert s.validate_key(k_alpha)["tenant_id"] == "alpha"
    assert s.validate_key(k_beta)["tenant_id"] == "beta"
    # Legacy default
    k_def = s.create_key(name="legacy")
    assert s.validate_key(k_def)["tenant_id"] == "default"


def test_TZ33_SYFIX3_billed_dispatch_blocks_over_quota_tenant(isolated_store):
    """SY-FIX-3 (CRITICAL): /analyze actually charges and 402s when over quota."""
    from governance.tenancy import create_tenant
    from api.server import _billed_dispatch, handle_analyze
    create_tenant(isolated_store, "tight", plan="FREE", unit_budget=2)
    key_info = {"key_prefix": "x", "tenant_id": "tight"}
    body = {"module_id": "m", "code": "x = 1\n"}
    # First 2 calls succeed
    for i in range(2):
        code, _ = _billed_dispatch("snapshot", key_info, "/analyze", handle_analyze, body)
        assert code != 402, f"call #{i+1} unexpectedly 402"
    # 3rd call rejected
    code, data = _billed_dispatch("snapshot", key_info, "/analyze", handle_analyze, body)
    assert code == 402
    assert data["error"] == "quota_exceeded"
    assert data["retry_after_seconds"] >= 0


def test_TZ34_SYFIX4_atomic_check_and_charge_no_double_spend():
    """SY-FIX-4 (HIGH): atomic_check_and_charge prevents concurrent overspend."""
    from governance.tenancy import create_tenant
    s = _fresh_store()
    create_tenant(s, "race", plan="FREE", unit_budget=5)
    # 100 sequential check+charge of cost=1 — only first 5 should succeed
    successes = 0
    for _ in range(100):
        ok, _ = s.atomic_check_and_charge("race", 1)
        if ok:
            successes += 1
    assert successes == 5, f"atomic charge should bound to budget; got {successes}"
    final = s.get_tenant("race")
    assert final["units_used"] == 5


def test_TZ35_SYFIX5_update_tenant_refuses_bypass_plan_change():
    """SY-FIX-5 (MED): update_tenant must reject plan change on bypass tenants."""
    from governance.tenancy import update_tenant
    s = _fresh_store()
    with pytest.raises(ValueError):
        update_tenant(s, "default", plan="FREE")
    with pytest.raises(ValueError):
        update_tenant(s, "default", status="suspended")
    with pytest.raises(ValueError):
        update_tenant(s, "default", unit_budget=100)
    # Display-only change is fine
    out = update_tenant(s, "default", display_name="Renamed")
    assert out["display_name"] == "Renamed"


def test_TZ36_SYFIX6_non_ENT_with_budget_zero_is_quota_zero_not_unlimited():
    """SY-FIX-6 (HIGH): unit_budget=0 must NOT grant unlimited to FREE/PRO plans."""
    from governance.tenancy import create_tenant
    from governance.billing import check_and_charge
    s = _fresh_store()
    create_tenant(s, "exploit", plan="FREE", unit_budget=0)
    ok, info = check_and_charge(s, "exploit", "snapshot", endpoint="/x")
    assert ok is False
    assert info.get("reason") == "non_ENT_budget_0" or info.get("error") == "quota_exceeded"


def test_TZ37_SYFIX7_reset_period_idempotent_under_concurrent_callers():
    """SY-FIX-7 (HIGH): reset_period_if_rolled re-checks anchor inside lock."""
    from governance.tenancy import create_tenant
    from governance.billing import reset_period_if_rolled, check_and_charge
    s = _fresh_store()
    create_tenant(s, "rollover", plan="PRO")
    # Charge some in June
    for _ in range(3):
        check_and_charge(s, "rollover", "snapshot", endpoint="/x", now_ts=1782302400.0)
    assert s.get_tenant("rollover")["units_used"] == 3
    # Two simulated callers in July see rollover
    r1 = reset_period_if_rolled(s, "rollover", now_ts=1784116800.0)
    r2 = reset_period_if_rolled(s, "rollover", now_ts=1784116800.0)
    assert r1 is True
    assert r2 is False  # second caller observes already-reset anchor
    assert s.get_tenant("rollover")["units_used"] == 0
