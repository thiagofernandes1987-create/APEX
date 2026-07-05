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


# ── Painel de detectores para a validação "parou de disparar?" (Sprint CS) ────
# DIAGNÓSTICO (sinal captado e não processado): até a CR, a validação before/after
# usava SÓ o M11 (memory-safety, GA01/GA02 — C-oriented).  Para os CVEs PyPI de
# injeção/XSS/DoS (a maioria do corpus) o M11 não dispara em nenhum lado →
# `stopped_firing` ficava null.  Os detectores CERTOS para essas classes já
# existiam no Sensor mas NÃO eram usados aqui: M7.2 taint (Python), M20 taint-lite
# (PHP/JS), M28 TOCTOU.  Este painel os inclui → a validação passa a ser
# significativa para todas as classes, não só memory-safety.
def _count_sensor_findings(src: str, ext: str) -> int:
    """
    Nº total de achados dos detectores de SEGURANÇA do Sensor aplicáveis a *src*.
    Usado para o before/after: se a contagem cai do vuln para o fixed, o sinal
    "parou de disparar".  Cada import é guardado — degrada sem levantar.  Onde
    entra: chamado por `build_degradation` para vuln_src e fixed_src. (CS v3.68.0)
    """
    total = 0
    # M11 — memory-safety (C/C++/qualquer ext)
    if _M11_AVAILABLE:
        try:
            total += len(GuardAwareScanner().scan(src, ext))
        except Exception:  # noqa: BLE001
            pass
    is_py = ext.lower() in (".py", "py")
    if is_py:
        # M22 — taint fluxo-sensível sobre a CFG do UCO V4.  USAMOS O M22 (não o
        # M7.2) DE PROPÓSITO: o M22 herda o gating SQL arg[0] e o sanitizador
        # int()/cast do M17/CD, então NÃO marca query parametrizada como injeção
        # (o M7.2 base ainda tem esse FP — ver dívida no inventário CS).  Assim a
        # validação before/after fica correta: vuln concatenado dispara, fixed
        # parametrizado não → stopped_firing=True.
        try:
            from sast.taint_cfg import CFGTaintAnalyzer   # M22
            total += len(CFGTaintAnalyzer().analyze(src))
        except Exception:  # noqa: BLE001
            pass
        # M28 — TOCTOU / race (CWE-367)
        try:
            from sast.toctou import TOCTOUDetector       # M28
            total += len(TOCTOUDetector().scan(src))
        except Exception:  # noqa: BLE001
            pass
    else:
        # M20 — taint-lite (PHP/JS), onde o AST-Python não se aplica
        try:
            from sast.taint_lite import TaintLite         # M20
            total += len(TaintLite().scan(src, ext))
        except Exception:  # noqa: BLE001
            pass
    return total


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
    # metadados do advisory OSV (janela de exposição + gravidade) — campos com
    # default DEPOIS dos obrigatórios (dataclass exige essa ordem)
    published: str = ""
    modified: str = ""
    severity: str = ""
    where_lines: List[int] = field(default_factory=list)
    how_constructs: List[str] = field(default_factory=list)   # kinds dos guards
    cwe_ids: List[str] = field(default_factory=list)
    localized: bool = False
    stopped_firing: Optional[bool] = None    # painel: contagem caiu vuln→fix?
    perpetuated: Optional[bool] = None        # painel: ainda dispara no fix?
    findings_vuln: Optional[int] = None       # evidência real: nº achados no vuln
    findings_fixed: Optional[int] = None      # evidência real: nº achados no fix
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

    @property
    def validated(self) -> bool:
        """
        Dimensão SEPARADA de `answers_all_four`: True quando o painel de
        detectores (M11+M22+M28+M20) produziu medida real before/after
        (`stopped_firing` conhecido).  Manter as duas flags distintas evita
        conflar "localizado (4/4 metadados)" com "validado dinamicamente" —
        achado 1.2/D6 da auditoria adversarial.
        """
        return self.stopped_firing is not None

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
            "ecosystem": self.ecosystem, "published": self.published,
            "modified": self.modified, "severity": self.severity,
            "when_broke": self.when_broke,
            "resolved_in": self.resolved_in, "fix_commit": self.fix_commit,
            "where_file": self.where_file, "where_lines": list(self.where_lines),
            "how_constructs": list(self.how_constructs), "cwe_ids": list(self.cwe_ids),
            "localized": self.localized, "stopped_firing": self.stopped_firing,
            "perpetuated": self.perpetuated,
            "findings_vuln": self.findings_vuln,
            "findings_fixed": self.findings_fixed,
            "status": self.status,
            "answers_all_four": self.answers_all_four,
            "validated": self.validated,
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

    # ── COMO (validação): o Sensor parou de disparar no fix? Algo perpetuou? ──
    # Painel de detectores (M11 + M7.2 + M20 + M28), não só memory-safety (CS).
    # Semântica HONESTA e mensurável: stopped_firing = a contagem de achados dos
    # detectores do Sensor CAIU do vuln para o fixed; perpetuated = ainda há
    # achado no fixed.  Quando NENHUM detector dispara no vuln (nv==0), a questão
    # é N/A para esta classe (localizada por diff via M10) → mantém-se null,
    # honestamente, e as contagens reais ficam registradas para auditoria.
    stopped_firing: Optional[bool] = None
    perpetuated: Optional[bool] = None
    findings_vuln: Optional[int] = None
    findings_fixed: Optional[int] = None
    ext = _ext_of(filename)
    if ext:
        try:
            nv = _count_sensor_findings(vuln_src, ext)
            nf = _count_sensor_findings(fixed_src, ext)
            findings_vuln, findings_fixed = nv, nf
            if nv > 0:                              # só é significativo se disparou no vuln
                stopped_firing = nf < nv
                perpetuated = nf > 0
        except Exception:  # noqa: BLE001
            pass

    # CWE: prioriza o do advisory (autoritativo); complementa com o do guard
    cwe_ids = list(advisory.cwe_ids) or cwe_from_guards

    # status: completo se as 4 respostas existem
    rec = DegradationRecord(
        cve=advisory.cve, ghsa=advisory.ghsa_id, package=advisory.package,
        ecosystem=advisory.ecosystem, published=getattr(advisory, "published", ""),
        modified=getattr(advisory, "modified", ""), severity=getattr(advisory, "severity", ""),
        when_broke=advisory.when_broke,
        resolved_in=advisory.resolved_in, fix_commit=advisory.fix_commit,
        where_file=filename, where_lines=where_lines,
        how_constructs=how_constructs, cwe_ids=cwe_ids, localized=localized,
        stopped_firing=stopped_firing, perpetuated=perpetuated,
        findings_vuln=findings_vuln, findings_fixed=findings_fixed,
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
        ecosystem=d["ecosystem"], published=d.get("published", ""),
        modified=d.get("modified", ""), severity=d.get("severity", ""),
        when_broke=d["when_broke"],
        resolved_in=d["resolved_in"], fix_commit=d["fix_commit"],
        where_file=d["where_file"], where_lines=d["where_lines"],
        how_constructs=d["how_constructs"], cwe_ids=d["cwe_ids"],
        localized=d["localized"], stopped_firing=d["stopped_firing"],
        perpetuated=d["perpetuated"],
        findings_vuln=d.get("findings_vuln"), findings_fixed=d.get("findings_fixed"),
        status=status,
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


# ── M30 (DO v3.90.0): degradação MULTI-ARQUIVO ───────────────────────────────
# Fixes que espalham a correção por VÁRIOS arquivos (refactor de segurança,
# merge-commits) não completam quando olhamos 1 arquivo só.  `build_degradation_multi`
# roda o M24 em CADA par (arquivo) e escolhe o registro que MELHOR responde as 4
# perguntas (prioriza `complete` > `partial` > `metadata_only`), agregando o
# ONDE (arquivo:linha) de todos os arquivos que localizaram guard.  Onde entra:
# chamado pela esteira quando o commit toca >1 arquivo-fonte.  O par de cada
# arquivo já deve vir do 1º pai (mainline) em merge-commits (responsabilidade do
# M27/fetcher — o before/after tem que ser honesto).
def build_degradation_multi(
    advisory: "AdvisoryRecord",
    file_pairs: List[Tuple[str, str, str]],
) -> DegradationRecord:
    """
    file_pairs: lista de (vuln_src, fixed_src, filename).  Retorna o melhor
    DegradationRecord (o que responde as 4 perguntas), agregando o ONDE dos
    demais arquivos que também localizaram guard.  PURO e defensivo.
    """
    best: Optional[DegradationRecord] = None
    extra_where: List[str] = []
    _rank = {"complete": 3, "partial": 2, "metadata_only": 1}
    for vuln_src, fixed_src, filename in file_pairs:
        rec = build_degradation(advisory, vuln_src, fixed_src, filename)
        if rec.where_lines and rec.where_file:
            extra_where.append(f"{rec.where_file}:L{','.join(map(str, rec.where_lines))}")
        if best is None or _rank.get(rec.status, 0) > _rank.get(best.status, 0):
            best = rec
    if best is None:                       # nenhum arquivo → só metadados
        return _with_status(build_degradation(advisory, "", "", ""), "metadata_only")
    # anexa, no registro vencedor, as localizações dos OUTROS arquivos (auditoria)
    if len(extra_where) > 1:
        d = best.to_dict()
        d["where_file"] = " + ".join(
            sorted({w.split(":")[0] for w in extra_where}))
        return _with_status(DegradationRecord(
            cve=d["cve"], ghsa=d["ghsa"], package=d["package"],
            ecosystem=d["ecosystem"], when_broke=d["when_broke"],
            resolved_in=d["resolved_in"], fix_commit=d["fix_commit"],
            where_file=d["where_file"], where_lines=d["where_lines"],
            how_constructs=d["how_constructs"], cwe_ids=d["cwe_ids"],
            localized=d["localized"], stopped_firing=d["stopped_firing"],
            perpetuated=d["perpetuated"],
            findings_vuln=d.get("findings_vuln"), findings_fixed=d.get("findings_fixed"),
        ), best.status)
    return best
