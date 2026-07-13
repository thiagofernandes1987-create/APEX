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
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
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


def route(task: str, catalog: list, k: int = 3, threshold: float = 0.02):
    ids = [c["id"] for c in catalog]
    texts = [f"{c.get('name','')} {c.get('description','')} {' '.join(c.get('tags',[]))}" for c in catalog]
    if _SKLEARN:
        vec = TfidfVectorizer(ngram_range=(1, 2)).fit(texts)
        sims = cosine_similarity(vec.transform([task]), vec.transform(texts))[0]
        order = sims.argsort()[::-1][:k]
    else:
        sims = _rank(task, texts)
        order = sorted(range(len(sims)), key=lambda i: -sims[i])[:k]
    return [{"id": ids[i], "score": round(float(sims[i]), 3),
             "use_when": catalog[i].get("use_when", "")}
            for i in order if sims[i] > threshold]


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "build a frontend ux ui component"
    cat = load_catalog()
    for hit in route(task, cat):
        print(f"{hit['score']:.3f}  {hit['id']}  — {hit['use_when']}")
