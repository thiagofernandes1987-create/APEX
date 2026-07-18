#!/usr/bin/env python3
"""
attraction_graph.py — PRECOMPUTED gravitational routing graph (the author's "super-estrutura").

WHY THIS EXISTS:
  gravity.py recomputes TF-IDF attraction on every call — good for one task, wasteful for the
  ecosystem. The author's design: a ROUTING JSON that records, once, how every skill, script,
  diff and agent CONNECTS (edges with gravitational weights). Then composition becomes a graph
  WALK, not a re-discovery: you look up the FIRST competency a task needs and everything that
  completes/potentiates it ATTRACTS along the edges ("atração hiperbólica"). Example: the Tech
  Leader needs an audit → finds the code-auditor skill → the graph pulls in QA, programming
  logic, database, frontend/backend — because those edges were computed when the bodies joined
  the library. Every new discovery/inclusion calls rebuild() and the super-structure grows.

WHEN TO USE:
  - build()/rebuild(): at packaging time and after ANY new skill/script/diff/agent is added.
  - neighbors(id): what one body attracts directly.
  - expand(seeds): the attraction chain — the connected set that self-assembles from seed(s).
  - equip_for(need): task/competency text → seeds via gravity pull → expanded constellation.
    This is what agent_spawn uses to equip a spawned agent WITHOUT re-discovering.

HOW THE WEIGHTS WORK (same physics as gravity.py, precomputed):
  attraction(i,j) = nmass_i * nmass_j * proximity(i,j)   (TF-IDF cosine over body text)
  Each node keeps its top-K strongest edges above a floor. expand() walks edges with a decay
  per hop, so nearby bodies dominate but a strong 2-hop pull still joins the constellation.

WHAT IF IT FAILS:
  - missing graph file -> build() it on the fly from the catalogs (slower, same result).
  - a seed id not in the graph -> skipped; empty seeds -> empty expansion (honest).
  - catalogs missing -> the graph is whatever bodies exist; never raises on normal use.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

HERE = os.path.dirname(__file__)
GRAPH_PATH = os.path.join(HERE, "..", "catalog", "attraction_graph.json")

TOP_K = 8            # strongest edges kept per node
EDGE_FLOOR = 0.02    # attraction below this is noise, not structure
DECAY = 0.7          # per-hop decay in expand() (2-hop pull counts 0.7x)


def build(top_k=TOP_K, floor=EDGE_FLOOR, path=GRAPH_PATH):
    """Compute the full pairwise attraction over every body in the library and persist the
    top-K edges per node. Call again (rebuild) whenever a new body joins the library."""
    import gravity
    from _tfidf import pairwise
    R = gravity._normalize_mass(gravity.load_resources())
    texts = [r["text"] for r in R]
    sim = pairwise(texts)
    n = len(R)
    edges = {}
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                continue
            w = R[i]["nmass"] * R[j]["nmass"] * sim[i][j]
            if w >= floor:
                row.append((round(w, 4), R[j]["id"]))
        row.sort(reverse=True)
        edges[R[i]["id"]] = [{"id": rid, "w": w} for w, rid in row[:top_k]]
    doc = {"_meta": {"note": ("Precomputed gravitational routing: node = body (script/agent/"
                              "skill/diff), edge = attraction (nmass*nmass*cosine), top-"
                              f"{top_k} per node, floor {floor}. Rebuild after every new "
                              "discovery/inclusion so the super-structure keeps growing."),
                     "built_at": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()),
                     "nodes": n, "top_k": top_k, "floor": floor},
           "nodes": [{"id": r["id"], "type": r["type"], "mass": round(r["nmass"], 3)} for r in R],
           "edges": edges}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1, ensure_ascii=False)
    return {"status": "OK", "path": path, "nodes": n,
            "edges": sum(len(v) for v in edges.values())}


def rebuild(path=GRAPH_PATH):
    """Explicit alias: call after ANY new skill/script/diff/agent enters the catalogs."""
    return build(path=path)


_CACHE = {}


def load(path=GRAPH_PATH):
    if path in _CACHE:
        return _CACHE[path]
    try:
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        build(path=path)                       # missing/corrupt -> rebuild from catalogs
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    _CACHE[path] = doc
    return doc


def neighbors(body_id, k=TOP_K, path=GRAPH_PATH):
    """The bodies one node attracts directly (its strongest edges)."""
    return load(path)["edges"].get(body_id, [])[:k]


def expand(seeds, depth=2, budget=12, decay=DECAY, path=GRAPH_PATH):
    """The attraction chain: from seed body ids, walk the edges up to `depth` hops, scoring
    each reached body by (edge weight x decay^hop), accumulate, and return the strongest
    `budget` bodies grouped by type. This is 'tudo que se completa se atrai' — no re-discovery."""
    doc = load(path)
    types = {n["id"]: n["type"] for n in doc["nodes"]}
    score = {}
    frontier = [(s, 1.0, 0) for s in seeds if s in doc["edges"]]
    seen_hops = {s: 0 for s, _, _ in frontier}
    while frontier:
        node, w, hop = frontier.pop(0)
        if hop >= depth:
            continue
        for e in doc["edges"].get(node, []):
            gain = w * e["w"] * (decay ** hop)
            score[e["id"]] = score.get(e["id"], 0.0) + gain
            nxt_hop = hop + 1
            if e["id"] not in seen_hops or nxt_hop < seen_hops[e["id"]]:
                seen_hops[e["id"]] = nxt_hop
                frontier.append((e["id"], w * e["w"], nxt_hop))
    for s in seeds:                            # seeds are members — but only REAL bodies
        if s in doc["edges"]:
            score.setdefault(s, 1.0)
    ranked = sorted(score.items(), key=lambda x: -x[1])[:budget]
    out = {"members": [{"id": i, "type": types.get(i, "?"), "score": round(sc, 4)}
                       for i, sc in ranked], "by_type": {}}
    for m in out["members"]:
        out["by_type"].setdefault(m["type"], []).append(m["id"])
    return out


def equip_for(need, k_seed=2, depth=2, budget=10, path=GRAPH_PATH):
    """Competency text -> seed bodies (strongest task pull, via gravity) -> expanded
    constellation. The Tech-Leader flow: search the FIRST skill; the rest attracts."""
    import gravity
    con = gravity.constellation(need, budget=max(k_seed, 2))
    seeds = [o["id"] for o in con["constellation"][:k_seed]]
    exp = expand(seeds, depth=depth, budget=budget, path=path)
    exp["need"] = need
    exp["seeds"] = seeds
    return exp


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        print(json.dumps(build(), indent=1))
    else:
        need = " ".join(sys.argv[1:]) or "audit code security and review the backend"
        r = equip_for(need)
        print(f"NEED: {need}\nseeds: {r['seeds']}")
        for t, ids in r["by_type"].items():
            print(f"  {t:7}: {', '.join(ids)}")
