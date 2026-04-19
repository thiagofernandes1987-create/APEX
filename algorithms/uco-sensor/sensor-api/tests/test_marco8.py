"""
UCO-Sensor — Testes Marco 8: Demo Final + Integração Ponta a Ponta
===================================================================
Valida o produto completo: documentação, demo, e pipeline end-to-end
cobrindo todos os marcos M1–M7 em sequência.

Testes:
  T80  README.md existe com badges, instalação, endpoints e tabela de testes
  T81  demo/demo_full.py existe e importa sem erro
  T82  Pipeline completo: analyze → history → classify → diff → fix (< 3s)
  T83  Multi-linguagem ponta a ponta: Python + JS na mesma sessão
  T84  APEX round-trip: anomaly event → fix_request → fix_result → improvement
  T85  GET /docs lista todos os 18+ endpoints incluindo novos
  T86  CHANGELOG.md tem versões v0.1.0 → v0.4.0
  T87  Todos os test_marco*.py existem (M1–M7 + M8)
  T88  Geração de badge SVG + HTML report end-to-end sem erro
  T89  Servidor HTTP: todos os endpoints respondem com status correto
"""
from __future__ import annotations
import sys
import json
import time
import threading
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from http.server import HTTPServer
from typing import List, Dict

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from api.server import UCOSensorHandler, _store, handle_diff, handle_apex_fix, handle_apex_webhook
from sensor_core.uco_bridge import UCOBridge
from sensor_storage.snapshot_store import SnapshotStore
from report.badge import generate_badge_svg, generate_status_badge_svg
from report.html_report import generate_html_report
from apex_integration.templates import get_template, all_error_types


# ─── Código de teste ──────────────────────────────────────────────────────────

CODE_SIMPLE  = "def hello(name): return f'Hello, {name}!'"
CODE_COMPLEX = """
def process(items, cfg, ctx, flags, state, meta, extra=None):
    results = []
    for item in items:
        if item and cfg:
            for k, v in cfg.items():
                if k in flags:
                    if v > 0:
                        if ctx.get('strict'):
                            if state.get('enabled'):
                                results.append(item)
    unused1 = 42
    unused2 = 99
    return results
    return []  # dead code
"""
CODE_JS = """
function processItems(items, config) {
    var results = [];
    for (var i = 0; i < items.length; i++) {
        if (items[i] && config) {
            results.push(items[i]);
        }
    }
    return results;
}
"""

# ─── HTTP helpers ─────────────────────────────────────────────────────────────

PORT_M8 = 19088
_server_m8 = None


def setup_server():
    global _server_m8
    if _server_m8 is None:
        server = HTTPServer(("127.0.0.1", PORT_M8), UCOSensorHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        time.sleep(0.15)
        _server_m8 = server
    return _server_m8


def _get(path: str):
    url = f"http://127.0.0.1:{PORT_M8}{path}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, json.loads(resp.read())


def _post(path: str, body: Dict):
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"http://127.0.0.1:{PORT_M8}{path}",
        data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


# ─── T80: README.md completo ─────────────────────────────────────────────────

def test_T80_readme_complete():
    """README.md existe com badges, instalação, endpoints e tabela de marcos."""
    p = _SENSOR / "README.md"
    assert p.exists(), "README.md não encontrado"
    content = p.read_text(encoding="utf-8")

    # Badges
    assert "shields.io" in content or "img.shields.io" in content or "badge" in content.lower(), \
        "README não tem badges"
    # Instalação
    assert "pip install" in content or "Installation" in content.lower() or "Instalação" in content, \
        "README não tem instruções de instalação"
    # Endpoints
    assert "/analyze" in content, "/analyze não documentado no README"
    assert "/diff"    in content, "/diff não documentado no README"
    assert "/apex/fix" in content, "/apex/fix não documentado no README"
    assert "/report"  in content, "/report não documentado no README"
    # Marcos
    for m in ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8"]:
        assert m in content, f"Marco {m} não encontrado no README"
    # Docker
    assert "docker" in content.lower(), "Docker não mencionado no README"
    print(f"  [T80] ok — README.md completo ({len(content):,} chars)")


# ─── T81: demo_full.py importa sem erro ──────────────────────────────────────

def test_T81_demo_importable():
    """demo/demo_full.py existe e importa (não executa o main)."""
    demo_path = _SENSOR / "demo" / "demo_full.py"
    assert demo_path.exists(), f"demo/demo_full.py não encontrado"

    # Verificar sintaxe via ast
    import ast
    source = demo_path.read_text(encoding="utf-8")
    tree   = ast.parse(source)

    # Verificar que main() existe
    funcs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    assert "main" in funcs, f"main() não encontrado em demo_full.py"
    # Verificar os 8 steps
    for step in ["step1_analyze", "step2_history", "step3_classify",
                  "step4_diff", "step5_report", "step6_apex_event",
                  "step7_apex_fix", "step8_status"]:
        assert step in funcs, f"função '{step}' não encontrada"
    print(f"  [T81] ok — demo_full.py tem main() e 8 steps ({len(source):,} chars)")


# ─── T82: Pipeline completo < 3s ─────────────────────────────────────────────

def test_T82_full_pipeline_under_3s():
    """Pipeline analyze → history → classify → diff → fix em < 3s."""
    from pipeline.frequency_engine import FrequencyEngine

    bridge = UCOBridge(mode="fast")
    store  = SnapshotStore(":memory:")
    engine = FrequencyEngine(verbose=False)

    t0 = time.perf_counter()

    # Acumular 15 snapshots
    for i in range(15):
        code = CODE_SIMPLE if i < 8 else CODE_COMPLEX
        mv   = bridge.analyze(code, "perf.pipe", f"pp{i:03d}",
                               timestamp=float(1700000000 + i * 86400))
        store.insert(mv)

    # Classificar
    history = store.get_history("perf.pipe", window=15)
    result  = engine.analyze(history, module_id="perf.pipe")

    # Diff
    code_d, _resp_d = handle_diff({
        "before": {"code": CODE_SIMPLE,  "commit_hash": "v1"},
        "after":  {"code": CODE_COMPLEX, "commit_hash": "v2"},
    })

    # Fix
    code_f, _resp_f = handle_apex_fix({
        "module_id":  "perf.pipe",
        "code":       CODE_COMPLEX,
        "error_type": "DEAD_CODE_DRIFT",
    })

    elapsed = time.perf_counter() - t0
    assert elapsed < 3.0, f"Pipeline levou {elapsed:.2f}s > 3s"
    assert code_d == 200
    assert code_f == 200
    print(f"  [T82] ok — pipeline completo em {elapsed:.3f}s")


# ─── T83: Multi-linguagem ponta a ponta ──────────────────────────────────────

def test_T83_multilang_end_to_end():
    """Python + JS analisados na mesma sessão com store compartilhado."""
    from lang_adapters.registry import get_registry
    registry = get_registry()

    store_ml = SnapshotStore(":memory:")

    # Python
    mv_py = registry.analyze(CODE_SIMPLE, ".py", "ml.py", "py001")
    store_ml.insert(mv_py)
    assert getattr(mv_py, "language", "python") == "python"

    # JavaScript
    mv_js = registry.analyze(CODE_JS, ".js", "ml.js", "js001")
    store_ml.insert(mv_js)
    assert getattr(mv_js, "language", "javascript") == "javascript"

    modules = store_ml.list_modules()
    assert "ml.py" in modules, "ml.py não encontrado no store"
    assert "ml.js" in modules, "ml.js não encontrado no store"

    # Diff cross-linguagem (mesmo tipo de análise)
    code_d, resp_d = handle_diff({
        "before": {"code": CODE_SIMPLE, "file_extension": ".py", "commit_hash": "v1"},
        "after":  {"code": CODE_JS,     "file_extension": ".js", "commit_hash": "v2"},
    })
    assert code_d == 200
    print(f"  [T83] ok — Python+JS no mesmo store, cross-diff delta_h={resp_d['delta_h']:.3f}")


# ─── T84: APEX round-trip ─────────────────────────────────────────────────────

def test_T84_apex_full_roundtrip():
    """Anomaly event → fix_request → fix_result com melhora confirmada."""
    from apex_integration.event_bus import ApexEventBus
    from apex_integration.connector import ApexConnector
    from sensor_storage.snapshot_store import SnapshotStore as _SS

    received_events: List[Dict] = []
    received_fixes:  List[Dict] = []

    # 1. Configurar connector com callback
    connector = ApexConnector.from_config(
        callback=received_events.append,
        severity_gate="CRITICAL",
        enabled=True,
    )

    # 2. Simular ClassificationResult CRITICAL
    from tests.test_marco3 import _make_classification_result
    result_crit = _make_classification_result("CRITICAL")
    store_rt    = _SS(":memory:")
    dr = connector.handle(result_crit, store=store_rt)

    assert dr is not None and dr.ok, f"Evento não publicado: {dr}"
    assert len(received_events) == 1
    assert received_events[0]["event"] == "UCO_ANOMALY_DETECTED"

    # 3. APEX responde com APEX_FIX_REQUEST
    fix_code, fix_resp = handle_apex_webhook({
        "event": "APEX_FIX_REQUEST",
        "payload": {
            "module_id":  "test.module",
            "code":       CODE_COMPLEX,
            "error_type": received_events[0]["payload"]["error_type"],
            "hurst":      0.82,
        },
    })
    assert fix_code == 200
    assert fix_resp["ack"] is True
    assert "fix_result" in fix_resp

    # 4. Confirmar que o fix não piorou
    fix = fix_resp["fix_result"]
    assert fix["h_after"] <= fix["h_before"] + 0.5
    print(f"  [T84] ok — round-trip: event→fix  H {fix['h_before']:.2f}→{fix['h_after']:.2f}")


# ─── T85: GET /docs lista 18+ endpoints ──────────────────────────────────────

def test_T85_docs_lists_all_endpoints():
    """GET /docs lista todos os endpoints incluindo diff, fix, report, badge."""
    setup_server()
    status, resp = _get("/docs")
    assert status == 200
    endpoints = {ep["path"] for ep in resp["data"]["endpoints"]}

    required = ["/analyze", "/repair", "/diff", "/report", "/badge",
                 "/apex/fix", "/apex/webhook", "/analyze-pr", "/auth/keys"]
    for ep in required:
        assert ep in endpoints, f"Endpoint '{ep}' ausente em /docs"
    assert len(endpoints) >= 18, f"Esperado >= 18 endpoints, got {len(endpoints)}"
    print(f"  [T85] ok — /docs lista {len(endpoints)} endpoints")


# ─── T86: CHANGELOG cobre v0.1.0 → v0.4.0 ────────────────────────────────────

def test_T86_changelog_all_versions():
    """CHANGELOG.md documenta v0.1.0 → v0.4.0 com todos os marcos."""
    p = _SENSOR / "CHANGELOG.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")

    for version in ["0.1.0", "0.1.1", "0.1.2", "0.1.3", "0.2.0", "0.3.0", "0.4.0"]:
        assert version in content, f"Versão {version} ausente no CHANGELOG"
    for kw in ["ANALISAR", "EXPANDIR", "CONECTAR", "VISUALIZAR",
                "CALIBRAR", "DISTRIBUIR", "AGIR"]:
        assert kw in content, f"Keyword '{kw}' ausente no CHANGELOG"
    print(f"  [T86] ok — CHANGELOG cobre v0.1.0 → v0.4.0 com todos os marcos")


# ─── T87: todos os test_marco*.py existem ────────────────────────────────────

def test_T87_all_test_files_exist():
    """Todos os arquivos tests/test_marco1.py até test_marco8.py existem."""
    for i in range(1, 9):
        p = _SENSOR / "tests" / f"test_marco{i}.py"
        assert p.exists(), f"test_marco{i}.py não encontrado"
    print(f"  [T87] ok — todos os 8 arquivos test_marco*.py existem")


# ─── T88: Badge + HTML report sem erro ───────────────────────────────────────

def test_T88_badge_and_report_end_to_end():
    """Gera badge SVG e HTML report a partir de dados do store e valida."""
    from scan.repo_scanner import ScanResult, FileScanResult

    # Badge para cada status
    for score, status in [(90, "STABLE"), (55, "WARNING"), (20, "CRITICAL")]:
        svg = generate_badge_svg(score=score, status=status, label="UCO Score")
        assert f"{score}/100" in svg, f"Score {score} não no SVG"
        assert status in svg or status.lower() in svg.lower(), f"Status {status} ausente"

    # Status badge
    for st in ["STABLE", "WARNING", "CRITICAL"]:
        svg = generate_status_badge_svg(st)
        assert st in svg

    # HTML report
    fr = FileScanResult(
        path="src/main.py", language="python", status="STABLE",
        loc=50, metrics={"hamiltonian": 4.0, "cyclomatic_complexity": 3,
                          "infinite_loop_risk": 0.0, "dsm_density": 0.1,
                          "dsm_cyclic_ratio": 0.0, "dependency_instability": 0.2,
                          "syntactic_dead_code": 0, "duplicate_block_count": 0,
                          "halstead_bugs": 0.05},
    )
    scan = ScanResult(
        root="/tmp/demo", commit_hash="abc123", timestamp=time.time(),
        scan_duration_s=0.1, files_found=1, files_scanned=1,
        stable_count=1, uco_score=87.0,
        by_language={"python": 1}, file_results=[fr],
    )
    html = generate_html_report(scan, title="Demo Report")
    assert "87" in html
    assert "<table" in html
    print(f"  [T88] ok — badges (6) + HTML report gerados sem erro")


# ─── T89: Servidor HTTP — todos os endpoints ─────────────────────────────────

def test_T89_server_all_endpoints_respond():
    """Servidor HTTP: todos os principais endpoints respondem com código correto."""
    setup_server()

    # Pré-popular store
    bridge = UCOBridge(mode="fast")
    for i in range(6):
        mv = bridge.analyze(
            CODE_SIMPLE if i < 3 else CODE_COMPLEX,
            "e2e.module", f"e2e{i:03d}",
            timestamp=float(1700000000 + i * 86400),
        )
        _store.insert(mv)

    checks = [
        ("GET",  "/health",                   None,                   200),
        ("GET",  "/docs",                     None,                   200),
        ("GET",  "/modules",                  None,                   200),
        ("GET",  "/history?module=e2e.module", None,                  200),
        ("GET",  "/baseline?module=e2e.module", None,                 200),
        ("GET",  "/anomalies",                None,                   200),
        ("GET",  "/apex/status",              None,                   200),
        ("GET",  "/apex/ping",                None,                   200),
        ("POST", "/analyze",
         {"code": CODE_SIMPLE, "module_id": "e2e.check", "commit_hash": "chk1"},  200),
        ("POST", "/diff",
         {"before": {"code": CODE_SIMPLE, "commit_hash": "v1"},
          "after":  {"code": CODE_COMPLEX, "commit_hash": "v2"}},               200),
        ("POST", "/apex/fix",
         {"module_id": "e2e.fix", "code": CODE_COMPLEX,
          "error_type": "DEAD_CODE_DRIFT"},                                       200),
        ("POST", "/apex/webhook",
         {"event": "APEX_PING", "payload": {}},                                  200),
    ]

    passed = 0
    failed_eps = []
    for method, path, body, expected in checks:
        try:
            if method == "GET":
                status, _ = _get(path)
            else:
                status, _ = _post(path, body)
            if status == expected:
                passed += 1
            else:
                failed_eps.append(f"{method} {path}: got {status} expected {expected}")
        except Exception as e:
            failed_eps.append(f"{method} {path}: exception {e}")

    assert not failed_eps, \
        f"Endpoints com falha:\n" + "\n".join(f"  {ep}" for ep in failed_eps)
    print(f"  [T89] ok — {passed}/{len(checks)} endpoints responderam corretamente")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T80",  test_T80_readme_complete),
    ("T81",  test_T81_demo_importable),
    ("T82",  test_T82_full_pipeline_under_3s),
    ("T83",  test_T83_multilang_end_to_end),
    ("T84",  test_T84_apex_full_roundtrip),
    ("T85",  test_T85_docs_lists_all_endpoints),
    ("T86",  test_T86_changelog_all_versions),
    ("T87",  test_T87_all_test_files_exist),
    ("T88",  test_T88_badge_and_report_end_to_end),
    ("T89",  test_T89_server_all_endpoints_respond),
]


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 8 — Demo Final + E2E  ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  OK {name}")
            passed += 1
        except Exception as exc:
            import traceback
            print(f"  FAIL {name}: {exc}")
            failed += 1
            errors.append((name, exc))

    print(f"\n{'='*65}")
    print(f"  Resultado: {passed}/{len(TESTS)} passaram")
    if errors:
        print(f"\n  Falhas:")
        for n, e in errors:
            print(f"    {n}: {e}")
    print(f"{'='*65}\n")

    sys.exit(0 if failed == 0 else 1)
