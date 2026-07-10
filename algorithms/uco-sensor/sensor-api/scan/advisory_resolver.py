"""
UCO-Sensor — Advisory Path Resolver  (M25)
===========================================
Resolve automaticamente a URL raw de um advisory no GitHub Advisory Database a
partir do GHSA id, SEM saber o mês de publicação de antemão — o obstáculo que
faltava para o harvester (M23/M24) rodar em LOTE sem seed manual.

O problema (galinha-e-ovo)
--------------------------
O advisory-database indexa por `advisories/github-reviewed/YYYY/MM/GHSA/GHSA.json`.
Para BUSCAR o JSON precisamos do ano/mês; mas o ano/mês só está DENTRO do JSON.
Solução determinística: varrer os meses candidatos de um ou mais anos com
requisições **GET** até obter HTTP 200 — GET (não HEAD) porque precisamos do
CORPO do JSON para parsear (`parse_advisory`); uma HEAD teria de ser seguida de
um GET no acerto, sem economia real. O ano-base sai do próprio CVE/GHSA
(advisories publicam no ano do CVE ou no seguinte). Custo do PIOR caso:
2 buckets (github-reviewed → unreviewed) × 2 anos × 12 meses = **até 48 GETs**;
o acerto normal encerra bem antes. (DT/Achado #10: a doc antiga dizia "HEAD,
≤24", o que não batia com a implementação.) O resultado é **memoizado por GHSA**
(`_RESOLVE_CACHE`) — idempotente e sem refetch dentro do processo.

Fecha o item de checklist "M25 — resolver CVE→GHSA→(ano/mês) automático".
Combinado com M23 (parse) + M24 (compositor das 4 perguntas) + M12 (before/after
por tag), habilita o batch de dezenas de CVEs PyPI/npm reais.

API
---
    from scan.advisory_resolver import resolve_advisory
    rec = resolve_advisory("GHSA-h5c8-rqwp-cp95", years=[2024])  # → AdvisoryRecord | None

Degradação graciosa: qualquer falha de rede → None (nunca levanta).

Versão: introduzido em v3.59.0 (Sprint CJ).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from scan.advisory_harvester import (
    AdvisoryRecord, parse_advisory, advisory_raw_url,
)

_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_CVE_YEAR_RE = re.compile(r"CVE-(\d{4})-")

# (DT/Achado #10) memoização por (ghsa, anos, buckets) — evita refetch da mesma
# esteira (`generate_corpus --backfill` resolve os mesmos GHSAs repetidamente).
_RESOLVE_CACHE: Dict[Tuple[str, Tuple[int, ...], bool], Optional[AdvisoryRecord]] = {}


def clear_resolve_cache() -> None:
    """Zera o cache de resolução (útil em testes)."""
    _RESOLVE_CACHE.clear()


def year_hint_from_cve(cve: str) -> Optional[int]:
    """Ano embutido no id do CVE (ex.: CVE-2024-22195 → 2024)."""
    m = _CVE_YEAR_RE.search(cve or "")
    return int(m.group(1)) if m else None


def resolve_advisory(
    ghsa_id: str,
    years: Optional[List[int]] = None,
    cve_hint: str = "",
    reviewed_buckets: bool = True,
    timeout: int = 12,
) -> Optional[AdvisoryRecord]:
    """
    Acha e parseia o advisory de `ghsa_id` varrendo (ano, mês) até HTTP 200.

    * `years` — anos candidatos; se None, deriva de `cve_hint` (o ano do CVE e o
      seguinte, pois advisories às vezes saem no ano posterior).
    * `reviewed_buckets` — tenta `github-reviewed` e, se falhar, `unreviewed`.

    Retorna o AdvisoryRecord (M23) ou None.  Nunca levanta.  Import de urllib
    tardio (só quando há busca de rede).
    """
    import urllib.request  # tardio

    if not ghsa_id:
        return None
    if years is None:
        y = year_hint_from_cve(cve_hint)
        years = [y, y + 1] if y else []
    if not years:
        return None

    cache_key = (ghsa_id, tuple(years), reviewed_buckets)
    if cache_key in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[cache_key]

    result: Optional[AdvisoryRecord] = None
    buckets = [True, False] if reviewed_buckets else [True]
    for reviewed in buckets:
        for year in years:
            for month in _MONTHS:
                url = advisory_raw_url(ghsa_id, str(year), month, reviewed)
                data = _try_fetch(urllib.request, url, timeout)
                if data is not None:
                    rec = parse_advisory(data)
                    if rec is not None:
                        result = rec
                        break
            if result is not None:
                break
        if result is not None:
            break
    # cacheia SÓ acertos: um None pode ser falha transiente de rede — não deve
    # ficar preso no cache impedindo retry (Achado #10, refinamento).
    if result is not None:
        _RESOLVE_CACHE[cache_key] = result
    return result


def _try_fetch(urllib_request, url: str, timeout: int) -> Optional[str]:
    """GET simples; retorna o corpo (str) em 200, senão None.  Nunca levanta.

    (DT/Achado #13) Delega ao ponto único `advisory_harvester.http_get` — antes
    reimplementava o mesmo urlopen+read do M23.  O param `urllib_request` é
    mantido por compatibilidade de assinatura (os testes monkeypatcham este
    símbolo), mas não é mais usado.
    """
    from scan.advisory_harvester import http_get
    return http_get(url, timeout)
