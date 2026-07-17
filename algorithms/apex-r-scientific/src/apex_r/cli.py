"""Interface de linha de comando do primeiro incremento APEX-R."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

from .benchmarks import (
    list_benchmarks,
    run_benchmark,
    run_verification_suite,
    write_benchmark_report,
)
from .contracts import ModuleContext
from .connectors.chembl import (
    ChemblActivityQuery,
    audit_activity_pages,
    chembl_source,
    fetch_activity_pages,
)
from .data import (
    ContentAddressedStore,
    FrozenSplit,
    SourceDefinition,
    build_local_snapshot,
    write_snapshot_manifest,
    SplitPartition,
)
from .db import ApexDatabase
from .formula_registry import get_formula, list_formulas
from .hashing import sha256_file
from .macros import execute_macro, get_macro, list_macros, readiness_gate
from .m2_dataset import build_chembl_m2_dataset, write_m2_dataset_build
from .modules.hemodynamics import WK2Parameters, validate_baseline
from .modules.identifiability import validate_linear_design
from .modules.causal_dsm import CausalDSM
from .modules.molecular import validate_affinity
from .modules.molecular_calibration import (
    CalibrationPoint,
    evaluate_molecular_calibration,
    fit_molecular_calibration,
)
from .modules.pbpk import validate_mass_balance
from .modules.validation import ValidationProtocol, evaluate_protocol
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

    data = commands.add_parser("data", help="Cria snapshots e valida splits")
    data_actions = data.add_subparsers(dest="action", required=True)
    snapshot = data_actions.add_parser("snapshot")
    snapshot.add_argument("--source", type=Path, required=True, help="Definição JSON da fonte")
    snapshot.add_argument("--file", type=Path, action="append", required=True)
    snapshot.add_argument("--store", type=Path, required=True)
    snapshot.add_argument("--manifest", type=Path, required=True)
    snapshot.add_argument("--db", type=Path)
    split = data_actions.add_parser("split-check")
    split.add_argument("--input", type=Path, required=True)
    split.add_argument("--db", type=Path)
    chembl_plan = data_actions.add_parser("chembl-plan")
    chembl_plan.add_argument("--target", required=True, help="Target ChEMBL ID")
    chembl_plan.add_argument("--endpoint", choices=("Kd", "Ki", "IC50"), required=True)
    chembl_plan.add_argument("--unit", choices=("M", "mM", "uM", "nM", "pM"), default="nM")
    chembl_plan.add_argument("--limit", type=int, default=1000)
    chembl_fetch = data_actions.add_parser(
        "chembl-fetch", help="Baixa, audita e congela uma consulta ChEMBL completa"
    )
    chembl_fetch.add_argument("--target", required=True, help="Target ChEMBL ID")
    chembl_fetch.add_argument("--endpoint", choices=("Kd", "Ki", "IC50"), required=True)
    chembl_fetch.add_argument(
        "--unit", choices=("M", "mM", "uM", "nM", "pM"), default="nM"
    )
    chembl_fetch.add_argument("--release", required=True, help="Release congelada, ex. CHEMBL_37")
    chembl_fetch.add_argument("--limit", type=int, default=1000)
    chembl_fetch.add_argument("--max-records", type=int, required=True)
    chembl_fetch.add_argument("--raw-dir", type=Path, required=True)
    chembl_fetch.add_argument("--store", type=Path, required=True)
    chembl_fetch.add_argument("--manifest", type=Path, required=True)
    chembl_fetch.add_argument("--audit-report", type=Path, required=True)
    chembl_fetch.add_argument("--db", type=Path)
    chembl_build = data_actions.add_parser(
        "chembl-build-m2", help="Normaliza afinidades e cria split Bemis-Murcko"
    )
    chembl_build.add_argument("--raw-dir", type=Path, required=True)
    chembl_build.add_argument("--snapshot-manifest", type=Path, required=True)
    chembl_build.add_argument("--target", required=True)
    chembl_build.add_argument("--endpoint", choices=("Kd", "Ki", "IC50"), required=True)
    chembl_build.add_argument("--unit", choices=("nM",), default="nM")
    chembl_build.add_argument("--split-salt", required=True)
    chembl_build.add_argument("--rdkit-version", required=True)
    chembl_build.add_argument("--focus-compound", action="append", default=[])
    chembl_build.add_argument("--dataset-output", type=Path, required=True)
    chembl_build.add_argument("--split-output", type=Path, required=True)
    chembl_build.add_argument("--db", type=Path)

    calibrate = commands.add_parser("calibrate", help="Ajusta modelos candidatos sem promoção")
    calibrations = calibrate.add_subparsers(dest="calibration", required=True)
    affinity_calibration = calibrations.add_parser("affinity")
    affinity_calibration.add_argument("--input", type=Path, required=True)

    benchmarks = commands.add_parser("benchmarks", help="Executa benchmarks rastreáveis")
    benchmark_actions = benchmarks.add_subparsers(dest="action", required=True)
    benchmark_actions.add_parser("list")
    benchmark_run = benchmark_actions.add_parser("run")
    benchmark_run.add_argument("benchmark_id")
    benchmark_run.add_argument("--output", type=Path)
    benchmark_all = benchmark_actions.add_parser("run-verification")
    benchmark_all.add_argument("--output", type=Path)

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
    protocol = validations.add_parser("protocol")
    protocol.add_argument("--input", type=Path, required=True, help="Protocolo e observações JSON")
    protocol.add_argument("--db", type=Path)
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
    if args.command == "data":
        if args.action == "chembl-plan":
            query = ChemblActivityQuery(args.target, args.endpoint, args.unit, args.limit)
            _print_json(
                {
                    "source": "ChEMBL",
                    "license": "CC BY-SA 3.0 Unported",
                    "query": query.to_dict(),
                    "execution": "not_started",
                }
            )
            return 0
        if args.action == "chembl-fetch":
            query = ChemblActivityQuery(args.target, args.endpoint, args.unit, args.limit)
            paths = fetch_activity_pages(
                query,
                args.raw_dir,
                max_records=args.max_records,
            )
            audit = audit_activity_pages(paths, query)
            audit_payload = {
                "source": "ChEMBL",
                "release": args.release,
                "query": query.to_dict(),
                "audit": audit.to_dict(),
            }
            encoded_audit = (
                json.dumps(audit_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
            )
            args.audit_report.parent.mkdir(parents=True, exist_ok=True)
            if args.audit_report.exists():
                raise FileExistsError("Relatório de auditoria ChEMBL é imutável")
            args.audit_report.write_text(encoded_audit, encoding="utf-8")
            if audit.gate.status.value != "PASSED":
                _print_json(audit_payload)
                return 2
            snapshot = build_local_snapshot(
                chembl_source(args.release),
                paths,
                store=ContentAddressedStore(args.store),
                query={
                    **query.to_dict(),
                    "max_records": args.max_records,
                    "total_count_reported": audit.total_count_reported,
                    "audit_gate": audit.gate.gate_id,
                },
            )
            write_snapshot_manifest(snapshot, args.manifest)
            if args.db:
                database = ApexDatabase(args.db)
                database.initialize()
                database.record_snapshot(snapshot)
                database.record_gate(audit.gate)
            output = {
                "snapshot": snapshot.to_dict(),
                "audit": audit.to_dict(),
            }
            _print_json(output)
            return 0
        if args.action == "chembl-build-m2":
            manifest = json.loads(args.snapshot_manifest.read_text(encoding="utf-8"))
            page_paths = tuple(sorted(args.raw_dir.glob("activity-page-*.json")))
            expected_files = {
                str(item["original_name"]): str(item["sha256"])
                for item in manifest["files"]
            }
            actual_files = {path.name: sha256_file(path) for path in page_paths}
            if actual_files != expected_files:
                _print_json(
                    {
                        "status": "BLOCKED",
                        "reason": "As páginas locais não correspondem ao snapshot congelado.",
                        "expected_files": expected_files,
                        "actual_files": actual_files,
                    }
                )
                return 2
            build = build_chembl_m2_dataset(
                page_paths,
                source_snapshot_id=str(manifest["snapshot_id"]),
                target_chembl_id=args.target,
                endpoint=args.endpoint,
                unit=args.unit,
                split_salt=args.split_salt,
                focus_compounds=args.focus_compound,
                expected_rdkit_version=args.rdkit_version,
            )
            output: dict[str, Any] = {"gate": build.gate.to_dict()}
            if build.gate.status.value == "PASSED":
                output["files"] = write_m2_dataset_build(
                    build, args.dataset_output, args.split_output
                )
                if args.db and build.split is not None:
                    database = ApexDatabase(args.db)
                    database.initialize()
                    database.record_split(build.split)
                    database.record_gate(build.gate)
            _print_json(output)
            return 0 if build.gate.status.value == "PASSED" else 2
        if args.action == "snapshot":
            source = SourceDefinition.from_dict(json.loads(args.source.read_text(encoding="utf-8")))
            snapshot = build_local_snapshot(
                source,
                args.file,
                store=ContentAddressedStore(args.store),
            )
            write_snapshot_manifest(snapshot, args.manifest)
            if args.db:
                database = ApexDatabase(args.db)
                database.initialize()
                database.record_snapshot(snapshot)
            _print_json(snapshot.to_dict())
            return 0
        split = FrozenSplit.from_dict(json.loads(args.input.read_text(encoding="utf-8")))
        gate = split.validation_gate()
        if args.db and gate.status.value == "PASSED":
            database = ApexDatabase(args.db)
            database.initialize()
            database.record_split(split)
            database.record_gate(gate)
        _print_json(gate.to_dict())
        return 0 if gate.status.value == "PASSED" else 2
    if args.command == "calibrate":
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        run_id = str(uuid4())
        points = [
            CalibrationPoint(
                record_id=str(item["record_id"]),
                group_id=str(item["group_id"]),
                endpoint=str(item["endpoint"]),
                score=float(item["score"]),
                observed_pk=float(item["observed_pk"]),
            )
            for item in payload["points"]
        ]
        split = FrozenSplit.from_dict(payload["split"])
        fit_result = fit_molecular_calibration(
            points, split, model_id=str(payload["model_id"]), run_id=run_id
        )
        output: dict[str, Any] = {
            "run_id": run_id,
            "fit_gate": fit_result.gate.to_dict(),
            "model": None,
        }
        final_gate = fit_result.gate
        if fit_result.model is not None:
            model = fit_result.model
            output["model"] = {
                "model_id": model.model_id,
                "endpoint": model.endpoint,
                "dataset_snapshot_id": model.dataset_snapshot_id,
                "split_id": model.split_id,
                "split_sha256": model.split_sha256,
                "fit": asdict(model.fit),
                "training_record_ids": list(model.training_record_ids),
            }
            if payload.get("evaluation_partition"):
                protocol = (
                    ValidationProtocol.from_dict(payload["protocol"])
                    if payload.get("protocol")
                    else None
                )
                evaluation = evaluate_molecular_calibration(
                    model,
                    points,
                    split,
                    SplitPartition(str(payload["evaluation_partition"])),
                    protocol=protocol,
                    run_id=run_id,
                )
                output["evaluation_gate"] = evaluation.gate.to_dict()
                output["evaluation_metrics"] = evaluation.metrics
                final_gate = evaluation.gate
        _print_json(output)
        return 0 if final_gate.status.value == "PASSED" else 2
    if args.command == "benchmarks":
        if args.action == "list":
            _print_json([definition.to_dict() for definition in list_benchmarks()])
            return 0
        if args.action == "run":
            outcome = run_benchmark(args.benchmark_id)
            report = {
                "schema_version": "1.0",
                "run_id": outcome.run_id,
                "status": outcome.gate.status.value,
                "outcomes": [outcome.to_dict()],
            }
            if args.output:
                write_benchmark_report(report, args.output)
            _print_json(report)
            return 0 if outcome.gate.status.value == "PASSED" else 2
        report = run_verification_suite()
        if args.output:
            write_benchmark_report(report, args.output)
        _print_json(report)
        return 0 if report["status"] == "PASSED" else 2
    if args.command == "validate":
        if args.validation == "affinity":
            gate = validate_affinity(args.kd, args.temperature)
        elif args.validation == "design":
            gate = validate_linear_design(json.loads(args.matrix), args.tolerance)
        elif args.validation == "dsm":
            model = CausalDSM.from_dict(json.loads(args.input.read_text(encoding="utf-8")))
            gate = model.structural_gate()
        elif args.validation == "protocol":
            payload = json.loads(args.input.read_text(encoding="utf-8"))
            protocol = ValidationProtocol.from_dict(payload["protocol"])
            outcome = evaluate_protocol(protocol, payload["observations"])
            gate = outcome.gate
            if args.db:
                database = ApexDatabase(args.db)
                database.initialize()
                database.record_validation_outcome(outcome)
                database.record_gate(gate)
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
