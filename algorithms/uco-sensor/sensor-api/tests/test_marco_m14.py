"""
UCO-Sensor — M7.1 SAST Expansion Round 1 — Test Suite
=======================================================
TV61-TV90 (30 tests)

Coverage:
  TS01-TS04  regex_analyzer.py — Class A/B/C / safe patterns
  TS05-TS08  SAST014 SSRF detection
  TS09-TS12  SAST015 XXE detection
  TS13-TS16  SAST018 SSTI + SAST019 ReDoS
  TS17-TS20  SAST021 weak key + SAST022 weak IV + SAST023 ECB mode
  TS21-TS24  SAST024 JWT none + SAST025 timing attack + SAST026 CSRF exempt
  TS25-TS28  SAST027 SSL verify=False + SAST028 weak TLS + SAST037 resource leak
  TS29-TS30  SAST038 exception swallow + SAST039 mutable default + rule count
"""
from __future__ import annotations

import sys
import os
import importlib

import pytest

# ── path setup ───────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from sast.regex_analyzer import analyze_pattern, is_vulnerable, ReDoSFinding
from sast.scanner import scan, RULES, SASTResult


# ═══════════════════════════════════════════════════════════════════════════════
# TS01-TS04 — regex_analyzer
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV61_RegexAnalyzerClassA:
    """TS01 — Class A: nested quantifiers detected."""

    def test_nested_plus_plus(self):
        findings = analyze_pattern(r"(\w+)+")
        assert findings, "Expected finding for (\\w+)+"
        assert findings[0].vuln_class == "A_NESTED_QUANTIFIER"

    def test_nested_star_plus(self):
        findings = analyze_pattern(r"([a-z]+)*")
        assert findings
        assert findings[0].vuln_class == "A_NESTED_QUANTIFIER"

    def test_dotplus_plus(self):
        findings = analyze_pattern(r"(.+)+end")
        assert findings
        assert findings[0].vuln_class == "A_NESTED_QUANTIFIER"

    def test_fragment_included(self):
        findings = analyze_pattern(r"(\d+)+")
        assert findings
        assert "+" in findings[0].fragment


class TestTV62_RegexAnalyzerClassB:
    """TS02 — Class B: overlapping alternation under quantifier."""

    def test_simple_overlap(self):
        findings = analyze_pattern(r"(a|aa)+")
        vuln_classes = {f.vuln_class for f in findings}
        assert "B_OVERLAP_ALTERNATION" in vuln_classes

    def test_prefix_overlap(self):
        findings = analyze_pattern(r"(foo|fo)+")
        vuln_classes = {f.vuln_class for f in findings}
        assert "B_OVERLAP_ALTERNATION" in vuln_classes

    def test_non_overlapping_alternation(self):
        # (abc|def)+ — no common prefix
        findings = analyze_pattern(r"(abc|def)+")
        b_findings = [f for f in findings if f.vuln_class == "B_OVERLAP_ALTERNATION"]
        assert not b_findings, "Non-overlapping alternation should not be flagged"

    def test_description_mentions_branches(self):
        findings = analyze_pattern(r"(a|aa)+")
        b_findings = [f for f in findings if f.vuln_class == "B_OVERLAP_ALTERNATION"]
        if b_findings:
            assert "branch" in b_findings[0].description.lower() or "alternati" in b_findings[0].description.lower()


class TestTV63_RegexAnalyzerClassC:
    """TS03 — Class C: char-class overlap in quantified group."""

    def test_email_like_pattern(self):
        # ([a-zA-Z0-9._]+@)+
        findings = analyze_pattern(r"([a-zA-Z0-9._]+@)+")
        # Should be flagged by A or C (nested quantifier or char-class overlap)
        assert findings

    def test_char_class_quantified_group(self):
        findings = analyze_pattern(r"([\w.]+)+")
        # Detected by Class A (nested quantifier)
        assert findings


class TestTV64_RegexAnalyzerSafe:
    """TS04 — Safe patterns produce no findings."""

    def test_simple_literal(self):
        assert not is_vulnerable(r"hello world")

    def test_anchored_pattern(self):
        assert not is_vulnerable(r"^\d{4}-\d{2}-\d{2}$")

    def test_non_overlapping_alternation_no_quantifier(self):
        assert not is_vulnerable(r"(abc|def)")

    def test_is_vulnerable_returns_bool(self):
        assert is_vulnerable(r"(\w+)+") is True
        assert is_vulnerable(r"\d+") is False


# ═══════════════════════════════════════════════════════════════════════════════
# TS05-TS08 — SAST014 SSRF
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV65_SAST014_SSRF:
    """TS05 — SSRF: requests.get with variable URL."""

    def test_ssrf_requests_get(self):
        src = "import requests\nrequests.get(url)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST014" in rule_ids

    def test_ssrf_requests_post(self):
        src = "requests.post(user_url, data=payload)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST014" in rule_ids

    def test_ssrf_urlopen(self):
        src = "from urllib import request\nrequest.urlopen(endpoint)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST014" in rule_ids

    def test_ssrf_literal_url_safe(self):
        # Literal URL — not SSRF
        src = 'import requests\nrequests.get("https://api.example.com/v1")'
        result = scan(src)
        ssrf = [f for f in result.findings if f.rule_id == "SAST014"]
        assert not ssrf, "Literal URL should not trigger SSRF"


# ═══════════════════════════════════════════════════════════════════════════════
# TS09-TS12 — SAST015 XXE
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV66_SAST015_XXE:
    """TS06 — XXE: vulnerable XML parsers."""

    def test_xxe_minidom_parse(self):
        src = "from xml.dom import minidom\nminidom.parse(f)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST015" in rule_ids

    def test_xxe_sax_parse(self):
        src = "import xml.sax\nxml.sax.parse(xmlfile, handler)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST015" in rule_ids

    def test_xxe_etree_parse(self):
        src = "from lxml import etree\ntree = etree.parse(fname)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST015" in rule_ids

    def test_xxe_cwe_id(self):
        src = "from xml.dom import minidom\nminidom.parse(x)"
        result = scan(src)
        xxe = [f for f in result.findings if f.rule_id == "SAST015"]
        assert xxe
        assert xxe[0].cwe_id == "CWE-611"


# ═══════════════════════════════════════════════════════════════════════════════
# TS13-TS16 — SAST018 SSTI + SAST019 ReDoS
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV67_SAST018_SSTI:
    """TS07 — Template injection detection."""

    def test_ssti_jinja2_template_variable(self):
        src = "from jinja2 import Template\nt = jinja2.Template(user_input)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST018" in rule_ids

    def test_ssti_render_template_string(self):
        src = "render_template_string(template_str)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST018" in rule_ids

    def test_ssti_severity_critical(self):
        src = "render_template_string(tmpl)"
        result = scan(src)
        ssti = [f for f in result.findings if f.rule_id == "SAST018"]
        assert ssti
        assert ssti[0].severity == "CRITICAL"

    def test_ssti_literal_template_safe(self):
        src = 'from jinja2 import Template\nt = jinja2.Template("Hello {{ name }}")'
        result = scan(src)
        ssti = [f for f in result.findings if f.rule_id == "SAST018"]
        assert not ssti, "Literal template string should not trigger SSTI"


class TestTV68_SAST019_ReDoS:
    """TS08 — ReDoS detection via regex_analyzer integration."""

    def test_redos_compile_vulnerable(self):
        src = r"import re" + "\n" + r're.compile(r"(\w+)+")'
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST019" in rule_ids

    def test_redos_search_vulnerable(self):
        src = r"import re" + "\n" + r're.search(r"([a-z]+)*", text)'
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST019" in rule_ids

    def test_redos_safe_pattern(self):
        src = r"import re" + "\n" + r're.compile(r"^\d{4}-\d{2}-\d{2}$")'
        result = scan(src)
        redos = [f for f in result.findings if f.rule_id == "SAST019"]
        assert not redos

    def test_redos_cwe_400(self):
        src = r"import re" + "\n" + r're.compile(r"(.+)+")'
        result = scan(src)
        redos = [f for f in result.findings if f.rule_id == "SAST019"]
        assert redos
        assert redos[0].cwe_id == "CWE-400"


# ═══════════════════════════════════════════════════════════════════════════════
# TS17-TS20 — SAST021 weak key + SAST022 weak IV + SAST023 ECB
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV69_SAST021_WeakKey:
    """TS09 — Weak asymmetric key size."""

    def test_weak_key_rsa_generate_1024(self):
        src = "key = RSA.generate(1024)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST021" in rule_ids

    def test_weak_key_generate_private_key(self):
        src = "key = generate_private_key(key_size=1024, public_exponent=65537)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST021" in rule_ids

    def test_strong_key_2048_safe(self):
        src = "key = RSA.generate(2048)"
        result = scan(src)
        weak = [f for f in result.findings if f.rule_id == "SAST021"]
        assert not weak

    def test_weak_key_severity_high(self):
        src = "key = RSA.generate(512)"
        result = scan(src)
        w = [f for f in result.findings if f.rule_id == "SAST021"]
        assert w and w[0].severity == "HIGH"


class TestTV70_SAST022_WeakIV:
    """TS10 — Weak all-zero IV/nonce detection."""

    def test_zero_iv_bytes_call(self):
        src = "cipher = AES.new(key, AES.MODE_CBC, bytes(16))"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST022" in rule_ids

    def test_zero_iv_literal(self):
        src = "cipher = AES.new(key, AES.MODE_CBC, b'\\x00' * 16)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST022" in rule_ids

    def test_ecb_mode_flagged(self):
        src = "cipher = AES.new(key, AES.MODE_ECB)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST023" in rule_ids

    def test_ecb_mode_severity_medium(self):
        src = "cipher = AES.new(secret, AES.MODE_ECB)"
        result = scan(src)
        ecb = [f for f in result.findings if f.rule_id == "SAST023"]
        assert ecb and ecb[0].severity == "MEDIUM"


class TestTV71_SAST006_DES_RC4:
    """TS11 — SAST006 expanded: DES and RC4 detection (M7.1)."""

    def test_des_new_flagged(self):
        src = "from Crypto.Cipher import DES\ncipher = DES.new(key)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST006" in rule_ids

    def test_arc4_new_flagged(self):
        src = "from Crypto.Cipher import ARC4\ncipher = ARC4.new(key)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST006" in rule_ids

    def test_hashlib_md5_still_flagged(self):
        src = "import hashlib\nh = hashlib.md5(data)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST006" in rule_ids

    def test_hashlib_sha256_safe(self):
        src = "import hashlib\nh = hashlib.sha256(data)"
        result = scan(src)
        sast006 = [f for f in result.findings if f.rule_id == "SAST006"]
        assert not sast006


# ═══════════════════════════════════════════════════════════════════════════════
# TS21-TS24 — SAST024 JWT + SAST025 timing + SAST026 CSRF
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV72_SAST024_JWT:
    """TS12 — JWT none algorithm / verify=False."""

    def test_jwt_verify_false(self):
        src = "payload = jwt.decode(token, secret, verify=False)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST024" in rule_ids

    def test_jwt_options_verify_signature_false(self):
        src = 'payload = jwt.decode(token, key, options={"verify_signature": False})'
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST024" in rule_ids

    def test_jwt_algorithms_none(self):
        src = "payload = jwt.decode(token, key, algorithms=['none'])"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST024" in rule_ids

    def test_jwt_severity_critical(self):
        src = "payload = jwt.decode(token, secret, verify=False)"
        result = scan(src)
        j = [f for f in result.findings if f.rule_id == "SAST024"]
        assert j and j[0].severity == "CRITICAL"


class TestTV73_SAST025_Timing:
    """TS13 — Timing attack via == comparison."""

    def test_timing_attack_token_eq(self):
        src = "if user_token == expected_token: grant()"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST025" in rule_ids

    def test_timing_attack_password_eq(self):
        src = "valid = (password == stored_hash)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST025" in rule_ids

    def test_timing_non_sensitive_safe(self):
        src = "if username == 'admin': pass"
        result = scan(src)
        t = [f for f in result.findings if f.rule_id == "SAST025"]
        assert not t, "Non-sensitive name comparison should not trigger timing"

    def test_timing_severity_medium(self):
        src = "if digest == provided_digest: ok()"
        result = scan(src)
        t = [f for f in result.findings if f.rule_id == "SAST025"]
        assert t and t[0].severity == "MEDIUM"


class TestTV74_SAST026_CSRF:
    """TS14 — CSRF exempt decorator detection."""

    def test_csrf_exempt_detected(self):
        src = (
            "from django.views.decorators.csrf import csrf_exempt\n"
            "@csrf_exempt\n"
            "def my_view(request):\n"
            "    pass\n"
        )
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST026" in rule_ids

    def test_csrf_exempt_cwe(self):
        src = "@csrf_exempt\ndef view(request): pass"
        result = scan(src)
        c = [f for f in result.findings if f.rule_id == "SAST026"]
        assert c and c[0].cwe_id == "CWE-352"

    def test_no_csrf_exempt_safe(self):
        src = "def view(request):\n    return response"
        result = scan(src)
        c = [f for f in result.findings if f.rule_id == "SAST026"]
        assert not c

    def test_csrf_exempt_async_view(self):
        src = "@csrf_exempt\nasync def async_view(request): pass"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST026" in rule_ids


# ═══════════════════════════════════════════════════════════════════════════════
# TS25-TS28 — SAST027 SSL verify + SAST028 weak TLS + SAST037 resource leak
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV75_SAST027_SSL:
    """TS15 — SSL verify=False detection."""

    def test_ssl_verify_false(self):
        src = 'resp = requests.get("https://api.example.com", verify=False)'
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST027" in rule_ids

    def test_ssl_verify_false_post(self):
        src = 'resp = requests.post(url, data=payload, verify=False)'
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST027" in rule_ids

    def test_ssl_verify_true_safe(self):
        src = 'resp = requests.get(url, verify=True)'
        result = scan(src)
        s = [f for f in result.findings if f.rule_id == "SAST027"]
        assert not s

    def test_ssl_verify_false_severity_high(self):
        src = 'resp = requests.get("https://x.com", verify=False)'
        result = scan(src)
        s = [f for f in result.findings if f.rule_id == "SAST027"]
        assert s and s[0].severity == "HIGH"


class TestTV76_SAST028_WeakTLS:
    """TS16 — Deprecated TLS protocol detection."""

    def test_weak_tls_v1(self):
        src = "import ssl\nctx = ssl.SSLContext(ssl.PROTOCOL_TLSv1)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST028" in rule_ids

    def test_weak_ssl_v3(self):
        src = "ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv3)"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST028" in rule_ids

    def test_strong_tls_safe(self):
        src = "import ssl\nctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)"
        result = scan(src)
        w = [f for f in result.findings if f.rule_id == "SAST028"]
        assert not w

    def test_weak_tls_cwe(self):
        src = "ssl.PROTOCOL_TLSv1_1"
        result = scan(src)
        w = [f for f in result.findings if f.rule_id == "SAST028"]
        assert w and w[0].cwe_id == "CWE-326"


class TestTV77_SAST037_ResourceLeak:
    """TS17 — Resource leak: open() outside with block."""

    def test_resource_leak_assignment(self):
        src = "f = open('data.txt', 'r')\ndata = f.read()\nf.close()"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST037" in rule_ids

    def test_with_open_safe(self):
        src = "with open('data.txt', 'r') as f:\n    data = f.read()"
        result = scan(src)
        leaks = [f for f in result.findings if f.rule_id == "SAST037"]
        assert not leaks

    def test_resource_leak_cwe(self):
        src = "handle = open(path, 'rb')"
        result = scan(src)
        r = [f for f in result.findings if f.rule_id == "SAST037"]
        assert r and r[0].cwe_id == "CWE-772"

    def test_resource_leak_severity_medium(self):
        src = "log_file = open('app.log', 'a')"
        result = scan(src)
        r = [f for f in result.findings if f.rule_id == "SAST037"]
        assert r and r[0].severity == "MEDIUM"


# ═══════════════════════════════════════════════════════════════════════════════
# TS29-TS30 — SAST038 exception swallowing + SAST039 mutable default + rule count
# ═══════════════════════════════════════════════════════════════════════════════

class TestTV78_SAST038_ExceptionSwallowing:
    """TS18 — Exception swallowing detection."""

    def test_bare_except_pass(self):
        src = "try:\n    risky()\nexcept:\n    pass"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST038" in rule_ids

    def test_except_exception_pass(self):
        src = "try:\n    op()\nexcept Exception:\n    pass"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST038" in rule_ids

    def test_except_with_log_safe(self):
        src = "try:\n    op()\nexcept Exception as e:\n    logger.warning(e)"
        result = scan(src)
        s = [f for f in result.findings if f.rule_id == "SAST038"]
        assert not s

    def test_swallow_severity_low(self):
        src = "try:\n    x()\nexcept:\n    pass"
        result = scan(src)
        s = [f for f in result.findings if f.rule_id == "SAST038"]
        assert s and s[0].severity == "LOW"


class TestTV79_SAST039_MutableDefault:
    """TS19 — Mutable default argument detection."""

    def test_list_default(self):
        src = "def process(items=[]):\n    return items"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST039" in rule_ids

    def test_dict_default(self):
        src = "def config(opts={}):\n    return opts"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST039" in rule_ids

    def test_none_default_safe(self):
        src = "def process(items=None):\n    if items is None: items = []\n    return items"
        result = scan(src)
        m = [f for f in result.findings if f.rule_id == "SAST039"]
        assert not m

    def test_set_default(self):
        src = "def dedupe(seen=set()):\n    return seen"
        result = scan(src)
        rule_ids = {f.rule_id for f in result.findings}
        assert "SAST039" in rule_ids


class TestTV80_RuleCount:
    """TS20 — Rule catalogue completeness and structural checks."""

    def test_rule_count_at_least_28(self):
        # 13 original + 15 new = 28 rules minimum
        assert len(RULES) >= 28, f"Expected >= 28 rules, got {len(RULES)}"

    def test_all_new_rules_in_catalogue(self):
        rule_ids = {r.rule_id for r in RULES}
        new_rules = {
            "SAST014", "SAST015", "SAST018", "SAST019",
            "SAST021", "SAST022", "SAST023", "SAST024",
            "SAST025", "SAST026", "SAST027", "SAST028",
            "SAST037", "SAST038", "SAST039",
        }
        missing = new_rules - rule_ids
        assert not missing, f"Missing rules from catalogue: {missing}"

    def test_all_rules_have_cwe(self):
        for r in RULES:
            assert r.cwe_id.startswith("CWE-"), f"{r.rule_id} missing CWE: {r.cwe_id}"

    def test_all_rules_have_remediation(self):
        for r in RULES:
            assert len(r.remediation) > 10, f"{r.rule_id} remediation too short"

    def test_sast007_narrowed(self):
        # SAST007 should NOT fire for random.shuffle (non-crypto)
        src = "import random\nrandom.shuffle(items)"
        result = scan(src)
        s7 = [f for f in result.findings if f.rule_id == "SAST007"]
        assert not s7, "random.shuffle should not trigger SAST007 after narrowing"

    def test_sast_result_to_dict_keys(self):
        result = scan("x = 1")
        d = result.to_dict()
        for key in ("findings", "finding_count", "critical", "high", "medium", "low",
                    "total_debt_minutes", "security_rating", "parse_error"):
            assert key in d, f"Missing key in to_dict: {key}"
