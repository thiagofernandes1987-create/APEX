"""M2 — calibração molecular supervisionada ligada a split congelado."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..contracts import GateEnvelope, GateStatus
from ..data import AffinityMeasurement, FrozenSplit, SplitPartition
from .molecular import LinearCalibration, calibrate_linear, pkd_from_kd
from .validation import EvidenceLayer, ValidationProtocol


@dataclass(frozen=True)
class CalibrationPoint:
    record_id: str
    group_id: str
    endpoint: str
    score: float
    observed_pk: float

    def __post_init__(self) -> None:
        if not self.record_id.strip() or not self.group_id.strip():
            raise ValueError("CalibrationPoint exige record_id e group_id")
        if self.endpoint not in {"Kd", "Ki", "IC50"}:
            raise ValueError("Endpoint de calibração inválido")
        if not math.isfinite(self.score) or not math.isfinite(self.observed_pk):
            raise ValueError("Score e pK observado devem ser finitos")


def point_from_affinity(
    measurement: AffinityMeasurement, *, score: float, group_id: str
) -> CalibrationPoint:
    if measurement.relation != "=":
        raise ValueError("Medições censuradas exigem modelo próprio e não entram no OLS")
    return CalibrationPoint(
        record_id=measurement.record_id,
        group_id=group_id,
        endpoint=measurement.endpoint,
        score=score,
        observed_pk=pkd_from_kd(measurement.value_molar),
    )


@dataclass(frozen=True)
class MolecularCalibrationModel:
    model_id: str
    endpoint: str
    dataset_snapshot_id: str
    split_id: str
    split_sha256: str
    fit: LinearCalibration
    training_record_ids: tuple[str, ...]

    def predict_pk(self, score: float) -> float:
        if not math.isfinite(score):
            raise ValueError("score deve ser finito")
        return self.fit.predict(score)


@dataclass(frozen=True)
class CalibrationFitResult:
    gate: GateEnvelope
    model: MolecularCalibrationModel | None


@dataclass(frozen=True)
class CalibrationEvaluation:
    gate: GateEnvelope
    metrics: dict[str, float | int | str]


def _points_by_id(points: Sequence[CalibrationPoint]) -> dict[str, CalibrationPoint]:
    indexed: dict[str, CalibrationPoint] = {}
    for point in points:
        if point.record_id in indexed:
            raise ValueError(f"CalibrationPoint duplicado: {point.record_id}")
        indexed[point.record_id] = point
    return indexed


def fit_molecular_calibration(
    points: Sequence[CalibrationPoint],
    split: FrozenSplit,
    *,
    model_id: str,
    run_id: str | None = None,
) -> CalibrationFitResult:
    split_gate = split.validation_gate()
    if split_gate.status is not GateStatus.PASSED:
        return CalibrationFitResult(
            GateEnvelope.blocked(
                "M2.CALIBRATION.FIT",
                "M2",
                "A calibração foi bloqueada por um split inválido.",
                "; ".join(split_gate.errors),
                run_id=run_id,
            ),
            None,
        )
    try:
        indexed = _points_by_id(points)
        train_ids = split.partitions.get(SplitPartition.TRAIN, ())
        if len(train_ids) < 3:
            raise ValueError("TRAIN exige ao menos três registros para o modelo linear")
        missing = [record_id for record_id in train_ids if record_id not in indexed]
        if missing:
            raise ValueError("Registros TRAIN ausentes: " + ", ".join(missing))
        train = [indexed[record_id] for record_id in train_ids]
        endpoints = {point.endpoint for point in train}
        if len(endpoints) != 1:
            raise ValueError("Kd, Ki e IC50 não podem ser misturados na mesma calibração")
        fit = calibrate_linear(
            [point.score for point in train],
            [point.observed_pk for point in train],
        )
    except ValueError as exc:
        return CalibrationFitResult(
            GateEnvelope.blocked(
                "M2.CALIBRATION.FIT",
                "M2",
                "Entradas de calibração inválidas.",
                str(exc),
                run_id=run_id,
            ),
            None,
        )
    model = MolecularCalibrationModel(
        model_id=model_id,
        endpoint=endpoints.pop(),
        dataset_snapshot_id=split.dataset_snapshot_id,
        split_id=split.split_id,
        split_sha256=split.definition_sha256(),
        fit=fit,
        training_record_ids=tuple(train_ids),
    )
    gate = GateEnvelope.passed(
        "M2.CALIBRATION.FIT",
        "M2",
        "Modelo candidato ajustado somente na partição TRAIN.",
        metrics={
            "model_id": model_id,
            "endpoint": model.endpoint,
            "n_train": fit.n,
            "intercept": fit.intercept,
            "slope": fit.slope,
            "r_squared_train": fit.r_squared,
            "residual_standard_error_train": fit.residual_standard_error,
            "split_sha256": model.split_sha256,
        },
        warnings=("Métrica de treino não constitui validação interna ou externa.",),
        run_id=run_id,
    )
    return CalibrationFitResult(gate, model)


def _average_ranks(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        average = (start + 1 + end) / 2
        for position in range(start, end):
            ranks[order[position]] = average
        start = end
    return ranks


def _pearson(x: Sequence[float], y: Sequence[float]) -> float:
    mean_x = sum(x) / len(x)
    mean_y = sum(y) / len(y)
    numerator = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y))
    denominator = math.sqrt(
        sum((a - mean_x) ** 2 for a in x) * sum((b - mean_y) ** 2 for b in y)
    )
    return numerator / denominator if denominator else 0.0


def evaluate_molecular_calibration(
    model: MolecularCalibrationModel,
    points: Sequence[CalibrationPoint],
    split: FrozenSplit,
    partition: SplitPartition,
    *,
    protocol: ValidationProtocol | None = None,
    run_id: str | None = None,
) -> CalibrationEvaluation:
    if model.split_sha256 != split.definition_sha256():
        gate = GateEnvelope.blocked(
            "M2.CALIBRATION.EVALUATE",
            "M2",
            "O split mudou depois do ajuste.",
            "Hash do split não corresponde ao modelo candidato.",
            run_id=run_id,
        )
        return CalibrationEvaluation(gate, {})
    if partition is SplitPartition.TRAIN:
        gate = GateEnvelope.blocked(
            "M2.CALIBRATION.EVALUATE",
            "M2",
            "TRAIN não pode ser apresentado como validação.",
            "Use INTERNAL_TEST ou EXTERNAL_TEST.",
            run_id=run_id,
        )
        return CalibrationEvaluation(gate, {})
    if partition is SplitPartition.EXTERNAL_TEST:
        if protocol is None or protocol.layer is not EvidenceLayer.EXTERNAL:
            gate = GateEnvelope.blocked(
                "M2.CALIBRATION.EVALUATE",
                "M2",
                "O conjunto externo só pode ser aberto por protocolo M11 externo.",
                "Forneça ValidationProtocol EXTERNAL pré-registrado e bloqueado.",
                run_id=run_id,
            )
            return CalibrationEvaluation(gate, {})
        if (
            protocol.dataset_snapshot_id != split.dataset_snapshot_id
            or protocol.split_id != split.split_id
            or not protocol.external_set_locked
            or not protocol.preregistered
        ):
            gate = GateEnvelope.blocked(
                "M2.CALIBRATION.EVALUATE",
                "M2",
                "O protocolo externo não corresponde ao dataset/split congelado.",
                "Identificadores, lock e pré-registro devem coincidir.",
                run_id=run_id,
            )
            return CalibrationEvaluation(gate, {})
    try:
        indexed = _points_by_id(points)
        ids = split.partitions.get(partition, ())
        if len(ids) < 2:
            raise ValueError(f"{partition.value} exige ao menos dois registros")
        selected = [indexed[record_id] for record_id in ids]
        if any(point.endpoint != model.endpoint for point in selected):
            raise ValueError("Endpoint de avaliação não corresponde ao modelo")
    except (KeyError, ValueError) as exc:
        gate = GateEnvelope.blocked(
            "M2.CALIBRATION.EVALUATE",
            "M2",
            "Avaliação molecular inválida.",
            str(exc),
            run_id=run_id,
        )
        return CalibrationEvaluation(gate, {})
    observed = [point.observed_pk for point in selected]
    predicted = [model.predict_pk(point.score) for point in selected]
    residuals = [prediction - truth for prediction, truth in zip(predicted, observed)]
    metrics: dict[str, float | int | str] = {
        "partition": partition.value,
        "n": len(selected),
        "rmse_pk": math.sqrt(sum(value**2 for value in residuals) / len(residuals)),
        "mae_pk": sum(abs(value) for value in residuals) / len(residuals),
        "spearman": _pearson(_average_ranks(predicted), _average_ranks(observed)),
        "endpoint": model.endpoint,
        "model_id": model.model_id,
    }
    gate = GateEnvelope.passed(
        "M2.CALIBRATION.EVALUATE",
        "M2",
        f"Métricas calculadas na partição {partition.value} sem reajuste do modelo.",
        metrics=metrics,
        warnings=("As métricas devem ser avaliadas por um protocolo M11 pré-especificado.",),
        run_id=run_id,
    )
    return CalibrationEvaluation(gate, metrics)
