"""
Marco 69 — Sprint AH: PHP05 refinement + CS06 (TAL01-TAL10)
============================================================

Sprint AG opened PHP05 and CS05 as low-confidence triage rules and
honestly documented that neither discriminated the CVE that motivated
it. Two more parallel agents found the actual structural diff in each
real fix:

- ``PHP05`` — Laravel CVE-2026-48041 (GHSA-crmm-hgp2-wgrp): the real
  fix is scoped to wrapping the ``'path'`` array entry passed to
  ``temporarySignedRoute()``/``signedRoute()`` with ``rawurlencode()``
  — the call site itself never changes. Re-targeted the regex from
  "call exists" to "the `['path' => $var]` entry is NOT wrapped in
  rawurlencode()/urlencode()". Validated against the real
  ``laravel/framework`` vulnerable (``071ac5c3``) and fixed
  (``cba82e4e``) ``LocalFilesystemAdapter.php``.
- ``CS06`` (new) — dotnet/runtime CVE-2026-45491 (GHSA-7q4v-2mr6-5gpx):
  the real bug is in ``TarEntry``'s internal
  ``ExtractRelativeToDirectoryAsync`` helper, not the public
  ``ExtractToDirectory``/``ExtractToFile`` API that CS05 (kept,
  unchanged, generic triage) flags. The fix adds a
  ``FilePathEscapesDirectory()`` call alongside the pre-existing
  null-checks on the resolved destination/link path. Whole-file
  presence/absence check (the null-guard exists, but the escape-check
  call doesn't appear anywhere in the file), the second cross-line
  rule in this codebase after RS01. Validated against the real
  ``dotnet/runtime`` vulnerable (``b06f62fc``) and fixed (``8c91e3b2``)
  ``TarEntry.cs``.
"""
from __future__ import annotations

from sast.multilang_scanner import scan_multilang


def _ids(src: str, ext: str) -> list:
    return [f.rule_id for f in scan_multilang(src, ext).findings]


# ── PHP05 (refined) ──────────────────────────────────────────────────────────

def test_TAL01_php05_detects_real_laravel_vulnerable_shape():
    src = (
        "<?php\nfunction link($path) {\n"
        "    return URL::temporarySignedRoute('dl', now()->addMinutes(5), ['path' => $path]);\n"
        "}\n"
    )
    assert "PHP05" in _ids(src, ".php")


def test_TAL02_php05_silent_on_real_laravel_fixed_shape():
    src = (
        "<?php\nfunction link($path) {\n"
        "    return URL::temporarySignedRoute('dl', now()->addMinutes(5), "
        "['path' => rawurlencode($path)]);\n"
        "}\n"
    )
    assert "PHP05" not in _ids(src, ".php")


def test_TAL03_php05_silent_when_urlencode_used_instead():
    src = "<?php\n$x = ['path' => urlencode($path), 'upload' => true];\n"
    assert "PHP05" not in _ids(src, ".php")


def test_TAL04_php05_silent_on_unrelated_array_key():
    src = "<?php\n$x = ['name' => $path];\n"
    assert "PHP05" not in _ids(src, ".php")


# ── CS06 (new, cross-line) ───────────────────────────────────────────────────

def test_TAL05_cs06_detects_real_dotnet_vulnerable_shape():
    src = (
        "if (fileDestinationPath == null) { throw new IOException(); }\n"
        "if (linkDestination is null) { throw new IOException(); }\n"
    )
    findings = scan_multilang(src, ".cs").findings
    cs06 = [f for f in findings if f.rule_id == "CS06"]
    assert len(cs06) == 2
    assert {f.line for f in cs06} == {1, 2}


def test_TAL06_cs06_silent_on_real_dotnet_fixed_shape():
    src = (
        "if (fileDestinationPath is null || FilePathEscapesDirectory(destDir, fileDestinationPath))\n"
        "    throw new IOException();\n"
    )
    assert "CS06" not in _ids(src, ".cs")


def test_TAL07_cs06_silent_when_no_tar_path_null_check():
    src = "if (value == null) { return; }\n"
    assert "CS06" not in _ids(src, ".cs")


def test_TAL08_cs05_still_fires_independently_of_cs06():
    # CS05 (generic public-API triage) is unaffected by the CS06 refinement.
    src = "TarFile.ExtractToDirectory(stream, destDir, true);\n"
    ids = _ids(src, ".cs")
    assert "CS05" in ids
    assert "CS06" not in ids


def test_TAL09_cs06_guard_anywhere_in_file_suppresses_all_sites():
    src = (
        "if (fileDestinationPath == null) { throw new IOException(); }\n"
        "bool ok = FilePathEscapesDirectory(dir, p);\n"
    )
    assert "CS06" not in _ids(src, ".cs")


def test_TAL10_rule_count_reflects_cs06():
    from sast.multilang_scanner import rule_count
    assert rule_count() == 51
