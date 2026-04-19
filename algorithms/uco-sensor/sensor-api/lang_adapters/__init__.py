"""UCO-Sensor — Language Adapters package.

Exporta:
  LanguageAdapter  — protocolo/ABC base
  PythonAdapter    — Python via ast.parse (UCOBridge)
  JavaScriptAdapter— JS/TS/JSX/TSX via tree-sitter
  JavaAdapter      — Java via tree-sitter
  GoAdapter        — Go via tree-sitter
  UCOBridgeRegistry— despacho automático por extensão
  get_registry()   — singleton global do registry
"""

from .base import LanguageAdapter
from .python_adapter import PythonAdapter
from .javascript import JavaScriptAdapter
from .java import JavaAdapter
from .golang import GoAdapter
from .registry import UCOBridgeRegistry, get_registry

__all__ = [
    "LanguageAdapter",
    "PythonAdapter",
    "JavaScriptAdapter",
    "JavaAdapter",
    "GoAdapter",
    "UCOBridgeRegistry",
    "get_registry",
]
