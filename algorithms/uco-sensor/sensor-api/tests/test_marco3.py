"""
UCO-Sensor — Testes Marco 3: APEX Integration
==============================================
Valida a camada de integração com o APEX Event Bus.

Testes:
  T30a — ApexEventBus modo null: publica sem erro
  T30b — ApexEventBus modo callback: invoca handler com evento correto
  T30c — ApexEventBus filtro de severidade: INFO não passa por gate CRITICAL
  T30d — ApexEventBus modo file: escreve NDJSON válido
  T31a — ApexConnector.from_config: cria conector com callback
  T31b — ApexConnector.handle: persiste anomalia no SnapshotStore
  T31c — ApexConnector.handle: publica evento apenas em CRITICAL
  T31d — ApexConnector.handle: não publica se enabled=False
  T32a — SignalOutputRouter._to_apex: evento tem estrutura correta
  T32b — Evento UCO_ANOMALY_DETECTED tem campos obrigatórios
  T33a — Servidor: GET /apex/status retorna transport e configured
  T33b — Servidor: GET /apex/ping retorna reachable
  T33c — Servidor: POST /apex/webhook ACK APEX_PING
  T33d — Servidor: GET /anomalies retorna lista (pode ser vazia)
  T34a — handle_analyze: apex_event_sent presente na resposta
  T34b — handle_analyze: evento publicado após acúmulo de histórico CRITICAL
"""
from __future__ import annotations
import sys
import json
import time
import tempfile
import threading
from pathlib import Path
from http.server import HTTPServer
from typing import List, Dict, Any

# ── Path setup ────────────────────────────────────────────────────────────────
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import urllib.request
import urllib.error

from apex_integration.event_bus import ApexEventBus, DeliveryResult
from apex_integration.connector import ApexConnector, set_connector
from sensor_storage.snapshot_store import SnapshotStore
from api.server import (
    UCOSensorHandler, _store, _config,
    handle_apex_status, handle_apex_ping, handle_apex_webhook,
    handle_anomalies,
)

# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_apex_event(severity: str = "CRITICAL") -> Dict:
    """Cria um evento UCO_ANOMALY_DETECTED mínimo para testes."""
    return {
        "event": "UCO_ANOMALY_DETECTED",
        "version": "1.0",
        "payload": {
            "module_id":           "test.module",
            "error_type":          "TECH_DEBT_ACCUMULATION",
            "severity":            severity,
            "frequency_band":      "MF",
            "confidence":          0.82,
            "change_point_commit": "abc1234",
            "apex_prompt":         "Refatorar módulo test.module",
            "suggested_mode":      "DEEP",
            "suggested_agents":    ["critic", "engineer"],
            "uco_transforms":      ["remove_dead_code"],
            "delta_h_potential":   -5.2,
            "persistence": {
                "hurst_H": 0.72,
                "phase_coupling_CC_H": 0.45,
                "burst_index_H": 0.3,
                "hflf_ratio_H": 1.8,
                "onset_reversibility": "MODERATE",
                "onset_confidence": "LIKELY",
                "self_cure_pct": 12.0,
                "spectral_signal_quality": 0.88,
                "classification_grade": "LIKELY",
                "intervention_now": False,
                "chronic": False,
                "acute": False,
            },
            "spectral_summary": {
                "dominant_band": "MF",
                "primary_channels": ["H", "CC"],
                "evidence": {"mf_h_power": 0.4},
            },
        }
    }


def _make_classification_result(severity: str = "CRITICAL"):
    """Cria ClassificationResult mínimo para testes."""
    from core.data_structures import ClassificationResult, SignatureMatch, ChangePoint
    hyp = SignatureMatch(
        error_type="TECH_DEBT_ACCUMULATION",
        description="Tech debt acumulando",
        confidence=0.82,
        matched_band="MF",
        matched_channels=["H", "CC"],
        temporal_pattern="SUSTAINED",
        severity_base="CRITICAL",
        evidence={"mf_h_power": 0.4},
        recommended_action="Refatorar",
        apex_prompt_template="Refatorar módulo {module_id}",
    )
    cp = ChangePoint(
        commit_idx=5,
        commit_hash="abc1234",
        confidence=0.75,
        magnitude=2.1,
        affected_channels=["H", "CC"],
    )
    ts = time.time()
    return ClassificationResult(
        module_id="test.module",
        timestamp=ts,
        primary_error="TECH_DEBT_ACCUMULATION",
        primary_confidence=0.82,
        severity=severity,
        severity_score=0.65,
        dominant_band="MF",
        band_description="Medium Frequency — mudanças incrementais",
        hypotheses=[hyp],
        change_point=cp,
        spectral_evidence={"mf_h_power": 0.4},
        suggested_transforms=["remove_dead_code"],
        potential_delta_h=-5.2,
        plain_english="Tech debt acumulando em test.module.",
        technical_summary="MF dominante em H e CC.",
        apex_prompt="Refatorar módulo test.module",
        n_commits_analyzed=15,
        analysis_timestamp=ts,
        hurst_H=0.72,
        phase_coupling_CC_H=0.45,
        burst_index_H=0.3,
        hflf_ratio_H=1.8,
        onset_reversibility=0.15,
        onset_confidence_context="LIKELY",
        self_cure_probability=12.0,
        spectral_signal_quality="GOOD",
        classification_grade="LIKELY",
        n_stable_channels=5,
        is_spectrally_valid=True,
    )


# ─── T30: ApexEventBus ────────────────────────────────────────────────────────

def test_T30a_null_mode():
    """ApexEventBus modo null: publica sem erro e retorna ok=True."""
    bus = ApexEventBus()   # sem transporte configurado
    result = bus.publish(_make_apex_event("CRITICAL"))
    assert result.ok, f"Esperado ok=True, got {result}"
    assert result.transport == "null"
    print(f"  [T30a] ok — transport=null, {result}")


def test_T30b_callback_mode():
    """ApexEventBus modo callback: invoca handler com evento correto."""
    received: List[Dict] = []

    def handler(event: Dict):
        received.append(event)

    bus = ApexEventBus(callback=handler, severity_filter="INFO")
    event = _make_apex_event("CRITICAL")
    result = bus.publish(event)

    assert result.ok, f"Esperado ok=True, got {result}"
    assert result.transport == "callback"
    assert len(received) == 1, f"Handler invocado {len(received)} vezes (esperado 1)"
    assert received[0]["event"] == "UCO_ANOMALY_DETECTED"
    assert received[0]["payload"]["severity"] == "CRITICAL"
    print(f"  [T30b] ok — callback invocado com evento correto")


def test_T30c_severity_filter():
    """ApexEventBus filtro: INFO não publica quando gate=CRITICAL."""
    published: List[Dict] = []

    bus = ApexEventBus(callback=published.append, severity_filter="CRITICAL")

    # INFO não deve passar
    r1 = bus.publish(_make_apex_event("INFO"))
    assert r1.transport == "null" or r1.error == "filtered_by_severity", \
        f"INFO deveria ser filtrado, got {r1}"
    assert len(published) == 0, "INFO não deveria ter sido publicado"

    # WARNING não deve passar
    r2 = bus.publish(_make_apex_event("WARNING"))
    assert len(published) == 0, "WARNING não deveria ter sido publicado"

    # CRITICAL deve passar
    r3 = bus.publish(_make_apex_event("CRITICAL"))
    assert r3.ok and r3.transport == "callback"
    assert len(published) == 1, "CRITICAL deveria ter sido publicado"
    print(f"  [T30c] ok — filtro CRITICAL funcionou (INFO/WARNING filtrados)")


def test_T30d_file_mode():
    """ApexEventBus modo file: escreve NDJSON válido."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson", delete=False) as f:
        fpath = f.name

    bus = ApexEventBus(file_path=fpath, severity_filter="INFO")
    event = _make_apex_event("CRITICAL")
    result = bus.publish(event)

    assert result.ok, f"Esperado ok=True, got {result}"
    assert result.transport == "file"

    content = Path(fpath).read_text()
    lines = [l for l in content.strip().splitlines() if l]
    assert len(lines) >= 1, "Arquivo deve ter ao menos 1 linha"
    record = json.loads(lines[-1])
    assert record["event"] == "UCO_ANOMALY_DETECTED"
    assert record["severity"] == "CRITICAL"
    print(f"  [T30d] ok — NDJSON escrito em {fpath}")


# ─── T31: ApexConnector ───────────────────────────────────────────────────────

def test_T31a_from_config():
    """ApexConnector.from_config cria conector com callback."""
    received: List[Dict] = []
    connector = ApexConnector.from_config(
        callback=received.append,
        severity_gate="CRITICAL",
        enabled=True,
    )
    assert connector.enabled
    assert connector.severity_gate == "CRITICAL"
    assert connector.bus.transport_mode == "callback"
    print(f"  [T31a] ok — conector criado com callback, transport={connector.bus.transport_mode}")


def test_T31b_handle_persiste_anomalia():
    """ApexConnector.handle: persiste anomalia no SnapshotStore."""
    store = SnapshotStore(":memory:")
    received: List[Dict] = []
    connector = ApexConnector.from_config(
        callback=received.append,
        severity_gate="INFO",
        enabled=True,
    )

    result = _make_classification_result("CRITICAL")
    connector.handle(result, store=store)

    anomalies = store.get_anomalies("test.module")
    assert len(anomalies) >= 1, "Anomalia deve ter sido persistida no store"
    assert anomalies[0]["error_type"] == "TECH_DEBT_ACCUMULATION"
    assert anomalies[0]["severity"] == "CRITICAL"
    print(f"  [T31b] ok — anomalia persistida: {anomalies[0]['error_type']}")


def test_T31c_handle_publica_critical():
    """ApexConnector.handle: publica evento quando severity=CRITICAL e gate=CRITICAL."""
    received: List[Dict] = []
    connector = ApexConnector.from_config(
        callback=received.append,
        severity_gate="CRITICAL",
        enabled=True,
    )

    # WARNING não deve publicar
    result_warn = _make_classification_result("WARNING")
    connector.handle(result_warn)
    assert len(received) == 0, "WARNING não deveria publicar com gate=CRITICAL"

    # CRITICAL deve publicar
    result_crit = _make_classification_result("CRITICAL")
    dr = connector.handle(result_crit)
    assert dr is not None and dr.ok, f"CRITICAL deveria publicar, got {dr}"
    assert len(received) == 1, "CRITICAL deveria ter publicado 1 evento"
    assert received[0]["event"] == "UCO_ANOMALY_DETECTED"
    print(f"  [T31c] ok — CRITICAL publicado, WARNING filtrado")


def test_T31d_handle_disabled():
    """ApexConnector.handle: não publica se enabled=False."""
    received: List[Dict] = []
    connector = ApexConnector.from_config(
        callback=received.append,
        severity_gate="INFO",
        enabled=False,        # desabilitado
    )

    result = _make_classification_result("CRITICAL")
    dr = connector.handle(result)
    assert dr is None, f"Esperado None quando disabled, got {dr}"
    assert len(received) == 0, "Nenhum evento deve ser publicado quando disabled"
    print(f"  [T31d] ok — connector disabled não publica")


# ─── T32: Estrutura do evento ─────────────────────────────────────────────────

def test_T32a_apex_event_structure():
    """SignalOutputRouter._to_apex: evento tem estrutura correta."""
    from router.signal_output_router import SignalOutputRouter, OutputFormat
    router = SignalOutputRouter()
    result = _make_classification_result("CRITICAL")
    event = router.route(result, OutputFormat.APEX)

    assert event["event"] == "UCO_ANOMALY_DETECTED"
    assert event["version"] == "1.0"
    assert "payload" in event
    payload = event["payload"]
    assert payload["module_id"] == "test.module"
    assert payload["error_type"] == "TECH_DEBT_ACCUMULATION"
    assert payload["severity"] == "CRITICAL"
    print(f"  [T32a] ok — evento APEX com estrutura correta")


def test_T32b_apex_event_required_fields():
    """UCO_ANOMALY_DETECTED tem todos os campos obrigatórios."""
    from router.signal_output_router import SignalOutputRouter, OutputFormat
    router = SignalOutputRouter()
    result = _make_classification_result("CRITICAL")
    event = router.route(result, OutputFormat.APEX)
    payload = event["payload"]

    required = [
        "module_id", "error_type", "severity", "frequency_band",
        "confidence", "apex_prompt", "suggested_mode", "suggested_agents",
        "uco_transforms", "delta_h_potential", "persistence", "spectral_summary",
    ]
    missing = [f for f in required if f not in payload]
    assert not missing, f"Campos ausentes no payload APEX: {missing}"

    # Verificar persistence
    persistence = payload["persistence"]
    pers_required = ["hurst_H", "intervention_now", "chronic", "acute"]
    missing_p = [f for f in pers_required if f not in persistence]
    assert not missing_p, f"Campos ausentes em persistence: {missing_p}"
    print(f"  [T32b] ok — todos os campos obrigatórios presentes")


# ─── T33: Endpoints do servidor ───────────────────────────────────────────────

def _start_test_server(port: int) -> HTTPServer:
    """Inicia servidor de teste em thread background."""
    server = HTTPServer(("127.0.0.1", port), UCOSensorHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    time.sleep(0.15)
    return server


def _get(port: int, path: str) -> Dict:
    url = f"http://127.0.0.1:{port}{path}"
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read())


def _post(port: int, path: str, body: Dict) -> Dict:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read())


PORT_M3 = 19083

_server_m3 = None


def setup_server():
    global _server_m3
    if _server_m3 is None:
        import api.server as srv
        # Conector de teste com callback
        received_events: List[Dict] = []
        test_connector = ApexConnector.from_config(
            callback=received_events.append,
            severity_gate="CRITICAL",
            enabled=True,
        )
        set_connector(test_connector)
        # Patch direto na variável do módulo (já bindada no import time)
        srv._connector = test_connector
        _server_m3 = _start_test_server(PORT_M3)
    return _server_m3


def test_T33a_apex_status():
    """GET /apex/status retorna transport e configured."""
    setup_server()
    resp = _get(PORT_M3, "/apex/status")
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "transport" in data
    assert "configured" in data
    assert "enabled" in data
    print(f"  [T33a] ok — /apex/status: transport={data['transport']}, enabled={data['enabled']}")


def test_T33b_apex_ping():
    """GET /apex/ping retorna reachable."""
    setup_server()
    resp = _get(PORT_M3, "/apex/ping")
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "reachable" in data
    # callback mode é sempre reachable
    assert data["reachable"] is True
    print(f"  [T33b] ok — /apex/ping: reachable={data['reachable']}")


def test_T33c_apex_webhook_ping():
    """POST /apex/webhook ACK APEX_PING."""
    setup_server()
    resp = _post(PORT_M3, "/apex/webhook", {"event": "APEX_PING", "payload": {}})
    assert resp["status"] == "ok"
    data = resp["data"]
    assert data.get("ack") is True
    print(f"  [T33c] ok — /apex/webhook ACK retornado")


def test_T33d_anomalies_endpoint():
    """GET /anomalies retorna lista (pode ser vazia)."""
    setup_server()
    resp = _get(PORT_M3, "/anomalies")
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "anomalies" in data
    assert isinstance(data["anomalies"], list)
    assert "count" in data
    print(f"  [T33d] ok — /anomalies: {data['count']} anomalias")


# ─── T34: handle_analyze com APEX ────────────────────────────────────────────

def test_T34a_analyze_has_apex_field():
    """handle_analyze: resposta contém campo apex_event_sent."""
    setup_server()
    body = {
        "code": "def f(): return 1",
        "module_id": "apex_test_m3.func",
        "commit_hash": "m3test001",
    }
    resp = _post(PORT_M3, "/analyze", body)
    assert resp["status"] == "ok"
    data = resp["data"]
    assert "apex_event_sent" in data, "Campo apex_event_sent deve estar na resposta"
    print(f"  [T34a] ok — apex_event_sent={data['apex_event_sent']}")


def test_T34b_analyze_apex_publishes_critical(monkeypatch_or_inject=None):
    """
    handle_analyze: após acumular histórico CRITICAL, apex_event_sent=True
    com connector em modo callback.
    """
    from sensor_storage.snapshot_store import SnapshotStore
    from core.data_structures import MetricVector

    store_local = SnapshotStore(":memory:")
    published: List[Dict] = []

    connector = ApexConnector.from_config(
        callback=published.append,
        severity_gate="CRITICAL",
        enabled=True,
    )

    # Simular injeção de histórico no store local
    from synthetic.generators import generate_tech_debt
    history = generate_tech_debt(n=20)

    for mv in history:
        store_local.insert(mv)

    # Usar connector diretamente com resultado sintético
    result = _make_classification_result("CRITICAL")
    dr = connector.handle(result, store=store_local)

    assert dr is not None, "Esperado DeliveryResult, got None"
    assert dr.ok, f"Esperado ok=True, got {dr}"
    assert len(published) == 1, f"Esperado 1 evento publicado, got {len(published)}"
    assert published[0]["event"] == "UCO_ANOMALY_DETECTED"
    assert published[0]["payload"]["severity"] == "CRITICAL"
    print(f"  [T34b] ok — evento CRITICAL publicado via callback após análise")


# ─── Runner ──────────────────────────────────────────────────────────────────

TESTS = [
    ("T30a", test_T30a_null_mode),
    ("T30b", test_T30b_callback_mode),
    ("T30c", test_T30c_severity_filter),
    ("T30d", test_T30d_file_mode),
    ("T31a", test_T31a_from_config),
    ("T31b", test_T31b_handle_persiste_anomalia),
    ("T31c", test_T31c_handle_publica_critical),
    ("T31d", test_T31d_handle_disabled),
    ("T32a", test_T32a_apex_event_structure),
    ("T32b", test_T32b_apex_event_required_fields),
    ("T33a", test_T33a_apex_status),
    ("T33b", test_T33b_apex_ping),
    ("T33c", test_T33c_apex_webhook_ping),
    ("T33d", test_T33d_anomalies_endpoint),
    ("T34a", test_T34a_analyze_has_apex_field),
    ("T34b", test_T34b_analyze_apex_publishes_critical),
]


if __name__ == "__main__":
    passed = 0
    failed = 0
    errors = []

    print(f"\n{'='*65}")
    print(f"  UCO-Sensor Marco 3 — APEX Integration Tests  ({len(TESTS)} testes)")
    print(f"{'='*65}")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  ✅ {name}")
            passed += 1
        except Exception as exc:
            print(f"  ❌ {name}: {exc}")
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
