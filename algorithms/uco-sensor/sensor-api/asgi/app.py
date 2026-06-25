"""
Sprint U — ASGI app wrapper (v3.5.0)
======================================
Optional Starlette/Uvicorn entry point that **delegates** every request
to the existing ``api.server`` handlers — zero handler duplication.

Why an ASGI wrapper instead of a full rewrite
---------------------------------------------
The synchronous ``http.server`` in ``api/server.py`` has 60+ handlers
already tested (1873 tests).  Re-implementing each one in ASGI would
double the maintenance surface and risk drift.  Instead, this module
exposes a thin Starlette app whose every route calls the SAME Python
function the legacy HTTP server calls.  The only difference is the
event loop and connection model — perfect for `uvicorn` deployment.

Usage
-----
::

    # Install:
    pip install starlette uvicorn

    # Run:
    uvicorn asgi.app:app --host 0.0.0.0 --port 8765 --workers 4

Without Starlette installed, importing this module raises a helpful
``ImportError`` — the legacy ``api.server`` continues to work unchanged.

Trade-offs
----------
- Handlers are still synchronous; ASGI gains come from:
  (1) async I/O for the HTTP layer itself,
  (2) per-worker isolation under uvicorn (true parallelism via
      multiple processes vs threads).
- Long-running handlers (HMC repair, /repo/health-history) still
  block their worker — they should be offloaded to a worker pool in
  a future sprint (Sprint W).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Tuple

_log = logging.getLogger("uco-sensor.asgi")

try:
    from starlette.applications import Starlette
    from starlette.requests    import Request
    from starlette.responses   import JSONResponse, Response, HTMLResponse
    from starlette.routing     import Route
except ImportError as exc:        # pragma: no cover — opt-in
    raise ImportError(
        "Sprint U ASGI wrapper requires Starlette: pip install starlette uvicorn"
    ) from exc


# Lazy import — api.server has heavy side effects on import (SnapshotStore,
# UCOBridge, FrequencyEngine).  We want that to happen exactly once at
# uvicorn startup.
from api import server as _legacy   # noqa: E402


def _envelope(status_code: int, data: Any) -> Response:
    """Mirror the legacy ``_send_json`` envelope."""
    status_str = "ok" if status_code < 400 else "error"
    payload = {"status": status_str, "data": data}
    resp = JSONResponse(payload, status_code=status_code)
    resp.headers["X-UCO-Sensor-Version"] = _legacy._config.version
    return resp


def _extract_key(request: "Request") -> str:
    """Same X-UCO-API-Key precedence as the legacy server."""
    h = request.headers.get("x-uco-api-key", "")
    if h:
        return h
    qp = request.query_params.get("api_key", "")
    return qp


async def _read_body(request: "Request") -> Dict[str, Any]:
    if request.method.upper() not in ("POST", "PUT", "PATCH"):
        return {}
    try:
        return await request.json()
    except Exception:
        return {}


def _check_auth(request: "Request", *, admin: bool = False) -> bool:
    if not _legacy._config.auth_enabled:
        return True
    ok, _ = _legacy._authenticate(_extract_key(request), require_admin=admin)
    return ok


# ─── Route handlers — generic delegation to legacy handle_* functions ────────

async def root_route(request):
    code, html = _legacy.handle_root()
    return HTMLResponse(html, status_code=code)


async def health_route(request):
    code, data = _legacy.handle_health()
    return _envelope(code, data)


async def docs_route(request):
    code, data = _legacy.handle_docs()
    return _envelope(code, data)


def _build_get_delegate(handler_name: str, *, admin: bool = False,
                       param_map: Dict[str, Tuple[str, Callable, Any]] = None):
    """
    Build an async ASGI route that delegates to ``_legacy.<handler_name>``.

    ``param_map`` maps function-parameter-name → (query_param_name,
    coercer, default).
    """
    handler = getattr(_legacy, handler_name)

    async def _route(request):
        if not _check_auth(request, admin=admin):
            return _envelope(401 if not admin else 403,
                             {"error": "auth required"})
        kwargs = {}
        if param_map:
            for fn_param, (qparam, coerce, default) in param_map.items():
                raw = request.query_params.get(qparam, None)
                try:
                    kwargs[fn_param] = coerce(raw) if raw is not None else default
                except Exception:
                    kwargs[fn_param] = default
        try:
            code, data = handler(**kwargs)
        except Exception as exc:
            return _envelope(500, {"error": str(exc)})
        return _envelope(code, data)

    _route.__name__ = f"asgi_{handler_name}"
    return _route


def _build_post_delegate(handler_name: str, *, admin: bool = False):
    handler = getattr(_legacy, handler_name)

    async def _route(request):
        if not _check_auth(request, admin=admin):
            return _envelope(401 if not admin else 403,
                             {"error": "auth required"})
        body = await _read_body(request)
        try:
            code, data = handler(body)
        except Exception as exc:
            return _envelope(500, {"error": str(exc)})
        return _envelope(code, data)

    _route.__name__ = f"asgi_{handler_name}"
    return _route


# ─── Route table (curated — heavy GETs + key POSTs; legacy server is
#     the source-of-truth for the long tail) ───────────────────────────────

_routes = [
    Route("/",              root_route,   methods=["GET"]),
    Route("/health",        health_route, methods=["GET"]),
    Route("/docs",          docs_route,   methods=["GET"]),

    # Read-heavy paths that benefit MOST from async + cache
    Route("/repo/health-score",
          _build_get_delegate("handle_repo_health_score",
              param_map={"window": ("window", int, 100)}),
          methods=["GET"]),
    Route("/spectral/fingerprint",
          _build_get_delegate("handle_spectral_fingerprint",
              param_map={"module_id": ("module", str, ""),
                          "window":     ("window", int, 100)}),
          methods=["GET"]),
    Route("/granger/matrix",
          _build_get_delegate("handle_granger_matrix",
              param_map={"module_id": ("module", str, ""),
                          "max_lag":   ("max_lag", int, 3),
                          "window":    ("window", int, 200),
                          "alpha":     ("alpha", float, 0.05)}),
          methods=["GET"]),
    Route("/rca",
          _build_get_delegate("handle_rca",
              param_map={"module_id": ("module", str, ""),
                          "repo_dir":  ("repo_dir", str, ""),
                          "window":    ("window", int, 200)}),
          methods=["GET"]),
    Route("/similar",
          _build_get_delegate("handle_similar",
              param_map={"module_id": ("module", str, ""),
                          "k":         ("k", int, 10),
                          "metric":    ("metric", str, "euclidean"),
                          "window":    ("window", int, 100)}),
          methods=["GET"]),

    # Write paths
    Route("/analyze",        _build_post_delegate("handle_analyze"),
          methods=["POST"]),
    Route("/repair/hmc",     _build_post_delegate("handle_repair_hmc"),
          methods=["POST"]),
    Route("/apex/auto-remediate",
          _build_post_delegate("handle_apex_auto_remediate"),
          methods=["POST"]),
]


app = Starlette(debug=False, routes=_routes)


# Optional Uvicorn entry-point so users can do `python -m asgi.app`
def run(host: str = "0.0.0.0", port: int = 8765, workers: int = 1) -> None:
    """Convenience runner — equivalent to `uvicorn asgi.app:app`."""
    try:
        import uvicorn   # type: ignore
    except ImportError as exc:
        raise ImportError(
            "Install uvicorn: pip install uvicorn"
        ) from exc
    uvicorn.run("asgi.app:app", host=host, port=port, workers=workers)


if __name__ == "__main__":   # pragma: no cover
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--workers", type=int, default=1)
    args = p.parse_args()
    run(args.host, args.port, args.workers)
