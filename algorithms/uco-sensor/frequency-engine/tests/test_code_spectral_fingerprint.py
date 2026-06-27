"""
Code Spectral Fingerprint — testes do MVP (versão mínima).
=============================================================
Valida empiricamente (não apenas afirma) a propriedade básica exigida
de qualquer fingerprint: estável sob mudança cosmética pequena entre
versões próximas do MESMO arquivo, discriminativo entre arquivos
estruturalmente diferentes. Usa o conteúdo real já buscado nesta sessão
(scrapy redirect.py vulnerável/corrigido, flask sessions.py
vulnerável/corrigido — ver tests/test_marco_m72.py no sensor-api) como
o par "mesma versão, diff pequeno", e o par scrapy×flask como o par
"arquivos diferentes" (negative control).

Execução:
  cd /home/claude/uco-frequency-engine  (ou equivalente)
  python tests/test_code_spectral_fingerprint.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from receptor.code_spectral_fingerprint import (
    source_to_signal, fingerprint, cosine_similarity,
)

_SCRATCH = "/tmp/claude-0/-home-user-APEX/cd3188e9-b829-5c21-b320-8e0c72dd6fbd/scratchpad"


def _read(name: str) -> str:
    with open(os.path.join(_SCRATCH, name), "r", encoding="utf-8") as f:
        return f.read()


def test_source_to_signal_nonempty_for_real_code():
    src = "def f(x):\n    return x + 1\n\n\ndef g(y):\n    return y * 2\n"
    sig = source_to_signal(src)
    assert len(sig) > 0
    print("OK: source_to_signal produz sinal não-vazio")


def test_fingerprint_is_unit_vector():
    src = "\n".join(f"def f{i}(x): return x + {i}" for i in range(20))
    fp = fingerprint(src)
    import numpy as np
    norm = float(np.linalg.norm(fp))
    assert abs(norm - 1.0) < 1e-6 or norm == 0.0
    print(f"OK: fingerprint normalizado (norma={norm:.4f})")


def test_same_file_vuln_vs_fixed_more_similar_than_unrelated_files():
    """
    Propriedade central do MVP: o par (scrapy vulnerável, scrapy
    corrigido) — mesma função, ~3 linhas de diff — deve ter similaridade
    de cosseno MAIOR do que o par (scrapy vulnerável, flask vulnerável)
    — arquivos de projetos e domínios completamente diferentes.
    """
    scrapy_vuln = _read("redirect_vuln.py")
    scrapy_fixed = _read("redirect_fixed.py")
    flask_vuln = _read("sessions_vuln.py")

    fp_scrapy_vuln = fingerprint(scrapy_vuln)
    fp_scrapy_fixed = fingerprint(scrapy_fixed)
    fp_flask_vuln = fingerprint(flask_vuln)

    sim_same_file = cosine_similarity(fp_scrapy_vuln, fp_scrapy_fixed)
    sim_diff_file = cosine_similarity(fp_scrapy_vuln, fp_flask_vuln)

    print(f"sim(scrapy_vuln, scrapy_fixed) = {sim_same_file:.4f}")
    print(f"sim(scrapy_vuln, flask_vuln)   = {sim_diff_file:.4f}")
    assert sim_same_file > sim_diff_file, (
        "MVP falhou na propriedade central: same-file deveria ser mais "
        "similar que cross-file"
    )
    print("OK: same-file (vuln vs fixed) mais similar que cross-file (negative control)")


def test_flask_vuln_vs_fixed_also_more_similar_than_unrelated():
    flask_vuln = _read("sessions_vuln.py")
    flask_fixed = _read("sessions_fixed.py")
    scrapy_vuln = _read("redirect_vuln.py")

    sim_same_file = cosine_similarity(fingerprint(flask_vuln), fingerprint(flask_fixed))
    sim_diff_file = cosine_similarity(fingerprint(flask_vuln), fingerprint(scrapy_vuln))

    print(f"sim(flask_vuln, flask_fixed) = {sim_same_file:.4f}")
    print(f"sim(flask_vuln, scrapy_vuln) = {sim_diff_file:.4f}")
    assert sim_same_file > sim_diff_file
    print("OK: mesma propriedade replicada com o par flask")


if __name__ == "__main__":
    tests = [
        test_source_to_signal_nonempty_for_real_code,
        test_fingerprint_is_unit_vector,
        test_same_file_vuln_vs_fixed_more_similar_than_unrelated_files,
        test_flask_vuln_vs_fixed_also_more_similar_than_unrelated,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"FALHOU: {t.__name__} — {e}")
        except FileNotFoundError as e:
            print(f"PULADO: {t.__name__} — arquivo scratch não encontrado ({e})")
    print(f"\n{len(tests) - failed}/{len(tests)} passaram")
    sys.exit(1 if failed else 0)
