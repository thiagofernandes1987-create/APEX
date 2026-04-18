"""
UCO-Sensor API — HTTP Server
==============================
UCOSensorHandler: servidor HTTP leve para a API REST do UCO-Sensor.

Endpoints:
  GET  /health          — liveness probe
  POST /analyze         — analisa código e retorna MetricVector + classifica
  GET  /modules         — lista módulos conhecidos no store
  GET  /history?module= — histórico de snapshots de um módulo
  POST /repair          — analisa + sugere transforms + retorna código otimizado
  GET  /baseline?module=— estatísticas de baseline do módulo

Design:
  • stdlib pura — sem Flask/FastAPI/aiohttp (zero dependências extras)
  • BaseHTTPRequestHandler com dispatcher por método+path
  • Thread-safe via SnapshotStore lock interno
  • Envelope de resposta padronizado: {"status": "ok"|"error", "data": {...}}
  • Content-Type: application/json em todas as respostas

Uso:
  python server.py --port 8080
  ou importar UCOSensorHandler para tests:
    server = HTTPServer(("127.0.0.1", 18080), UCOSensorHandler)
"""
from __future__ import annotations
import sys
import json
import time
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Any, Dict, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# ── Path setup (compatível com test runner e execução direta) ─────────────────
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


# ─── Configuração ────────────────────────────────────────────────────────────

@dataclass
class SensorConfig:
    db_path:      str   = ":memory:"
    engine_mode:  str   = "fast"
    verbose:      bool  = False
    max_history:  int   = 100
    version:      str   = "0.2.0"


# ─── Singletons globais (inicializados na primeira importação) ───────────────

_config  = SensorConfig()
_store   = SnapshotStore(_config.db_path)
_bridge  = UCOBridge(mode=_config.engine_mode)
_engine  = FrequencyEngine(verbose=_config.verbose)
_router  = SignalOutputRouter()


# ─── Handlers de endpoint ────────────────────────────────────────────────────

def handle_health() -> Tuple[int, Dict]:
    return 200, {
        "status": "healthy",
        "version": _config.version,
        "timestamp": time.time(),
        "modules_tracked": len(_store.list_modules()),
    }


def handle_analyze(data: Dict) -> Tuple[int, Dict]:
    """
    POST /analyze
    Body: {"code": str, "module_id": str, "commit_hash": str, "timestamp"?: float}

    Retorna MetricVector serializado + classificação espectral se houver histórico.
    """
    code        = data.get("code", "")
    module_id   = data.get("module_id", "unknown")
    commit_hash = data.get("commit_hash", f"auto_{int(time.time())}")
    timestamp   = float(data.get("timestamp", time.time()))

    if not code.strip():
        return 400, {"error": "code is required and cannot be empty"}

    # 1. Analisar com UCOBridge
    mv = _bridge.analyze(code, module_id, commit_hash, timestamp=timestamp)

    # 2. Persistir no store
    _store.insert(mv)

    # 3. Classificação espectral (se houver histórico suficiente)
    classification = None
    history = _store.get_history(module_id, window=_config.max_history)
    if len(history) >= 5:
        result = _engine.analyze(history, module_id=module_id)
        if result:
            classification = {
                "primary_error":    result.primary_error,
                "severity":         result.severity,
                "confidence":       round(result.primary_confidence, 4),
                "dominant_band":    result.dominant_band,
                "plain_english":    result.plain_english,
                "spectral_evidence": result.spectral_evidence,
            }

    return 200, {
        "metric_vector": {
            "module_id":              mv.module_id,
            "commit_hash":            mv.commit_hash,
            "timestamp":              mv.timestamp,
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
        },
        "classification": classification,
        "history_size":   len(history),
    }


def handle_modules() -> Tuple[int, Dict]:
    """GET /modules — lista todos os módulos rastreados."""
    modules = _store.list_modules()
    return 200, {
        "modules": modules,
        "count": len(modules),
    }


def handle_history(module_id: Optional[str], window: int = 50) -> Tuple[int, Dict]:
    """GET /history?module=<id>&window=<n>"""
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
                "status":      mv.status,
            }
            for mv in history
        ],
        "count": len(history),
    }


def handle_baseline(module_id: Optional[str]) -> Tuple[int, Dict]:
    """GET /baseline?module=<id>"""
    if not module_id:
        return 400, {"error": "module parameter is required"}

    baseline = _store.get_baseline(module_id)
    if baseline is None:
        return 404, {"error": f"No baseline for '{module_id}' (need ≥ 3 snapshots)"}

    return 200, {
        "module_id":   module_id,
        "n_samples":   baseline.n_samples,
        "h_mean":      round(baseline.h_mean, 4),
        "h_std":       round(baseline.h_std, 4),
        "h_trend":     round(baseline.h_trend_slope, 6),
        "cc_mean":     round(baseline.cc_mean, 4),
        "di_mean":     round(baseline.di_mean, 4),
    }


def handle_repair(data: Dict) -> Tuple[int, Dict]:
    """
    POST /repair
    Body: {"code": str, "module_id"?: str, "depth"?: "fast"|"full"}

    Analisa o código, aplica transforms UCO e retorna versão otimizada.
    Retorna: h_before, h_after, delta_h, optimized_code, metrics_before, metrics_after.
    """
    code      = data.get("code", "")
    module_id = data.get("module_id", "repair.anonymous")
    depth     = data.get("depth", "fast")

    if not code.strip():
        return 400, {"error": "code is required and cannot be empty"}

    # Análise antes
    bridge_local = UCOBridge(mode=depth)
    mv_before = bridge_local.analyze(code, module_id, "repair_before")
    sugg = bridge_local.suggest_transforms(code, module_id, "repair_suggest")

    optimized = sugg.get("optimized_code", code)

    # Análise depois (se o código mudou)
    mv_after = bridge_local.analyze(optimized, module_id, "repair_after")

    metrics_before = {
        "hamiltonian": mv_before.hamiltonian,
        "cc":          mv_before.cyclomatic_complexity,
        "dead":        mv_before.syntactic_dead_code,
        "dups":        mv_before.duplicate_block_count,
        "ilr":         mv_before.infinite_loop_risk,
    }
    metrics_after = {
        "hamiltonian": mv_after.hamiltonian,
        "cc":          mv_after.cyclomatic_complexity,
        "dead":        mv_after.syntactic_dead_code,
        "dups":        mv_after.duplicate_block_count,
        "ilr":         mv_after.infinite_loop_risk,
    }

    # delta_h = redução de H (positivo = melhoria, negativo = piora inesperada)
    delta_h = mv_before.hamiltonian - mv_after.hamiltonian

    return 200, {
        "h_before":       round(mv_before.hamiltonian, 4),
        "h_after":        round(mv_after.hamiltonian, 4),
        "delta_h":        round(delta_h, 4),
        "optimized_code": optimized,
        "transforms":     sugg.get("transforms", []),
        "metrics_before": metrics_before,
        "metrics_after":  metrics_after,
    }


# ─── HTTP Handler ─────────────────────────────────────────────────────────────

class UCOSensorHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP para o UCO-Sensor REST API.

    Despacha requests para as funções handle_* acima.
    Envelope de resposta: {"status": "ok"|"error", "data": {...}}
    """

    def log_message(self, fmt: str, *args) -> None:  # type: ignore
        """Silencia logs padrão do BaseHTTPRequestHandler."""
        pass

    # ── GET ────────────────────────────────────────────────────────────────

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path   = parsed.path
        params = parse_qs(parsed.query)

        try:
            if path == "/health":
                code, data = handle_health()

            elif path == "/modules":
                code, data = handle_modules()

            elif path == "/history":
                module_id = params.get("module", [None])[0]
                window    = int(params.get("window", ["50"])[0])
                code, data = handle_history(module_id, window)

            elif path == "/baseline":
                module_id = params.get("module", [None])[0]
                code, data = handle_baseline(module_id)

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

        # Ler body
        length = int(self.headers.get("Content-Length", 0))
        raw    = self.rfile.read(length) if length > 0 else b"{}"
        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Invalid JSON body"})
            return

        try:
            if path == "/analyze":
                code, data = handle_analyze(body)

            elif path == "/repair":
                code, data = handle_repair(body)

            else:
                code, data = 404, {"error": f"Unknown endpoint: {path}"}

        except Exception as e:
            code = 500
            data = {"error": str(e), "trace": traceback.format_exc()[-500:]}

        self._send_json(code, data)

    # ── Resposta ───────────────────────────────────────────────────────────

    def _send_json(self, status_code: int, data: Any) -> None:
        """Envia resposta JSON com envelope padrão."""
        status_str = "ok" if status_code < 400 else "error"
        envelope   = {"status": status_str, "data": data}
        body = json.dumps(envelope, default=str).encode("utf-8")

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-UCO-Sensor-Version", _config.version)
        self.end_headers()
        self.wfile.write(body)


# ─── Entrypoint CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UCO-Sensor API Server")
    parser.add_argument("--port",   type=int,  default=8080)
    parser.add_argument("--host",   type=str,  default="0.0.0.0")
    parser.add_argument("--db",     type=str,  default="uco_sensor.db")
    parser.add_argument("--verbose",action="store_true", default=False)
    args = parser.parse_args()

    # Reconfigurar singletons com opções CLI
    _config.db_path = args.db
    _config.verbose = args.verbose
    _store.__init__(args.db)

    server = HTTPServer((args.host, args.port), UCOSensorHandler)
    print(f"[UCO-Sensor] API server rodando em http://{args.host}:{args.port}")
    print(f"[UCO-Sensor] DB: {args.db} | Verbose: {args.verbose}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[UCO-Sensor] Encerrando...")
        server.shutdown()
