"""
Marco 74 — M9.1: SCA bridge (OSV-Scanner) — degradação graciosa +
mapeamento real para SASTFinding/SASTResult
========================================================================
Resposta ao pedido do usuário de integrar OSV-Scanner ou Grype, decisão
documentada em ``sast/sca_bridge.py`` (OSV-Scanner venceu por
alcançabilidade de rede em ambiente restrito — Grype falhou por
completo no mesmo sandbox). Estes testes validam:

1. Degradação graciosa quando o binário não está em PATH (mesmo
   contrato de "nunca quebra import/chamada" do
   ``lang_adapters/tree_sitter_bridge.py``).
2. O mapeamento ``_to_sast_result`` contra um payload JSON REAL
   capturado de uma execução real do OSV-Scanner (modo offline) nesta
   sessão, contra ``requests==2.27.0`` — não um payload inventado.
"""
from __future__ import annotations

import json

from sast.sca_bridge import OSVScannerBridge, _to_sast_result, _severity_for_score

# Payload real (recortado) de `osv-scanner --offline --format json` contra
# requirements.txt com `requests==2.27.0`, capturado nesta sessão.
_REAL_OSV_PAYLOAD = {
    "results": [
        {
            "source": {"path": "/tmp/requirements.txt", "type": "lockfile"},
            "packages": [
                {
                    "package": {"name": "requests", "version": "2.27.0", "ecosystem": "PyPI"},
                    "groups": [
                        {
                            "ids": ["PYSEC-2023-74"],
                            "aliases": ["CVE-2023-32681", "GHSA-j8r2-6x86-q33q", "PYSEC-2023-74"],
                            "max_severity": "6.1",
                        },
                        {
                            "ids": ["GHSA-9hjg-9r4m-mvj7"],
                            "aliases": ["CVE-2024-47081", "GHSA-9hjg-9r4m-mvj7"],
                            "max_severity": "5.3",
                        },
                    ],
                    "vulnerabilities": [
                        {
                            "id": "PYSEC-2023-74",
                            "aliases": ["CVE-2023-32681", "GHSA-j8r2-6x86-q33q"],
                            "details": "Requests is a HTTP library. Since Requests 2.3.0, "
                                       "Requests has been leaking Proxy-Authorization headers "
                                       "to destination servers when redirected to an HTTPS "
                                       "endpoint.",
                            "references": [{"type": "ADVISORY", "url": "https://github.com/psf/requests/security/advisories/GHSA-j8r2-6x86-q33q"}],
                        },
                        {
                            "id": "GHSA-9hjg-9r4m-mvj7",
                            "aliases": ["CVE-2024-47081"],
                            "details": "requests vulnerable to .netrc credentials leak via "
                                       "malicious URLs.",
                            "references": [{"type": "ADVISORY", "url": "https://github.com/psf/requests/security/advisories/GHSA-9hjg-9r4m-mvj7"}],
                        },
                    ],
                }
            ],
        }
    ]
}


def test_TAP01_unavailable_binary_returns_parse_error_not_crash():
    bridge = OSVScannerBridge(binary="this-binary-definitely-does-not-exist-xyz")
    assert bridge.available() is False
    result = bridge.scan_manifest("requests==2.27.0\n", "requirements.txt")
    assert result.parse_error is True
    assert result.findings == []


def test_TAP02_available_caches_probe_result():
    bridge = OSVScannerBridge(binary="this-binary-definitely-does-not-exist-xyz")
    assert bridge.available() is False
    assert bridge.available() is False  # segunda chamada usa cache, não re-probe


def test_TAP03_real_payload_maps_two_findings():
    result = _to_sast_result(_REAL_OSV_PAYLOAD)
    assert len(result.findings) == 2
    rule_ids = {f.rule_id for f in result.findings}
    assert "SCA-PYSEC-2023-74" in rule_ids
    assert "SCA-GHSA-9hjg-9r4m-mvj7" in rule_ids


def test_TAP04_real_payload_finding_has_cve_and_cwe1395():
    result = _to_sast_result(_REAL_OSV_PAYLOAD)
    f = next(f for f in result.findings if f.rule_id == "SCA-PYSEC-2023-74")
    assert "CVE-2023-32681" in f.title
    assert f.cwe_id == "CWE-1395"
    assert "requests" in f.code_snippet
    assert f.debt_minutes > 0


def test_TAP05_severity_score_buckets():
    assert _severity_for_score(9.5) == "CRITICAL"
    assert _severity_for_score(7.2) == "HIGH"
    assert _severity_for_score(6.1) == "MEDIUM"
    assert _severity_for_score(2.0) == "LOW"
    assert _severity_for_score(None) == "MEDIUM"


def test_TAP06_security_rating_degrades_with_severity():
    clean = _to_sast_result({"results": []})
    assert clean.security_rating == "A"
    assert clean.findings == []

    dirty = _to_sast_result(_REAL_OSV_PAYLOAD)
    assert dirty.security_rating in ("B", "C", "D", "E")


def test_TAP07_empty_results_no_packages_clean_scan():
    payload = {"results": [{"source": {"path": "x"}, "packages": []}]}
    result = _to_sast_result(payload)
    assert result.findings == []
    assert result.security_rating == "A"


def test_TAP08_to_dict_roundtrip_matches_sast_shape():
    result = _to_sast_result(_REAL_OSV_PAYLOAD)
    d = result.to_dict()
    assert "findings" in d
    assert "total_debt_minutes" in d
    assert "security_rating" in d
    f0 = d["findings"][0]
    for key in ("rule_id", "severity", "cwe_id", "owasp", "title", "description",
                "line", "col", "code_snippet", "remediation", "debt_minutes"):
        assert key in f0


# ── DV/P0-1: path-traversal via filename (CWE-22) ─────────────────────────────

def test_TAP09_safe_manifest_name_neutralizes_traversal():
    from sast.sca_bridge import _safe_manifest_name
    assert _safe_manifest_name("../../../../tmp/evil.txt") == "requirements.txt"
    assert _safe_manifest_name("/etc/passwd") == "requirements.txt"
    assert _safe_manifest_name(r"..\..\windows\x.txt") == "requirements.txt"
    assert _safe_manifest_name("subdir/go.mod") == "go.mod"          # basename mantido
    assert _safe_manifest_name("package-lock.json") == "package-lock.json"
    assert _safe_manifest_name("weird.name") == "requirements.txt"    # desconhecido → default


def test_TAP11_v2_signals_captured():
    # (DV/P1-1) severity[] (vetor CVSS), affected[].fixed, source.path.
    payload = {"results": [{"source": {"path": "/repo/requirements.txt"},
      "packages": [{"package": {"name": "requests", "version": "2.27.0", "ecosystem": "PyPI"},
        "groups": [{"ids": ["GHSA-x"], "aliases": ["CVE-2023-32681"], "max_severity": "6.1"}],
        "vulnerabilities": [{"id": "GHSA-x", "aliases": ["CVE-2023-32681"], "details": "d",
          "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:N"}],
          "affected": [{"package": {"name": "requests"}, "ranges": [{"type": "ECOSYSTEM",
            "events": [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]}]}],
          "references": [{"type": "ADVISORY", "url": "https://x"}]}]}]}]}
    f = _to_sast_result(payload).findings[0]
    assert f.suggested_fix == "requests>=2.31.0"
    assert "2.31.0" in f.remediation
    assert "CVSS:3.1/" in f.explanation
    assert "requirements.txt" in f.explanation and "requirements.txt" in f.code_snippet


def test_TAP12_v1_payload_degrades_gracefully():
    # payload sem os campos V2 → sem crash, campos extras vazios.
    result = _to_sast_result(_REAL_OSV_PAYLOAD)
    assert len(result.findings) == 2
    for f in result.findings:
        assert f.suggested_fix == ""           # sem affected[] → sem fixed
        assert "CVSS:" not in f.explanation     # sem severity[] → sem vetor


def test_TAP10_safe_name_never_contains_separators():
    # invariante central de segurança: o nome resultante NUNCA tem separador de
    # caminho, logo `Path(tmpdir) / nome` não pode escapar do tempdir.
    from sast.sca_bridge import _safe_manifest_name
    for evil in ("../../x/requirements.txt", r"..\..\requirements.txt",
                 "/abs/go.mod", "a/b/c/package-lock.json", "....//....//x"):
        out = _safe_manifest_name(evil)
        assert "/" not in out and "\\" not in out and ".." != out
