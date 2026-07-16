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


def route(subtask, kind="auto"):
    """The routing contract for ONE micro-task. Emits the surface, the internet flag, and who
    provides the tools — and ENFORCES the hard rule so discovery can never land in the sandbox."""
    surface, needs_net = classify_surface(subtask)
    if needs_net and surface != "agent+internet":          # belt-and-suspenders enforcement
        surface = "agent+internet"
    if surface == "subprocess" and needs_net:              # impossible by construction, but guard
        surface, needs_net = "agent+internet", True
    return {"subtask": subtask, "surface": surface, "needs_internet": needs_net,
            "provider_of_tools": "llm-orchestrator",
            "rule": ("discovery/research runs in an internet-enabled agent (or subagent), NEVER the "
                     "sealed subprocess; the sandbox only runs already-provided deterministic code")}


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


def dissect_entry(task, mode="DEEP"):
    """THE ENTRY. Returns the plan the LLM executes: the 3 dissect personas to raise, the micros
    (each with SWOT + needed resources + resolution + ROUTING + a template + governance), the
    provisioning rule (the LLM provides the tools) and the feedback protocol. Reuses the existing
    dissect/assign/gravity/learning engines — no discovery is reimplemented here."""
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
        routing = route(sub)
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
        "macro": task, "mode": mode, "personas": DISSECT_PERSONAS, "micros": micros,
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
    plan = dissect_entry("build a compliant medical billing pipeline and find the right skills")
    print("\ndissect_entry ->")
    print("  personas:", [p["persona"] for p in plan["personas"]])
    for m in plan["micros"]:
        print(f"  micro[{m['discipline']}] surface={m['routing']['surface']} "
              f"net={m['routing']['needs_internet']} gov={m['needed']['governance'][:30]}")
    print("  hard_rule:", plan["hard_rule"])
