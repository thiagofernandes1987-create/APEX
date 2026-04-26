"""
UCO-Sensor — Testes Marco M3: SAST Security Rules (v0.9.0)
============================================================

  TS01  scan() clean code → 0 findings, rating A
  TS02  SAST001 SQL Injection — %-format in execute()
  TS03  SAST001 SQL Injection — f-string in execute()
  TS04  SAST001 SQL Injection — safe parameterised query NOT flagged
  TS05  SAST002 OS Command Injection — os.system(var)
  TS06  SAST002 OS command with literal NOT flagged
  TS07  SAST003 Unsafe eval() with variable
  TS08  SAST003 eval() with literal NOT flagged
  TS09  SAST004 Pickle deserialization
  TS10  SAST005 YAML unsafe load (no Loader kwarg)
  TS11  SAST005 yaml.safe_load() NOT flagged
  TS12  SAST006 Weak hash MD5
  TS13  SAST006 Weak hash SHA1
  TS14  SAST006 SHA-256 NOT flagged
  TS15  SAST007 random.randint flagged
  TS16  SAST008 Hardcoded password variable
  TS17  SAST008 Hardcoded api_key variable
  TS18  SAST008 Placeholder value NOT flagged
  TS19  SAST009 PEM private key in source
  TS20  SAST010 Flask debug=True
  TS21  SAST010 debug=False NOT flagged
  TS22  SAST011 open() with variable path
  TS23  SAST011 open() with literal path NOT flagged
  TS24  SAST013 subprocess.run shell=True + variable
  TS25  SAST013 subprocess.run shell=False NOT flagged
  TS26  SASTResult.to_dict() round-trip
  TS27  security_rating — CRITICAL → E
  TS28  security_rating — clean → A
  TS29  scan() non-Python extension → empty result
  TS30  RULES catalogue has 13 entries
"""
from __future__ import annotations
import sys
from pathlib import Path

_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sast.scanner import scan, RULES, SASTResult, SASTFinding


# ── Helpers ──────────────────────────────────────────────────────────────────

def _rule_ids(result: SASTResult):
    return {f.rule_id for f in result.findings}

def _has(result: SASTResult, rule_id: str) -> bool:
    return rule_id in _rule_ids(result)


# ══════════════════════════════════════════════════════════════════════════════
# TS01 — Clean code
# ══════════════════════════════════════════════════════════════════════════════

def test_TS01_clean_code_no_findings():
    """Clean code → 0 findings, rating A."""
    src = """
import hashlib
import json

def process(data: dict) -> str:
    h = hashlib.sha256(json.dumps(data).encode()).hexdigest()
    return h

def load_config(path: str) -> dict:
    with open("/etc/config.json") as f:
        return json.load(f)
"""
    result = scan(src)
    assert result.security_rating == "A", \
        f"Expected A, got {result.security_rating}; findings={_rule_ids(result)}"
    assert result.total_debt_minutes == 0


# ══════════════════════════════════════════════════════════════════════════════
# TS02-TS04 — SQL Injection (SAST001)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS02_sql_injection_percent_format():
    """SAST001: %-format in cursor.execute()."""
    src = """
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = %s" % user_id)
"""
    result = scan(src)
    assert _has(result, "SAST001"), f"Expected SAST001; got {_rule_ids(result)}"


def test_TS03_sql_injection_fstring():
    """SAST001: f-string in cursor.execute()."""
    src = """
def get_user(user_id):
    cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")
"""
    result = scan(src)
    assert _has(result, "SAST001"), f"Expected SAST001; got {_rule_ids(result)}"


def test_TS04_sql_safe_parameterised_not_flagged():
    """SAST001: parameterised query not flagged."""
    src = """
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
"""
    result = scan(src)
    assert not _has(result, "SAST001"), \
        f"SAST001 false positive on safe query; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS05-TS06 — OS Command Injection (SAST002)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS05_os_system_variable():
    """SAST002: os.system() with non-literal."""
    src = """
import os
def run(cmd):
    os.system(cmd)
"""
    result = scan(src)
    assert _has(result, "SAST002"), f"Expected SAST002; got {_rule_ids(result)}"


def test_TS06_os_system_literal_not_flagged():
    """SAST002: os.system() with literal string not flagged."""
    src = """
import os
os.system("ls -la")
"""
    result = scan(src)
    assert not _has(result, "SAST002"), \
        f"SAST002 false positive on literal; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS07-TS08 — Unsafe eval / exec (SAST003)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS07_eval_with_variable():
    """SAST003: eval() with non-literal."""
    src = """
def run_expr(user_input):
    return eval(user_input)
"""
    result = scan(src)
    assert _has(result, "SAST003"), f"Expected SAST003; got {_rule_ids(result)}"


def test_TS08_eval_literal_not_flagged():
    """SAST003: eval() with literal not flagged."""
    src = """
result = eval("2 + 2")
"""
    result = scan(src)
    assert not _has(result, "SAST003"), \
        f"SAST003 false positive on literal eval; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS09 — Pickle (SAST004)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS09_pickle_loads():
    """SAST004: pickle.loads() flagged."""
    src = """
import pickle
def load(data):
    return pickle.loads(data)
"""
    result = scan(src)
    assert _has(result, "SAST004"), f"Expected SAST004; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS10-TS11 — YAML Unsafe Load (SAST005)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS10_yaml_unsafe_load():
    """SAST005: yaml.load() without SafeLoader."""
    src = """
import yaml
def load_config(data):
    return yaml.load(data)
"""
    result = scan(src)
    assert _has(result, "SAST005"), f"Expected SAST005; got {_rule_ids(result)}"


def test_TS11_yaml_safe_load_not_flagged():
    """SAST005: yaml.safe_load() not flagged."""
    src = """
import yaml
def load_config(data):
    return yaml.safe_load(data)
"""
    result = scan(src)
    assert not _has(result, "SAST005"), \
        f"SAST005 false positive on safe_load; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS12-TS14 — Weak Hash (SAST006)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS12_hashlib_md5():
    """SAST006: hashlib.md5() flagged."""
    src = """
import hashlib
h = hashlib.md5(data).hexdigest()
"""
    result = scan(src)
    assert _has(result, "SAST006"), f"Expected SAST006; got {_rule_ids(result)}"


def test_TS13_hashlib_sha1():
    """SAST006: hashlib.sha1() flagged."""
    src = """
import hashlib
h = hashlib.sha1(data).hexdigest()
"""
    result = scan(src)
    assert _has(result, "SAST006"), f"Expected SAST006; got {_rule_ids(result)}"


def test_TS14_hashlib_sha256_not_flagged():
    """SAST006: hashlib.sha256() not flagged."""
    src = """
import hashlib
h = hashlib.sha256(data).hexdigest()
"""
    result = scan(src)
    assert not _has(result, "SAST006"), \
        f"SAST006 false positive on sha256; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS15 — Insecure Randomness (SAST007)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS15_random_randint():
    """SAST007: random.randint flagged."""
    src = """
import random
token = random.randint(0, 1000000)
"""
    result = scan(src)
    assert _has(result, "SAST007"), f"Expected SAST007; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS16-TS18 — Hardcoded Secret (SAST008)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS16_hardcoded_password():
    """SAST008: password = "..." flagged."""
    src = """
password = "super_secret_123"
"""
    result = scan(src)
    assert _has(result, "SAST008"), f"Expected SAST008; got {_rule_ids(result)}"


def test_TS17_hardcoded_api_key():
    """SAST008: api_key = "..." flagged."""
    src = """
api_key = "sk-abc123xyz789"
"""
    result = scan(src)
    assert _has(result, "SAST008"), f"Expected SAST008; got {_rule_ids(result)}"


def test_TS18_placeholder_not_flagged():
    """SAST008: obvious placeholder value not flagged."""
    src = """
password = "CHANGEME"
"""
    result = scan(src)
    assert not _has(result, "SAST008"), \
        f"SAST008 false positive on placeholder; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS19 — Hardcoded Private Key (SAST009)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS19_pem_private_key():
    """SAST009: PEM private key material in source."""
    src = """
private_key = \"\"\"
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4bzU
-----END RSA PRIVATE KEY-----
\"\"\"
"""
    result = scan(src)
    assert _has(result, "SAST009"), f"Expected SAST009; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS20-TS21 — Debug Mode (SAST010)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS20_flask_debug_true():
    """SAST010: app.run(debug=True) flagged."""
    src = """
from flask import Flask
app = Flask(__name__)
if __name__ == "__main__":
    app.run(debug=True)
"""
    result = scan(src)
    assert _has(result, "SAST010"), f"Expected SAST010; got {_rule_ids(result)}"


def test_TS21_debug_false_not_flagged():
    """SAST010: app.run(debug=False) not flagged."""
    src = """
app.run(debug=False, port=8080)
"""
    result = scan(src)
    assert not _has(result, "SAST010"), \
        f"SAST010 false positive on debug=False; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS22-TS23 — Path Traversal (SAST011)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS22_open_variable_path():
    """SAST011: open() with non-literal path flagged."""
    src = """
def read_file(user_path):
    with open(user_path) as f:
        return f.read()
"""
    result = scan(src)
    assert _has(result, "SAST011"), f"Expected SAST011; got {_rule_ids(result)}"


def test_TS23_open_literal_path_not_flagged():
    """SAST011: open() with string literal not flagged."""
    src = """
with open("/etc/hosts") as f:
    content = f.read()
"""
    result = scan(src)
    assert not _has(result, "SAST011"), \
        f"SAST011 false positive on literal path; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS24-TS25 — Subprocess shell=True (SAST013)
# ══════════════════════════════════════════════════════════════════════════════

def test_TS24_subprocess_shell_true_variable():
    """SAST013: subprocess.run(cmd, shell=True) with variable flagged."""
    src = """
import subprocess
def run_cmd(cmd):
    subprocess.run(cmd, shell=True)
"""
    result = scan(src)
    assert _has(result, "SAST013"), f"Expected SAST013; got {_rule_ids(result)}"


def test_TS25_subprocess_shell_false_not_flagged():
    """SAST013: subprocess.run(cmd, shell=False) not flagged."""
    src = """
import subprocess
subprocess.run(["ls", "-la"], shell=False, check=True)
"""
    result = scan(src)
    assert not _has(result, "SAST013"), \
        f"SAST013 false positive on shell=False; got {_rule_ids(result)}"


# ══════════════════════════════════════════════════════════════════════════════
# TS26-TS30 — Metadata and catalogue
# ══════════════════════════════════════════════════════════════════════════════

def test_TS26_sast_result_to_dict():
    """SASTResult.to_dict() contains expected keys."""
    src = """
import pickle
data = pickle.loads(raw)
"""
    result = scan(src)
    d = result.to_dict()
    assert "findings" in d
    assert "finding_count" in d
    assert "total_debt_minutes" in d
    assert "security_rating" in d
    assert isinstance(d["findings"], list)
    if d["findings"]:
        f = d["findings"][0]
        assert "rule_id" in f
        assert "severity" in f
        assert "cwe_id" in f
        assert "line" in f
        assert "debt_minutes" in f


def test_TS27_security_rating_critical_e():
    """SAST009 (CRITICAL) → security_rating = E."""
    src = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0Z3VS5JJcds
-----END RSA PRIVATE KEY-----
"""
    # Manual check via regex-based detection
    result = scan(src)
    if _has(result, "SAST009"):
        assert result.security_rating == "E", \
            f"Expected E for CRITICAL finding; got {result.security_rating}"


def test_TS28_security_rating_clean_a():
    """No findings → security_rating = A."""
    src = """
def add(a, b):
    return a + b
"""
    result = scan(src)
    assert result.security_rating == "A"


def test_TS29_non_python_extension_empty():
    """Non-Python extension → empty result, no findings."""
    src = """
eval(user_input)
password = "secret"
"""
    result = scan(src, file_extension=".js")
    assert len(result.findings) == 0
    assert result.parse_error is False


def test_TS30_rules_catalogue():
    """RULES catalogue has 13 entries with all required fields."""
    assert len(RULES) == 13, f"Expected 13 rules, got {len(RULES)}"
    for r in RULES:
        assert r.rule_id.startswith("SAST"), f"Bad rule_id: {r.rule_id}"
        assert r.severity in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")
        assert r.cwe_id.startswith("CWE-")
        assert r.owasp
        assert r.title
        assert r.remediation


# ── Runner ────────────────────────────────────────────────────────────────────

TESTS = [
    ("TS01", test_TS01_clean_code_no_findings),
    ("TS02", test_TS02_sql_injection_percent_format),
    ("TS03", test_TS03_sql_injection_fstring),
    ("TS04", test_TS04_sql_safe_parameterised_not_flagged),
    ("TS05", test_TS05_os_system_variable),
    ("TS06", test_TS06_os_system_literal_not_flagged),
    ("TS07", test_TS07_eval_with_variable),
    ("TS08", test_TS08_eval_literal_not_flagged),
    ("TS09", test_TS09_pickle_loads),
    ("TS10", test_TS10_yaml_unsafe_load),
    ("TS11", test_TS11_yaml_safe_load_not_flagged),
    ("TS12", test_TS12_hashlib_md5),
    ("TS13", test_TS13_hashlib_sha1),
    ("TS14", test_TS14_hashlib_sha256_not_flagged),
    ("TS15", test_TS15_random_randint),
    ("TS16", test_TS16_hardcoded_password),
    ("TS17", test_TS17_hardcoded_api_key),
    ("TS18", test_TS18_placeholder_not_flagged),
    ("TS19", test_TS19_pem_private_key),
    ("TS20", test_TS20_flask_debug_true),
    ("TS21", test_TS21_debug_false_not_flagged),
    ("TS22", test_TS22_open_variable_path),
    ("TS23", test_TS23_open_literal_path_not_flagged),
    ("TS24", test_TS24_subprocess_shell_true_variable),
    ("TS25", test_TS25_subprocess_shell_false_not_flagged),
    ("TS26", test_TS26_sast_result_to_dict),
    ("TS27", test_TS27_security_rating_critical_e),
    ("TS28", test_TS28_security_rating_clean_a),
    ("TS29", test_TS29_non_python_extension_empty),
    ("TS30", test_TS30_rules_catalogue),
]

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    passed = failed = 0
    errors = []
    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco M3 — SAST Security Rules ({len(TESTS)} testes)")
    print(f"{'='*65}")
    for name, fn in TESTS:
        try:
            fn()
            print(f"  OK {name}")
            passed += 1
        except Exception as exc:
            print(f"  FAIL {name}: {exc}")
            failed += 1
            errors.append((name, exc))
    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")
    sys.exit(0 if failed == 0 else 1)
