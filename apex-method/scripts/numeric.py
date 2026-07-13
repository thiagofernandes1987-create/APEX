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

WHAT IF IT FAILS:
  If the derivative function raises, the caller gets the exception — no silent
  NaN propagation. Validate against a closed form or conserved quantity when one
  exists (see validate_conserved()).
"""
from typing import Callable, Sequence


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
