"""M2 — relações termodinâmicas e calibração mínima auditável."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from ..contracts import GateEnvelope

GAS_CONSTANT_J_MOL_K = 8.31446261815324
STANDARD_CONCENTRATION_MOLAR = 1.0


def _positive_finite(value: float, name: str) -> None:
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{name} deve ser finito e maior que zero")


def pkd_from_kd(kd_molar: float) -> float:
    _positive_finite(kd_molar, "Kd")
    return -math.log10(kd_molar)


def kd_from_pkd(pkd: float) -> float:
    if not math.isfinite(pkd):
        raise ValueError("pKd deve ser finito")
    return 10.0 ** (-pkd)


def delta_g_from_kd(kd_molar: float, temperature_k: float = 298.15) -> float:
    """Retorna ΔG° em J/mol para Kd expresso em mol/L e C° = 1 mol/L."""
    _positive_finite(kd_molar, "Kd")
    _positive_finite(temperature_k, "temperatura")
    return GAS_CONSTANT_J_MOL_K * temperature_k * math.log(
        kd_molar / STANDARD_CONCENTRATION_MOLAR
    )


def kd_from_delta_g(delta_g_j_mol: float, temperature_k: float = 298.15) -> float:
    if not math.isfinite(delta_g_j_mol):
        raise ValueError("ΔG° deve ser finito")
    _positive_finite(temperature_k, "temperatura")
    return STANDARD_CONCENTRATION_MOLAR * math.exp(
        delta_g_j_mol / (GAS_CONSTANT_J_MOL_K * temperature_k)
    )


@dataclass(frozen=True)
class LinearCalibration:
    intercept: float
    slope: float
    r_squared: float
    residual_standard_error: float
    n: int

    def predict(self, x: float) -> float:
        return self.intercept + self.slope * x


def calibrate_linear(x: Sequence[float], y: Sequence[float]) -> LinearCalibration:
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("x e y devem ter o mesmo tamanho e ao menos três pares")
    if not all(math.isfinite(value) for value in (*x, *y)):
        raise ValueError("A calibração não aceita valores não finitos")
    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    sxx = sum((value - mean_x) ** 2 for value in x)
    if sxx == 0:
        raise ValueError("x não possui variação; o coeficiente não é identificável")
    slope = sum((a - mean_x) * (b - mean_y) for a, b in zip(x, y)) / sxx
    intercept = mean_y - slope * mean_x
    residuals = [b - (intercept + slope * a) for a, b in zip(x, y)]
    ss_res = sum(value**2 for value in residuals)
    ss_tot = sum((value - mean_y) ** 2 for value in y)
    r_squared = 1.0 if ss_tot == 0 and ss_res == 0 else 1.0 - ss_res / ss_tot
    residual_standard_error = math.sqrt(ss_res / (n - 2))
    return LinearCalibration(intercept, slope, r_squared, residual_standard_error, n)


def validate_affinity(kd_molar: float, temperature_k: float = 298.15) -> GateEnvelope:
    try:
        pkd = pkd_from_kd(kd_molar)
        delta_g = delta_g_from_kd(kd_molar, temperature_k)
        round_trip = kd_from_delta_g(delta_g, temperature_k)
    except ValueError as exc:
        return GateEnvelope.blocked(
            "M2.AFFINITY", "M2", "Entrada molecular inválida.", str(exc)
        )
    relative_error = abs(round_trip - kd_molar) / kd_molar
    return GateEnvelope.passed(
        "M2.AFFINITY",
        "M2",
        "Conversões de afinidade e energia livre são internamente consistentes.",
        metrics={
            "kd_molar": kd_molar,
            "pkd": pkd,
            "temperature_k": temperature_k,
            "delta_g_j_mol": delta_g,
            "round_trip_relative_error": relative_error,
        },
    )

