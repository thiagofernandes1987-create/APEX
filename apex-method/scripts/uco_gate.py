#!/usr/bin/env python3
"""
uco_gate.py — Fast objective quality gate for generated code (APEX SR_33).

WHY THIS EXISTS:
  Before running LLM-generated PoT code, check it with a DETERMINISTIC judge that
  does not depend on the LLM's opinion of its own code (breaks circular self-eval).

WHEN TO USE:
  On every PoT program before subprocess execution in DEEP/SCIENTIFIC.

WHAT IT DOES:
  Uses the UCO optimizer if available; otherwise a lightweight AST fallback that
  flags: while-True without break, bare except, obvious dead code after return.

WHAT IF IT FAILS:
  Returns status REJECTED with reasons; caller should auto-fix and re-gate, or
  fall back to inline reasoning with a lowered confidence cap.
"""
import ast, sys, json

def _fallback_scan(code):
    reasons = []
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"status": "REJECTED", "reasons": [f"syntax: {e}"], "engine": "fallback"}
    for node in ast.walk(tree):
        if isinstance(node, ast.While) and isinstance(node.test, ast.Constant) and node.test.value is True:
            has_break = any(isinstance(n, ast.Break) for n in ast.walk(node))
            if not has_break:
                reasons.append(f"while True without break (line {node.lineno})")
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            reasons.append(f"bare except (line {node.lineno})")
    # dead code after return in a function body
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for i, stmt in enumerate(fn.body[:-1]):
            if isinstance(stmt, ast.Return):
                reasons.append(f"dead code after return in {fn.name} (line {fn.body[i+1].lineno})")
                break
    return {"status": "PASS" if not reasons else "REJECTED", "reasons": reasons, "engine": "fallback"}

def gate(code, uco_path=None):
    """Try UCO; fall back to AST scan. Returns {status, reasons, metrics?, engine}."""
    try:
        if uco_path:
            sys.path.insert(0, uco_path)
        from universal_code_optimizer_v4 import UniversalCodeOptimizer
        m = UniversalCodeOptimizer(seed=42).analyze(code, language_hint="python").metrics
        risky = m.infinite_loop_risk > 0.3 or m.syntactic_dead_code > 0 or m.hamiltonian > 5.5
        return {"status": "REJECTED" if risky else "PASS",
                "metrics": {"hamiltonian": round(m.hamiltonian, 2),
                            "loop_risk": round(m.infinite_loop_risk, 2),
                            "cyclomatic": m.cyclomatic_complexity,
                            "dead_code": m.syntactic_dead_code},
                "reasons": [] if not risky else ["UCO flagged structural risk"],
                "engine": "UCO"}
    except Exception:
        return _fallback_scan(code)

if __name__ == "__main__":
    code = sys.stdin.read() if not sys.stdin.isatty() else "def f(n):\n while True:\n  n+=1"
    print(json.dumps(gate(code), indent=2))
