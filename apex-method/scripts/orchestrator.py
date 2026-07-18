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
    # v1.49 dogfooding: SUFIXOS PT também ("2+2 é quanto?" caía no ramo factual com answer=None
    # e o cálculo real se perdia) — remove prefixos E sufixos interrogativos antes do parse.
    core = t.rstrip("=? ").lower()
    for pat in ("what is", "how much is", "quanto é", "quanto e", "quanto dá", "quanto da",
                "é quanto", "e quanto", "dá quanto", "da quanto", "calcule", "calculate"):
        core = core.replace(pat, " ")
    core = core.strip()
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
# Bilingual (EN + PT) keywords: the old EN-only map silently mislabelled Portuguese
# tasks (e.g. "reserva de caixa / burn / runway" classified only as engineering).
DISCIPLINE_KEYWORDS = {
    "engineering": ["code", "api", "build", "refactor", "architecture", "backend", "system",
                    "código", "codigo", "arquitetura", "sistema", "programação", "programacao"],
    "frontend": ["ui", "ux", "frontend", "react", "component", "design",
                 "interface", "componente", "front-end", "usuário", "usuario"],
    "security": ["security", "vulnerability", "audit", "threat", "taint", "cve", "exploit",
                 "segurança", "seguranca", "vulnerabilidade", "auditoria", "ameaça", "ameaca"],
    "data-ai": ["model", "ml", "data", "train", "embedding", "recommender", "pipeline",
                "modelo", "dados", "treinar", "aprendizado", "recomendação", "recomendacao"],
    "finance": ["valuation", "portfolio", "trading", "risk", "cash flow", "option", "backtest",
                "portfólio", "portfolio", "risco", "caixa", "runway", "burn", "investimento",
                "financeiro", "fluxo de caixa", "reserva", "orçamento", "orcamento"],
    "math": ["prove", "proof", "integral", "derivative", "equation", "algebra",
             "prova", "provar", "derivada", "equação", "equacao", "álgebra", "algebra"],
    "science": ["physics", "simulation", "ode", "pde", "monte carlo", "annealing", "hmc",
                "statistical", "navier", "stokes", "turbulência", "turbulencia", "turbulence",
                "fluido", "fluid", "reynolds", "viscosidade", "física", "fisica", "simulação",
                "simulacao", "estatística", "estatistica", "dinâmica", "dinamica", "depleção",
                "deplecao"],
    "legal": ["contract", "compliance", "regulation", "clause", "liability",
              "contrato", "conformidade", "regulação", "regulacao", "cláusula", "clausula"],
    "healthcare": ["clinical", "patient", "diagnosis", "medical", "treatment",
                   "clínico", "clinico", "paciente", "diagnóstico", "diagnostico", "médico", "medico"],
}
# canonical one-line description per discipline — used by the semantic fallback so a task
# with no keyword hit is still routed by meaning (char-n-gram, language-robust), not dumped
# into "engineering" by default.
_DISCIPLINE_GLOSS = {
    "engineering": "software engineering code api backend architecture system programação",
    "frontend": "frontend ui ux interface design react component usuário",
    "security": "security vulnerability audit threat exploit segurança auditoria",
    "data-ai": "machine learning data model training ai dados modelo",
    "finance": "finance valuation portfolio risk cash flow runway burn financeiro caixa risco",
    "math": "mathematics proof integral derivative equation algebra prova equação",
    "science": "physics simulation dynamics statistical monte carlo física simulação dinâmica",
    "legal": "legal contract compliance regulation clause contrato conformidade",
    "healthcare": "healthcare clinical patient diagnosis medical clínico paciente médico",
}


def dissect(task, semantic_floor=0.06):
    """Split a task into the disciplines it touches (multi-discipline = hard problem).
    Keyword pass first (bilingual); if it finds nothing, a char-n-gram semantic pass
    (language-robust) picks the closest discipline instead of defaulting to engineering."""
    tl = task.lower()
    def has(kw):
        # word-boundary match so short keywords (ui, ml, ux) don't match inside words (b-ui-ld)
        return re.search(r"\b" + re.escape(kw) + r"\b", tl) is not None
    hits = [d for d, kws in DISCIPLINE_KEYWORDS.items() if any(has(k) for k in kws)]
    if hits:
        return hits
    # AUD-G2: canonical-facet fallback (taxonomy.py) — the language-independent classifier was
    # shipped in v1.41 but NEVER called by anything (orphan module). It maps PT/EN text to the
    # SAME canonical English facets, so it runs before the char-n-gram similarity pass.
    try:
        import taxonomy
        _FACET2DISC = {"software": "engineering", "mathematics": "math", "security": "security",
                       "finance": "finance", "data-ai": "data-ai", "legal": "legal",
                       "healthcare": "healthcare", "science": "science"}
        c = taxonomy.classify(task)
        facet_hits = []
        if c["domain"] in _FACET2DISC:
            facet_hits.append(_FACET2DISC[c["domain"]])
        if c["subdomain"] == "frontend" and "frontend" not in facet_hits:
            facet_hits.append("frontend")
        if facet_hits:
            return facet_hits
    except Exception:
        pass
    # semantic fallback (no keyword/facet hit): rank disciplines by char-n-gram similarity
    try:
        from _tfidf import semantic_rank
        labels = list(_DISCIPLINE_GLOSS)
        sims, _used = semantic_rank(task, [_DISCIPLINE_GLOSS[d] for d in labels], backend="char")
        ranked = [(labels[i], sims[i]) for i in range(len(labels))]
        best = [d for d, s in sorted(ranked, key=lambda x: -x[1]) if s >= semantic_floor]
        if best:
            return best[:2]  # top disciplines above the floor
    except Exception:
        pass
    return ["engineering"]  # last-resort default


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


# ── KERNEL CHECKLIST + GATE (RT-22: the pipeline is a boolean contract, not a suggestion) ────
# Every kernel step has an OWNER: "code" steps are executed by run() itself and marked done with
# evidence; "llm" steps are the passagem de bastão — run() hands the LLM the EXACT call to make.
# gate() refuses to declare the run complete until every step is True: incomplete -> RETURN_TO_LLM
# with the missing steps, so the LLM cannot silently skip validations.
KERNEL_STEPS = [
    ("TRIAGE", "code"), ("DISSECT", "code"), ("RESOLVE_SPECIALISTS", "code"),
    ("MODE", "code"), ("PHASE_PLAN", "code"),
    ("SPAWN_AGENTS", "llm"), ("RUN_STANCES", "llm"), ("BARRIER_MERGE", "llm"),
    ("VERIFY", "llm"), ("PMI_CONVERGE", "code"), ("SNAPSHOT", "code"), ("PAGE_OUT", "llm"),
]


def new_checklist():
    return [{"step": s, "owner": o, "done": False, "evidence": None} for s, o in KERNEL_STEPS]


def complete_step(checklist, step, evidence=""):
    """Mark one kernel step done WITH evidence (the baton comes back from the LLM here)."""
    for item in checklist:
        if item["step"] == step:
            item["done"], item["evidence"] = True, str(evidence)[:200]
            return checklist
    return checklist


def gate(checklist):
    """The boolean gate: PASS only when EVERY step is done. Otherwise RETURN_TO_LLM naming the
    missing steps + who owns each — the run is NOT complete until this gate passes."""
    missing = [{"step": i["step"], "owner": i["owner"]} for i in checklist if not i["done"]]
    return {"pass": not missing, "missing": missing,
            "action": ("COMPLETE" if not missing else
                       "RETURN_TO_LLM — execute the missing steps (llm-owned: make the stated "
                       "call, then complete_step(checklist, STEP, evidence)); re-run gate() "
                       "until it passes")}


# ── FULL FLOW ─────────────────────────────────────────────────────────────────
def run(task, candidates=None, snapshot=None):
    """Public entry — NEVER raises. On any unexpected failure it returns a degraded result so the
    LLM gets a safe fallback instead of a crash (error handling contract)."""
    try:
        return _run(task, candidates, snapshot)
    except Exception as e:
        # the handler itself must never crash: coerce task to str (int/dict/None are all valid inputs)
        return {"path": "ERROR_DEGRADED", "mode": "STANDARD",
                "error": f"{type(e).__name__}: {str(e)[:140]}", "task": str(task)[:120],
                "note": "pipeline failed safely — answer directly, flag the uncertainty, do not loop"}


def _run(task, candidates=None, snapshot=None):
    # TRIAGE IS THE ENTRY GATE (v1.36): it runs FIRST and decides both the SKIP (a trivial task ->
    # EXPRESS, token economy) and the escalation floor (hard problem or low MCFE reliability -> DEEP+),
    # so both happen automatically without a manual call. It wraps express_check internally; if
    # execution_policy is unavailable, we fall back to the original express_check gate.
    tri, ep, escalate_discovery = None, None, False
    try:
        import execution_policy as ep
        tri = ep.triage(task)
    except Exception:
        ep = None
    if tri is not None and tri.get("skip_pipeline"):
        exp = tri.get("express") or express_check(task) or {"mode": "EXPRESS", "answer": None,
                                                             "reason": "trivial"}
        return {"path": "EXPRESS", **exp,
                "triage": {"mode": tri["mode"], "reason": tri.get("reason")}}
    if tri is None:                                    # execution_policy missing -> original gate
        ex = express_check(task)
        if ex:
            return {"path": "EXPRESS", **ex}
    disciplines = dissect(task)
    specialists = assign_specialists(task, disciplines)
    auto_mode = "SCIENTIFIC" if any(d in disciplines for d in ("science", "math")) else \
                "DEEP" if len(disciplines) > 1 else "STANDARD"
    # triage (already computed above) sets the escalation FLOOR — escalate only, never downgrade a
    # discipline-driven mode: take the HIGHER of the discipline-mode and the triage-mode.
    if tri is not None:
        try:
            auto_mode = ep._bump(auto_mode, tri["mode"])
            escalate_discovery = tri.get("escalate_discovery", False)
        except Exception:
            pass
    # honour the user's preferred/default modes from config (menu.py sets them); never
    # silently downgrade — resolve_mode snaps up to the nearest preferred mode.
    try:
        import config
        mode = config.resolve_mode(auto_mode)
    except Exception:
        mode = auto_mode
    # audit fix v1.17.0: wire mental_interpreter (was documented in the flow but never called)
    import mental_interpreter
    phase_plan = mental_interpreter.plan_phases(mode, fractal_depth=len(disciplines))
    result = {"path": "FULL_PIPELINE", "mode": mode, "disciplines": disciplines,
              "specialists": specialists, "phase_plan": phase_plan,
              "escalate_discovery": escalate_discovery}
    # ── RT-22: the kernel checklist — code-owned steps are DONE here with evidence; llm-owned
    # steps carry the exact next call (passagem de bastão). gate() blocks completion until all True.
    ck = new_checklist()
    complete_step(ck, "TRIAGE", f"triage mode={tri['mode'] if tri else 'n/a'}")
    complete_step(ck, "DISSECT", f"disciplines={disciplines}")
    complete_step(ck, "RESOLVE_SPECIALISTS", f"{len(specialists)} disciplines resolved via gravity")
    complete_step(ck, "MODE", f"mode={mode}")
    complete_step(ck, "PHASE_PLAN", f"phases={phase_plan['phases']} n_final={phase_plan['n_final']}")
    llm_actions = {
        "SPAWN_AGENTS": ("concurrent_executor.subagent_manifest(task, mode) -> spawn each entry "
                         "(spec-based, refuse spawn_ready=False) as a real Agent subagent"),
        "RUN_STANCES": ("collect each subagent's JSON; for numeric work also run "
                        "concurrent_executor.run_stances(task, stances, mode)"),
        "BARRIER_MERGE": ("concurrent_executor.evaluate_hypotheses(task, hypotheses, mode, "
                          "subagent_hypotheses=[...]) — barrier + entropy merge + directors"),
        "VERIFY": ("uco_gate.gate on generated code; verify.verify_identity on formal claims; "
                   "verification_gate.route for risky hypotheses"),
        "PAGE_OUT": ("swap_store.page_out(session_id, memory_db, snapshot) at session end; "
                     "upload drive_manifest; print the log"),
    }
    try:
        import swap_store as _ss
        if not _ss.persist_due(mode):
            complete_step(ck, "PAGE_OUT", f"n/a — mode {mode} is ephemeral by design")
            llm_actions.pop("PAGE_OUT", None)
        # v1.44 plug-and-play: the symmetric twin of persist_due — if the swap holds state this
        # machine never paged in (habits, trained agents, grants, learning), say so AT ENTRY.
        rd = _ss.resume_due()
        if rd.get("due"):
            result["resume_due"] = rd
    except Exception:
        pass
    # v1.44 (author's thesis: context beats prompt): every FULL_PIPELINE run starts with the
    # runtime's VALIDATED experience — vaccines, memory, proven/demoted, rag pointers — so a
    # future instance never reasons cold. Bounded; empty when the stores are empty (honest).
    try:
        import agent_spawn as _as
        budget = 1200
        try:                                    # DSM optimization: context sized per mode
            import pipeline_dsm
            budget = pipeline_dsm.context_budget(mode)
        except Exception:
            pass
        if budget > 0:
            cp = _as.context_pack(task, budget_chars=budget)
            if cp.get("rendered"):
                result["context_pack"] = cp
    except Exception:
        pass
    result["kernel_checklist"] = ck
    result["llm_actions"] = llm_actions
    # PERSISTENCE TRIGGER (v1.39): heavy modes MUST page out at session end. Signal it here so the
    # LLM cannot forget — SKILL.md makes acting on `persist_due` mandatory before ending the session.
    try:
        import swap_store
        if swap_store.persist_due(mode):
            result["persist_due"] = {"due": True, "mode": mode,
                "directive": "at session end call swap_store.page_out(session_id, memory_db, snapshot) "
                             "and upload its drive_manifest to APEX/swap/<session>/ (or the chosen "
                             "backend); print the returned log so the user sees the page-out"}
    except Exception:
        pass
    if candidates:
        result["pmi_decision"] = pmi_converge(candidates)
        complete_step(ck, "PMI_CONVERGE", f"reliability={result['pmi_decision'].get('reliability')}")
    else:
        llm_actions["PMI_CONVERGE"] = ("after BARRIER_MERGE, re-call orchestrator.run(task, "
                                       "candidates=[...merged hypotheses...]) or "
                                       "pmi_converge(candidates) directly; then complete_step")
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
        complete_step(ck, "SNAPSHOT", f"{len(snapshot['findings'])} findings recorded")
    else:
        llm_actions["SNAPSHOT"] = ("pass snapshot=snapshot.new_snapshot(task, mode) into run(), "
                                   "or record findings via snapshot.add_finding; then complete_step")
    # v1.47 (OPP-99): measure the REAL payload each code step produced (chars/4 proxy, declared)
    # so pipeline_dsm's per-mode flow calibrates itself with data instead of estimates.
    try:
        import token_tracker as tt
        rnd = tt.start_round(mode, str(task))
        tt.record(rnd, "TRIAGE", tri or {})
        tt.record(rnd, "DISSECT", disciplines)
        tt.record(rnd, "RESOLVE_SPECIALISTS", specialists)
        tt.record(rnd, "PHASE_PLAN", phase_plan)
        if result.get("context_pack"):
            tt.record(rnd, "CONTEXT_PACK", result["context_pack"].get("rendered", ""))
        if result.get("pmi_decision"):
            tt.record(rnd, "PMI_CONVERGE", result["pmi_decision"])
        if snapshot is not None:
            tt.record(rnd, "SNAPSHOT", snapshot)
        result["tokens_measured"] = tt.end_round(rnd)
    except Exception:
        pass
    # the gate is computed LAST so it reflects everything run() itself completed
    result["gate"] = gate(ck)
    return result


if __name__ == "__main__":
    task = " ".join(sys.argv[1:]) or "2+2"
    print(json.dumps(run(task), indent=2, ensure_ascii=False))
