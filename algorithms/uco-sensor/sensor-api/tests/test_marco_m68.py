"""
Marco 68 — Sprint AG: JS11, JV11, PHP01-05, CS01-05, RS01
==========================================================

Continuing the per-case audit of remaining blind spots from
``paper/corpus_runs/AF_consolidated_timeline.md`` (task #57) per the
6-way parallel CVE investigation. Adds:

- ``JS11`` — axios CVE-2023-45857 (XSRF token sent cross-origin via
  ``withCredentials || isURLSameOrigin`` bypass). Validated against the
  real ``axios/axios`` vulnerable (``7d45ab2e``) and fixed (``96ee232b``)
  ``lib/adapters/xhr.js``.
- ``JV11`` — Spring4Shell CVE-2022-22965 (bean property denylisted by
  name string instead of by type). Validated against the real
  ``spring-projects/spring-framework`` vulnerable (``1627f57f``) and
  fixed (``002546b3``) ``CachedIntrospectionResults.java``.
- ``RS01`` — first Rust rule, opens Rust SAST support. tokio
  CVE-2023-22466 (``ServerOptions::pipe_mode`` overwrites a bit-field
  that ``reject_remote_clients`` preserves via ``bool_flag!``).
  Validated against the real ``tokio-rs/tokio`` vulnerable
  (``5c76d070``) and fixed (``9241c3ed``) ``named_pipe.rs``.
- ``PHP01-05`` / ``CS01-05`` — opens PHP and C# SAST support with 4
  generic core rules each plus one CVE-motivated low-confidence triage
  rule (PHP05 / CS05), per the Laravel CVE-2026-48041 and dotnet/runtime
  CVE-2026-45491 investigation.
"""
from __future__ import annotations

from sast.multilang_scanner import scan_multilang


def _ids(src: str, ext: str) -> list:
    return [f.rule_id for f in scan_multilang(src, ext).findings]


# ── JS11 ────────────────────────────────────────────────────────────────────

def test_TAK01_js11_detects_real_axios_vulnerable_shape():
    src = (
        "const xsrfValue = (config.withCredentials || isURLSameOrigin(fullPath))\n"
        "  && config.xsrfCookieName && cookies.read(config.xsrfCookieName);\n"
    )
    assert "JS11" in _ids(src, ".js")


def test_TAK02_js11_silent_on_real_axios_fixed_shape():
    src = (
        "const xsrfValue = isURLSameOrigin(fullPath) && config.xsrfCookieName "
        "&& cookies.read(config.xsrfCookieName);\n"
    )
    assert "JS11" not in _ids(src, ".js")


def test_TAK03_js11_silent_when_no_withcredentials_disjunction():
    src = "const ok = isSameOrigin(url) && hasToken;\n"
    assert "JS11" not in _ids(src, ".js")


# ── JV11 ────────────────────────────────────────────────────────────────────

def test_TAK04_jv11_detects_real_spring4shell_vulnerable_shape():
    src = (
        'if (Class.class == beanClass &&\n'
        '        ("classLoader".equals(pd.getName()) ||  "protectionDomain".equals(pd.getName()))) {\n'
        '    continue;\n'
        '}\n'
    )
    assert "JV11" in _ids(src, ".java")


def test_TAK05_jv11_silent_on_real_spring4shell_fixed_shape():
    src = (
        'if (Class.class == beanClass && (!"name".equals(pd.getName()) '
        '&& !pd.getName().endsWith("Name"))) {\n'
        '    continue;\n'
        '}\n'
        'if (pd.getPropertyType() != null && (ClassLoader.class.isAssignableFrom(pd.getPropertyType())\n'
        '        || ProtectionDomain.class.isAssignableFrom(pd.getPropertyType()))) {\n'
        '    continue;\n'
        '}\n'
    )
    assert "JV11" not in _ids(src, ".java")


def test_TAK06_jv11_silent_on_unrelated_name_equals():
    src = 'if ("email".equals(pd.getName())) { skip(); }\n'
    assert "JV11" not in _ids(src, ".java")


# ── RS01 (opens Rust) ────────────────────────────────────────────────────────

def test_TAK07_rs01_detects_real_tokio_vulnerable_shape():
    src = (
        "impl ServerOptions {\n"
        "    pub fn pipe_mode(&mut self, pipe_mode: PipeMode) -> &mut Self {\n"
        "        self.pipe_mode = match pipe_mode {\n"
        "            PipeMode::Byte => winbase::PIPE_TYPE_BYTE,\n"
        "            PipeMode::Message => winbase::PIPE_TYPE_MESSAGE,\n"
        "        };\n"
        "        self\n"
        "    }\n"
        "    pub fn reject_remote_clients(&mut self, reject: bool) -> &mut Self {\n"
        "        bool_flag!(self.pipe_mode, reject, winbase::PIPE_REJECT_REMOTE_CLIENTS);\n"
        "        self\n"
        "    }\n"
        "}\n"
    )
    findings = scan_multilang(src, ".rs").findings
    rs01 = [f for f in findings if f.rule_id == "RS01"]
    assert len(rs01) == 1
    assert rs01[0].line == 3


def test_TAK08_rs01_silent_on_real_tokio_fixed_shape():
    src = (
        "impl ServerOptions {\n"
        "    pub fn pipe_mode(&mut self, pipe_mode: PipeMode) -> &mut Self {\n"
        "        let is_msg = matches!(pipe_mode, PipeMode::Message);\n"
        "        bool_flag!(self.pipe_mode, is_msg, winbase::PIPE_TYPE_MESSAGE);\n"
        "        self\n"
        "    }\n"
        "    pub fn reject_remote_clients(&mut self, reject: bool) -> &mut Self {\n"
        "        bool_flag!(self.pipe_mode, reject, winbase::PIPE_REJECT_REMOTE_CLIENTS);\n"
        "        self\n"
        "    }\n"
        "}\n"
    )
    assert "RS01" not in _ids(src, ".rs")


def test_TAK09_rs01_silent_when_field_never_bit_preserved_elsewhere():
    src = (
        "impl Builder {\n"
        "    pub fn timeout(&mut self, t: u64) -> &mut Self {\n"
        "        self.timeout = t;\n"
        "        self\n"
        "    }\n"
        "}\n"
    )
    assert "RS01" not in _ids(src, ".rs")


def test_TAK10_rs01_silent_on_plain_compound_assignment_only():
    # A field only ever touched via |=/&= (never overwritten outright) is
    # not a finding — there's no clobbering setter to flag.
    src = (
        "impl Builder {\n"
        "    pub fn enable(&mut self) -> &mut Self {\n"
        "        self.flags |= ENABLE_BIT;\n"
        "        self\n"
        "    }\n"
        "}\n"
    )
    assert "RS01" not in _ids(src, ".rs")


# ── PHP01-05 (opens PHP) ──────────────────────────────────────────────────────

def test_TAK11_php01_command_injection():
    src = '<?php\nfunction run($name) {\n    exec("ping " . $name);\n}\n'
    assert "PHP01" in _ids(src, ".php")


def test_TAK12_php02_sql_injection():
    src = "<?php\n$r = $pdo->query(\"SELECT * FROM t WHERE id = \" . $id);\n"
    assert "PHP02" in _ids(src, ".php")


def test_TAK13_php03_eval():
    src = "<?php\neval($_GET['code']);\n"
    assert "PHP03" in _ids(src, ".php")


def test_TAK14_php04_unsafe_unserialize():
    src = "<?php\n$obj = unserialize($_POST['data']);\n"
    assert "PHP04" in _ids(src, ".php")


def test_TAK15_php05_unencoded_signed_route_param():
    src = (
        "<?php\nfunction link($path) {\n"
        "    return URL::temporarySignedRoute('dl', now()->addMinutes(5), ['path' => $path]);\n"
        "}\n"
    )
    assert "PHP05" in _ids(src, ".php")


def test_TAK16_php_silent_on_safe_code():
    src = "<?php\n$stmt = $pdo->prepare('SELECT * FROM t WHERE id = ?');\n$stmt->execute([$id]);\n"
    assert _ids(src, ".php") == []


# ── CS01-05 (opens C#) ────────────────────────────────────────────────────────

def test_TAK17_cs01_process_start_injection():
    src = 'Process.Start("cmd /c " + userInput);\n'
    assert "CS01" in _ids(src, ".cs")


def test_TAK18_cs02_sqlcommand_concat():
    src = 'var cmd = new SqlCommand("SELECT * FROM t WHERE id = " + id);\n'
    assert "CS02" in _ids(src, ".cs")


def test_TAK19_cs03_binaryformatter():
    src = "var bf = new BinaryFormatter();\n"
    assert "CS03" in _ids(src, ".cs")


def test_TAK20_cs04_trust_all_tls():
    src = "handler.ServerCertificateCustomValidationCallback = (msg, cert, chain, errors) => true;\n"
    assert "CS04" in _ids(src, ".cs")


def test_TAK21_cs05_archive_extraction_triage():
    src = "TarFile.ExtractToDirectory(stream, destDir, true);\n"
    assert "CS05" in _ids(src, ".cs")


def test_TAK22_cs_silent_on_safe_code():
    src = 'cmd.Parameters.AddWithValue("@id", id);\n'
    assert _ids(src, ".cs") == []


def test_TAK23_rule_count_reflects_new_rules():
    from sast.multilang_scanner import rule_count
    assert rule_count() == 51
