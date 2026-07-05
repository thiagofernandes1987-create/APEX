"""
Marco 95 — M23: Advisory Harvester (advisory OSV → registro de degradação)
==========================================================================
O `AdvisoryHarvester` (M23) processa o canal estruturado que estávamos captando
e não processando: o GitHub Advisory Database (formato OSV, acessível via
`raw.githubusercontent.com`).  De um advisory ele extrai, com DADO REAL:
  * CVE↔GHSA (aliases);
  * `introduced` (quando quebrou) e `fixed` (em qual versão resolveu);
  * commit do fix + tag de release (âncoras para o before/after do M12);
  * CWE + pacote/ecossistema.

Fixtures = RECORTES REAIS dos advisories buscados nesta sessão via raw
(GHSA-h5c8-rqwp-cp95 jinja / GHSA-j8r2-6x86-q33q requests), preservando os
campos que o parser consome — nenhum dado inventado.
"""
from __future__ import annotations

from scan.advisory_harvester import (
    parse_advisory, AdvisoryRecord, advisory_raw_url, parse_cvss_vector,
)

# ── recorte real do advisory do jinja (CVE-2024-22195) ───────────────────────
_JINJA = """
{
  "id": "GHSA-h5c8-rqwp-cp95",
  "aliases": ["CVE-2024-22195"],
  "summary": "Jinja vulnerable to HTML attribute injection when passing user input as keys to xmlattr filter",
  "affected": [{
    "package": {"ecosystem": "PyPI", "name": "jinja2"},
    "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.1.3"}]}]
  }],
  "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N"}],
  "references": [
    {"type": "WEB", "url": "https://github.com/pallets/jinja/security/advisories/GHSA-h5c8-rqwp-cp95"},
    {"type": "WEB", "url": "https://github.com/pallets/jinja/commit/716795349a41d4983a9a4771f7d883c96ea17be7"},
    {"type": "WEB", "url": "https://github.com/pallets/jinja/releases/tag/3.1.3"}
  ],
  "database_specific": {"cwe_ids": ["CWE-79", "CWE-80"], "severity": "MODERATE"}
}
"""

# ── recorte real do advisory do requests (CVE-2023-32681) ────────────────────
_REQUESTS = """
{
  "id": "GHSA-j8r2-6x86-q33q",
  "aliases": ["CVE-2023-32681"],
  "summary": "Unintended leak of Proxy-Authorization header in requests",
  "affected": [{
    "package": {"ecosystem": "PyPI", "name": "requests"},
    "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]}]
  }],
  "references": [
    {"type": "WEB", "url": "https://github.com/psf/requests/commit/74ea7cf7a6a27a4eeb2ae24e162bcc942a6706d5"}
  ],
  "database_specific": {"cwe_ids": ["CWE-200"], "severity": "MODERATE"}
}
"""


def test_T95_jinja_when_broke_and_resolved():
    rec = parse_advisory(_JINJA)
    assert isinstance(rec, AdvisoryRecord)
    assert rec.cve == "CVE-2024-22195"
    assert rec.package == "jinja2" and rec.ecosystem == "PyPI"
    # quando quebrou / em qual versão resolveu — as duas perguntas do goal
    assert rec.introduced == "0"
    assert rec.fixed == "3.1.3"
    assert "introdução" in rec.when_broke
    assert rec.resolved_in == "versão 3.1.3"


def test_T95_jinja_fix_commit_and_tag():
    rec = parse_advisory(_JINJA)
    assert rec.fix_commit == "716795349a41d4983a9a4771f7d883c96ea17be7"
    assert rec.fix_tag == "3.1.3"
    assert rec.cwe_ids == ["CWE-79", "CWE-80"]
    assert rec.has_version_pair


def test_T95_requests_introduced_range():
    rec = parse_advisory(_REQUESTS)
    assert rec.cve == "CVE-2023-32681"
    assert rec.introduced == "2.3.0" and rec.fixed == "2.31.0"
    assert rec.fix_commit == "74ea7cf7a6a27a4eeb2ae24e162bcc942a6706d5"
    # sem reference de release/tag → cai para a própria versão fixed como tag
    assert rec.fix_tag == "2.31.0"
    assert rec.cwe_ids == ["CWE-200"]


def test_T95_malformed_json_returns_none():
    assert parse_advisory("{not valid json") is None
    assert parse_advisory(12345) is None
    assert parse_advisory("{}") is None  # sem id nem package → inútil


def test_T95_dict_input_accepted():
    rec = parse_advisory({"id": "GHSA-x", "affected": [
        {"package": {"name": "p", "ecosystem": "npm"},
         "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "1.0.0"}, {"fixed": "1.2.0"}]}]}]})
    assert rec is not None and rec.package == "p" and rec.fixed == "1.2.0"


def test_T95_git_range_supplies_commit():
    # range GIT traz SHAs de introduced/fixed direto do repo → fix_commit.
    rec = parse_advisory({"id": "GHSA-y", "affected": [
        {"package": {"name": "lib", "ecosystem": "Go"},
         "ranges": [{"type": "GIT", "events": [
             {"introduced": "0"},
             {"fixed": "abcdef1234567890abcdef1234567890abcdef12"}]}]}]})
    assert rec.fix_commit == "abcdef1234567890abcdef1234567890abcdef12"
    assert rec.git_fixed == "abcdef1234567890abcdef1234567890abcdef12"


def test_T95_raw_url_construction():
    url = advisory_raw_url("GHSA-h5c8-rqwp-cp95", "2024", "01")
    assert url.endswith(
        "github-reviewed/2024/01/GHSA-h5c8-rqwp-cp95/GHSA-h5c8-rqwp-cp95.json")
    assert url.startswith("https://raw.githubusercontent.com/github/advisory-database/")


def test_T95_no_fixed_version_handled():
    rec = parse_advisory({"id": "GHSA-z", "affected": [
        {"package": {"name": "p", "ecosystem": "PyPI"},
         "ranges": [{"type": "ECOSYSTEM", "events": [{"introduced": "0"}]}]}]})
    assert rec is not None
    assert rec.fixed == ""
    assert not rec.has_version_pair
    assert "desconhecida" in rec.resolved_in


# ── Sprint DS: vetor CVSS completo (Diretriz #8 / relatorio #2) ───────────────

def test_TDS_jinja_captures_cvss_vector_and_label():
    # o rótulo (MODERATE) NÃO deve mais engolir o vetor CVSS — ambos capturados.
    rec = parse_advisory(_JINJA)
    assert rec.severity == "MODERATE"
    assert rec.cvss_vector == "CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N"


def test_TDS_parse_cvss_vector_axes():
    axes = parse_cvss_vector("CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N")
    assert axes["attack_vector"] == "NETWORK"
    assert axes["attack_complexity"] == "LOW"
    assert axes["privileges_required"] == "NONE"
    assert axes["user_interaction"] == "REQUIRED"
    assert axes["scope"] == "UNCHANGED"
    assert axes["confidentiality"] == "LOW"
    assert axes["integrity"] == "LOW"
    assert axes["availability"] == "NONE"


def test_TDS_parse_cvss_vector_malformed_is_empty():
    assert parse_cvss_vector("") == {}
    assert parse_cvss_vector("MODERATE") == {}          # rótulo, não vetor
    assert parse_cvss_vector("garbage/without/prefix") == {}


def test_TDS_cvss_vector_absent_when_only_label():
    # advisory sem o array `severity[].score` → cvss_vector fica vazio (honesto).
    rec = parse_advisory(_REQUESTS)
    assert rec.severity == "MODERATE"
    assert rec.cvss_vector == ""


def test_TDS_cvss_vector_flows_into_to_dict():
    rec = parse_advisory(_JINJA)
    assert rec.to_dict()["cvss_vector"].startswith("CVSS:3.1/")
