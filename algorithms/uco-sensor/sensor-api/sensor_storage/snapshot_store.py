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
    UNIQUE(module_id, commit_hash)
);
"""

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
            cur.execute(_IDX_SNAPSHOTS)
            cur.execute(_IDX_ANOMALIES)
            cur.execute(_IDX_API_KEYS)

    # ─── Insert ──────────────────────────────────────────────────────────────

    def insert(self, mv: MetricVector) -> None:
        """
        Upsert MetricVector.

        Idempotente: inserir (module_id, commit_hash) já existente
        atualiza os campos — não duplica o registro.
        """
        sql = """
        INSERT OR REPLACE INTO snapshots (
            module_id, commit_hash, timestamp,
            hamiltonian, cyclomatic_complexity, infinite_loop_risk,
            dsm_density, dsm_cyclic_ratio, dependency_instability,
            syntactic_dead_code, duplicate_block_count, halstead_bugs,
            language, lines_of_code, status,
            n_functions, n_classes, max_methods_per_class,
            cc_hotspot_ratio, max_function_cc
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
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
        )
        with self._lock:
            self._get_conn().execute(sql, values)

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
            cc_hotspot_ratio, max_function_cc
        FROM snapshots
        WHERE module_id = ?
        ORDER BY timestamp DESC
        LIMIT ?
        """
        with self._lock:
            rows = self._get_conn().execute(sql, (module_id, window)).fetchall()

        # Reverter para ordem ASC (mais antigo primeiro — correto para FrequencyEngine)
        rows = list(reversed(rows))
        return [self._row_to_mv(r) for r in rows]

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

    # ─── Close ───────────────────────────────────────────────────────────────

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
        """Converte linha SQLite em MetricVector."""
        (
            module_id, commit_hash, timestamp,
            h, cc, ilr,
            dsm_d, dsm_c, di,
            dead, dups, bugs,
            lang, loc, status,
            n_fn, n_cls, max_meth,
            cc_hr, max_fn_cc,
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
        return mv
