#!/usr/bin/env python3
"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: anthropic-skills.document-skills.pptx
script_name: unpack.py
script_purpose: [TODO: one sentence — what this script does and when it is invoked]
why: [TODO: why this script exists — what problem it solves vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block the parent skill.
apex_version: v00.36.0
"""
"""Unpack and format XML contents of Office files (.docx, .pptx, .xlsx)"""

import random
import sys
import defusedxml.minidom
import zipfile
from pathlib import Path

# Get command line arguments
assert len(sys.argv) == 3, "Usage: python unpack.py <office_file> <output_dir>"
input_file, output_dir = sys.argv[1], sys.argv[2]

# Extract and format
output_path = Path(output_dir)
output_path.mkdir(parents=True, exist_ok=True)
zipfile.ZipFile(input_file).extractall(output_path)

# Pretty print all XML files
xml_files = list(output_path.rglob("*.xml")) + list(output_path.rglob("*.rels"))
for xml_file in xml_files:
    content = xml_file.read_text(encoding="utf-8")
    dom = defusedxml.minidom.parseString(content)
    xml_file.write_bytes(dom.toprettyxml(indent="  ", encoding="ascii"))

# For .docx files, suggest an RSID for tracked changes
if input_file.endswith(".docx"):
    suggested_rsid = "".join(random.choices("0123456789ABCDEF", k=8))
    print(f"Suggested RSID for edit session: {suggested_rsid}")
