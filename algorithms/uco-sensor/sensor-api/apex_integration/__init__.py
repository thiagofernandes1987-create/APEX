"""
UCO-Sensor — APEX Integration
================================
Publicação de eventos UCO_ANOMALY_DETECTED para o APEX Event Bus.

Exporta:
  ApexEventBus   — cliente HTTP que publica eventos para o APEX
  ApexConnector  — liga FrequencyEngine → ApexEventBus automaticamente
  get_connector  — singleton global do conector
"""
from .event_bus import ApexEventBus, DeliveryResult
from .connector import ApexConnector, get_connector

__all__ = [
    "ApexEventBus",
    "DeliveryResult",
    "ApexConnector",
    "get_connector",
]
