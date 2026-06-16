"""
test_marco_m24.py — SCA+ FASE 8: CVE expansion + 3 new ecosystems (30 tests TS31-TS60)
======================================================================================
Validates the SCA+ deliverable (FASE 8 → v3.1.1):

  TS31-TS40: CVE database size + spot-checks across existing ecosystems
  TS41-TS47: New ecosystem registrations (swift / pub / hex)
  TS48-TS54: Manifest parsers (Package.resolved, Podfile.lock, pubspec.lock, mix.lock)
  TS55-TS60: End-to-end scanner integration
"""
from __future__ import annotations

import json
import sys
import textwrap
import unittest
from pathlib import Path

_TESTS_DIR  = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
_ENGINE_DIR = _SENSOR_DIR.parent / "frequency-engine"
for _p in [str(_ENGINE_DIR), str(_SENSOR_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sca.cve_database import (
    database_size, ecosystems, lookup, all_packages, _CVE_DB, _normalize_name,
)
from sca.vulnerability_scanner import VulnerabilityScanner, Dependency


# ══════════════════════════════════════════════════════════════════════════════
# TS31-TS40 — CVE database expansion (target ≥200, 12 ecosystems)
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabaseExpansion(unittest.TestCase):

    def test_TS31_database_size_at_least_200(self):
        """TS31: SCA+ target = 200+ CVEs across all ecosystems."""
        self.assertGreaterEqual(
            database_size(), 200,
            f"SCA+ FASE 8 target ≥200 CVEs, got {database_size()}",
        )

    def test_TS32_twelve_ecosystems(self):
        """TS32: Twelve ecosystems registered (9 original + swift + pub + hex)."""
        ecos = ecosystems()
        self.assertEqual(len(ecos), 12)
        for e in ("pip", "npm", "maven", "cargo", "go", "composer",
                  "gem", "nuget", "gradle", "swift", "pub", "hex"):
            self.assertIn(e, ecos)

    def test_TS33_pip_werkzeug_debugger_rce(self):
        """TS33: CVE-2024-34069 (Werkzeug debugger RCE) hits Werkzeug 3.0.2."""
        hits = lookup("pip", "werkzeug", "3.0.2")
        self.assertIn("CVE-2024-34069", [c.cve_id for c in hits])

    def test_TS34_pip_werkzeug_safe_version(self):
        """TS34: Werkzeug 3.0.3 (fixed) shows no Werkzeug-debugger CVE."""
        hits = [c.cve_id for c in lookup("pip", "werkzeug", "3.0.3")]
        self.assertNotIn("CVE-2024-34069", hits)

    def test_TS35_npm_next_middleware_bypass(self):
        """TS35: Next.js middleware auth bypass (CVE-2025-29927) on 13.4.0."""
        hits = lookup("npm", "next", "13.4.0")
        self.assertTrue(any(c.cve_id == "CVE-2025-29927" for c in hits))

    def test_TS36_maven_snakeyaml_rce(self):
        """TS36: SnakeYAML 1.30 RCE (CVE-2022-1471) — unsafe deserialization."""
        hits = lookup("maven", "org.yaml:snakeyaml", "1.30")
        ids = [c.cve_id for c in hits]
        self.assertIn("CVE-2022-1471", ids)

    def test_TS37_cargo_hyper_smuggling(self):
        """TS37: hyper 0.14.9 HTTP/1 smuggling (RUSTSEC-2021-0079)."""
        hits = [c.cve_id for c in lookup("cargo", "hyper", "0.14.9")]
        self.assertIn("RUSTSEC-2021-0079", hits)

    def test_TS38_go_jwt_aud_bypass(self):
        """TS38: dgrijalva/jwt-go aud bypass (CVE-2020-26160) — empty range = all versions."""
        hits = [c.cve_id for c in lookup(
            "go", "github.com/dgrijalva/jwt-go", "3.2.0",
        )]
        self.assertIn("CVE-2020-26160", hits)

    def test_TS39_gem_rack_path_traversal(self):
        """TS39: Rack::Static path traversal (CVE-2025-27610) on Rack 2.2.10."""
        hits = [c.cve_id for c in lookup("gem", "rack", "2.2.10")]
        self.assertIn("CVE-2025-27610", hits)

    def test_TS40_no_severity_outside_canonical_set(self):
        """TS40: Every CVE severity is CRITICAL/HIGH/MEDIUM/LOW (no typos)."""
        bad = []
        for entries in _CVE_DB.values():
            for c in entries:
                if c.severity not in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                    bad.append((c.cve_id, c.severity))
        self.assertEqual(bad, [], f"Non-canonical severities: {bad}")


# ══════════════════════════════════════════════════════════════════════════════
# TS41-TS47 — New ecosystems (swift / pub / hex)
# ══════════════════════════════════════════════════════════════════════════════

class TestNewEcosystems(unittest.TestCase):

    def test_TS41_swift_alamofire_mitm(self):
        """TS41: Alamofire 5.4.3 trust-evaluation MITM (CVE-2021-31755)."""
        hits = [c.cve_id for c in lookup("swift", "Alamofire", "5.4.3")]
        self.assertIn("CVE-2021-31755", hits)

    def test_TS42_swift_vapor_smuggling(self):
        """TS42: Vapor 4.83.0 request smuggling (CVE-2023-44389)."""
        hits = [c.cve_id for c in lookup("swift", "vapor", "4.83.0")]
        self.assertIn("CVE-2023-44389", hits)

    def test_TS43_pub_dio_cert_bypass(self):
        """TS43: Dart dio 3.0.0 cert-validation bypass (CVE-2021-31402)."""
        hits = [c.cve_id for c in lookup("pub", "dio", "3.0.0")]
        self.assertIn("CVE-2021-31402", hits)

    def test_TS44_pub_http_header_injection(self):
        """TS44: Dart http 0.12.2 header injection (CVE-2020-35669)."""
        hits = [c.cve_id for c in lookup("pub", "http", "0.12.2")]
        self.assertIn("CVE-2020-35669", hits)

    def test_TS45_hex_phoenix_open_redirect(self):
        """TS45: Phoenix 1.6.0 open redirect (CVE-2023-21538)."""
        hits = [c.cve_id for c in lookup("hex", "phoenix", "1.6.0")]
        self.assertIn("CVE-2023-21538", hits)

    def test_TS46_hex_plug_cookie_dos(self):
        """TS46: Plug 1.15.2 cookie-parsing algorithmic DoS (CVE-2024-27284)."""
        hits = [c.cve_id for c in lookup("hex", "plug", "1.15.2")]
        self.assertIn("CVE-2024-27284", hits)

    def test_TS47_swift_normalization_lowercase(self):
        """TS47: Swift normalisation lowercases ``Alamofire``→``alamofire``."""
        self.assertEqual(_normalize_name("swift", "Alamofire"), "alamofire")


# ══════════════════════════════════════════════════════════════════════════════
# TS48-TS54 — Manifest parsers for the 3 new ecosystems
# ══════════════════════════════════════════════════════════════════════════════

class TestNewParsers(unittest.TestCase):

    def setUp(self):
        self.scan = VulnerabilityScanner()

    def test_TS48_parse_package_resolved_v2(self):
        """TS48: Package.resolved v2 (pins at top level)."""
        content = json.dumps({
            "pins": [
                {"identity": "alamofire",
                 "state": {"version": "5.4.0"}},
                {"identity": "swift-nio",
                 "state": {"version": "2.40.0"}},
            ],
        })
        deps = self.scan._parse_package_resolved(content, "Package.resolved")
        names = sorted(d.name for d in deps)
        self.assertEqual(names, ["alamofire", "swift-nio"])
        self.assertTrue(all(d.ecosystem == "swift" for d in deps))

    def test_TS49_parse_package_resolved_v1(self):
        """TS49: Package.resolved v1 (object.pins)."""
        content = json.dumps({
            "object": {
                "pins": [
                    {"package": "Alamofire",
                     "state": {"version": "5.4.3"}},
                ]
            }
        })
        deps = self.scan._parse_package_resolved(content, "Package.resolved")
        self.assertEqual(len(deps), 1)
        self.assertEqual(deps[0].name, "alamofire")
        self.assertEqual(deps[0].version, "5.4.3")

    def test_TS50_parse_podfile_lock(self):
        """TS50: Podfile.lock top-level pods only (sub-specs ignored)."""
        content = textwrap.dedent("""\
            PODS:
              - Alamofire (5.6.4):
                - Alamofire/Core (= 5.6.4)
              - SwiftyJSON (5.0.1)

            DEPENDENCIES:
              - Alamofire
        """)
        deps = self.scan._parse_podfile_lock(content, "Podfile.lock")
        names = sorted(d.name for d in deps)
        self.assertEqual(names, ["alamofire", "swiftyjson"])
        self.assertTrue(all(d.ecosystem == "swift" for d in deps))

    def test_TS51_parse_pubspec_lock(self):
        """TS51: pubspec.lock parses `packages:` → name + version pairs."""
        content = textwrap.dedent("""\
            packages:
              http:
                dependency: "direct main"
                source: hosted
                version: "0.13.6"
              dio:
                dependency: "direct main"
                source: hosted
                version: "5.4.0"
            sdks:
              dart: ">=3.0.0"
        """)
        deps = self.scan._parse_pubspec_lock(content, "pubspec.lock")
        d_map = {d.name: d.version for d in deps}
        self.assertEqual(d_map.get("http"), "0.13.6")
        self.assertEqual(d_map.get("dio"), "5.4.0")
        self.assertTrue(all(d.ecosystem == "pub" for d in deps))

    def test_TS52_parse_mix_lock(self):
        """TS52: mix.lock — extract hex name + version from tuple."""
        content = textwrap.dedent("""\
            %{
              "phoenix": {:hex, :phoenix, "1.6.16", "abcdef0123456789", [:mix], [], "hexpm"},
              "plug": {:hex, :plug, "1.15.2", "deadbeefdeadbeef", [:mix], [], "hexpm"},
            }
        """)
        deps = self.scan._parse_mix_lock(content, "mix.lock")
        d_map = {d.name: d.version for d in deps}
        self.assertEqual(d_map.get("phoenix"), "1.6.16")
        self.assertEqual(d_map.get("plug"), "1.15.2")
        self.assertTrue(all(d.ecosystem == "hex" for d in deps))

    def test_TS53_pubspec_lock_ignores_sdks_block(self):
        """TS53: pubspec.lock parser leaves the ``sdks:`` block alone."""
        content = "packages:\n  http:\n    version: \"0.13.6\"\nsdks:\n  dart: \">=3.0.0\"\n"
        deps = self.scan._parse_pubspec_lock(content, "pubspec.lock")
        names = [d.name for d in deps]
        self.assertEqual(names, ["http"])

    def test_TS54_mix_lock_ignores_non_hex_entries(self):
        """TS54: mix.lock entries not of type :hex (e.g. :git) are skipped."""
        content = '%{"private": {:git, "https://x/y.git", "abc", []}}'
        deps = self.scan._parse_mix_lock(content, "mix.lock")
        self.assertEqual(deps, [])


# ══════════════════════════════════════════════════════════════════════════════
# TS55-TS60 — End-to-end scan integration (manifest → CVE finding)
# ══════════════════════════════════════════════════════════════════════════════

class TestScanIntegration(unittest.TestCase):

    def setUp(self):
        self.scan = VulnerabilityScanner()

    def test_TS55_scan_files_vulnerable_dio(self):
        """TS55: A pubspec.lock with vulnerable dio 3.0.0 → CVE-2021-31402."""
        files = {
            "pubspec.lock": textwrap.dedent("""\
                packages:
                  dio:
                    version: "3.0.0"
            """),
        }
        result = self.scan.scan_files(files)
        cve_ids = {f.cve_id for f in result.findings}
        self.assertIn("CVE-2021-31402", cve_ids)

    def test_TS56_scan_files_vulnerable_phoenix(self):
        """TS56: A mix.lock with vulnerable Phoenix 1.6.0 → CVE-2023-21538."""
        files = {
            "mix.lock": (
                '%{"phoenix": {:hex, :phoenix, "1.6.0", "x", [:mix], [], "hexpm"}}'
            ),
        }
        result = self.scan.scan_files(files)
        cve_ids = {f.cve_id for f in result.findings}
        self.assertIn("CVE-2023-21538", cve_ids)

    def test_TS57_scan_files_vulnerable_alamofire_podfile(self):
        """TS57: A Podfile.lock with vulnerable Alamofire 5.4.0 → CVE-2021-31755."""
        files = {
            "Podfile.lock": (
                "PODS:\n  - Alamofire (5.4.0)\n\nDEPENDENCIES:\n  - Alamofire\n"
            ),
        }
        result = self.scan.scan_files(files)
        cve_ids = {f.cve_id for f in result.findings}
        self.assertIn("CVE-2021-31755", cve_ids)

    def test_TS58_scan_files_clean_pubspec(self):
        """TS58: A pubspec.lock with fixed dio 5.4.0 → no Dart findings."""
        files = {
            "pubspec.lock": "packages:\n  dio:\n    version: \"5.4.0\"\n",
        }
        result = self.scan.scan_files(files)
        dart_findings = [
            f for f in result.findings
            if f.dependency.ecosystem == "pub"
        ]
        self.assertEqual(dart_findings, [])

    def test_TS59_scan_multi_new_ecosystems(self):
        """TS59: One scan over swift+pub+hex manifests aggregates all findings."""
        files = {
            "Package.resolved": json.dumps({
                "pins": [{"identity": "vapor",
                          "state": {"version": "4.83.0"}}],
            }),
            "pubspec.lock": "packages:\n  dio:\n    version: \"3.0.0\"\n",
            "mix.lock": (
                '%{"phoenix": {:hex, :phoenix, "1.6.0", "x", [:mix], [], "hexpm"}}'
            ),
        }
        result = self.scan.scan_files(files)
        cve_ids = {f.cve_id for f in result.findings}
        self.assertIn("CVE-2023-44389", cve_ids)
        self.assertIn("CVE-2021-31402", cve_ids)
        self.assertIn("CVE-2023-21538", cve_ids)

    def test_TS60_status_warning_on_high_finding_in_new_eco(self):
        """TS60: A HIGH severity finding in a new ecosystem trips status to WARNING."""
        # Vapor 4.83.0 has CVE-2023-44389 (HIGH, CVSS 7.5)
        files = {
            "Package.resolved": json.dumps({
                "pins": [{"identity": "vapor",
                          "state": {"version": "4.83.0"}}],
            }),
        }
        result = self.scan.scan_files(files)
        self.assertGreater(len(result.findings), 0)
        self.assertIn(result.status, ("CRITICAL", "WARNING"))


if __name__ == "__main__":
    unittest.main()
