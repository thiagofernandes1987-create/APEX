#!/usr/bin/env python3
"""
skill_forge.py — Native APEX skill generator (nativized from APEX tools/skill_forge.py).

WHY THIS EXISTS:
  APEX's own skill-creation method, ported to the awesome-skills/neoformat schema so it
  runs STANDALONE (no APEX repo needed). Generates a schema-valid SKILL.md scaffold and
  manages a CANDIDATE -> ADOPTED lifecycle.

WHAT IF IT FAILS:
  Pure stdlib (argparse/re/pathlib). If a field is missing it errors clearly; it never
  writes an invalid frontmatter (description is length-checked <=400).

USAGE:
  python3 skill_forge.py create --name my-skill --kind workflow --domain engineering \\
      --description "What it does. Use when: <triggers>."
  python3 skill_forge.py promote --path path/to/SKILL.md
"""
import argparse, re, sys
from pathlib import Path
from datetime import date

KINDS = ("persona", "workflow", "tool", "template", "composite")
LICENSES = ("MIT", "Apache-2.0", "BSD-3-Clause", "CC-BY-4.0", "CC0-1.0", "Unlicense")

TEMPLATE = """---
name: {name}
display_name: {display}
kind: {kind}
version: 0.1.0
category: {domain}
description: "{description}"
license: MIT
tags:
  - domain: {domain}
    subtype: {subtype}
    level: intermediate
metadata:
  author: {author}
  status: CANDIDATE
  created: {today}
---

# {display}

<one-paragraph summary of what this skill does and its boundary>

## 1.1 Decision Framework
<when to use, how to choose an approach>

## § 2 · Steps
<the actual procedure>

## § 12 · Scope & Limitations
<what it does not do>

## § 13 · Trigger Words
{name}, <keywords>

## § 14 · Quality Verification
### Test Cases
1. <input -> expected>
"""


def validate_desc(desc: str) -> str:
    if len(desc) > 400:
        raise SystemExit(f"description is {len(desc)} chars; must be <=400 (schema).")
    if len(desc) < 20:
        raise SystemExit("description must be >=20 chars and include 'Use when:' triggers.")
    return desc


def kebab(name: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", s):
        raise SystemExit(f"name '{name}' -> '{s}' is not valid kebab-case.")
    return s


def create(args):
    name = kebab(args.name)
    if args.kind not in KINDS:
        raise SystemExit(f"kind must be one of {KINDS}")
    desc = validate_desc(args.description)
    content = TEMPLATE.format(
        name=name, display=args.name, kind=args.kind, domain=args.domain,
        subtype=args.subtype or "general", description=desc,
        author=args.author, today=date.today().isoformat())
    out = Path(args.out or f"{name}/SKILL.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    print(f"[OK] created CANDIDATE skill: {out}")


def promote(args):
    p = Path(args.path)
    t = p.read_text(encoding="utf-8")
    if "status: CANDIDATE" in t:
        t = t.replace("status: CANDIDATE", "status: ADOPTED")
        # bump 0.1.0 -> 1.0.0 on adoption
        t = re.sub(r"version: 0\.\d+\.\d+", "version: 1.0.0", t, count=1)
        p.write_text(t, encoding="utf-8")
        print(f"[OK] promoted to ADOPTED + v1.0.0: {p}")
    else:
        print("[skip] not a CANDIDATE (or already adopted)")


def main():
    ap = argparse.ArgumentParser(description="Native APEX skill generator (neoformat).")
    # C-09: a bare `skill_forge.py` should print help and exit 0 (like the other modules' self-tests),
    # not argparse's exit-2 usage error. Subcommand stays mandatory for actual work.
    sub = ap.add_subparsers(dest="cmd")
    c = sub.add_parser("create")
    c.add_argument("--name", required=True)
    c.add_argument("--kind", default="workflow")
    c.add_argument("--domain", default="engineering")
    c.add_argument("--subtype", default="general")
    c.add_argument("--description", required=True)
    c.add_argument("--author", default="APEX")
    c.add_argument("--out", default="")
    c.set_defaults(fn=create)
    p = sub.add_parser("promote")
    p.add_argument("--path", required=True)
    p.set_defaults(fn=promote)
    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return
    args.fn(args)


if __name__ == "__main__":
    main()
