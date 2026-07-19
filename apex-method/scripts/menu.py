#!/usr/bin/env python3
"""
menu.py — The apex-method skill menu: update, choose preferred modes, deep research.

WHY THIS EXISTS:
  A skill has no GUI, but users still want a small set of top-level actions. This is that
  menu, exposed as commands Claude runs on request:
    - `menu`               show the menu + current preferences
    - `update`             check the repo for a newer skill version and sync it, then verify
    - `modes A,B,C`        set the preferred operating modes (persisted via config.py)
    - `set KEY VALUE`      set one option (router_backend / discovery_source / min_installs)
    - `research "<q>" [--source native|search|both]`  run the goal-like deep-research loop

WHEN TO USE:
  When the user asks to update the skill, change preferred modes, or launch a deep/goal-like
  research run over the APEX domain and its agents.

WHAT IF IT FAILS:
  update offline -> reports OFFLINE and keeps the installed version; every action degrades
  to a clear message instead of crashing.
"""
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(__file__)
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import config as _config


def _installed_version():
    try:
        txt = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
        m = re.search(r"^version:\s*([0-9.]+)", txt, re.M)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


def _remote_version():
    """Read the version of the skill's SKILL.md in the APEX repo (allowlisted raw)."""
    try:
        import repo_bridge
        r = repo_bridge.fetch("apex-method/SKILL.md")
        if r["status"] != "OK":
            return None, r["status"]
        m = re.search(r"^version:\s*([0-9.]+)", r["text"], re.M)
        return (m.group(1) if m else "?"), "OK"
    except Exception as e:
        return None, str(e)[:80]


def _vtuple(v):
    try:
        return tuple(int(x) for x in v.split("."))
    except Exception:
        return (0,)


def update(apply=False):
    """Check the repo for a newer version. With apply=True (and a local clone), sync files."""
    cur = _installed_version()
    rem, status = _remote_version()
    if rem is None:
        return {"status": status, "installed": cur,
                "note": "cannot reach the repo; installed version unchanged"}
    newer = _vtuple(rem) > _vtuple(cur)
    out = {"status": "OK", "installed": cur, "remote": rem, "update_available": newer}
    if newer and apply:
        try:
            import repo_bridge
            root = repo_bridge._local_root()
            if root:
                src = os.path.join(root, "apex-method")
                # AUD-W2: `cp -r` is Unix-only; shutil is the portable equivalent.
                import shutil
                # UPD-001 fix (v1.52.0): the old flow copied OVER the live install BEFORE
                # validating and never checked the benchmark's exit code, so a broken remote
                # version bricked the skill and still returned applied=true. Now it is
                # TRANSACTIONAL: stage in a temp dir -> validate there -> only swap in on a
                # clean pass -> keep a backup and roll back on any failure.
                import tempfile
                stage = tempfile.mkdtemp(prefix="apex-update-stage-")
                staged = os.path.join(stage, "apex-method")
                shutil.copytree(src, staged)
                bench = subprocess.run(
                    [sys.executable, os.path.join(staged, "tests", "benchmark.py")],
                    capture_output=True, text=True)
                total = next((l for l in bench.stdout.splitlines() if l.startswith("TOTAL")), "")
                frac = total.split()[1] if len(total.split()) > 1 else "0/1"
                p_ok, t_ok = (int(x) for x in frac.split("/")) if "/" in frac else (0, 1)
                clean = bench.returncode == 0 and p_ok == t_ok and t_ok > 0
                if not clean:
                    shutil.rmtree(stage, ignore_errors=True)
                    out["applied"] = False
                    out["status"] = "REJECTED_STAGED"
                    out["verify"] = total.strip()
                    out["note"] = ("staged version failed validation "
                                   f"(rc={bench.returncode}, {frac}); install untouched")
                    return out
                # atomic-ish swap: move current aside, move staged in, drop backup on success
                backup = os.path.join(stage, "backup")
                shutil.move(ROOT, backup)
                try:
                    shutil.move(staged, ROOT)
                except Exception:
                    shutil.move(backup, ROOT)     # rollback
                    raise
                shutil.rmtree(stage, ignore_errors=True)
                out["applied"] = True
                out["verify"] = total.strip()
            else:
                out["applied"] = False
                out["note"] = "no local clone; run `npx skills update` or pull the repo, then re-run"
        except Exception as e:
            out["applied"] = False
            out["error"] = str(e)[:120]
    elif newer:
        out["how"] = "run menu.py update --apply (local clone) or `npx skills update apex-method`"
    return out


def set_modes(modes_csv):
    return _config.set_preferred_modes([m.strip() for m in modes_csv.split(",") if m.strip()])


def set_option(key, value):
    if key == "min_installs":
        try:
            value = int(value)
        except ValueError:
            return {"status": "ERROR", "reason": "min_installs must be an integer"}
    return _config.set_option(key, value)


def research(question, source=None):
    import deep_research
    return deep_research.research(question, source=source)


def persist(session_id=None, backend=None):
    """Explicit page-out trigger: swap the current session's durable memory to the swap store and,
    for the drive-swap backend, return the manifest for Claude to upload to Drive. Prints the log."""
    import swap_store
    sid = session_id or time.strftime("session-%Y%m%d%H%M%S", time.gmtime())
    be = backend or _config.load().get("persist_backend") or "local"
    import memory as _mem                       # AUD-W1: honour APEX_METHOD_HOME, one source of truth
    res = swap_store.page_out(sid, memory_db=_mem.DB_DEFAULT,
                              snapshot={"objective": "session page-out via menu"}, backend=be)
    return res


def show():
    cfg = _config.load()
    return {
        "skill": "apex-method", "version": _installed_version(),
        "menu": {
            "1_update": "menu.py update [--apply] — check/sync a newer skill version",
            "2_modes": f"menu.py modes DEEP,SCIENTIFIC — set preferred modes (now: {cfg['preferred_modes']})",
            "3_options": (f"menu.py set router_backend char|word|st (now: {cfg['router_backend']}) · "
                          f"set discovery_source native|search|both (now: {cfg['discovery_source']}) · "
                          f"set min_mode DEEP (force pipeline; now: {cfg.get('min_mode')}) · "
                          f"set persist_backend drive-swap|git|zip|local (now: {cfg.get('persist_backend')})"),
            "4_research": "menu.py research \"<question>\" --source native|search|both — goal-like deep research",
            "5_persist": "menu.py persist [session_id] [backend] — page the session's memory out to the swap store (Drive/git/zip/local)",
        },
        "preferences": cfg,
    }


def main():
    a = sys.argv[1:]
    if not a or a[0] == "menu":
        print(json.dumps(show(), indent=1, ensure_ascii=False)); return
    cmd = a[0]
    if cmd == "update":
        print(json.dumps(update(apply="--apply" in a), indent=1))
    elif cmd == "modes" and len(a) >= 2:
        print(json.dumps(set_modes(a[1]), indent=1))
    elif cmd == "set" and len(a) >= 3:
        print(json.dumps(set_option(a[1], a[2]), indent=1))
    elif cmd == "research" and len(a) >= 2:
        src = next((x.split("=", 1)[1] for x in a if x.startswith("--source=")), None)
        if src is None and "--source" in a:
            i = a.index("--source"); src = a[i + 1] if i + 1 < len(a) else None
        q = " ".join(x for x in a[1:] if not x.startswith("--") and x != src)
        out = research(q, source=src)
        print(f"MODE {out['mode']} | SOURCE {out['source']} | STOP {out['stop_reason']} "
              f"after {out['rounds_run']} rounds | trace {out['reliability_trace']}")
        print(f"staged installs needing approval (H5): {len(out['staged_installs'])}")
    elif cmd == "persist":
        sid = a[1] if len(a) >= 2 else None
        be = a[2] if len(a) >= 3 else None
        res = persist(sid, be)
        print(res["log"])
        print(json.dumps({"written": res["written"], "counts": res["counts"],
                          "drive_manifest_files": [m["path"] for m in res["drive_manifest"]]},
                         indent=1, ensure_ascii=False))
    else:
        print(json.dumps(show(), indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
