#!/usr/bin/env python3
"""
numeric.py — Deterministic numeric methods (APEX SCIENTIFIC mode).

WHY THIS EXISTS:
  An LLM cannot integrate a differential equation by "thinking". Naive stepping
  (Euler) accumulates large error. RK4 gives orders-of-magnitude better accuracy.
  This module gives the LLM a precise, verifiable numeric arm.

WHEN TO USE:
  Multidimensional ODE systems, trajectory/energy problems, any dynamics where
  accuracy matters. Prefer RK4; use Euler only for a fast/rough baseline.

ACCELERATION (environment-gated, NOT model-gated):
  numpy/scipy make big ODE systems faster and more accurate (scipy's adaptive solve_ivp beats a
  fixed-step RK4). Whether they are importable is a property of the EXECUTION ENVIRONMENT running
  this code — not of which LLM sits on top. So this module USES them when `capabilities()` reports
  them present and falls back to the pure-stdlib RK4 otherwise. `solve_ode(..., method="auto")`
  picks scipy > stdlib automatically; the llm_adapter can advertise this as a `numeric_accel`
  capability so a caller knows precision is available.

WHAT IF IT FAILS:
  If the derivative function raises, the caller gets the exception — no silent
  NaN propagation. Validate against a closed form or conserved quantity when one
  exists (see validate_conserved()). A missing numpy/scipy simply drops to the stdlib path.
"""
from typing import Callable, Sequence

try:
    import numpy as _np
    _HAS_NUMPY = True
except Exception:
    _np, _HAS_NUMPY = None, False
try:
    from scipy.integrate import solve_ivp as _solve_ivp
    _HAS_SCIPY = True
except Exception:
    _solve_ivp, _HAS_SCIPY = None, False


def capabilities():
    """Which acceleration libs are importable HERE (environment fact, not LLM capability).
    numpy/scipy accelerate ODEs; sklearn/pandas may accelerate other analyses."""
    def _has(name):
        try:
            __import__(name)
            return True
        except Exception:
            return False
    return {"numpy": _HAS_NUMPY, "scipy": _HAS_SCIPY,
            "sklearn": _has("sklearn"), "pandas": _has("pandas")}


def solve_ode(deriv: Callable, s0: Sequence[float], dt: float, steps: int, method: str = "auto"):
    """Integrate an ODE system, using the best available backend. method='auto' picks scipy's
    adaptive solver (higher accuracy) when scipy is importable, else the deterministic stdlib RK4.
    Returns {"final": state, "backend": "scipy"|"rk4", "t_end": dt*steps}. deriv(state)->d/dt list
    is the same signature as rk4/euler (scipy is adapted internally to f(t, y))."""
    use = method
    if method == "auto":
        use = "scipy" if _HAS_SCIPY else "rk4"
    if use == "scipy" and _HAS_SCIPY:
        t_end = dt * steps
        sol = _solve_ivp(lambda t, y: deriv(list(y)), (0.0, t_end), list(s0),
                         method="RK45", t_eval=[t_end], rtol=1e-8, atol=1e-10)
        return {"final": [float(v) for v in sol.y[:, -1]], "backend": "scipy", "t_end": t_end}
    return {"final": rk4(deriv, s0, dt, steps), "backend": "rk4", "t_end": dt * steps}


def euler(deriv: Callable, s0: Sequence[float], dt: float, steps: int):
    """First-order Euler. Fast, low accuracy — baseline only."""
    s = list(s0)
    for _ in range(steps):
        d = deriv(s)
        s = [s[i] + dt * d[i] for i in range(len(s))]
    return s


def rk4(deriv: Callable, s0: Sequence[float], dt: float, steps: int):
    """Classic 4th-order Runge-Kutta. Preferred integrator."""
    s = list(s0)
    n = len(s)
    for _ in range(steps):
        k1 = deriv(s)
        k2 = deriv([s[i] + dt / 2 * k1[i] for i in range(n)])
        k3 = deriv([s[i] + dt / 2 * k2[i] for i in range(n)])
        k4 = deriv([s[i] + dt * k3[i] for i in range(n)])
        s = [s[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(n)]
    return s


def rk4_trajectory(deriv: Callable, s0: Sequence[float], dt: float, steps: int):
    """RK4 but returns the full trajectory (list of states)."""
    s = list(s0)
    n = len(s)
    traj = [list(s)]
    for _ in range(steps):
        k1 = deriv(s)
        k2 = deriv([s[i] + dt / 2 * k1[i] for i in range(n)])
        k3 = deriv([s[i] + dt / 2 * k2[i] for i in range(n)])
        k4 = deriv([s[i] + dt * k3[i] for i in range(n)])
        s = [s[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(n)]
        traj.append(list(s))
    return traj


def validate_conserved(quantity_fn: Callable, state, expected: float):
    """Return absolute error of a conserved quantity vs expected (sanity check)."""
    return abs(quantity_fn(state) - expected)


if __name__ == "__main__":
    # demo: 2D harmonic oscillator x''=-x ; energy x^2+v^2 must stay = 1
    deriv = lambda s: [s[1], -s[0]]
    e = euler(deriv, [1.0, 0.0], 0.05, 2000)
    r = rk4(deriv, [1.0, 0.0], 0.05, 2000)
    energy = lambda s: s[0] ** 2 + s[1] ** 2
    print("euler energy error:", validate_conserved(energy, e, 1.0))
    print("rk4   energy error:", validate_conserved(energy, r, 1.0))
