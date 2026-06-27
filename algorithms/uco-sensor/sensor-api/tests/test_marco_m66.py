"""
Marco 66 — Sprint AF correction: SAST048 (TAG01-TAG07)
=======================================================

While re-verifying the AF consolidated timeline report against the
hook's pushback (the goal isn't met just because most cases are
"architecturally infeasible blind spots"), two real classification
errors were found and fixed (CVE-2024-47081/CVE-2023-32681 were
mislabeled BLIND_SPOT when SAST046/047 actually fire on them), and a
third, genuinely new generalizable rule was added: SAST048, pinned
against the root cause of CVE-2021-23727 (celery/celery stored command
injection via ``exception_to_python()``'s unsafe ``getattr`` chain).

All cases below were verified against the real GitHub-fetched
vulnerable (``2d8dbc2a``) and fixed (``1f7ad7e6``) snapshots of
``celery/backends/base.py`` before being pinned here.
"""
from __future__ import annotations

from sast.scanner import scan


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in res.findings]


def test_TAG01_sast048_detects_real_celery_shape():
    # Simplified shape of the real vulnerable exception_to_python():
    # cls is resolved via a getattr() chain from attacker-influenced
    # exc_type/exc_module data, then called directly with no type check.
    src = (
        "def exception_to_python(self, exc):\n"
        "    exc_module = exc.get('exc_module')\n"
        "    exc_type = exc['exc_type']\n"
        "    cls = sys.modules[exc_module]\n"
        "    for name in exc_type.split('.'):\n"
        "        cls = getattr(cls, name)\n"
        "    exc_msg = exc.get('exc_message', '')\n"
        "    exc = cls(exc_msg)\n"
        "    return exc\n"
    )
    assert "SAST048" in _scan_ids(src)


def test_TAG02_sast048_silent_on_real_celery_fixed_shape():
    # Exact fixed shape: same resolution, but guarded by an
    # isinstance/issubclass type check before the call.
    src = (
        "def exception_to_python(self, exc):\n"
        "    exc_module = exc.get('exc_module')\n"
        "    exc_type = exc['exc_type']\n"
        "    cls = sys.modules[exc_module]\n"
        "    for name in exc_type.split('.'):\n"
        "        cls = getattr(cls, name)\n"
        "    if not isinstance(cls, type) or not issubclass(cls, BaseException):\n"
        "        raise SecurityError('not an exception class')\n"
        "    exc_msg = exc.get('exc_message', '')\n"
        "    exc = cls(exc_msg)\n"
        "    return exc\n"
    )
    assert "SAST048" not in _scan_ids(src)


def test_TAG03_sast048_silent_on_literal_attribute_name():
    # getattr() with a fixed, literal attribute name is ordinary
    # constant-attribute dispatch, not data-driven reflection.
    src = (
        "def render(self, obj):\n"
        "    handler = getattr(obj, 'render')\n"
        "    return handler()\n"
    )
    assert "SAST048" not in _scan_ids(src)


def test_TAG04_sast048_silent_when_resolved_object_never_called():
    src = (
        "def inspect_only(obj, name):\n"
        "    target = getattr(obj, name)\n"
        "    return repr(target)\n"
    )
    assert "SAST048" not in _scan_ids(src)


def test_TAG05_sast048_detects_single_step_getattr_then_call():
    # No loop needed — a single dynamic getattr() followed by an
    # unguarded call is enough to trigger the same risk shape.
    src = (
        "def dispatch(obj, action_name):\n"
        "    handler = getattr(obj, action_name)\n"
        "    return handler(42)\n"
    )
    assert "SAST048" in _scan_ids(src)


def test_TAG06_sast048_silent_with_issubclass_guard_only():
    src = (
        "def dispatch(obj, action_name):\n"
        "    handler = getattr(obj, action_name)\n"
        "    if issubclass(handler, BaseException):\n"
        "        return handler('x')\n"
    )
    assert "SAST048" not in _scan_ids(src)


def test_TAG07_sast048_finding_has_correct_metadata():
    src = (
        "def dispatch(obj, action_name):\n"
        "    handler = getattr(obj, action_name)\n"
        "    return handler(42)\n"
    )
    findings = [f for f in scan(src, ".py").findings if f.rule_id == "SAST048"]
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert findings[0].cwe_id == "CWE-470"
