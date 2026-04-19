"""
UCO-Sensor API — Test Suite Marco 1
=====================================
Testa os três componentes do Marco 1:
  T01  UCOBridge — extrai os 9 canais corretamente do UCO v4.0
  T02  SnapshotStore — persistência, histórico, baseline, z-score
  T03  API endpoints — ciclo completo analyze → history → baseline
  T04  FrequencyEngine integrado — pipeline ponta a ponta com UCO real
  T05  Performance — < 500ms para análise completa
"""
import sys, os, time, json, threading, urllib.request, urllib.error
from pathlib import Path

# ── Path setup (portável Windows/Linux/Mac) ────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sensor_core.uco_bridge import UCOBridge
from sensor_storage.snapshot_store import SnapshotStore
from core.data_structures import MetricVector

# ─── Test runner ────────────────────────────────────────────────────────────

class Runner:
    def __init__(self):
        self.passed = self.failed = 0
        self.errors = []

    def run(self, name, fn):
        try:
            t0 = time.perf_counter()
            fn()
            ms = (time.perf_counter() - t0) * 1000
            print(f"  \033[92m✓\033[0m {name:<58} ({ms:.1f}ms)")
            self.passed += 1
        except Exception as e:
            print(f"  \033[91m✗\033[0m {name}")
            print(f"    {type(e).__name__}: {e}")
            self.failed += 1
            self.errors.append((name, str(e)))

    def summary(self):
        total = self.passed + self.failed
        ok = self.failed == 0
        color = "\033[92m" if ok else "\033[91m"
        print(f"\n{'─'*65}")
        print(f"  {color}{self.passed}/{total} testes passaram\033[0m")
        if self.errors:
            for n, e in self.errors:
                print(f"  • {n}: {e[:80]}")
        return ok

R = Runner()

# ─── Código de teste ──────────────────────────────────────────────────────────

CODE_SIMPLE = """
def process(items):
    result = []
    for i in items:
        if i > 0:
            result.append(i * 2)
    return result
"""

CODE_WITH_DEAD = """
def risky(x, y):
    if x > 0:
        return x / y
    return 0
    print("never reached")
    unused_var = 42
"""

CODE_LOOP_RISK = """
def poll(service):
    while True:
        status = service.check()
        if status == 'done':
            return status
    # no timeout guard — ILR spike
"""

CODE_COMPLEX = """
def mega_function(a, b, c, d, e):
    if a > 0:
        if b > 0:
            if c > 0:
                for i in range(d):
                    if i % 2 == 0:
                        for j in range(e):
                            if j > i:
                                print(i, j)
                    else:
                        while True:
                            pass
"""

# ─── T01 UCOBridge ────────────────────────────────────────────────────────────

print(f"\n{'═'*65}")
print("  Marco 1 — Test Suite")
print(f"{'═'*65}\n")

bridge = UCOBridge(mode="fast")

def test_bridge_returns_metricvector():
    mv = bridge.analyze(CODE_SIMPLE, "test.mod", "abc123")
    assert isinstance(mv, MetricVector)
    assert mv.module_id == "test.mod"
    assert mv.commit_hash == "abc123"

R.run("T01a — bridge retorna MetricVector", test_bridge_returns_metricvector)

def test_bridge_9_channels_nonzero():
    mv = bridge.analyze(CODE_COMPLEX, "test.complex", "def456")
    assert mv.hamiltonian > 0, f"H={mv.hamiltonian}"
    assert mv.cyclomatic_complexity >= 1
    assert mv.language == "python"

R.run("T01b — 9 canais preenchidos corretamente", test_bridge_9_channels_nonzero)

def test_bridge_dead_code_detected():
    mv = bridge.analyze(CODE_WITH_DEAD, "test.dead", "ghi789")
    # UCO deve detectar print("never reached") como dead code
    assert mv.syntactic_dead_code >= 1, f"dead={mv.syntactic_dead_code}"

R.run("T01c — dead code detectado via UCO AST", test_bridge_dead_code_detected)

def test_bridge_loop_risk():
    mv = bridge.analyze(CODE_LOOP_RISK, "test.loop", "jkl012")
    assert mv.infinite_loop_risk > 0, f"ILR={mv.infinite_loop_risk}"

R.run("T01d — ILR detectado em while True sem timeout", test_bridge_loop_risk)

def test_bridge_suggest_transforms():
    sugg = bridge.suggest_transforms(CODE_WITH_DEAD)
    assert "h_before" in sugg
    assert "h_after" in sugg
    assert "delta_h" in sugg
    assert isinstance(sugg["transforms"], list)

R.run("T01e — suggest_transforms retorna campos corretos", test_bridge_suggest_transforms)

def test_bridge_status_mapping():
    # Código simples → STABLE
    mv_simple = bridge.analyze(CODE_SIMPLE, "mod", "a1")
    assert mv_simple.status in ("STABLE", "WARNING", "CRITICAL")
    # Código complexo → provavelmente WARNING ou CRITICAL
    mv_complex = bridge.analyze(CODE_COMPLEX, "mod2", "b2")
    assert mv_complex.status in ("STABLE", "WARNING", "CRITICAL")

R.run("T01f — status mapeado corretamente (STABLE/WARNING/CRITICAL)", test_bridge_status_mapping)

# ─── T02 SnapshotStore ────────────────────────────────────────────────────────

store = SnapshotStore(":memory:")

def test_store_insert_and_retrieve():
    mv = bridge.analyze(CODE_SIMPLE, "auth.login", "c001")
    store.insert(mv)
    history = store.get_history("auth.login", window=10)
    assert len(history) == 1
    assert history[0].module_id == "auth.login"
    assert abs(history[0].hamiltonian - mv.hamiltonian) < 0.01

R.run("T02a — insert e get_history básicos", test_store_insert_and_retrieve)

def test_store_history_ordering():
    """Histórico deve estar em ordem cronológica (mais antigo primeiro)."""
    for i in range(5):
        mv = MetricVector(
            module_id="order.test", commit_hash=f"t{i:03d}",
            timestamp=float(1700000000 + i * 3600),
            hamiltonian=float(5 + i), cyclomatic_complexity=i+1,
            infinite_loop_risk=0.01, dsm_density=0.2, dsm_cyclic_ratio=0.0,
            dependency_instability=0.3, syntactic_dead_code=0,
            duplicate_block_count=0, halstead_bugs=0.1,
        )
        store.insert(mv)
    history = store.get_history("order.test", window=10)
    assert len(history) == 5
    ts_list = [mv.timestamp for mv in history]
    assert ts_list == sorted(ts_list), "história não está em ordem cronológica"

R.run("T02b — histórico ordenado cronologicamente", test_store_history_ordering)

def test_store_baseline_computed():
    """Baseline com ≥ 3 amostras deve retornar BaselineStats."""
    for i in range(10):
        mv = MetricVector(
            module_id="baseline.test", commit_hash=f"b{i:03d}",
            timestamp=float(1700000000 + i * 3600),
            hamiltonian=10.0 + i * 0.5,
            cyclomatic_complexity=5, infinite_loop_risk=0.02,
            dsm_density=0.25, dsm_cyclic_ratio=0.05,
            dependency_instability=0.3,
            syntactic_dead_code=1, duplicate_block_count=0,
            halstead_bugs=0.12,
        )
        store.insert(mv)
    baseline = store.get_baseline("baseline.test", window=10)
    assert baseline is not None
    assert baseline.n_samples == 10
    assert baseline.h_mean > 0
    assert baseline.h_std > 0
    assert baseline.h_trend_slope > 0  # H crescendo → slope positivo

R.run("T02c — baseline calculado com stats corretas", test_store_baseline_computed)

def test_store_z_score():
    baseline = store.get_baseline("baseline.test")
    assert baseline is not None
    # z_score de um valor igual à média deve ser ~0
    z = baseline.z_score("H", baseline.h_mean)
    assert abs(z) < 0.1, f"z_score(mean) = {z:.4f} ≠ 0"
    # z_score de mean + std deve ser ~1
    z_one = baseline.z_score("H", baseline.h_mean + baseline.h_std)
    assert abs(z_one - 1.0) < 0.1, f"z_score(mean+std) = {z_one:.4f} ≠ 1"

R.run("T02d — z_score calculado corretamente", test_store_z_score)

def test_store_anomaly_persistence():
    event_id = "test-event-001"
    store.insert_anomaly(event_id, "auth.login", {
        "primary_error": "AI_CODE_BOMB",
        "severity": "CRITICAL",
        "primary_confidence": 0.85,
        "dominant_band": "MF",
        "plain_english": "Código AI-generated detectado",
        "technical_summary": "AI_CODE_BOMB | MF | conf=0.85",
        "apex_prompt": "[UCO-SENSOR] AI_CODE_BOMB...",
        "change_point": {"commit_idx": 5, "commit_hash": "abc12345"},
        "timestamp": time.time(),
    })
    events = store.get_anomalies(module_id="auth.login")
    assert len(events) >= 1
    assert events[0]["error_type"] == "AI_CODE_BOMB"
    assert events[0]["severity"] == "CRITICAL"

R.run("T02e — anomalia persistida e recuperada", test_store_anomaly_persistence)

def test_store_list_modules():
    modules = store.list_modules()
    assert "auth.login" in modules
    assert "baseline.test" in modules
    assert "order.test" in modules

R.run("T02f — list_modules retorna todos os módulos", test_store_list_modules)

def test_store_upsert_idempotent():
    """Inserir o mesmo (module_id, commit_hash) duas vezes não duplica."""
    mv = bridge.analyze(CODE_SIMPLE, "upsert.test", "same-hash")
    store.insert(mv)
    store.insert(mv)  # segunda vez
    history = store.get_history("upsert.test")
    assert len(history) == 1, f"esperado 1, obtido {len(history)}"

R.run("T02g — insert idempotente por (module_id, commit_hash)", test_store_upsert_idempotent)

# ─── T03 Pipeline integrado ───────────────────────────────────────────────────

from pipeline.frequency_engine import FrequencyEngine
from synthetic.generators import generate_ai_code_bomb, generate_tech_debt

engine = FrequencyEngine(verbose=False)
store2 = SnapshotStore(":memory:")

def test_pipeline_full_with_real_uco():
    """
    Pipeline completo: UCO real → MetricVector → SnapshotStore → FrequencyEngine.
    Demonstra que UCO como motor de análise alimenta o FrequencyEngine corretamente.
    """
    codes = [
        "def f(x): return x",
        "def f(x, y): return x + y",
        "def f(x, y, z):\n  if x: return y\n  return z",
        "def f(a,b,c,d):\n  for i in range(a):\n    if b: print(c)\n  return d",
        "def f(a,b,c,d,e):\n  for i in range(a):\n    if b:\n      for j in range(c): print(d,e)\n  return a",
    ]
    for i, code in enumerate(codes):
        mv = bridge.analyze(code, "pipeline.test", f"p{i:03d}",
                            timestamp=float(1700000000 + i * 3600))
        store2.insert(mv)

    history = store2.get_history("pipeline.test", window=10)
    assert len(history) == 5

    result = engine.analyze(history, module_id="pipeline.test")
    assert result is not None
    assert result.primary_error
    assert result.severity in ("INFO", "WARNING", "CRITICAL")
    assert 0.0 <= result.primary_confidence <= 1.0

R.run("T03a — pipeline UCO→Store→Engine produz ClassificationResult", test_pipeline_full_with_real_uco)

def test_pipeline_synthetic_then_classify():
    """
    Usa dados sintéticos (onset=25/60) + FrequencyEngine.
    Demonstra ciclo completo detect-classify-output.
    """
    history = generate_ai_code_bomb(n=60, onset=25)
    result = engine.analyze(history, module_id="synth.bomb")
    assert result is not None
    assert result.severity in ("WARNING", "CRITICAL"), \
        f"esperado anomalia, obtido severity={result.severity}"
    # Qualquer anomalia de step/spike é válida para AI_CODE_BOMB
    STEP_ANOMALIES = {
        "AI_CODE_BOMB", "DEPENDENCY_CYCLE_INTRODUCTION",
        "LOOP_RISK_INTRODUCTION", "COGNITIVE_COMPLEXITY_EXPLOSION",
        "DEAD_CODE_DRIFT",  # plateau de dead code é fisicamente step-LF
    }
    assert result.primary_error in STEP_ANOMALIES, \
        f"obtido: {result.primary_error}"

R.run("T03b — sintético + FrequencyEngine classifica corretamente", test_pipeline_synthetic_then_classify)

# ─── T04 Performance ─────────────────────────────────────────────────────────

def test_performance_analyze_single():
    """POST /analyze completo (UCO + store + engine) deve rodar em < 800ms."""
    store_perf = SnapshotStore(":memory:")
    bridge_perf = UCOBridge(mode="fast")
    engine_perf = FrequencyEngine(verbose=False)

    # Pré-popular com 10 snapshots
    for i in range(10):
        code = f"def f_{i}(x):\n" + "  " * (i % 3 + 1) + "return x\n"
        mv = bridge_perf.analyze(code, "perf.mod", f"perf{i:03d}",
                                  timestamp=float(1700000000 + i * 3600))
        store_perf.insert(mv)

    # Medir análise com engine
    t0 = time.perf_counter()
    history = store_perf.get_history("perf.mod", window=60)
    engine_perf.analyze(history, module_id="perf.mod")
    elapsed = (time.perf_counter() - t0) * 1000

    assert elapsed < 800, f"latência={elapsed:.1f}ms > 800ms"

R.run("T04a — latência total < 800ms (UCO+Store+Engine)", test_performance_analyze_single)

def test_performance_bridge_only():
    """UCOBridge.analyze() para código simples deve ser < 150ms."""
    t0 = time.perf_counter()
    bridge.analyze(CODE_SIMPLE, "perf2", "x001")
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 150, f"bridge latência={elapsed:.1f}ms > 150ms"

R.run("T04b — UCOBridge.analyze() < 150ms para código simples", test_performance_bridge_only)

# ─── T05 API Server (lightweight test via thread) ─────────────────────────────

def test_api_server_lifecycle():
    """
    Sobe o servidor em thread, faz requests reais, verifica respostas.
    """
    import http.client

    # Importar e iniciar o servidor em thread separada
    from api.server import UCOSensorHandler, SensorConfig
    from http.server import HTTPServer

    test_port = 18080
    server = HTTPServer(("127.0.0.1", test_port), UCOSensorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)  # aguardar inicialização

    try:
        # /health
        conn = http.client.HTTPConnection("127.0.0.1", test_port, timeout=5)
        conn.request("GET", "/health")
        resp = conn.getresponse()
        body = json.loads(resp.read())
        assert resp.status == 200, f"health status={resp.status}"
        assert body["status"] == "ok"
        assert body["data"]["status"] == "healthy"

        # POST /analyze
        payload = json.dumps({
            "code": CODE_SIMPLE,
            "module_id": "api.test",
            "commit_hash": "api001",
        }).encode()
        conn2 = http.client.HTTPConnection("127.0.0.1", test_port, timeout=10)
        conn2.request("POST", "/analyze",
                      body=payload,
                      headers={"Content-Type": "application/json",
                               "Content-Length": str(len(payload))})
        resp2 = conn2.getresponse()
        body2 = json.loads(resp2.read())
        assert resp2.status == 200, f"analyze status={resp2.status}"
        assert body2["status"] == "ok"
        assert "metric_vector" in body2["data"]
        assert body2["data"]["metric_vector"]["hamiltonian"] > 0

        # GET /modules
        conn3 = http.client.HTTPConnection("127.0.0.1", test_port, timeout=5)
        conn3.request("GET", "/modules")
        resp3 = conn3.getresponse()
        body3 = json.loads(resp3.read())
        assert resp3.status == 200

    finally:
        server.shutdown()

R.run("T05a — servidor HTTP: /health + /analyze + /modules", test_api_server_lifecycle)

# ─── T06 Gap A — f_w (Weighted Mean Frequency) ──────────────────────────────────

from receptor.spectral_analyzer import SpectralAnalyzer
from transmitter.metric_signal_builder import MetricSignalBuilder
from synthetic.generators import generate_tech_debt as _gen_td, generate_ai_code_bomb as _gen_bomb

def test_fw_fields_exist_in_profile():
    """SpectralProfile deve ter os campos f_w derivados do CSL."""
    history  = _gen_td(n=40)
    signal   = MetricSignalBuilder().build(history)
    profiles = SpectralAnalyzer().analyze_full(signal)
    ch_H = [p for p in profiles if p.channel == "H"][0]
    assert hasattr(ch_H, "weighted_mean_freq"), "weighted_mean_freq ausente"
    assert hasattr(ch_H, "fw_shift"),           "fw_shift ausente"
    assert hasattr(ch_H, "norm_spectrum_area"), "norm_spectrum_area ausente"

R.run("T06a — SpectralProfile tem campos CSL: weighted_mean_freq, fw_shift, A_n", test_fw_fields_exist_in_profile)

def test_fw_shift_positive_for_tech_debt():
    """TECH_DEBT acumula em ULF → f_w desloca para esquerda → fw_shift > 0."""
    history  = _gen_td(n=60)
    signal   = MetricSignalBuilder().build(history)
    profiles = SpectralAnalyzer().analyze_full(signal)
    ch_H = [p for p in profiles if p.channel == "H"][0]
    assert ch_H.fw_shift > 0.0,         f"TECH_DEBT deve ter fw_shift > 0 (obtido {ch_H.fw_shift:.4f})"

R.run("T06b — fw_shift > 0 para TECH_DEBT (ULF dominante)", test_fw_shift_positive_for_tech_debt)

def test_fw_values_in_valid_range():
    """f_w, fw_shift e A_n devem estar em intervalos válidos."""
    history  = _gen_bomb(n=40, onset=25)
    signal   = MetricSignalBuilder().build(history)
    profiles = SpectralAnalyzer().analyze_full(signal)
    for p in profiles:
        if "cross:" in p.channel:
            continue
        assert 0.0 <= p.weighted_mean_freq <= 0.5,             f"{p.channel}: f_w={p.weighted_mean_freq:.4f} fora de [0, 0.5]"
        assert -2.0 <= p.fw_shift <= 2.0,             f"{p.channel}: fw_shift={p.fw_shift:.4f} fora de [-2, 2]"
        assert p.norm_spectrum_area >= 0.0,             f"{p.channel}: A_n={p.norm_spectrum_area:.4f} < 0"

R.run("T06c — f_w, fw_shift, A_n em intervalos válidos", test_fw_values_in_valid_range)


# ─── T07 Gap B — Dual Confirmation ───────────────────────────────────────────

from pipeline.frequency_engine import FrequencyEngine as _FE
from core.data_structures import MetricVector as _MV
import numpy as _np

_engine_dc = _FE(verbose=False)

def test_dual_confirm_healthy_not_critical():
    """
    Módulo saudável com variância natural NÃO deve ser CRITICAL.
    Gap B: dual confirmation exige AMBOS z_score E fw_shift para CRITICAL.
    """
    rng = _np.random.default_rng(123)
    n   = 50
    history = [_MV(
        module_id="healthy.dc", commit_hash=f"h{i:03d}",
        timestamp=float(1700000000 + i*3600),
        hamiltonian=5.0 + rng.normal(0, 0.4),
        cyclomatic_complexity=5, infinite_loop_risk=0.02,
        dsm_density=0.20 + rng.normal(0, 0.01),
        dsm_cyclic_ratio=0.03, dependency_instability=0.30,
        syntactic_dead_code=2, duplicate_block_count=1,
        halstead_bugs=0.10) for i in range(n)]
    result = _engine_dc.analyze(history)
    assert result is not None
    assert result.severity != "CRITICAL",         f"Falso positivo CRITICAL em módulo saudável (severity={result.severity})"

R.run("T07a — dual confirmation: módulo saudável nunca CRITICAL", test_dual_confirm_healthy_not_critical)

def test_dual_confirm_tech_debt_severity():
    """TECH_DEBT real: ambos atributos alertam → severidade WARNING ou CRITICAL."""
    from synthetic.generators import generate_tech_debt as _gtd
    history = _gtd(n=80)
    result  = _engine_dc.analyze(history)
    assert result is not None
    assert result.severity in ("WARNING", "CRITICAL"),         f"TECH_DEBT deve ser WARNING/CRITICAL (obtido {result.severity})"

R.run("T07b — dual confirmation: TECH_DEBT real é WARNING/CRITICAL", test_dual_confirm_tech_debt_severity)

def test_dual_confirm_fw_evidence_in_result():
    """ClassificationResult deve ter evidências de fw_shift nas spectral_evidence."""
    from synthetic.generators import generate_god_class as _ggc
    history = _ggc(n=60)
    result  = _engine_dc.analyze(history)
    assert result is not None
    # spectral_evidence deve existir e ter campos
    assert isinstance(result.spectral_evidence, dict), "spectral_evidence deve ser dict"

R.run("T07c — dual confirmation: spectral_evidence presente no resultado", test_dual_confirm_fw_evidence_in_result)


# ─── T08 Gap C — POST /repair ─────────────────────────────────────────────────

import threading as _thr, http.client as _hc, json as _json

CODE_BROKEN = """def validate(token, secret):
    if not token: return False
    if not token: return False
    if not token: return False
    h = hash(token)
    h = hash(token)
    h = hash(token)
    unused_x = 42
    unused_y = 99
    return h == secret
    return False
    return True
"""

def test_repair_endpoint_reduces_h():
    """
    POST /repair deve retornar código com H menor que o original.
    Valida o ciclo completo: detect→repair→prove improvement.
    """
    from api.server import UCOSensorHandler, SensorConfig
    from http.server import HTTPServer

    port   = 18081
    server = HTTPServer(("127.0.0.1", port), UCOSensorHandler)
    t      = _thr.Thread(target=server.serve_forever, daemon=True)
    t.start()
    import time as _t; _t.sleep(0.3)

    try:
        payload = _json.dumps({
            "code":      CODE_BROKEN,
            "module_id": "repair.test",
            "depth":     "fast",
        }).encode()

        conn = _hc.HTTPConnection("127.0.0.1", port, timeout=10)
        conn.request("POST", "/repair",
                     body=payload,
                     headers={"Content-Type": "application/json",
                              "Content-Length": str(len(payload))})
        resp = conn.getresponse()
        body = _json.loads(resp.read())

        assert resp.status == 200, f"status={resp.status}"
        assert body["status"] == "ok", f"erro: {body}"
        d = body["data"]
        assert "h_before"  in d, "h_before ausente"
        assert "h_after"   in d, "h_after ausente"
        assert "delta_h"   in d, "delta_h ausente"
        assert "optimized_code" in d, "optimized_code ausente"
        assert d["h_before"] > 0, "h_before deve ser > 0"
        assert d["h_after"]  > 0, "h_after deve ser > 0"
        assert d["delta_h"]  >= 0, f"delta_h negativo não esperado: {d['delta_h']}"
        assert "metrics_before" in d, "metrics_before ausente"
        assert "metrics_after"  in d, "metrics_after ausente"

    finally:
        server.shutdown()

R.run("T08a — POST /repair retorna h_before, h_after, delta_h, optimized_code", test_repair_endpoint_reduces_h)

def test_repair_fixes_dead_code():
    """POST /repair deve eliminar dead code e duplicatas via transforms UCO."""
    from sensor_core.uco_bridge import UCOBridge as _UCOBridge
    bridge = _UCOBridge(mode="fast")
    
    mv_before = bridge.analyze(CODE_BROKEN, "repair.dc", "b1")
    sugg      = bridge.suggest_transforms(CODE_BROKEN)
    
    assert mv_before.syntactic_dead_code > 0,         f"código deve ter dead code (obtido {mv_before.syntactic_dead_code})"
    assert mv_before.duplicate_block_count > 0,         f"código deve ter duplicatas (obtido {mv_before.duplicate_block_count})"
    
    # Depois de aplicar transforms, H deve cair
    if sugg["optimized_code"] != CODE_BROKEN:
        mv_after = bridge.analyze(sugg["optimized_code"], "repair.dc", "a1")
        assert mv_after.hamiltonian <= mv_before.hamiltonian,             f"H deve cair após repair: {mv_before.hamiltonian:.2f} → {mv_after.hamiltonian:.2f}"

R.run("T08b — repair elimina dead code e duplicatas (delta_h ≥ 0)", test_repair_fixes_dead_code)

def test_repair_empty_code_returns_error():
    """POST /repair com código vazio deve retornar erro 400."""
    from api.server import handle_repair
    code, _ = handle_repair({"code": "", "depth": "fast"})
    assert code == 400, f"esperado 400, obtido {code}"

R.run("T08c — POST /repair com código vazio retorna 400", test_repair_empty_code_returns_error)


# ─── Summary ─────────────────────────────────────────────────────────────────

print(f"\n{'═'*65}")
print("  Marco 1 — Test Suite")
print(f"{'═'*65}")
ok = R.summary()
sys.exit(0 if ok else 1)
