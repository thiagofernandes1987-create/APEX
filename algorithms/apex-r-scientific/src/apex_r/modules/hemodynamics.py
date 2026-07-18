"""M3 — núcleo Windkessel de dois elementos com integração RK4."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass

from ..contracts import GateEnvelope


@dataclass(frozen=True)
class WK2Parameters:
    resistance: float
    compliance: float
    venous_pressure: float = 0.0

    def validate(self) -> None:
        if not math.isfinite(self.resistance) or self.resistance <= 0:
            raise ValueError("resistance deve ser finita e positiva")
        if not math.isfinite(self.compliance) or self.compliance <= 0:
            raise ValueError("compliance deve ser finita e positiva")
        if not math.isfinite(self.venous_pressure):
            raise ValueError("venous_pressure deve ser finita")


def equilibrium_pressure(flow: float, params: WK2Parameters) -> float:
    params.validate()
    if not math.isfinite(flow):
        raise ValueError("flow deve ser finito")
    return params.venous_pressure + flow * params.resistance


def pressure_derivative(pressure: float, flow: float, params: WK2Parameters) -> float:
    params.validate()
    return (flow - (pressure - params.venous_pressure) / params.resistance) / params.compliance


def simulate_wk2(
    initial_pressure: float,
    inflow: float | Callable[[float], float],
    params: WK2Parameters,
    duration: float,
    dt: float,
) -> tuple[list[float], list[float]]:
    params.validate()
    if duration <= 0 or dt <= 0 or dt > duration:
        raise ValueError("duration e dt devem ser positivos, com dt <= duration")
    if not math.isfinite(initial_pressure):
        raise ValueError("initial_pressure deve ser finita")
    flow_at = inflow if callable(inflow) else lambda _time: float(inflow)
    steps = int(math.ceil(duration / dt))
    times = [0.0]
    pressures = [initial_pressure]
    for index in range(steps):
        time = times[-1]
        step = min(dt, duration - time)
        pressure = pressures[-1]
        k1 = pressure_derivative(pressure, flow_at(time), params)
        k2 = pressure_derivative(pressure + step * k1 / 2, flow_at(time + step / 2), params)
        k3 = pressure_derivative(pressure + step * k2 / 2, flow_at(time + step / 2), params)
        k4 = pressure_derivative(pressure + step * k3, flow_at(time + step), params)
        pressures.append(pressure + step * (k1 + 2 * k2 + 2 * k3 + k4) / 6)
        times.append(time + step)
    return times, pressures


def validate_baseline(flow: float, params: WK2Parameters) -> GateEnvelope:
    try:
        pressure = equilibrium_pressure(flow, params)
        derivative = pressure_derivative(pressure, flow, params)
    except ValueError as exc:
        return GateEnvelope.blocked(
            "M3.BASELINE", "M3", "Parâmetros hemodinâmicos inválidos.", str(exc)
        )
    return GateEnvelope.passed(
        "M3.BASELINE",
        "M3",
        "O ponto de equilíbrio do modelo WK2 satisfaz dP/dt = 0.",
        metrics={
            "flow": flow,
            "equilibrium_pressure": pressure,
            "derivative_at_equilibrium": derivative,
            "time_constant": params.resistance * params.compliance,
        },
    )

