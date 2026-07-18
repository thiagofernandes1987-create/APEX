"""Contratos públicos que impedem resultados silenciosos ou ambíguos."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4


class GateStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"


class ModuleReadiness(str, Enum):
    ACTIVE = "ACTIVE"
    SCAFFOLDED = "SCAFFOLDED"
    PLANNED = "PLANNED"


@dataclass(frozen=True)
class EvidenceReference:
    source_id: str
    locator: str
    sha256: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class GateEnvelope:
    gate_id: str
    module_id: str
    status: GateStatus
    summary: str
    run_id: str = field(default_factory=lambda: str(uuid4()))
    metrics: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def __post_init__(self) -> None:
        if not self.gate_id.strip() or not self.module_id.strip() or not self.summary.strip():
            raise ValueError("gate_id, module_id e summary são obrigatórios")
        if self.status in {GateStatus.FAILED, GateStatus.BLOCKED, GateStatus.INVALIDATED}:
            if not self.errors:
                raise ValueError(f"O estado {self.status.value} exige ao menos um erro explícito")
        if self.status is GateStatus.PASSED and self.errors:
            raise ValueError("Um gate PASSED não pode conter erros")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def passed(
        cls,
        gate_id: str,
        module_id: str,
        summary: str,
        *,
        metrics: Mapping[str, Any] | None = None,
        warnings: tuple[str, ...] = (),
        run_id: str | None = None,
    ) -> "GateEnvelope":
        kwargs: dict[str, Any] = {}
        if run_id is not None:
            kwargs["run_id"] = run_id
        return cls(
            gate_id=gate_id,
            module_id=module_id,
            status=GateStatus.PASSED,
            summary=summary,
            metrics=metrics or {},
            warnings=warnings,
            **kwargs,
        )

    @classmethod
    def blocked(
        cls,
        gate_id: str,
        module_id: str,
        summary: str,
        error: str,
        *,
        run_id: str | None = None,
    ) -> "GateEnvelope":
        kwargs: dict[str, Any] = {}
        if run_id is not None:
            kwargs["run_id"] = run_id
        return cls(
            gate_id=gate_id,
            module_id=module_id,
            status=GateStatus.BLOCKED,
            summary=summary,
            errors=(error,),
            **kwargs,
        )


@dataclass(frozen=True)
class ModuleContext:
    workspace: Path
    run_id: str = field(default_factory=lambda: str(uuid4()))
    database_path: Path | None = None
    config: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModuleDescriptor:
    module_id: str
    name: str
    purpose: str
    readiness: ModuleReadiness
    dependencies: tuple[str, ...] = ()
    cross_cutting: bool = False

