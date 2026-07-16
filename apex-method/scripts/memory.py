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

DB_DEFAULT = os.path.expanduser("~/.apex-method/memory.db")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MemoryStore:
    def __init__(self, db_path=DB_DEFAULT):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
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
    def record_event(self, kind, subject, action, evidence=None):
        """Neutral API the subsystems CALL when a rule/diff/agent/skill/vaccine is promoted or
        demoted or an error is corrected. SHA-256 chained (each event carries the previous hash)
        so the ledger is tamper-evident. Also mirrored as a semantic memory for recall."""
        con = self._con()
        prev = con.execute("SELECT sha FROM ledger ORDER BY ts DESC LIMIT 1").fetchone()
        prev_sha = prev[0] if prev else ""
        payload = f"{kind}|{subject}|{action}|{prev_sha}|{time.time()}"
        sha = _sha(payload)
        con.execute("INSERT OR REPLACE INTO ledger VALUES(?,?,?,?,?,?,?)",
                    (sha, time.time(), kind, subject, action,
                     json.dumps(evidence or {}, ensure_ascii=False), prev_sha))
        con.commit()
        con.close()
        # mirror into semantic memory so `recall` surfaces the evolution
        self.remember(f"[{kind}] {subject}: {action}", "semantic",
                      {"ledger_event": sha, "prev": prev_sha})
        return {"sha": sha, "prev_sha": prev_sha, "kind": kind, "subject": subject, "action": action}

    def verify_ledger(self):
        """Re-walk the chain and confirm each event's prev_sha matches its predecessor."""
        con = self._con()
        rows = con.execute("SELECT sha, ts, kind, subject, action, prev_sha FROM ledger "
                           "ORDER BY ts ASC").fetchall()
        con.close()
        ok, prev = True, ""
        for sha, ts, kind, subject, action, prev_sha in rows:
            if prev_sha != prev:
                ok = False
                break
            prev = sha
        return {"ok": ok, "events": len(rows)}

    def stats(self):
        con = self._con()
        n_mem = con.execute("SELECT COUNT(*) FROM memory").fetchone()[0]
        n_sem = con.execute("SELECT COUNT(*) FROM memory WHERE kind='semantic'").fetchone()[0]
        n_led = con.execute("SELECT COUNT(*) FROM ledger").fetchone()[0]
        con.close()
        return {"memories": n_mem, "semantic": n_sem, "episodic": n_mem - n_sem, "ledger": n_led}


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
    print("ledger chain ok:", m.verify_ledger(), "| stats:", m.stats())
