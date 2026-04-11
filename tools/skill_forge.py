#!/usr/bin/env python3
"""
skill_forge.py — CLI de criação e promoção de SKILL.md APEX
Uso:
  python tools/skill_forge.py create --domain engineering --name my-skill
  python tools/skill_forge.py promote --path skills/domain/skill/SKILL.md
  python tools/skill_forge.py batch-add-executor --status ADOPTED
"""
import re, sys, io, argparse
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

REPO = Path(__file__).parent.parent

SKILL_TEMPLATE = """---
skill_id: {domain}.{skill_name_snake}
name: {skill_name}
description: "{description}"
version: v00.37.0
status: CANDIDATE
tier: 2
executor: LLM_BEHAVIOR
domain_path: {domain}/{skill_name}
anchors:
{anchors}
input_schema:
  input: "str — {description}"
output_schema:
  output: "str — resultado processado"
what_if_fails: >
  FALLBACK: Se input inválido, retornar [SKILL_ERROR: {skill_name} input inválido].
  Nunca bloquear pipeline.
risk: safe
llm_compat:
  claude: full
  gpt4o: partial
apex_version: v00.37.0
---

# {skill_name}

## Descrição
{description}

## Uso
Ativar quando: {when}

## Input
- `input`: string com o contexto necessário

## Output
- Resultado processado conforme o domínio `{domain}`

## Diff History
- **v00.37.0**: Criado via skill_forge.py — {date}
"""

def create_skill(domain: str, name: str, description: str = "", when: str = ""):
    skill_dir = REPO / "skills" / domain / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    sk_path = skill_dir / "SKILL.md"
    if sk_path.exists():
        print(f"  ⚠️  Skill já existe: {sk_path.relative_to(REPO)}")
        return

    snake = name.replace("-", "_")
    anchors = "\n".join(f"  - {a}" for a in name.split("-"))
    content = SKILL_TEMPLATE.format(
        domain=domain, skill_name=name, skill_name_snake=snake,
        description=description or f"{name} skill for {domain} domain",
        anchors=anchors, when=when or f"user requests {name}",
        date=datetime.now().strftime("%Y-%m-%d"),
    )
    sk_path.write_text(content, encoding='utf-8')
    print(f"  ✅ Criado: {sk_path.relative_to(REPO)}")

def promote_skill(path: str):
    sk_path = REPO / path
    if not sk_path.exists():
        print(f"  ❌ Não encontrado: {path}")
        return
    content = sk_path.read_text(encoding='utf-8', errors='replace')
    changes = []
    if "status: CANDIDATE" in content:
        content = content.replace("status: CANDIDATE", "status: ADOPTED")
        changes.append("CANDIDATE→ADOPTED")
    if "status: ADAPTED" in content:
        content = content.replace("status: ADAPTED", "status: ADOPTED")
        changes.append("ADAPTED→ADOPTED")
    if "executor" not in content:
        content = re.sub(r'(status\s*:\s*\w+)', r'\1\nexecutor: LLM_BEHAVIOR', content, count=1)
        changes.append("executor:LLM_BEHAVIOR adicionado")
    if changes:
        sk_path.write_text(content, encoding='utf-8')
        print(f"  ✅ {path}: {changes}")
    else:
        print(f"  -- {path}: sem mudanças necessárias")

def batch_add_executor(status_filter: str = "ADOPTED"):
    patched = 0
    for sk in (REPO / "skills").rglob("SKILL.md"):
        content = sk.read_text(encoding='utf-8', errors='replace')
        sm = re.search(r'status\s*:\s*(\w+)', content)
        if not sm or sm.group(1).upper() != status_filter.upper():
            continue
        if "executor" in content:
            continue
        content = re.sub(r'(status\s*:\s*\w+)', r'\1\nexecutor: LLM_BEHAVIOR', content, count=1)
        sk.write_text(content, encoding='utf-8')
        patched += 1
    print(f"  ✅ executor adicionado em {patched} skills {status_filter}")

def main():
    parser = argparse.ArgumentParser(description="APEX Skill Forge CLI")
    subparsers = parser.add_subparsers(dest="command")

    # create
    p_create = subparsers.add_parser("create", help="Criar nova skill")
    p_create.add_argument("--domain", required=True)
    p_create.add_argument("--name", required=True)
    p_create.add_argument("--description", default="")
    p_create.add_argument("--when", default="")

    # promote
    p_promote = subparsers.add_parser("promote", help="Promover skill para ADOPTED")
    p_promote.add_argument("--path", required=True)

    # batch-add-executor
    p_batch = subparsers.add_parser("batch-add-executor", help="Adicionar executor em batch")
    p_batch.add_argument("--status", default="ADOPTED")

    args = parser.parse_args()

    if args.command == "create":
        create_skill(args.domain, args.name, args.description, args.when)
    elif args.command == "promote":
        promote_skill(args.path)
    elif args.command == "batch-add-executor":
        batch_add_executor(args.status)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
