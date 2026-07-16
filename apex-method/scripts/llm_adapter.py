#!/usr/bin/env python3
"""
llm_adapter.py — APEX LLM Adapter (B2): the hardware-abstraction layer of the cognitive runtime.

WHY THIS EXISTS:
  The kernel (SKILL.md + the 36 scripts) must stay stable while the model underneath changes —
  Claude, GPT, Gemini, or a small local model. This reads the contract in meta/llm_compat.json
  (what the runtime REQUIRES + a per-provider capability matrix + degradation rules) and answers
  three questions the orchestrator needs before it runs a mode:
    1. check(provider)      — does this model meet the kernel's REQUIRED capabilities?
    2. fits(provider, mode) — does its context window fit the mode's budget?
    3. degrade(provider,mode) — the concrete plan when something is missing (Level A instead of B,
       manual tool loop, best-effort JSON parsing, or a capped mode), announced not silent.

WHEN TO USE:
  At the start of a run on a NON-reference model, or whenever you need to know if a Level-B
  subagent fan-out is available (Claude: yes; GPT/Gemini/local: degrade to Level A).

WHAT IF IT FAILS:
  Pure stdlib (json). A missing/broken contract file degrades to a conservative built-in baseline
  (only the required caps assumed, small window) so the runtime still answers. Never raises.
"""
import json
import os

_META = os.path.join(os.path.dirname(__file__), "..", "meta")
_CONTRACT_YAML = os.path.join(_META, "apex_llm.yaml")     # authoritative (PyYAML when present)
_CONTRACT = os.path.join(_META, "llm_compat.json")        # stdlib fallback mirror

# Loop-prevention defaults if the contract omits them (never let the LLM spin).
_LIMITS_DEFAULT = {"max_iterations": 8, "max_restarts": 3, "min_progress": 0.15,
                   "reliability_replan": 0.50, "reliability_early_exit": 0.30,
                   "rejections_streak_abort": 20, "low_variance_abort": 0.03,
                   "wall_seconds_per_round": 30}

# Conservative fallback if the contract file is missing/corrupt: assume only the REQUIRED caps,
# no optional ones, and a small window — so degrade() errs toward safety.
_BASELINE = {
    "kernel_requirements": {
        "capabilities": {
            "tool_calling": {"required": True}, "subprocess_exec": {"required": True},
            "structured_json_output": {"required": True}, "multi_turn": {"required": True},
            "subagents": {"required": False}, "long_context": {"required": False},
        },
        "context_window_tokens": {"EXPRESS": 4000, "STANDARD": 8000, "FOGGY": 16000,
                                  "DEEP": 32000, "SCIENTIFIC": 48000, "RESEARCH": 64000},
    },
    "providers": {
        "claude": {"tool_calling": True, "subprocess_exec": True, "structured_json_output": True,
                   "multi_turn": True, "subagents": True, "long_context": True,
                   "context_window_tokens": 200000},
    },
    "degradation_rules": [],
}

# mode order for capping (least -> most demanding)
_MODE_ORDER = ["EXPRESS", "STANDARD", "FOGGY", "DEEP", "SCIENTIFIC", "RESEARCH"]


def load():
    """Return the contract dict. Prefers the authoritative YAML (PyYAML when importable), then the
    JSON mirror, then a conservative built-in baseline — so it never crashes and never over-promises."""
    # 1. YAML (authoritative) when PyYAML is available
    try:
        import yaml
        with open(_CONTRACT_YAML, encoding="utf-8") as f:
            c = yaml.safe_load(f)
        if isinstance(c, dict) and "kernel_requirements" in c and "providers" in c:
            return c
    except Exception:
        pass
    # 2. JSON mirror (stdlib fallback)
    try:
        with open(_CONTRACT, encoding="utf-8") as f:
            c = json.load(f)
        if "kernel_requirements" in c and "providers" in c:
            return c
    except Exception:
        pass
    return _BASELINE


def limits(contract=None):
    """The loop-prevention / minimum-run limits (max iterations, min progress, R_acum gates,
    stuck thresholds). Missing keys fall back to safe defaults so the LLM can never spin."""
    c = contract or load()
    lp = dict(_LIMITS_DEFAULT)
    lp.update({k: v for k, v in (c.get("loop_prevention") or {}).items() if k in _LIMITS_DEFAULT})
    return lp


def requirements(contract=None):
    """The required capabilities + the optional accelerators (numpy/scipy/scikit-learn/…), so a
    caller can see the minimum contract and what would speed things up."""
    c = contract or load()
    req = [k for k, v in c["kernel_requirements"]["capabilities"].items() if v.get("required")]
    return {"required": req, "optional_accelerators": c.get("optional_accelerators", {}),
            "context_window_tokens": c["kernel_requirements"]["context_window_tokens"]}


def current_provider():
    """The provider to assume. APEX_LLM_PROVIDER overrides; default 'claude' (reference runtime)."""
    return (os.environ.get("APEX_LLM_PROVIDER") or "claude").strip().lower()


def capabilities(provider=None, contract=None):
    """The provider's capability row. Unknown provider -> the conservative 'local'-like baseline
    (every optional cap off, small window) so we never over-promise for a model we don't know."""
    c = contract or load()
    provider = (provider or current_provider()).lower()
    prov = c.get("providers", {})
    if provider in prov:
        return dict(prov[provider])
    # unknown model: assume required caps present but every OPTIONAL cap OFF, smallest window
    caps = {}
    for name, spec in c["kernel_requirements"]["capabilities"].items():
        caps[name] = bool(spec.get("required"))
    caps["context_window_tokens"] = min(c["kernel_requirements"]["context_window_tokens"].values())
    caps["notes"] = f"unknown provider '{provider}': conservative baseline"
    return caps


def check(provider=None, contract=None):
    """Does the model meet the kernel's REQUIRED capabilities? Returns {ok, missing, provider}."""
    c = contract or load()
    caps = capabilities(provider, c)
    missing = [name for name, spec in c["kernel_requirements"]["capabilities"].items()
               if spec.get("required") and not caps.get(name, False)]
    return {"ok": not missing, "missing_required": missing,
            "provider": (provider or current_provider()).lower()}


def fits(provider=None, mode="STANDARD", contract=None):
    """Does the provider's context window fit the mode's budget?"""
    c = contract or load()
    need = c["kernel_requirements"]["context_window_tokens"].get(mode.upper(), 8000)
    have = capabilities(provider, c).get("context_window_tokens", 0)
    return {"fits": have >= need, "need": need, "have": have, "mode": mode.upper()}


def cap_mode(provider=None, mode="STANDARD", contract=None):
    """The largest mode (<= the requested one) whose window fits. Never upgrades the request."""
    c = contract or load()
    want = mode.upper()
    have = capabilities(provider, c).get("context_window_tokens", 0)
    budgets = c["kernel_requirements"]["context_window_tokens"]
    want_i = _MODE_ORDER.index(want) if want in _MODE_ORDER else 1
    for i in range(want_i, -1, -1):                 # walk DOWN from the requested mode
        m = _MODE_ORDER[i]
        if have >= budgets.get(m, 0):
            return m
    return "EXPRESS"


def degrade(provider=None, mode="STANDARD", contract=None):
    """The concrete degradation plan for running `mode` on `provider`: parallelism level, whether
    the tool loop / JSON parsing must be manual, and the capped mode. Announced, not silent."""
    c = contract or load()
    provider = (provider or current_provider()).lower()
    caps = capabilities(provider, c)
    adjustments = []
    parallelism = "B" if caps.get("subagents") else "A"
    if not caps.get("subagents"):
        adjustments.append("no native subagents -> parallelism Level A (subprocess PoT); "
                           "ignore spawn_subagents manifests")
    if not caps.get("tool_calling"):
        adjustments.append("no tool-calling -> run scripts manually and paste output; "
                           "PoT becomes copy-run-paste (no auto tool loop)")
    if not caps.get("structured_json_output"):
        adjustments.append("no structured JSON -> parse the last JSON-looking line; wrap stance/"
                           "laudo prompts with 'print exactly one JSON object' and validate")
    capped = cap_mode(provider, mode, c)
    if capped != mode.upper():
        adjustments.append(f"context window too small for {mode.upper()} -> capped to {capped}")
    return {"provider": provider, "requested_mode": mode.upper(), "effective_mode": capped,
            "parallelism": parallelism, "meets_required": check(provider, c)["ok"],
            "adjustments": adjustments or ["none — full runtime available"]}


def report(provider=None, mode="STANDARD"):
    """One call the orchestrator can log: requirement check + window fit + degradation plan."""
    c = load()
    provider = (provider or current_provider()).lower()
    return {"provider": provider, "check": check(provider, c),
            "fits": fits(provider, mode, c), "plan": degrade(provider, mode, c)}


if __name__ == "__main__":
    import sys
    prov = sys.argv[1] if len(sys.argv) > 1 else None
    mode = sys.argv[2] if len(sys.argv) > 2 else "RESEARCH"
    for p in ([prov] if prov else ["claude", "gpt", "gemini", "local", "mystery-model"]):
        r = report(p, mode)
        print(f"\n== {p} @ {mode} ==")
        print(json.dumps(r, indent=1, ensure_ascii=False))
