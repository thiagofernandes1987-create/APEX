"""
Marco 87 — M18 auto-fix: loop Sensor → Core → aplica → re-scan silencia
=======================================================================
Fecha a META C: o UCO Core não só SUGERE o patch — ele o APLICA e o Sensor
**para de disparar** no site corrigido. Validado com dado real (php-src) no
harness; aqui, fixtures offline reproduzem o padrão (subtração não-guardada
`p = base + a - b` → M11 GA01 dispara → auto-fix insere `if (!(a>b))` → o
site silencia).
"""
from __future__ import annotations

from sast.guard_aware import GuardAwareScanner
from sast.fix_suggester import FixSuggester

_VULN = """\
static int f(char *base, int pilen, int slen)
{
    char *p = base + pilen - slen;
    return p != base;
}
"""


def _ga01(findings):
    return [g for g in findings if g.rule_id == "GA01"]


def test_T87_sensor_fires_on_unguarded_subtraction():
    finds = _ga01(GuardAwareScanner().scan(_VULN, ".c"))
    assert len(finds) >= 1
    assert finds[0].needs_guard_on == ("pilen", "slen")


def test_T87_autofix_makes_sensor_stop_firing():
    sc = GuardAwareScanner()
    fs = FixSuggester()
    before = _ga01(sc.scan(_VULN, ".c"))
    assert before, "pré-condição: deve disparar no vulnerável"
    gf = before[0]
    sug = fs.suggest_for_guard(gf)
    assert sug.guard_expr == "pilen > slen"

    patched = fs.apply_fix(_VULN, sug)
    # o guard sugerido está agora no fonte corrigido
    assert "pilen > slen" in patched

    after = _ga01(sc.scan(patched, ".c"))
    # o site (pilen,slen) parou de disparar
    still = [g for g in after if g.needs_guard_on == ("pilen", "slen")]
    assert not still, "o Sensor deveria silenciar após o auto-fix"


def test_T87_autofix_noop_for_taint_suggestion():
    # sugestão de taint (sem guard_expr) não altera o fonte
    fs = FixSuggester()
    flow = {"vuln_type": "UNSAFE_DESERIALIZATION", "cwe_id": "CWE-502", "sink_line": 2}
    sug = fs.suggest_for_taint(flow)
    src = "x = 1\ny = 2\n"
    assert fs.apply_fix(src, sug) == src
