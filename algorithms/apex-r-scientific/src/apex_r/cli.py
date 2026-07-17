"""Interface de linha de comando do primeiro incremento APEX-R."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence

from .contracts import ModuleContext
from .db import ApexDatabase
from .formula_registry import get_formula, list_formulas
from .macros import execute_macro, get_macro, list_macros, readiness_gate
from .modules.hemodynamics import WK2Parameters, validate_baseline
from .modules.identifiability import validate_linear_design
from .modules.causal_dsm import CausalDSM
from .modules.molecular import validate_affinity
from .modules.pbpk import validate_mass_balance
from .registry import list_modules


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="apex-r", description="Núcleo científico APEX-R")
    commands = parser.add_subparsers(dest="command", required=True)

    modules = commands.add_parser("modules", help="Inspeciona o catálogo de módulos")
    modules.add_argument("action", choices=("list",))

    formulas = commands.add_parser("formulas", help="Inspeciona fórmulas e evidência")
    formula_actions = formulas.add_subparsers(dest="action", required=True)
    formula_actions.add_parser("list")
    formula_show = formula_actions.add_parser("show")
    formula_show.add_argument("formula_id")

    macros = commands.add_parser("macros", help="Inspeciona e verifica macros")
    macro_actions = macros.add_subparsers(dest="action", required=True)
    macro_actions.add_parser("list")
    macro_show = macro_actions.add_parser("show")
    macro_show.add_argument("macro_id")
    macro_check = macro_actions.add_parser("check")
    macro_check.add_argument("macro_id")
    macro_run = macro_actions.add_parser("run")
    macro_run.add_argument("macro_id")
    macro_run.add_argument("--input", type=Path, required=True, help="Payload JSON por módulo")
    macro_run.add_argument("--workspace", type=Path, default=Path.cwd())
    macro_run.add_argument("--db", type=Path)

    database = commands.add_parser("db", help="Gerencia a base auditável")
    database.add_argument("action", choices=("init",))
    database.add_argument("path", type=Path)

    validate = commands.add_parser("validate", help="Executa gates matemáticos iniciais")
    validations = validate.add_subparsers(dest="validation", required=True)
    affinity = validations.add_parser("affinity")
    affinity.add_argument("--kd", type=float, required=True, help="Kd em mol/L")
    affinity.add_argument("--temperature", type=float, default=298.15, help="Temperatura em K")
    hemo = validations.add_parser("hemodynamics")
    hemo.add_argument("--flow", type=float, required=True)
    hemo.add_argument("--resistance", type=float, required=True)
    hemo.add_argument("--compliance", type=float, required=True)
    hemo.add_argument("--venous-pressure", type=float, default=0.0)
    pbpk = validations.add_parser("pbpk")
    pbpk.add_argument("--amounts", required=True, help="Vetor JSON")
    pbpk.add_argument("--transfers", required=True, help="Matriz JSON; [i][j] é i→j")
    pbpk.add_argument("--elimination", help="Vetor JSON")
    pbpk.add_argument("--inputs", help="Vetor JSON")
    design = validations.add_parser("design")
    design.add_argument("--matrix", required=True, help="Matriz de desenho em JSON")
    design.add_argument("--tolerance", type=float, default=1e-12)
    dsm = validations.add_parser("dsm")
    dsm.add_argument("--input", type=Path, required=True, help="Definição JSON do CausalDSM")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "modules":
        rows = []
        for descriptor in list_modules():
            row = asdict(descriptor)
            row["readiness"] = descriptor.readiness.value
            rows.append(row)
        _print_json(rows)
        return 0
    if args.command == "formulas":
        if args.action == "list":
            _print_json([formula.to_dict() for formula in list_formulas()])
        else:
            _print_json(get_formula(args.formula_id).to_dict())
        return 0
    if args.command == "macros":
        if args.action == "list":
            _print_json([macro.to_dict() for macro in list_macros()])
            return 0
        macro = get_macro(args.macro_id)
        if args.action == "show":
            _print_json(macro.to_dict())
            return 0
        if args.action == "run":
            inputs = json.loads(args.input.read_text(encoding="utf-8"))
            context = ModuleContext(
                workspace=args.workspace.resolve(),
                database_path=args.db.resolve() if args.db else None,
            )
            gates = execute_macro(macro, context, inputs)
            _print_json({"run_id": context.run_id, "gates": [gate.to_dict() for gate in gates]})
            return 0 if gates and gates[-1].status.value == "PASSED" else 2
        gate = readiness_gate(macro)
        _print_json(gate.to_dict())
        return 0 if gate.status.value == "PASSED" else 2
    if args.command == "db":
        database = ApexDatabase(args.path)
        database.initialize()
        _print_json({"status": "initialized", "path": str(database.path.resolve())})
        return 0
    if args.command == "validate":
        if args.validation == "affinity":
            gate = validate_affinity(args.kd, args.temperature)
        elif args.validation == "design":
            gate = validate_linear_design(json.loads(args.matrix), args.tolerance)
        elif args.validation == "dsm":
            model = CausalDSM.from_dict(json.loads(args.input.read_text(encoding="utf-8")))
            gate = model.structural_gate()
        elif args.validation == "hemodynamics":
            gate = validate_baseline(
                args.flow,
                WK2Parameters(args.resistance, args.compliance, args.venous_pressure),
            )
        else:
            gate = validate_mass_balance(
                json.loads(args.amounts),
                json.loads(args.transfers),
                json.loads(args.elimination) if args.elimination else None,
                json.loads(args.inputs) if args.inputs else None,
            )
        _print_json(gate.to_dict())
        return 0 if gate.status.value == "PASSED" else 2
    return 1
