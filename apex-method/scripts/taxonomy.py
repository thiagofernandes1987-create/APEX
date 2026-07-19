#!/usr/bin/env python3
"""
taxonomy.py — canonical (ENGLISH) facet classifier: the language-independent attraction layer.

WHY THIS EXISTS:
  Lexical routing (`router` TF-IDF) fails across languages and on name collisions ("moderna"->
  moderna-scientist, "mobile"->t-mobile, "moda"->nothing useful). The fix the author asked for:
  reduce BOTH the task AND every body (agent/skill/diff/script) to the SAME canonical ENGLISH facets
  — domain / subdomain / intent / platform / specialties — then attract by FACET OVERLAP, not raw
  words. A PT task and an EN skill both map to `{domain:mathematics, subdomain:statistics}` and so
  they attract regardless of language.

WHAT IT PRODUCES (the author's target shape):
  classify("crie uma interface moderna para aplicativo mobile") ->
    {"domain":"software","subdomain":"frontend","intent":"ui_ux_design","platform":"mobile",
     "specialties":["ui","ux"], "facets":{...canonical english tokens...}}

HOW IT WORKS:
  Each canonical facet owns a BILINGUAL trigger set (PT+EN). classify() scores every facet by
  word-boundary hits in the (lowered) text and keeps the top facet per axis. `facet_score(a,b)` is
  a weighted Jaccard over the two facet sets — the attraction weight the router/gravity use.

WHAT IF IT FAILS:
  Pure stdlib (re). No trigger hit on an axis -> that axis is None (not guessed). Empty text -> the
  empty classification. Never raises.
"""
import re

# ── canonical facets → bilingual (PT+EN) triggers. The KEYS are the language-independent tokens. ──
DOMAIN = {
    "software":     {"code", "código", "codigo", "api", "backend", "frontend", "app", "aplicativo",
                     "software", "sistema", "system", "programa", "programação", "programacao",
                     "microservice", "microserviço", "devops", "deploy"},
    "mathematics":  {"math", "mathematics", "matemática", "matematica", "statistics", "statistical",
                     "estatística", "estatistica", "moda", "mode", "média", "media", "mean",
                     "desvio", "deviation", "variance", "variância", "variancia", "população",
                     "populacao", "population", "cálculo", "calculo", "calculus", "integral",
                     "derivada", "derivative", "probability", "probabilidade", "monte", "carlo",
                     "hmc", "bayesian", "bayesiano", "regression", "regressão", "algebra", "álgebra",
                     "equation", "equação", "equacao", "ode", "pde", "numerical", "numérico"},
    "security":     {"security", "segurança", "seguranca", "vulnerability", "vulnerabilidade",
                     "exploit", "audit", "auditoria", "autópsia", "autopsia", "pentest", "cve",
                     "threat", "ameaça", "forensic", "forense", "hardening", "malware"},
    "finance":      {"finance", "financeiro", "financial", "valuation", "dcf", "portfolio",
                     "portfólio", "investment", "investimento", "trading", "risk", "risco",
                     "cash", "caixa", "runway", "budget", "orçamento", "orcamento", "accounting"},
    "data-ai":      {"data", "dados", "ml", "machine", "learning", "aprendizado", "model", "modelo",
                     "embedding", "neural", "ai", "ia", "dataset", "training", "treinamento",
                     "recommender", "recomendação", "nlp", "llm", "pipeline"},
    "marketing":    {"marketing", "campaign", "campanha", "seo", "instagram", "ads", "social",
                     "brand", "marca", "content", "conteúdo", "conteudo", "growth", "engagement"},
    "legal":        {"legal", "jurídico", "juridico", "contract", "contrato", "compliance",
                     "conformidade", "regulation", "regulação", "hipaa", "gdpr", "lgpd", "law", "lei"},
    "healthcare":   {"health", "saúde", "saude", "clinical", "clínico", "clinico", "patient",
                     "paciente", "medical", "médico", "medico", "diagnosis", "diagnóstico"},
    "science":      {"physics", "física", "fisica", "simulation", "simulação", "simulacao",
                     "chemistry", "química", "quimica", "biology", "biologia", "dynamics", "dinâmica"},
    "engineering":  {"engineering", "engenharia", "structural", "estrutural", "viga", "beam",
                     "concreto", "concrete", "laje", "slab", "pilar", "coluna", "column",
                     "fundação", "fundacao", "foundation", "dimensionamento", "dimensione",
                     "dimensionar", "nbr", "aço", "aco", "steel", "carga", "load", "momento",
                     "moment", "tensão", "tensao", "stress", "flexão", "flexao", "bending",
                     "cisalhamento", "shear", "armadura", "rebar", "geotécnica", "geotecnica",
                     "geotechnical", "mecânica", "mecanica", "mechanical", "elétrica", "eletrica",
                     "electrical", "hidráulica", "hidraulica", "hydraulic", "civil"},
}
SUBDOMAIN = {
    "frontend":     {"ui", "ux", "interface", "frontend", "front-end", "react", "vue", "angular",
                     "component", "componente", "layout", "css", "design", "screen", "tela",
                     "usabilidade", "usability", "responsive", "responsivo"},
    "backend":      {"backend", "back-end", "server", "servidor", "database", "banco", "api",
                     "endpoint", "microservice", "queue", "fila", "cache", "sharding", "shard",
                     "replication", "replicação", "partition", "partição", "distributed",
                     "distribuído", "distribuido", "sql", "postgres", "index", "índice"},
    "structural":   {"structural", "estrutural", "viga", "beam", "laje", "slab", "pilar", "coluna",
                     "column", "concreto", "concrete", "armadura", "rebar", "reinforcement",
                     "flexão", "flexao", "bending", "cisalhamento", "shear", "momento", "moment",
                     "carga", "load", "dimensionamento", "dimensione", "elu", "els",
                     "estado", "limite", "limit", "nbr"},
    "geotechnical": {"geotécnica", "geotecnica", "geotechnical", "fundação", "fundacao",
                     "foundation", "solo", "soil", "estaca", "pile", "sapata", "footing",
                     "recalque", "settlement", "empuxo", "retaining", "contenção"},
    "mechanical":   {"mecânica", "mecanica", "mechanical", "torque", "fadiga", "fatigue",
                     "vibração", "vibration", "engrenagem", "gear", "rolamento", "bearing"},
    "electrical":   {"elétrica", "eletrica", "electrical", "circuito", "circuit", "tensão",
                     "voltage", "corrente", "current", "transformador", "transformer"},
    "statistics":   {"statistics", "estatística", "estatistica", "moda", "mode", "mean", "média",
                     "media", "median", "mediana", "desvio", "deviation", "variance", "variância",
                     "variancia", "população", "populacao", "population", "sample", "amostra",
                     "distribution", "distribuição", "distribuicao", "hypothesis", "hipótese"},
    "calculus":     {"integral", "derivada", "derivative", "calculus", "cálculo", "calculo",
                     "differential", "diferencial", "ode", "pde", "limit", "limite"},
    "simulation":   {"monte", "carlo", "hmc", "mcmc", "simulation", "simulação", "simulacao",
                     "stochastic", "estocástico", "annealing", "sampling", "amostragem"},
    "appsec":       {"appsec", "sast", "dast", "taint", "injection", "injeção", "xss", "csrf",
                     "owasp", "code", "código", "vulnerability", "vulnerabilidade"},
    "modeling":     {"model", "modelo", "valuation", "dcf", "forecast", "previsão", "projeção"},
}
INTENT = {
    "ui_ux_design": {"design", "interface", "ui", "ux", "moderna", "modern", "layout", "protótipo",
                     "prototype", "wireframe", "mockup", "usabilidade", "usability"},
    "compute":      {"calcule", "calculate", "compute", "cálculo", "calculo", "resolva", "solve",
                     "integrate", "integrar", "simule", "simulate", "estime", "estimate", "medir",
                     "dimensione", "dimensionar", "dimensionamento", "verifique", "verify"},
    "audit":        {"audit", "auditoria", "autópsia", "autopsy", "review", "revisar", "revisão",
                     "inspect", "inspecionar", "verificar", "verify", "analise", "analyze", "análise"},
    "build":        {"build", "construa", "construir", "crie", "create", "criar", "implemente",
                     "implement", "desenvolva", "develop", "make", "faça"},
    "optimize":     {"optimize", "otimizar", "otimize", "melhorar", "improve", "refactor", "refatorar",
                     "acelerar", "speed", "performance", "desempenho"},
    "research":     {"research", "pesquisa", "pesquise", "investigate", "investigar", "explore",
                     "descubra", "discover", "estudo", "study"},
}
PLATFORM = {
    "mobile":       {"mobile", "aplicativo", "app", "android", "ios", "smartphone", "celular",
                     "tablet", "flutter", "react-native", "swift", "kotlin"},
    "web":          {"web", "browser", "navegador", "site", "website", "página", "pagina", "spa"},
    "cloud":        {"cloud", "nuvem", "aws", "azure", "gcp", "kubernetes", "docker", "serverless"},
    "desktop":      {"desktop", "windows", "macos", "linux", "electron"},
}
AXES = {"domain": DOMAIN, "subdomain": SUBDOMAIN, "intent": INTENT, "platform": PLATFORM}

# facet weights when scoring attraction (domain/subdomain matter most; platform least)
AXIS_WEIGHT = {"domain": 3.0, "subdomain": 2.5, "intent": 1.5, "platform": 1.0}


# ── SELF-EVOLVING TAXONOMY (v1.55) ───────────────────────────────────────────────────────────
# The base tables above are the seed. A DURABLE overlay (JSON, under APEX_METHOD_HOME/library) is
# loaded at SESSION START and merged in, and every VALIDATED run appends the task's salient terms
# to the facet the run proved out — so the taxonomy's vocabulary GROWS with experience instead of
# staying frozen. JSON (not YAML/MD) is deliberate: stdlib-only, no PyYAML dependency, and the same
# durable-overlay pattern as grown_agents.json / agent_grants.json — deterministically mergeable.
import json as _json
import os as _os
import time as _time

# stopwords (PT+EN) so evolved anchors are SALIENT task terms, not filler
_STOP = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "um", "uma", "e", "para", "por",
         "com", "no", "na", "em", "que", "the", "of", "for", "and", "to", "in", "on", "with",
         "seu", "sua", "como", "ao", "à", "uns", "umas", "ou", "se", "é", "por"}


def _evolved_path():
    base = _os.environ.get("APEX_METHOD_HOME") or _os.path.expanduser("~/.apex-method")
    d = _os.path.join(base, "library")
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return _os.path.join(d, "taxonomy_evolved.json")


def _salient_terms(text, k=10):
    """Task terms worth learning: len>=4, not stopwords, deduped, order-preserving."""
    seen, out = set(), []
    for w in re.findall(r"[a-zà-ÿ0-9]{4,}", (text or "").lower()):
        if w in _STOP or w in seen:
            continue
        seen.add(w)
        out.append(w)
        if len(out) >= k:
            break
    return out


def _merge_evolved(axes_overlay):
    """Merge {axis: {facet: [terms]}} into the LIVE facet tables (idempotent; sets dedupe). New
    facets introduced by evolution are created on demand."""
    for axis, facets_map in (axes_overlay or {}).items():
        table = AXES.get(axis)
        if table is None or not isinstance(facets_map, dict):
            continue
        for facet, terms in facets_map.items():
            bucket = table.setdefault(facet, set())
            for t in (terms or []):
                if isinstance(t, str) and t.strip():
                    bucket.add(t.strip().lower())


def load_evolved():
    """Load the durable evolved-taxonomy overlay and merge it into the live tables. Called at import
    (SESSION START) so a vocabulary the runtime GREW in past sessions is active from the first
    classify(). Never raises."""
    try:
        with open(_evolved_path(), encoding="utf-8") as f:
            data = _json.load(f)
        _merge_evolved(data.get("axes", data))
        return data
    except Exception:
        return {}


def evolve(task, domain=None, subdomain=None, specialties=None, terms=None, persist=True):
    """Grow the taxonomy from a VALIDATED run: associate the task's salient terms with the
    validated-good domain/subdomain (and specialty subdomains), so future similar tasks classify
    correctly. Appends to the durable overlay and merges live. The CALLER gates on validation —
    this only learns from proven outcomes, never reinforces an unvalidated guess."""
    terms = terms or _salient_terms(task)
    if not terms or not (domain or subdomain or specialties):
        return {"status": "SKIPPED", "reason": "need salient terms + at least one target facet"}
    try:
        with open(_evolved_path(), encoding="utf-8") as f:
            data = _json.load(f)
    except Exception:
        data = {}
    axes = data.setdefault("axes", {})
    added = 0

    def _add(axis, facet):
        nonlocal added
        if not facet:
            return
        bucket = axes.setdefault(axis, {}).setdefault(facet, [])
        live = AXES.get(axis, {}).get(facet, set())
        for t in terms:
            if t not in bucket and t not in live:
                bucket.append(t)
                added += 1

    _add("domain", domain)
    _add("subdomain", subdomain)
    for sp in (specialties or []):
        _add("subdomain", sp)
    data["version"] = data.get("version", 1)
    data["updated_at"] = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    if persist:
        try:
            with open(_evolved_path(), "w", encoding="utf-8") as f:
                _json.dump(data, f, ensure_ascii=False, indent=1)
        except Exception as e:
            return {"status": "ERROR", "reason": str(e)[:80]}
    _merge_evolved(axes)                          # live-merge so THIS session sees it immediately
    return {"status": "EVOLVED", "added_terms": added, "path": _evolved_path(),
            "domain": domain, "subdomain": subdomain}


# session-start load: the grown vocabulary is active from the first classify()
_EVOLVED = load_evolved()


def _tokens(text):
    return set(re.findall(r"[a-zà-ÿ0-9\-]{2,}", (text or "").lower()))


def _score_axis(tokens, table):
    """Return (best_facet, hits) for one axis: the facet with the most trigger hits, else None."""
    best, best_hits = None, 0
    for facet, triggers in table.items():
        hits = len(tokens & triggers)
        if hits > best_hits:
            best, best_hits = facet, hits
    return best, best_hits


def classify(text):
    """Reduce free text (PT or EN) to canonical ENGLISH facets. This is the author's target output:
    {domain, subdomain, intent, platform, specialties, facets}. Language-independent by construction:
    both a PT task and an EN description map to the same facet tokens."""
    tokens = _tokens(text)
    picked, flat = {}, set()
    for axis, table in AXES.items():
        facet, hits = _score_axis(tokens, table)
        picked[axis] = facet
        if facet:
            flat.add(f"{axis}:{facet}")
    # specialties = every facet (any axis) that had at least one hit, as bare canonical tokens
    specialties = sorted({f for axis, table in AXES.items() for f, trg in table.items()
                          if tokens & trg})
    return {"domain": picked["domain"], "subdomain": picked["subdomain"],
            "intent": picked["intent"], "platform": picked["platform"],
            "specialties": specialties, "facets": flat}


def facets(text):
    """The flat canonical facet set (`{axis:facet}` tokens) for attraction scoring."""
    return classify(text)["facets"]


def facet_score(task_text, candidate_text):
    """Language-independent ATTRACTION weight in [0,1]: weighted overlap of the two texts' canonical
    facets. A PT task and an EN skill attract when they share a domain/subdomain, regardless of the
    surface words. This is the 'pesos e medidas' the author wants — computed on meaning, not tokens."""
    fa, fb = facets(task_text), facets(candidate_text)
    if not fa or not fb:
        return 0.0
    num = sum(AXIS_WEIGHT.get(f.split(":", 1)[0], 1.0) for f in (fa & fb))
    den = sum(AXIS_WEIGHT.get(f.split(":", 1)[0], 1.0) for f in (fa | fb))
    return round(num / den, 4) if den else 0.0


if __name__ == "__main__":
    import json
    def _jsonable(c):  # facets is a set -> render as a sorted list for display
        return {**c, "facets": sorted(c["facets"])}
    for t in ["crie uma interface moderna para aplicativo mobile",
              "calcule moda, desvio padrão e população de uma amostra",
              "faça uma auditoria de segurança em código python",
              "construa um modelo financeiro DCF",
              "build a modern UI for a mobile app"]:
        print(t, "->", json.dumps(_jsonable(classify(t)), ensure_ascii=False))
    print("\nPT task vs EN skill attraction (must be > 0, language-independent):")
    print(" moda/desvio (PT) vs 'statistics mean variance population' (EN):",
          facet_score("calcule moda e desvio padrão da população",
                      "expert in statistics: mean, variance, population, distributions"))
    print(" interface mobile (PT) vs 'T-Mobile carrier' (EN, name collision):",
          facet_score("crie interface moderna para aplicativo mobile", "Expert skill for T-Mobile"))
