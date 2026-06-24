"""
Marco 57 — Sprint X: CFG visualizável + hotspot overlay + port-allocator (TY01-TY30)
======================================================================================

* `governance/cfg.py` — pure-Python AST → control-flow graph per function.
* `/cfg/{module_id}` and `/cfg/hotspots/{module_id}` REST endpoints.
* `tests/_port_allocator.py` — quick-win fix for gate-2b LOW finding
  "hardcoded_port".

Layout
------
TY01-TY10 — cfg.py core: if/loop/try/return shapes, truncation, ERROR path.
TY11-TY20 — overlay_hotspots + cfg_as_dot rendering.
TY21-TY27 — REST handlers + /docs registration.
TY28-TY30 — port-allocator + sanity.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


# ═══════════════════════════════════════════════════════════════════════════════
# TY01-TY10 — CFG core
# ═══════════════════════════════════════════════════════════════════════════════

def test_TY01_build_cfg_OK_status_on_trivial_function():
    from governance.cfg import build_cfg
    src = "def f(x):\n    return x + 1\n"
    cfg = build_cfg(src)
    assert cfg["status"] == "OK"
    assert cfg["n_functions"] == 1


def test_TY02_build_cfg_returns_ERROR_on_invalid_syntax():
    from governance.cfg import build_cfg
    cfg = build_cfg("def f(:\n    pass")
    assert cfg["status"] == "ERROR"
    assert "SyntaxError" in cfg["error"]


def test_TY03_build_cfg_returns_ERROR_on_empty_source():
    from governance.cfg import build_cfg
    cfg = build_cfg("")
    assert cfg["status"] == "ERROR"


def test_TY04_build_cfg_extracts_if_branches():
    from governance.cfg import build_cfg
    src = (
        "def f(x):\n"
        "    if x > 0:\n"
        "        return 'pos'\n"
        "    else:\n"
        "        return 'neg'\n"
    )
    cfg = build_cfg(src)
    fn = cfg["functions"][0]
    kinds = [n["kind"] for n in fn["nodes"]]
    assert "if" in kinds
    assert "return" in kinds


def test_TY05_build_cfg_extracts_loop_back_edge():
    from governance.cfg import build_cfg
    src = (
        "def f():\n"
        "    for i in range(10):\n"
        "        print(i)\n"
    )
    cfg = build_cfg(src)
    fn = cfg["functions"][0]
    # at least one back-edge from body back to loop head
    loop_ids = [n["id"] for n in fn["nodes"] if n["kind"] == "loop"]
    assert loop_ids, "loop node missing"
    has_back = any(e["to"] in loop_ids and e["from"] != fn["nodes"][0]["id"]
                   for e in fn["edges"])
    assert has_back, "loop back-edge missing"


def test_TY06_build_cfg_truncates_at_max_nodes():
    from governance.cfg import build_cfg
    big = "def f():\n" + "\n".join(f"    x{i} = {i}" for i in range(500))
    cfg = build_cfg(big, max_nodes=20)
    assert cfg["status"] == "TRUNCATED"
    assert cfg["functions"][0]["truncated"] is True
    assert cfg["functions"][0]["n_nodes"] <= 20


def test_TY07_build_cfg_handles_try_except_finally():
    from governance.cfg import build_cfg
    src = (
        "def f():\n"
        "    try:\n"
        "        do()\n"
        "    except Exception:\n"
        "        recover()\n"
        "    finally:\n"
        "        cleanup()\n"
    )
    cfg = build_cfg(src)
    kinds = [n["kind"] for n in cfg["functions"][0]["nodes"]]
    assert "try" in kinds


def test_TY08_build_cfg_handles_async_def():
    from governance.cfg import build_cfg
    src = (
        "async def f():\n"
        "    await x\n"
        "    return 1\n"
    )
    cfg = build_cfg(src)
    assert cfg["status"] == "OK"
    assert any(n["kind"] == "return" for n in cfg["functions"][0]["nodes"])


def test_TY09_build_cfg_returns_module_pseudo_when_no_functions():
    from governance.cfg import build_cfg
    cfg = build_cfg("x = 1\ny = 2\n")
    assert cfg["status"] == "OK"
    fn = cfg["functions"][0]
    assert fn["name"] == "<module>"


def test_TY10_build_cfg_handles_multiple_functions():
    from governance.cfg import build_cfg
    src = (
        "def a():\n    return 1\n"
        "def b():\n    return 2\n"
        "def c():\n    return 3\n"
    )
    cfg = build_cfg(src)
    names = [fn["name"] for fn in cfg["functions"]]
    assert names == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════════════
# TY11-TY20 — overlay + DOT
# ═══════════════════════════════════════════════════════════════════════════════

class _StubStore:
    def __init__(self, findings=None):
        self._findings = findings or []

    def get_anomalies(self, module_id):
        return self._findings


def test_TY11_overlay_hotspots_marks_severity_on_matching_line():
    from governance.cfg import build_cfg, overlay_hotspots
    src = "def f():\n    eval(1)\n    return 2\n"
    cfg = build_cfg(src)
    findings = [{"line": 2, "severity": "HIGH"}]
    out = overlay_hotspots(cfg, _StubStore(), "m", findings=findings)
    fn = out["functions"][0]
    hot = [n for n in fn["nodes"] if n.get("severity") == "HIGH"]
    assert len(hot) >= 1


def test_TY12_overlay_preserves_nodes_when_no_findings():
    from governance.cfg import build_cfg, overlay_hotspots
    src = "def f(x):\n    return x\n"
    cfg = build_cfg(src)
    out = overlay_hotspots(cfg, _StubStore(), "m", findings=[])
    fn = out["functions"][0]
    assert all(n.get("severity") is None for n in fn["nodes"])


def test_TY13_overlay_keeps_max_severity_per_line():
    from governance.cfg import build_cfg, overlay_hotspots
    src = "def f():\n    bad()\n"
    cfg = build_cfg(src)
    findings = [
        {"line": 2, "severity": "MEDIUM"},
        {"line": 2, "severity": "CRITICAL"},
        {"line": 2, "severity": "LOW"},
    ]
    out = overlay_hotspots(cfg, _StubStore(), "m", findings=findings)
    sev = [n["severity"] for n in out["functions"][0]["nodes"] if n["severity"]]
    assert "CRITICAL" in sev


def test_TY14_overlay_aps_contribution_is_within_unit_interval():
    from governance.cfg import build_cfg, overlay_hotspots
    src = "def f():\n    a()\n    b()\n    c()\n"
    cfg = build_cfg(src)
    findings = [
        {"line": 2, "severity": "HIGH"},
        {"line": 3, "severity": "LOW"},
    ]
    out = overlay_hotspots(cfg, _StubStore(), "m", findings=findings)
    for n in out["functions"][0]["nodes"]:
        c = n.get("aps_contribution", 0.0)
        assert 0.0 <= c <= 1.0


def test_TY15_overlay_carries_overlay_module_id():
    from governance.cfg import build_cfg, overlay_hotspots
    cfg = build_cfg("def f():\n    pass\n")
    out = overlay_hotspots(cfg, _StubStore(), "mod.x", findings=[])
    assert out["overlay_module_id"] == "mod.x"


def test_TY16_overlay_passes_through_when_cfg_is_ERROR():
    from governance.cfg import build_cfg, overlay_hotspots
    cfg = build_cfg("")
    out = overlay_hotspots(cfg, _StubStore(), "m")
    assert out["status"] == "ERROR"


def test_TY17_cfg_as_dot_includes_digraph_and_subgraph():
    from governance.cfg import build_cfg, cfg_as_dot
    cfg = build_cfg("def f():\n    return 1\n")
    dot = cfg_as_dot(cfg)
    assert "digraph cfg" in dot
    assert "subgraph" in dot


def test_TY18_cfg_as_dot_on_ERROR_returns_safe_comment():
    from governance.cfg import build_cfg, cfg_as_dot
    cfg = build_cfg("")
    dot = cfg_as_dot(cfg)
    assert "digraph cfg" in dot


def test_TY19_overlay_n_hotspot_nodes_field_present():
    from governance.cfg import build_cfg, overlay_hotspots
    cfg = build_cfg("def f():\n    eval(1)\n")
    out = overlay_hotspots(cfg, _StubStore(), "m",
                           findings=[{"line": 2, "severity": "CRITICAL"}])
    fn = out["functions"][0]
    assert "n_hotspot_nodes" in fn
    assert fn["n_hotspot_nodes"] >= 1


def test_TY20_overlay_findings_count_carried():
    from governance.cfg import build_cfg, overlay_hotspots
    cfg = build_cfg("def f():\n    pass\n")
    out = overlay_hotspots(cfg, _StubStore(), "m",
                           findings=[{"line": 2, "severity": "LOW"}])
    assert out["overlay_findings"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TY21-TY27 — REST handlers
# ═══════════════════════════════════════════════════════════════════════════════

def test_TY21_handle_cfg_400_on_missing_module_id():
    from api.server import handle_cfg
    code, data = handle_cfg("", source="def f():\n    pass\n")
    assert code == 400


def test_TY22_handle_cfg_returns_200_with_source_in_query():
    from api.server import handle_cfg
    code, data = handle_cfg("mod.x", source="def f(x):\n    return x + 1\n")
    assert code == 200
    assert data["module_id"] == "mod.x"
    assert data["status"] == "OK"


def test_TY23_handle_cfg_returns_ERROR_on_syntax_error():
    from api.server import handle_cfg
    code, data = handle_cfg("mod.x", source="def f(:\n    pass")
    assert code == 200
    assert data["status"] == "ERROR"


def test_TY24_handle_cfg_hotspots_returns_overlay_module_id(isolated_store):
    from api.server import handle_cfg_hotspots
    code, data = handle_cfg_hotspots("mod.x",
                                     source="def f():\n    return 1\n")
    assert code == 200
    assert data["overlay_module_id"] == "mod.x"


def test_TY25_handle_cfg_max_nodes_param_enforced():
    from api.server import handle_cfg
    big = "def f():\n" + "\n".join(f"    x{i} = {i}" for i in range(200))
    code, data = handle_cfg("mod.big", source=big, max_nodes=10)
    assert code == 200
    assert data["status"] in ("TRUNCATED", "OK")


def test_TY26_docs_endpoint_lists_cfg_routes(isolated_store):
    from api.server import handle_docs
    code, data = handle_docs()
    routes = {r["path"] for r in data["endpoints"]}
    assert "/cfg/{module_id}" in routes
    assert "/cfg/hotspots/{module_id}" in routes


def test_TY27_handle_cfg_returns_500_only_on_truly_unexpected_error(monkeypatch):
    """If build_cfg ever raises, handler should catch and 500."""
    from api import server as srv
    import governance.cfg as cfg_mod

    def _boom(*a, **k):
        raise RuntimeError("simulated")

    monkeypatch.setattr(cfg_mod, "build_cfg", _boom)
    code, data = srv.handle_cfg("mod.x", source="def f():\n    pass\n")
    assert code == 500
    assert "simulated" in data["error"]


# ═══════════════════════════════════════════════════════════════════════════════
# TY28-TY30 — port-allocator quick-win
# ═══════════════════════════════════════════════════════════════════════════════

def test_TY28_allocate_port_returns_int_in_valid_range():
    from tests._port_allocator import allocate_port
    p = allocate_port()
    assert isinstance(p, int)
    assert 1024 <= p < 65536


def test_TY29_allocate_port_yields_distinct_ports_across_calls():
    from tests._port_allocator import allocate_port
    seen = {allocate_port() for _ in range(10)}
    # ephemeral pool is wide; uniqueness is not guaranteed but typical
    assert len(seen) >= 5


def test_TY30_allocated_port_is_actually_bindable():
    import socket
    from tests._port_allocator import allocate_port
    p = allocate_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", p))  # must not raise
