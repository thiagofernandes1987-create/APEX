"""
Marco 61 — Sprint AA: UCO Deep Integration, part 1 (TUC01-TUC15)
=================================================================

AA-1: bridges the 5 previously-orphan ``CodeTransform`` classes from
``algorithms/uco/universal_code_optimizer_v4.py`` that Sprint K (Marco 42)
left unwired. Two of them detect a genuine defect and get a new SAST rule
each (SAST044, SAST045), growing the closed SAST↔Fix loop from 11 to 13
mapped rules. The other three are cosmetic-only and are bridged as
directly-callable transforms with no SAST rule attached (see
``uco_transform_bridge.py`` module docstring for the rationale).

Coverage layout
---------------
* TUC01-TUC06 — SAST044 detector + UCOAdjacentDuplicateRemover end-to-end
* TUC07-TUC12 — SAST045 detector + UCOConstantFolder end-to-end
* TUC13-TUC15 — cosmetic transforms (merge / whitespace / empty block) callable
"""
from __future__ import annotations

import sys
from pathlib import Path

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from sast.scanner import scan
from sensor_core.autofix.engine import AutofixEngine
from sensor_core.autofix.sast_remediation import SAST_TO_TRANSFORM, auto_remediate
from sensor_core.autofix.transforms.uco_transform_bridge import (
    UCOAdjacentDuplicateRemover,
    UCOConstantFolder,
    UCODuplicateControlBlockMerger,
    UCOBracketWhitespaceNormalizer,
    UCOEmptyBlockRemover,
)


def _scan_ids(src: str) -> list:
    res = scan(src, file_extension=".py")
    return [f.rule_id for f in getattr(res, "findings", [])]


def _apply(transform_cls, src: str) -> str:
    res = AutofixEngine(transforms=[transform_cls]).apply(src)
    assert res.is_valid_python, f"invalid:\n{res.fixed_source}"
    return res.fixed_source


# ═══════════════════════════════════════════════════════════════════════════
# SAST044 — Adjacent Duplicate Statement (TUC01-TUC06)
# ═══════════════════════════════════════════════════════════════════════════

def test_TUC01_sast044_detects_consecutive_duplicate_line():
    src = "x = 1\nx = 1\nprint(x)\n"
    assert "SAST044" in _scan_ids(src)


def test_TUC02_sast044_ignores_whitespace_only_diff():
    src = "x = 1\nx = 1  \nprint(x)\n"
    assert "SAST044" in _scan_ids(src)


def test_TUC03_sast044_clean_no_dup_unflagged():
    src = "x = 1\ny = 2\nprint(x, y)\n"
    assert "SAST044" not in _scan_ids(src)


def test_TUC04_sast044_blank_lines_dont_count_as_duplicate():
    src = "x = 1\n\n\ny = 2\n"
    assert "SAST044" not in _scan_ids(src)


def test_TUC05_duplicate_removed_via_apply():
    src = "x = 1\nx = 1\nprint(x)\n"
    out = _apply(UCOAdjacentDuplicateRemover, src)
    assert out.count("x = 1") == 1


def test_TUC06_duplicate_end_to_end_via_auto_remediate():
    src = "x = 1\nx = 1\nprint(x)\n"
    r = auto_remediate(src, module_id="tuc06")
    assert "SAST044" in r.fixed_rules


# ═══════════════════════════════════════════════════════════════════════════
# SAST045 — Unsimplified Constant Expression (TUC07-TUC12)
# ═══════════════════════════════════════════════════════════════════════════

def test_TUC07_sast045_detects_foldable_binop():
    src = "x = 2 + 3 * 4\nprint(x)\n"
    assert "SAST045" in _scan_ids(src)


def test_TUC08_sast045_detects_foldable_boolop():
    src = "x = True and False\nprint(x)\n"
    assert "SAST045" in _scan_ids(src)


def test_TUC09_sast045_clean_var_rhs_unflagged():
    src = "y = 2\nx = y * 4\nprint(x)\n"
    assert "SAST045" not in _scan_ids(src)


def test_TUC10_sast045_plain_literal_unflagged():
    src = "x = 5\nprint(x)\n"
    assert "SAST045" not in _scan_ids(src)


def test_TUC11_constant_folded_via_apply():
    src = "x = 2 + 3 * 4\nprint(x)\n"
    out = _apply(UCOConstantFolder, src)
    assert "x = 14" in out


def test_TUC12_constant_fold_end_to_end_via_auto_remediate():
    src = "x = 2 + 3 * 4\nprint(x)\n"
    r = auto_remediate(src, module_id="tuc12")
    assert "SAST045" in r.fixed_rules


# ═══════════════════════════════════════════════════════════════════════════
# Cosmetic transforms — callable but not wired to a SAST rule (TUC13-TUC15)
# ═══════════════════════════════════════════════════════════════════════════

def test_TUC13_duplicate_control_block_merger_callable():
    # The transform merges literally-adjacent identical lines, not blocks
    # separated by other content — exercise it on directly-adjacent dupes.
    src = "x = 1\nx = 1\nprint(x)\n"
    out = _apply(UCODuplicateControlBlockMerger, src)
    assert out.count("x = 1") == 1


def test_TUC14_bracket_whitespace_normalizer_callable():
    src = "x = 1   \n\n\n\ny = 2\n"
    out = _apply(UCOBracketWhitespaceNormalizer, src)
    assert "   \n" not in out
    assert "\n\n\n\n" not in out


def test_TUC15_empty_block_remover_callable_noop_on_python():
    # EmptyBlockRemover targets C-like {} blocks; Python source has none,
    # so it must be a safe no-op rather than corrupt the source.
    src = "x = {}\nprint(x)\n"
    out = _apply(UCOEmptyBlockRemover, src)
    assert "x = {}" in out


# ═══════════════════════════════════════════════════════════════════════════
# Mapping table size — pinned alongside test_marco_m42's TN30
# ═══════════════════════════════════════════════════════════════════════════

def test_TUC16_mapping_table_grew_to_thirteen_entries():
    assert len(SAST_TO_TRANSFORM) == 13
    for rule in ("SAST044", "SAST045"):
        assert rule in SAST_TO_TRANSFORM
