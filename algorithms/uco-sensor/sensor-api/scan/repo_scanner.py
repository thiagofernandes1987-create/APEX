"""
UCO-Sensor — RepoScanner
==========================
Escaneia um repositório inteiro (ou subdiretório) e produz relatório
agregado de qualidade de código com os 9 canais UCO.

O que faz:
  1. Descobre todos os arquivos de código-fonte suportados
  2. Respeita .gitignore e padrões de exclusão customizados
  3. Analisa cada arquivo via UCOBridgeRegistry
  4. Persiste no SnapshotStore (histórico por módulo)
  5. Agrega métricas em ScanResult com top-N piores módulos
  6. Calcula score UCO global do projeto [0–100]

Uso direto:
    scanner = RepoScanner("/path/to/project")
    result  = scanner.scan()
    print(result.summary())

Uso com store persistente:
    store   = SnapshotStore("uco_sensor.db")
    scanner = RepoScanner("/path/to/project", store=store, commit_hash="abc123")
    result  = scanner.scan()
"""
from __future__ import annotations
import time
import sys
import fnmatch
from pathlib import Path
from typing import Optional, List, Dict, Set, Tuple, Any
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed

_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from core.data_structures import MetricVector
from lang_adapters.registry import get_registry


# ─── Tipos de resultado ───────────────────────────────────────────────────────

@dataclass
class FileScanResult:
    """Resultado da análise de um único arquivo."""
    path:       str              # path relativo à raiz do projeto
    language:   str
    status:     str              # STABLE | WARNING | CRITICAL
    loc:        int
    metrics: Dict[str, Any] = field(default_factory=dict)
    error:      Optional[str] = None
    scan_ms:    float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class ScanResult:
    """Resultado agregado do scan de um repositório."""
    root:           str
    commit_hash:    str
    timestamp:      float
    scan_duration_s: float

    files_found:    int = 0
    files_scanned:  int = 0
    files_skipped:  int = 0
    files_error:    int = 0

    # Contagens por status
    critical_count: int = 0
    warning_count:  int = 0
    stable_count:   int = 0

    # Médias globais dos 9 canais
    avg_hamiltonian:            float = 0.0
    avg_cyclomatic_complexity:  float = 0.0
    avg_infinite_loop_risk:     float = 0.0
    avg_dsm_density:            float = 0.0
    avg_dependency_instability: float = 0.0
    avg_halstead_bugs:          float = 0.0
    total_loc:      int = 0
    total_dead:     int = 0
    total_dups:     int = 0

    # Score global [0–100]: 100 = perfeito, 0 = catastrófico
    uco_score:      float = 100.0

    # Top-N módulos por gravidade
    top_critical:   List[FileScanResult] = field(default_factory=list)
    top_warning:    List[FileScanResult] = field(default_factory=list)

    # Breakdown por linguagem
    by_language:    Dict[str, int] = field(default_factory=dict)

    # Todos os resultados individuais
    file_results:   List[FileScanResult] = field(default_factory=list)

    # Status geral do projeto — baseado no UCO Score e ratio de arquivos críticos
    @property
    def project_status(self) -> str:
        n = max(1, self.files_scanned)
        critical_ratio = self.critical_count / n
        if self.uco_score < 50 or critical_ratio > 0.40:
            return "CRITICAL"
        if self.uco_score < 70 or critical_ratio > 0.20:
            return "WARNING"
        return "STABLE"

    def summary(self, top_n: int = 10) -> str:
        """Texto legível para CLI / logs."""
        lines = [
            f"╔{'═'*63}╗",
            f"║  UCO-Sensor Project Scan — {Path(self.root).name:<33}║",
            f"╠{'═'*63}╣",
            f"║  Status      : {self.project_status:<46}║",
            f"║  UCO Score   : {self.uco_score:.1f}/100{'':<40}║",
            f"║  Files       : {self.files_scanned} scanned / {self.files_found} found"
            f"  ({self.files_error} erros){'':>12}║",
            f"║  LOC total   : {self.total_loc:<46}║",
            f"╠{'═'*63}╣",
            f"║  CRITICAL : {self.critical_count:<5}  WARNING : {self.warning_count:<5}  STABLE : {self.stable_count:<11}║",
            f"║  H̄={self.avg_hamiltonian:.2f}  CC̄={self.avg_cyclomatic_complexity:.1f}"
            f"  ILR̄={self.avg_infinite_loop_risk:.3f}  bugs̄={self.avg_halstead_bugs:.3f}{'':>12}║",
            f"╠{'═'*63}╣",
        ]

        if self.top_critical:
            lines.append(f"║  Top CRITICAL files:{'':>42}║")
            for fr in self.top_critical[:top_n]:
                h   = fr.metrics.get("hamiltonian", 0)
                cc  = fr.metrics.get("cyclomatic_complexity", 0)
                rel = fr.path[-52:] if len(fr.path) > 52 else fr.path
                lines.append(f"║  🔴  {rel:<52}║")
                lines.append(f"║      H={h:.2f}  CC={cc}{'':>47}║")

        if self.top_warning and len(self.top_critical) < top_n:
            lines.append(f"║  Top WARNING files:{'':>43}║")
            for fr in self.top_warning[:max(0, top_n - len(self.top_critical))]:
                h   = fr.metrics.get("hamiltonian", 0)
                cc  = fr.metrics.get("cyclomatic_complexity", 0)
                rel = fr.path[-52:] if len(fr.path) > 52 else fr.path
                lines.append(f"║  🟡  {rel:<52}║")

        if self.by_language:
            lines.append(f"╠{'═'*63}╣")
            lang_str = "  ".join(f"{k}:{v}" for k, v in sorted(self.by_language.items()))
            lines.append(f"║  Linguagens: {lang_str:<49}║")

        lines.append(f"║  Duração: {self.scan_duration_s:.2f}s{'':>50}║")
        lines.append(f"╚{'═'*63}╝")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serializa para JSON."""
        return {
            "root":             self.root,
            "commit_hash":      self.commit_hash,
            "timestamp":        self.timestamp,
            "scan_duration_s":  round(self.scan_duration_s, 3),
            "project_status":   self.project_status,
            "uco_score":        round(self.uco_score, 2),
            "files": {
                "found":    self.files_found,
                "scanned":  self.files_scanned,
                "skipped":  self.files_skipped,
                "error":    self.files_error,
            },
            "status_counts": {
                "critical": self.critical_count,
                "warning":  self.warning_count,
                "stable":   self.stable_count,
            },
            "averages": {
                "hamiltonian":            round(self.avg_hamiltonian, 4),
                "cyclomatic_complexity":  round(self.avg_cyclomatic_complexity, 4),
                "infinite_loop_risk":     round(self.avg_infinite_loop_risk, 4),
                "dsm_density":            round(self.avg_dsm_density, 4),
                "dependency_instability": round(self.avg_dependency_instability, 4),
                "halstead_bugs":          round(self.avg_halstead_bugs, 4),
            },
            "totals": {
                "loc":  self.total_loc,
                "dead": self.total_dead,
                "dups": self.total_dups,
            },
            "by_language": self.by_language,
            "top_critical": [_fr_to_dict(f) for f in self.top_critical],
            "top_warning":  [_fr_to_dict(f) for f in self.top_warning],
            "file_results": [_fr_to_dict(f) for f in self.file_results],
        }


def _fr_to_dict(f: FileScanResult) -> Dict[str, Any]:
    return {
        "path":     f.path,
        "language": f.language,
        "status":   f.status,
        "loc":      f.loc,
        "metrics":  f.metrics,
        "error":    f.error,
        "scan_ms":  round(f.scan_ms, 1),
    }


# ─── RepoScanner ─────────────────────────────────────────────────────────────

# Extensões suportadas pelo UCOBridgeRegistry
_SUPPORTED_EXTENSIONS: Set[str] = {
    ".py", ".pyw", ".pyi",
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".java",
    ".go",
}

# Padrões de exclusão padrão (estilo .gitignore)
_DEFAULT_EXCLUDES = [
    "**/__pycache__/**",
    "**/*.pyc", "**/*.pyo",
    "**/node_modules/**",
    "**/vendor/**",
    "**/dist/**",
    "**/build/**",
    "**/.git/**",
    "**/.tox/**",
    "**/.venv/**",
    "**/venv/**",
    "**/env/**",
    "**/*.egg-info/**",
    "**/site-packages/**",
    "**/target/**",       # Java/Rust build
    "**/.gradle/**",
]

# Tamanho máximo de arquivo (evitar arquivos gerados gigantes)
_MAX_FILE_BYTES = 500_000   # 500 KB


class RepoScanner:
    """
    Escaneia um repositório e produz ScanResult agregado.

    Parâmetros
    ----------
    root         : Diretório raiz do projeto (absoluto ou relativo).
    commit_hash  : Hash do commit atual (default: "local").
    store        : SnapshotStore para persistência (opcional).
    max_workers  : Threads para análise paralela (default: 4).
    max_files    : Limite de arquivos (0 = sem limite).
    exclude      : Padrões glob adicionais de exclusão.
    include_tests: False → exclui arquivos em test*/ spec*/ __test__/ etc.
    top_n        : Número de top arquivos por gravidade no ScanResult.
    """

    def __init__(
        self,
        root: str,
        commit_hash: str = "local",
        store=None,
        max_workers: int = 4,
        max_files: int = 0,
        exclude: Optional[List[str]] = None,
        include_tests: bool = True,
        top_n: int = 20,
    ):
        self.root         = Path(root).resolve()
        self.commit_hash  = commit_hash
        self.store        = store
        self.max_workers  = max_workers
        self.max_files    = max_files
        self.top_n        = top_n
        self.include_tests = include_tests

        self._excludes = list(_DEFAULT_EXCLUDES)
        if exclude:
            self._excludes.extend(exclude)
        if not include_tests:
            self._excludes.extend([
                "**/test_*.py", "**/*_test.py",
                "**/tests/**", "**/spec/**",
                "**/__tests__/**",
            ])

        self._registry = get_registry()

    # ── Descoberta de arquivos ─────────────────────────────────────────────────

    def discover_files(self) -> List[Path]:
        """Descobre todos os arquivos suportados respeitando exclusões."""
        all_files: List[Path] = []

        # Ler .gitignore se existir
        gitignore_patterns = self._load_gitignore()

        for path in self.root.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
                continue
            if path.stat().st_size > _MAX_FILE_BYTES:
                continue

            rel = path.relative_to(self.root)
            rel_str = str(rel).replace("\\", "/")

            # Verificar padrões de exclusão
            if self._is_excluded(rel_str, gitignore_patterns):
                continue

            all_files.append(path)

            if self.max_files > 0 and len(all_files) >= self.max_files:
                break

        return sorted(all_files)

    def _load_gitignore(self) -> List[str]:
        """Carrega padrões do .gitignore se existir."""
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            return []
        patterns = []
        try:
            for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
        except Exception:
            pass
        return patterns

    def _is_excluded(self, rel_path: str, gitignore_patterns: List[str]) -> bool:
        """Verifica se um path relativo deve ser excluído."""
        for pattern in self._excludes + gitignore_patterns:
            # Normalizar padrão
            pat = pattern.lstrip("/")
            if fnmatch.fnmatch(rel_path, pat):
                return True
            # Verificar componentes do path
            parts = rel_path.split("/")
            for i in range(len(parts)):
                partial = "/".join(parts[:i+1])
                if fnmatch.fnmatch(partial, pat.rstrip("/**")):
                    return True
        return False

    # ── Análise de arquivo ─────────────────────────────────────────────────────

    def _scan_file(self, path: Path, timestamp: float) -> FileScanResult:
        """Analisa um único arquivo e retorna FileScanResult."""
        t0 = time.perf_counter()
        rel = str(path.relative_to(self.root)).replace("\\", "/")

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            if not source.strip():
                return FileScanResult(
                    path=rel, language="unknown", status="STABLE",
                    loc=0, scan_ms=(time.perf_counter() - t0) * 1000,
                )

            mv = self._registry.analyze(
                source=source,
                file_extension=path.suffix.lower(),
                module_id=rel,
                commit_hash=self.commit_hash,
                timestamp=timestamp,
            )

            # Persistir no store se fornecido
            if self.store is not None:
                try:
                    self.store.insert(mv)
                except Exception:
                    pass

            return FileScanResult(
                path=rel,
                language=getattr(mv, "language", "unknown"),
                status=mv.status,
                loc=getattr(mv, "lines_of_code", 0),
                metrics={
                    "hamiltonian":            mv.hamiltonian,
                    "cyclomatic_complexity":  mv.cyclomatic_complexity,
                    "infinite_loop_risk":     mv.infinite_loop_risk,
                    "dsm_density":            mv.dsm_density,
                    "dsm_cyclic_ratio":       mv.dsm_cyclic_ratio,
                    "dependency_instability": mv.dependency_instability,
                    "syntactic_dead_code":    mv.syntactic_dead_code,
                    "duplicate_block_count":  mv.duplicate_block_count,
                    "halstead_bugs":          mv.halstead_bugs,
                    "n_functions":            getattr(mv, "n_functions", 0),
                    "n_classes":              getattr(mv, "n_classes", 0),
                    "max_function_cc":        getattr(mv, "max_function_cc", 0),
                },
                scan_ms=(time.perf_counter() - t0) * 1000,
            )

        except Exception as exc:
            return FileScanResult(
                path=rel, language="unknown", status="STABLE",
                loc=0, error=str(exc),
                scan_ms=(time.perf_counter() - t0) * 1000,
            )

    # ── Scan principal ─────────────────────────────────────────────────────────

    def scan(self, verbose: bool = False) -> ScanResult:
        """
        Escaneia o repositório e retorna ScanResult agregado.

        Parâmetros
        ----------
        verbose : imprime progresso em tempo real.
        """
        t_start = time.perf_counter()
        ts      = time.time()

        files = self.discover_files()
        n_found = len(files)

        if verbose:
            print(f"[UCO-Sensor] Descobertos {n_found} arquivos em {self.root}")

        # Análise paralela
        file_results: List[FileScanResult] = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {pool.submit(self._scan_file, f, ts): f for f in files}
            done = 0
            for future in as_completed(futures):
                fr = future.result()
                file_results.append(fr)
                done += 1
                if verbose and done % 20 == 0:
                    print(f"[UCO-Sensor]   {done}/{n_found} arquivos analisados…")

        # Agregação
        result = self._aggregate(file_results, n_found, ts, time.perf_counter() - t_start)

        if verbose:
            print(f"[UCO-Sensor] Scan concluído em {result.scan_duration_s:.2f}s")

        return result

    # ── Agregação ─────────────────────────────────────────────────────────────

    def _aggregate(
        self,
        file_results: List[FileScanResult],
        n_found: int,
        timestamp: float,
        duration: float,
    ) -> ScanResult:
        """Agrega FileScanResult em ScanResult."""
        scanned  = [fr for fr in file_results if fr.ok]
        errored  = [fr for fr in file_results if not fr.ok]
        skipped  = n_found - len(file_results)

        critical = [fr for fr in scanned if fr.status == "CRITICAL"]
        warning  = [fr for fr in scanned if fr.status == "WARNING"]
        stable   = [fr for fr in scanned if fr.status == "STABLE"]

        # Ordenar por H descendente para top-N
        def _h(fr): return fr.metrics.get("hamiltonian", 0)
        top_crit = sorted(critical, key=_h, reverse=True)[:self.top_n]
        top_warn = sorted(warning,  key=_h, reverse=True)[:self.top_n]

        # Médias
        n = max(1, len(scanned))
        avg_h   = sum(fr.metrics.get("hamiltonian", 0)            for fr in scanned) / n
        avg_cc  = sum(fr.metrics.get("cyclomatic_complexity", 0)  for fr in scanned) / n
        avg_ilr = sum(fr.metrics.get("infinite_loop_risk", 0)     for fr in scanned) / n
        avg_dsm = sum(fr.metrics.get("dsm_density", 0)            for fr in scanned) / n
        avg_di  = sum(fr.metrics.get("dependency_instability", 0) for fr in scanned) / n
        avg_bug = sum(fr.metrics.get("halstead_bugs", 0)          for fr in scanned) / n
        total_loc  = sum(fr.loc for fr in scanned)
        total_dead = sum(fr.metrics.get("syntactic_dead_code", 0) for fr in scanned)
        total_dups = sum(fr.metrics.get("duplicate_block_count", 0) for fr in scanned)

        # Score UCO [0–100] — fórmula proporcional (escala com qualquer tamanho de repo)
        # Penalidades baseadas em RATIO para não colapsar em repos grandes:
        #   critical_ratio * 50  → até -50 se 100% crítico
        #   warning_ratio  * 20  → até -20 se 100% em aviso
        #   avg_H > 10           → -2 pts por unidade acima do threshold
        #   avg_CC > 15          → -1 pt por unidade acima do threshold
        #   avg_bugs > 1.0       → -5 pts por unidade acima de 1.0
        #   ILR > 0.5            → -10 pts fixo
        n_total        = max(1, len(scanned))
        critical_ratio = len(critical) / n_total
        warning_ratio  = len(warning)  / n_total

        score = 100.0
        score -= critical_ratio * 50.0
        score -= warning_ratio  * 20.0
        score -= max(0, avg_h   - 10.0) * 2.0
        score -= max(0, avg_cc  - 15.0) * 1.0
        score -= max(0, avg_bug -  1.0) * 5.0
        score -= (avg_ilr > 0.5) * 10.0
        score  = max(0.0, min(100.0, score))

        # By language
        by_lang: Dict[str, int] = {}
        for fr in scanned:
            by_lang[fr.language] = by_lang.get(fr.language, 0) + 1

        return ScanResult(
            root=str(self.root),
            commit_hash=self.commit_hash,
            timestamp=timestamp,
            scan_duration_s=duration,
            files_found=n_found,
            files_scanned=len(scanned),
            files_skipped=skipped,
            files_error=len(errored),
            critical_count=len(critical),
            warning_count=len(warning),
            stable_count=len(stable),
            avg_hamiltonian=avg_h,
            avg_cyclomatic_complexity=avg_cc,
            avg_infinite_loop_risk=avg_ilr,
            avg_dsm_density=avg_dsm,
            avg_dependency_instability=avg_di,
            avg_halstead_bugs=avg_bug,
            total_loc=total_loc,
            total_dead=total_dead,
            total_dups=total_dups,
            uco_score=score,
            top_critical=top_crit,
            top_warning=top_warn,
            by_language=by_lang,
            file_results=sorted(file_results, key=lambda f: f.path),
        )
