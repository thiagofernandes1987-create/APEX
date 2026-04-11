#!/usr/bin/env python3
"""
validate_skills.py — Validador APEX de SKILL.md
Verifica campos obrigatórios, status, unicidade de skill_id e executor.
Uso: python tools/validate_skills.py [--domain DOMAIN] [--status ADOPTED]
"""
import re, sys, io, argparse
from pathlib import Path
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = Path(__file__).parent.parent
REQUIRED_ADOPTED = ["skill_id", "description", "tier", "executor",
                    "anchors", "input_schema", "output_schema", "what_if_fails"]
REQUIRED_CANDIDATE = ["skill_id", "description", "anchors"]

def validate_skill(sk_path: Path, strict: bool = False) -> dict:
    content = sk_path.read_text(encoding='utf-8', errors='replace')
    status_m = re.search(r'status\s*:\s*(\w+)', content)
    status = status_m.group(1).upper() if status_m else "UNKNOWN"
    sid_m = re.search(r'skill_id\s*:\s*["\']?([^\s"\'#\n]+)["\']?', content)
    sid = sid_m.group(1) if sid_m else None
    required = REQUIRED_ADOPTED if status == "ADOPTED" or strict else REQUIRED_CANDIDATE
    missing = [f for f in required if f not in content]
    return {
        "path": str(sk_path.relative_to(REPO)),
        "skill_id": sid,
        "status": status,
        "missing": missing,
        "ok": len(missing) == 0,
    }

def main():
    parser = argparse.ArgumentParser(description="Validador APEX de SKILL.md")
    parser.add_argument("--domain", default=None, help="Filtrar por domínio")
    parser.add_argument("--status", default=None, help="Filtrar por status (ADOPTED/CANDIDATE)")
    parser.add_argument("--strict", action="store_true", help="Exigir todos campos mesmo para CANDIDATE")
    parser.add_argument("--summary", action="store_true", help="Só mostrar resumo")
    args = parser.parse_args()

    skills_dir = REPO / "skills"
    pattern = f"**/{args.domain}/**/SKILL.md" if args.domain else "**/SKILL.md"
    skill_files = list(skills_dir.glob(pattern))

    results = []
    skill_ids = []
    for sk in skill_files:
        r = validate_skill(sk, strict=args.strict)
        if args.status and r["status"] != args.status.upper():
            continue
        results.append(r)
        if r["skill_id"]:
            skill_ids.append(r["skill_id"])

    ok = [r for r in results if r["ok"]]
    fail = [r for r in results if not r["ok"]]
    dup_sids = {k: v for k, v in Counter(skill_ids).items() if v > 1}

    print(f"APEX Skill Validator — {len(results)} skills verificadas")
    print(f"  ✅ OK: {len(ok)}")
    print(f"  ❌ FAIL: {len(fail)}")
    print(f"  ⚠️  skill_id duplicados: {len(dup_sids)}")

    if not args.summary:
        for r in fail[:50]:
            print(f"  ❌ {r['path']}: faltam {r['missing']}")
        for sid, cnt in list(dup_sids.items())[:10]:
            print(f"  ⚠️  skill_id duplicado: {sid} x{cnt}")

    return 0 if len(fail) == 0 and len(dup_sids) == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
