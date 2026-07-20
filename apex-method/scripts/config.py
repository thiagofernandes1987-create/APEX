#!/usr/bin/env python3
"""
config.py — Persistent user preferences for the apex-method skill.

WHY THIS EXISTS:
  The skill should remember the user's choices between sessions: which operating modes
  they prefer, which router backend to use, and how they want skill discovery to behave
  (use native APEX skills first, always search the marketplace, or both). This stores those
  in a small JSON file so the menu (menu.py) and the orchestrator honour them.

WHEN TO USE:
  Read at the start of a run (orchestrator picks the preferred mode when applicable);
  written by menu.py when the user sets preferences.

WHAT IF IT FAILS:
  Any read error returns DEFAULTS (never crashes); an unwritable path is reported but the
  in-memory config still applies for the session.
"""
import json
import os

# Prefer a user-level config; fall back to a skill-local file when HOME is not writable.
# AUD-W1: APEX_METHOD_HOME redirects EVERY durable store (tests/CI isolation). On Windows,
# os.environ["HOME"] does NOT redirect expanduser (Python>=3.8 uses USERPROFILE), so tests
# that relied on a HOME swap silently wrote into the user's REAL ~/.apex-method.
_APEX_BASE = os.environ.get("APEX_METHOD_HOME") or os.path.expanduser("~/.apex-method")
_HOME_CFG = os.path.join(_APEX_BASE, "config.json")
_LOCAL_CFG = os.path.join(os.path.dirname(__file__), "..", "user_config.json")

VALID_MODES = ["EXPRESS", "STANDARD", "FOGGY", "DEEP", "SCIENTIFIC", "RESEARCH"]
VALID_BACKENDS = ["word", "char", "st"]
VALID_SOURCES = ["native", "search", "both"]

DEFAULTS = {
    "preferred_modes": ["STANDARD", "DEEP", "SCIENTIFIC"],  # the modes the user favours
    "default_mode": None,           # force a mode, or None = let the pipeline decide
    "router_backend": "word",       # word | char (language-robust) | st (sentence-transformers)
    "discovery_source": "both",     # native | search | both
    "discovery_github": True,       # GitHub-native tier (trusted vendors + semantic) in the cascade
    "min_installs": 1000,           # skills.sh quality bar
    "auto_escalate": True,          # escalate mode on conflict signals
    "min_mode": None,               # HARD floor: force the pipeline at >= this mode for EVERY task
    "persist_backend": None,        # where end-of-session page-out goes: drive-swap | git | zip | local
}


def _path():
    d = os.path.dirname(_HOME_CFG)
    try:
        os.makedirs(d, exist_ok=True)
        return _HOME_CFG
    except Exception:
        return os.path.abspath(_LOCAL_CFG)


def load():
    """Return the merged config (DEFAULTS overlaid with whatever is saved)."""
    cfg = dict(DEFAULTS)
    for p in (_HOME_CFG, os.path.abspath(_LOCAL_CFG)):
        try:
            with open(p, encoding="utf-8") as f:
                cfg.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
            break
        except Exception:
            continue
    return cfg


def save(cfg: dict):
    """Persist the config (only known keys). Returns the path written, or an error dict."""
    clean = {k: v for k, v in cfg.items() if k in DEFAULTS}
    p = _path()
    try:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=1)
        return {"status": "OK", "path": p}
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)[:120], "config": clean}


def set_preferred_modes(modes):
    """Validate + persist the user's preferred operating modes."""
    modes = [m.upper() for m in modes]
    bad = [m for m in modes if m not in VALID_MODES]
    if bad:
        return {"status": "ERROR", "reason": f"unknown modes {bad}; valid: {VALID_MODES}"}
    cfg = load()
    cfg["preferred_modes"] = modes
    cfg["default_mode"] = modes[0] if len(modes) == 1 else cfg.get("default_mode")
    res = save(cfg)
    res["preferred_modes"] = modes
    return res


def set_option(key, value):
    """Set a single option (router_backend / discovery_source / min_installs / …)."""
    if key not in DEFAULTS:
        return {"status": "ERROR", "reason": f"unknown option {key}; valid: {list(DEFAULTS)}"}
    if key == "router_backend" and value not in VALID_BACKENDS:
        return {"status": "ERROR", "reason": f"backend must be {VALID_BACKENDS}"}
    if key == "discovery_source" and value not in VALID_SOURCES:
        return {"status": "ERROR", "reason": f"source must be {VALID_SOURCES}"}
    if key == "min_mode" and value not in VALID_MODES and value not in (None, "", "none"):
        return {"status": "ERROR", "reason": f"min_mode must be one of {VALID_MODES} (or none)"}
    if key == "min_mode" and value in ("", "none"):
        value = None
    cfg = load()
    cfg[key] = value
    res = save(cfg)
    res[key] = value
    return res


# ── exploration policy per mode (author's spec) ──────────────────────────────
# chaos agents start at FOGGY; parallelism switches from Level A (subprocess PoT) to
# Level B (concurrent LLM subagents) from FOGGY up; RESEARCH forces a mandatory genius stance.
EXPLORATION_POLICY = {
    "EXPRESS":    {"chaos": False, "p_chaos": 0.0,  "parallelism": "none", "genius": False},
    "STANDARD":   {"chaos": False, "p_chaos": 0.0,  "parallelism": "A",    "genius": False},
    "FOGGY":      {"chaos": True,  "p_chaos": 0.10, "parallelism": "B",    "genius": False},
    "DEEP":       {"chaos": True,  "p_chaos": 0.20, "parallelism": "B",    "genius": False},
    "SCIENTIFIC": {"chaos": True,  "p_chaos": 0.25, "parallelism": "B",    "genius": False},
    "RESEARCH":   {"chaos": True,  "p_chaos": 0.30, "parallelism": "B",    "genius": True},
}


def exploration_policy(mode: str) -> dict:
    """Return the per-mode exploration policy: whether chaos agents run, the P_chaos ceiling,
    the parallelism level (A=subprocess PoT / B=concurrent LLM subagents), and whether a
    mandatory 'genius' (non-obvious) stance is required. FOGGY+ turns chaos on and moves to B."""
    return EXPLORATION_POLICY.get((mode or "STANDARD").upper(), EXPLORATION_POLICY["STANDARD"])


def _mode_rank(m: str) -> int:
    return VALID_MODES.index(m) if m in VALID_MODES else 1


def resolve_mode(auto_mode: str, allow_downgrade: bool = False) -> str:
    """Resolve the effective operating mode honouring user preference WITHOUT dropping below the
    safety floor (RT-23).

    Rules:
      - `min_mode` is a HARD floor: the result is never weaker than it.
      - a forced `default_mode` is applied, but it cannot silently downgrade a STRONGER auto_mode
        (e.g. a SCIENTIFIC task under default_mode=STANDARD stays SCIENTIFIC) unless the caller
        passes allow_downgrade=True. It also cannot go below `min_mode`.
      - otherwise keep auto_mode, snapping UP to the nearest preferred mode when auto_mode isn't
        already preferred.
    """
    cfg = load()
    floor = cfg.get("min_mode")

    def clamp(m):
        return floor if (floor and _mode_rank(m) < _mode_rank(floor)) else m

    if cfg.get("default_mode"):
        forced = cfg["default_mode"]
        if not allow_downgrade and _mode_rank(forced) < _mode_rank(auto_mode):
            return clamp(auto_mode)          # never silently weaken a stronger computed mode
        return clamp(forced)

    pref = cfg.get("preferred_modes") or VALID_MODES
    chosen = auto_mode
    if auto_mode not in pref:
        stronger = [m for m in pref if _mode_rank(m) >= _mode_rank(auto_mode)]
        chosen = min(stronger, key=_mode_rank) if stronger else auto_mode
    return clamp(chosen)


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "modes":
        print(json.dumps(set_preferred_modes(sys.argv[2].split(",")), indent=1))
    elif len(sys.argv) >= 4 and sys.argv[1] == "set":
        print(json.dumps(set_option(sys.argv[2], sys.argv[3]), indent=1))
    else:
        print(json.dumps(load(), indent=1))
