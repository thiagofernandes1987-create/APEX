"""
Marco 98 — M26: NVD / CVE-Record Harvester (cvelistV5)
======================================================
O `parse_cve_record` (M26) colhe metadados de degradação de CVEs SEM GHSA —
projetos C de servidor (postgres/ffmpeg/sqlite/…) — do CVE Project
(`CVEProject/cvelistV5`) via raw.  Duck-compatível com o AdvisoryRecord (M23)
para o compositor M24 consumir.

Honestidade sobre qualidade de dado (validada com recortes REAIS desta sessão):
  * postgres CVE-2021-32027 → CNA preencheu versões corrigidas (13.3/12.7/…);
  * ffmpeg CVE-2020-22015 → product/versions "n/a" (dado ausente no canal —
    reportado como tal, sem fabricar).
"""
from __future__ import annotations

from scan.nvd_harvester import parse_cve_record, NvdRecord, cve_raw_url

# ── recorte real do cvelistV5 (postgres CVE-2021-32027) ──────────────────────
_PG = """
{
  "cveMetadata": {"cveId": "CVE-2021-32027"},
  "containers": {"cna": {
    "affected": [{"product": "postgresql", "versions": [
      {"status": "affected",
       "version": "postgresql 13.3, postgresql 12.7, postgresql 11.12, postgresql 10.17, postgresql 9.6.22"}]}],
    "references": [
      {"url": "https://www.postgresql.org/support/security/CVE-2021-32027/"},
      {"url": "https://bugzilla.redhat.com/show_bug.cgi?id=1956876"}],
    "descriptions": [{"lang": "en", "value": "Buffer overrun from integer overflow in array subscripting."}]
  }}
}
"""

# ── recorte real ESCASSO (ffmpeg CVE-2020-22015 → tudo n/a) ──────────────────
_FF = """
{
  "cveMetadata": {"cveId": "CVE-2020-22015"},
  "containers": {"cna": {
    "affected": [{"product": "n/a", "versions": [{"status": "affected", "version": "n/a"}]}],
    "problemTypes": [{"descriptions": [{"description": "n/a"}]}],
    "references": [{"url": "https://github.com/FFmpeg/FFmpeg/commit/4c1afa292520"}]
  }}
}
"""


def test_T98_postgres_fixed_versions_extracted():
    rec = parse_cve_record(_PG)
    assert isinstance(rec, NvdRecord)
    assert rec.cve == "CVE-2021-32027"
    assert rec.package == "postgresql"
    # versões corrigidas do texto livre da CNA
    assert rec.fixed_versions == ["13.3", "12.7", "11.12", "10.17", "9.6.22"]
    assert rec.resolved_in.startswith("versão 13.3")
    assert rec.has_version_pair


def test_T98_postgres_when_broke_honest_absence():
    rec = parse_cve_record(_PG)
    # o CVE-record não traz `introduced` → reportado honestamente como ausente
    assert "não disponível" in rec.when_broke


def test_T98_ffmpeg_sparse_record_no_versions():
    rec = parse_cve_record(_FF)
    assert rec.cve == "CVE-2020-22015"
    # product/versions "n/a" → sem versão corrigida (dado ausente, não fabricado)
    assert rec.fixed_versions == []
    assert rec.resolved_in == ""
    assert not rec.has_version_pair
    # mas o commit do fix está nas references
    assert rec.fix_commit == "4c1afa292520"


def test_T98_duck_compatible_with_advisory_record():
    # os campos que o M24 build_degradation consome existem no NvdRecord
    rec = parse_cve_record(_PG)
    for attr in ("cve", "ghsa_id", "package", "ecosystem", "cwe_ids",
                 "fix_commit", "when_broke", "resolved_in"):
        assert hasattr(rec, attr)
    assert rec.ghsa_id == "" and rec.ecosystem == "C/native"


def test_T98_malformed_returns_none():
    assert parse_cve_record("{bad json") is None
    assert parse_cve_record(3.14) is None
    assert parse_cve_record("{}") is None


def test_T98_cve_raw_url_bucket():
    assert cve_raw_url("CVE-2021-32027").endswith("cves/2021/32xxx/CVE-2021-32027.json")
    assert cve_raw_url("CVE-2019-19646").endswith("cves/2019/19xxx/CVE-2019-19646.json")
    # número curto → bucket "0xxx"
    assert cve_raw_url("CVE-2020-123").endswith("cves/2020/0xxx/CVE-2020-123.json")
    assert cve_raw_url("not-a-cve") is None


def test_T98_end_to_end_with_composer():
    # M26 → M24: postgres compõe registro PARCIAL (3/4: falta 'quando').
    from scan.corpus_expander import build_degradation
    rec = parse_cve_record(_PG)
    vuln = "int f(int n){ int a[n]; return a[n+1]; }\n"
    fixed = ("int f(int n){ int a[n];\n"
             "  ArrayCheckBounds(n, a, 0);\n"
             "  return a[n+1]; }\n")
    deg = build_degradation(rec, vuln, fixed, filename="arrayfuncs.c")
    assert deg.resolved_in.startswith("versão 13.3")   # M26
    assert "bounds-check-call" in deg.how_constructs     # M10
    # 'quando' ausente → não é 4/4, mas é registro válido (partial)
    assert not deg.answers_all_four
    assert deg.status in ("partial", "metadata_only")
