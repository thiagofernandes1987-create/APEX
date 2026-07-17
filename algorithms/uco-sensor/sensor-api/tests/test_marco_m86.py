"""
Marco 86 — M18: FixSuggester (o elo Sensor → UCO Core → patch)
==============================================================
META C: dado um finding do Sensor, o UCO Core emite o patch mínimo
sugerido e — para CVE conhecida — a sugestão coincide com o fix REAL dos
mantenedores. Fecha "identifica o que corrigir".

Fixtures offline reproduzem o padrão real do php-src CVE-2019-11043
(guard `pilen > slen`) e da deserialização insegura (pickle → json).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from sast.fix_suggester import FixSuggester, FixSuggestion


@dataclass
class _GF:
    rule_id: str
    cwe_id: str
    line: int
    needs_guard_on: Tuple[str, ...]
    severity: str = "HIGH"
    snippet: str = ""
    title: str = ""


def test_T86_core_suggests_bounds_guard_for_ga01():
    gf = _GF("GA01", "CWE-191", 1212, ("pilen", "slen"))
    sug = FixSuggester().suggest_for_guard(gf)
    assert isinstance(sug, FixSuggestion)
    assert sug.guard_expr == "pilen > slen"
    assert sug.guard_vars == ("pilen", "slen")
    assert "underflow" in sug.rationale.lower()


def test_T86_suggestion_matches_real_php_src_fix():
    gf = _GF("GA01", "CWE-191", 1212, ("pilen", "slen"))
    sug = FixSuggester().suggest_for_guard(gf)
    # a versão corrigida real contém `pilen > slen`
    fixed = "path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;"
    assert FixSuggester.explains_real_fix(sug, fixed) is True
    # numa versão que NÃO tem o guard, não coincide
    vuln = "path_info = env_path_info + pilen - slen;"
    assert FixSuggester.explains_real_fix(sug, vuln) is False


def test_T86_core_suggests_safe_deserialization():
    flow = {"vuln_type": "UNSAFE_DESERIALIZATION", "cwe_id": "CWE-502",
            "sink_line": 4, "rule_id": "SAST046"}
    sug = FixSuggester().suggest_for_taint(flow)
    assert "json.loads" in sug.suggested_patch or "safe_load" in sug.suggested_patch
    assert FixSuggester.explains_real_fix(sug, "obj = json.loads(request.data)") is True
    # ainda usando pickle → não satisfaz a sugestão
    assert FixSuggester.explains_real_fix(sug, "obj = pickle.loads(request.data)") is False


def test_T86_command_injection_suggests_shlex_or_listform():
    flow = {"vuln_type": "COMMAND_INJECTION", "cwe_id": "CWE-78", "sink_line": 3}
    sug = FixSuggester().suggest_for_taint(flow)
    assert "shlex" in sug.suggested_patch or "shell=False" in sug.suggested_patch


def test_T86_ga02_suggests_length_bound():
    gf = _GF("GA02", "CWE-120", 50, ("n",))
    sug = FixSuggester().suggest_for_guard(gf)
    assert sug.guard_vars == ("n",)
    assert "sizeof" in sug.guard_expr
