"""
Marco 65 — Sprint AE: validation-script dispatch bug + JS05 bare-call gap (TAE01-TAE06)
=========================================================================================

Sprint AE ran a multi-agent loop resolving 8 new CVE/sha pairs (lodash, etcd,
tokio, netty, laravel, rails, dotnet, git) and re-running the AC-3/AD CVE
before/after methodology against each.

Two real findings came out of it:

1. ``paper/cve_diff_check.py`` called ``sast.scanner.scan()`` (the Python-only
   AST engine) unconditionally for every language, silently no-op'ing on
   every non-Python file — even though the production API
   (``api/server.py``'s ``handle_sast``, M9.0) already correctly dispatches
   JS/TS/Java/Go to ``sast.multilang_scanner.scan_multilang``. This means
   every prior non-Python verdict from Sprint AC-3/AD/AE (curl, golang/go,
   axios, spring-framework, rust-lang/regex, lodash, etcd, netty) was reached
   via the wrong code path. Fixed by mirroring the M9.0 routing in the
   validation script. Re-running all 6 affected JS/Java/Go cases with the
   corrected dispatch confirmed the BLIND_SPOT verdicts held regardless
   (no rule matched any of those 6 patterns even via the right engine) —
   the original conclusions were right by coincidence, not rigor.

2. While re-verifying the lodash/lodash CVE-2021-23337 case (command
   injection via ``_.template``'s ``variable`` option) with the corrected
   multilang engine, JS05 ("Code injection via Function constructor") still
   didn't fire — because lodash's actual vulnerable call is the bare
   ``Function(importsKeys, ...)`` (no ``new``), which is semantically
   identical to ``new Function(...)`` but wasn't matched by JS05's
   ``\\bnew\\s+Function\\s*\\(`` regex. Fixed by broadening it to
   ``\\b(?:new\\s+)?Function\\s*\\(`` (the leading ``\\b`` still excludes
   ``isFunction(``/``castFunction(``-style calls).
"""
from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

from sast.multilang_scanner import scan_multilang, language_for_extension


def _ids(source: str, ext: str):
    return {f.rule_id for f in scan_multilang(source, ext).findings}


def test_TAE01_js05_bare_function_call_now_detected():
    """TAE01: `Function(...)` without `new` is the real lodash CVE-2021-23337 pattern."""
    src = "var result = Function(importsKeys, sourceURL + 'return ' + source).apply(undefined, importsValues);"
    assert "JS05" in _ids(src, ".js")


def test_TAE02_js05_new_function_still_detected():
    """TAE02: regression guard — the original `new Function(...)` form must keep firing."""
    assert "JS05" in _ids("const f = new Function('return 1');", ".js")


def test_TAE03_js05_isfunction_not_a_false_positive():
    """TAE03: `isFunction(value)`/`castFunction(value)` must not trigger JS05."""
    assert "JS05" not in _ids("if (isFunction(value)) { return castFunction(value); }", ".js")


def test_TAE04_js05_printfunction_call_not_a_false_positive():
    """TAE04: any `*Function(` identifier (not just is/cast-prefixed) must not match."""
    assert "JS05" not in _ids("logFunction(handler); registerFunction(cb);", ".js")


def test_TAE05_language_for_extension_routes_js_java_go():
    """TAE05: pins the M9.0 extension routing relied on by cve_diff_check.py's dispatch."""
    assert language_for_extension(".js") == "javascript"
    assert language_for_extension(".java") == "java"
    assert language_for_extension(".go") == "go"
    assert language_for_extension(".rs") == "rust"
    assert language_for_extension(".c") is None
    assert language_for_extension(".py") is None


def test_TAE06_lodash_vulnerable_and_fixed_both_flag_function_risk():
    """TAE06: the fix sanitizes the input but the risky Function() call site remains —
    SAST correctly flags the pattern in both, which is expected static-analysis
    behavior (it can't verify a guard is sufficient, only that the risky call exists)."""
    vulnerable = "var f = Function(importsKeys, 'return ' + source).apply(undefined, importsValues);"
    fixed = (
        "if (reForbiddenIdentifierChars.test(variable)) { throw new Error('bad'); }\n"
        "var f = Function(importsKeys, 'return ' + source).apply(undefined, importsValues);"
    )
    assert "JS05" in _ids(vulnerable, ".js")
    assert "JS05" in _ids(fixed, ".js")
