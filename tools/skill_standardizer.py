#!/usr/bin/env python3
"""skill_standardizer.py — conformidade e reparo da biblioteca skills/.

Problema que corrige (auditoria v1.62): na importação em massa, descrições em YAML
block-scalar (`description: >` / `|`) viraram lixo literal ("Use — >", "Create — |"),
e parte das skills ficou sem `name:`/`description:`. O router (TF-IDF/gravity) depende
desses campos — skill sem descrição real é invisível para o roteamento.

O que faz:
  - Varre skills/**/SKILL.md (frontmatter parseado por regex, sem dependências).
  - Classifica cada skill: OK | DESC_MANGLED | DESC_SHORT | NO_DESC | NO_NAME | UNREADABLE.
  - Com --apply, repara APENAS as linhas `name:`/`description:` do frontmatter:
      name        <- nome do diretório da skill
      description <- colhida do corpo (1º bullet de "When to Use"/"Use when", ou 1º
                     parágrafo substantivo), 1 linha, <=220 chars, aspas escapadas.
  - Nunca toca no corpo nem nos demais campos. Reversível via git.
  - Relatório JSON em tools/skill_standardizer_report.json (determinístico, sem timestamp).

Uso:
  python3 tools/skill_standardizer.py            # só relatório
  python3 tools/skill_standardizer.py --apply    # relatório + reparos
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
REPORT = os.path.join(ROOT, "tools", "skill_standardizer_report.json")

MANGLED = re.compile(r'^\s*(?:Use|Create|Skill|This|Provides|Apply)?\s*[—–-]?\s*[>|]\s*$')
MIN_DESC = 40


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except (UnicodeDecodeError, OSError):
        return None


def _split_frontmatter(text):
    """Return (frontmatter_lines, body) or (None, None)."""
    if not text.startswith("---"):
        return None, None
    parts = text.split("\n---", 2)
    if len(parts) < 2:
        return None, None
    fm = parts[0].lstrip("-\n")
    body = parts[1] if len(parts) == 2 else parts[1] + "\n---" + parts[2]
    # normal case: '---\n<fm>\n---\n<body>'
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if m:
        return m.group(1).splitlines(), m.group(2)
    return fm.splitlines(), body


def _fm_value(fm_lines, key):
    for ln in fm_lines:
        m = re.match(rf"^{key}:\s*(.*)$", ln)
        if m:
            return m.group(1).strip().strip('"').strip("'")
    return None


def harvest_description(body, dirname):
    """Extract a real one-line description from the skill body."""
    # 1) first bullet under a "When to Use"-like heading
    m = re.search(r"^#+\s*(?:When to Use|Use when|Quando usar|When to use this skill)\b.*?$",
                  body, re.M | re.I)
    if m:
        tail = body[m.end():]
        b = re.search(r"^\s*[-*]\s+(.+)$", tail, re.M)
        if b:
            return _clean(b.group(1))
    # 2) explicit "Use when ..." sentence anywhere
    m = re.search(r"^\s*[-*]?\s*(Use (?:this skill )?when .{20,200})$", body, re.M | re.I)
    if m:
        return _clean(m.group(1))
    # 3) first substantive paragraph (skip headings, code fences, tables, markers)
    for para in re.split(r"\n\s*\n", body):
        p = para.strip()
        if not p or p.startswith(("#", "```", "|", ">", "<!--", "[")):
            continue
        p = re.sub(r"\s+", " ", p)
        if len(p) >= 30:
            return _clean(p)
    # 4) fallback: humanized dir name
    return "Skill: " + dirname.replace("-", " ").replace("_", " ")


def _clean(s):
    s = re.sub(r"\s+", " ", s).strip()
    s = s.replace('"', "'")
    return (s[:217] + "...") if len(s) > 220 else s


def classify(path):
    text = _read(path)
    if text is None:
        return {"path": path, "status": "UNREADABLE"}
    fm, body = _split_frontmatter(text)
    if fm is None:
        return {"path": path, "status": "NO_FRONTMATTER"}
    name = _fm_value(fm, "name")
    desc = _fm_value(fm, "description")
    issues = []
    if not name:
        issues.append("NO_NAME")
    if desc is None or desc == "":
        issues.append("NO_DESC")
    elif MANGLED.match(desc):
        issues.append("DESC_MANGLED")
    elif len(desc) < MIN_DESC:
        issues.append("DESC_SHORT")
    return {"path": path, "status": ",".join(issues) if issues else "OK",
            "name": name, "description": desc}


def repair(path, entry):
    """Surgically fix name/description lines in the frontmatter. Returns list of fixes."""
    text = _read(path)
    if text is None:
        return []
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return []
    fm_text, body = m.group(1), m.group(2)
    dirname = os.path.basename(os.path.dirname(path))
    fixes = []
    statuses = entry["status"].split(",")
    if any(s in statuses for s in ("DESC_MANGLED", "DESC_SHORT", "NO_DESC")):
        new_desc = harvest_description(body, dirname)
        if len(new_desc) >= MIN_DESC or "NO_DESC" in statuses or "DESC_MANGLED" in statuses:
            line = f'description: "{new_desc}"'
            if re.search(r"^description:.*$", fm_text, re.M):
                fm_text = re.sub(r"^description:.*$", line, fm_text, count=1, flags=re.M)
            else:
                fm_text = line + "\n" + fm_text
            fixes.append("description")
    if "NO_NAME" in statuses:
        fm_text = f"name: {dirname}\n" + fm_text
        fixes.append("name")
    if fixes:
        with open(path, "w", encoding="utf-8") as f:
            f.write("---\n" + fm_text + "\n---\n" + body)
    return fixes


def main(apply=False):
    entries = []
    for root, _dirs, files in os.walk(SKILLS):
        if "SKILL.md" in files:
            entries.append(classify(os.path.join(root, "SKILL.md")))
    entries.sort(key=lambda e: e["path"])
    counts = {}
    for e in entries:
        for s in e["status"].split(","):
            counts[s] = counts.get(s, 0) + 1
    fixed = {"description": 0, "name": 0, "files": 0}
    if apply:
        for e in entries:
            if e["status"] not in ("OK", "UNREADABLE", "NO_FRONTMATTER"):
                fx = repair(e["path"], e)
                if fx:
                    fixed["files"] += 1
                    for f in fx:
                        fixed[f] += 1
    report = {"total": len(entries), "by_status": dict(sorted(counts.items())),
              "applied": apply, "fixed": fixed,
              "non_ok": [{"path": os.path.relpath(e["path"], ROOT), "status": e["status"]}
                         for e in entries if e["status"] != "OK"]}
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f"[skill_standardizer] total={report['total']} status={report['by_status']}")
    if apply:
        print(f"[skill_standardizer] fixed: {fixed}")
    print(f"[skill_standardizer] report: {os.path.relpath(REPORT, ROOT)}")
    return report


if __name__ == "__main__":
    main(apply="--apply" in sys.argv)
