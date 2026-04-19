"""
UCO-Sensor — Git History Scanner
==================================
Extrai histórico real de commits de um repositório git e constrói uma
série temporal de MetricVectors por arquivo para alimentar o FrequencyEngine.

Pipeline:
  git log → commits →  git show hash:file → UCOBridge →
  MetricVector[]  →  FrequencyEngine  →  ClassificationResult

Diferencial vs SonarQube:
  Não apenas "você tem tech debt" — mas "seu tech debt COMEÇOU no commit
  abc123 (45 dias atrás), Hurst=0.96 indica que é irreversível sem
  refactoring ativo."

Uso:
  from scan.git_history_scanner import GitHistoryScanner
  scanner = GitHistoryScanner("/path/to/repo", n_commits=60)
  results = scanner.scan()
  for r in results:
      print(r.summary())
"""
from __future__ import annotations

import os
import sys
import time
import subprocess
import math
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.data_structures import MetricVector
from lang_adapters.registry import get_registry


# ─── Estruturas de dados ──────────────────────────────────────────────────────

@dataclass
class CommitInfo:
    hash:      str
    timestamp: float   # unix epoch
    date_str:  str     # ISO 8601
    subject:   str


@dataclass
class FileTemporalResult:
    """Resultado da análise temporal de um único arquivo."""
    path:               str
    language:           str
    n_commits:          int                       # commits com este arquivo
    history:            List[MetricVector]         # série temporal (por commit)
    classification:     Optional[object]   = None # ClassificationResult do FrequencyEngine
    error:              Optional[str]      = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.classification is not None

    @property
    def severity(self) -> str:
        if not self.ok:
            return "ERROR"
        return getattr(self.classification, "severity", "INFO")

    @property
    def primary_error(self) -> str:
        if not self.ok:
            return self.error or "UNKNOWN"
        return getattr(self.classification, "primary_error", "UNKNOWN_PATTERN")

    @property
    def onset_commit(self) -> Optional[str]:
        """Commit onde o onset foi detectado (se houver ChangePoint)."""
        if not self.ok:
            return None
        cp = getattr(self.classification, "change_point", None)
        if cp and self.history:
            idx = getattr(cp, "commit_idx", None)
            if idx is not None and 0 <= idx < len(self.history):
                return self.history[idx].commit_hash
        return None

    @property
    def hurst(self) -> float:
        if not self.ok:
            return 0.5
        return getattr(self.classification, "hurst_H", 0.5)

    @property
    def self_cure_probability(self) -> float:
        if not self.ok:
            return 1.0
        return getattr(self.classification, "self_cure_probability", 1.0)

    def summary(self) -> str:
        lines = [f"  {'─'*60}"]
        lines.append(f"  {self.path}")
        lines.append(f"  language={self.language}  commits={self.n_commits}  "
                     f"severity={self.severity}")
        if self.ok:
            lines.append(f"  pattern={self.primary_error}")
            lines.append(f"  hurst={self.hurst:.3f}  "
                         f"self_cure={self.self_cure_probability*100:.1f}%")
            if self.onset_commit:
                lines.append(f"  onset_commit={self.onset_commit[:12]}")
            conf = getattr(self.classification, "primary_confidence", 0.0)
            lines.append(f"  confidence={conf:.2f}")
        else:
            lines.append(f"  error={self.error}")
        return "\n".join(lines)


@dataclass
class GitHistoryScanResult:
    """Resultado agregado do scan histórico de um repositório."""
    repo_path:       str
    n_commits:       int
    n_files:         int                           # arquivos com histórico suficiente
    file_results:    List[FileTemporalResult] = field(default_factory=list)
    elapsed_s:       float = 0.0

    @property
    def critical_files(self) -> List[FileTemporalResult]:
        return [r for r in self.file_results if r.severity == "CRITICAL"]

    @property
    def warning_files(self) -> List[FileTemporalResult]:
        return [r for r in self.file_results if r.severity == "WARNING"]

    @property
    def stable_files(self) -> List[FileTemporalResult]:
        return [r for r in self.file_results
                if r.severity in ("INFO", "STABLE") and r.ok]

    @property
    def project_status(self) -> str:
        if self.critical_files:
            return "CRITICAL"
        if self.warning_files:
            return "WARNING"
        return "STABLE"

    def summary(self, top_n: int = 10) -> str:
        lines = []
        lines.append(f"\n{'═'*65}")
        lines.append(f"  UCO-Sensor — Análise Temporal")
        lines.append(f"{'═'*65}")
        lines.append(f"  Repositório : {self.repo_path}")
        lines.append(f"  Commits     : {self.n_commits}")
        lines.append(f"  Arquivos    : {self.n_files}")
        lines.append(f"  Status      : {self.project_status}")
        lines.append(f"  Tempo       : {self.elapsed_s:.1f}s")
        lines.append(f"")

        if self.critical_files:
            lines.append(f"  🔴 CRITICAL ({len(self.critical_files)} arquivos):")
            for r in self.critical_files[:top_n]:
                onset = f" ← onset: {r.onset_commit[:12]}" if r.onset_commit else ""
                lines.append(f"    • {r.path}")
                lines.append(f"      {r.primary_error}  hurst={r.hurst:.3f}"
                              f"  cure={r.self_cure_probability*100:.0f}%{onset}")

        if self.warning_files:
            lines.append(f"\n  🟡 WARNING ({len(self.warning_files)} arquivos):")
            for r in self.warning_files[:top_n]:
                lines.append(f"    • {r.path}  [{r.primary_error}]")

        lines.append(f"\n{'═'*65}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "repo_path":      self.repo_path,
            "n_commits":      self.n_commits,
            "n_files":        self.n_files,
            "project_status": self.project_status,
            "elapsed_s":      self.elapsed_s,
            "critical":       len(self.critical_files),
            "warning":        len(self.warning_files),
            "stable":         len(self.stable_files),
            "file_results": [
                {
                    "path":              r.path,
                    "language":          r.language,
                    "n_commits":         r.n_commits,
                    "severity":          r.severity,
                    "primary_error":     r.primary_error,
                    "hurst":             r.hurst,
                    "self_cure_pct":     round(r.self_cure_probability * 100, 1),
                    "onset_commit":      r.onset_commit,
                    "confidence": (
                        round(getattr(r.classification, "primary_confidence", 0), 3)
                        if r.ok else 0
                    ),
                }
                for r in self.file_results
            ],
        }


# ─── GitHistoryScanner ────────────────────────────────────────────────────────

class GitHistoryScanner:
    """
    Escaneia o histórico git de um repositório, analisando a evolução
    temporal dos arquivos de código.

    Args:
        root:         Caminho do repositório git local
        n_commits:    Número máximo de commits a analisar (default: 60)
        min_commits:  Mínimo de commits por arquivo para rodar o FrequencyEngine (default: 5)
        extensions:   Extensões a analisar (default: .py .js .ts .java .go)
        max_files:    Máximo de arquivos a analisar (0 = sem limite)
        max_workers:  Threads de análise paralela
        verbose:      Imprimir progresso
    """

    DEFAULT_EXTENSIONS = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go"}

    def __init__(
        self,
        root: str,
        n_commits:   int = 60,
        min_commits: int = 5,
        extensions:  Optional[set] = None,
        max_files:   int = 0,
        max_workers: int = 4,
        verbose:     bool = False,
        commit_hash: Optional[str] = None,
    ):
        self.root        = Path(root).resolve()
        self.n_commits   = n_commits
        self.min_commits = min_commits
        self.extensions  = extensions or self.DEFAULT_EXTENSIONS
        self.max_files   = max_files
        self.max_workers = max_workers
        self.verbose     = verbose
        self.commit_hash = commit_hash
        self._registry   = get_registry()

    # ── Git helpers ───────────────────────────────────────────────────────────

    def _git(self, *args, check: bool = True) -> str:
        """Executa um comando git e retorna stdout."""
        result = subprocess.run(
            ["git", "-C", str(self.root)] + list(args),
            capture_output=True, text=True, timeout=60,
        )
        if check and result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip()}")
        return result.stdout

    def _get_commits(self) -> List[CommitInfo]:
        """Retorna os últimos N commits do repositório."""
        log = self._git(
            "log", f"-{self.n_commits}",
            "--format=%H|%ai|%s",
            "--no-merges",
        )
        commits = []
        for line in log.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("|", 2)
            if len(parts) < 3:
                continue
            h, date_str, subject = parts
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(date_str.strip().replace(" ", "T").rsplit("+", 1)[0])
                ts = dt.timestamp()
            except Exception:
                ts = time.time()
            commits.append(CommitInfo(
                hash=h.strip(), timestamp=ts,
                date_str=date_str.strip(), subject=subject.strip(),
            ))
        return list(reversed(commits))  # mais antigo → mais recente

    def _get_file_at_commit(self, commit_hash: str, file_path: str) -> Optional[str]:
        """Retorna o conteúdo de um arquivo em um commit específico."""
        try:
            result = subprocess.run(
                ["git", "-C", str(self.root), "show", f"{commit_hash}:{file_path}"],
                capture_output=True, timeout=15,
            )
            if result.returncode != 0:
                return None
            return result.stdout.decode("utf-8", errors="replace")
        except Exception:
            return None

    def _files_touched_by_commits(self, commits: List[CommitInfo]) -> Dict[str, List[int]]:
        """
        Retorna {filepath: [commit_indices]} para arquivos relevantes.
        Usa `git diff-tree` para cada commit.
        """
        file_commits: Dict[str, List[int]] = {}

        for idx, commit in enumerate(commits):
            try:
                out = self._git(
                    "diff-tree", "--no-commit-id", "-r", "--name-only", commit.hash,
                    check=False,
                )
                for line in out.strip().splitlines():
                    fp = line.strip()
                    if not fp:
                        continue
                    ext = Path(fp).suffix.lower()
                    if ext not in self.extensions:
                        continue
                    # Excluir arquivos de teste e gerados
                    if any(x in fp for x in ["test_", "_test.", "spec.", ".min.", "vendor/",
                                              "node_modules/", ".pb.", "generated"]):
                        continue
                    file_commits.setdefault(fp, []).append(idx)
            except Exception:
                continue

        return file_commits

    # ── Análise temporal por arquivo ─────────────────────────────────────────

    def _analyze_file_history(
        self,
        file_path: str,
        commit_indices: List[int],
        commits: List[CommitInfo],
    ) -> FileTemporalResult:
        """
        Extrai e analisa a série temporal de um arquivo.
        Retorna FileTemporalResult com classificação do FrequencyEngine.
        """
        from pipeline.frequency_engine import FrequencyEngine

        ext      = Path(file_path).suffix.lower()
        language = self._registry.language_for(ext) or "unknown"
        history: List[MetricVector] = []

        # Coleta MetricVectors por commit
        for idx in commit_indices:
            commit = commits[idx]
            source = self._get_file_at_commit(commit.hash, file_path)
            if source is None or len(source.strip()) == 0:
                continue
            try:
                mv = self._registry.analyze(
                    source=source,
                    file_extension=ext,
                    module_id=file_path,
                    commit_hash=commit.hash,
                    timestamp=commit.timestamp,
                )
                history.append(mv)
            except Exception:
                continue

        if len(history) < self.min_commits:
            return FileTemporalResult(
                path=file_path, language=language,
                n_commits=len(history), history=history,
                error=f"insufficient_history ({len(history)} < {self.min_commits})",
            )

        # FrequencyEngine — classificação temporal
        try:
            engine = FrequencyEngine(verbose=False)
            result = engine.analyze(history, module_id=file_path)
            return FileTemporalResult(
                path=file_path, language=language,
                n_commits=len(history), history=history,
                classification=result,
            )
        except Exception as e:
            return FileTemporalResult(
                path=file_path, language=language,
                n_commits=len(history), history=history,
                error=f"engine_error: {e}",
            )

    # ── Scan principal ────────────────────────────────────────────────────────

    def scan(self, verbose: Optional[bool] = None) -> GitHistoryScanResult:
        """
        Executa o scan temporal completo do repositório.
        Retorna GitHistoryScanResult com análise por arquivo.
        """
        if verbose is None:
            verbose = self.verbose

        t0 = time.perf_counter()

        # 1. Listar commits
        if verbose:
            print(f"  Lendo commits (últimos {self.n_commits})...", flush=True)
        try:
            commits = self._get_commits()
        except RuntimeError as e:
            raise RuntimeError(f"Não é um repositório git válido: {self.root}\n{e}")

        if verbose:
            print(f"  {len(commits)} commits encontrados")

        if not commits:
            return GitHistoryScanResult(
                repo_path=str(self.root), n_commits=0,
                n_files=0, elapsed_s=time.perf_counter() - t0,
            )

        # 2. Arquivos tocados pelos commits
        if verbose:
            print(f"  Mapeando arquivos modificados...", flush=True)
        file_commits = self._files_touched_by_commits(commits)

        # Filtrar arquivos com commits suficientes
        eligible = {
            fp: idxs
            for fp, idxs in file_commits.items()
            if len(idxs) >= self.min_commits
        }

        if self.max_files and len(eligible) > self.max_files:
            # Prioriza arquivos com mais commits (mais signal)
            eligible = dict(
                sorted(eligible.items(), key=lambda x: len(x[1]), reverse=True)[:self.max_files]
            )

        if verbose:
            print(f"  {len(eligible)} arquivos com ≥ {self.min_commits} commits")

        if not eligible:
            return GitHistoryScanResult(
                repo_path=str(self.root), n_commits=len(commits),
                n_files=0, elapsed_s=time.perf_counter() - t0,
            )

        # 3. Análise temporal paralela
        file_results: List[FileTemporalResult] = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {
                pool.submit(
                    self._analyze_file_history, fp, idxs, commits
                ): fp
                for fp, idxs in eligible.items()
            }
            done = 0
            for future in as_completed(futures):
                fp = futures[future]
                done += 1
                try:
                    result = future.result()
                    file_results.append(result)
                    if verbose:
                        icon = ("🔴" if result.severity == "CRITICAL"
                                else "🟡" if result.severity == "WARNING"
                                else "🟢" if result.ok
                                else "⚪")
                        print(f"  [{done:>3}/{len(eligible)}] {icon} {fp:<50} "
                              f"n={result.n_commits}", flush=True)
                except Exception as e:
                    if verbose:
                        print(f"  [{done:>3}/{len(eligible)}] ✗ {fp}: {e}", flush=True)

        # Ordenar: CRITICAL primeiro, depois por hurst decrescente
        file_results.sort(
            key=lambda r: (
                0 if r.severity == "CRITICAL" else 1 if r.severity == "WARNING" else 2,
                -r.hurst,
            )
        )

        elapsed = time.perf_counter() - t0

        return GitHistoryScanResult(
            repo_path=str(self.root),
            n_commits=len(commits),
            n_files=len(eligible),
            file_results=file_results,
            elapsed_s=elapsed,
        )
