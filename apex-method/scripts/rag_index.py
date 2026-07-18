#!/usr/bin/env python3
"""
rag_index.py — node-based vector RAG index for FAST mapping of the whole repository.

WHY THIS EXISTS:
  "Where does X live?" should never require re-reading 16k files. This builds ONE index of
  NODES — every script, catalog, reference, test, meta file of the skill, plus the top-level
  areas of the APEX repo when a local clone is present — each with a summary and a sparse
  char-n-gram vector computed against a GLOBAL IDF (one vocabulary over the whole corpus, not
  per-text — the GPT audit correctly flagged per-text embedders as a ranking weakness).
  search(query) then maps any question to the right node(s) in milliseconds, language-robustly
  (PT/EN). Edges are NOT duplicated here: composition lives in attraction_graph; this index is
  the retrieval layer (RAG: retrieve the node, then Read the file it points to).

WHEN TO USE:
  - build()/rebuild(): at packaging time and after adding/renaming modules or references.
  - search("como funciona a memória durável?") -> top nodes with path + summary; then load the
    file(s). deep_research / the LLM use it to map the repo before acting.

WHAT IF IT FAILS:
  - missing index file -> built on the fly. Missing local clone -> repo-level nodes are
    skipped (the skill's own nodes always index). Never raises on normal input.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
INDEX_PATH = os.path.join(ROOT, "catalog", "rag_index.json")

TOP_TERMS = 48          # sparse vector size per node (bounds the index file)
SUMMARY_CHARS = 480


def _docstring(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
        m = re.search(r'"""(.*?)"""', text, re.S)
        return (m.group(1).strip() if m else text[:SUMMARY_CHARS])[:SUMMARY_CHARS]
    except Exception:
        return ""


def _md_head(path):
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
        body = re.sub(r"^---.*?---\s*", "", text, count=1, flags=re.S)   # skip frontmatter
        return " ".join(body.split())[:SUMMARY_CHARS]
    except Exception:
        return ""


def _json_meta(path):
    try:
        doc = json.load(open(path, encoding="utf-8"))
        if isinstance(doc, dict):
            meta = doc.get("_meta", {})
            note = meta.get("note", "") or doc.get("_doc", "")
            keys = ", ".join(list(doc)[:8])
            return f"{note} [keys: {keys}]"[:SUMMARY_CHARS]
        return f"list of {len(doc)} entries; first: {json.dumps(doc[0])[:200]}"[:SUMMARY_CHARS]
    except Exception:
        return ""


# Top-level APEX repo areas (indexed as pointer nodes when a local clone exists).
REPO_AREAS = {
    "agents/": "the 213+ AGENT.md persona files (community + native + cs_*) the spawn contract loads",
    "algorithms/": "41 mined assets: UCO, UCO-Sensor (SAST/SCA/taint), third-party libraries (indexed, not copied)",
    "apex_boot/": "the compiled boot kernel: 111 lazy-load pages + sha8 manifest (module_registry maps them)",
    "skills/": "the 3,784 native APEX skills (apex_native_skills_index.json is the fast index)",
    "integrations/": "23 MCP servers/plugins by domain (engineering, legal, healthcare, science-physics...)",
    "diffs/": "the DIFF packs v00.33-36: evolution rules with FMEA/RPN (diffs_lib.json indexes them)",
    "meta/": "anchors registry + repo-level metadata",
    "tools/": "repo maintenance tooling (roster generator, executor linter, skill forge)",
    "reference-docs/": "long-form reference documentation of the APEX framework",
}


def _collect_nodes():
    nodes = []
    def add(nid, ntype, path, summary):
        if summary:
            nodes.append({"id": nid, "type": ntype, "path": path, "summary": summary})
    for f in sorted(os.listdir(os.path.join(ROOT, "scripts"))):
        if f.endswith(".py"):
            add(f"script:{f[:-3]}", "script", f"scripts/{f}",
                _docstring(os.path.join(ROOT, "scripts", f)))
    for f in sorted(os.listdir(os.path.join(ROOT, "catalog"))):
        if f.endswith(".json"):
            add(f"catalog:{f[:-5]}", "catalog", f"catalog/{f}",
                _json_meta(os.path.join(ROOT, "catalog", f)))
    for f in sorted(os.listdir(os.path.join(ROOT, "references"))):
        if f.endswith(".md"):
            add(f"reference:{f[:-3]}", "reference", f"references/{f}",
                _md_head(os.path.join(ROOT, "references", f)))
    for f in ("SKILL.md", "spec.md", "inventario.md", "requirements.txt"):
        p = os.path.join(ROOT, f)
        if os.path.isfile(p):
            add(f"doc:{f}", "doc", f, _md_head(p))
    for f in sorted(os.listdir(os.path.join(ROOT, "tests"))):
        if f.endswith(".py"):
            add(f"test:{f[:-3]}", "test", f"tests/{f}",
                _docstring(os.path.join(ROOT, "tests", f)))
    for f in ("apex_llm.yaml", "llm_compat.json"):
        p = os.path.join(ROOT, "meta", f)
        if os.path.isfile(p):
            add(f"meta:{f}", "meta", f"meta/{f}",
                open(p, encoding="utf-8", errors="replace").read()[:SUMMARY_CHARS])
    # repo-level pointer nodes (local clone only)
    try:
        import repo_bridge
        root = repo_bridge._local_root()
        if root:
            for rel, desc in REPO_AREAS.items():
                if os.path.isdir(os.path.join(root, rel.rstrip("/"))):
                    add(f"repo:{rel.rstrip('/')}", "repo-area", rel, desc)
    except Exception:
        pass
    return nodes


def build(path=INDEX_PATH):
    """Build the index: collect nodes, fit ONE global char-n-gram IDF over every summary, embed
    each node, keep the TOP_TERMS strongest terms (sparse, bounded)."""
    from _tfidf import CharEmbedder
    nodes = _collect_nodes()
    emb = CharEmbedder().fit([n["summary"] for n in nodes])
    for n in nodes:
        vec = emb.embed(n["summary"])
        top = sorted(vec.items(), key=lambda kv: -abs(kv[1]))[:TOP_TERMS]
        n["terms"] = {g: round(w, 4) for g, w in top}
    doc = {"_meta": {"note": ("Node-based vector RAG index: one node per module/catalog/reference/"
                              "test/repo-area, sparse char-n-gram vectors under a GLOBAL IDF. "
                              "search(query) maps a question to the right nodes fast; then Read "
                              "the node's path. Rebuild after adding/renaming modules."),
                     "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                     "count": len(nodes), "top_terms": TOP_TERMS,
                     "idf": {g: round(v, 4) for g, v in emb.idf.items()}},
           "nodes": nodes}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False)
    return {"status": "OK", "path": path, "nodes": len(nodes)}


def rebuild(path=INDEX_PATH):
    return build(path=path)


_CACHE = {}


def load(path=INDEX_PATH):
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        build(path=path)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    _CACHE[path] = doc
    return doc


def search(query, k=5, node_type=None, path=INDEX_PATH):
    """Map a question (PT or EN) to the top-k nodes by cosine against the stored sparse vectors,
    using the SAME global IDF the index was built with (consistent space, not per-text)."""
    import math
    from _tfidf import _char_ngrams
    doc = load(path)
    idf = doc["_meta"].get("idf", {})
    from collections import Counter
    tf = Counter(_char_ngrams(query))
    qv = {g: c * idf.get(g, 1.0) for g, c in tf.items()}
    norm = math.sqrt(sum(v * v for v in qv.values())) or 1.0
    qv = {g: v / norm for g, v in qv.items()}
    scored = []
    for n in doc["nodes"]:
        if node_type and n["type"] != node_type:
            continue
        s = sum(w * qv.get(g, 0.0) for g, w in n["terms"].items())
        if s > 0:
            scored.append((s, n))
    scored.sort(key=lambda x: -x[0])
    return [{"id": n["id"], "type": n["type"], "path": n["path"],
             "score": round(s, 4), "summary": n["summary"][:160]}
            for s, n in scored[:k]]


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(json.dumps(build(), indent=1))
    else:
        q = " ".join(sys.argv[1:]) or "como funciona a memória durável entre sessões?"
        for hit in search(q):
            print(f"{hit['score']:.3f}  {hit['id']:32} {hit['path']:34} {hit['summary'][:60]}")
