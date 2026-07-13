#!/usr/bin/env python3
"""
geometry_estimator.py — APEX geometry_estimator (v00.20.2), nativized.

WHY: an LLM can't know how big an integration block can be before error blows up. This
estimates the adaptive local error (DELTA_ERR) by step-doubling and derives the optimal block
size — the n_num that bounds mental_interpreter's planning formula.

WHEN: before pot_engine_v2 / mental_interpreter run (warmup planning).

WHAT IF IT FAILS: if the integrator raises, the caller gets the exception; if DELTA_ERR is ~0,
the block size is clamped to MAX_SIZE. Falls back to a fixed block size if not computable.
"""
MIN_SIZE, MAX_SIZE = 5, 30


def delta_err(deriv, s0, dt, integrator):
    """DELTA_ERR via step doubling: |one full step(dt) - two half steps(dt/2)| * 0.1."""
    full = integrator(deriv, s0, dt, 1)
    half = integrator(deriv, s0, dt / 2, 2)
    residual = max(abs(f - h) for f, h in zip(full, half))
    return residual * 0.1


def optimal_block_size(x_magnitude, derr, eps_block_stop=1e-3):
    """n_max = eps / (DELTA_ERR * |x|), clamped to [MIN_SIZE, MAX_SIZE]."""
    if derr <= 0 or x_magnitude <= 0:
        return MAX_SIZE
    n = int(eps_block_stop / (derr * x_magnitude))
    return max(MIN_SIZE, min(MAX_SIZE, n))


if __name__ == "__main__":
    # Lotka-Volterra-ish bilinear system; compare RK4 vs Euler error
    def deriv(s):
        x, y = s
        return [1.1 * x - 0.4 * x * y, -0.4 * y + 0.1 * x * y]

    def euler(d, s0, dt, steps):
        s = list(s0)
        for _ in range(steps):
            k = d(s); s = [s[i] + dt * k[i] for i in range(len(s))]
        return s

    def rk4(d, s0, dt, steps):
        s = list(s0); n = len(s)
        for _ in range(steps):
            k1 = d(s); k2 = d([s[i] + dt / 2 * k1[i] for i in range(n)])
            k3 = d([s[i] + dt / 2 * k2[i] for i in range(n)]); k4 = d([s[i] + dt * k3[i] for i in range(n)])
            s = [s[i] + dt / 6 * (k1[i] + 2 * k2[i] + 2 * k3[i] + k4[i]) for i in range(n)]
        return s

    s0 = [10.0, 5.0]
    de_rk4 = delta_err(deriv, s0, 0.1, rk4)
    de_eul = delta_err(deriv, s0, 0.1, euler)
    print(f"DELTA_ERR rk4={de_rk4:.3e}  euler={de_eul:.3e}  (euler less precise: {de_eul > de_rk4})")
    print(f"optimal block size (rk4): {optimal_block_size(10.0, de_rk4)}")
    print(f"optimal block size (euler): {optimal_block_size(10.0, de_eul)}")
