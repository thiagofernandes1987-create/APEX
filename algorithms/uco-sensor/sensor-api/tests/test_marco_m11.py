"""
test_marco_m11.py — M6.3 SCA Dependency Vulnerability Scanner  (30 tests TS01–TS30)
====================================================================================
APEX SCIENTIFIC mode — Software Composition Analysis covering 9 ecosystems,
65+ embedded CVEs, version range matching, and REST endpoint integration.

WBS M6.3: SCA Dependency Vulnerability Scan
  Differentiator: SonarQube Community has NO SCA; requires separate OWASP
  Dependency-Check. UCO-Sensor integrates SCA natively with SQALE debt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ── Path setup ───────────────────────────────────────────────────────────────
_SENSOR_API = Path(__file__).resolve().parent.parent
_ENGINE     = _SENSOR_API.parent / "frequency-engine"
for _p in (str(_ENGINE), str(_SENSOR_API)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sca.cve_database import (
    CVEEntry, lookup, _parse_version, _version_satisfies,
    all_packages, database_size, _normalize_name,
)
from sca.vulnerability_scanner import (
    Dependency, VulnerabilityFinding, SCAResult, VulnerabilityScanner,
)
import api.server as srv


# ── Helpers ───────────────────────────────────────────────────────────────────

def _scanner() -> VulnerabilityScanner:
    return VulnerabilityScanner()


# ════════════════════════════════════════════════════════════════════════════
# Group 1 — CVE database internals (TS01–TS05)
# ════════════════════════════════════════════════════════════════════════════

class TestCVEDatabase:
    """TS01–TS05 — cve_database module: parse, satisfy, lookup."""

    def test_TS01_parse_version_simple(self):
        """TS01: _parse_version produces correct comparable tuples."""
        assert _parse_version("1.2.3")   == (1, 2, 3)
        assert _parse_version("4.17.21") == (4, 17, 21)
        assert _parse_version("v2.0.0")  == (2, 0, 0)
        assert _parse_version("10.0")    == (10, 0)

    def test_TS02_parse_version_edge_cases(self):
        """TS02: _parse_version handles pre-release, epoch, empty."""
        assert _parse_version("2.15.0") == (2, 15, 0)
        assert _parse_version("1.0.0-rc1") == (1, 0, 0)
        assert _parse_version("1.0.0.post1") == (1, 0, 0)
        assert _parse_version("") == (0,)

    def test_TS03_version_satisfies_ranges(self):
        """TS03: _version_satisfies correctly evaluates range constraints."""
        # In range
        assert _version_satisfies("2.10.0", ">=2.0,<2.15.0") is True
        assert _version_satisfies("4.17.11", "<4.17.21")     is True
        assert _version_satisfies("1.0.0", ">=1.0.0")        is True
        # Out of range
        assert _version_satisfies("2.15.0", ">=2.0,<2.15.0") is False
        assert _version_satisfies("4.17.21", "<4.17.21")      is False
        # Empty range = all versions
        assert _version_satisfies("99.0.0", "") is True

    def test_TS04_lookup_known_cve(self):
        """TS04: lookup returns CVEs for known vulnerable package+version."""
        # Log4Shell — log4j 2.14.0 is in range >=2.0,<2.15.0
        results = lookup(
            "maven", "org.apache.logging.log4j:log4j-core", "2.14.0"
        )
        assert len(results) >= 1
        cve_ids = [r.cve_id for r in results]
        assert "CVE-2021-44228" in cve_ids

    def test_TS05_lookup_safe_version_returns_empty(self):
        """TS05: lookup returns empty list for patched version."""
        # log4j 2.17.1 is safe (fixes applied at 2.15.0, 2.16.0, 2.17.0)
        results = lookup(
            "maven", "org.apache.logging.log4j:log4j-core", "2.17.1"
        )
        assert results == []

    def test_TS06_database_size(self):
        """TS06: embedded DB has ≥ 50 CVE entries."""
        assert database_size() >= 50, f"Expected ≥50 CVEs, got {database_size()}"

    def test_TS07_normalize_pip_name(self):
        """TS07: pip package name normalization (PEP 503)."""
        assert _normalize_name("pip", "Flask") == "flask"
        assert _normalize_name("pip", "Pillow") == "pillow"
        assert _normalize_name("pip", "PyYAML") == "pyyaml"
        # underscores and hyphens normalized to hyphen
        assert _normalize_name("pip", "python_dotenv") == "python-dotenv"


# ════════════════════════════════════════════════════════════════════════════
# Group 2 — Data structures (TS08–TS10)
# ════════════════════════════════════════════════════════════════════════════

class TestDataStructures:
    """TS08–TS10 — Dependency, VulnerabilityFinding, SCAResult."""

    def test_TS08_dependency_to_dict(self):
        """TS08: Dependency.to_dict() serializes correctly."""
        dep = Dependency(
            name="lodash", version="4.17.11",
            ecosystem="npm", source_file="package.json",
        )
        d = dep.to_dict()
        assert d["name"]        == "lodash"
        assert d["version"]     == "4.17.11"
        assert d["ecosystem"]   == "npm"
        assert d["source_file"] == "package.json"

    def test_TS09_vulnerability_finding_debt_auto_set(self):
        """TS09: VulnerabilityFinding debt_minutes defaults from severity."""
        dep = Dependency("log4j-core", "2.14.0", "maven", "pom.xml")
        f = VulnerabilityFinding(
            dependency=dep,
            cve_id="CVE-2021-44228",
            severity="CRITICAL",
            cvss_score=10.0,
            description="Log4Shell",
            fixed_version="2.15.0",
            cwe="CWE-917",
        )
        assert f.debt_minutes == 240   # CRITICAL = 240 min

    def test_TS10_sca_result_summary_and_status(self):
        """TS10: SCAResult.summary() and status computed correctly."""
        dep = Dependency("django", "3.1.0", "pip", "requirements.txt")
        finding = VulnerabilityFinding(
            dependency=dep,
            cve_id="CVE-2021-44420",
            severity="HIGH",
            cvss_score=7.3,
            description="SQL injection",
            fixed_version="3.2.10",
            cwe="CWE-89",
        )
        result = SCAResult(
            scanned_files=["requirements.txt"],
            dependencies=[dep],
            findings=[finding],
            total_deps=1,
            vulnerable_deps=1,
            critical_count=0,
            high_count=1,
            medium_count=0,
            low_count=0,
            total_debt_minutes=120,
            status="WARNING",
        )
        assert result.status == "WARNING"
        summary = result.summary()
        assert "WARNING" in summary
        assert "1" in summary   # 1 finding
        d = result.to_dict()
        assert d["high_count"] == 1
        assert len(d["findings"]) == 1


# ════════════════════════════════════════════════════════════════════════════
# Group 3 — Manifest parsers (TS11–TS20)
# ════════════════════════════════════════════════════════════════════════════

class TestParsers:
    """TS11–TS20 — One parser test per key ecosystem."""

    def _s(self) -> VulnerabilityScanner:
        return VulnerabilityScanner()

    def test_TS11_parse_requirements_txt(self):
        """TS11: requirements.txt with pinned and ranged versions."""
        content = (
            "# Production dependencies\n"
            "django==3.1.0\n"
            "requests>=2.25.0,<3.0.0\n"
            "flask==1.1.2\n"
            "  # comment\n"
            "-r base.txt\n"
            "pillow[jpeg]==8.0.0\n"
        )
        deps = self._s()._parse_requirements_txt(content, "requirements.txt")
        names = [d.name.lower() for d in deps]
        assert "django"   in names
        assert "flask"    in names
        assert "pillow"   in names
        # Pinned versions extracted correctly
        django_dep = next(d for d in deps if d.name.lower() == "django")
        assert django_dep.version == "3.1.0"

    def test_TS12_parse_package_json_lodash(self):
        """TS12: package.json extracts lodash 4.17.11 → strips ^ prefix."""
        content = json.dumps({
            "dependencies": {
                "lodash": "^4.17.11",
                "axios": "~0.21.0",
            },
            "devDependencies": {
                "ws": ">=7.4.0",
            }
        })
        deps = self._s()._parse_package_json(content, "package.json")
        names = [d.name for d in deps]
        assert "lodash" in names
        assert "axios"  in names
        assert "ws"     in names
        lodash = next(d for d in deps if d.name == "lodash")
        assert lodash.version == "4.17.11"

    def test_TS13_parse_pom_xml_log4j(self):
        """TS13: pom.xml extracts log4j-core groupId:artifactId:version."""
        content = """<project>
  <dependencies>
    <dependency>
      <groupId>org.apache.logging.log4j</groupId>
      <artifactId>log4j-core</artifactId>
      <version>2.14.0</version>
    </dependency>
    <dependency>
      <groupId>org.springframework</groupId>
      <artifactId>spring-webmvc</artifactId>
      <version>5.3.10</version>
    </dependency>
  </dependencies>
</project>"""
        deps = self._s()._parse_pom_xml(content, "pom.xml")
        coords = [d.name for d in deps]
        assert "org.apache.logging.log4j:log4j-core" in coords
        assert "org.springframework:spring-webmvc"   in coords
        log4j = next(d for d in deps if "log4j-core" in d.name)
        assert log4j.version == "2.14.0"

    def test_TS14_parse_cargo_lock(self):
        """TS14: Cargo.lock extracts exact pinned versions."""
        content = """# This file is automatically @generated by Cargo.
[[package]]
name = "regex"
version = "1.5.4"
source = "registry+https://github.com/rust-lang/crates.io-index"

[[package]]
name = "serde"
version = "1.0.130"
"""
        deps = self._s()._parse_cargo_lock(content, "Cargo.lock")
        names = [d.name for d in deps]
        assert "regex" in names
        assert "serde" in names
        regex_dep = next(d for d in deps if d.name == "regex")
        assert regex_dep.version == "1.5.4"

    def test_TS15_parse_go_mod(self):
        """TS15: go.mod parses both inline and block require forms."""
        content = """module github.com/example/app

go 1.19

require (
    golang.org/x/net v0.3.0
    github.com/gin-gonic/gin v1.8.0
)

require golang.org/x/crypto v0.16.0
"""
        deps = self._s()._parse_go_mod(content, "go.mod")
        names = [d.name for d in deps]
        assert "golang.org/x/net"       in names
        assert "github.com/gin-gonic/gin" in names
        assert "golang.org/x/crypto"    in names
        net_dep = next(d for d in deps if d.name == "golang.org/x/net")
        assert net_dep.version == "0.3.0"

    def test_TS16_parse_composer_json(self):
        """TS16: composer.json extracts require and require-dev."""
        content = json.dumps({
            "require": {
                "php": ">=8.0",
                "laravel/framework": "^8.0",
                "guzzlehttp/guzzle": "^7.0",
            },
            "require-dev": {
                "phpunit/phpunit": "^9.0",
            }
        })
        deps = self._s()._parse_composer_json(content, "composer.json")
        names = [d.name for d in deps]
        assert "laravel/framework"   in names
        assert "guzzlehttp/guzzle"   in names
        # php is skipped
        assert "php" not in names

    def test_TS17_parse_gemfile_lock(self):
        """TS17: Gemfile.lock GEM specs extracted correctly."""
        content = """GEM
  remote: https://rubygems.org/
  specs:
    rails (7.0.2)
    nokogiri (1.13.0-x86_64-linux)
    loofah (2.18.0)
    actionpack (7.0.2)
      rails (~> 7.0.0)

PLATFORMS
  x86_64-linux
"""
        deps = self._s()._parse_gemfile_lock(content, "Gemfile.lock")
        names = [d.name for d in deps]
        assert "rails"    in names
        assert "nokogiri" in names
        assert "loofah"   in names
        rails_dep = next(d for d in deps if d.name == "rails")
        assert rails_dep.version == "7.0.2"

    def test_TS18_parse_packages_config(self):
        """TS18: packages.config NuGet extracts id+version pairs."""
        content = """<?xml version="1.0" encoding="utf-8"?>
<packages>
  <package id="Newtonsoft.Json" version="12.0.3" targetFramework="net6.0" />
  <package id="System.Text.Encodings.Web" version="6.0.0" />
</packages>"""
        deps = self._s()._parse_packages_config(content, "packages.config")
        names = [d.name for d in deps]
        assert "Newtonsoft.Json"           in names
        assert "System.Text.Encodings.Web" in names
        enc = next(d for d in deps if d.name == "System.Text.Encodings.Web")
        assert enc.version == "6.0.0"

    def test_TS19_parse_build_gradle(self):
        """TS19: build.gradle extracts implementation dependencies."""
        content = """
plugins {
    id 'java'
}

dependencies {
    implementation 'org.apache.logging.log4j:log4j-core:2.14.0'
    implementation "org.springframework:spring-webmvc:5.3.10"
    testImplementation 'junit:junit:4.13.2'
}
"""
        deps = self._s()._parse_build_gradle(content, "build.gradle")
        coords = [d.name for d in deps]
        assert "org.apache.logging.log4j:log4j-core" in coords
        assert "org.springframework:spring-webmvc"   in coords
        log4j = next(d for d in deps if "log4j-core" in d.name)
        assert log4j.version == "2.14.0"

    def test_TS20_parse_pyproject_toml_pep621(self):
        """TS20: pyproject.toml PEP 621 [project] dependencies parsed."""
        content = """[build-system]
requires = ["setuptools"]

[project]
name = "myapp"
version = "1.0.0"
dependencies = [
    "django==3.1.0",
    "requests>=2.25.0",
    "flask==2.0.1",
]
"""
        deps = self._s()._parse_pyproject_toml(content, "pyproject.toml")
        names = [d.name.lower() for d in deps]
        assert "django"   in names
        assert "requests" in names
        assert "flask"    in names
        django = next(d for d in deps if d.name.lower() == "django")
        assert django.version == "3.1.0"


# ════════════════════════════════════════════════════════════════════════════
# Group 4 — End-to-end scan_files (TS21–TS25)
# ════════════════════════════════════════════════════════════════════════════

class TestScanFiles:
    """TS21–TS25 — scan_files() with known vulnerable manifests."""

    def test_TS21_scan_log4shell_detected(self):
        """TS21: Log4Shell CVE-2021-44228 detected in pom.xml."""
        pom = """<project>
  <dependencies>
    <dependency>
      <groupId>org.apache.logging.log4j</groupId>
      <artifactId>log4j-core</artifactId>
      <version>2.14.0</version>
    </dependency>
  </dependencies>
</project>"""
        result = VulnerabilityScanner().scan_files({"pom.xml": pom})
        assert result.status == "CRITICAL"
        cve_ids = [f.cve_id for f in result.findings]
        assert "CVE-2021-44228" in cve_ids
        assert result.critical_count >= 1

    def test_TS22_scan_lodash_prototype_pollution(self):
        """TS22: lodash prototype pollution detected in package.json."""
        pkg = json.dumps({
            "dependencies": {"lodash": "4.17.11"}
        })
        result = VulnerabilityScanner().scan_files({"package.json": pkg})
        cve_ids = [f.cve_id for f in result.findings]
        # 4.17.11 is in range <4.17.12 (CVE-2019-10744)
        assert "CVE-2019-10744" in cve_ids

    def test_TS23_scan_clean_deps_returns_stable(self):
        """TS23: Fully patched dependencies return STABLE status."""
        req = "django==4.2.7\nrequests==2.31.0\nflask==2.3.3\n"
        result = VulnerabilityScanner().scan_files({"requirements.txt": req})
        assert result.status == "STABLE"
        assert len(result.findings) == 0

    def test_TS24_scan_multiple_ecosystems(self):
        """TS24: Scanning multiple manifest files across ecosystems."""
        files = {
            "requirements.txt":
                "pyyaml==5.3\ncryptography==3.2.0\n",
            "package.json": json.dumps({
                "dependencies": {"axios": "0.20.0"}
            }),
            "pom.xml": """<project><dependencies>
                <dependency>
                    <groupId>commons-collections</groupId>
                    <artifactId>commons-collections</artifactId>
                    <version>3.2.1</version>
                </dependency>
            </dependencies></project>""",
        }
        result = VulnerabilityScanner().scan_files(files)
        assert result.total_deps >= 4
        assert len(result.scanned_files) == 3
        # pyyaml 5.3 < 5.4 → CVE-2020-14343 (CRITICAL)
        # cryptography 3.2.0 is in >=2.1.4,<3.3.2 → CVE-2020-36242
        # axios 0.20.0 < 0.21.1 → CVE-2020-28168
        # commons-collections 3.2.1 < 3.2.2 → CVE-2015-7501
        cve_ids = {f.cve_id for f in result.findings}
        assert len(cve_ids) >= 3

    def test_TS25_debt_computed_correctly(self):
        """TS25: SQALE debt accumulates correctly across findings."""
        # Log4Shell = CRITICAL = 240 min
        pom = """<project><dependencies>
            <dependency>
                <groupId>org.apache.logging.log4j</groupId>
                <artifactId>log4j-core</artifactId>
                <version>2.14.0</version>
            </dependency>
        </dependencies></project>"""
        result = VulnerabilityScanner().scan_files({"pom.xml": pom})
        # Multiple CVEs for 2.14.0 (44228 + 45046 + 45105)
        assert result.total_debt_minutes >= 240


# ════════════════════════════════════════════════════════════════════════════
# Group 5 — REST endpoint (TS26–TS30)
# ════════════════════════════════════════════════════════════════════════════

class TestScanSCAEndpoint:
    """TS26–TS30 — handle_scan_sca() REST endpoint."""

    def test_TS26_endpoint_files_mode_200(self):
        """TS26: mode='files' with valid content returns 200 SCAResult."""
        req = "pyyaml==5.3\n"
        code, data = srv.handle_scan_sca({
            "mode": "files",
            "files": {"requirements.txt": req},
        })
        assert code == 200
        assert "status"   in data
        assert "findings" in data
        assert "total_deps" in data

    def test_TS27_endpoint_files_mode_detects_cve(self):
        """TS27: endpoint detects CVE-2021-44228 in inline pom.xml."""
        pom = """<project><dependencies>
            <dependency>
                <groupId>org.apache.logging.log4j</groupId>
                <artifactId>log4j-core</artifactId>
                <version>2.14.0</version>
            </dependency>
        </dependencies></project>"""
        code, data = srv.handle_scan_sca({
            "mode": "files",
            "files": {"pom.xml": pom},
        })
        assert code == 200
        assert data["status"] == "CRITICAL"
        cve_ids = [f["cve_id"] for f in data["findings"]]
        assert "CVE-2021-44228" in cve_ids

    def test_TS28_endpoint_missing_files_returns_400(self):
        """TS28: mode='files' with empty files dict returns 400."""
        code, data = srv.handle_scan_sca({
            "mode": "files",
            "files": {},
        })
        assert code == 400
        assert "error" in data

    def test_TS29_endpoint_missing_files_key_returns_400(self):
        """TS29: mode='files' with no 'files' key returns 400."""
        code, data = srv.handle_scan_sca({"mode": "files"})
        assert code == 400
        assert "error" in data

    def test_TS30_endpoint_path_mode_default(self):
        """TS30: mode='path' (default) scans a temp directory cleanly."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            # Write a clean requirements.txt
            req_path = os.path.join(tmp, "requirements.txt")
            with open(req_path, "w") as fh:
                fh.write("django==4.2.7\nrequests==2.31.0\n")
            code, data = srv.handle_scan_sca({"root": tmp})
        assert code == 200
        assert data["status"] == "STABLE"
        assert data["total_deps"] >= 2
