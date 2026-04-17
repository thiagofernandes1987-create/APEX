"""
tools/patch_path_traversal.py — APEX OPP-Phase1 / R-15
========================================================
Patches 44 scripts that use `open(args.input)` without path validation.

WHAT IT DOES:
  For each target script, inserts a security comment block explaining
  the vulnerability and how to migrate to safe_io.safe_open_input().
  Does NOT auto-rewrite open() calls — developers must opt-in per script
  to avoid breaking changes. The comment is a migration guide + warning.

USAGE:
  python tools/patch_path_traversal.py [--dry-run]

WHY:
  44 scripts with open(args.input) are potentially vulnerable to path
  traversal if exposed as agent tools with user-controlled CLI arguments.
  Automated comment injection ensures every developer who opens these
  files sees the security guidance immediately.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).parent.parent
SRC_ROOT = REPO_ROOT / "algorithms" / "claude-skills" / "src"

SECURITY_COMMENT = '''\
# ─────────────────────────────────────────────────────────────────────────────
# SECURITY NOTE (APEX OPP-Phase1 / R-15) — Path Traversal Risk
# ─────────────────────────────────────────────────────────────────────────────
# This script uses open(args.input / args.input_file / input_file) without
# resolving or validating the path. If this script is exposed as a tool to an
# agent that accepts user-provided arguments, path traversal is possible:
#   e.g. --input ../../etc/passwd
#
# REMEDIATION: Replace open(args.input) with:
#   from _shared.safe_io import safe_open_input
#   with safe_open_input(args.input) as f:
#       data = f.read()
#
# safe_io.safe_open_input() calls pathlib.Path.resolve() and verifies the
# resolved path is within the current working directory (configurable).
# See algorithms/claude-skills/src/_shared/safe_io.py for full API.
# ─────────────────────────────────────────────────────────────────────────────
'''

MARKER = "APEX OPP-Phase1 / R-15"


def find_targets() -> list[pathlib.Path]:
    patterns = [
        "open(args.input",
        "open(args.input_file",
        "open(input_file",
    ]
    targets: list[pathlib.Path] = []
    for py_file in SRC_ROOT.rglob("*.py"):
        try:
            text = py_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(p in text for p in patterns) and MARKER not in text:
            targets.append(py_file)
    return targets


def patch_file(path: pathlib.Path, dry_run: bool = False) -> bool:
    try:
        original = path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"  [SKIP] {path.name}: {e}")
        return False

    patched = SECURITY_COMMENT + original
    if dry_run:
        print(f"  [DRY_RUN] Would patch: {path.relative_to(REPO_ROOT)}")
        return True

    path.write_text(patched, encoding="utf-8")
    print(f"  [PATCHED] {path.relative_to(REPO_ROOT)}")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch path-traversal risk scripts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    targets = find_targets()
    print(f"\nAPEX OPP-Phase1 / R-15 — Path Traversal Patch")
    print(f"Found {len(targets)} scripts to patch\n")

    patched = 0
    for path in sorted(targets):
        if patch_file(path, dry_run=args.dry_run):
            patched += 1

    action = "Would patch" if args.dry_run else "Patched"
    print(f"\n{action} {patched}/{len(targets)} files.")
    if not args.dry_run:
        print("Next step: replace open(args.input) with safe_open_input() in each file.")
        print("See algorithms/claude-skills/src/_shared/safe_io.py")


if __name__ == "__main__":
    main()
