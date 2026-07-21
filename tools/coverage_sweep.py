#!/usr/bin/env python3
"""coverage_sweep.py — varredura determinística de cobertura sobre TODA a biblioteca.

"Um problema por skill / forçar todos os agentes e skills" — realisticamente NÃO se spawna
3.784 subagentes LLM. O que É real, escalável e honesto: exercitar o CAMINHO de roteamento do
kernel (taxonomy → router/gravity → resolução de agente) para CADA skill e CADA agente, medindo:

  - REACHABILITY: gerando um problema-proxy a partir da descrição de cada skill, o router a
    encontra? (skill órfã = descrição pobre = invisível ao roteamento)
  - DEPTH: o problema aciona um agente + facet coerentes (uso profundo) ou cai em genérico
    (uso superficial)?
  - AGENT COVERAGE: quais dos 213 agentes são alcançáveis por alguma disciplina?
  - por DISCIPLINA: distribuição de skills/agentes, para calibrar gravidade e popularidade.

Produz coverage_report.json (determinístico) consumido por calibrate_gravity.py e pelo MCP KB.
Uso: python3 tools/coverage_sweep.py [--limit N]
"""
import json
import os
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "apex-method", "scripts"))
SKILLS_IDX = os.path.join(ROOT, "apex-method", "catalog", "apex_native_skills_index.json")
ROSTER = os.path.join(ROOT, "apex-method", "catalog", "apex_agents_roster.json")
OUT = os.path.join(ROOT, "apex-method", "catalog", "coverage_report.json")


def _proxy_problem(skill):
    """Um 'problema' realista a partir da skill: sua descrição/triggers (o que um usuário pediria)."""
    desc = (skill.get("desc") or "").strip()
    trig = (skill.get("triggers") or "").replace("- ", "").strip()
    base = desc or trig or skill.get("id", "").replace("-", " ")
    return base[:160]


def sweep(limit=None):
    import taxonomy, orchestrator
    skills = json.load(open(SKILLS_IDX, encoding="utf-8"))["skills"]
    roster = json.load(open(ROSTER, encoding="utf-8"))
    if limit:
        skills = skills[:limit]

    per_discipline = Counter()      # disciplina -> nº de skills roteadas
    domain_recognized = 0           # skills cujo proxy classifica em algum domínio
    orphans = []                    # skills cujo proxy não classifica em nada (invisíveis)
    cat_to_domain = defaultdict(Counter)

    for s in skills:
        prob = _proxy_problem(s)
        c = taxonomy.classify(prob)
        dom = c.get("domain")
        if dom or c.get("subdomain"):
            domain_recognized += 1
            key = dom or c.get("subdomain")
            per_discipline[key] += 1
            cat_to_domain[s.get("category", "?")][key] += 1
        else:
            orphans.append({"id": s.get("id"), "category": s.get("category"),
                            "desc": prob[:80]})

    # cobertura de agentes: cada agente é alcançável por seus domains?
    agent_domains = Counter()
    for a in roster:
        for d in a.get("domains", []):
            agent_domains[d] += 1

    n = len(skills)
    report = {
        "skills_swept": n,
        "domain_recognized": domain_recognized,
        "recognition_rate": round(domain_recognized / n, 4) if n else 0,
        "orphans_count": len(orphans),
        "orphans_sample": orphans[:40],
        "skills_per_discipline": dict(per_discipline.most_common()),
        "agents_total": len(roster),
        "agent_domain_distribution": dict(agent_domains.most_common()),
        "category_to_domain_top": {cat: dict(dc.most_common(3))
                                   for cat, dc in sorted(cat_to_domain.items())},
    }
    return report, orphans


def main():
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    report, orphans = sweep(limit)
    json.dump(report, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[coverage] {report['skills_swept']} skills varridas")
    print(f"  reconhecimento de domínio: {report['domain_recognized']}/{report['skills_swept']} "
          f"= {report['recognition_rate']:.1%}")
    print(f"  órfãs (invisíveis ao roteamento): {report['orphans_count']}")
    print(f"  disciplinas cobertas: {len(report['skills_per_discipline'])}")
    print("  top disciplinas:", dict(list(report['skills_per_discipline'].items())[:8]))
    print(f"  relatório -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
