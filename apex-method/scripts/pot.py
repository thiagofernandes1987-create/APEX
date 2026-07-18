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
import subprocess, sys, json, time, hashlib
from concurrent.futures import ThreadPoolExecutor


def run_step(code: str, stdin_data: str = "", timeout: int = 20) -> dict:
    """Run one PoT step in an isolated subprocess. Returns a result dict."""
    t0 = time.time()
    try:
        p = subprocess.run(
            [sys.executable, "-c", code],
            input=stdin_data, capture_output=True, text=True, timeout=timeout,
        )
        return {
            "ok": p.returncode == 0,
            "stdout": p.stdout.strip(),
            "stderr": p.stderr.strip()[:1000],
            "rc": p.returncode,
            "ms": round((time.time() - t0) * 1000, 1),
            "code_hash": hashlib.sha256(code.encode()).hexdigest()[:8],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "stdout": "", "stderr": f"timeout>{timeout}s",
                "rc": -1, "ms": timeout * 1000, "code_hash": hashlib.sha256(code.encode()).hexdigest()[:8]}


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
