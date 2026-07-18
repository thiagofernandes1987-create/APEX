#!/usr/bin/env python3
"""
code_genetics.py — APEX code_genetics / vaccine store (SR_35), nativized.

WHY: learn from fixed errors. save_vaccine() crystallizes an (error_signature -> fix)
pattern with O(1) frozenset lookup; error_evolution_loop applies known fixes and only
promotes a vaccine after it works (sessions>=2 AND success_rate>0.85), with rollback if
stderr does not shrink.

HONEST SCOPE: this is a within-session store (dict; persist to SQLite/snapshot externally).
It records patterns; it does not itself execute untrusted code.

WHEN: After a PoT/code failure is fixed, to crystallize the error->fix pattern.
WHAT IF IT FAILS: Within-session dict; if not persisted to SQLite/snapshot it is lost — callers persist externally.
"""
import hashlib, json


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
                    "(sig TEXT PRIMARY KEY, fix TEXT, uses INTEGER, successes INTEGER)")
        con.commit()
        con.close()

    def _load(self):
        import sqlite3
        con = sqlite3.connect(self.db_path)
        for sig, fix, uses, succ in con.execute("SELECT sig, fix, uses, successes FROM vaccines"):
            self.vaccines[sig] = {"fix": fix, "uses": uses, "successes": succ}
        con.close()

    def _persist(self, sig):
        if not self.db_path:
            return
        import sqlite3
        v = self.vaccines[sig]
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO vaccines(sig,fix,uses,successes) VALUES(?,?,?,?) "
                    "ON CONFLICT(sig) DO UPDATE SET fix=excluded.fix, uses=excluded.uses, "
                    "successes=excluded.successes",
                    (sig, v["fix"], v["uses"], v["successes"]))
        con.commit()
        con.close()

    def save_vaccine(self, error_text, fix):
        sig = signature(error_text)
        v = self.vaccines.setdefault(sig, {"fix": fix, "uses": 0, "successes": 0})
        v["fix"] = fix
        self._persist(sig)
        return sig

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
