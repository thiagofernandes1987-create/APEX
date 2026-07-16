#!/usr/bin/env python3
"""
snapshot.py — Standardized session snapshot (APEX rule C5).

WHY THIS EXISTS:
  Across a long task or a resumed conversation, the LLM needs a compact, fixed
  format state summary so it doesn't lose decisions, findings, or "why". The
  snapshot lives in the CONVERSATION CONTEXT (not a database) and the method
  requires reading it at the start of every resumed session.

WHAT IT IS NOT:
  - Not cross-session disk persistence. If it isn't written into the context /
    handed back to the next session, it is gone. "Persistence" = discipline of
    re-emitting it, not a kernel that stores it.

FORMAT (stable keys so it's diffable and re-readable):
  objective, mode, milestones[], checklist{}, findings[], skills_staged[],
  open_questions[], confidence_notes[]

WHAT IF IT FAILS: Context-resident only; if not re-emitted into the next session it is gone (not disk persistence).
"""
import json, gzip, base64


STABLE_KEYS = ["objective", "mode", "milestones", "checklist", "findings",
               "skills_staged", "open_questions", "confidence_notes"]


def new_snapshot(objective: str, mode: str = "STANDARD") -> dict:
    return {"objective": objective, "mode": mode, "milestones": [],
            "checklist": {}, "findings": [], "skills_staged": [],
            "open_questions": [], "confidence_notes": []}


def add_finding(snap, what, where="", how="", confidence="[APPROX] medium"):
    """Every finding carries WHAT / WHERE / HOW / confidence (APEX diff-rules)."""
    snap["findings"].append({"what": what, "where": where, "how": how,
                             "confidence": confidence})
    return snap


def to_context_block(snap: dict) -> str:
    """Render a compact human+LLM-readable block to paste into context."""
    lines = [f"# APEX SNAPSHOT — {snap['objective']} (mode={snap['mode']})"]
    if snap["milestones"]:
        lines.append("## milestones\n" + "\n".join(f"- {m}" for m in snap["milestones"]))
    if snap["findings"]:
        lines.append("## findings")
        for f in snap["findings"]:
            lines.append(f"- {f['what']} | where={f['where']} | how={f['how']} | {f['confidence']}")
    if snap["skills_staged"]:
        lines.append("## skills_staged (require approval before install/run)")
        for s in snap["skills_staged"]:
            lines.append(f"- {s['id']}: use_when={s.get('use_when','')} status={s.get('status','STAGED')}")
    if snap["open_questions"]:
        lines.append("## open_questions\n" + "\n".join(f"- {q}" for q in snap["open_questions"]))
    return "\n".join(lines)


def compress(snap: dict) -> str:
    """gzip+base64 for large snapshots (>~2KB). Small ones: keep as plain JSON."""
    return base64.b64encode(gzip.compress(json.dumps(snap).encode(), 6)).decode()


def decompress(blob: str) -> dict:
    return json.loads(gzip.decompress(base64.b64decode(blob)))


if __name__ == "__main__":
    s = new_snapshot("audit APEX", "SCIENTIFIC")
    add_finding(s, "org apex-marketplace is claimable", "kernel L268", "curl -> HTTP 404", "[APPROX] high")
    s["skills_staged"].append({"id": "vercel-labs/ui", "use_when": "frontend task", "status": "STAGED"})
    print(to_context_block(s))
