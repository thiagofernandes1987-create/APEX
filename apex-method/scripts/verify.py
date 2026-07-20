#!/usr/bin/env python3
"""
verify.py — Symbolic formal verifier (APEX C8 / SCIENTIFIC).

WHY THIS EXISTS:
  Lets the LLM prove/refute an algebraic or calculus claim exactly, instead of
  asserting it. Crucially, it marks CONJECTURE when out of scope rather than
  inventing certainty (APEX rule: no formal notation without evidence).

WHEN TO USE:
  Any identity, derivative, or integral claim that can be checked symbolically.

RETURNS: [FORMAL_VERIFIED] / [FORMAL_REFUTED] / [CONJECTURA_FORMAL].

WHAT IF IT FAILS: Out-of-scope claims return [CONJECTURA_FORMAL] rather than inventing certainty.
"""
import sys, json, hashlib
try:
    import sympy as sp
except ImportError:      # audit fix v1.17.0: degrade to CONJECTURE instead of crashing
    sp = None

# Opt #2 (token economy): memoize by (lhs, rhs). verify_identity is DETERMINISTIC (symbolic), so an
# identical claim re-checked across rounds returns the cached verdict instead of re-proving.
_VERIFY_CACHE = {}


def clear_cache():
    _VERIFY_CACHE.clear()


def verify_identity(lhs: str, rhs: str) -> dict:
    _key = hashlib.sha256(f"{lhs}\x00{rhs}".encode("utf-8")).hexdigest()
    if _key in _VERIFY_CACHE:
        return dict(_VERIFY_CACHE[_key], cached=True)
    if sp is None:
        return {"tag": "CONJECTURA_FORMAL", "residual": "sympy not installed — cannot verify"}
    try:
        r = sp.simplify(sp.sympify(lhs) - sp.sympify(rhs))
        tag = "FORMAL_VERIFIED" if r == 0 else "FORMAL_REFUTED"
        result = {"tag": tag, "residual": str(r)}
        _VERIFY_CACHE[_key] = result
        return result
    except Exception as e:
        return {"tag": "CONJECTURA_FORMAL", "residual": f"out of scope: {str(e)[:80]}"}

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        print(json.dumps(verify_identity(sys.argv[1], sys.argv[2]), indent=2))
    else:
        print(json.dumps(verify_identity("(x+1)**2", "x**2+2*x+1"), indent=2))
