"""
Marco 51 — Sprint T: VS Code Extension Wiring (TY01-TY30)
=============================================================

Sprint T extended the pre-existing VS Code extension (v1.0.0 → v1.1.0)
to consume the five new horizon-90d endpoints:

  /rca, /changepoints, /similar, /granger/significant, /repair/hmc

The TypeScript surface is verified by file-content checks (no tsc in
the Python sandbox); the *contract* the extension expects is verified
by hitting the Python handlers directly and asserting payload shapes
match what UCOClient methods are coded to consume.

Coverage layout
---------------
* TY01-TY10 — UCOClient (api.ts) surface: 5 new methods exist with the
  expected signatures and HTTP paths
* TY11-TY20 — extension.ts: 4 new commands registered + 4 handler
  functions exist + module ID helper
* TY21-TY30 — server-side payload shapes match what the extension
  client expects (status/data envelope, key names)
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


# Locate the extension sources from the sensor-api test runner.
_EXT_DIR = Path(__file__).resolve().parents[2] / "vscode-extension"
_API_TS  = _EXT_DIR / "src" / "api.ts"
_EXT_TS  = _EXT_DIR / "src" / "extension.ts"
_PKG_JSON = _EXT_DIR / "package.json"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════════
# TY01-TY10 — UCOClient (api.ts) surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TY01_api_ts_exists():
    assert _API_TS.is_file()


def test_TY02_extension_ts_exists():
    assert _EXT_TS.is_file()


def test_TY03_package_json_exists():
    assert _PKG_JSON.is_file()


def test_TY04_client_has_getRCA_method():
    assert "async getRCA(" in _read(_API_TS)


def test_TY05_client_has_getChangepoints_method():
    assert "async getChangepoints(" in _read(_API_TS)


def test_TY06_client_has_repairHMC_method():
    assert "async repairHMC(" in _read(_API_TS)


def test_TY07_client_has_getSimilar_method():
    assert "async getSimilar(" in _read(_API_TS)


def test_TY08_client_has_getGrangerSignificant_method():
    assert "async getGrangerSignificant(" in _read(_API_TS)


def test_TY09_client_repairHMC_uses_post_method():
    src = _read(_API_TS)
    # Locate the method body and confirm it issues a POST.
    chunk = src.split("async repairHMC(", 1)[1].split("\n    /**", 1)[0]
    assert '"POST", "/repair/hmc"' in chunk


def test_TY10_client_has_getLSPDiagnostics_method():
    """LSP wiring is the contract for IDE-side diagnostics."""
    assert "async getLSPDiagnostics(" in _read(_API_TS)


# ═══════════════════════════════════════════════════════════════════════════════
# TY11-TY20 — extension.ts + package.json contributes
# ═══════════════════════════════════════════════════════════════════════════════

def test_TY11_extension_registers_showRCA_command():
    assert 'registerCommand("uco-sensor.showRCA"' in _read(_EXT_TS)


def test_TY12_extension_registers_showChangepoints_command():
    assert 'registerCommand("uco-sensor.showChangepoints"' in _read(_EXT_TS)


def test_TY13_extension_registers_showSimilar_command():
    assert 'registerCommand("uco-sensor.showSimilar"' in _read(_EXT_TS)


def test_TY14_extension_registers_repairHMC_command():
    assert 'registerCommand("uco-sensor.repairHMC"' in _read(_EXT_TS)


def test_TY15_extension_has_currentModuleId_helper():
    assert "function currentModuleId()" in _read(_EXT_TS)


def test_TY16_repairHMC_handler_uses_deterministic_true():
    """CI-friendly default."""
    src = _read(_EXT_TS)
    chunk = src.split("async function repairHMC()", 1)[1]
    assert "deterministic: true" in chunk


def test_TY17_repairHMC_handler_uses_preserve_aps_true():
    src = _read(_EXT_TS)
    chunk = src.split("async function repairHMC()", 1)[1]
    assert "preserve_aps: true" in chunk


def test_TY18_package_json_lists_four_new_commands():
    pkg = json.loads(_read(_PKG_JSON))
    cmd_ids = {c["command"] for c in pkg["contributes"]["commands"]}
    for cmd in ("uco-sensor.showRCA", "uco-sensor.showChangepoints",
                "uco-sensor.showSimilar", "uco-sensor.repairHMC"):
        assert cmd in cmd_ids


def test_TY19_package_json_repairHMC_python_only():
    """HMC repair is Python-only in v1.1.0."""
    pkg = json.loads(_read(_PKG_JSON))
    entries = pkg["contributes"]["menus"]["commandPalette"]
    repair = next((e for e in entries if e.get("command") == "uco-sensor.repairHMC"), None)
    assert repair is not None
    assert "python" in repair.get("when", "").lower()


def test_TY20_package_json_version_bumped_to_1_1_0():
    pkg = json.loads(_read(_PKG_JSON))
    assert pkg["version"] == "1.1.0"


# ═══════════════════════════════════════════════════════════════════════════════
# TY21-TY30 — server-side payload contract (what the extension consumes)
# ═══════════════════════════════════════════════════════════════════════════════

def _shifted_store():
    """History with a regime shift — exercises RCA / changepoints / granger."""
    from core.data_structures import MetricVector
    from sensor_storage.snapshot_store import SnapshotStore
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(25):
        h    = 5.0 if i < 10 else 50.0
        cc   = 2 + (i if i < 10 else 10)
        bugs = 0.1 + max(0, (i - 3) * 0.05)
        s.insert(MetricVector(
            module_id="ext.demo", commit_hash=f"c{i:02d}", timestamp=base + i,
            hamiltonian=h, cyclomatic_complexity=cc,
            infinite_loop_risk=0.0, dsm_density=0.4, dsm_cyclic_ratio=0.1,
            dependency_instability=0.2, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=bugs,
        ))
    return s


def test_TY21_rca_payload_has_summary_text_field():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca("ext.demo")
    assert code == 200
    assert "summary_text" in payload


def test_TY22_rca_payload_has_primary_root_when_OK():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca("ext.demo")
    assert "primary_root" in payload   # may be None, but key present


def test_TY23_changepoints_payload_has_changepoints_list():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_changepoints("ext.demo")
    assert code == 200
    assert isinstance(payload.get("changepoints"), list)


def test_TY24_changepoint_record_has_commit_hash_and_confidence():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_changepoints("ext.demo")
    if payload["changepoints"]:
        cp = payload["changepoints"][0]
        assert "commit_hash" in cp
        assert "confidence"  in cp
        assert "affected_channels" in cp


def test_TY25_similar_payload_has_hits_list():
    import api.server as srv
    from sensor_storage.snapshot_store import SnapshotStore
    # Build minimal multi-module store for /similar
    import math
    from core.data_structures import MetricVector
    from metrics.extended_vectors import SecurityVector
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod, fn in [
        ("a", lambda i: int(5 + 10 * math.sin(2*math.pi*i/6))),
        ("b", lambda i: int(5 + 10 * math.sin(2*math.pi*i/6 + 0.5))),
    ]:
        for i in range(20):
            mv = MetricVector(mod, f"c{i:02d}", base+i, hamiltonian=5.0,
                              cyclomatic_complexity=2, infinite_loop_risk=0.0,
                              dsm_density=0.4, dsm_cyclic_ratio=0.1,
                              dependency_instability=0.2, syntactic_dead_code=0,
                              duplicate_block_count=0, halstead_bugs=0.1)
            mv.security = SecurityVector(sca_vulnerable_deps=max(0, fn(i)))
            s.insert(mv)
    srv._store = s
    code, payload = srv.handle_similar("a", k=5)
    assert code == 200
    assert isinstance(payload.get("hits"), list)


def test_TY26_similar_hit_carries_distance_and_module_id():
    import api.server as srv
    from sensor_storage.snapshot_store import SnapshotStore
    import math
    from core.data_structures import MetricVector
    from metrics.extended_vectors import SecurityVector
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod in ("a", "b"):
        for i in range(20):
            mv = MetricVector(mod, f"c{i:02d}", base+i, hamiltonian=5.0,
                              cyclomatic_complexity=2, infinite_loop_risk=0.0,
                              dsm_density=0.4, dsm_cyclic_ratio=0.1,
                              dependency_instability=0.2, syntactic_dead_code=0,
                              duplicate_block_count=0, halstead_bugs=0.1)
            mv.security = SecurityVector(sca_vulnerable_deps=i + (0 if mod == "a" else 1))
            s.insert(mv)
    srv._store = s
    _, payload = srv.handle_similar("a", k=5)
    if payload["hits"]:
        h = payload["hits"][0]
        assert "module_id" in h
        assert "distance"  in h


def test_TY27_granger_significant_payload_has_pairs():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_granger_significant("ext.demo", max_lag=2)
    assert code == 200
    assert "pairs" in payload


def test_TY28_repair_hmc_payload_has_patched_source_and_status():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": "def f():\n    if True:\n        return 1\n",
        "n_steps": 3,
        "deterministic": True,
    })
    assert code == 200
    assert "patched_source" in payload
    assert "status" in payload


def test_TY29_repair_hmc_summary_text_present():
    import api.server as srv
    code, payload = srv.handle_repair_hmc({
        "code": "x = 1\n", "n_steps": 3, "deterministic": True,
    })
    assert "summary_text" in payload


def test_TY30_extension_version_matches_sprint_T():
    """End-to-end: package.json version must reflect Sprint T release."""
    pkg = json.loads(_read(_PKG_JSON))
    assert pkg["version"] == "1.1.0"
    # Spot-check: at least one command from Sprint T present in contributes
    cmd_ids = {c["command"] for c in pkg["contributes"]["commands"]}
    assert "uco-sensor.repairHMC" in cmd_ids
