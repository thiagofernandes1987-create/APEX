"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: anthropic-official._source.skills.pptx
script_name: __init__.py
script_purpose: [TODO: one sentence — what this script does and when it is invoked]
why: [TODO: why this script exists — what problem it solves vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block the parent skill.
apex_version: v00.36.0
"""
"""
Validation modules for Word document processing.
"""

from .base import BaseSchemaValidator
from .docx import DOCXSchemaValidator
from .pptx import PPTXSchemaValidator
from .redlining import RedliningValidator

__all__ = [
    "BaseSchemaValidator",
    "DOCXSchemaValidator",
    "PPTXSchemaValidator",
    "RedliningValidator",
]
