#!/usr/bin/env python3
"""
learning.py — APEX Op-P3: aprendizado que persiste (durable promote/demote loop).

WHY THIS EXISTS:
  competence_matrix diagnoses a WEAK round in the moment (PERSONA_SWAP / INJECT_SKILL /
  HARD_PROBLEM) and competence.db holds per-persona signals for a session. What was MISSING is the
  loop that makes those outcomes CHANGE FUTURE BEHAVIOUR across sessions: accumulate evidence per
  (kind, subject, domain), decide PROMOTE / KEEP / DEMOTE with the SAME Bayesian layer the kernel
  uses (beta-binomial + Ω 0.72/0.5), write every promotion/demotion to the SHA-256 governance
  ledger (so it is durable + auditable), and let the next task CONSULT this history to pick the
  historically-best persona/skill. That closes Op-P3: rules/diffs/agents/skills/vaccines that prove
  out are promoted, ones that keep failing are demoted, and the framework remembers.

WHEN TO USE:
  record_outcome() after every adjudicated round (evaluate_hypotheses does it automatically);
  best()/score()/reward() at task start to consult the validated cross-session history.

KINDS: persona | skill | diff | rule | vaccine  — anything that can prove out or fail.

HOW IT DECIDES (faithful to bayes.py):
  posterior mean = beta_binomial_update(Beta(1,1), successes, trials).mean; with >= MIN_OBS trials:
  mean >= 0.72 -> PROMOTE, mean <= 0.50 -> DEMOTE, else KEEP (the Ω thresholds).

WHAT IF IT FAILS:
  Pure stdlib (sqlite3). A missing bayes engine falls back to the raw success rate. A missing
  memory ledger just means the promotion isn't mirrored (still recorded locally). Never raises on
  normal use; an empty store returns neutral scores.
"""
import hashlib
import os
import sqlite3
import time

import sys
sys.path.insert(0, os.path.dirname(__file__))

# AUD-W1: APEX_METHOD_HOME redirects the durable store (tests/CI isolation) — see config.py.
DB_DEFAULT = os.path.join(os.environ.get("APEX_METHOD_HOME")
                          or os.path.expanduser("~/.apex-method"), "learning.db")
MIN_OBS = 3                       # need at least 3 observations before promoting/demoting
PROMOTE_AT = 0.72                 # Ω adopt
DEMOTE_AT = 0.50                  # Ω review floor
VALID_KINDS = ("persona", "skill", "diff", "rule", "vaccine")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _key(kind, subject, domain):
    return _sha(f"{kind}|{subject}|{domain}")


def _mean(successes, trials):
    """Posterior mean via the kernel's beta-binomial (Beta(1,1) prior); raw rate as fallback."""
    try:
        import bayes
        return bayes.beta_binomial_update(1, 1, successes, trials)["mean"]
    except Exception:
        return round((successes + 1) / (trials + 2), 4)      # Laplace-smoothed fallback


def _decide(mean, trials):
    if trials < MIN_OBS:
        return "KEEP"
    if mean >= PROMOTE_AT:
        return "PROMOTE"
    if mean <= DEMOTE_AT:
        return "DEMOTE"
    return "KEEP"


class LearningStore:
    def __init__(self, db_path=DB_DEFAULT):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        con = self._con()
        con.execute("CREATE TABLE IF NOT EXISTS outcomes("
                    "sha TEXT PRIMARY KEY, kind TEXT, subject TEXT, domain TEXT, "
                    "successes REAL, trials REAL, status TEXT, mean REAL, updated REAL)")
        con.commit()
        con.close()

    def _con(self):
        return sqlite3.connect(self.db_path)

    # ── write: accumulate an outcome, recompute, auto-promote/demote ───────────
    def record_outcome(self, kind, subject, domain, success, weight=1.0, evidence=None):
        """Add one outcome (success True/False) for (kind, subject, domain), recompute the posterior,
        and auto-decide. On a STATUS CHANGE (ACTIVE->PROMOTED/DEMOTED) a durable governance event is
        written to the SHA-256 ledger (memory.record_event). Returns the new score + whether the
        status changed."""
        if kind not in VALID_KINDS:
            return {"status": "REFUSED", "reason": f"unknown kind '{kind}'; valid: {VALID_KINDS}"}
        subject = (subject or "").strip()
        domain = (domain or "general").strip()
        sha = _key(kind, subject, domain)
        con = self._con()
        row = con.execute("SELECT successes, trials, status FROM outcomes WHERE sha=?", (sha,)).fetchone()
        succ, trials, prev_status = (row[0], row[1], row[2]) if row else (0.0, 0.0, "ACTIVE")
        succ += float(weight) if success else 0.0
        trials += float(weight)
        mean = _mean(succ, trials)
        decision = _decide(mean, trials)
        new_status = {"PROMOTE": "PROMOTED", "DEMOTE": "DEMOTED"}.get(decision, prev_status or "ACTIVE")
        con.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?)",
                    (sha, kind, subject, domain, succ, trials, new_status, mean, time.time()))
        con.commit()
        con.close()
        changed = (new_status != (prev_status or "ACTIVE"))
        if changed and new_status in ("PROMOTED", "DEMOTED"):
            self._ledger(kind, subject, domain, new_status, mean, trials, evidence)
        return {"kind": kind, "subject": subject, "domain": domain, "mean": mean,
                "n": int(trials), "decision": decision, "status": new_status, "changed": changed}

    def _ledger(self, kind, subject, domain, status, mean, trials, evidence=None):
        """Mirror a promotion/demotion into the durable SHA-256 governance ledger."""
        try:
            import memory
            action = "promote" if status == "PROMOTED" else "demote"
            memory.MemoryStore().record_event(
                f"{kind}_{action}d", f"{subject}@{domain}", action,
                {"mean": mean, "n": int(trials), **(evidence or {})})
        except Exception:
            pass

    # ── read: consult history to pick the best / know a status ─────────────────
    def score(self, kind, subject, domain):
        con = self._con()
        row = con.execute("SELECT successes, trials, status, mean FROM outcomes WHERE sha=?",
                          (_key(kind, subject, domain),)).fetchone()
        con.close()
        if not row:
            return {"mean": 0.5, "n": 0, "status": "ACTIVE", "decision": "KEEP"}  # neutral, no history
        succ, trials, status, mean = row
        return {"mean": mean, "n": int(trials), "status": status, "decision": _decide(mean, trials)}

    def best(self, kind, domain, k=5, include_demoted=False):
        """Rank subjects of `kind` for `domain` by posterior mean (history required). DEMOTED ones are
        excluded by default — this is what task-start consults to pick the historically-best pick."""
        con = self._con()
        rows = con.execute("SELECT subject, mean, trials, status FROM outcomes "
                           "WHERE kind=? AND domain=? ORDER BY mean DESC", (kind, domain)).fetchall()
        con.close()
        out = []
        for subject, mean, trials, status in rows:
            if status == "DEMOTED" and not include_demoted:
                continue
            out.append({"subject": subject, "mean": mean, "n": int(trials), "status": status})
        return out[:k]

    def reward(self, subject, domain, kind="persona"):
        """A [0,1] durable reward for (subject, domain) — the cross-session partner of
        competence_matrix._reward (which is session-local). Neutral 0.5 with no history."""
        s = self.score(kind, subject, domain)
        return s["mean"], s["n"]

    def stats(self):
        con = self._con()
        n = con.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0]
        prom = con.execute("SELECT COUNT(*) FROM outcomes WHERE status='PROMOTED'").fetchone()[0]
        dem = con.execute("SELECT COUNT(*) FROM outcomes WHERE status='DEMOTED'").fetchone()[0]
        con.close()
        return {"tracked": n, "promoted": prom, "demoted": dem, "active": n - prom - dem}


# ── module-level convenience (default store) ────────────────────────────────────
_DEFAULT = None


def _store():
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = LearningStore()
    return _DEFAULT


def record_outcome(kind, subject, domain, success, weight=1.0, evidence=None):
    return _store().record_outcome(kind, subject, domain, success, weight, evidence)


def score(kind, subject, domain):
    return _store().score(kind, subject, domain)


def best(kind, domain, k=5, include_demoted=False):
    return _store().best(kind, domain, k, include_demoted)


if __name__ == "__main__":
    import json
    import tempfile
    s = LearningStore(os.path.join(tempfile.mkdtemp(), "learning.db"))
    # a persona that keeps succeeding in 'engineering' gets PROMOTED (durable ledger event)
    for _ in range(4):
        r = s.record_outcome("persona", "architect", "engineering", True)
    print("architect:", json.dumps(r, ensure_ascii=False))
    # a persona that keeps failing gets DEMOTED
    for _ in range(4):
        d = s.record_outcome("persona", "poet", "engineering", False)
    print("poet:", json.dumps(d, ensure_ascii=False))
    print("best engineering personas:", s.best("persona", "engineering"))
    print("stats:", s.stats())
