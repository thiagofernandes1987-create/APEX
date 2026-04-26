"""
test_marco_m9.py — M6.1 Incremental Analysis Engine  (30 tests TI01–TI30)
==========================================================================
APEX DEEP mode — Incremental scanner with per-file metric deltas,
regression detection, git diff integration, and REST endpoint.

WBS M6.1: Incremental Analysis Engine
  Differentiator: SonarQube incremental is enterprise-only.
  UCO-Sensor delivers it free, with Hamiltonian delta tracking + regression.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ───────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scan.incremental_scanner import (
    CHANGE_ADDED, CHANGE_DELETED, CHANGE_MODIFIED, CHANGE_RENAMED,
    ChangedFile, FileDelta, IncrementalScanResult, IncrementalScanner,
)
import api.server as srv

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_store(history: dict | None = None):
    """Build a minimal mock SnapshotStore."""
    store   = MagicMock()
    history = history or {}

    def _get_history(module_id, window=50):
        return history.get(module_id, [])

    store.get_history.side_effect = _get_history
    store.insert.return_value     = None
    store.list_modules.return_value = list(history.keys())
    return store


def _make_mv(h: float = 5.0, cc: int = 3, status: str = "STABLE",
             lang: str = "python"):
    """Build a minimal mock MetricVector."""
    mv = MagicMock()
    mv.hamiltonian           = h
    mv.cyclomatic_complexity = cc
    mv.status                = status
    mv.language              = lang
    return mv


_SIMPLE_PY = """\
def hello(name):
    return f"Hello, {name}!"
"""

_COMPLEX_PY = """\
def compute(x):
    if x > 0:
        if x > 10:
            return x * 2
        return x
    elif x == 0:
        return 0
    else:
        for i in range(x):
            print(i)
        return -x
"""


def _make_isr(deltas=None) -> IncrementalScanResult:
    """Convenience builder for IncrementalScanResult."""
    deltas = deltas or []
    return IncrementalScanResult(
        total_changed  = len(deltas),
        added_count    = sum(1 for d in deltas if d.change_type == CHANGE_ADDED),
        modified_count = sum(1 for d in deltas if d.change_type == CHANGE_MODIFIED),
        deleted_count  = sum(1 for d in deltas if d.change_type == CHANGE_DELETED),
        renamed_count  = 0,
        scanned_count  = sum(1 for d in deltas if d.change_type != CHANGE_DELETED),
        error_count    = 0,
        regressions    = sum(1 for d in deltas if d.regression),
        new_criticals  = sum(
            1 for d in deltas
            if d.status_after == "CRITICAL" and d.status_before != "CRITICAL"
        ),
        file_deltas    = deltas,
        commit_hash    = "abc123",
        base_commit    = "HEAD~1",
        scan_duration_s = 0.042,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Group 1 — ChangedFile  (TI01–TI03)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChangedFile:

    def test_ti01_basic_construction(self):
        """TI01: ChangedFile fields default correctly."""
        cf = ChangedFile(path="src/auth.py", change_type=CHANGE_MODIFIED)
        assert cf.path        == "src/auth.py"
        assert cf.change_type == CHANGE_MODIFIED
        assert cf.old_path    is None
        assert cf.content     is None

    def test_ti02_renamed_carries_old_path(self):
        """TI02: RENAMED ChangedFile records both old and new paths."""
        cf = ChangedFile(
            path        = "src/auth_v2.py",
            change_type = CHANGE_RENAMED,
            old_path    = "src/auth.py",
        )
        assert cf.change_type == CHANGE_RENAMED
        assert cf.old_path    == "src/auth.py"
        assert cf.path        == "src/auth_v2.py"

    def test_ti03_content_stored(self):
        """TI03: ChangedFile.content holds provided source text."""
        cf = ChangedFile(path="x.py", change_type=CHANGE_ADDED, content="x = 1\n")
        assert cf.content == "x = 1\n"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 2 — FileDelta  (TI04–TI07)
# ═══════════════════════════════════════════════════════════════════════════════

class TestFileDelta:

    def test_ti04_defaults_are_safe(self):
        """TI04: FileDelta numeric defaults are zero / non-regression."""
        d = FileDelta(path="a.py", change_type=CHANGE_ADDED)
        assert d.old_hamiltonian == 0.0
        assert d.new_hamiltonian == 0.0
        assert d.delta_h         == 0.0
        assert d.regression      is False
        assert d.scan_error      is None

    def test_ti05_to_dict_contains_all_keys(self):
        """TI05: to_dict() exposes all 13 expected fields."""
        d = FileDelta(
            path="b.py", change_type=CHANGE_MODIFIED,
            old_hamiltonian=5.0, new_hamiltonian=8.0, delta_h=3.0,
            old_cc=2, new_cc=4, delta_cc=2,
            status_before="STABLE", status_after="WARNING",
            regression=True,
        )
        keys = set(d.to_dict().keys())
        required = {
            "path", "change_type", "language",
            "old_hamiltonian", "new_hamiltonian", "delta_h",
            "old_cc", "new_cc", "delta_cc",
            "status_before", "status_after",
            "regression", "scan_error",
        }
        assert required.issubset(keys)

    def test_ti06_regression_preserved_in_dict(self):
        """TI06: regression=True is visible in to_dict()."""
        d = FileDelta(path="c.py", change_type=CHANGE_MODIFIED, regression=True)
        assert d.to_dict()["regression"] is True

    def test_ti07_deleted_status_after(self):
        """TI07: DELETED FileDelta records status_after='DELETED' in dict."""
        d = FileDelta(path="old.py", change_type=CHANGE_DELETED,
                     status_after="DELETED")
        result = d.to_dict()
        assert result["status_after"]  == "DELETED"
        assert result["change_type"]   == CHANGE_DELETED


# ═══════════════════════════════════════════════════════════════════════════════
# Group 3 — IncrementalScanResult  (TI08–TI12)
# ═══════════════════════════════════════════════════════════════════════════════

class TestIncrementalScanResult:

    def test_ti08_summary_has_expected_labels(self):
        """TI08: summary() output contains 'Incremental Scan' and 'Regressions'."""
        r = _make_isr()
        s = r.summary()
        assert "Incremental Scan" in s
        assert "Regressions" in s
        assert "Duration" in s

    def test_ti09_regressions_list_filters_correctly(self):
        """TI09: regressions_list() returns only entries with regression=True."""
        d_reg = FileDelta("x.py", CHANGE_MODIFIED, regression=True)
        d_ok  = FileDelta("y.py", CHANGE_MODIFIED, regression=False)
        r     = _make_isr([d_reg, d_ok])
        assert len(r.regressions_list()) == 1
        assert r.regressions_list()[0].path == "x.py"

    def test_ti10_new_criticals_list_excludes_preexisting(self):
        """TI10: new_criticals_list() skips files already CRITICAL before."""
        d_new  = FileDelta("a.py", CHANGE_MODIFIED,
                            status_before="WARNING", status_after="CRITICAL")
        d_pre  = FileDelta("b.py", CHANGE_MODIFIED,
                            status_before="CRITICAL", status_after="CRITICAL")
        d_ok   = FileDelta("c.py", CHANGE_MODIFIED,
                            status_before="STABLE", status_after="STABLE")
        r  = _make_isr([d_new, d_pre, d_ok])
        nc = r.new_criticals_list()
        assert len(nc) == 1
        assert nc[0].path == "a.py"

    def test_ti11_to_dict_all_required_keys(self):
        """TI11: to_dict() has all 13 required top-level fields."""
        d = _make_isr().to_dict()
        for key in (
            "total_changed", "added_count", "modified_count",
            "deleted_count", "renamed_count", "scanned_count",
            "error_count", "regressions", "new_criticals",
            "file_deltas", "commit_hash", "base_commit", "scan_duration_s",
        ):
            assert key in d, f"Missing key: {key}"

    def test_ti12_scan_duration_rounded_to_3dp(self):
        """TI12: scan_duration_s is rounded to 3 decimal places in to_dict."""
        r = _make_isr()
        r.scan_duration_s = 0.123456789
        assert r.to_dict()["scan_duration_s"] == round(0.123456789, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# Group 4 — IncrementalScanner.scan_files()  (TI13–TI17)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScanFiles:

    def test_ti13_empty_path_list(self, tmp_path):
        """TI13: scan_files([]) → total_changed == 0, no errors."""
        scanner = IncrementalScanner(root=str(tmp_path))
        result  = scanner.scan_files([])
        assert result.total_changed == 0
        assert result.scanned_count == 0
        assert result.error_count   == 0

    def test_ti14_new_file_no_history_is_added(self, tmp_path):
        """TI14: file present on disk with no store history → ADDED."""
        (tmp_path / "new.py").write_text(_SIMPLE_PY, encoding="utf-8")
        store   = _make_store({})           # no history
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        result  = scanner.scan_files(["new.py"])
        assert result.total_changed                    == 1
        assert result.added_count                      == 1
        assert result.file_deltas[0].change_type       == CHANGE_ADDED

    def test_ti15_existing_file_with_history_is_modified(self, tmp_path):
        """TI15: file on disk + store history → MODIFIED, old_h from baseline."""
        (tmp_path / "auth.py").write_text(_SIMPLE_PY, encoding="utf-8")
        mv_old  = _make_mv(h=4.0, cc=2, status="STABLE")
        store   = _make_store({"auth.py": [mv_old]})
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        result  = scanner.scan_files(["auth.py"])
        delta   = result.file_deltas[0]
        assert delta.change_type     == CHANGE_MODIFIED
        assert delta.old_hamiltonian == 4.0

    def test_ti16_missing_file_is_deleted(self, tmp_path):
        """TI16: file absent from disk → DELETED, old_h from baseline."""
        mv_old  = _make_mv(h=6.0, cc=3, status="WARNING")
        store   = _make_store({"gone.py": [mv_old]})
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        result  = scanner.scan_files(["gone.py"])
        delta   = result.file_deltas[0]
        assert delta.change_type     == CHANGE_DELETED
        assert delta.status_after    == "DELETED"
        assert delta.old_hamiltonian == 6.0
        assert delta.regression      is False      # deletion ≠ regression

    def test_ti17_multiple_files_counts_match(self, tmp_path):
        """TI17: mixed added/modified/deleted → correct per-type counts."""
        (tmp_path / "a.py").write_text(_SIMPLE_PY, encoding="utf-8")
        (tmp_path / "b.py").write_text(_SIMPLE_PY, encoding="utf-8")
        # c.py is absent → deleted
        mv_a  = _make_mv(h=3.0, cc=1)
        store = _make_store({"a.py": [mv_a]})       # a → MODIFIED
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        result  = scanner.scan_files(["a.py", "b.py", "c.py"])
        assert result.total_changed   == 3
        assert result.modified_count  == 1   # a.py has history
        assert result.added_count     == 1   # b.py new
        assert result.deleted_count   == 1   # c.py gone


# ═══════════════════════════════════════════════════════════════════════════════
# Group 5 — IncrementalScanner.scan_changed_files()  (TI18–TI21)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScanChangedFiles:

    def test_ti18_empty_content_no_error(self, tmp_path):
        """TI18: ChangedFile with content='' → scan_error=None, h=0."""
        cf      = ChangedFile(path="empty.py", change_type=CHANGE_ADDED, content="")
        scanner = IncrementalScanner(root=str(tmp_path))
        result  = scanner.scan_changed_files([cf])
        delta   = result.file_deltas[0]
        assert delta.scan_error      is None
        assert delta.new_hamiltonian == 0.0

    def test_ti19_unsupported_extension_produces_scan_error(self, tmp_path):
        """TI19: .txt extension → scan_error contains 'Unsupported'."""
        cf      = ChangedFile(path="readme.txt", change_type=CHANGE_MODIFIED,
                              content="some text")
        scanner = IncrementalScanner(root=str(tmp_path))
        result  = scanner.scan_changed_files([cf])
        delta   = result.file_deltas[0]
        assert delta.scan_error is not None
        assert "Unsupported" in delta.scan_error

    def test_ti20_deleted_change_no_regression(self, tmp_path):
        """TI20: DELETED ChangedFile → status_after='DELETED', regression=False."""
        mv_old  = _make_mv(h=7.0, cc=5)
        store   = _make_store({"api.py": [mv_old]})
        cf      = ChangedFile(path="api.py", change_type=CHANGE_DELETED)
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        result  = scanner.scan_changed_files([cf])
        delta   = result.file_deltas[0]
        assert delta.status_after    == "DELETED"
        assert delta.regression      is False
        assert delta.old_hamiltonian == 7.0

    def test_ti21_valid_python_returns_language(self, tmp_path):
        """TI21: valid Python content → scan_error=None, language contains 'python'."""
        cf      = ChangedFile(path="core.py", change_type=CHANGE_ADDED,
                              content=_COMPLEX_PY)
        scanner = IncrementalScanner(root=str(tmp_path))
        result  = scanner.scan_changed_files([cf])
        delta   = result.file_deltas[0]
        assert delta.scan_error is None
        assert "python" in delta.language.lower() or delta.language == "py"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 6 — IncrementalScanner._baseline()  (TI22–TI23)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseline:

    def test_ti22_no_store_returns_zeros_and_stable(self, tmp_path):
        """TI22: _baseline() without a store returns (0.0, 0, 'STABLE')."""
        scanner = IncrementalScanner(root=str(tmp_path), store=None)
        h, cc, status = scanner._baseline("anything.py")
        assert h      == 0.0
        assert cc     == 0
        assert status == "STABLE"

    def test_ti23_store_with_history_returns_last_values(self, tmp_path):
        """TI23: _baseline() reads hamiltonian, cc, status from last snapshot."""
        mv      = _make_mv(h=12.5, cc=7, status="WARNING")
        store   = _make_store({"src/auth.py": [mv]})
        scanner = IncrementalScanner(root=str(tmp_path), store=store)
        h, cc, status = scanner._baseline("src/auth.py")
        assert h      == 12.5
        assert cc     == 7
        assert status == "WARNING"


# ═══════════════════════════════════════════════════════════════════════════════
# Group 7 — IncrementalScanner._git_changed_files()  (TI24–TI26)
# ═══════════════════════════════════════════════════════════════════════════════

class TestGitChangedFiles:

    def test_ti24_non_git_dir_returns_empty_list(self, tmp_path):
        """TI24: non-git directory → _git_changed_files returns []."""
        result = IncrementalScanner._git_changed_files(tmp_path, "HEAD~1", "HEAD")
        assert result == []

    def test_ti25_parses_all_four_status_codes(self, tmp_path):
        """TI25: A/M/D/R outputs → ADDED/MODIFIED/DELETED/RENAMED ChangedFiles."""
        fake_stdout = (
            "A\tnew_file.py\n"
            "M\tmodified.py\n"
            "D\tdeleted.py\n"
            "R90\told_name.py\tnew_name.py\n"
        )
        with patch("subprocess.run") as mock_run:
            proc            = MagicMock()
            proc.returncode = 0
            proc.stdout     = fake_stdout
            mock_run.return_value = proc

            result = IncrementalScanner._git_changed_files(tmp_path, "HEAD~1", "HEAD")

        by_type = {cf.change_type: cf for cf in result}
        assert by_type[CHANGE_ADDED].path    == "new_file.py"
        assert by_type[CHANGE_MODIFIED].path == "modified.py"
        assert by_type[CHANGE_DELETED].path  == "deleted.py"
        assert by_type[CHANGE_RENAMED].path  == "new_name.py"
        assert by_type[CHANGE_RENAMED].old_path == "old_name.py"

    def test_ti26_timeout_returns_empty_list(self, tmp_path):
        """TI26: subprocess.TimeoutExpired → returns [] without raising."""
        with patch("subprocess.run",
                   side_effect=subprocess.TimeoutExpired("git", 30)):
            result = IncrementalScanner._git_changed_files(tmp_path, "HEAD~1", "HEAD")
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# Group 8 — handle_scan_incremental() REST  (TI27–TI30)
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleScanIncremental:
    """Integration tests for POST /scan-incremental handler."""

    def setup_method(self):
        self._orig_store = srv._store
        srv._store = _make_store({})

    def teardown_method(self):
        srv._store = self._orig_store

    def test_ti27_missing_files_key_returns_400(self):
        """TI27: body without 'files' → 400 with error message."""
        code, data = srv.handle_scan_incremental({})
        assert code == 400
        assert "error" in data

    def test_ti28_files_mode_returns_200_and_result_shape(self):
        """TI28: valid files mode → 200 with IncrementalScanResult dict."""
        body = {
            "files": [
                {
                    "path":        "src/auth.py",
                    "content":     _SIMPLE_PY,
                    "change_type": "ADDED",
                }
            ],
            "commit_hash": "test_commit",
            "base_commit": "baseline",
            "root":        str(_SENSOR_API),
        }
        code, data = srv.handle_scan_incremental(body)
        assert code == 200
        assert data["total_changed"] == 1
        assert data["added_count"]   == 1
        for key in ("scanned_count", "error_count", "regressions",
                    "new_criticals", "file_deltas"):
            assert key in data

    def test_ti29_git_diff_mode_delegates_correctly(self, tmp_path):
        """TI29: git_diff mode calls scan_git_diff and returns its to_dict()."""
        fake = IncrementalScanResult(
            total_changed=2, added_count=1, modified_count=1,
            deleted_count=0, renamed_count=0, scanned_count=2,
            error_count=0, regressions=0, new_criticals=0,
            file_deltas=[], commit_hash="HEAD", base_commit="HEAD~1",
            scan_duration_s=0.1,
        )
        with patch(
            "scan.incremental_scanner.IncrementalScanner.scan_git_diff",
            return_value=fake,
        ):
            code, data = srv.handle_scan_incremental({
                "mode":        "git_diff",
                "repo_path":   str(tmp_path),
                "base_commit": "HEAD~1",
                "head_commit": "HEAD",
            })
        assert code == 200
        assert data["total_changed"]  == 2
        assert data["added_count"]    == 1
        assert data["modified_count"] == 1

    def test_ti30_persist_false_passes_none_store(self, tmp_path):
        """TI30: persist=False → IncrementalScanner receives store=None."""
        captured: list = []
        _orig_init = IncrementalScanner.__init__

        def _spy_init(self_, root, store=None, commit_hash="HEAD"):
            captured.append(store)
            _orig_init(self_, root, store=store, commit_hash=commit_hash)

        body = {
            "files": [
                {
                    "path":        "x.py",
                    "content":     _SIMPLE_PY,
                    "change_type": "ADDED",
                }
            ],
            "persist": False,
            "root":    str(tmp_path),
        }

        with patch.object(IncrementalScanner, "__init__", _spy_init):
            code, data = srv.handle_scan_incremental(body)

        assert code == 200
        # store must be None when persist=False
        assert any(s is None for s in captured), (
            "Expected store=None when persist=False, got: " + str(captured)
        )
