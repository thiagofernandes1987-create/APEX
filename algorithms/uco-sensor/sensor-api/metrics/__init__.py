"""
UCO-Sensor — metrics package  (M7.3 + M7.2 + M7.4 + M7.5 + M7.6 + M7.7)
=========================================================================
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
PerformanceVector     — 8-channel performance anti-pattern signals (M7.4)
ArchitectureVector    — 8-channel architecture coupling / cohesion signals (M7.5)
TestQualityVector     — 8-channel test-suite quality signals (M7.6)
ThreadSafetyVector    — 6-channel concurrency-correctness signals (M7.7)
Anti-Pattern Score    — compute_aps / rate_aps / aps_from_metric_vector (M7.7)
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
    PerformanceVector,
    ArchitectureVector,
    TestQualityVector,
    ThreadSafetyVector,
)
from .anti_pattern_score import (
    compute_aps,
    rate_aps,
    aps_from_metric_vector,
    APS_COMPONENTS,
    APS_WEIGHT_SUM,
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
    "PerformanceVector",
    "ArchitectureVector",
    "TestQualityVector",
    "ThreadSafetyVector",
    "compute_aps",
    "rate_aps",
    "aps_from_metric_vector",
    "APS_COMPONENTS",
    "APS_WEIGHT_SUM",
]
