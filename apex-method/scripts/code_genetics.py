#!/usr/bin/env python3
"""
code_genetics.py — APEX code_genetics / vaccine store (SR_35), nativized.

WHY: learn from fixed errors. save_vaccine() crystallizes an (error_signature -> fix)
pattern with O(1) frozenset lookup; error_evolution_loop applies known fixes and only
promotes a vaccine after it works (sessions>=2 AND success_rate>0.85), with rollback if
stderr does not shrink.

HONEST SCOPE: it records patterns; it does not itself execute untrusted code.

v1.44 (author's context vision): vaccines are EXPERIENCE — the raw material that future windows
consume as CONTEXT. They now have a DURABLE default home (`durable_store()` -> vaccines.db under
APEX_METHOD_HOME/~/.apex-method), travel in the swap bundle, and feed agent_spawn's context pack.
`VaccineStore()` with no path stays in-memory (explicit, for tests).

WHEN: After a PoT/code failure is fixed, to crystallize the error->fix pattern.
WHAT IF IT FAILS: In-memory store is lost with the process; the durable store degrades to
in-memory if the db path is unwritable — never raises.
"""
import hashlib, json, os

# durable default: experience must survive the session to become future context
DB_DEFAULT = os.path.join(os.environ.get("APEX_METHOD_HOME")
                          or os.path.expanduser("~/.apex-method"), "vaccines.db")


def durable_store():
    """The cross-session vaccine store (creates the db on first use; in-memory on failure)."""
    try:
        os.makedirs(os.path.dirname(DB_DEFAULT), exist_ok=True)
        return VaccineStore(db_path=DB_DEFAULT)
    except Exception:
        return VaccineStore()


def signature(error_text: str) -> str:
    """Stable O(1)-lookup key from an error (normalize numbers/paths)."""
    import re
    norm = re.sub(r"\d+", "N", error_text)
    norm = re.sub(r"[/\\][\w./\\-]+", "PATH", norm).strip().lower()
    return hashlib.sha256(norm.encode()).hexdigest()[:12]


class VaccineStore:
    def __init__(self, db_path=None):
        """In-session dict by default. Pass db_path (audit P3) for real cross-session
        SQLite persistence (as in the full APEX); load()/persist happen automatically."""
        self.vaccines = {}   # sig -> {fix, uses, successes}
        self.db_path = db_path
        if db_path:
            self._init_db()
            self._load()

    def _init_db(self):
        import sqlite3
        con = sqlite3.connect(self.db_path)
        con.execute("CREATE TABLE IF NOT EXISTS vaccines "
                    "(sig TEXT PRIMARY KEY, fix TEXT, uses INTEGER, successes INTEGER, error TEXT)")
        # v1.44 migration: older dbs lack the `error` column — without the original (normalized)
        # error text a vaccine is just a hash+fix, useless as CONTEXT for a future window.
        try:
            con.execute("ALTER TABLE vaccines ADD COLUMN error TEXT")
        except sqlite3.OperationalError:
            pass
        con.commit()
        con.close()

    def _load(self):
        import sqlite3
        con = sqlite3.connect(self.db_path)
        for sig, fix, uses, succ, err in con.execute(
                "SELECT sig, fix, uses, successes, error FROM vaccines"):
            self.vaccines[sig] = {"fix": fix, "uses": uses, "successes": succ, "error": err or ""}
        con.close()

    def _persist(self, sig):
        if not self.db_path:
            return
        import sqlite3
        v = self.vaccines[sig]
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO vaccines(sig,fix,uses,successes,error) VALUES(?,?,?,?,?) "
                    "ON CONFLICT(sig) DO UPDATE SET fix=excluded.fix, uses=excluded.uses, "
                    "successes=excluded.successes, error=excluded.error",
                    (sig, v["fix"], v["uses"], v["successes"], v.get("error", "")))
        con.commit()
        con.close()

    def save_vaccine(self, error_text, fix):
        sig = signature(error_text)
        v = self.vaccines.setdefault(sig, {"fix": fix, "uses": 0, "successes": 0})
        v["fix"] = fix
        v["error"] = (error_text or "")[:200]      # the lesson's subject — future context
        self._persist(sig)
        return sig

    def relevant(self, task_text, k=3):
        """The vaccines most relevant to a task (lexical overlap on error+fix) — the
        'experience -> context' read path used by agent_spawn.context_pack."""
        import re
        words = set(re.findall(r"[a-zà-ÿ0-9]{3,}", (task_text or "").lower()))
        scored = []
        for sig, v in self.vaccines.items():
            text = f"{v.get('error','')} {v['fix']}".lower()
            score = sum(1 for w in words if w in text)
            if score:
                scored.append((score, v["successes"], sig, v))
        scored.sort(key=lambda x: (-x[0], -x[1]))
        return [dict(v, sig=sig) for _, _, sig, v in scored[:k]]

    def lookup(self, error_text):
        return self.vaccines.get(signature(error_text))

    def record_outcome(self, error_text, success: bool):
        sig = signature(error_text)
        v = self.vaccines.get(sig)
        if not v:
            return None
        v["uses"] += 1
        v["successes"] += int(success)
        self._persist(sig)
        return v

    def is_promotable(self, error_text):
        """Promote a vaccine only after it proves itself (sessions>=2 AND success>0.85)."""
        v = self.vaccines.get(signature(error_text))
        if not v or v["uses"] < 2:
            return False
        return (v["successes"] / v["uses"]) > 0.85


if __name__ == "__main__":
    s = VaccineStore()
    sig = s.save_vaccine("NameError: name 'foo' is not defined at line 12", "define foo before use")
    print("saved:", sig, "| lookup:", s.lookup("NameError: name 'bar' is not defined at line 99"))
    for ok in (True, True, False, True):
        s.record_outcome("NameError: name 'x' is not defined at line 1", ok)
    print("promotable:", s.is_promotable("NameError: name 'x' is not defined at line 1"))
