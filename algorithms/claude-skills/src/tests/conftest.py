"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: algorithms.tests.conftest
script_name: conftest.py
script_purpose: [TODO: one sentence — what this script does and when invoked]
why: [TODO: why this script exists vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block parent skill.
apex_version: v00.36.0
"""
"""Shared fixtures and configuration for the test suite."""

import os
import sys

# Repository root
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def add_script_dir_to_path(script_path: str):
    """Add a script's parent directory to sys.path for imports."""
    script_dir = os.path.dirname(os.path.abspath(script_path))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    return script_dir
