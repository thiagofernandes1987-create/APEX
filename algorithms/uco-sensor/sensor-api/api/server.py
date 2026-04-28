"""
UCO-Sensor API — HTTP Server
==============================
UCOSensorHandler: servidor HTTP leve para a API REST do UCO-Sensor.

Endpoints:
  GET  /health              — liveness probe
  GET  /docs                — auto-documentação dos endpoints
  POST /analyze             — analisa código (multi-linguagem) + classifica
  GET  /modules             — lista módulos conhecidos no store
  GET  /history?module=     — histórico de snapshots de um módulo
  POST /repair              — analisa + sugere transforms + retorna código otimizado
  GET  /baseline?module=    — estatísticas de baseline do módulo
  POST /analyze-pr          — analisa diff de PR (retorna SARIF + sumário)

  Auth + Billing:
  POST /auth/keys           — cria nova API key  [admin]
  GET  /auth/keys           — lista chaves       [admin]
  DELETE /auth/keys/<prefix>— revoga chave       [admin]
  GET  /usage               — uso da chave corrente

Design:
  • stdlib pura — sem Flask/FastAPI/aiohttp (zero dependências extras)
  • BaseHTTPRequestHandler com dispatcher por método+path
  • Auth middleware: header X-UCO-API-Key ou query param api_key
  • Thread-safe via SnapshotStore lock interno
  • Envelope de resposta padronizado: {"status": "ok"|"error", "data": {...}}

Uso:
  python server.py --port 8080
  Sem auth: python server.py --no-auth   (desabilita validação de key)
"""
from __future__ import annotations
import os
import sys
import json
import time
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, Optional, Tuple, List
from dataclasses import dataclass
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
_API_DIR    = Path(__file__).resolve().parent
_SENSOR_DIR = _API_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sensor_core.uco_bridge import UCOBridge
from sensor_storage.snapshot_store import SnapshotStore
from pipeline.frequency_engine import FrequencyEngine
from router.signal_output_router import SignalOutputRouter, OutputFormat
from lang_adapters.registry import get_registry
from apex_integration.connector import ApexConnector, get_connector
from scan.repo_scanner import RepoScanner
from report.html_report import generate_html_report
from report.badge import generate_badge_svg, generate_status_badge_svg
from apex_integration.templates import get_template, render_prompt, fix_action_for, all_error_types
from sast.scanner import scan as sast_scan, RULES as SAST_RULES
from governance.policy_engine import (
    evaluate_policy, load_default_policy, policy_from_dict, mv_to_metrics_dict,
)
from governance.trend_engine import (
    analyze_trend, analyze_module_trends, track_debt_budget,
    trend_summary, overall_trend,
)
from report.sarif import SARIFBuilder
from report.webui import generate_dashboard_html
from sensor_core.auto_analyzer import AutoAnalyzer
from scan.incremental_scanner import (
    IncrementalScanner, ChangedFile,
    CHANGE_ADDED, CHANGE_MODIFIED, CHANGE_DELETED, CHANGE_RENAMED,
)
from sca.vulnerability_scanner import VulnerabilityScanner
from iac.iac_scanner import IaCScanner

# M7.0 — DiagnosticVector (FrequencyEngine persistence signals)
try:
    from metrics.extended_vectors import DiagnosticVector as _DiagnosticVector
    _DIAGNOSTIC_VECTOR_AVAILABLE = True
except ImportError:
    _DIAGNOSTIC_VECTOR_AVAILABLE = False

# M7.3 — ReliabilityVector + MaintainabilityVector
try:
    from metrics.extended_vectors import (
        ReliabilityVector  as _ReliabilityVector,
        MaintainabilityVector as _MaintainabilityVector,
    )
    _RELIABILITY_VECTOR_AVAILABLE     = True
    _MAINTAINABILITY_VECTOR_AVAILABLE = True
except ImportError:
    _ReliabilityVector                = None  # type: ignore[assignment,misc]
    _MaintainabilityVector            = None  # type: ignore[assignment,misc]
    _RELIABILITY_VECTOR_AVAILABLE     = False
    _MAINTAINABILITY_VECTOR_AVAILABLE = False

# M7.2 — TaintAnalyzer + FlowVector
try:
    from sast.taint_engine import TaintAnalyzer as _TaintAnalyzer
    from metrics.extended_vectors import FlowVector as _FlowVector
    _TAINT_ENGINE_AVAILABLE = True
except ImportError:
    _TaintAnalyzer  = None  # type: ignore[assignment,misc]
    _FlowVector     = None  # type: ignore[assignment,misc]
    _TAINT_ENGINE_AVAILABLE = False

# M7.4 — PerformanceAnalyzer + PerformanceVector
try:
    from metrics.performance_analyzer import PerformanceAnalyzer as _PerformanceAnalyzer
    from metrics.extended_vectors import PerformanceVector as _PerformanceVector
    _PERFORMANCE_AVAILABLE = True
except ImportError:
    _PerformanceAnalyzer = None  # type: ignore[assignment,misc]
    _PerformanceVector   = None  # type: ignore[assignment,misc]
    _PERFORMANCE_AVAILABLE = False


# ─── Configuração ────────────────────────────────────────────────────────────

@dataclass
class SensorConfig:
    db_path:      str   = ":memory:"
    engine_mode:  str   = "fast"
    verbose:      bool  = False
    max_history:  int   = 100
    version:      str   = "2.8.0"
    # BUG-05: auth was False by default — any unprotected server was open.
    # Now reads UCO_AUTH_ENABLED env var; set UCO_NO_AUTH=1 ONLY for dev/tests.
    auth_enabled: bool  = False   # overridden by env var below
    admin_key:    str   = ""      # key do admin para /auth/keys
    apex_enabled: bool  = False   # True → integração APEX ativa


# ─── Singletons globais ──────────────────────────────────────────────────────

_config = SensorConfig(
    # BUG-05: resolve from env at startup so production containers are
    # always authenticated even if the code default wasn't changed.
    auth_enabled=os.environ.get("UCO_AUTH_ENABLED", "0").lower() in ("1", "true", "yes"),
    admin_key=os.environ.get("UCO_ADMIN_KEY", ""),
    apex_enabled=os.environ.get("UCO_APEX_ENABLED", "0").lower() in ("1", "true", "yes"),
)
_store     = SnapshotStore(_config.db_path)
_bridge    = UCOBridge(mode=_config.engine_mode)
_engine    = FrequencyEngine(verbose=_config.verbose)
_router    = SignalOutputRouter()
_connector = get_connector()        # ApexConnector — null mode até configurado via env


# ─── Auth middleware ─────────────────────────────────────────────────────────

def _extract_api_key(headers: Any, params: Dict) -> str:
    """Extrai API key do header X-UCO-API-Key ou query param api_key."""
    key = headers.get("X-UCO-API-Key", "") or headers.get("x-uco-api-key", "")
    if not key:
        key = params.get("api_key", [""])[0]
    return key.strip()


def _authenticate(plain_key: str, require_admin: bool = False) -> Tuple[bool, Optional[Dict]]:
    """
    Valida a API key.

    Retorna (True, info_dict) se válido, (False, None) caso contrário.
    Se auth_enabled=False, sempre aceita (modo dev).
    """
    if not _config.auth_enabled:
        return True, {"key_prefix": "dev", "name": "dev_mode", "calls_total": 0}

    if require_admin:
        # Admin endpoint: usa variável de ambiente UCO_ADMIN_KEY
        admin_k = _config.admin_key or os.environ.get("UCO_ADMIN_KEY", "")
        if admin_k and plain_key == admin_k:
            return True, {"key_prefix": "admin", "name": "admin"}
        return False, None

    info = _store.validate_key(plain_key)
    if info is None:
        return False, None
    return True, info


# ─── Handlers de endpoint ────────────────────────────────────────────────────

def handle_health() -> Tuple[int, Dict]:
    return 200, {
        "status":          "healthy",
        "version":         _config.version,
        "timestamp":       time.time(),
        "modules_tracked": len(_store.list_modules()),
        "auth_enabled":    _config.auth_enabled,
        "languages":       get_registry().supported_languages(),
    }


def handle_docs() -> Tuple[int, Dict]:
    """GET /docs — autodocumentação."""
    return 200, {
        "name":    "UCO-Sensor API",
        "version": _config.version,
        "endpoints": [
            {"method": "GET",    "path": "/health",        "auth": False,  "desc": "Liveness probe"},
            {"method": "GET",    "path": "/docs",          "auth": False,  "desc": "Esta documentação"},
            {"method": "POST",   "path": "/analyze",       "auth": True,   "desc": "Analisa código (multi-linguagem)"},
            {"method": "POST",   "path": "/repair",        "auth": True,   "desc": "Sugere e aplica transformações UCO"},
            {"method": "POST",   "path": "/analyze-pr",    "auth": True,   "desc": "Analisa diff de PR (SARIF output)"},
            {"method": "POST",   "path": "/scan-repo",     "auth": True,   "desc": "Escaneia repositório inteiro (batch)"},
            {"method": "GET",    "path": "/modules",       "auth": True,   "desc": "Lista módulos rastreados"},
            {"method": "GET",    "path": "/history",       "auth": True,   "desc": "Histórico de snapshots"},
            {"method": "GET",    "path": "/baseline",      "auth": True,   "desc": "Baseline e z-scores"},
            {"method": "GET",    "path": "/usage",         "auth": True,   "desc": "Uso da chave corrente"},
            {"method": "GET",    "path": "/anomalies",     "auth": True,   "desc": "Anomalias detectadas"},
            {"method": "POST",   "path": "/auth/keys",     "auth": "admin","desc": "Cria API key"},
            {"method": "GET",    "path": "/auth/keys",     "auth": "admin","desc": "Lista API keys"},
            {"method": "DELETE", "path": "/auth/keys",     "auth": "admin","desc": "Revoga API key (?prefix=)"},
            {"method": "GET",    "path": "/apex/status",   "auth": True,   "desc": "Status integração APEX"},
            {"method": "GET",    "path": "/apex/ping",     "auth": True,   "desc": "Teste conectividade APEX"},
            {"method": "POST",   "path": "/apex/webhook",  "auth": True,   "desc": "Recebe eventos do APEX (bidirecional)"},
            {"method": "GET",    "path": "/report",        "auth": True,   "desc": "Relatório HTML standalone (?module=)"},
            {"method": "GET",    "path": "/badge",         "auth": False,  "desc": "Badge SVG (?score=87&status=STABLE ou ?module=)"},
            {"method": "POST",   "path": "/diff",          "auth": True,   "desc": "Diff UCO entre 2 commits (before/after)"},
            {"method": "POST",   "path": "/apex/fix",      "auth": True,   "desc": "Fix bidirecional: APEX envia comando corretivo"},
            {"method": "GET",    "path": "/predict",          "auth": True,   "desc": "Degradation forecast para um módulo (?module=&horizon=)"},
            {"method": "GET",    "path": "/predict/all",      "auth": True,   "desc": "Fleet forecast — todos os módulos, ordenado por risco"},
            {"method": "POST",   "path": "/scan-incremental", "auth": True,   "desc": "Incremental scan — apenas arquivos alterados (M6.1)"},
            {"method": "POST",   "path": "/scan-sca",         "auth": True,   "desc": "SCA dependency vulnerability scan — 9 ecosystems, 65+ CVEs (M6.3)"},
            {"method": "POST",   "path": "/scan-iac",         "auth": True,   "desc": "IaC misconfiguration scan — Dockerfile/Compose/k8s/Terraform/Helm (M6.4)"},
            {"method": "GET",    "path": "/metrics/advanced",        "auth": True,   "desc": "AdvancedVector + DiagnosticVector — persisted M7.0 extended signals (?module=)"},
            {"method": "GET",    "path": "/metrics/reliability",     "auth": True,   "desc": "ReliabilityVector — 10-channel reliability posture for a module (?module=) [M7.3a]"},
            {"method": "GET",    "path": "/metrics/maintainability", "auth": True,   "desc": "MaintainabilityVector — 9-channel maintainability posture for a module (?module=) [M7.3b]"},
            {"method": "POST",   "path": "/scan-flow",               "auth": True,   "desc": "Taint analysis DFA — source→sink flows, FlowVector, SAST findings (M7.2)"},
            {"method": "GET",    "path": "/metrics/flow",            "auth": True,   "desc": "FlowVector — 6-channel taint/data-flow posture for a module (?module=) [M7.2]"},
            {"method": "POST",   "path": "/scan-performance",        "auth": True,   "desc": "Performance anti-pattern analysis — 8 channels, PerformanceVector (M7.4)"},
            {"method": "GET",    "path": "/metrics/performance",     "auth": True,   "desc": "PerformanceVector — 8-channel performance posture for a module (?module=) [M7.4]"},
            {"method": "GET",    "path": "/lsp/diagnostics",         "auth": True,   "desc": "LSP-format diagnostics (publishDiagnostics) from stored vectors (?module=) [M8.1]"},
        ],
        "analyze_body": {
            "code":           "string — código fonte",
            "module_id":      "string — identificador do módulo",
            "commit_hash":    "string — hash do commit",
            "file_extension": "string — extensão (.py|.js|.ts|.java|.go) default .py",
            "timestamp":      "float  — unix timestamp opcional",
        },
        "supported_languages": get_registry().supported_languages(),
    }


def handle_analyze(data: Dict) -> Tuple[int, Dict]:
    """
    POST /analyze
    Body: {"code": str, "module_id": str, "commit_hash": str,
           "file_extension"?: str, "timestamp"?: float}

    Suporta Python, JS, TS, Java, Go via UCOBridgeRegistry.
    """
    code        = data.get("code", "")
    module_id   = data.get("module_id", "unknown")
    commit_hash = data.get("commit_hash", f"auto_{int(time.time())}")
    timestamp   = float(data.get("timestamp", time.time()))
    file_ext    = data.get("file_extension", data.get("language", ".py"))
    # Normalizar extensão
    if not file_ext.startswith("."):
        file_ext = f".{file_ext}"

    if not code.strip():
        return 400, {"error": "code is required and cannot be empty"}

    # Analisar via registry (multi-linguagem)
    registry = get_registry()
    mv = registry.analyze(
        source=code,
        file_extension=file_ext,
        module_id=module_id,
        commit_hash=commit_hash,
        timestamp=timestamp,
    )

    # Persistir no store
    _store.insert(mv)

    # Classificação espectral (se houver histórico suficiente)
    classification = None
    history = _store.get_history(module_id, window=_config.max_history)
    apex_event_sent = False
    if len(history) >= 5:
        result = _engine.analyze(history, module_id=module_id)
        if result:
            classification = {
                "primary_error":     result.primary_error,
                "severity":          result.severity,
                "confidence":        round(result.primary_confidence, 4),
                "dominant_band":     result.dominant_band,
                "plain_english":     result.plain_english,
                "spectral_evidence": result.spectral_evidence,
                # M7.0 persistence signals
                "hurst_H":               round(getattr(result, "hurst_H", 0.5), 4),
                "burst_index_H":         round(getattr(result, "burst_index_H", 0.0), 4),
                "phase_coupling_CC_H":   round(getattr(result, "phase_coupling_CC_H", 0.0), 4),
                "onset_reversibility":   round(getattr(result, "onset_reversibility", 0.5), 4),
                "self_cure_probability": round(getattr(result, "self_cure_probability", 0.0), 4),
            }
            # ── M7.0: persist DiagnosticVector into the most-recent snapshot ──
            if _DIAGNOSTIC_VECTOR_AVAILABLE:
                try:
                    dv = _DiagnosticVector.from_classification_result(
                        result,
                        module_id=module_id,
                        n_snapshots=len(history),
                    )
                    dv_json = __import__("json").dumps(dv.to_dict(), default=str)
                    _store.update_diagnostic(
                        module_id=module_id,
                        commit_hash=mv.commit_hash,
                        diagnostic_json=dv_json,
                    )
                except Exception:
                    pass   # DiagnosticVector never breaks the main flow
            # ── Marco 3: publicar evento APEX se severity=CRITICAL ───────────
            try:
                delivery = _connector.handle(result, store=_store)
                apex_event_sent = delivery is not None and delivery.ok
            except Exception:
                pass   # APEX nunca quebra o fluxo principal

    # SAST scan (Python only, non-blocking)
    sast_result = None
    try:
        sast_result = sast_scan(code, file_extension=file_ext)
    except Exception:
        pass

    return 200, {
        "sast": sast_result.to_dict() if sast_result else None,
        "metric_vector": {
            "module_id":              mv.module_id,
            "commit_hash":            mv.commit_hash,
            "timestamp":              mv.timestamp,
            "language":               getattr(mv, "language", "unknown"),
            "lines_of_code":          getattr(mv, "lines_of_code", 0),
            "hamiltonian":            mv.hamiltonian,
            "cyclomatic_complexity":  mv.cyclomatic_complexity,
            "infinite_loop_risk":     mv.infinite_loop_risk,
            "dsm_density":            mv.dsm_density,
            "dsm_cyclic_ratio":       mv.dsm_cyclic_ratio,
            "dependency_instability": mv.dependency_instability,
            "syntactic_dead_code":    mv.syntactic_dead_code,
            "duplicate_block_count":  mv.duplicate_block_count,
            "halstead_bugs":          mv.halstead_bugs,
            "status":                 mv.status,
            # M1 advanced metrics (present when language=python and mode=full)
            "cognitive_complexity":   getattr(mv, "cognitive_complexity", None),
            "cognitive_fn_max":       getattr(mv, "cognitive_fn_max", None),
            "sqale_debt_minutes":     getattr(mv, "sqale_debt_minutes", None),
            "sqale_ratio":            getattr(mv, "sqale_ratio", None),
            "sqale_rating":           getattr(mv, "sqale_rating", None),
            "clone_count":            getattr(mv, "clone_count", None),
            "ratings":                getattr(mv, "ratings", None),
            "function_profiles":      getattr(mv, "function_profiles", None),
        },
        "classification":  classification,
        "history_size":    len(history),
        "apex_event_sent": apex_event_sent,
    }


def handle_modules() -> Tuple[int, Dict]:
    modules = _store.list_modules()
    return 200, {"modules": modules, "count": len(modules)}


def handle_history(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    if not module_id:
        return 400, {"error": "module parameter is required"}
    history = _store.get_history(module_id, window=window)
    return 200, {
        "module_id": module_id,
        "snapshots": [
            {
                "commit_hash": mv.commit_hash,
                "timestamp":   mv.timestamp,
                "hamiltonian": mv.hamiltonian,
                "cc":          mv.cyclomatic_complexity,
                "language":    getattr(mv, "language", "python"),
                "status":      mv.status,
            }
            for mv in history
        ],
        "count": len(history),
    }


def handle_baseline(module_id: Optional[str]) -> Tuple[int, Dict]:
    if not module_id:
        return 400, {"error": "module parameter is required"}
    baseline = _store.get_baseline(module_id)
    if baseline is None:
        return 404, {"error": f"No baseline for '{module_id}' (need ≥ 3 snapshots)"}
    return 200, {
        "module_id": module_id,
        "n_samples": baseline.n_samples,
        "h_mean":    round(baseline.h_mean, 4),
        "h_std":     round(baseline.h_std, 4),
        "h_trend":   round(baseline.h_trend_slope, 6),
        "cc_mean":   round(baseline.cc_mean, 4),
        "di_mean":   round(baseline.di_mean, 4),
    }


def handle_repair(data: Dict) -> Tuple[int, Dict]:
    """
    POST /repair — análise + transforms UCO.
    """
    code      = data.get("code", "")
    module_id = data.get("module_id", "repair.anonymous")
    depth     = data.get("depth", "fast")
    file_ext  = data.get("file_extension", ".py")
    if not file_ext.startswith("."):
        file_ext = f".{file_ext}"

    if not code.strip():
        return 400, {"error": "code is required and cannot be empty"}

    # Repair só suporta Python (UCOBridge tem transforms)
    bridge_local = UCOBridge(mode=depth)
    mv_before = bridge_local.analyze(code, module_id, "repair_before")
    sugg      = bridge_local.suggest_transforms(code, module_id, "repair_suggest")
    optimized = sugg.get("optimized_code", code)
    mv_after  = bridge_local.analyze(optimized, module_id, "repair_after")

    delta_h = mv_before.hamiltonian - mv_after.hamiltonian
    return 200, {
        "h_before":       round(mv_before.hamiltonian, 4),
        "h_after":        round(mv_after.hamiltonian, 4),
        "delta_h":        round(delta_h, 4),
        "optimized_code": optimized,
        "transforms":     sugg.get("transforms", []),
        "metrics_before": {
            "hamiltonian": mv_before.hamiltonian,
            "cc":          mv_before.cyclomatic_complexity,
            "dead":        mv_before.syntactic_dead_code,
            "dups":        mv_before.duplicate_block_count,
            "ilr":         mv_before.infinite_loop_risk,
        },
        "metrics_after": {
            "hamiltonian": mv_after.hamiltonian,
            "cc":          mv_after.cyclomatic_complexity,
            "dead":        mv_after.syntactic_dead_code,
            "dups":        mv_after.duplicate_block_count,
            "ilr":         mv_after.infinite_loop_risk,
        },
    }


def handle_analyze_pr(data: Dict) -> Tuple[int, Dict]:
    """
    POST /analyze-pr

    Analisa um pull request como lista de arquivos modificados.
    Retorna sumário UCO + saída SARIF para upload em GitHub Actions.

    Body:
    {
      "files": [
        {"path": "src/auth.py", "content": "...", "commit_hash": "abc123"},
        ...
      ],
      "pr_number":   42,
      "repo":        "owner/repo",
      "base_branch": "main"
    }
    """
    files    = data.get("files", [])
    pr_num   = data.get("pr_number", 0)
    repo     = data.get("repo", "unknown/repo")
    base_ref = data.get("base_branch", "main")

    if not files:
        return 400, {"error": "files list is required and cannot be empty"}

    registry = get_registry()
    results:       List[Dict] = []
    critical_count = 0
    warning_count  = 0
    sarif_builder  = SARIFBuilder(
        tool_version=_config.version,
        repo=repo,
    )

    for f in files:
        path    = f.get("path", "unknown")
        content = f.get("content", "")
        chash   = f.get("commit_hash", f"pr_{pr_num}")
        ext     = Path(path).suffix or ".py"

        if not content.strip():
            continue

        mv = registry.analyze(
            source=content,
            file_extension=ext,
            module_id=path,
            commit_hash=chash,
        )
        _store.insert(mv)

        result = {
            "path":     path,
            "language": getattr(mv, "language", "unknown"),
            "status":   mv.status,
            "metrics": {
                "hamiltonian":            mv.hamiltonian,
                "cyclomatic_complexity":  mv.cyclomatic_complexity,
                "infinite_loop_risk":     mv.infinite_loop_risk,
                "duplicate_block_count":  mv.duplicate_block_count,
                "syntactic_dead_code":    mv.syntactic_dead_code,
                "halstead_bugs":          mv.halstead_bugs,
            },
        }
        results.append(result)

        if mv.status == "CRITICAL":
            critical_count += 1
        elif mv.status == "WARNING":
            warning_count += 1

        # SARIF — use SARIFBuilder for rich line/col + SAST integration
        if mv.status != "STABLE":
            h  = mv.hamiltonian
            cc = mv.cyclomatic_complexity
            sarif_builder.add_uco_finding(
                file_uri=path,
                rule_id="UCO001",
                message=(
                    f"UCO {mv.status}: H={h:.2f}, CC={cc}, "
                    f"ILR={mv.infinite_loop_risk:.2f}, bugs={mv.halstead_bugs:.2f}"
                ),
                severity=mv.status,
                line=1,
            )
        # SAST scan inline per file (Python only, non-blocking)
        if content.strip() and path.endswith(".py"):
            try:
                sast_file = sast_scan(content, file_extension=".py")
                sarif_builder.add_sast_findings(path, sast_file)
            except Exception:
                pass
        # Function-level UCO findings from profiles
        fps = getattr(mv, "function_profiles", None) or []
        if fps:
            sarif_builder.add_uco_findings_from_profiles(path, fps)

    sarif_output = sarif_builder.build()

    pr_status = "CRITICAL" if critical_count > 0 else ("WARNING" if warning_count > 0 else "STABLE")
    return 200, {
        "pr_number":      pr_num,
        "repo":           repo,
        "base_branch":    base_ref,
        "files_analyzed": len(results),
        "pr_status":      pr_status,
        "critical_files": critical_count,
        "warning_files":  warning_count,
        "file_results":   results,
        "sarif":          sarif_output,
    }


# ─── Scan Repository ─────────────────────────────────────────────────────────

def handle_scan_repo(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-repo

    Escaneia um diretório local e retorna relatório UCO agregado.

    Body:
    {
      "path":          "/abs/path/to/project",   # obrigatório
      "commit_hash":   "abc123",                 # opcional
      "max_files":     500,                      # opcional (0 = sem limite)
      "include_tests": true,                     # opcional
      "exclude":       ["**/migrations/**"],     # opcional
      "persist":       true,                     # salvar no SnapshotStore?
      "top_n":         20                        # top arquivos no resultado
    }
    """
    root = data.get("path", "")
    if not root:
        return 400, {"error": "path is required"}

    from pathlib import Path as _Path
    root_path = _Path(root)
    if not root_path.exists() or not root_path.is_dir():
        return 400, {"error": f"Path '{root}' não existe ou não é um diretório"}

    commit_hash  = data.get("commit_hash", f"scan_{int(time.time())}")
    max_files    = int(data.get("max_files", 0))
    include_tests = bool(data.get("include_tests", True))
    exclude      = data.get("exclude", [])
    persist      = bool(data.get("persist", True))
    top_n        = int(data.get("top_n", 20))

    store_ref = _store if persist else None

    try:
        scanner = RepoScanner(
            root=root,
            commit_hash=commit_hash,
            store=store_ref,
            max_files=max_files,
            include_tests=include_tests,
            exclude=exclude,
            top_n=top_n,
            max_workers=4,
        )
        result = scanner.scan()
    except Exception as exc:
        return 500, {"error": f"Scan failed: {exc}"}

    return 200, result.to_dict()


# ─── APEX endpoints ──────────────────────────────────────────────────────────

def handle_apex_fix(data: Dict) -> Tuple[int, Dict]:
    """
    POST /apex/fix
    Recebe uma solicitação de fix do APEX e aplica transforms UCO no código.

    Body:
      {
        "module_id":     str,
        "code":          str,          — código a corrigir
        "error_type":    str,          — TECH_DEBT_ACCUMULATION | AI_CODE_BOMB | ...
        "transforms":    [str],        — opcional (override do template)
        "commit_hash":   str,          — opcional
        "file_extension": str,         — opcional (default ".py")
        "hurst":         float,        — opcional (para prompt contextual)
        "onset_commit":  str,          — opcional
      }

    Retorna:
      {
        "original_code", "fixed_code",
        "h_before", "h_after", "delta_h",
        "transforms_applied", "apex_prompt",
        "template", "success": bool
      }
    """
    module_id  = data.get("module_id", "unknown.module")
    code       = data.get("code", "")
    error_type = data.get("error_type", "UNKNOWN")
    file_ext   = data.get("file_extension", ".py")
    commit     = data.get("commit_hash", "unknown")
    hurst      = float(data.get("hurst", 0.0))
    onset      = data.get("onset_commit", commit)

    if not code.strip():
        return 400, {"error": "'code' é obrigatório e não pode ser vazio"}

    if not file_ext.startswith("."):
        file_ext = f".{file_ext}"

    # Obter template para o tipo de erro
    template   = get_template(error_type)
    transforms = data.get("transforms") or template["transforms"]

    # Analisar código original
    mv_before = _bridge.analyze(code, module_id, commit)
    h_before  = mv_before.hamiltonian
    cc_before = mv_before.cyclomatic_complexity

    # Aplicar transforms via UCOBridge
    sugg = _bridge.suggest_transforms(code)
    fixed_code = sugg.get("optimized_code", code)

    # Se o suggest_transforms não melhorou, tentar aplicar transforms específicos
    if fixed_code == code and "remove_dead_code" in transforms:
        # Fallback: tentar limpeza básica via bridge
        sugg2 = _bridge.suggest_transforms(code)
        fixed_code = sugg2.get("optimized_code", code)

    # Analisar código corrigido
    mv_after  = _bridge.analyze(fixed_code, module_id, f"{commit}_fixed")
    h_after   = mv_after.hamiltonian
    delta_h   = h_after - h_before
    improved  = delta_h <= 0 or abs(delta_h) < 0.01  # melhorou ou igual

    # Identificar transforms realmente aplicados (comparando métricas)
    transforms_applied: List[str] = []
    if mv_after.syntactic_dead_code < mv_before.syntactic_dead_code:
        transforms_applied.append("remove_dead_code")
    if mv_after.duplicate_block_count < mv_before.duplicate_block_count:
        transforms_applied.append("remove_duplicate_blocks")
    if mv_after.cyclomatic_complexity < mv_before.cyclomatic_complexity:
        transforms_applied.append("simplify_logic")
    if mv_after.hamiltonian < mv_before.hamiltonian - 0.1:
        transforms_applied.append("reduce_complexity")
    if not transforms_applied:
        transforms_applied = ["no_change_needed"] if improved else ["attempted"]

    # Renderizar prompt APEX contextualizado
    apex_prompt = render_prompt(
        error_type=error_type,
        module_id=module_id,
        delta_h=delta_h,
        hurst=hurst,
        commit=onset,
        cc=cc_before,
        delta_cc=mv_after.cyclomatic_complexity - cc_before,
        dsm_density=mv_before.dsm_density,
        dsm_cyclic=mv_before.dsm_cyclic_ratio,
        ilr=mv_before.infinite_loop_risk,
        dead=mv_before.syntactic_dead_code,
        halstead=mv_before.halstead_bugs,
    )

    return 200, {
        "module_id":          module_id,
        "error_type":         error_type,
        "original_code":      code,
        "fixed_code":         fixed_code,
        "h_before":           round(h_before, 4),
        "h_after":            round(h_after,  4),
        "delta_h":            round(delta_h,  4),
        "cc_before":          cc_before,
        "cc_after":           mv_after.cyclomatic_complexity,
        "transforms_applied": transforms_applied,
        "transforms_template": template["transforms"],
        "apex_prompt":        apex_prompt,
        "apex_mode":          template["mode"],
        "apex_agents":        template["agents"],
        "success":            improved,
        "success_criteria":   template["success_criteria"],
        "intervention_now":   template["intervention_now"],
        "template_used":      error_type if error_type in all_error_types() else "UNKNOWN",
        "summary": (
            f"{'OK' if improved else 'PARCIAL'}: "
            f"H {h_before:.2f} -> {h_after:.2f} "
            f"(delta={delta_h:+.2f}) | "
            f"transforms={transforms_applied}"
        ),
    }


def handle_apex_status() -> Tuple[int, Dict]:
    """GET /apex/status — status da integração APEX."""
    status = _connector.status()
    return 200, status


def handle_apex_ping() -> Tuple[int, Dict]:
    """GET /apex/ping — testa conectividade com o APEX."""
    ok = _connector.ping()
    return 200, {
        "reachable":  ok,
        "transport":  _connector.bus.transport_mode,
        "configured": _connector.bus.is_configured,
    }


# SEC-04: thread-local depth counter prevents recursive APEX event processing.
_MAX_WEBHOOK_DEPTH = 3
_webhook_depth     = threading.local()


def handle_apex_webhook(data: Dict) -> Tuple[int, Dict]:
    """
    POST /apex/webhook — recebe eventos do APEX (handshake bidirecional).

    Permite que o APEX envie comandos de volta para o UCO Sensor,
    como "rescan module X" ou "lower severity gate".

    SEC-04: profundidade máxima de processamento aninhado = 3.
    Um APEX_FIX_REQUEST que dispara outro webhook não pode ultrapassar esse limite.
    """
    # SEC-04: guard against deeply-nested event chains
    depth = getattr(_webhook_depth, "n", 0)
    if depth >= _MAX_WEBHOOK_DEPTH:
        return 400, {"error": f"APEX webhook depth limit ({_MAX_WEBHOOK_DEPTH}) exceeded"}
    _webhook_depth.n = depth + 1
    try:
        return _handle_apex_webhook_impl(data)
    finally:
        _webhook_depth.n = depth


def _handle_apex_webhook_impl(data: Dict) -> Tuple[int, Dict]:
    event_type = data.get("event", "")
    payload    = data.get("payload", {})

    if event_type == "APEX_RESCAN_REQUEST":
        module_id = payload.get("module_id", "")
        if module_id:
            history = _store.get_history(module_id, window=_config.max_history)
            return 200, {
                "ack": True,
                "module_id": module_id,
                "snapshots_available": len(history),
            }

    if event_type == "APEX_PING":
        return 200, {"ack": True, "version": _config.version}

    if event_type == "APEX_FIX_REQUEST":
        # APEX solicita correção inline de um módulo
        fix_data = {
            "module_id":  payload.get("module_id", ""),
            "code":       payload.get("code", ""),
            "error_type": payload.get("error_type", "UNKNOWN"),
            "transforms": payload.get("transforms"),
            "commit_hash": payload.get("commit_hash", ""),
            "hurst":      payload.get("hurst", 0.0),
            "onset_commit": payload.get("onset_commit", ""),
        }
        if fix_data["code"]:
            fix_code, fix_result = handle_apex_fix(fix_data)
            return 200, {"ack": True, "fix_result": fix_result}
        return 200, {"ack": True, "note": "APEX_FIX_REQUEST sem código — ignorado"}

    if event_type == "APEX_TEMPLATE_REQUEST":
        # APEX solicita lista de templates disponíveis
        error_t = payload.get("error_type")
        if error_t:
            from apex_integration.templates import get_template
            tmpl = get_template(error_t)
            return 200, {"ack": True, "template": tmpl}
        from apex_integration.templates import all_error_types
        return 200, {"ack": True, "error_types": all_error_types()}

    return 200, {"ack": True, "event_received": event_type}


def handle_diff(data: Dict) -> Tuple[int, Dict]:
    """
    POST /diff
    Body:
      {
        "before": {"code": str, "module_id": str, "commit_hash": str,
                   "file_extension"?: str},
        "after":  {"code": str, "module_id": str, "commit_hash": str,
                   "file_extension"?: str},
        "persist"?: bool   (default False — diff não salva no store)
      }

    Retorna delta dos 9 canais UCO entre before e after, flag de regressão,
    e sugestões de transforms quando há piora.
    """
    before = data.get("before", {})
    after  = data.get("after",  {})
    persist = bool(data.get("persist", False))

    code_b = before.get("code", "")
    code_a = after.get("code",  "")
    if not code_b or not code_a:
        return 400, {"error": "'before.code' e 'after.code' são obrigatórios"}

    module_b  = before.get("module_id",   "diff.before")
    module_a  = after.get("module_id",    "diff.after")
    hash_b    = before.get("commit_hash", "before")
    hash_a    = after.get("commit_hash",  "after")
    ext_b     = before.get("file_extension", after.get("file_extension", ".py"))
    ext_a     = after.get("file_extension",  ext_b)
    if not ext_b.startswith("."):
        ext_b = f".{ext_b}"
    if not ext_a.startswith("."):
        ext_a = f".{ext_a}"

    # Analisar ambas as versões
    registry = get_registry()
    ts_b = float(before.get("timestamp", time.time() - 3600))
    ts_a = float(after.get("timestamp",  time.time()))

    mv_b = registry.analyze(source=code_b, file_extension=ext_b,
                             module_id=module_b, commit_hash=hash_b, timestamp=ts_b)
    mv_a = registry.analyze(source=code_a, file_extension=ext_a,
                             module_id=module_a, commit_hash=hash_a, timestamp=ts_a)

    if persist:
        _store.insert(mv_b)
        _store.insert(mv_a)

    # Deltas (after − before)
    def _mv_dict(mv) -> Dict:
        return {
            "hamiltonian":            mv.hamiltonian,
            "cyclomatic_complexity":  mv.cyclomatic_complexity,
            "infinite_loop_risk":     mv.infinite_loop_risk,
            "dsm_density":            mv.dsm_density,
            "dsm_cyclic_ratio":       mv.dsm_cyclic_ratio,
            "dependency_instability": mv.dependency_instability,
            "syntactic_dead_code":    mv.syntactic_dead_code,
            "duplicate_block_count":  mv.duplicate_block_count,
            "halstead_bugs":          mv.halstead_bugs,
            "status":                 mv.status,
            "language":               getattr(mv, "language", "python"),
            "lines_of_code":          getattr(mv, "lines_of_code", 0),
        }

    d_b = _mv_dict(mv_b)
    d_a = _mv_dict(mv_a)

    channels = [
        "hamiltonian", "cyclomatic_complexity", "infinite_loop_risk",
        "dsm_density", "dsm_cyclic_ratio", "dependency_instability",
        "syntactic_dead_code", "duplicate_block_count", "halstead_bugs",
    ]
    delta = {ch: round(d_a[ch] - d_b[ch], 6) for ch in channels}

    # Regressão: piora em H ou CC acima de threshold
    regression = (
        delta["hamiltonian"] > 2.0
        or delta["cyclomatic_complexity"] > 3
        or delta["infinite_loop_risk"] > 0.2
        or (d_a["status"] == "CRITICAL" and d_b["status"] != "CRITICAL")
    )

    # Sugestões de transforms baseadas nos canais que pioraram
    suggested_transforms: List[str] = []
    if delta["syntactic_dead_code"] > 0:
        suggested_transforms.append("remove_dead_code")
    if delta["duplicate_block_count"] > 0:
        suggested_transforms.append("remove_duplicate_blocks")
    if delta["hamiltonian"] > 3:
        suggested_transforms.append("simplify_logic")
    if delta["cyclomatic_complexity"] > 3:
        suggested_transforms.append("extract_functions")
    if delta["infinite_loop_risk"] > 0:
        suggested_transforms.append("add_loop_guard")

    # Score simples para before/after
    def _quick_score(mv) -> float:
        h  = mv.hamiltonian
        cc = mv.cyclomatic_complexity
        return max(0.0, 100.0 - min(h * 2, 60) - min((cc - 1) * 2, 30))

    score_b = _quick_score(mv_b)
    score_a = _quick_score(mv_a)

    return 200, {
        "before":    d_b,
        "after":     d_a,
        "delta":     delta,
        "delta_h":   delta["hamiltonian"],
        "regression": regression,
        "severity_before": d_b["status"],
        "severity_after":  d_a["status"],
        "uco_score_before": round(score_b, 2),
        "uco_score_after":  round(score_a, 2),
        "score_delta":      round(score_a - score_b, 2),
        "suggested_transforms": suggested_transforms,
        "summary": (
            f"{'REGRESSÃO' if regression else 'OK'}: "
            f"ΔH={delta['hamiltonian']:+.2f}  "
            f"ΔCC={delta['cyclomatic_complexity']:+d}  "
            f"Score {score_b:.0f}→{score_a:.0f}"
        ),
    }


def handle_report(module_id: Optional[str], title: str = "UCO-Sensor Report") -> Tuple[int, str]:
    """
    GET /report?module=<id>  — gera HTML report standalone do histórico de um módulo.
    Retorna (status_code, html_string).
    """
    if not module_id:
        # Relatório global: usa todos os módulos
        modules = _store.list_modules()
        if not modules:
            return 404, "<html><body><p>Nenhum módulo rastreado ainda.</p></body></html>"
        module_id = modules[0]   # fallback: primeiro módulo

    from scan.repo_scanner import ScanResult, FileScanResult
    import time as _time

    # Reconstruir ScanResult a partir do store
    history = _store.get_history(module_id, window=_config.max_history)
    if not history:
        return 404, f"<html><body><p>Módulo '{module_id}' não encontrado.</p></body></html>"

    # Pegar último snapshot como referência
    last = history[-1]
    lang = getattr(last, "language", "python")

    # Construir FileScanResult para cada snapshot (1 por commit)
    file_results = []
    for mv in history:
        h   = mv.hamiltonian
        cc  = mv.cyclomatic_complexity
        # status simples pelo hamiltoniano
        if h > 20 or cc > 15:
            status = "CRITICAL"
        elif h > 10 or cc > 8:
            status = "WARNING"
        else:
            status = "STABLE"
        file_results.append(FileScanResult(
            path=f"{module_id}@{mv.commit_hash[:7]}",
            language=getattr(mv, "language", lang),
            status=status,
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
            },
        ))

    # Métricas agregadas
    hs     = [mv.hamiltonian for mv in history]
    avg_h  = sum(hs) / len(hs)
    crit   = sum(1 for f in file_results if f.status == "CRITICAL")
    warn   = sum(1 for f in file_results if f.status == "WARNING")
    stable = sum(1 for f in file_results if f.status == "STABLE")
    # Score: penaliza proporcionalmente
    ratio_crit = crit / max(len(file_results), 1)
    ratio_warn = warn / max(len(file_results), 1)
    uco_score  = max(0.0, 100.0 - ratio_crit * 60 - ratio_warn * 25 - min(avg_h, 30))

    scan = ScanResult(
        root=module_id,
        commit_hash=getattr(last, "commit_hash", ""),
        timestamp=getattr(last, "timestamp", _time.time()),
        scan_duration_s=0.0,
        files_found=len(file_results),
        files_scanned=len(file_results),
        critical_count=crit,
        warning_count=warn,
        stable_count=stable,
        avg_hamiltonian=avg_h,
        avg_cyclomatic_complexity=sum(mv.cyclomatic_complexity for mv in history) / len(history),
        avg_infinite_loop_risk=sum(mv.infinite_loop_risk for mv in history) / len(history),
        avg_dsm_density=sum(mv.dsm_density for mv in history) / len(history),
        avg_dependency_instability=sum(mv.dependency_instability for mv in history) / len(history),
        avg_halstead_bugs=sum(mv.halstead_bugs for mv in history) / len(history),
        total_loc=sum(getattr(mv, "lines_of_code", 0) for mv in history),
        total_dead=sum(mv.syntactic_dead_code for mv in history),
        total_dups=sum(mv.duplicate_block_count for mv in history),
        uco_score=uco_score,
        top_critical=[f for f in file_results if f.status == "CRITICAL"][:5],
        top_warning=[f for f in file_results if f.status == "WARNING"][:5],
        by_language={getattr(mv, "language", lang): 1 for mv in history},
        file_results=file_results,
    )

    html = generate_html_report(scan, title=title, repo=module_id, commit=scan.commit_hash)
    return 200, html


def handle_badge(score: Optional[float], status: str = "STABLE",
                  label: str = "UCO Score", module_id: Optional[str] = None) -> Tuple[int, str]:
    """
    GET /badge?score=<n>&status=<s>&label=<l>
    GET /badge?module=<id>         — usa último score do módulo
    Retorna (status_code, svg_string).
    """
    # Se module_id fornecido, buscar último score
    if module_id and score is None:
        history = _store.get_history(module_id, window=1)
        if history:
            last = history[-1]
            h    = last.hamiltonian
            cc   = last.cyclomatic_complexity
            # Score simples baseado no último snapshot
            score = max(0.0, 100.0 - min(h * 2, 60) - min((cc - 1) * 2, 30))
            if last.hamiltonian > 20 or cc > 15:
                status = "CRITICAL"
            elif last.hamiltonian > 10 or cc > 8:
                status = "WARNING"
            else:
                status = "STABLE"

    if score is None:
        score = 0.0

    svg = generate_badge_svg(score=score, status=status, label=label)
    return 200, svg


def handle_anomalies(module_id: Optional[str], limit: int = 50) -> Tuple[int, Dict]:
    """GET /anomalies — lista anomalias detectadas."""
    anomalies = _store.get_anomalies(module_id=module_id, limit=limit)
    return 200, {
        "module_id": module_id,
        "anomalies": anomalies,
        "count":     len(anomalies),
    }


# ─── Governance endpoints ────────────────────────────────────────────────────

def handle_gate(data: Dict) -> Tuple[int, Dict]:
    """
    POST /gate — Quality gate for CI/CD pipelines.

    Body:
      {
        "code":          str,         — source code to analyse
        "module_id":     str,         — module identifier
        "commit_hash":   str,         — current commit hash
        "file_extension": str,        — ".py" | ".js" | ...
        "policy":        dict | null  — inline policy; null = default UCO policy
      }

    Response:
      {
        "passed":        bool,
        "gate_score":    int,   [0–100]
        "grade":         str,   A–F
        "violations":    [...],
        "metric_vector": {...},
        "policy_name":   str
      }
    """
    code        = data.get("code", "")
    module_id   = data.get("module_id", "unknown")
    commit_hash = data.get("commit_hash", f"gate_{int(time.time())}")
    file_ext    = data.get("file_extension", data.get("language", ".py"))
    policy_dict = data.get("policy", None)

    if not code.strip():
        return 400, {"error": "code is required and cannot be empty"}
    if not file_ext.startswith("."):
        file_ext = f".{file_ext}"

    # Analyse code
    registry = get_registry()
    mv = registry.analyze(
        source=code,
        file_extension=file_ext,
        module_id=module_id,
        commit_hash=commit_hash,
        timestamp=time.time(),
    )
    _store.insert(mv)

    # Load policy
    policy = policy_from_dict(policy_dict) if policy_dict else load_default_policy()

    # Evaluate
    metrics = mv_to_metrics_dict(mv)
    result  = evaluate_policy(metrics, policy)

    # Publish APEX event on failure
    if not result.passed and _config.apex_enabled:
        try:
            from apex_integration.event_bus import ApexEvent
            ev = ApexEvent(
                event_type="UCO_GATE_FAILURE",
                module_id=module_id,
                commit_hash=commit_hash,
                severity="CRITICAL" if result.errors else "WARNING",
                payload={
                    "gate_score":  result.gate_score,
                    "violations":  [v.to_dict() for v in result.violations[:5]],
                    "policy_name": result.policy_name,
                },
            )
            _connector._bus.publish(ev)
        except Exception:
            pass

    return 200, {
        **result.to_dict(),
        "metric_vector": metrics,
    }


def handle_trend(module_id: Optional[str], metric: str = "hamiltonian",
                 window: int = 10) -> Tuple[int, Dict]:
    """
    GET /trend?module=<id>&metric=<field>&window=<n>

    Returns trend analysis for one module / one metric.
    Also returns overall multi-metric trend direction.
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history for module '{module_id}'"}

    # Single-metric trend
    trend = analyze_trend(history, metric=metric, window=window,
                          module_id=module_id)

    # Multi-metric overview (always compute for dashboard convenience)
    multi = analyze_module_trends(history, module_id=module_id, window=window)
    ov    = overall_trend(multi)

    return 200, {
        "module_id":      module_id,
        "metric":         metric,
        "trend":          trend.to_dict(),
        "trend_summary":  trend_summary(trend),
        "overall_direction": ov,
        "multi_metric": {
            m: t.to_dict() for m, t in multi.items()
        },
    }


def handle_dashboard() -> Tuple[int, Dict]:
    """
    GET /dashboard

    Returns project-wide quality dashboard:
    - All known modules with their latest snapshot
    - Per-module trend direction (H, CC)
    - Project-level aggregates
    - SQALE debt budget summary
    """
    modules = _store.list_modules()
    module_data: List[Dict] = []
    total_debt  = 0
    module_debts: Dict[str, int] = {}

    for mod_id in modules:
        history = _store.get_history(mod_id, window=10)
        if not history:
            continue
        latest = history[-1]

        # Trend direction (hamiltonian as primary signal)
        trend = analyze_trend(history, metric="hamiltonian",
                              window=10, module_id=mod_id)

        debt = getattr(latest, "sqale_debt_minutes", 0) or 0
        module_debts[mod_id] = debt
        total_debt += debt

        module_data.append({
            "module_id":        mod_id,
            "status":           latest.status,
            "hamiltonian":      round(latest.hamiltonian, 4),
            "cyclomatic_complexity": latest.cyclomatic_complexity,
            "cognitive_complexity":  getattr(latest, "cognitive_complexity", None),
            "sqale_rating":     getattr(latest, "sqale_rating", None),
            "sqale_debt_minutes": debt,
            "ratings":          getattr(latest, "ratings", None),
            "trend_direction":  trend.direction,
            "trend_slope_pct":  round(trend.slope_pct, 4),
            "snapshots_count":  len(history),
        })

    # Sort: CRITICAL first, then by hamiltonian desc
    module_data.sort(key=lambda m: (
        {"CRITICAL": 0, "WARNING": 1, "STABLE": 2}.get(m["status"], 3),
        -(m["hamiltonian"]),
    ))

    # SQALE debt budget (default 480 min = 1 working day per project)
    budget = track_debt_budget(module_debts, budget_minutes=480)

    # Aggregate counts
    critical_n = sum(1 for m in module_data if m["status"] == "CRITICAL")
    warning_n  = sum(1 for m in module_data if m["status"] == "WARNING")
    stable_n   = sum(1 for m in module_data if m["status"] == "STABLE")

    degrading_n  = sum(1 for m in module_data if m["trend_direction"] == "DEGRADING")
    improving_n  = sum(1 for m in module_data if m["trend_direction"] == "IMPROVING")

    return 200, {
        "modules":    module_data,
        "total_modules": len(module_data),
        "status_counts": {
            "critical": critical_n,
            "warning":  warning_n,
            "stable":   stable_n,
        },
        "trend_counts": {
            "degrading": degrading_n,
            "improving": improving_n,
            "stable":    len(module_data) - degrading_n - improving_n,
        },
        "debt_budget": budget.to_dict(),
        "generated_at": time.time(),
    }


# ─── Web UI endpoint ─────────────────────────────────────────────────────────

def handle_dashboard_ui() -> Tuple[int, str]:
    """
    GET /dashboard/ui — Serve the interactive HTML dashboard (M4.1).

    Returns a self-contained HTML page with Chart.js temporal charts.
    Dashboard data is pre-embedded as JSON so the page renders without
    an additional /dashboard round-trip.
    """
    _, dashboard_data = handle_dashboard()
    html = generate_dashboard_html(
        dashboard_data=dashboard_data,
        title="UCO-Sensor Dashboard",
        refresh_seconds=30,
        api_base="",
        tool_version=_config.version,
    )
    return 200, html


# ─── SAST endpoints ──────────────────────────────────────────────────────────

def handle_sast(data: Dict) -> Tuple[int, Dict]:
    """
    POST /sast — Static security scan of source code.

    Body: {"code": str, "file_extension": str, "module_id": str}
    Response: SASTResult dict + SQALE debt contribution
    """
    code     = data.get("code", "")
    file_ext = data.get("file_extension", data.get("language", ".py"))
    if not code.strip():
        return 400, {"error": "code is required"}
    if not file_ext.startswith("."):
        file_ext = f".{file_ext}"

    result = sast_scan(code, file_extension=file_ext)
    return 200, result.to_dict()


def handle_sast_rules() -> Tuple[int, Dict]:
    """GET /sast/rules — list all SAST rules with metadata."""
    return 200, {
        "rules": [
            {
                "rule_id":    r.rule_id,
                "title":      r.title,
                "cwe_id":     r.cwe_id,
                "owasp":      r.owasp,
                "severity":   r.severity,
                "description": r.description,
                "remediation": r.remediation,
            }
            for r in SAST_RULES
        ],
        "count": len(SAST_RULES),
    }


# ─── Predictor endpoints (M6) ────────────────────────────────────────────────

def handle_predict(
    module_id: Optional[str],
    window:    int = 20,
    horizon:   int = 5,
) -> Tuple[int, Dict]:
    """
    GET /predict?module=<id>&window=<n>&horizon=<h>

    Returns a DegradationForecast for one module from its stored history.
    """
    if not module_id:
        return 400, {"error": "module query param is required"}

    analyzer = AutoAnalyzer(_store, default_window=window, default_horizon=horizon)
    forecast = analyzer.analyze_module(module_id, window=window, horizon=horizon)
    return 200, forecast.to_dict()


def handle_predict_all(
    window:  int = 20,
    horizon: int = 5,
    top_n:   int = 10,
) -> Tuple[int, Dict]:
    """
    GET /predict/all?window=<n>&horizon=<h>&top_n=<k>

    Returns FleetReport: all modules ordered by risk level then slope.
    """
    analyzer = AutoAnalyzer(_store, default_window=window, default_horizon=horizon)
    report   = analyzer.analyze_fleet(window=window, top_n=top_n, horizon=horizon)
    return 200, report.to_dict()


# ─── Incremental scan endpoint (M6.1) ───────────────────────────────────────

def handle_scan_incremental(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-incremental  (M6.1)

    Scans ONLY changed files and returns per-file metric deltas against
    stored baselines.  Two modes:

    Mode "files" (default):
    {
      "files": [
        {"path": "src/auth.py", "content": "...", "change_type": "MODIFIED"},
        ...
      ],
      "commit_hash":  "abc123",          # optional
      "base_commit":  "baseline",        # optional (informational label)
      "root":         "/abs/repo/path",  # optional (default ".")
      "persist":      true               # save new snapshots to store
    }

    Mode "git_diff":
    {
      "mode":         "git_diff",
      "repo_path":    "/abs/path/repo",
      "base_commit":  "HEAD~1",
      "head_commit":  "HEAD",
      "commit_hash":  "HEAD",            # optional
      "persist":      true
    }

    Returns IncrementalScanResult.to_dict():
    {
      "total_changed", "added_count", "modified_count", "deleted_count",
      "renamed_count", "scanned_count", "error_count", "regressions",
      "new_criticals", "file_deltas": [...], "commit_hash", "base_commit",
      "scan_duration_s"
    }
    """
    mode        = data.get("mode", "files")
    commit_hash = data.get("commit_hash", f"inc_{int(time.time())}")
    base_commit = data.get("base_commit", "baseline")
    root        = data.get("root", ".")
    persist     = bool(data.get("persist", True))

    store_ref = _store if persist else None
    scanner   = IncrementalScanner(root=root, store=store_ref, commit_hash=commit_hash)

    if mode == "git_diff":
        repo_path   = data.get("repo_path", root)
        head_commit = data.get("head_commit", "HEAD")
        result = scanner.scan_git_diff(
            repo_path=repo_path,
            base_commit=base_commit,
            head_commit=head_commit,
        )
        return 200, result.to_dict()

    # ── files mode ────────────────────────────────────────────────────────────
    raw_files = data.get("files", [])
    if not raw_files:
        return 400, {
            "error": "'files' list is required (or set mode='git_diff')"
        }

    changed: List[ChangedFile] = []
    for f in raw_files:
        path        = f.get("path", "")
        change_type = (f.get("change_type") or CHANGE_MODIFIED).upper()
        content     = f.get("content", None)
        old_path    = f.get("old_path", None)
        if not path:
            continue
        # Normalise change_type — accept "added"/"ADDED" etc.
        if change_type not in (CHANGE_ADDED, CHANGE_MODIFIED, CHANGE_DELETED, CHANGE_RENAMED):
            change_type = CHANGE_MODIFIED
        changed.append(ChangedFile(
            path=path,
            change_type=change_type,
            old_path=old_path,
            content=content,
        ))

    if not changed:
        return 400, {"error": "No valid file entries found in 'files' list"}

    result = scanner.scan_changed_files(
        changed,
        commit_hash=commit_hash,
        base_commit=base_commit,
    )
    return 200, result.to_dict()


# ─── SCA endpoint (M6.3) ─────────────────────────────────────────────────────

def handle_scan_sca(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-sca  (M6.3)

    Software Composition Analysis: detect known CVEs in project dependencies.
    Two modes:

    mode="path" (default):
        Scans the filesystem starting at `root`.
        Body: {"root": "/path/to/repo"}

    mode="files":
        Inline manifest content supplied in the request.
        Body: {"files": {"requirements.txt": "django==3.1.0\\n..."}}

    Returns SCAResult.to_dict() with:
        status, summary, findings[], dependencies[], severity counts, debt.
    """
    mode = data.get("mode", "path")
    scanner = VulnerabilityScanner()

    if mode == "files":
        files_raw = data.get("files", {})
        if not isinstance(files_raw, dict) or not files_raw:
            return 400, {"error": "'files' dict is required for mode='files'"}
        result = scanner.scan_files(files_raw)
        return 200, result.to_dict()

    # mode == "path"
    root = data.get("root", ".")
    result = scanner.scan_path(root)
    return 200, result.to_dict()


def handle_scan_iac(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-iac  (M6.4)

    IaC Misconfiguration Scanner: detect security misconfigurations in
    Infrastructure-as-Code files (Dockerfile, Compose, k8s YAML,
    Terraform .tf/.tfvars, Helm values.yaml).

    Two modes:

    mode="path" (default):
        Walks the filesystem starting at `root`.
        Body: {"root": "/path/to/repo"}

    mode="files":
        Inline file contents supplied in the request body.
        Body: {"files": {"Dockerfile": "FROM ubuntu:latest\\n..."}}

    Returns IaCScanResult.to_dict() with:
        status, total_findings, by_severity, by_category,
        total_debt_minutes, files_scanned, findings[].
    """
    mode = data.get("mode", "path")
    scanner = IaCScanner()

    if mode == "files":
        files_raw = data.get("files", {})
        if not isinstance(files_raw, dict) or not files_raw:
            return 400, {"error": "'files' dict is required for mode='files'"}
        result = scanner.scan_files(files_raw)
        return 200, result.to_dict()

    # mode == "path"
    root = data.get("root", ".")
    result = scanner.scan_path(root)
    return 200, result.to_dict()


# ─── M7.0 Advanced metrics endpoint ─────────────────────────────────────────

def handle_metrics_advanced(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    """
    GET /metrics/advanced?module=<id>[&window=<n>]  (M7.0)

    Returns the most-recent persisted AdvancedVector + DiagnosticVector for a
    module.  These vectors capture signals computed on every /analyze call that
    were previously lost between requests.

    Response schema
    ---------------
    {
      "module_id":       str,
      "history_size":    int,
      "advanced_vector": {   — AdvancedVector (6 channels)
        "cognitive_cc_total":  int,
        "cognitive_cc_max":    int,
        "sqale_debt_minutes":  int,
        "sqale_rating":        str,   # A–E
        "clone_count":         int,
        "fn_profile_count":    int
      } | null,
      "diagnostic_vector": {  — DiagnosticVector (8 channels), present when ≥5 snapshots
        "dominant_frequency_H":    float,
        "spectral_entropy_H":      float,
        "phase_coupling_CC_H":     float,
        "burst_index":             float,
        "self_cure_probability":   float,
        "onset_reversibility":     float,
        "degradation_signature":   str,
        "frequency_anomaly_score": float
      } | null,
      "risk_tier":   str   — STABLE | WARNING | CRITICAL (DiagnosticVector.risk_tier)
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest = history[-1]   # most-recent snapshot (chronological order)

    # AdvancedVector
    adv = getattr(latest, "advanced", None)
    adv_dict = adv.to_dict() if adv is not None else None

    # DiagnosticVector
    diag = getattr(latest, "diagnostic", None)
    diag_dict = None
    risk_tier  = "STABLE"
    if diag is not None:
        diag_dict = diag.to_dict()
        risk_tier  = diag.risk_tier()

    return 200, {
        "module_id":         module_id,
        "history_size":      len(history),
        "last_commit":       latest.commit_hash,
        "last_timestamp":    latest.timestamp,
        "advanced_vector":   adv_dict,
        "diagnostic_vector": diag_dict,
        "risk_tier":         risk_tier,
    }


# ─── M7.3a ReliabilityVector endpoint ───────────────────────────────────────

def handle_metrics_reliability(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    """
    GET /metrics/reliability?module=<id>[&window=<n>]  (M7.3a)

    Returns the most-recent persisted ReliabilityVector for a module.

    Response schema
    ---------------
    {
      "module_id":          str,
      "history_size":       int,
      "last_commit":        str,
      "last_timestamp":     float,
      "reliability_vector": {          — ReliabilityVector (10 channels)
        "bare_except_count":           int,
        "swallowed_exception_count":   int,
        "mutable_default_arg_count":   int,
        "inconsistent_return_count":   int,
        "shadow_builtin_count":        int,
        "global_mutation_count":       int,
        "empty_except_block_count":    int,
        "resource_leak_risk":          int,
        "regex_redos_risk":            int,
        "infinite_recursion_risk":     float,
        "total_issues":                int,
        "reliability_rating":          str   # A–E
      } | null,
      "reliability_rating": str   — A–E (top-level convenience field)
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    if not _RELIABILITY_VECTOR_AVAILABLE:
        return 503, {"error": "ReliabilityVector not available (metrics package missing)"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest = history[-1]

    rel = getattr(latest, "reliability", None)
    rel_dict   = rel.to_dict()           if rel is not None else None
    rel_rating = rel.reliability_rating() if rel is not None else "N/A"

    return 200, {
        "module_id":          module_id,
        "history_size":       len(history),
        "last_commit":        latest.commit_hash,
        "last_timestamp":     latest.timestamp,
        "reliability_vector": rel_dict,
        "reliability_rating": rel_rating,
    }


# ─── M7.3b MaintainabilityVector endpoint ────────────────────────────────────

def handle_metrics_maintainability(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    """
    GET /metrics/maintainability?module=<id>[&window=<n>]  (M7.3b)

    Returns the most-recent persisted MaintainabilityVector for a module.

    Response schema
    ---------------
    {
      "module_id":               str,
      "history_size":            int,
      "last_commit":             str,
      "last_timestamp":          float,
      "maintainability_vector":  {       — MaintainabilityVector (9 channels)
        "missing_docstring_ratio":  float,
        "avg_function_args":        float,
        "long_function_ratio":      float,
        "deeply_nested_ratio":      float,
        "cognitive_cc_hotspot":     int,
        "boolean_param_count":      int,
        "magic_number_count":       int,
        "long_parameter_list":      int,
        "invariant_density":        float,
        "maintainability_rating":   str   # A–E
      } | null,
      "maintainability_rating": str   — A–E (top-level convenience field)
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    if not _MAINTAINABILITY_VECTOR_AVAILABLE:
        return 503, {"error": "MaintainabilityVector not available (metrics package missing)"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest = history[-1]

    mnt = getattr(latest, "maintainability", None)
    mnt_dict   = mnt.to_dict()                if mnt is not None else None
    mnt_rating = mnt.maintainability_rating() if mnt is not None else "N/A"

    return 200, {
        "module_id":              module_id,
        "history_size":           len(history),
        "last_commit":            latest.commit_hash,
        "last_timestamp":         latest.timestamp,
        "maintainability_vector": mnt_dict,
        "maintainability_rating": mnt_rating,
    }


# ─── M7.2 Taint Analysis endpoints ──────────────────────────────────────────

def handle_scan_flow(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-flow  (M7.2)

    Run intra-function taint analysis (DFA) on a Python source snippet.
    Returns all detected source→sink flows, FlowVector, and SAST-compatible
    finding dicts for each confirmed taint path.

    Request body
    ------------
    {
      "code":      str  — Python source code (required)
      "module_id": str  — identifier for the module (optional)
    }

    Response schema
    ---------------
    {
      "module_id":         str,
      "flow_vector": {
        "taint_source_count":    int,
        "taint_sink_count":      int,
        "taint_path_count":      int,
        "taint_sanitized_ratio": float,
        "cross_fn_taint_risk":   int,
        "injection_surface":     float,
        "flow_rating":           str,   # A–E
        "unsanitized_paths":     int
      },
      "flows": [
        {
          "rule_id":      str,          # SAST040-SAST045
          "severity":     str,          # CRITICAL / HIGH / MEDIUM
          "cwe_id":       str,
          "vuln_type":    str,          # SQL_INJECTION / COMMAND_INJECTION / …
          "source_desc":  str,
          "source_line":  int,
          "sink_desc":    str,
          "line":         int,
          "flow_path":    [str],        # variable chain source→sink
          "sanitized":    bool,
          "debt_minutes": int
        }
      ],
      "summary": {
        "source_count":          int,
        "sink_count":            int,
        "taint_path_count":      int,
        "sanitized_count":       int,
        "taint_sanitized_ratio": float,
        "injection_surface":     float,
        "cross_fn_risk":         int
      }
    }
    """
    if not _TAINT_ENGINE_AVAILABLE:
        return 503, {"error": "Taint engine not available (sast.taint_engine missing)"}

    source    = data.get("code", "")
    module_id = data.get("module_id", "<anonymous>")

    if not source or not source.strip():
        return 400, {"error": "Field 'code' is required and must be non-empty"}

    try:
        result = _TaintAnalyzer().analyze(source, module_id=module_id)
    except Exception as exc:
        return 500, {"error": f"Taint analysis failed: {exc}"}

    fv = _FlowVector.from_taint_result(result, module_id=module_id)

    return 200, {
        "module_id":   module_id,
        "flow_vector": fv.to_dict(),
        "flows":       [f.to_dict() for f in result.flows],
        "summary": {
            "source_count":          result.source_count,
            "sink_count":            result.sink_count,
            "taint_path_count":      result.taint_path_count,
            "sanitized_count":       result.sanitized_count,
            "taint_sanitized_ratio": result.taint_sanitized_ratio,
            "injection_surface":     result.injection_surface,
            "cross_fn_risk":         result.cross_fn_risk,
        },
    }


def handle_metrics_flow(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    """
    GET /metrics/flow?module=<id>[&window=<n>]  (M7.2)

    Returns the most-recent persisted FlowVector for a module.

    Response schema
    ---------------
    {
      "module_id":    str,
      "history_size": int,
      "last_commit":  str,
      "last_timestamp": float,
      "flow_vector":  {FlowVector.to_dict()} | null,
      "flow_rating":  str   — A–E (top-level convenience)
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    if not _TAINT_ENGINE_AVAILABLE:
        return 503, {"error": "FlowVector not available (taint engine missing)"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest = history[-1]

    fv = getattr(latest, "flow", None)
    fv_dict   = fv.to_dict()     if fv is not None else None
    fv_rating = fv.flow_rating() if fv is not None else "N/A"

    return 200, {
        "module_id":     module_id,
        "history_size":  len(history),
        "last_commit":   latest.commit_hash,
        "last_timestamp": latest.timestamp,
        "flow_vector":   fv_dict,
        "flow_rating":   fv_rating,
    }


# ─── M7.4 Performance endpoints ─────────────────────────────────────────────

def handle_scan_performance(data: Dict) -> Tuple[int, Dict]:
    """
    POST /scan-performance  (M7.4)

    Run performance anti-pattern analysis on a Python source snippet.
    Returns PerformanceVector + per-pattern counts + rating.

    Request body
    ------------
    {
      "code":      str  — Python source code (required)
      "module_id": str  — identifier for the module (optional)
    }

    Response schema
    ---------------
    {
      "module_id":          str,
      "performance_vector": {PerformanceVector.to_dict()},
      "summary": {
        "n_plus_one_risk":             int,
        "list_in_loop_append_count":   int,
        "string_concat_in_loop":       int,
        "quadratic_nested_loop_count": int,
        "repeated_computation_count":  int,
        "regex_compile_in_loop":       int,
        "io_in_tight_loop":            int,
        "inefficient_dict_lookup":     int,
        "total_issues":                int,
        "performance_rating":          str
      }
    }
    """
    if not _PERFORMANCE_AVAILABLE:
        return 503, {"error": "Performance analyzer not available (metrics.performance_analyzer missing)"}

    source    = data.get("code", "")
    module_id = data.get("module_id", "<anonymous>")

    if not source or not source.strip():
        return 400, {"error": "Field 'code' is required and must be non-empty"}

    try:
        result = _PerformanceAnalyzer().analyze(source, module_id=module_id)
    except Exception as exc:
        return 500, {"error": f"Performance analysis failed: {exc}"}

    pv = _PerformanceVector.from_analyzer(result, module_id=module_id)

    return 200, {
        "module_id":          module_id,
        "performance_vector": pv.to_dict(),
        "summary": {
            "n_plus_one_risk":             result.n_plus_one_risk,
            "list_in_loop_append_count":   result.list_in_loop_append_count,
            "string_concat_in_loop":       result.string_concat_in_loop,
            "quadratic_nested_loop_count": result.quadratic_nested_loop_count,
            "repeated_computation_count":  result.repeated_computation_count,
            "regex_compile_in_loop":       result.regex_compile_in_loop,
            "io_in_tight_loop":            result.io_in_tight_loop,
            "inefficient_dict_lookup":     result.inefficient_dict_lookup,
            "total_issues":                pv.total_issues,
            "performance_rating":          pv.performance_rating(),
        },
    }


def handle_metrics_performance(
    module_id: Optional[str], window: int = 50,
) -> Tuple[int, Dict]:
    """
    GET /metrics/performance?module=<id>[&window=<n>]  (M7.4)

    Returns the most-recent persisted PerformanceVector for a module.

    Response schema
    ---------------
    {
      "module_id":            str,
      "history_size":         int,
      "last_commit":          str,
      "last_timestamp":       float,
      "performance_vector":   {PerformanceVector.to_dict()} | null,
      "performance_rating":   str   — A–E (top-level convenience)
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    if not _PERFORMANCE_AVAILABLE:
        return 503, {"error": "PerformanceVector not available (performance_analyzer missing)"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest = history[-1]
    pv     = getattr(latest, "performance", None)
    pv_dict   = pv.to_dict()            if pv is not None else None
    pv_rating = pv.performance_rating() if pv is not None else "N/A"

    return 200, {
        "module_id":          module_id,
        "history_size":       len(history),
        "last_commit":        latest.commit_hash,
        "last_timestamp":     latest.timestamp,
        "performance_vector": pv_dict,
        "performance_rating": pv_rating,
    }


# ─── M8.1 LSP endpoint ───────────────────────────────────────────────────────

# LSP severity constants (Microsoft Language Server Protocol)
_LSP_SEV_ERROR:       int = 1
_LSP_SEV_WARNING:     int = 2
_LSP_SEV_INFORMATION: int = 3
_LSP_SEV_HINT:        int = 4

_SAST_SEV_TO_LSP: Dict[str, int] = {
    "CRITICAL": _LSP_SEV_ERROR,
    "HIGH":     _LSP_SEV_ERROR,
    "MEDIUM":   _LSP_SEV_WARNING,
    "LOW":      _LSP_SEV_INFORMATION,
    "INFO":     _LSP_SEV_HINT,
}


def _lsp_range(line: int, col: int = 0, end_col: int = 80) -> Dict:
    """Build an LSP ``range`` object (0-indexed)."""
    ln = max(0, line - 1)       # LSP is 0-indexed; SAST findings are 1-indexed
    return {
        "start": {"line": ln, "character": col},
        "end":   {"line": ln, "character": max(col, end_col)},
    }


def _finding_to_lsp_diag(finding: Dict) -> Dict:
    """Convert a SASTFinding.to_dict() payload to an LSP Diagnostic object."""
    severity = _SAST_SEV_TO_LSP.get(finding.get("severity", "MEDIUM"), _LSP_SEV_WARNING)
    line = finding.get("line", 1)
    col  = finding.get("col", 0)
    return {
        "range":    _lsp_range(line, col),
        "severity": severity,
        "code":     finding.get("rule_id", ""),
        "source":   "uco-sensor",
        "message":  (
            f"[{finding.get('rule_id','')}] {finding.get('title', '')}: "
            f"{finding.get('description', '')}"
        ),
        "data": {
            "rule_id":       finding.get("rule_id", ""),
            "cwe_id":        finding.get("cwe_id", ""),
            "owasp":         finding.get("owasp", ""),
            "remediation":   finding.get("remediation", ""),
            "suggested_fix": finding.get("suggested_fix", ""),
            "confidence":    finding.get("confidence", 0.9),
            "explanation":   finding.get("explanation", ""),
            "debt_minutes":  finding.get("debt_minutes", 0),
        },
    }


def _vector_diag(
    line: int, col: int, severity: int,
    code: str, message: str, data: Optional[Dict] = None,
) -> Dict:
    """Build a synthetic LSP diagnostic from a metric vector signal."""
    return {
        "range":    _lsp_range(line, col),
        "severity": severity,
        "code":     code,
        "source":   "uco-sensor",
        "message":  message,
        "data":     data or {},
    }


def handle_lsp_diagnostics(
    module_id: Optional[str],
    window: int = 50,
) -> Tuple[int, Dict]:
    """
    GET /lsp/diagnostics?module=<id>[&window=<n>]  (M8.1)

    Returns stored analysis results in Language Server Protocol (LSP)
    Diagnostic format, suitable for direct consumption by editors via
    the LSP ``textDocument/publishDiagnostics`` notification.

    Diagnostic sources (in priority order)
    ----------------------------------------
    1. SAST findings stored in the latest snapshot (if available)
    2. FlowVector (taint) signals — unsanitised flows → Error/Warning
    3. ReliabilityVector signals  — crash_risk, bug_density → Warning/Info
    4. MaintainabilityVector signals — hotspot_density → Hint

    Response schema
    ---------------
    {
      "uri":         str,              # file:///<module_id>.py
      "module_id":   str,
      "diagnostics": [
        {
          "range":    {"start": {"line": N, "character": C},
                       "end":   {"line": N, "character": C}},
          "severity": 1|2|3|4,        # Error/Warning/Information/Hint
          "code":     str,             # rule_id / signal code
          "source":   "uco-sensor",
          "message":  str,
          "data":     {...}            # rule metadata + enrichment
        }
      ],
      "count": int,
      "history_size": int,
      "last_timestamp": float | null
    }
    """
    if not module_id:
        return 400, {"error": "module parameter is required"}

    history = _store.get_history(module_id, window=window)
    if not history:
        return 404, {"error": f"No history found for module '{module_id}'"}

    latest       = history[-1]
    uri          = f"file:///{module_id.replace('.', '/')}.py"
    diagnostics: List[Dict] = []

    # ── 1. SAST findings (stored in mv.sast_result if present) ───────────────
    sast_result = getattr(latest, "sast_result", None)
    if sast_result is not None:
        raw_findings = (
            sast_result.get("findings", [])
            if isinstance(sast_result, dict)
            else getattr(sast_result, "findings", [])
        )
        for finding in raw_findings:
            f_dict = finding if isinstance(finding, dict) else finding.to_dict()
            diagnostics.append(_finding_to_lsp_diag(f_dict))

    # ── 2. FlowVector signals ─────────────────────────────────────────────────
    if _TAINT_ENGINE_AVAILABLE:
        fv = getattr(latest, "flow", None)
        if fv is not None:
            unsanitized = getattr(fv, "unsanitized_paths",
                                  fv.taint_path_count if hasattr(fv, "taint_path_count") else 0)
            if unsanitized > 0:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_ERROR,
                    code="UCO-FLOW-001",
                    message=(
                        f"{unsanitized} unsanitised taint flow(s) detected "
                        f"(injection_surface={fv.injection_surface:.2f}). "
                        f"Run /scan-flow for line-level detail."
                    ),
                    data={
                        "flow_rating":         fv.flow_rating(),
                        "taint_source_count":  fv.taint_source_count,
                        "taint_sink_count":    fv.taint_sink_count,
                        "unsanitized_paths":   unsanitized,
                        "injection_surface":   fv.injection_surface,
                        "cross_fn_taint_risk": fv.cross_fn_taint_risk,
                    },
                ))
            if fv.cross_fn_taint_risk > 0:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_WARNING,
                    code="UCO-FLOW-002",
                    message=(
                        f"Cross-function taint risk detected at {fv.cross_fn_taint_risk} "
                        f"call site(s). Tainted values passed to non-sink functions."
                    ),
                    data={"cross_fn_taint_risk": fv.cross_fn_taint_risk},
                ))

    # ── 3. ReliabilityVector signals ──────────────────────────────────────────
    if _RELIABILITY_VECTOR_AVAILABLE:
        rv = getattr(latest, "reliability", None)
        if rv is not None:
            crash_risk = getattr(rv, "crash_risk", 0.0)
            bug_density = getattr(rv, "bug_density", 0.0)
            if crash_risk > 0.6:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_WARNING,
                    code="UCO-REL-001",
                    message=(
                        f"High crash risk detected: crash_risk={crash_risk:.2f}. "
                        f"Review exception handling and null-check coverage."
                    ),
                    data={"crash_risk": crash_risk, "bug_density": bug_density,
                          "reliability_rating": rv.reliability_rating()
                          if hasattr(rv, "reliability_rating") else "?"},
                ))
            elif crash_risk > 0.3:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_INFORMATION,
                    code="UCO-REL-001",
                    message=(
                        f"Moderate crash risk: crash_risk={crash_risk:.2f}. "
                        f"Consider adding defensive exception handling."
                    ),
                    data={"crash_risk": crash_risk},
                ))
            if bug_density > 0.05:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_INFORMATION,
                    code="UCO-REL-002",
                    message=(
                        f"Elevated bug density: {bug_density:.4f} issues/LOC. "
                        f"Review bare exceptions and error handling."
                    ),
                    data={"bug_density": bug_density},
                ))

    # ── 4. MaintainabilityVector signals ─────────────────────────────────────
    if _MAINTAINABILITY_VECTOR_AVAILABLE:
        mv = getattr(latest, "maintainability", None)
        if mv is not None:
            hotspot_density = getattr(mv, "hotspot_density", 0.0)
            debt_ratio      = getattr(mv, "debt_ratio", 0.0)
            if hotspot_density > 0.5:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_HINT,
                    code="UCO-MAINT-001",
                    message=(
                        f"High hotspot density: {hotspot_density:.2f}. "
                        f"Module has many refactoring candidates."
                    ),
                    data={"hotspot_density": hotspot_density, "debt_ratio": debt_ratio},
                ))
            if debt_ratio > 0.3:
                diagnostics.append(_vector_diag(
                    line=1, col=0,
                    severity=_LSP_SEV_HINT,
                    code="UCO-MAINT-002",
                    message=(
                        f"Technical debt ratio: {debt_ratio:.2f}. "
                        f"Consider scheduling a refactoring sprint."
                    ),
                    data={"debt_ratio": debt_ratio},
                ))

    return 200, {
        "uri":            uri,
        "module_id":      module_id,
        "diagnostics":    diagnostics,
        "count":          len(diagnostics),
        "history_size":   len(history),
        "last_timestamp": getattr(latest, "timestamp", None),
    }


# ─── Auth endpoints ──────────────────────────────────────────────────────────

def handle_create_key(data: Dict) -> Tuple[int, Dict]:
    """POST /auth/keys [admin] — cria API key."""
    name      = data.get("name", "")
    quota_day = int(data.get("quota_day", 0))
    plain = _store.create_key(name=name, quota_day=quota_day)
    return 201, {
        "api_key":    plain,
        "key_prefix": plain[:12],
        "name":       name,
        "quota_day":  quota_day,
        "warning":    "Store this key securely — it will not be shown again.",
    }


def handle_list_keys() -> Tuple[int, Dict]:
    """GET /auth/keys [admin] — lista chaves."""
    keys = _store.list_keys()
    return 200, {"keys": keys, "count": len(keys)}


def handle_revoke_key(key_prefix: str) -> Tuple[int, Dict]:
    """DELETE /auth/keys?prefix=<prefix> [admin] — revoga chave."""
    if not key_prefix:
        return 400, {"error": "prefix parameter is required"}
    ok = _store.revoke_key(key_prefix)
    if not ok:
        return 404, {"error": f"Key '{key_prefix}' not found or already revoked"}
    return 200, {"revoked": key_prefix}


def handle_usage(key_info: Dict) -> Tuple[int, Dict]:
    """GET /usage — uso da chave corrente."""
    prefix = key_info.get("key_prefix", "")
    usage  = _store.get_usage(prefix) if prefix != "dev" else key_info
    return 200, usage or key_info


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class UCOSensorHandler(BaseHTTPRequestHandler):
    """Handler HTTP para o UCO-Sensor REST API."""

    def log_message(self, fmt: str, *args) -> None:
        pass  # silencia logs padrão

    # ── GET ────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        # Endpoints sem auth
        if path == "/health":
            return self._send_json(*handle_health())
        if path == "/docs":
            return self._send_json(*handle_docs())

        # Auth para todos os demais
        raw_key = _extract_api_key(self.headers, params)
        ok, key_info = _authenticate(raw_key)
        if not ok:
            return self._send_json(401, {"error": "Invalid or missing API key"})

        try:
            if path == "/modules":
                code, data = handle_modules()
            elif path == "/history":
                module_id = params.get("module", [None])[0]
                window    = int(params.get("window", ["50"])[0])
                code, data = handle_history(module_id, window)
            elif path == "/baseline":
                module_id = params.get("module", [None])[0]
                code, data = handle_baseline(module_id)
            elif path == "/usage":
                code, data = handle_usage(key_info)
            elif path == "/auth/keys":
                ok_admin, _ = _authenticate(raw_key, require_admin=True)
                if not ok_admin:
                    code, data = 403, {"error": "Admin key required"}
                else:
                    code, data = handle_list_keys()
            elif path == "/apex/status":
                code, data = handle_apex_status()
            elif path == "/apex/ping":
                code, data = handle_apex_ping()
            elif path == "/anomalies":
                module_id = params.get("module", [None])[0]
                limit_n   = int(params.get("limit", ["50"])[0])
                code, data = handle_anomalies(module_id, limit_n)
            elif path == "/trend":
                module_id = params.get("module", [None])[0]
                metric    = params.get("metric", ["hamiltonian"])[0]
                window_n  = int(params.get("window", ["10"])[0])
                code, data = handle_trend(module_id, metric, window_n)
            elif path == "/dashboard":
                code, data = handle_dashboard()
            elif path == "/dashboard/ui":
                http_code, html = handle_dashboard_ui()
                return self._send_html(http_code, html)
            elif path == "/sast/rules":
                code, data = handle_sast_rules()
            elif path == "/report":
                module_id = params.get("module", [None])[0]
                title     = params.get("title", ["UCO-Sensor Report"])[0]
                http_code, html = handle_report(module_id, title=title)
                return self._send_html(http_code, html)
            elif path == "/badge":
                # Endpoint sem auth — badge público
                module_id  = params.get("module",  [None])[0]
                score_raw  = params.get("score",   [None])[0]
                status_val = params.get("status",  ["STABLE"])[0]
                label_val  = params.get("label",   ["UCO Score"])[0]
                score_val  = float(score_raw) if score_raw is not None else None
                http_code, svg = handle_badge(
                    score=score_val, status=status_val,
                    label=label_val, module_id=module_id
                )
                return self._send_svg(http_code, svg)
            elif path == "/predict":
                module_id = params.get("module",  [None])[0]
                window_n  = int(params.get("window",  ["20"])[0])
                horizon_n = int(params.get("horizon", ["5"])[0])
                code, data = handle_predict(module_id, window=window_n, horizon=horizon_n)
            elif path == "/predict/all":
                window_n  = int(params.get("window",  ["20"])[0])
                horizon_n = int(params.get("horizon", ["5"])[0])
                top_n_val = int(params.get("top_n",   ["10"])[0])
                code, data = handle_predict_all(window=window_n, horizon=horizon_n, top_n=top_n_val)
            elif path == "/metrics/advanced":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_metrics_advanced(module_id, window=window_n)
            elif path == "/metrics/reliability":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_metrics_reliability(module_id, window=window_n)
            elif path == "/metrics/maintainability":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_metrics_maintainability(module_id, window=window_n)
            elif path == "/metrics/flow":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_metrics_flow(module_id, window=window_n)
            elif path == "/metrics/performance":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_metrics_performance(module_id, window=window_n)
            elif path == "/lsp/diagnostics":
                module_id = params.get("module", [None])[0]
                window_n  = int(params.get("window", ["50"])[0])
                code, data = handle_lsp_diagnostics(module_id, window=window_n)
            else:
                code, data = 404, {"error": f"Unknown endpoint: {path}"}
        except Exception as e:
            code = 500
            data = {"error": str(e), "trace": traceback.format_exc()[-500:]}

        self._send_json(code, data)

    # ── POST ───────────────────────────────────────────────────────────────

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        # Ler body — T77: limite de 10 MB para evitar DoS
        _MAX_BODY = 10 * 1024 * 1024  # 10 MB
        length = int(self.headers.get("Content-Length", 0))
        if length > _MAX_BODY:
            return self._send_json(413, {
                "error": f"Request body too large: {length} bytes (max {_MAX_BODY})"
            })
        raw    = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            return self._send_json(400, {"error": "Invalid JSON body"})

        # Auth
        raw_key = _extract_api_key(self.headers, params)
        ok, key_info = _authenticate(raw_key)
        if not ok:
            return self._send_json(401, {"error": "Invalid or missing API key"})

        try:
            if path == "/analyze":
                code, data = handle_analyze(body)
            elif path == "/repair":
                code, data = handle_repair(body)
            elif path == "/analyze-pr":
                code, data = handle_analyze_pr(body)
            elif path == "/scan-repo":
                code, data = handle_scan_repo(body)
            elif path == "/apex/webhook":
                code, data = handle_apex_webhook(body)
            elif path == "/diff":
                code, data = handle_diff(body)
            elif path == "/gate":
                code, data = handle_gate(body)
            elif path == "/sast":
                code, data = handle_sast(body)
            elif path == "/apex/fix":
                code, data = handle_apex_fix(body)
            elif path == "/scan-incremental":
                code, data = handle_scan_incremental(body)
            elif path == "/scan-sca":
                code, data = handle_scan_sca(body)
            elif path == "/scan-iac":
                code, data = handle_scan_iac(body)
            elif path == "/scan-flow":
                code, data = handle_scan_flow(body)
            elif path == "/scan-performance":
                code, data = handle_scan_performance(body)
            elif path == "/auth/keys":
                ok_admin, _ = _authenticate(raw_key, require_admin=True)
                if not ok_admin:
                    code, data = 403, {"error": "Admin key required"}
                else:
                    code, data = handle_create_key(body)
            else:
                code, data = 404, {"error": f"Unknown endpoint: {path}"}
        except Exception as e:
            code = 500
            data = {"error": str(e), "trace": traceback.format_exc()[-500:]}

        self._send_json(code, data)

    # ── DELETE ─────────────────────────────────────────────────────────────

    def do_DELETE(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        raw_key = _extract_api_key(self.headers, params)
        ok_admin, _ = _authenticate(raw_key, require_admin=True)
        if not ok_admin:
            return self._send_json(403, {"error": "Admin key required"})

        try:
            if path == "/auth/keys":
                prefix = params.get("prefix", [None])[0]
                code, data = handle_revoke_key(prefix)
            else:
                code, data = 404, {"error": f"Unknown endpoint: {path}"}
        except Exception as e:
            code = 500
            data = {"error": str(e), "trace": traceback.format_exc()[-500:]}

        self._send_json(code, data)

    # ── Resposta ───────────────────────────────────────────────────────────

    def _send_json(self, status_code: int, data: Any) -> None:
        status_str = "ok" if status_code < 400 else "error"
        envelope   = {"status": status_str, "data": data}
        body = json.dumps(envelope, default=str).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-UCO-Sensor-Version", _config.version)
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, status_code: int, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-UCO-Sensor-Version", _config.version)
        self.end_headers()
        self.wfile.write(body)

    def _send_svg(self, status_code: int, svg: str) -> None:
        body = svg.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-UCO-Sensor-Version", _config.version)
        self.end_headers()
        self.wfile.write(body)


# ─── Entrypoint CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UCO-Sensor API Server")
    parser.add_argument("--port",     type=int,  default=8080)
    parser.add_argument("--host",     type=str,  default="0.0.0.0")
    parser.add_argument("--db",       type=str,  default="uco_sensor.db")
    parser.add_argument("--verbose",  action="store_true", default=False)
    parser.add_argument("--auth",     action="store_true", default=False,
                        help="Habilitar verificação de API key")
    parser.add_argument("--no-auth",  action="store_true", default=False,
                        help="Desabilitar verificação de API key (dev mode)")
    parser.add_argument("--apex-url", type=str, default="",
                        help="URL do APEX event bus (habilita integração APEX)")
    parser.add_argument("--apex-key", type=str, default="",
                        help="API key para autenticação no APEX")
    args = parser.parse_args()

    _config.db_path      = args.db
    _config.verbose      = args.verbose
    _config.auth_enabled = args.auth and not args.no_auth
    _config.admin_key    = os.environ.get("UCO_ADMIN_KEY", "")
    _store.__init__(args.db)

    # Configurar APEX connector se URL fornecida
    if args.apex_url or os.environ.get("APEX_WEBHOOK_URL"):
        from apex_integration.connector import ApexConnector, set_connector as _set_connector
        apex_url = args.apex_url or os.environ.get("APEX_WEBHOOK_URL", "")
        apex_key = args.apex_key or os.environ.get("APEX_API_KEY", "")
        _set_connector(ApexConnector.from_config(
            webhook_url=apex_url,
            api_key=apex_key or None,
            severity_gate="CRITICAL",
            enabled=True,
        ))
        _config.apex_enabled = True

    server = HTTPServer((args.host, args.port), UCOSensorHandler)
    print(f"[UCO-Sensor v{_config.version}] Rodando em http://{args.host}:{args.port}")
    print(f"[UCO-Sensor] DB: {args.db} | Auth: {_config.auth_enabled} | Verbose: {args.verbose}")
    print(f"[UCO-Sensor] Linguagens: {', '.join(get_registry().supported_languages())}")
    if _config.apex_enabled:
        print(f"[UCO-Sensor] APEX: {args.apex_url or os.environ.get('APEX_WEBHOOK_URL')} | Gate: CRITICAL")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[UCO-Sensor] Encerrando...")
        server.shutdown()
