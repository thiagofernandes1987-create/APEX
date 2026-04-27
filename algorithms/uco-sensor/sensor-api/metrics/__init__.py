"""
UCO-Sensor — metrics package  (M7.3 + M7.2)
=============================================
Extended metric vectors that complement the 9-channel MetricVector schema.

Exports
-------
HalsteadVector        — 6-channel Halstead Software Science metrics
StructuralVector      — 7-channel structural/OO shape metrics
SecurityVector        — 10-channel aggregated security posture metrics (SAST+SCA+IaC)
VelocityVector        — 4-channel temporal-velocity / degradation metrics
AdvancedVector        — 6-channel advanced static analysis (cognitive CC, SQALE, clones)
DiagnosticVector      — 8-channel spectral diagnostic (FrequencyEngine persistence signals)
ReliabilityVector     — 10-channel reliability signals (M7.3a)
MaintainabilityVector — 9-channel maintainability signals (M7.3b)
FlowVector            — 6-channel taint / data-flow analysis signals (M7.2)
"""
from .extended_vectors import (
    HalsteadVector,
    StructuralVector,
    SecurityVector,
    VelocityVector,
    AdvancedVector,
    DiagnosticVector,
    ReliabilityVector,
    MaintainabilityVector,
    FlowVector,
)

__all__ = [
    "HalsteadVector",
    "StructuralVector",
    "SecurityVector",
    "VelocityVector",
    "AdvancedVector",
    "DiagnosticVector",
    "ReliabilityVector",
    "MaintainabilityVector",
    "FlowVector",
]
