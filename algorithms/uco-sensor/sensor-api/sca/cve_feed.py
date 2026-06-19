"""
Sprint J — Dynamic CVE feed loader  (v3.3.2)
=============================================
Loads additional CVE entries at runtime from local JSON files or remote
URLs, merging them into the built-in ``_CVE_DB`` keyed on
``(ecosystem, package_name)``.  Addresses the Codex gap:
"hardcoded cve_database becomes debt in 6 months" — now ops can drop a
``cves-2026-Q2.json`` next to the sensor and refresh the corpus without
a new release.

Schema (JSON / YAML — both accepted)
------------------------------------
::

    {
      "version": "1.0",
      "generated_at": "2026-06-18T15:00:00Z",
      "source":     "internal-feed-v3",
      "cves": [
        {
          "ecosystem":      "npm",
          "package":        "minimist",
          "cve_id":         "CVE-2024-99999",
          "severity":       "HIGH",
          "cvss_score":     7.5,
          "description":    "Prototype pollution …",
          "affected_range": ">=1.0.0,<1.2.6",
          "fixed_version":  "1.2.6",
          "cwe":            "CWE-1321"
        },
        …
      ]
    }

Design contract
---------------
- **Built-in DB is never mutated destructively** unless you call
  ``unload(feed_id)`` or ``reset_overrides()``.  Each load is tracked
  by a feed-id so it can be rolled back.
- **Dedup-by-CVE-id**: if a CVE id already exists for the same
  ``(ecosystem, package)`` pair, the new entry **overrides** the old.
  This is intentional — feeds update severity / range after disclosure
  refinement.
- **Defensive parsing**: malformed entries are skipped (not raised) and
  reported in the load result.  One bad row never poisons the batch.
- **No silent network**: ``load_from_url`` requires an explicit timeout
  and respects ``UCO_CVE_FEED_ALLOWLIST`` env var (CSV of allowed
  hostnames).  Empty allowlist = network calls disabled.
- **Pure-stdlib**: ``urllib.request`` for HTTP, ``json`` / ``yaml``
  (optional) for parsing — no requests dependency added.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from sca.cve_database import CVEEntry, _CVE_DB, _normalize_name


_log = logging.getLogger("uco-sensor.cve_feed")


# ─── Load tracking ────────────────────────────────────────────────────────────

@dataclass
class FeedLoadResult:
    feed_id:        str
    source:         str
    ts_loaded:      float
    added_new:      int             # entries that introduced a new key
    added_override: int             # entries that replaced an existing CVE id
    skipped_bad:    int             # malformed entries dropped
    errors:         List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Track every load so unload() can roll it back.
# Maps feed_id → list[(key, cve_id, *previous_entry_or_None*)]
_LOADED_FEEDS: Dict[str, List[Tuple[Tuple[str, str], str, Optional[CVEEntry]]]] = {}


# ─── Parsing helpers ──────────────────────────────────────────────────────────

_REQUIRED_FIELDS = {"ecosystem", "package", "cve_id", "affected_range"}
_DEFAULTS = {
    "severity":     "MEDIUM",
    "cvss_score":   5.0,
    "description":  "(no description)",
    "fixed_version": "",
    "cwe":          "CWE-0",
}


def _parse_entry(raw: Dict[str, Any]) -> Tuple[Optional[Tuple[str, str]], Optional[CVEEntry], Optional[str]]:
    """Return (key, entry, error_message).  All-None entry+key = skipped."""
    missing = _REQUIRED_FIELDS - set(raw.keys())
    if missing:
        return None, None, f"missing fields {sorted(missing)}"

    eco = str(raw["ecosystem"]).lower().strip()
    if not eco:
        return None, None, "empty ecosystem"

    pkg = str(raw["package"]).strip()
    if not pkg:
        return None, None, "empty package"

    try:
        cvss = float(raw.get("cvss_score", _DEFAULTS["cvss_score"]))
    except (TypeError, ValueError):
        return None, None, "invalid cvss_score"

    severity = str(raw.get("severity", _DEFAULTS["severity"])).upper()
    if severity not in {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}:
        return None, None, f"invalid severity {severity!r}"

    try:
        entry = CVEEntry(
            cve_id=str(raw["cve_id"]).strip(),
            severity=severity,
            cvss_score=cvss,
            description=str(raw.get("description", _DEFAULTS["description"])),
            affected_range=str(raw["affected_range"]).strip(),
            fixed_version=str(raw.get("fixed_version", _DEFAULTS["fixed_version"])),
            cwe=str(raw.get("cwe", _DEFAULTS["cwe"])),
        )
    except Exception as exc:
        return None, None, f"build failed: {exc}"

    key = (eco, _normalize_name(eco, pkg))
    return key, entry, None


# ─── Public API: load ─────────────────────────────────────────────────────────

def load_from_file(path: str, feed_id: Optional[str] = None) -> FeedLoadResult:
    """Load CVE entries from a local JSON or YAML file."""
    if feed_id is None:
        feed_id = f"file:{os.path.basename(path)}:{int(time.time())}"

    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as exc:
        return FeedLoadResult(
            feed_id=feed_id, source=path, ts_loaded=time.time(),
            added_new=0, added_override=0, skipped_bad=0,
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return _ingest_text(text, source=path, feed_id=feed_id)


def load_from_url(url: str, *, timeout: float = 10.0,
                  feed_id: Optional[str] = None) -> FeedLoadResult:
    """Load CVE entries from an HTTP(S) URL.

    Requires the host to be present in ``UCO_CVE_FEED_ALLOWLIST`` (CSV
    of hostnames).  Empty / unset allowlist disables network loads —
    closed by default.
    """
    if feed_id is None:
        feed_id = f"url:{url}:{int(time.time())}"

    allowlist_env = os.environ.get("UCO_CVE_FEED_ALLOWLIST", "")
    allowed = {h.strip() for h in allowlist_env.split(",") if h.strip()}
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
    except Exception:
        host = ""

    if not allowed or host not in allowed:
        return FeedLoadResult(
            feed_id=feed_id, source=url, ts_loaded=time.time(),
            added_new=0, added_override=0, skipped_bad=0,
            errors=[
                f"host {host!r} not in UCO_CVE_FEED_ALLOWLIST "
                "(set env var to a CSV of allowed hostnames)"
            ],
        )

    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            text = resp.read().decode("utf-8")
    except Exception as exc:
        return FeedLoadResult(
            feed_id=feed_id, source=url, ts_loaded=time.time(),
            added_new=0, added_override=0, skipped_bad=0,
            errors=[f"{type(exc).__name__}: {exc}"],
        )

    return _ingest_text(text, source=url, feed_id=feed_id)


def _ingest_text(text: str, *, source: str, feed_id: str) -> FeedLoadResult:
    """Parse JSON/YAML and merge into _CVE_DB."""
    payload: Optional[Dict[str, Any]] = None
    try:
        payload = json.loads(text)
    except Exception:
        try:
            import yaml   # type: ignore
            payload = yaml.safe_load(text)
        except Exception:
            payload = None

    if not isinstance(payload, dict) or "cves" not in payload:
        return FeedLoadResult(
            feed_id=feed_id, source=source, ts_loaded=time.time(),
            added_new=0, added_override=0, skipped_bad=0,
            errors=["payload is not a dict with 'cves' key"],
        )

    cves_raw = payload.get("cves")
    if not isinstance(cves_raw, list):
        return FeedLoadResult(
            feed_id=feed_id, source=source, ts_loaded=time.time(),
            added_new=0, added_override=0, skipped_bad=0,
            errors=["'cves' field is not a list"],
        )

    result = FeedLoadResult(
        feed_id=feed_id, source=source, ts_loaded=time.time(),
        added_new=0, added_override=0, skipped_bad=0, errors=[],
    )
    rollback_log: List[Tuple[Tuple[str, str], str, Optional[CVEEntry]]] = []

    for i, raw in enumerate(cves_raw):
        if not isinstance(raw, dict):
            result.skipped_bad += 1
            result.errors.append(f"entry[{i}]: not a dict")
            continue
        key, entry, err = _parse_entry(raw)
        if err is not None or key is None or entry is None:
            result.skipped_bad += 1
            result.errors.append(f"entry[{i}]: {err}")
            continue

        bucket = _CVE_DB.setdefault(key, [])
        previous = next((e for e in bucket if e.cve_id == entry.cve_id), None)
        if previous is not None:
            bucket.remove(previous)
            bucket.append(entry)
            result.added_override += 1
            rollback_log.append((key, entry.cve_id, previous))
        else:
            bucket.append(entry)
            result.added_new += 1
            rollback_log.append((key, entry.cve_id, None))

    _LOADED_FEEDS[feed_id] = rollback_log
    _log.info("cve feed loaded: id=%s new=%d override=%d skipped=%d",
              feed_id, result.added_new, result.added_override, result.skipped_bad)
    return result


# ─── Public API: unload + status ──────────────────────────────────────────────

def unload(feed_id: str) -> int:
    """Roll back a previously-loaded feed.  Returns number of rows reverted."""
    log = _LOADED_FEEDS.pop(feed_id, None)
    if log is None:
        return 0
    n = 0
    for key, cve_id, previous in reversed(log):
        bucket = _CVE_DB.get(key, [])
        # Remove current entry by CVE id.
        bucket[:] = [e for e in bucket if e.cve_id != cve_id]
        if previous is not None:
            bucket.append(previous)
        if not bucket:
            _CVE_DB.pop(key, None)
        n += 1
    return n


def reset_overrides() -> int:
    """Roll back every loaded feed in reverse load order."""
    n = 0
    for feed_id in list(_LOADED_FEEDS.keys())[::-1]:
        n += unload(feed_id)
    return n


def loaded_feeds() -> List[Dict[str, Any]]:
    """Summary of currently-active feeds for ``GET /feeds/status``."""
    return [
        {"feed_id": fid, "entries": len(log)}
        for fid, log in _LOADED_FEEDS.items()
    ]


def feed_status() -> Dict[str, Any]:
    """Aggregate status report — total CVEs, active feeds, last load timestamp."""
    from sca.cve_database import database_size, ecosystems
    return {
        "total_cves":      database_size(),
        "ecosystems":      ecosystems(),
        "active_feeds":    loaded_feeds(),
        "n_active_feeds":  len(_LOADED_FEEDS),
    }
