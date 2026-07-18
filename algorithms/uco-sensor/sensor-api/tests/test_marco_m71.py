"""
Marco 71 — loop pesado: abertura de C/C++ fecha curl (C01-C04) e git (C05)
============================================================================

Continuação do loop iterativo de fechamento de BLIND_SPOT por repositório.
curl (CVE-2023-38545, SOCKS5 heap buffer overflow em ``lib/socks.c``) e git
(CVE-2021-21300, symlink TOCTOU em ``unpack-trees.c``) eram 2 dos 9 casos
sem regra SAST. C01 e C05 fecham esses casos.

git/CVE-2021-21300: o bug real é a ausência de
``invalidate_lstat_cache()`` em qualquer lugar do arquivo que define
``check_updates()`` — a função vulnerável (sha real ``0d58fef5``) confia
em um lstat cache potencialmente obsoleto ao decidir o que escrever no
worktree, permitindo uma corrida de troca de symlink entre o preenchimento
do cache e a escrita real. O fix (sha real ``22539ec3``) adiciona uma
única chamada ``invalidate_lstat_cache();`` no topo de ``check_updates()``.
Mesmo padrão whole-file presence/absence de CS06. Validado contra o
``unpack-trees.c`` real nos dois SHAs: dispara na versão vulnerável,
silencioso na corrigida.

curl/CVE-2023-38545 — detalhes abaixo (regra C01):

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


# ── C05 (git CVE-2021-21300 shape) ──────────────────────────────────────────

def test_TAM20_c05_fires_when_check_updates_never_invalidates_cache():
    src = (
        "static int check_updates(struct unpack_trees_options *o)\n"
        "{\n"
        "    int ret;\n"
        "    struct progress *progress;\n"
        "    progress = get_progress(o);\n"
        "    if (o->update)\n"
        "        git_attr_set_direction(GIT_ATTR_CHECKOUT, index);\n"
        "    return ret;\n"
        "}\n"
    )
    assert "C05" in _ids(src)


def test_TAM21_c05_silent_when_cache_invalidated_anywhere_in_file():
    src = (
        "static int check_updates(struct unpack_trees_options *o)\n"
        "{\n"
        "    invalidate_lstat_cache();\n"
        "    if (o->update)\n"
        "        git_attr_set_direction(GIT_ATTR_CHECKOUT, index);\n"
        "    return 0;\n"
        "}\n"
    )
    assert "C05" not in _ids(src)


def test_TAM22_c05_silent_without_check_updates_definition():
    src = "static int some_other_fn(struct unpack_trees_options *o)\n{\n    return 0;\n}\n"
    assert "C05" not in _ids(src)


def test_TAM23_c05_silent_on_prototype_declaration_only():
    src = "static int check_updates(struct unpack_trees_options *o);\n"
    assert "C05" not in _ids(src)


# ── GO11 (golang/go CVE-2023-29404 shape) ───────────────────────────────────

def test_TAM24_go11_fires_on_real_vulnerable_optional_arg_regex():
    src = 're(`-Wl,-O([^@,\\-][^,]*)?`),\n'
    assert "GO11" in _ids(src, ".go")


def test_TAM25_go11_silent_on_real_fixed_mandatory_arg_regex():
    src = "re(`-Wl,-O[0-9]+`),\n"
    assert "GO11" not in _ids(src, ".go")


def test_TAM26_go11_fires_on_vulnerable_e_flag_star_quantifier():
    src = "re(`-Wl,-e[=,][a-zA-Z0-9]*`),\n"
    assert "GO11" in _ids(src, ".go")


def test_TAM27_go11_silent_on_fixed_e_flag_plus_quantifier():
    src = "re(`-Wl,-e[=,][a-zA-Z0-9]+`),\n"
    assert "GO11" not in _ids(src, ".go")


def test_TAM28_go11_fires_on_vulnerable_r_flag_without_optional_comma():
    src = "re(`-Wl,-R([^@\\-][^,@]*$)`),\n"
    assert "GO11" in _ids(src, ".go")


def test_TAM29_go11_silent_on_fixed_r_flag_with_optional_comma():
    src = "re(`-Wl,-R,?([^@\\-,][^,@]*$)`),\n"
    assert "GO11" not in _ids(src, ".go")


def test_TAM30_go11_silent_on_unrelated_go_code():
    src = "func main() {\n\tfmt.Println(\"hi\")\n}\n"
    assert "GO11" not in _ids(src, ".go")


# ── GO12 (etcd CVE-2021-28235 shape) ────────────────────────────────────────

def test_TAM31_go12_fires_when_authenticate_never_clears_password():
    src = (
        "func (s *EtcdServer) Authenticate(ctx context.Context, r *pb.AuthenticateRequest) (*pb.AuthenticateResponse, error) {\n"
        "\tlg := s.Logger()\n"
        "\tvar resp proto.Message\n"
        "\tfor {\n"
        "\t\tcheckedRevision, err := s.AuthStore().CheckPassword(r.Name, r.Password)\n"
        "\t\tif err != nil {\n"
        "\t\t\treturn nil, err\n"
        "\t\t}\n"
        "\t\tbreak\n"
        "\t}\n"
        "\treturn resp.(*pb.AuthenticateResponse), nil\n"
        "}\n"
        "\n"
        "func (s *EtcdServer) UserAdd(ctx context.Context, r *pb.AuthUserAddRequest) (*pb.AuthUserAddResponse, error) {\n"
        "\tr.Password = \"\"\n"
        "\treturn nil, nil\n"
        "}\n"
    )
    assert "GO12" in _ids(src, ".go")


def test_TAM32_go12_silent_when_authenticate_clears_password_via_defer():
    src = (
        "func (s *EtcdServer) Authenticate(ctx context.Context, r *pb.AuthenticateRequest) (*pb.AuthenticateResponse, error) {\n"
        "\tlg := s.Logger()\n"
        "\tdefer func() {\n"
        "\t\tif r != nil {\n"
        "\t\t\tr.Password = \"\"\n"
        "\t\t}\n"
        "\t}()\n"
        "\tvar resp proto.Message\n"
        "\tfor {\n"
        "\t\tcheckedRevision, err := s.AuthStore().CheckPassword(r.Name, r.Password)\n"
        "\t\tif err != nil {\n"
        "\t\t\treturn nil, err\n"
        "\t\t}\n"
        "\t\tbreak\n"
        "\t}\n"
        "\treturn resp.(*pb.AuthenticateResponse), nil\n"
        "}\n"
    )
    assert "GO12" not in _ids(src, ".go")


def test_TAM33_go12_silent_without_authenticate_definition():
    src = "func (s *EtcdServer) UserAdd(ctx context.Context, r *pb.AuthUserAddRequest) (*pb.AuthUserAddResponse, error) {\n\tr.Password = \"\"\n\treturn nil, nil\n}\n"
    assert "GO12" not in _ids(src, ".go")


def test_TAM34_go12_silent_when_authenticate_does_not_check_password():
    src = (
        "func (s *EtcdServer) Authenticate(ctx context.Context, r *pb.AuthenticateRequest) (*pb.AuthenticateResponse, error) {\n"
        "\treturn nil, nil\n"
        "}\n"
    )
    assert "GO12" not in _ids(src, ".go")


# ── Dispatch / rule count ───────────────────────────────────────────────────

def test_TAM18_unsupported_ext_still_empty():
    assert scan_multilang("x = 1", ".py").findings == []


def test_TAM19_rule_count_reflects_c_rules():
    assert rule_count() == 52
