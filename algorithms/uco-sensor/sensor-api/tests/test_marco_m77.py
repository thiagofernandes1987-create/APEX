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
    parse_packages_config,
    parse_msbuild_cpm,
    parse_cargo_lock,
    parse_package_lock,
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


# ── parsers de manifesto: packages.config (NuGet old-style) ───────────────────

# Recorte REAL de shadowsocks-csharp/packages.config (Sprint AX).
_PACKAGES_CONFIG = """\
<?xml version="1.0" encoding="utf-8"?>
<packages>
  <package id="Newtonsoft.Json" version="13.0.3" targetFramework="net472" />
  <package id="Google.Protobuf" version="3.27.2" targetFramework="net472" />
  <package id="System.Net.Http" version="4.3.4" targetFramework="net472" />
</packages>
"""


def test_T77_parse_packages_config():
    pkgs = parse_packages_config(_PACKAGES_CONFIG)
    assert pkgs == {
        "Newtonsoft.Json": "13.0.3",
        "Google.Protobuf": "3.27.2",
        "System.Net.Http": "4.3.4",
    }


def test_T77_parse_packages_config_empty():
    assert parse_packages_config("") == {}
    assert parse_packages_config("<packages></packages>") == {}


# ── parsers de manifesto: Central Package Management (MSBuild) ─────────────────

# Recorte REAL do padrão roslyn eng/Packages.props + eng/Versions.props (AY).
_PACKAGES_PROPS = """\
<Project>
  <ItemGroup>
    <PackageVersion Include="MessagePack" Version="$(MessagePackVersion)" />
    <PackageVersion Include="Newtonsoft.Json" Version="$(NewtonsoftJsonVersion)" />
    <PackageVersion Include="LiteralPkg" Version="1.2.3" />
    <PackageVersion Include="UnresolvedPkg" Version="$(MissingVersion)" />
  </ItemGroup>
</Project>
"""
_VERSIONS_PROPS = """\
<Project>
  <PropertyGroup>
    <MessagePackVersion>2.5.198</MessagePackVersion>
    <NewtonsoftJsonVersion>13.0.3</NewtonsoftJsonVersion>
  </PropertyGroup>
</Project>
"""


def test_T77_parse_msbuild_cpm_resolves_indirection():
    pkgs = parse_msbuild_cpm(_PACKAGES_PROPS, _VERSIONS_PROPS)
    assert pkgs["MessagePack"] == "2.5.198"
    assert pkgs["Newtonsoft.Json"] == "13.0.3"
    # versão literal mantida
    assert pkgs["LiteralPkg"] == "1.2.3"
    # variável sem definição é DESCARTADA (nunca chuta → evita FP)
    assert "UnresolvedPkg" not in pkgs


def test_T77_parse_cargo_lock():
    # recorte real de estilo Cargo.lock (clickhouse rust/workspace, Sprint AZ)
    cargo = (
        '[[package]]\nname = "serde"\nversion = "1.0.197"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n\n'
        '[[package]]\nname = "tokio"\nversion = "1.36.0"\n'
    )
    pkgs = parse_cargo_lock(cargo)
    assert pkgs == {"serde": "1.0.197", "tokio": "1.36.0"}


def test_T77_parse_cargo_lock_empty():
    assert parse_cargo_lock("") == {}


def test_T77_parse_package_lock_v3():
    # formato npm v2/v3: packages{ "node_modules/<name>": {version} }
    lock = (
        '{"lockfileVersion": 3, "packages": {'
        '"": {"name": "root"},'
        '"node_modules/lodash": {"version": "4.17.21"},'
        '"node_modules/@babel/core": {"version": "7.24.0"}'
        '}}'
    )
    pkgs = parse_package_lock(lock)
    assert pkgs == {"lodash": "4.17.21", "@babel/core": "7.24.0"}


def test_T77_parse_package_lock_v1():
    # formato npm v1: dependencies{ "<name>": {version} }
    lock = '{"lockfileVersion": 1, "dependencies": {"ms": {"version": "2.1.3"}}}'
    assert parse_package_lock(lock) == {"ms": "2.1.3"}


def test_T77_parse_package_lock_malformed_is_empty():
    assert parse_package_lock("") == {}
    assert parse_package_lock("not json") == {}


def test_T77_jackson_databind_elasticsearch_true_positive():
    # elasticsearch build.versions.toml resolve jackson-databind 2.15.0 ->
    # cai em ">= 2.8.0, < 2.18.9" (CVE-2026-54515 série), patched 2.18.9.
    assert version_in_range("2.15.0", ">= 2.8.0, < 2.18.9") is True
    assert version_in_range("2.15.0", ">= 2.10.0, <= 2.18.7") is True
    assert version_in_range("2.18.9", ">= 2.8.0, < 2.18.9") is False  # patched


def test_T77_msbuild_cpm_messagepack_window_is_a_true_positive():
    # 2.5.198 cai em "< 2.5.301" (vulnerável) mas NÃO em "< 2.5.187" (patched)
    # — confirma que o range-matching distingue a janela vulnerável real.
    assert version_in_range("2.5.198", "< 2.5.301") is True
    assert version_in_range("2.5.198", "< 2.5.187") is False
    assert version_in_range("2.5.198", ">= 3.0, < 3.1.7") is False
