"""M11 — protocolos pré-especificados e validação em camadas."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from ..contracts import GateEnvelope, GateStatus


class EvidenceLayer(str, Enum):
    FORMAL = "FORMAL"
    NUMERICAL = "NUMERICAL"
    SYNTHETIC = "SYNTHETIC"
    INTERNAL = "INTERNAL"
    PRECLINICAL = "PRECLINICAL"
    EXTERNAL = "EXTERNAL"
    CLINICAL = "CLINICAL"


class CriterionOperator(str, Enum):
    LTE = "LTE"
    GTE = "GTE"
    BETWEEN = "BETWEEN"
    ABS_LTE = "ABS_LTE"


@dataclass(frozen=True)
class MetricCriterion:
    metric_id: str
    operator: CriterionOperator
    threshold: float
    upper_threshold: float | None = None

    def __post_init__(self) -> None:
        if not self.metric_id.strip() or not math.isfinite(self.threshold):
            raise ValueError("metric_id e threshold finito são obrigatórios")
        if self.operator is CriterionOperator.BETWEEN:
            if self.upper_threshold is None or not math.isfinite(self.upper_threshold):
                raise ValueError("BETWEEN exige upper_threshold finito")
            if self.threshold > self.upper_threshold:
                raise ValueError("O limite inferior não pode exceder o superior")
        elif self.upper_threshold is not None:
            raise ValueError("upper_threshold é permitido somente para BETWEEN")
        if self.operator is CriterionOperator.ABS_LTE and self.threshold < 0:
            raise ValueError("ABS_LTE exige threshold não negativo")

    def evaluate(self, value: float) -> bool:
        if not math.isfinite(value):
            return False
        if self.operator is CriterionOperator.LTE:
            return value <= self.threshold
        if self.operator is CriterionOperator.GTE:
            return value >= self.threshold
        if self.operator is CriterionOperator.ABS_LTE:
            return abs(value) <= self.threshold
        assert self.upper_threshold is not None
        return self.threshold <= value <= self.upper_threshold

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MetricCriterion":
        return cls(
            metric_id=str(data["metric_id"]),
            operator=CriterionOperator(str(data["operator"])),
            threshold=float(data["threshold"]),
            upper_threshold=(
                float(data["upper_threshold"])
                if data.get("upper_threshold") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class MetricObservation:
    value: float
    sample_size: int
    lower_interval: float | None = None
    upper_interval: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.value) or self.sample_size <= 0:
            raise ValueError("Observação exige valor finito e sample_size positivo")
        if (self.lower_interval is None) != (self.upper_interval is None):
            raise ValueError("Intervalo deve declarar os dois limites")
        if self.lower_interval is not None:
            assert self.upper_interval is not None
            if not all(math.isfinite(v) for v in (self.lower_interval, self.upper_interval)):
                raise ValueError("Limites do intervalo devem ser finitos")
            if self.lower_interval > self.upper_interval:
                raise ValueError("Intervalo inválido")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "MetricObservation":
        return cls(
            value=float(data["value"]),
            sample_size=int(data["sample_size"]),
            lower_interval=data.get("lower_interval"),
            upper_interval=data.get("upper_interval"),
        )


@dataclass(frozen=True)
class ValidationProtocol:
    protocol_id: str
    version: str
    module_id: str
    layer: EvidenceLayer
    dataset_snapshot_id: str
    split_id: str
    criteria: tuple[MetricCriterion, ...]
    minimum_sample_size: int
    preregistered: bool
    external_set_locked: bool = False
    synthetic_data: bool = False
    pcl_level: int | None = None
    species: str | None = None
    biological_model: str | None = None

    def __post_init__(self) -> None:
        text_fields = (
            self.protocol_id,
            self.version,
            self.module_id,
            self.dataset_snapshot_id,
            self.split_id,
        )
        if not all(value.strip() for value in text_fields):
            raise ValueError("Identificadores do protocolo não podem ser vazios")
        if not self.criteria or self.minimum_sample_size <= 0:
            raise ValueError("Protocolo exige critérios e amostra mínima positiva")
        if self.synthetic_data and self.layer is not EvidenceLayer.SYNTHETIC:
            raise ValueError("Dados sintéticos devem permanecer na camada SYNTHETIC")
        if self.layer is EvidenceLayer.SYNTHETIC and not self.synthetic_data:
            raise ValueError("A camada SYNTHETIC exige synthetic_data=true")
        if self.layer is EvidenceLayer.EXTERNAL and not self.external_set_locked:
            raise ValueError("Validação externa exige conjunto externo bloqueado")
        if self.layer is EvidenceLayer.PRECLINICAL:
            if self.pcl_level is None or not 1 <= self.pcl_level <= 5:
                raise ValueError("Validação pré-clínica exige PCL-1 a PCL-5")
            if not self.species or not self.biological_model:
                raise ValueError("Validação pré-clínica exige espécie e modelo biológico")
        elif self.pcl_level is not None:
            raise ValueError("pcl_level pertence somente à camada PRECLINICAL")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ValidationProtocol":
        return cls(
            protocol_id=str(data["protocol_id"]),
            version=str(data["version"]),
            module_id=str(data["module_id"]),
            layer=EvidenceLayer(str(data["layer"])),
            dataset_snapshot_id=str(data["dataset_snapshot_id"]),
            split_id=str(data["split_id"]),
            criteria=tuple(MetricCriterion.from_dict(item) for item in data["criteria"]),
            minimum_sample_size=int(data["minimum_sample_size"]),
            preregistered=bool(data["preregistered"]),
            external_set_locked=bool(data.get("external_set_locked", False)),
            synthetic_data=bool(data.get("synthetic_data", False)),
            pcl_level=data.get("pcl_level"),
            species=data.get("species"),
            biological_model=data.get("biological_model"),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["layer"] = self.layer.value
        for criterion, raw in zip(self.criteria, data["criteria"]):
            raw["operator"] = criterion.operator.value
        return data


@dataclass(frozen=True)
class ValidationOutcome:
    protocol: ValidationProtocol
    gate: GateEnvelope
    criterion_results: Mapping[str, bool]

    @property
    def candidate_evidence_label(self) -> str | None:
        if self.gate.status is not GateStatus.PASSED:
            return None
        labels = {
            EvidenceLayer.FORMAL: "TESTED",
            EvidenceLayer.NUMERICAL: "REPRODUCED",
            EvidenceLayer.SYNTHETIC: "TESTED",
            EvidenceLayer.INTERNAL: "INTERNALLY_VALIDATED",
            EvidenceLayer.PRECLINICAL: "PRECLINICALLY_VALIDATED",
            EvidenceLayer.EXTERNAL: "EXTERNALLY_VALIDATED",
            EvidenceLayer.CLINICAL: "CLINICALLY_EVALUATED",
        }
        return labels[self.protocol.layer]


def evaluate_protocol(
    protocol: ValidationProtocol,
    observations: Mapping[str, MetricObservation | Mapping[str, Any]],
    *,
    run_id: str | None = None,
) -> ValidationOutcome:
    if not protocol.preregistered:
        gate = GateEnvelope.blocked(
            f"M11.{protocol.protocol_id}",
            "M11",
            "O protocolo não pode ser executado como validação confirmatória.",
            "Critérios e thresholds devem ser pré-registrados antes do acesso ao conjunto avaliado.",
            run_id=run_id,
        )
        return ValidationOutcome(protocol, gate, {})

    parsed: dict[str, MetricObservation] = {}
    for metric_id, value in observations.items():
        parsed[metric_id] = (
            value if isinstance(value, MetricObservation) else MetricObservation.from_dict(value)
        )
    missing = [criterion.metric_id for criterion in protocol.criteria if criterion.metric_id not in parsed]
    if missing:
        gate = GateEnvelope.blocked(
            f"M11.{protocol.protocol_id}",
            "M11",
            "Métricas obrigatórias não foram fornecidas.",
            "Métricas ausentes: " + ", ".join(missing),
            run_id=run_id,
        )
        return ValidationOutcome(protocol, gate, {})

    results: dict[str, bool] = {}
    details: dict[str, Any] = {}
    for criterion in protocol.criteria:
        observation = parsed[criterion.metric_id]
        enough_samples = observation.sample_size >= protocol.minimum_sample_size
        criterion_passed = enough_samples and criterion.evaluate(observation.value)
        results[criterion.metric_id] = criterion_passed
        details[criterion.metric_id] = {
            "value": observation.value,
            "sample_size": observation.sample_size,
            "minimum_sample_size": protocol.minimum_sample_size,
            "operator": criterion.operator.value,
            "threshold": criterion.threshold,
            "upper_threshold": criterion.upper_threshold,
            "passed": criterion_passed,
        }
    metrics = {
        "protocol_id": protocol.protocol_id,
        "protocol_version": protocol.version,
        "layer": protocol.layer.value,
        "dataset_snapshot_id": protocol.dataset_snapshot_id,
        "split_id": protocol.split_id,
        "criteria": details,
    }
    failed = [metric_id for metric_id, passed in results.items() if not passed]
    if failed:
        gate = GateEnvelope(
            gate_id=f"M11.{protocol.protocol_id}",
            module_id="M11",
            status=GateStatus.FAILED,
            summary="O protocolo foi executado, mas não atingiu todos os critérios.",
            metrics=metrics,
            errors=("Critérios reprovados: " + ", ".join(failed),),
            **({"run_id": run_id} if run_id is not None else {}),
        )
    else:
        warnings = ()
        if protocol.layer in {
            EvidenceLayer.PRECLINICAL,
            EvidenceLayer.EXTERNAL,
            EvidenceLayer.CLINICAL,
        }:
            warnings = ("A aprovação do protocolo gera evidência candidata; promoção exige revisão humana.",)
        gate = GateEnvelope.passed(
            f"M11.{protocol.protocol_id}",
            "M11",
            "Todos os critérios pré-especificados foram atingidos.",
            metrics=metrics,
            warnings=warnings,
            run_id=run_id,
        )
    return ValidationOutcome(protocol, gate, results)


def promotion_readiness(
    outcomes: Sequence[ValidationOutcome],
    required_layers: Sequence[EvidenceLayer],
    *,
    run_id: str | None = None,
) -> GateEnvelope:
    approved_layers = {
        outcome.protocol.layer
        for outcome in outcomes
        if outcome.gate.status is GateStatus.PASSED
    }
    missing = [layer.value for layer in required_layers if layer not in approved_layers]
    if missing:
        return GateEnvelope.blocked(
            "M11.PROMOTION_READINESS",
            "M11",
            "A evidência ainda não cobre todas as camadas exigidas.",
            "Camadas pendentes: " + ", ".join(missing),
            run_id=run_id,
        )
    return GateEnvelope(
        gate_id="M11.PROMOTION_READINESS",
        module_id="M11",
        status=GateStatus.NEEDS_REVIEW,
        summary="As camadas exigidas foram aprovadas; decisão humana é obrigatória.",
        metrics={
            "approved_layers": sorted(layer.value for layer in approved_layers),
            "candidate_labels": sorted(
                label
                for outcome in outcomes
                if (label := outcome.candidate_evidence_label) is not None
            ),
        },
        warnings=("Este gate nunca promove automaticamente coeficientes ou claims.",),
        **({"run_id": run_id} if run_id is not None else {}),
    )
