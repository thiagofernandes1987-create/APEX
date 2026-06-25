"""
Sprint M — Cross-Channel Propagation + Causality Matrix  (v3.3.5)
==================================================================
Exposes ``frequency-engine/receptor/propagation_analyzer.py`` as a
governance signal AND adds a **9×9 cross-channel lag/correlation matrix**
on top of it — the foundation for Granger-causality work (Sprint S).

Why both layers
---------------
- **Propagation fingerprint** (already implemented by the engine):
  identifies *which group of channels* moved together and *in what
  order* (ISOLATED, SIMULTANEOUS, CASCADED_FAST, CASCADED_SLOW).
- **9×9 lag-correlation matrix** (new in this sprint): for every pair
  of channels, finds the lag k that maximises Pearson correlation
  between ``ch_i[t]`` and ``ch_j[t+k]`` over the persisted history.
  Sign of k tells direction; magnitude tells coupling strength.
  Together they answer "did CC move BEFORE bugs, and by how much?".

Public API
----------
- ``compute_propagation(store, module_id, *, primary_channels=None,
  penalty=2.5, window=200)`` → ``Dict``
- ``compute_causality_matrix(store, module_id, *, max_lag=5,
  window=200)`` → ``Dict[str, List[Dict]]`` (matrix in long-form)

Design contract
---------------
* Pure read-only — never writes to the store.
* Defensive: every failure path returns a structured ``status``
  payload, never raises.
* Lag computation runs entirely in numpy — O(C² · L · N) where C=9
  channels, L=2·max_lag+1, N=history length.  For N≤200, L≤11 this
  is sub-millisecond.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger("uco-sensor.propagation")


_DEFAULT_PRIMARY = ("H", "CC", "DI")


def _json_safe(obj: Any) -> Any:
    """Recursively coerce numpy scalars / arrays to Python natives for JSON."""
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(x) for x in obj]
    # numpy scalars expose .item(); plain Python ints/floats/bools/strs/None pass through
    if hasattr(obj, "item") and not isinstance(obj, (str, bytes)):
        try:
            return obj.item()
        except Exception:
            return obj
    return obj


# ─── propagation fingerprint (wraps PropagationAnalyzer) ─────────────────────

def compute_propagation(
    store: Any,
    module_id: str,
    *,
    primary_channels: Optional[List[str]] = None,
    penalty: float = 2.5,
    window: int = 200,
) -> Dict[str, Any]:
    """Wrap PropagationAnalyzer.compute and serialize to a JSON-safe dict."""
    try:
        history = store.get_history(module_id, window=window)
    except Exception:
        return {"module_id": module_id, "status": "ERROR",
                "error": "store unreachable"}
    if not history:
        return {"module_id": module_id, "status": "NO_HISTORY"}

    try:
        from transmitter.metric_signal_builder import MetricSignalBuilder
        from receptor.propagation_analyzer import PropagationAnalyzer
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"frequency-engine unavailable: {exc}"}

    signal = MetricSignalBuilder().build(history, verbose=False)
    if signal is None:
        return {"module_id": module_id, "status": "INSUFFICIENT"}

    channels = list(primary_channels) if primary_channels else list(_DEFAULT_PRIMARY)
    try:
        fp = PropagationAnalyzer(pelt_penalty=penalty).compute(signal, channels)
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"PropagationAnalyzer failed: {exc}"}

    payload = _json_safe(asdict(fp))
    payload["module_id"] = module_id
    payload["status"] = "OK"
    payload["primary_channels"] = channels
    return payload


def compute_propagation_groups(
    store: Any,
    module_id: str,
    *,
    penalty: float = 2.5,
    window: int = 200,
) -> Dict[str, Any]:
    """Compute fingerprints for the 7 predefined diagnostic groups."""
    try:
        history = store.get_history(module_id, window=window)
    except Exception:
        return {"module_id": module_id, "status": "ERROR"}
    if not history:
        return {"module_id": module_id, "status": "NO_HISTORY", "groups": {}}

    try:
        from transmitter.metric_signal_builder import MetricSignalBuilder
        from receptor.propagation_analyzer import PropagationAnalyzer
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"frequency-engine unavailable: {exc}"}

    signal = MetricSignalBuilder().build(history, verbose=False)
    if signal is None:
        return {"module_id": module_id, "status": "INSUFFICIENT", "groups": {}}

    analyzer = PropagationAnalyzer(pelt_penalty=penalty)
    try:
        groups = analyzer.compute_all(signal)
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"compute_all failed: {exc}"}

    return {
        "module_id": module_id,
        "status":    "OK",
        "groups":    {name: _json_safe(asdict(fp)) for name, fp in groups.items()},
    }


# ─── 9×9 lag-correlation matrix ───────────────────────────────────────────────

# Sprint W fix (audit-3, HIGH): channel maps moved to governance.channels SSOT.
# Local aliases preserved so existing imports (tests etc.) keep working.
from governance.channels import (
    CHANNELS as _CHANNELS,
    ATTR_BY_SHORT as _ATTR_BY_SHORT,
    series as _series,
)


def _pearson(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 3:
        return 0.0
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((x[i] - mx) * (y[i] - my) for i in range(n))
    den_x = (sum((x[i] - mx) ** 2 for i in range(n))) ** 0.5
    den_y = (sum((y[i] - my) ** 2 for i in range(n))) ** 0.5
    if den_x < 1e-12 or den_y < 1e-12:
        return 0.0
    return num / (den_x * den_y)


def _best_lag(x: List[float], y: List[float], max_lag: int) -> Tuple[int, float]:
    """
    Search lag k in [-max_lag, +max_lag] that maximises |corr(x[t], y[t+k])|.
    Returns (best_lag, signed_correlation_at_that_lag).
    Sign convention: k > 0 means y LAGS x (x leads y); k < 0 means y leads x.
    """
    best_k = 0
    best_r = 0.0
    for k in range(-max_lag, max_lag + 1):
        if k >= 0:
            xs = x[: len(x) - k] if k else x
            ys = y[k:]            if k else y
        else:
            xs = x[-k:]
            ys = y[: len(y) + k]
        r = _pearson(xs, ys)
        if abs(r) > abs(best_r):
            best_r = r
            best_k = k
    return best_k, best_r


def compute_causality_matrix(
    store: Any,
    module_id: str,
    *,
    max_lag: int = 5,
    window: int = 200,
) -> Dict[str, Any]:
    """
    Compute the 9×9 lag-correlation matrix on the persisted history.

    Returns
    -------
    {
      "module_id":  str,
      "status":     "OK" | "NO_HISTORY" | "INSUFFICIENT" | "ERROR",
      "n_samples":  int,
      "max_lag":    int,
      "channels":   [9 short names],
      "matrix":     [
          {"from": "H", "to": "CC", "best_lag": 2, "correlation": 0.78,
           "direction": "LEADS" | "LAGS" | "SYNC"},
          ... 81 entries total (including diagonal)
      ]
    }

    Diagonal entries are still emitted (auto-correlation at lag 0) so
    clients can render the full square heatmap without missing cells.
    """
    try:
        history = store.get_history(module_id, window=window)
    except Exception as exc:
        return {"module_id": module_id, "status": "ERROR",
                "error": f"store: {exc}"}
    if not history:
        return {"module_id": module_id, "status": "NO_HISTORY",
                "n_samples": 0}

    n = len(history)
    if n < 2 * max_lag + 3:
        return {"module_id": module_id, "status": "INSUFFICIENT",
                "n_samples": n, "min_required": 2 * max_lag + 3}

    series = {ch: _series(history, ch) for ch in _CHANNELS}
    matrix: List[Dict[str, Any]] = []
    for ch_i in _CHANNELS:
        for ch_j in _CHANNELS:
            if ch_i == ch_j:
                # Auto-correlation at lag 0 = 1.0 by definition.
                matrix.append({
                    "from": ch_i, "to": ch_j,
                    "best_lag": 0, "correlation": 1.0,
                    "direction": "SYNC",
                })
                continue
            k, r = _best_lag(series[ch_i], series[ch_j], max_lag)
            direction = "SYNC" if k == 0 else ("LEADS" if k > 0 else "LAGS")
            matrix.append({
                "from":        ch_i,
                "to":          ch_j,
                "best_lag":    int(k),
                "correlation": round(float(r), 4),
                "direction":   direction,
            })

    return {
        "module_id": module_id,
        "status":    "OK",
        "n_samples": n,
        "max_lag":   max_lag,
        "channels":  list(_CHANNELS),
        "matrix":    matrix,
    }


def top_causal_pairs(
    store: Any,
    module_id: str,
    *,
    max_lag: int = 5,
    window: int = 200,
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Convenience over compute_causality_matrix: returns the top-K
    off-diagonal pairs by absolute correlation, with their best_lag.
    Useful for "what couples to what" in dashboards.
    """
    full = compute_causality_matrix(
        store, module_id, max_lag=max_lag, window=window,
    )
    if full.get("status") != "OK":
        return full

    off_diag = [m for m in full["matrix"] if m["from"] != m["to"]]
    off_diag.sort(
        key=lambda m: (-abs(m["correlation"]), m["from"], m["to"]),
    )
    return {
        "module_id": module_id,
        "status":    "OK",
        "n_samples": full["n_samples"],
        "max_lag":   max_lag,
        "top_k":     max(0, int(top_k)),
        "pairs":     off_diag[: max(0, int(top_k))],
    }
