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
        self.db_path = db_path
        self._lock   = threading.Lock()
        # Em-memória: check_same_thread=False para acessos de múltiplas threads
        self._conn   = sqlite3.connect(
            db_path,
            check_same_thread=False,
            isolation_level=None,   # autocommit
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._init_schema()

    # ─── Schema ──────────────────────────────────────────────────────────────

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(_DDL_SNAPSHOTS)
            cur.execute(_DDL_ANOMALIES)
            cur.execute(_IDX_SNAPSHOTS)
            cur.execute(_IDX_ANOMALIES)

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
            self._conn.execute(sql, values)

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
            rows = self._conn.execute(sql, (module_id, window)).fetchall()

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
            self._conn.execute(sql, values)

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
                rows = self._conn.execute(sql, (module_id, limit)).fetchall()
        else:
            sql = """
            SELECT event_id, module_id, error_type, severity, confidence,
                   band, plain_text, change_point_idx, change_point_hash, created_at
            FROM anomalies
            ORDER BY created_at DESC
            LIMIT ?
            """
            with self._lock:
                rows = self._conn.execute(sql, (limit,)).fetchall()

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
            rows = self._conn.execute(sql).fetchall()
        return [r[0] for r in rows]

    # ─── Close ───────────────────────────────────────────────────────────────

    def close(self) -> None:
        """Fecha conexão SQLite explicitamente."""
        with self._lock:
            self._conn.close()

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
