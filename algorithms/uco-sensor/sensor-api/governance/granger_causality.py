"""
Sprint S — Granger Causality (formal F-test)  (v3.4.3)
========================================================
Replaces the Pearson-lag heuristic from Sprint M with the canonical
**Granger causality F-test** between channel pairs.

The question Granger answers (vs Pearson)
-----------------------------------------
Pearson asks: "is `X` correlated with `Y[t+k]`?"
Granger asks: "does past `X` help predict `Y` BEYOND past `Y` alone?"

That extra constraint — improvement over an autoregressive baseline —
makes Granger the **canonical formalism for temporal causality** in
time-series. Two random walks can be highly correlated; Granger
correctly rules out coincidence.

Mathematical model
------------------
For each lag ``k ∈ 1..max_lag`` and each ordered pair ``(X → Y)``:

    Restricted model:   y_t = a₀ + Σⱼ aⱼ·y_{t-j}  + ε_R
    Unrestricted model: y_t = a₀ + Σⱼ aⱼ·y_{t-j}  + Σⱼ bⱼ·x_{t-j} + ε_U

    F = ((RSS_R - RSS_U) / k) / (RSS_U / (n - 2k - 1))

    p-value via F-distribution survival function (scipy.stats.f).
    Lower p-value → stronger evidence that X Granger-causes Y at lag k.

The best lag is the one that minimises p-value across ``1..max_lag``.
The pair is **significant** when ``p_value < alpha`` (default 0.05).

Public API
----------
- ``granger_pair(x, y, *, max_lag=5, alpha=0.05)`` → ``GrangerResult``
- ``granger_matrix(store, module_id, *, max_lag=3, window=200,
  alpha=0.05)`` → 9×9 matrix of GrangerResult dicts
- ``significant_pairs(store, module_id, *, alpha=0.05, ...)`` →
  filtered list of pairs that passed the F-test

Design contract
---------------
* Pure functions; never raise on missing data — return structured
  ``status`` instead.
* Pure-Python OLS (no statsmodels dependency); scipy.stats.f only for
  the survival function — graceful fallback if scipy missing.
* Diagonal of the matrix has ``p_value=1.0, granger_causes=False``
  (a channel cannot Granger-cause itself in this formalism).
"""
from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("uco-sensor.granger")


_CHANNELS = ("H", "CC", "ILR", "DSM_d", "DSM_c", "DI", "dead", "dups", "bugs")
_ATTR_BY_SHORT = {
    "H":     "hamiltonian",
    "CC":    "cyclomatic_complexity",
    "ILR":   "infinite_loop_risk",
    "DSM_d": "dsm_density",
    "DSM_c": "dsm_cyclic_ratio",
    "DI":    "dependency_instability",
    "dead":  "syntactic_dead_code",
    "dups":  "duplicate_block_count",
    "bugs":  "halstead_bugs",
}


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class GrangerResult:
    """F-test result for one ordered channel pair."""
    from_channel:     str
    to_channel:       str
    best_lag:         int
    f_statistic:      float
    p_value:          float
    granger_causes:   bool
    n_samples:        int
    alpha:            float = 0.05

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── OLS helpers (pure Python, no numpy) ─────────────────────────────────────

def _ols_solve(X: List[List[float]], y: List[float]) -> Tuple[List[float], float]:
    """
    Solve OLS: y = X β + ε via numpy.linalg.lstsq if available, else
    via normal equations.  Returns (beta, RSS).
    """
    try:
        import numpy as np
        Xa = np.asarray(X, dtype=float)
        ya = np.asarray(y, dtype=float)
        beta, residuals, rank, sv = np.linalg.lstsq(Xa, ya, rcond=None)
        pred = Xa @ beta
        rss  = float(((ya - pred) ** 2).sum())
        return beta.tolist(), rss
    except Exception:
        # Fallback: normal equations
        n = len(y)
        p = len(X[0]) if X else 0
        # Compute XtX and Xty
        XtX = [[sum(X[i][a] * X[i][b] for i in range(n))
                for b in range(p)] for a in range(p)]
        Xty = [sum(X[i][a] * y[i] for i in range(n)) for a in range(p)]
        # Solve via Gaussian elimination
        beta = _gauss_solve(XtX, Xty)
        if beta is None:
            return [0.0] * p, sum(yi * yi for yi in y)
        rss = sum((y[i] - sum(X[i][a] * beta[a] for a in range(p))) ** 2
                   for i in range(n))
        return beta, rss


def _gauss_solve(A: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """Gaussian elimination with partial pivoting; None on singular."""
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for i in range(n):
        # Pivot
        piv = max(range(i, n), key=lambda r: abs(M[r][i]))
        if abs(M[piv][i]) < 1e-12:
            return None
        M[i], M[piv] = M[piv], M[i]
        # Eliminate
        for r in range(i + 1, n):
            factor = M[r][i] / M[i][i]
            for c in range(i, n + 1):
                M[r][c] -= factor * M[i][c]
    # Back-substitute
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = M[i][n] - sum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / M[i][i]
    return x


def _f_survival(f: float, df1: int, df2: int) -> float:
    """Survival function of F-distribution (P[F > f])."""
    try:
        from scipy.stats import f as f_dist
        return float(f_dist.sf(f, df1, df2))
    except Exception:
        # Fallback: tail approximation (conservative) — returns 1.0 when
        # scipy is missing.  Caller treats this as "no significance".
        return 1.0


# ─── Granger F-test for one pair ─────────────────────────────────────────────

def granger_pair(
    x: List[float],
    y: List[float],
    *,
    max_lag: int = 5,
    alpha: float = 0.05,
) -> GrangerResult:
    """
    Test whether x Granger-causes y across lags 1..max_lag.

    Picks the lag minimising p-value; returns that lag's statistics.
    """
    if len(x) != len(y) or len(x) < 2 * max_lag + 3:
        return GrangerResult(
            from_channel="", to_channel="",
            best_lag=0, f_statistic=0.0, p_value=1.0,
            granger_causes=False, n_samples=len(y), alpha=alpha,
        )

    best_p   = 1.0
    best_f   = 0.0
    best_lag = 0

    for k in range(1, max_lag + 1):
        n_eff = len(y) - k
        if n_eff < 2 * k + 1:
            continue

        # Build restricted (y on past y) and unrestricted (y on past y + past x)
        Y = y[k:]
        X_R: List[List[float]] = []  # autoregressive only
        X_U: List[List[float]] = []  # autoregressive + cross lags
        for t in range(n_eff):
            row_r = [1.0] + [y[t + k - j] for j in range(1, k + 1)]
            row_u = row_r + [x[t + k - j] for j in range(1, k + 1)]
            X_R.append(row_r)
            X_U.append(row_u)

        _, rss_r = _ols_solve(X_R, Y)
        _, rss_u = _ols_solve(X_U, Y)

        if rss_u < 1e-12 or rss_r <= rss_u:
            continue

        df1 = k
        df2 = n_eff - 2 * k - 1
        if df2 <= 0:
            continue
        F = ((rss_r - rss_u) / df1) / (rss_u / df2)
        p = _f_survival(F, df1, df2)

        if p < best_p:
            best_p   = p
            best_f   = F
            best_lag = k

    return GrangerResult(
        from_channel="", to_channel="",
        best_lag=best_lag, f_statistic=round(best_f, 4),
        p_value=round(best_p, 6),
        granger_causes=(best_p < alpha),
        n_samples=len(y), alpha=alpha,
    )


# ─── Store integration ───────────────────────────────────────────────────────

def _series(history: List[Any], short: str) -> List[float]:
    attr = _ATTR_BY_SHORT[short]
    return [float(getattr(mv, attr, 0.0) or 0.0) for mv in history]


def granger_matrix(
    store: Any,
    module_id: str,
    *,
    max_lag: int = 3,
    window: int = 200,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """
    Compute the 9×9 Granger-causality matrix on the persisted history.

    Returns
    -------
    {
      "module_id":  str,
      "status":     "OK" | "NO_HISTORY" | "INSUFFICIENT" | "ERROR",
      "n_samples":  int,
      "max_lag":    int,
      "alpha":      float,
      "channels":   [9 short names],
      "matrix":     [ {from, to, best_lag, f_statistic, p_value,
                       granger_causes, n_samples, alpha} ... 81 entries ]
    }
    """
    try:
        history = store.get_history(module_id, window=window)
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"store: {exc}"}
    if not history:
        return {"module_id": module_id, "status": "NO_HISTORY"}

    n = len(history)
    if n < 2 * max_lag + 3:
        return {"module_id": module_id, "status": "INSUFFICIENT",
                "n_samples": n, "min_required": 2 * max_lag + 3}

    series = {ch: _series(history, ch) for ch in _CHANNELS}
    matrix: List[Dict[str, Any]] = []
    for ch_i in _CHANNELS:
        for ch_j in _CHANNELS:
            if ch_i == ch_j:
                matrix.append({
                    "from":           ch_i,
                    "to":             ch_j,
                    "best_lag":       0,
                    "f_statistic":    0.0,
                    "p_value":        1.0,
                    "granger_causes": False,
                    "n_samples":      n,
                    "alpha":          alpha,
                })
                continue
            res = granger_pair(
                series[ch_i], series[ch_j],
                max_lag=max_lag, alpha=alpha,
            )
            d = res.to_dict()
            d["from"] = ch_i
            d["to"]   = ch_j
            matrix.append(d)

    return {
        "module_id": module_id,
        "status":    "OK",
        "n_samples": n,
        "max_lag":   max_lag,
        "alpha":     alpha,
        "channels":  list(_CHANNELS),
        "matrix":    matrix,
    }


def significant_pairs(
    store: Any,
    module_id: str,
    *,
    max_lag: int = 3,
    window: int = 200,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Filter granger_matrix to keep only pairs with p_value < alpha."""
    full = granger_matrix(
        store, module_id,
        max_lag=max_lag, window=window, alpha=alpha,
    )
    if full.get("status") != "OK":
        return full
    sig = [m for m in full["matrix"]
           if m["from"] != m["to"] and m["granger_causes"]]
    sig.sort(key=lambda m: (m["p_value"], m["from"], m["to"]))
    return {
        "module_id":      module_id,
        "status":         "OK",
        "n_samples":      full["n_samples"],
        "max_lag":        max_lag,
        "alpha":          alpha,
        "n_significant":  len(sig),
        "pairs":          sig,
    }
