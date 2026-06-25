"""
Sprint Z — UCO Sensor: 5 Core Invariants (Executable Specification) (v3.9.0)
==============================================================================

Each invariant is a TRIPLE:

* PROPERTY (the informal claim).
* CHECKER (a Python predicate that decides whether a given system state
  satisfies the property).
* RUNTIME ASSERTION HOOK (a function call sites embed to fail fast when
  the invariant is violated in production).

The five invariants correspond to the formal core of the UCO Sensor as
documented in ``paper/paper.tex`` (Sprint Z release).  Each is paired
with at least three regression tests in ``tests/test_marco_m59.py``
(TW01-TW15), including adversarial cases designed to break it.

------------------------------------------------------------------------
INVARIANT INDEX
------------------------------------------------------------------------

I1  APS preservation under repair
    `aps_after >= aps_before` after any patch accepted with
    `preserve_aps=True` in `sensor_core/autofix/hmc_repair.py`.

I2  Severity monotone under repair
    Patch is REJECTED if it introduces NEW CRITICAL or HIGH findings.
    Re-cast of `_no_severity_regression` from Sprint W2 gate-2 fix G2-3
    as a first-class invariant.

I3  HMC convergence bound
    For any HMC chain with ``n_steps >= 1`` and finite source, the final
    Hamiltonian satisfies ``H_final <= H_initial`` OR ``status != "OK"``.

I4  Propagation tensor symmetry (under reverse-edge case)
    For a propagation pair (a,b) with delay τ=0, the correlation is
    bidirectionally consistent: ``cov(a,b) == cov(b,a)`` within ε=1e-9.

I5  Period reset atomicity (Sprint Y SY-FIX-7)
    Two concurrent calls to ``reset_period_if_rolled`` for the same
    tenant cannot both observe the pre-reset anchor; the second caller
    returns ``False`` because the first already advanced the anchor.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple


# ─── I1: APS preservation ────────────────────────────────────────────────────

def invariant_i1_aps_preserved(
    aps_before: Optional[float],
    aps_after: Optional[float],
    *,
    tolerance: float = 1e-9,
) -> bool:
    """APS-after >= APS-before (within numerical tolerance).

    None values are treated as "unmeasured" → invariant trivially holds
    (refuse to claim a violation we cannot observe).
    """
    if aps_before is None or aps_after is None:
        return True
    return float(aps_after) >= float(aps_before) - tolerance


# ─── I2: Severity monotone ───────────────────────────────────────────────────

def _count_findings(scan_result: Any, severity: str) -> int:
    findings = getattr(scan_result, "findings", []) or []
    return sum(1 for f in findings if getattr(f, "severity", "") == severity)


def invariant_i2_no_severity_regression(
    scan_before: Any, scan_after: Any,
) -> bool:
    """Number of CRITICAL or HIGH findings does NOT strictly increase."""
    if scan_before is None or scan_after is None:
        return True
    crit_b, crit_a = _count_findings(scan_before, "CRITICAL"), _count_findings(scan_after, "CRITICAL")
    high_b, high_a = _count_findings(scan_before, "HIGH"),     _count_findings(scan_after, "HIGH")
    if crit_a > crit_b:
        return False
    if high_a > high_b:
        return False
    return True


# ─── I3: HMC convergence bound ───────────────────────────────────────────────

def invariant_i3_hmc_convergence(
    h_initial: Optional[float],
    h_final: Optional[float],
    status: str,
    *,
    tolerance: float = 1e-6,
) -> bool:
    """For status == OK: ``h_final <= h_initial`` (sampling converges
    to a no-worse energy).  Any other status: invariant vacuously true."""
    if status != "OK":
        return True
    if h_initial is None or h_final is None:
        return True
    return float(h_final) <= float(h_initial) + tolerance


# ─── I4: Propagation symmetry at τ=0 ─────────────────────────────────────────

def invariant_i4_propagation_symmetry(
    cov_ab: float, cov_ba: float, *, tolerance: float = 1e-9,
) -> bool:
    """At zero lag the cross-covariance is symmetric."""
    return abs(float(cov_ab) - float(cov_ba)) <= tolerance


# ─── I5: Period reset atomicity ──────────────────────────────────────────────

def invariant_i5_period_reset_idempotent(
    first_call_result: bool, second_call_result: bool,
) -> bool:
    """If first call reset the anchor, the second must NOT reset again."""
    if first_call_result is True:
        return second_call_result is False
    # If first call did NOT reset, the second is unconstrained
    # (caller decides; not an invariant violation either way).
    return True


# ─── Runtime assertion hook ──────────────────────────────────────────────────

class InvariantViolation(AssertionError):
    """Raised when a registered invariant fails at runtime.

    Carries structured context for telemetry: which invariant id, what
    values were observed, optional callsite hint.
    """
    def __init__(self, invariant_id: str, observed: Dict[str, Any], hint: str = ""):
        msg = f"UCO invariant {invariant_id} violated: observed={observed}"
        if hint:
            msg += f" ({hint})"
        super().__init__(msg)
        self.invariant_id = invariant_id
        self.observed = observed
        self.hint = hint


_INVARIANTS = {
    "I1": invariant_i1_aps_preserved,
    "I2": invariant_i2_no_severity_regression,
    "I3": invariant_i3_hmc_convergence,
    "I4": invariant_i4_propagation_symmetry,
    "I5": invariant_i5_period_reset_idempotent,
}


def assert_invariant(invariant_id: str, *args, hint: str = "", **kwargs) -> None:
    """Evaluate the named invariant; raise ``InvariantViolation`` if false."""
    fn = _INVARIANTS.get(invariant_id)
    if fn is None:
        raise KeyError(f"unknown invariant {invariant_id!r}; "
                       f"valid={sorted(_INVARIANTS)}")
    if not fn(*args, **kwargs):
        observed = {f"arg{i}": a for i, a in enumerate(args)}
        observed.update(kwargs)
        raise InvariantViolation(invariant_id, observed, hint)


def list_invariants() -> Dict[str, str]:
    """Return ``{invariant_id: docstring_first_line}`` for catalogue endpoints."""
    return {
        iid: (fn.__doc__ or "").strip().split("\n")[0]
        for iid, fn in _INVARIANTS.items()
    }
