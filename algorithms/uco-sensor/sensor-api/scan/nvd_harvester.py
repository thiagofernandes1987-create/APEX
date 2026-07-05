"""
UCO-Sensor — NVD / CVE-Record Harvester  (M26)
===============================================
Colhe metadados de degradação para CVEs que NÃO estão no GitHub Advisory
Database (M23) — tipicamente projetos C de servidor (postgres, ffmpeg, sqlite,
redis, php-src, kernel) que não vivem num ecossistema empacotado (PyPI/npm/…).

Canal (dado real, provado)
--------------------------
O CVE Project (MITRE) publica CADA CVE como JSON no GitHub
`CVEProject/cvelistV5`, acessível via `raw.githubusercontent.com` (HTTP 200 —
o mesmo padrão que destravou o advisory-database no M23).  Caminho:
`cves/YYYY/Nxxx/CVE-YYYY-NNNNN.json` (N = milhar do número, truncado).
(A REST API do NVD, `services.nvd.nist.gov`, está BLOQUEADA pelo proxy; este
canal a substitui.)

Honestidade sobre qualidade de dado (importante — sem inventar)
--------------------------------------------------------------
A completude do CVE-record depende da CNA que o registrou:
  * bem-preenchido (ex.: postgres CVE-2021-32027 → versões corrigidas 13.3/12.7/
    11.12/10.17/9.6.22, references do vendor);
  * ESCASSO (ex.: ffmpeg CVE-2020-22015, sqlite CVE-2019-19646 → product/versions
    "n/a").  Nesses, a versão corrigida NÃO está neste canal — é um dado
    genuinamente ausente, não um gap de processamento.  O `NvdRecord` reporta
    isso honestamente (`resolved_in` vazio / "n/a"), sem fabricar.

Interface
---------
`NvdRecord` é DUCK-COMPATÍVEL com `AdvisoryRecord` (M23) — expõe `cve`,
`ghsa_id` (""), `package`, `ecosystem` ("C/native"), `cwe_ids`, `fix_commit`,
`introduced`, `fixed`, `when_broke`, `resolved_in` — para o compositor M24
`build_degradation` consumir sem alteração.

Versão: introduzido em v3.60.0 (Sprint CK).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_COMMIT_RE = re.compile(r"/commit/?([0-9a-f]{7,40})\b", re.I)
# versões soltas num texto tipo "postgresql 13.3, postgresql 12.7, 11.12"
_VER_RE = re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b")
_NA = {"", "n/a", "N/A", "na", "unknown", "*"}


@dataclass(frozen=True)
class NvdRecord:
    """Metadados de degradação de um CVE via cvelistV5 (duck-compat M23)."""
    cve: str
    package: str
    ecosystem: str = "C/native"
    introduced: str = ""
    fixed_versions: List[str] = field(default_factory=list)
    fix_commit: str = ""
    cwe_ids: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    description: str = ""

    # ── campos/props que espelham AdvisoryRecord (para o M24) ────────────────
    ghsa_id: str = ""

    @property
    def fixed(self) -> str:
        """Primeira versão corrigida (a mais antiga costuma vir primeiro)."""
        return self.fixed_versions[0] if self.fixed_versions else ""

    @property
    def has_version_pair(self) -> bool:
        return bool(self.fixed_versions)

    @property
    def when_broke(self) -> str:
        if self.introduced and self.introduced not in _NA:
            return f"versão {self.introduced}"
        return "não disponível no CVE-record (CNA não informou introduced)"

    @property
    def resolved_in(self) -> str:
        if self.fixed_versions:
            return "versão " + "/".join(self.fixed_versions)
        return ""   # honesto: dado ausente neste canal

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cve": self.cve, "package": self.package, "ecosystem": self.ecosystem,
            "introduced": self.introduced, "fixed_versions": list(self.fixed_versions),
            "fixed": self.fixed, "fix_commit": self.fix_commit,
            "cwe_ids": list(self.cwe_ids), "references": list(self.references),
            "when_broke": self.when_broke, "resolved_in": self.resolved_in,
        }


def parse_cve_record(cvelist_json: Any) -> Optional[NvdRecord]:
    """
    Parseia um JSON do cvelistV5 (schema CVE 5.x) num NvdRecord.
    PURO e defensivo: nunca levanta; None se inutilizável.
    """
    try:
        d = json.loads(cvelist_json) if isinstance(cvelist_json, (str, bytes)) else cvelist_json
        if not isinstance(d, dict):
            return None
    except (ValueError, TypeError):
        return None

    meta = d.get("cveMetadata") or {}
    cve = str(meta.get("cveId", "") or "")
    cna = (d.get("containers") or {}).get("cna") or {}

    # ── produto + versões afetadas/corrigidas ───────────────────────────────
    package = ""
    fixed_versions: List[str] = []
    introduced = ""
    for aff in (cna.get("affected") or []):
        if not isinstance(aff, dict):
            continue
        prod = str(aff.get("product", "") or "")
        if package == "" and prod and prod not in _NA:
            package = prod
        for v in (aff.get("versions") or []):
            if not isinstance(v, dict):
                continue
            # schema estruturado: lessThan/lessThanOrEqual = fronteira corrigida
            lt = v.get("lessThan") or v.get("lessThanOrEqual")
            if lt and str(lt) not in _NA:
                fixed_versions.extend(_VER_RE.findall(str(lt)))
            # (DS/Achado #2 — com ressalva validada em dado REAL) O campo
            # `version` de `status=affected` é AMBÍGUO no dado público:
            #   * postgres (CVE-2021-32027) ABUSA do schema e põe uma LISTA de
            #     versões CORRIGIDAS ("13.3, 12.7, ...") aqui → são fixed.
            #   * schema limpo (1 versão, com `lessThan`) → `version` é o INÍCIO
            #     do range afetado = introduced.
            # Discriminador que respeita os dois: nº de versões no texto.
            #   - várias  → convenção postgres (fixed list)
            #   - uma só  → fronteira introduced (nunca marcar a versão vulnerável
            #               como "corrigida", que era o bug original).
            iv = v.get("version")
            if iv and str(iv) not in _NA and v.get("status") == "affected":
                found = _VER_RE.findall(str(iv))
                if len(found) > 1:
                    fixed_versions.extend(found)      # lista de fixed (postgres)
                elif len(found) == 1 and not introduced:
                    introduced = found[0]             # fronteira do range afetado
    # dedup preservando ordem
    seen: set = set()
    fixed_versions = [x for x in fixed_versions if not (x in seen or seen.add(x))]

    # ── CWE ──────────────────────────────────────────────────────────────────
    cwe_ids: List[str] = []
    for pt in (cna.get("problemTypes") or []):
        for desc in (pt.get("descriptions") or []):
            cid = desc.get("cweId")
            if cid and str(cid) not in _NA:
                cwe_ids.append(str(cid))

    # ── references + commit ──────────────────────────────────────────────────
    references: List[str] = []
    fix_commit = ""
    for ref in (cna.get("references") or []):
        url = str(ref.get("url", "")) if isinstance(ref, dict) else ""
        if url:
            references.append(url)
            if not fix_commit:
                m = _COMMIT_RE.search(url)
                if m:
                    fix_commit = m.group(1)

    # descrição (primeira em inglês)
    description = ""
    for desc in (cna.get("descriptions") or []):
        if isinstance(desc, dict) and desc.get("lang", "").startswith("en"):
            description = str(desc.get("value", ""))[:400]
            break

    if not cve and not package:
        return None

    return NvdRecord(
        cve=cve, package=package or "n/a", introduced=introduced,
        fixed_versions=fixed_versions, fix_commit=fix_commit, cwe_ids=cwe_ids,
        references=references, description=description,
    )


def cve_raw_url(cve_id: str) -> Optional[str]:
    """
    Monta a URL raw do cvelistV5 para um CVE.
    Ex.: CVE-2021-32027 → cves/2021/32xxx/CVE-2021-32027.json
    (bucket = milhar do número truncado com 'xxx').
    """
    m = re.match(r"CVE-(\d{4})-(\d+)$", cve_id or "", re.I)
    if not m:
        return None
    year, num = m.group(1), m.group(2)
    # bucket: tudo menos os 3 últimos dígitos + 'xxx' (mínimo "0xxx")
    bucket = (num[:-3] if len(num) > 3 else "0") + "xxx"
    return ("https://raw.githubusercontent.com/CVEProject/cvelistV5/main/"
            f"cves/{year}/{bucket}/CVE-{year}-{num}.json")


def fetch_cve(cve_id: str, timeout: int = 25) -> Optional[NvdRecord]:
    """Busca + parseia via raw (canal provado).  Guardada: falha → None."""
    import urllib.request  # tardio
    url = cve_raw_url(cve_id)
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            if getattr(resp, "status", 200) != 200:
                return None
            data = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001
        return None
    return parse_cve_record(data)
