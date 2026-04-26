"""AutofixEngine — transforms package."""
from sensor_core.autofix.transforms.base import BaseTransform, TransformResult
from sensor_core.autofix.transforms.dead_code import DeadCodeRemover
from sensor_core.autofix.transforms.redundant_else import RedundantElseRemover
from sensor_core.autofix.transforms.boolean_simplify import BooleanSimplifier
from sensor_core.autofix.transforms.unused_imports import UnusedImportRemover

__all__ = [
    "BaseTransform",
    "TransformResult",
    "DeadCodeRemover",
    "RedundantElseRemover",
    "BooleanSimplifier",
    "UnusedImportRemover",
]
