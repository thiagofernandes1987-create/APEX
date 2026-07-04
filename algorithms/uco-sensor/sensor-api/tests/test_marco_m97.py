"""
Marco 97 — M25: Advisory Path Resolver
=======================================
O `resolve_advisory` (M25) acha automaticamente a URL raw de um advisory no
GitHub Advisory Database a partir do GHSA id, sem saber o mês de publicação —
varrendo (ano, mês) com requisições até HTTP 200.  É o que faltava para o
harvester (M23/M24) rodar em LOTE sem seed manual.

Nesta sessão o resolver foi validado AO VIVO (jinja→2024/01, requests→2023/05)
e o batch real produziu 2/2 registros de degradação COMPLETOS
(paper/corpus_runs/degradation_report_pypi.json).  Aqui testamos a lógica pura
(year_hint) e a varredura com um fetcher mockado (sem rede no CI).
"""
from __future__ import annotations

import scan.advisory_resolver as R
from scan.advisory_resolver import year_hint_from_cve, resolve_advisory


def test_T97_year_hint_from_cve():
    assert year_hint_from_cve("CVE-2024-22195") == 2024
    assert year_hint_from_cve("CVE-2023-32681") == 2023
    assert year_hint_from_cve("GHSA-only-no-cve") is None
    assert year_hint_from_cve("") is None


def test_T97_no_years_no_ghsa_returns_none():
    # sem GHSA → None; sem anos deriváveis → None
    assert resolve_advisory("") is None
    assert resolve_advisory("GHSA-x", years=None, cve_hint="") is None


def _install_fake_fetch(monkeypatch, hit_url, payload):
    """Substitui o _try_fetch por um que só devolve payload na URL alvo."""
    def fake(_urllib, url, timeout):
        return payload if url == hit_url else None
    monkeypatch.setattr(R, "_try_fetch", fake)


def test_T97_resolve_scans_until_match(monkeypatch):
    ghsa = "GHSA-h5c8-rqwp-cp95"
    # a URL "correta" é a de 2024/01 (github-reviewed) — igual ao real
    from scan.advisory_harvester import advisory_raw_url
    hit = advisory_raw_url(ghsa, "2024", "01", reviewed=True)
    payload = ('{"id":"%s","aliases":["CVE-2024-22195"],'
               '"affected":[{"package":{"name":"jinja2","ecosystem":"PyPI"},'
               '"ranges":[{"type":"ECOSYSTEM","events":[{"introduced":"0"},'
               '{"fixed":"3.1.3"}]}]}]}' % ghsa)
    _install_fake_fetch(monkeypatch, hit, payload)
    rec = resolve_advisory(ghsa, cve_hint="CVE-2024-22195")
    assert rec is not None
    assert rec.cve == "CVE-2024-22195" and rec.fixed == "3.1.3"


def test_T97_resolve_returns_none_when_nothing_matches(monkeypatch):
    monkeypatch.setattr(R, "_try_fetch", lambda _u, _url, _t: None)
    assert resolve_advisory("GHSA-none", cve_hint="CVE-2020-0001") is None


def test_T97_years_param_overrides_hint(monkeypatch):
    ghsa = "GHSA-j8r2-6x86-q33q"
    from scan.advisory_harvester import advisory_raw_url
    hit = advisory_raw_url(ghsa, "2023", "05", reviewed=True)
    payload = ('{"id":"%s","aliases":["CVE-2023-32681"],'
               '"affected":[{"package":{"name":"requests","ecosystem":"PyPI"},'
               '"ranges":[{"type":"ECOSYSTEM","events":[{"introduced":"2.3.0"},'
               '{"fixed":"2.31.0"}]}]}]}' % ghsa)
    _install_fake_fetch(monkeypatch, hit, payload)
    rec = resolve_advisory(ghsa, years=[2023])
    assert rec is not None and rec.fixed == "2.31.0"
