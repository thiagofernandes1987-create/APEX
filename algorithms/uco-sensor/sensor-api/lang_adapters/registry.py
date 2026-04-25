"""
UCO-Sensor — UCOBridgeRegistry
================================
Registro central de adaptadores de linguagem.

Roteia chamadas de análise para o adaptador correto baseado na
extensão do arquivo. Suporta Python, JavaScript, TypeScript, Java e Go.

Uso:
    from lang_adapters.registry import UCOBridgeRegistry

    registry = UCOBridgeRegistry()
    mv = registry.analyze(source_code, file_extension=".ts", module_id="auth.ts")

    # Ou via factory global:
    from lang_adapters.registry import get_registry
    mv = get_registry().analyze(code, ".java", "UserService.java")
"""
from __future__ import annotations
import sys
import threading
from pathlib import Path
from typing import Optional, Dict, List

from .base import LanguageAdapter

_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


class UCOBridgeRegistry:
    """
    Registro de LanguageAdapters com despacho automático por extensão.

    Adaptadores são inicializados de forma lazy — tree-sitter só é
    carregado quando o primeiro arquivo da linguagem é analisado.

    Linguagens suportadas:
      Python      → PythonAdapter     (.py, .pyw, .pyi)
      JavaScript  → JavaScriptAdapter (.js, .jsx, .mjs, .cjs)
      TypeScript  → JavaScriptAdapter (.ts, .tsx)
      Java        → JavaAdapter       (.java)
      Go          → GoAdapter         (.go)

    Fallback:
      Extensão desconhecida → PythonAdapter com análise de texto
      (CC=1, H estimado por LOC)
    """

    def __init__(self):
        # Mapa de extensão → adapter (lazy loaded)
        self._adapters: Dict[str, LanguageAdapter] = {}
        self._ext_to_class: Dict[str, str] = {}
        self._build_ext_map()

    def _build_ext_map(self) -> None:
        """Mapeia extensões → nome da classe de adapter."""
        mapping = {
            ".py":   "PythonAdapter",
            ".pyw":  "PythonAdapter",
            ".pyi":  "PythonAdapter",
            ".js":   "JavaScriptAdapter",
            ".jsx":  "JavaScriptAdapter",
            ".mjs":  "JavaScriptAdapter",
            ".cjs":  "JavaScriptAdapter",
            ".ts":   "JavaScriptAdapter",
            ".tsx":  "JavaScriptAdapter",
            ".java": "JavaAdapter",
            ".go":   "GoAdapter",
        }
        self._ext_to_class = mapping

    def _load_adapter(self, class_name: str) -> LanguageAdapter:
        """Carrega e instancia um adapter pelo nome da classe."""
        _pkg = Path(__file__).resolve().parent
        if str(_pkg.parent) not in sys.path:
            sys.path.insert(0, str(_pkg.parent))

        if class_name == "PythonAdapter":
            from lang_adapters.python_adapter import PythonAdapter
            return PythonAdapter(mode="full")

        if class_name == "JavaScriptAdapter":
            from lang_adapters.javascript import JavaScriptAdapter
            return JavaScriptAdapter()

        if class_name == "JavaAdapter":
            from lang_adapters.java import JavaAdapter
            return JavaAdapter()

        if class_name == "GoAdapter":
            from lang_adapters.golang import GoAdapter
            return GoAdapter()

        raise ValueError(f"Unknown adapter class: {class_name}")

    def get_adapter(self, file_extension: str) -> LanguageAdapter:
        """
        Retorna o adapter para a extensão dada.
        Usa PythonAdapter como fallback para extensões desconhecidas.
        """
        ext = file_extension.lower()
        if not ext.startswith("."):
            ext = f".{ext}"

        class_name = self._ext_to_class.get(ext, "PythonAdapter")

        # Cache por classe (não por extensão — economiza instâncias)
        if class_name not in self._adapters:
            try:
                self._adapters[class_name] = self._load_adapter(class_name)
            except Exception:
                # Fallback absoluto: PythonAdapter
                from lang_adapters.python_adapter import PythonAdapter
                self._adapters[class_name] = PythonAdapter(mode="minimal")

        return self._adapters[class_name]

    def analyze(
        self,
        source: str,
        file_extension: str = ".py",
        module_id: str = "unknown",
        commit_hash: str = "0000000",
        timestamp: Optional[float] = None,
    ) -> MetricVector:
        """
        Analisa source code e retorna MetricVector.

        Seleciona o adapter correto pela extensão e delega compute_metrics.

        Args:
            source:         Código-fonte como string.
            file_extension: Extensão do arquivo (".py", ".ts", ".java", etc.).
            module_id:      Identificador do módulo (path relativo ou nome).
            commit_hash:    Hash do commit (para histórico).
            timestamp:      Unix timestamp (default: agora).

        Returns:
            MetricVector com os 9 canais UCO preenchidos.
        """
        adapter = self.get_adapter(file_extension)
        return adapter.compute_metrics(
            source=source,
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=timestamp,
            file_extension=file_extension,
        )

    def supported_extensions(self) -> List[str]:
        """Lista todas as extensões suportadas nativamente."""
        return sorted(self._ext_to_class.keys())

    def supported_languages(self) -> List[str]:
        """Lista de linguagens com suporte nativo."""
        return ["python", "javascript", "typescript", "java", "go"]

    def language_for(self, file_extension: str) -> str:
        """Retorna nome da linguagem para uma extensão."""
        ext = file_extension.lower().lstrip(".")
        mapping = {
            "py": "python", "pyw": "python", "pyi": "python",
            "js": "javascript", "jsx": "javascript",
            "mjs": "javascript", "cjs": "javascript",
            "ts": "typescript", "tsx": "typescript",
            "java": "java",
            "go": "go",
        }
        return mapping.get(ext, "unknown")


# ─── Singleton global ─────────────────────────────────────────────────────────

_REGISTRY: Optional[UCOBridgeRegistry] = None
_REGISTRY_LOCK = threading.Lock()


def get_registry() -> UCOBridgeRegistry:
    """Retorna a instância global do UCOBridgeRegistry (singleton thread-safe).

    BUG-03: double-checked locking prevents race condition when multiple
    threads call get_registry() simultaneously during server startup.
    """
    global _REGISTRY
    if _REGISTRY is None:          # fast path (no lock when already initialized)
        with _REGISTRY_LOCK:
            if _REGISTRY is None:  # inner check: re-test after acquiring lock
                _REGISTRY = UCOBridgeRegistry()
    return _REGISTRY
