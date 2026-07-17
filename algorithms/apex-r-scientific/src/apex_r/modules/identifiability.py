"""M0 — verificações iniciais de identificabilidade para modelos lineares locais."""

from __future__ import annotations

import math
from typing import Sequence

from ..contracts import GateEnvelope, GateStatus


def matrix_rank(matrix: Sequence[Sequence[float]], tolerance: float = 1e-12) -> int:
    if not matrix or not matrix[0]:
        raise ValueError("A matriz de desenho não pode ser vazia")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("A matriz de desenho deve ser retangular")
    if tolerance <= 0 or not math.isfinite(tolerance):
        raise ValueError("tolerance deve ser finita e positiva")
    values = [[float(value) for value in row] for row in matrix]
    if not all(math.isfinite(value) for row in values for value in row):
        raise ValueError("A matriz de desenho não aceita valores não finitos")

    rank = 0
    rows = len(values)
    for column in range(width):
        pivot = max(range(rank, rows), key=lambda row: abs(values[row][column]), default=None)
        if pivot is None or abs(values[pivot][column]) <= tolerance:
            continue
        values[rank], values[pivot] = values[pivot], values[rank]
        pivot_value = values[rank][column]
        for j in range(column, width):
            values[rank][j] /= pivot_value
        for row in range(rows):
            if row == rank:
                continue
            factor = values[row][column]
            if abs(factor) <= tolerance:
                continue
            for j in range(column, width):
                values[row][j] -= factor * values[rank][j]
        rank += 1
        if rank == rows:
            break
    return rank


def validate_linear_design(
    design_matrix: Sequence[Sequence[float]], tolerance: float = 1e-12
) -> GateEnvelope:
    try:
        observations = len(design_matrix)
        parameters = len(design_matrix[0]) if observations else 0
        rank = matrix_rank(design_matrix, tolerance)
    except ValueError as exc:
        return GateEnvelope.blocked(
            "M0.LINEAR_RANK", "M0", "Desenho experimental inválido.", str(exc)
        )
    metrics = {
        "observations": observations,
        "parameters": parameters,
        "rank": rank,
        "degrees_of_freedom": observations - parameters,
        "tolerance": tolerance,
    }
    if rank < parameters:
        return GateEnvelope(
            gate_id="M0.LINEAR_RANK",
            module_id="M0",
            status=GateStatus.FAILED,
            summary="O desenho não identifica todos os coeficientes lineares.",
            metrics=metrics,
            errors=(f"Posto {rank} menor que {parameters} parâmetros.",),
        )
    if observations == parameters:
        return GateEnvelope(
            gate_id="M0.LINEAR_RANK",
            module_id="M0",
            status=GateStatus.NEEDS_REVIEW,
            summary="O desenho tem posto completo, mas não possui graus de liberdade residuais.",
            metrics=metrics,
            warnings=("Adicione observações independentes para estimar erro e incerteza.",),
        )
    return GateEnvelope.passed(
        "M0.LINEAR_RANK",
        "M0",
        "A matriz possui posto de coluna completo e graus de liberdade residuais.",
        metrics=metrics,
        warnings=(
            "Este gate avalia identificabilidade linear local; não comprova identificabilidade global.",
        ),
    )

