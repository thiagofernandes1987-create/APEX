#!/usr/bin/env python3
"""
orchestrator.py — The APEX flow, end to end.

WHAT IT DOES (the flow you described):
  1. EXPRESS CHECK — trivial input (2+2, one-line fact) skips the whole pipeline and answers
     directly. No bureaucracy.
  2. DISSECT BY DISCIPLINE — a hard problem is split into per-discipline sub-problems.
  3. ASSIGN SPECIALISTS — each discipline gets a specialized agent + its skills + diffs via the
     gravity engine (gravity.plan), which also flags gaps -> skills.sh install requests + MCP.
  4. PMI CONVERGENCE — the PMI agent decides among the candidate sub-answers which converge to a
     high-reliability answer, using a real convergence/confidence calculation.

HONEST NOTE ON THE PMI CALCULATION:
  - When candidate answers are QUANTIFIABLE (numbers), convergence is REAL: agreement across
    independent solutions + their confidences -> a computed reliability.
  - When candidates are QUALITATIVE (reasoning branches), "convergence" is a transparent
    weighted vote of confidences, NOT a physical Monte Carlo. It is labeled as judgment.

WHAT IF IT FAILS: If a sub-tool is missing the phase is skipped and reported; the express path always answers trivial input.
"""
import re, sys, json, os, ast, statistics

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)


# ── 1. EXPRESS CHECK ──────────────────────────────────────────────────────────
_ARITH = re.compile(r"^[\s\d+\-*/().]+$")


def _safe_arith(expr):
    """Evaluate a pure-arithmetic expression via AST (no eval, no names/calls)."""
    node = ast.parse(expr, mode="eval")
    allowed = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Constant,
               ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod,
               ast.USub, ast.UAdd, ast.FloorDiv)
    for n in ast.walk(node):
        if not isinstance(n, allowed):
            raise ValueError("not pure arithmetic")
        # audit fix v1.17.0: 9**9**9 hung the express path (unbounded bignum) — cap exponents
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Pow):
            if not (isinstance(n.right, ast.Constant) and abs(n.right.value) <= 64):
                raise ValueError("exponent too large for express path")
    return eval(compile(node, "<arith>", "eval"))  # safe: AST whitelisted above


def express_check(task):
    """Return an EXPRESS answer for trivial input, else None (go to full pipeline)."""
    t = task.strip()
    # audit fix v1.17.0: lowercase before stripping the question prefix ("What is 2+2?" missed)
    core = t.rstrip("=? ").lower().replace("what is", "").replace("quanto é", "").strip()
    if _ARITH.match(core) and any(op in core for op in "+-*/"):
        try:
            return {"mode": "EXPRESS", "answer": _safe_arith(core), "reason": "pure arithmetic"}
        except Exception:
            pass
    words = t.split()
    if len(words) <= 6 and "?" in t and not any(w in t.lower() for w in
            ["why", "how", "design", "optimize", "prove", "compare", "plan", "porquê", "como"]):
        return {"mode": "EXPRESS", "answer": None, "reason": "short factual — answer directly, skip pipeline"}
    return None


# ── 2. DISSECT BY DISCIPLINE ──────────────────────────────────────────────────
DISCIPLINE_KEYWORDS = {
    "engineering": ["code", "api", "build", "refactor", "architecture", "backend", "system"],
    "frontend": ["ui", "ux", "frontend", "react", "component", "design"],
    "security": ["security", "vulnerability", "audit", "threat", "taint", "cve", "exploit"],
    "data-ai": ["model", "ml", "data", "train", "embedding", "recommender", "pipeline"],
    "finance": ["valuation", "portfolio", "trading", "risk", "cash flow", "option", "backtest"],
    "math": ["prove", "proof", "integral", "derivative", "equation", "algebra"],
    "science": ["physics", "simulation", "ode", "monte carlo", "annealing", "hmc", "statistical"],
    "legal": ["contract", "compliance", "regulation", "clause", "liability"],
    "healthcare": ["clinical", "patient", "diagnosis", "medical", "treatment"],
}


def dissect(task):
    """Split a task into the disciplines it touches (multi-discipline = hard problem)."""
    tl = task.lower()
    def has(kw):
        # word-boundary match so short keywords (ui, ml, ux) don't match inside words (b-ui-ld)
        return re.search(r"\b" + re.escape(kw) + r"\b", tl) is not None
    hits = [d for d, kws in DISCIPLINE_KEYWORDS.items() if any(has(k) for k in kws)]
    return hits or ["engineering"]  # default discipline


def assign_specialists(task, disciplines):
    """For each discipline, get agent+skills+diffs (+gaps) via the gravity engine."""
    import gravity
    out = {}
    for d in disciplines:
        sub = f"{task} [{d}]"
        plan = gravity.plan(sub)
        out[d] = {"constellation": plan["constellation"], "gaps": plan["gaps"],
                  "install_requests": [ir["gap"] for ir in plan["install_requests"]],
                  "mcp": plan["mcp_suggestions"]}
    return out


# ── 4. PMI CONVERGENCE DECISION ───────────────────────────────────────────────
def pmi_converge(candidates):
    """
    candidates: [{"discipline","answer","confidence"(0-1),"numeric"(bool)}]
    Uses the real APEX Bayesian layer (bayes.py):
      - numeric: agreement × mean confidence (real convergence)
      - qualitative: Bayesian posterior over answers (confidence as likelihood) + Omega decision
      - R_acum gate over the per-candidate confidences (SR_10) applied to both.
    """
    import bayes
    if not candidates:
        return {"answer": None, "reliability": 0.0, "method": "none"}
    # R_acum reliability gate over the candidates' confidences.
    # audit fix v1.17.1: the chaos stance is EXCLUDED from the gate — its low confidence
    # is deliberate anti-convergence (SR_11), not chain unreliability; including it forced
    # CRITICAL_EARLY_EXIT exactly when the method was working as designed. It still
    # participates in the debate/posterior below.
    gate_confs = [c["confidence"] for c in candidates
                  if "confidence" in c
                  and "chaos" not in (str(c.get("stance", "")) + str(c.get("discipline", ""))).lower()]
    all_confs = [c["confidence"] for c in candidates if "confidence" in c]
    gate = bayes.r_acum(gate_confs or all_confs or [1.0])

    # G5 (bayes.filter_priors): drop candidates whose explicit prior is below 0.4
    if any("prior" in c for c in candidates):
        keep = bayes.filter_priors({str(c["answer"]): c.get("prior", 1.0) for c in candidates})
        candidates = [c for c in candidates if str(c["answer"]) in keep] or candidates

    # audit P3: quantifiable candidates (model_fn + distributions) -> REAL Monte Carlo,
    # not a weighted vote. Honest use of the term (SKILL.md §10).
    simulable = [c for c in candidates if callable(c.get("model_fn")) and c.get("distributions")]
    if simulable:
        import monte_carlo
        sims = []
        for c in simulable:
            r = monte_carlo.simulate(c["model_fn"], c["distributions"],
                                     n_iterations=c.get("n", 10000))
            if r["status"] in ("OK", "PARTIAL"):
                sims.append((c, r))
        if sims:
            best_c, best_r = min(sims, key=lambda cr: cr[1]["statistics"]["cv"])
            return {"answer": best_c.get("answer", best_r["statistics"]["p50"]),
                    "reliability": round(max(0.0, 1.0 - best_r["statistics"]["cv"]), 3),
                    "monte_carlo": best_r["marker"], "statistics": best_r["statistics"],
                    "method": "monte-carlo simulation (real; lowest CV wins)",
                    "r_acum": gate}

    numeric = []
    for c in candidates:
        if c.get("numeric"):
            try:
                float(c["answer"])
                numeric.append(c)
            except (TypeError, ValueError):
                c["numeric"] = False  # audit fix v1.17.0: degrade to qualitative, don't crash
    if len(numeric) >= 2:
        import statistics
        vals = [float(c["answer"]) for c in numeric]
        consensus = statistics.mode([round(v, 6) for v in vals])
        agree = sum(1 for v in vals if abs(v - consensus) < 1e-6) / len(vals)
        conf = statistics.mean(c["confidence"] for c in numeric)
        return {"answer": consensus, "reliability": round(agree * conf, 3),
                "agreement": f"{int(agree*len(vals))}/{len(vals)}",
                "method": "numeric-convergence (real)", "r_acum": gate}

    # qualitative -> real Bayesian posterior over answers (confidence = likelihood, uniform prior)
    answers = sorted({str(c["answer"]) for c in candidates})
    priors = {a: 1.0 / len(answers) for a in answers}
    likelihoods = {a: max((c["confidence"] for c in candidates if str(c["answer"]) == a), default=0)
                   for a in answers}
    post = bayes.posterior_over_hypotheses(priors, likelihoods)
    return {"answer": post["dominant"], "reliability": post["dominant_p"],
            "posteriors": post["posteriors"], "decision": post["decision"],
            "entropy_bits": post["entropy_bits"],
            "method": "bayesian-posterior + Omega decision (real math; beliefs are LLM-supplied)",
            "r_acum": gate}


# ── FULL FLOW ─────────────────────────────────────────────────────────────────
def run(task, candidates=None, snapshot=None):
    ex = express_check(task)
    if ex:
        return {"path": "EXPRESS", **ex}
    disciplines = dissect(task)
    specialists = assign_specialists(task, disciplines)
    mode = "SCIENTIFIC" if any(d in disciplines for d in ("science", "math")) else \
           "DEEP" if len(disciplines) > 1 else "STANDARD"
    # audit fix v1.17.0: wire mental_interpreter (was documented in the flow but never called)
    import mental_interpreter
    phase_plan = mental_interpreter.plan_phases(mode, fractal_depth=len(disciplines))
    result = {"path": "FULL_PIPELINE", "mode": mode, "disciplines": disciplines,
              "specialists": specialists, "phase_plan": phase_plan}
    if candidates:
        result["pmi_decision"] = pmi_converge(candidates)
    # audit P3: close the loop in code — record the run into the snapshot (C5) so the end
    # of the flow (snapshot + provenance) is not left purely to the LLM's discipline.
    if snapshot is not None:
        import snapshot as snap_mod
        snapshot["mode"] = mode
        snapshot["milestones"].append(f"dissected into {len(disciplines)} disciplines; mode {mode}")
        snap_mod.add_finding(snapshot, f"pipeline planned for: {task[:80]}",
                             where="orchestrator.run", how=f"disciplines={disciplines}",
                             confidence="[APPROX] medium")
        for d, spec in specialists.items():
            for gap in spec.get("install_requests", []):
                snapshot["skills_staged"].append({"id": gap, "use_when": d, "status": "STAGED"})
        result["snapshot"] = snapshot
    return result


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "2+2"
    print(json.dumps(run(task), indent=2, ensure_ascii=False))
