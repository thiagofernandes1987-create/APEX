"""
Sprint N — Dynamic SAST Rules Feed  (v3.3.6)
=============================================
Extends Sprint J's dynamic-feed pattern to the SAST corpus: ops can
inject **new SAST detectors at runtime** without a release, with the
same rollback-by-feed-id semantics.

Security constraint
-------------------
The CVE feed allows arbitrary data because no code runs on it.  Rules
are different: a rule **executes** against source code. To stay safe
we accept only **regex-based predicates** — no Python eval, no arbitrary
AST predicate, no file system access.  This is the same constraint
Semgrep, Bandit and Snyk apply to user-contributed rules.

Schema (JSON / YAML auto-detect)
--------------------------------
::

    {
      "version": "1.0",
      "rules": [
        {
          "rule_id":     "SAST900",            # required, unique
          "title":       "Custom Pattern",     # required
          "severity":    "MEDIUM",             # CRITICAL/HIGH/MEDIUM/LOW/INFO
          "cwe_id":      "CWE-XXX",            # optional
          "owasp":       "A04:2021",           # optional
          "description": "...",                # optional
          "remediation": "...",                # optional
          "pattern":     "regex on each line"  # required — Python re flavor
        },
        ...
      ]
    }

Design contract
---------------
- Loaded rules live in ``_DYNAMIC_RULES`` (process-local) and contribute
  findings via ``scan_dynamic(source)`` — invoked from ``sast/scanner.py``
  alongside the static catalogue.
- Each load is tracked by feed_id so ``unload(feed_id)`` reverts.
- Malformed rules are skipped, never raise; bad rule_ids that collide
  with the built-in catalogue are rejected (no override of built-ins).
- Regex is compiled once per rule at load time; invalid regex → skipped
  with structured error.
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Pattern, Tuple


_log = logging.getLogger("uco-sensor.sast_rules_feed")


@dataclass
class DynamicRule:
    rule_id:     str
    title:       str
    severity:    str
    pattern_src: str
    cwe_id:      str = "CWE-0"
    owasp:       str = ""
    description: str = ""
    remediation: str = ""
    _compiled:   Optional[Pattern] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("_compiled", None)
        d["pattern"] = d.pop("pattern_src")
        return d


@dataclass
class RuleFeedLoadResult:
    feed_id:        str
    source:         str
    ts_loaded:      float
    added_new:      int
    skipped_bad:    int
    errors:         List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ─── Module state ─────────────────────────────────────────────────────────────

_DYNAMIC_RULES: Dict[str, DynamicRule] = {}
_LOADED_FEEDS:  Dict[str, List[str]]   = {}   # feed_id → [rule_ids loaded]


_VALID_SEVERITY = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}
_REQUIRED_FIELDS = {"rule_id", "title", "severity", "pattern"}


def _builtin_rule_ids() -> set:
    """Lazy fetch built-in SAST rule IDs to prevent dynamic override."""
    try:
        from sast.scanner import RULES
        return {r.rule_id for r in RULES}
    except Exception:
        return set()


# ─── Parsing ──────────────────────────────────────────────────────────────────

def _parse_rule(raw: Dict[str, Any]) -> Tuple[Optional[DynamicRule], Optional[str]]:
    missing = _REQUIRED_FIELDS - set(raw.keys())
    if missing:
        return None, f"missing fields {sorted(missing)}"

    rule_id = str(raw["rule_id"]).strip()
    if not rule_id:
        return None, "empty rule_id"

    if rule_id in _builtin_rule_ids():
        return None, f"rule_id {rule_id!r} collides with built-in catalogue"

    if rule_id in _DYNAMIC_RULES:
        return None, f"rule_id {rule_id!r} already loaded (use unload first)"

    severity = str(raw.get("severity", "MEDIUM")).upper()
    if severity not in _VALID_SEVERITY:
        return None, f"invalid severity {severity!r}"

    pattern_src = str(raw["pattern"])
    try:
        compiled = re.compile(pattern_src)
    except re.error as exc:
        return None, f"invalid regex: {exc}"

    return DynamicRule(
        rule_id=rule_id,
        title=str(raw["title"]),
        severity=severity,
        pattern_src=pattern_src,
        cwe_id=str(raw.get("cwe_id", "CWE-0")),
        owasp=str(raw.get("owasp", "")),
        description=str(raw.get("description", "")),
        remediation=str(raw.get("remediation", "")),
        _compiled=compiled,
    ), None


# ─── Public load / unload ────────────────────────────────────────────────────

def load_from_file(path: str, feed_id: Optional[str] = None) -> RuleFeedLoadResult:
    if feed_id is None:
        feed_id = f"sast-file:{os.path.basename(path)}:{int(time.time())}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as exc:
        return RuleFeedLoadResult(
            feed_id=feed_id, source=path, ts_loaded=time.time(),
            added_new=0, skipped_bad=0,
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return _ingest_text(text, source=path, feed_id=feed_id)


def load_from_url(url: str, *, timeout: float = 10.0,
                  feed_id: Optional[str] = None) -> RuleFeedLoadResult:
    if feed_id is None:
        feed_id = f"sast-url:{url}:{int(time.time())}"
    allowlist = {h.strip() for h in
                 os.environ.get("UCO_SAST_FEED_ALLOWLIST", "").split(",")
                 if h.strip()}
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""
    if not allowlist or host not in allowlist:
        return RuleFeedLoadResult(
            feed_id=feed_id, source=url, ts_loaded=time.time(),
            added_new=0, skipped_bad=0,
            errors=[
                f"host {host!r} not in UCO_SAST_FEED_ALLOWLIST "
                "(set env var to a CSV of allowed hostnames)"
            ],
        )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:
        return RuleFeedLoadResult(
            feed_id=feed_id, source=url, ts_loaded=time.time(),
            added_new=0, skipped_bad=0,
            errors=[f"{type(exc).__name__}: {exc}"],
        )
    return _ingest_text(text, source=url, feed_id=feed_id)


def _ingest_text(text: str, *, source: str, feed_id: str) -> RuleFeedLoadResult:
    payload: Optional[Dict[str, Any]] = None
    try:
        payload = json.loads(text)
    except Exception:
        try:
            import yaml  # type: ignore
            payload = yaml.safe_load(text)
        except Exception:
            payload = None
    if not isinstance(payload, dict) or "rules" not in payload:
        return RuleFeedLoadResult(
            feed_id=feed_id, source=source, ts_loaded=time.time(),
            added_new=0, skipped_bad=0,
            errors=["payload is not a dict with 'rules' key"],
        )
    rules_raw = payload.get("rules")
    if not isinstance(rules_raw, list):
        return RuleFeedLoadResult(
            feed_id=feed_id, source=source, ts_loaded=time.time(),
            added_new=0, skipped_bad=0,
            errors=["'rules' field is not a list"],
        )

    result = RuleFeedLoadResult(
        feed_id=feed_id, source=source, ts_loaded=time.time(),
        added_new=0, skipped_bad=0, errors=[],
    )
    loaded_ids: List[str] = []
    for i, raw in enumerate(rules_raw):
        if not isinstance(raw, dict):
            result.skipped_bad += 1
            result.errors.append(f"rule[{i}]: not a dict")
            continue
        rule, err = _parse_rule(raw)
        if rule is None:
            result.skipped_bad += 1
            result.errors.append(f"rule[{i}]: {err}")
            continue
        _DYNAMIC_RULES[rule.rule_id] = rule
        loaded_ids.append(rule.rule_id)
        result.added_new += 1

    _LOADED_FEEDS[feed_id] = loaded_ids
    _log.info("sast feed loaded: id=%s new=%d skipped=%d",
              feed_id, result.added_new, result.skipped_bad)
    return result


def unload(feed_id: str) -> int:
    ids = _LOADED_FEEDS.pop(feed_id, None)
    if not ids:
        return 0
    n = 0
    for rid in ids:
        if _DYNAMIC_RULES.pop(rid, None) is not None:
            n += 1
    return n


def reset() -> int:
    n = 0
    for fid in list(_LOADED_FEEDS.keys())[::-1]:
        n += unload(fid)
    return n


def loaded_rules() -> List[Dict[str, Any]]:
    return [r.to_dict() for r in _DYNAMIC_RULES.values()]


def loaded_feeds() -> List[Dict[str, Any]]:
    return [{"feed_id": fid, "rule_ids": list(ids)}
            for fid, ids in _LOADED_FEEDS.items()]


def feed_status() -> Dict[str, Any]:
    return {
        "n_dynamic_rules": len(_DYNAMIC_RULES),
        "n_active_feeds":  len(_LOADED_FEEDS),
        "rules":           loaded_rules(),
        "feeds":           loaded_feeds(),
    }


# ─── Scan hook (called from sast/scanner.py) ──────────────────────────────────

def scan_dynamic(source: str) -> List[Dict[str, Any]]:
    """
    Apply every loaded dynamic rule line-by-line to *source*.
    Returns a list of finding dicts compatible with SASTFinding shape:
        {rule_id, severity, line, evidence, description, remediation}
    """
    if not _DYNAMIC_RULES:
        return []
    out: List[Dict[str, Any]] = []
    lines = source.splitlines()
    for rule in _DYNAMIC_RULES.values():
        pat = rule._compiled
        if pat is None:
            try:
                pat = re.compile(rule.pattern_src)
            except re.error:
                continue
        for line_no, text in enumerate(lines, start=1):
            if pat.search(text):
                out.append({
                    "rule_id":     rule.rule_id,
                    "severity":    rule.severity,
                    "line":        line_no,
                    "evidence":    text.strip()[:120],
                    "description": rule.description,
                    "remediation": rule.remediation,
                    "cwe_id":      rule.cwe_id,
                })
    return out
