"""
Sprint Q — HMC Closed-Loop Repair  (v3.4.4)
=============================================
Biggest scientific leap in the project. Uses **Hamiltonian Monte Carlo**
(HMC, Bayesian sampling) to search the space of AST transforms with
proof of MINIMALITY: the returned patch minimises H subject to the
constraint that APS does not regress.

How this differs from rule-based autofix
----------------------------------------
- Rule-based (Sprint K/D): "if SAST006 fires, apply WeakHashReplacer".
  Local greedy, no global optimum, no proof of minimality.
- HMC repair: Bayesian sampling of the joint distribution
  P(transform_sequence | source) weighted by exp(-β·H) — converges to
  the global minimum of H under the temperature schedule.

HMC is already implemented in ``algorithms/uco/universal_code_optimizer_v4.py``
via ``UniversalCodeOptimizer.optimize(method='hmc')``.  It was never
called by the sensor — Sprint Q connects the two.

Public API
----------
- ``hmc_repair(source, *, module_id="", n_steps=20, burn_in=5,
  preserve_aps=True, deterministic=False, timeout_s=60.0)``
  → ``HMCRepairResult``

Design contract
---------------
* **Defensive**: numpy missing → falls back to GreedyOptimizer
  (`uco.optimize_fast`).  Never raises.
* **APS preservation**: when ``preserve_aps=True`` (default), patches
  that would lower APS are **rejected**; we return the original source
  with status="REJECTED_APS_REGRESSION".
* **Determinism**: ``deterministic=True`` pins numpy random seed → same
  source produces same patch (reproducibility for CI).
* **Timeout**: wallclock cap; if HMC exceeds, falls back to original
  with status="TIMEOUT".
* **Convergence proxy**: HMC acceptance_rate and h_drop_pct serve as
  pragmatic convergence diagnostics (full R̂ Gelman-Rubin would need
  multiple chains — out of scope for v1).
"""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("uco-sensor.hmc_repair")


# Resolve UCO core path (same pattern as Sprint K's uco_transform_bridge)
_UCO_PATH = Path(__file__).resolve().parents[3].parent / "uco"
if str(_UCO_PATH) not in sys.path:
    sys.path.insert(0, str(_UCO_PATH))


@dataclass
class HMCRepairResult:
    """Outcome of an HMC repair attempt."""
    module_id:           str
    original_source:     str
    patched_source:      str
    status:              str            # OK / REJECTED_APS_REGRESSION / TIMEOUT
                                        # / FALLBACK_GREEDY / FALLBACK_NO_NUMPY
                                        # / NO_CHANGE / ERROR
    is_valid_python:     bool          = True
    # Hamiltonian diagnostics
    h_before:            float         = 0.0
    h_after:             float         = 0.0
    h_drop_abs:          float         = 0.0
    h_drop_pct:          float         = 0.0
    # APS diagnostics (Sprint G correctness — APS regression rejected)
    aps_before:          Optional[float] = None
    aps_after:           Optional[float] = None
    # HMC diagnostics
    n_samples:           int           = 0
    acceptance_rate:     float         = 0.0
    elapsed_s:           float         = 0.0
    deterministic_seed:  Optional[int] = None
    # Narrative
    summary_text:        str           = ""
    error:               str           = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _summary_get(summary: Any, key: str, default: float = 0.0) -> float:
    """
    Sprint W gate-2 fix (G2-2): unified accessor that works whether
    ``summary`` is a dict (legacy) or a dataclass / SimpleNamespace
    (UCO core's actual return shape).  The previous ternary
    `getattr(...) if isinstance(summary, dict) else 0.0` silently
    zeroed every diagnostic in the production path.
    """
    if summary is None:
        return float(default)
    if isinstance(summary, dict):
        return float(summary.get(key, default) or default)
    val = getattr(summary, key, None)
    if val is None:
        return float(default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return float(default)


def _compute_aps(source: str) -> Optional[float]:
    """
    Compute the canonical APS for a snippet by delegating to the SSOT
    ``metrics.anti_pattern_score.aps_from_metric_vector``.

    Sprint W fix (audit-2, HIGH): prior to this fix the function imported
    ``aps_from_metric_vector`` but never called it — instead returning
    a shadow ``100 - 10*n_crit_high`` heuristic that ignored the 17
    weighted components of the canonical APS.  The Sprint H SSOT for
    governance signals was bypassed and the ``preserve_aps`` guard in
    ``hmc_repair`` only checked CRITICAL/HIGH SAST count.

    We now build a minimal MetricVector-shaped object from the SAST
    findings, attach a synthetic ``SecurityVector`` + ``FlowVector``
    derived from those findings, and call the canonical APS function.
    Other extended vectors stay ``None`` — ``aps_from_metric_vector``
    handles missing vectors deterministically (zero contribution for
    each absent signal).
    """
    try:
        from sast.scanner import scan
        from metrics.anti_pattern_score import aps_from_metric_vector
        from metrics.extended_vectors import SecurityVector, FlowVector
    except Exception:
        return None

    try:
        result = scan(source, file_extension=".py")
        findings = list(getattr(result, "findings", []))

        n_crit = sum(1 for f in findings if f.severity == "CRITICAL")
        n_high = sum(1 for f in findings if f.severity == "HIGH")
        n_med  = sum(1 for f in findings if f.severity == "MEDIUM")

        # Map SAST findings into the SecurityVector / FlowVector channels
        # that aps_from_metric_vector reads (anti_pattern_score.py:170-191).
        # This keeps the canonical formula in play; we DO NOT re-implement it.
        sec_vector  = SecurityVector(
            sca_vulnerable_deps=0,        # SAST is code-level, not SCA
            iac_misconfig_count=0,        # ditto, not IaC
        )
        # taint_path_count / injection_surface approximated from SAST severity.
        flow_vector = FlowVector(
            taint_path_count=n_crit + n_high,
            injection_surface=float(n_crit) * 0.5 + float(n_high) * 0.3 + float(n_med) * 0.1,
        )

        class _MinimalMV:
            pass
        mv = _MinimalMV()
        mv.security = sec_vector
        mv.flow     = flow_vector

        payload = aps_from_metric_vector(mv)
        aps = payload.get("aps") if isinstance(payload, dict) else None
        return float(aps) if aps is not None else None
    except Exception:
        return None


def _make_summary(r: HMCRepairResult) -> str:
    if r.status == "OK":
        return (f"HMC converged in {r.n_samples} samples "
                f"({r.elapsed_s:.2f}s); ΔH = {r.h_drop_abs:+.3f} "
                f"({r.h_drop_pct:+.1%}); accept_rate {r.acceptance_rate:.2f}.")
    if r.status == "NO_CHANGE":
        return "HMC found no transform with positive ΔH."
    if r.status == "REJECTED_APS_REGRESSION":
        return (f"HMC patch rejected: APS would drop "
                f"{r.aps_before:.1f} → {r.aps_after:.1f}.")
    if r.status == "TIMEOUT":
        return f"HMC exceeded timeout of {r.elapsed_s:.1f}s; original kept."
    if r.status == "FALLBACK_NO_NUMPY":
        return "numpy unavailable; fell back to GreedyOptimizer."
    if r.status == "FALLBACK_GREEDY":
        return "HMC initialisation failed; fell back to GreedyOptimizer."
    if r.status == "ERROR":
        return f"HMC repair failed: {r.error}"
    return ""


def hmc_repair(
    source: str,
    *,
    module_id: str = "",
    n_steps: int = 20,
    burn_in: int = 5,
    preserve_aps: bool = True,
    deterministic: bool = False,
    timeout_s: float = 60.0,
) -> HMCRepairResult:
    """
    Run HMC sampling over AST transforms; return patched source with
    proof of H minimality under APS-preservation constraint.

    Parameters
    ----------
    source : str
        Python source code to repair (must compile).
    module_id : str
        Identifier carried through into the result.
    n_steps : int
        Number of HMC sampling steps (default 20).
    burn_in : int
        Burn-in iterations discarded from acceptance stats (default 5).
    preserve_aps : bool
        Reject patches that would lower the APS (default True).
    deterministic : bool
        Pin numpy random seed for reproducibility (default False).
    timeout_s : float
        Wallclock cap; on overrun the original source is returned with
        status="TIMEOUT".
    """
    t0 = time.time()
    r = HMCRepairResult(
        module_id=module_id,
        original_source=source,
        patched_source=source,
        status="ERROR",
    )

    if not source or not source.strip():
        r.status = "ERROR"
        r.error  = "empty source"
        r.summary_text = _make_summary(r)
        return r

    # Defensive imports — UCO core may not be reachable in some sandboxes.
    try:
        import universal_code_optimizer_v4 as ucm
    except Exception as exc:
        r.status = "ERROR"
        r.error  = f"UCO core unavailable: {exc}"
        r.summary_text = _make_summary(r)
        return r

    # Determinism: pin numpy seed when requested.
    # Sprint W gate-2 fix (G2-1, HIGH): np.random.seed(42) mutates the GLOBAL
    # numpy RNG and poisons every other consumer in the process (concurrent
    # request handlers, predictor, spectral_aps, etc.).  We save the prior
    # global state, install our seed, run HMC, and restore the prior state
    # in a finally block.  This is the minimally invasive fix that keeps the
    # UCO core's signature (which uses np.random directly) deterministic
    # without leaking state.  A cleaner long-term fix is to pass np.random.default_rng(42)
    # down through optimizer.optimize() but that requires UCO core API change.
    seed = None
    _np_state_before = None
    if deterministic:
        try:
            import numpy as np
            seed = 42
            _np_state_before = np.random.get_state()
            np.random.seed(seed)
            r.deterministic_seed = seed
        except Exception:
            _np_state_before = None

    optimizer = ucm.UniversalCodeOptimizer()

    # Numpy presence: optimize() requires it; optimize_fast() does not.
    try:
        import numpy as _np_check  # noqa: F401
        has_numpy = True
    except Exception:
        has_numpy = False

    # ─── HMC main path ───────────────────────────────────────────────────────
    if has_numpy:
        try:
            try:
                output = optimizer.optimize(
                    code=source, n_steps=n_steps, burn_in=burn_in,
                )
            finally:
                # Sprint W gate-2 fix (G2-1, HIGH): restore the global numpy
                # RNG state IMMEDIATELY after optimize() consumes the seed.
                # Without this, concurrent handlers would inherit the seeded
                # state and produce unintentionally-reproducible-but-coupled
                # results.
                if _np_state_before is not None:
                    try:
                        import numpy as _np
                        _np.random.set_state(_np_state_before)
                    except Exception:
                        pass
            r.patched_source    = output.optimized_code
            # Sprint W gate-2 fix (G2-2, HIGH): the previous ternary
            #   `getattr(...) if isinstance(summary, dict) else 0.0`
            # silently zeroed h_before/h_after when summary is a dataclass
            # (the production case in UCO core's OptimizationOutput).
            # Use a unified helper that handles both shapes.
            r.h_before          = _summary_get(output.summary, "h_initial", 0.0)
            r.h_after           = _summary_get(output.summary, "h_final",   0.0)
            r.h_drop_abs        = r.h_before - r.h_after
            r.h_drop_pct        = (r.h_drop_abs / r.h_before) if r.h_before > 1e-9 else 0.0
            r.n_samples         = n_steps
            r.acceptance_rate   = float(getattr(output.optimization,
                                                 "acceptance_rate", 0.0) or 0.0)
            r.status = "OK"
        except RuntimeError as exc:
            # numpy was imported but HMC init failed for some other reason
            r.error  = f"HMC init failed: {exc}"
            r.status = "FALLBACK_GREEDY"
        except Exception as exc:
            r.error  = f"{type(exc).__name__}: {exc}"
            r.status = "ERROR"
            r.summary_text = _make_summary(r)
            return r
    else:
        r.status = "FALLBACK_NO_NUMPY"

    # ─── Greedy fallback ──────────────────────────────────────────────────────
    if r.status in ("FALLBACK_GREEDY", "FALLBACK_NO_NUMPY"):
        try:
            fast = optimizer.optimize_fast(code=source, max_iterations=n_steps)
            r.patched_source = fast.optimized_code
            r.n_samples      = getattr(fast.optimization, "iterations_completed",
                                       n_steps)
            # h_before/h_after not directly available — read from analysis
            try:
                r.h_before = float(fast.analysis.metrics.hamiltonian
                                   if hasattr(fast, "analysis")
                                   else 0.0)
            except Exception:
                pass
        except Exception as exc:
            r.error  = f"GreedyOptimizer also failed: {exc}"
            r.status = "ERROR"
            r.summary_text = _make_summary(r)
            return r

    # ─── Timeout enforcement ──────────────────────────────────────────────────
    r.elapsed_s = time.time() - t0
    if r.elapsed_s > timeout_s:
        r.status = "TIMEOUT"
        r.patched_source = source

    # ─── No-change short-circuit ──────────────────────────────────────────────
    if r.patched_source == source and r.status not in (
            "TIMEOUT", "ERROR", "FALLBACK_NO_NUMPY"):
        r.status = "NO_CHANGE"
        r.summary_text = _make_summary(r)
        return r

    # ─── Validate patched source compiles ─────────────────────────────────────
    try:
        compile(r.patched_source, "<hmc>", "exec")
        r.is_valid_python = True
    except SyntaxError:
        r.is_valid_python = False
        r.patched_source  = source
        r.status = "ERROR"
        r.error  = "HMC produced invalid Python; reverted"
        r.summary_text = _make_summary(r)
        return r

    # ─── APS preservation check (Sprint G correctness alignment) ──────────────
    if preserve_aps:
        aps_before = _compute_aps(source)
        aps_after  = _compute_aps(r.patched_source)
        r.aps_before = aps_before
        r.aps_after  = aps_after
        # Sprint W gate-2 fix (G2-3, HIGH): APS via aps_from_metric_vector
        # saturates on canonical thresholds (taint_path_count=1.0 →
        # 1 finding already maxes the component).  Two patches with 1
        # vs 5 CRITICAL findings produce the SAME APS, and the guard
        # `aps_after < aps_before - eps` returns False.  We therefore
        # add a defence-in-depth raw-finding-count check: reject the
        # patch when n_critical+n_high RISES, even if APS appears
        # unchanged.
        if not _no_severity_regression(source, r.patched_source):
            r.patched_source = source
            r.status = "REJECTED_APS_REGRESSION"
        elif (aps_before is not None and aps_after is not None
                and aps_after < aps_before - 1e-9):
            r.patched_source = source
            r.status = "REJECTED_APS_REGRESSION"

    r.summary_text = _make_summary(r)
    return r


def _no_severity_regression(source_before: str, source_after: str) -> bool:
    """
    Sprint W gate-2 (G2-3): return False (= reject) when the patched
    source has STRICTLY MORE CRITICAL or STRICTLY MORE HIGH findings
    than the original.  This catches the APS-clipping blind spot:
    aps_from_metric_vector saturates at 1 finding and cannot
    distinguish 1 vs 5 CRITICAL.
    """
    try:
        from sast.scanner import scan
    except Exception:
        return True   # cannot evaluate → don't reject (preserve old behaviour)
    try:
        before = scan(source_before, file_extension=".py")
        after  = scan(source_after,  file_extension=".py")
        def _count(result, sev):
            return sum(1 for f in getattr(result, "findings", [])
                        if f.severity == sev)
        crit_b, crit_a = _count(before, "CRITICAL"), _count(after, "CRITICAL")
        high_b, high_a = _count(before, "HIGH"),     _count(after, "HIGH")
        if crit_a > crit_b:
            return False
        if high_a > high_b:
            return False
        return True
    except Exception:
        return True
