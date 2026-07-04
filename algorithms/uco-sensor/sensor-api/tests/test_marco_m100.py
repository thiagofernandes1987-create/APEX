"""
Marco 100 — M28: TOCTOU / Race Detector (CWE-367)
=================================================
O `TOCTOUDetector` (M28) cobre a classe de RACE que M10 (guard-por-diff) e M11
(memory-safety) não pegavam: Time-Of-Check to Time-Of-Use em recurso de FS —
"checar" um caminho e depois "usar" o MESMO caminho de forma não-atômica,
deixando janela de corrida (comum em código gerado por IA).

Disciplina anti-FP validada (um FP afirmado é pior que um miss):
  * dispara só com a MESMA variável no check e no use, nessa ordem;
  * NÃO dispara em abertura atômica (`open(p,'x')`, `os.open(...,O_EXCL)`);
  * NÃO dispara em variáveis diferentes, use-antes-do-check, ou reatribuição
    da variável entre check e use.
"""
from __future__ import annotations

from sast.toctou import TOCTOUDetector, TOCTOUFinding


def _scan(code: str):
    return TOCTOUDetector().scan(code)


def test_T100_classic_exists_then_open_fires():
    fs = _scan(
        "import os\n"
        "def save(p):\n"
        "    if os.path.exists(p):\n"
        "        log('e')\n"
        "    with open(p, 'w') as f:\n"
        "        f.write('x')\n")
    assert len(fs) == 1
    f = fs[0]
    assert isinstance(f, TOCTOUFinding)
    assert f.cwe_id == "CWE-367" and f.rule_id == "SAST060"
    assert f.var == "p"
    assert f.check_line == 3 and f.use_line == 5


def test_T100_access_then_remove_fires():
    fs = _scan(
        "import os\n"
        "def rm(target):\n"
        "    if os.access(target, os.W_OK):\n"
        "        os.remove(target)\n")
    assert len(fs) == 1
    assert fs[0].var == "target" and fs[0].use_call == "os.remove"


def test_T100_atomic_open_x_is_safe():
    # open(p, 'x') é criação atômica exclusiva → o PADRÃO-FIX, não dispara.
    fs = _scan(
        "import os\n"
        "def save(p):\n"
        "    if os.path.exists(p):\n"
        "        log('e')\n"
        "    with open(p, 'x') as f:\n"
        "        f.write('x')\n")
    assert fs == []


def test_T100_os_open_o_excl_is_safe():
    fs = _scan(
        "import os\n"
        "def save(p):\n"
        "    if os.path.exists(p):\n"
        "        pass\n"
        "    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)\n")
    assert fs == []


def test_T100_different_vars_no_fire():
    fs = _scan(
        "import os\n"
        "def cp(a, b):\n"
        "    if os.path.exists(a):\n"
        "        open(b, 'w').close()\n")
    assert fs == []


def test_T100_use_before_check_no_fire():
    fs = _scan(
        "import os\n"
        "def f(p):\n"
        "    open(p, 'w').close()\n"
        "    if os.path.exists(p):\n"
        "        pass\n")
    assert fs == []


def test_T100_reassignment_between_suppresses():
    # a var é sanitizada/reatribuída entre check e use → recurso mudou → não dispara.
    fs = _scan(
        "import os\n"
        "def f(p):\n"
        "    if os.path.exists(p):\n"
        "        p = sanitize(p)\n"
        "    open(p, 'w').close()\n")
    assert fs == []


def test_T100_syntax_error_returns_empty():
    assert _scan("def (:::") == []


def test_T100_no_check_no_fire():
    # abrir sem checar não é TOCTOU (não há time-of-check).
    fs = _scan(
        "def f(p):\n"
        "    open(p, 'w').close()\n")
    assert fs == []


def test_T100_module_level_scope():
    # TOCTOU em script sem função (nível de módulo) também é detectado.
    fs = _scan(
        "import os\n"
        "if os.path.isfile(cfg):\n"
        "    os.remove(cfg)\n")
    assert len(fs) == 1 and fs[0].function == "<module>"


def test_T100_finding_to_dict_message():
    fs = _scan(
        "import os\n"
        "def f(p):\n"
        "    if os.path.exists(p):\n"
        "        open(p, 'w').close()\n")
    d = fs[0].to_dict()
    assert d["cwe_id"] == "CWE-367"
    assert "janela de corrida" in d["message"]
