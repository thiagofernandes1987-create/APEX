#!/usr/bin/env python3
"""
router.py — Semantic skill router (APEX skill-resolution).

WHY THIS EXISTS:
  Given a task, decide WHICH skill (local or from the catalog) is most relevant,
  so the LLM loads specialized procedural knowledge on demand instead of guessing.

WHEN TO USE:
  At the "skill resolution" step of the pipeline (STANDARD+), whenever a task
  might benefit from a specialized skill (frontend, SEO, data, etc.).

HOW IT WORKS:
  TF-IDF (1-2 grams) over skill descriptions + cosine similarity to the task.

WHAT IT IS NOT / LIMITATION:
  TF-IDF is LEXICAL: it matches shared words, not meaning. A task written in a
  different language than the catalog (e.g. PT task vs EN description) can miss.
  For robustness, keep catalog descriptions in the same language as tasks, or
  swap in a real embedding model.

WHAT IF IT FAILS: TF-IDF is lexical; cross-language misses fall through to skill_scout + install request.
"""
import json, sys, os, re
sys.path.insert(0, os.path.dirname(__file__))

# AUD (Codex-confirmed): the catalog carries auto-generated STUB skills whose only content is
# "Expert skill for <Name>" (e.g. t-mobile, moderna-scientist). Their NAME token then wins by
# lexical collision — "mobile"->t-mobile, "moderna"(PT: modern)->moderna-scientist. A stub whose
# description is a generic template / too short is demoted so real skills rank above the noise.
_STUB_RE = re.compile(r"^\s*expert(?:[-\s]level)?\s+skill\s+for\b", re.I)


def _quality_factor(c):
    desc = (c.get("description") or c.get("use_when") or "").strip()
    if not desc or _STUB_RE.match(desc) or len(desc) < 25:
        return 0.25              # auto-generated / empty stub → heavy demotion (name-collision noise)
    return 1.0
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    _SKLEARN = True
except ImportError:                    # audit fix v1.17.0: sklearn was a HARD dependency —
    from _tfidf import rank as _rank   # the entry point crashed in any clean environment.
    _SKLEARN = False                   # Pure-python fallback keeps every router alive.

CATALOG = os.path.join(os.path.dirname(__file__), "..", "catalog", "skills_catalog.json")


def load_catalog(path=CATALOG):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def route(task: str, catalog: list, k: int = 3, threshold: float = 0.02, backend=None):
    """Rank skills for a task. backend (or env APEX_ROUTER_BACKEND):
      'word' (sklearn/word-TF-IDF, default), 'char' (language-robust char n-grams),
      'st' (sentence-transformers if installed). 'char'/'st' handle cross-language
      (PT task vs EN catalog) far better — the audit's known TF-IDF weakness."""
    ids = [c["id"] for c in catalog]
    texts = [f"{c.get('name','')} {c.get('description','')} {' '.join(c.get('tags',[]))}" for c in catalog]
    backend = backend or os.environ.get("APEX_ROUTER_BACKEND", "word")
    if backend in ("char", "st"):
        from _tfidf import semantic_rank
        sims, _used = semantic_rank(task, texts, backend=backend)
    elif _SKLEARN:
        vec = TfidfVectorizer(ngram_range=(1, 2)).fit(texts)
        sims = list(cosine_similarity(vec.transform([task]), vec.transform(texts))[0])
    else:
        sims = _rank(task, texts)
    # demote auto-generated name-stub skills so lexical name collisions (t-mobile, moderna-scientist)
    # cannot outrank real skills — the Codex-confirmed routing bug.
    sims = [float(sims[i]) * _quality_factor(catalog[i]) for i in range(len(sims))]
    order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
    return [{"id": ids[i], "score": round(float(sims[i]), 3),
             "use_when": catalog[i].get("use_when", "")}
            for i in order if sims[i] > threshold]


def route_confident(task: str, catalog: list, k: int = 3, min_confidence: float = 0.12, backend=None):
    """Like route() but returns a CONFIDENCE VERDICT: if the top score is below `min_confidence`,
    the result is flagged `confident=False` with 'no reliable skill — stage a discovery/install
    request' instead of surfacing weak lexical noise (Codex: 'threshold padrão é baixo demais')."""
    hits = route(task, catalog, k=k, threshold=0.02, backend=backend)
    top = hits[0]["score"] if hits else 0.0
    confident = top >= min_confidence
    return {"confident": confident, "top_score": top, "hits": hits,
            "verdict": ("ok" if confident else
                        "NO_RELIABLE_SKILL — top score below confidence floor; stage discovery/install (H5)")}


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "build a frontend ux ui component"
    cat = load_catalog()
    for hit in route(task, cat):
        print(f"{hit['score']:.3f}  {hit['id']}  — {hit['use_when']}")
