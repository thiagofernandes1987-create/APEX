"""
Marco 99 — M27: Fix File Locator & Auto-Pair Builder
====================================================
O M27 fecha a AUTOMAÇÃO da coleta do corpus: escolhe o arquivo-fonte alterado
pelo fix, deriva a versão anterior (lado vulnerável) e monta o par before/after
por tag — sem a API de commits.  Provado nesta sessão end-to-end (WebFetch lê os
arquivos do commit; raw busca as duas tags).
"""
from __future__ import annotations

from scan.fix_file_locator import (
    pick_source_file, prior_version, tag_candidates, build_pair,
)


def test_T99_pick_source_file_prefers_code_over_test_and_docs():
    files = ["CHANGES.rst", "tests/test_filters.py", "src/jinja2/filters.py"]
    assert pick_source_file(files) == "src/jinja2/filters.py"


def test_T99_pick_source_file_ignores_pure_noise():
    # nenhum código-fonte → None (não escolhe doc/changelog como fonte)
    assert pick_source_file(["CHANGELOG.md", "docs/index.rst"]) is None


def test_T99_pick_source_file_shallowest_wins():
    files = ["a/b/c/deep.py", "top.py"]
    assert pick_source_file(files) == "top.py"


def test_T99_prior_version_decrements_patch():
    assert prior_version("3.1.3") == "3.1.2"
    assert prior_version("2.31.0") == "2.30.0"
    assert prior_version("2.2.3") == "2.2.2"
    assert prior_version("1.26.5") == "1.26.4"


def test_T99_prior_version_edge_cases():
    assert prior_version("") == ""
    assert prior_version("garbage") == ""
    # (DP v3.93.0/D9) mantém 3 componentes quando a corrigida tinha patch.
    assert prior_version("1.0.0") == "0.0.0"
    assert prior_version("2.0") == "1.0"


def test_T99_tag_candidates_both_prefixes():
    assert tag_candidates("3.1.3") == ["3.1.3", "v3.1.3"]
    assert tag_candidates("") == []


def test_T99_build_pair_with_injected_fetcher():
    # fetcher offline: devolve conteúdo distinto por (ref, path).
    store = {
        ("acme/lib", "3.1.3", "src/x.py"): "def f(): return safe()\n",
        ("acme/lib", "3.1.2", "src/x.py"): "def f(): return unsafe()\n",
    }
    def raw_fetch(repo, ref, path):
        return store.get((repo, ref, path))
    pair = build_pair("acme/lib", "3.1.3", "deadbeef", "src/x.py", raw_fetch)
    assert pair is not None
    vuln, fixed, fn = pair
    assert "unsafe" in vuln and "safe" in fixed and fn == "x.py"


def test_T99_build_pair_none_when_side_missing():
    def raw_fetch(repo, ref, path):
        return "only fixed" if ref in ("3.1.3", "v3.1.3") else None
    assert build_pair("r", "3.1.3", "sha", "x.py", raw_fetch) is None


def test_T99_build_pair_tries_v_prefix():
    store = {("r", "v2.31.0", "s.py"): "fixed", ("r", "v2.30.0", "s.py"): "vuln"}
    def raw_fetch(repo, ref, path):
        return store.get((repo, ref, path))
    pair = build_pair("r", "2.31.0", "sha", "s.py", raw_fetch)
    assert pair is not None and pair[0] == "vuln" and pair[1] == "fixed"


# ── D5: path relocation entre versões (src/ toggle) ──────────────────────────

def test_T99_path_candidates_toggles_src_prefix():
    from scan.fix_file_locator import path_candidates
    assert path_candidates("src/requests/adapters.py") == [
        "src/requests/adapters.py", "requests/adapters.py"]
    assert path_candidates("requests/adapters.py") == [
        "requests/adapters.py", "src/requests/adapters.py"]
    assert path_candidates("") == []


def test_T99_build_pair_monorepo_at_tag_format():
    # gradio usa `gradio@4.11.0` (monorepo). build_pair deve tentar `<nome>@<v>`.
    store = {
        ("gradio-app/gradio", "gradio@4.11.0", "gradio/utils.py"): "fixed\n",
        ("gradio-app/gradio", "gradio@4.10.0", "gradio/utils.py"): "vuln\n",
    }
    def raw_fetch(repo, ref, path):
        return store.get((repo, ref, path))
    pair = build_pair("gradio-app/gradio", "4.11.0", "sha", "gradio/utils.py",
                      raw_fetch, prior_version_hint="4.10.0")
    assert pair is not None and pair[0] == "vuln\n" and pair[1] == "fixed\n"


def test_T99_build_pair_survives_src_layout_migration():
    # Reproduz o caso real requests CVE-2024-35195: fix em src/requests/...,
    # tag anterior tem o arquivo em requests/... (sem src/).
    store = {
        ("psf/requests", "v2.32.0", "src/requests/adapters.py"): "fixed body\n",
        ("psf/requests", "v2.31.0", "requests/adapters.py"): "vuln body\n",
    }
    def raw_fetch(repo, ref, path):
        return store.get((repo, ref, path))
    pair = build_pair("psf/requests", "2.32.0", "sha",
                      "src/requests/adapters.py", raw_fetch)
    assert pair is not None
    vuln, fixed, fn = pair
    assert vuln == "vuln body\n" and fixed == "fixed body\n" and fn == "adapters.py"
