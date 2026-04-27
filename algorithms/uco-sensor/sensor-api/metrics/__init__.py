"""
UCO-Sensor — metrics package  (M6.4)
=====================================
Extended metric vectors that complement the 9-channel MetricVector schema.

Exports
-------
HalsteadVector   — 6-channel Halstead Software Science metrics
StructuralVector — 7-channel structural/OO shape metrics
SecurityVector   — 10-channel aggregated security posture metrics
VelocityVector   — 4-channel temporal-velocity / degradation metrics
"""
from .extended_vectors import (
    HalsteadVector,
    StructuralVector,
    SecurityVector,
    VelocityVector,
)

__all__ = [
    "HalsteadVector",
    "StructuralVector",
    "SecurityVector",
    "VelocityVector",
]
