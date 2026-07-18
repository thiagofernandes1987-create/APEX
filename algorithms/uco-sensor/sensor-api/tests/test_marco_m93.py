"""
Marco 93 — M19: APEX Auto-Correction Loop (MVP local)
=====================================================
Valida o ciclo fim-a-fim, 100% local (sem IA externa): o Sensor
(GuardAwareScanner) emite o sinal → o corretor (FixSuggester) aplica o patch
determinístico → o Sensor revalida e o sinal silencia. É o loop que será
plugado à IA/MCP depois (trocando só o corretor).
"""
from __future__ import annotations

from apex_integration.apex_loop import ApexLoop, ApexLoopReport

# Padrão real do php-src CVE-2019-11043: subtração de ponteiro/comprimento
# sem o guard `pilen > slen` no escopo → underflow → OOB.
_VULN_C = """\
static void handle(void) {
    if (env_path_info) {
        path_info = env_path_info + pilen - slen;
        tflag = (orig != path_info);
    }
}
"""

# Versão já com o guard — o Sensor não deve emitir sinal, loop no-op.
_SAFE_C = """\
static void handle(void) {
    if (env_path_info && pilen > slen) {
        path_info = env_path_info + pilen - slen;
    }
}
"""


def test_T93_loop_silences_the_signal():
    rep = ApexLoop().run(_VULN_C, ext=".c")
    assert isinstance(rep, ApexLoopReport)
    assert len(rep.signals_before) == 1          # Sensor detectou
    assert len(rep.fixes_applied) == 1           # corretor aplicou
    assert rep.silenced_count == 1               # re-scan silenciou
    assert rep.still_firing == []
    assert rep.fully_resolved is True
    # o patch de fato está no código corrigido
    assert "pilen > slen" in rep.patched_source
    assert "auto-fix" in rep.patched_source


def test_T93_noop_on_already_safe_code():
    rep = ApexLoop().run(_SAFE_C, ext=".c")
    assert rep.signals_before == []
    assert rep.fixes_applied == []
    assert rep.fully_resolved is False           # nada a resolver (sem sinais)


def test_T93_report_is_serializable():
    rep = ApexLoop().run(_VULN_C, ext=".c")
    d = rep.to_dict()
    assert d["signals_before"] == 1 and d["silenced"] == 1 and d["fully_resolved"] is True
    assert "fixes" in d["detail"]


def test_T93_taint_signal_included_for_python():
    # o loop também emite os fluxos de taint inter-procedural para Python.
    py = (
        "def view(request):\n"
        "    uid = request.GET['id']\n"
        "    q(uid)\n"
        "def q(x):\n"
        "    cursor.execute('SELECT ' + x)\n"
    )
    rep = ApexLoop().run(py, ext=".py")
    assert len(rep.taint_flows) >= 1
    assert rep.taint_flows[0]["interprocedural"] is True


# ── BZ (v3.49.0): detecção de regressão introduzida pelo próprio auto-fix ──────
# Estes testes existem porque o `before_keys` (comparar findings antes×depois)
# não era dead code — era a base da feature "newly_introduced", que faltava.

def test_T93_clean_fix_introduces_no_regression():
    """Um patch de guard bem-formado não deve criar sinais novos."""
    rep = ApexLoop().run(_VULN_C, ext=".c")
    assert rep.newly_introduced == []      # nada novo criado pelo corretor
    assert rep.regressed is False
    assert "newly_introduced" in rep.to_dict()


def test_T93_regression_makes_not_fully_resolved():
    """
    Se o auto-fix introduz um sinal novo (newly_introduced), o loop NÃO pode
    reportar fully_resolved — mesmo que o alvo original tenha sido silenciado.
    Validado montando o relatório diretamente (unidade da regra de veredito).
    """
    rep = ApexLoopReport(ext=".c")
    rep.signals_before = [{"rule_id": "GA01", "line": 3}]     # havia 1 sinal
    rep.silenced = [{"rule_id": "GA01", "line": 3}]           # foi silenciado
    rep.newly_introduced = [{"rule_id": "GA02", "line": 9}]   # mas o patch criou outro
    assert rep.regressed is True
    assert rep.fully_resolved is False                        # anti-regressão barra o "resolvido"
    assert rep.to_dict()["regressed"] is True
