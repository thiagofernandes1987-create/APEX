#!/usr/bin/env python3
"""
_tfidf.py — Pure-Python TF-IDF + cosine fallback (no sklearn required).

WHY THIS EXISTS:
  router/gravity/agent_registry used sklearn's TfidfVectorizer as a HARD dependency,
  so the orchestrator (the skill's entry point) crashed with ModuleNotFoundError in any
  environment without scikit-learn (benchmark: 19/24 in a clean env). This module gives
  the same (1,2)-gram TF-IDF + cosine ranking in pure stdlib, so every routing script
  degrades gracefully instead of dying.

WHEN: imported by router.py / gravity.py / agent_registry.py when sklearn is missing.

WHAT IF IT FAILS: it is stdlib-only; the only failure mode is empty input, which
  returns empty rankings (callers already handle []).
"""
import math
import re
from collections import Counter

_TOKEN = re.compile(r"[a-z0-9]+")


def _ngrams(text, nrange=(1, 2)):
    toks = _TOKEN.findall(text.lower())
    out = list(toks) if nrange[0] == 1 else []
    if nrange[1] >= 2:
        out += [f"{a} {b}" for a, b in zip(toks, toks[1:])]
    return out


class TinyTfidf:
    """Minimal TfidfVectorizer-alike: fit(corpus) -> transform(texts) -> sparse dict vectors."""

    def __init__(self, ngram_range=(1, 2)):
        self.ngram_range = ngram_range
        self.idf = {}

    def fit(self, corpus):
        n = len(corpus) or 1
        df = Counter()
        for text in corpus:
            df.update(set(_ngrams(text, self.ngram_range)))
        # smooth idf (same shape as sklearn's smooth_idf)
        self.idf = {t: math.log((1 + n) / (1 + c)) + 1.0 for t, c in df.items()}
        return self

    def transform_one(self, text):
        tf = Counter(_ngrams(text, self.ngram_range))
        vec = {t: c * self.idf[t] for t, c in tf.items() if t in self.idf}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {t: v / norm for t, v in vec.items()}

    def transform(self, texts):
        return [self.transform_one(t) for t in texts]


def cosine(a: dict, b: dict) -> float:
    if len(b) < len(a):
        a, b = b, a
    return sum(v * b.get(t, 0.0) for t, v in a.items())


def rank(query, texts, ngram_range=(1, 2)):
    """Return cosine similarity of `query` against each text (list of floats)."""
    vec = TinyTfidf(ngram_range).fit(list(texts) + [query])
    q = vec.transform_one(query)
    return [cosine(q, vec.transform_one(t)) for t in texts]


def pairwise(texts, ngram_range=(1, 2)):
    """Full pairwise cosine matrix (list of lists) — used by gravity's synergy term."""
    vec = TinyTfidf(ngram_range).fit(list(texts))
    vs = vec.transform(texts)
    n = len(vs)
    M = [[0.0] * n for _ in range(n)]
    for i in range(n):
        M[i][i] = 1.0
        for j in range(i + 1, n):
            M[i][j] = M[j][i] = cosine(vs[i], vs[j])
    return M
