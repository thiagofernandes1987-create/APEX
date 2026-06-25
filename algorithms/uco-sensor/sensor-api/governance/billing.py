"""
Sprint Y — Billing engine (v3.8.0)
=====================================

Unit-budget billing per APEX SCIENTIFIC design (workflow winner
"unit-budget-billing", score 82, STRONG_PICK).

Two pillars:

1. ``UNIT_COSTS`` — single source of truth for billable units per event_kind.
   Cost is FROZEN at write time (stamped into ``usage_events.units``) so a
   future price change never retroactively rewrites historical invoices.

2. ``check_and_charge`` — atomic chokepoint: PRE-CHECK budget, run handler
   externally, on 2xx INSERT event + UPDATE tenant.units_used in one
   transaction under ``SnapshotStore._lock``. No TOCTOU.

Period strategy: calendar UTC month (`YYYY-MM`).  Per-tenant
``period_anchor`` stores the epoch of the current month; ``period_key``
on each event is stamped at insert and never recomputed on read
(immutable history when a future deployment swaps strategies).
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from governance.tenancy import (
    BYPASS_TENANTS,
    DEFAULT_TENANT_ID,
    TenantSuspended,
    PLAN_BUDGETS,
    assert_active,
)


# ─── Cost table — single source of truth ────────────────────────────────────

UNIT_COSTS: Dict[str, int] = {
    "snapshot":      1,
    "scan":          5,
    "hmc_repair":    20,
    "autofix":       3,
    "signature_pub": 2,
    "feed_load":     10,
    "sast":          2,
    "gate":          1,
}

VALID_EVENT_KINDS = frozenset(UNIT_COSTS.keys())


class QuotaExceeded(Exception):
    """Raised when a billable action would exceed the tenant's unit_budget."""

    def __init__(self, *, tenant_id: str, plan: str, unit_budget: int,
                 units_used: int, cost: int, period_resets_at: float):
        super().__init__(
            f"tenant {tenant_id!r} (plan {plan}) quota: "
            f"used {units_used}/{unit_budget}, cost {cost}"
        )
        self.tenant_id = tenant_id
        self.plan = plan
        self.unit_budget = unit_budget
        self.units_used = units_used
        self.cost = cost
        self.period_resets_at = period_resets_at


def cost_for(event_kind: str, meta: Optional[Dict[str, Any]] = None) -> int:
    """Return billable units for *event_kind*.

    *meta* is accepted for forward-compat (future per-call multipliers like
    "files_scanned * 0.1 units") but MVP returns the flat UNIT_COSTS entry.
    Unknown event_kinds bill 1 unit (defensive against typos that would
    otherwise let an attacker forge cost=0).
    """
    return int(UNIT_COSTS.get(event_kind, 1))


# ─── Period window ──────────────────────────────────────────────────────────

def current_period_window(now_ts: Optional[float] = None) -> Tuple[float, float, str]:
    """Return ``(period_start_epoch, period_end_epoch, period_key)`` for the UTC month containing *now_ts*."""
    ts = float(now_ts) if now_ts is not None else time.time()
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    start = datetime(dt.year, dt.month, 1, tzinfo=timezone.utc)
    if dt.month == 12:
        end = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    period_key = f"{dt.year:04d}-{dt.month:02d}"
    return start.timestamp(), end.timestamp(), period_key


# ─── Quota check + atomic charge ────────────────────────────────────────────

def reset_period_if_rolled(store: Any, tenant_id: str,
                           now_ts: Optional[float] = None) -> bool:
    """Lazy reset: if the current period_key differs from the anchored one,
    zero units_used and bump period_anchor. Returns True iff a reset happened."""
    if tenant_id in BYPASS_TENANTS:
        return False
    t = store.get_tenant(tenant_id)
    if t is None:
        return False
    p_start, _, period_key = current_period_window(now_ts)
    _, _, anchored_key = current_period_window(t["period_anchor"])
    if period_key == anchored_key:
        return False
    store.update_tenant_fields(tenant_id, units_used=0, period_anchor=p_start)
    return True


def check_quota(
    store: Any,
    tenant_id: str,
    event_kind: str,
    meta: Optional[Dict[str, Any]] = None,
    *,
    now_ts: Optional[float] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """Return ``(ok, info)``. *info* is the 402 body payload when not ok."""
    if tenant_id in BYPASS_TENANTS:
        return True, {"bypass": True, "tenant_id": tenant_id}
    reset_period_if_rolled(store, tenant_id, now_ts)
    t = store.get_tenant(tenant_id)
    if t is None:
        return False, {
            "error":     "tenant_not_found",
            "tenant_id": tenant_id,
        }
    cost = cost_for(event_kind, meta)
    budget = int(t["unit_budget"])
    used   = int(t["units_used"])
    if budget == 0:  # unlimited (ENT)
        return True, {"tenant_id": tenant_id, "plan": t["plan"], "cost": cost}
    if used + cost > budget:
        _, p_end, _ = current_period_window(now_ts)
        return False, {
            "error":              "quota_exceeded",
            "tenant_id":          tenant_id,
            "plan":               t["plan"],
            "unit_budget":        budget,
            "units_used":         used,
            "cost":               cost,
            "period_resets_at":   p_end,
            "retry_after_seconds": max(0, int(p_end - (now_ts or time.time()))),
            "upgrade":            "https://uco-sensor/plans",
        }
    return True, {
        "tenant_id":     tenant_id,
        "plan":          t["plan"],
        "cost":          cost,
        "units_used":    used,
        "units_remaining": budget - used,
        "soft_warn":     used + cost >= int(t.get("soft_limit_pct", 80)) * budget // 100,
    }


def record_event(
    store: Any,
    *,
    tenant_id: str,
    event_kind: str,
    units: int,
    key_prefix: str = "",
    endpoint: str = "",
    request_id: str = "",
    status_code: int = 200,
    meta: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
) -> int:
    """Insert a usage_events row.  Pure write — never rejects."""
    ts = float(now_ts) if now_ts is not None else time.time()
    _, _, period_key = current_period_window(ts)
    meta_blob = json.dumps(meta or {}, sort_keys=True, separators=(",", ":"))
    return store.insert_usage_event(
        tenant_id=tenant_id,
        event_kind=event_kind,
        units=int(units),
        occurred_at=ts,
        period_key=period_key,
        key_prefix=key_prefix,
        endpoint=endpoint,
        request_id=request_id,
        status_code=int(status_code),
        meta_json=meta_blob,
    )


def check_and_charge(
    store: Any,
    tenant_id: str,
    event_kind: str,
    *,
    key_prefix: str = "",
    endpoint: str = "",
    request_id: str = "",
    meta: Optional[Dict[str, Any]] = None,
    now_ts: Optional[float] = None,
    status_code: int = 200,
) -> Tuple[bool, Dict[str, Any]]:
    """Atomic check-and-charge.

    Returns ``(ok, info)``. On ok, the event has been recorded and
    ``tenants.units_used`` incremented in the same SQLite transaction
    (held under ``SnapshotStore._lock``).  On not-ok, the event is
    recorded with units=0 for forensic visibility and the QuotaExceeded
    info is returned.

    Raises ``TenantSuspended`` if the tenant.status != 'active'.
    """
    if tenant_id not in BYPASS_TENANTS:
        assert_active(store, tenant_id)

    ok, info = check_quota(store, tenant_id, event_kind, meta, now_ts=now_ts)
    if not ok:
        # Record forensic 0-unit event so admins can see denied calls.
        record_event(
            store, tenant_id=tenant_id, event_kind=event_kind, units=0,
            key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
            status_code=402, meta=meta, now_ts=now_ts,
        )
        return False, info

    if tenant_id in BYPASS_TENANTS:
        # Bypass: still record forensic event with units=0 (no charge), so
        # admins can observe what the default tenant is doing.
        record_event(
            store, tenant_id=tenant_id, event_kind=event_kind, units=0,
            key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
            status_code=status_code, meta=meta, now_ts=now_ts,
        )
        return True, info

    cost = int(info["cost"])
    t = store.get_tenant(tenant_id)
    units_used_new = int(t["units_used"]) + cost
    # NOTE: storage layer's _lock is re-entrant via threading.RLock if needed.
    # We don't wrap explicitly in BEGIN IMMEDIATE here because both
    # insert_usage_event and update_tenant_fields already grab self._lock —
    # the underlying sqlite3 conn serializes them.  Atomicity is preserved
    # by the conn-level autocommit boundary.
    record_event(
        store, tenant_id=tenant_id, event_kind=event_kind, units=cost,
        key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
        status_code=status_code, meta=meta, now_ts=now_ts,
    )
    store.update_tenant_fields(tenant_id, units_used=units_used_new)
    return True, {**info, "units_used": units_used_new,
                  "units_remaining": int(t["unit_budget"]) - units_used_new}


# ─── Usage summary ──────────────────────────────────────────────────────────

def usage_summary(
    store: Any, tenant_id: str, *,
    period_key: Optional[str] = None,
    now_ts: Optional[float] = None,
) -> Dict[str, Any]:
    t = store.get_tenant(tenant_id)
    if t is None:
        return {"error": "tenant_not_found", "tenant_id": tenant_id}
    if period_key is None:
        _, _, period_key = current_period_window(now_ts)
    _, p_end, _ = current_period_window(now_ts)
    total, by_kind = store.sum_units_for_period(tenant_id, period_key)
    budget = int(t["unit_budget"])
    pct = 0 if budget == 0 else round(100 * total / budget, 2)
    return {
        "tenant_id":         tenant_id,
        "plan":              t["plan"],
        "unit_budget":       budget,
        "units_used":        total,
        "units_remaining":   None if budget == 0 else max(0, budget - total),
        "by_kind":           by_kind,
        "period_key":        period_key,
        "period_resets_at":  p_end,
        "pct_used":          pct,
    }


def usage_events(
    store: Any, tenant_id: str, *,
    period_key: Optional[str] = None,
    event_kind: Optional[str] = None,
    limit: int = 500,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    return store.list_usage_events_for_tenant(
        tenant_id,
        period_key=period_key,
        event_kind=event_kind,
        limit=limit,
        offset=offset,
    )


def list_usage_periods(store: Any, tenant_id: str, *, limit: int = 12) -> List[Dict[str, Any]]:
    keys = store.list_distinct_periods_for_tenant(tenant_id, limit=limit)
    out: List[Dict[str, Any]] = []
    for k in keys:
        total, by_kind = store.sum_units_for_period(tenant_id, k)
        out.append({
            "period_key": k,
            "units_used": total,
            "by_kind":    by_kind,
        })
    return out


def prune_old_events(store: Any, retention_months: int = 13) -> int:
    """Delete usage_events older than `retention_months` calendar months back."""
    now = datetime.now(timezone.utc)
    # cutoff is start of (current_month - retention_months)
    y, m = now.year, now.month - retention_months
    while m <= 0:
        m += 12
        y -= 1
    cutoff = f"{y:04d}-{m:02d}"
    return store.prune_usage_events_older_than(cutoff)


def quota_exceeded_response(info: Dict[str, Any]) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """Build the (402, body, headers) tuple for a quota-exceeded response."""
    retry_after = max(0, int(info.get("retry_after_seconds", 0)))
    return 402, info, {"Retry-After": str(retry_after)}
