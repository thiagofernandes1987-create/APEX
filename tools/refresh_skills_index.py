#!/usr/bin/env python3
"""refresh_skills_index.py — re-sincroniza apex_native_skills_index.json com os SKILL.md atuais.

Achado do coverage_sweep (v1.63): 1.236 skills apareciam como órfãs porque o índice ainda
carregava as descrições DESTRUÍDAS na importação ("Apply — >"), embora o skill_standardizer já
tivesse recuperado a descrição real nos SKILL.md. O índice estava stale. Este script relê o
frontmatter (description + triggers) de cada SKILL.md e atualiza os campos desc/triggers no índice,
sem tocar em id/category/path. Determinístico. Uso: python3 tools/refresh_skills_index.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, "apex-method", "catalog", "apex_native_skills_index.json")


def _frontmatter(path):
    try:
        with open(os.path.join(ROOT, path), encoding="utf-8") as f:
            txt = f.read(4000)
    except (OSError, UnicodeDecodeError):
        return None, None, []
    m = re.match(r"^---\n(.*?)\n---", txt, re.S)
    if not m:
        return None, None, []
    fm = m.group(1)
    d = re.search(r"^description:\s*(.+)$", fm, re.M)
    desc = d.group(1).strip().strip('"').strip("'") if d else None
    anchors = re.findall(r"^\s*-\s*([a-z][a-z0-9 _-]{2,40})\s*$",
                         fm[fm.find("anchors:"):fm.find("anchors:") + 500], re.M) if "anchors:" in fm else []
    trig = re.search(r"triggers:\s*\n((?:\s*-\s*.+\n)+)", fm)
    triggers = None
    if trig:
        triggers = " ".join(re.findall(r"-\s*(.+)", trig.group(1)))[:200]
    return desc, triggers, anchors


def _is_junk(desc):
    if not desc or len(desc) < 12:
        return True
    low = desc.lower()
    return (low.startswith(("apply —", "apply -", "use —", "create —", "**v", "ingested"))
            or "ingested from" in low or desc.strip() in (">", "|", "Apply — >"))


def _synth(skill, anchors):
    """Descrição sintética roteável a partir de labels REAIS (id + category + anchors) quando o
    SKILL.md não tem descrição usável — honesto: são os rótulos que já existem."""
    name = skill.get("id", "").replace("-", " ").replace("_", " ")
    cat = skill.get("category", "").replace("_", " ").replace("-", " ")
    extra = " ".join(a for a in anchors[:6] if a not in name)
    return f"{name} — {cat} skill. {extra}".strip()


def main():
    data = json.load(open(IDX, encoding="utf-8"))
    skills = data["skills"]
    fixed = synth = 0
    for s in skills:
        desc, trig, anchors = _frontmatter(s.get("path", ""))
        if desc and not _is_junk(desc):
            if desc[:400] != s.get("desc"):
                s["desc"] = desc[:400]
                fixed += 1
        elif _is_junk(s.get("desc")):
            # nem o SKILL.md nem o índice têm descrição usável -> sintetiza dos labels reais
            s["desc"] = _synth(s, anchors or [])[:400]
            synth += 1
        if trig and trig != s.get("triggers"):
            s["triggers"] = trig
    if "_meta" in data:
        data["_meta"]["refreshed"] = "desc/triggers re-synced from SKILL.md + synth for junk (v1.63)"
    json.dump(data, open(IDX, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[refresh_index] {fixed} re-sincronizadas dos SKILL.md + {synth} sintetizadas de labels")


if __name__ == "__main__":
    main()
