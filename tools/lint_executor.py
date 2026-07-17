#!/usr/bin/env python3
"""
lint_executor.py — SR_40 compile-time linter: every boot page must declare a
top-level `executor:` field.

WHY THIS EXISTS:
  SR_40 (ZERO_AMBIGUITY_GUARD) requires every module to state HOW it runs
  (LLM_BEHAVIOR / SANDBOX_CODE / HYBRID / DOCUMENTATION). The audit found 50 of
  111 boot pages with no top-level executor, so the compiler could ship an
  ambiguous kernel. This linter is meant to run inside apex_compiler (build-time,
  fase 1 "validar") and fail the build until every page declares one.

WHEN: build-time, before paginate/assemble; and in CI on the pages directory.

WHAT IF IT FAILS: prints each offending page and exits non-zero. With --fix it
  backfills a conservative `executor:` inferred from the page (never overwriting
  an existing one), then re-lints.

USAGE:
  python3 tools/lint_executor.py apex_boot/v00_39_1/pages [--fix]
"""
import re
import sys
from pathlib import Path

# doc-like pages (history/schema/changelog) are DOCUMENTATION; module pages default
# to LLM_BEHAVIOR unless they carry sandbox/code markers -> SANDBOX_CODE.
_DOC_HINTS = ("changelog", "diff_ecosystem", "apex_schema", "_additions",
              "_legacy", "_preserved", "roster")
_CODE_MARKERS = ("SANDBOX_CODE", "def ", "import ", "algorithm:", "python:")


def _has_top_level_executor(text: str) -> bool:
    # top level = no leading whitespace before `executor:`
    return re.search(r"(?m)^executor:\s*\S", text) is not None


def infer_executor(path: Path, text: str) -> str:
    name = path.stem.lower()
    if any(h in name for h in _DOC_HINTS):
        return "DOCUMENTATION"
    # reuse a nested executor if the page already names one
    m = re.search(r"executor:\s*(LLM_BEHAVIOR|SANDBOX_CODE|HYBRID|DOCUMENTATION)", text)
    if m:
        return m.group(1)
    if any(mk in text for mk in _CODE_MARKERS):
        return "SANDBOX_CODE"
    return "LLM_BEHAVIOR"


def lint(pages_dir: str, fix: bool = False):
    pages = sorted(Path(pages_dir).glob("*.yaml"))
    missing, fixed = [], []
    for p in pages:
        text = p.read_text(encoding="utf-8", errors="replace")
        if _has_top_level_executor(text):
            continue
        missing.append(p.name)
        if fix:
            ex = infer_executor(p, text)
            # insert executor: as the SECOND line (after the top-level key line)
            lines = text.splitlines(keepends=True)
            insert_at = 1 if lines else 0
            lines.insert(insert_at, f"executor: {ex}  # backfilled by lint_executor (SR_40)\n")
            p.write_text("".join(lines), encoding="utf-8")
            fixed.append(f"{p.name} -> {ex}")

    print(f"pages: {len(pages)} | missing top-level executor: {len(missing)}")
    if fix and fixed:
        print(f"backfilled {len(fixed)}:")
        for f in fixed:
            print("  ", f)
        # re-lint
        still = [p.name for p in pages
                 if not _has_top_level_executor(p.read_text(encoding='utf-8', errors='replace'))]
        print(f"after --fix, still missing: {len(still)}")
        return 0 if not still else 1
    if missing and not fix:
        for m in missing:
            print("  MISSING:", m)
        return 1
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    pages_dir = args[0] if args else "apex_boot/v00_39_1/pages"
    sys.exit(lint(pages_dir, fix="--fix" in sys.argv))
