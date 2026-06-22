"""
Marco 48 — Sprint R: Automated Root-Cause Analysis (TJ01-TJ30)
=================================================================

Orchestrates PELT (Sprint L) + git blame (Sprint L) + cross-channel
causality (Sprint M) into a single pipeline that answers:

  "In which commit did the regime shift, who authored it, which channel
   was the root cause, and what was the lag to the visible effect?"

Coverage layout
---------------
* TJ01-TJ10 — analyze() pure: change-point detection, no-changepoint
  path, error handling, dataclass shape, summary text
* TJ11-TJ20 — root-cause filtering: affected_channels gate, LEADS-only
  direction, primary_root selection, lag propagation
* TJ21-TJ30 — REST: handle_rca, handle_rca_repo, 400/200 paths,
  payload shape, /docs registration
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
from governance.rca import (
    analyze, analyze_repo,
    RCAReport, RCARootCause,
    _build_summary_text,
)


def _mv(module: str, commit: str, ts: float, *,
        h: float = 5.0, cc: int = 2, bugs: float = 0.1,
        di: float = 0.2) -> MetricVector:
    return MetricVector(
        module_id=module, commit_hash=commit, timestamp=ts,
        hamiltonian=h, cyclomatic_complexity=cc,
        infinite_loop_risk=0.0, dsm_density=0.4,
        dsm_cyclic_ratio=0.1, dependency_instability=di,
        syntactic_dead_code=0, duplicate_block_count=0, halstead_bugs=bugs,
    )


def _shifted_store(n: int = 25) -> SnapshotStore:
    """History with regime shift at i=10, CC leading bugs."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        h    = 5.0 if i < 10 else 50.0
        cc   = 2 + (i if i < 10 else 10)
        bugs = 0.1 + max(0, (i - 3) * 0.05)
        di   = 0.2 if i < 12 else 0.7
        s.insert(_mv("demo", f"c{i:02d}", base + i,
                     h=h, cc=cc, bugs=bugs, di=di))
    return s


def _flat_store(n: int = 20) -> SnapshotStore:
    """History with no regime shift."""
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(n):
        s.insert(_mv("flat", f"c{i:02d}", base + i))
    return s


# ═══════════════════════════════════════════════════════════════════════════════
# TJ01-TJ10 — analyze() pure
# ═══════════════════════════════════════════════════════════════════════════════

def test_TJ01_analyze_returns_RCAReport():
    r = analyze(_shifted_store(), "demo")
    assert isinstance(r, RCAReport)


def test_TJ02_analyze_OK_status_on_shifted_history():
    r = analyze(_shifted_store(), "demo")
    assert r.status == "OK"


def test_TJ03_analyze_NO_CHANGEPOINT_on_flat_history():
    r = analyze(_flat_store(), "flat")
    assert r.status == "NO_CHANGEPOINT"


def test_TJ04_analyze_unknown_module_no_changepoint():
    r = analyze(SnapshotStore(":memory:"), "ghost")
    assert r.status == "NO_CHANGEPOINT"


def test_TJ05_analyze_carries_commit_hash():
    r = analyze(_shifted_store(), "demo")
    assert r.commit_hash is not None
    assert r.commit_hash.startswith("c")


def test_TJ06_analyze_carries_confidence_and_channels():
    r = analyze(_shifted_store(), "demo")
    assert r.changepoint_confidence > 0.5
    assert len(r.affected_channels) > 0


def test_TJ07_analyze_summary_text_contains_commit_hash():
    r = analyze(_shifted_store(), "demo")
    assert r.commit_hash[:8] in r.summary_text


def test_TJ08_analyze_handles_broken_store_gracefully():
    class Broken:
        def get_history(self, *a, **kw):
            raise RuntimeError("DB exploded")
        def list_modules(self):
            return []
    r = analyze(Broken(), "x")
    assert r.status in {"ERROR", "NO_CHANGEPOINT"}


def test_TJ09_RCAReport_to_dict_serializable():
    import json
    r = analyze(_shifted_store(), "demo")
    text = json.dumps(r.to_dict())
    assert "module_id" in text
    assert "summary_text" in text


def test_TJ10_analyze_module_id_carried_through():
    r = analyze(_shifted_store(), "demo")
    assert r.module_id == "demo"


# ═══════════════════════════════════════════════════════════════════════════════
# TJ11-TJ20 — root-cause filtering
# ═══════════════════════════════════════════════════════════════════════════════

def test_TJ11_root_causes_only_leading_channels_in_affected():
    """Each candidate's root_channel must appear in affected_channels."""
    r = analyze(_shifted_store(), "demo")
    if r.root_causes:
        affected = set(r.affected_channels)
        for rc in r.root_causes:
            assert rc.root_channel in affected


def test_TJ12_primary_root_is_first_candidate():
    r = analyze(_shifted_store(), "demo")
    if r.root_causes:
        assert r.primary_root is r.root_causes[0]


def test_TJ13_root_cause_lag_is_int():
    r = analyze(_shifted_store(), "demo")
    for rc in r.root_causes:
        assert isinstance(rc.lag_to_visible_effect, int)


def test_TJ14_root_cause_correlation_signed():
    r = analyze(_shifted_store(), "demo")
    for rc in r.root_causes:
        assert -1.0 <= rc.correlation <= 1.0


def test_TJ15_no_root_cause_when_flat():
    r = analyze(_flat_store(), "flat")
    assert r.root_causes == []
    assert r.primary_root is None


def test_TJ16_summary_includes_root_cause_when_present():
    r = analyze(_shifted_store(), "demo")
    if r.primary_root:
        assert "Root cause" in r.summary_text


def test_TJ17_summary_omits_root_cause_on_no_changepoint():
    r = analyze(_flat_store(), "flat")
    assert "Root cause" not in r.summary_text


def test_TJ18_RCARootCause_to_dict_includes_all_fields():
    rc = RCARootCause(
        root_channel="H", target_channel="CC",
        correlation=0.9, lag_to_visible_effect=2, confidence=0.5,
    )
    d = rc.to_dict()
    for k in ("root_channel", "target_channel", "correlation",
              "lag_to_visible_effect", "confidence"):
        assert k in d


def test_TJ19_build_summary_text_empty_when_no_primary():
    """Helper with primary=None must still produce a sentence."""
    class DummyCP:
        author = "Alice"
        commit_hash = "abc12345"
        commit_date = "2026-01-01"
        affected_channels = ["H", "CC"]
        confidence = 0.85
    text = _build_summary_text(DummyCP(), None)
    assert "Alice" in text
    assert "abc12345" in text
    assert "Root cause" not in text


def test_TJ20_analyze_top_k_pairs_parameter():
    """top_k_pairs limits the number of root candidates."""
    r1 = analyze(_shifted_store(), "demo", top_k_pairs=1)
    r3 = analyze(_shifted_store(), "demo", top_k_pairs=10)
    assert len(r1.root_causes) <= len(r3.root_causes)


# ═══════════════════════════════════════════════════════════════════════════════
# TJ21-TJ30 — REST + repo-wide
# ═══════════════════════════════════════════════════════════════════════════════

def test_TJ21_handle_rca_400_missing_module():
    import api.server as srv
    code, _ = srv.handle_rca("")
    assert code == 400


def test_TJ22_handle_rca_200_with_payload():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca("demo")
    assert code == 200
    assert payload["status"] in {"OK", "NO_CHANGEPOINT"}


def test_TJ23_handle_rca_payload_contains_summary():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca("demo")
    assert "summary_text" in payload
    assert isinstance(payload["summary_text"], str)


def test_TJ24_handle_rca_unknown_module_returns_no_changepoint():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_rca("ghost")
    assert code == 200
    assert payload["status"] == "NO_CHANGEPOINT"


def test_TJ25_handle_rca_repo_returns_list():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca_repo()
    assert code == 200
    assert "reports" in payload
    assert isinstance(payload["reports"], list)


def test_TJ26_handle_rca_repo_empty_store():
    import api.server as srv
    srv._store = SnapshotStore(":memory:")
    code, payload = srv.handle_rca_repo()
    assert code == 200
    assert payload["n_reports"] == 0


def test_TJ27_handle_rca_repo_top_k_bound():
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca_repo(top_k=0)
    assert payload["n_reports"] == 0


def test_TJ28_handle_rca_repo_sorts_by_confidence_desc():
    import api.server as srv
    # Two modules with regime shifts of different magnitudes
    s = SnapshotStore(":memory:")
    base = time.time()
    for i in range(25):
        # mod_strong: drastic shift
        h_strong = 5.0 if i < 10 else 80.0
        cc_strong = 2 if i < 10 else 40
        s.insert(_mv("mod_strong", f"c{i:02d}", base + i,
                     h=h_strong, cc=cc_strong))
        # mod_mild: smaller shift
        h_mild = 5.0 if i < 10 else 10.0
        cc_mild = 2 if i < 10 else 5
        s.insert(_mv("mod_mild", f"c{i:02d}", base + i,
                     h=h_mild, cc=cc_mild))
    srv._store = s
    code, payload = srv.handle_rca_repo()
    confidences = [r["changepoint_confidence"] for r in payload["reports"]]
    assert confidences == sorted(confidences, reverse=True)


def test_TJ29_handle_rca_with_repo_dir_no_git_safe():
    """Non-existent repo_dir must NOT crash — git silent."""
    import api.server as srv
    srv._store = _shifted_store()
    code, payload = srv.handle_rca("demo", repo_dir="/nonexistent")
    assert code == 200
    assert payload["author"] is None


def test_TJ30_endpoints_registered_in_docs():
    import api.server as srv
    code, docs = srv.handle_docs()
    paths = {ep["path"] for ep in docs["endpoints"]}
    assert "/rca" in paths
    assert "/rca/repo" in paths
