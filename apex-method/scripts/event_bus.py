#!/usr/bin/env python3
"""event_bus.py — barramento único de telemetria cognitiva (v1.62).

A camada que as auditorias externas pediam como "continuous evaluation + tracing":
em vez de três subsistemas sobrepostos, UM fluxo de eventos padronizados que qualquer
consumidor lê — avaliação contínua, tracing, exporters (OTEL/JSONL) e o MCP.

DESIGN (deliberadamente mínimo):
  - `emit(module, action, trace_id=None, **fields)` — evento padronizado em SQLite
    (`APEX_METHOD_HOME/library/events.db`, stdlib). Nunca levanta exceção: telemetria
    jamais derruba o pipeline (best-effort, degrada para no-op).
  - `new_trace()` — id de correlação por execução; `orchestrator.run` abre um trace e
    emite triage/cache/mode/finish automaticamente — o loop NÃO depende de o LLM
    lembrar de instrumentar.
  - `trace(trace_id)` — timeline completa do trace (spans ordenados).
  - `evaluate(trace_id)` — o registro de avaliação por execução (o "Evaluation Engine"
    da análise externa): módulos tocados, cache hit/miss + tier, modo, latência total,
    contagem de eventos. `quality`/`validated` entram quando o validador reporta
    (`emit(..., action="validation", quality=...)`) — nunca inventados.
  - `export_jsonl(path)` — dump determinístico para exporters externos.

Vocabulário canônico de `action` (consumidores confiam nele):
  run_started | triage | cache_hit | cache_miss | mode_decision | validation |
  promotion | demotion | run_finished | error
"""
import json
import os
import sqlite3
import time
import uuid

_SCHEMA = """CREATE TABLE IF NOT EXISTS events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  trace_id TEXT NOT NULL,
  module TEXT NOT NULL,
  action TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS idx_events_trace ON events(trace_id);
CREATE INDEX IF NOT EXISTS idx_events_action ON events(action);"""


def _db_path():
    home = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    lib = os.path.join(home, "library")
    os.makedirs(lib, exist_ok=True)
    return os.path.join(lib, "events.db")


def _conn():
    c = sqlite3.connect(_db_path(), timeout=5)
    c.executescript(_SCHEMA)
    return c


def new_trace():
    return uuid.uuid4().hex[:16]


def emit(module, action, trace_id=None, **fields):
    """Best-effort append. Returns the event dict (or None on failure). NEVER raises."""
    try:
        ev = {"ts": round(time.time(), 3), "trace_id": trace_id or "-",
              "module": str(module), "action": str(action), "data": fields}
        with _conn() as c:
            c.execute("INSERT INTO events(ts, trace_id, module, action, data) VALUES (?,?,?,?,?)",
                      (ev["ts"], ev["trace_id"], ev["module"], ev["action"],
                       json.dumps(fields, ensure_ascii=False, default=str)))
        return ev
    except Exception:
        return None


def trace(trace_id, limit=500):
    """Ordered timeline of one execution."""
    try:
        with _conn() as c:
            rows = c.execute("SELECT ts, module, action, data FROM events WHERE trace_id=? "
                             "ORDER BY id LIMIT ?", (trace_id, limit)).fetchall()
        return [{"ts": r[0], "module": r[1], "action": r[2], "data": json.loads(r[3])}
                for r in rows]
    except Exception:
        return []


def evaluate(trace_id):
    """The per-execution evaluation record (the external audits' 'Evaluation Engine').
    Aggregates ONLY what was actually emitted — no invented metrics."""
    evs = trace(trace_id)
    if not evs:
        return {"trace_id": trace_id, "found": False}
    first, last = evs[0], evs[-1]
    cache_hits = [e for e in evs if e["action"] == "cache_hit"]
    cache_miss = [e for e in evs if e["action"] == "cache_miss"]
    validations = [e for e in evs if e["action"] == "validation"]
    mode = next((e["data"].get("mode") for e in reversed(evs)
                 if e["action"] == "mode_decision" and e["data"].get("mode")), None)
    quality = next((v["data"].get("quality") for v in reversed(validations)
                    if v["data"].get("quality") is not None), None)
    return {
        "trace_id": trace_id, "found": True,
        "started": first["ts"], "finished": last["ts"],
        "latency_s": round(last["ts"] - first["ts"], 3),
        "events": len(evs),
        "modules": sorted({e["module"] for e in evs}),
        "mode": mode,
        "cache": {"hits": len(cache_hits), "misses": len(cache_miss),
                  "tier": (cache_hits[-1]["data"].get("tier") if cache_hits else None)},
        "validation": {"count": len(validations),
                       "passed": sum(1 for v in validations if v["data"].get("passed")),
                       "quality": quality},
        "completed": any(e["action"] == "run_finished" for e in evs),
        "errors": [e["data"] for e in evs if e["action"] == "error"],
    }


def recent_traces(k=20):
    try:
        with _conn() as c:
            rows = c.execute("SELECT trace_id, MIN(ts), COUNT(*) FROM events "
                             "WHERE trace_id != '-' GROUP BY trace_id "
                             "ORDER BY MIN(ts) DESC LIMIT ?", (k,)).fetchall()
        return [{"trace_id": r[0], "started": r[1], "events": r[2]} for r in rows]
    except Exception:
        return []


def export_jsonl(path):
    """Deterministic dump for external exporters (OTEL bridge, LangSmith, files)."""
    try:
        with _conn() as c:
            rows = c.execute("SELECT ts, trace_id, module, action, data FROM events ORDER BY id").fetchall()
        with open(path, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"ts": r[0], "trace_id": r[1], "module": r[2],
                                    "action": r[3], "data": json.loads(r[4])},
                                   ensure_ascii=False) + "\n")
        return {"exported": len(rows), "path": path}
    except Exception as e:
        return {"exported": 0, "error": str(e)[:120]}


if __name__ == "__main__":
    t = new_trace()
    emit("demo", "run_started", t, task="demo")
    emit("orchestrator", "mode_decision", t, mode="STANDARD")
    emit("resolution_cache", "cache_hit", t, tier="facet", skill="css3-advanced")
    emit("verify", "validation", t, passed=True, quality=0.9)
    emit("demo", "run_finished", t)
    print(json.dumps(evaluate(t), ensure_ascii=False, indent=1))
