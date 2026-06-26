"""
Marco 60 — QA Loop Round 1 fixes (TQA01-TQA15)
================================================

Pins the 6 high-leverage fixes confirmed by the 4-lens QA loop
(QA + Product + Engineering + Security) on the v3.9.0 surface,
adversarially-verified 2/2 (or 2/2 + 1/2 split with manual judgment).

QA-FIX-1 CRIT  api/server.py — `_safe_500_envelope` strips traceback
                from production responses (gated on UCO_INCLUDE_TRACE).
QA-FIX-2 HIGH  api/server.py — `_QueryParamError` + `_qp_int`/`_qp_float`
                map malformed query params to 400 (was 500 + trace leak).
QA-FIX-3 MED   api/server.py:handle_tenants_usage — strict YYYY-MM
                regex on `?period=…` (was silently echoing back garbage).
QA-FIX-4 MED   api/server.py:handle_tenants_{get,suspend,reactivate} —
                strip + sanitize tenant_id (was phantom 404s on
                whitespace + newline injection via !r echo).
QA-FIX-5 MED   api/server.py — `_sanitize_for_echo` cleans user-supplied
                values before they appear in error bodies.
QA-FIX-6 MED   marketplace.py — `_has_redos_shape("")` returns False
                (empty string is not a regex shape; only over-long
                strings + nested quantifiers are DoS surface).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


# ═══════════════════════════════════════════════════════════════════════════════
# TQA01-TQA03 — QA-FIX-1: safe 500 envelope
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQA01_safe_500_strips_trace_by_default(monkeypatch):
    """QA-FIX-1 (CRITICAL): default response must NOT contain `trace` key."""
    from api.server import _safe_500_envelope
    monkeypatch.delenv("UCO_INCLUDE_TRACE", raising=False)
    code, body = _safe_500_envelope(RuntimeError("boom"))
    assert code == 500
    assert body["error"] == "internal_error"
    assert body["error_class"] == "RuntimeError"
    assert "trace" not in body
    # No file paths leaked
    assert "/home/" not in str(body)
    assert ".py" not in str(body)


def test_TQA02_safe_500_includes_trace_only_under_explicit_env(monkeypatch):
    """QA-FIX-1: UCO_INCLUDE_TRACE=1 → trace shows (dev/debug mode)."""
    from api.server import _safe_500_envelope
    monkeypatch.setenv("UCO_INCLUDE_TRACE", "1")
    try:
        raise ValueError("debug me")
    except ValueError as e:
        code, body = _safe_500_envelope(e)
    assert "trace" in body
    assert "ValueError" in body["trace"]


def test_TQA03_safe_500_unknown_exception_class():
    """QA-FIX-1: unfamiliar exception class still produces structured body."""
    from api.server import _safe_500_envelope

    class _CustomBoom(Exception):
        pass

    code, body = _safe_500_envelope(_CustomBoom("x"))
    assert body["error_class"] == "_CustomBoom"


# ═══════════════════════════════════════════════════════════════════════════════
# TQA04-TQA07 — QA-FIX-2: typed query-param parsers
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQA04_qp_int_returns_default_when_absent():
    from api.server import _qp_int
    assert _qp_int({}, "limit", 50) == 50


def test_TQA05_qp_int_parses_valid_value():
    from api.server import _qp_int
    assert _qp_int({"limit": ["100"]}, "limit", 50) == 100


def test_TQA06_qp_int_raises_QueryParamError_on_garbage():
    from api.server import _qp_int, _QueryParamError
    with pytest.raises(_QueryParamError) as exc_info:
        _qp_int({"limit": ["abc"]}, "limit", 50)
    assert exc_info.value.param == "limit"
    assert exc_info.value.value == "abc"
    assert exc_info.value.expected == "integer"


def test_TQA07_qp_float_raises_QueryParamError_on_garbage():
    from api.server import _qp_float, _QueryParamError
    with pytest.raises(_QueryParamError):
        _qp_float({"penalty": ["not-a-number"]}, "penalty", 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# TQA08-TQA10 — QA-FIX-3: period_key strict validation
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQA08_period_key_validator_accepts_well_formed():
    from api.server import _validate_period_key
    assert _validate_period_key("2026-01") == "2026-01"
    assert _validate_period_key("2026-12") == "2026-12"
    assert _validate_period_key(" 2026-06 ") == "2026-06"  # strip


def test_TQA09_period_key_validator_rejects_malformed():
    from api.server import _validate_period_key
    assert _validate_period_key("2026-13") is None  # month > 12
    assert _validate_period_key("2026-00") is None  # month 0
    assert _validate_period_key("foo")     is None
    assert _validate_period_key("2026")    is None  # missing month
    assert _validate_period_key("'; DROP TABLE x;--") is None
    assert _validate_period_key("")        is None


def test_TQA10_handle_tenants_usage_returns_400_on_bad_period(isolated_store):
    from api.server import handle_tenants_create, handle_tenants_usage
    handle_tenants_create({"tenant_id": "acme", "plan": "FREE"})
    code, body = handle_tenants_usage("acme", period="2026-13")
    assert code == 400
    assert body["error"] == "invalid_query_param"
    assert body["param"] == "period"


# ═══════════════════════════════════════════════════════════════════════════════
# TQA11-TQA13 — QA-FIX-4/5: tenant_id strip + sanitize echo
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQA11_handle_tenants_get_strips_whitespace(isolated_store):
    from api.server import handle_tenants_create, handle_tenants_get
    handle_tenants_create({"tenant_id": "acme"})
    # leading/trailing whitespace should resolve
    code_ok, _ = handle_tenants_get("  acme  ")
    code_404, body = handle_tenants_get("ghost")
    assert code_ok == 200
    assert code_404 == 404
    assert body["error"] == "tenant_not_found"
    assert body["tenant_id"] == "ghost"


def test_TQA12_sanitize_for_echo_strips_newlines_and_control_chars():
    from api.server import _sanitize_for_echo
    payload = "evil\nLOG INJECTION\rmore\twork"
    cleaned = _sanitize_for_echo(payload)
    assert "\n" not in cleaned
    assert "\r" not in cleaned
    assert "\t" not in cleaned


def test_TQA13_sanitize_for_echo_caps_length():
    from api.server import _sanitize_for_echo
    long = "X" * 1000
    out = _sanitize_for_echo(long, max_len=10)
    assert len(out) <= 11   # 10 chars + ellipsis
    assert out.endswith("…")


# ═══════════════════════════════════════════════════════════════════════════════
# TQA14-TQA15 — QA-FIX-6: marketplace ReDoS guard empty-string handling
# ═══════════════════════════════════════════════════════════════════════════════

def test_TQA14_redos_guard_accepts_empty_string():
    """Empty string is NOT a regex shape — must NOT trip the guard."""
    from governance.marketplace import _has_redos_shape
    assert _has_redos_shape("") is False
    assert _has_redos_shape(None) is False


def test_TQA15_redos_guard_still_rejects_dangerous_patterns():
    """Regression: the actual ReDoS shapes are still rejected."""
    from governance.marketplace import _has_redos_shape
    assert _has_redos_shape("(.*)+") is True
    assert _has_redos_shape("(.+)+") is True
    assert _has_redos_shape("X" * 2001) is True
    assert _has_redos_shape("normal label") is False
