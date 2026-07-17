"""
UCO-Sensor — SCA priorização por EXPLORABILIDADE (EPSS + CISA KEV)  (M9.7)
==========================================================================
Severidade (CVSS) mede IMPACTO, não probabilidade de exploração. Dois canais
gratuitos e de altíssimo sinal, hoje não captados, mudam a priorização:

* **EPSS** (FIRST.org) — probabilidade [0,1] de exploração nos próximos 30 dias.
  Um CRITICAL com EPSS 0.02 é menos urgente que um HIGH com EPSS 0.90.
* **CISA KEV** — catálogo de vulnerabilidades *ativamente exploradas* na prática.
  Um CVE no KEV é a maior prioridade possível, independente do CVSS.

Este módulo é PURO: recebe os dados já buscados (map EPSS / set KEV) e enriquece
os findings. A rede fica INJETADA no chamador (mesmo padrão do resto do SCA), o
que mantém tudo testável offline. Fornece parsers para os formatos oficiais
(CSV do EPSS, JSON do KEV) para o chamador que tiver rede.

API
---
    from sca.priority import enrich_with_epss, enrich_with_kev, parse_epss_csv, parse_kev_json
    enrich_with_epss(findings, {"CVE-2021-44228": 0.97})
    enrich_with_kev(findings, {"CVE-2021-44228"})
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Set

_CVE_RE = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)


def _cve_of(finding: Any) -> str:
    """Extrai o CVE de um finding (rule_id `SCA-...`, `cve_id`, ou texto)."""
    for attr in ("cve_id", "cve"):
        v = getattr(finding, attr, None)
        if isinstance(v, str) and v.upper().startswith("CVE-"):
            return v.upper()
    for attr in ("rule_id", "title", "explanation", "description"):
        v = getattr(finding, attr, "") or ""
        m = _CVE_RE.search(str(v))
        if m:
            return m.group(0).upper()
    return ""


# ── EPSS ──────────────────────────────────────────────────────────────────────

def parse_epss_csv(csv_text: str) -> Dict[str, float]:
    """Parseia o CSV oficial do EPSS (`cve,epss,percentile`, com linhas `#`)."""
    out: Dict[str, float] = {}
    for line in csv_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.lower().startswith("cve,"):
            continue
        parts = line.split(",")
        if len(parts) >= 2 and parts[0].upper().startswith("CVE-"):
            try:
                out[parts[0].upper()] = float(parts[1])
            except ValueError:
                continue
    return out


def enrich_with_epss(findings: Iterable, epss: Dict[str, float]):
    """Anexa `epss` (probabilidade) a cada finding e anota a explicação.

    Muta os findings (adiciona atributo `epss`); devolve a lista. `epss` é o map
    {CVE: probabilidade} (ex.: de `parse_epss_csv`).
    """
    out = list(findings)
    for f in out:
        cve = _cve_of(f)
        p = epss.get(cve) if cve else None
        if p is not None:
            setattr(f, "epss", round(float(p), 5))
            tag = "ALTA" if p >= 0.5 else ("média" if p >= 0.1 else "baixa")
            if hasattr(f, "explanation"):
                f.explanation = (getattr(f, "explanation", "") or "") + \
                    f" [EPSS={p:.2%} exploração-30d ({tag})]"
    return out


# ── CISA KEV ────────────────────────────────────────────────────────────────

def parse_kev_json(kev_text: str) -> Set[str]:
    """Extrai o conjunto de CVEs do JSON oficial do CISA KEV catalog."""
    try:
        data = json.loads(kev_text)
    except (json.JSONDecodeError, TypeError):
        return set()
    out: Set[str] = set()
    for v in data.get("vulnerabilities", []):
        cid = str(v.get("cveID", "") or "").upper()
        if cid.startswith("CVE-"):
            out.add(cid)
    return out


def enrich_with_kev(findings: Iterable, kev: Set[str]):
    """Marca findings cujo CVE está no CISA KEV (ativamente explorado).

    KEV é sinal de máxima urgência: eleva severidade a CRITICAL e anota. Muta e
    devolve a lista. `kev` é o set de CVEs (ex.: de `parse_kev_json`).
    """
    kev_up = {c.upper() for c in kev}
    out = list(findings)
    for f in out:
        cve = _cve_of(f)
        in_kev = bool(cve and cve in kev_up)
        setattr(f, "kev", in_kev)
        if in_kev:
            if getattr(f, "severity", "") != "CRITICAL":
                f.severity = "CRITICAL"
            if hasattr(f, "explanation"):
                f.explanation = (getattr(f, "explanation", "") or "") + \
                    " [CISA-KEV: ATIVAMENTE EXPLORADO — prioridade máxima]"
    return out


def priority_score(finding: Any) -> float:
    """Escore combinado [0,1] para ordenar findings por urgência REAL.

    Combina KEV (domina), EPSS e severidade CVSS. KEV → 1.0. Senão, mistura
    EPSS (probabilidade) com o peso da severidade.
    """
    if getattr(finding, "kev", False):
        return 1.0
    sev_w = {"CRITICAL": 0.9, "HIGH": 0.7, "MEDIUM": 0.4, "LOW": 0.2}.get(
        getattr(finding, "severity", ""), 0.3)
    epss = getattr(finding, "epss", None)
    if epss is None:
        return round(sev_w * 0.6, 4)          # sem EPSS: só severidade, atenuada
    return round(0.6 * float(epss) + 0.4 * sev_w, 4)
