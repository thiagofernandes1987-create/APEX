"""Runner único dos benchmarks matemáticos, sintéticos e bloqueados do APEX-R."""

from __future__ import annotations

import json
import platform
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from .contracts import GateEnvelope, GateStatus
from .connectors.chembl import ChemblActivityQuery, audit_activity_pages
from .data import FrozenSplit, SplitPartition
from .modules.hemodynamics import WK2Parameters, equilibrium_pressure, pressure_derivative
from .modules.molecular import delta_g_from_kd, kd_from_delta_g
from .modules.molecular_calibration import (
    CalibrationPoint,
    evaluate_molecular_calibration,
    fit_molecular_calibration,
)
from .modules.pbpk import mass_balance_error
from .modules.validation import (
    CriterionOperator,
    EvidenceLayer,
    MetricCriterion,
    MetricObservation,
    ValidationProtocol,
    evaluate_protocol,
    promotion_readiness,
)


@dataclass(frozen=True)
class BenchmarkDefinition:
    benchmark_id: str
    module_id: str
    kind: str
    description: str
    executable: bool
    runner: Callable[[str], GateEnvelope] | None = None
    blocked_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "module_id": self.module_id,
            "kind": self.kind,
            "description": self.description,
            "executable": self.executable,
            "blocked_reason": self.blocked_reason,
        }


@dataclass(frozen=True)
class BenchmarkOutcome:
    benchmark_id: str
    run_id: str
    duration_ms: float
    gate: GateEnvelope

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "run_id": self.run_id,
            "duration_ms_informational": self.duration_ms,
            "gate": self.gate.to_dict(),
        }


def _core_runner(run_id: str) -> GateEnvelope:
    kd_values = (1e-12, 1e-9, 1e-6, 1e-3)
    roundtrip_errors = [
        abs(kd_from_delta_g(delta_g_from_kd(kd)) - kd) / kd for kd in kd_values
    ]
    params = WK2Parameters(resistance=2.0, compliance=1.5, venous_pressure=5.0)
    pressure = equilibrium_pressure(4.0, params)
    wk2_error = abs(pressure_derivative(pressure, 4.0, params))
    mass_error = abs(
        mass_balance_error(
            [100.0, 20.0, 5.0],
            [[0, 0.2, 0.1], [0.05, 0, 0.03], [0.02, 0.04, 0]],
            [0.01, 0.02, 0.0],
            [1.4, 0.0, 0.0],
        )
    )
    metrics = {
        "m2_max_roundtrip_relative_error": max(roundtrip_errors),
        "m2_tolerance": 1e-12,
        "m3_derivative_at_equilibrium": wk2_error,
        "m3_tolerance": 1e-12,
        "m4_mass_balance_error": mass_error,
        "m4_tolerance": 1e-12,
    }
    failures = []
    if max(roundtrip_errors) > 1e-12:
        failures.append("M2 round-trip excedeu 1e-12")
    if wk2_error > 1e-12:
        failures.append("M3 equilíbrio excedeu 1e-12")
    if mass_error > 1e-12:
        failures.append("M4 conservação excedeu 1e-12")
    if failures:
        return GateEnvelope(
            "BENCHMARK.B-VERIFY-CORE",
            "M11",
            GateStatus.FAILED,
            "O benchmark matemático central apresentou regressão.",
            run_id=run_id,
            metrics=metrics,
            errors=tuple(failures),
        )
    return GateEnvelope.passed(
        "BENCHMARK.B-VERIFY-CORE",
        "M11",
        "Termodinâmica, equilíbrio WK2 e conservação de massa permanecem nas tolerâncias.",
        run_id=run_id,
        metrics=metrics,
    )


def _m11_runner(run_id: str) -> GateEnvelope:
    protocol = ValidationProtocol(
        "B-VERIFY-M11-DEMO",
        "1.0",
        "M2",
        EvidenceLayer.SYNTHETIC,
        "synthetic-snapshot",
        "synthetic-split",
        (MetricCriterion("recovery_error", CriterionOperator.ABS_LTE, 1e-12),),
        30,
        True,
        synthetic_data=True,
    )
    outcome = evaluate_protocol(
        protocol,
        {"recovery_error": MetricObservation(0.0, 30)},
        run_id=run_id,
    )
    review = promotion_readiness([outcome], [EvidenceLayer.SYNTHETIC], run_id=run_id)
    invalid_external_rejected = False
    try:
        ValidationProtocol(
            "invalid",
            "1",
            "M2",
            EvidenceLayer.EXTERNAL,
            "synthetic",
            "split",
            (MetricCriterion("x", CriterionOperator.LTE, 1.0),),
            1,
            True,
            external_set_locked=True,
            synthetic_data=True,
        )
    except ValueError:
        invalid_external_rejected = True
    checks = {
        "synthetic_protocol_passed": outcome.gate.status is GateStatus.PASSED,
        "promotion_requires_review": review.status is GateStatus.NEEDS_REVIEW,
        "synthetic_external_rejected": invalid_external_rejected,
    }
    if not all(checks.values()):
        return GateEnvelope(
            "BENCHMARK.B-VERIFY-M11",
            "M11",
            GateStatus.FAILED,
            "O fluxo de evidência M11 regrediu.",
            run_id=run_id,
            metrics=checks,
            errors=("Ao menos uma barreira de evidência não foi preservada.",),
        )
    return GateEnvelope.passed(
        "BENCHMARK.B-VERIFY-M11",
        "M11",
        "Pré-registro, separação sintética e revisão humana foram preservados.",
        run_id=run_id,
        metrics=checks,
    )


def _m2_calibration_runner(run_id: str) -> GateEnvelope:
    points = [
        CalibrationPoint(f"r{i}", f"g{i}", "Kd", float(i), 2.0 + 3.0 * i)
        for i in range(1, 7)
    ]
    split = FrozenSplit(
        "benchmark-m2-cal",
        "synthetic-snapshot",
        {
            SplitPartition.TRAIN: ("r1", "r2", "r3", "r4"),
            SplitPartition.INTERNAL_TEST: ("r5", "r6"),
        },
        {f"r{i}": f"g{i}" for i in range(1, 7)},
        False,
        "independent-synthetic-groups",
    )
    fitted = fit_molecular_calibration(
        points, split, model_id="benchmark-linear", run_id=run_id
    )
    if fitted.model is None:
        return GateEnvelope(
            "BENCHMARK.B-VERIFY-M2-CAL",
            "M2",
            GateStatus.FAILED,
            "O modelo sintético não pôde ser ajustado.",
            run_id=run_id,
            errors=fitted.gate.errors or ("Fit bloqueado.",),
        )
    evaluation = evaluate_molecular_calibration(
        fitted.model,
        points,
        split,
        SplitPartition.INTERNAL_TEST,
        run_id=run_id,
    )
    metrics = {
        "intercept_error": abs(fitted.model.fit.intercept - 2.0),
        "slope_error": abs(fitted.model.fit.slope - 3.0),
        "internal_rmse_pk": evaluation.metrics.get("rmse_pk"),
        "internal_spearman": evaluation.metrics.get("spearman"),
        "tolerance": 1e-12,
    }
    passed = (
        metrics["intercept_error"] <= 1e-12
        and metrics["slope_error"] <= 1e-12
        and metrics["internal_rmse_pk"] <= 1e-12
        and metrics["internal_spearman"] == 1.0
    )
    if not passed:
        return GateEnvelope(
            "BENCHMARK.B-VERIFY-M2-CAL",
            "M2",
            GateStatus.FAILED,
            "A recuperação sintética da calibração M2 regrediu.",
            run_id=run_id,
            metrics=metrics,
            errors=("Coeficientes ou métricas excederam a tolerância.",),
        )
    return GateEnvelope.passed(
        "BENCHMARK.B-VERIFY-M2-CAL",
        "M2",
        "Coeficientes conhecidos e avaliação interna foram recuperados.",
        run_id=run_id,
        metrics=metrics,
        warnings=("Benchmark sintético; não constitui validação molecular externa.",),
    )


def _chembl_qc_runner(run_id: str) -> GateEnvelope:
    activity = {
        "activity_id": 1,
        "molecule_chembl_id": "CHEMBL113",
        "target_chembl_id": "CHEMBL251",
        "standard_type": "Ki",
        "standard_relation": "=",
        "standard_value": "10000",
        "standard_units": "nM",
        "canonical_smiles": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    }
    query = ChemblActivityQuery("CHEMBL251", "Ki", "nM", 1000)
    with tempfile.TemporaryDirectory() as directory:
        complete_path = Path(directory) / "complete.json"
        complete_path.write_text(
            json.dumps(
                {
                    "activities": [activity],
                    "page_meta": {"total_count": 1, "next": None},
                }
            ),
            encoding="utf-8",
        )
        partial_path = Path(directory) / "partial.json"
        partial_path.write_text(
            json.dumps(
                {
                    "activities": [activity],
                    "page_meta": {"total_count": 2, "next": "/chembl/api/data/activity.json?offset=1"},
                }
            ),
            encoding="utf-8",
        )
        complete = audit_activity_pages([complete_path], query, run_id=run_id)
        partial = audit_activity_pages([partial_path], query, run_id=run_id)
    checks = {
        "complete_snapshot_passed": complete.gate.status is GateStatus.PASSED,
        "partial_snapshot_failed": partial.gate.status is GateStatus.FAILED,
        "endpoint_preserved": complete.gate.metrics.get("endpoint") == "Ki",
        "structure_required": complete.records_with_structure == complete.raw_records,
    }
    if not all(checks.values()):
        return GateEnvelope(
            "BENCHMARK.B-VERIFY-CHEMBL-QC",
            "M2",
            GateStatus.FAILED,
            "As barreiras de aquisição ChEMBL regrediram.",
            run_id=run_id,
            metrics=checks,
            errors=("Completude, tipagem ou estrutura deixou de ser fiscalizada.",),
        )
    return GateEnvelope.passed(
        "BENCHMARK.B-VERIFY-CHEMBL-QC",
        "M2",
        "O QC aceita aquisição completa e rejeita paginação parcial.",
        run_id=run_id,
        metrics=checks,
        warnings=("Fixture sintética de schema; não valida afinidade molecular.",),
    )


BENCHMARKS: tuple[BenchmarkDefinition, ...] = (
    BenchmarkDefinition("B-VERIFY-CORE", "M0-M4", "synthetic", "Invariantes matemáticos centrais", True, _core_runner),
    BenchmarkDefinition("B-VERIFY-M11", "M11", "synthetic", "Barreiras de evidência e promoção", True, _m11_runner),
    BenchmarkDefinition("B-VERIFY-M2-CAL", "M2", "synthetic", "Recuperação de calibração linear conhecida", True, _m2_calibration_runner),
    BenchmarkDefinition("B-VERIFY-CHEMBL-QC", "M2", "synthetic", "Completude e tipagem da aquisição ChEMBL", True, _chembl_qc_runner),
    BenchmarkDefinition("B-M2", "M2", "external", "Afinidade em conjunto externo bloqueado", False, blocked_reason="Aguardando snapshot real, features e protocolo S2-S4."),
    BenchmarkDefinition("B-CAUSAL", "M2.5/M9", "synthetic", "ACE, viés, RMSE e cobertura", False, blocked_reason="Aguardando equações causais executáveis no S6."),
    BenchmarkDefinition("B-M4", "M4", "external", "PBPK OSP por estudo", False, blocked_reason="Aguardando PBPK fisiológico completo no S7."),
    BenchmarkDefinition("B-M6", "M6", "external", "Superfícies checkerboard", False, blocked_reason="Aguardando M5/M6 no S8-S9."),
    BenchmarkDefinition("B-M8", "M8", "analytic", "ZDT/DTLZ e robustez Pareto", False, blocked_reason="Aguardando otimizador no S11."),
    BenchmarkDefinition("B-PCL", "PCL", "preclinical", "Pacote pré-clínico em camadas", False, blocked_reason="Aguardando perfil executável no S13."),
)


def list_benchmarks() -> tuple[BenchmarkDefinition, ...]:
    return BENCHMARKS


def get_benchmark(benchmark_id: str) -> BenchmarkDefinition:
    normalized = benchmark_id.upper()
    for definition in BENCHMARKS:
        if definition.benchmark_id.upper() == normalized:
            return definition
    raise KeyError(f"Benchmark desconhecido: {benchmark_id}")


def run_benchmark(benchmark_id: str, *, run_id: str | None = None) -> BenchmarkOutcome:
    definition = get_benchmark(benchmark_id)
    effective_run_id = run_id or str(uuid4())
    started = time.perf_counter()
    if not definition.executable or definition.runner is None:
        gate = GateEnvelope.blocked(
            f"BENCHMARK.{definition.benchmark_id}",
            definition.module_id,
            "Benchmark registrado, mas ainda não executável.",
            definition.blocked_reason or "Implementação ou dados pendentes.",
            run_id=effective_run_id,
        )
    else:
        gate = definition.runner(effective_run_id)
    duration_ms = (time.perf_counter() - started) * 1000
    return BenchmarkOutcome(definition.benchmark_id, effective_run_id, duration_ms, gate)


def run_verification_suite(*, run_id: str | None = None) -> dict[str, Any]:
    effective_run_id = run_id or str(uuid4())
    outcomes = [
        run_benchmark(definition.benchmark_id, run_id=effective_run_id)
        for definition in BENCHMARKS
        if definition.executable
    ]
    passed = all(outcome.gate.status is GateStatus.PASSED for outcome in outcomes)
    return {
        "schema_version": "1.0",
        "run_id": effective_run_id,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "environment": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "status": "PASSED" if passed else "FAILED",
        "outcomes": [outcome.to_dict() for outcome in outcomes],
    }


def write_benchmark_report(report: dict[str, Any], destination: Path) -> None:
    if destination.exists():
        raise FileExistsError("Relatórios de benchmark são imutáveis; use um novo run_id")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
