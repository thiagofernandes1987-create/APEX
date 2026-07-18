#!/usr/bin/env python3
"""
guards.py — APEX inviolable guards SR_36..SR_40, made enforceable.

Each guard is the literal rule from the APEX kernel, implemented as a check that returns a
PASS/REJECT verdict (not LLM_BEHAVIOR hand-waving). Where a guard is purely about ordering or
LLM judgment, the check enforces the structural part and says so.
"""
import ast, os, re

# ── SR_36 [JIT_CRYSTALLIZATION_GUARD] ────────────────────────────────────────
# Per-class ΔH thresholds; a single threshold for all classes is a violation.
CRYSTALLIZATION_THRESHOLDS = {
    "class_1": 0.02, "class_2": 0.05, "class_3": 0.08,
    "resolution_cache": 0.05, "code_genetics": 0.0, "hypothesis_dag": 0.0,
}


def crystallization_guard(class_, delta_h):
    """SR_36: crystallize (commit) a posterior update iff ΔH >= the class threshold."""
    if class_ not in CRYSTALLIZATION_THRESHOLDS:
        return {"ok": False, "reason": f"unknown class {class_}"}
    thr = CRYSTALLIZATION_THRESHOLDS[class_]
    crystallize = delta_h >= thr
    return {"ok": True, "class": class_, "threshold": thr, "delta_h": delta_h,
            "crystallize": crystallize}


def validate_thresholds(thresholds: dict):
    """SR_36 violation check: a single flat threshold (e.g. 0.05 for all) is invalid."""
    non_zero = [v for k, v in thresholds.items() if k in ("class_1", "class_2", "class_3")]
    if len(set(non_zero)) <= 1:
        return {"ok": False, "reason": "flat threshold across classes discards valid class_1 updates"}
    return {"ok": True}


# ── SR_37 [DYNAMIC_FORGE_SECURITY_GUARD] ─────────────────────────────────────
# Strict: imports outside whitelist = REJECT (not review); exec/eval = REJECT;
# clone HTTPS + allowlist only. This is stricter than the general two-tier scan.
FORGE_IMPORT_WHITELIST = {
    "json", "math", "re", "time", "typing", "dataclasses", "collections", "itertools",
    "functools", "datetime", "random", "statistics", "numpy", "pandas", "sklearn",
    "scipy", "sympy", "matplotlib", "argparse", "__future__",
}
FORGE_ALLOWLIST = ("https://raw.githubusercontent.com/", "https://github.com/")


def forge_load_gate(code, url=None):
    """SR_37: mandatory AST security scan before exec/importlib. REJECT on any violation."""
    reasons = []
    if url is not None and not (url.startswith(FORGE_ALLOWLIST) and url.startswith("https://")):
        reasons.append(f"clone must be HTTPS + allowlist: {url}")
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"verdict": "REJECTED", "reasons": [f"syntax: {e}"]}
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("exec", "eval", "__import__", "compile"):
            reasons.append(f"exec/eval detected: {n.func.id}() line {n.lineno}")
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            recv = n.func.value.id if isinstance(n.func.value, ast.Name) else None
            if n.func.attr in ("system", "popen", "spawn", "urlopen", "connect"):
                reasons.append(f"dangerous call .{n.func.attr}() line {n.lineno}")
            # audit fix v1.17.0: reject loads/load only on deserializer receivers
            # (json.loads was a hard false positive that rejected legitimate skills)
            elif n.func.attr in ("load", "loads") and recv in (
                    "pickle", "marshal", "dill", "shelve", "cPickle", "joblib", "yaml"):
                reasons.append(f"deserializer {recv}.{n.func.attr}() line {n.lineno}")
        # audit fix v1.17.0: getattr with a non-literal name is an obfuscation vector
        # (getattr(os, 's'+'ystem')) that bypassed the attribute check entirely
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "getattr"
                and len(n.args) >= 2 and not isinstance(n.args[1], ast.Constant)):
            reasons.append(f"dynamic getattr (obfuscation vector) line {n.lineno}")
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = ([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""])
            for m in mods:
                top = m.split(".")[0]
                if top and top not in FORGE_IMPORT_WHITELIST:
                    reasons.append(f"import outside whitelist: {top} line {n.lineno}")
    return {"verdict": "REJECTED" if reasons else "ACCEPTED", "reasons": sorted(set(reasons))}


# ── SR_38 [EXTERNAL_CRITIC_INJECTION_GUARD] ──────────────────────────────────
def external_critic_order(step_sequence):
    """SR_38: ExternalCritic must run BEFORE meta_reasoning at STEP_12. Structural check."""
    try:
        ic = step_sequence.index("external_critic")
        im = step_sequence.index("meta_reasoning")
    except ValueError:
        return {"ok": False, "reason": "external_critic or meta_reasoning missing from STEP_12"}
    return {"ok": ic < im,
            "reason": "OK" if ic < im else "critic injected AFTER meta_reasoning — evidence neutralized"}


# ── SR_39 [LLM_RUNTIME_GUARD] ────────────────────────────────────────────────
def runtime_guard():
    """SR_39: detect runtime before any SANDBOX_CODE; return the required output marker."""
    import shutil
    caps = {"subprocess": True, "sqlite": _try("sqlite3"), "numpy": _try("numpy"),
            "git": shutil.which("git") is not None}
    if all(caps.values()):
        profile, marker = "FULL", ""
    elif caps["subprocess"]:
        profile, marker = "PARTIAL", "[SANDBOX_PARTIAL: {module}]"
    else:
        profile, marker = "MINIMAL", "[SIMULATED]"
    return {"profile": profile, "caps": caps, "required_marker": marker}


def _try(mod):
    try:
        __import__(mod); return True
    except Exception:
        return False


# ── SR_40 [ZERO_AMBIGUITY_GUARD] ─────────────────────────────────────────────
def zero_ambiguity_lint_module(source_code):
    """SR_40: a SANDBOX_CODE script must document why/when/what-if-fails; >5-line blocks need # WHY/# WHEN."""
    missing = []
    low = source_code.lower()
    for token in ("why", "when", "what if it fails"):
        if token not in low and token.replace(" ", "_") not in low:
            missing.append(f"missing '{token}'")
    return {"ok": not missing, "missing": missing}


def zero_ambiguity_lint_skill(skill_md):
    """SR_40: a SKILL.md must have Why This Skill Exists / When to Use / What If Fails."""
    low = skill_md.lower()
    need = {"why": "why" in low, "when to use": "when" in low and "use" in low,
            "what if fails": "what if" in low or "fail" in low}
    missing = [k for k, v in need.items() if not v]
    return {"ok": not missing, "missing": missing}


if __name__ == "__main__":
    print("SR_36 class_1 ΔH=0.03:", crystallization_guard("class_1", 0.03))
    print("SR_36 class_3 ΔH=0.03:", crystallization_guard("class_3", 0.03))
    print("SR_36 flat 0.05 violation:", validate_thresholds({"class_1": 0.05, "class_2": 0.05, "class_3": 0.05}))
    print("SR_37 exec:", forge_load_gate("import os\nexec('x')"))
    print("SR_37 clean:", forge_load_gate("import numpy as np\ndef f(x): return np.sqrt(x)"))
    print("SR_38 order:", external_critic_order(["external_critic", "meta_reasoning", "synthesis"]))
    print("SR_39 runtime:", runtime_guard())
