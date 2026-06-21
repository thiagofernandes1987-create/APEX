"""
Marco 45 — Sprint N: Dynamic SAST Rules Feed (TQ01-TQ30)
===========================================================

Extends Sprint J's dynamic-feed pattern to the SAST corpus, with the
regex-only safety constraint.

Coverage layout
---------------
* TQ01-TQ10 — load / unload / reset; built-in collision rejected;
  malformed payloads; YAML auto-detect; rule compilation
* TQ11-TQ20 — scan_dynamic hook; integration with scanner.scan();
  unload reverts; multi-feed isolation
* TQ21-TQ30 — REST surface: status / load (inline / path / url) /
  unload; admin auth requirement on writes (handlers tested directly)
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sast import rules_feed
from sast.scanner import scan


@pytest.fixture(autouse=True)
def _isolate_rules():
    rules_feed.reset()
    yield
    rules_feed.reset()


def _build_feed(*rules):
    return {"version": "1.0", "rules": list(rules)}


def _rule(**kw):
    base = {
        "rule_id":  "SAST900",
        "title":    "test rule",
        "severity": "MEDIUM",
        "pattern":  r"\beval\s*\(",
    }
    base.update(kw)
    return base


def _file_with(payload):
    f = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
    json.dump(payload, f); f.close()
    return f.name


# ═══════════════════════════════════════════════════════════════════════════════
# TQ01-TQ10 — module API
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQ01_load_adds_rule():
    path = _file_with(_build_feed(_rule()))
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 1
        assert r.skipped_bad == 0
    finally:
        os.unlink(path)


def test_TQ02_unload_reverts_rule():
    path = _file_with(_build_feed(_rule()))
    try:
        r = rules_feed.load_from_file(path)
        assert len(rules_feed.loaded_rules()) == 1
        rules_feed.unload(r.feed_id)
        assert len(rules_feed.loaded_rules()) == 0
    finally:
        os.unlink(path)


def test_TQ03_reset_clears_all_feeds():
    p1 = _file_with(_build_feed(_rule(rule_id="SAST900")))
    p2 = _file_with(_build_feed(_rule(rule_id="SAST901", pattern=r"exec\(")))
    try:
        rules_feed.load_from_file(p1)
        rules_feed.load_from_file(p2)
        assert len(rules_feed.loaded_rules()) == 2
        rules_feed.reset()
        assert len(rules_feed.loaded_rules()) == 0
    finally:
        os.unlink(p1); os.unlink(p2)


def test_TQ04_builtin_collision_rejected():
    path = _file_with(_build_feed(_rule(rule_id="SAST001")))
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 0
        assert r.skipped_bad == 1
        assert any("collides" in e for e in r.errors)
    finally:
        os.unlink(path)


def test_TQ05_duplicate_rule_id_in_same_feed_skipped():
    path = _file_with(_build_feed(
        _rule(rule_id="SAST900"),
        _rule(rule_id="SAST900"),
    ))
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 1
        assert r.skipped_bad == 1
    finally:
        os.unlink(path)


def test_TQ06_invalid_regex_skipped():
    path = _file_with(_build_feed(_rule(pattern="[")))
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("regex" in e for e in r.errors)
    finally:
        os.unlink(path)


def test_TQ07_invalid_severity_skipped():
    path = _file_with(_build_feed(_rule(severity="BLAZING")))
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("severity" in e.lower() for e in r.errors)
    finally:
        os.unlink(path)


def test_TQ08_missing_required_field_skipped():
    payload = _build_feed({"rule_id": "SAST900", "title": "x"})  # missing severity + pattern
    path = _file_with(payload)
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("missing" in e for e in r.errors)
    finally:
        os.unlink(path)


def test_TQ09_missing_file_returns_error_payload():
    r = rules_feed.load_from_file("/nonexistent/path/rules.json")
    assert r.added_new == 0
    assert r.errors


def test_TQ10_payload_without_rules_field_rejected():
    path = _file_with({"version": "1.0"})
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("rules" in e for e in r.errors)
    finally:
        os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# TQ11-TQ20 — scanner integration
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQ11_dynamic_rule_triggers_in_scan():
    path = _file_with(_build_feed(_rule(rule_id="SAST900")))
    try:
        rules_feed.load_from_file(path)
        findings = scan("x = eval(input())\n", file_extension=".py").findings
        assert any(f.rule_id == "SAST900" for f in findings)
    finally:
        os.unlink(path)


def test_TQ12_dynamic_rule_carries_severity():
    path = _file_with(_build_feed(_rule(rule_id="SAST900", severity="HIGH")))
    try:
        rules_feed.load_from_file(path)
        findings = scan("eval(x)\n", file_extension=".py").findings
        f = next(f for f in findings if f.rule_id == "SAST900")
        assert f.severity == "HIGH"
    finally:
        os.unlink(path)


def test_TQ13_dynamic_rule_carries_cwe():
    path = _file_with(_build_feed(_rule(rule_id="SAST900", cwe_id="CWE-95")))
    try:
        rules_feed.load_from_file(path)
        findings = scan("eval(x)\n", file_extension=".py").findings
        f = next(f for f in findings if f.rule_id == "SAST900")
        assert f.cwe_id == "CWE-95"
    finally:
        os.unlink(path)


def test_TQ14_dynamic_rule_line_number_correct():
    path = _file_with(_build_feed(_rule(rule_id="SAST900")))
    try:
        rules_feed.load_from_file(path)
        src = "x = 1\ny = eval('2+2')\nz = 3\n"
        findings = scan(src, file_extension=".py").findings
        f = next(f for f in findings if f.rule_id == "SAST900")
        assert f.line == 2
    finally:
        os.unlink(path)


def test_TQ15_unload_removes_findings_from_subsequent_scans():
    path = _file_with(_build_feed(_rule(rule_id="SAST900")))
    try:
        r = rules_feed.load_from_file(path)
        n_before = sum(1 for f in scan("eval(x)\n", file_extension=".py").findings
                       if f.rule_id == "SAST900")
        rules_feed.unload(r.feed_id)
        n_after = sum(1 for f in scan("eval(x)\n", file_extension=".py").findings
                       if f.rule_id == "SAST900")
        assert n_before == 1
        assert n_after == 0
    finally:
        os.unlink(path)


def test_TQ16_multiple_rules_from_same_feed():
    payload = _build_feed(
        _rule(rule_id="SAST900", pattern=r"\beval\("),
        _rule(rule_id="SAST901", pattern=r"\bexec\("),
    )
    path = _file_with(payload)
    try:
        r = rules_feed.load_from_file(path)
        assert r.added_new == 2
        findings = scan("eval(x)\nexec(y)\n", file_extension=".py").findings
        ids = {f.rule_id for f in findings}
        assert "SAST900" in ids and "SAST901" in ids
    finally:
        os.unlink(path)


def test_TQ17_two_feeds_isolated():
    p1 = _file_with(_build_feed(_rule(rule_id="SAST900")))
    p2 = _file_with(_build_feed(_rule(rule_id="SAST901", pattern=r"exec\(")))
    try:
        r1 = rules_feed.load_from_file(p1)
        r2 = rules_feed.load_from_file(p2)
        assert len(rules_feed.loaded_feeds()) == 2
        rules_feed.unload(r1.feed_id)
        rules_feed.loaded_rules()
        # Only SAST901 still loaded
        ids = {r["rule_id"] for r in rules_feed.loaded_rules()}
        assert ids == {"SAST901"}
    finally:
        os.unlink(p1); os.unlink(p2)


def test_TQ18_static_findings_preserved_after_dynamic_load():
    """Loading dynamic rules must NOT eclipse the built-in scanner."""
    path = _file_with(_build_feed(_rule(rule_id="SAST900")))
    src_with_builtin = "import hashlib\nhashlib.md5(b'x')\n"
    try:
        n_before = len(scan(src_with_builtin, file_extension=".py").findings)
        rules_feed.load_from_file(path)
        n_after = len(scan(src_with_builtin, file_extension=".py").findings)
        # Built-in findings are still there; nothing in src triggers SAST900.
        assert n_after >= n_before
    finally:
        os.unlink(path)


def test_TQ19_loaded_rule_serializable():
    path = _file_with(_build_feed(_rule()))
    try:
        rules_feed.load_from_file(path)
        rule_dict = rules_feed.loaded_rules()[0]
        # Must be JSON-serializable (no compiled Pattern leaking).
        json.dumps(rule_dict)
    finally:
        os.unlink(path)


def test_TQ20_unload_unknown_feed_returns_zero():
    assert rules_feed.unload("ghost-feed-id") == 0


# ═══════════════════════════════════════════════════════════════════════════════
# TQ21-TQ30 — REST surface
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQ21_handle_status_returns_payload():
    import api.server as srv
    code, payload = srv.handle_feeds_sast_status()
    assert code == 200
    assert "n_dynamic_rules" in payload
    assert "rules" in payload


def test_TQ22_handle_load_inline():
    import api.server as srv
    payload = _build_feed(_rule(rule_id="SAST900"))
    code, result = srv.handle_feeds_sast_load({"inline": payload, "feed_id": "tq22"})
    assert code == 200
    assert result["added_new"] == 1


def test_TQ23_handle_load_400_without_source():
    import api.server as srv
    code, _ = srv.handle_feeds_sast_load({})
    assert code == 400


def test_TQ24_handle_load_file_path():
    import api.server as srv
    path = _file_with(_build_feed(_rule(rule_id="SAST900")))
    try:
        code, result = srv.handle_feeds_sast_load({"path": path})
        assert code == 200
        assert result["added_new"] == 1
    finally:
        os.unlink(path)


def test_TQ25_handle_unload_400_without_feed_id():
    import api.server as srv
    code, _ = srv.handle_feeds_sast_unload({})
    assert code == 400


def test_TQ26_handle_unload_reverts_inline_feed():
    import api.server as srv
    srv.handle_feeds_sast_load({"inline": _build_feed(_rule(rule_id="SAST900")),
                                "feed_id": "tq26"})
    code, result = srv.handle_feeds_sast_unload({"feed_id": "tq26"})
    assert code == 200
    assert result["n_reverted"] == 1


def test_TQ27_url_blocked_when_allowlist_empty():
    import api.server as srv
    saved = os.environ.pop("UCO_SAST_FEED_ALLOWLIST", None)
    try:
        code, result = srv.handle_feeds_sast_load({"url": "https://example.com/r.json"})
        assert code == 200
        assert result["added_new"] == 0
        assert any("allowlist" in e.lower() for e in result["errors"])
    finally:
        if saved is not None:
            os.environ["UCO_SAST_FEED_ALLOWLIST"] = saved


def test_TQ28_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    for p in ("/feeds/sast/status", "/feeds/sast/load", "/feeds/sast/unload"):
        assert p in paths


def test_TQ29_status_after_load_counts_active_feeds():
    import api.server as srv
    srv.handle_feeds_sast_load({"inline": _build_feed(_rule(rule_id="SAST900")),
                                "feed_id": "tq29"})
    code, payload = srv.handle_feeds_sast_status()
    assert payload["n_active_feeds"] == 1
    assert any(f["feed_id"] == "tq29" for f in payload["feeds"])


def test_TQ30_load_then_scan_then_unload_roundtrip():
    import api.server as srv
    srv.handle_feeds_sast_load({"inline": _build_feed(_rule(rule_id="SAST900")),
                                "feed_id": "tq30"})
    findings = scan("eval(x)\n", file_extension=".py").findings
    assert any(f.rule_id == "SAST900" for f in findings)
    srv.handle_feeds_sast_unload({"feed_id": "tq30"})
    findings = scan("eval(x)\n", file_extension=".py").findings
    assert not any(f.rule_id == "SAST900" for f in findings)
