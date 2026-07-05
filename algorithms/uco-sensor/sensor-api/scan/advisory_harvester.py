"""
UCO-Sensor — Advisory Harvester  (M23)
=======================================
Transforma um advisory de segurança em **formato OSV** (o schema do GitHub
Advisory Database) num registro estruturado de DEGRADAÇÃO — respondendo, com
DADO REAL e sem fabricação, duas das quatro perguntas do objetivo do corpus:

    * **quando quebrou**        → versão `introduced` do range afetado
    * **em qual versão resolveu** → versão `fixed` do range afetado
    (+ commit do fix, tag do fix, CWE, pacote/ecossistema — âncoras para o
     M10/M11/M12/M17/M22 responderem "como" e "onde" via before/after.)

Por que isto (romper a barreira do corpus rumo a 100/100)
---------------------------------------------------------
O gargalo real do corpus NÃO era o scanner — era IDENTIFICAR, por CVE e sem a
API de commits (403), o par de versões correto e o commit do fix.  O GitHub
Advisory Database é um repositório git de JSONs OSV, acessível via
`raw.githubusercontent.com` (HTTP 200 — canal provado), e já traz de graça:
`aliases` (CVE↔GHSA), `affected[].ranges[].events` (introduced/fixed) e
`references` (URL do commit e da release).  Era um canal que captávamos e não
processávamos.  Este módulo o processa.

Método (alinhado à literatura — CVEfixes arXiv:2107.08760, VFCFinder
arXiv:2311.01532): advisory → (repo, fix_commit, fixed_version, introduced) →
o Sensor busca os dois lados por TAG via raw e roda o diferencial before/after
(D2A arXiv:2102.07995: fixed / pre-existing / introduced), que os módulos
M12/M19 já implementam.

Design
------
* `parse_advisory(osv_json)` — PURO (sem rede), testável offline; nunca levanta.
* `AdvisoryRecord` — o registro estruturado (dataclass).
* `advisory_raw_url(ghsa_id, year, month)` — monta a URL raw canônica.
* `fetch_advisory(...)` — busca via rede (guardada; degrada para None).

Versão: introduzido em v3.57.0 (Sprint CH).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# SHA de commit em URL de reference (`.../commit/<sha>`), 7..40 hex.
_COMMIT_RE = re.compile(r"/commit/([0-9a-f]{7,40})\b", re.I)
# tag de release em reference (`.../releases/tag/<tag>`).
_TAG_RE = re.compile(r"/releases/tag/([^/\s]+)")
# CVE canônico entre os aliases.
_CVE_RE = re.compile(r"^CVE-\d{4}-\d+$", re.I)


@dataclass(frozen=True)
class AdvisoryRecord:
    """Registro de degradação derivado de um advisory OSV (dado real)."""
    ghsa_id: str
    cve: str                      # "" se não houver alias CVE
    package: str
    ecosystem: str
    introduced: str               # versão onde a vuln foi introduzida ("0" = desde sempre)
    fixed: str                    # versão que resolveu ("" se sem fixed conhecido)
    fix_commit: str               # SHA do commit do fix ("" se ausente)
    fix_tag: str                  # tag de release do fix ("" se ausente)
    cwe_ids: List[str] = field(default_factory=list)
    severity: str = ""
    summary: str = ""
    published: str = ""
    modified: str = ""
    advisory_url: str = ""
    # ranges GIT (quando presentes) trazem SHAs de introduced/fixed direto do repo
    git_introduced: str = ""
    git_fixed: str = ""

    @property
    def has_version_pair(self) -> bool:
        """True se dá para montar um par before/after por VERSÃO (tag)."""
        return bool(self.fixed) and self.fixed != ""

    @property
    def when_broke(self) -> str:
        """Resposta legível para 'quando quebrou'."""
        if self.introduced in ("", "0"):
            return "desde a introdução do componente (introduced=0)"
        return f"versão {self.introduced}"

    @property
    def resolved_in(self) -> str:
        """Resposta legível para 'em qual versão foi resolvido'."""
        return f"versão {self.fixed}" if self.fixed else "desconhecida (sem 'fixed' no advisory)"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ghsa_id": self.ghsa_id, "cve": self.cve,
            "package": self.package, "ecosystem": self.ecosystem,
            "introduced": self.introduced, "fixed": self.fixed,
            "fix_commit": self.fix_commit, "fix_tag": self.fix_tag,
            "cwe_ids": list(self.cwe_ids), "severity": self.severity,
            "summary": self.summary, "advisory_url": self.advisory_url,
            "git_introduced": self.git_introduced, "git_fixed": self.git_fixed,
            "when_broke": self.when_broke, "resolved_in": self.resolved_in,
            "published": self.published, "modified": self.modified,
        }


def parse_advisory(osv_json: Any) -> Optional[AdvisoryRecord]:
    """
    Parseia um advisory OSV (str JSON ou dict já carregado) num AdvisoryRecord.
    PURO e defensivo: nunca levanta; retorna None se o JSON for inutilizável.

    Onde entra: consumido pelo M12 CorpusValidator para saber QUAL par de
    versões buscar (introduced→fixed) e por scripts de expansão de corpus.
    """
    try:
        d = json.loads(osv_json) if isinstance(osv_json, (str, bytes)) else osv_json
        if not isinstance(d, dict):
            return None
    except (ValueError, TypeError):
        return None

    ghsa_id = str(d.get("id", "") or "")
    aliases = d.get("aliases") or []
    cve = next((a for a in aliases if isinstance(a, str) and _CVE_RE.match(a)), "")

    # ── primeiro `affected` com pacote nomeado ──────────────────────────────
    package = ecosystem = ""
    introduced = fixed = ""
    git_introduced = git_fixed = ""
    for aff in (d.get("affected") or []):
        if not isinstance(aff, dict):
            continue
        pkg = aff.get("package") or {}
        if package == "" and pkg.get("name"):
            package = str(pkg.get("name", ""))
            ecosystem = str(pkg.get("ecosystem", ""))
        for rng in (aff.get("ranges") or []):
            if not isinstance(rng, dict):
                continue
            rtype = str(rng.get("type", "")).upper()
            for ev in (rng.get("events") or []):
                if not isinstance(ev, dict):
                    continue
                if "introduced" in ev:
                    val = str(ev["introduced"])
                    if rtype == "GIT":
                        git_introduced = git_introduced or val
                    elif introduced == "":
                        introduced = val
                if "fixed" in ev:
                    val = str(ev["fixed"])
                    if rtype == "GIT":
                        git_fixed = git_fixed or val
                    elif fixed == "":
                        fixed = val
        # se já temos par de versão por ecossistema, não precisa varrer o resto
        if package and fixed:
            break

    # ── references: commit do fix + tag de release ──────────────────────────
    fix_commit = fix_tag = advisory_url = ""
    for ref in (d.get("references") or []):
        if not isinstance(ref, dict):
            continue
        url = str(ref.get("url", ""))
        if not fix_commit:
            m = _COMMIT_RE.search(url)
            if m:
                fix_commit = m.group(1)
        if not fix_tag:
            m = _TAG_RE.search(url)
            if m:
                fix_tag = m.group(1)
        if not advisory_url and "/security/advisories/" in url:
            advisory_url = url
    # o commit GIT do range é o fix commit mais confiável quando presente
    if git_fixed and not fix_commit:
        fix_commit = git_fixed
    # tag do fix: se ausente nas refs, a própria versão `fixed` costuma ser a tag
    if not fix_tag and fixed:
        fix_tag = fixed

    # ── CWE + severidade ────────────────────────────────────────────────────
    dbspec = d.get("database_specific") or {}
    cwe_ids = [str(c) for c in (dbspec.get("cwe_ids") or []) if c]
    severity = str(dbspec.get("severity", "") or "")
    if not severity:
        sev = d.get("severity") or []
        if sev and isinstance(sev, list) and isinstance(sev[0], dict):
            severity = str(sev[0].get("score", "") or "")

    summary = str(d.get("summary", "") or "")
    published = str(d.get("published", "") or "")
    modified = str(d.get("modified", "") or "")
    
    if not advisory_url and ghsa_id:
        advisory_url = f"https://github.com/advisories/{ghsa_id}"

    # registro inútil se não há id nem pacote
    if not ghsa_id and not package:
        return None

    return AdvisoryRecord(
        ghsa_id=ghsa_id, cve=cve, package=package, ecosystem=ecosystem,
        introduced=introduced, fixed=fixed, fix_commit=fix_commit,
        fix_tag=fix_tag, cwe_ids=cwe_ids, severity=severity, summary=summary,
        advisory_url=advisory_url, git_introduced=git_introduced,
        git_fixed=git_fixed, published=published, modified=modified
    )


def advisory_raw_url(ghsa_id: str, year: str, month: str,
                     reviewed: bool = True) -> str:
    """
    Monta a URL canônica do advisory no GitHub Advisory Database via raw.
    Ex.: advisory_raw_url("GHSA-h5c8-rqwp-cp95", "2024", "01") →
      .../github-reviewed/2024/01/GHSA-h5c8-rqwp-cp95/GHSA-h5c8-rqwp-cp95.json
    """
    bucket = "github-reviewed" if reviewed else "unreviewed"
    return ("https://raw.githubusercontent.com/github/advisory-database/main/"
            f"advisories/{bucket}/{year}/{month}/{ghsa_id}/{ghsa_id}.json")


def fetch_advisory(ghsa_id: str, year: str, month: str,
                   reviewed: bool = True, timeout: int = 25) -> Optional[AdvisoryRecord]:
    """
    Busca + parseia um advisory via rede (canal provado: raw.githubusercontent).
    Guardada: qualquer falha de rede/parse → None (nunca levanta).  Import de
    urllib tardio para não pesar quem só usa `parse_advisory` (offline).
    """
    import urllib.request  # tardio — só quando há busca de rede real

    url = advisory_raw_url(ghsa_id, year, month, reviewed)
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:  # noqa: S310
            if getattr(resp, "status", 200) != 200:
                return None
            data = resp.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 — rede é best-effort
        return None
    return parse_advisory(data)
