"""
UCO-Sensor — ApexConnector
============================
Liga o FrequencyEngine ao ApexEventBus.

Responsabilidades:
  1. Receber ClassificationResult do FrequencyEngine
  2. Formatar como evento UCO_ANOMALY_DETECTED via SignalOutputRouter
  3. Persistir anomalia no SnapshotStore
  4. Publicar no ApexEventBus se severity >= threshold

Pipeline:
  FrequencyEngine.analyze(history)
    → ClassificationResult
    → ApexConnector.handle(result, store)
      → SignalOutputRouter._to_apex()
      → SnapshotStore.insert_anomaly()
      → ApexEventBus.publish()
      → DeliveryResult

Uso:
    connector = ApexConnector.from_env()   # configura via env vars
    connector.handle(result, store)

Variáveis de ambiente:
    APEX_WEBHOOK_URL    — URL do endpoint APEX (obrigatória para webhook)
    APEX_API_KEY        — API key APEX (opcional)
    APEX_EVENTS_FILE    — arquivo NDJSON local (alternativa ao webhook)
    APEX_SEVERITY       — filtro mínimo: "INFO"|"WARNING"|"CRITICAL" (default: CRITICAL)
    UCO_APEX_ENABLED    — "1" para ativar (default: "0")
"""
from __future__ import annotations
import os
import time
import uuid
from typing import Optional, Dict, Any

import sys
from pathlib import Path

# Adicionar frequency-engine ao path
_SENSOR = Path(__file__).resolve().parent.parent
_ENGINE = _SENSOR.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from router.signal_output_router import SignalOutputRouter, OutputFormat
from core.data_structures import ClassificationResult
from .event_bus import ApexEventBus, DeliveryResult


class ApexConnector:
    """
    Conector entre FrequencyEngine e APEX Event Bus.

    Parâmetros
    ----------
    bus           : ApexEventBus configurado
    enabled       : False = passa silenciosamente sem publicar
    severity_gate : Severidade mínima para publicar ("CRITICAL" padrão)
    """

    def __init__(
        self,
        bus: ApexEventBus,
        enabled: bool = True,
        severity_gate: str = "CRITICAL",
    ):
        self.bus           = bus
        self.enabled       = enabled
        self.severity_gate = severity_gate
        self._router       = SignalOutputRouter()

    # ── Factory: from environment ─────────────────────────────────────────────

    @classmethod
    def from_env(cls) -> "ApexConnector":
        """
        Cria ApexConnector a partir de variáveis de ambiente.

        UCO_APEX_ENABLED=1 é obrigatório para ativar.
        Sem ele, retorna conector em modo null (não publica).
        """
        enabled = os.environ.get("UCO_APEX_ENABLED", "0") == "1"

        webhook_url  = os.environ.get("APEX_WEBHOOK_URL", "")
        api_key      = os.environ.get("APEX_API_KEY", "")
        events_file  = os.environ.get("APEX_EVENTS_FILE", "")
        severity     = os.environ.get("APEX_SEVERITY", "CRITICAL").upper()

        bus = ApexEventBus(
            webhook_url    = webhook_url or None,
            api_key        = api_key or None,
            file_path      = events_file or None,
            severity_filter = severity,
            timeout_s      = float(os.environ.get("APEX_TIMEOUT_S", "10")),
            max_retries    = int(os.environ.get("APEX_MAX_RETRIES", "3")),
        )

        return cls(bus=bus, enabled=enabled, severity_gate=severity)

    # ── Factory: from explicit config ────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        webhook_url:    Optional[str] = None,
        api_key:        Optional[str] = None,
        events_file:    Optional[str] = None,
        severity_gate:  str           = "CRITICAL",
        enabled:        bool          = True,
        callback = None,
    ) -> "ApexConnector":
        """
        Cria ApexConnector com configuração explícita.

        Ideal para testes e uso programático.
        """
        bus = ApexEventBus(
            webhook_url    = webhook_url,
            api_key        = api_key,
            file_path      = events_file,
            callback       = callback,
            severity_filter = severity_gate,
        )
        return cls(bus=bus, enabled=enabled, severity_gate=severity_gate)

    # ── Handle result ─────────────────────────────────────────────────────────

    def handle(
        self,
        result: ClassificationResult,
        store=None,            # SnapshotStore opcional — para persistir anomalia
    ) -> Optional[DeliveryResult]:
        """
        Processa ClassificationResult pós-FrequencyEngine.

        1. Formata evento APEX via SignalOutputRouter
        2. Persiste no SnapshotStore (se fornecido)
        3. Publica no ApexEventBus (se habilitado e severity >= gate)

        Parâmetros
        ----------
        result : ClassificationResult do FrequencyEngine
        store  : SnapshotStore (opcional) — se fornecido, persiste a anomalia

        Retorna
        -------
        DeliveryResult se houve tentativa de publicação, None caso contrário.
        """
        if not result:
            return None

        # Formatar evento APEX
        apex_event = self._router.route(result, OutputFormat.APEX)

        # Persistir anomalia no store
        if store is not None:
            try:
                event_id = f"uco_{result.module_id}_{int(result.analysis_timestamp)}_{uuid.uuid4().hex[:8]}"
                cp = result.change_point
                store.insert_anomaly(
                    event_id=event_id,
                    module_id=result.module_id,
                    data={
                        "primary_error":      result.primary_error,
                        "severity":           result.severity,
                        "primary_confidence": result.primary_confidence,
                        "dominant_band":      result.dominant_band,
                        "plain_english":      result.plain_english,
                        "technical_summary":  result.technical_summary,
                        "apex_prompt":        result.apex_prompt,
                        "change_point": {
                            "commit_idx":  cp.commit_idx if cp else None,
                            "commit_hash": cp.commit_hash if cp else None,
                        } if cp else None,
                        "timestamp": result.analysis_timestamp,
                    },
                )
            except Exception:
                pass   # persistência nunca quebra o fluxo

        # Verificar gate de severidade antes de publicar
        if not self.enabled:
            return None

        sev_order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
        min_level = sev_order.get(self.severity_gate, 2)
        evt_level = sev_order.get(result.severity, 0)
        if evt_level < min_level:
            return None

        # Publicar
        return self.bus.publish(apex_event)

    # ── Status ────────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """Retorna status da integração APEX."""
        return {
            "enabled":       self.enabled,
            "severity_gate": self.severity_gate,
            "transport":     self.bus.transport_mode,
            "configured":    self.bus.is_configured,
            "bus_stats":     self.bus.stats(),
        }

    def ping(self) -> bool:
        """Testa conectividade com o APEX."""
        return self.bus.ping()


# ─── Singleton global ─────────────────────────────────────────────────────────

_CONNECTOR: Optional[ApexConnector] = None


def get_connector() -> ApexConnector:
    """
    Retorna o ApexConnector global (singleton lazy).

    Na primeira chamada, inicializa via variáveis de ambiente.
    Pode ser substituído com set_connector() para testes.
    """
    global _CONNECTOR
    if _CONNECTOR is None:
        _CONNECTOR = ApexConnector.from_env()
    return _CONNECTOR


def set_connector(connector: ApexConnector) -> None:
    """Substitui o connector global (para testes)."""
    global _CONNECTOR
    _CONNECTOR = connector
