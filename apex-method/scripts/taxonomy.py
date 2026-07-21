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


def _merge_extra_seed():
    """v1.62: merge catalog/taxonomy_extra_seed.json into the base tables at import time.

    The seed carries (a) the curated PT+EN vocabulary for the gaps the v1.62 audit PROVED
    empirically (frontend/web tasks classified domain=None; trivial edits unrecognized) and
    (b) vocabulary mined from the OpenClaw maturity scorecard (agent-infra / automation /
    observability / devops / docs). Deterministic, stdlib-only; a missing or corrupt seed
    changes nothing (base tables remain the behavior of v1.61)."""
    import json as _json
    import os as _os
    cat = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "catalog")
    # two seeds, merged in order: curated+OpenClaw (extra) then the real-corpus mining (corpus).
    # v1.63: the corpus seed is the durable "memory" — vocabulary mined from the 3.784 skills +
    # 213 agents already labeled by domain. Both are optional; a missing/corrupt seed is a no-op.
    for name in ("taxonomy_extra_seed.json", "taxonomy_corpus_seed.json"):
        try:
            with open(_os.path.join(cat, name), encoding="utf-8") as f:
                seed = _json.load(f)
        except Exception:
            continue
        for axis, table in AXES.items():
            for facet, terms in (seed.get(axis) or {}).items():
                if isinstance(terms, list):
                    table.setdefault(facet, set()).update(t for t in terms if isinstance(t, str))


_merge_extra_seed()

# facet weights when scoring attraction (domain/subdomain matter most; platform least)
AXIS_WEIGHT = {"domain": 3.0, "subdomain": 2.5, "intent": 1.5, "platform": 1.0}


# ── SELF-EVOLVING TAXONOMY (v1.56) — two-tier, SQLite-backed ─────────────────────────────────
# The base tables above are the SEED. Learned vocabulary lives in a DURABLE SQLite overlay (stdlib
# sqlite3), NOT a monolithic JSON document — so it scales by INDEXED PARTIAL lookup (O(log n), only
# the task's tokens are queried) instead of loading the whole file every session. Two tiers, unified
# schema (same conceptual fields as AGENT.md/SKILL.md — bilingual + provenance + status):
#   triggers(term, axis, facet, status, uses)  — HOT PATH: term->facet, indexed; classify() reads
#         ONLY the ADOPTED rows for the CURRENT task's tokens (never the whole table).
#   term_meta(term, en, pt, validated_by, ts)  — COLD PATH: the bilingual pair + provenance the LLM
#         validates; never touched by classify().
# A term is CANDIDATE on first sight and ADOPTED after PROMOTE_N validations (like skills/vaccines),
# so one run's tokens never pollute classification. Facet↔facet dependency/escalation relations
# REUSE the existing Knowledge Graph vocabulary (memory.relate: causa|depende_de|refina|contradiz|
# suporta) — no new relation language. JSON overlays from v1.55 are migrated once, losslessly.
import json as _json
import os as _os
import time as _time
import sqlite3 as _sqlite

PROMOTE_N = 2          # validations before a learned term is ADOPTED (matches the vaccine gate)

# stopwords (PT+EN) so evolved anchors are SALIENT task terms, not filler
_STOP = {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "um", "uma", "e", "para", "por",
         "com", "no", "na", "em", "que", "the", "of", "for", "and", "to", "in", "on", "with",
         "seu", "sua", "como", "ao", "à", "uns", "umas", "ou", "se", "é", "por"}


def _library_dir():
    base = _os.environ.get("APEX_METHOD_HOME") or _os.path.expanduser("~/.apex-method")
    d = _os.path.join(base, "library")
    try:
        _os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _db_path():
    return _os.path.join(_library_dir(), "taxonomy_evolved.db")


def _legacy_json():
    return _os.path.join(_library_dir(), "taxonomy_evolved.json")


def _init_db(con):
    con.execute("CREATE TABLE IF NOT EXISTS triggers("
                "term TEXT NOT NULL, axis TEXT NOT NULL, facet TEXT NOT NULL, "
                "status TEXT NOT NULL DEFAULT 'CANDIDATE', uses INTEGER NOT NULL DEFAULT 0, "
                "PRIMARY KEY(term, axis, facet))")
    con.execute("CREATE INDEX IF NOT EXISTS idx_triggers_term ON triggers(term)")
    con.execute("CREATE TABLE IF NOT EXISTS term_meta("
                "term TEXT PRIMARY KEY, en TEXT, pt TEXT, validated_by TEXT, ts TEXT)")
    con.commit()
    _migrate_legacy(con)


def _migrate_legacy(con):
    """One-time, lossless import of the v1.55 JSON overlay: its terms were already validated, so they
    enter ADOPTED. The file is renamed to *.migrated so the import runs exactly once."""
    p = _legacy_json()
    if not _os.path.isfile(p):
        return
    try:
        with open(p, encoding="utf-8") as f:
            data = _json.load(f)
        for axis, fmap in (data.get("axes", {}) or {}).items():
            for facet, terms in (fmap or {}).items():
                for t in (terms or []):
                    con.execute("INSERT OR IGNORE INTO triggers(term,axis,facet,status,uses) "
                                "VALUES(?,?,?,?,?)", (str(t).lower(), axis, facet, "ADOPTED", PROMOTE_N))
        con.commit()
        _os.rename(p, p + ".migrated")
    except Exception:
        pass


def _con(create=False):
    """Open the overlay DB. Returns None (zero cost) when no overlay exists yet AND create=False —
    so classify() adds NO overhead until the runtime has actually learned something."""
    p = _db_path()
    if not create and not _os.path.isfile(p) and not _os.path.isfile(_legacy_json()):
        return None
    try:
        con = _sqlite.connect(p)
        _init_db(con)
        return con
    except Exception:
        return None


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


def _overlay_hits(tokens):
    """{axis: {facet: hits}} from the ADOPTED overlay, querying ONLY the current task's tokens via
    the term index (O(len(tokens)·log n)) — never a full-table scan/load."""
    out = {ax: {} for ax in AXES}
    if not tokens:
        return out
    con = _con(create=False)
    if con is None:
        return out
    try:
        toks = list(tokens)
        qs = ",".join("?" * len(toks))
        for axis, facet in con.execute(
                f"SELECT axis, facet FROM triggers WHERE status='ADOPTED' AND term IN ({qs})",
                toks):
            if axis in out:
                out[axis][facet] = out[axis].get(facet, 0) + 1
    except Exception:
        pass
    finally:
        con.close()
    return out


def load_evolved():
    """Ensure the overlay DB exists and the legacy v1.55 JSON is migrated. Does NOT bulk-load into
    memory — the whole point of SQLite is INDEXED PARTIAL lookup, so nothing is loaded until the
    first classify() queries the task's own tokens. Called at import (cheap: no-op if no overlay)."""
    if _os.path.isfile(_db_path()) or _os.path.isfile(_legacy_json()):
        con = _con(create=True)
        if con:
            con.close()
    return {"db": _db_path()}


def evolve(task, domain=None, subdomain=None, specialties=None, terms=None, persist=True):
    """Grow the taxonomy from a VALIDATED run: associate the task's salient terms with the
    validated-good domain/subdomain. Each term is CANDIDATE on first sight and ADOPTED after
    PROMOTE_N validations (so one run's tokens never drive classification). Terms already in the
    BASE tables are skipped. The CALLER gates on validation — this never reinforces an unvalidated
    guess. Indexed append; no whole-file rewrite."""
    terms = terms or _salient_terms(task)
    targets = [("domain", domain), ("subdomain", subdomain)]
    targets += [("subdomain", sp) for sp in (specialties or [])]
    targets = [(ax, f) for ax, f in targets if f]
    if not terms or not targets:
        return {"status": "SKIPPED", "reason": "need salient terms + at least one target facet"}
    con = _con(create=True)
    if con is None:
        return {"status": "ERROR", "reason": "cannot open overlay db"}
    added = promoted = 0
    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    try:
        for t in terms:
            con.execute("INSERT OR IGNORE INTO term_meta(term, ts) VALUES(?, ?)", (t, now))
            for axis, facet in targets:
                if t in AXES.get(axis, {}).get(facet, set()):
                    continue                     # already a base trigger — nothing to learn
                row = con.execute("SELECT uses, status FROM triggers WHERE term=? AND axis=? "
                                  "AND facet=?", (t, axis, facet)).fetchone()
                if row is None:
                    st = "ADOPTED" if PROMOTE_N <= 1 else "CANDIDATE"
                    con.execute("INSERT INTO triggers(term,axis,facet,status,uses) VALUES(?,?,?,?,1)",
                                (t, axis, facet, st))
                    added += 1
                    if st == "ADOPTED":
                        promoted += 1
                else:
                    uses = row[0] + 1
                    st = "ADOPTED" if uses >= PROMOTE_N else "CANDIDATE"
                    con.execute("UPDATE triggers SET uses=?, status=? WHERE term=? AND axis=? "
                                "AND facet=?", (uses, st, t, axis, facet))
                    if st == "ADOPTED" and row[1] != "ADOPTED":
                        promoted += 1
        con.commit()
    except Exception as e:
        con.close()
        return {"status": "ERROR", "reason": str(e)[:80]}
    con.close()
    return {"status": "EVOLVED", "added_terms": added, "promoted": promoted,
            "db": _db_path(), "domain": domain, "subdomain": subdomain}


def translate(term, en, pt, validated_by="llm", facets_from=None):
    """UNIFIED SCHEMA — the bilingual pair the LLM validates (cold path). Records EN/PT + provenance
    in term_meta, and PROPAGATES the term's facets to BOTH languages so a PT task and its EN
    translation attract on the same facet (the bilingual convention of AGENT.md/SKILL.md, now in the
    taxonomy). `facets_from` defaults to `term`'s own triggers."""
    con = _con(create=True)
    if con is None:
        return {"status": "ERROR", "reason": "cannot open overlay db"}
    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    src = (facets_from or term).lower()
    try:
        con.execute("INSERT OR REPLACE INTO term_meta(term, en, pt, validated_by, ts) "
                    "VALUES(?,?,?,?,?)", (term.lower(), en, pt, validated_by, now))
        rows = con.execute("SELECT axis, facet, status, uses FROM triggers WHERE term=?",
                           (src,)).fetchall()
        propagated = 0
        for lang_term in {en.lower(), pt.lower()} - {""}:
            for axis, facet, status, uses in rows:
                con.execute("INSERT OR IGNORE INTO triggers(term,axis,facet,status,uses) "
                            "VALUES(?,?,?,?,?)", (lang_term, axis, facet, status, uses))
                propagated += 1
        con.commit()
    except Exception as e:
        con.close()
        return {"status": "ERROR", "reason": str(e)[:80]}
    con.close()
    return {"status": "OK", "term": term.lower(), "en": en, "pt": pt, "propagated": propagated}


def relate_facets(src_facet, dst_facet, rel="depende_de"):
    """Facet↔facet dependency / escalation, recorded in the EXISTING Knowledge Graph (memory.relate)
    — REUSING its typed-edge vocabulary (causa|depende_de|refina|contradiz|suporta), never a new
    relation language. A subdomain that 'escalates to' its domain is modeled as `depende_de`."""
    try:
        import memory
        return memory.MemoryStore().relate_text(f"facet:{src_facet}", f"facet:{dst_facet}", rel)
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:80]}


def stats():
    """Overlay health: candidate/adopted counts + how many terms carry a validated bilingual pair."""
    con = _con(create=False)
    if con is None:
        return {"adopted": 0, "candidate": 0, "translated": 0}
    try:
        adopted = con.execute("SELECT COUNT(*) FROM triggers WHERE status='ADOPTED'").fetchone()[0]
        cand = con.execute("SELECT COUNT(*) FROM triggers WHERE status='CANDIDATE'").fetchone()[0]
        tr = con.execute("SELECT COUNT(*) FROM term_meta WHERE en IS NOT NULL AND pt IS NOT NULL"
                         ).fetchone()[0]
        return {"adopted": adopted, "candidate": cand, "translated": tr, "db": _db_path()}
    finally:
        con.close()


# session-start: ensure the overlay DB exists / migrate legacy JSON (no bulk load)
_EVOLVED = load_evolved()


def _tokens(text):
    # defensive: classify() may be handed a non-string (int/dict/list) by upstream callers
    # (orchestrator dissect fallback, MCP tool args). Coerce instead of raising (kernel contract:
    # the recognition layer never crashes the pipeline).
    if not isinstance(text, str):
        text = "" if text is None else str(text)
    return set(re.findall(r"[a-zà-ÿ0-9\-]{2,}", text.lower()))


def _score_axis(tokens, table):
    """Return (best_facet, hits) for one axis: the facet with the most trigger hits, else None."""
    best, best_hits = None, 0
    for facet, triggers in table.items():
        hits = len(tokens & triggers)
        if hits > best_hits:
            best, best_hits = facet, hits
    return best, best_hits


def _combined_hits(tokens):
    """Per-axis facet hit counts merging the in-memory BASE tables with the ADOPTED SQLite overlay
    (one indexed query for the task's tokens). This is the single place base + learned vocabulary
    meet, so classify() and specialties stay consistent."""
    overlay = _overlay_hits(tokens)
    out = {}
    for axis, table in AXES.items():
        hits = {}
        for facet, trg in table.items():
            h = len(tokens & trg)
            if h:
                hits[facet] = h
        for facet, h in overlay.get(axis, {}).items():
            hits[facet] = hits.get(facet, 0) + h
        out[axis] = hits
    return out


def classify(text):
    """Reduce free text (PT or EN) to canonical ENGLISH facets. This is the author's target output:
    {domain, subdomain, intent, platform, specialties, facets}. Language-independent by construction:
    both a PT task and an EN description map to the same facet tokens. Merges the base seed with the
    ADOPTED learned overlay (SQLite, queried for this task's tokens only)."""
    tokens = _tokens(text)
    hits = _combined_hits(tokens)
    picked, flat = {}, set()
    for axis in AXES:
        d = hits.get(axis, {})
        facet = max(d, key=d.get) if d else None
        picked[axis] = facet
        if facet:
            flat.add(f"{axis}:{facet}")
    # specialties = every facet (any axis) that had at least one hit (base OR learned overlay)
    specialties = sorted({f for axis in AXES for f in hits.get(axis, {})})
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
