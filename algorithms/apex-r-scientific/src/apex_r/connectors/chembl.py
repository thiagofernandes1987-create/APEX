"""Conector ChEMBL Activity API com URL allowlisted e normalização conservadora."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from ..contracts import GateEnvelope, GateStatus
from ..data import AffinityMeasurement, LicenseClass, SourceDefinition


CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
_ALLOWED_HOSTS = {"www.ebi.ac.uk"}
_ENDPOINTS = {"Kd", "Ki", "IC50"}


def chembl_source(release: str) -> SourceDefinition:
    return SourceDefinition(
        source_id="chembl",
        name="ChEMBL",
        version=release,
        license_name="CC BY-SA 3.0 Unported",
        license_class=LicenseClass.ATTRIBUTION,
        uri="https://www.ebi.ac.uk/chembl/",
        redistribution_allowed=True,
    )


@dataclass(frozen=True)
class ChemblActivityQuery:
    target_chembl_id: str
    standard_type: str
    standard_units: str = "nM"
    limit: int = 1000
    offset: int = 0
    standard_relation: str = "="

    def __post_init__(self) -> None:
        if not self.target_chembl_id.startswith("CHEMBL"):
            raise ValueError("target_chembl_id deve ser um identificador CHEMBL")
        if self.standard_type not in _ENDPOINTS:
            raise ValueError("Cada consulta deve selecionar exatamente Kd, Ki ou IC50")
        if self.standard_units not in {"M", "mM", "uM", "nM", "pM"}:
            raise ValueError("Unidade padrão não suportada")
        if not 1 <= self.limit <= 1000 or self.offset < 0:
            raise ValueError("limit deve estar entre 1 e 1000 e offset deve ser não negativo")
        if self.standard_relation not in {"=", "<", "<=", ">", ">="}:
            raise ValueError("standard_relation deve preservar uma relação ChEMBL suportada")

    def url(self) -> str:
        parameters = {
            "target_chembl_id": self.target_chembl_id,
            "standard_type": self.standard_type,
            "standard_units": self.standard_units,
            "standard_relation": self.standard_relation,
            "limit": self.limit,
            "offset": self.offset,
            "standard_relation": self.standard_relation,
            "format": "json",
        }
        return f"{CHEMBL_API_BASE}/activity.json?{urlencode(parameters)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_chembl_id": self.target_chembl_id,
            "standard_type": self.standard_type,
            "standard_units": self.standard_units,
            "limit": self.limit,
            "offset": self.offset,
            "url": self.url(),
        }


def _validate_api_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("URL de paginação fora do host HTTPS allowlisted do ChEMBL")
    if not parsed.path.startswith("/chembl/api/data/activity"):
        raise ValueError("URL de paginação aponta para recurso ChEMBL inesperado")


def parse_activity_page(payload: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(payload, bytes):
        data = json.loads(payload.decode("utf-8"))
    elif isinstance(payload, str):
        data = json.loads(payload)
    else:
        data = dict(payload)
    if not isinstance(data.get("activities"), list) or not isinstance(data.get("page_meta"), dict):
        raise ValueError("Resposta ChEMBL não contém activities e page_meta válidos")
    return data


def normalize_activity_page(
    payload: bytes | str | Mapping[str, Any], snapshot_id: str
) -> tuple[AffinityMeasurement, ...]:
    data = parse_activity_page(payload)
    records: list[AffinityMeasurement] = []
    for raw in data["activities"]:
        required = (
            "activity_id",
            "molecule_chembl_id",
            "target_chembl_id",
            "standard_type",
            "standard_relation",
            "standard_value",
            "standard_units",
        )
        if any(raw.get(field) in {None, ""} for field in required):
            continue
        try:
            records.append(
                AffinityMeasurement(
                    record_id=f"chembl:{raw['activity_id']}",
                    snapshot_id=snapshot_id,
                    source_record_id=str(raw["activity_id"]),
                    compound_id=str(raw["molecule_chembl_id"]),
                    target_id=str(raw["target_chembl_id"]),
                    endpoint=str(raw["standard_type"]),
                    relation=str(raw["standard_relation"]),
                    value=float(raw["standard_value"]),
                    unit=str(raw["standard_units"]),
                    conditions={
                        key: str(raw[key])
                        for key in ("assay_chembl_id", "document_chembl_id", "pchembl_value")
                        if raw.get(key) not in {None, ""}
                    },
                )
            )
        except (TypeError, ValueError):
            continue
    return tuple(records)


@dataclass(frozen=True)
class ActivityPageAudit:
    """Resultado de QC das páginas brutas antes de congelar um snapshot."""

    gate: GateEnvelope
    total_count_reported: int
    raw_records: int
    normalized_records: int
    exact_records: int
    censored_records: int
    unique_activities: int
    unique_molecules: int
    records_with_structure: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.gate.to_dict(),
            "total_count_reported": self.total_count_reported,
            "raw_records": self.raw_records,
            "normalized_records": self.normalized_records,
            "exact_records": self.exact_records,
            "censored_records": self.censored_records,
            "unique_activities": self.unique_activities,
            "unique_molecules": self.unique_molecules,
            "records_with_structure": self.records_with_structure,
        }


def audit_activity_pages(
    paths: tuple[Path, ...] | list[Path],
    query: ChemblActivityQuery,
    *,
    require_complete: bool = True,
    require_structure: bool = True,
    run_id: str | None = None,
) -> ActivityPageAudit:
    """Verifica completude, schema, tipagem e duplicatas sem ajustar coeficientes."""
    if not paths:
        raise ValueError("A auditoria exige ao menos uma página ChEMBL")

    total_counts: set[int] = set()
    activity_ids: list[str] = []
    molecule_ids: set[str] = set()
    raw_records = 0
    normalized_records = 0
    exact_records = 0
    censored_records = 0
    records_with_structure = 0
    mismatched_records = 0
    last_next: str | None = None

    for path in paths:
        data = parse_activity_page(path.read_bytes())
        page_meta = data["page_meta"]
        try:
            total_counts.add(int(page_meta["total_count"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Página {path} não declara total_count válido") from exc
        last_next = str(page_meta["next"]) if page_meta.get("next") else None
        raw_records += len(data["activities"])
        normalized_records += len(normalize_activity_page(data, "audit-pending-snapshot"))
        for raw in data["activities"]:
            activity_id = raw.get("activity_id")
            if activity_id not in {None, ""}:
                activity_ids.append(str(activity_id))
            molecule_id = raw.get("molecule_chembl_id")
            if molecule_id not in {None, ""}:
                molecule_ids.add(str(molecule_id))
            relation = raw.get("standard_relation")
            if relation == "=":
                exact_records += 1
            elif relation in {"<", "<=", ">", ">="}:
                censored_records += 1
            if raw.get("canonical_smiles") not in {None, ""}:
                records_with_structure += 1
            if (
                raw.get("target_chembl_id") != query.target_chembl_id
                or raw.get("standard_type") != query.standard_type
                or raw.get("standard_units") != query.standard_units
                or raw.get("standard_relation") != query.standard_relation
            ):
                mismatched_records += 1

    total_count_reported = next(iter(total_counts)) if len(total_counts) == 1 else -1
    unique_activities = len(set(activity_ids))
    duplicate_activities = len(activity_ids) - unique_activities
    errors: list[str] = []
    if len(total_counts) != 1:
        errors.append("As páginas discordam sobre page_meta.total_count")
    if normalized_records != raw_records:
        errors.append(
            f"{raw_records - normalized_records} registros não satisfazem o schema normalizado"
        )
    if duplicate_activities:
        errors.append(f"Foram encontrados {duplicate_activities} activity_id duplicados")
    if mismatched_records:
        errors.append(f"{mismatched_records} registros violam alvo, endpoint ou unidade da consulta")
    if require_complete and (
        total_count_reported < 0
        or raw_records != total_count_reported
        or last_next is not None
    ):
        errors.append(
            "A aquisição está parcial: total recebido ou paginação não corresponde ao total declarado"
        )
    if require_structure and records_with_structure != raw_records:
        errors.append(
            f"{raw_records - records_with_structure} registros não possuem canonical_smiles"
        )

    metrics = {
        "target_chembl_id": query.target_chembl_id,
        "endpoint": query.standard_type,
        "unit": query.standard_units,
        "total_count_reported": total_count_reported,
        "raw_records": raw_records,
        "normalized_records": normalized_records,
        "exact_records": exact_records,
        "censored_records": censored_records,
        "unique_activities": unique_activities,
        "unique_molecules": len(molecule_ids),
        "records_with_structure": records_with_structure,
    }
    if errors:
        gate = GateEnvelope(
            "DATA.CHEMBL.ACTIVITY_QC",
            "M2",
            GateStatus.FAILED,
            "As páginas ChEMBL não satisfazem o contrato do piloto M2.",
            run_id=run_id or "chembl-audit",
            metrics=metrics,
            errors=tuple(errors),
        )
    else:
        warnings = (
            f"{censored_records} registros censurados foram preservados e não podem entrar em OLS comum.",
        ) if censored_records else ()
        gate = GateEnvelope.passed(
            "DATA.CHEMBL.ACTIVITY_QC",
            "M2",
            "Aquisição ChEMBL completa, tipada e sem duplicatas de activity_id.",
            run_id=run_id,
            metrics=metrics,
            warnings=warnings,
        )
    return ActivityPageAudit(
        gate,
        total_count_reported,
        raw_records,
        normalized_records,
        exact_records,
        censored_records,
        unique_activities,
        len(molecule_ids),
        records_with_structure,
    )


def fetch_activity_pages(
    query: ChemblActivityQuery,
    output_dir: Path,
    *,
    max_records: int,
    timeout_seconds: float = 30.0,
    opener: Callable[..., Any] = urlopen,
) -> tuple[Path, ...]:
    """Baixa páginas brutas; normalização e snapshot são etapas posteriores separadas."""
    if max_records <= 0:
        raise ValueError("max_records deve ser positivo")
    output_dir.mkdir(parents=True, exist_ok=True)
    next_url: str | None = query.url()
    paths: list[Path] = []
    received = 0
    page_number = 1
    while next_url is not None and received < max_records:
        _validate_api_url(next_url)
        request = Request(next_url, headers={"Accept": "application/json", "User-Agent": "APEX-R/0.1 research"})
        with opener(request, timeout=timeout_seconds) as response:
            raw_payload = response.read()
        data = parse_activity_page(raw_payload)
        path = output_dir / f"activity-page-{page_number:05d}.json"
        if path.exists():
            raise FileExistsError(f"Página bruta já existe e não será sobrescrita: {path}")
        path.write_bytes(raw_payload)
        paths.append(path)
        received += len(data["activities"])
        candidate = data["page_meta"].get("next")
        next_url = urljoin(f"{CHEMBL_API_BASE}/", str(candidate)) if candidate else None
        page_number += 1
    return tuple(paths)
