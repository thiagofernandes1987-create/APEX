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
    zero units_used and bump period_anchor. Returns True iff a reset happened.

    Sprint Y SY-FIX-7: the read-then-write happens under SnapshotStore._lock
    (insert_usage_event + update_tenant_fields both grab the same lock).  For
    a stronger guarantee that two concurrent rollers don't both reset, the
    underlying SQLite ``BEGIN IMMEDIATE`` is implicit on the first write.
    """
    if tenant_id in BYPASS_TENANTS:
        return False
    t = store.get_tenant(tenant_id)
    if t is None:
        return False
    p_start, _, period_key = current_period_window(now_ts)
    _, _, anchored_key = current_period_window(t["period_anchor"])
    if period_key == anchored_key:
        return False
    # Re-check inside the same logical critical section by re-reading anchor.
    # SnapshotStore._lock serializes the read+update, so two callers cannot
    # both observe the stale anchor and both reset.
    t2 = store.get_tenant(tenant_id)
    _, _, anchored_key2 = current_period_window(t2["period_anchor"])
    if anchored_key2 == period_key:
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
    # Sprint Y SY-FIX-6: unit_budget=0 means UNLIMITED, but only when the
    # tenant is explicitly on the ENT plan.  A FREE/PRO tenant accidentally
    # written with budget=0 (e.g. PATCH /tenants/{id} {unit_budget: 0}) must
    # NOT be granted unlimited service — that would be a privilege escalation.
    if budget == 0:
        if t["plan"] == "ENT":
            return True, {"tenant_id": tenant_id, "plan": t["plan"], "cost": cost}
        # budget=0 on non-ENT plan → treat as quota-0, reject ALL billable calls
        _, p_end, _ = current_period_window(now_ts)
        return False, {
            "error":             "quota_exceeded",
            "tenant_id":         tenant_id,
            "plan":              t["plan"],
            "unit_budget":       0,
            "units_used":        used,
            "cost":              cost,
            "period_resets_at":  p_end,
            "retry_after_seconds": max(0, int(p_end - (now_ts or time.time()))),
            "upgrade":           "https://uco-sensor/plans",
            "reason":            "non_ENT_budget_0",
        }
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
    # Sprint Z v3.8.1-fix-5 — float arithmetic; integer-floor previously
    # delayed soft_warn firing by up to ~1 unit on large budgets.
    soft_pct = float(t.get("soft_limit_pct", 80)) / 100.0
    soft_threshold = soft_pct * budget  # float
    return True, {
        "tenant_id":     tenant_id,
        "plan":          t["plan"],
        "cost":          cost,
        "units_used":    used,
        "units_remaining": budget - used,
        "soft_warn":     (used + cost) >= soft_threshold,
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
    # Bypass tenants short-circuit BEFORE any quota math.
    if tenant_id in BYPASS_TENANTS:
        record_event(
            store, tenant_id=tenant_id, event_kind=event_kind, units=0,
            key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
            status_code=status_code, meta=meta, now_ts=now_ts,
        )
        return True, {"bypass": True, "tenant_id": tenant_id,
                      "plan": "ENT", "cost": 0}

    # Lazy period reset before the atomic charge.
    reset_period_if_rolled(store, tenant_id, now_ts)

    cost = cost_for(event_kind, meta)
    # Sprint Y SY-FIX-4: single-acquire atomic check+UPDATE eliminates TOCTOU
    # between check_quota and the subsequent UPDATE units_used.
    ok, info = store.atomic_check_and_charge(tenant_id, cost)

    if not ok and info.get("error") == "tenant_suspended":
        # Record forensic 423-status event and raise structured exception.
        record_event(
            store, tenant_id=tenant_id, event_kind=event_kind, units=0,
            key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
            status_code=423, meta=meta, now_ts=now_ts,
        )
        raise TenantSuspended(tenant_id, info.get("status", "suspended"))

    if not ok:
        # quota_exceeded or tenant_not_found — enrich with period info + record forensic.
        _, p_end, _ = current_period_window(now_ts)
        info["period_resets_at"]   = p_end
        info["retry_after_seconds"] = max(0, int(p_end - (now_ts or time.time())))
        info["upgrade"]            = "https://uco-sensor/plans"
        record_event(
            store, tenant_id=tenant_id, event_kind=event_kind, units=0,
            key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
            status_code=402, meta=meta, now_ts=now_ts,
        )
        return False, info

    # ok=True: append the billable event row.
    record_event(
        store, tenant_id=tenant_id, event_kind=event_kind, units=cost,
        key_prefix=key_prefix, endpoint=endpoint, request_id=request_id,
        status_code=status_code, meta=meta, now_ts=now_ts,
    )
    return True, info


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
    """Sprint Z v3.8.1-fix-2: single SQL aggregation replaces the prior
    1+N round-trips (one DISTINCT + one SUM per period).  For ``limit=12``
    that was 13 queries; now it is 1.
    """
    rows = store.sum_units_by_period_and_kind(tenant_id, limit_periods=limit)
    if not rows:
        return []
    grouped: Dict[str, Dict[str, Any]] = {}
    for period_key, event_kind, units in rows:
        bucket = grouped.setdefault(
            period_key, {"period_key": period_key, "units_used": 0, "by_kind": {}}
        )
        bucket["by_kind"][event_kind] = units
        bucket["units_used"] += units
    # Preserve order (DESC by period_key) from the SQL.
    return [grouped[p] for p in dict.fromkeys(r[0] for r in rows)]


def prune_old_events(store: Any, retention_months: int = 13,
                     *, vacuum: bool = False) -> int:
    """Delete usage_events older than `retention_months` calendar months back.

    Sprint Z v3.8.1-fix-4 — pass ``vacuum=True`` to run SQLite ``VACUUM`` after
    the delete so the underlying file shrinks.  Default False because VACUUM
    rewrites the whole database file (expensive) — only do it in nightly cron.
    """
    now = datetime.now(timezone.utc)
    y, m = now.year, now.month - retention_months
    while m <= 0:
        m += 12
        y -= 1
    cutoff = f"{y:04d}-{m:02d}"
    deleted = store.prune_usage_events_older_than(cutoff)
    if vacuum and deleted > 0:
        try:
            store.vacuum()
        except Exception:
            pass  # best-effort; never fail prune on vacuum error
    return deleted


def quota_exceeded_response(info: Dict[str, Any]) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
    """Build the (402, body, headers) tuple for a quota-exceeded response."""
    retry_after = max(0, int(info.get("retry_after_seconds", 0)))
    return 402, info, {"Retry-After": str(retry_after)}
