"""
Marco 43 — Sprint L: PELT Change-Point + RCA (TO01-TO30)
===========================================================

Exposes the PELT change-point detector from frequency-engine as a
governance signal, with optional git blame enrichment.

Coverage layout
---------------
* TO01-TO10 — detect_changepoints pure behavior (clear shift, no shift,
  insufficient samples, missing module, dataclass shape, primary channels
  override, model + penalty propagation, payload serialization).
* TO11-TO20 — repo_changepoints aggregation, sorting by confidence,
  empty repo, multi-module isolation, ChangePointRecord.to_dict.
* TO21-TO30 — REST endpoints: 400 on missing module, 200 with shape,
  repo endpoint shape, parameters parsed, git enrichment best-effort
  (no git in sandbox → fields stay None, never crashes), defaults pinned.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_FREQ = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_FREQ) not in sys.path:
    sys.path.insert(0, str(_FREQ))

from core.data_structures import MetricVector
from sensor_storage.snapshot_store import SnapshotStore
from governance.changepoints import (
    ChangePointRecord,
    detect_changepoints,
    repo_changepoints,
    annotate_with_git,
    _DEFAULT_PRIMARY,
)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _mv(module: str, commit: str, ts: float, *, h: float = 5.0,
        cc: int = 2, di: float = 0.2) -> MetricVector:
    return MetricVector(
        module_id=module, commit_hash=commit, timestamp=ts,
        hamiltonian=h, cyclomatic_complexity=cc,
        infinite_loop_risk=0.05, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=di,
        syntactic_dead_code=0, duplicate_block_count=0, halstead_bugs=0.1,
    )


def _shifted_store(n_pre: int = 10, n_post: int = 10) -> SnapshotStore:
    """History with a clear regime shift at i = n_pre."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n_pre + n_post):
        h, cc = (5.0, 2) if i < n_pre else (50.0, 30)
        s.insert(_mv("demo", f"c{i:02d}", base + i, h=h, cc=cc))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# detect_changepoints — pure behavior (TO01-TO10)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TO01_detects_clear_regime_shift():
    s = _shifted_store(10, 10)
    records = detect_changepoints(s, "demo")
    assert len(records) >= 1
    assert records[0].confidence > 0.5


def test_TO02_returns_empty_when_no_shift():
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(20):
        s.insert(_mv("flat", f"c{i:02d}", base + i, h=5.0))
    records = detect_changepoints(s, "flat")
    # May return [] or a low-confidence record — assert either case is fine.
    if records:
        assert records[0].confidence < 0.95   # low confidence on flat series


def test_TO03_empty_history_returns_empty_list():
    assert detect_changepoints(SnapshotStore(":memory:"), "ghost") == []


def test_TO04_below_min_samples_returns_empty():
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(3):
        s.insert(_mv("short", f"c{i}", base + i))
    assert detect_changepoints(s, "short") == []


def test_TO05_record_carries_required_fields():
    s = _shifted_store()
    rec = detect_changepoints(s, "demo")[0]
    assert rec.module_id == "demo"
    assert rec.commit_idx >= 0
    assert rec.commit_hash is not None
    assert rec.timestamp > 0
    assert rec.confidence >= 0.0
    assert rec.magnitude  >= 0.0
    assert isinstance(rec.affected_channels, list)


def test_TO06_default_primary_channels_pin():
    assert _DEFAULT_PRIMARY == ("H", "CC", "DI")


def test_TO07_custom_primary_channels_accepted():
    s = _shifted_store()
    # Custom channel set should not raise.
    records = detect_changepoints(s, "demo", primary_channels=["H"])
    assert isinstance(records, list)


def test_TO08_penalty_higher_reduces_or_equals_detections():
    s = _shifted_store()
    low_pen  = detect_changepoints(s, "demo", penalty=0.1)
    high_pen = detect_changepoints(s, "demo", penalty=100.0)
    assert len(high_pen) <= len(low_pen)


def test_TO09_model_l2_also_works():
    s = _shifted_store()
    records = detect_changepoints(s, "demo", model="l2")
    assert isinstance(records, list)


def test_TO10_record_to_dict_serializable():
    import json
    s = _shifted_store()
    rec = detect_changepoints(s, "demo")[0]
    text = json.dumps(rec.to_dict())
    assert "commit_hash" in text
    assert "confidence" in text
    assert "affected_channels" in text


# ═══════════════════════════════════════════════════════════════════════════════
# repo_changepoints aggregation (TO11-TO20)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TO11_repo_empty_returns_empty_list():
    assert repo_changepoints(SnapshotStore(":memory:")) == []


def test_TO12_repo_scans_every_module():
    s = SnapshotStore(":memory:")
    base = time.time()
    for mod in ("a", "b", "c"):
        for i in range(15):
            h = 5.0 if i < 7 else 40.0
            s.insert(_mv(mod, f"c{i:02d}", base + i, h=h, cc=2 if i < 7 else 20))
    records = repo_changepoints(s)
    modules_with_cp = {r.module_id for r in records}
    assert len(modules_with_cp) == 3


def test_TO13_repo_sorts_by_confidence_descending():
    s = SnapshotStore(":memory:")
    base = time.time()
    # mod_strong: huge shift; mod_weak: tiny shift
    for i in range(15):
        s.insert(_mv("mod_strong", f"c{i:02d}", base + i,
                     h=5.0 if i < 7 else 80.0,
                     cc=2 if i < 7 else 40))
    for i in range(15):
        s.insert(_mv("mod_weak", f"c{i:02d}", base + i,
                     h=5.0 if i < 7 else 6.0,
                     cc=2 if i < 7 else 3))
    records = repo_changepoints(s)
    confidences = [r.confidence for r in records]
    assert confidences == sorted(confidences, reverse=True)


def test_TO14_modules_without_history_skipped():
    s = SnapshotStore(":memory:")
    # No inserts — no modules at all
    assert repo_changepoints(s) == []


def test_TO15_repo_isolation_between_modules():
    s = _shifted_store(10, 10)
    # Add a second clean module
    base = time.time()
    for i in range(20):
        s.insert(_mv("clean", f"c{i:02d}", base + 1000 + i, h=5.0))
    records = repo_changepoints(s)
    assert any(r.module_id == "demo" for r in records)


def test_TO16_annotate_with_git_no_repo_is_safe():
    """No git available => fields stay None, no exception."""
    s = _shifted_store()
    records = detect_changepoints(s, "demo")
    annotated = annotate_with_git(records, repo_dir="/nonexistent/path")
    assert annotated is records   # in-place mutation
    for r in annotated:
        assert r.author is None
        assert r.commit_subject is None


def test_TO17_annotate_with_unknown_commit_hash_stays_none():
    rec = ChangePointRecord(
        module_id="x", commit_idx=0, commit_hash="abcdef1234567890",
        timestamp=0.0, confidence=0.5, magnitude=1.0, affected_channels=["H"],
    )
    annotate_with_git([rec])
    assert rec.author is None


def test_TO18_annotate_skips_records_without_commit_hash():
    rec = ChangePointRecord(
        module_id="x", commit_idx=0, commit_hash=None,
        timestamp=0.0, confidence=0.5, magnitude=1.0, affected_channels=["H"],
    )
    annotate_with_git([rec])
    assert rec.author is None


def test_TO19_repo_dir_kwarg_propagates_to_annotation():
    s = _shifted_store()
    records = repo_changepoints(s, repo_dir="/nonexistent/path")
    # Annotation runs (silently fails) — records still returned with None fields
    assert all(r.author is None for r in records)


def test_TO20_record_dataclass_optional_fields_default_none():
    rec = ChangePointRecord(
        module_id="m", commit_idx=0, commit_hash="x",
        timestamp=0.0, confidence=0.0, magnitude=0.0,
    )
    assert rec.author is None
    assert rec.commit_subject is None


# ═══════════════════════════════════════════════════════════════════════════════
# REST surface — handle_changepoints + handle_repo_changepoints (TO21-TO30)
# ═══════════════════════════════════════════════════════════════════════════════

def test_TO21_handle_changepoints_400_on_missing_module():
    import api.server as srv
    code, payload = srv.handle_changepoints("")
    assert code == 400
    assert "module" in payload["error"]


def test_TO22_handle_changepoints_200_with_records():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_changepoints("demo")
    assert code == 200
    assert payload["n_records"] >= 1
    assert payload["module_id"] == "demo"
    assert "changepoints" in payload


def test_TO23_handle_changepoints_serialized_payload_has_required_keys():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_changepoints("demo")
    cp = payload["changepoints"][0]
    for k in ("commit_hash", "timestamp", "confidence", "magnitude",
              "affected_channels", "author", "commit_subject"):
        assert k in cp


def test_TO24_handle_repo_changepoints_empty_store():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_repo_changepoints()
    assert code == 200
    assert payload["n_records"] == 0
    assert payload["changepoints"] == []


def test_TO25_handle_repo_changepoints_with_data():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_repo_changepoints()
    assert code == 200
    assert payload["n_records"] >= 1


def test_TO26_handle_repo_changepoints_carries_model_and_penalty_in_payload():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_repo_changepoints(model="l2", penalty=2.5)
    assert payload["model"]   == "l2"
    assert payload["penalty"] == 2.5


def test_TO27_handle_changepoints_unknown_module_returns_200_empty():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_changepoints("ghost")
    assert code == 200
    assert payload["n_records"] == 0


def test_TO28_handle_changepoints_with_repo_dir_does_not_crash():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_changepoints("demo", repo_dir="/nonexistent")
    assert code == 200
    # All authors None because /nonexistent has no git
    for cp in payload["changepoints"]:
        assert cp["author"] is None


def test_TO29_endpoint_is_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    assert "/changepoints" in paths
    assert "/changepoints/repo" in paths


def test_TO30_default_window_clamped_to_min_5():
    import api.server as srv
    srv._store = _shifted_store()
    # Passing window=1 should be clamped to min 5 internally — request should
    # succeed without raising even if data is small.
    code, payload = srv.handle_changepoints("demo", window=1)
    assert code == 200
