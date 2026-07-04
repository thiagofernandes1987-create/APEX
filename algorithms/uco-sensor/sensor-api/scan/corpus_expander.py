"""
UCO-Sensor — Corpus Expander / Degradation Composer  (M24)
===========================================================
Orquestra os módulos existentes num ÚNICO registro que responde as QUATRO
perguntas do objetivo do corpus, com dado real e sem fabricação:

    QUANDO quebrou        → M23 AdvisoryHarvester (versão `introduced`)
    EM QUAL versão resolveu → M23 AdvisoryHarvester (versão `fixed`)
    ONDE quebrou           → M10 FixDiffLocalizer (arquivo + linha[s] do guard)
    COMO quebrou/foi fixado → M10 (construção de segurança adicionada) +
                              M11 GuardAwareScanner (parou de disparar? perpetuou?)

Por que M24 (fechar o loop rumo a 100/100)
------------------------------------------
M23 destravou o "quando/qual-versão" em escala (advisory OSV via raw).  M10/M11
já davam "onde/como" via before/after.  Faltava o COMPOSITOR que une os dois num
registro auditável por CVE — e um runner em LOTE que o produza para uma lista de
CVEs, transformando o corpus de "9 pares validados à mão" numa esteira
reproduzível.  Método alinhado a CVEfixes (coleta) + D2A (diferencial
fixed/perpetuado/introduced).

Design
------
* `build_degradation(advisory, vuln_src, fixed_src, filename)` — PURO (sem rede):
  recebe um `AdvisoryRecord` (M23) e o par before/after e devolve `DegradationRecord`.
  Nunca levanta; campos ausentes viram "" / listas vazias.
* `DegradationRecord.narrative()` — as 4 respostas em texto auditável.
* `expand_batch(seeds, fetch_pair)` — runner em lote; `fetch_pair(seed)` é um
  callback injetável que devolve (vuln_src, fixed_src, filename) — mantém o
  módulo testável offline e desacoplado da rede.

Versão: introduzido em v3.58.0 (Sprint CI).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# M23 — registro de advisory (quando/qual-versão/commit)
from scan.advisory_harvester import AdvisoryRecord
# M10 — localização do fix (onde/como) via diff before/after
from sast.fix_localizer import FixDiffLocalizer

# M11 — parou de disparar? (import guardado: memory-safety scanner é opcional)
try:
    from sast.guard_aware import GuardAwareScanner  # type: ignore
    _M11_AVAILABLE = True
except Exception:  # noqa: BLE001
    GuardAwareScanner = None  # type: ignore
    _M11_AVAILABLE = False


@dataclass(frozen=True)
class DegradationRecord:
    """As 4 perguntas do goal, respondidas para um CVE com dado real."""
    cve: str
    ghsa: str
    package: str
    ecosystem: str
    # QUANDO / QUAL-VERSÃO (M23)
    when_broke: str
    resolved_in: str
    fix_commit: str
    # ONDE / COMO (M10 + M11)
    where_file: str
    where_lines: List[int] = field(default_factory=list)
    how_constructs: List[str] = field(default_factory=list)   # kinds dos guards
    cwe_ids: List[str] = field(default_factory=list)
    localized: bool = False
    stopped_firing: Optional[bool] = None    # M11: guard parou de disparar?
    perpetuated: Optional[bool] = None        # M11: algo persistiu no fix?
    status: str = "partial"                   # complete | partial | metadata_only

    @property
    def answers_all_four(self) -> bool:
        """
        True só se as 4 perguntas têm resposta CONCRETA.  Uma resposta que
        sinaliza AUSÊNCIA de dado ("não disponível", "n/a", "desconhecida") NÃO
        conta — honestidade legível por máquina (ex.: postgres, cujo CVE-record
        não traz `introduced`, fica corretamente em 3/4, não 4/4).
        """
        def _real(s: str) -> bool:
            low = (s or "").lower()
            return bool(s) and not any(
                mark in low for mark in ("não disponível", "nao disponivel",
                                         "n/a", "desconhecid"))
        return (
            _real(self.when_broke) and _real(self.resolved_in)
            and bool(self.where_file) and bool(self.where_lines)
            and bool(self.how_constructs)
        )

    def narrative(self) -> str:
        """As 4 respostas em texto auditável (pt-BR)."""
        where = (f"{self.where_file}:L{','.join(map(str, self.where_lines))}"
                 if self.where_lines else (self.where_file or "não localizado"))
        how = ", ".join(self.how_constructs) if self.how_constructs else "não localizado"
        extra = ""
        if self.stopped_firing is not None:
            extra = (f"  • parou de disparar no fix: "
                     f"{'sim' if self.stopped_firing else 'não'}")
            if self.perpetuated:
                extra += "  • ALGO PERPETUOU (persistiu no fix)"
        return (
            f"[{self.cve} / {self.ghsa}] {self.package} ({self.ecosystem}) "
            f"— {', '.join(self.cwe_ids) or 'CWE ?'}\n"
            f"  • QUANDO quebrou:        {self.when_broke}\n"
            f"  • EM QUAL versão resolveu: {self.resolved_in}"
            f"  (commit {self.fix_commit[:12] or '?'})\n"
            f"  • ONDE quebrou:           {where}\n"
            f"  • COMO (construção do fix): {how}\n"
            f"{extra}".rstrip()
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cve": self.cve, "ghsa": self.ghsa, "package": self.package,
            "ecosystem": self.ecosystem, "when_broke": self.when_broke,
            "resolved_in": self.resolved_in, "fix_commit": self.fix_commit,
            "where_file": self.where_file, "where_lines": list(self.where_lines),
            "how_constructs": list(self.how_constructs), "cwe_ids": list(self.cwe_ids),
            "localized": self.localized, "stopped_firing": self.stopped_firing,
            "perpetuated": self.perpetuated, "status": self.status,
            "answers_all_four": self.answers_all_four,
        }


def build_degradation(
    advisory: AdvisoryRecord,
    vuln_src: str,
    fixed_src: str,
    filename: str = "",
) -> DegradationRecord:
    """
    Compõe o registro de degradação (4 perguntas) unindo M23 + M10 (+ M11).
    PURO e defensivo: nunca levanta.  Onde entra: chamado por `expand_batch`
    e por scripts de relatório do corpus.
    """
    # ── ONDE / COMO: M10 localiza os guards adicionados no diff ──────────────
    where_lines: List[int] = []
    how_constructs: List[str] = []
    cwe_from_guards: List[str] = []
    localized = False
    try:
        loc = FixDiffLocalizer().localize(vuln_src, fixed_src, filename=filename)
        localized = loc.guard_present_in_fix_absent_in_vuln
        for g in loc.added_guards:
            where_lines.append(g.line)
            if g.kind not in how_constructs:
                how_constructs.append(g.kind)
            if g.cwe_class and g.cwe_class not in cwe_from_guards:
                cwe_from_guards.append(g.cwe_class)
    except Exception:  # noqa: BLE001 — M10 nunca deve derrubar o compositor
        pass

    # ── COMO (validação): M11 diz se o guard parou de disparar / perpetuou ───
    stopped_firing: Optional[bool] = None
    perpetuated: Optional[bool] = None
    ext = _ext_of(filename)
    if _M11_AVAILABLE and ext:
        try:
            scanner = GuardAwareScanner()
            v_find = scanner.scan(vuln_src, ext)
            f_find = scanner.scan(fixed_src, ext)
            nv, nf = len(v_find), len(f_find)
            if nv or nf:
                stopped_firing = nf < nv          # menos achados no fix
                perpetuated = nf > 0               # algo persistiu no fix
        except Exception:  # noqa: BLE001
            pass

    # CWE: prioriza o do advisory (autoritativo); complementa com o do guard
    cwe_ids = list(advisory.cwe_ids) or cwe_from_guards

    # status: completo se as 4 respostas existem
    rec = DegradationRecord(
        cve=advisory.cve, ghsa=advisory.ghsa_id, package=advisory.package,
        ecosystem=advisory.ecosystem, when_broke=advisory.when_broke,
        resolved_in=advisory.resolved_in, fix_commit=advisory.fix_commit,
        where_file=filename, where_lines=where_lines,
        how_constructs=how_constructs, cwe_ids=cwe_ids, localized=localized,
        stopped_firing=stopped_firing, perpetuated=perpetuated,
        status="partial",
    )
    status = "complete" if rec.answers_all_four else (
        "partial" if localized else "metadata_only")
    # dataclass é frozen → recria trocando só o status calculado
    return _with_status(rec, status)


def _with_status(rec: DegradationRecord, status: str) -> DegradationRecord:
    """Recria o record (frozen) trocando só o status."""
    d = rec.to_dict()
    return DegradationRecord(
        cve=d["cve"], ghsa=d["ghsa"], package=d["package"],
        ecosystem=d["ecosystem"], when_broke=d["when_broke"],
        resolved_in=d["resolved_in"], fix_commit=d["fix_commit"],
        where_file=d["where_file"], where_lines=d["where_lines"],
        how_constructs=d["how_constructs"], cwe_ids=d["cwe_ids"],
        localized=d["localized"], stopped_firing=d["stopped_firing"],
        perpetuated=d["perpetuated"], status=status,
    )


def expand_batch(
    seeds: List[Tuple[AdvisoryRecord, Any]],
    fetch_pair: Callable[[Any], Optional[Tuple[str, str, str]]],
) -> List[DegradationRecord]:
    """
    Runner em LOTE: para cada (advisory, seed), `fetch_pair(seed)` devolve
    (vuln_src, fixed_src, filename) — ou None se indisponível.  Compõe um
    DegradationRecord por CVE.  Callback injetável = testável offline e
    desacoplado da rede (o fetch real por TAG via raw fica no chamador).
    """
    out: List[DegradationRecord] = []
    for advisory, seed in seeds:
        pair = None
        try:
            pair = fetch_pair(seed)
        except Exception:  # noqa: BLE001 — falha de um item não derruba o lote
            pair = None
        if pair is None:
            # só metadados (M23) — ainda responde 2 das 4 perguntas
            out.append(_with_status(
                build_degradation(advisory, "", "", ""), "metadata_only"))
            continue
        vuln_src, fixed_src, filename = pair
        out.append(build_degradation(advisory, vuln_src, fixed_src, filename))
    return out


def _ext_of(filename: str) -> str:
    """Extensão com ponto (.c/.py/...) ou '' se não houver."""
    if "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()
