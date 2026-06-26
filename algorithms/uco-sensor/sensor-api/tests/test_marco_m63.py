"""
Marco 63 — Sprint AC-3: CVE-anchored corpus audit findings (TAC01-TAC14)
=========================================================================

Sprint AC-3 ran ``paper/cve_diff_check.py``-style before/after comparisons
against 6 real, documented CVEs across psf/requests, scrapy/scrapy,
pallets/flask, django/django, celery/celery and fastapi/fastapi (see
``paper/corpus_runs/AC3_cve_before_after.md``). 4/6 were confirmed blind
spots: neither SAST nor the 9 structural metric channels changed
diagnostically between the vulnerable and fixed snapshot. Two of those
blind spots had a crisp, generalizable AST shape and got a real new SAST
rule each: SAST046 (CVE-2024-47081 root cause) and SAST047
(CVE-2023-32681 root cause). This module pins both rules against the
exact vulnerable/fixed code shapes found in the wild, plus
false-positive-avoidance cases for ordinary code that must NOT fire.

Coverage layout
---------------
* TAC01-TAC05 — SAST046 (netloc.split instead of .hostname)
* TAC06-TAC14 — SAST047 (sensitive header reattached without origin guard)
"""
from __future__ import annotations

from sast.scanner import scan


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in res.findings]


# ═══════════════════════════════════════════════════════════════════════════
# SAST046 — URL Host Extracted via netloc.split() Instead of .hostname
# (root cause of CVE-2024-47081, psf/requests .netrc credential leak)
# ═══════════════════════════════════════════════════════════════════════════

def test_TAC01_sast046_detects_netloc_split_real_requests_shape():
    # Exact vulnerable shape from src/requests/utils.py, pre-fix.
    src = (
        "def get_netrc_auth(url, raise_errors=False):\n"
        "    splitstr = ':'\n"
        "    ri = urlparse(url)\n"
        "    host = ri.netloc.split(splitstr)[0]\n"
        "    return host\n"
    )
    assert "SAST046" in _scan_ids(src)


def test_TAC02_sast046_detects_literal_colon_split():
    src = "host = urlparse(url).netloc.split(':')[0]\n"
    assert "SAST046" in _scan_ids(src)


def test_TAC03_sast046_silent_on_hostname_property():
    # The actual fix: use .hostname instead of splitting .netloc.
    src = "host = urlparse(url).hostname\n"
    assert "SAST046" not in _scan_ids(src)


def test_TAC04_sast046_silent_on_unrelated_split():
    src = "parts = some_string.split(':')\n"
    assert "SAST046" not in _scan_ids(src)


def test_TAC05_sast046_fires_regardless_of_split_arg_being_variable():
    # The real CVE split on a *variable* holding ':', not a literal —
    # confirms the rule isn't over-fit to the literal-arg case.
    src = "sep = ':'\nhost = parsed.netloc.split(sep)[0]\n"
    assert "SAST046" in _scan_ids(src)


# ═══════════════════════════════════════════════════════════════════════════
# SAST047 — Sensitive Header Re-sent on Redirect Without Origin Check
# (root cause of CVE-2023-32681, psf/requests Proxy-Authorization leak)
# ═══════════════════════════════════════════════════════════════════════════

def test_TAC06_sast047_detects_real_requests_rebuild_proxies_shape():
    # Exact vulnerable shape from requests/sessions.py rebuild_proxies(),
    # pre-fix: 'scheme' is read but only used to index a dict, never
    # compared — so the header gets reattached to a different scheme.
    src = (
        "def rebuild_proxies(self, prepared_request, proxies):\n"
        "    headers = prepared_request.headers\n"
        "    scheme = urlparse(prepared_request.url).scheme\n"
        "    new_proxies = resolve_proxies(prepared_request, proxies, self.trust_env)\n"
        "    if 'Proxy-Authorization' in headers:\n"
        "        del headers['Proxy-Authorization']\n"
        "    try:\n"
        "        username, password = get_auth_from_url(new_proxies[scheme])\n"
        "    except KeyError:\n"
        "        username, password = None, None\n"
        "    if username and password:\n"
        "        headers['Proxy-Authorization'] = _basic_auth_str(username, password)\n"
        "    return new_proxies\n"
    )
    assert "SAST047" in _scan_ids(src)


def test_TAC07_sast047_silent_on_real_requests_fixed_shape():
    # Exact fixed shape: same function, but now guarded by
    # 'scheme.startswith(...)' before re-attaching the header.
    src = (
        "def rebuild_proxies(self, prepared_request, proxies):\n"
        "    headers = prepared_request.headers\n"
        "    scheme = urlparse(prepared_request.url).scheme\n"
        "    new_proxies = resolve_proxies(prepared_request, proxies, self.trust_env)\n"
        "    if 'Proxy-Authorization' in headers:\n"
        "        del headers['Proxy-Authorization']\n"
        "    try:\n"
        "        username, password = get_auth_from_url(new_proxies[scheme])\n"
        "    except KeyError:\n"
        "        username, password = None, None\n"
        "    if not scheme.startswith('https') and username and password:\n"
        "        headers['Proxy-Authorization'] = _basic_auth_str(username, password)\n"
        "    return new_proxies\n"
    )
    assert "SAST047" not in _scan_ids(src)


def test_TAC08_sast047_silent_on_deletion_without_reassignment():
    # Header is dropped and never re-set — no reattachment, no leak shape.
    src = (
        "def strip_auth(headers):\n"
        "    if 'Authorization' in headers:\n"
        "        del headers['Authorization']\n"
    )
    assert "SAST047" not in _scan_ids(src)


def test_TAC09_sast047_silent_on_one_shot_header_set():
    # Setting a header once (no prior deletion) is ordinary auth setup,
    # not a redirect-time reattachment — must not be flagged.
    src = (
        "def add_auth(headers, token):\n"
        "    headers['Authorization'] = f'Bearer {token}'\n"
    )
    assert "SAST047" not in _scan_ids(src)


def test_TAC10_sast047_silent_with_explicit_equality_guard():
    src = (
        "def rebuild(headers, old_url, new_url):\n"
        "    old_host = urlparse(old_url).hostname\n"
        "    new_host = urlparse(new_url).hostname\n"
        "    if 'Authorization' in headers:\n"
        "        del headers['Authorization']\n"
        "    if old_host == new_host:\n"
        "        headers['Authorization'] = build_auth()\n"
    )
    assert "SAST047" not in _scan_ids(src)


def test_TAC11_sast047_detects_cookie_reattachment_too():
    src = (
        "def carry_cookie(headers):\n"
        "    if 'Cookie' in headers:\n"
        "        del headers['Cookie']\n"
        "    headers['Cookie'] = build_cookie_header()\n"
    )
    assert "SAST047" in _scan_ids(src)


def test_TAC12_sast047_finding_has_correct_metadata():
    src = (
        "def rebuild_proxies(headers):\n"
        "    del headers['Proxy-Authorization']\n"
        "    headers['Proxy-Authorization'] = build_auth()\n"
    )
    findings = [f for f in scan(src, ".py").findings if f.rule_id == "SAST047"]
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert findings[0].cwe_id == "CWE-200"


def test_TAC13_sast046_finding_has_correct_metadata():
    src = "host = parsed.netloc.split(':')[0]\n"
    findings = [f for f in scan(src, ".py").findings if f.rule_id == "SAST046"]
    assert len(findings) == 1
    assert findings[0].severity == "MEDIUM"
    assert findings[0].cwe_id == "CWE-1286"


def test_TAC14_sast046_and_sast047_independent_in_same_file():
    src = (
        "def get_netrc_auth(url):\n"
        "    host = urlparse(url).netloc.split(':')[0]\n"
        "    return host\n"
        "\n"
        "def rebuild_proxies(headers):\n"
        "    del headers['Proxy-Authorization']\n"
        "    headers['Proxy-Authorization'] = build_auth()\n"
    )
    ids = _scan_ids(src)
    assert "SAST046" in ids
    assert "SAST047" in ids
