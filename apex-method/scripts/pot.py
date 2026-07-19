#!/usr/bin/env python3
"""
pot.py — Program-of-Thought runner (APEX method).

WHY THIS EXISTS:
  An LLM reasoning in prose approximates arithmetic and loses precision on
  multi-step numeric/logical work. PoT offloads those sub-problems to a real
  Python interpreter, so the answer is COMPUTED, not guessed.

WHEN TO USE:
  Any sub-problem with >2 intermediate numeric steps, iteration, combinatorics,
  simulation, or anything where an exact/verifiable answer matters.
  (Mirrors APEX rules SR_01 / SR_09: iteration >5 steps MUST run in subprocess.)

WHAT IT DOES:
  - Runs each PoT step in an ISOLATED subprocess (crash in one != crash in run).
  - Chains steps: the stdout of step N is passed as input to step N+1.
  - Records every step into a snapshot checklist (see snapshot.py format).

WHAT IT IS NOT:
  - Not parallel *reasoning*. Generation of the code is sequential (one LLM).
    Parallelism here is of EXECUTION only, and only pays off for slow steps.

WHAT IF IT FAILS:
  - A failed step is recorded with its stderr; the chain STOPS (does not
    fabricate a downstream result). Caller decides whether to patch & retry.
"""
import os, subprocess, sys, json, time, hashlib, signal, tempfile, shutil
from concurrent.futures import ThreadPoolExecutor

# ── Autopsy hardening (v1.52.0) ──────────────────────────────────────────────
# The audit proved a PoT step is NOT a sandbox: it read parent-env secrets, wrote
# files anywhere, kept orphaned descendants alive past the timeout, and could
# capture unbounded stdout. This is still a plain subprocess (real OS isolation
# needs a container/namespace — see run_step docstring), but these controls close
# the confirmed holes: a scrubbed env (no secret inheritance), a disposable scratch
# CWD, a hard output cap, and process-TREE termination on timeout.
MAX_OUTPUT_BYTES = 1_000_000          # SEC-003: cap captured stdout/stderr
_TRUNC = "\n[OUTPUT_TRUNCATED]"

# SEC-001: only pass the variables Python itself needs to start + load extensions.
# Arbitrary parent-process secrets (API keys, tokens, APEX_* internals) are dropped.
_ENV_ALLOW = ("SYSTEMROOT", "WINDIR", "PATH", "PATHEXT", "TEMP", "TMP", "TMPDIR",
              "LANG", "LC_ALL", "LC_CTYPE", "TZ", "NUMBER_OF_PROCESSORS",
              "SYSTEMDRIVE", "HOMEDRIVE", "COMSPEC", "LD_LIBRARY_PATH")


def _safe_env() -> dict:
    env = {k: os.environ[k] for k in _ENV_ALLOW if k in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _kill_tree(proc):
    """SEC-002: kill the whole process group/tree, not just the direct child, so a
    grandchild spawned by the PoT code cannot outlive the timeout."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           capture_output=True)
        else:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def run_step(code: str, stdin_data: str = "", timeout: int = 20,
             inherit_env: bool = False) -> dict:
    """Run one PoT step in an isolated subprocess. Returns a result dict.

    Hardened (v1.52.0): scrubbed env by default (pass inherit_env=True only for trusted
    code that genuinely needs the parent environment), disposable working directory,
    output capped at MAX_OUTPUT_BYTES, and process-tree kill on timeout. This is
    containment of *accidents and confirmed leaks* — NOT a security sandbox for hostile
    code; that still requires an OS-level container."""
    t0 = time.time()
    chash = hashlib.sha256(code.encode()).hexdigest()[:8]
    workdir = tempfile.mkdtemp(prefix="apex-pot-")
    popen_kw = {}
    if os.name == "nt":
        popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        popen_kw["start_new_session"] = True     # own process group -> killpg works
    proc = None
    try:
        # NOTE: no -I/-E — that would ignore our PYTHONIOENCODING=utf-8 and reintroduce
        # cp1252 crashes on Windows. Security comes from the scrubbed env + scratch cwd,
        # not from interpreter isolation flags. -s drops user site-packages only.
        proc = subprocess.Popen(
            [sys.executable, "-s", "-c", code],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", cwd=workdir,
            env=None if inherit_env else _safe_env(), **popen_kw,
        )
        try:
            out, err = proc.communicate(input=stdin_data, timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)                      # SEC-002: terminate descendants
            try:
                out, err = proc.communicate(timeout=5)
            except Exception:
                out, err = "", ""
            return {"ok": False, "stdout": "", "stderr": f"timeout>{timeout}s",
                    "rc": -1, "ms": timeout * 1000, "code_hash": chash}
        truncated = False
        if out and len(out) > MAX_OUTPUT_BYTES:   # SEC-003: bound captured output
            out, truncated = out[:MAX_OUTPUT_BYTES] + _TRUNC, True
        return {
            "ok": proc.returncode == 0,
            "stdout": out.strip(),
            "stderr": err.strip()[:1000],
            "rc": proc.returncode,
            "ms": round((time.time() - t0) * 1000, 1),
            "code_hash": chash,
            "truncated": truncated,
        }
    finally:
        if proc and proc.poll() is None:
            _kill_tree(proc)
        shutil.rmtree(workdir, ignore_errors=True)


def run_chain(steps: list, snapshot: dict = None) -> dict:
    """
    Execute a chain of PoT steps. Each item: {"name": str, "code": str}.
    stdout of step N becomes stdin of step N+1. Records into snapshot checklist.
    """
    snapshot = snapshot or {"objective": "pot_chain", "milestones": [], "checklist": {}}
    carry = ""
    for i, step in enumerate(steps):
        r = run_step(step["code"], stdin_data=carry)
        snapshot["checklist"][step["name"]] = {"ok": r["ok"], "out": r["stdout"][:200], "ms": r["ms"]}
        if r["ok"]:
            snapshot["milestones"].append(f"STEP {i+1} '{step['name']}': ok ({r['ms']}ms)")
            carry = r["stdout"]  # chain: output -> next input
        else:
            snapshot["milestones"].append(f"STEP {i+1} '{step['name']}': FAILED — chain stopped")
            snapshot["checklist"][step["name"]]["stderr"] = r["stderr"]
            return {"ok": False, "failed_at": step["name"], "snapshot": snapshot}
    return {"ok": True, "final_output": carry, "snapshot": snapshot}


def run_parallel(programs: dict, timeout: int = 20) -> dict:
    """
    Run independent PoT programs in parallel (isolated subprocesses).
    Use ONLY when each program is slow/independent — for fast programs the
    ThreadPool overhead exceeds the gain (measured ~0.95x on trivial work).
    """
    def _r(item):
        name, code = item
        res = run_step(code, timeout=timeout)
        res["name"] = name
        return res
    with ThreadPoolExecutor(max_workers=min(4, len(programs))) as ex:
        return {r["name"]: r for r in ex.map(_r, programs.items())}


if __name__ == "__main__":
    # self-test / demo
    demo = [
        {"name": "sum_1_to_100", "code": "print(sum(range(1,101)))"},
        {"name": "square_it", "code": "n=int(input()); print(n*n)"},
    ]
    out = run_chain(demo)
    print(json.dumps(out, indent=2))
