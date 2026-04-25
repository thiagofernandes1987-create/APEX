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


# ─── Configuração ────────────────────────────────────────────────────────────

@dataclass
class SensorConfig:
    db_path:      str   = ":memory:"
    engine_mode:  str   = "fast"
    verbose:      bool  = False
    max_history:  int   = 100
    version:      str   = "0.7.0"
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
            }
            # ── Marco 3: publicar evento APEX se severity=CRITICAL ───────────
            try:
                delivery = _connector.handle(result, store=_store)
                apex_event_sent = delivery is not None and delivery.ok
            except Exception:
                pass   # APEX nunca quebra o fluxo principal

    return 200, {
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
    results: List[Dict] = []
    sarif_results: List[Dict] = []
    critical_count = 0
    warning_count  = 0

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

        severity_map = {"CRITICAL": "error", "WARNING": "warning", "STABLE": "note"}
        sarif_level = severity_map.get(mv.status, "note")

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

        # SARIF result para cada arquivo com status não-STABLE
        if mv.status != "STABLE":
            sarif_results.append({
                "ruleId": f"UCO-{mv.status}",
                "level": sarif_level,
                "message": {
                    "text": (
                        f"UCO-Sensor: {mv.status} — "
                        f"H={mv.hamiltonian:.2f}, CC={mv.cyclomatic_complexity}, "
                        f"ILR={mv.infinite_loop_risk:.2f}, bugs={mv.halstead_bugs:.2f}"
                    )
                },
                "locations": [{
                    "physicalLocation": {
                        "artifactLocation": {"uri": path},
                        "region": {"startLine": 1}
                    }
                }]
            })

    # SARIF 2.1.0 envelope
    sarif_output = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "UCO-Sensor",
                    "version": _config.version,
                    "informationUri": "https://github.com/apex/uco-sensor",
                    "rules": [
                        {
                            "id": "UCO-CRITICAL",
                            "name": "CriticalQualitySignal",
                            "shortDescription": {"text": "UCO critical quality threshold exceeded"},
                        },
                        {
                            "id": "UCO-WARNING",
                            "name": "WarningQualitySignal",
                            "shortDescription": {"text": "UCO warning quality threshold exceeded"},
                        },
                    ]
                }
            },
            "results": sarif_results,
        }]
    }

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
            elif path == "/apex/fix":
                code, data = handle_apex_fix(body)
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
