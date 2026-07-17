"""
Marco 67 — Sprint AF audit round 2: SAST049 (TAH01-TAH06)
==========================================================

Continuing the per-case audit of the 15 remaining blind spots from
``paper/corpus_runs/AF_consolidated_timeline.md`` (task #57), found a
second generalizable gap: ``fastapi/fastapi`` CVE-2021-32677 (DoS via
unconditional ``await request.json()`` regardless of Content-Type).
SAST049 pins this shape, validated against the real GitHub-fetched
vulnerable (``90120dd6``) and fixed (``fa7e3c99``) snapshots of
``fastapi/routing.py``.
"""
from __future__ import annotations

from sast.scanner import scan


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in res.findings]


def test_TAH01_sast049_detects_real_fastapi_vulnerable_shape():
    src = (
        "async def app(request):\n"
        "    body = None\n"
        "    body_bytes = await request.body()\n"
        "    if body_bytes:\n"
        "        body = await request.json()\n"
        "    return body\n"
    )
    assert "SAST049" in _scan_ids(src)


def test_TAH02_sast049_silent_on_real_fastapi_fixed_shape():
    src = (
        "async def app(request):\n"
        "    body = None\n"
        "    body_bytes = await request.body()\n"
        "    if body_bytes:\n"
        "        content_type_value = request.headers.get('content-type')\n"
        "        if content_type_value and 'json' in content_type_value:\n"
        "            body = await request.json()\n"
        "        else:\n"
        "            body = body_bytes\n"
        "    return body\n"
    )
    assert "SAST049" not in _scan_ids(src)


def test_TAH03_sast049_silent_on_response_json_idiom():
    # The extremely common 'requests.get(url).json()' response-parsing
    # idiom must NOT fire — it parses an outgoing call's response, not
    # an incoming, attacker-controlled request body.
    src = (
        "def fetch(url):\n"
        "    response = requests.get(url)\n"
        "    return response.json()\n"
    )
    assert "SAST049" not in _scan_ids(src)


def test_TAH04_sast049_silent_when_content_type_checked_via_attribute():
    # Django-style 'request.content_type' attribute check (not the
    # 'content-type' header-dict lookup) must also count as a guard.
    src = (
        "def view(request):\n"
        "    if request.content_type == 'application/json':\n"
        "        return request.json()\n"
    )
    assert "SAST049" not in _scan_ids(src)


def test_TAH05_sast049_detects_sync_request_json_too():
    src = (
        "def view(req):\n"
        "    data = req.json()\n"
        "    return data\n"
    )
    assert "SAST049" in _scan_ids(src)


def test_TAH06_sast049_finding_has_correct_metadata():
    src = (
        "def view(request):\n"
        "    return request.json()\n"
    )
    findings = [f for f in scan(src, ".py").findings if f.rule_id == "SAST049"]
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert findings[0].cwe_id == "CWE-400"
