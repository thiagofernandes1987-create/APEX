"""
Marco 35 — Sprint D: AutoFix↔SAST Mapping Expansion (TU01–TU30)
=================================================================

Adds **three** new high-confidence rewrite transforms to the
``SAST_TO_TRANSFORM`` mapping:

    SAST022  Weak IV / All-Zero Nonce   → ZeroNonceReplacer
    SAST024  JWT signature bypass       → JWTVerifyEnabler
    SAST027  SSL verify=False           → SSLVerifyEnabler

SAST014 (SSRF) and SAST037 (file-handle leak) were deliberately excluded:
the first requires semantic provenance of the URL argument, the second
requires structural AST rewriting (lift assignment + close into a
``with`` block).  Both are filed for a future sprint.

Coverage layout
---------------
* TU01-TU10 — SSL transform (SAST027): positional + keyword cases, false
  negatives on non-HTTP clients, untouched non-boolean values, idempotence.
* TU11-TU20 — JWT transform (SAST024): legacy ``verify=False``, nested
  options dict, ``algorithms=["none"]`` removal, multiple algorithms,
  case insensitivity, full-stop "none-only" → conservative fallback.
* TU21-TU30 — Nonce transform (SAST022): positional + keyword cases,
  ``b"\\x00" * N`` and literal zero-bytes, length preservation, automatic
  ``import os`` insertion, non-cipher calls left alone, end-to-end
  auto_remediate loop.
"""
from __future__ import annotations

import ast
import pytest

from sensor_core.autofix.engine import AutofixEngine
from sensor_core.autofix.sast_remediation import (
    SAST_TO_TRANSFORM, auto_remediate,
)
from sensor_core.autofix.transforms.enable_ssl_verify  import SSLVerifyEnabler
from sensor_core.autofix.transforms.enable_jwt_verify  import JWTVerifyEnabler
from sensor_core.autofix.transforms.replace_zero_nonce import ZeroNonceReplacer


def _apply(transform_cls, source: str) -> str:
    eng = AutofixEngine(transforms=[transform_cls])
    res = eng.apply(source)
    assert res.is_valid_python, f"output is not valid Python:\n{res.fixed_source}"
    return res.fixed_source


# ─── SSL verify (TU01–TU10) ───────────────────────────────────────────────────

def test_TU01_requests_verify_false_becomes_true():
    src = 'import requests\nrequests.get("https://x", verify=False)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert "verify=True" in out
    assert "verify=False" not in out


def test_TU02_httpx_verify_false_becomes_true():
    src = 'import httpx\nhttpx.post("https://x", verify=False)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert "verify=True" in out


def test_TU03_method_request_also_rewritten():
    src = 'import requests\nrequests.request("GET", "https://x", verify=False)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert "verify=True" in out


def test_TU04_non_http_module_left_alone():
    src = 'import other\nother.get("x", verify=False)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert "verify=False" in out


def test_TU05_non_constant_verify_left_alone():
    src = 'import requests\nflag=False\nrequests.get("https://x", verify=flag)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert "verify=flag" in out


def test_TU06_verify_true_idempotent():
    src = 'import requests\nrequests.get("https://x", verify=True)\n'
    out = _apply(SSLVerifyEnabler, src)
    assert out.count("verify=True") == 1


def test_TU07_multiple_calls_all_fixed():
    src = (
        'import requests\n'
        'requests.get("a", verify=False)\n'
        'requests.post("b", verify=False)\n'
    )
    out = _apply(SSLVerifyEnabler, src)
    assert out.count("verify=True") == 2


def test_TU08_ssl_transform_in_mapping():
    assert SAST_TO_TRANSFORM.get("SAST027") is SSLVerifyEnabler


def test_TU09_ssl_end_to_end_via_auto_remediate():
    src = 'import requests\nrequests.get("https://x", verify=False)\n'
    r = auto_remediate(src, module_id="ssl")
    assert "SAST027" in r.fixed_rules
    assert "SSLVerifyEnabler" in r.transforms_applied


def test_TU10_no_ssl_findings_no_change():
    src = "x = 1\n"
    r = auto_remediate(src, module_id="ssl-empty")
    assert r.fixed_rules == []
    assert r.transforms_applied == []


# ─── JWT verification (TU11–TU20) ─────────────────────────────────────────────

def test_TU11_jwt_legacy_verify_false():
    src = "import jwt\njwt.decode(t, k, verify=False)\n"
    out = _apply(JWTVerifyEnabler, src)
    assert "verify=True" in out


def test_TU12_jwt_options_verify_signature_false():
    src = 'import jwt\njwt.decode(t, k, options={"verify_signature": False})\n'
    out = _apply(JWTVerifyEnabler, src)
    assert "'verify_signature': True" in out or '"verify_signature": True' in out


def test_TU13_jwt_algorithms_none_dropped():
    src = 'import jwt\njwt.decode(t, k, algorithms=["none", "HS256"])\n'
    out = _apply(JWTVerifyEnabler, src)
    assert "'none'" not in out and '"none"' not in out
    assert "HS256" in out


def test_TU14_jwt_algorithms_only_none_falls_back_to_HS256():
    src = 'import jwt\njwt.decode(t, k, algorithms=["none"])\n'
    out = _apply(JWTVerifyEnabler, src)
    assert "HS256" in out
    assert "'none'" not in out


def test_TU15_jwt_none_case_insensitive():
    src = 'import jwt\njwt.decode(t, k, algorithms=["None", "HS256"])\n'
    out = _apply(JWTVerifyEnabler, src)
    assert "None" not in out.split("algorithms=")[1].split("]")[0]
    assert "HS256" in out


def test_TU16_jwt_pyjwt_alias_also_handled():
    src = "import PyJWT\nPyJWT.decode(t, k, verify=False)\n"
    out = _apply(JWTVerifyEnabler, src)
    assert "verify=True" in out


def test_TU17_jwt_non_decode_call_left_alone():
    src = "import jwt\njwt.encode(t, k, algorithm='none')\n"
    out = _apply(JWTVerifyEnabler, src)
    assert "encode" in out and "'none'" in out


def test_TU18_jwt_transform_in_mapping():
    assert SAST_TO_TRANSFORM.get("SAST024") is JWTVerifyEnabler


def test_TU19_jwt_end_to_end_via_auto_remediate():
    src = "import jwt\njwt.decode(t, k, verify=False)\n"
    r = auto_remediate(src, module_id="jwt")
    assert "SAST024" in r.fixed_rules
    assert "JWTVerifyEnabler" in r.transforms_applied


def test_TU20_jwt_no_findings_no_change():
    src = "import jwt\njwt.decode(t, k, algorithms=['HS256'])\n"
    r = auto_remediate(src, module_id="jwt-ok")
    assert r.transforms_applied == []
    assert r.fixed_rules == []


# ─── Zero-Nonce replacement (TU21–TU30) ───────────────────────────────────────

def test_TU21_keyword_nonce_replaced_with_urandom():
    src = (
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x00"*12)\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert "os.urandom(12)" in out
    assert "b'\\x00'" not in out


def test_TU22_positional_zero_iv_replaced():
    src = (
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_CBC, b"\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00\\x00")\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert "os.urandom(16)" in out


def test_TU23_os_import_inserted_when_missing():
    src = (
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x00"*8)\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert "import os" in out
    assert out.index("import os") < out.index("AES.new")


def test_TU24_os_import_not_duplicated():
    src = (
        "import os\n"
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x00"*8)\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert out.count("import os") == 1


def test_TU25_non_zero_nonce_left_alone():
    src = (
        "import os\n"
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x12\\x34"*6)\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert "os.urandom" not in out
    assert "\\x12" in out


def test_TU26_iv_keyword_also_handled():
    src = (
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_CBC, iv=b"\\x00"*16)\n'
    )
    out = _apply(ZeroNonceReplacer, src)
    assert "os.urandom(16)" in out


def test_TU27_non_cipher_call_left_alone():
    src = 'helper.new(key, mode, b"\\x00"*16)\n'
    out = _apply(ZeroNonceReplacer, src)
    assert "os.urandom" not in out


def test_TU28_nonce_transform_in_mapping():
    assert SAST_TO_TRANSFORM.get("SAST022") is ZeroNonceReplacer


def test_TU29_nonce_end_to_end_via_auto_remediate():
    src = (
        "from Crypto.Cipher import AES\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x00"*12)\n'
    )
    r = auto_remediate(src, module_id="iv")
    assert "SAST022" in r.fixed_rules
    assert "ZeroNonceReplacer" in r.transforms_applied


def test_TU30_combined_fix_multiple_rules_one_pass():
    """auto_remediate handles SSL + JWT + IV in one shot."""
    src = (
        "import requests\n"
        "import jwt\n"
        "from Crypto.Cipher import AES\n"
        'requests.get("https://x", verify=False)\n'
        "jwt.decode(t, k, verify=False)\n"
        'AES.new(key, AES.MODE_GCM, nonce=b"\\x00"*12)\n'
    )
    r = auto_remediate(src, module_id="combo")
    assert "SAST022" in r.fixed_rules
    assert "SAST024" in r.fixed_rules
    assert "SAST027" in r.fixed_rules
    assert r.residual_count == 0
