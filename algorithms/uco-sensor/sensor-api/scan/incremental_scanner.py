"""
UCO-Sensor — IncrementalScanner  (M6.1)
=========================================
Scans ONLY the files that changed between two states (commits or explicit
file list), producing per-file metric deltas against the stored baseline.

Key differentiator from SonarQube:
  SonarQube incremental analysis is **enterprise-only**.  UCO-Sensor delivers
  it free, with Hamiltonian delta tracking and regression detection baked in.

Classes
-------
ChangedFile
    A file that changed: path, change_type, optional old_path for renames.
FileDelta
    Metrics comparison (before vs after) for a single changed file.
IncrementalScanResult
    Aggregated result: regressions, new criticals, per-file deltas.
IncrementalScanner
    Orchestrator with two entry points:
      scan_files(paths, ...)    — explicit file list (no git required)
      scan_git_diff(repo, ...) — derives changed files from git diff

Usage
-----
    # Explicit file list (e.g. from CI webhook payload)
    scanner = IncrementalScanner("/repo", store=store, commit_hash="abc123")
    result  = scanner.scan_files(["src/auth.py", "src/api.py"])
    print(result.summary())

    # Git diff between two commits
    result = scanner.scan_git_diff("/repo", base="HEAD~1", head="HEAD")
    for delta in result.regressions_list():
        print(delta.path, delta.delta_h)
"""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys as _sys
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

from lang_adapters.registry import get_registry as _get_registry

_SUPPORTED_EXT = {
    # ── Python ────────────────────────────────────────────────────────────────
    ".py", ".pyw", ".pyi",
    # ── JavaScript / TypeScript ───────────────────────────────────────────────
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    # ── Java ──────────────────────────────────────────────────────────────────
    ".java",
    # ── Go ────────────────────────────────────────────────────────────────────
    ".go",
    # ── C / C++ / Objective-C  (M6.2) ────────────────────────────────────────
    ".c", ".h",
    ".cpp", ".cc", ".cxx", ".hpp", ".hxx", ".h++", ".c++", ".cp", ".inl",
    ".m", ".mm",
    # ── C# (M6.2) ─────────────────────────────────────────────────────────────
    ".cs",
    # ── Rust (M6.2) ───────────────────────────────────────────────────────────
    ".rs",
    # ── Ruby (M6.2) ───────────────────────────────────────────────────────────
    ".rb", ".rake", ".gemspec", ".ru", ".rbw",
    # ── Swift (M6.2) ──────────────────────────────────────────────────────────
    ".swift",
    # ── Kotlin (M6.2) ─────────────────────────────────────────────────────────
    ".kt", ".kts",
    # ── PHP (M6.2) ────────────────────────────────────────────────────────────
    ".php", ".php3", ".php4", ".php5", ".php7", ".phps", ".phtml",
    # ── Scala / Groovy (M6.2) ─────────────────────────────────────────────────
    ".scala", ".sc", ".sbt",
    ".groovy", ".gradle", ".gvy", ".gy",
    # ── Scripting languages (M6.2) ────────────────────────────────────────────
    ".r", ".R", ".rmd", ".Rmd", ".rscript",
    ".sh", ".bash", ".zsh", ".ksh", ".fish", ".command",
    ".ps1", ".psm1", ".psd1", ".pssc",
    ".lua",
    ".pl", ".pm", ".t", ".cgi", ".plx",
    ".matlab", ".octave",
    # ── Functional languages (M6.2) ───────────────────────────────────────────
    ".hs", ".lhs",
    ".erl", ".hrl",
    ".ex", ".exs",
    ".fs", ".fsx", ".fsi",
    ".ml", ".mli",
    ".clj", ".cljs", ".cljc", ".edn",
    # ── Modern systems languages (M6.2) ───────────────────────────────────────
    ".dart",
    ".jl",
    ".zig",
    ".nim", ".nims",
    ".cr",
    ".d", ".di",
    # ── Domain / legacy / IaC languages (M6.2) ───────────────────────────────
    ".vb",
    ".asm", ".s", ".S", ".nasm", ".nas",
    ".cob", ".cbl", ".cpy", ".cobol",
    ".f", ".for", ".f77", ".f90", ".f95", ".f03", ".f08",
    ".tcl", ".tk", ".tclsh",
    ".sol",
    ".hcl", ".tf", ".tfvars",
}

# ── ChangedFile ───────────────────────────────────────────────────────────────

CHANGE_ADDED    = "ADDED"
CHANGE_MODIFIED = "MODIFIED"
CHANGE_DELETED  = "DELETED"
CHANGE_RENAMED  = "RENAMED"


@dataclass
class ChangedFile:
    """
    Represents a single file that changed between two states.

    Attributes
    ----------
    path        : relative path of the file in the new state
    change_type : ADDED | MODIFIED | DELETED | RENAMED
    old_path    : previous path (only for RENAMED)
    content     : new source content (None for DELETED)
    """
    path:        str
    change_type: str
    old_path:    Optional[str] = None
    content:     Optional[str] = None


# ── FileDelta ─────────────────────────────────────────────────────────────────

@dataclass
class FileDelta:
    """
    Metric comparison for a single changed file.

    ``old_*`` values come from the most recent SnapshotStore baseline.
    ``new_*`` values come from fresh analysis of the current content.
    Both are 0 / "STABLE" for ADDED files (no prior baseline).
    DELETED files have new_hamiltonian=0 and new_status="DELETED".

    Attributes
    ----------
    path            : relative file path
    change_type     : ADDED | MODIFIED | DELETED | RENAMED
    language        : detected language
    old_hamiltonian : prior H (from store baseline, 0 if ADDED)
    new_hamiltonian : new H (from scan, 0 if DELETED)
    delta_h         : new_hamiltonian - old_hamiltonian
    old_cc          : prior cyclomatic complexity
    new_cc          : new cyclomatic complexity
    delta_cc        : new_cc - old_cc
    status_before   : STABLE | WARNING | CRITICAL (prior)
    status_after    : STABLE | WARNING | CRITICAL | DELETED (new)
    regression      : True when quality got measurably worse
    scan_error      : error message if analysis failed
    """
    path:            str
    change_type:     str
    language:        str        = "unknown"
    old_hamiltonian: float      = 0.0
    new_hamiltonian: float      = 0.0
    delta_h:         float      = 0.0
    old_cc:          int        = 0
    new_cc:          int        = 0
    delta_cc:        int        = 0
    status_before:   str        = "STABLE"
    status_after:    str        = "STABLE"
    regression:      bool       = False
    scan_error:      Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path":            self.path,
            "change_type":     self.change_type,
            "language":        self.language,
            "old_hamiltonian": round(self.old_hamiltonian, 4),
            "new_hamiltonian": round(self.new_hamiltonian, 4),
            "delta_h":         round(self.delta_h, 4),
            "old_cc":          self.old_cc,
            "new_cc":          self.new_cc,
            "delta_cc":        self.delta_cc,
            "status_before":   self.status_before,
            "status_after":    self.status_after,
            "regression":      self.regression,
            "scan_error":      self.scan_error,
        }


# ── IncrementalScanResult ─────────────────────────────────────────────────────

@dataclass
class IncrementalScanResult:
    """
    Aggregated result of an incremental scan pass.

    Attributes
    ----------
    total_changed   : total files in the changed set
    added_count     : ADDED files
    modified_count  : MODIFIED files
    deleted_count   : DELETED files
    renamed_count   : RENAMED files
    scanned_count   : files actually analysed (non-DELETED)
    error_count     : files that failed analysis
    regressions     : files whose quality got worse
    new_criticals   : files newly at CRITICAL status
    file_deltas     : per-file FileDelta list
    commit_hash     : head commit for this scan
    base_commit     : base commit (or "baseline")
    scan_duration_s : wall-clock time
    """
    total_changed:   int
    added_count:     int
    modified_count:  int
    deleted_count:   int
    renamed_count:   int
    scanned_count:   int
    error_count:     int
    regressions:     int
    new_criticals:   int
    file_deltas:     List[FileDelta]
    commit_hash:     str   = "HEAD"
    base_commit:     str   = "baseline"
    scan_duration_s: float = 0.0

    def regressions_list(self) -> List[FileDelta]:
        """Return only the FileDelta entries that are regressions."""
        return [d for d in self.file_deltas if d.regression]

    def new_criticals_list(self) -> List[FileDelta]:
        """Return FileDelta entries that are newly CRITICAL."""
        return [
            d for d in self.file_deltas
            if d.status_after == "CRITICAL" and d.status_before != "CRITICAL"
        ]

    def summary(self) -> str:
        lines = [
            f"Incremental Scan: {self.total_changed} changed file(s) "
            f"[+{self.added_count} ~{self.modified_count} -{self.deleted_count}]",
            f"Scanned: {self.scanned_count} | Errors: {self.error_count} | "
            f"Regressions: {self.regressions} | New CRITICAL: {self.new_criticals}",
            f"Duration: {self.scan_duration_s:.3f}s",
        ]
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_changed":   self.total_changed,
            "added_count":     self.added_count,
            "modified_count":  self.modified_count,
            "deleted_count":   self.deleted_count,
            "renamed_count":   self.renamed_count,
            "scanned_count":   self.scanned_count,
            "error_count":     self.error_count,
            "regressions":     self.regressions,
            "new_criticals":   self.new_criticals,
            "file_deltas":     [d.to_dict() for d in self.file_deltas],
            "commit_hash":     self.commit_hash,
            "base_commit":     self.base_commit,
            "scan_duration_s": round(self.scan_duration_s, 3),
        }


# ── IncrementalScanner ────────────────────────────────────────────────────────

class IncrementalScanner:
    """
    Scans only the changed files and computes metric deltas.

    Parameters
    ----------
    root        : Project root directory (absolute path string).
    store       : SnapshotStore for reading prior baselines (optional).
    commit_hash : Commit hash to tag new snapshots with.
    """

    def __init__(
        self,
        root:        str,
        store:       Any   = None,   # SnapshotStore | None
        commit_hash: str   = "HEAD",
    ) -> None:
        self.root        = Path(root).resolve()
        self.store       = store
        self.commit_hash = commit_hash
        self._registry   = _get_registry()

    # ── Public: explicit file list ────────────────────────────────────────────

    def scan_files(
        self,
        paths:       List[str],
        commit_hash: Optional[str] = None,
        base_commit: str           = "baseline",
    ) -> IncrementalScanResult:
        """
        Scan an explicit list of file paths (relative to root).

        Files are read from disk.  For DELETED files, pass them as ChangedFile
        objects instead; this method auto-detects missing files as DELETED.

        Parameters
        ----------
        paths       : list of relative file paths to scan
        commit_hash : override for this scan's commit hash
        base_commit : label for the baseline (informational)

        Returns
        -------
        IncrementalScanResult
        """
        changed: List[ChangedFile] = []
        for rel in paths:
            abs_path = self.root / rel
            if not abs_path.exists():
                changed.append(ChangedFile(path=rel, change_type=CHANGE_DELETED))
                continue
            try:
                content = abs_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
            # Determine change type based on store history
            ct = CHANGE_ADDED
            if self.store is not None:
                history = self.store.get_history(rel, window=1)
                if history:
                    ct = CHANGE_MODIFIED
            changed.append(ChangedFile(path=rel, change_type=ct, content=content))

        return self._process(changed, commit_hash or self.commit_hash, base_commit)

    def scan_changed_files(
        self,
        changed_files: List[ChangedFile],
        commit_hash:   Optional[str] = None,
        base_commit:   str           = "baseline",
    ) -> IncrementalScanResult:
        """
        Scan a pre-built list of ChangedFile objects.

        Useful when the caller already knows change types (e.g. from a CI
        webhook payload or git diff parser).
        """
        return self._process(
            changed_files,
            commit_hash or self.commit_hash,
            base_commit,
        )

    def scan_git_diff(
        self,
        repo_path:   Optional[str] = None,
        base_commit: str           = "HEAD~1",
        head_commit: str           = "HEAD",
    ) -> IncrementalScanResult:
        """
        Derive changed files from ``git diff --name-status`` and scan them.

        File content is read from the filesystem (HEAD state).
        Falls back to empty result on git errors (e.g. no git repo).

        Parameters
        ----------
        repo_path   : git repo directory (defaults to self.root)
        base_commit : base commit ref (e.g. "HEAD~1", "main", "abc123")
        head_commit : head commit ref (e.g. "HEAD", "feature-branch")
        """
        repo = Path(repo_path).resolve() if repo_path else self.root
        changed = self._git_changed_files(repo, base_commit, head_commit)
        return self._process(changed, head_commit, base_commit)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _process(
        self,
        changed_files: List[ChangedFile],
        commit_hash:   str,
        base_commit:   str,
    ) -> IncrementalScanResult:
        """Core: analyse each ChangedFile and build IncrementalScanResult."""
        t0     = time.perf_counter()
        deltas: List[FileDelta] = []

        for cf in changed_files:
            delta = self._analyse_one(cf, commit_hash)
            deltas.append(delta)

        elapsed = time.perf_counter() - t0

        added    = sum(1 for d in deltas if d.change_type == CHANGE_ADDED)
        modified = sum(1 for d in deltas if d.change_type == CHANGE_MODIFIED)
        deleted  = sum(1 for d in deltas if d.change_type == CHANGE_DELETED)
        renamed  = sum(1 for d in deltas if d.change_type == CHANGE_RENAMED)
        errors   = sum(1 for d in deltas if d.scan_error is not None)
        regressions  = sum(1 for d in deltas if d.regression)
        new_crit = sum(
            1 for d in deltas
            if d.status_after == "CRITICAL" and d.status_before != "CRITICAL"
        )

        return IncrementalScanResult(
            total_changed=len(deltas),
            added_count=added,
            modified_count=modified,
            deleted_count=deleted,
            renamed_count=renamed,
            scanned_count=len(deltas) - deleted - errors,
            error_count=errors,
            regressions=regressions,
            new_criticals=new_crit,
            file_deltas=deltas,
            commit_hash=commit_hash,
            base_commit=base_commit,
            scan_duration_s=elapsed,
        )

    def _analyse_one(self, cf: ChangedFile, commit_hash: str) -> FileDelta:
        """Analyse a single ChangedFile and return its FileDelta."""
        ext = Path(cf.path).suffix.lower()

        # ── DELETED — no new scan, just record removal ────────────────────────
        if cf.change_type == CHANGE_DELETED:
            old_h, old_cc, old_status = self._baseline(cf.path)
            return FileDelta(
                path=cf.path,
                change_type=CHANGE_DELETED,
                language="unknown",
                old_hamiltonian=old_h,
                new_hamiltonian=0.0,
                delta_h=-old_h,
                old_cc=old_cc,
                new_cc=0,
                delta_cc=-old_cc,
                status_before=old_status,
                status_after="DELETED",
                regression=False,   # deletion is not a regression
            )

        # ── Unsupported extension — skip ──────────────────────────────────────
        if ext not in _SUPPORTED_EXT:
            return FileDelta(
                path=cf.path,
                change_type=cf.change_type,
                scan_error=f"Unsupported extension: {ext}",
            )

        # ── Read content ──────────────────────────────────────────────────────
        content = cf.content
        if content is None:
            abs_p = self.root / cf.path
            try:
                content = abs_p.read_text(encoding="utf-8", errors="replace")
            except Exception as exc:
                return FileDelta(
                    path=cf.path,
                    change_type=cf.change_type,
                    scan_error=str(exc),
                )

        if not content.strip():
            return FileDelta(
                path=cf.path,
                change_type=cf.change_type,
                language="unknown",
            )

        # ── Analyse ───────────────────────────────────────────────────────────
        try:
            mv = self._registry.analyze(
                source=content,
                file_extension=ext,
                module_id=cf.path,
                commit_hash=commit_hash,
                timestamp=time.time(),
            )
        except Exception as exc:
            old_h, old_cc, old_status = self._baseline(cf.path)
            return FileDelta(
                path=cf.path,
                change_type=cf.change_type,
                old_hamiltonian=old_h,
                old_cc=old_cc,
                status_before=old_status,
                scan_error=str(exc),
            )

        # ── Persist new snapshot ──────────────────────────────────────────────
        if self.store is not None:
            try:
                self.store.insert(mv)
            except Exception:
                pass

        # ── Compare with baseline ─────────────────────────────────────────────
        old_h, old_cc, old_status = self._baseline(cf.path)
        new_h    = float(mv.hamiltonian)
        new_cc   = int(mv.cyclomatic_complexity)
        new_stat = getattr(mv, "status", "STABLE")
        lang     = getattr(mv, "language", ext.lstrip(".") or "unknown")

        delta_h  = new_h - old_h
        delta_cc = new_cc - old_cc

        # Regression: H increased > 5% or new status is worse
        _STATUS_RANK = {"STABLE": 0, "WARNING": 1, "CRITICAL": 2, "DELETED": 3}
        old_rank = _STATUS_RANK.get(old_status, 0)
        new_rank = _STATUS_RANK.get(new_stat, 0)
        regression = (delta_h > max(0.5, old_h * 0.05)) or (new_rank > old_rank)

        return FileDelta(
            path=cf.path,
            change_type=cf.change_type,
            language=lang,
            old_hamiltonian=old_h,
            new_hamiltonian=new_h,
            delta_h=round(delta_h, 4),
            old_cc=old_cc,
            new_cc=new_cc,
            delta_cc=delta_cc,
            status_before=old_status,
            status_after=new_stat,
            regression=regression,
        )

    def _baseline(self, path: str):
        """
        Retrieve last known metrics for a module from the store.

        Returns (hamiltonian, cc, status) — zeros/STABLE if no history.
        """
        if self.store is None:
            return 0.0, 0, "STABLE"
        history = self.store.get_history(path, window=1)
        if not history:
            return 0.0, 0, "STABLE"
        last = history[-1]
        return (
            float(last.hamiltonian),
            int(last.cyclomatic_complexity),
            getattr(last, "status", "STABLE"),
        )

    # ── Git diff helper ───────────────────────────────────────────────────────

    @staticmethod
    def _git_changed_files(
        repo:        Path,
        base_commit: str,
        head_commit: str,
    ) -> List[ChangedFile]:
        """
        Run ``git diff --name-status`` and return ChangedFile list.

        Returns [] on any git error.
        """
        try:
            proc = subprocess.run(
                ["git", "diff", "--name-status", base_commit, head_commit],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=30,
            )
            if proc.returncode != 0:
                return []
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []

        changed: List[ChangedFile] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if not parts:
                continue
            status = parts[0].upper()
            if status.startswith("R") and len(parts) >= 3:
                # Renamed: R<similarity>  old_path  new_path
                changed.append(ChangedFile(
                    path=parts[2],
                    change_type=CHANGE_RENAMED,
                    old_path=parts[1],
                ))
            elif status == "A" and len(parts) >= 2:
                changed.append(ChangedFile(path=parts[1], change_type=CHANGE_ADDED))
            elif status == "M" and len(parts) >= 2:
                changed.append(ChangedFile(path=parts[1], change_type=CHANGE_MODIFIED))
            elif status == "D" and len(parts) >= 2:
                changed.append(ChangedFile(path=parts[1], change_type=CHANGE_DELETED))

        return changed
