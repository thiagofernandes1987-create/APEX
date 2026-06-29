"""
Marco 77 — M9.4: Vendored-Dependency SCA — terceiro eixo (source-tree)
======================================================================
Para repos SEM lockfile committado mas que VENDORIZAM bibliotecas de
terceiros com versão declarada no fonte (ex.: WordPress embute
`rmccue/requests` com um `VERSION`), este eixo:

1. detecta a (lib, versão) vendorizada;
2. consulta os advisories do pacote no GHSA (mesmo endpoint permitido do
   M9.3);
3. decide vulnerável vs. limpo por **contenção de range de versão** —
   reportando LIMPO quando a versão vendorizada já está corrigida.

Um veredito limpo é um eixo SCA validado legítimo (igual a
three.js/pytorch contarem como "SCA A, limpo"): o valor é o tool ter
produzido um veredito real sobre uma versão resolvida real, não o repo
ser necessariamente vulnerável.

Os payloads de advisory abaixo são REAIS, recortados de
`api.github.com/advisories?ecosystem=composer&affects=rmccue/requests`
(e getid3) nesta sessão — não inventados.
"""
from __future__ import annotations

import pytest

from sca.vendored_scanner import (
    version_in_range,
    verdict_for,
    VendoredScanner,
    VendorVerdict,
)

# Advisory REAL: rmccue/requests CVE-2021-29476, range ">= 1.6.0, < 1.8.0".
_REQUESTS_ADV = [
    {
        "ghsa_id": "GHSA-52qp-jpq7-6c54",
        "cve_id": "CVE-2021-29476",
        "vulnerabilities": [
            {
                "package": {"ecosystem": "composer", "name": "rmccue/requests"},
                "vulnerable_version_range": ">= 1.6.0, < 1.8.0",
                "first_patched_version": "1.8.0",
            }
        ],
    }
]


# ── version_in_range (pura) ───────────────────────────────────────────────────

@pytest.mark.parametrize("ver,rng,expected", [
    ("1.7.0", ">= 1.6.0, < 1.8.0", True),
    ("1.6.0", ">= 1.6.0, < 1.8.0", True),    # limite inferior inclusivo
    ("1.8.0", ">= 1.6.0, < 1.8.0", False),   # limite superior exclusivo
    ("2.0.17", ">= 1.6.0, < 1.8.0", False),  # versão vendorizada do WP (patched)
    ("1.5.9", ">= 1.6.0, < 1.8.0", False),   # abaixo do range
    ("3.4", "<= 3.4", True),
    ("3.4.1", "<= 3.4", False),
    ("2.0.1", "= 2.0.1", True),
    ("v1.7.0", ">= 1.6.0, < 1.8.0", True),   # prefixo 'v'
    ("1.8.0-beta2", "< 1.8.0", False),       # sufixo pre-release tratado como 1.8.0
])
def test_T77_version_in_range(ver, rng, expected):
    assert version_in_range(ver, rng) is expected


def test_T77_unparseable_range_is_clean():
    # range vazio/sem comparador NUNCA flagra (fail-safe p/ limpo)
    assert version_in_range("1.0.0", "") is False
    assert version_in_range("1.0.0", "any") is False


# ── verdict_for (pura) — o caso WordPress ─────────────────────────────────────

def test_T77_vendored_patched_version_is_clean():
    # WordPress vendoriza requests 2.0.17 → fora do range → LIMPO (rating A)
    v = verdict_for("2.0.17", _REQUESTS_ADV, package="rmccue/requests")
    assert isinstance(v, VendorVerdict)
    assert v.vulnerable is False
    assert v.rating == "A"
    assert v.advisories_checked == 1
    assert v.hits == []


def test_T77_vendored_vulnerable_version_is_flagged():
    # versão hipotética dentro do range → flagrada com o CVE correto
    v = verdict_for("1.7.0", _REQUESTS_ADV, package="rmccue/requests")
    assert v.vulnerable is True
    assert v.rating == "C"
    assert v.hits[0].cve_id == "CVE-2021-29476"
    assert v.hits[0].vulnerable_range == ">= 1.6.0, < 1.8.0"


def test_T77_package_name_must_match():
    # advisory de outro pacote não contamina o veredito
    v = verdict_for("1.7.0", _REQUESTS_ADV, package="some/other-lib")
    assert v.vulnerable is False
    assert v.advisories_checked == 1


def test_T77_empty_advisories_is_clean():
    v = verdict_for("1.7.0", [], package="rmccue/requests")
    assert v.vulnerable is False
    assert v.rating == "A"


# ── scanner: offline gracioso + fetcher injetável ─────────────────────────────

def test_T77_scanner_offline_returns_none():
    sc = VendoredScanner(token=None)
    assert sc.available() is False
    assert sc.scan_package("composer", "rmccue/requests", "2.0.17") is None


def test_T77_scanner_with_injected_fetcher_wordpress_clean():
    sc = VendoredScanner(fetcher=lambda url: _REQUESTS_ADV)
    assert sc.available() is True
    v = sc.scan_package("composer", "rmccue/requests", "2.0.17")
    assert v is not None
    assert v.vulnerable is False  # WordPress vendor é patched → eixo SCA limpo válido
    assert v.rating == "A"


def test_T77_scanner_fetch_failure_returns_none():
    def boom(url):
        raise RuntimeError("network down")
    assert VendoredScanner(fetcher=boom).scan_package("composer", "x/y", "1.0.0") is None
