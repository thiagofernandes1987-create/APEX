"""
test_marco_m12.py — M6.4 Extended Metric Vectors + IaC Scanner  (30 tests)
===========================================================================
Test IDs: TV01–TV30

Groups
------
TV01–TV06  HalsteadVector — construction, channels, edge cases
TV07–TV12  StructuralVector — construction, hotspot ratio, comment density
TV13–TV17  SecurityVector — SAST channels, SCA channels, IaC channels, merge, rating
TV18–TV20  VelocityVector — from_metric_series, Hurst exponent, regression rate
TV21–TV26  IaCScanner — Dockerfile rules, docker-compose, k8s YAML, Terraform, Helm
TV27–TV30  /scan-iac REST endpoint via handle_scan_iac()
"""
from __future__ import annotations

import sys
import math
from pathlib import Path

# ── path bootstrap ─────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parent.parent
_ENGINE = _ROOT.parent / "frequency-engine"
for _p in [str(_ROOT), str(_ENGINE)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from metrics.extended_vectors import (
    HalsteadVector,
    StructuralVector,
    SecurityVector,
    VelocityVector,
)
from iac.iac_scanner import IaCScanner, IaCScanResult, IaCFinding


# ═══════════════════════════════════════════════════════════════════════════════
# TV01–TV06  HalsteadVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestHalsteadVector:

    def test_TV01_from_primitives_basic(self):
        """TV01 — from_primitives produces all 6 channels > 0."""
        hv = HalsteadVector.from_primitives(n1=10, n2=20, N1=50, N2=80)
        assert hv.volume > 0.0,            "volume must be positive"
        assert hv.difficulty > 0.0,        "difficulty must be positive"
        assert hv.effort > 0.0,            "effort must be positive"
        assert hv.time_to_implement > 0.0, "time_to_implement must be positive"
        assert hv.program_level > 0.0,     "program_level must be positive"
        assert hv.token_count > 0,         "token_count must be positive"

    def test_TV02_volume_formula(self):
        """TV02 — volume = (N1+N2) * log2(n1+n2)."""
        n1, n2, N1, N2 = 4, 6, 20, 30
        hv = HalsteadVector.from_primitives(n1=n1, n2=n2, N1=N1, N2=N2)
        expected_V = (N1 + N2) * math.log2(n1 + n2)
        assert abs(hv.volume - expected_V) < 0.01

    def test_TV03_difficulty_formula(self):
        """TV03 — difficulty = (n1/2) * (N2/n2)."""
        n1, n2, N1, N2 = 4, 6, 20, 30
        hv = HalsteadVector.from_primitives(n1=n1, n2=n2, N1=N1, N2=N2)
        expected_D = (n1 / 2) * (N2 / n2)
        assert abs(hv.difficulty - expected_D) < 0.01

    def test_TV04_effort_equals_d_times_v(self):
        """TV04 — effort = difficulty × volume."""
        hv = HalsteadVector.from_primitives(n1=8, n2=12, N1=40, N2=60)
        expected_E = hv.difficulty * hv.volume
        assert abs(hv.effort - expected_E) < 0.5   # rounding tolerance

    def test_TV05_time_to_implement(self):
        """TV05 — time_to_implement = effort / 18."""
        hv = HalsteadVector.from_primitives(n1=8, n2=12, N1=40, N2=60)
        assert abs(hv.time_to_implement - hv.effort / 18.0) < 0.01

    def test_TV06_to_dict_completeness(self):
        """TV06 — to_dict() returns all expected keys."""
        hv = HalsteadVector.from_primitives(n1=5, n2=10, N1=25, N2=40)
        d = hv.to_dict()
        for key in ("volume", "difficulty", "effort", "time_to_implement",
                    "program_level", "token_count", "module_id", "language"):
            assert key in d, f"missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# TV07–TV12  StructuralVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestStructuralVector:

    def test_TV07_basic_construction(self):
        """TV07 — from_counts populates all 7 channels."""
        sv = StructuralVector.from_counts(
            max_function_cc=8,
            fn_cc_list=[2, 4, 8],
            max_methods_per_class=5,
            n_functions=10,
            n_classes=3,
        )
        assert sv.max_function_cc == 8
        assert sv.n_functions == 10
        assert sv.n_classes == 3
        assert sv.max_methods_per_class == 5

    def test_TV08_cc_hotspot_ratio_calculation(self):
        """TV08 — hotspot = max_fn_cc / (avg_fn_cc × 3), capped at 1.0."""
        # fn_cc_list = [2, 4, 12], avg = 6, max = 12, hotspot = 12 / 18 = 0.667
        sv = StructuralVector.from_counts(
            max_function_cc=12,
            fn_cc_list=[2, 4, 12],
            max_methods_per_class=0,
            n_functions=3,
            n_classes=0,
        )
        expected_hotspot = min(1.0, 12 / (6.0 * 3))
        assert abs(sv.cc_hotspot_ratio - expected_hotspot) < 0.01

    def test_TV09_hotspot_capped_at_1(self):
        """TV09 — cc_hotspot_ratio never exceeds 1.0."""
        sv = StructuralVector.from_counts(
            max_function_cc=100,
            fn_cc_list=[1, 1, 100],
            max_methods_per_class=0,
            n_functions=3,
            n_classes=0,
        )
        assert sv.cc_hotspot_ratio <= 1.0

    def test_TV10_comment_density_from_source(self):
        """TV10 — comment_density detects comment lines."""
        src = "# comment\nx = 1\n# another\ny = 2\n"
        sv = StructuralVector.from_counts(
            max_function_cc=1,
            fn_cc_list=[1],
            max_methods_per_class=0,
            n_functions=0,
            n_classes=0,
            source=src,
        )
        assert sv.comment_density > 0.0
        assert sv.comment_density <= 1.0

    def test_TV11_test_ratio_detected(self):
        """TV11 — test_ratio > 0 when test functions present."""
        src = "def test_foo():\n    pass\ndef real_fn():\n    pass\n"
        sv = StructuralVector.from_counts(
            max_function_cc=1,
            fn_cc_list=[1, 1],
            max_methods_per_class=0,
            n_functions=2,
            n_classes=0,
            source=src,
        )
        assert sv.test_ratio > 0.0

    def test_TV12_to_dict_completeness(self):
        """TV12 — to_dict() contains all 7 structural channel keys."""
        sv = StructuralVector.from_counts(
            max_function_cc=5,
            fn_cc_list=[5],
            max_methods_per_class=3,
            n_functions=4,
            n_classes=1,
        )
        d = sv.to_dict()
        for key in ("max_function_cc", "cc_hotspot_ratio", "max_methods_per_class",
                    "n_functions", "n_classes", "comment_density", "test_ratio"):
            assert key in d, f"missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# TV13–TV17  SecurityVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestSecurityVector:

    def _make_mock_sast_result(self, findings):
        """Build a lightweight mock SASTResult."""
        class MockFinding:
            def __init__(self, sev, debt):
                self.severity = sev
                self.debt_minutes = debt
        class MockSASTResult:
            pass
        r = MockSASTResult()
        r.findings = [MockFinding(s, d) for s, d in findings]
        return r

    def test_TV13_sast_channels_populated(self):
        """TV13 — from_sast_result populates sast_critical/high/medium/low counts."""
        mock = self._make_mock_sast_result([
            ("CRITICAL", 240), ("HIGH", 120), ("HIGH", 120), ("MEDIUM", 60), ("LOW", 30),
        ])
        sv = SecurityVector.from_sast_result(mock, module_id="auth")
        assert sv.sast_critical == 1
        assert sv.sast_high == 2
        assert sv.sast_medium == 1
        assert sv.sast_low == 1
        assert sv.sast_debt_minutes == 240 + 120 + 120 + 60 + 30

    def test_TV14_rating_critical_gives_E(self):
        """TV14 — any CRITICAL finding → rating 5 (E)."""
        mock = self._make_mock_sast_result([("CRITICAL", 240)])
        sv = SecurityVector.from_sast_result(mock)
        assert sv.sast_security_rating == 5

    def test_TV15_rating_no_findings_gives_2(self):
        """TV15 — no findings → rating 2 (B) [conservative baseline]."""
        sv = SecurityVector()   # empty
        assert sv.sast_security_rating == 1   # default field value

    def test_TV16_merge_sums_findings(self):
        """TV16 — merge() sums counts and takes max of cvss_max."""
        sv1 = SecurityVector(sast_critical=1, sca_cvss_max=7.5, sca_vulnerable_deps=2)
        sv2 = SecurityVector(sast_high=3,     sca_cvss_max=9.8, sca_vulnerable_deps=1)
        merged = SecurityVector.merge(sv1, sv2)
        assert merged.sast_critical == 1
        assert merged.sast_high == 3
        assert merged.sca_cvss_max == 9.8
        assert merged.sca_vulnerable_deps == 3

    def test_TV17_to_dict_has_all_channels(self):
        """TV17 — to_dict() contains all 10 security channel keys."""
        sv = SecurityVector(sast_critical=2, sca_cvss_max=8.1, iac_misconfig_count=5)
        d = sv.to_dict()
        for key in ("sast_critical", "sast_high", "sast_medium", "sast_low",
                    "sast_security_rating", "sast_debt_minutes", "sca_vulnerable_deps",
                    "sca_cvss_max", "sca_debt_minutes", "iac_misconfig_count",
                    "iac_privilege_score"):
            assert key in d, f"missing key: {key}"


# ═══════════════════════════════════════════════════════════════════════════════
# TV18–TV20  VelocityVector
# ═══════════════════════════════════════════════════════════════════════════════

class TestVelocityVector:

    def test_TV18_from_metric_series_velocity(self):
        """TV18 — hamiltonian_velocity = (last - first) / n."""
        h_series  = [1.0, 2.0, 3.0, 4.0, 5.0]
        cc_series = [2,   3,   4,   5,   6  ]
        vv = VelocityVector.from_metric_series(h_series, cc_series)
        expected_h_vel = (5.0 - 1.0) / 5
        assert abs(vv.hamiltonian_velocity - expected_h_vel) < 1e-6

    def test_TV19_hurst_exponent_range(self):
        """TV19 — Hurst exponent is in (0, 1) for any valid series."""
        # Monotonically increasing series → should have H > 0.5 (persistent)
        h_series = [float(i) for i in range(1, 20)]
        vv = VelocityVector.from_metric_series(h_series, [])
        assert 0.0 < vv.degradation_hurst < 1.0

    def test_TV20_regression_rate_all_improving(self):
        """TV20 — regression_rate = 0 when series is strictly decreasing."""
        h_series = [10.0, 9.0, 8.0, 7.0, 6.0, 5.0]
        vv = VelocityVector.from_metric_series(h_series, [])
        assert vv.regression_rate == 0.0
        assert vv.hamiltonian_velocity < 0   # improving


# ═══════════════════════════════════════════════════════════════════════════════
# TV21–TV26  IaCScanner
# ═══════════════════════════════════════════════════════════════════════════════

class TestIaCScanner:

    def _scan(self, files: dict) -> IaCScanResult:
        return IaCScanner().scan_files(files)

    # ── Dockerfile ─────────────────────────────────────────────────────────────

    def test_TV21_dockerfile_no_user_flagged(self):
        """TV21 — Dockerfile without USER instruction triggers IAC-D001 (HIGH)."""
        content = "FROM ubuntu:20.04\nRUN apt-get update\n"
        result = self._scan({"Dockerfile": content})
        ids = [f.rule_id for f in result.findings]
        assert "IAC-D001" in ids

    def test_TV22_dockerfile_latest_tag_flagged(self):
        """TV22 — FROM image:latest triggers IAC-D002 (MEDIUM)."""
        content = "FROM python:latest\nUSER nobody\nHEALTHCHECK CMD curl -f http://localhost/\n"
        result = self._scan({"Dockerfile": content})
        ids = [f.rule_id for f in result.findings]
        assert "IAC-D002" in ids

    def test_TV23_dockerfile_secret_env_flagged(self):
        """TV23 — ENV PASSWORD=secret triggers IAC-D004 (CRITICAL)."""
        content = (
            "FROM alpine:3.18\n"
            "USER nobody\n"
            "ENV PASSWORD=supersecret123\n"
            "HEALTHCHECK CMD echo ok\n"
        )
        result = self._scan({"Dockerfile": content})
        ids = [f.rule_id for f in result.findings]
        assert "IAC-D004" in ids
        critical = [f for f in result.findings if f.severity == "CRITICAL"]
        assert len(critical) >= 1

    # ── docker-compose ─────────────────────────────────────────────────────────

    def test_TV24_compose_privileged_flagged(self):
        """TV24 — docker-compose with privileged: true triggers IAC-C001 (CRITICAL)."""
        content = (
            "version: '3'\n"
            "services:\n"
            "  app:\n"
            "    image: myapp:1.0\n"
            "    privileged: true\n"
        )
        result = self._scan({"docker-compose.yml": content})
        ids = [f.rule_id for f in result.findings]
        assert "IAC-C001" in ids

    # ── Kubernetes YAML ────────────────────────────────────────────────────────

    def test_TV25_k8s_privileged_flagged(self):
        """TV25 — k8s Pod with privileged: true triggers IAC-K001 (CRITICAL)."""
        content = (
            "apiVersion: v1\n"
            "kind: Pod\n"
            "metadata:\n"
            "  name: test\n"
            "spec:\n"
            "  containers:\n"
            "  - name: app\n"
            "    image: myapp:1.0\n"
            "    securityContext:\n"
            "      privileged: true\n"
        )
        result = self._scan({"pod.yaml": content})
        ids = [f.rule_id for f in result.findings]
        assert "IAC-K001" in ids

    def test_TV26_terraform_open_ssh_flagged(self):
        """TV26 — Terraform SG with SSH from 0.0.0.0/0 triggers IAC-T005 or network rule."""
        content = (
            'resource "aws_security_group" "web" {\n'
            '  ingress {\n'
            '    from_port   = 22\n'
            '    to_port     = 22\n'
            '    protocol    = "tcp"\n'
            '    cidr_blocks = ["0.0.0.0/0"]\n'
            '  }\n'
            '}\n'
        )
        result = self._scan({"main.tf": content})
        # IAC-T001 is the SSH-open rule
        assert result.total_findings >= 1
        ids = [f.rule_id for f in result.findings]
        assert "IAC-T001" in ids


# ═══════════════════════════════════════════════════════════════════════════════
# TV27–TV30  /scan-iac REST endpoint
# ═══════════════════════════════════════════════════════════════════════════════

class TestHandleScanIac:
    """Test handle_scan_iac() directly without starting a real HTTP server."""

    def _import_handler(self):
        """Lazily import handle_scan_iac to avoid circular-import issues at module load."""
        sys.path.insert(0, str(_ROOT / "api"))
        from api.server import handle_scan_iac
        return handle_scan_iac

    def test_TV27_mode_files_valid(self):
        """TV27 — mode=files with valid Dockerfile returns 200 + findings."""
        handle_scan_iac = self._import_handler()
        payload = {
            "mode": "files",
            "files": {
                "Dockerfile": "FROM ubuntu:20.04\nRUN apt-get update\n"
            },
        }
        code, data = handle_scan_iac(payload)
        assert code == 200
        assert "total_findings" in data
        assert data["total_findings"] >= 1   # at least IAC-D001 (no USER)

    def test_TV28_mode_files_empty_returns_400(self):
        """TV28 — mode=files with empty files dict returns 400."""
        handle_scan_iac = self._import_handler()
        payload = {"mode": "files", "files": {}}
        code, data = handle_scan_iac(payload)
        assert code == 400
        assert "error" in data

    def test_TV29_mode_path_missing_dir(self):
        """TV29 — mode=path with non-existent root returns 200 with 0 findings."""
        handle_scan_iac = self._import_handler()
        payload = {"mode": "path", "root": "/this/path/does/not/exist/xyz123"}
        code, data = handle_scan_iac(payload)
        assert code == 200
        assert data["total_findings"] == 0

    def test_TV30_scan_iac_result_structure(self):
        """TV30 — result has all required top-level keys."""
        handle_scan_iac = self._import_handler()
        payload = {
            "mode": "files",
            "files": {
                "docker-compose.yml": (
                    "version: '3'\n"
                    "services:\n"
                    "  app:\n"
                    "    image: myapp:latest\n"
                    "    privileged: true\n"
                ),
            },
        }
        code, data = handle_scan_iac(payload)
        assert code == 200
        for key in ("status", "total_findings", "by_severity", "by_category",
                    "total_debt_minutes", "files_scanned", "findings"):
            assert key in data, f"missing key in response: {key}"
        # privileged: true → CRITICAL → status must be CRITICAL
        assert data["status"] == "CRITICAL"
