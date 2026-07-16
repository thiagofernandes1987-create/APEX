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
    r"^(?P<name>[A-Za-z0-9_]+)-(?P<function>[A-Za-z0-9_]+)-(?P<ts>\d{14})-R(?P<rev>\d{2})\.(?P<ext>[A-Za-z0-9]+)$")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def default_root():
    """Local swap root. APEX_HOME overrides; default ~/.apex-method/APEX (portable, offline)."""
    return os.environ.get("APEX_HOME") or os.path.expanduser("~/.apex-method/APEX")


# ── the file-naming standard ─────────────────────────────────────────────────────────────────
def make_filename(name, ext=None, function=None, rev=None, ts=None):
    """Canonical name `<name>-<function>-<YYYYMMDDHHMMSS>-R<NN>.<ext>`. function/ext default from
    FILE_SPEC; rev defaults to the file-type's current validated revision; ts defaults to now (UTC)."""
    fn, fext, _folder = FILE_SPEC.get(name, (function or "User", ext or "json", None))
    function = function or fn
    ext = ext or fext
    if rev is None:
        rev = FILE_REVISIONS.get(name, 0)
    ts = ts or time.strftime(NAME_TS_FMT, time.gmtime())
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


# ── the swap page: a portable bundle of the session's working + durable memory ───────────────
def export_bundle(session_id, memory_db=None, snapshot=None, working=None, project_ledger=None,
                  competence=None, session_meta=None):
    """Build ONE portable JSON page (page-out): durable memory export + ephemeral session state, with
    a SHA-256 over the canonical payload for integrity. The runtime writes it under swap/<session>/
    with a canonical `bundle-...` name (make_filename('bundle'))."""
    mem = {}
    try:
        import memory
        mem = (memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()).export()
    except Exception as e:
        mem = {"_error": str(e)[:80]}
    payload = {"schema_version": SCHEMA_VERSION, "session_id": session_id, "ts": time.time(),
               "filename": make_filename("bundle"), "session": session_meta or {},
               "snapshot": snapshot or {}, "working": working or [],
               "project_ledger": project_ledger or {}, "competence": competence or [], "memory": mem}
    payload["sha256"] = _sha(json.dumps({k: payload[k] for k in
                             ("session_id", "session", "snapshot", "working", "memory")},
                             sort_keys=True, ensure_ascii=False))
    return payload


def import_bundle(bundle, memory_db=None):
    """Rehydrate a swap page (page-in): load durable memory back into the local .db and return the
    ephemeral session state to resume from. Verifies the integrity hash."""
    try:
        check = _sha(json.dumps({k: bundle.get(k) for k in
                     ("session_id", "session", "snapshot", "working", "memory")},
                     sort_keys=True, ensure_ascii=False))
        ok = (check == bundle.get("sha256"))
    except Exception:
        ok = False
    mem_stats = {}
    try:
        import memory
        store = memory.MemoryStore(memory_db) if memory_db else memory.MemoryStore()
        mem_stats = store.load_rows(bundle.get("memory", {}))
    except Exception as e:
        mem_stats = {"_error": str(e)[:80]}
    return {"integrity_ok": ok, "session_id": bundle.get("session_id"),
            "session": bundle.get("session", {}), "snapshot": bundle.get("snapshot", {}),
            "working": bundle.get("working", []), "project_ledger": bundle.get("project_ledger", {}),
            "memory_stats": mem_stats}


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
