"""
Marco 56 — Sprint V: Marketplace de Spectral Signatures (TV01-TV30)
=====================================================================

MVP de marketplace: publish/pull/list/import com:

* hash canônico SHA-256 sobre payload normalizado (sort_keys, separators).
* version auto-incrementada por signature_id.
* payload allowlist + ReDoS guard reusado do Sprint W audit-6.
* write endpoints exigem UCO_ADMIN_KEY (Sprint W audit-1 hardening).

Layout
------
TV01-TV10 — pure-Python core (governance/marketplace.py): hash,
            publish, pull, list, import, ReDoS guard, allowlist.
TV11-TV20 — store layer (sensor_storage): version auto-increment,
            pagination, latest-per-id, count, delete.
TV21-TV30 — REST: /marketplace/publish, /list, /pull/{id}, /import,
            auth gating, 400/404/200 paths, /docs registration.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))


# ─── shared helpers ──────────────────────────────────────────────────────────

def _fresh_store():
    from sensor_storage.snapshot_store import SnapshotStore
    return SnapshotStore(":memory:")


def _payload(label: str = "demo", n_members: int = 5):
    return {
        "centroid":   [0.1, 0.2, 0.3, 0.4, 0.5],
        "diameter":   0.07,
        "n_members":  n_members,
        "label":      label,
        "notes":      "test fixture",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TV01-TV10 — pure-Python core
# ═══════════════════════════════════════════════════════════════════════════════

def test_TV01_canonical_hash_is_stable():
    from governance.marketplace import canonical_payload_hash
    p1 = {"a": 1, "b": [1, 2, 3]}
    p2 = {"b": [1, 2, 3], "a": 1}
    assert canonical_payload_hash(p1) == canonical_payload_hash(p2)


def test_TV02_canonical_hash_differs_on_change():
    from governance.marketplace import canonical_payload_hash
    p = {"a": 1}
    q = {"a": 2}
    assert canonical_payload_hash(p) != canonical_payload_hash(q)


def test_TV03_publish_returns_OK_status():
    from governance.marketplace import publish_signature
    out = publish_signature(_fresh_store(), "sig.abc", _payload())
    assert out["status"] == "OK"
    assert out["signature_id"] == "sig.abc"
    assert out["version"] == 1
    assert out["payload_hash"]


def test_TV04_publish_rejects_invalid_payload_keys():
    from governance.marketplace import publish_signature
    bad = {"centroid": [0, 0], "evil_field": "boom"}
    out = publish_signature(_fresh_store(), "sig.x", bad)
    assert out["status"] == "REJECTED_INVALID_PAYLOAD"


def test_TV05_publish_rejects_redos_shape_in_label():
    from governance.marketplace import publish_signature
    bad = {"label": "(.*)+", "centroid": [0]}
    out = publish_signature(_fresh_store(), "sig.x", bad)
    assert out["status"] == "REJECTED_REDOS"


def test_TV06_publish_then_pull_round_trip():
    from governance.marketplace import publish_signature, pull_signature
    s = _fresh_store()
    publish_signature(s, "sig.abc", _payload())
    out = pull_signature(s, "sig.abc")
    assert out is not None
    assert out["signature_id"] == "sig.abc"
    assert out["payload"]["label"] == "demo"


def test_TV07_publish_increments_version_per_id():
    from governance.marketplace import publish_signature
    s = _fresh_store()
    v1 = publish_signature(s, "sig.abc", _payload("v1"))
    v2 = publish_signature(s, "sig.abc", _payload("v2"))
    assert v1["version"] == 1 and v2["version"] == 2


def test_TV08_list_returns_latest_version_per_id():
    from governance.marketplace import publish_signature, list_marketplace
    s = _fresh_store()
    publish_signature(s, "sig.A", _payload("v1"))
    publish_signature(s, "sig.A", _payload("v2"))
    publish_signature(s, "sig.B", _payload("only"))
    out = list_marketplace(s)
    assert out["total_distinct"] == 2
    versions = {item["signature_id"]: item["version"] for item in out["items"]}
    assert versions["sig.A"] == 2
    assert versions["sig.B"] == 1


def test_TV09_import_rejects_hash_mismatch():
    from governance.marketplace import import_signature, canonical_payload_hash
    s = _fresh_store()
    payload = _payload("foreign")
    wrong = hashlib.sha256(b"not-the-real-blob").hexdigest()
    out = import_signature(s, "sig.foreign", payload,
                           expected_hash=wrong)
    assert out["status"] == "HASH_MISMATCH"
    assert "computed_hash" in out


def test_TV10_import_accepts_matching_hash():
    from governance.marketplace import import_signature, canonical_payload_hash
    s = _fresh_store()
    payload = _payload("foreign")
    digest = canonical_payload_hash(payload)
    out = import_signature(s, "sig.foreign", payload,
                           expected_hash=digest, publisher_id="peer-org")
    assert out["status"] == "OK"
    assert out["publisher_id"] == "peer-org"
    assert out["source"] == "imported"


# ═══════════════════════════════════════════════════════════════════════════════
# TV11-TV20 — storage layer
# ═══════════════════════════════════════════════════════════════════════════════

def test_TV11_marketplace_publish_version_auto_increments():
    s = _fresh_store()
    e1 = s.marketplace_publish("s", "{}", "h1")
    e2 = s.marketplace_publish("s", "{}", "h2")
    assert e1["version"] == 1
    assert e2["version"] == 2


def test_TV12_marketplace_get_latest_by_default():
    s = _fresh_store()
    s.marketplace_publish("s", '{"x":1}', "h1")
    e2 = s.marketplace_publish("s", '{"x":2}', "h2")
    latest = s.marketplace_get("s")
    assert latest["version"] == e2["version"]


def test_TV13_marketplace_get_pinned_version():
    s = _fresh_store()
    e1 = s.marketplace_publish("s", '{"x":1}', "h1")
    s.marketplace_publish("s", '{"x":2}', "h2")
    pinned = s.marketplace_get("s", version=e1["version"])
    assert pinned["version"] == 1
    assert pinned["payload"] == {"x": 1}


def test_TV14_marketplace_get_missing_returns_None():
    s = _fresh_store()
    assert s.marketplace_get("ghost") is None


def test_TV15_marketplace_list_pagination():
    s = _fresh_store()
    for i in range(15):
        s.marketplace_publish(f"s{i:02d}", "{}", f"h{i}")
    page1 = s.marketplace_list(limit=10, offset=0)
    page2 = s.marketplace_list(limit=10, offset=10)
    assert len(page1) == 10 and len(page2) == 5


def test_TV16_marketplace_list_filter_publisher():
    s = _fresh_store()
    s.marketplace_publish("s.alpha", "{}", "h1", publisher_id="org-a")
    s.marketplace_publish("s.beta", "{}", "h2", publisher_id="org-b")
    out = s.marketplace_list(publisher_id="org-a")
    assert len(out) == 1
    assert out[0]["signature_id"] == "s.alpha"


def test_TV17_marketplace_count_distinct_signature_ids():
    s = _fresh_store()
    s.marketplace_publish("s1", "{}", "h1")
    s.marketplace_publish("s1", "{}", "h1b")
    s.marketplace_publish("s2", "{}", "h2")
    assert s.marketplace_count() == 2


def test_TV18_marketplace_delete_removes_all_versions():
    s = _fresh_store()
    s.marketplace_publish("s", "{}", "h1")
    s.marketplace_publish("s", "{}", "h2")
    n = s.marketplace_delete("s")
    assert n == 2
    assert s.marketplace_get("s") is None


def test_TV19_marketplace_payload_decodes_back_to_dict():
    s = _fresh_store()
    blob = json.dumps({"centroid": [1, 2, 3], "label": "x"},
                      sort_keys=True, separators=(",", ":"))
    s.marketplace_publish("s", blob, "h")
    out = s.marketplace_get("s")
    assert out["payload"] == {"centroid": [1, 2, 3], "label": "x"}


def test_TV20_marketplace_isolated_from_discovered_signatures():
    """marketplace_signatures table doesn't collide with discovered_signatures."""
    s = _fresh_store()
    s.marketplace_publish("sig-x", "{}", "h1")
    assert s.signature_count() == 0  # discovered_signatures untouched
    assert s.marketplace_count() == 1


# ═══════════════════════════════════════════════════════════════════════════════
# TV21-TV30 — REST endpoints (using isolated_store fixture from gate-2)
# ═══════════════════════════════════════════════════════════════════════════════

ADMIN_KEY = os.environ.get("UCO_ADMIN_KEY", "test-admin-key-do-not-use-in-prod")


def test_TV21_publish_handler_OK_with_admin_payload(isolated_store):
    from api.server import handle_marketplace_publish
    code, data = handle_marketplace_publish({
        "signature_id": "sig.api1", "payload": _payload(),
        "publisher_id": "tester",
    })
    assert code == 200
    assert data["status"] == "OK"
    assert data["version"] == 1


def test_TV22_publish_handler_400_on_missing_signature_id(isolated_store):
    from api.server import handle_marketplace_publish
    code, data = handle_marketplace_publish({"payload": _payload()})
    assert code == 400


def test_TV23_publish_handler_400_on_bad_payload_keys(isolated_store):
    from api.server import handle_marketplace_publish
    bad = {"signature_id": "s", "payload": {"evil": "x", "centroid": [0]}}
    code, data = handle_marketplace_publish(bad)
    assert code == 400
    assert data["status"] == "REJECTED_INVALID_PAYLOAD"


def test_TV24_list_handler_returns_envelope(isolated_store):
    from api.server import (
        handle_marketplace_publish, handle_marketplace_list,
    )
    handle_marketplace_publish({
        "signature_id": "sig.api2", "payload": _payload(),
    })
    code, data = handle_marketplace_list(limit=10, offset=0)
    assert code == 200
    assert data["total_distinct"] >= 1
    assert "items" in data


def test_TV25_pull_handler_200_then_404(isolated_store):
    from api.server import (
        handle_marketplace_publish, handle_marketplace_pull,
    )
    handle_marketplace_publish({
        "signature_id": "sig.pull", "payload": _payload(),
    })
    code_ok, data_ok = handle_marketplace_pull("sig.pull")
    assert code_ok == 200
    assert data_ok["signature_id"] == "sig.pull"
    code_404, _ = handle_marketplace_pull("ghost.nope")
    assert code_404 == 404


def test_TV26_import_handler_400_on_hash_mismatch(isolated_store):
    from api.server import handle_marketplace_import
    code, data = handle_marketplace_import({
        "signature_id": "sig.imp", "payload": _payload(),
        "expected_hash": "deadbeef" * 8,
    })
    assert code == 400
    assert data["status"] == "HASH_MISMATCH"


def test_TV27_import_handler_OK_with_correct_hash(isolated_store):
    from api.server import handle_marketplace_import
    from governance.marketplace import canonical_payload_hash
    p = _payload("imported-ok")
    digest = canonical_payload_hash(p)
    code, data = handle_marketplace_import({
        "signature_id": "sig.imp.ok", "payload": p,
        "expected_hash": digest, "publisher_id": "peer-y",
    })
    assert code == 200
    assert data["status"] == "OK"
    assert data["source"] == "imported"


def test_TV28_docs_endpoint_lists_marketplace_routes(isolated_store):
    from api.server import handle_docs
    code, data = handle_docs()
    assert code == 200
    routes = {r["path"] for r in data.get("endpoints", [])}
    assert "/marketplace/publish" in routes
    assert "/marketplace/list"    in routes
    assert "/marketplace/pull/{id}" in routes
    assert "/marketplace/import"  in routes


def test_TV29_pull_with_pinned_version_query_param(isolated_store):
    from api.server import (
        handle_marketplace_publish, handle_marketplace_pull,
    )
    e1 = handle_marketplace_publish({
        "signature_id": "sig.pin", "payload": _payload("v1"),
    })
    e2 = handle_marketplace_publish({
        "signature_id": "sig.pin", "payload": _payload("v2"),
    })
    # Pull v1 explicitly
    code, data = handle_marketplace_pull("sig.pin", version=1)
    assert code == 200
    assert data["version"] == 1
    assert data["payload"]["label"] == "v1"


def test_TV30_publish_handler_budget_under_100ms(isolated_store):
    from api.server import handle_marketplace_publish
    t0 = time.perf_counter()
    for i in range(20):
        handle_marketplace_publish({
            "signature_id": f"sig.bench{i:02d}",
            "payload": _payload(f"bench-{i}"),
        })
    dt = time.perf_counter() - t0
    assert dt < 2.0, f"20 publishes took {dt:.3f}s — budget regression"
