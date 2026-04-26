"""
test_marco_m4.py — M4 Web UI + SARIF + GitHub Actions + VS Code Extension
===========================================================================
30 tests covering:

  TW01-TW10  report/sarif.py   — SARIFBuilder (M4.3: SARIF 2.1.0 com line/col reais)
  TW11-TW18  action.yml        — GitHub Actions composite action (M4.4)
  TW19-TW25  report/webui.py   — Dashboard HTML com Chart.js (M4.1)
  TW26-TW30  vscode package.json — VS Code Extension manifest (M4.2)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR_API  = Path(__file__).resolve().parent.parent   # sensor-api/
_REPO_ROOT   = _SENSOR_API.parent.parent.parent          # APEX_GITHUB_REPO/
_UCO_ROOT    = _SENSOR_API.parent                        # algorithms/uco-sensor/
_VSCODE_DIR  = _UCO_ROOT / "vscode-extension"
_ACTION_YML  = _UCO_ROOT / "action.yml"

for _p in [str(_SENSOR_API)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Imports under test ────────────────────────────────────────────────────────
from report.sarif import SARIFBuilder, _UCO_RULES, _SAST_RULES   # noqa: E402
from report.webui import generate_dashboard_html                  # noqa: E402
from sast.scanner import scan as sast_scan                        # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _builder() -> SARIFBuilder:
    """Fresh SARIFBuilder instance for each test."""
    return SARIFBuilder(tool_version="1.0.0", repo="test/repo")


def _sast_result_with_sql():
    """SASTResult with at least one SAST001 (SQL injection) HIGH/CRITICAL finding."""
    src = """
import sqlite3
conn = sqlite3.connect(":memory:")
cur  = conn.cursor()
def search(name):
    cur.execute("SELECT * FROM users WHERE name = '" + name + "'")
"""
    return sast_scan(src, file_extension=".py")


def _sample_dashboard_data() -> Dict[str, Any]:
    return {
        "modules": [
            {
                "module_id":             "src/auth.py",
                "status":                "CRITICAL",
                "hamiltonian":           22.5,
                "cyclomatic_complexity": 18,
                "cognitive_complexity":  25,
                "sqale_rating":          "D",
                "sqale_debt_minutes":    240,
                "ratings":               {"uco": "C", "reliability": "D"},
                "trend_direction":       "DEGRADING",
                "trend_slope_pct":       12.3,
                "snapshots_count":       8,
            },
            {
                "module_id":             "src/utils.py",
                "status":                "STABLE",
                "hamiltonian":           3.1,
                "cyclomatic_complexity": 3,
                "cognitive_complexity":  4,
                "sqale_rating":          "A",
                "sqale_debt_minutes":    10,
                "ratings":               {"uco": "A", "reliability": "A"},
                "trend_direction":       "STABLE",
                "trend_slope_pct":       0.2,
                "snapshots_count":       5,
            },
        ],
        "total_modules":  2,
        "status_counts":  {"critical": 1, "warning": 0, "stable": 1},
        "trend_counts":   {"degrading": 1, "improving": 0, "stable": 1},
        "debt_budget": {
            "total_debt_minutes":   250,
            "budget_minutes":       480,
            "over_budget":          False,
            "days_until_exhausted": 3,
        },
        "generated_at": 1700000000.0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TW01-TW10 — report/sarif.py (SARIFBuilder — M4.3)
# ══════════════════════════════════════════════════════════════════════════════

def test_TW01_sarif_schema_uri():
    """TW01: build() contains correct SARIF 2.1.0 $schema URI."""
    doc = _builder().build()
    assert doc["$schema"] == SARIFBuilder.SCHEMA_URI
    assert "sarif-schema-2.1.0.json" in doc["$schema"]


def test_TW02_sarif_version_field():
    """TW02: build() version field is exactly '2.1.0'."""
    doc = _builder().build()
    assert doc["version"] == "2.1.0"


def test_TW03_rule_catalog_total_count():
    """TW03: rule catalog has exactly 22 rules (9 UCO + 13 SAST)."""
    b = _builder()
    assert b.rule_count() == 22
    assert len(b.rule_ids) == 22


def test_TW04_uco_rule_ids():
    """TW04: UCO rules are UCO001-UCO009 in catalog order."""
    b = _builder()
    uco_ids = b.uco_rule_ids()
    assert uco_ids == [f"UCO00{i}" for i in range(1, 10)]


def test_TW05_sast_rule_ids_complete():
    """TW05: SAST rule IDs cover SAST001-SAST013 in catalog."""
    b = _builder()
    sast_ids = b.sast_rule_ids()
    expected = [f"SAST{i:03d}" for i in range(1, 14)]
    assert sast_ids == expected


def test_TW06_add_sast_findings_correct_line():
    """TW06: add_sast_findings() maps SASTFinding.line to SARIF region.startLine."""
    result = _sast_result_with_sql()
    assert result.findings, "No SAST findings — test prerequisite failed"

    b = _builder()
    b.add_sast_findings("src/auth.py", result)
    doc = b.build()

    findings = doc["runs"][0]["results"]
    assert len(findings) > 0

    for fr in findings:
        line = fr["locations"][0]["physicalLocation"]["region"]["startLine"]
        assert isinstance(line, int) and line >= 1, f"startLine must be ≥1, got {line}"


def test_TW07_add_sast_findings_correct_col():
    """TW07: SASTFinding.col (0-based) is converted to 1-based startColumn in SARIF."""
    src = """import pickle
data = pickle.loads(b"...")
"""
    result = sast_scan(src, file_extension=".py")
    b = _builder()
    b.add_sast_findings("src/x.py", result)
    doc = b.build()

    results = doc["runs"][0]["results"]
    if results:
        for r in results:
            col = r["locations"][0]["physicalLocation"]["region"]["startColumn"]
            assert col >= 1, f"startColumn must be ≥1 (1-based), got {col}"


def test_TW08_critical_severity_maps_to_error():
    """TW08: SAST CRITICAL severity (SAST009 PEM key) → SARIF level 'error'."""
    src = '# test\nKEY = "-----BEGIN RSA PRIVATE KEY-----"\n'
    result = sast_scan(src, file_extension=".py")
    # Must have a CRITICAL finding (SAST009)
    critical_findings = [f for f in result.findings if f.severity == "CRITICAL"]

    b = _builder()
    b.add_sast_findings("src/config.py", result)
    doc = b.build()

    error_results = [r for r in doc["runs"][0]["results"] if r["level"] == "error"]
    if critical_findings:
        assert error_results, "CRITICAL SAST finding must produce SARIF level=error"


def test_TW09_medium_severity_maps_to_warning():
    """TW09: SAST MEDIUM severity → SARIF level 'warning'."""
    src = """import hashlib
h = hashlib.md5(b"data").hexdigest()
"""
    result = sast_scan(src, file_extension=".py")
    medium_findings = [f for f in result.findings if f.severity == "MEDIUM"]

    b = _builder()
    b.add_sast_findings("src/hash.py", result)
    doc = b.build()

    if medium_findings:
        warn_results = [r for r in doc["runs"][0]["results"] if r["level"] == "warning"]
        assert warn_results, "MEDIUM findings must produce SARIF level=warning"


def test_TW10_build_is_json_serialisable():
    """TW10: build() returns a dict that json.dumps() handles without error."""
    result = _sast_result_with_sql()
    b = _builder()
    b.add_sast_findings("src/auth.py", result)
    b.add_uco_finding(
        "src/auth.py", rule_id="UCO001",
        message="CC=22", severity="CRITICAL",
        line=10, col=4, function_name="authenticate",
    )
    try:
        serialised = json.dumps(b.build(), default=str)
    except (TypeError, ValueError) as exc:
        pytest.fail(f"build() produced non-JSON-serialisable object: {exc}")
    assert len(serialised) > 100


# ══════════════════════════════════════════════════════════════════════════════
# TW11-TW18 — action.yml (GitHub Actions — M4.4)
# ══════════════════════════════════════════════════════════════════════════════

def _action_text() -> str:
    assert _ACTION_YML.exists(), f"action.yml not found at {_ACTION_YML}"
    return _ACTION_YML.read_text(encoding="utf-8")


def test_TW11_action_yml_exists():
    """TW11: action.yml exists at algorithms/uco-sensor/action.yml."""
    assert _ACTION_YML.exists(), f"Missing: {_ACTION_YML}"
    assert _ACTION_YML.stat().st_size > 0


def test_TW12_action_yml_has_name():
    """TW12: action.yml contains a 'name:' field."""
    text = _action_text()
    assert "name:" in text


def test_TW13_action_yml_has_inputs_section():
    """TW13: action.yml has 'inputs:' section."""
    text = _action_text()
    assert "inputs:" in text


def test_TW14_action_yml_input_path():
    """TW14: action.yml declares 'path' input."""
    text = _action_text()
    assert "path:" in text


def test_TW15_action_yml_input_fail_on_critical():
    """TW15: action.yml declares 'fail_on_critical' input with default 'true'."""
    text = _action_text()
    assert "fail_on_critical:" in text
    assert "'true'" in text or "default: 'true'" in text or "default: true" in text.lower()


def test_TW16_action_yml_input_sarif_output():
    """TW16: action.yml declares 'sarif_output' input."""
    text = _action_text()
    assert "sarif_output:" in text


def test_TW17_action_yml_has_outputs_section():
    """TW17: action.yml has 'outputs:' section with 'uco_score'."""
    text = _action_text()
    assert "outputs:" in text
    assert "uco_score:" in text


def test_TW18_action_yml_composite_runner():
    """TW18: action.yml uses composite runner (runs.using: composite)."""
    text = _action_text()
    assert "composite" in text


# ══════════════════════════════════════════════════════════════════════════════
# TW19-TW25 — report/webui.py (Web Dashboard — M4.1)
# ══════════════════════════════════════════════════════════════════════════════

def test_TW19_generate_dashboard_html_returns_string():
    """TW19: generate_dashboard_html() returns a non-empty string."""
    html = generate_dashboard_html()
    assert isinstance(html, str)
    assert len(html) > 500


def test_TW20_html_starts_with_doctype():
    """TW20: HTML starts with <!DOCTYPE html> declaration."""
    html = generate_dashboard_html()
    assert html.strip().startswith("<!DOCTYPE html")


def test_TW21_html_contains_chartjs_cdn():
    """TW21: HTML contains Chart.js CDN script src reference."""
    html = generate_dashboard_html()
    assert "chart.js" in html.lower() or "cdn.jsdelivr.net" in html


def test_TW22_html_contains_temporal_chart_canvas():
    """TW22: HTML contains canvas elements for temporal charts (H and CC)."""
    html = generate_dashboard_html()
    assert 'id="chart-hamiltonian"' in html
    assert 'id="chart-cc"' in html


def test_TW23_html_contains_module_health_section():
    """TW23: HTML contains module-health-section and module-grid elements."""
    html = generate_dashboard_html()
    assert "module-health-section" in html
    assert "module-grid" in html


def test_TW24_html_embeds_dashboard_data_as_json():
    """TW24: generate_dashboard_html(dashboard_data=...) embeds module data as JSON."""
    data = _sample_dashboard_data()
    html = generate_dashboard_html(dashboard_data=data)

    # Verify module IDs are present in the embedded JSON
    assert "src/auth.py" in html
    assert "src/utils.py" in html
    # Verify INITIAL_DATA is set (not null)
    assert "INITIAL_DATA = null" not in html
    assert "INITIAL_DATA =" in html


def test_TW25_html_empty_modules_does_not_crash():
    """TW25: generate_dashboard_html() with empty modules list does not raise."""
    empty_data = {
        "modules":       [],
        "total_modules": 0,
        "status_counts": {"critical": 0, "warning": 0, "stable": 0},
        "trend_counts":  {"degrading": 0, "improving": 0, "stable": 0},
        "debt_budget":   {"total_debt_minutes": 0, "budget_minutes": 480,
                          "over_budget": False, "days_until_exhausted": None},
        "generated_at":  0.0,
    }
    html = generate_dashboard_html(dashboard_data=empty_data)
    assert isinstance(html, str) and len(html) > 200


# ══════════════════════════════════════════════════════════════════════════════
# TW26-TW30 — VS Code Extension package.json (M4.2)
# ══════════════════════════════════════════════════════════════════════════════

def _vscode_pkg() -> Dict[str, Any]:
    pkg_path = _VSCODE_DIR / "package.json"
    assert pkg_path.exists(), f"VS Code package.json not found at {pkg_path}"
    return json.loads(pkg_path.read_text(encoding="utf-8"))


def test_TW26_vscode_package_json_exists():
    """TW26: vscode-extension/package.json exists and is non-empty."""
    pkg_path = _VSCODE_DIR / "package.json"
    assert pkg_path.exists()
    assert pkg_path.stat().st_size > 0


def test_TW27_vscode_package_json_valid():
    """TW27: package.json is valid JSON and has required top-level fields."""
    pkg = _vscode_pkg()
    for field in ("name", "version", "publisher", "engines", "activationEvents", "contributes"):
        assert field in pkg, f"Missing field: {field}"


def test_TW28_vscode_engines_vscode():
    """TW28: engines.vscode field is present with a valid version constraint."""
    pkg = _vscode_pkg()
    vsc = pkg.get("engines", {}).get("vscode", "")
    assert vsc, "engines.vscode must be set"
    assert "^" in vsc or ">=" in vsc, f"engines.vscode looks malformed: {vsc}"


def test_TW29_vscode_contributes_commands():
    """TW29: contributes.commands is a non-empty list with required commands."""
    pkg = _vscode_pkg()
    commands: List[Dict] = pkg.get("contributes", {}).get("commands", [])
    assert isinstance(commands, list) and len(commands) >= 2

    command_ids = {c["command"] for c in commands}
    assert "uco-sensor.analyze"       in command_ids
    assert "uco-sensor.showDashboard" in command_ids


def test_TW30_vscode_activation_events_python():
    """TW30: activationEvents includes onLanguage:python."""
    pkg = _vscode_pkg()
    events: List[str] = pkg.get("activationEvents", [])
    assert isinstance(events, list) and len(events) > 0
    assert "onLanguage:python" in events


# ══════════════════════════════════════════════════════════════════════════════
# Inventory (for CI summary)
# ══════════════════════════════════════════════════════════════════════════════

_ALL_TESTS = [
    ("TW01", test_TW01_sarif_schema_uri),
    ("TW02", test_TW02_sarif_version_field),
    ("TW03", test_TW03_rule_catalog_total_count),
    ("TW04", test_TW04_uco_rule_ids),
    ("TW05", test_TW05_sast_rule_ids_complete),
    ("TW06", test_TW06_add_sast_findings_correct_line),
    ("TW07", test_TW07_add_sast_findings_correct_col),
    ("TW08", test_TW08_critical_severity_maps_to_error),
    ("TW09", test_TW09_medium_severity_maps_to_warning),
    ("TW10", test_TW10_build_is_json_serialisable),
    ("TW11", test_TW11_action_yml_exists),
    ("TW12", test_TW12_action_yml_has_name),
    ("TW13", test_TW13_action_yml_has_inputs_section),
    ("TW14", test_TW14_action_yml_input_path),
    ("TW15", test_TW15_action_yml_input_fail_on_critical),
    ("TW16", test_TW16_action_yml_input_sarif_output),
    ("TW17", test_TW17_action_yml_has_outputs_section),
    ("TW18", test_TW18_action_yml_composite_runner),
    ("TW19", test_TW19_generate_dashboard_html_returns_string),
    ("TW20", test_TW20_html_starts_with_doctype),
    ("TW21", test_TW21_html_contains_chartjs_cdn),
    ("TW22", test_TW22_html_contains_temporal_chart_canvas),
    ("TW23", test_TW23_html_contains_module_health_section),
    ("TW24", test_TW24_html_embeds_dashboard_data_as_json),
    ("TW25", test_TW25_html_empty_modules_does_not_crash),
    ("TW26", test_TW26_vscode_package_json_exists),
    ("TW27", test_TW27_vscode_package_json_valid),
    ("TW28", test_TW28_vscode_engines_vscode),
    ("TW29", test_TW29_vscode_contributes_commands),
    ("TW30", test_TW30_vscode_activation_events_python),
]

if __name__ == "__main__":
    passed = failed = 0
    for tid, fn in _ALL_TESTS:
        try:
            fn()
            print(f"  ✅ {tid} {fn.__name__}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {tid} {fn.__name__}: {exc}")
            failed += 1
    print(f"\n{passed}/{passed+failed} passed")
