"""
UCO-Sensor API — SnapshotStore
================================
Camada de persistência SQLite para snapshots UCO.

Funcionalidades:
  insert(mv)                         — upsert MetricVector por (module_id, commit_hash)
  get_history(module_id, window)     — histórico cronológico de snapshots
  get_baseline(module_id, window)    — estatísticas de baseline + z-score
  insert_anomaly(event_id, mod, data)— persiste evento de anomalia
  get_anomalies(module_id)           — lista anomalias detectadas
  list_modules()                     — lista todos os módulos conhecidos

  Auth + Billing:
  create_key(name, quota)            — cria API key e retorna chave plain-text
  validate_key(plain_key)            — valida + incrementa uso; retorna dict ou None
  get_usage(key_prefix)              — retorna uso corrente de uma chave
  list_keys()                        — lista chaves (sem revelar hash)
  revoke_key(key_prefix)             — revoga API key

Design:
  SQLite em arquivo ou ":memory:" — adequado para testes e uso local.
  Schema imutável (não usa ALTER TABLE) — compatível com SQLite < 3.37.
  Thread-safe via lock explícito (para uso em servidor multi-thread).
  Upsert via INSERT OR REPLACE com chave (module_id, commit_hash).

BaselineStats:
  Objeto calculado on-the-fly a partir do histórico.
  Campos: n_samples, h_mean, h_std, h_trend_slope, + métodos z_score().
  Requer ≥ 3 amostras para ser válido (retorna None abaixo disso).
"""
from __future__ import annotations
import sqlite3
import json
import math
import time
import threading
import statistics
import secrets
import hashlib
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent.parent / "frequency-engine"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from core.data_structures import MetricVector


# ─── Schema SQLite ───────────────────────────────────────────────────────────

_DDL_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS snapshots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id       TEXT    NOT NULL,
    commit_hash     TEXT    NOT NULL,
    timestamp       REAL    NOT NULL,
    hamiltonian     REAL    NOT NULL DEFAULT 0.0,
    cyclomatic_complexity INTEGER NOT NULL DEFAULT 1,
    infinite_loop_risk    REAL NOT NULL DEFAULT 0.0,
    dsm_density     REAL    NOT NULL DEFAULT 0.0,
    dsm_cyclic_ratio REAL   NOT NULL DEFAULT 0.0,
    dependency_instability REAL NOT NULL DEFAULT 0.0,
    syntactic_dead_code    INTEGER NOT NULL DEFAULT 0,
    duplicate_block_count  INTEGER NOT NULL DEFAULT 0,
    halstead_bugs          REAL    NOT NULL DEFAULT 0.0,
    language        TEXT    NOT NULL DEFAULT 'python',
    lines_of_code   INTEGER NOT NULL DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'STABLE',
    n_functions     INTEGER NOT NULL DEFAULT 0,
    n_classes       INTEGER NOT NULL DEFAULT 0,
    max_methods_per_class INTEGER NOT NULL DEFAULT 0,
    cc_hotspot_ratio REAL   NOT NULL DEFAULT 0.0,
    max_function_cc  INTEGER NOT NULL DEFAULT 0,
    extended_vectors_json    TEXT DEFAULT NULL,
    advanced_vector_json     TEXT DEFAULT NULL,
    diagnostic_vector_json   TEXT DEFAULT NULL,
    extended_vectors_v2_json TEXT DEFAULT NULL,
    aps_score                REAL DEFAULT NULL,
    predictor_hurst          REAL DEFAULT NULL,
    predictor_slope_pct      REAL DEFAULT NULL,
    predictor_forecast_next  REAL DEFAULT NULL,
    predictor_confidence     REAL DEFAULT NULL,
    UNIQUE(module_id, commit_hash)
);
"""

# M7.0 — Column migration for databases created before this schema version.
# Uses try/except because SQLite does not support IF NOT EXISTS on ADD COLUMN
# before version 3.37 (2021-11-27).  The except branch is intentionally silent
# — the column simply already exists.
#
# LEAP 1 (Persistence Sprint) appends ``extended_vectors_v2_json`` carrying
# nine vectors previously DROPPED on every scan: security, velocity, flow,
# reliability, maintainability, performance, architecture, test_quality,
# thread_safety.  Backward-compat: DEFAULT NULL — old rows load with each
# vector = None, identical to today's behaviour.
#
# LEAP 2 (APS as a persisted signal) appends ``aps_score`` REAL.  Computed at
# insert time via metrics.anti_pattern_score.aps_from_metric_vector when the
# extended vectors are attached; otherwise stays NULL.  Old rows: NULL ⇒
# /anti-pattern-score/history treats them as missing samples.
_M70_MIGRATION_COLUMNS = [
    ("extended_vectors_json",     "TEXT DEFAULT NULL"),
    ("advanced_vector_json",      "TEXT DEFAULT NULL"),
    ("diagnostic_vector_json",    "TEXT DEFAULT NULL"),
    ("extended_vectors_v2_json",  "TEXT DEFAULT NULL"),   # LEAP 1
    ("aps_score",                 "REAL DEFAULT NULL"),   # LEAP 2
    # LEAP 4 — Predictor/Trend persisted at insert time.  Each snapshot
    # carries the forecast the DegradationPredictor produced from history
    # PRIOR to its own write — enabling later forecast-accuracy analysis
    # (predicted_next at row[t] vs actual hamiltonian at row[t+1]).
    ("predictor_hurst",           "REAL DEFAULT NULL"),
    ("predictor_slope_pct",       "REAL DEFAULT NULL"),
    ("predictor_forecast_next",   "REAL DEFAULT NULL"),
    ("predictor_confidence",      "REAL DEFAULT NULL"),
]

_DDL_ANOMALIES = """
CREATE TABLE IF NOT EXISTS anomalies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    TEXT    NOT NULL UNIQUE,
    module_id   TEXT    NOT NULL,
    error_type  TEXT    NOT NULL,
    severity    TEXT    NOT NULL,
    confidence  REAL    NOT NULL DEFAULT 0.0,
    band        TEXT    NOT NULL DEFAULT '',
    plain_text  TEXT    NOT NULL DEFAULT '',
    tech_summary TEXT   NOT NULL DEFAULT '',
    apex_prompt TEXT    NOT NULL DEFAULT '',
    change_point_idx  INTEGER,
    change_point_hash TEXT,
    created_at  REAL    NOT NULL,
    raw_json    TEXT    NOT NULL DEFAULT '{}'
);
"""

_IDX_SNAPSHOTS = """
CREATE INDEX IF NOT EXISTS idx_snap_module_ts
ON snapshots(module_id, timestamp);
"""

_IDX_ANOMALIES = """
CREATE INDEX IF NOT EXISTS idx_anom_module
ON anomalies(module_id);
"""

_DDL_API_KEYS = """
CREATE TABLE IF NOT EXISTS api_keys (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key_prefix  TEXT    NOT NULL UNIQUE,   -- primeiros 8 chars (uco_XXXX) — display safe
    key_hash    TEXT    NOT NULL UNIQUE,   -- SHA-256 da chave completa
    name        TEXT    NOT NULL DEFAULT '',
    quota_day   INTEGER NOT NULL DEFAULT 0,    -- 0 = ilimitado
    calls_today INTEGER NOT NULL DEFAULT 0,
    calls_total INTEGER NOT NULL DEFAULT 0,
    last_reset  REAL    NOT NULL DEFAULT 0.0,  -- timestamp do último reset diário
    active      INTEGER NOT NULL DEFAULT 1,    -- 1=ativo, 0=revogado
    created_at  REAL    NOT NULL
);
"""

_IDX_API_KEYS = """
CREATE INDEX IF NOT EXISTS idx_api_key_hash
ON api_keys(key_hash);
"""

# Sprint C — Auto-fix telemetry.  Each row is one auto_remediate() call:
# the outcome of attempting to fix SAST findings via mapped transforms.
# Closes the LEAP 3 loop by letting callers ask "is auto-remediation
# actually working over time? which rules get fixed most? which leave
# residuals?" — without recomputing anything.
_DDL_REMEDIATIONS = """
CREATE TABLE IF NOT EXISTS remediations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id            TEXT    NOT NULL,
    commit_hash          TEXT    NOT NULL DEFAULT '',
    timestamp            REAL    NOT NULL,
    is_valid             INTEGER NOT NULL DEFAULT 1,
    findings_before      INTEGER NOT NULL DEFAULT 0,
    findings_after       INTEGER NOT NULL DEFAULT 0,
    fixed_count          INTEGER NOT NULL DEFAULT 0,
    residual_count       INTEGER NOT NULL DEFAULT 0,
    transforms_json      TEXT    NOT NULL DEFAULT '[]',
    fixed_rules_json     TEXT    NOT NULL DEFAULT '[]',
    findings_before_json TEXT    NOT NULL DEFAULT '[]',
    findings_after_json  TEXT    NOT NULL DEFAULT '[]'
);
"""

_IDX_REMEDIATIONS = """
CREATE INDEX IF NOT EXISTS idx_remed_module_ts
ON remediations(module_id, timestamp);
"""

# Sprint P — discovered signatures persistence.  Each row is one
# DBSCAN cluster found over the spectral fingerprints (Sprint O).
# signature_id is a stable hash of the centroid → re-running discover()
# on a re-evolved repo bumps occurrence_count instead of duplicating.
_DDL_SIGNATURES = """
CREATE TABLE IF NOT EXISTS discovered_signatures (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    signature_id       TEXT    NOT NULL UNIQUE,
    created_at         REAL    NOT NULL,
    last_seen_at       REAL    NOT NULL,
    occurrence_count   INTEGER NOT NULL DEFAULT 1,
    n_members          INTEGER NOT NULL DEFAULT 0,
    diameter           REAL    NOT NULL DEFAULT 0.0,
    centroid_json      TEXT    NOT NULL DEFAULT '[]',
    members_json       TEXT    NOT NULL DEFAULT '[]',
    label              TEXT    NOT NULL DEFAULT '',
    notes              TEXT    NOT NULL DEFAULT ''
);
"""

_IDX_SIGNATURES = """
CREATE INDEX IF NOT EXISTS idx_sig_signature_id
ON discovered_signatures(signature_id);
"""


# ─── BaselineStats ───────────────────────────────────────────────────────────

@dataclass
class BaselineStats:
    """
    Estatísticas de baseline computadas sobre janela de histórico.

    Usadas para z-score normalizado e detecção de desvio.

    Campos
    ------
    n_samples      : número de snapshots na janela
    h_mean         : média de H na janela
    h_std          : desvio padrão de H
    h_trend_slope  : tendência linear de H (Δ H por snapshot)
    cc_mean        : média de CC
    cc_std         : desvio padrão de CC
    di_mean        : média de DI
    di_std         : desvio padrão de DI
    dead_mean      : média de dead code count
    dead_std       : desvio padrão de dead code
    """
    n_samples:      int
    h_mean:         float
    h_std:          float
    h_trend_slope:  float
    cc_mean:        float
    cc_std:         float
    di_mean:        float
    di_std:         float
    dead_mean:      float
    dead_std:       float

    # Métricas adicionais para uso interno
    _channel_means: Dict[str, float] = None  # type: ignore
    _channel_stds:  Dict[str, float] = None  # type: ignore

    def z_score(self, channel: str, value: float) -> float:
        """
        Calcula z-score de um valor no canal dado.

        z = (x - μ) / σ

        Parâmetros
        ----------
        channel : "H" | "CC" | "DI" | "dead" | "dups" | "ILR" | "bugs" | "DSM_d" | "DSM_c"
        value   : valor a normalizar

        Retorna
        -------
        float — z-score (0 = na média, 1 = 1 desvio-padrão acima, etc.)
        """
        _MAP = {
            "H":     (self.h_mean,    self.h_std),
            "CC":    (self.cc_mean,   self.cc_std),
            "DI":    (self.di_mean,   self.di_std),
            "dead":  (self.dead_mean, self.dead_std),
        }
        # Fallback para channel_means/_stds se disponível
        if channel in _MAP:
            mu, sigma = _MAP[channel]
        elif self._channel_means and channel in self._channel_means:
            mu    = self._channel_means[channel]
            sigma = (self._channel_stds or {}).get(channel, 1.0)
        else:
            return 0.0

        if sigma < 1e-9:
            return 0.0 if abs(value - mu) < 1e-9 else float("inf")

        return (value - mu) / sigma


# ─── SnapshotStore ────────────────────────────────────────────────────────────

class SnapshotStore:
    """
    Armazena e recupera snapshots UCO via SQLite.

    Parâmetros
    ----------
    db_path : caminho para o arquivo SQLite, ou ":memory:" para em-memória.
              ":memory:" é ideal para testes (banco descartado ao destruir objeto).
    """

    def __init__(self, db_path: str = ":memory:"):
        self.db_path   = db_path
        self._lock     = threading.Lock()
        self._in_memory = (db_path == ":memory:")

        if self._in_memory:
            # ":memory:" databases MUST share a single connection — per-thread
            # connections would create independent empty databases.
            # Protect with Lock throughout (already done for every operation).
            self._shared_conn = sqlite3.connect(
                db_path,
                check_same_thread=False,
                isolation_level=None,  # autocommit
            )
            self._shared_conn.execute("PRAGMA journal_mode=WAL")
            self._shared_conn.execute("PRAGMA synchronous=NORMAL")
        else:
            # BUG-04: file databases use per-thread connections via threading.local()
            # to avoid cross-thread SQLite cursor issues even with WAL + Lock.
            self._local = threading.local()

        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        """Returns the appropriate SQLite connection for the current thread."""
        if self._in_memory:
            return self._shared_conn
        # Per-thread connection: created on first access for this thread
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=True,   # safe: this conn is thread-local
                isolation_level=None,     # autocommit
            )
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

    # ─── Schema ──────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._get_conn().cursor()
            cur.execute(_DDL_SNAPSHOTS)
            cur.execute(_DDL_ANOMALIES)
            cur.execute(_DDL_API_KEYS)
            cur.execute(_DDL_REMEDIATIONS)        # Sprint C
            cur.execute(_DDL_SIGNATURES)          # Sprint P
            cur.execute(_IDX_SNAPSHOTS)
            cur.execute(_IDX_ANOMALIES)
            cur.execute(_IDX_API_KEYS)
            cur.execute(_IDX_REMEDIATIONS)        # Sprint C
            cur.execute(_IDX_SIGNATURES)          # Sprint P
            # M7.0: add extended-vector columns to pre-existing databases
            self._migrate_m70(cur)

    def _migrate_m70(self, cur: sqlite3.Cursor) -> None:
        """
        Idempotent migration: add M7.0 JSON columns to the snapshots table.

        Safe to call on both new (columns already in DDL) and old databases
        (columns added here).  sqlite3.OperationalError is suppressed because
        it signals that the column already exists — not a real error.
        """
        for col_name, col_def in _M70_MIGRATION_COLUMNS:
            try:
                cur.execute(
                    f"ALTER TABLE snapshots ADD COLUMN {col_name} {col_def}"
                )
            except Exception:
                pass   # column already exists — not an error

    # ─── Insert ──────────────────────────────────────────────────────────────

    def insert(self, mv: MetricVector, *, defer_derived: bool = False) -> None:
        """
        Upsert MetricVector.

        Idempotente: inserir (module_id, commit_hash) já existente
        atualiza os campos — não duplica o registro.

        M7.0: serializes AdvancedVector + Halstead/StructuralVector JSON blobs
        into the three new extended-vector columns when present on the mv.

        Sprint I — ``defer_derived`` (default False) controls whether the
        cost of computing APS + Predictor forecast happens inline (the
        previous behavior, "compute on write") or is **skipped** so that
        the hot insert path stays cheap.  When deferred, the derived
        columns are written as NULL and ``recompute_derived(module_id,
        commit_hash)`` (or batch helper ``recompute_derived_pending()``)
        must be called later to populate them.  Designed for batch-scan
        use cases (ingesting a full repo) where ``compute APS + forecast
        on every row`` adds ~O(window)·log(window) per insert.
        """
        # ── M7.0 + LEAP 1 + LEAP 2 + LEAP 4: serialize extras + APS + forecast
        extended_json     = self._serialize_extended(mv)
        advanced_json     = self._serialize_advanced(mv)
        diagnostic_json   = self._serialize_diagnostic(mv)
        extended_v2_json  = self._serialize_extended_v2(mv)   # LEAP 1

        if defer_derived:
            # Sprint I — hot path: skip the heavy work.
            aps_score = None
            p_hurst = p_slope_pct = p_forecast_next = p_confidence = None
        else:
            aps_score = self._compute_aps_score(mv)           # LEAP 2
            forecast  = self._compute_forecast(mv)            # LEAP 4
            (p_hurst, p_slope_pct, p_forecast_next, p_confidence) = forecast

        # Sprint G fix (C-4): INSERT OR REPLACE used to delete+reinsert the row,
        # silently wiping any value populated AFTER the original insert (notably
        # diagnostic_vector_json set by update_diagnostic).  We now do an upsert
        # via ON CONFLICT DO UPDATE and COALESCE the late-populated columns —
        # if the new payload is NULL, keep what we already had.  Requires
        # SQLite ≥ 3.24 (2018-06).
        sql = """
        INSERT INTO snapshots (
            module_id, commit_hash, timestamp,
            hamiltonian, cyclomatic_complexity, infinite_loop_risk,
            dsm_density, dsm_cyclic_ratio, dependency_instability,
            syntactic_dead_code, duplicate_block_count, halstead_bugs,
            language, lines_of_code, status,
            n_functions, n_classes, max_methods_per_class,
            cc_hotspot_ratio, max_function_cc,
            extended_vectors_json, advanced_vector_json, diagnostic_vector_json,
            extended_vectors_v2_json, aps_score,
            predictor_hurst, predictor_slope_pct,
            predictor_forecast_next, predictor_confidence
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(module_id, commit_hash) DO UPDATE SET
            timestamp              = excluded.timestamp,
            hamiltonian            = excluded.hamiltonian,
            cyclomatic_complexity  = excluded.cyclomatic_complexity,
            infinite_loop_risk     = excluded.infinite_loop_risk,
            dsm_density            = excluded.dsm_density,
            dsm_cyclic_ratio       = excluded.dsm_cyclic_ratio,
            dependency_instability = excluded.dependency_instability,
            syntactic_dead_code    = excluded.syntactic_dead_code,
            duplicate_block_count  = excluded.duplicate_block_count,
            halstead_bugs          = excluded.halstead_bugs,
            language               = excluded.language,
            lines_of_code          = excluded.lines_of_code,
            status                 = excluded.status,
            n_functions            = excluded.n_functions,
            n_classes              = excluded.n_classes,
            max_methods_per_class  = excluded.max_methods_per_class,
            cc_hotspot_ratio       = excluded.cc_hotspot_ratio,
            max_function_cc        = excluded.max_function_cc,
            extended_vectors_json    = COALESCE(excluded.extended_vectors_json,    extended_vectors_json),
            advanced_vector_json     = COALESCE(excluded.advanced_vector_json,     advanced_vector_json),
            diagnostic_vector_json   = COALESCE(excluded.diagnostic_vector_json,   diagnostic_vector_json),
            extended_vectors_v2_json = COALESCE(excluded.extended_vectors_v2_json, extended_vectors_v2_json),
            aps_score                = COALESCE(excluded.aps_score,                aps_score),
            predictor_hurst          = COALESCE(excluded.predictor_hurst,          predictor_hurst),
            predictor_slope_pct      = COALESCE(excluded.predictor_slope_pct,      predictor_slope_pct),
            predictor_forecast_next  = COALESCE(excluded.predictor_forecast_next,  predictor_forecast_next),
            predictor_confidence     = COALESCE(excluded.predictor_confidence,     predictor_confidence)
        """
        values = (
            mv.module_id,
            mv.commit_hash,
            mv.timestamp,
            float(mv.hamiltonian),
            int(mv.cyclomatic_complexity),
            float(mv.infinite_loop_risk),
            float(mv.dsm_density),
            float(mv.dsm_cyclic_ratio),
            float(mv.dependency_instability),
            int(mv.syntactic_dead_code),
            int(mv.duplicate_block_count),
            float(mv.halstead_bugs),
            getattr(mv, "language", "python"),
            getattr(mv, "lines_of_code", 0),
            getattr(mv, "status", "STABLE"),
            getattr(mv, "n_functions", 0),
            getattr(mv, "n_classes", 0),
            getattr(mv, "max_methods_per_class", 0),
            float(getattr(mv, "cc_hotspot_ratio", 0.0)),
            int(getattr(mv, "max_function_cc", 0)),
            extended_json,
            advanced_json,
            diagnostic_json,
            extended_v2_json,   # LEAP 1
            aps_score,          # LEAP 2
            p_hurst,            # LEAP 4
            p_slope_pct,        # LEAP 4
            p_forecast_next,    # LEAP 4
            p_confidence,       # LEAP 4
        )
        with self._lock:
            self._get_conn().execute(sql, values)

    # ── M7.0: update diagnostic_vector after FrequencyEngine classification ──

    def update_diagnostic(self, module_id: str, commit_hash: str,
                          diagnostic_json: str) -> None:
        """
        Update the diagnostic_vector_json column for the given snapshot.

        Called from the API server after FrequencyEngine.analyze() produces a
        ClassificationResult (requires ≥5 snapshots — cannot be set at insert time).
        """
        sql = """
        UPDATE snapshots
        SET diagnostic_vector_json = ?
        WHERE module_id = ? AND commit_hash = ?
        """
        with self._lock:
            self._get_conn().execute(sql, (diagnostic_json, module_id, commit_hash))

    # ── Sprint I — deferred APS/forecast computation ─────────────────────────

    def recompute_derived(self, module_id: str, commit_hash: str) -> bool:
        """
        Recompute APS + Predictor forecast for a single (module, commit) row
        and persist them.  Returns True when the row exists and was updated;
        False when it doesn't.

        Used after a bulk ingest with ``insert(mv, defer_derived=True)`` to
        backfill the derived columns at a quieter moment.
        """
        with self._lock:
            row = self._get_conn().execute(
                "SELECT 1 FROM snapshots WHERE module_id=? AND commit_hash=?",
                (module_id, commit_hash),
            ).fetchone()
        if not row:
            return False

        history = self.get_history(module_id, window=100)
        target = next((mv for mv in history if mv.commit_hash == commit_hash), None)
        if target is None:
            return False

        aps_score = self._compute_aps_score(target)
        forecast  = self._compute_forecast(target)
        (p_hurst, p_slope_pct, p_forecast_next, p_confidence) = forecast

        sql = """
        UPDATE snapshots
        SET aps_score                = ?,
            predictor_hurst          = ?,
            predictor_slope_pct      = ?,
            predictor_forecast_next  = ?,
            predictor_confidence     = ?
        WHERE module_id = ? AND commit_hash = ?
        """
        with self._lock:
            self._get_conn().execute(sql, (
                aps_score, p_hurst, p_slope_pct,
                p_forecast_next, p_confidence,
                module_id, commit_hash,
            ))
        return True

    def recompute_derived_pending(self, module_id: Optional[str] = None,
                                  batch_limit: int = 1000) -> int:
        """
        Bulk-backfill APS + forecast for rows where ``aps_score IS NULL``.
        Scope optionally narrowed to a single module.  Returns the number
        of rows actually updated.

        Safe to interrupt: each row is its own transaction.  Idempotent:
        rows already populated are skipped by the WHERE clause.
        """
        params: tuple = ()
        where = " WHERE aps_score IS NULL"
        if module_id is not None:
            where += " AND module_id = ?"
            params = (module_id,)
        sql = (
            f"SELECT module_id, commit_hash FROM snapshots{where} "
            f"ORDER BY timestamp ASC, id ASC LIMIT {int(batch_limit)}"
        )
        with self._lock:
            pending = self._get_conn().execute(sql, params).fetchall()

        n_updated = 0
        for mid, sha in pending:
            if self.recompute_derived(mid, sha):
                n_updated += 1
        return n_updated

    # ── Sprint I — single-query "latest APS per module" ──────────────────────

    def latest_aps_per_module(self) -> List[Dict[str, Any]]:
        """
        Return ``[{module_id, aps, loc, timestamp}, ...]`` for every module
        whose latest snapshot has a non-NULL APS — computed in a SINGLE SQL
        query with a self-join on (module_id, MAX(timestamp)).

        Replaces the N+1 Python loop in ``governance/repo_meta_score.py``:
        previously one ``list_modules()`` plus one ``get_aps_history(...)``
        plus one ``get_history(..., window=1)`` per module.  On a repo with
        500 modules and 100 snapshots each that was 1000+ queries.
        Now it's 1.
        """
        sql = """
        SELECT s.module_id,
               s.aps_score,
               s.lines_of_code,
               s.timestamp
        FROM snapshots s
        INNER JOIN (
            SELECT module_id, MAX(timestamp) AS max_ts
            FROM snapshots
            WHERE aps_score IS NOT NULL
            GROUP BY module_id
        ) latest
          ON s.module_id = latest.module_id
         AND s.timestamp = latest.max_ts
        WHERE s.aps_score IS NOT NULL
        ORDER BY s.module_id ASC
        """
        with self._lock:
            rows = self._get_conn().execute(sql).fetchall()
        return [
            {"module_id": r[0],
             "aps":       float(r[1]),
             "loc":       int(r[2] or 0),
             "timestamp": float(r[3])}
            for r in rows
        ]

    # ── M7.0: serialization helpers ──────────────────────────────────────────

    @staticmethod
    def _serialize_extended(mv: Any) -> Optional[str]:
        """JSON-serialize HalsteadVector + StructuralVector (M6.4) if present."""
        halstead  = getattr(mv, "halstead",  None)
        structural = getattr(mv, "structural", None)
        if halstead is None and structural is None:
            return None
        d: Dict[str, Any] = {}
        if halstead is not None:
            try:
                d["halstead"] = halstead.to_dict()
            except Exception:
                pass
        if structural is not None:
            try:
                d["structural"] = structural.to_dict()
            except Exception:
                pass
        return json.dumps(d, default=str) if d else None

    @staticmethod
    def _serialize_advanced(mv: Any) -> Optional[str]:
        """JSON-serialize AdvancedVector (M7.0) if present."""
        advanced = getattr(mv, "advanced", None)
        if advanced is None:
            return None
        try:
            return json.dumps(advanced.to_dict(), default=str)
        except Exception:
            return None

    @staticmethod
    def _serialize_diagnostic(mv: Any) -> Optional[str]:
        """JSON-serialize DiagnosticVector (M7.0) if present."""
        diagnostic = getattr(mv, "diagnostic", None)
        if diagnostic is None:
            return None
        try:
            return json.dumps(diagnostic.to_dict(), default=str)
        except Exception:
            return None

    # ── LEAP 1 — Persistence Sprint ───────────────────────────────────────────
    # The nine vectors below were attached to ``mv`` since M7.2-M7.7 but
    # dropped on every scan because the SnapshotStore never knew about them.
    # We pack them into one JSON object keyed by attribute name.  Missing
    # vectors (e.g. non-Python language) are skipped — round-trip preserves
    # exactly the keys that were present at insert time.
    _EXTENDED_V2_ATTRS: tuple = (
        "security",
        "velocity",
        "flow",
        "reliability",
        "maintainability",
        "performance",
        "architecture",
        "test_quality",
        "thread_safety",
    )

    # ── LEAP 2 — APS persisted at insert time ─────────────────────────────────
    # We compute APS ONCE at insert so subsequent /aps/history queries do not
    # depend on having every extended vector still attached (defense-in-depth
    # against extended_vectors_v2_json being silently lost via migration).
    @staticmethod
    def _compute_aps_score(mv: Any) -> Optional[float]:
        """
        Compute the Anti-Pattern Score for *mv* (0–100, higher = better).

        Returns ``None`` (column stays NULL) when no APS-contributing signal
        is attached — which is identical to today's "old row" semantics.
        Any failure in the APS engine is swallowed so persistence cannot
        fail because of a metrics-module issue.
        """
        try:
            from metrics.anti_pattern_score import aps_from_metric_vector
        except Exception:
            return None
        try:
            result = aps_from_metric_vector(mv)
            raw = result.get("aps") if isinstance(result, dict) else None
            if raw is None:
                return None
            return float(raw)
        except Exception:
            return None

    # ── LEAP 4 — Predictor/Trend persisted at insert time ─────────────────────
    # We run the DegradationPredictor on the history PRIOR to the row being
    # written.  Each snapshot stores what the predictor knew at the time of
    # its own write — enabling later forecast-accuracy analysis (predicted
    # at row[t] vs actual hamiltonian at row[t+1]).
    def _compute_forecast(self, mv: Any) -> Tuple[
        Optional[float], Optional[float], Optional[float], Optional[float]
    ]:
        """
        Run the DegradationPredictor on the history strictly PRIOR to ``mv``.

        Returns
        -------
        (hurst, slope_pct, forecast_next, confidence) — all Optional[float].
        Any failure (insufficient history, predictor import error, …) yields
        ``(None, None, None, None)`` so the snapshot still writes.
        """
        try:
            from sensor_core.predictor import DegradationPredictor
        except Exception:
            return (None, None, None, None)
        try:
            module_id = getattr(mv, "module_id", None)
            if not module_id:
                return (None, None, None, None)
            # Look at the history WITHOUT the row we're about to write.
            history = self.get_history(module_id, window=100)
            if len(history) < 4:
                return (None, None, None, None)
            forecast = DegradationPredictor().predict(history, module_id=module_id)
            return (
                float(forecast.hurst_exponent),
                float(forecast.slope_pct),
                float(getattr(forecast, "predicted_h", 0.0) or 0.0),
                float(forecast.confidence),
            )
        except Exception:
            return (None, None, None, None)

    @classmethod
    def _serialize_extended_v2(cls, mv: Any) -> Optional[str]:
        """
        JSON-serialize the nine LEAP-1 extended vectors that are present on *mv*.

        Returns
        -------
        Optional[str]
            JSON object string keyed by attribute name, or ``None`` if no
            LEAP-1 vector is attached (so the column stays NULL).
        """
        payload: Dict[str, Any] = {}
        for attr in cls._EXTENDED_V2_ATTRS:
            vec = getattr(mv, attr, None)
            if vec is None:
                continue
            try:
                payload[attr] = vec.to_dict()
            except Exception:
                # A single bad vector must NOT block persistence of the others.
                continue
        if not payload:
            return None
        try:
            return json.dumps(payload, default=str)
        except Exception:
            return None

    # ─── Get history ─────────────────────────────────────────────────────────

    def get_history(
        self,
        module_id: str,
        window: int = 100,
    ) -> List[MetricVector]:
        """
        Retorna histórico de snapshots em ordem cronológica (mais antigo primeiro).

        Parâmetros
        ----------
        module_id : identificador do módulo
        window    : máximo de snapshots a retornar (os N mais recentes)

        Retorna
        -------
        List[MetricVector] ordenado por timestamp ASC.
        """
        sql = """
        SELECT
            module_id, commit_hash, timestamp,
            hamiltonian, cyclomatic_complexity, infinite_loop_risk,
            dsm_density, dsm_cyclic_ratio, dependency_instability,
            syntactic_dead_code, duplicate_block_count, halstead_bugs,
            language, lines_of_code, status,
            n_functions, n_classes, max_methods_per_class,
            cc_hotspot_ratio, max_function_cc,
            extended_vectors_json, advanced_vector_json, diagnostic_vector_json,
            extended_vectors_v2_json, aps_score,
            predictor_hurst, predictor_slope_pct,
            predictor_forecast_next, predictor_confidence
        FROM snapshots
        WHERE module_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """
        with self._lock:
            rows = self._get_conn().execute(sql, (module_id, window)).fetchall()

        # Reverter para ordem ASC (mais antigo primeiro — correto para FrequencyEngine)
        rows = list(reversed(rows))
        return [self._row_to_mv(r) for r in rows]

    # ── LEAP 2 — APS time-series helper ──────────────────────────────────────

    def get_aps_history(
        self,
        module_id: str,
        window: int = 100,
    ) -> List[Tuple[str, float, Optional[float]]]:
        """
        Return ``(commit_hash, timestamp, aps_score)`` tuples for a module,
        ordered chronologically ascending.  Rows predating LEAP 2 carry
        ``aps_score = None`` — callers should filter those out before
        running OLS / Hurst on the series.

        Cheaper than ``get_history`` (skips all the JSON deserialization),
        designed for the ``/anti-pattern-score/history`` and ``/trend``
        endpoints that only need the score time-series.
        """
        sql = """
        SELECT commit_hash, timestamp, aps_score
        FROM snapshots
        WHERE module_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """
        with self._lock:
            rows = self._get_conn().execute(sql, (module_id, window)).fetchall()
        rows = list(reversed(rows))
        return [
            (str(r[0]), float(r[1]),
             float(r[2]) if r[2] is not None else None)
            for r in rows
        ]

    # ── LEAP 4 — Predictor time-series helper ────────────────────────────────

    def get_predictor_history(
        self,
        module_id: str,
        window: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return ``[{commit, timestamp, hamiltonian, hurst, slope_pct,
                   forecast_next, confidence, forecast_error}]``
        ordered chronologically ASC.  ``forecast_error`` is the gap between
        the forecast THIS row made (``forecast_next``) and the actual
        ``hamiltonian`` of the NEXT row — i.e. the predictor's accuracy on
        each step.  The last row has ``forecast_error = None``.

        Rows predating LEAP 4 carry predictor_* = None; their dict entries
        are also None and ``forecast_error`` is None for the row before them
        (because we cannot compare against a missing forecast).
        """
        sql = """
        SELECT commit_hash, timestamp, hamiltonian,
               predictor_hurst, predictor_slope_pct,
               predictor_forecast_next, predictor_confidence
        FROM snapshots
        WHERE module_id = ?
        ORDER BY timestamp DESC, id DESC
        LIMIT ?
        """
        with self._lock:
            rows = self._get_conn().execute(sql, (module_id, window)).fetchall()
        rows = list(reversed(rows))

        out: List[Dict[str, Any]] = []
        for r in rows:
            commit, ts, ham, hurst, slope, fcst, conf = r
            out.append({
                "commit":        str(commit),
                "timestamp":     float(ts),
                "hamiltonian":   float(ham),
                "hurst":         float(hurst) if hurst is not None else None,
                "slope_pct":     float(slope) if slope is not None else None,
                "forecast_next": float(fcst)  if fcst  is not None else None,
                "confidence":    float(conf)  if conf  is not None else None,
                "forecast_error": None,
            })
        # Backfill forecast_error: row[i].forecast_next vs row[i+1].hamiltonian
        for i in range(len(out) - 1):
            fcst = out[i]["forecast_next"]
            if fcst is not None:
                out[i]["forecast_error"] = round(
                    out[i + 1]["hamiltonian"] - fcst, 6
                )
        return out

    # ─── Baseline ────────────────────────────────────────────────────────────

    def get_baseline(
        self,
        module_id: str,
        window: int = 100,
    ) -> Optional[BaselineStats]:
        """
        Calcula estatísticas de baseline para o módulo.

        Requer ≥ 3 amostras. Retorna None se insuficiente.
        """
        history = self.get_history(module_id, window=window)
        if len(history) < 3:
            return None

        h_vals    = [mv.hamiltonian for mv in history]
        cc_vals   = [float(mv.cyclomatic_complexity) for mv in history]
        di_vals   = [mv.dependency_instability for mv in history]
        dead_vals = [float(mv.syntactic_dead_code) for mv in history]
        ilr_vals  = [mv.infinite_loop_risk for mv in history]
        dsmd_vals = [mv.dsm_density for mv in history]
        dsmc_vals = [mv.dsm_cyclic_ratio for mv in history]
        dups_vals = [float(mv.duplicate_block_count) for mv in history]
        bugs_vals = [mv.halstead_bugs for mv in history]

        def _std(vals: List[float]) -> float:
            if len(vals) < 2:
                return 0.0
            try:
                return statistics.stdev(vals)
            except statistics.StatisticsError:
                return 0.0

        def _slope(vals: List[float]) -> float:
            """Tendência linear por regressão simples."""
            n = len(vals)
            if n < 2:
                return 0.0
            x_mean = (n - 1) / 2.0
            y_mean = sum(vals) / n
            num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(vals))
            den = sum((i - x_mean) ** 2 for i in range(n))
            return num / den if den > 1e-12 else 0.0

        channel_means = {
            "H":     statistics.mean(h_vals),
            "CC":    statistics.mean(cc_vals),
            "ILR":   statistics.mean(ilr_vals),
            "DSM_d": statistics.mean(dsmd_vals),
            "DSM_c": statistics.mean(dsmc_vals),
            "DI":    statistics.mean(di_vals),
            "dead":  statistics.mean(dead_vals),
            "dups":  statistics.mean(dups_vals),
            "bugs":  statistics.mean(bugs_vals),
        }
        channel_stds = {
            "H":     _std(h_vals),
            "CC":    _std(cc_vals),
            "ILR":   _std(ilr_vals),
            "DSM_d": _std(dsmd_vals),
            "DSM_c": _std(dsmc_vals),
            "DI":    _std(di_vals),
            "dead":  _std(dead_vals),
            "dups":  _std(dups_vals),
            "bugs":  _std(bugs_vals),
        }

        stats = BaselineStats(
            n_samples=len(history),
            h_mean=channel_means["H"],
            h_std=channel_stds["H"],
            h_trend_slope=_slope(h_vals),
            cc_mean=channel_means["CC"],
            cc_std=channel_stds["CC"],
            di_mean=channel_means["DI"],
            di_std=channel_stds["DI"],
            dead_mean=channel_means["dead"],
            dead_std=channel_stds["dead"],
            _channel_means=channel_means,
            _channel_stds=channel_stds,
        )
        return stats

    # ─── Anomalias ───────────────────────────────────────────────────────────

    def insert_anomaly(
        self,
        event_id: str,
        module_id: str,
        data: Dict[str, Any],
    ) -> None:
        """
        Persiste evento de anomalia detectado pelo FrequencyEngine.

        Parâmetros
        ----------
        event_id  : ID único do evento (ex: "test-event-001")
        module_id : módulo onde a anomalia foi detectada
        data      : dict com chaves: primary_error, severity, primary_confidence,
                    dominant_band, plain_english, technical_summary, apex_prompt,
                    change_point (opcional), timestamp
        """
        cp = data.get("change_point") or {}
        sql = """
        INSERT OR REPLACE INTO anomalies (
            event_id, module_id, error_type, severity, confidence,
            band, plain_text, tech_summary, apex_prompt,
            change_point_idx, change_point_hash,
            created_at, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            event_id,
            module_id,
            data.get("primary_error", "UNKNOWN"),
            data.get("severity", "INFO"),
            float(data.get("primary_confidence", 0.0)),
            data.get("dominant_band", ""),
            data.get("plain_english", ""),
            data.get("technical_summary", ""),
            data.get("apex_prompt", ""),
            cp.get("commit_idx") if isinstance(cp, dict) else None,
            cp.get("commit_hash") if isinstance(cp, dict) else None,
            float(data.get("timestamp", time.time())),
            json.dumps(data, default=str),
        )
        with self._lock:
            self._get_conn().execute(sql, values)

    def get_anomalies(
        self,
        module_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Retorna anomalias registradas.

        Parâmetros
        ----------
        module_id : filtro por módulo (None → todos)
        limit     : máximo de registros

        Retorna
        -------
        List[dict] com chaves: event_id, module_id, error_type, severity,
                               confidence, change_point_hash, created_at.
        """
        if module_id:
            sql = """
            SELECT event_id, module_id, error_type, severity, confidence,
                   band, plain_text, change_point_idx, change_point_hash, created_at
            FROM anomalies
            WHERE module_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """
            with self._lock:
                rows = self._get_conn().execute(sql, (module_id, limit)).fetchall()
        else:
            sql = """
            SELECT event_id, module_id, error_type, severity, confidence,
                   band, plain_text, change_point_idx, change_point_hash, created_at
            FROM anomalies
            ORDER BY created_at DESC
            LIMIT ?
            """
            with self._lock:
                rows = self._get_conn().execute(sql, (limit,)).fetchall()

        return [
            {
                "event_id":          r[0],
                "module_id":         r[1],
                "error_type":        r[2],
                "severity":          r[3],
                "confidence":        r[4],
                "band":              r[5],
                "plain_text":        r[6],
                "change_point_idx":  r[7],
                "change_point_hash": r[8],
                "created_at":        r[9],
            }
            for r in rows
        ]

    # ─── List modules ────────────────────────────────────────────────────────

    def list_modules(self) -> List[str]:
        """Retorna lista de todos os module_id conhecidos."""
        sql = "SELECT DISTINCT module_id FROM snapshots ORDER BY module_id"
        with self._lock:
            rows = self._get_conn().execute(sql).fetchall()
        return [r[0] for r in rows]

    # ─── Auth + Billing ──────────────────────────────────────────────────────

    @staticmethod
    def _hash_key(plain_key: str) -> str:
        return hashlib.sha256(plain_key.encode("utf-8")).hexdigest()

    def create_key(self, name: str = "", quota_day: int = 0) -> str:
        """
        Cria uma nova API key.

        Formato: uco_<32 hex chars>  (total 36 chars)
        Armazena apenas o SHA-256 — a plain key é retornada UMA vez.

        Parâmetros
        ----------
        name      : descrição humana (ex: "github_ci_prod")
        quota_day : máximo de chamadas por dia, 0 = ilimitado

        Retorna
        -------
        str — plain key no formato "uco_<hex>" (guardar em segurança)
        """
        plain = f"uco_{secrets.token_hex(16)}"
        prefix = plain[:12]           # "uco_" + 8 hex = 12 chars de display
        key_hash = self._hash_key(plain)
        sql = """
        INSERT INTO api_keys (key_prefix, key_hash, name, quota_day, calls_today,
                              calls_total, last_reset, active, created_at)
        VALUES (?, ?, ?, ?, 0, 0, ?, 1, ?)
        """
        now = time.time()
        with self._lock:
            self._get_conn().execute(sql, (prefix, key_hash, name, quota_day, now, now))
        return plain

    def validate_key(self, plain_key: str) -> Optional[Dict[str, Any]]:
        """
        Valida uma API key e incrementa contador.

        Realiza reset diário automático se o dia mudou desde last_reset.

        Retorna dict com info da chave, ou None se inválida/excedeu quota.
        """
        if not plain_key or not plain_key.startswith("uco_"):
            return None

        key_hash = self._hash_key(plain_key)
        sql = """
        SELECT id, key_prefix, name, quota_day, calls_today, calls_total,
               last_reset, active
        FROM api_keys
        WHERE key_hash = ?
        """
        with self._lock:
            row = self._get_conn().execute(sql, (key_hash,)).fetchone()
            if not row:
                return None

            key_id, prefix, name, quota_day, calls_today, calls_total, last_reset, active = row

            if not active:
                return None

            # Reset diário
            now = time.time()
            today_start = now - (now % 86400)
            if last_reset < today_start:
                calls_today = 0
                self._get_conn().execute(
                    "UPDATE api_keys SET calls_today=0, last_reset=? WHERE id=?",
                    (now, key_id)
                )

            # Verificar quota
            if quota_day > 0 and calls_today >= quota_day:
                return None   # quota excedida

            # Incrementar
            self._get_conn().execute(
                "UPDATE api_keys SET calls_today=calls_today+1, calls_total=calls_total+1 WHERE id=?",
                (key_id,)
            )

        return {
            "key_prefix":   prefix,
            "name":         name,
            "quota_day":    quota_day,
            "calls_today":  calls_today + 1,
            "calls_total":  calls_total + 1,
        }

    def get_usage(self, key_prefix: str) -> Optional[Dict[str, Any]]:
        """Retorna stats de uso de uma chave pelo prefixo (sem expor hash)."""
        sql = """
        SELECT key_prefix, name, quota_day, calls_today, calls_total, active, created_at
        FROM api_keys WHERE key_prefix = ?
        """
        with self._lock:
            row = self._get_conn().execute(sql, (key_prefix,)).fetchone()
        if not row:
            return None
        return {
            "key_prefix":  row[0],
            "name":        row[1],
            "quota_day":   row[2],
            "calls_today": row[3],
            "calls_total": row[4],
            "active":      bool(row[5]),
            "created_at":  row[6],
        }

    def list_keys(self) -> List[Dict[str, Any]]:
        """Lista todas as chaves (sem expor hash completo)."""
        sql = """
        SELECT key_prefix, name, quota_day, calls_today, calls_total, active, created_at
        FROM api_keys ORDER BY created_at DESC
        """
        with self._lock:
            rows = self._get_conn().execute(sql).fetchall()
        return [
            {
                "key_prefix":  r[0],
                "name":        r[1],
                "quota_day":   r[2],
                "calls_today": r[3],
                "calls_total": r[4],
                "active":      bool(r[5]),
                "created_at":  r[6],
            }
            for r in rows
        ]

    def revoke_key(self, key_prefix: str) -> bool:
        """
        Revoga uma API key pelo prefixo.

        Retorna True se a chave existia e foi revogada.
        """
        with self._lock:
            cur = self._get_conn().execute(
                "UPDATE api_keys SET active=0 WHERE key_prefix=? AND active=1",
                (key_prefix,)
            )
        return cur.rowcount > 0

    # ─── Sprint C — Auto-fix telemetry ───────────────────────────────────────

    def store_remediation(
        self,
        module_id: str,
        result: Any,
        *,
        commit_hash: str = "",
        timestamp: Optional[float] = None,
    ) -> int:
        """
        Persist one RemediationResult row.

        ``result`` is duck-typed: it can be a sensor_core.autofix.sast_remediation
        .RemediationResult, or any object with the same field surface, or even a
        plain dict produced by ``RemediationResult.to_dict()``.  Defensive: any
        missing field defaults to a neutral value (empty list / 0 / True).

        Returns the inserted row id.
        """
        ts = float(timestamp) if timestamp is not None else time.time()

        # Accept dict OR object form interchangeably.
        if isinstance(result, dict):
            getter = result.get
        else:
            getter = lambda key, default=None: getattr(result, key, default)

        is_valid             = 1 if bool(getter("is_valid", True)) else 0
        findings_before_list = list(getter("findings_before", []) or [])
        findings_after_list  = list(getter("findings_after",  []) or [])
        transforms_list      = list(getter("transforms_applied", []) or [])
        fixed_rules_list     = list(getter("fixed_rules", []) or [])

        fixed_count = getter("fixed_count", None)
        if fixed_count is None:
            fixed_count = len(fixed_rules_list)

        residual_count = getter("residual_count", None)
        if residual_count is None:
            residual_count = len(findings_after_list)

        sql = """
        INSERT INTO remediations (
            module_id, commit_hash, timestamp,
            is_valid, findings_before, findings_after,
            fixed_count, residual_count,
            transforms_json, fixed_rules_json,
            findings_before_json, findings_after_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = (
            module_id,
            commit_hash or "",
            ts,
            is_valid,
            len(findings_before_list),
            len(findings_after_list),
            int(fixed_count),
            int(residual_count),
            json.dumps(transforms_list),
            json.dumps(fixed_rules_list),
            json.dumps(findings_before_list),
            json.dumps(findings_after_list),
        )
        with self._lock:
            cur = self._get_conn().execute(sql, values)
            return int(cur.lastrowid or 0)

    def get_remediation_history(
        self,
        module_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return remediation rows ASC by timestamp (oldest first).

        ``module_id=None`` returns rows for **all** modules — useful for the
        repo-level stats endpoint.  ``limit`` is applied AFTER the ASC sort,
        so passing limit=100 yields the 100 oldest rows; reverse client-side
        if you need newest-first.
        """
        sql = """
        SELECT id, module_id, commit_hash, timestamp,
               is_valid, findings_before, findings_after,
               fixed_count, residual_count,
               transforms_json, fixed_rules_json,
               findings_before_json, findings_after_json
        FROM remediations
        """
        params: tuple = ()
        if module_id is not None:
            sql += " WHERE module_id = ?"
            params = (module_id,)
        sql += " ORDER BY timestamp ASC, id ASC"
        if limit and limit > 0:
            sql += f" LIMIT {int(limit)}"

        with self._lock:
            rows = self._get_conn().execute(sql, params).fetchall()

        out: List[Dict[str, Any]] = []
        for r in rows:
            try:
                transforms = json.loads(r[9])  if r[9]  else []
                fixed      = json.loads(r[10]) if r[10] else []
                before     = json.loads(r[11]) if r[11] else []
                after      = json.loads(r[12]) if r[12] else []
            except Exception:
                transforms, fixed, before, after = [], [], [], []
            out.append({
                "id":                 int(r[0]),
                "module_id":          r[1],
                "commit_hash":        r[2] or "",
                "timestamp":          float(r[3]),
                "is_valid":           bool(r[4]),
                "findings_before":    int(r[5]),
                "findings_after":     int(r[6]),
                "fixed_count":        int(r[7]),
                "residual_count":     int(r[8]),
                "transforms_applied": transforms,
                "fixed_rules":        fixed,
                "findings_before_rules": before,
                "findings_after_rules":  after,
            })
        return out

    def get_remediation_stats(
        self,
        module_id: Optional[str] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Aggregate metrics across the remediation history.

        Repo-wide when ``module_id`` is None; per-module otherwise.

        Returns a dict with:
            n_total            — total runs
            n_valid            — runs whose patched source compiled
            n_with_fixes       — runs that fixed ≥ 1 rule
            success_rate       — n_with_fixes / n_total (0.0 when n_total=0)
            total_fixed        — sum of fixed_count
            total_residual     — sum of residual_count
            mean_fixed         — total_fixed / n_total
            mean_residual      — total_residual / n_total
            top_fixed_rules    — [(rule_id, count), ...] top-K by frequency
            top_transforms     — [(transform_name, count), ...] top-K
            first_ts / last_ts — bookends

        Sprint I — fast path: the scalar aggregates (n_total, n_valid,
        n_with_fixes, total_fixed, total_residual, first_ts, last_ts) are
        computed in ONE native SQL query using SUM/COUNT/MIN/MAX.  Only
        the top_k frequency tables still need to read JSON blobs (Python),
        and that pass is limited to the ``fixed_rules_json`` /
        ``transforms_json`` columns — not the full rows.
        """
        # ── Scalar aggregates via single SQL query ───────────────────────────
        params: tuple = ()
        where = ""
        if module_id is not None:
            where = " WHERE module_id = ?"
            params = (module_id,)

        scalar_sql = f"""
        SELECT
            COUNT(*)                                        AS n_total,
            COALESCE(SUM(CASE WHEN is_valid=1 THEN 1 ELSE 0 END), 0) AS n_valid,
            COALESCE(SUM(CASE WHEN fixed_count > 0 THEN 1 ELSE 0 END), 0) AS n_with_fixes,
            COALESCE(SUM(fixed_count),    0)                AS total_fixed,
            COALESCE(SUM(residual_count), 0)                AS total_residual,
            MIN(timestamp)                                  AS first_ts,
            MAX(timestamp)                                  AS last_ts
        FROM remediations{where}
        """
        with self._lock:
            (n_total, n_valid, n_with_fixes, total_fixed, total_resid,
             first_ts, last_ts) = self._get_conn().execute(
                scalar_sql, params,
            ).fetchone()

        if n_total == 0:
            return {
                "n_total":         0,
                "n_valid":         0,
                "n_with_fixes":    0,
                "success_rate":    0.0,
                "total_fixed":     0,
                "total_residual":  0,
                "mean_fixed":      0.0,
                "mean_residual":   0.0,
                "top_fixed_rules": [],
                "top_transforms":  [],
                "first_ts":        None,
                "last_ts":         None,
            }

        # ── Frequency tables — only read the 2 JSON columns we need ──────────
        freq_sql = f"""
        SELECT fixed_rules_json, transforms_json
        FROM remediations{where}
        """
        with self._lock:
            freq_rows = self._get_conn().execute(freq_sql, params).fetchall()

        rule_counts: Dict[str, int] = {}
        transform_counts: Dict[str, int] = {}
        for fr_json, tr_json in freq_rows:
            try:
                rules = json.loads(fr_json) if fr_json else []
            except Exception:
                rules = []
            try:
                trans = json.loads(tr_json) if tr_json else []
            except Exception:
                trans = []
            for r in rules:
                rule_counts[r] = rule_counts.get(r, 0) + 1
            for t in trans:
                transform_counts[t] = transform_counts.get(t, 0) + 1

        top_fixed = sorted(
            rule_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:max(0, int(top_k))]
        top_trans = sorted(
            transform_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:max(0, int(top_k))]

        return {
            "n_total":         int(n_total),
            "n_valid":         int(n_valid),
            "n_with_fixes":    int(n_with_fixes),
            "success_rate":    n_with_fixes / n_total,
            "total_fixed":     int(total_fixed),
            "total_residual":  int(total_resid),
            "mean_fixed":      total_fixed  / n_total,
            "mean_residual":   total_resid  / n_total,
            "top_fixed_rules": [{"rule_id": k,   "count": v} for k, v in top_fixed],
            "top_transforms":  [{"transform": k, "count": v} for k, v in top_trans],
            "first_ts":        float(first_ts) if first_ts is not None else None,
            "last_ts":         float(last_ts)  if last_ts  is not None else None,
        }

    # ─── Close ───────────────────────────────────────────────────────────────

    # ── Sprint P — Discovered signatures persistence ────────────────────────

    def store_signature(
        self,
        signature_id: str,
        centroid: List[float],
        members: List[str],
        diameter: float,
        *,
        label: str = "",
        notes: str = "",
    ) -> Dict[str, Any]:
        """
        Persist a discovered signature.  If ``signature_id`` already exists:
        bump ``occurrence_count``, update ``last_seen_at`` + ``n_members`` +
        ``members_json``; do NOT overwrite the original centroid (it defines
        the cluster identity).
        """
        now = time.time()
        members_text  = json.dumps(list(members))
        centroid_text = json.dumps(list(centroid))

        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT id FROM discovered_signatures WHERE signature_id = ?",
                (signature_id,),
            ).fetchone()

            if row is None:
                conn.execute(
                    "INSERT INTO discovered_signatures ("
                    "signature_id, created_at, last_seen_at, occurrence_count, "
                    "n_members, diameter, centroid_json, members_json, label, notes"
                    ") VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                    (signature_id, now, now,
                     len(members), float(diameter),
                     centroid_text, members_text, label, notes),
                )
            else:
                conn.execute(
                    "UPDATE discovered_signatures SET "
                    "last_seen_at = ?, occurrence_count = occurrence_count + 1, "
                    "n_members = ?, diameter = ?, members_json = ?, "
                    "label = CASE WHEN ? != '' THEN ? ELSE label END, "
                    "notes = CASE WHEN ? != '' THEN ? ELSE notes END "
                    "WHERE signature_id = ?",
                    (now, len(members), float(diameter), members_text,
                     label, label, notes, notes, signature_id),
                )

        return self.get_signature(signature_id) or {}

    def get_signature(self, signature_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT id, signature_id, created_at, last_seen_at, "
                "occurrence_count, n_members, diameter, centroid_json, "
                "members_json, label, notes "
                "FROM discovered_signatures WHERE signature_id = ?",
                (signature_id,),
            ).fetchone()
        if row is None:
            return None
        return _signature_row_to_dict(row)

    def list_signatures(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        sql = (
            "SELECT id, signature_id, created_at, last_seen_at, "
            "occurrence_count, n_members, diameter, centroid_json, "
            "members_json, label, notes "
            "FROM discovered_signatures "
            "ORDER BY occurrence_count DESC, last_seen_at DESC "
            f"LIMIT {int(max(1, limit))}"
        )
        with self._lock:
            rows = self._get_conn().execute(sql).fetchall()
        return [_signature_row_to_dict(r) for r in rows]

    def delete_signature(self, signature_id: str) -> bool:
        with self._lock:
            cur = self._get_conn().execute(
                "DELETE FROM discovered_signatures WHERE signature_id = ?",
                (signature_id,),
            )
        return cur.rowcount > 0

    def signature_count(self) -> int:
        with self._lock:
            row = self._get_conn().execute(
                "SELECT COUNT(*) FROM discovered_signatures"
            ).fetchone()
        return int(row[0] or 0)

    def close(self) -> None:
        """Fecha conexão(ões) SQLite explicitamente."""
        with self._lock:
            if self._in_memory:
                self._shared_conn.close()
            else:
                # Close the connection for the current thread if it exists
                conn = getattr(self._local, "conn", None)
                if conn is not None:
                    conn.close()
                    self._local.conn = None

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    # ─── Helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_mv(row: tuple) -> MetricVector:
        """
        Converte linha SQLite em MetricVector.

        M7.0: also deserializes extended_vectors_json, advanced_vector_json,
        and diagnostic_vector_json back into their respective vector objects
        (HalsteadVector, StructuralVector, AdvancedVector, DiagnosticVector).

        LEAP 1: also deserializes extended_vectors_v2_json into nine vectors
        previously dropped on every scan — security, velocity, flow,
        reliability, maintainability, performance, architecture,
        test_quality, thread_safety.

        LEAP 2: attaches the persisted aps_score to ``mv.aps_score`` (None
        for legacy rows predating LEAP 2 — callers must treat None as
        "missing sample", not as zero).

        LEAP 4: attaches predictor_hurst, predictor_slope_pct,
        predictor_forecast_next, predictor_confidence to ``mv.predictor_*``
        — the predictor's view at the moment this snapshot was written.
        """
        (
            module_id, commit_hash, timestamp,
            h, cc, ilr,
            dsm_d, dsm_c, di,
            dead, dups, bugs,
            lang, loc, status,
            n_fn, n_cls, max_meth,
            cc_hr, max_fn_cc,
            extended_json, advanced_json, diagnostic_json,
            extended_v2_json,                                       # LEAP 1
            aps_score,                                              # LEAP 2
            p_hurst, p_slope_pct, p_forecast_next, p_confidence,    # LEAP 4
        ) = row

        mv = MetricVector(
            module_id=module_id,
            commit_hash=commit_hash,
            timestamp=float(timestamp),
            hamiltonian=float(h),
            cyclomatic_complexity=int(cc),
            infinite_loop_risk=float(ilr),
            dsm_density=float(dsm_d),
            dsm_cyclic_ratio=float(dsm_c),
            dependency_instability=float(di),
            syntactic_dead_code=int(dead),
            duplicate_block_count=int(dups),
            halstead_bugs=float(bugs),
            language=lang or "python",
            lines_of_code=int(loc or 0),
            status=status or "STABLE",
        )
        # Extra fields used by MetricSignalBuilder (via getattr with defaults)
        mv.n_functions           = int(n_fn or 0)
        mv.n_classes             = int(n_cls or 0)
        mv.max_methods_per_class = int(max_meth or 0)
        mv.cc_hotspot_ratio      = float(cc_hr or 0.0)
        mv.max_function_cc       = int(max_fn_cc or 0)

        # M7.0: restore extended vectors from JSON blobs (lazy import)
        if extended_json:
            try:
                from metrics.extended_vectors import HalsteadVector, StructuralVector
                d = json.loads(extended_json)
                if "halstead" in d:
                    from dataclasses import fields as _dc_fields
                    hd = d["halstead"]
                    mv.halstead = HalsteadVector(
                        volume=float(hd.get("volume", 0.0)),
                        difficulty=float(hd.get("difficulty", 0.0)),
                        effort=float(hd.get("effort", 0.0)),
                        time_to_implement=float(hd.get("time_to_implement", 0.0)),
                        program_level=float(hd.get("program_level", 0.0)),
                        token_count=int(hd.get("token_count", 0)),
                        module_id=str(hd.get("module_id", "")),
                        language=str(hd.get("language", "")),
                    )
                if "structural" in d:
                    sd = d["structural"]
                    mv.structural = StructuralVector(
                        max_function_cc=int(sd.get("max_function_cc", 1)),
                        cc_hotspot_ratio=float(sd.get("cc_hotspot_ratio", 0.0)),
                        max_methods_per_class=int(sd.get("max_methods_per_class", 0)),
                        n_functions=int(sd.get("n_functions", 0)),
                        n_classes=int(sd.get("n_classes", 0)),
                        comment_density=float(sd.get("comment_density", 0.0)),
                        test_ratio=float(sd.get("test_ratio", 0.0)),
                        module_id=str(sd.get("module_id", "")),
                        language=str(sd.get("language", "")),
                    )
            except Exception:
                pass

        if advanced_json:
            try:
                from metrics.extended_vectors import AdvancedVector
                mv.advanced = AdvancedVector.from_dict(json.loads(advanced_json))
            except Exception:
                pass

        if diagnostic_json:
            try:
                from metrics.extended_vectors import DiagnosticVector
                mv.diagnostic = DiagnosticVector.from_dict(json.loads(diagnostic_json))
            except Exception:
                pass

        # ── LEAP 2 — attach persisted APS (None for legacy rows) ─────────────
        mv.aps_score = float(aps_score) if aps_score is not None else None

        # ── LEAP 4 — attach persisted predictor outputs ──────────────────────
        mv.predictor_hurst         = float(p_hurst)         if p_hurst         is not None else None
        mv.predictor_slope_pct     = float(p_slope_pct)     if p_slope_pct     is not None else None
        mv.predictor_forecast_next = float(p_forecast_next) if p_forecast_next is not None else None
        mv.predictor_confidence    = float(p_confidence)    if p_confidence    is not None else None

        # ── LEAP 1 — restore the nine previously dropped vectors ─────────────
        if extended_v2_json:
            try:
                from metrics.extended_vectors import (
                    SecurityVector, VelocityVector, FlowVector,
                    ReliabilityVector, MaintainabilityVector,
                    PerformanceVector, ArchitectureVector,
                    TestQualityVector, ThreadSafetyVector,
                )
                _CLASSES = {
                    "security":        SecurityVector,
                    "velocity":        VelocityVector,
                    "flow":            FlowVector,
                    "reliability":     ReliabilityVector,
                    "maintainability": MaintainabilityVector,
                    "performance":     PerformanceVector,
                    "architecture":    ArchitectureVector,
                    "test_quality":    TestQualityVector,
                    "thread_safety":   ThreadSafetyVector,
                }
                payload = json.loads(extended_v2_json)
                for attr, cls in _CLASSES.items():
                    if attr in payload:
                        try:
                            setattr(mv, attr, cls.from_dict(payload[attr]))
                        except Exception:
                            # One bad vector must not poison the row.
                            continue
            except Exception:
                pass

        return mv


# ─── Sprint P — signature row helper (module-level) ───────────────────────────

def _signature_row_to_dict(row: tuple) -> Dict[str, Any]:
    (id_, signature_id, created_at, last_seen_at,
     occurrence_count, n_members, diameter,
     centroid_json, members_json, label, notes) = row
    try:
        centroid = json.loads(centroid_json) if centroid_json else []
    except Exception:
        centroid = []
    try:
        members = json.loads(members_json) if members_json else []
    except Exception:
        members = []
    return {
        "id":               int(id_),
        "signature_id":     str(signature_id),
        "created_at":       float(created_at),
        "last_seen_at":     float(last_seen_at),
        "occurrence_count": int(occurrence_count),
        "n_members":        int(n_members),
        "diameter":         float(diameter),
        "centroid":         centroid,
        "members":          members,
        "label":            str(label or ""),
        "notes":            str(notes or ""),
    }
