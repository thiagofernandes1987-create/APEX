"""
Sprint V — Marketplace de spectral signatures (v3.6.0)
======================================================

Allows local UCO Sensor instances to publish discovered signatures to a
marketplace table and pull signatures published by peers, with payload
hash verification to detect tampering in transit.

Public API
----------
* ``publish_signature(store, signature_id, payload, *, publisher_id)``
  → ``Dict`` with the freshly published entry (auto-incremented version).
* ``pull_signature(store, signature_id, *, version=None)``
  → ``Dict`` or ``None`` if not found.
* ``list_marketplace(store, *, limit, offset, publisher_id)``
  → ``List[Dict]`` — latest version per signature_id.
* ``import_signature(store, payload, *, publisher_id, expected_hash)``
  → ``Dict`` with ``status`` ∈ {OK, HASH_MISMATCH, REJECTED_REDOS,
  REJECTED_INVALID_PAYLOAD}.

Security
--------
* All write operations gated by ``UCO_ADMIN_KEY`` at the REST layer.
* ``import_signature`` re-computes the canonical hash before persisting
  and rejects mismatches.
* If a signature carries a regex-like field, it is screened by the same
  ReDoS guard as ``sast.rules_feed`` (Sprint W audit-6).
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional


# Sprint V — fields allowed in a marketplace payload.  Importer rejects
# any key outside this set to avoid surprising side-effects on receivers.
_ALLOWED_PAYLOAD_KEYS = {
    "centroid", "diameter", "n_members", "label", "notes",
    "members", "occurrence_count", "category", "tags", "schema_version",
}


def canonical_payload_hash(payload: Dict[str, Any]) -> str:
    """Stable SHA-256 of a payload — keys sorted, separators canonical."""
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _has_redos_shape(text: str) -> bool:
    """ReDoS guard for marketplace payloads.

    Sprint AB (v3.10.0): replaces the prior substring blocklist
    (``("**", "++", "(.*)+", ...)``) with a call to
    ``sast.regex_analyzer.analyze_pattern`` — the same structured
    ReDoS analyzer used by SAST019. The blocklist let through whole
    families of catastrophic patterns (``(a+)+``, ``([a-z]+)*``,
    ``(\\d+)*``) that the analyzer correctly flags. Reusing the SSOT
    closes the DRY divergence identified in UCO_SENSOR_DEEP_EVAL §3
    Finding #5.

    Preserved guards (unchanged contract):
      * ``None`` or empty → False (publishers may omit optional fields;
        QA-FIX-6 v3.9.1).
      * length > 2000 chars → True (DoS-by-input-size surface).
    """
    if text is None or text == "":
        return False
    if len(text) > 2000:
        return True
    try:
        from sast.regex_analyzer import is_vulnerable
        return is_vulnerable(text)
    except Exception:
        # Defensive fallback: if the analyzer is missing or raises on a
        # malformed pattern, retain the conservative blocklist so the
        # guard never opens a hole due to import error.
        suspect = ("**", "++", "*?+", "+?*", "{0,}{",
                   "(?:.*)+", "(.*)+", "(.+)+")
        return any(s in text for s in suspect)


def _payload_passes_guards(payload: Dict[str, Any]) -> Optional[str]:
    """Return None if payload is OK, else the reason for rejection."""
    if not isinstance(payload, dict):
        return "REJECTED_INVALID_PAYLOAD"
    bad_keys = set(payload.keys()) - _ALLOWED_PAYLOAD_KEYS
    if bad_keys:
        return "REJECTED_INVALID_PAYLOAD"
    # Screen string fields for ReDoS-like shapes.
    for k in ("label", "notes", "category"):
        v = payload.get(k)
        if isinstance(v, str) and _has_redos_shape(v):
            return "REJECTED_REDOS"
    return None


def publish_signature(
    store: Any,
    signature_id: str,
    payload: Dict[str, Any],
    *,
    publisher_id: str = "anonymous",
    notes: str = "",
) -> Dict[str, Any]:
    """Validate + hash + persist a local signature for marketplace exchange."""
    rejection = _payload_passes_guards(payload)
    if rejection is not None:
        return {"status": rejection, "signature_id": signature_id}
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    digest = canonical_payload_hash(payload)
    entry = store.marketplace_publish(
        signature_id,
        blob,
        digest,
        publisher_id=publisher_id,
        source="local",
        notes=notes,
    )
    entry["status"] = "OK"
    return entry


def pull_signature(
    store: Any,
    signature_id: str,
    *,
    version: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    return store.marketplace_get(signature_id, version=version)


def list_marketplace(
    store: Any,
    *,
    limit: int = 100,
    offset: int = 0,
    publisher_id: Optional[str] = None,
) -> Dict[str, Any]:
    items = store.marketplace_list(
        limit=limit, offset=offset, publisher_id=publisher_id,
    )
    return {
        "total_distinct": store.marketplace_count(),
        "returned":       len(items),
        "limit":          int(limit),
        "offset":         int(offset),
        "items":          items,
    }


def import_signature(
    store: Any,
    signature_id: str,
    payload: Dict[str, Any],
    *,
    expected_hash: str,
    publisher_id: str = "imported",
    notes: str = "",
) -> Dict[str, Any]:
    """Import a foreign signature; re-hash payload and reject mismatches."""
    rejection = _payload_passes_guards(payload)
    if rejection is not None:
        return {"status": rejection, "signature_id": signature_id}
    digest = canonical_payload_hash(payload)
    if digest != expected_hash:
        return {
            "status":        "HASH_MISMATCH",
            "signature_id":  signature_id,
            "computed_hash": digest,
            "expected_hash": expected_hash,
        }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    entry = store.marketplace_publish(
        signature_id,
        blob,
        digest,
        publisher_id=publisher_id,
        source="imported",
        notes=notes,
    )
    entry["status"] = "OK"
    return entry
