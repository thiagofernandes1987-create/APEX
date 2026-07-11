"""
test_marco_m104.py — Sprint DV: SCA reachability (M9.5, o "salto")
==================================================================
Nível 1 (import-presence): cruza findings SCA com os imports reais do repo e
rebaixa/anota os pacotes não importados (VEX vulnerable_code_not_reachable).
"""
from __future__ import annotations

import sys
from pathlib import Path

_SENSOR = Path(__file__).resolve().parent.parent
if str(_SENSOR) not in sys.path:
    sys.path.insert(0, str(_SENSOR))

from sca.reachability import (  # noqa: E402
    extract_imported_modules, reachability_verdict, import_names_for_package,
    annotate_findings,
)


_SRC = {
    "app.py": "import requests\nfrom yaml import safe_load\nimport os\n",
    "web.js": "const lodash = require('lodash');\nimport foo from '@scope/pkg/x';\n",
    "rel.py": "from . import sibling\nfrom .mod import thing\n",   # relativos ignorados
}


def test_TDV_extract_imports_py_and_js():
    imp = extract_imported_modules(_SRC)
    assert {"requests", "yaml", "os", "lodash", "@scope/pkg"} <= imp
    assert "sibling" not in imp and "mod" not in imp   # relativos não contam


def test_TDV_dist_to_import_mapping():
    assert "yaml" in import_names_for_package("PyYAML")
    assert "bs4" in import_names_for_package("beautifulsoup4")
    # maven group:artifact → último segmento
    assert "jackson_databind" in import_names_for_package(
        "com.fasterxml.jackson.core:jackson-databind")


def test_TDV_verdict_imported():
    imp = extract_imported_modules(_SRC)
    assert reachability_verdict("requests", "PyPI", imp) == "imported"
    assert reachability_verdict("PyYAML", "PyPI", imp) == "imported"   # via yaml
    assert reachability_verdict("lodash", "npm", imp) == "imported"


def test_TDV_verdict_not_imported():
    imp = extract_imported_modules(_SRC)
    assert reachability_verdict("django", "PyPI", imp) == "not_imported"


def test_TDV_verdict_unknown_without_source():
    # None (sem fonte) NUNCA rebaixa às cegas.
    assert reachability_verdict("django", "PyPI", None) == "unknown"


class _Finding:
    def __init__(self, snippet, severity="CRITICAL", conf=0.95):
        self.code_snippet = snippet
        self.severity = severity
        self.confidence = conf
        self.explanation = ""


def test_TDV_annotate_downgrades_not_imported():
    f = _Finding("req.txt: django==3.1.0")
    annotate_findings([f], _SRC)
    assert f.reachability == "not_imported"
    assert f.severity == "MEDIUM"                 # CRITICAL rebaixado
    assert f.confidence < 0.5
    assert "not_reachable" in f.explanation


def test_TDV_annotate_keeps_imported():
    f = _Finding("req.txt: requests==2.27.0")
    annotate_findings([f], _SRC)
    assert f.reachability == "imported"
    assert f.severity == "CRITICAL"               # mantém
    assert f.confidence == 0.95


def test_TDV_annotate_unknown_without_source_does_not_downgrade():
    f = _Finding("req.txt: django==3.1.0")
    annotate_findings([f], None)
    assert f.reachability == "unknown"
    assert f.severity == "CRITICAL"               # sem fonte → não rebaixa
    assert f.confidence == 0.95


# ── DV/P2: SBOM CycloneDX ─────────────────────────────────────────────────────

def test_TDV_sbom_cyclonedx_shape_and_purl():
    import json
    from sca.vulnerability_scanner import VulnerabilityScanner
    from report.sbom import to_cyclonedx, _purl
    r = VulnerabilityScanner().scan_files({"requirements.txt": "requests==2.25.0\n"})
    bom = to_cyclonedx(r, timestamp="2026-07-10T00:00:00Z", serial_number="urn:uuid:x")
    assert bom["bomFormat"] == "CycloneDX" and bom["specVersion"] == "1.5"
    assert bom["components"][0]["purl"] == "pkg:pypi/requests@2.25.0"
    assert bom["components"][0]["type"] == "library"
    assert bom["metadata"]["timestamp"] == "2026-07-10T00:00:00Z"
    json.dumps(bom)   # válido


def test_TDV_sbom_purl_ecosystems():
    from report.sbom import _purl
    assert _purl("lodash", "4.17.11", "npm") == "pkg:npm/lodash@4.17.11"
    assert _purl("serde", "1.0", "cargo") == "pkg:cargo/serde@1.0"
    assert (_purl("com.fasterxml.jackson.core:jackson-databind", "2.9", "maven")
            == "pkg:maven/com.fasterxml.jackson.core/jackson-databind@2.9")


def test_TDV_sbom_vulnerability_block():
    from sca.vulnerability_scanner import VulnerabilityScanner
    from report.sbom import to_cyclonedx
    # django 3.1.0 tem CVE conhecido no _CVE_DB
    r = VulnerabilityScanner().scan_files({"requirements.txt": "django==3.1.0\n"})
    bom = to_cyclonedx(r)
    if r.findings:   # só assere o bloco se o DB embarcado tiver o CVE
        assert "vulnerabilities" in bom
        v = bom["vulnerabilities"][0]
        assert v["id"].startswith("CVE-") or v["id"]
        assert v["ratings"][0]["severity"] in ("critical", "high", "medium", "low", "unknown")
        assert v["affects"][0]["ref"].startswith("pkg:")


def test_TDV_sbom_deterministic_without_timestamp():
    # sem timestamp/serial → campos omitidos, saída reproduzível.
    from sca.vulnerability_scanner import VulnerabilityScanner
    from report.sbom import to_cyclonedx
    r = VulnerabilityScanner().scan_files({"requirements.txt": "requests==2.25.0\n"})
    b1 = to_cyclonedx(r)
    b2 = to_cyclonedx(r)
    assert b1 == b2
    assert "timestamp" not in b1["metadata"] and "serialNumber" not in b1
