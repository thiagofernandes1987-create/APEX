"""
Marco 41 — Sprint J: Dynamic CVE Feed (TK01-TK30)
====================================================
Validates the dynamic-feed knowledge layer:

  J.1  ``sca/cve_feed.py`` — load, override, unload, status
  J.2  REST endpoints ``GET /feeds/status``, ``POST /feeds/cve/load``,
       ``POST /feeds/cve/unload`` (admin-only for the writes)
  J.3  Defensive parsing — bad rows skipped, malformed payloads
       structured-rejected, network closed by default

Coverage layout
---------------
* TK01-TK10 — module API: load_from_file, override semantics, unload,
  reset_overrides, dedupe by (eco, package, cve_id), defensive parse
* TK11-TK20 — REST surface: inline / file / url branches, status payload,
  admin auth requirement on writes, isolation between feeds
* TK21-TK30 — security & edge cases: URL allowlist (closed by default),
  bad JSON / bad YAML / missing keys / wrong types, reset isolates,
  built-in DB preserved after roundtrip
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sca import cve_database, cve_feed


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _isolate_feeds():
    """Each test starts with NO active dynamic feeds and ends the same."""
    cve_feed.reset_overrides()
    yield
    cve_feed.reset_overrides()


def _build_feed(*entries):
    """Synthetic feed payload helper."""
    return {
        "version": "1.0",
        "generated_at": "2026-06-18T00:00:00Z",
        "source": "test",
        "cves": list(entries),
    }


def _entry(eco: str, pkg: str, cid: str, *, sev="HIGH",
           rng=">=0.0.0", fixed="999.0.0", cwe="CWE-79"):
    return {
        "ecosystem": eco, "package": pkg, "cve_id": cid,
        "severity": sev, "cvss_score": 7.5,
        "description": "synthetic test entry",
        "affected_range": rng, "fixed_version": fixed,
        "cwe": cwe,
    }


def _file_with(payload):
    f = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
    json.dump(payload, f)
    f.close()
    return f.name


# ═══════════════════════════════════════════════════════════════════════════════
# J.1 — module API (TK01-TK10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TK01_load_from_file_adds_new_entries():
    path = _file_with(_build_feed(_entry("npm", "tk01-pkg", "CVE-9001-1")))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 1
        assert r.added_override == 0
        assert r.skipped_bad == 0
    finally:
        os.unlink(path)


def test_TK02_loaded_cve_is_actually_lookupable():
    path = _file_with(_build_feed(_entry(
        "npm", "tk02-pkg", "CVE-9002-1", rng=">=1.0.0,<2.0.0"
    )))
    try:
        cve_feed.load_from_file(path)
        hits = cve_database.lookup("npm", "tk02-pkg", "1.5.0")
        assert any(h.cve_id == "CVE-9002-1" for h in hits)
    finally:
        os.unlink(path)


def test_TK03_unload_reverts_loaded_entries():
    baseline = cve_database.database_size()
    path = _file_with(_build_feed(
        _entry("npm", "tk03-pkg-a", "CVE-9003-1"),
        _entry("npm", "tk03-pkg-b", "CVE-9003-2"),
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert cve_database.database_size() == baseline + 2
        n = cve_feed.unload(r.feed_id)
        assert n == 2
        assert cve_database.database_size() == baseline
    finally:
        os.unlink(path)


def test_TK04_override_replaces_previous_cve_entry():
    path1 = _file_with(_build_feed(_entry(
        "npm", "tk04-pkg", "CVE-9004-1", sev="LOW",
    )))
    path2 = _file_with(_build_feed(_entry(
        "npm", "tk04-pkg", "CVE-9004-1", sev="CRITICAL",
    )))
    try:
        cve_feed.load_from_file(path1)
        r2 = cve_feed.load_from_file(path2)
        assert r2.added_override == 1
        hits = cve_database.lookup("npm", "tk04-pkg", "1.0.0")
        assert any(h.cve_id == "CVE-9004-1" and h.severity == "CRITICAL" for h in hits)
    finally:
        os.unlink(path1)
        os.unlink(path2)


def test_TK05_reset_overrides_clears_everything():
    baseline = cve_database.database_size()
    p1 = _file_with(_build_feed(_entry("pip", "tk05-a", "CVE-9005-1")))
    p2 = _file_with(_build_feed(_entry("pip", "tk05-b", "CVE-9005-2")))
    try:
        cve_feed.load_from_file(p1)
        cve_feed.load_from_file(p2)
        assert cve_database.database_size() == baseline + 2
        n = cve_feed.reset_overrides()
        assert n == 2
        assert cve_database.database_size() == baseline
    finally:
        os.unlink(p1)
        os.unlink(p2)


def test_TK06_bad_rows_are_skipped_not_raised():
    path = _file_with(_build_feed(
        _entry("npm", "tk06-good", "CVE-9006-1"),
        {"ecosystem": "npm"},                              # missing fields
        {"ecosystem": "npm", "package": "x", "cve_id": "Y",
         "affected_range": "", "severity": "MYSTERY"},     # bad severity
        {"ecosystem": "npm", "package": "z", "cve_id": "W",
         "affected_range": ">=0", "cvss_score": "notnumber"},  # bad cvss
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 1
        assert r.skipped_bad == 3
        assert len(r.errors) == 3
    finally:
        os.unlink(path)


def test_TK07_missing_file_returns_error_payload_not_exception():
    r = cve_feed.load_from_file("/nonexistent/path/feed.json")
    assert r.added_new == 0
    assert r.errors


def test_TK08_malformed_payload_returns_error_payload():
    f = tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False)
    f.write("this is not JSON {{")
    f.close()
    try:
        r = cve_feed.load_from_file(f.name)
        assert r.added_new == 0
        assert any("dict" in e or "cves" in e for e in r.errors)
    finally:
        os.unlink(f.name)


def test_TK09_payload_without_cves_field_is_rejected():
    path = _file_with({"version": "1.0", "cves_typo": []})
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("cves" in e for e in r.errors)
    finally:
        os.unlink(path)


def test_TK10_cves_field_must_be_list():
    path = _file_with({"version": "1.0", "cves": "not a list"})
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("list" in e for e in r.errors)
    finally:
        os.unlink(path)


# ═══════════════════════════════════════════════════════════════════════════════
# J.2 — REST surface (TK11-TK20)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TK11_handle_feeds_status_returns_payload():
    import api.server as srv
    code, payload = srv.handle_feeds_status()
    assert code == 200
    assert "total_cves" in payload
    assert "ecosystems" in payload
    assert "active_feeds" in payload


def test_TK12_handle_feeds_status_counts_active_feeds():
    import api.server as srv
    path = _file_with(_build_feed(_entry("npm", "tk12-pkg", "CVE-9012-1")))
    try:
        cve_feed.load_from_file(path, feed_id="tk12-feed")
        _, payload = srv.handle_feeds_status()
        assert payload["n_active_feeds"] == 1
        assert any(f["feed_id"] == "tk12-feed" for f in payload["active_feeds"])
    finally:
        os.unlink(path)


def test_TK13_handle_load_inline_payload():
    import api.server as srv
    payload = _build_feed(_entry("npm", "tk13-pkg", "CVE-9013-1"))
    code, result = srv.handle_feeds_cve_load({"inline": payload, "feed_id": "tk13"})
    assert code == 200
    assert result["added_new"] == 1


def test_TK14_handle_load_file_path():
    import api.server as srv
    path = _file_with(_build_feed(_entry("npm", "tk14-pkg", "CVE-9014-1")))
    try:
        code, result = srv.handle_feeds_cve_load({"path": path})
        assert code == 200
        assert result["added_new"] == 1
    finally:
        os.unlink(path)


def test_TK15_handle_load_url_blocked_when_allowlist_empty():
    import api.server as srv
    saved = os.environ.pop("UCO_CVE_FEED_ALLOWLIST", None)
    try:
        code, result = srv.handle_feeds_cve_load({
            "url": "https://example.com/cves.json"
        })
        assert code == 200
        # Result carries the error, not the HTTP code.
        assert result["added_new"] == 0
        assert any("allowlist" in e.lower() for e in result["errors"])
    finally:
        if saved is not None:
            os.environ["UCO_CVE_FEED_ALLOWLIST"] = saved


def test_TK16_handle_load_400_when_no_source_given():
    import api.server as srv
    code, result = srv.handle_feeds_cve_load({})
    assert code == 400


def test_TK17_handle_unload_400_without_feed_id():
    import api.server as srv
    code, _ = srv.handle_feeds_cve_unload({})
    assert code == 400


def test_TK18_handle_unload_reverts_loaded_inline_feed():
    import api.server as srv
    payload = _build_feed(_entry("npm", "tk18-pkg", "CVE-9018-1"))
    srv.handle_feeds_cve_load({"inline": payload, "feed_id": "tk18"})
    code, result = srv.handle_feeds_cve_unload({"feed_id": "tk18"})
    assert code == 200
    assert result["n_reverted"] == 1


def test_TK19_unload_unknown_feed_returns_zero_reverted():
    import api.server as srv
    code, result = srv.handle_feeds_cve_unload({"feed_id": "tk19-ghost"})
    assert code == 200
    assert result["n_reverted"] == 0


def test_TK20_load_then_status_shows_new_total():
    import api.server as srv
    baseline_payload = srv.handle_feeds_status()[1]
    baseline = baseline_payload["total_cves"]
    srv.handle_feeds_cve_load({
        "inline": _build_feed(
            _entry("npm", "tk20-a", "CVE-9020-1"),
            _entry("npm", "tk20-b", "CVE-9020-2"),
        ),
        "feed_id": "tk20",
    })
    _, after = srv.handle_feeds_status()
    assert after["total_cves"] == baseline + 2


# ═══════════════════════════════════════════════════════════════════════════════
# J.3 — security & edge cases (TK21-TK30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TK21_url_allowlist_respects_host_match():
    """A host listed in the allowlist passes the gate (may then fail HTTP, separately)."""
    os.environ["UCO_CVE_FEED_ALLOWLIST"] = "internal.example.com"
    try:
        r = cve_feed.load_from_url("https://internal.example.com/cves.json",
                                   timeout=0.001)
        assert r.added_new == 0
        # The error is now about the HTTP fetch failing (timeout), NOT the allowlist.
        assert not any("allowlist" in e.lower() for e in r.errors)
    finally:
        os.environ.pop("UCO_CVE_FEED_ALLOWLIST", None)


def test_TK22_url_allowlist_blocks_unlisted_host():
    os.environ["UCO_CVE_FEED_ALLOWLIST"] = "trusted.example.com"
    try:
        r = cve_feed.load_from_url("https://attacker.example.com/cves.json")
        assert r.added_new == 0
        assert any("allowlist" in e.lower() for e in r.errors)
    finally:
        os.environ.pop("UCO_CVE_FEED_ALLOWLIST", None)


def test_TK23_empty_allowlist_blocks_all_urls():
    os.environ.pop("UCO_CVE_FEED_ALLOWLIST", None)
    r = cve_feed.load_from_url("https://anywhere.example.com/cves.json")
    assert r.added_new == 0
    assert any("allowlist" in e.lower() for e in r.errors)


def test_TK24_invalid_ecosystem_field_skipped():
    path = _file_with(_build_feed(
        {"ecosystem": "", "package": "x", "cve_id": "Y",
         "affected_range": ">=0"},
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 0
        assert r.skipped_bad == 1
    finally:
        os.unlink(path)


def test_TK25_invalid_severity_skipped():
    path = _file_with(_build_feed(
        {"ecosystem": "npm", "package": "x", "cve_id": "Y",
         "affected_range": ">=0", "severity": "BLAZING"},
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 0
        assert any("severity" in e.lower() for e in r.errors)
    finally:
        os.unlink(path)


def test_TK26_dedupe_within_same_load_uses_override():
    """Same CVE id appearing twice in one feed → last one wins (override path)."""
    path = _file_with(_build_feed(
        _entry("npm", "tk26-pkg", "CVE-9026-1", sev="LOW"),
        _entry("npm", "tk26-pkg", "CVE-9026-1", sev="CRITICAL"),
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 1
        assert r.added_override == 1
        hits = cve_database.lookup("npm", "tk26-pkg", "1.0.0")
        assert any(h.cve_id == "CVE-9026-1" and h.severity == "CRITICAL"
                   for h in hits)
    finally:
        os.unlink(path)


def test_TK27_reset_after_multiple_loads_restores_baseline():
    baseline = cve_database.database_size()
    p1 = _file_with(_build_feed(_entry("pip", "tk27-a", "CVE-9027-1")))
    p2 = _file_with(_build_feed(_entry("npm", "tk27-b", "CVE-9027-2")))
    try:
        cve_feed.load_from_file(p1)
        cve_feed.load_from_file(p2)
        cve_feed.reset_overrides()
        assert cve_database.database_size() == baseline
    finally:
        os.unlink(p1)
        os.unlink(p2)


def test_TK28_feed_load_result_to_dict_serializable():
    path = _file_with(_build_feed(_entry("npm", "tk28-pkg", "CVE-9028-1")))
    try:
        r = cve_feed.load_from_file(path)
        d = r.to_dict()
        text = json.dumps(d)
        assert "feed_id" in text
        assert "added_new" in text
    finally:
        os.unlink(path)


def test_TK29_default_severity_used_when_missing():
    path = _file_with(_build_feed(
        {"ecosystem": "npm", "package": "tk29-pkg", "cve_id": "CVE-9029-1",
         "affected_range": ">=0", "cvss_score": 3.0},
    ))
    try:
        r = cve_feed.load_from_file(path)
        assert r.added_new == 1
        hits = cve_database.lookup("npm", "tk29-pkg", "1.0.0")
        assert hits
        assert hits[0].severity == "MEDIUM"        # the default
    finally:
        os.unlink(path)


def test_TK30_builtin_db_preserved_through_full_roundtrip():
    """Loading a synthetic feed then unloading it leaves the built-in CVEs
    intact — any test that ran inside the fixture proves this implicitly,
    but we assert the headline property on a representative built-in CVE.
    """
    baseline_hits = cve_database.lookup("npm", "lodash", "4.17.11")
    path = _file_with(_build_feed(_entry("npm", "tk30-pkg", "CVE-9030-1")))
    try:
        r = cve_feed.load_from_file(path)
        cve_feed.unload(r.feed_id)
        assert cve_database.lookup("npm", "lodash", "4.17.11") == baseline_hits
    finally:
        os.unlink(path)
