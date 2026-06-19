"""
Marco 42 — Sprint K: UCO Transform Bridge + 4 new closed-loop rules (TN01-TN30)
================================================================================

Validates that the SAST↔Fix loop grows from 7 to 11 mapped rules by
exposing UCO core transforms (SAST040, 041) and shipping AST-native
implementations where the UCO core only had advisors (SAST042, 043).

Coverage layout
---------------
* TN01-TN08 — SAST040 detector + UCOUnreachableRemover end-to-end
* TN09-TN15 — SAST041 detector + UCORedundantConditionRemover end-to-end
* TN16-TN22 — SAST042 detector + NoOpAssignRemover (AST native)
* TN23-TN28 — SAST043 detector + UnusedVarRemover  (AST native)
* TN29-TN30 — combined regression + mapping table size pinned
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sast.scanner import scan
from sensor_core.autofix.engine import AutofixEngine
from sensor_core.autofix.sast_remediation import (
    SAST_TO_TRANSFORM, auto_remediate,
)
from sensor_core.autofix.transforms.uco_transform_bridge import (
    UCOUnreachableRemover, UCORedundantConditionRemover,
)
from sensor_core.autofix.transforms.remove_noop_assign import NoOpAssignRemover
from sensor_core.autofix.transforms.remove_unused_var  import UnusedVarRemover


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in getattr(res, "findings", [])]


def _apply(transform_cls, src: str) -> str:
    res = AutofixEngine(transforms=[transform_cls]).apply(src)
    assert res.is_valid_python, f"invalid:\n{res.fixed_source}"
    return res.fixed_source


# ═══════════════════════════════════════════════════════════════════════════════
# SAST040 — Unreachable After Terminal (TN01-TN08)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TN01_sast040_detects_code_after_return():
    src = "def f():\n    return 1\n    x = 2\n"
    assert "SAST040" in _scan_ids(src)


def test_TN02_sast040_detects_code_after_raise():
    src = "def f():\n    raise ValueError\n    x = 2\n"
    assert "SAST040" in _scan_ids(src)


def test_TN03_sast040_detects_code_after_break():
    src = "def f():\n    for i in range(3):\n        break\n        print(i)\n"
    assert "SAST040" in _scan_ids(src)


def test_TN04_sast040_clean_after_return_unflagged():
    src = "def f():\n    return 1\n"
    assert "SAST040" not in _scan_ids(src)


def test_TN05_unreachable_removed_via_apply():
    src = "def f():\n    return 1\n    x = 2\n    print(x)\n"
    out = _apply(UCOUnreachableRemover, src)
    assert "return 1" in out
    assert "x = 2" not in out


def test_TN06_unreachable_end_to_end_via_auto_remediate():
    src = "def f():\n    return 1\n    x = 2\n"
    r = auto_remediate(src, module_id="tn06")
    assert "SAST040" in r.fixed_rules


def test_TN07_unreachable_no_terminal_no_fix():
    src = "def f():\n    return 1\n"
    r = auto_remediate(src, module_id="tn07")
    assert r.fixed_rules == []


def test_TN08_unreachable_inside_nested_block():
    src = "def f():\n    if True:\n        return 1\n        dead = 2\n    return 0\n"
    assert "SAST040" in _scan_ids(src)


# ═══════════════════════════════════════════════════════════════════════════════
# SAST041 — Redundant Constant Condition (TN09-TN15)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TN09_sast041_detects_if_true():
    assert "SAST041" in _scan_ids("if True:\n    print(1)\n")


def test_TN10_sast041_detects_if_false():
    assert "SAST041" in _scan_ids("if False:\n    print(1)\n")


def test_TN11_sast041_detects_while_false():
    assert "SAST041" in _scan_ids("while False:\n    pass\n")


def test_TN12_sast041_normal_condition_unflagged():
    assert "SAST041" not in _scan_ids("if x > 0:\n    print(1)\n")


def test_TN13_if_true_flattened_via_apply():
    out = _apply(UCORedundantConditionRemover, "if True:\n    print('a')\n")
    assert "if True" not in out
    assert "print('a')" in out


def test_TN14_if_true_end_to_end():
    r = auto_remediate("if True:\n    print('a')\n", module_id="tn14")
    assert "SAST041" in r.fixed_rules


def test_TN15_while_true_not_flagged_as_redundant():
    # while True is the canonical infinite loop pattern — should NOT trigger.
    assert "SAST041" not in _scan_ids("while True:\n    pass\n")


# ═══════════════════════════════════════════════════════════════════════════════
# SAST042 — No-Op Self Assignment (TN16-TN22)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TN16_sast042_detects_x_equals_x():
    assert "SAST042" in _scan_ids("x = 1\nx = x\n")


def test_TN17_sast042_detects_aug_assign_plus_zero():
    assert "SAST042" in _scan_ids("x = 1\nx += 0\n")


def test_TN18_sast042_detects_aug_assign_mult_one():
    assert "SAST042" in _scan_ids("x = 1\nx *= 1\n")


def test_TN19_sast042_normal_assign_unflagged():
    assert "SAST042" not in _scan_ids("x = 1\nx = x + 1\n")


def test_TN20_noop_self_assign_removed():
    out = _apply(NoOpAssignRemover, "x = 1\nx = x\nprint(x)\n")
    assert "x = x" not in out
    assert "x = 1" in out


def test_TN21_noop_plus_zero_removed():
    out = _apply(NoOpAssignRemover, "x = 1\nx += 0\nprint(x)\n")
    assert "x += 0" not in out


def test_TN22_noop_end_to_end():
    r = auto_remediate("x = 1\nx = x\n", module_id="tn22")
    assert "SAST042" in r.fixed_rules


# ═══════════════════════════════════════════════════════════════════════════════
# SAST043 — Unused Local Variable (TN23-TN28)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TN23_sast043_detects_unused_assignment():
    src = "def f():\n    unused = 999\n    return 1\n"
    assert "SAST043" in _scan_ids(src)


def test_TN24_sast043_does_not_flag_used_var():
    src = "def f():\n    x = 1\n    return x\n"
    assert "SAST043" not in _scan_ids(src)


def test_TN25_sast043_does_not_flag_underscore_prefixed():
    src = "def f():\n    _internal = 1\n    return 2\n"
    assert "SAST043" not in _scan_ids(src)


def test_TN26_sast043_does_not_flag_function_params():
    src = "def f(a, b):\n    return a\n"
    assert "SAST043" not in _scan_ids(src)


def test_TN27_unused_var_removed():
    src = "def f():\n    unused = 999\n    return 1\n"
    out = _apply(UnusedVarRemover, src)
    assert "unused" not in out
    assert "return 1" in out


def test_TN28_unused_var_with_side_effect_preserved():
    """RHS with a Call (side effect) is NOT dropped — conservative."""
    src = "def f():\n    log = print('side')\n    return 1\n"
    out = _apply(UnusedVarRemover, src)
    assert "print('side')" in out   # call preserved


# ═══════════════════════════════════════════════════════════════════════════════
# Combined regression + mapping table (TN29-TN30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TN29_combined_fix_closes_all_four_rules_in_one_pass():
    src = (
        "def f(a):\n"
        "    unused = 1\n"
        "    if True:\n"
        "        a = a\n"
        "    return a\n"
        "    print('dead')\n"
    )
    r = auto_remediate(src, module_id="tn29")
    for rule in ("SAST040", "SAST041", "SAST042", "SAST043"):
        assert rule in r.fixed_rules, f"{rule} not fixed: {r.fixed_rules}"
    assert r.residual_count == 0


def test_TN30_mapping_table_grew_to_eleven_entries():
    # Pin: regressions that drop a Sprint-K rule must fail this assertion.
    assert len(SAST_TO_TRANSFORM) == 11
    for rule in ("SAST040", "SAST041", "SAST042", "SAST043"):
        assert rule in SAST_TO_TRANSFORM
