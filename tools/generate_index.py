#!/usr/bin/env python3
"""
generate_index.py — Gerador automático do INDEX.md do APEX
OPP: OPP-135
VERSION: v1.0.0

WHY: O INDEX.md era mantido manualmente, causando drift em relação à estrutura
     real de skills/. Com 2.624 skills em 50 domínios, manutenção manual é inviável.
WHEN: Executar após qualquer mudança em skills/ — idealmente via GitHub Actions.
HOW: Walk em skills/, parse de frontmatter YAML de cada SKILL.md, geração do
     domain_map em formato machine-parseable para LLMs.
WHAT_IF_FAILS: Manter INDEX.md anterior, registrar erros em index_generation_errors.log.
USAGE:
    python tools/generate_index.py                    # gera INDEX.md na raiz
    python tools/generate_index.py --dry-run          # imprime sem escrever
    python tools/generate_index.py --errors-only      # lista apenas skills com erros
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

# ═══════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════

REPO_ROOT = Path(__file__).parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
INDEX_PATH = REPO_ROOT / "INDEX.md"
ERRORS_LOG = REPO_ROOT / "tools" / "index_generation_errors.log"

APEX_VERSION = "v00.36.0"

# Mapeamento de nomes de diretório para nomes legíveis
DOMAIN_DISPLAY_NAMES = {
    "ai-ml": "AI & Machine Learning",
    "ai_ml_agents": "AI/ML — Agents",
    "ai_ml_llm": "AI/ML — LLMs",
    "ai_ml_ml": "AI/ML — Machine Learning",
    "anthropic-official": "Anthropic Official",
    "apex_internals": "APEX Internals",
    "awesome_claude": "Awesome Claude",
    "business": "Business",
    "business_content": "Business — Content",
    "business_human_resources": "Business — Human Resources",
    "business_productivity": "Business — Productivity",
    "business_sales": "Business — Sales",
    "claude_skills_m": "Claude Skills (M)",
    "community": "Community",
    "community_general": "Community — General",
    "customer-support": "Customer Support",
    "data": "Data",
    "data-science": "Data Science",
    "design": "Design",
    "engineering": "Engineering (Core)",
    "engineering_api": "Engineering — API",
    "engineering_backend": "Engineering — Backend",
    "engineering_cli": "Engineering — CLI",
    "engineering_cloud_aws": "Engineering — Cloud AWS",
    "engineering_cloud_azure": "Engineering — Cloud Azure",
    "engineering_cloud_gcp": "Engineering — Cloud GCP",
    "engineering_database": "Engineering — Database",
    "engineering_devops": "Engineering — DevOps",
    "engineering_frontend": "Engineering — Frontend",
    "engineering_git": "Engineering — Git",
    "engineering_mobile": "Engineering — Mobile",
    "engineering_security": "Engineering — Security",
    "engineering_testing": "Engineering — Testing",
    "finance": "Finance",
    "healthcare": "Healthcare",
    "human-resources": "Human Resources",
    "integrations": "Integrations",
    "knowledge-management": "Knowledge Management",
    "knowledge-work": "Knowledge Work",
    "legal": "Legal",
    "marketing": "Marketing",
    "mathematics": "Mathematics",
    "operations": "Operations",
    "product-management": "Product Management",
    "productivity": "Productivity",
    "sales": "Sales",
    "science": "Science",
    "science_research": "Science — Research",
    "security": "Security",
    "web3": "Web3",
}

# ═══════════════════════════════════════════════════════
# PARSE DE FRONTMATTER
# ═══════════════════════════════════════════════════════

FRONTMATTER_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    """
    WHY: Extrair metadados do SKILL.md sem depender de biblioteca YAML pesada.
    HOW: Regex para capturar bloco entre '---', parse linha a linha de campos simples.
    WHAT_IF_FAILS: Retornar dict vazio — skill será listada com dados mínimos.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}

    frontmatter_text = match.group(1)
    result = {}

    # Parse campo a campo (suporta strings simples, listas, valores quoted)
    lines = frontmatter_text.split('\n')
    current_key = None
    current_list = None

    for line in lines:
        # Linha de lista (começa com - )
        if line.startswith('- ') and current_key and current_list is not None:
            value = line[2:].strip().strip("'\"")
            current_list.append(value)
            result[current_key] = current_list
            continue

        # Linha de chave: valor
        if ':' in line and not line.startswith(' '):
            current_list = None
            parts = line.split(':', 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ''

            if value == '' or value == '[]':
                # Pode ser lista vazia ou lista a seguir
                current_key = key
                current_list = []
                result[key] = []
            elif value.startswith('[') and value.endswith(']'):
                # Lista inline: [a, b, c]
                items = [v.strip().strip("'\"") for v in value[1:-1].split(',') if v.strip()]
                result[key] = items
                current_key = None
            else:
                result[key] = value.strip("'\"")
                current_key = key

    return result


# ═══════════════════════════════════════════════════════
# SCAN DE SKILLS
# ═══════════════════════════════════════════════════════

def scan_domain(domain_dir: Path) -> dict:
    """
    WHY: Varrer um domínio e retornar estrutura com todas as skills encontradas.
    HOW: Walk recursivo buscando SKILL.md, parse de frontmatter, extração de campos.
    WHAT_IF_FAILS: Pular arquivo com erro e continuar — não abortar geração.
    """
    domain_name = domain_dir.name
    skills = []
    errors = []
    sub_domains = defaultdict(list)

    skill_files = sorted(domain_dir.rglob("SKILL.md"))

    for skill_path in skill_files:
        try:
            text = skill_path.read_text(encoding='utf-8', errors='replace')
            meta = parse_frontmatter(text)

            # Determinar sub_domain relativo ao domínio raiz
            relative_parts = skill_path.parent.relative_to(domain_dir).parts
            sub_domain = relative_parts[0] if relative_parts else "_root"

            skill_entry = {
                "skill_id": meta.get("skill_id", skill_path.parent.name),
                "name": meta.get("name", skill_path.parent.name),
                "description": meta.get("description", "")[:120],  # truncar para legibilidade
                "path": str(skill_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "anchors": meta.get("anchors", [])[:8],  # top 8 anchors
                "status": meta.get("status", "UNKNOWN"),
                "tier": meta.get("tier", "IMPORTED"),
                "version": meta.get("version", ""),
            }

            skills.append(skill_entry)
            sub_domains[sub_domain].append(skill_entry)

        except Exception as e:
            errors.append({
                "path": str(skill_path.relative_to(REPO_ROOT)).replace("\\", "/"),
                "error": str(e)
            })

    return {
        "domain": domain_name,
        "display_name": DOMAIN_DISPLAY_NAMES.get(domain_name, domain_name.replace("_", " ").title()),
        "path": f"skills/{domain_name}/",
        "skill_count": len(skills),
        "error_count": len(errors),
        "sub_domains": dict(sub_domains),
        "skills": skills,
        "errors": errors,
    }


def scan_all_domains() -> list:
    """
    WHY: Varrer todos os domínios em skills/ em ordem alfabética.
    HOW: Listar subdiretórios de skills/, chamar scan_domain() para cada um.
    WHAT_IF_FAILS: Retornar resultados parciais — domínios com erro são pulados.
    """
    domains = []
    for domain_dir in sorted(SKILLS_DIR.iterdir()):
        if domain_dir.is_dir():
            domains.append(scan_domain(domain_dir))
    return domains


# ═══════════════════════════════════════════════════════
# GERAÇÃO DO INDEX.md
# ═══════════════════════════════════════════════════════

def generate_index_md(domains: list, generated_at: str) -> str:
    """
    WHY: Produzir INDEX.md em formato legível por humanos E machine-parseable por LLMs.
    HOW: Seção 1 = navegação humana, Seção 2 = domain_map YAML, Seção 3 = estatísticas.
    WHAT_IF_FAILS: Retornar string de erro — não abortar execução.
    """
    total_skills = sum(d["skill_count"] for d in domains)
    total_errors = sum(d["error_count"] for d in domains)

    lines = []

    # ── CABEÇALHO ──────────────────────────────────────────────────────────────
    lines.append("# APEX Index — Hub de Navegação")
    lines.append("")
    lines.append(f"**Gerado automaticamente** por `tools/generate_index.py` — {generated_at}")
    lines.append(f"**Versão APEX**: {APEX_VERSION} | **Skills**: {total_skills} | "
                 f"**Domínios**: {len(domains)} | **Erros de parse**: {total_errors}")
    lines.append("")
    lines.append("> Este arquivo é gerado automaticamente. Não editar manualmente.")
    lines.append("> Para atualizar: `python tools/generate_index.py` ou aguardar o GitHub Action.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── COMO NAVEGAR ───────────────────────────────────────────────────────────
    lines.append("## Como Encontrar Qualquer Skill em 3 Passos")
    lines.append("")
    lines.append("```")
    lines.append("PASSO 1: Identifique o domínio na tabela abaixo ou no domain_map YAML")
    lines.append("PASSO 2: Acesse skills/{domínio}/  (use o path exato da tabela)")
    lines.append("PASSO 3: Leia o SKILL.md do skill específico")
    lines.append("```")
    lines.append("")
    lines.append("> ATENÇÃO: Use nomes canônicos de domínio (ex: `engineering_frontend`,")
    lines.append("> não `frontend`). Ver coluna 'Path' na tabela abaixo.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── TABELA DE DOMÍNIOS ─────────────────────────────────────────────────────
    lines.append("## Domínios Disponíveis")
    lines.append("")
    lines.append("| Domínio | Skills | Path | Status |")
    lines.append("|---------|--------|------|--------|")

    for d in domains:
        status = "OK" if d["error_count"] == 0 else f"{d['error_count']} erros"
        lines.append(
            f"| {d['display_name']} | {d['skill_count']} | `{d['path']}` | {status} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # ── DOMAIN MAP YAML (machine-parseable) ────────────────────────────────────
    lines.append("## Domain Map (machine-parseable YAML)")
    lines.append("")
    lines.append("```yaml")
    lines.append("domain_map:")

    for d in domains:
        domain_key = d["domain"].upper().replace("-", "_")
        lines.append(f"  {domain_key}:")
        lines.append(f"    path: {d['path']}")
        lines.append(f"    display_name: \"{d['display_name']}\"")
        lines.append(f"    skill_count: {d['skill_count']}")

        # Anchors agregados do domínio (top 15 mais frequentes)
        all_anchors = []
        for skill in d["skills"]:
            all_anchors.extend(skill.get("anchors", []))
        anchor_freq = defaultdict(int)
        for a in all_anchors:
            if a and len(a) > 2:
                anchor_freq[a.lower()] += 1
        top_anchors = sorted(anchor_freq, key=anchor_freq.get, reverse=True)[:15]

        if top_anchors:
            anchors_str = ", ".join(top_anchors)
            lines.append(f"    anchors: [{anchors_str}]")

        # Sub-domínios
        if d["sub_domains"]:
            lines.append(f"    sub_domains:")
            for sub, sub_skills in sorted(d["sub_domains"].items()):
                if sub == "_root":
                    continue
                lines.append(f"      {sub}:")
                lines.append(f"        path: {d['path']}{sub}/")
                lines.append(f"        skill_count: {len(sub_skills)}")
                # Listar até 5 skills no sub-domínio
                lines.append(f"        skills:")
                for skill in sub_skills[:5]:
                    lines.append(f"          - skill: {skill['skill_id']}")
                    lines.append(f"            path: {skill['path']}")
                    lines.append(f"            status: {skill['status']}")
                    if skill.get("anchors"):
                        anchors_str = ", ".join(skill["anchors"][:5])
                        lines.append(f"            anchors: [{anchors_str}]")
                if len(sub_skills) > 5:
                    lines.append(f"          # ... +{len(sub_skills) - 5} skills adicionais")

        # Skills na raiz do domínio (sem sub-domínio)
        root_skills = d["sub_domains"].get("_root", [])
        if root_skills:
            lines.append(f"    skills:")
            for skill in root_skills[:10]:
                lines.append(f"      - skill: {skill['skill_id']}")
                lines.append(f"        path: {skill['path']}")
                lines.append(f"        status: {skill['status']}")
            if len(root_skills) > 10:
                lines.append(f"      # ... +{len(root_skills) - 10} skills adicionais")

        lines.append("")

    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("")

    # ── ESTATÍSTICAS ───────────────────────────────────────────────────────────
    lines.append("## Estatísticas de Geração")
    lines.append("")

    # Status breakdown
    status_counts = defaultdict(int)
    tier_counts = defaultdict(int)
    for d in domains:
        for skill in d["skills"]:
            status_counts[skill.get("status", "UNKNOWN")] += 1
            tier_counts[skill.get("tier", "IMPORTED")] += 1

    lines.append("**Por Status:**")
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        pct = count / total_skills * 100 if total_skills > 0 else 0
        lines.append(f"- {status}: {count} ({pct:.1f}%)")
    lines.append("")

    lines.append("**Por Tier:**")
    for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
        pct = count / total_skills * 100 if total_skills > 0 else 0
        lines.append(f"- {tier}: {count} ({pct:.1f}%)")
    lines.append("")

    # Top domínios por tamanho
    top_domains = sorted(domains, key=lambda d: d["skill_count"], reverse=True)[:10]
    lines.append("**Top 10 Domínios por Quantidade de Skills:**")
    for i, d in enumerate(top_domains, 1):
        lines.append(f"{i}. {d['display_name']}: {d['skill_count']} skills")
    lines.append("")

    if total_errors > 0:
        lines.append(f"**Erros de Parse**: {total_errors} skills com frontmatter malformado")
        lines.append(f"Ver: `tools/index_generation_errors.log` para detalhes")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Gerado por `tools/generate_index.py` — APEX {APEX_VERSION} — {generated_at}*")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Gera INDEX.md automaticamente a partir de skills/"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Imprimir o INDEX.md gerado sem escrever o arquivo"
    )
    parser.add_argument(
        "--errors-only", action="store_true",
        help="Listar apenas skills com erros de parse"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Exportar domain_map como JSON em vez de Markdown"
    )
    args = parser.parse_args()

    print(f"[generate_index] Scanning {SKILLS_DIR}...", file=sys.stderr)
    domains = scan_all_domains()

    total_skills = sum(d["skill_count"] for d in domains)
    total_errors = sum(d["error_count"] for d in domains)
    print(
        f"[generate_index] {len(domains)} domínios | {total_skills} skills | {total_errors} erros",
        file=sys.stderr
    )

    if args.errors_only:
        all_errors = []
        for d in domains:
            all_errors.extend(d["errors"])
        if all_errors:
            print(f"\n[ERRORS] {len(all_errors)} skills com erro de parse:")
            for err in all_errors:
                print(f"  - {err['path']}: {err['error']}")
        else:
            print("[OK] Nenhum erro de parse encontrado.")
        return

    if args.json:
        output = json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(), "domains": domains},
            ensure_ascii=False,
            indent=2
        )
        if args.dry_run:
            print(output)
        else:
            json_path = REPO_ROOT / "tools" / "domain_map.json"
            json_path.write_text(output, encoding="utf-8")
            print(f"[generate_index] domain_map.json escrito: {json_path}", file=sys.stderr)
        return

    # Gerar INDEX.md
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    index_content = generate_index_md(domains, generated_at)

    if args.dry_run:
        print(index_content)
        return

    # Escrever INDEX.md
    INDEX_PATH.write_text(index_content, encoding="utf-8")
    print(f"[generate_index] INDEX.md escrito: {INDEX_PATH}", file=sys.stderr)
    print(f"[generate_index] Linhas: {len(index_content.splitlines())}", file=sys.stderr)

    # Escrever log de erros (se houver)
    if total_errors > 0:
        all_errors = []
        for d in domains:
            for err in d["errors"]:
                all_errors.append({"domain": d["domain"], **err})

        ERRORS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with ERRORS_LOG.open("w", encoding="utf-8") as f:
            f.write(f"# index_generation_errors.log — {generated_at}\n")
            f.write(f"# Total: {total_errors} erros\n\n")
            for err in all_errors:
                f.write(f"[{err['domain']}] {err['path']}: {err['error']}\n")
        print(f"[generate_index] Erros salvos: {ERRORS_LOG}", file=sys.stderr)

    print(f"[generate_index] DONE — {total_skills} skills indexadas, {total_errors} erros",
          file=sys.stderr)


if __name__ == "__main__":
    main()
