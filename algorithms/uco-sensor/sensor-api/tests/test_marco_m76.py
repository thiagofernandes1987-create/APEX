"""
Marco 76 — M9.3: GHSA Fix-Commit Resolver — localização real do patch
=====================================================================
Resolve o commit de correção de uma vulnerabilidade direto do banco GHSA,
em vez de adivinhar via busca por mensagem de commit (que falha quando o
projeto não cita o CVE na mensagem — Apache httpd/SVN, Wireshark/GitLab,
e vários repos Java GitHub-nativos como spring-boot/kafka/elasticsearch).

Validado nesta sessão: `CVE-2023-20883` (spring-boot DoS) →
GHSA-xf96-w227-r7c4 → `commit/418dd1ba...` — o fix exato, que a busca por
mensagem de commit NÃO tinha encontrado.

O payload abaixo é REAL, capturado de
`api.github.com/advisories?cve_id=CVE-2023-20883` nesta sessão (campos
recortados aos que o resolver consome) — não inventado.
"""
from __future__ import annotations

from sast.ghsa_fix_resolver import (
    extract_fix_commits,
    GHSAFixResolver,
    FixRef,
)

# Payload GHSA REAL (recortado) — CVE-2023-20883 / spring-boot.
_REAL_GHSA = {
    "ghsa_id": "GHSA-xf96-w227-r7c4",
    "cve_id": "CVE-2023-20883",
    "references": [
        "https://nvd.nist.gov/vuln/detail/CVE-2023-20883",
        "https://spring.io/security/cve-2023-20883",
        "https://github.com/spring-projects/spring-boot/issues/35552",
        "https://github.com/spring-projects/spring-boot/commit/418dd1ba5bdad79b55a043000164bfcbda2acd78",
        "https://github.com/spring-projects/spring-boot/releases/tag/v2.5.15",
        "https://security.netapp.com/advisory/ntap-20230703-0008/",
        "https://github.com/advisories/GHSA-xf96-w227-r7c4",
    ],
}

# Shape OSV/alternativo: references como list[{"url","type"}].
_OSV_SHAPE = {
    "id": "GHSA-mjmj-j48q-9wg2",
    "references": [
        {"type": "WEB", "url": "https://nvd.nist.gov/vuln/detail/CVE-2022-1471"},
        {"type": "FIX", "url": "https://github.com/snakeyaml/snakeyaml/commit/acc44099f5f4af26ff86b4e4e4cc1c874e2dc5c4"},
    ],
}


# ── extração pura (offline) ──────────────────────────────────────────────────

def test_T76_extracts_real_fix_commit_filtered_by_repo():
    refs = extract_fix_commits(_REAL_GHSA, repo="spring-projects/spring-boot")
    assert len(refs) == 1
    assert refs[0].sha == "418dd1ba5bdad79b55a043000164bfcbda2acd78"
    assert refs[0].repo == "spring-projects/spring-boot"
    assert "/commit/" in refs[0].url


def test_T76_repo_filter_excludes_other_repos():
    # Sem filtro acha o commit; filtrando por um repo que não está, vem vazio.
    assert extract_fix_commits(_REAL_GHSA, repo="apache/kafka") == []
    assert len(extract_fix_commits(_REAL_GHSA)) == 1  # sem filtro


def test_T76_ignores_release_issue_and_advisory_links():
    # releases/tag, issues e /advisories NÃO são commits — não devem casar.
    refs = extract_fix_commits(_REAL_GHSA)
    assert all(r.sha for r in refs)
    assert all("/releases/" not in r.url and "/issues/" not in r.url for r in refs)


def test_T76_supports_osv_reference_object_shape():
    refs = extract_fix_commits(_OSV_SHAPE, repo="snakeyaml/snakeyaml")
    assert len(refs) == 1
    assert refs[0].sha.startswith("acc44099")


def test_T76_empty_payload_returns_empty_not_raises():
    assert extract_fix_commits({}) == []
    assert extract_fix_commits({"references": []}) == []
    assert extract_fix_commits({"references": [123, None, "not-a-url"]}) == []


def test_T76_dedups_repeated_commit_refs():
    dup = {"references": [
        "https://github.com/o/n/commit/abcabcabc",
        "https://github.com/o/n/commit/abcabcabc",
    ]}
    refs = extract_fix_commits(dup)
    assert len(refs) == 1


# ── resolver: modo offline gracioso ───────────────────────────────────────────

def test_T76_resolver_offline_returns_none():
    r = GHSAFixResolver(token=None)  # sem fetcher, sem token
    assert r.available() is False
    assert r.resolve("CVE-2023-20883", repo="spring-projects/spring-boot") is None


def test_T76_resolver_with_injected_fetcher():
    # fetcher injetado devolve o payload real → resolve sem rede.
    resolver = GHSAFixResolver(fetcher=lambda url: [_REAL_GHSA])
    assert resolver.available() is True
    refs = resolver.resolve("CVE-2023-20883", repo="spring-projects/spring-boot")
    assert refs is not None and len(refs) == 1
    assert isinstance(refs[0], FixRef)
    assert refs[0].sha == "418dd1ba5bdad79b55a043000164bfcbda2acd78"


def test_T76_resolver_fetch_failure_returns_none():
    def boom(url):
        raise RuntimeError("network down")
    resolver = GHSAFixResolver(fetcher=boom)
    assert resolver.resolve("CVE-2023-20883") is None
