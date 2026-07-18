"""
UCO-Sensor — SBOM CycloneDX exporter  (M9.6)
=============================================
Gera um SBOM (Software Bill of Materials) no formato **CycloneDX 1.5 (JSON)** a
partir do `SCAResult` do `VulnerabilityScanner`. Antes o Sensor só emitia SARIF
(findings); SBOM é o inventário de COMPONENTES, requisito de compliance
(US EO 14028, EU Cyber Resilience Act) e insumo padrão de ferramentas
downstream (Dependency-Track, GUAC).

Puro e determinístico: o `timestamp` é injetável (default: omitido) para tornar
a saída reproduzível em testes. Nenhuma rede.

API
---
    from report.sbom import to_cyclonedx
    bom = to_cyclonedx(sca_result)            # dict CycloneDX 1.5
    json.dumps(bom)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ecossistema (como o VulnerabilityScanner nomeia) → tipo de PURL (spec purl).
_PURL_TYPE = {
    "pip": "pypi", "pypi": "pypi",
    "npm": "npm",
    "maven": "maven", "gradle": "maven",
    "cargo": "cargo",
    "go": "golang",
    "composer": "composer",
    "gem": "gem", "rubygems": "gem",
    "nuget": "nuget",
    "hex": "hex",
    "pub": "pub",
    "swift": "swift",
}

_SEVERITY_TO_CYCLONEDX = {
    "CRITICAL": "critical", "HIGH": "high",
    "MEDIUM": "medium", "LOW": "low",
}


def _purl(name: str, version: str, ecosystem: str) -> str:
    """Package URL (purl) canônico. Maven usa `group/artifact`."""
    ptype = _PURL_TYPE.get((ecosystem or "").lower(), "generic")
    n = (name or "").strip()
    if ptype == "maven" and ":" in n:
        group, _, artifact = n.partition(":")
        return f"pkg:maven/{group}/{artifact}@{version}"
    # npm com escopo @scope/pkg mantém a barra; demais são planos
    return f"pkg:{ptype}/{n}@{version}"


def _bom_ref(name: str, version: str, ecosystem: str) -> str:
    return _purl(name, version, ecosystem)


def to_cyclonedx(sca_result: Any, *, timestamp: Optional[str] = None,
                 serial_number: Optional[str] = None) -> Dict[str, Any]:
    """Converte um `SCAResult` (ou dict equivalente) num SBOM CycloneDX 1.5.

    `timestamp` (ISO-8601) e `serial_number` (urn:uuid:...) são injetáveis para
    reprodutibilidade; se omitidos, os campos correspondentes não são incluídos
    (SBOM continua válido — ambos são opcionais na spec).
    """
    deps = getattr(sca_result, "dependencies", None)
    finds = getattr(sca_result, "findings", None)
    if deps is None and isinstance(sca_result, dict):
        deps = sca_result.get("dependencies", [])
        finds = sca_result.get("findings", [])
    deps = deps or []
    finds = finds or []

    components: List[Dict[str, Any]] = []
    seen_refs = set()
    for d in deps:
        name = _attr(d, "name")
        version = _attr(d, "version")
        eco = _attr(d, "ecosystem")
        ref = _bom_ref(name, version, eco)
        if ref in seen_refs:
            continue
        seen_refs.add(ref)
        components.append({
            "type": "library",
            "bom-ref": ref,
            "name": name,
            "version": version,
            "purl": _purl(name, version, eco),
        })

    vulnerabilities: List[Dict[str, Any]] = []
    for f in finds:
        dep = _attr(f, "dependency")
        name = _attr(dep, "name")
        version = _attr(dep, "version")
        eco = _attr(dep, "ecosystem")
        cve = _attr(f, "cve_id")
        score = _attr(f, "cvss_score")
        sev = _SEVERITY_TO_CYCLONEDX.get(_attr(f, "severity"), "unknown")
        cwe = _attr(f, "cwe")
        fixed = _attr(f, "fixed_version")
        vuln: Dict[str, Any] = {
            "id": cve,
            "ratings": [{
                "severity": sev,
                **({"score": float(score)} if isinstance(score, (int, float)) and score else {}),
                "method": "CVSSv3",
            }],
            "affects": [{"ref": _bom_ref(name, version, eco)}],
        }
        cwe_num = _cwe_number(cwe)
        if cwe_num is not None:
            vuln["cwes"] = [cwe_num]
        if fixed:
            vuln["recommendation"] = f"Atualizar {name} para >= {fixed}."
        desc = _attr(f, "description")
        if desc:
            vuln["description"] = str(desc)[:1000]
        vulnerabilities.append(vuln)

    bom: Dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "metadata": {
            "tools": [{"vendor": "APEX", "name": "UCO-Sensor", "component": "SCA (M9.6)"}],
        },
        "components": components,
    }
    if serial_number:
        bom["serialNumber"] = serial_number
    if timestamp:
        bom["metadata"]["timestamp"] = timestamp
    if vulnerabilities:
        bom["vulnerabilities"] = vulnerabilities
    return bom


def _attr(obj: Any, name: str) -> Any:
    if obj is None:
        return ""
    if isinstance(obj, dict):
        return obj.get(name, "")
    return getattr(obj, name, "")


def _cwe_number(cwe: str) -> Optional[int]:
    """'CWE-89' → 89; devolve None se não parsear."""
    if not cwe:
        return None
    s = str(cwe).upper().replace("CWE-", "").strip()
    return int(s) if s.isdigit() else None
