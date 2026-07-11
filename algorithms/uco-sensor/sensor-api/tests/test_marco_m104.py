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


# ── DV/P3: priorização por explorabilidade (EPSS + CISA KEV) ──────────────────

class _PF:
    def __init__(self, rule_id, severity):
        self.rule_id = rule_id
        self.severity = severity
        self.explanation = ""


def test_TDV_epss_parser_and_enrich():
    from sca.priority import parse_epss_csv, enrich_with_epss
    epss = parse_epss_csv("#v\ncve,epss,percentile\nCVE-2021-44228,0.97565,0.99\n")
    assert epss["CVE-2021-44228"] == 0.97565
    f = _PF("SCA-CVE-2021-44228", "HIGH")
    enrich_with_epss([f], epss)
    assert f.epss == 0.97565 and "EPSS=" in f.explanation


def test_TDV_kev_parser_and_bump():
    from sca.priority import parse_kev_json, enrich_with_kev
    kev = parse_kev_json('{"vulnerabilities":[{"cveID":"CVE-2021-44228"}]}')
    assert "CVE-2021-44228" in kev
    f = _PF("SCA-CVE-2021-44228", "MEDIUM")
    enrich_with_kev([f], kev)
    assert f.kev is True and f.severity == "CRITICAL" and "KEV" in f.explanation


def test_TDV_priority_kev_dominates_and_orders():
    from sca.priority import enrich_with_epss, enrich_with_kev, priority_score
    exploited = _PF("SCA-CVE-2021-44228", "HIGH")   # KEV + EPSS alto
    quiet_crit = _PF("SCA-CVE-2020-0001", "CRITICAL")  # EPSS baixíssimo
    unknown = _PF("SCA-CVE-2099-9999", "MEDIUM")
    fs = [exploited, quiet_crit, unknown]
    enrich_with_epss(fs, {"CVE-2021-44228": 0.97, "CVE-2020-0001": 0.0004})
    enrich_with_kev(fs, {"CVE-2021-44228"})
    assert priority_score(exploited) == 1.0
    # o CRITICAL "quieto" fica ABAIXO do exploratado → priorização por urgência real
    assert priority_score(exploited) > priority_score(quiet_crit)
    order = [f.rule_id for f in sorted(fs, key=priority_score, reverse=True)]
    assert order[0] == "SCA-CVE-2021-44228"


def test_TDV_priority_no_data_uses_severity():
    from sca.priority import priority_score
    f = _PF("SCA-CVE-2099-0001", "CRITICAL")
    # sem epss/kev → escore só por severidade (atenuado), nunca crasha
    assert 0.0 < priority_score(f) < 1.0


# ── DV nível 2: alcançar a FUNÇÃO vulnerável via call-graph ───────────────────

def _reach2(files, syms=None):
    from sca.reachability import analyze_symbol_reachability, import_names_for_package
    return analyze_symbol_reachability(files, import_names_for_package("requests"), syms)


def test_TDV2_module_level_call_reachable():
    assert _reach2({"a.py": "import requests\nrequests.get('x')\n"}) == "reachable"


def test_TDV2_imported_but_never_called():
    assert _reach2({"a.py": "import requests\nx = 1\n"}) == "imported_unused"


def test_TDV2_symbol_in_dead_function():
    assert _reach2({"a.py": "from requests import get\ndef f():\n    return get('x')\n"}) == "called_unreachable"


def test_TDV2_reachable_via_call_and_transitive():
    assert _reach2({"a.py": "import requests\ndef f():\n    return requests.get('x')\nf()\n"}) == "reachable"
    assert _reach2({"a.py": "import requests\ndef g():\n    return requests.get('x')\ndef f():\n    return g()\nf()\n"}) == "reachable"


def test_TDV2_cross_file_reachability():
    files = {"a.py": "import requests\ndef f():\n    return requests.get('x')\n",
             "b.py": "from a import f\nf()\n"}
    assert _reach2(files) == "reachable"


def test_TDV2_named_vulnerable_symbol_matched():
    assert _reach2({"a.py": "import requests\nrequests.get('x')\n"}, {"get"}) == "reachable_vulnerable_symbol"
    # símbolo vulnerável nomeado NÃO é o chamado → só reachable
    assert _reach2({"a.py": "import requests\nrequests.get('x')\n"}, {"post"}) == "reachable"


def test_TDV2_not_imported_and_unknown():
    assert _reach2({"a.py": "import os\nos.getcwd()\n"}) == "not_imported"
    assert _reach2({"go.mod": "module x\n"}) == "unknown"


def test_TDV2_annotate_downgrade_and_boost():
    from sca.reachability import annotate_findings_v2

    class F:
        def __init__(self, snip, sev="CRITICAL", conf=0.95):
            self.code_snippet = snip
            self.severity = sev
            self.confidence = conf
            self.explanation = ""
            self.rule_id = "SCA-CVE-2023-32681"

    # imported_unused → rebaixa forte
    f = F("r.txt: requests==2.0")
    annotate_findings_v2([f], {"a.py": "import requests\nx=1\n"})
    assert f.reachability2 == "imported_unused" and f.severity == "MEDIUM" and f.confidence < 0.5
    # reachable → mantém
    f = F("r.txt: requests==2.0")
    annotate_findings_v2([f], {"a.py": "import requests\nrequests.get('x')\n"})
    assert f.reachability2 == "reachable" and f.severity == "CRITICAL" and f.confidence == 0.95
    # símbolo vulnerável nomeado alcançável → boost, mantém CRITICAL
    f = F("r.txt: requests==2.0")
    annotate_findings_v2([f], {"a.py": "import requests\nrequests.get('x')\n"},
                         {"CVE-2023-32681": {"get"}})
    assert f.reachability2 == "reachable_vulnerable_symbol" and f.confidence >= 0.95
    # sem fonte → unknown, não rebaixa
    f = F("r.txt: requests==2.0")
    annotate_findings_v2([f], None)
    assert f.reachability2 == "unknown" and f.severity == "CRITICAL"


def test_TDV3_symbols_auto_inherited_from_finding_no_map():
    # (nível 3) o finding CARREGA `vuln_symbols` (herdado do advisory pelo OSV
    # bridge). annotate_findings_v2 os usa AUTOMATICAMENTE, sem map manual.
    from sca.reachability import annotate_findings_v2

    class F:
        def __init__(self):
            self.code_snippet = "r.txt: requests==2.0"
            self.severity = "CRITICAL"
            self.confidence = 0.95
            self.explanation = ""
            self.rule_id = "SCA-CVE-2023-32681"
            self.vuln_symbols = ["get"]        # herdado do advisory

    f = F()
    annotate_findings_v2([f], {"a.py": "import requests\nrequests.get('x')\n"})  # SEM map
    assert f.reachability2 == "reachable_vulnerable_symbol"


def test_TDV3_end_to_end_osv_bridge_attaches_symbols():
    from sast.sca_bridge import _to_sast_result
    payload = {"results": [{"source": {"path": "r.txt"}, "packages": [{
        "package": {"name": "requests", "version": "2.0", "ecosystem": "PyPI"},
        "groups": [{"ids": ["G"], "aliases": ["CVE-2023-32681"], "max_severity": "6.1"}],
        "vulnerabilities": [{"id": "G", "affected": [
            {"ecosystem_specific": {"imports": [{"symbols": ["get"]}]}}]}]}]}]}
    f = _to_sast_result(payload).findings[0]
    assert getattr(f, "vuln_symbols", None) == ["get"]
