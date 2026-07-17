"""
test_marco_m103.py — Sprint DU: correções da auditoria de DOGFOODING
=====================================================================
O próprio UCO Sensor rodou sobre seu código-fonte; estes testes fixam as
correções dos achados:

  • item 2 — infinite_loop_risk PONDERADO (regressões em test_calibration::TestILR).
  • item 3 — `find_unreferenced_defs`: dead-code por SÍMBOLO não-referenciado
    (funções/classes privadas de módulo nunca usadas), complementando o
    `syntactic_dead_code` (que só pega código pós-return). Conservador: só
    privados, sem decorador, fora de __all__, não-dunder, não citados por string,
    e ignora hooks de teste (`*_for_tests`).
"""
from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

from sensor_core.uco_bridge import find_unreferenced_defs as F  # noqa: E402


# ── item 3: true positives ────────────────────────────────────────────────────

def test_TDU_flags_unused_private_function():
    assert F("def _helper():\n    return 1\ndef main():\n    return 2\n") == ["_helper"]


def test_TDU_flags_unused_private_class():
    assert F("class _Internal:\n    pass\n") == ["_Internal"]


def test_TDU_multiple_unused_sorted():
    assert F("def _a():\n    pass\ndef _b():\n    pass\n") == ["_a", "_b"]


# ── item 3: anti-FP (todos devem retornar []) ─────────────────────────────────

def test_TDU_used_private_not_flagged():
    assert F("def _h():\n    return 1\ndef m():\n    return _h()\n") == []


def test_TDU_public_symbol_never_flagged():
    assert F("def helper():\n    return 1\n") == []


def test_TDU_decorated_not_flagged():
    assert F("import functools\n@functools.cache\ndef _memo():\n    return 1\n") == []


def test_TDU_dunder_not_flagged():
    assert F("def __getattr__(name):\n    return name\n") == []


def test_TDU_all_export_not_flagged():
    assert F("__all__ = ['_api']\ndef _api():\n    return 1\n") == []


def test_TDU_string_mention_getattr_not_flagged():
    assert F("def _dyn():\n    return 1\ndef run(x):\n    return getattr(x, '_dyn')\n") == []


def test_TDU_test_hook_convention_not_flagged():
    assert F("_cache = {}\ndef _reset_for_tests():\n    _cache.clear()\n") == []


def test_TDU_attribute_reference_counts_as_use():
    assert F("def _foo():\n    return 1\nclass C:\n    def m(self):\n        return _foo\n") == []


def test_TDU_syntax_error_returns_empty():
    assert F("def broken(:\n") == []


def test_TDU_recursive_private_not_flagged():
    assert F("def _rec(n):\n    return _rec(n - 1)\n") == []
