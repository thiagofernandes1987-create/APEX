"""
Marco 96 — M24: Corpus Expander / Degradation Composer
======================================================
O `build_degradation` (M24) funde M23 (quando/qual-versão) + M10/M11 (onde/como)
num único `DegradationRecord` que responde as QUATRO perguntas do objetivo do
corpus.  Provado end-to-end nesta sessão com dado 100% real (jinja CVE-2024-22195:
advisory real GHSA-h5c8-rqwp-cp95 + par filters.py 3.1.2→3.1.3 buscado por tag),
resultando em status="complete" e answers_all_four=True.

As fixtures abaixo reproduzem, offline, o padrão REAL desse fix (o xmlattr filter
que passou a `raise ValueError` para chave com espaço + escape).
"""
from __future__ import annotations

from scan.advisory_harvester import AdvisoryRecord
from scan.corpus_expander import (
    build_degradation, expand_batch, DegradationRecord,
)


def _jinja_advisory() -> AdvisoryRecord:
    # recorte real do advisory (GHSA-h5c8-rqwp-cp95 / CVE-2024-22195)
    return AdvisoryRecord(
        ghsa_id="GHSA-h5c8-rqwp-cp95", cve="CVE-2024-22195",
        package="jinja2", ecosystem="PyPI", introduced="0", fixed="3.1.3",
        fix_commit="716795349a41d4983a9a4771f7d883c96ea17be7", fix_tag="3.1.3",
        cwe_ids=["CWE-79"], severity="MODERATE",
    )


# padrão real do fix do xmlattr (Python) — reduzido mas fiel à construção
_VULN = '''\
def do_xmlattr(d, autospace=True):
    rv = " ".join(
        f'{escape(key)}="{escape(value)}"'
        for key, value in d.items()
        if value is not None and not isinstance(value, Undefined)
    )
    return rv
'''

_FIX = '''\
def do_xmlattr(d, autospace=True):
    items = []
    for key, value in d.items():
        if value is None or isinstance(value, Undefined):
            continue
        if _space_re.search(key) is not None:
            raise ValueError(f"Spaces are not allowed in attributes: '{key}'")
        items.append(f'{escape(key)}="{escape(value)}"')
    rv = " ".join(items)
    return rv
'''


def test_T96_complete_record_answers_all_four():
    rec = build_degradation(_jinja_advisory(), _VULN, _FIX, filename="filters.py")
    assert isinstance(rec, DegradationRecord)
    # QUANDO / QUAL-VERSÃO (M23)
    assert "introdução" in rec.when_broke
    assert rec.resolved_in == "versão 3.1.3"
    assert rec.fix_commit.startswith("716795349a41")
    # ONDE / COMO (M10)
    assert rec.where_file == "filters.py"
    assert rec.where_lines  # não-vazio
    assert "input-validation-raise" in rec.how_constructs
    # as 4 perguntas
    assert rec.answers_all_four
    assert rec.status == "complete"


def test_T96_narrative_has_four_answers():
    rec = build_degradation(_jinja_advisory(), _VULN, _FIX, filename="filters.py")
    text = rec.narrative()
    assert "QUANDO quebrou" in text
    assert "EM QUAL versão resolveu" in text
    assert "ONDE quebrou" in text
    assert "COMO" in text
    assert "CVE-2024-22195" in text


def test_T96_metadata_only_when_no_pair():
    # sem par before/after → só metadados do advisory (2 das 4 perguntas).
    rec = build_degradation(_jinja_advisory(), "", "", filename="")
    assert rec.status == "metadata_only"
    assert not rec.answers_all_four
    # ainda responde quando/qual-versão
    assert rec.resolved_in == "versão 3.1.3"


def test_T96_cwe_prefers_advisory():
    rec = build_degradation(_jinja_advisory(), _VULN, _FIX, filename="filters.py")
    assert rec.cwe_ids == ["CWE-79"]  # autoritativo do advisory


def test_T96_never_raises_on_garbage():
    # contrato defensivo: entrada inútil não levanta.
    rec = build_degradation(_jinja_advisory(), "def (:::", "still broken", "x.py")
    assert isinstance(rec, DegradationRecord)


def test_T96_expand_batch_with_injected_fetcher():
    # runner em lote com fetch_pair injetável (offline, sem rede).
    adv = _jinja_advisory()
    seeds = [(adv, "jinja"), (adv, "missing")]

    def fetch_pair(seed):
        if seed == "jinja":
            return (_VULN, _FIX, "filters.py")
        return None  # simula par indisponível

    recs = expand_batch(seeds, fetch_pair)
    assert len(recs) == 2
    assert recs[0].status == "complete" and recs[0].answers_all_four
    assert recs[1].status == "metadata_only"


def test_T96_to_dict_roundtrip_keys():
    rec = build_degradation(_jinja_advisory(), _VULN, _FIX, filename="filters.py")
    d = rec.to_dict()
    for k in ("cve", "when_broke", "resolved_in", "where_file",
              "how_constructs", "answers_all_four", "status",
              "findings_vuln", "findings_fixed"):
        assert k in d


# ── Sprint CS (v3.68.0): validação "parou de disparar?" com painel de detectores ──
# Antes, a validação usava só o M11 (memory-safety) → null para injeção.  Agora o
# painel (M11 + M22 taint + M28 TOCTOU + M20 lite) mede a contagem de achados
# antes/depois. Semântica honesta: stopped_firing = a contagem caiu vuln→fix.

_SQLI_VULN = '''\
def view(request):
    q = request.GET['id']
    cursor.execute('SELECT * FROM u WHERE id=' + q)
'''
_SQLI_FIX = '''\
def view(request):
    q = request.GET['id']
    cursor.execute('SELECT * FROM u WHERE id=%s', (q,))
'''


def _sqli_advisory() -> AdvisoryRecord:
    return AdvisoryRecord(
        ghsa_id="GHSA-sqli", cve="CVE-sqli", package="demo", ecosystem="PyPI",
        introduced="1.0.0", fixed="1.1.0", fix_commit="deadbeef1234",
        fix_tag="1.1.0", cwe_ids=["CWE-89"])


def test_T96_panel_stopped_firing_on_injection():
    # o par SQLi: vuln concatenado dispara (M22 taint), fixed parametrizado não →
    # o painel detecta que PAROU DE DISPARAR (o M11-only dava null aqui).
    rec = build_degradation(_sqli_advisory(), _SQLI_VULN, _SQLI_FIX, "views.py")
    d = rec.to_dict()
    assert d["findings_vuln"] == 1 and d["findings_fixed"] == 0
    assert d["stopped_firing"] is True
    assert d["perpetuated"] is False


def test_T96_panel_uses_m22_not_m7_2_no_fp_on_parameterized():
    # trava a decisão de usar o M22 (com gating SQL arg[0]) e não o M7.2 base:
    # a query parametrizada do fix NÃO pode contar como achado (senão FP).
    from scan.corpus_expander import _count_sensor_findings
    assert _count_sensor_findings(_SQLI_FIX, ".py") == 0


def test_T96_panel_na_when_no_detector_fires():
    # jinja (XSS em filtro) não tem detector do Sensor que dispare → contagem 0
    # nos dois lados → stopped_firing permanece null (N/A honesto, localizado por
    # diff via M10), sem inventar um "sim/não".
    rec = build_degradation(_jinja_advisory(), _VULN, _FIX, filename="filters.py")
    assert rec.findings_vuln == 0 and rec.findings_fixed == 0
    assert rec.stopped_firing is None


# ── DO (v3.90.0): M30 build_degradation_multi (multi-arquivo) ─────────────────
def test_T96_multi_file_picks_localized():
    """build_degradation_multi tenta vários arquivos e escolhe o que localiza."""
    from scan.corpus_expander import build_degradation_multi
    adv = _jinja_advisory()
    no_guard = ("def a():\n    return 1\n", "def a():\n    return 2\n", "a.py")
    with_guard = (_VULN, _FIX, "filters.py")   # tem input-validation-raise
    rec = build_degradation_multi(adv, [no_guard, with_guard])
    assert rec.status == "complete"
    assert "filters.py" in rec.where_file
