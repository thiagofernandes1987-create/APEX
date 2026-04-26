"""sensor_core.autofix — AutofixEngine M5.2"""
from sensor_core.autofix.engine import AutofixEngine, AutofixResult
from sensor_core.autofix.transforms import (
    BaseTransform, TransformResult,
    DeadCodeRemover, RedundantElseRemover,
    BooleanSimplifier, UnusedImportRemover,
)

__all__ = [
    "AutofixEngine", "AutofixResult",
    "BaseTransform", "TransformResult",
    "DeadCodeRemover", "RedundantElseRemover",
    "BooleanSimplifier", "UnusedImportRemover",
]
