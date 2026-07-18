"""M4 — utilitários PBPK com convenção explícita de balanço de massa."""

from __future__ import annotations

import math
from typing import Sequence

from ..contracts import GateEnvelope, GateStatus


def _validate_system(
    amounts: Sequence[float],
    transfer_rates: Sequence[Sequence[float]],
    elimination_rates: Sequence[float],
    input_rates: Sequence[float],
) -> None:
    n = len(amounts)
    if n == 0 or len(transfer_rates) != n or any(len(row) != n for row in transfer_rates):
        raise ValueError("transfer_rates deve ser uma matriz quadrada compatível com amounts")
    if len(elimination_rates) != n or len(input_rates) != n:
        raise ValueError("elimination_rates e input_rates devem ter tamanho compatível")
    values = list(amounts) + list(elimination_rates) + list(input_rates)
    values.extend(value for row in transfer_rates for value in row)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("O sistema PBPK não aceita valores não finitos")
    if any(value < 0 for value in amounts):
        raise ValueError("amounts não pode conter massas negativas")
    if any(value < 0 for value in elimination_rates):
        raise ValueError("elimination_rates não pode conter taxas negativas")
    for i, row in enumerate(transfer_rates):
        if any(value < 0 for j, value in enumerate(row) if i != j):
            raise ValueError("taxas de transferência fora da diagonal devem ser não negativas")


def derivative(
    amounts: Sequence[float],
    transfer_rates: Sequence[Sequence[float]],
    elimination_rates: Sequence[float] | None = None,
    input_rates: Sequence[float] | None = None,
) -> list[float]:
    """Calcula dA/dt; transfer_rates[i][j] é a taxa do compartimento i para j."""
    n = len(amounts)
    elimination = list(elimination_rates or [0.0] * n)
    inputs = list(input_rates or [0.0] * n)
    _validate_system(amounts, transfer_rates, elimination, inputs)
    result = inputs.copy()
    for i in range(n):
        result[i] -= elimination[i] * amounts[i]
        for j in range(n):
            if i == j:
                continue
            result[i] -= transfer_rates[i][j] * amounts[i]
            result[i] += transfer_rates[j][i] * amounts[j]
    return result


def mass_balance_error(
    amounts: Sequence[float],
    transfer_rates: Sequence[Sequence[float]],
    elimination_rates: Sequence[float] | None = None,
    input_rates: Sequence[float] | None = None,
) -> float:
    n = len(amounts)
    elimination = list(elimination_rates or [0.0] * n)
    inputs = list(input_rates or [0.0] * n)
    rates = derivative(amounts, transfer_rates, elimination, inputs)
    expected_total = sum(inputs) - sum(k * amount for k, amount in zip(elimination, amounts))
    return sum(rates) - expected_total


def validate_mass_balance(
    amounts: Sequence[float],
    transfer_rates: Sequence[Sequence[float]],
    elimination_rates: Sequence[float] | None = None,
    input_rates: Sequence[float] | None = None,
    tolerance: float = 1e-12,
) -> GateEnvelope:
    try:
        error = mass_balance_error(amounts, transfer_rates, elimination_rates, input_rates)
    except ValueError as exc:
        return GateEnvelope.blocked(
            "M4.MASS_BALANCE", "M4", "Sistema PBPK inválido.", str(exc)
        )
    if abs(error) > tolerance:
        return GateEnvelope(
            gate_id="M4.MASS_BALANCE",
            module_id="M4",
            status=GateStatus.FAILED,
            summary="O sistema PBPK viola o balanço de massa.",
            metrics={"mass_balance_error": error, "tolerance": tolerance},
            errors=("Erro de conservação acima da tolerância.",),
        )
    return GateEnvelope.passed(
        "M4.MASS_BALANCE",
        "M4",
        "As transferências internas conservam massa dentro da tolerância.",
        metrics={"mass_balance_error": error, "tolerance": tolerance},
    )
