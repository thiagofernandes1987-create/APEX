#!/usr/bin/env python3
"""
memory.py — APEX live cross-session vector memory (Op1): episodic + semantic, on SQLite.

WHY THIS EXISTS:
  The snapshot lives in context and dies on interruption; the semantic index was built once at
  build-time. This is the live memory: an INCREMENTAL store, read at the start of a session and
  written at the end, so knowledge survives across sessions instead of being rebuilt. It is the
  durable partner of project_ledger (which holds the plan; this holds what was learned).

DESIGN (agreed with the author):
  - Storage: SQLite (stdlib) at ~/.apex-method/memory.db by default. An optional MongoDB adapter
    can be plugged for those who run a server; SQLite is always the default (offline, portable).
  - Vectors: _tfidf.CharEmbedder (char-n-gram, pure-stdlib, language-robust) with an embeddings
    hook (sentence-transformers when present). recall() = cosine top-k (brute force, fine to ~10-50k).
  - SHA-256: (1) content-address/dedup for SEMANTIC facts (same fact stored once); (2) an
    integrity column; (3) chaining of governance events (each event carries the previous hash).
  - Two kinds: EPISODIC (session findings, keyed by sha(text+ts+session) — not deduped) and
    SEMANTIC (distilled facts, deduped by sha(text)).
  - Knowledge Graph (B1): typed edges between memories (causa/contradiz/depende_de/refina/
    suporta). Directional relations are kept ACYCLIC via the hypothesis_dag engine. recall_graph()
    turns retrieval into a graph walk — "the fact AND everything that contradicts it" — instead of
    a flat top-k. Every edge is also written to the governance ledger, so the graph is durable.
  - Curated writes: remember_from_snapshot() persists the snapshot's findings (not every run).
  - Governance ledger: record_event(kind, subject, action, evidence) — a neutral API that
    code_genetics (vaccine promotion), agent_registry (skill grant), crystallization (diff
    promote/demote) and SR_47 (rule on/off) CALL, so promotions/demotions become durable memory.

WHAT IF IT FAILS:
  Pure stdlib; a missing DB is created on first write. recall on an empty store returns [].
  Any embed error falls back to a zero vector (that memory simply won't match). Never raises
  on normal use.
"""
import hashlib
import json
import os
import sqlite3
import time

sys_path_added = False
try:
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from _tfidf import CharEmbedder, cosine
except Exception:                       # degrade: no vectors -> exact-text recall only
    CharEmbedder, cosine = None, None

# AUD-W1: APEX_METHOD_HOME redirects the durable store (tests/CI isolation) — see config.py.
DB_DEFAULT = os.path.join(os.environ.get("APEX_METHOD_HOME")
                          or os.path.expanduser("~/.apex-method"), "memory.db")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MemoryStore:
    def __init__(self, db_path=DB_DEFAULT):
        self.db_path = db_path
        # RT-10: a bare relative name ("bare.db") has an empty dirname; os.makedirs("") raises.
        # Resolve the absolute parent so a cwd-relative db path is always creatable.
        parent = os.path.dirname(os.path.abspath(db_path))
        os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _con(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        con = self._con()
        con.execute("CREATE TABLE IF NOT EXISTS memory("
                    "sha TEXT PRIMARY KEY, kind TEXT, text TEXT, meta TEXT, vector TEXT, "
                    "ts REAL, session TEXT)")
        con.execute("CREATE TABLE IF NOT EXISTS ledger("
                    "sha TEXT PRIMARY KEY, ts REAL, kind TEXT, subject TEXT, action TEXT, "
                    "evidence TEXT, prev_sha TEXT)")
        # B1 — Knowledge Graph: typed edges between memories. This turns recall from "top-k by
        # similarity" into a graph walk ("give me fact X and everything that contradicts it").
        con.execute("CREATE TABLE IF NOT EXISTS relations("
                    "sha TEXT PRIMARY KEY, src TEXT, dst TEXT, rel TEXT, weight REAL, ts REAL)")
        con.commit()
        con.close()

    # ── embedding ─────────────────────────────────────────────────────────
    def _embed(self, text):
        if CharEmbedder is None:
            return {}
        try:
            emb = CharEmbedder().fit([text])
            return emb.embed(text)
        except Exception:
            return {}

    # ── write ─────────────────────────────────────────────────────────────
    def remember(self, text, kind="semantic", meta=None, session="default"):
        """Store a memory. SEMANTIC is content-addressed (dedup by sha(text)); EPISODIC is
        keyed by sha(text+ts+session) so repeated events stay distinct. Returns the sha."""
        text = (text or "").strip()
        if not text:
            return None
        if kind == "semantic":
            sha = _sha(text)
        else:
            sha = _sha(f"{text}|{time.time()}|{session}")
        con = self._con()
        con.execute("INSERT OR REPLACE INTO memory VALUES(?,?,?,?,?,?,?)",
                    (sha, kind, text, json.dumps(meta or {}, ensure_ascii=False),
                     json.dumps(self._embed(text)), time.time(), session))
        con.commit()
        con.close()
        return sha

    def remember_from_snapshot(self, snapshot, session="default"):
        """Curated write: persist a snapshot's findings (episodic) + objective (semantic).
        This is the ONLY automatic write path (author's spec: curated, not every run)."""
        shas = []
        if snapshot.get("objective"):
            shas.append(self.remember(f"objective: {snapshot['objective']}", "semantic",
                                      {"mode": snapshot.get("mode")}, session))
        for f in snapshot.get("findings", []):
            txt = f"{f.get('what','')} | where={f.get('where','')} | how={f.get('how','')}"
            shas.append(self.remember(txt, "episodic",
                                      {"confidence": f.get("confidence")}, session))
        return [s for s in shas if s]

    # ── read ──────────────────────────────────────────────────────────────
    def recall(self, query, k=5, kind=None):
        """Top-k memories by cosine of char-n-gram vectors (brute force). Filter by kind."""
        con = self._con()
        rows = con.execute("SELECT sha, kind, text, meta, vector, ts, session FROM memory"
                           + (" WHERE kind=?" if kind else ""),
                           (kind,) if kind else ()).fetchall()
        con.close()
        if not rows:
            return []
        qv = self._embed(query)
        scored = []
        for sha, k_, text, meta, vec, ts, session in rows:
            v = json.loads(vec) if vec else {}
            score = cosine(qv, v) if (cosine and qv and v) else (
                1.0 if query.lower() in text.lower() else 0.0)   # exact-text fallback
            scored.append((score, {"sha": sha, "kind": k_, "text": text,
                                   "meta": json.loads(meta or "{}"), "score": round(score, 4),
                                   "ts": ts, "session": session}))
        scored.sort(key=lambda x: -x[0])
        return [m for s, m in scored[:k] if s > 0]

    # ── governance ledger (promotions/demotions become durable memory) ────
    @staticmethod
    def _ledger_hash(ts, kind, subject, action, evidence_json, prev_sha):
        """Canonical content hash for a ledger event. RT-05: the hash MUST cover every mutable
        field (ts, kind, subject, action, evidence, prev_sha) so tampering any column is detectable.
        A stable, sorted JSON canonicalization keeps write-time and verify-time hashes identical."""
        canonical = json.dumps(
            {"ts": ts, "kind": kind, "subject": subject, "action": action,
             "evidence": evidence_json, "prev_sha": prev_sha},
            sort_keys=True, ensure_ascii=False)
        return _sha(canonical)

    def record_event(self, kind, subject, action, evidence=None):
        """Neutral API the subsystems CALL when a rule/diff/agent/skill/vaccine is promoted or
        demoted or an error is corrected. SHA-256 chained (each event carries the previous hash)
        so the ledger is tamper-evident. Also mirrored as a semantic memory for recall."""
        con = self._con()
        prev = con.execute("SELECT sha FROM ledger ORDER BY ts DESC LIMIT 1").fetchone()
        prev_sha = prev[0] if prev else ""
        # RT-05: hash the SAME ts and evidence we store (one time.time() read, not two) so
        # verify_ledger can recompute the content hash and detect any later column edit.
        ts = time.time()
        evidence_json = json.dumps(evidence or {}, ensure_ascii=False)
        sha = self._ledger_hash(ts, kind, subject, action, evidence_json, prev_sha)
        con.execute("INSERT OR REPLACE INTO ledger VALUES(?,?,?,?,?,?,?)",
                    (sha, ts, kind, subject, action, evidence_json, prev_sha))
        con.commit()
        con.close()
        # mirror into semantic memory so `recall` surfaces the evolution
        self.remember(f"[{kind}] {subject}: {action}", "semantic",
                      {"ledger_event": sha, "prev": prev_sha})
        return {"sha": sha, "prev_sha": prev_sha, "kind": kind, "subject": subject, "action": action}

    def verify_ledger(self):
        """Re-walk the chain: confirm each event's prev_sha matches its predecessor AND that its
        stored sha equals the recomputed content hash. RT-05: recomputing the hash makes a silent
        edit to any column (kind/subject/action/evidence/ts) break verification, not just a broken
        prev_sha pointer."""
        con = self._con()
        rows = con.execute("SELECT sha, ts, kind, subject, action, evidence, prev_sha FROM ledger "
                           "ORDER BY ts ASC").fetchall()
        con.close()
        ok, prev, reason = True, "", None
        for sha, ts, kind, subject, action, evidence, prev_sha in rows:
            if prev_sha != prev:
                ok, reason = False, "chain pointer mismatch"
                break
            if self._ledger_hash(ts, kind, subject, action, evidence, prev_sha) != sha:
                ok, reason = False, "content hash mismatch"
                break
            prev = sha
        out = {"ok": ok, "events": len(rows)}
        if reason:
            out["reason"] = reason
        return out

    # ── Knowledge Graph (B1): typed edges + graph-walk recall ──────────────
    # A small, fixed relation vocabulary. The DIRECTIONAL/logical ones (causa/depende_de/refina)
    # must stay ACYCLIC — a cycle there is a reasoning error — so they are cycle-checked through
    # the faithful hypothesis_dag engine before insert. The SYMMETRIC ones (contradiz/suporta)
    # may form loops and are not cycle-checked.
    REL_TYPES = ("causa", "contradiz", "depende_de", "refina", "suporta")
    ACYCLIC_RELS = ("causa", "depende_de", "refina")

    def _acyclic_edges(self, rel):
        con = self._con()
        rows = con.execute("SELECT src, dst FROM relations WHERE rel=?", (rel,)).fetchall()
        con.close()
        return rows

    def relate(self, src_sha, dst_sha, rel, weight=1.0):
        """Add a typed edge src --rel--> dst between two existing memories. For a DIRECTIONAL
        relation (causa/depende_de/refina) the edge is rejected if it would create a cycle
        (checked via hypothesis_dag). The edge is also recorded in the governance ledger so the
        graph's growth is itself durable, auditable memory. Returns a status dict."""
        if rel not in self.REL_TYPES:
            return {"status": "REFUSED", "reason": f"unknown rel '{rel}'; valid: {self.REL_TYPES}"}
        if src_sha == dst_sha:
            return {"status": "REFUSED", "reason": "self-loop"}
        con = self._con()
        have = {r[0] for r in con.execute("SELECT sha FROM memory WHERE sha IN (?,?)",
                                          (src_sha, dst_sha)).fetchall()}
        con.close()
        if {src_sha, dst_sha} - have:
            return {"status": "REFUSED", "reason": "src/dst not in memory (remember() first)"}
        if rel in self.ACYCLIC_RELS:
            try:
                import hypothesis_dag
                g = hypothesis_dag.HypothesisDAG()
                for s, d in self._acyclic_edges(rel):
                    g.add_edge(s, d)
                if not g.add_edge(src_sha, dst_sha):        # cycle -> rejected by the engine
                    return {"status": "REFUSED", "reason": f"cycle in '{rel}' rejected (DAG)"}
            except Exception:
                pass                                        # engine missing -> allow (degrade)
        sha = _sha(f"{src_sha}|{dst_sha}|{rel}")
        con = self._con()
        con.execute("INSERT OR REPLACE INTO relations VALUES(?,?,?,?,?,?)",
                    (sha, src_sha, dst_sha, rel, float(weight), time.time()))
        con.commit()
        con.close()
        self.record_event("knowledge_edge", f"{src_sha[:8]}--{rel}-->{dst_sha[:8]}", "relate",
                          {"weight": weight})
        return {"status": "OK", "sha": sha, "src": src_sha, "dst": dst_sha, "rel": rel}

    def relate_text(self, src_text, dst_text, rel, weight=1.0, session="default"):
        """Convenience: ensure both facts exist as semantic memories, then relate them."""
        s = self.remember(src_text, "semantic", session=session)
        d = self.remember(dst_text, "semantic", session=session)
        if not (s and d):
            return {"status": "REFUSED", "reason": "empty text"}
        return self.relate(s, d, rel, weight)

    def neighbors(self, sha, rel=None, direction="out"):
        """Direct edges of a node. direction='out' (sha --rel--> ?), 'in' (? --rel--> sha),
        or 'both'. Returns edge dicts with the neighbour's text."""
        con = self._con()
        q, args = "SELECT src, dst, rel, weight FROM relations WHERE ", []
        clauses = []
        if direction in ("out", "both"):
            clauses.append("src=?"); args.append(sha)
        if direction in ("in", "both"):
            clauses.append("dst=?"); args.append(sha)
        q += "(" + " OR ".join(clauses) + ")"
        if rel:
            q += " AND rel=?"; args.append(rel)
        rows = con.execute(q, args).fetchall()
        texts = dict(con.execute("SELECT sha, text FROM memory").fetchall())
        con.close()
        out = []
        for src, dst, r, w in rows:
            other = dst if src == sha else src
            out.append({"src": src, "dst": dst, "rel": r, "weight": w,
                        "neighbor": other, "neighbor_text": texts.get(other, "")})
        return out

    def walk(self, start_sha, rel_types=None, depth=2, direction="out"):
        """Bounded BFS from start_sha over the typed edges (optionally filtered by rel_types),
        up to `depth` hops. Returns the reachable nodes (with text + the hop distance)."""
        con = self._con()
        edges = con.execute("SELECT src, dst, rel FROM relations").fetchall()
        texts = dict(con.execute("SELECT sha, text FROM memory").fetchall())
        con.close()
        rels = set(rel_types) if rel_types else None
        adj = {}
        for src, dst, r in edges:
            if rels and r not in rels:
                continue
            if direction in ("out", "both"):
                adj.setdefault(src, []).append((dst, r))
            if direction in ("in", "both"):
                adj.setdefault(dst, []).append((src, r))
        seen, frontier, out = {start_sha}, [(start_sha, 0)], []
        while frontier:
            node, d = frontier.pop(0)
            if d >= depth:
                continue
            for nxt, r in adj.get(node, []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                out.append({"sha": nxt, "text": texts.get(nxt, ""), "via": r, "hop": d + 1})
                frontier.append((nxt, d + 1))
        return out

    def recall_graph(self, query, k=3, depth=1, rel=None):
        """Graph-aware recall: seed with recall(query, k) (char-n-gram top-k), then EXPAND along
        the typed edges up to `depth` hops. This answers 'give me the fact and everything that
        <rel> it' — e.g. rel='contradiz' surfaces the seed AND its contradictions. Returns
        {seeds, expanded, edges_followed}."""
        seeds = self.recall(query, k=k)
        rel_types = [rel] if rel else None
        expanded, seen_sha = [], {s["sha"] for s in seeds}
        for s in seeds:
            for node in self.walk(s["sha"], rel_types=rel_types, depth=depth, direction="both"):
                if node["sha"] not in seen_sha:
                    seen_sha.add(node["sha"])
                    node["seeded_by"] = s["sha"]
                    expanded.append(node)
        return {"query": query, "seeds": seeds, "expanded": expanded,
                "edges_followed": rel or "all", "n_total": len(seeds) + len(expanded)}

    # ── portable export/import (for the swap store: durable memory as NDJSON, not a binary .db) ──
    def export(self):
        """Return all durable rows as plain dicts (vectors omitted — re-derivable on import). This
        is what the swap store serializes to NDJSON so memory survives the ephemeral container."""
        con = self._con()

        def rows(q):
            cur = con.execute(q)
            cols = [c[0] for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        data = {"memory": rows("SELECT sha,kind,text,meta,ts,session FROM memory"),
                "relations": rows("SELECT sha,src,dst,rel,weight,ts FROM relations"),
                "ledger": rows("SELECT sha,ts,kind,subject,action,evidence,prev_sha FROM ledger")}
        con.close()
        return data

    def load_rows(self, data):
        """Rehydrate rows from export() (vectors recomputed on the way in). Idempotent via the
        primary-key REPLACE, so re-importing a bundle is safe. Returns stats()."""
        con = self._con()
        for m in data.get("memory", []):
            vec = json.dumps(self._embed(m.get("text", "")))
            con.execute("INSERT OR REPLACE INTO memory VALUES(?,?,?,?,?,?,?)",
                        (m["sha"], m.get("kind", "semantic"), m.get("text", ""), m.get("meta", "{}"),
                         vec, m.get("ts", time.time()), m.get("session", "default")))
        for r in data.get("relations", []):
            con.execute("INSERT OR REPLACE INTO relations VALUES(?,?,?,?,?,?)",
                        (r["sha"], r["src"], r["dst"], r["rel"], r.get("weight", 1.0),
                         r.get("ts", time.time())))
        for l in data.get("ledger", []):
            con.execute("INSERT OR REPLACE INTO ledger VALUES(?,?,?,?,?,?,?)",
                        (l["sha"], l.get("ts", time.time()), l["kind"], l["subject"], l["action"],
                         l.get("evidence", "{}"), l.get("prev_sha", "")))
        con.commit()
        con.close()
        return self.stats()

    def stats(self):
        con = self._con()
        n_mem = con.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        n_sem = con.execute("SELECT COUNT(*) FROM memory WHERE kind='semantic'").fetchone()[0]
        n_led = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        n_rel = con.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
        con.close()
        return {"memories": n_mem, "semantic": n_sem, "episodic": n_mem - n_sem,
                "ledger": n_led, "relations": n_rel}


if __name__ == "__main__":
    import tempfile
    m = MemoryStore(os.path.join(tempfile.mkdtemp(), "memory.db"))
    m.remember("APEX uses beta-binomial for the Bayesian layer", "semantic")
    m.remember("the char-n-gram backend fixes cross-language routing", "semantic")
    m.remember_from_snapshot({"objective": "build live memory",
                              "findings": [{"what": "SQLite is the default store",
                                            "where": "memory.py", "how": "stdlib", "confidence": "high"}]})
    e1 = m.record_event("vaccine_promoted", "NameError->define-first", "promote", {"uses": 3})
    e2 = m.record_event("skill_granted", "react-vt->react-specialist", "grant")
    print("recall 'bayesian':", [r["text"][:50] for r in m.recall("bayesian statistics")])
    print("recall 'language':", [r["text"][:50] for r in m.recall("cross language routing")])
    # Knowledge Graph demo: a claim and its contradiction, plus a directional (acyclic) chain
    a = m.remember("the default persistence store should be SQLite for offline portability", "semantic")
    b = m.remember("MongoDB is the better persistence store for multi-server deployments", "semantic")
    m.relate(a, b, "contradiz")
    g = m.recall_graph("persistence store", k=1, depth=1, rel="contradiz")
    print("contradiction walk:", [e["text"][:45] for e in g["expanded"]])
    # directional chain x->y->z, then a cycle z->x must be REJECTED by the DAG engine
    x = m.remember("premise: the container is ephemeral", "semantic")
    y = m.remember("therefore local .db is not durable", "semantic")
    z = m.remember("therefore durability needs git or zip export", "semantic")
    m.relate(x, y, "causa"); m.relate(y, z, "causa")
    print("cycle rejected:", m.relate(z, x, "causa")["status"] == "REFUSED")
    print("stats:", m.stats(), "| ledger chain ok:", m.verify_ledger())
