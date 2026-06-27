"""
Marco 71 — Sprint AI (loop pesado): abertura de C/C++ (C01-C04) para curl
==========================================================================

Continuação do loop iterativo de fechamento de BLIND_SPOT por repositório.
curl (CVE-2023-38545, SOCKS5 heap buffer overflow em ``lib/socks.c``) era
um dos 9 casos sem regra SAST. C01 fecha esse caso:

- O bug real não é a presença de uma chamada perigosa isolada, é a
  *ausência* de um ``return``/abort logo após o guard
  ``hostname_len > 255`` — o ``do_SOCKS5()`` vulnerável (sha real
  ``09e25b9d``) apenas loga e cai para
  ``memcpy(&socksreq[len], sx->hostname, hostname_len)`` contra um buffer
  fixo de ~256 bytes. O fix (sha real ``fb4415d8``) substitui o log por
  ``failf(...); return CURLPX_LONG_HOSTNAME;``.
- Regra cross-line (mesmo padrão de RS01/CS06): ``_scan_c_socks_overflow``
  dispara só se existir ``memcpy(..., hostname_len)`` perigoso E o guard
  ``hostname_len > 255`` existir E **nenhum** ``return`` aparecer nos
  ~200 caracteres seguintes ao guard.
- Validado empiricamente (fora deste arquivo de teste, via fetch direto
  do GitHub) contra o ``lib/socks.c`` real nos dois SHAs: dispara na
  versão vulnerável, silencioso na versão corrigida.
- C02-C04 são regras genéricas de triagem (strcpy/strcat/gets,
  sprintf, system()/popen() com concatenação) — não amarradas a um CVE
  específico, cobrindo classes comuns de C memory-safety/injection.

Reclassifica curl de BLIND_SPOT para SIGNAL em
``paper/AF_consolidated_timeline.md``.
"""
from __future__ import annotations

from sast.multilang_scanner import scan_multilang, rule_count


def _ids(src: str, ext: str = ".c") -> list:
    return [f.rule_id for f in scan_multilang(src, ext).findings]


# ── C01 (curl CVE-2023-38545 shape) ─────────────────────────────────────────

def test_TAM10_c01_fires_on_log_and_fallthrough_shape():
    src = (
        "static CURLproxycode do_SOCKS5(struct Curl_cfilter *cf, struct Curl_easy *data) {\n"
        "  if(hostname_len > 255) {\n"
        "    infof(data, \"SOCKS5: hostname too long, ignoring\");\n"
        "    socks5_resolve_local = TRUE;\n"
        "  }\n"
        "  len += hostname_len;\n"
        "  socksreq[len++] = (unsigned char)(sx->remote_port >> 8);\n"
        "  socksreq[len++] = (unsigned char)(sx->remote_port & 0xff);\n"
        "  memcpy(&socksreq[len], sx->hostname, hostname_len);\n"
        "  len += hostname_len;\n"
        "}\n"
    )
    assert "C01" in _ids(src)


def test_TAM11_c01_silent_when_guard_returns():
    src = (
        "static CURLproxycode do_SOCKS5(struct Curl_cfilter *cf, struct Curl_easy *data) {\n"
        "  if(hostname_len > 255) {\n"
        "    failf(data, \"SOCKS5: hostname too long\");\n"
        "    return CURLPX_LONG_HOSTNAME;\n"
        "  }\n"
        "  memcpy(&socksreq[len], sx->hostname, hostname_len);\n"
        "  return CURLPX_OK;\n"
        "}\n"
    )
    assert "C01" not in _ids(src)


def test_TAM12_c01_silent_without_dangerous_memcpy():
    src = (
        "if(hostname_len > 255) {\n"
        "  infof(data, \"too long\");\n"
        "}\n"
        "memcpy(buf, other, other_len);\n"
    )
    assert "C01" not in _ids(src)


def test_TAM13_c01_silent_without_len_guard_at_all():
    src = "memcpy(&socksreq[len], sx->hostname, hostname_len);\n"
    assert "C01" not in _ids(src)


# ── C02-C04 (generic triage) ────────────────────────────────────────────────

def test_TAM14_c02_strcpy_unbounded():
    assert "C02" in _ids("strcpy(dst, src);\n")


def test_TAM15_c03_sprintf_unbounded():
    assert "C03" in _ids("sprintf(buf, \"%s\", input);\n")


def test_TAM16_c04_system_with_concatenation():
    assert "C04" in _ids("system(strcat(cmd, user_input));\n")


def test_TAM17_c_silent_on_safe_code():
    src = "snprintf(buf, sizeof(buf), \"%s\", input);\n"
    assert _ids(src) == []


# ── Dispatch / rule count ───────────────────────────────────────────────────

def test_TAM18_unsupported_ext_still_empty():
    assert scan_multilang("x = 1", ".py").findings == []


def test_TAM19_rule_count_reflects_c_rules():
    assert rule_count() == 48
