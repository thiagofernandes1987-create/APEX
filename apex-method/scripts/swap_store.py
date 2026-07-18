#!/usr/bin/env python3
"""
swap_store.py — APEX swap store: one STANDARD, backend-agnostic memory hierarchy with versioned,
revisioned, rotated files.

WHY THIS EXISTS:
  The container is ephemeral, so working state (`~/.apex-method/*.db`, snapshots) dies on
  interruption. This defines ONE canonical folder/file standard — identical on a local PC folder or
  in Google Drive — that behaves like an OS memory hierarchy:

     RAM (context, dies)  ->  SWAP (this store: survives the container)  ->  DISK (git: validated)

  Only what passes the VALIDATION gate (PMI adopt + intact ledger + tests) is promoted from swap to
  a git commit. Everything else stays disposable in swap.

THE FILE STANDARD (author's spec):
  - Names carry a timestamp AND a layout revision: `<name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext>`
    (e.g. `memory-User-20260716183245-R00.json`). The timestamp makes every write a new, sortable
    version; the revision `R<NN>` is the file's LAYOUT version (bump it when the schema changes) so
    old and new layouts never collide. ALWAYS read/edit the LATEST validated (highest rev, then ts).
  - The MAIN folder always holds the LATEST; older versions live in a `versions/` sub-folder.
  - Backups are ROTATED: the newest `KEEP_BACKUPS` (10) survive; older ones are obsolete (deleted on
    local; on Drive there is no delete API here, so they are LISTED for GC — an honest constraint).
  - New users NEVER improvise the tree: it is built from the standard `models/apex_structure.model.json`
    (shipped in the repo), the same on Windows or Drive.

WHO DOES WHAT:
  This script OWNS the standard, the local materialization + rotation, the portable bundle
  (export/import) and the promotion manifest. It NEVER talks to Google Drive (no credentials) — the
  runtime (Claude) uploads/downloads via the Drive tools, driven by `drive_tree()`.

WHAT IF IT FAILS:
  Pure stdlib. materialize() is idempotent (seeds use a fixed ts) and never overwrites data. Missing
  memory.py degrades to an empty bundle. Never raises on normal use.
"""
import hashlib
import json
import os
import re
import time

import sys
sys.path.insert(0, os.path.dirname(__file__))

SCHEMA_VERSION = "1.0"
NAME_TS_FMT = "%Y%m%d%H%M%S"          # anomesdiahoraminutosegundo (UTC), 14 digits, sortable
SEED_TS = "00000000000000"            # the template/seed timestamp (deterministic -> idempotent)
KEEP_BACKUPS = 10                     # rotation: newest N versions survive

# Current VALIDATED layout revision per file-type. Bump when that file's schema/layout changes;
# readers always take the highest revision present (the latest validated model).
FILE_REVISIONS = {
    "persona": 0, "preferences": 0, "memory": 0, "knowledge_graph": 0, "ledger": 0,
    "session": 0, "snapshot": 0, "working": 0, "competence": 0, "bundle": 0,
}

# file-type -> (function/scope, ext, folder relative to root | None for per-session).
FILE_SPEC = {
    "persona":         ("User", "json",   "user"),
    "preferences":     ("User", "json",   "user"),
    "memory":          ("User", "ndjson", "memory"),
    "knowledge_graph": ("User", "ndjson", "memory"),
    "ledger":          ("User", "ndjson", "memory"),
    "session":         ("Session", "json",   None),
    "snapshot":        ("Session", "json",   None),
    "working":         ("Session", "ndjson", None),
    "competence":      ("Session", "ndjson", None),
    "bundle":          ("Session", "json",   None),
}

# Folders of the canonical tree. `versions/` holds superseded copies; the MAIN folder holds latest.
FOLDERS = ["user", "user/files", "user/versions", "memory", "memory/versions",
           "swap", "staging", "archive"]

# Per-session files written under swap/<session_id>/ on a page-out.
SESSION_TYPES = ["session", "snapshot", "working", "competence", "bundle"]

_NAME_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9_]+)-(?P<function>[A-Za-z0-9_]+)-(?P<ts>\d{14}(?:\d{6})?)-R(?P<rev>\d{2})\.(?P<ext>[A-Za-z0-9]+)$")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_root():
    """Local swap root. APEX_HOME overrides; APEX_METHOD_HOME (AUD-W1, tests/CI isolation)
    relocates the base; default ~/.apex-method/APEX (portable, offline)."""
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    return os.environ.get("APEX_HOME") or os.path.join(base, "APEX")


# ── the file-naming standard ─────────────────────────────────────────────────────────────────
def make_filename(name, ext=None, function=None, rev=None, ts=None):
    """Canonical name `<name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext>`. function/ext default from
    FILE_SPEC; rev defaults to the file-type's current validated revision; ts defaults to now (UTC)."""
    fn, fext, _folder = FILE_SPEC.get(name, (function or "User", ext or "json", None))
    function = function or fn
    ext = ext or fext
    if rev is None:
        rev = FILE_REVISIONS.get(name, 0)
    # RT-09: second-resolution timestamps collide on rapid/concurrent page-outs and silently
    # overwrite a version. Default to UTC with MICROSECONDS (20 digits) from a single clock read
    # so two writes in the same second get distinct, still-sortable names ("every write a version").
    if ts is None:
        t = time.time()
        ts = time.strftime(NAME_TS_FMT, time.gmtime(t)) + f"{int((t % 1) * 1_000_000):06d}"
    return f"{name}-{function}-{ts}-R{int(rev):02d}.{ext}"


def parse_filename(fn):
    """Parse a canonical name into {name, function, ts, rev(int), ext} or None if it doesn't match."""
    m = _NAME_RE.match(fn or "")
    if not m:
        return None
    d = m.groupdict()
    d["rev"] = int(d["rev"])
    return d


def latest(filenames, name=None, function=None):
    """The LATEST validated file among a list: highest (revision, timestamp). Optionally filter by
    name/function. Returns the filename or None. Always read/edit this one, never an older revision."""
    best, best_key = None, None
    for fn in filenames:
        p = parse_filename(fn)
        if not p or (name and p["name"] != name) or (function and p["function"] != function):
            continue
        key = (p["rev"], p["ts"])
        if best_key is None or key > best_key:
            best, best_key = fn, key
    return best


def rotate(filenames, keep=KEEP_BACKUPS, name=None, function=None):
    """Rotation: keep the newest `keep` versions (by rev, ts) of a name/function; the rest are
    obsolete. Returns {keep, obsolete}. Local deletes the obsolete; on Drive (no delete API here)
    they are LISTED for GC."""
    versions = []
    for fn in filenames:
        p = parse_filename(fn)
        if not p or (name and p["name"] != name) or (function and p["function"] != function):
            continue
        versions.append((p["rev"], p["ts"], fn))
    versions.sort(reverse=True)                       # newest first
    return {"keep": [v[2] for v in versions[:keep]], "obsolete": [v[2] for v in versions[keep:]]}


def write_versioned(folder, name, content, keep=KEEP_BACKUPS, ts=None):
    """LOCAL page-out with rotation: write the new latest into `folder`, move any previous versions
    of the same file-type into `folder/versions/`, then delete versions beyond `keep`. Returns the
    written path + what was kept/deleted. (On Drive the runtime appends the new file and cannot move/
    delete — `latest()` computes the current one and `rotate()` lists obsolete ones for GC.)"""
    os.makedirs(folder, exist_ok=True)
    vdir = os.path.join(folder, "versions")
    os.makedirs(vdir, exist_ok=True)
    fn = make_filename(name, ts=ts)
    path = os.path.join(folder, fn)
    # RT-09b (GPT audit, validated on v1.42): the DEFAULT ts is already microsecond-unique, but a
    # caller-supplied EXPLICIT ts could collide with an existing file (same second/params) and
    # silently OVERWRITE it — breaking "every write is a new version". On collision, extend the
    # explicit 14-digit ts with a microsecond suffix (still matches the naming standard) until free.
    while os.path.exists(path) or os.path.exists(os.path.join(vdir, fn)):
        base_ts = parse_filename(fn)["ts"][:14]
        t = time.time()
        fn = make_filename(name, ts=base_ts + f"{int((t % 1) * 1_000_000):06d}")
        path = os.path.join(folder, fn)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    function = parse_filename(fn)["function"]
    for existing in list(os.listdir(folder)):
        p = parse_filename(existing)
        if not p or existing == fn:
            continue
        if p["name"] == name and p["function"] == function:
            os.replace(os.path.join(folder, existing), os.path.join(vdir, existing))
    rot = rotate(os.listdir(vdir), keep=keep, name=name, function=function)
    for old in rot["obsolete"]:
        try:
            os.remove(os.path.join(vdir, old))
        except OSError:
            pass
    return {"written": path, "filename": fn, "kept_versions": rot["keep"], "deleted": rot["obsolete"]}


# ── seed content for the template files ──────────────────────────────────────────────────────
def _seed_content(kind):
    if kind == "manifest":
        return json.dumps(model_spec(), indent=1, ensure_ascii=False)
    if kind == "readme":
        return ("# APEX swap store\n\nStandard memory hierarchy for apex-method (identical on local "
                "disk or Google Drive). Build it from `models/apex_structure.model.json` — never "
                "improvise the tree.\n\n"
                "- `user/` — persona + preferences + input files (durable, yours)\n"
                "- `memory/` — persistent validated memory across sessions (NDJSON, data not code)\n"
                "- `swap/<session>/` — ephemeral working state; survives the container, disposable\n"
                "- `staging/<session>/` — passed the validation gate, queued for a git commit\n"
                "- `archive/` — superseded swap pages · every folder has a `versions/` for backups\n\n"
                "Names: `<name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext>` — latest = highest (rev, ts), "
                "kept in the MAIN folder; older in `versions/`; newest 10 survive, older are GC'd.\n\n"
                "**Rule:** only what passes the gate (PMI adopt + intact SHA-256 ledger + tests) is "
                "promoted from `swap/` to a git commit.\n")
    if kind == "persona":
        return json.dumps({"role": "", "domain": "", "pronouns": "they/them", "expertise": [],
                           "tone": "", "notes": "",
                           "_doc": "Who the user is. APEX adapts personas/tone from this."},
                          indent=1, ensure_ascii=False)
    if kind == "preferences":
        try:
            import config
            cfg = config.load()
        except Exception:
            cfg = {"preferred_modes": ["STANDARD", "DEEP", "SCIENTIFIC"], "router_backend": "word",
                   "discovery_source": "both", "min_installs": 1000}
        cfg["persistence_backend"] = cfg.get("persistence_backend", "local-swap")
        cfg["_doc"] = "Mirror of config.json; the menu reads/writes these across sessions."
        return json.dumps(cfg, indent=1, ensure_ascii=False)
    if kind in ("memory", "knowledge_graph", "ledger"):
        table = {"memory": "memory", "knowledge_graph": "relations", "ledger": "ledger"}[kind]
        return json.dumps({"_seed": True, "table": table,
                           "note": "populated on first curated page-out"}, ensure_ascii=False) + "\n"
    return ""


def model_spec():
    """The STANDARD, as a dict — the single source of truth shipped as models/apex_structure.model.json
    so any backend (Windows / Drive) builds the SAME tree instead of improvising."""
    return {
        "schema_version": SCHEMA_VERSION, "product": "apex-method",
        "naming": {
            "pattern": "<name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext>",
            "example": "memory-User-20260716183245-R00.json",
            "ts_format": "%Y%m%d%H%M%S (UTC, 14 digits, sortable)",
            "revision": "R<NN> is the file's LAYOUT revision; bump on schema change; readers take the "
                        "highest (revision, ts) — the latest validated model",
        },
        "rotation": {"keep_backups": KEEP_BACKUPS, "versions_folder": "versions",
                     "policy": "newest KEEP by (revision, ts) survive in versions/; older are obsolete "
                               "(deleted on local; listed for GC on Drive — no delete API)"},
        "main_vs_versions": "the MAIN folder always holds the LATEST; older copies live in versions/",
        "file_revisions": dict(FILE_REVISIONS),
        "file_spec": {k: {"function": v[0], "ext": v[1], "folder": v[2]} for k, v in FILE_SPEC.items()},
        "folders": FOLDERS, "session_types": SESSION_TYPES,
        "static_files": ["apex.manifest.json", "README.md"],
        "tiers": {
            "user": "durable, user-owned (persona + preferences + input files)",
            "memory": "persistent validated memory (data, NDJSON)",
            "swap": "ephemeral per-session working state (disposable)",
            "staging": "validated, queued to promote to git",
            "archive": "superseded swap pages (GC target)"},
        "promotion_gate": ["pmi_adopt", "ledger_ok", "tests_ok", "completion_not_blocked"],
        "build_instructions": {
            "principle": "ALWAYS build from this standard model; never let the LLM invent the tree.",
            "windows": "materialize() into the user-provided folder; latest file in the main folder, "
                       "older in versions/.",
            "drive": "create the same folders/files via the Drive connector (drive_tree()); append-only "
                     "(no delete/move) — latest is computed by (revision, ts), obsolete listed for GC."},
    }


# ── materialize the tree (local) + describe it (drive) ───────────────────────────────────────
def materialize(root=None):
    """Build the canonical tree in a LOCAL folder from the standard. Idempotent: folders and seed
    files (fixed SEED_TS names) are created only if missing; existing data is NEVER overwritten."""
    root = root or default_root()
    created, skipped = [], []
    os.makedirs(root, exist_ok=True)
    for rel in FOLDERS:
        path = os.path.join(root, rel)
        (created if not os.path.isdir(path) else skipped).append(rel + "/")
        os.makedirs(path, exist_ok=True)
    for fname, kind in (("apex.manifest.json", "manifest"), ("README.md", "readme")):
        path = os.path.join(root, fname)
        if os.path.exists(path):
            skipped.append(fname)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(_seed_content(kind))
            created.append(fname)
    for name, (function, ext, folder) in FILE_SPEC.items():
        if folder is None:
            continue
        seed = make_filename(name, ts=SEED_TS)
        # only seed if no version of this file-type exists yet in the folder
        existing = [x for x in os.listdir(os.path.join(root, folder))
                    if (parse_filename(x) or {}).get("name") == name]
        if existing:
            skipped.append(f"{folder}/{name}*")
            continue
        with open(os.path.join(root, folder, seed), "w", encoding="utf-8") as f:
            f.write(_seed_content(name))
        created.append(f"{folder}/{seed}")
    return {"root": root, "created": created, "skipped": skipped}


def write_model(models_dir):
    """Write the standard to `<repo>/models/apex_structure.model.json` (the shipped template)."""
    os.makedirs(models_dir, exist_ok=True)
    path = os.path.join(models_dir, "apex_structure.model.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(model_spec(), f, indent=1, ensure_ascii=False)
    return path


def drive_tree():
    """The layout the RUNTIME creates on Google Drive (folders first, then static + seed files with
    content). Same standard as materialize(), so both backends match. Drive is append-only here."""
    tree = [{"path": rel, "kind": "folder"} for rel in FOLDERS]
    for fname, kind in (("apex.manifest.json", "manifest"), ("README.md", "readme")):
        tree.append({"path": fname, "kind": "file", "content": _seed_content(kind),
                     "mime": "application/json" if fname.endswith(".json") else "text/markdown"})
    for name, (function, ext, folder) in FILE_SPEC.items():
        if folder is None:
            continue
        tree.append({"path": f"{folder}/{make_filename(name, ts=SEED_TS)}", "kind": "file",
                     "content": _seed_content(name),
                     "mime": "application/json" if ext == "json" else "application/x-ndjson"})
    return tree


# ── the swap page: a portable bundle of the session's working + ALL durable state ────────────
def _sqlite_rows(db_path, query):
    """Best-effort row export from a store .db (missing db/table -> [])."""
    import sqlite3
    try:
        con = sqlite3.connect(db_path)
        cur = con.execute(query)
        cols = [c[0] for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        con.close()
        return rows
    except Exception:
        return []


def collect_stores(root=None):
    """PLUG-AND-PLAY (the original idea): capture EVERY durable store, so a page-in on a fresh
    machine never starts from zero — the user's habits/spec directives (config + persona +
    preferences), the trained agents (grants = what each agent equipped), the validated
    promote/demote history (learning), the session competence signals, and who-connects-to-whom
    is re-derivable from the shipped attraction_graph. Memory itself travels separately (delta-able)."""
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    stores = {"grants": [], "learning": [], "competence": [], "config": {}, "user": {}}
    try:
        import agent_registry
        stores["grants"] = agent_registry.load_grants()
    except Exception:
        pass
    stores["learning"] = _sqlite_rows(os.path.join(base, "learning.db"),
                                      "SELECT sha,kind,subject,domain,successes,trials,status,mean,updated FROM outcomes")
    stores["competence"] = _sqlite_rows(os.path.join(base, "competence.db"),
                                        "SELECT sha,ts,persona,stance,task,signal,confidence FROM competence")
    stores["vaccines"] = _sqlite_rows(os.path.join(base, "vaccines.db"),
                                      "SELECT sig,fix,uses,successes,error FROM vaccines")
    try:                                           # v1.46: as ROTINAS das personas viajam também
        import routine_composer
        stores["routines"] = routine_composer.load_routines()
    except Exception:
        stores["routines"] = []
    try:
        import config
        stores["config"] = config.load()
    except Exception:
        pass
    # the user tier of the swap tree: persona + preferences (habits / standard spec directives)
    try:
        udir = os.path.join(root or default_root(), "user")
        for name in ("persona", "preferences"):
            fn = latest(os.listdir(udir), name)
            if fn:
                stores["user"][name] = json.loads(open(os.path.join(udir, fn), encoding="utf-8").read())
    except Exception:
        pass
    return stores


def export_bundle(session_id, memory_db=None, snapshot=None, working=None, project_ledger=None,
                  competence=None, session_meta=None, stores=None, root=None, delta_known=None):
    """Build ONE portable JSON page (page-out): durable memory export + ALL durable stores +
    ephemeral session state, with a SHA-256 over the canonical payload for integrity.

    v1.44 (plug-and-play): `stores` carries grants/learning/competence/config/persona — the full
    "never start from zero" state. `delta_known` = {"memory": set, "relations": set, "ledger": set}
    of shas already persisted: when given, only NEW memory rows are exported and the bundle records
    `delta_of` (the previous bundle's sha) so page-in applies the chain in order. Stores are small
    and always travel FULL (idempotent to reapply)."""
    mem = {}
    try:
        import memory
        mem = (memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()).export()
    except Exception as e:
        mem = {"_error": str(e)[:80]}
    delta_of = None
    if delta_known:
        delta_of = delta_known.get("bundle_sha")
        for table, key in (("memory", "memory"), ("relations", "relations"), ("ledger", "ledger")):
            known = set(delta_known.get(key) or ())
            if isinstance(mem.get(table), list):
                mem[table] = [r for r in mem[table] if r.get("sha") not in known]
    payload = {"schema_version": SCHEMA_VERSION, "session_id": session_id, "ts": time.time(),
               "filename": make_filename("bundle"), "session": session_meta or {},
               "snapshot": snapshot or {}, "working": working or [],
               "project_ledger": project_ledger or {}, "competence": competence or [],
               "memory": mem, "stores": (stores if stores is not None else collect_stores(root)),
               "delta_of": delta_of}
    # RT-08: hash EVERY field (except the signature itself) so project_ledger, competence,
    # schema_version, ts and filename are all covered — not just the old 5-field subset.
    payload["sha256"] = _bundle_sha(payload)
    return payload


def _bundle_sha(bundle):
    """SHA-256 over the whole bundle except its own `sha256` field (canonical, sorted JSON)."""
    unsigned = {k: v for k, v in bundle.items() if k != "sha256"}
    return _sha(json.dumps(unsigned, sort_keys=True, ensure_ascii=False))


def _restore_stores(stores):
    """Rehydrate the plug-and-play stores. Semantics: bundle WINS (idempotent restore — re-applying
    the same bundle is a no-op). Grants merge by record identity; learning/competence REPLACE by
    primary key; config merges known keys; persona/preferences are returned for the user tier."""
    import sqlite3
    out = {"grants": 0, "learning": 0, "competence": 0, "vaccines": 0, "routines": 0,
           "config": False, "user": list((stores or {}).get("user", {}))}
    if not stores:
        return out
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    os.makedirs(base, exist_ok=True)
    try:                                           # grants: union preserving order (identity = full record)
        import agent_registry
        local = agent_registry.load_grants()
        seen = [json.dumps(g, sort_keys=True) for g in local]
        added = [g for g in stores.get("grants", []) if json.dumps(g, sort_keys=True) not in seen]
        if added:
            merged = local + added
            with open(agent_registry._grants_path(), "w", encoding="utf-8") as f:
                json.dump(merged, f, indent=1, ensure_ascii=False)
        out["grants"] = len(added)
    except Exception:
        pass
    try:                                           # learning: bundle rows REPLACE by sha
        import learning
        s = learning.LearningStore()               # ensures schema
        con = sqlite3.connect(s.db_path)
        for r in stores.get("learning", []):
            con.execute("INSERT OR REPLACE INTO outcomes VALUES(?,?,?,?,?,?,?,?,?)",
                        (r["sha"], r["kind"], r["subject"], r["domain"], r["successes"],
                         r["trials"], r["status"], r["mean"], r["updated"]))
            out["learning"] += 1
        con.commit(); con.close()
    except Exception:
        pass
    try:                                           # competence: session signals REPLACE by sha
        con = sqlite3.connect(os.path.join(base, "competence.db"))
        con.execute("CREATE TABLE IF NOT EXISTS competence("
                    "sha TEXT PRIMARY KEY, ts REAL, persona TEXT, stance TEXT, task TEXT, "
                    "signal TEXT, confidence REAL)")
        for r in stores.get("competence", []):
            con.execute("INSERT OR REPLACE INTO competence VALUES(?,?,?,?,?,?,?)",
                        (r["sha"], r["ts"], r["persona"], r["stance"], r["task"],
                         r["signal"], r["confidence"]))
            out["competence"] += 1
        con.commit(); con.close()
    except Exception:
        pass
    try:                                           # vaccines: experience -> future context
        con = sqlite3.connect(os.path.join(base, "vaccines.db"))
        con.execute("CREATE TABLE IF NOT EXISTS vaccines "
                    "(sig TEXT PRIMARY KEY, fix TEXT, uses INTEGER, successes INTEGER, error TEXT)")
        for r in stores.get("vaccines", []):
            con.execute("INSERT OR REPLACE INTO vaccines VALUES(?,?,?,?,?)",
                        (r["sig"], r["fix"], r["uses"], r["successes"], r.get("error", "")))
            out["vaccines"] += 1
        con.commit(); con.close()
    except Exception:
        pass
    try:                                           # routines: a persona reutiliza o que funcionou
        import routine_composer
        for r in stores.get("routines", []):
            if routine_composer.save_routine(r).get("status") == "OK":
                out["routines"] += 1
    except Exception:
        pass
    try:                                           # config: the user's habits/spec directives win
        import config as cfg_mod
        if stores.get("config"):
            local_cfg = cfg_mod.load()
            local_cfg.update({k: v for k, v in stores["config"].items() if k in cfg_mod.DEFAULTS})
            cfg_mod.save(local_cfg)
            out["config"] = True
    except Exception:
        pass
    return out


def _decode_envelope(bundle):
    """Accept a gzip+b64 envelope (v1.44 compress=True) transparently."""
    if isinstance(bundle, dict) and bundle.get("encoding") == "gzip+b64":
        import base64
        import gzip
        return json.loads(gzip.decompress(base64.b64decode(bundle["payload"])).decode("utf-8"))
    return bundle


def _marker_path():
    base = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
    return os.path.join(base, "last_page_in.json")


def import_bundle(bundle, memory_db=None, quarantine_dir=None, restore_stores=True, root=None):
    """Rehydrate a swap page (page-in): load durable memory back into the local .db, restore the
    plug-and-play stores (grants/learning/competence/config), record the page-in marker (feeds
    resume_due), and return the ephemeral session state to resume from.

    RT-07/RT-08: verify integrity over the WHOLE payload and FAIL CLOSED — a bundle whose hash does
    not match (or whose schema is unknown) is REJECTED before any write to the memory .db. For
    forensics, pass quarantine_dir to copy the rejected bundle aside without hydrating it."""
    bundle = _decode_envelope(bundle)
    try:
        ok = (bundle.get("sha256") is not None and _bundle_sha(bundle) == bundle["sha256"])
    except Exception:
        ok = False
    sv = bundle.get("schema_version")
    if sv is not None and sv != SCHEMA_VERSION:
        return {"integrity_ok": ok, "status": "REJECTED_SCHEMA", "memory_stats": {},
                "reason": f"unknown schema_version {sv!r} (expected {SCHEMA_VERSION})"}
    if not ok:
        if quarantine_dir:                       # forensic mode: isolate, never load
            try:
                os.makedirs(quarantine_dir, exist_ok=True)
                qn = os.path.join(quarantine_dir, bundle.get("filename") or "rejected-bundle.json")
                with open(qn, "w", encoding="utf-8") as f:
                    json.dump(bundle, f, ensure_ascii=False)
            except Exception:
                pass
        return {"integrity_ok": False, "status": "REJECTED", "memory_stats": {},
                "reason": "bundle hash mismatch — refusing to hydrate tampered state"}
    mem_stats = {}
    try:
        import memory
        store = memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()
        mem_stats = store.load_rows(bundle.get("memory", {}))
    except Exception as e:
        mem_stats = {"_error": str(e)[:80]}
    stores_restored = _restore_stores(bundle.get("stores")) if restore_stores else None
    # user tier files (persona/preferences) are re-materialized into the swap tree when known
    if restore_stores and root and (bundle.get("stores") or {}).get("user"):
        try:
            udir = os.path.join(root, "user")
            for name, content in bundle["stores"]["user"].items():
                write_versioned(udir, name, json.dumps(content, ensure_ascii=False, indent=1))
        except Exception:
            pass
    try:                                           # resume_due marker: this bundle is now local
        with open(_marker_path(), "w", encoding="utf-8") as f:
            json.dump({"bundle_sha": bundle["sha256"], "filename": bundle.get("filename"),
                       "session_id": bundle.get("session_id"), "ts": time.time()}, f)
    except Exception:
        pass
    return {"integrity_ok": True, "status": "OK", "session_id": bundle.get("session_id"),
            "session": bundle.get("session", {}), "snapshot": bundle.get("snapshot", {}),
            "working": bundle.get("working", []), "project_ledger": bundle.get("project_ledger", {}),
            "competence": bundle.get("competence", []), "memory_stats": mem_stats,
            "stores_restored": stores_restored, "delta_of": bundle.get("delta_of")}


# ── THE EXPLICIT PERSISTENCE TRIGGER (page-out) ──────────────────────────────────────────────
PERSIST_MODES = ("DEEP", "SCIENTIFIC", "RESEARCH")


def persist_due(mode):
    """End-of-session page-out is MANDATORY for heavy modes (state worth keeping); lighter modes
    are ephemeral by design. The orchestrator/menu use this to fire page_out at session end."""
    return (mode or "").upper() in PERSIST_MODES


def _load_bundle_file(path):
    """Read a bundle file (plain JSON or gzip+b64 envelope)."""
    with open(path, encoding="utf-8") as f:
        return _decode_envelope(json.load(f))


def _session_bundles(sdir):
    """The session's bundle files, oldest -> newest by (revision, ts). Rotation keeps only the
    LATEST in the main folder and moves older versions into versions/ — a delta CHAIN therefore
    spans both places, so the versions/ subfolder MUST be scanned too (found by the plug-and-play
    smoke test: without it, page_in_session applied the delta but lost the base memories)."""
    out = []
    for base, sub in ((sdir, ""), (os.path.join(sdir, "versions"), "versions/")):
        try:
            for x in os.listdir(base):
                if (parse_filename(x) or {}).get("name") == "bundle":
                    out.append(sub + x)
        except OSError:
            continue
    return sorted(out, key=lambda fn: (parse_filename(os.path.basename(fn))["rev"],
                                       parse_filename(os.path.basename(fn))["ts"]))


def page_out(session_id, memory_db=None, snapshot=None, working=None, session_meta=None,
             root=None, backend=None, delta=False, compress=False):
    """THE EXPLICIT SWAP TRIGGER. Builds the session bundle, writes it (+ a session header) LOCALLY
    into <root>/swap/<session_id>/ with canonical versioned names, and returns a `drive_manifest`
    the runtime uploads to APEX/swap/<session_id>/ on Drive — plus a human-readable `log` so the
    user ALWAYS sees the page-out happened (never silent). `backend` (config.persist_backend) says
    where durability goes: 'drive-swap' = Claude uploads the manifest via the Drive tools; 'local'/
    'git'/'zip' = the on-disk copy is the durable artifact."""
    root = root or default_root()
    materialize(root)
    sdir = os.path.join(root, "swap", str(session_id))
    os.makedirs(sdir, exist_ok=True)
    # v1.44 delta: export only what the session's previous bundles haven't persisted yet
    delta_known = None
    if delta:
        prev = _session_bundles(sdir)
        if prev:
            known = {"memory": set(), "relations": set(), "ledger": set()}
            last_sha = None
            for fn in prev:
                try:
                    b = _load_bundle_file(os.path.join(sdir, fn))
                    for key in known:
                        known[key] |= {r.get("sha") for r in b.get("memory", {}).get(key, [])}
                    last_sha = b.get("sha256", last_sha)
                except Exception:
                    continue
            delta_known = {**known, "bundle_sha": last_sha}
    bundle = export_bundle(session_id, memory_db=memory_db, snapshot=snapshot, working=working,
                           session_meta=session_meta, root=root, delta_known=delta_known)
    hdr = {"session_id": session_id, "ts": time.time(), "session": session_meta or {},
           "snapshot_objective": (snapshot or {}).get("objective"), "bundle": bundle["filename"],
           "sha256": bundle["sha256"], "delta_of": bundle.get("delta_of")}
    raw = json.dumps(bundle, ensure_ascii=False)
    if compress:                                   # v1.44: ~10x smaller on the wire/Drive
        import base64
        import gzip
        raw = json.dumps({"schema_version": SCHEMA_VERSION, "encoding": "gzip+b64",
                          "payload": base64.b64encode(gzip.compress(raw.encode("utf-8"), 6)).decode()})
    written = {}
    for name, content in (("session", json.dumps(hdr, ensure_ascii=False, indent=1)),
                          ("bundle", raw)):
        written[name] = write_versioned(sdir, name, content)["filename"]
    n_mem = len(bundle.get("memory", {}).get("memory", []))
    n_led = len(bundle.get("memory", {}).get("ledger", []))
    st = bundle.get("stores", {})
    drive_manifest = [
        {"path": f"swap/{session_id}/{written['session']}",
         "content": json.dumps(hdr, ensure_ascii=False, indent=1), "mime": "application/json"},
        {"path": f"swap/{session_id}/{written['bundle']}",
         "content": raw, "mime": "application/json"}]
    log = (f"[PAGE-OUT] session={session_id} -> swap/{session_id}/ | {written['bundle']} "
           f"({n_mem} memories{' DELTA' if bundle.get('delta_of') else ''}, {n_led} ledger events, "
           f"{len(st.get('grants', []))} grants, {len(st.get('learning', []))} learning rows, "
           f"sha {bundle['sha256'][:12]}) | backend={backend or 'local'}"
           + (" | compressed" if compress else "")
           + (" | UPLOAD the drive_manifest to Drive to persist" if backend == "drive-swap" else ""))
    return {"session_dir": sdir, "written": written, "bundle_sha": bundle["sha256"],
            "counts": {"memories": n_mem, "ledger": n_led,
                       "grants": len(st.get("grants", [])), "learning": len(st.get("learning", []))},
            "backend": backend, "delta": bool(bundle.get("delta_of")), "compressed": compress,
            "drive_manifest": drive_manifest, "log": log}


def page_in_session(session_dir, memory_db=None, root=None):
    """Apply a session's WHOLE bundle chain (base + deltas), oldest -> newest. Each bundle is
    integrity-checked individually; a tampered link is skipped and reported, never hydrated."""
    applied, skipped = [], []
    last = None
    for fn in _session_bundles(session_dir):
        try:
            b = _load_bundle_file(os.path.join(session_dir, fn))
        except Exception as e:
            skipped.append({"file": fn, "reason": f"unreadable: {str(e)[:60]}"})
            continue
        r = import_bundle(b, memory_db=memory_db, root=root)
        if r["status"] == "OK":
            applied.append({"file": fn, "delta_of": r.get("delta_of")})
            last = r
        else:
            skipped.append({"file": fn, "reason": r.get("reason", r["status"])})
    return {"status": "OK" if applied else "EMPTY", "applied": applied, "skipped": skipped,
            "resumed": last}


def resume_due(root=None):
    """The symmetric twin of persist_due (v1.44): is there swap state NEWER than what this machine
    already paged in? Scans swap/<session>/ for the newest bundle and compares against the local
    page-in marker. due=True carries the exact page-in call — plug-and-play resume at session start."""
    root = root or default_root()
    swap = os.path.join(root, "swap")
    newest = None                                   # (rev, ts, session, filename)
    try:
        for sess in os.listdir(swap):
            sdir = os.path.join(swap, sess)
            if not os.path.isdir(sdir):
                continue
            for fn in _session_bundles(sdir):
                p = parse_filename(os.path.basename(fn))
                key = (p["rev"], p["ts"])
                if newest is None or key > newest[0]:
                    newest = (key, sess, fn)
    except OSError:
        pass
    if newest is None:
        return {"due": False, "reason": "no swap state found"}
    _, sess, fn = newest
    try:
        marker = json.load(open(_marker_path(), encoding="utf-8"))
    except Exception:
        marker = {}
    try:
        newest_sha = _load_bundle_file(os.path.join(swap, sess, fn)).get("sha256")
    except Exception:
        newest_sha = None
    if newest_sha and marker.get("bundle_sha") == newest_sha:
        return {"due": False, "reason": "latest swap state already paged in", "session": sess}
    return {"due": True, "session": sess, "bundle": fn, "bundle_sha": newest_sha,
            "directive": (f"swap has state this machine hasn't loaded — call "
                          f"swap_store.page_in_session(r'{os.path.join(swap, sess)}') to resume "
                          f"with the user's habits, trained agents, grants and validated learning")}


# ── the promotion gate: only VALIDATED artifacts go to a git commit ─────────────────────────
def is_validated(signals):
    """The gate. Validated = PMI adopted AND the SHA-256 ledger is intact AND tests pass (if run)
    AND completion is not blocking. Anything failing this stays in swap (disposable)."""
    return (bool(signals.get("pmi_adopt")) and signals.get("ledger_ok", True)
            and signals.get("tests_ok", True) and not signals.get("completion_blocked", False))


def promotion_manifest(session_id, artifacts, signals):
    """Split the session's artifacts into PROMOTE (git commit / durable memory) vs KEEP in swap,
    using the gate. `artifacts` = [{name, kind, target}]."""
    validated = is_validated(signals)
    promote, keep = ([], artifacts) if not validated else (artifacts, [])
    return {"session_id": session_id, "validated": validated,
            "gate": {k: signals.get(k) for k in
                     ("pmi_adopt", "ledger_ok", "tests_ok", "completion_blocked")},
            "promote": promote, "keep_in_swap": keep,
            "reason": ("gate passed — promote to commit/memory" if validated
                       else "gate failed — stays disposable in swap until validated")}


if __name__ == "__main__":
    import tempfile
    root = os.path.join(tempfile.mkdtemp(), "APEX")
    res = materialize(root)
    print("materialized:", res["root"], "| created:", len(res["created"]))
    print("example name:", make_filename("memory"))
    # versioned writes + rotation (keep 3)
    folder = os.path.join(root, "user")
    for i in range(5):
        w = write_versioned(folder, "persona", json.dumps({"v": i}), keep=3,
                            ts=time.strftime(NAME_TS_FMT, time.gmtime(time.time() + i)))
    main = [x for x in os.listdir(folder) if (parse_filename(x) or {}).get("name") == "persona"]
    vers = os.listdir(os.path.join(folder, "versions"))
    print("latest in main:", latest(main, "persona"), "| versions kept:", len(vers), "(keep=3)")
    b = export_bundle("sess1", snapshot={"objective": "demo"}, session_meta={"mode": "DEEP"})
    print("bundle:", b["filename"], "| page-in ok:", import_bundle(b)["integrity_ok"])
    print("promotion:", promotion_manifest("s", [{"name": "d"}], {"pmi_adopt": True})["validated"])
    print("model file:", write_model(os.path.join(root, "models")))
