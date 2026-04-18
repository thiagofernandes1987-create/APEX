"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: anthropic-official._source.skills.pdf
script_name: check_fillable_fields.py
script_purpose: [TODO: one sentence — what this script does and when it is invoked]
why: [TODO: why this script exists — what problem it solves vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block the parent skill.
apex_version: v00.36.0
"""
import sys
from pypdf import PdfReader




reader = PdfReader(sys.argv[1])
if (reader.get_fields()):
    print("This PDF has fillable form fields")
else:
    print("This PDF does not have fillable form fields; you will need to visually determine where to enter data")
