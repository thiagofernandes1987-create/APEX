"""
test_marco_m102.py — Sprint DS: pipeline SAST unificado + rename-guard (auditoria 2ª rodada)
=============================================================================================
  * scan_source / scan_path (scan/sast_pipeline.py): um ponto de entrada que roda
    todos os motores de segurança sobre arquivo/diretório — habilita
    `uco-sensor sast <path>` sem subir a API nem chamar motor por motor.
  * dedup de findings idênticos (o taint engine emite 1 flow por caminho).
  * rename-guard no build_degradation (achado #3): renomear a var tainted não pode
    mais reportar um falso `stopped_firing=True`.
"""
from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_SENSOR_DIR = _TESTS_DIR.parent
if str(_SENSOR_DIR) not in sys.path:
    sys.path.insert(0, str(_SENSOR_DIR))

from scan.sast_pipeline import scan_source, scan_path  # noqa: E402
from scan.corpus_expander import build_degradation  # noqa: E402
from scan.advisory_harvester import AdvisoryRecord  # noqa: E402


_SQLI = (
    "from flask import request\n"
    "def h(cursor):\n"
    "    name = request.args.get('name')\n"
    "    cursor.execute(\"SELECT * FROM u WHERE n='\" + name + \"'\")\n"
)


# ── pipeline unificado ───────────────────────────────────────────────────────

def test_TDS_pipeline_detects_sqli_python():
    findings = scan_source(_SQLI, ".py")
    assert any(f.rule_id == "SAST040" for f in findings)


def test_TDS_pipeline_dedups_identical_findings():
    # o taint engine emite 2 flows (1 por source→sink); o pipeline deve colapsar.
    findings = scan_source(_SQLI, ".py")
    sqli = [f for f in findings if f.rule_id == "SAST040"]
    assert len(sqli) == 1, f"esperava 1 SQLi deduplicado, veio {len(sqli)}"


def test_TDS_pipeline_clean_code_no_findings():
    assert scan_source("def add(a, b):\n    return a + b\n", ".py") == []


def test_TDS_scan_path_on_single_file(tmp_path):
    p = tmp_path / "vuln.py"
    p.write_text(_SQLI, encoding="utf-8")
    report = scan_path(str(p))
    assert report["files_scanned"] == 1
    assert report["total_findings"] >= 1
    assert report["rating"] == "CRITICAL"


def test_TDS_scan_path_directory_skips_and_aggregates(tmp_path):
    (tmp_path / "a.py").write_text(_SQLI, encoding="utf-8")
    (tmp_path / "clean.py").write_text("x = 1\n", encoding="utf-8")
    sub = tmp_path / "__pycache__"
    sub.mkdir()
    (sub / "junk.py").write_text(_SQLI, encoding="utf-8")  # deve ser ignorado
    report = scan_path(str(tmp_path))
    # 2 arquivos varridos (a.py + clean.py); __pycache__ pulado
    assert report["files_scanned"] == 2
    assert report["files_with_findings"] == 1


def test_TDS_scan_path_self_analysis_runs():
    # o sensor consegue analisar o PRÓPRIO código sem crashar.
    report = scan_path(str(_SENSOR_DIR / "scan"), max_files=8)
    assert report["files_scanned"] >= 1
    assert "severity_counts" in report


# ── rename-guard (achado #3) ─────────────────────────────────────────────────

def _adv():
    return AdvisoryRecord(
        ghsa_id="GHSA-x", cve="CVE-x", package="p", ecosystem="PyPI",
        introduced="0", fixed="1.1", fix_commit="abc", fix_tag="1.1",
        cwe_ids=["CWE-89"])


def test_TDS_rename_only_does_not_claim_stopped_firing():
    vuln = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    user_id = request.args.get('id')\n"
        "    cursor.execute('SELECT * FROM u WHERE id=' + user_id)\n"
    )
    fixed = vuln.replace("user_id", "identifier")   # só renomeia — NÃO conserta
    rec = build_degradation(_adv(), vuln, fixed, filename="views.py")
    assert rec.stopped_firing is None, (
        "rename-only nunca deve afirmar stopped_firing=True (correcao inexistente)")


def test_TDS_genuine_fix_still_reports_stopped_firing():
    vuln = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    user_id = request.args.get('id')\n"
        "    cursor.execute('SELECT * FROM u WHERE id=' + user_id)\n"
    )
    fixed = (
        "from flask import request\n"
        "def h(cursor):\n"
        "    user_id = request.args.get('id')\n"
        "    cursor.execute('SELECT * FROM u WHERE id=%s', (user_id,))\n"
    )
    rec = build_degradation(_adv(), vuln, fixed, filename="views.py")
    assert rec.stopped_firing is True
