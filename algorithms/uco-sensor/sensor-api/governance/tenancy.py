"""
Sprint Y — Multi-tenancy (v3.8.0)
====================================

Tenant registry + plan tier helpers + API-key resolution.

Hardened invariants (APEX SCIENTIFIC design panel verdict STRONG_PICK):

* ``DEFAULT_TENANT_ID = "default"`` is the bootstrap tenant; it always
  exists (idempotent INSERT at schema init) and lives in ``BYPASS_TENANTS``.
* ``BYPASS_TENANTS`` is a HARDCODED ``frozenset`` — it cannot be disabled
  via a DB UPDATE. This protects the 2052 legacy tests + single-tenant
  deployments from accidental quota lockout.
* All write operations on the tenant registry are admin-only at the REST
  layer; the storage helpers do not enforce auth themselves.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


DEFAULT_TENANT_ID: str = "default"
BYPASS_TENANTS: frozenset = frozenset({"default"})

VALID_PLANS = ("FREE", "PRO", "ENT")
VALID_STATUSES = ("active", "suspended", "trial", "cancelled")


class TenantSuspended(Exception):
    """Raised when a billable action is attempted on a non-active tenant."""

    def __init__(self, tenant_id: str, status: str):
        super().__init__(f"tenant {tenant_id!r} is {status}")
        self.tenant_id = tenant_id
        self.status = status


# ─── Plan tiers ──────────────────────────────────────────────────────────────

PLAN_BUDGETS: Dict[str, int] = {
    "FREE":  100,
    "PRO":   10_000,
    "ENT":   0,   # 0 = unlimited
}


def plan_budget(plan: str) -> int:
    return PLAN_BUDGETS.get(plan, PLAN_BUDGETS["FREE"])


# ─── Tenant CRUD wrappers ────────────────────────────────────────────────────

def create_tenant(
    store: Any,
    tenant_id: str,
    *,
    display_name: str = "",
    plan: str = "FREE",
    unit_budget: Optional[int] = None,
    contact_email: str = "",
    status: str = "active",
    soft_limit_pct: int = 80,
    notes: str = "",
) -> Dict[str, Any]:
    tenant_id = (tenant_id or "").strip()
    if not tenant_id:
        raise ValueError("tenant_id is required")
    if plan not in VALID_PLANS:
        raise ValueError(f"plan must be one of {VALID_PLANS}")
    if status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")
    if store.get_tenant(tenant_id):
        raise ValueError(f"tenant {tenant_id!r} already exists")
    budget = plan_budget(plan) if unit_budget is None else int(unit_budget)
    return store.insert_tenant(
        tenant_id,
        display_name=display_name,
        plan=plan,
        unit_budget=budget,
        soft_limit_pct=int(soft_limit_pct),
        status=status,
        contact_email=contact_email,
        notes=notes,
    )


def get_tenant(store: Any, tenant_id: str) -> Optional[Dict[str, Any]]:
    return store.get_tenant(tenant_id)


def list_tenants(
    store: Any,
    *,
    plan: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    return store.list_tenants(plan=plan, status=status, limit=limit, offset=offset)


def update_tenant(
    store: Any,
    tenant_id: str,
    *,
    display_name: Optional[str] = None,
    plan: Optional[str] = None,
    unit_budget: Optional[int] = None,
    status: Optional[str] = None,
    soft_limit_pct: Optional[int] = None,
    contact_email: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if plan is not None and plan not in VALID_PLANS:
        raise ValueError(f"plan must be one of {VALID_PLANS}")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"status must be one of {VALID_STATUSES}")
    # Sprint Y SY-FIX-5: BYPASS_TENANTS invariant cannot be broken via PATCH.
    # Refuse to change plan/status/unit_budget on the bypass tenants so an
    # admin cannot accidentally (or maliciously) flip 'default' to a FREE-100
    # quota and brick the 2052 legacy tests + every single-tenant deployment.
    if tenant_id in BYPASS_TENANTS:
        if plan is not None and plan != "ENT":
            raise ValueError(
                f"cannot change plan on bypass tenant {tenant_id!r}"
            )
        if status is not None and status != "active":
            raise ValueError(
                f"cannot change status on bypass tenant {tenant_id!r}"
            )
        if unit_budget is not None and unit_budget != 0:
            raise ValueError(
                f"cannot change unit_budget on bypass tenant {tenant_id!r}"
            )
    return store.update_tenant_fields(
        tenant_id,
        display_name=display_name,
        plan=plan,
        unit_budget=unit_budget,
        status=status,
        soft_limit_pct=soft_limit_pct,
        contact_email=contact_email,
        notes=notes,
    )


def suspend_tenant(store: Any, tenant_id: str, *, reason: str = "") -> Optional[Dict[str, Any]]:
    if tenant_id in BYPASS_TENANTS:
        raise ValueError(f"refusing to suspend bypass tenant {tenant_id!r}")
    notes_now = f"suspended: {reason}" if reason else "suspended"
    return store.update_tenant_fields(tenant_id, status="suspended", notes=notes_now)


def reactivate_tenant(store: Any, tenant_id: str) -> Optional[Dict[str, Any]]:
    return store.update_tenant_fields(tenant_id, status="active", notes="")


def assert_active(store: Any, tenant_id: str) -> None:
    """Raise TenantSuspended if tenant.status != 'active'. Bypass tenants always OK."""
    if tenant_id in BYPASS_TENANTS:
        return
    t = store.get_tenant(tenant_id)
    if t is None:
        raise TenantSuspended(tenant_id, "not_found")
    if t["status"] != "active":
        raise TenantSuspended(tenant_id, t["status"])


# ─── Resolution ──────────────────────────────────────────────────────────────

def resolve_tenant_from_api_key(
    store: Any, key_info: Optional[Dict[str, Any]],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Return (tenant_id, tenant_row).

    * If ``key_info`` is None (no auth / dev mode), returns DEFAULT_TENANT_ID.
    * If ``key_info`` carries a ``tenant_id`` field (post-Sprint-Y keys),
      resolves via the registry.
    * Otherwise falls back to DEFAULT_TENANT_ID (legacy keys created before
      Sprint Y).
    """
    if not key_info:
        tid = DEFAULT_TENANT_ID
    else:
        tid = (key_info.get("tenant_id") or DEFAULT_TENANT_ID).strip() or DEFAULT_TENANT_ID
    return tid, store.get_tenant(tid)
