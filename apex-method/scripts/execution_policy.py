#!/usr/bin/env python3
"""
execution_policy.py — explicit ROUTING CONTRACT + the 3-persona dissect ENTRY.

WHY THIS EXISTS:
  The single biggest failure mode of a "cognitive runtime" is routing DISCOVERY/RESEARCH into the
  sealed PoT sandbox (no internet) — you lose skills.sh, repos, papers, MCPs by a mere
  interpretation error. This module makes the routing EXPLICIT and machine-checkable (a manifest,
  deliberately NOT a DSL — less surface for the LLM to misread), and formalizes the entry the author
  wants: on a new task, the LLM raises 3 dissect personas that break the macro into micros, run a
  SWOT per micro to name the needed agents/skills/governance/tools, resolve them
  (repo -> skills.sh -> create as a last resort), route each to the correct SURFACE, attach a
  document/layout template so nothing is generic, provision everything to the working instances, and
  collect structured feedback (need more tools / wrong persona / need a template).

THE TWO SURFACES (never conflate them):
  - subprocess      : deterministic compute in the sealed PoT sandbox. NO internet. (RK4, TF-IDF, DAG)
  - agent           : LLM reasoning/synthesis. No internet needed.
  - agent+internet  : discovery/research (skills.sh, repos, papers, MCPs) — a subagent WITH web tools.
  HARD RULE: needs_internet=True  =>  surface MUST be 'agent+internet', NEVER 'subprocess'.
  WHO PROVIDES TOOLS: always the LLM orchestrator — it discovers/vets/hands the concrete tool to the
  instance; the sandbox only RUNS already-provided deterministic code.

REUSES (does not reimplement): orchestrator.dissect / assign_specialists, gravity.plan (discovery
  URLs, staged — never auto-installs), learning.best (durable best persona), repo_bridge / skills_sh.

WHAT IF IT FAILS:
  Pure stdlib. Missing sibling engines degrade to the safe default (agent surface, native-only
  resolution). Never raises on normal input.
"""
import os
import re

import sys
sys.path.insert(0, os.path.dirname(__file__))

# ── surfaces + the routing keyword classes (bilingual EN/PT) ─────────────────────────────────
SURFACES = ("subprocess", "agent", "agent+internet")

DISCOVER_KW = {
    "search", "buscar", "busca", "discover", "descobrir", "find", "encontrar", "skill", "skills",
    "repository", "repositório", "repo", "paper", "papers", "artigo", "artigos", "mcp", "download",
    "baixar", "install", "instalar", "marketplace", "web", "online", "internet", "latest", "última",
    "atualizar", "update", "fetch", "crawl", "scrape", "google", "github", "arxiv", "benchmark",
}
COMPUTE_KW = {
    "compute", "calcular", "cálculo", "integrate", "integrar", "ode", "rk4", "euler", "matrix",
    "matriz", "simulate", "simular", "montecarlo", "optimize", "otimizar", "sort", "ordenar", "hash",
    "sha", "regex", "parse", "aggregate", "agregar", "sum", "somar", "derivative", "derivada",
    "eigen", "autovalor", "solve", "resolver", "numeric", "numérico", "statistics", "estatística",
}

# domains whose micros carry regulatory/governance weight (region-specific rules must be attached)
REGULATED_DOMAINS = {"legal", "health", "healthcare", "finance", "financial", "medical", "privacy"}
# regulation is also detected from the PROBLEM TEXT (a discipline label may hide it) — bilingual.
REGULATED_KW = {"hipaa", "gdpr", "lgpd", "healthcare", "health", "medical", "clinical", "patient",
                "legal", "law", "lei", "jurídico", "regulatory", "regulation", "regulação",
                "regulamentação", "compliance", "conformidade", "finance", "financial", "financeiro",
                "banking", "bancário", "privacy", "privacidade", "sox", "pci", "kyc", "aml", "audit"}


def _is_regulated(text, discipline):
    """Regulation applies if the discipline is regulated OR the problem text names a regime/regulator
    (region-specific rules must then be attached — the author's 'cada região tem suas regras')."""
    if (discipline or "").lower() in REGULATED_DOMAINS:
        return True
    tl = (text or "").lower()
    return any(re.search(r"\b" + re.escape(k) + r"\b", tl) for k in REGULATED_KW)


def classify_surface(subtask):
    """Return (surface, needs_internet) for a micro-task. Discovery/research -> agent+internet;
    deterministic compute -> subprocess; everything else -> agent. Bilingual, word-boundary."""
    tl = (subtask or "").lower()

    def has(kw):
        return re.search(r"\b" + re.escape(kw) + r"\b", tl) is not None
    if any(has(k) for k in DISCOVER_KW):
        return "agent+internet", True
    if any(has(k) for k in COMPUTE_KW):
        return "subprocess", False
    return "agent", False


def route(subtask, kind="auto", escalate=False):
    """The routing contract for ONE micro-task. Emits the surface, the internet flag, and who
    provides the tools — and ENFORCES the hard rule so discovery can never land in the sandbox.
    `escalate=True` (from triage: low MCFE reliability or high difficulty) pushes a plain reasoning
    task to `agent+internet` so it goes DISCOVER better tools/context — but compute stays compute
    (you never send RK4 to the internet)."""
    surface, needs_net = classify_surface(subtask)
    escalated = False
    if escalate and surface == "agent":                    # uncertain reasoning -> go discover
        surface, needs_net, escalated = "agent+internet", True, True
    if needs_net and surface != "agent+internet":          # belt-and-suspenders enforcement
        surface = "agent+internet"
    if surface == "subprocess" and needs_net:              # impossible by construction, but guard
        surface, needs_net = "agent+internet", True
    return {"subtask": subtask, "surface": surface, "needs_internet": needs_net,
            "escalated_to_discovery": escalated, "provider_of_tools": "llm-orchestrator",
            "rule": ("discovery/research runs in an internet-enabled agent (or subagent), NEVER the "
                     "sealed subprocess; the sandbox only runs already-provided deterministic code")}


# ── MCFE/difficulty triage: skip trivial (token economy) · escalate uncertain (discovery) ────
R_REPLAN = 0.50            # MCFE reliability below this -> replan/escalate to discovery (bayes R_acum)
R_EARLY_EXIT = 0.30        # below this -> early-exit/abort candidate
HARD_DIFF = 0.85           # BehavioralDifficultyEstimator: hard problem -> escalate
SIMPLE_DIFF = 0.35         # low difficulty -> stay light, save tokens
FANOUT_QUORUM = 3          # min stances kept when pruning — still a real cross-check, not a single voice


def fanout_plan(mode, prior_reliability=None, p_target=0.72, full_cap=8):
    """Adaptive fan-out (Opt #3, geodesic pruning). The expensive modes fan out to the FULL mode
    budget of stances every time. When a PRIOR reliability estimate already clears the target — a
    familiar/converged problem (e.g. the resolution-cache prior, or a first cheap round) — a NARROWER
    quorum suffices, so cut the fan-out instead of paying for the full budget. Returns
    {cap, full_cap, pruned, saved, reason}. Never drops below FANOUT_QUORUM (keeps a real cross-check).
    HONEST: prunes ONLY when reliability >= target; below target it runs the full budget unchanged."""
    full = int(full_cap) if full_cap else 8
    if prior_reliability is not None and prior_reliability >= p_target and full > FANOUT_QUORUM:
        cap = max(FANOUT_QUORUM, full // 2)
        return {"cap": cap, "full_cap": full, "pruned": cap < full, "saved": full - cap,
                "reason": f"prior reliability {round(prior_reliability,3)} >= target {p_target} — "
                          f"pruned fan-out {full}->{cap} (quorum keeps the cross-check)"}
    return {"cap": full, "full_cap": full, "pruned": False, "saved": 0,
            "reason": "no convergence prior — full fan-out"}
MODE_LADDER = ["EXPRESS", "STANDARD", "FOGGY", "DEEP", "SCIENTIFIC", "RESEARCH"]


def _bump(mode, floor):
    """Return the HIGHER of `mode` and `floor` on the ladder (never downgrades)."""
    i = max(MODE_LADDER.index(mode) if mode in MODE_LADDER else 1,
            MODE_LADDER.index(floor) if floor in MODE_LADDER else 1)
    return MODE_LADDER[i]


def _cap(mode, ceiling):
    """Return the LOWER of `mode` and `ceiling` (used to keep simple tasks light)."""
    i = min(MODE_LADDER.index(mode) if mode in MODE_LADDER else 1,
            MODE_LADDER.index(ceiling) if ceiling in MODE_LADDER else 1)
    return MODE_LADDER[i]


# ── MODE FLOOR: task classes that must NEVER skip the pipeline (min mode enforced) ───────────
# A skill the LLM can silently skip is not a skill. These classes force the pipeline: no EXPRESS
# skip, and a minimum operating mode. The user can also set a global floor via config.min_mode.
FLOOR_KEYWORDS = {
    "DEEP": {"audit", "audite", "auditar", "auditando", "auditoria", "autopsy", "autópsia",
             "autopsia", "pentest", "security", "segurança", "seguranca", "vulnerability",
             "vulnerabilidade", "vulnerabilidades", "exploit", "threat", "ameaça", "ameaças",
             "cve", "compliance", "conformidade", "hipaa", "gdpr", "lgpd", "regulatory",
             "regulação", "regulacao", "regulamentação", "regulamentacao", "sox", "pci",
             "high-stakes", "forensic", "forense", "incident", "incidente", "breach"},
}


def mode_floor(task):
    """The MINIMUM mode this task must run at (or None). Comes from (1) task-class keywords
    (audit/security/compliance never skip and run >= DEEP) and (2) the user's config.min_mode
    (a hard global floor that forces the pipeline for EVERY task). Returns the highest floor."""
    tl = (task or "").lower() if isinstance(task, str) else ""
    floor = None
    for mode, kws in FLOOR_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(k) + r"\b", tl) for k in kws):
            floor = _bump(floor or "EXPRESS", mode)
    try:
        import config
        mm = config.load().get("min_mode")
        if mm:
            floor = _bump(floor or "EXPRESS", mm)
    except Exception:
        pass
    return floor if floor and floor != "EXPRESS" else None


def triage(task, reliability=None, mode="STANDARD"):
    """Decide, BEFORE running the pipeline, whether to (a) SKIP it entirely for a trivial task
    (token economy — `orchestrator.express_check`), (b) keep it LIGHT for a low-difficulty task, or
    (c) ESCALATE mode + discovery when the problem is hard (`competence_matrix.estimate_difficulty`)
    or the MCFE reliability signal is low (bayes R_acum gate 0.50/0.30). A MODE FLOOR
    (`mode_floor`: audit/security/compliance or the user's min_mode) OVERRIDES the skip and pins a
    minimum mode — the LLM cannot skip a task that must run the pipeline. Returns the recommended
    mode + whether micros should escalate to discovery."""
    floor = mode_floor(task)
    # (a) token economy: trivial input skips — but ONLY when no floor forces the pipeline
    if floor is None:
        try:
            import orchestrator
            exp = orchestrator.express_check(task)
        except Exception:
            exp = None
        if exp:
            return {"skip_pipeline": True, "mode": "EXPRESS", "difficulty": None,
                    "reliability": reliability, "escalate_discovery": False, "express": exp,
                    "reason": f"trivial ({exp.get('reason')}) — skip pipeline, save tokens"}
    # (b/c) difficulty + reliability
    dinfo, uncertain = {"bde_score": 0.5, "uncertain": False}, False
    try:
        import competence_matrix
        dinfo = competence_matrix.estimate_difficulty(task)
    except Exception:
        pass
    diff, uncertain = dinfo.get("bde_score", 0.5), dinfo.get("uncertain", False)
    rec, escalate, reasons, need_personas = mode, False, [], False
    # UNKNOWN problem class: do NOT stay light, do NOT skip — escalate and REQUIRE the 3 dissect
    # personas to establish the real difficulty (the estimator admitted it doesn't know).
    if uncertain:
        rec, escalate, need_personas = _bump(rec, "DEEP"), True, True
        reasons.append("difficulty class UNKNOWN — escalate + the 3 dissect personas MUST establish "
                       "the real difficulty before proceeding (no silent 0.5)")
    if diff < SIMPLE_DIFF and floor is None and not uncertain:
        rec = _cap(rec, "STANDARD")
        reasons.append(f"low difficulty {diff} — light mode, save tokens")
    if diff >= HARD_DIFF:
        rec, escalate = _bump(rec, "DEEP"), True
        reasons.append(f"high difficulty {diff} — escalate + discover")
    if reliability is not None and reliability < R_REPLAN:
        rec, escalate = _bump(rec, "DEEP"), True
        reasons.append(f"MCFE reliability {reliability} < {R_REPLAN} — escalate to discovery (replan)")
    if reliability is not None and reliability < R_EARLY_EXIT:
        reasons.append(f"MCFE reliability {reliability} < {R_EARLY_EXIT} — early-exit/abort candidate")
    # MODE FLOOR wins last: a forced task class / user min_mode pins the minimum — no skip, no downgrade.
    if floor:
        rec = _bump(rec, floor)
        reasons.append(f"mode floor {floor} enforced (forced task class / min_mode) — pipeline mandatory")
    return {"skip_pipeline": False, "mode": rec, "difficulty": diff, "uncertain": uncertain,
            "reliability": reliability, "escalate_discovery": escalate, "floor": floor,
            "require_dissect_personas": need_personas or bool(floor),
            "reasons": reasons or ["nominal difficulty/reliability"]}


# ── loop guard: hard STOP conditions so the runtime NEVER spins (reads apex_llm.yaml limits) ──
def loop_guard(iteration, progress_history=None, restarts=0, reliability=None):
    """Return {stop, reason, action}. STOP when: iterations exceed the cap, restarts exceed the cap,
    reliability falls under the early-exit gate, or there is no progress for 2 rounds (stagnation).
    Limits come from llm_adapter (apex_llm.yaml) with safe defaults — a missing adapter still stops."""
    try:
        import llm_adapter
        lim = llm_adapter.limits()
    except Exception:
        lim = {"max_iterations": 8, "max_restarts": 3, "min_progress": 0.15,
               "reliability_early_exit": 0.30}
    if iteration >= lim["max_iterations"]:
        return {"stop": True, "reason": f"max_iterations {lim['max_iterations']} reached",
                "action": "return best-so-far (never loop)"}
    if restarts >= lim["max_restarts"]:
        return {"stop": True, "reason": f"max_restarts {lim['max_restarts']} reached",
                "action": "stop restarting; return best-so-far"}
    if reliability is not None and reliability < lim["reliability_early_exit"]:
        return {"stop": True, "reason": f"reliability {reliability} < early_exit "
                f"{lim['reliability_early_exit']}", "action": "EARLY_EXIT with PARTIAL"}
    ph = list(progress_history or [])
    if len(ph) >= 2 and all(p < lim["min_progress"] for p in ph[-2:]):
        return {"stop": True, "reason": f"no progress for 2 rounds (< min_progress "
                f"{lim['min_progress']})", "action": "STOP PARTIAL; do not re-attempt the same plan"}
    return {"stop": False, "reason": "within limits", "action": "continue"}


# ── the 3-persona dissect entry ──────────────────────────────────────────────────────────────
DISSECT_PERSONAS = [
    {"persona": "architect", "role": "decompose the MACRO into micro-problems; name the agents, "
                                     "skills and tools each micro needs"},
    {"persona": "analyst",   "role": "SWOT per micro; flag governance/regulation; RESOLVE tools "
                                     "(native repo -> skills.sh -> create as last resort)"},
    {"persona": "critic",    "role": "challenge each micro: wrong persona? missing tool? generic "
                                     "output? demand a concrete document/layout template"},
]

# document/layout templates so outputs are never generic (the author's requirement).
TEMPLATES = {
    "laudo": ["director", "ranking", "best", "confidence", "justificativa", "diagnostico", "sha256"],
    "decision_record": ["context", "options", "decision", "rationale", "consequences", "reversible?"],
    "spec": ["objective", "scope", "constraints", "interfaces", "acceptance_criteria", "risks(FMEA)"],
    "report": ["summary", "evidence(what/where/how/confidence)", "method", "limitations", "next"],
}


def _swot(problem, discipline):
    """A concrete SWOT scaffold the analyst persona fills (not a generic blob)."""
    return {"strengths": f"what APEX already has for {discipline}",
            "weaknesses": f"gaps/uncertainty in '{problem[:60]}'",
            "opportunities": "native skill / marketplace / new tool to acquire",
            "threats": "regulation, ambiguity, or a stuck persona"}


def _resolve_tools(subtask):
    """Resolve needed tools WITHOUT executing anything online: native repo first, then a staged
    skills.sh request, and only then 'create'. This runs at the orchestrator layer (has internet);
    it returns a PLAN, never auto-installs (H5)."""
    native, market = [], None
    try:
        import repo_bridge
        native = [{"id": h["id"], "path": h["path"]} for h in repo_bridge.search_native(subtask, k=3)]
    except Exception:
        pass
    try:
        import gravity
        plan = gravity.plan(subtask)
        market = [ir["gap"] for ir in plan.get("install_requests", [])] or None
    except Exception:
        pass
    return {"native": native, "skills_sh_request": market,
            "create_if_missing": not native and not market}


def dissect_entry(task, mode="DEEP", reliability=None):
    """THE ENTRY. First TRIAGES (skip the pipeline for a trivial task; escalate mode+discovery for a
    hard task or low MCFE reliability), then returns the plan the LLM executes: the 3 dissect personas
    to raise, the micros (each with SWOT + needed resources + resolution + ROUTING + a template +
    governance), the provisioning rule (the LLM provides the tools) and the feedback protocol.
    Reuses dissect/assign/gravity/learning/express_check — no discovery is reimplemented here."""
    tri = triage(task, reliability=reliability, mode=mode)
    if tri["skip_pipeline"]:
        # token economy: a trivial task never enters the pipeline
        return {"macro": task, "skip_pipeline": True, "triage": tri,
                "answer_directly": True, "mode": "EXPRESS"}
    mode = tri["mode"]                       # honour the escalated/capped mode
    escalate = tri["escalate_discovery"]
    try:
        import orchestrator
        disciplines = orchestrator.dissect(task)
    except Exception:
        disciplines = ["engineering"]
    micros = []
    for d in disciplines:
        sub = f"{task} [{d}]"
        # needed specialists via the existing gravity constellation (staged, offline-safe)
        constellation, gaps = {}, []
        try:
            import orchestrator
            spec = orchestrator.assign_specialists(task, [d]).get(d, {})
            constellation, gaps = spec.get("constellation", {}), spec.get("gaps", [])
        except Exception:
            pass
        # durable best persona for this domain (Op-P3 learning), else the constellation's agent
        best_persona = None
        try:
            import learning
            b = learning.best("persona", d, k=1)
            best_persona = b[0]["subject"] if b else None
        except Exception:
            pass
        routing = route(sub, escalate=escalate)
        regulated = _is_regulated(task, d)
        micros.append({
            "problem": sub, "discipline": d,
            "swot": _swot(task, d),
            "needed": {"agent": best_persona or constellation.get("agent"),
                       "skills": constellation.get("skills", []),
                       "tools_gaps": gaps,
                       "governance": ("region-specific regulatory rules REQUIRED"
                                      if regulated else "standard engineering governance")},
            "resolution": _resolve_tools(sub),
            "routing": routing,
            "template": TEMPLATES.get("spec"),
        })
    return {
        "macro": task, "mode": mode, "skip_pipeline": False, "triage": tri,
        "personas": DISSECT_PERSONAS, "micros": micros,
        "provisioning": {"provider_of_tools": "llm-orchestrator",
                         "how": "the LLM discovers/vets and HANDS each instance its concrete tool/"
                                "skill/persona + a template; the sealed sandbox only runs given code"},
        "surfaces": {s: n for s, n in
                     [(m["routing"]["surface"], m["routing"]["needs_internet"]) for m in micros]},
        "feedback_protocol": ["need_more_tools", "wrong_persona", "need_template",
                              "needs_internet_route", "insufficient_confidence"],
        "hard_rule": "needs_internet=True is NEVER routed to the subprocess sandbox",
    }


if __name__ == "__main__":
    import json
    print("route(compute):", route("integrate the ODE with rk4")["surface"])
    print("route(discover):", route("search skills.sh for a legal MCP")["surface"],
          "| internet:", route("search skills.sh for a legal MCP")["needs_internet"])
    print("route(reason):", route("decide the best architecture")["surface"])
    print("route(reason, escalate):", route("decide the best architecture", escalate=True)["surface"])
    # triage: trivial skips the pipeline (token economy)
    print("\ntriage(trivial):", triage("What is 2+2?")["skip_pipeline"], "->",
          triage("What is 2+2?")["mode"])
    print("triage(hard):", triage("solve navier stokes turbulência pde")["mode"],
          "| escalate:", triage("solve navier stokes turbulência pde")["escalate_discovery"])
    print("triage(low MCFE):", triage("refactor the module", reliability=0.4)["escalate_discovery"],
          triage("refactor the module", reliability=0.4)["reasons"])
    # dissect_entry short-circuits a trivial task
    print("\ndissect_entry(trivial) skip:", dissect_entry("What is 2+2?")["skip_pipeline"])
    plan = dissect_entry("build a compliant medical billing pipeline", reliability=0.45)
    print("dissect_entry -> mode:", plan["mode"], "| escalate:", plan["triage"]["escalate_discovery"])
    for m in plan["micros"]:
        print(f"  micro[{m['discipline']}] surface={m['routing']['surface']} "
              f"escalated={m['routing']['escalated_to_discovery']} gov={m['needed']['governance'][:28]}")
    print("  hard_rule:", plan["hard_rule"])
