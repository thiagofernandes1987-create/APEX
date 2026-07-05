"""
test_marco_m101.py — Sprint DP (v3.93.0): correções da auditoria adversarial
=============================================================================
Regressões para os defeitos confirmados na auditoria independente:

  • D3 — `_SINK_GENERIC_METHODS`: `.execute()/.raw()` em objeto NÃO-SQL
    (pipeline/task/strategy) deixava de ser FP CRITICAL de SQL Injection.
  • D4 — gating SQL ignorava kwargs por completo: `execute(sql=user_input)`
    passava sem checagem (falso-negativo).
  • D7 — SAST046 (unsafe deserialization) sem metadata → caía no fallback
    genérico SAST045.

Todos os fixtures são shapes mínimos reais; nenhum dado fabricado.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

from sast.taint_engine import TaintAnalyzer  # noqa: E402
from sast.taint_cfg import CFGTaintAnalyzer  # noqa: E402
from sast.taint_interproc import InterprocTaintAnalyzer  # noqa: E402


def _base_rules(code: str):
    return [f.rule_id for f in TaintAnalyzer().analyze(code).flows]


def _cfg_rules(code: str):
    return [f.rule_id for f in CFGTaintAnalyzer().analyze(code)]


def _inter_rules(code: str):
    return [f.rule_id for f in InterprocTaintAnalyzer().analyze(code)]


# ── D3: generic .execute() FP ────────────────────────────────────────────────

def test_TBA01_pipeline_execute_is_not_sql_sink():
    code = (
        "from flask import request\n"
        "def run(pipeline):\n"
        "    plan = request.args.get('plan')\n"
        "    pipeline.execute(plan)\n"
    )
    assert "SAST040" not in _base_rules(code)


def test_TBA02_task_execute_is_not_sql_sink():
    code = (
        "from flask import request\n"
        "def run(task):\n"
        "    payload = request.args.get('p')\n"
        "    task.execute(payload)\n"
    )
    assert "SAST040" not in _base_rules(code)


def test_TBA03_strategy_execute_is_not_sql_sink():
    code = (
        "from flask import request\n"
        "def run(strategy):\n"
        "    plan = request.args.get('plan')\n"
        "    strategy.execute(plan)\n"
    )
    assert "SAST040" not in _base_rules(code)


def test_TBA04_real_cursor_execute_still_flagged():
    code = (
        "from flask import request\n"
        "def q(cursor):\n"
        "    name = request.args.get('name')\n"
        "    cursor.execute(\"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
    )
    assert "SAST040" in _base_rules(code)


def test_TBA05_db_handle_alias_still_flagged():
    code = (
        "from flask import request\n"
        "def q(self):\n"
        "    name = request.args.get('name')\n"
        "    self.db.execute(\"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
    )
    assert "SAST040" in _base_rules(code)


def test_TBA06_conn_alias_still_flagged():
    code = (
        "from flask import request\n"
        "def q(self):\n"
        "    name = request.args.get('name')\n"
        "    self._conn.execute(\"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
    )
    assert "SAST040" in _base_rules(code)


# ── D4: SQL query passed by keyword ──────────────────────────────────────────

def test_TBA07_cfg_execute_sql_kwarg_flagged():
    code = (
        "from flask import request\n"
        "def q(cursor):\n"
        "    name = request.args.get('name')\n"
        "    cursor.execute(sql=\"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
    )
    assert "SAST040" in _cfg_rules(code)


def test_TBA08_interproc_execute_query_kwarg_flagged():
    code = (
        "from flask import request\n"
        "def handler(cursor):\n"
        "    name = request.args.get('name')\n"
        "    run_query(cursor, \"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
        "def run_query(cursor, q):\n"
        "    cursor.execute(sql=q)\n"
    )
    assert "SAST040" in _inter_rules(code)


def test_TBA09_bind_param_kwarg_not_treated_as_query():
    # `parameters=` é bind param seguro; não deve reintroduzir FP quando a query
    # é uma constante literal.
    code = (
        "from flask import request\n"
        "def q(cursor):\n"
        "    val = request.args.get('v')\n"
        "    cursor.execute('SELECT * FROM u WHERE n=%s', parameters=(val,))\n"
    )
    assert "SAST040" not in _cfg_rules(code)


# ── D7: SAST046 metadata specificity ─────────────────────────────────────────

def test_TBA10_sast046_has_dedicated_metadata():
    from sast.taint_engine import _TAINT_RULE_META
    assert "SAST046" in _TAINT_RULE_META
    meta = _TAINT_RULE_META["SAST046"]
    assert "deserial" in meta["title"].lower()
    assert meta is not _TAINT_RULE_META["SAST045"]


# ── M22 recall: taint propaga por AugAssign (`q += tainted`) ──────────────────

def test_TBA11_cfg_augassign_propagates_taint():
    code = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    name = request.args.get('name')\n"
        "    q = \"SELECT * FROM u WHERE n='\"\n"
        "    q += name\n"
        "    q += \"'\"\n"
        "    cursor.execute(q)\n"
    )
    assert "SAST040" in _cfg_rules(code)


def test_TBA12_cfg_augassign_sanitized_is_clean():
    # `+= str(int(...))` só adiciona dígitos → sem metacaracteres → sem flow.
    code = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    uid = int(request.args.get('id'))\n"
        "    q = 'SELECT * FROM u WHERE id='\n"
        "    q += str(uid)\n"
        "    cursor.execute(q)\n"
    )
    assert "SAST040" not in _cfg_rules(code)


def test_TBA13_cfg_augassign_preserves_prior_taint():
    # q já contaminado; `q += const` deve MANTER o taint (aug nunca mata).
    code = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    name = request.args.get('name')\n"
        "    q = name\n"
        "    q += ' LIMIT 1'\n"
        "    cursor.execute(q)\n"
    )
    assert "SAST040" in _cfg_rules(code)
