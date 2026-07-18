"""Persistência SQLite local para fontes, coeficientes, gates e auditoria."""

from __future__ import annotations

import json
import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .contracts import GateEnvelope

if TYPE_CHECKING:
    from .data import FrozenSplit, SourceSnapshot
    from .modules.validation import ValidationOutcome, ValidationProtocol


SCHEMA_VERSION = 2

SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    uri TEXT,
    license TEXT,
    version TEXT,
    retrieved_at TEXT NOT NULL,
    sha256 TEXT,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS artifact (
    artifact_id TEXT PRIMARY KEY,
    source_id TEXT REFERENCES source(source_id),
    kind TEXT NOT NULL,
    locator TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source_snapshot (
    snapshot_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES source(source_id),
    source_version TEXT NOT NULL,
    license_name TEXT NOT NULL,
    license_class TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('STAGED', 'FROZEN', 'REJECTED')),
    query_json TEXT NOT NULL,
    manifest_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS snapshot_file (
    snapshot_id TEXT NOT NULL REFERENCES source_snapshot(snapshot_id),
    sha256 TEXT NOT NULL,
    original_name TEXT NOT NULL,
    original_path TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes >= 0),
    stored_locator TEXT,
    PRIMARY KEY(snapshot_id, sha256, original_name)
);

CREATE TABLE IF NOT EXISTS benchmark_split (
    split_id TEXT PRIMARY KEY,
    dataset_snapshot_id TEXT NOT NULL,
    definition_sha256 TEXT NOT NULL,
    external_set_locked INTEGER NOT NULL CHECK(external_set_locked IN (0,1)),
    strategy TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS validation_protocol (
    protocol_id TEXT NOT NULL,
    version TEXT NOT NULL,
    module_id TEXT NOT NULL,
    evidence_layer TEXT NOT NULL,
    protocol_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(protocol_id, version)
);

CREATE TABLE IF NOT EXISTS validation_run (
    validation_run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    protocol_id TEXT NOT NULL,
    protocol_version TEXT NOT NULL,
    run_id TEXT NOT NULL,
    gate_status TEXT NOT NULL,
    candidate_evidence_label TEXT,
    outcome_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(protocol_id, protocol_version) REFERENCES validation_protocol(protocol_id, version)
);

CREATE TABLE IF NOT EXISTS coefficient_definition (
    coefficient_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    symbol TEXT,
    unit TEXT NOT NULL,
    module_id TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('HYPOTHESIS', 'CALIBRATING', 'VALIDATED', 'REJECTED'))
);

CREATE TABLE IF NOT EXISTS coefficient_estimate (
    estimate_id INTEGER PRIMARY KEY AUTOINCREMENT,
    coefficient_id TEXT NOT NULL REFERENCES coefficient_definition(coefficient_id),
    run_id TEXT NOT NULL,
    value REAL NOT NULL,
    uncertainty REAL,
    method TEXT NOT NULL,
    dataset_sha256 TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS gate_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    gate_id TEXT NOT NULL,
    module_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_event (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER IF NOT EXISTS gate_event_no_update
BEFORE UPDATE ON gate_event BEGIN SELECT RAISE(ABORT, 'gate_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS gate_event_no_delete
BEFORE DELETE ON gate_event BEGIN SELECT RAISE(ABORT, 'gate_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS coefficient_estimate_no_update
BEFORE UPDATE ON coefficient_estimate BEGIN SELECT RAISE(ABORT, 'coefficient_estimate is append-only'); END;
CREATE TRIGGER IF NOT EXISTS coefficient_estimate_no_delete
BEFORE DELETE ON coefficient_estimate BEGIN SELECT RAISE(ABORT, 'coefficient_estimate is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_event_no_update
BEFORE UPDATE ON audit_event BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_event_no_delete
BEFORE DELETE ON audit_event BEGIN SELECT RAISE(ABORT, 'audit_event is append-only'); END;
CREATE TRIGGER IF NOT EXISTS source_snapshot_no_update
BEFORE UPDATE ON source_snapshot BEGIN SELECT RAISE(ABORT, 'source_snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS source_snapshot_no_delete
BEFORE DELETE ON source_snapshot BEGIN SELECT RAISE(ABORT, 'source_snapshot is immutable'); END;
CREATE TRIGGER IF NOT EXISTS snapshot_file_no_update
BEFORE UPDATE ON snapshot_file BEGIN SELECT RAISE(ABORT, 'snapshot_file is immutable'); END;
CREATE TRIGGER IF NOT EXISTS snapshot_file_no_delete
BEFORE DELETE ON snapshot_file BEGIN SELECT RAISE(ABORT, 'snapshot_file is immutable'); END;
CREATE TRIGGER IF NOT EXISTS benchmark_split_no_update
BEFORE UPDATE ON benchmark_split BEGIN SELECT RAISE(ABORT, 'benchmark_split is immutable'); END;
CREATE TRIGGER IF NOT EXISTS benchmark_split_no_delete
BEFORE DELETE ON benchmark_split BEGIN SELECT RAISE(ABORT, 'benchmark_split is immutable'); END;
CREATE TRIGGER IF NOT EXISTS validation_protocol_no_update
BEFORE UPDATE ON validation_protocol BEGIN SELECT RAISE(ABORT, 'validation_protocol is immutable'); END;
CREATE TRIGGER IF NOT EXISTS validation_protocol_no_delete
BEFORE DELETE ON validation_protocol BEGIN SELECT RAISE(ABORT, 'validation_protocol is immutable'); END;
CREATE TRIGGER IF NOT EXISTS validation_run_no_update
BEFORE UPDATE ON validation_run BEGIN SELECT RAISE(ABORT, 'validation_run is append-only'); END;
CREATE TRIGGER IF NOT EXISTS validation_run_no_delete
BEFORE DELETE ON validation_run BEGIN SELECT RAISE(ABORT, 'validation_run is append-only'); END;
"""


class ApexDatabase:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection:
            with connection:
                connection.executescript(SCHEMA)
                connection.execute(
                    "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('schema_version', ?)",
                    (str(SCHEMA_VERSION),),
                )

    def record_gate(self, gate: GateEnvelope) -> int:
        payload = gate.to_dict()
        with closing(self.connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO gate_event(gate_id, module_id, run_id, status, summary, payload_json, created_at)
                    VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gate.gate_id,
                        gate.module_id,
                        gate.run_id,
                        gate.status.value,
                        gate.summary,
                        json.dumps(payload, ensure_ascii=False, sort_keys=True),
                        gate.created_at,
                    ),
                )
                return int(cursor.lastrowid)

    def define_coefficient(
        self,
        coefficient_id: str,
        name: str,
        unit: str,
        module_id: str,
        description: str,
        *,
        symbol: str | None = None,
        status: str = "HYPOTHESIS",
    ) -> None:
        allowed = {"HYPOTHESIS", "CALIBRATING", "VALIDATED", "REJECTED"}
        if status not in allowed:
            raise ValueError(f"status inválido: {status}")
        required = (coefficient_id, name, unit, module_id, description)
        if not all(value.strip() for value in required):
            raise ValueError("Os campos obrigatórios do coeficiente não podem ser vazios")
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO coefficient_definition(
                        coefficient_id, name, symbol, unit, module_id, description, status
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (coefficient_id, name, symbol, unit, module_id, description, status),
                )

    def record_coefficient_estimate(
        self,
        coefficient_id: str,
        run_id: str,
        value: float,
        method: str,
        dataset_sha256: str,
        *,
        uncertainty: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        if not math.isfinite(value):
            raise ValueError("value deve ser finito")
        if uncertainty is not None and (not math.isfinite(uncertainty) or uncertainty < 0):
            raise ValueError("uncertainty deve ser finita e não negativa")
        if not run_id.strip() or not method.strip() or not dataset_sha256.strip():
            raise ValueError("run_id, method e dataset_sha256 são obrigatórios")
        with closing(self.connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    INSERT INTO coefficient_estimate(
                        coefficient_id, run_id, value, uncertainty, method,
                        dataset_sha256, metadata_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        coefficient_id,
                        run_id,
                        value,
                        uncertainty,
                        method,
                        dataset_sha256,
                        json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True),
                    ),
                )
                return int(cursor.lastrowid)

    def record_snapshot(self, snapshot: "SourceSnapshot") -> None:
        manifest = snapshot.to_dict()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO source(
                        source_id, name, uri, license, version, retrieved_at, sha256, metadata_json
                    ) VALUES(?, ?, ?, ?, ?, ?, NULL, ?)
                    """,
                    (
                        snapshot.source.source_id,
                        snapshot.source.name,
                        snapshot.source.uri,
                        snapshot.source.license_name,
                        snapshot.source.version,
                        now,
                        json.dumps(
                            {
                                "license_class": snapshot.source.license_class.value,
                                "redistribution_allowed": snapshot.source.redistribution_allowed,
                            },
                            sort_keys=True,
                        ),
                    ),
                )
                connection.execute(
                    """
                    INSERT INTO source_snapshot(
                        snapshot_id, source_id, source_version, license_name, license_class,
                        retrieved_at, status, query_json, manifest_json
                    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snapshot.snapshot_id,
                        snapshot.source.source_id,
                        snapshot.source.version,
                        snapshot.source.license_name,
                        snapshot.source.license_class.value,
                        snapshot.retrieved_at,
                        snapshot.status,
                        json.dumps(dict(snapshot.query), ensure_ascii=False, sort_keys=True),
                        json.dumps(manifest, ensure_ascii=False, sort_keys=True),
                    ),
                )
                connection.executemany(
                    """
                    INSERT INTO snapshot_file(
                        snapshot_id, sha256, original_name, original_path, size_bytes, stored_locator
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            snapshot.snapshot_id,
                            item.sha256,
                            item.original_name,
                            item.original_path,
                            item.size_bytes,
                            item.stored_locator,
                        )
                        for item in snapshot.files
                    ],
                )

    def record_split(self, split: "FrozenSplit") -> None:
        definition = {
            "split_id": split.split_id,
            "dataset_snapshot_id": split.dataset_snapshot_id,
            "partitions": {
                partition.value: list(members) for partition, members in split.partitions.items()
            },
            "groups": dict(split.groups),
            "external_set_locked": split.external_set_locked,
            "strategy": split.strategy,
        }
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT INTO benchmark_split(
                        split_id, dataset_snapshot_id, definition_sha256,
                        external_set_locked, strategy, definition_json
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        split.split_id,
                        split.dataset_snapshot_id,
                        split.definition_sha256(),
                        int(split.external_set_locked),
                        split.strategy,
                        json.dumps(definition, ensure_ascii=False, sort_keys=True),
                    ),
                )

    def record_validation_outcome(self, outcome: "ValidationOutcome") -> int:
        protocol = outcome.protocol
        with closing(self.connect()) as connection:
            with connection:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO validation_protocol(
                        protocol_id, version, module_id, evidence_layer, protocol_json
                    ) VALUES(?, ?, ?, ?, ?)
                    """,
                    (
                        protocol.protocol_id,
                        protocol.version,
                        protocol.module_id,
                        protocol.layer.value,
                        json.dumps(protocol.to_dict(), ensure_ascii=False, sort_keys=True),
                    ),
                )
                cursor = connection.execute(
                    """
                    INSERT INTO validation_run(
                        protocol_id, protocol_version, run_id, gate_status,
                        candidate_evidence_label, outcome_json
                    ) VALUES(?, ?, ?, ?, ?, ?)
                    """,
                    (
                        protocol.protocol_id,
                        protocol.version,
                        outcome.gate.run_id,
                        outcome.gate.status.value,
                        outcome.candidate_evidence_label,
                        json.dumps(
                            {
                                "gate": outcome.gate.to_dict(),
                                "criterion_results": dict(outcome.criterion_results),
                            },
                            ensure_ascii=False,
                            sort_keys=True,
                        ),
                    ),
                )
                return int(cursor.lastrowid)

    def list_gate_events(self, run_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM gate_event"
        params: tuple[Any, ...] = ()
        if run_id is not None:
            query += " WHERE run_id = ?"
            params = (run_id,)
        query += " ORDER BY event_id"
        with closing(self.connect()) as connection:
            return [dict(row) for row in connection.execute(query, params).fetchall()]
