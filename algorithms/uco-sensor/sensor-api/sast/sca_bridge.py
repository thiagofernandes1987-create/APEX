"""
UCO-Sensor — SCA Bridge (OSV-Scanner)
======================================
Resposta ao pedido literal do usuário: *"vamos integrar ou o
Osv-scanner ou Grype, avalie qual dos dois trazem mais Roi e que não
gerem custos"*.

Decisão: **OSV-Scanner** (Google, Apache-2.0). Evidência empírica
coletada nesta sessão, neste mesmo sandbox de rede restrita:

* OSV-Scanner em modo ``--offline --download-offline-databases`` baixa
  o banco de vulnerabilidades do Google Cloud Storage (host
  tipicamente liberado) e depois escaneia 100% localmente, sem chamada
  de rede por scan. Testado e validado: detecta corretamente
  CVE-2023-32681 (`requests==2.27.0`) com metadados completos.
* Grype depende de ``grype.anchore.io``/``toolbox-data.anchore.io`` —
  ambos bloqueados pelo proxy deste sandbox — e falha por completo
  (``failed to load vulnerability db: database does not exist``).
* Ambos são gratuitos/Apache-2.0; o diferencial real de custo é
  **alcançabilidade de rede**, não licenciamento — e OSV-Scanner vence
  de forma decisiva nesse eixo. Cobertura de ecossistemas (PyPI, npm,
  Go, crates.io, GHSA) também se alinha melhor ao footprint
  multi-linguagem já existente no UCO Sensor do que o foco adicional de
  Grype em pacotes de SO (apk/dpkg/rpm), fora do escopo atual.

Design (mesmo padrão de ``lang_adapters/tree_sitter_bridge.py``):
ferramenta externa opcional, nunca quebra o import, degrada de forma
graciosa quando o binário não está disponível no ambiente de deploy.
``available()`` apenas verifica se o binário existe em PATH (ou em
``OSV_SCANNER_BIN``) — não dispara rede; o download do DB offline só
acontece dentro de ``scan_manifest`` quando de fato chamado.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from sast.scanner import SASTFinding, SASTResult

_DEFAULT_BIN = "osv-scanner"

# CVSS score -> severidade UCO, mesmos cortes usados no resto do sensor.
_SCORE_BUCKETS = (
    (9.0, "CRITICAL"),
    (7.0, "HIGH"),
    (4.0, "MEDIUM"),
)

_SEVERITY_DEBT: Dict[str, int] = {
    "CRITICAL": 240,
    "HIGH":     120,
    "MEDIUM":    60,
    "LOW":       30,
}


def _severity_for_score(score: Optional[float]) -> str:
    if score is None:
        return "MEDIUM"
    for threshold, label in _SCORE_BUCKETS:
        if score >= threshold:
            return label
    return "LOW"


class OSVScannerBridge:
    """
    Bridge opcional para o binário ``osv-scanner``.

    Parameters
    ----------
    binary
        Caminho/nome do executável. Default: variável de ambiente
        ``OSV_SCANNER_BIN``, ou ``"osv-scanner"`` em PATH.
    """

    def __init__(self, binary: Optional[str] = None) -> None:
        self.binary = binary or os.environ.get("OSV_SCANNER_BIN", _DEFAULT_BIN)
        self._resolved: Optional[str] = None
        self._checked = False

    def available(self) -> bool:
        """True se o binário existir em PATH — não verifica rede/DB."""
        if not self._checked:
            self._checked = True
            self._resolved = shutil.which(self.binary)
        return self._resolved is not None

    def scan_manifest(
        self,
        content: str,
        filename: str,
        offline: bool = True,
        timeout: int = 60,
    ) -> SASTResult:
        """
        Escaneia um único arquivo de manifesto de dependências (ex.:
        ``requirements.txt``, ``package-lock.json``, ``go.sum``,
        ``Cargo.lock``) e retorna um ``SASTResult`` no mesmo formato
        dos demais scanners SAST do UCO Sensor.

        Quando o binário não está disponível, retorna um
        ``SASTResult`` vazio com ``parse_error=True`` — mesma
        semântica de "degradar sem quebrar" do ``TreeSitterBridge``.
        Ausência de binário NÃO deve ser confundida com "0
        vulnerabilidades encontradas"; o chamador deve checar
        ``available()`` antes de decidir como reportar isso ao
        usuário final.
        """
        if not self.available():
            return SASTResult(parse_error=True)

        with tempfile.TemporaryDirectory(prefix="uco-sca-") as tmpdir:
            manifest_path = Path(tmpdir) / filename
            manifest_path.write_text(content, encoding="utf-8")

            cmd = [self._resolved, "--format", "json", "--recursive"]
            if offline:
                cmd += ["--offline", "--download-offline-databases"]
            cmd.append(str(tmpdir))

            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=timeout,
                )
            except (subprocess.TimeoutExpired, OSError):
                return SASTResult(parse_error=True)

            # osv-scanner sai com status 1 quando ENCONTRA vulnerabilidades
            # (não é erro) e 0 quando o scan está limpo; só >1 é falha real.
            if proc.returncode > 1 or not proc.stdout.strip():
                return SASTResult(parse_error=proc.returncode > 1)

            try:
                payload = json.loads(proc.stdout)
            except json.JSONDecodeError:
                return SASTResult(parse_error=True)

        return _to_sast_result(payload)


def _to_sast_result(payload: Dict[str, Any]) -> SASTResult:
    findings: List[SASTFinding] = []

    for result in payload.get("results", []):
        for pkg_entry in result.get("packages", []):
            pkg = pkg_entry.get("package", {})
            pkg_name = pkg.get("name", "unknown")
            pkg_version = pkg.get("version", "?")
            pkg_ecosystem = pkg.get("ecosystem", "")

            vulns_by_id = {v.get("id"): v for v in pkg_entry.get("vulnerabilities", [])}

            for group in pkg_entry.get("groups", []):
                ids = group.get("ids", [])
                if not ids:
                    continue
                primary_id = ids[0]
                vuln = vulns_by_id.get(primary_id, {})
                aliases = group.get("aliases", [])
                cve = next((a for a in aliases if a.startswith("CVE-")), primary_id)

                try:
                    score = float(group.get("max_severity") or 0) or None
                except (TypeError, ValueError):
                    score = None
                severity = _severity_for_score(score)

                details = (vuln.get("details") or "").strip()
                description = details[:500] if details else f"Vulnerabilidade conhecida em {pkg_name} {pkg_version} ({pkg_ecosystem})."

                refs = vuln.get("references", [])
                ref_url = refs[0].get("url") if refs else None

                findings.append(SASTFinding(
                    rule_id=f"SCA-{primary_id}",
                    severity=severity,
                    cwe_id="CWE-1395",
                    owasp="A06:2021",
                    title=f"Dependência vulnerável: {pkg_name}@{pkg_version} ({cve})",
                    description=description,
                    line=0,
                    col=0,
                    code_snippet=f"{pkg_name}=={pkg_version}",
                    remediation=(
                        f"Atualizar {pkg_name} para uma versão corrigida. "
                        + (f"Referência: {ref_url}" if ref_url else "Ver advisory na referência do alias.")
                    ),
                    debt_minutes=_SEVERITY_DEBT.get(severity, 60),
                    confidence=0.95,
                    explanation=f"Identificado via OSV-Scanner (banco offline OSV.dev), alias(es): {', '.join(aliases) or primary_id}.",
                ))

    total_debt = sum(f.debt_minutes for f in findings)
    crit = sum(1 for f in findings if f.severity == "CRITICAL")
    high = sum(1 for f in findings if f.severity == "HIGH")
    if crit:
        rating = "E"
    elif high:
        rating = "D" if high > 2 else "C"
    elif findings:
        rating = "B"
    else:
        rating = "A"

    return SASTResult(
        findings=findings,
        total_debt_minutes=total_debt,
        security_rating=rating,
        parse_error=False,
    )
