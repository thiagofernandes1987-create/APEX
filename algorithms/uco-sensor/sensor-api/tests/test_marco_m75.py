"""
Marco 75 — M9.2: AST Structural Diff (tree-sitter) — sensibilidade real
=======================================================================
Resposta à barreira documentada na Sprint AQ: o eixo SAST CVE-anchored
before/after, para as linguagens Tier-2 *regex* (C/C++/PHP/Ruby/C#),
podia reportar **delta = 0** num fix genuíno de uma linha — porque o
``GenericRegexAdapter`` tem piso de granularidade mais grosseiro que um
operador adicionado.  O caso concreto: ``php/php-src`` CVE-2019-11043
(``sapi/fpm/fpm/fpm_main.c``), onde o fix adiciona ``pilen > slen`` e um
``path_info &&`` — e o ``CAdapter`` regex dá delta zero em todos os 9
canais UCO.

O módulo ``lang_adapters/ast_structural_diff.py`` (M9.2) corrige isso
com um parse tree-sitter real e um diff estrutural por tipo de nó.
Estes testes pinam:

1. Degradação graciosa: linguagem sem gramática → ``available() == False``,
   ``signature`` / ``diff`` retornam ``None`` (mesmo contrato de
   "nunca quebra" do ``tree_sitter_bridge``).
2. Diff idêntico → churn 0 (não detecta mudança onde não há).
3. Um bounds-check de uma linha adicionado a uma função C produz
   ``churn > 0`` E move um operador de segurança (``>``), exatamente o
   sinal que o regex perdia.
4. Reprodução fiel (offline) do padrão php-src: a transformação ternária
   + null-guard registra ``&&`` e ``>`` no ``security_operator_delta``.
"""
from __future__ import annotations

import pytest

from lang_adapters.ast_structural_diff import (
    ASTStructuralDiff,
    ASTSignature,
    ASTDiff,
)

# ── fixtures C (offline, sem rede) ────────────────────────────────────────────

# Antes: sem checagem de limite (padrão da classe de bugs CVE-2019-11043).
_C_BEFORE = """\
static void init_request_info(void)
{
    int path_info;
    if (env_path_info) {
        path_info = env_path_info + pilen - slen;
        tflag = (orig_path_info != path_info);
    }
}
"""

# Depois: bounds-check `pilen > slen` + null-guard `path_info &&` adicionados.
_C_AFTER = """\
static void init_request_info(void)
{
    int path_info;
    if (env_path_info) {
        path_info = (env_path_info && pilen > slen) ? env_path_info + pilen - slen : 0;
        tflag = path_info && (orig_path_info != path_info);
    }
}
"""


def _c_differ() -> ASTStructuralDiff:
    differ = ASTStructuralDiff("c")
    if not differ.available():
        pytest.skip("tree-sitter C grammar não instalada neste ambiente")
    return differ


# ── 1. degradação graciosa ────────────────────────────────────────────────────

def test_T75_unavailable_language_degrades():
    differ = ASTStructuralDiff("a-language-that-does-not-exist")
    assert differ.available() is False
    assert differ.signature("anything") is None
    assert differ.diff("a", "b") is None


def test_T75_diff_returns_none_when_unavailable_not_raises():
    # Contrato: nunca levanta — sempre None no modo indisponível.
    differ = ASTStructuralDiff("cobol-not-bundled")
    assert differ.diff("MOVE A TO B", "MOVE A TO C") is None


# ── 2. identidade → churn zero ────────────────────────────────────────────────

def test_T75_identical_source_zero_churn():
    differ = _c_differ()
    d = differ.diff(_C_BEFORE, _C_BEFORE)
    assert isinstance(d, ASTDiff)
    assert d.churn == 0
    assert d.detected is False
    assert d.security_relevant is False


# ── 3. signature básica ───────────────────────────────────────────────────────

def test_T75_signature_shape():
    differ = _c_differ()
    sig = differ.signature(_C_BEFORE)
    assert isinstance(sig, ASTSignature)
    assert sig.total_nodes > 0
    assert sig.max_depth > 0
    # o corpo da função tem ao menos uma if_statement
    assert sig.node_types.get("if_statement", 0) >= 1


# ── 4. bounds-check de 1 linha é detectado (o que o regex perdia) ─────────────

def test_T75_one_line_bounds_check_detected():
    differ = _c_differ()
    d = differ.diff(_C_BEFORE, _C_AFTER)
    assert d is not None
    # churn não-zero — a estrutura AST mudou, ao contrário do delta=0 regex
    assert d.churn > 0
    assert d.detected is True


def test_T75_security_operator_delta_captures_bounds_check():
    differ = _c_differ()
    d = differ.diff(_C_BEFORE, _C_AFTER)
    assert d is not None
    # o operador `>` do bounds-check `pilen > slen` aparece no delta
    assert d.security_operator_delta.get(">", 0) >= 1
    # e o `&&` do null-guard / da condição composta também
    assert d.security_operator_delta.get("&&", 0) >= 1
    assert d.security_relevant is True


def test_T75_binary_expression_count_increases():
    differ = _c_differ()
    sig_b = differ.signature(_C_BEFORE)
    sig_a = differ.signature(_C_AFTER)
    assert sig_a.node_types["binary_expression"] > sig_b.node_types["binary_expression"]


# ── 5. multilíngue: gramáticas adicionais carregam (quando presentes) ─────────

@pytest.mark.parametrize("lang,snippet", [
    ("cpp", "int main(){ if (a && b > c) return 1; return 0; }"),
    ("php", "<?php if ($a && $b > $c) { echo 1; }"),
    ("ruby", "def f(a,b)\n  return 1 if a && b > 0\n  0\nend\n"),
    ("csharp", "class C { int F(int a,int b){ if (a > 0 && b > a) return 1; return 0; } }"),
])
def test_T75_additional_grammars_parse(lang, snippet):
    differ = ASTStructuralDiff(lang)
    if not differ.available():
        pytest.skip(f"gramática tree-sitter {lang} não instalada")
    sig = differ.signature(snippet)
    assert sig is not None
    assert sig.total_nodes > 0
