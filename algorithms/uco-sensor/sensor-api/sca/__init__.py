"""UCO-Sensor — SCA (Software Composition Analysis) package  (M6.3)"""
from .vulnerability_scanner import (
    VulnerabilityScanner,
    SCAResult,
    VulnerabilityFinding,
    Dependency,
)

__all__ = [
    "VulnerabilityScanner",
    "SCAResult",
    "VulnerabilityFinding",
    "Dependency",
]
