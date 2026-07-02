"""
Marco 80 — M12: CorpusValidator — validação before/after persistível
=====================================================================
Orquestra M10 (localizar fix) + M11 (dispara-no-vuln / para-no-fix) sobre
pares CVE (parent=vulnerável, fix=corrigido) e produz um registro estruturado
por repo: onde/como/qual-versão + parou de disparar + perpetuados. Fetch
injetável (dict nos testes → offline; raw em produção). Reproduz o padrão real
php/php-src CVE-2019-11043.
"""
from __future__ import annotations

from scan.corpus_validator import CorpusValidator, summarize

_VULN = """\
static void init_request_info(void)
{
    char *path_info;
    if (env_path_info) {
        path_info = env_path_info + pilen - slen;
        tflag = (orig_path_info != path_info);
    }
}
"""
_FIXED = """\
static void init_request_info(void)
{
    char *path_info;
    if (env_path_info) {
        path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : NULL;
        tflag = path_info && (orig_path_info != path_info);
    }
}
"""

_STORE = {
    ("php/php-src", "PAR", "sapi/x.c"): _VULN,
    ("php/php-src", "FIX", "sapi/x.c"): _FIXED,
}

def _fetch(repo, sha, path):
    return _STORE[(repo, sha, path)]


def test_T80_tracked_pair_localized_and_stopped():
    v = CorpusValidator(fetcher=_fetch)
    rec = v.validate_pair("php/php-src", "PAR", "FIX", "sapi/x.c", "CVE-2019-11043")
    assert rec["status"] == "tracked"
    assert rec["fix_localized"] is True          # M10 achou o guard adicionado
    assert rec["m11_stopped_firing"] is True      # M11 disparou no vuln e parou no fix
    assert rec["m11_vuln_findings"] >= 1
    assert rec["m11_fix_findings"] < rec["m11_vuln_findings"]
    # a linha/where está no registro
    assert rec["fix_guards"] and rec["fix_guards"][0]["line"] >= 1


def test_T80_fetch_error_is_captured_not_raised():
    v = CorpusValidator(fetcher=_fetch)
    rec = v.validate_pair("nonexistent/repo", "a", "b", "no.c", "CVE-X")
    assert rec["status"] == "fetch_error"
    assert "error" in rec


def test_T80_validate_all_and_summary():
    v = CorpusValidator(fetcher=_fetch)
    recs = v.validate_all([
        {"repo": "php/php-src", "parent": "PAR", "fix": "FIX", "path": "sapi/x.c", "cve": "CVE-2019-11043"},
    ])
    s = summarize(recs)
    assert s["total"] == 1
    assert s["tracked"] == 1
    assert s["m11_stopped_firing"] == 1
    assert s["fetch_error"] == 0


def test_T80_record_is_json_serializable():
    import json
    v = CorpusValidator(fetcher=_fetch)
    rec = v.validate_pair("php/php-src", "PAR", "FIX", "sapi/x.c", "CVE-2019-11043")
    json.dumps(rec)  # não deve levantar
