"""
UCO-Sensor — ApexEventBus
===========================
Cliente que publica eventos UCO_ANOMALY_DETECTED para o APEX.

Modos de transporte suportados:
  webhook   — POST HTTP para URL configurada (SaaS, servidor remoto)
  callback  — chama função Python registrada (co-localizado no mesmo processo)
  file      — escreve NDJSON em arquivo/fila (CI, debug, dry-run)
  null      — descarta silenciosamente (testes, modo dev)

Resilência:
  • Retry com backoff exponencial (configurável)
  • Timeout por requisição
  • Falha silenciosa — UCO Sensor nunca quebra por falha no APEX
  • Log de entrega em SnapshotStore.insert_anomaly()

Uso mínimo:
    bus = ApexEventBus(webhook_url="https://apex.mycompany.com/events")
    result = bus.publish(apex_event_dict)
    # → DeliveryResult(ok=True, transport="webhook", ...)

Uso co-localizado (APEX + UCO no mesmo processo):
    def my_handler(event: dict): ...
    bus = ApexEventBus(callback=my_handler)
    bus.publish(apex_event_dict)
"""
from __future__ import annotations
import json
import time
import urllib.request
import urllib.error
import threading
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path


# ─── Resultado de entrega ────────────────────────────────────────────────────

@dataclass
class DeliveryResult:
    ok:          bool
    transport:   str                      # "webhook" | "callback" | "file" | "null"
    event_type:  str = ""
    module_id:   str = ""
    severity:    str = ""
    status_code: Optional[int] = None    # HTTP status (webhook only)
    error:       Optional[str] = None
    latency_ms:  float = 0.0
    attempts:    int = 1

    def __repr__(self) -> str:
        if self.ok:
            return (f"<DeliveryResult ok transport={self.transport} "
                    f"module={self.module_id} severity={self.severity} "
                    f"latency={self.latency_ms:.0f}ms>")
        return (f"<DeliveryResult FAIL transport={self.transport} "
                f"error={self.error!r} attempts={self.attempts}>")


# ─── ApexEventBus ─────────────────────────────────────────────────────────────

class ApexEventBus:
    """
    Publica eventos UCO_ANOMALY_DETECTED para o APEX.

    Parâmetros
    ----------
    webhook_url   : URL do endpoint APEX que recebe eventos POST.
                    Ex: "https://apex.mycompany.com/api/events"
    api_key       : API key APEX para autenticação (opcional).
    callback      : Callable Python invocado com o dict do evento.
                    Usado quando UCO Sensor e APEX rodam no mesmo processo.
    file_path     : Caminho de arquivo NDJSON para persistência local.
                    Útil para CI/CD e dry-run.
    severity_filter: Publica apenas eventos com severity >= este nível.
                    "INFO" | "WARNING" | "CRITICAL"  (default: "CRITICAL")
    timeout_s     : Timeout em segundos por requisição HTTP (default: 10).
    max_retries   : Tentativas antes de desistir (default: 3).
    retry_delay_s : Delay base do backoff exponencial (default: 1.0).

    Modo null:
        Se nenhum transport estiver configurado, descarta eventos silenciosamente.
        Útil em dev/test para não exigir APEX running.
    """

    SEVERITY_ORDER = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}

    def __init__(
        self,
        webhook_url:    Optional[str]      = None,
        api_key:        Optional[str]      = None,
        callback:       Optional[Callable] = None,
        file_path:      Optional[str]      = None,
        severity_filter: str               = "CRITICAL",
        timeout_s:      float              = 10.0,
        max_retries:    int                = 3,
        retry_delay_s:  float              = 1.0,
    ):
        self.webhook_url     = webhook_url.rstrip("/") if webhook_url else None
        self.api_key         = api_key
        self.callback        = callback
        self.file_path       = Path(file_path) if file_path else None
        self.severity_filter = severity_filter
        self.timeout_s       = timeout_s
        self.max_retries     = max_retries
        self.retry_delay_s   = retry_delay_s

        self._lock = threading.Lock()
        self._delivery_log: List[DeliveryResult] = []
        self._total_published = 0
        self._total_failed    = 0

        # Garantir existência do arquivo de saída
        if self.file_path:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Propriedades ──────────────────────────────────────────────────────────

    @property
    def transport_mode(self) -> str:
        """Modo de transporte ativo."""
        if self.webhook_url:
            return "webhook"
        if self.callback:
            return "callback"
        if self.file_path:
            return "file"
        return "null"

    @property
    def is_configured(self) -> bool:
        """True se algum transporte ativo (não-null)."""
        return self.transport_mode != "null"

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, event: Dict[str, Any]) -> DeliveryResult:
        """
        Publica um evento UCO_ANOMALY_DETECTED.

        O evento deve ter a estrutura gerada por SignalOutputRouter._to_apex():
            {
              "event": "UCO_ANOMALY_DETECTED",
              "version": "1.0",
              "payload": { ... }
            }

        Parâmetros
        ----------
        event : dict — payload do evento APEX

        Retorna
        -------
        DeliveryResult — resultado da entrega (nunca lança exceção)
        """
        t0 = time.time()

        # Extrair metadados do evento
        payload  = event.get("payload", {})
        severity = payload.get("severity", "INFO")
        module   = payload.get("module_id", "unknown")
        etype    = event.get("event", "UCO_ANOMALY_DETECTED")

        # Verificar filtro de severidade
        if not self._passes_filter(severity):
            return DeliveryResult(
                ok=True, transport="null",
                event_type=etype, module_id=module, severity=severity,
                error="filtered_by_severity",
            )

        # Despachar para o transporte ativo
        result = self._dispatch(event, severity, module, etype, t0)

        # Atualizar contadores
        with self._lock:
            self._delivery_log.append(result)
            if len(self._delivery_log) > 500:          # limite de memória
                self._delivery_log = self._delivery_log[-500:]
            if result.ok:
                self._total_published += 1
            else:
                self._total_failed += 1

        return result

    def _passes_filter(self, severity: str) -> bool:
        min_level = self.SEVERITY_ORDER.get(self.severity_filter, 2)
        evt_level = self.SEVERITY_ORDER.get(severity, 0)
        return evt_level >= min_level

    def _dispatch(
        self,
        event: Dict,
        severity: str,
        module: str,
        etype: str,
        t0: float,
    ) -> DeliveryResult:
        transport = self.transport_mode

        try:
            if transport == "webhook":
                return self._deliver_webhook(event, severity, module, etype, t0)
            if transport == "callback":
                return self._deliver_callback(event, severity, module, etype, t0)
            if transport == "file":
                return self._deliver_file(event, severity, module, etype, t0)
            # null
            return DeliveryResult(
                ok=True, transport="null",
                event_type=etype, module_id=module, severity=severity,
                latency_ms=(time.time() - t0) * 1000,
            )
        except Exception as exc:
            return DeliveryResult(
                ok=False, transport=transport,
                event_type=etype, module_id=module, severity=severity,
                error=f"dispatch_error: {exc}",
                latency_ms=(time.time() - t0) * 1000,
            )

    # ── Transporte: Webhook ───────────────────────────────────────────────────

    def _deliver_webhook(
        self,
        event: Dict, severity: str, module: str, etype: str, t0: float,
    ) -> DeliveryResult:
        body = json.dumps(event, default=str).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent":   "UCO-Sensor/0.3.0",
            "X-UCO-Event":  etype,
            "X-UCO-Severity": severity,
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url     = f"{self.webhook_url}/events"
        attempt = 0
        last_err = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    status = resp.status
                    if 200 <= status < 300:
                        return DeliveryResult(
                            ok=True, transport="webhook",
                            event_type=etype, module_id=module, severity=severity,
                            status_code=status,
                            latency_ms=(time.time() - t0) * 1000,
                            attempts=attempt,
                        )
                    last_err = f"HTTP {status}"
            except urllib.error.HTTPError as exc:
                last_err = f"HTTP {exc.code}: {exc.reason}"
            except urllib.error.URLError as exc:
                last_err = f"URLError: {exc.reason}"
            except Exception as exc:
                last_err = str(exc)

            if attempt < self.max_retries:
                time.sleep(self.retry_delay_s * (2 ** (attempt - 1)))

        return DeliveryResult(
            ok=False, transport="webhook",
            event_type=etype, module_id=module, severity=severity,
            error=last_err,
            latency_ms=(time.time() - t0) * 1000,
            attempts=attempt,
        )

    # ── Transporte: Callback ──────────────────────────────────────────────────

    def _deliver_callback(
        self,
        event: Dict, severity: str, module: str, etype: str, t0: float,
    ) -> DeliveryResult:
        self.callback(event)
        return DeliveryResult(
            ok=True, transport="callback",
            event_type=etype, module_id=module, severity=severity,
            latency_ms=(time.time() - t0) * 1000,
        )

    # ── Transporte: File (NDJSON) ─────────────────────────────────────────────

    def _deliver_file(
        self,
        event: Dict, severity: str, module: str, etype: str, t0: float,
    ) -> DeliveryResult:
        record = {
            "ts":      time.time(),
            "event":   etype,
            "severity": severity,
            "module":  module,
            "payload": event,
        }
        line = json.dumps(record, default=str) + "\n"
        with self._lock:
            with open(self.file_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        return DeliveryResult(
            ok=True, transport="file",
            event_type=etype, module_id=module, severity=severity,
            latency_ms=(time.time() - t0) * 1000,
        )

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de entrega."""
        with self._lock:
            recent_failures = [
                {"error": r.error, "module": r.module_id, "ts": time.time()}
                for r in self._delivery_log[-20:]
                if not r.ok
            ]
        return {
            "transport":       self.transport_mode,
            "configured":      self.is_configured,
            "severity_filter": self.severity_filter,
            "total_published": self._total_published,
            "total_failed":    self._total_failed,
            "recent_failures": recent_failures,
        }

    def ping(self) -> bool:
        """
        Testa conectividade com o APEX.

        Retorna True se o transporte está acessível.
        Modo null/file/callback: sempre True.
        """
        if self.transport_mode != "webhook":
            return True
        try:
            url = f"{self.webhook_url}/health"
            req = urllib.request.Request(url, method="GET",
                                         headers={"User-Agent": "UCO-Sensor/0.3.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status < 400
        except Exception:
            return False
