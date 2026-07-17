"""Construção reproduzível do dataset M2 a partir de páginas ChEMBL congeladas."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .contracts import GateEnvelope, GateStatus
from .data import FrozenSplit, SplitPartition
from .hashing import canonical_json_hash, sha256_file


@dataclass(frozen=True)
class M2DatasetBuild:
    dataset: Mapping[str, Any] | None
    split: FrozenSplit | None
    gate: GateEnvelope


def _load_rdkit() -> tuple[Any, Any, str]:
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem.Scaffolds import MurckoScaffold
    except ImportError as exc:
        raise RuntimeError(
            "RDKit é obrigatório para o split Bemis-Murcko; instale o extra chemistry"
        ) from exc
    return Chem, MurckoScaffold, str(rdBase.rdkitVersion)


def _partition_groups(
    group_records: Mapping[str, list[str]],
    *,
    salt: str,
) -> dict[SplitPartition, tuple[str, ...]]:
    ratios = {
        SplitPartition.TRAIN: 0.70,
        SplitPartition.CALIBRATION: 0.15,
        SplitPartition.INTERNAL_TEST: 0.15,
    }
    total = sum(len(records) for records in group_records.values())
    assigned: dict[SplitPartition, list[str]] = {partition: [] for partition in ratios}
    ordered = sorted(
        group_records,
        key=lambda group: hashlib.sha256(f"{salt}\0{group}".encode("utf-8")).hexdigest(),
    )
    for group in ordered:
        records = group_records[group]
        partition = min(
            ratios,
            key=lambda candidate: (
                (len(assigned[candidate]) + len(records) - total * ratios[candidate]) ** 2
                - (len(assigned[candidate]) - total * ratios[candidate]) ** 2,
                candidate.value,
            ),
        )
        assigned[partition].extend(records)
    return {
        partition: tuple(sorted(records)) for partition, records in assigned.items()
    }


def build_chembl_m2_dataset(
    page_paths: Sequence[Path],
    *,
    source_snapshot_id: str,
    target_chembl_id: str,
    endpoint: str,
    unit: str,
    split_salt: str,
    focus_compounds: Sequence[str] = (),
    expected_rdkit_version: str | None = None,
    run_id: str | None = None,
) -> M2DatasetBuild:
    if not page_paths:
        raise ValueError("Informe páginas ChEMBL congeladas")
    if endpoint not in {"Kd", "Ki", "IC50"}:
        raise ValueError("endpoint deve permanecer tipado")
    if unit != "nM":
        raise ValueError("O primeiro builder M2 aceita apenas o contrato explícito nM")
    if not split_salt.strip():
        raise ValueError("split_salt é obrigatório")

    Chem, MurckoScaffold, rdkit_version = _load_rdkit()
    if expected_rdkit_version and rdkit_version != expected_rdkit_version:
        return M2DatasetBuild(
            None,
            None,
            GateEnvelope.blocked(
                "DATA.M2.BUILD",
                "M2",
                "A versão do motor químico não corresponde ao protocolo.",
                f"Esperado RDKit {expected_rdkit_version}; encontrado {rdkit_version}.",
                run_id=run_id,
            ),
        )

    records: list[dict[str, Any]] = []
    invalid_smiles: list[str] = []
    contract_violations: list[str] = []
    activity_ids: set[str] = set()
    molecule_scaffolds: dict[str, str] = {}
    molecule_values: dict[str, list[float]] = {}

    for path in page_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for raw in payload.get("activities", []):
            activity_id = str(raw.get("activity_id", ""))
            if (
                not activity_id
                or raw.get("target_chembl_id") != target_chembl_id
                or raw.get("standard_type") != endpoint
                or raw.get("standard_units") != unit
                or raw.get("standard_relation") != "="
            ):
                contract_violations.append(activity_id or "missing-activity-id")
                continue
            if activity_id in activity_ids:
                contract_violations.append(activity_id)
                continue
            activity_ids.add(activity_id)
            smiles = str(raw.get("canonical_smiles") or "")
            molecule = Chem.MolFromSmiles(smiles)
            if molecule is None:
                invalid_smiles.append(activity_id)
                continue
            canonical_smiles = Chem.MolToSmiles(molecule, canonical=True, isomericSmiles=True)
            scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=molecule)
            group_id = f"MURCKO:{scaffold}" if scaffold else f"ACYCLIC:{canonical_smiles}"
            molecule_id = str(raw["molecule_chembl_id"])
            previous_scaffold = molecule_scaffolds.setdefault(molecule_id, group_id)
            if previous_scaffold != group_id:
                contract_violations.append(activity_id)
                continue
            value_nm = float(raw["standard_value"])
            if not math.isfinite(value_nm) or value_nm <= 0:
                contract_violations.append(activity_id)
                continue
            p_activity = 9.0 - math.log10(value_nm)
            molecule_values.setdefault(molecule_id, []).append(p_activity)
            records.append(
                {
                    "record_id": f"chembl:{activity_id}",
                    "source_activity_id": activity_id,
                    "molecule_chembl_id": molecule_id,
                    "molecule_pref_name": raw.get("molecule_pref_name"),
                    "target_chembl_id": target_chembl_id,
                    "target_organism": raw.get("target_organism"),
                    "endpoint": endpoint,
                    "relation": "=",
                    "value": value_nm,
                    "unit": unit,
                    "value_molar": value_nm * 1e-9,
                    "p_activity": p_activity,
                    "canonical_smiles": canonical_smiles,
                    "murcko_scaffold": scaffold,
                    "group_id": group_id,
                    "assay_chembl_id": raw.get("assay_chembl_id"),
                    "document_chembl_id": raw.get("document_chembl_id"),
                    "assay_type": raw.get("assay_type"),
                    "potential_duplicate": int(raw.get("potential_duplicate") or 0),
                    "data_validity_comment": raw.get("data_validity_comment"),
                    "eligible_for_model": not raw.get("potential_duplicate")
                    and raw.get("data_validity_comment") in {None, ""},
                }
            )

    errors: list[str] = []
    if contract_violations:
        errors.append(f"{len(contract_violations)} registros violam o contrato ou estão duplicados")
    if invalid_smiles:
        errors.append(f"{len(invalid_smiles)} estruturas não puderam ser interpretadas pelo RDKit")
    if not records:
        errors.append("Nenhum registro normalizado foi produzido")
    if errors:
        return M2DatasetBuild(
            None,
            None,
            GateEnvelope(
                "DATA.M2.BUILD",
                "M2",
                GateStatus.FAILED,
                "O dataset M2 não pôde ser construído.",
                run_id=run_id or "m2-build",
                metrics={
                    "contract_violations": len(contract_violations),
                    "invalid_smiles": len(invalid_smiles),
                },
                errors=tuple(errors),
            ),
        )

    records.sort(key=lambda record: int(record["source_activity_id"]))
    spreads = {
        molecule_id: max(values) - min(values)
        for molecule_id, values in molecule_values.items()
        if len(values) > 1
    }
    focus_counts = {
        compound: sum(record["molecule_chembl_id"] == compound for record in records)
        for compound in focus_compounds
    }
    focus_spreads = {compound: spreads.get(compound, 0.0) for compound in focus_compounds}
    group_records: dict[str, list[str]] = {}
    groups: dict[str, str] = {}
    for record in records:
        record_id = str(record["record_id"])
        group_id = str(record["group_id"])
        group_records.setdefault(group_id, []).append(record_id)
        groups[record_id] = group_id

    dataset_core = {
        "schema_version": "1.0",
        "source_snapshot_id": source_snapshot_id,
        "target_chembl_id": target_chembl_id,
        "endpoint": endpoint,
        "unit": unit,
        "relation": "=",
        "chemistry_engine": {"name": "RDKit", "version": rdkit_version},
        "records": records,
    }
    dataset_id = canonical_json_hash(dataset_core)
    dataset = {
        **dataset_core,
        "dataset_id": dataset_id,
        "qc": {
            "records": len(records),
            "eligible_records": sum(bool(record["eligible_for_model"]) for record in records),
            "unique_molecules": len(molecule_values),
            "unique_scaffold_groups": len(group_records),
            "molecules_with_replicates": len(spreads),
            "max_within_molecule_pk_spread": max(spreads.values(), default=0.0),
            "molecules_with_pk_spread_gt_1": sum(value > 1.0 for value in spreads.values()),
            "molecules_with_pk_spread_gt_2": sum(value > 2.0 for value in spreads.values()),
            "focus_compound_records": focus_counts,
            "focus_compound_pk_spread": focus_spreads,
            "modeling_readiness": "BLOCKED_PENDING_REPLICATE_POLICY" if spreads else "READY",
        },
    }
    partitions = _partition_groups(group_records, salt=split_salt)
    split = FrozenSplit(
        split_id=f"m2-{target_chembl_id.lower()}-{endpoint.lower()}-murcko-v1",
        dataset_snapshot_id=dataset_id,
        partitions=partitions,
        groups=groups,
        external_set_locked=False,
        strategy=f"Bemis-Murcko/RDKit-{rdkit_version}; deterministic-salt:{split_salt}",
    )
    split_gate = split.validation_gate()
    if split_gate.status is not GateStatus.PASSED:
        return M2DatasetBuild(dataset, None, split_gate)
    metrics = {
        **dataset["qc"],
        "dataset_id": dataset_id,
        "source_snapshot_id": source_snapshot_id,
        "rdkit_version": rdkit_version,
        "partition_sizes": {
            partition.value: len(member_ids)
            for partition, member_ids in partitions.items()
        },
        "split_sha256": split.definition_sha256(),
    }
    return M2DatasetBuild(
        dataset,
        split,
        GateEnvelope.passed(
            "DATA.M2.BUILD",
            "M2",
            "Dataset real normalizado e split Bemis-Murcko sem leakage foram construídos.",
            run_id=run_id,
            metrics=metrics,
            warnings=(
                "Medições repetidas foram preservadas; agregação/ponderação será pré-registrada no S3.",
                "Dispersão entre ensaios é diagnóstica e bloqueia ajuste até a política de replicatas.",
                "Este gate valida dados e split, não desempenho preditivo nem causalidade.",
            ),
        ),
    )


def write_m2_dataset_build(
    build: M2DatasetBuild,
    dataset_path: Path,
    split_path: Path,
) -> dict[str, str]:
    if build.dataset is None or build.split is None:
        raise ValueError("Somente builds aprovados podem ser gravados")
    if dataset_path.exists() or split_path.exists():
        raise FileExistsError("Dataset e split são imutáveis; escolha novos destinos")
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    split_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps(build.dataset, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    split_payload = {
        "split_id": build.split.split_id,
        "dataset_snapshot_id": build.split.dataset_snapshot_id,
        "partitions": {
            partition.value: list(members)
            for partition, members in build.split.partitions.items()
        },
        "groups": dict(build.split.groups),
        "external_set_locked": build.split.external_set_locked,
        "strategy": build.split.strategy,
        "definition_sha256": build.split.definition_sha256(),
    }
    split_path.write_text(
        json.dumps(split_payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "dataset_path": str(dataset_path.resolve()),
        "dataset_file_sha256": sha256_file(dataset_path),
        "split_path": str(split_path.resolve()),
        "split_file_sha256": sha256_file(split_path),
    }
