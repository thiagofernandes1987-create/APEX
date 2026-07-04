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
Solução determinística e barata: varrer os meses candidatos de um ou mais anos
com requisições HEAD (só o cabeçalho, sem baixar o corpo) até obter HTTP 200.
O ano-base sai do próprio CVE/GHSA (advisories publicam no ano do CVE ou no
seguinte), então na prática são ≤ 24 HEADs — cacheável e idempotente.

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
from typing import List, Optional

from scan.advisory_harvester import (
    AdvisoryRecord, parse_advisory, advisory_raw_url,
)

_MONTHS = ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12")
_CVE_YEAR_RE = re.compile(r"CVE-(\d{4})-")


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

    buckets = [True, False] if reviewed_buckets else [True]
    for reviewed in buckets:
        for year in years:
            for month in _MONTHS:
                url = advisory_raw_url(ghsa_id, str(year), month, reviewed)
                data = _try_fetch(urllib.request, url, timeout)
                if data is not None:
                    rec = parse_advisory(data)
                    if rec is not None:
                        return rec
    return None


def _try_fetch(urllib_request, url: str, timeout: int) -> Optional[str]:
    """GET simples; retorna o corpo (str) em 200, senão None.  Nunca levanta."""
    try:
        with urllib_request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            if getattr(resp, "status", 200) != 200:
                return None
            return resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — 404/rede são esperados na varredura
        return None
