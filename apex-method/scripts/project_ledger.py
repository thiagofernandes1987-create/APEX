#!/usr/bin/env python3
"""
project_ledger.py — The living project inventory (MACRO + micros) that survives session
interruptions (usage limits, container recycling).

WHY THIS EXISTS:
  Long projects lose state when a session is cut by a usage limit. The snapshot lives in
  context (it dies if not re-emitted); this ledger is DURABLE — a git-committed PROJECT_LEDGER.md
  (human quick-consult) + a JSON sidecar (machine). It records, per micro-task: WHO delivers
  WHAT to WHOM and WHEN (WHEN = order in the DSM, not a clock), the milestones, the checklist,
  the deliverable TYPE, and the status — so a fresh session reads it and resumes exactly.

DSM (Design Structure Matrix) for process optimization:
  micros are nodes in an acyclic dependency graph (reuses hypothesis_dag). `dsm()` returns the
  topological order (WHEN), the parallelizable batches (cost saving), and the critical path.

GOVERNANCE (author's spec):
  - Only DEEP/SCIENTIFIC/RESEARCH create a ledger (lighter modes skip the bureaucracy).
  - `guard_completion()` tells the LLM to finish the OPEN micros before starting new scope.
  - A mapped solution is NOT abandoned silently: `authorize_abandon(id, reason)` requires a
    justified, recorded reason and then triggers a MACRO readjust.
  - FOGGY: prompt the user to create/attach a persistence file (see request_persistence()).

PERSISTENCE (user chooses one backend):
  - "git":   commit PROJECT_LEDGER.md into the repo (durable across recycling).
  - "local": read/write a local repo checkout path.
  - "zip":   export_zip() the ledger + competence.db + memory.db; the user re-uploads on resume.

WHAT IF IT FAILS:
  Pure stdlib. A cycle in dependencies is rejected (hypothesis_dag). A missing sidecar starts a
  fresh ledger. persist() reports the backend action for the LLM to run; it never runs git itself.
"""
import hashlib
import json
import os
import time

HEAVY_MODES = ("DEEP", "SCIENTIFIC", "RESEARCH")
DELIVERABLE_TYPES = ("laudo", "snapshot", "pot_result", "skill", "diff", "doc", "code", "decision")
STATUSES = ("pending", "in_progress", "done", "blocked", "abandoned")


def _sha8(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]


class ProjectLedger:
    def __init__(self, objective="", mode="DEEP", backend="git", path=None):
        self.objective = objective
        self.mode = (mode or "DEEP").upper()
        self.backend = backend            # git | local | zip
        self.path = path or "PROJECT_LEDGER.md"
        self.milestones = []              # [{name, status}]
        self.micros = {}                  # id -> micro dict
        self.order = []                   # insertion order of micro ids
        self.events = []
        self.created = time.time()

    # ── macro ─────────────────────────────────────────────────────────────
    def is_active(self):
        """Only DEEP+ maintain a ledger (author's spec: keep light modes bureaucracy-free)."""
        return self.mode in HEAVY_MODES

    def add_milestone(self, name, status="pending"):
        self.milestones.append({"name": name, "status": status})
        return self

    # ── micros (RACI + deliverable + DSM deps) ────────────────────────────
    def add_micro(self, micro_id, task, responsible, deliver_to, deliverable_type,
                  accountable=None, depends_on=None, checklist=None):
        """WHO (responsible persona) delivers WHAT (deliverable_type) to WHOM (deliver_to),
        WHEN = after depends_on (DSM order). accountable defaults to 'pmi_pm'."""
        if deliverable_type not in DELIVERABLE_TYPES:
            raise ValueError(f"deliverable_type must be one of {DELIVERABLE_TYPES}")
        self.micros[micro_id] = {
            "id": micro_id, "task": task, "responsible": responsible,
            "accountable": accountable or "pmi_pm", "deliver_to": deliver_to,
            "deliverable_type": deliverable_type, "depends_on": list(depends_on or []),
            "checklist": [{"item": c, "done": False} for c in (checklist or [])],
            "status": "pending", "abandon_reason": None}
        if micro_id not in self.order:
            self.order.append(micro_id)
        return self

    def check_item(self, micro_id, item_index, done=True):
        self.micros[micro_id]["checklist"][item_index]["done"] = done
        return self

    def set_status(self, micro_id, status):
        if status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        self.micros[micro_id]["status"] = status
        self.events.append(f"{micro_id} -> {status}")
        return self

    # ── DSM: topological order (WHEN), parallel batches, critical path ────
    def dsm(self):
        """Order the micros by dependency via an acyclic DAG (hypothesis_dag). Returns the
        topological levels (each level = micros that can run IN PARALLEL — the cost saving),
        the linear order, and the critical path (longest dependency chain)."""
        ids = list(self.order)
        deps = {i: [d for d in self.micros[i]["depends_on"] if d in self.micros] for i in ids}
        # acyclicity via hypothesis_dag
        cycle = False
        try:
            import hypothesis_dag
            g = hypothesis_dag.HypothesisDAG()
            for i in ids:
                g.register(i)
            for i in ids:
                for d in deps[i]:
                    if not g.add_edge(d, i):      # d must precede i
                        cycle = True
        except Exception:
            pass
        # Kahn topological levels
        indeg = {i: len(deps[i]) for i in ids}
        levels, remaining = [], set(ids)
        while remaining:
            ready = sorted(i for i in remaining if all(d not in remaining for d in deps[i]))
            if not ready:
                cycle = True
                levels.append(sorted(remaining))    # break the deadlock, report the cycle
                break
            levels.append(ready)
            remaining -= set(ready)
        # critical path = longest chain by level depth
        depth = {}
        for lvl in levels:
            for i in lvl:
                # .get so a cycle (deps not yet in `depth`) degrades instead of KeyError
                depth[i] = 1 + max([depth.get(d, 0) for d in deps[i]] or [0])
        critical = sorted(depth, key=lambda i: -depth.get(i, 0))[:1]
        crit_chain, seen = [], set()
        cur = critical[0] if critical else None
        while cur and cur not in seen:      # `seen` breaks a cycle in the critical-path walk
            crit_chain.append(cur)
            seen.add(cur)
            nxt = max(deps[cur], key=lambda d: depth.get(d, 0)) if deps[cur] else None
            cur = nxt
        return {"levels": levels, "linear_order": [i for lvl in levels for i in lvl],
                "parallel_batches": [lvl for lvl in levels if len(lvl) > 1],
                "critical_path": list(reversed(crit_chain)), "cycle": cycle}

    # ── governance ────────────────────────────────────────────────────────
    def guard_completion(self):
        """The LLM must finish OPEN micros before opening new scope. Returns what is pending,
        in DSM order, so the user is told to complete the current minimum inventory first."""
        order = self.dsm()["linear_order"]
        pending = [i for i in order if self.micros[i]["status"] in ("pending", "in_progress", "blocked")]
        return {"complete_first": pending,
                "instruction": ("Finish these micros (in DSM order) before starting new scope."
                                if pending else "All micros done — safe to advance the macro."),
                "blocked_advance": bool(pending)}

    def authorize_abandon(self, micro_id, reason):
        """A mapped solution is not dropped silently: abandoning REQUIRES a justified reason,
        which is recorded, and then the macro is flagged for readjustment (H5-style gate)."""
        if not reason or len(reason.strip()) < 8:
            return {"status": "REFUSED", "why": "abandon requires a justified reason (>=8 chars)"}
        self.micros[micro_id]["status"] = "abandoned"
        self.micros[micro_id]["abandon_reason"] = reason
        self.events.append(f"{micro_id} ABANDONED: {reason}")
        return {"status": "AUTHORIZED", "macro_readjust_required": True,
                "micro": micro_id, "reason": reason}

    # ── persistence ───────────────────────────────────────────────────────
    def request_persistence(self):
        """FOGGY prompt: ask the user which durable backend to use and to attach the file/DB."""
        return {"ask_user": "choose a persistence backend for the living inventory",
                "options": {
                    "git": "commit PROJECT_LEDGER.md into the repo (recommended, survives recycling)",
                    "local": "point to a local repo checkout to read/write",
                    "zip": "download the latest base .zip and re-upload it when a session resumes"},
                "on_recycle": "if the container was recycled, attach the last PROJECT_LEDGER.md + "
                              "competence.db/memory.db (or the zip) so I can resume where we stopped"}

    def to_json(self):
        return {"objective": self.objective, "mode": self.mode, "backend": self.backend,
                "milestones": self.milestones, "micros": self.micros, "order": self.order,
                "created": self.created, "sha8": _sha8(self.micros)}

    @classmethod
    def from_json(cls, data):
        pl = cls(data.get("objective", ""), data.get("mode", "DEEP"),
                 data.get("backend", "git"))
        pl.milestones = data.get("milestones", [])
        pl.micros = data.get("micros", {})
        pl.order = data.get("order", list(pl.micros))
        pl.created = data.get("created", time.time())
        return pl

    def render_md(self):
        d = self.dsm()
        lines = [f"# PROJECT LEDGER — {self.objective}",
                 f"_mode={self.mode} · backend={self.backend} · sha8={_sha8(self.micros)} · "
                 f"generated={time.strftime('%Y-%m-%d %H:%M', time.gmtime())}_", ""]
        if self.milestones:
            lines.append("## Milestones")
            for m in self.milestones:
                mark = {"done": "x", "in_progress": "~"}.get(m["status"], " ")
                lines.append(f"- [{mark}] {m['name']}")
            lines.append("")
        lines.append("## Micro-inventories (WHO delivers WHAT to WHOM, WHEN=DSM order)")
        lines.append("| # | micro | responsible → deliver_to | deliverable | depends_on | status |")
        lines.append("|---|---|---|---|---|---|")
        for i, mid in enumerate(d["linear_order"], 1):
            m = self.micros[mid]
            lines.append(f"| {i} | {m['task'][:40]} | {m['responsible']} → {m['deliver_to']} | "
                         f"{m['deliverable_type']} | {', '.join(m['depends_on']) or '—'} | {m['status']} |")
        lines.append("")
        lines.append("## DSM (process optimization)")
        lines.append(f"- **Critical path:** {' → '.join(d['critical_path']) or '—'}")
        for b in d["parallel_batches"]:
            lines.append(f"- **Parallelizable (cost saving):** {{{', '.join(b)}}}")
        if d["cycle"]:
            lines.append("- ⚠️ **dependency cycle detected — fix before proceeding**")
        g = self.guard_completion()
        lines.append("")
        lines.append("## Completion gate")
        lines.append(f"- {g['instruction']}")
        if g["complete_first"]:
            lines.append(f"- Pending (finish first, DSM order): {', '.join(g['complete_first'])}")
        abandoned = [m for m in self.micros.values() if m["status"] == "abandoned"]
        if abandoned:
            lines.append("\n## Abandoned (with justification)")
            for m in abandoned:
                lines.append(f"- {m['id']}: {m['abandon_reason']}")
        return "\n".join(lines)

    def save(self, directory="."):
        """Write PROJECT_LEDGER.md + .json sidecar. Returns the persist instruction for the
        chosen backend (the LLM runs git/zip; this module does not shell out)."""
        md_path = os.path.join(directory, self.path)
        json_path = md_path.rsplit(".", 1)[0] + ".json"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(self.render_md())
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_json(), f, ensure_ascii=False, indent=1)
        instr = {"git": f"git add {self.path} {os.path.basename(json_path)} && git commit -m 'ledger update'",
                 "local": f"saved to {md_path} (local backend)",
                 "zip": "call export_zip([ledger, competence.db, memory.db]) and hand the zip to the user"}
        return {"md": md_path, "json": json_path, "persist": instr.get(self.backend, instr["git"])}

    def export_zip(self, extra_paths=None, out="apex_project_state.zip", directory="."):
        """Bundle the ledger + sidecar (+ competence.db/memory.db if present) into a zip the
        user can download and re-upload after a container recycle."""
        import zipfile
        saved = self.save(directory)
        paths = [saved["md"], saved["json"]]
        # AUD-W1: honour APEX_METHOD_HOME so the zip bundles the ACTIVE stores, not always ~
        base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
        for p in (extra_paths or [os.path.join(base, "competence.db"),
                                  os.path.join(base, "memory.db")]):
            if os.path.isfile(p):
                paths.append(p)
        out_path = os.path.join(directory, out)
        with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in paths:
                z.write(p, arcname=os.path.basename(p))
        return {"zip": out_path, "contents": [os.path.basename(p) for p in paths]}


if __name__ == "__main__":
    pl = ProjectLedger("cognitive upgrades for APEX", mode="DEEP", backend="git")
    pl.add_milestone("Op1 memory").add_milestone("Op2 parallelism", "done")
    pl.add_micro("m1", "design memory schema", "architect", "critic", "doc")
    pl.add_micro("m2", "implement memory.py", "engineer", "critic", "code", depends_on=["m1"])
    pl.add_micro("m3", "write tests", "qa-expert", "pmi_pm", "code", depends_on=["m2"])
    pl.add_micro("m4", "docs", "technical-writer", "pmi_pm", "doc", depends_on=["m2"])
    pl.set_status("m1", "done")
    print(pl.render_md())
    print("\nGUARD:", pl.guard_completion()["instruction"])
    print("ABANDON (no reason):", pl.authorize_abandon("m4", "")["status"])
