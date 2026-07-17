"""Snapshots locais imutáveis, registros normalizados e splits sem vazamento."""

from __future__ import annotations

import json
import math
import os
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import GateEnvelope, GateStatus
from .hashing import canonical_json_hash, sha256_file


class LicenseClass(str, Enum):
    OPEN = "OPEN"
    ATTRIBUTION = "ATTRIBUTION"
    CONDITIONAL = "CONDITIONAL"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    name: str
    version: str
    license_name: str
    license_class: LicenseClass
    uri: str | None = None
    redistribution_allowed: bool = False

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.source_id, self.name, self.version, self.license_name)):
            raise ValueError("Fonte exige ID, nome, versão e licença")
        if self.license_class in {LicenseClass.RESTRICTED, LicenseClass.UNKNOWN}:
            if self.redistribution_allowed:
                raise ValueError("Fonte restrita/desconhecida não pode habilitar redistribuição por padrão")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceDefinition":
        return cls(
            source_id=str(data["source_id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            license_name=str(data["license_name"]),
            license_class=LicenseClass(str(data["license_class"])),
            uri=data.get("uri"),
            redistribution_allowed=bool(data.get("redistribution_allowed", False)),
        )


@dataclass(frozen=True)
class SnapshotFile:
    original_path: str
    original_name: str
    size_bytes: int
    sha256: str
    stored_locator: str | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    snapshot_id: str
    source: SourceDefinition
    retrieved_at: str
    files: tuple[SnapshotFile, ...]
    query: Mapping[str, Any] = field(default_factory=dict)
    status: str = "FROZEN"

    def __post_init__(self) -> None:
        if not self.files:
            raise ValueError("Snapshot exige ao menos um arquivo")
        if self.status not in {"STAGED", "FROZEN", "REJECTED"}:
            raise ValueError("Status de snapshot inválido")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["source"]["license_class"] = self.source.license_class.value
        return data


class ContentAddressedStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def put(self, source_path: Path) -> tuple[str, Path]:
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        digest = sha256_file(source_path)
        destination = self.root / digest[:2] / digest
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(destination) != digest:
                raise RuntimeError(f"Colisão ou corrupção no content store: {destination}")
            return digest, destination
        temporary = destination.with_suffix(f".partial-{os.getpid()}")
        shutil.copyfile(source_path, temporary)
        if sha256_file(temporary) != digest:
            temporary.unlink(missing_ok=True)
            raise RuntimeError("O hash mudou durante a cópia do artefato")
        try:
            temporary.replace(destination)
        except FileExistsError:
            temporary.unlink(missing_ok=True)
        return digest, destination


def build_local_snapshot(
    source: SourceDefinition,
    paths: Sequence[Path],
    *,
    store: ContentAddressedStore | None = None,
    query: Mapping[str, Any] | None = None,
    retrieved_at: str | None = None,
) -> SourceSnapshot:
    if not paths:
        raise ValueError("Informe ao menos um arquivo para o snapshot")
    files: list[SnapshotFile] = []
    for raw_path in paths:
        path = raw_path.resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if store is None:
            digest = sha256_file(path)
            locator = None
        else:
            digest, stored_path = store.put(path)
            locator = str(stored_path.resolve())
        files.append(
            SnapshotFile(
                original_path=str(path),
                original_name=path.name,
                size_bytes=path.stat().st_size,
                sha256=digest,
                stored_locator=locator,
            )
        )
    canonical = {
        "source_id": source.source_id,
        "source_version": source.version,
        "license_name": source.license_name,
        "files": [
            {"name": item.original_name, "size_bytes": item.size_bytes, "sha256": item.sha256}
            for item in sorted(files, key=lambda value: (value.original_name, value.sha256))
        ],
        "query": dict(query or {}),
    }
    return SourceSnapshot(
        snapshot_id=canonical_json_hash(canonical),
        source=source,
        retrieved_at=retrieved_at
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        files=tuple(files),
        query=dict(query or {}),
    )


_CONCENTRATION_FACTORS = {
    "M": 1.0,
    "mM": 1e-3,
    "uM": 1e-6,
    "nM": 1e-9,
    "pM": 1e-12,
}


@dataclass(frozen=True)
class AffinityMeasurement:
    record_id: str
    snapshot_id: str
    source_record_id: str
    compound_id: str
    target_id: str
    endpoint: str
    relation: str
    value: float
    unit: str
    conditions: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        required = (
            self.record_id,
            self.snapshot_id,
            self.source_record_id,
            self.compound_id,
            self.target_id,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Medição de afinidade possui identificador vazio")
        if self.endpoint not in {"Kd", "Ki", "IC50"}:
            raise ValueError("endpoint deve permanecer tipado como Kd, Ki ou IC50")
        if self.relation not in {"=", "<", "<=", ">", ">="}:
            raise ValueError("Relação de medição inválida")
        if self.unit not in _CONCENTRATION_FACTORS:
            raise ValueError("Unidade de concentração não suportada")
        if not math.isfinite(self.value) or self.value <= 0:
            raise ValueError("Afinidade deve ser finita e positiva")

    @property
    def value_molar(self) -> float:
        return self.value * _CONCENTRATION_FACTORS[self.unit]


class SplitPartition(str, Enum):
    TRAIN = "TRAIN"
    CALIBRATION = "CALIBRATION"
    INTERNAL_TEST = "INTERNAL_TEST"
    EXTERNAL_TEST = "EXTERNAL_TEST"


@dataclass(frozen=True)
class FrozenSplit:
    split_id: str
    dataset_snapshot_id: str
    partitions: Mapping[SplitPartition, tuple[str, ...]]
    groups: Mapping[str, str]
    external_set_locked: bool
    strategy: str

    def __post_init__(self) -> None:
        if not self.split_id.strip() or not self.dataset_snapshot_id.strip() or not self.strategy.strip():
            raise ValueError("Split exige IDs e estratégia")
        if not self.partitions:
            raise ValueError("Split exige partições")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FrozenSplit":
        return cls(
            split_id=str(data["split_id"]),
            dataset_snapshot_id=str(data["dataset_snapshot_id"]),
            partitions={
                SplitPartition(str(name)): tuple(str(item) for item in members)
                for name, members in data["partitions"].items()
            },
            groups={str(key): str(value) for key, value in data.get("groups", {}).items()},
            external_set_locked=bool(data.get("external_set_locked", False)),
            strategy=str(data["strategy"]),
        )

    def definition_sha256(self) -> str:
        return canonical_json_hash(
            {
                "split_id": self.split_id,
                "dataset_snapshot_id": self.dataset_snapshot_id,
                "partitions": {
                    partition.value: sorted(members)
                    for partition, members in self.partitions.items()
                },
                "groups": dict(sorted(self.groups.items())),
                "external_set_locked": self.external_set_locked,
                "strategy": self.strategy,
            }
        )

    def validation_gate(self) -> GateEnvelope:
        owner: dict[str, str] = {}
        duplicates: list[str] = []
        group_owners: dict[str, set[str]] = {}
        for partition, members in self.partitions.items():
            for record_id in members:
                if record_id in owner:
                    duplicates.append(record_id)
                owner[record_id] = partition.value
                group = self.groups.get(record_id)
                if group is not None:
                    group_owners.setdefault(group, set()).add(partition.value)
        leaking_groups = sorted(group for group, partitions in group_owners.items() if len(partitions) > 1)
        errors: list[str] = []
        if duplicates:
            errors.append("Registros em múltiplas partições: " + ", ".join(sorted(set(duplicates))))
        if leaking_groups:
            errors.append("Grupos atravessam partições: " + ", ".join(leaking_groups))
        if SplitPartition.EXTERNAL_TEST in self.partitions and not self.external_set_locked:
            errors.append("EXTERNAL_TEST deve permanecer bloqueado")
        metrics = {
            "split_id": self.split_id,
            "definition_sha256": self.definition_sha256(),
            "partition_sizes": {
                partition.value: len(members) for partition, members in self.partitions.items()
            },
            "duplicate_records": sorted(set(duplicates)),
            "leaking_groups": leaking_groups,
        }
        if errors:
            return GateEnvelope(
                gate_id="DATA.SPLIT.LEAKAGE",
                module_id="M11",
                status=GateStatus.FAILED,
                summary="O split apresenta risco de vazamento ou conjunto externo desbloqueado.",
                metrics=metrics,
                errors=tuple(errors),
            )
        return GateEnvelope.passed(
            "DATA.SPLIT.LEAKAGE",
            "M11",
            "As partições são disjuntas por registro e grupo protegido.",
            metrics=metrics,
        )


def write_snapshot_manifest(snapshot: SourceSnapshot, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(snapshot.to_dict(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if destination.exists() and destination.read_text(encoding="utf-8") != encoded:
        raise FileExistsError("Manifesto existente é imutável e possui conteúdo diferente")
    destination.write_text(encoded, encoding="utf-8")
