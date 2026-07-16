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
_HOME_CFG = os.path.expanduser("~/.apex-method/config.json")
_LOCAL_CFG = os.path.join(os.path.dirname(__file__), "..", "user_config.json")

VALID_MODES = ["EXPRESS", "STANDARD", "FOGGY", "DEEP", "SCIENTIFIC", "RESEARCH"]
VALID_BACKENDS = ["word", "char", "st"]
VALID_SOURCES = ["native", "search", "both"]

DEFAULTS = {
    "preferred_modes": ["STANDARD", "DEEP", "SCIENTIFIC"],  # the modes the user favours
    "default_mode": None,           # force a mode, or None = let the pipeline decide
    "router_backend": "word",       # word | char (language-robust) | st (sentence-transformers)
    "discovery_source": "both",     # native | search | both
    "min_installs": 1000,           # skills.sh quality bar
    "auto_escalate": True,          # escalate mode on conflict signals
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
    cfg = load()
    cfg[key] = value
    res = save(cfg)
    res[key] = value
    return res


def resolve_mode(auto_mode: str) -> str:
    """Given the mode the pipeline computed, honour the user's preference:
    a forced default_mode wins; otherwise keep auto_mode but, if it is not among the
    preferred modes, snap up to the nearest preferred one (never silently downgrade)."""
    cfg = load()
    if cfg.get("default_mode"):
        return cfg["default_mode"]
    pref = cfg.get("preferred_modes") or VALID_MODES
    if auto_mode in pref:
        return auto_mode
    order = VALID_MODES
    ai = order.index(auto_mode) if auto_mode in order else 1
    stronger = [m for m in pref if m in order and order.index(m) >= ai]
    return min(stronger, key=lambda m: order.index(m)) if stronger else auto_mode


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3 and sys.argv[1] == "modes":
        print(json.dumps(set_preferred_modes(sys.argv[2].split(",")), indent=1))
    elif len(sys.argv) >= 4 and sys.argv[1] == "set":
        print(json.dumps(set_option(sys.argv[2], sys.argv[3]), indent=1))
    else:
        print(json.dumps(load(), indent=1))
