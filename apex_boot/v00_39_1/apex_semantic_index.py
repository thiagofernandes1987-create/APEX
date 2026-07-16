#!/usr/bin/env python3
"""
APEX SEMANTIC GRAVITY ENGINE v1.0 (OPP-169 — DIFF_SEMANTIC_GRAVITY_001)
═══════════════════════════════════════════════════════════════════════
WHY: A busca hiperbólica (OPP-138) instruía o LLM a calcular
     cosine_similarity(query_embedding, anchor_embedding) — mas o LLM
     não tem acesso a embeddings. A gravidade era estimada por intuição
     ("vibed"). A sandbox TEM sklearn (OPP-71): este módulo computa a
     gravidade DE VERDADE, sobre 3 corpora:
       (a) páginas do kernel compilado (OPP-163)
       (b) CATALOG.md / SKILL.md do superrepo online (OPP-165)
       (c) memórias episódicas do snapshot SQLite (OPP-168)

USO:
  python3 apex_semantic_index.py build <pages_dir> [catalog.md] [apex_memory.db]
  python3 apex_semantic_index.py query "texto da consulta" [k]

WHAT_IF_FAILS:
  sklearn indisponível → o LLM usa o fallback LLM_BEHAVIOR do OPP-138
  (estimativa declarada com marcador [GRAVITY_APPROX]).
"""
import sys, os, re, json, pickle, sqlite3, hashlib

INDEX_FILE = "apex_semantic_index.pkl"


def _collect_pages(pages_dir):
    docs = []
    for f in sorted(os.listdir(pages_dir)):
        if f.endswith(".yaml"):
            txt = open(os.path.join(pages_dir, f), encoding="utf-8").read()
            docs.append({"id": f"page:{f[:-5]}", "kind": "page",
                         "text": txt[:12000], "ref": os.path.join(pages_dir, f)})
    return docs


def _collect_catalog(catalog_path):
    """CATALOG.md do superrepo: blocos por skill (## nome ... descrição)."""
    docs = []
    if not catalog_path or not os.path.exists(catalog_path):
        return docs
    txt = open(catalog_path, encoding="utf-8").read()
    blocks = re.split(r"^##+ ", txt, flags=re.M)
    for b in blocks[1:]:
        name = b.split("\n", 1)[0].strip()[:80]
        docs.append({"id": f"skill:{name}", "kind": "skill",
                     "text": b[:4000], "ref": catalog_path})
    return docs


def _collect_memories(db_path):
    """Memórias episódicas do SQLite (OPP-66/168) — tabela snapshots."""
    docs = []
    if not db_path or not os.path.exists(db_path):
        return docs
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        tables = {r[0] for r in rows}
        if "snapshots" in tables:
            for sid, data in con.execute(
                    "SELECT session_id, payload FROM snapshots "
                    "ORDER BY session_id DESC LIMIT 200"):
                docs.append({"id": f"memory:{sid}", "kind": "memory",
                             "text": str(data)[:4000], "ref": db_path})
        con.close()
    except sqlite3.Error as e:
        print(f"  aviso: memórias não indexadas ({e})")
    return docs


def build(pages_dir, catalog=None, db=None):
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = _collect_pages(pages_dir) + _collect_catalog(catalog) \
        + _collect_memories(db)
    if not docs:
        sys.exit("nenhum documento para indexar")
    vec = TfidfVectorizer(max_features=20000, ngram_range=(1, 2),
                          sublinear_tf=True)
    X = vec.fit_transform([d["text"] for d in docs])
    meta = [{k: d[k] for k in ("id", "kind", "ref")} for d in docs]
    with open(INDEX_FILE, "wb") as f:
        pickle.dump({"vectorizer": vec, "matrix": X, "meta": meta,
                     "sha8": hashlib.sha256(
                         json.dumps(meta).encode()).hexdigest()[:8]}, f)
    kinds = {}
    for d in docs:
        kinds[d["kind"]] = kinds.get(d["kind"], 0) + 1
    print(f"✓ índice: {len(docs)} docs {kinds} → {INDEX_FILE}")


class _RestrictedUnpickler(pickle.Unpickler):
    """V-02 audit fix: a swapped .pkl executed arbitrary code via pickle.load (RCE).
    Only the classes the index legitimately contains may be deserialized; anything
    else aborts. If the index is untrusted or fails here, rebuild with build() —
    the pages/catalog text is the source of truth."""
    _ALLOWED_PREFIXES = ("sklearn.", "scipy.", "numpy", "builtins")

    def find_class(self, module, name):
        if any(module == p.rstrip(".") or module.startswith(p) for p in self._ALLOWED_PREFIXES):
            return super().find_class(module, name)
        raise pickle.UnpicklingError(
            f"blocked class {module}.{name} — index .pkl not trusted; rebuild via build()")


def _load_index():
    with open(INDEX_FILE, "rb") as f:
        return _RestrictedUnpickler(f).load()


def query(text, k=5):
    from sklearn.metrics.pairwise import cosine_similarity
    idx = _load_index()
    q = idx["vectorizer"].transform([text])
    sims = cosine_similarity(q, idx["matrix"])[0]
    order = sims.argsort()[::-1][:k]
    out = []
    for i in order:
        m = idx["meta"][i]
        out.append({"gravity": round(float(sims[i]), 4), **m})
        print(f"[SEARCH_GRAVITY: {m['id']} | score={sims[i]:.3f} "
              f"| kind={m['kind']} | COMPUTED]")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "build":
        build(sys.argv[2],
              sys.argv[3] if len(sys.argv) > 3 else None,
              sys.argv[4] if len(sys.argv) > 4 else None)
    elif sys.argv[1] == "query":
        query(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 5)
