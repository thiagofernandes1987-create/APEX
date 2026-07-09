"""
UCO-Sensor — Unified SAST Pipeline  (DS)
========================================
Um único ponto de entrada que roda TODOS os motores de segurança aplicáveis a um
arquivo e agrega os findings num formato normalizado — para que a CLI (`uco-sensor
sast <path>`) produza um relatório de segurança completo SEM o usuário ter de
chamar motor por motor ou subir a API.

Motores compostos (degradação graciosa: cada import é guardado):
  * M7.2  TaintAnalyzer        — taint intra-procedural (Python): SQLi, cmd
                                 injection, template, code, path, desserialização.
  * multilang SAST             — regras por-linguagem (JS/TS/Java/Go/PHP/Rust/C#…).
  * M11   GuardAwareScanner    — memory-safety (C/C++): overflow/bounds sem guard.
  * M28   TOCTOU               — race check→use (Python).

Puro (exceto leitura de arquivo no walker).  Nunca levanta: um motor que falha em
um arquivo apenas não contribui findings para aquele arquivo.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Extensões de código-fonte que varremos (subconjunto pragmático).
_SOURCE_EXTS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".php",
    ".rb", ".rs", ".cs", ".kt", ".c", ".h", ".cpp", ".cc", ".cxx", ".hpp",
}
_MEMORY_UNSAFE = {".c", ".h", ".cpp", ".cc", ".cxx", ".hpp"}
_PY = {".py"}

# diretórios ignorados no walk
_SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv",
              ".mypy_cache", ".pytest_cache", "dist", "build", ".tox"}

_SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "MODERATE": 2, "LOW": 3, "": 4}


@dataclass
class SastFinding:
    engine: str
    rule_id: str
    vuln_type: str
    severity: str
    cwe_id: str
    line: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "engine": self.engine, "rule_id": self.rule_id,
            "vuln_type": self.vuln_type, "severity": self.severity,
            "cwe_id": self.cwe_id, "line": self.line,
        }


@dataclass
class FileSastResult:
    path: str
    ext: str
    findings: List[SastFinding] = field(default_factory=list)
    error: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "ext": self.ext, "error": self.error,
                "findings": [f.to_dict() for f in self.findings]}


def scan_source(source: str, ext: str) -> List[SastFinding]:
    """Roda os motores aplicáveis à extensão e devolve findings normalizados."""
    out: List[SastFinding] = []
    ext = ext.lower()

    if ext in _PY:
        # M7.2 — taint intra-procedural
        try:
            from sast.taint_engine import TaintAnalyzer
            for fl in TaintAnalyzer().analyze(source).flows:
                out.append(SastFinding(
                    "M7.2-taint", fl.rule_id, fl.vuln_type, fl.severity,
                    fl.cwe_id, getattr(fl, "sink_line", 0)))
        except Exception:  # noqa: BLE001
            pass
        # M28 — TOCTOU
        try:
            from sast.toctou import TOCTOUDetector
            for f in TOCTOUDetector().scan(source):
                out.append(SastFinding(
                    "M28-toctou", f.rule_id, "TOCTOU", f.severity,
                    f.cwe_id, getattr(f, "use_line", 0)))
        except Exception:  # noqa: BLE001
            pass

    if ext in _MEMORY_UNSAFE:
        # M11 — memory-safety guard-aware
        try:
            from sast.guard_aware import GuardAwareScanner
            for f in GuardAwareScanner().scan(source, ext):
                out.append(SastFinding(
                    "M11-guard", f.rule_id, "MEMORY_SAFETY", f.severity,
                    f.cwe_id, getattr(f, "line", 0)))
        except Exception:  # noqa: BLE001
            pass

    # multilang SAST — cobre todas as linguagens (regras por-linguagem)
    try:
        from sast.multilang_scanner import scan_multilang
        res = scan_multilang(source, file_extension=ext)
        for f in res.findings:
            out.append(SastFinding(
                "multilang", f.rule_id, getattr(f, "title", "") or f.rule_id,
                f.severity, f.cwe_id, getattr(f, "line", 0)))
    except Exception:  # noqa: BLE001
        pass

    # dedup: alguns motores emitem o mesmo finding mais de uma vez (ex.: o taint
    # engine gera 1 flow por caminho source→sink, então 2 sources para o mesmo
    # sink viram 2 findings idênticos na mesma linha).  Colapsa por identidade.
    seen: set = set()
    deduped: List[SastFinding] = []
    for f in out:
        key = (f.engine, f.rule_id, f.cwe_id, f.line, f.vuln_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
    deduped.sort(key=lambda f: (_SEV_ORDER.get(f.severity.upper(), 4), f.line))
    return deduped


def scan_path(path: str, max_files: int = 0,
              include_tests: bool = True) -> Dict[str, Any]:
    """Varre um arquivo ou diretório e agrega findings de segurança de todos os
    motores.  Retorna um relatório serializável (dict)."""
    targets: List[str] = []
    if os.path.isfile(path):
        targets = [path]
    else:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in _SOURCE_EXTS:
                    continue
                if not include_tests and ("test" in fn.lower()):
                    continue
                targets.append(os.path.join(root, fn))
    if max_files and len(targets) > max_files:
        targets = targets[:max_files]

    file_results: List[FileSastResult] = []
    sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for fp in targets:
        ext = os.path.splitext(fp)[1].lower()
        fr = FileSastResult(path=fp, ext=ext)
        try:
            src = open(fp, encoding="utf-8", errors="replace").read()
            fr.findings = scan_source(src, ext)
        except Exception as e:  # noqa: BLE001
            fr.error = str(e)[:120]
        for f in fr.findings:
            key = "MODERATE" if f.severity.upper() == "MODERATE" else f.severity.upper()
            if key == "MODERATE":
                key = "MEDIUM"
            if key in sev_counts:
                sev_counts[key] += 1
        if fr.findings or fr.error:
            file_results.append(fr)

    total = sum(sev_counts.values())
    return {
        "root": path,
        "files_scanned": len(targets),
        "files_with_findings": len(file_results),
        "total_findings": total,
        "severity_counts": sev_counts,
        "rating": ("CRITICAL" if sev_counts["CRITICAL"] else
                   "HIGH" if sev_counts["HIGH"] else
                   "MEDIUM" if sev_counts["MEDIUM"] else
                   "LOW" if sev_counts["LOW"] else "CLEAN"),
        "file_results": [fr.to_dict() for fr in file_results],
    }
