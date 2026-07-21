#!/usr/bin/env python3
"""mine_corpus_taxonomy.py — enriquece a taxonomy a partir do CORPUS REAL do repositório.

A "memória durável" do APEX não é um tempdir efêmero — são as 3.784 skills (cada uma com
category + desc + triggers) e os 213 agentes (cada um com um vocabulário `domains` controlado).
Este minerador agrupa esse corpus rotulado por facet e extrai o vocabulário que MAIS discrimina
cada facet, gerando `apex-method/catalog/taxonomy_corpus_seed.json` (mesclado por taxonomy.py
junto do extra_seed). É a fonte de enriquecimento de maior ROI: dados reais, já rotulados.

Anti-ruído (mesma disciplina do mine_taxonomy_vocab): frequência mínima, document-frequency
entre facets (termo em muitos facets = genérico, descartado), filtro morfológico, denylist.

Regenerar: python3 tools/mine_corpus_taxonomy.py
"""
import json
import os
import re
import unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS_IDX = os.path.join(ROOT, "apex-method", "catalog", "apex_native_skills_index.json")
ROSTER = os.path.join(ROOT, "apex-method", "catalog", "apex_agents_roster.json")
OUT = os.path.join(ROOT, "apex-method", "catalog", "taxonomy_corpus_seed.json")

# categoria da biblioteca -> (eixo, facet canônico do APEX). Categorias genéricas (community,
# knowledge-work, awesome_claude) ficam de fora de propósito — poluiriam a classificação.
CATEGORY_MAP = {
    "ai-ml": ("domain", "data-ai"), "ai_ml_agents": ("subdomain", "agent-infra"),
    "ai_ml_llm": ("subdomain", "agent-infra"), "ai_ml_ml": ("domain", "data-ai"),
    "data": ("domain", "data-ai"), "data-science": ("domain", "data-ai"),
    "science": ("domain", "science"), "science_research": ("domain", "science"),
    "mathematics": ("domain", "mathematics"),
    "finance": ("domain", "finance"), "business": ("domain", "business"),
    "business_content": ("domain", "business"), "business_sales": ("domain", "business"),
    "business_productivity": ("domain", "business"), "business_human_resources": ("domain", "business"),
    "human-resources": ("domain", "business"),
    "marketing": ("domain", "marketing"), "sales": ("domain", "marketing"),
    "legal": ("domain", "legal"), "healthcare": ("domain", "healthcare"),
    "security": ("domain", "security"), "engineering_security": ("subdomain", "appsec"),
    "design": ("subdomain", "frontend"), "engineering_frontend": ("subdomain", "frontend"),
    "engineering_backend": ("subdomain", "backend"), "engineering_api": ("subdomain", "backend"),
    "engineering_database": ("subdomain", "backend"),
    "engineering_devops": ("subdomain", "devops"), "engineering_cloud_azure": ("subdomain", "devops"),
    "engineering_cloud_aws": ("subdomain", "devops"), "engineering_cloud_gcp": ("subdomain", "devops"),
    "engineering_testing": ("subdomain", "testing"), "engineering_agentops": ("subdomain", "agent-infra"),
    "engineering_git": ("subdomain", "devops"), "engineering_cli": ("subdomain", "devops"),
    "engineering_mobile": ("platform", "mobile"),
    "product-management": ("subdomain", "product"), "operations": ("domain", "business"),
    "web3": ("subdomain", "web3"),
}

# domínio controlado do roster de agentes -> facet (fonte de alta qualidade, já curada)
AGENT_DOMAIN_MAP = {
    "security": ("domain", "security"), "testing": ("subdomain", "testing"),
    "frontend": ("subdomain", "frontend"), "backend": ("subdomain", "backend"),
    "database": ("subdomain", "backend"), "devops": ("subdomain", "devops"),
    "cloud": ("subdomain", "devops"), "infrastructure": ("subdomain", "devops"),
    "data": ("domain", "data-ai"), "ml": ("domain", "data-ai"), "ai": ("domain", "data-ai"),
    "finance": ("domain", "finance"), "legal": ("domain", "legal"),
    "marketing": ("domain", "marketing"), "design": ("subdomain", "frontend"),
    "mobile": ("platform", "mobile"), "blockchain": ("subdomain", "web3"),
}

STOP = {"the","and","for","with","from","that","this","use","using","when","your","you","are",
        "can","all","its","not","who","how","what","via","per","apply","create","build","skill",
        "task","tasks","help","need","want","also","into","out","get","set","new","one","two"}
TOO_GENERIC = {"api","apis","http","json","yaml","file","files","user","users","data","model",
               "models","code","test","tests","tool","tools","config","system","service","app",
               "apps","web","text","list","time","work","team","project","support","content",
               "management","analysis","design","development","developer","engineer","expert",
               "including","based","various","different","specific","related","best","practices"}
ING_OK = {"testing","tracing","logging","polling","onboarding","scaling","embedding","monitoring",
          "profiling","routing","caching","sharding","forecasting","modeling","auditing","hedging"}
DENY = {"skill","agent","assistant","helper","review","reviewer","analyzer","generator","manager",
        "specialist","framework","platform","solution","provide","provides","perform","performs"}


def _fold(text):
    # NFKD accent-fold BEFORE tokenizing so "cláusulas" stays whole (senão o split por
    # não-[a-z0-9] fragmenta em 'cl'/'usulas'). Mesmo princípio do _tfidf._fold.
    return "".join(c for c in unicodedata.normalize("NFKD", text or "")
                   if not unicodedata.combining(c)).lower()


def _tok(text):
    out = []
    for t in re.split(r"[^a-z0-9]+", _fold(text)):   # sem '-': ids compostos viram tokens simples
        if len(t) < 4 or t.isdigit() or t in STOP or t in TOO_GENERIC or t in DENY:
            continue
        if any(ch.isdigit() for ch in t):            # descarta '5-task','8-12','v3', ids numéricos
            continue
        if t.endswith(("ed", "ly")) or (t.endswith("ing") and t not in ING_OK):
            continue
        out.append(t)
    return out


def mine():
    skills = json.load(open(SKILLS_IDX, encoding="utf-8"))["skills"]
    roster = json.load(open(ROSTER, encoding="utf-8"))
    # 1) contagem por facet a partir das skills
    per_facet = {}          # (axis,facet) -> Counter
    for s in skills:
        tgt = CATEGORY_MAP.get(s.get("category"))
        if not tgt:
            continue
        c = per_facet.setdefault(tgt, Counter())
        for field in ("id", "desc", "triggers"):
            for t in _tok(s.get(field, "")):
                c[t] += 1
    # 2) reforço pelos domains dos agentes (vocabulário curado)
    for a in roster:
        for dom in a.get("domains", []):
            tgt = AGENT_DOMAIN_MAP.get(dom)
            if tgt:
                per_facet.setdefault(tgt, Counter())[dom] += 3
                for t in _tok(a.get("id", "")):
                    per_facet[tgt][t] += 1
    # 3) document-frequency entre facets: termo genérico (em > 3 facets) é descartado
    df = Counter()
    for c in per_facet.values():
        for t in c:
            df[t] += 1
    # 4) seleciona os termos mais frequentes e discriminantes por facet (top 60)
    seed = {}
    for (axis, facet), c in per_facet.items():
        keep = sorted([t for t, n in c.items() if n >= 3 and df[t] <= 3],
                      key=lambda t: -c[t])[:60]
        if keep:
            seed.setdefault(axis, {}).setdefault(facet, sorted(keep))
    return seed, len(skills), len(roster)


def main():
    seed, ns, na = mine()
    out = {"_source": f"corpus real: {ns} skills + {na} agentes (mine_corpus_taxonomy.py)",
           **seed}
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    total = sum(len(v) for facets in seed.values() for v in facets.values())
    print(f"[mine_corpus] {total} termos de {ns} skills + {na} agentes -> {os.path.relpath(OUT, ROOT)}")
    for axis, facets in sorted(seed.items()):
        print(f"  {axis}: " + ", ".join(f"{k}({len(v)})" for k, v in sorted(facets.items())))


if __name__ == "__main__":
    main()
