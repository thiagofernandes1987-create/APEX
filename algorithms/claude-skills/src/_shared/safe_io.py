"""
APEX Script Header (APEX OPP-Phase2 / 2.8)
skill_id: algorithms._shared.safe_io
script_name: safe_io.py
script_purpose: [TODO: one sentence — what this script does and when invoked]
why: [TODO: why this script exists vs inline LLM reasoning]
what_if_fails: emit {"error": "<message>", "code": 1} to stderr; never block parent skill.
apex_version: v00.36.0
"""
"""
_shared/safe_io.py — APEX Secure I/O Utilities
================================================
APEX OPP-Phase1 / R-15 remediation.

PURPOSE: Provide safe file-open helpers that prevent path traversal attacks
         for scripts that accept user-supplied file paths via CLI args.

WHY: 44 scripts in this bundle use `open(args.input)` directly without
     resolving symlinks or checking that the path stays within an allowed
     directory. An attacker controlling the CLI args could pass
     `../../etc/passwd` or similar traversal sequences.

WHEN: Import and use `safe_open_input()` / `safe_resolve_path()` in every
      script that opens a file from CLI arguments.

WHAT_IF_FAILS: If path validation fails, ValueError is raised with a safe
               error message. Callers should catch ValueError and exit(1).

SECURITY: stdlib-only (pathlib). No external dependencies.
"""

from __future__ import annotations

import pathlib
import sys
from typing import IO, Optional


# Default allowed base directories — scripts may override this list.
_DEFAULT_ALLOWED_BASES: list[pathlib.Path] = [
    pathlib.Path.cwd(),
]


def safe_resolve_path(
    user_path: str,
    allowed_bases: Optional[list[pathlib.Path]] = None,
    *,
    must_exist: bool = True,
) -> pathlib.Path:
    """Resolve *user_path* and verify it is inside one of *allowed_bases*.

    Parameters
    ----------
    user_path:
        Raw path string from CLI arg or config file.
    allowed_bases:
        List of allowed base directories. Defaults to [cwd()].
        Pass an empty list to skip the base-directory check (not recommended).
    must_exist:
        If True (default), raise ValueError when the path does not exist.

    Returns
    -------
    pathlib.Path
        Resolved absolute path, guaranteed to be within an allowed base.

    Raises
    ------
    ValueError
        If path traversal is detected or the file does not exist.

    Example
    -------
    >>> path = safe_resolve_path(args.input)
    >>> with open(path) as f: ...
    """
    if allowed_bases is None:
        allowed_bases = _DEFAULT_ALLOWED_BASES

    try:
        resolved = pathlib.Path(user_path).resolve()
    except (OSError, ValueError) as exc:
        raise ValueError(f"[APEX_SAFE_IO] Invalid path: {user_path!r} — {exc}") from exc

    if must_exist and not resolved.exists():
        raise ValueError(
            f"[APEX_SAFE_IO] Path does not exist: {resolved}"
        )

    if allowed_bases:
        for base in allowed_bases:
            base_resolved = pathlib.Path(base).resolve()
            try:
                resolved.relative_to(base_resolved)
                return resolved  # path is within this base — OK
            except ValueError:
                continue
        raise ValueError(
            f"[APEX_SAFE_IO] Path traversal detected: {resolved} is not "
            f"within any allowed base: {[str(b) for b in allowed_bases]}"
        )

    return resolved


def safe_open_input(
    user_path: str,
    mode: str = "r",
    encoding: str = "utf-8",
    allowed_bases: Optional[list[pathlib.Path]] = None,
) -> IO:
    """Open *user_path* safely, preventing path traversal.

    Drop-in replacement for ``open(args.input)`` with security validation.

    Example
    -------
    # BEFORE (vulnerable):
    #   with open(args.input) as f: data = f.read()

    # AFTER (safe):
    #   from _shared.safe_io import safe_open_input
    #   with safe_open_input(args.input) as f: data = f.read()
    """
    safe_path = safe_resolve_path(user_path, allowed_bases=allowed_bases, must_exist=True)
    return open(safe_path, mode=mode, encoding=encoding if "b" not in mode else None)


def safe_open_output(
    user_path: str,
    mode: str = "w",
    encoding: str = "utf-8",
    allowed_bases: Optional[list[pathlib.Path]] = None,
) -> IO:
    """Open *user_path* for writing safely, preventing path traversal.

    Example
    -------
    # BEFORE (vulnerable):
    #   with open(args.output, 'w') as f: ...

    # AFTER (safe):
    #   from _shared.safe_io import safe_open_output
    #   with safe_open_output(args.output) as f: ...
    """
    safe_path = safe_resolve_path(user_path, allowed_bases=allowed_bases, must_exist=False)
    return open(safe_path, mode=mode, encoding=encoding if "b" not in mode else None)
