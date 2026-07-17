"""Carregamento e verificação das macros de orquestração."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .contracts import GateEnvelope, GateStatus, ModuleContext, ModuleReadiness
from .db import ApexDatabase
from .modules.hemodynamics import WK2Parameters, validate_baseline
from .modules.identifiability import validate_linear_design
from .modules.molecular import validate_affinity
from .modules.pbpk import validate_mass_balance
from .modules.provenance import build_manifest
from .registry import get_module


@dataclass(frozen=True)
class MacroDefinition:
    macro_id: str
    name: str
    description: str
    steps: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "macro_id": self.macro_id,
            "name": self.name,
            "description": self.description,
            "steps": list(self.steps),
        }


def default_macros_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "macros"


def load_macro(path: Path) -> MacroDefinition:
    data = json.loads(path.read_text(encoding="utf-8"))
    required = {"macro_id", "name", "description", "steps"}
    missing = required.difference(data)
    if missing:
        raise ValueError(f"Macro {path} não contém: {', '.join(sorted(missing))}")
    steps = tuple(str(step) for step in data["steps"])
    if not steps:
        raise ValueError(f"Macro {path} não possui etapas")
    for step in steps:
        get_module(step)
    return MacroDefinition(
        macro_id=str(data["macro_id"]),
        name=str(data["name"]),
        description=str(data["description"]),
        steps=steps,
    )


def list_macros(macros_dir: Path | None = None) -> tuple[MacroDefinition, ...]:
    directory = macros_dir or default_macros_dir()
    return tuple(load_macro(path) for path in sorted(directory.glob("*.json")))


def get_macro(macro_id: str, macros_dir: Path | None = None) -> MacroDefinition:
    for macro in list_macros(macros_dir):
        if macro.macro_id == macro_id:
            return macro
    raise KeyError(f"Macro desconhecida: {macro_id}")


def readiness_gate(macro: MacroDefinition, run_id: str | None = None) -> GateEnvelope:
    unavailable = [
        descriptor.module_id
        for descriptor in (get_module(step) for step in macro.steps)
        if descriptor.readiness is not ModuleReadiness.ACTIVE
    ]
    if unavailable:
        return GateEnvelope.blocked(
            f"MACRO.{macro.macro_id}",
            "ORCHESTRATOR",
            "A macro está estruturalmente correta, mas ainda não pode produzir conclusão científica.",
            "Módulos não ativos: " + ", ".join(unavailable),
            run_id=run_id,
        )
    return GateEnvelope.passed(
        f"MACRO.{macro.macro_id}",
        "ORCHESTRATOR",
        "Todos os módulos da macro estão ativos.",
        metrics={"steps": list(macro.steps)},
        run_id=run_id,
    )


def _execute_active_module(
    module_id: str, payload: dict[str, Any], context: ModuleContext
) -> GateEnvelope:
    if module_id == "M1":
        paths = [
            path if path.is_absolute() else context.workspace / path
            for path in (Path(item) for item in payload.get("paths", []))
        ]
        return build_manifest(paths, context)
    if module_id == "M0":
        return replace(
            validate_linear_design(payload["design_matrix"], payload.get("tolerance", 1e-12)),
            run_id=context.run_id,
        )
    if module_id == "M2":
        return replace(
            validate_affinity(payload["kd_molar"], payload.get("temperature_k", 298.15)),
            run_id=context.run_id,
        )
    if module_id == "M3":
        params = WK2Parameters(
            payload["resistance"],
            payload["compliance"],
            payload.get("venous_pressure", 0.0),
        )
        return replace(validate_baseline(payload["flow"], params), run_id=context.run_id)
    if module_id == "M4":
        return replace(
            validate_mass_balance(
                payload["amounts"],
                payload["transfer_rates"],
                payload.get("elimination_rates"),
                payload.get("input_rates"),
                payload.get("tolerance", 1e-12),
            ),
            run_id=context.run_id,
        )
    return GateEnvelope.blocked(
        f"{module_id}.IMPLEMENTATION",
        module_id,
        "Não há executor registrado para o módulo.",
        "Implemente e valide o executor antes de ativar este módulo.",
        run_id=context.run_id,
    )


def execute_macro(
    macro: MacroDefinition,
    context: ModuleContext,
    inputs: dict[str, dict[str, Any]],
) -> tuple[GateEnvelope, ...]:
    """Executa em ordem e interrompe no primeiro gate que não esteja PASSED."""
    database: ApexDatabase | None = None
    if context.database_path is not None:
        database = ApexDatabase(context.database_path)
        database.initialize()
    results: list[GateEnvelope] = []
    passed_modules: set[str] = set()
    for module_id in macro.steps:
        descriptor = get_module(module_id)
        unmet = [dependency for dependency in descriptor.dependencies if dependency not in passed_modules]
        if unmet:
            gate = GateEnvelope.blocked(
                f"{module_id}.DEPENDENCIES",
                module_id,
                "Dependências do módulo não foram aprovadas nesta execução.",
                "Dependências pendentes: " + ", ".join(unmet),
                run_id=context.run_id,
            )
        elif descriptor.readiness is not ModuleReadiness.ACTIVE:
            gate = GateEnvelope.blocked(
                f"{module_id}.READINESS",
                module_id,
                "A macro alcançou um módulo ainda não ativo.",
                f"Estado atual de {module_id}: {descriptor.readiness.value}.",
                run_id=context.run_id,
            )
        else:
            try:
                gate = _execute_active_module(module_id, inputs.get(module_id, {}), context)
            except (KeyError, TypeError, ValueError) as exc:
                gate = GateEnvelope.blocked(
                    f"{module_id}.INPUT",
                    module_id,
                    "A entrada da macro não satisfaz o contrato do módulo.",
                    str(exc),
                    run_id=context.run_id,
                )
        results.append(gate)
        if database is not None:
            database.record_gate(gate)
        if gate.status is not GateStatus.PASSED:
            break
        passed_modules.add(module_id)
    return tuple(results)
