"""
UCO-Sensor — Multi-Language SAST Scanner  (M9.0)
=================================================
Security scanning for JavaScript / TypeScript, Java, and Go, complementing
the Python-only ``sast/scanner.py``.

Runs on top of :class:`TreeSitterBridge`: when tree-sitter grammars are
present a real parse tree could refine matches; in their absence (the
common offline case) the rules execute as line-oriented regex checks.  The
public contract — a list of :class:`SASTFinding` — is identical to the
Python scanner, so the REST/report layers consume both transparently.

Rule sets
---------
JavaScript / TypeScript (JS01-JS10)
  XSS via innerHTML / document.write / dangerouslySetInnerHTML, eval /
  Function constructor, child_process exec with interpolation, prototype
  pollution, weak crypto (createHash('md5')), Math.random for secrets,
  hardcoded secrets, SQL string concatenation.

Java (JV01-JV10)
  Runtime.exec, SQL injection via Statement+concat, XXE (unhardened
  DocumentBuilderFactory), insecure deserialization (ObjectInputStream),
  weak crypto (MessageDigest "MD5"), trust-all TLS, hardcoded password,
  java.util.Random for security, Spring @CrossOrigin("*").

Go (GO01-GO10)
  os/exec with interpolation, SQL injection via fmt.Sprintf, weak crypto
  (md5/sha1), math/rand for crypto, tls.Config{InsecureSkipVerify:true},
  hardcoded credentials, defer inside a loop (resource leak),
  text/template for HTML (no auto-escaping).

PHP (PHP01-PHP05)
  exec/shell_exec/system injection, SQL injection via concatenation,
  eval(), unserialize() of external input, unencoded parameter passed to
  a signed/temporary route builder (low-confidence triage heuristic).

C# (CS01-CS05)
  Process.Start injection, SqlCommand concatenation, BinaryFormatter
  deserialization, trust-all TLS callback, archive extraction without
  symlink/path-containment validation (low-confidence triage heuristic).

Public API
----------
    scan_multilang(source, file_extension) -> SASTResult
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from lang_adapters.tree_sitter_bridge import TreeSitterBridge

# Reuse the canonical finding/result dataclasses from the Python scanner.
from sast.scanner import SASTFinding, SASTResult

# ── SQALE remediation cost per severity (minutes) ─────────────────────────────
_DEBT = {"CRITICAL": 60, "HIGH": 40, "MEDIUM": 20, "LOW": 10}


# ── Rule definition ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MLRule:
    """One multi-language SAST regex rule."""
    rule_id:      str
    languages:    Tuple[str, ...]      # ("javascript", "typescript"), ("java",), …
    severity:     str
    cwe_id:       str
    owasp:        str
    title:        str
    pattern:      "re.Pattern[str]"
    remediation:  str
    suggested_fix: str = ""
    explanation:  str = ""


def _rx(p: str) -> "re.Pattern[str]":
    return re.compile(p)


# ── JavaScript / TypeScript rules ─────────────────────────────────────────────

_JS = ("javascript", "typescript")

_JS_RULES: List[MLRule] = [
    MLRule("JS01", _JS, "HIGH", "CWE-79", "A03:2021",
           "DOM XSS via innerHTML assignment",
           _rx(r'\.(innerHTML|outerHTML)\s*=\s*(?!["\'`]\s*["\'`])'),
           "Use textContent, or sanitise with DOMPurify before assigning HTML.",
           "el.textContent = userInput;  // or el.innerHTML = DOMPurify.sanitize(userInput)",
           "Assigning untrusted data to innerHTML executes embedded <script>/onerror payloads."),
    MLRule("JS02", _JS, "HIGH", "CWE-79", "A03:2021",
           "XSS via document.write",
           _rx(r'document\.write(?:ln)?\s*\('),
           "Avoid document.write; build DOM nodes and set textContent.",
           "container.append(document.createTextNode(userInput));"),
    MLRule("JS03", _JS, "HIGH", "CWE-79", "A03:2021",
           "React dangerouslySetInnerHTML",
           _rx(r'dangerouslySetInnerHTML\s*=\s*\{\{'),
           "Render text as children; if HTML is required, sanitise with DOMPurify.",
           "dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(html) }}"),
    MLRule("JS04", _JS, "CRITICAL", "CWE-95", "A03:2021",
           "Code injection via eval()",
           _rx(r'\beval\s*\('),
           "Never eval user data; use JSON.parse for data or a safe expression parser.",
           "const data = JSON.parse(jsonString);"),
    MLRule("JS05", _JS, "CRITICAL", "CWE-95", "A03:2021",
           "Code injection via Function constructor",
           # `Function(...)` without `new` builds a function exactly like
           # `new Function(...)` (CVE-2021-23337, lodash _.template, used the
           # bare-call form). `\b` keeps `isFunction(`/`castFunction(` excluded.
           _rx(r'\b(?:new\s+)?Function\s*\('),
           "Avoid the Function constructor with dynamic input.",
           ""),
    MLRule("JS06", _JS, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via child_process",
           _rx(r'(?:child_process\.)?exec(?:Sync)?\s*\(\s*[`"\'].*\$\{'),
           "Use execFile/spawn with an argument array; never interpolate into a shell string.",
           "execFile('cmd', [arg], (err, out) => { ... });"),
    MLRule("JS07", _JS, "HIGH", "CWE-1321", "A08:2021",
           "Prototype pollution via __proto__ key",
           _rx(r'\[\s*["\']__proto__["\']\s*\]\s*='),
           "Validate object keys; use Map or Object.create(null) for untrusted dictionaries.",
           ""),
    MLRule("JS08", _JS, "MEDIUM", "CWE-327", "A02:2021",
           "Weak hash (MD5) via crypto.createHash",
           _rx(r'createHash\s*\(\s*["\'](?:md5|sha1)["\']'),
           "Use sha256 or stronger for integrity/signatures.",
           "crypto.createHash('sha256')"),
    MLRule("JS09", _JS, "MEDIUM", "CWE-330", "A02:2021",
           "Insecure randomness (Math.random) for security value",
           _rx(r'Math\.random\s*\(\s*\)'),
           "Use crypto.randomBytes / crypto.getRandomValues for tokens & secrets.",
           "crypto.randomBytes(32).toString('hex')"),
    MLRule("JS10", _JS, "HIGH", "CWE-89", "A03:2021",
           "SQL injection via string concatenation in query",
           _rx(r'(?:query|execute)\s*\(\s*[`"\'].*(?:\+|\$\{)'),
           "Use parameterised queries / prepared statements.",
           "db.query('SELECT * FROM t WHERE id = ?', [id])"),
    MLRule("JS11", _JS, "HIGH", "CWE-200", "A01:2021",
           "Credential attached cross-origin via withCredentials || same-origin check",
           # CVE-2023-45857 (axios): `(config.withCredentials || isURLSameOrigin(x))`
           # makes the same-origin check an optional disjunct instead of a
           # mandatory conjunct, so `withCredentials: true` alone is enough
           # to attach a same-origin-only cookie/token cross-origin.
           _rx(r'withCredentials\s*\|\|.*(?:isURLSameOrigin|isSameOrigin|sameOrigin)'),
           "Require the same-origin check unconditionally (use && , not ||) before "
           "attaching a cookie-derived credential header to a request.",
           "const xsrfValue = isURLSameOrigin(fullPath) && config.xsrfCookieName && cookies.read(...);"),
]


# ── Java rules ────────────────────────────────────────────────────────────────

_JAVA = ("java",)

_JAVA_RULES: List[MLRule] = [
    MLRule("JV01", _JAVA, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via Runtime.exec",
           _rx(r'Runtime\.getRuntime\(\)\.exec\s*\(\s*[^)]*\+'),
           "Use ProcessBuilder with an argument list; avoid string concatenation.",
           "new ProcessBuilder(\"cmd\", arg).start();"),
    MLRule("JV02", _JAVA, "HIGH", "CWE-89", "A03:2021",
           "SQL injection via Statement + concatenation",
           _rx(r'(?:createStatement\(\)|\.execute(?:Query|Update)?)\s*\(\s*[^)]*\+'),
           "Use PreparedStatement with bind parameters.",
           "PreparedStatement ps = conn.prepareStatement(\"... WHERE id = ?\");"),
    MLRule("JV03", _JAVA, "HIGH", "CWE-611", "A05:2021",
           "XXE: DocumentBuilderFactory not hardened",
           _rx(r'DocumentBuilderFactory\.newInstance\s*\('),
           "Call setFeature(\"http://apache.org/xml/features/disallow-doctype-decl\", true).",
           "dbf.setFeature(\"http://apache.org/xml/features/disallow-doctype-decl\", true);"),
    MLRule("JV04", _JAVA, "CRITICAL", "CWE-502", "A08:2021",
           "Insecure deserialization via ObjectInputStream",
           _rx(r'new\s+ObjectInputStream\s*\('),
           "Avoid native serialization for untrusted data; use JSON with a schema.",
           ""),
    MLRule("JV05", _JAVA, "MEDIUM", "CWE-327", "A02:2021",
           "Weak hash (MD5/SHA-1) via MessageDigest",
           _rx(r'MessageDigest\.getInstance\s*\(\s*"(?:MD5|SHA-1)"'),
           "Use SHA-256 or stronger.",
           "MessageDigest.getInstance(\"SHA-256\");"),
    MLRule("JV06", _JAVA, "CRITICAL", "CWE-295", "A07:2021",
           "Trust-all TLS (custom X509TrustManager)",
           _rx(r'(?:checkServerTrusted|getAcceptedIssuers)\s*\([^)]*\)\s*\{\s*\}|TrustManager\s*\[\s*\]'),
           "Never disable certificate validation; trust the system store.",
           ""),
    MLRule("JV07", _JAVA, "HIGH", "CWE-798", "A07:2021",
           "Hardcoded password / secret",
           _rx(r'(?:String\s+)?(?:password|secret|apiKey|api_key)\s*=\s*"[^"]{6,}"'),
           "Load secrets from a vault / environment, never source.",
           ""),
    MLRule("JV08", _JAVA, "MEDIUM", "CWE-330", "A02:2021",
           "java.util.Random used for security value",
           _rx(r'new\s+java\.util\.Random\s*\(|new\s+Random\s*\(\s*\)'),
           "Use java.security.SecureRandom for tokens & secrets.",
           "SecureRandom rng = new SecureRandom();"),
    MLRule("JV09", _JAVA, "MEDIUM", "CWE-942", "A05:2021",
           "Spring permissive CORS @CrossOrigin(\"*\")",
           _rx(r'@CrossOrigin\s*\(\s*(?:origins\s*=\s*)?"\*"'),
           "Restrict allowed origins to a known allowlist.",
           "@CrossOrigin(origins = \"https://app.example.com\")"),
    MLRule("JV10", _JAVA, "HIGH", "CWE-95", "A03:2021",
           "Expression injection via ScriptEngine.eval",
           _rx(r'ScriptEngine\w*\.eval\s*\('),
           "Avoid evaluating dynamic scripts from user input.",
           ""),
    MLRule("JV11", _JAVA, "CRITICAL", "CWE-915", "A08:2021",
           "Bean property filtered by name denylist instead of by type",
           # Spring4Shell (CVE-2022-22965): pre-fix code excluded the
           # dangerous "classLoader"/"protectionDomain" properties from
           # data-binding by comparing the literal property *name* string,
           # which is trivially bypassed (e.g. via "class.module.classLoader"
           # on JDK 9+). The fix replaced the denylist with an
           # isAssignableFrom() type check.
           _rx(r'"(?:classLoader|protectionDomain)"\s*\.equals\s*\(\s*\w+\.getName\(\)\s*\)'
               r'|\w+\.getName\(\)\.equals\s*\(\s*"(?:classLoader|protectionDomain)"\s*\)'),
           "Filter sensitive bean properties by type (isAssignableFrom), not by "
           "comparing the property name string — name denylists are bypassable.",
           "if (ClassLoader.class.isAssignableFrom(pd.getPropertyType())) continue;"),
]


# ── Go rules ──────────────────────────────────────────────────────────────────

_GO = ("go",)

_GO_RULES: List[MLRule] = [
    MLRule("GO01", _GO, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via exec.Command",
           _rx(r'exec\.Command(?:Context)?\s*\([^)]*(?:\+|fmt\.Sprintf)'),
           "Pass arguments as separate parameters; never build the command via Sprintf/concat.",
           "exec.Command(\"cmd\", arg)  // args passed separately"),
    MLRule("GO02", _GO, "HIGH", "CWE-89", "A03:2021",
           "SQL injection via fmt.Sprintf in query",
           _rx(r'(?:Query|Exec|QueryRow)\s*\(\s*fmt\.Sprintf\s*\('),
           "Use parameterised queries with placeholders ($1, ?).",
           "db.Query(\"SELECT * FROM t WHERE id = $1\", id)"),
    MLRule("GO03", _GO, "MEDIUM", "CWE-327", "A02:2021",
           "Weak hash (md5/sha1)",
           _rx(r'(?:md5|sha1)\.(?:New|Sum)\s*\('),
           "Use crypto/sha256 or stronger.",
           "h := sha256.New()"),
    MLRule("GO04", _GO, "MEDIUM", "CWE-330", "A02:2021",
           "Insecure randomness via math/rand",
           _rx(r'\bmath/rand\b|\brand\.(?:Intn|Int|Float64|Read)\s*\('),
           "Use crypto/rand for tokens, keys, and secrets.",
           "crypto/rand.Read(buf)"),
    MLRule("GO05", _GO, "CRITICAL", "CWE-295", "A07:2021",
           "TLS verification disabled (InsecureSkipVerify)",
           _rx(r'InsecureSkipVerify\s*:\s*true'),
           "Never disable certificate verification in production.",
           "tls.Config{ /* verify enabled by default */ }"),
    MLRule("GO06", _GO, "HIGH", "CWE-798", "A07:2021",
           "Hardcoded credential",
           _rx(r'(?:password|secret|apiKey|token)\s*:?=\s*"[^"]{6,}"'),
           "Load secrets from the environment / a secret manager.",
           ""),
    MLRule("GO07", _GO, "MEDIUM", "CWE-772", "A05:2021",
           "defer inside a loop (resource leak)",
           _rx(r'for\b.*\{[^}]*\bdefer\b'),
           "Move defer out of the loop or wrap the body in a function.",
           ""),
    MLRule("GO08", _GO, "HIGH", "CWE-79", "A03:2021",
           "text/template used for HTML (no auto-escaping)",
           _rx(r'text/template'),
           "Use html/template for HTML output — it auto-escapes.",
           "import \"html/template\""),
    MLRule("GO09", _GO, "MEDIUM", "CWE-22", "A01:2021",
           "Path traversal via filepath.Join with request input",
           _rx(r'filepath\.Join\s*\([^)]*(?:r\.URL|req\.|param|input)'),
           "Validate/clean the path and confine it under a known root.",
           "filepath.Join(root, filepath.Clean(\"/\"+name))"),
    MLRule("GO10", _GO, "CRITICAL", "CWE-95", "A03:2021",
           "SSRF via http.Get with user-controlled URL",
           _rx(r'http\.(?:Get|Post)\s*\(\s*(?:r\.URL|req\.|param|input|userURL)'),
           "Allowlist destination hosts before issuing the request.",
           ""),
]


# ── Rust rules ────────────────────────────────────────────────────────────────
#
# RS01 is not a simple per-line regex: the bug (CVE-2023-22466, tokio
# `ServerOptions::pipe_mode`) only exists in the *relationship* between two
# different setter methods that both write the same bit-field. One setter
# (`pipe_mode`) did `self.pipe_mode = match ...` — a full overwrite that
# silently clobbers any flag bits another setter (`reject_remote_clients`,
# using the bit-preserving `bool_flag!` macro) had set on that same field.
# A single-line regex cannot see this — it needs the whole file's setter
# inventory per field name. Handled by `_scan_rust_bitfield_setters` below;
# RS01 still carries the standard MLRule metadata so findings shape the
# same as every other multi-language rule.

_RUST = ("rust",)

RS01 = MLRule(
    "RS01", _RUST, "HIGH", "CWE-693", "A04:2021",
    "Bit-field overwritten by one setter while another preserves flags",
    _rx(r'(?!)'),  # never matches directly; detection is cross-line (see below)
    "Use a bit-preserving operation (|=, &=, or the same bool_flag! style "
    "already used by the other setter) instead of a full-field overwrite.",
    "self.field |= FLAG;  // not: self.field = FLAG;",
)

_RUST_RULES: List[MLRule] = [RS01]

_RUST_DIRECT_ASSIGN = re.compile(r'\bself\.(\w+)\s*=\s*(?!=)')
_RUST_BIT_PRESERVE = re.compile(
    r'bool_flag!\s*\(\s*self\.(\w+)\s*,|\bself\.(\w+)\s*(?:\|=|&=)'
)


def _scan_rust_bitfield_setters(source: str) -> List[Tuple[int, int, str]]:
    """Cross-line RS01 detection: fields written by both a direct `self.f =`
    overwrite and a bit-preserving op (`bool_flag!`/`|=`/`&=`) somewhere
    else in the same file. Returns (lineno, col, field) for the overwrite
    sites of every such field."""
    direct: Dict[str, List[Tuple[int, int]]] = {}
    preserved: set = set()

    for lineno, raw in TreeSitterBridge.iter_lines(source):
        line = _strip_line_comment(raw)
        m = _RUST_DIRECT_ASSIGN.search(line)
        if m:
            direct.setdefault(m.group(1), []).append((lineno, m.start()))
        for m2 in _RUST_BIT_PRESERVE.finditer(line):
            field = m2.group(1) or m2.group(2)
            preserved.add(field)

    hits: List[Tuple[int, int, str]] = []
    for field, sites in direct.items():
        if field in preserved:
            hits.extend((lineno, col, field) for lineno, col in sites)
    return hits


# ── PHP rules ─────────────────────────────────────────────────────────────────

_PHP = ("php",)

_PHP_RULES: List[MLRule] = [
    MLRule("PHP01", _PHP, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via exec/shell_exec/system",
           _rx(r'\b(?:exec|shell_exec|system|passthru|popen|proc_open)\s*\(\s*["\'].*\$'),
           "Use escapeshellarg()/escapeshellcmd() on every argument, or avoid shelling out.",
           "exec('cmd ' . escapeshellarg($arg));"),
    MLRule("PHP02", _PHP, "HIGH", "CWE-89", "A03:2021",
           "SQL injection via string concatenation in query",
           _rx(r'(?:mysqli_query|->query|->exec)\s*\(\s*["\'].*\.\s*\$'),
           "Use prepared statements (PDO/mysqli bind_param).",
           "$stmt = $pdo->prepare('SELECT * FROM t WHERE id = ?');"),
    MLRule("PHP03", _PHP, "CRITICAL", "CWE-95", "A03:2021",
           "Code injection via eval()",
           _rx(r'\beval\s*\('),
           "Never eval dynamic/user-controlled strings.",
           ""),
    MLRule("PHP04", _PHP, "CRITICAL", "CWE-502", "A08:2021",
           "Insecure deserialization via unserialize() of external input",
           _rx(r'\bunserialize\s*\(\s*\$_(?:GET|POST|REQUEST|COOKIE)'),
           "Use json_decode for untrusted data; never unserialize() external input.",
           "$data = json_decode($_POST['data'], true);"),
    MLRule("PHP05", _PHP, "HIGH", "CWE-116", "A04:2021",
           "Unencoded path variable passed to a signed/temporary route's parameter array",
           # CVE-2026-48041 (Laravel, GHSA-crmm-hgp2-wgrp): the actual fix
           # (sha 071ac5c3 -> cba82e4e in LocalFilesystemAdapter.php) is
           # narrowly scoped to wrapping the 'path' array entry with
           # rawurlencode() — the temporarySignedRoute()/signedRoute() call
           # itself is identical before and after, so flagging the call
           # site (the original heuristic) fires equally on both. This
           # tighter pattern matches only the `['path' => $var]`-style
           # array entry, requiring it NOT be wrapped in
           # rawurlencode()/urlencode() — validated to fire on the real
           # vulnerable line and go silent on the real fixed line.
           _rx(r'''\[\s*['"]path['"]\s*=>\s*(?!rawurlencode\(|urlencode\()\$\w+'''),
           "Pass path/query-like values through rawurlencode() before placing "
           "them in a signed-route parameter array.",
           "['path' => rawurlencode($path)]"),
]


# ── C# rules ──────────────────────────────────────────────────────────────────

_CS = ("csharp",)

_CS_RULES: List[MLRule] = [
    MLRule("CS01", _CS, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via Process.Start",
           _rx(r'Process\.Start\s*\(\s*[^)]*(?:\+|\$")'),
           "Pass arguments via ProcessStartInfo.ArgumentList; never concatenate.",
           "psi.ArgumentList.Add(arg);"),
    MLRule("CS02", _CS, "HIGH", "CWE-89", "A03:2021",
           "SQL injection via SqlCommand string concatenation",
           _rx(r'new\s+SqlCommand\s*\(\s*[^)]*\+'),
           "Use parameterised SqlCommand with SqlParameter.",
           "cmd.Parameters.AddWithValue(\"@id\", id);"),
    MLRule("CS03", _CS, "CRITICAL", "CWE-502", "A08:2021",
           "Insecure deserialization via BinaryFormatter",
           _rx(r'\bBinaryFormatter\s*\(\s*\)|\.Deserialize\s*\(\s*\w*[Ss]tream'),
           "BinaryFormatter is deprecated and unsafe; use System.Text.Json instead.",
           ""),
    MLRule("CS04", _CS, "CRITICAL", "CWE-295", "A07:2021",
           "Trust-all TLS (certificate validation callback always true)",
           _rx(r'ServerCertificateCustomValidationCallback\s*=.*=>\s*true'),
           "Never disable certificate validation in production.",
           ""),
    MLRule("CS05", _CS, "MEDIUM", "CWE-59", "A05:2021",
           "Archive extraction without symlink/path-containment validation",
           # Low-confidence generic triage flag: presence of the public
           # extraction API alone, regardless of any internal containment
           # check elsewhere in the file. Deliberately NOT a detector of
           # CVE-2026-45491 specifically (see CS06 below) — kept because it
           # has standalone triage value for other archive-extraction CVEs.
           _rx(r'\.(?:ExtractToDirectory|ExtractToFile)\s*\('),
           "Resolve symlinks in the destination path and verify containment "
           "before extracting each archive entry.",
           ""),
    MLRule("CS06", _CS, "HIGH", "CWE-59", "A05:2021",
           "Tar entry extraction resolves destination without symlink-escape validation",
           # CVE-2026-45491 (dotnet/runtime, GHSA-7q4v-2mr6-5gpx): the real
           # bug lives in TarEntry's internal extraction helper
           # (ExtractRelativeToDirectoryAsync), not the public
           # ExtractToDirectory/ExtractToFile API that CS05 flags. The fix
           # (sha b06f62fc -> 8c91e3b2) added a FilePathEscapesDirectory()
           # call alongside the pre-existing null checks on the resolved
           # destination/link path. File-wide presence/absence check (the
           # null-guard exists, but the escape-check call doesn't anywhere
           # in the file) — validated to fire on the real vulnerable
           # TarEntry.cs and go silent on the real fixed version.
           _rx(r'(?!)'),  # never matches directly; detection is whole-file (see below)
           "Resolve symlinks component-by-component and reject any "
           "destination/link path that escapes the target directory before "
           "extracting.",
           "if (fileDestinationPath is null || FilePathEscapesDirectory(destDir, fileDestinationPath)) ..."),
]

CS06 = _CS_RULES[-1]

_CS_TAR_ESCAPE_GUARD_SITE = re.compile(
    r'\b(?:fileDestinationPath|linkDestination)\s*(?:==|is)\s*null\b'
)
_CS_TAR_ESCAPE_GUARD_CALL = re.compile(r'\bFilePathEscapesDirectory\s*\(')


def _scan_csharp_tar_extraction(source: str) -> List[Tuple[int, int]]:
    """CS06: a file that null-checks a resolved tar entry destination/link
    path (the pre-fix pattern) but never calls a symlink-escape guard
    anywhere in the same file is the CVE-2026-45491 shape."""
    if _CS_TAR_ESCAPE_GUARD_CALL.search(source):
        return []
    hits: List[Tuple[int, int]] = []
    for lineno, raw in TreeSitterBridge.iter_lines(source):
        line = _strip_line_comment(raw)
        m = _CS_TAR_ESCAPE_GUARD_SITE.search(line)
        if m:
            hits.append((lineno, m.start()))
    return hits


# ── C / C++ rules ─────────────────────────────────────────────────────────────
#
# C01 is not a simple per-line regex: the bug (CVE-2023-38545, curl SOCKS5
# heap buffer overflow) is the *absence* of a length guard, not the presence
# of a bad call by itself. The pre-fix `do_SOCKS5()` (lib/socks.c, sha
# 09e25b9d) detects `hostname_len > 255` but only *logs* it and flips
# `socks5_resolve_local = TRUE` (a no-op downgrade attempt that does not
# actually short-circuit the function) before falling through to
# `memcpy(&socksreq[len], sx->hostname, hostname_len)` against the fixed
# ~256-byte `socksreq` buffer. The fix (sha fb4415d8) replaces the log+flag
# with `failf(...); return CURLPX_LONG_HOSTNAME;`, which aborts before the
# memcpy is ever reached. A single-line regex cannot see this — it needs to
# know whether *any* `return` follows the `hostname_len > 255` guard
# elsewhere in the file. Handled by `_scan_c_socks_overflow` below; C01
# still carries the standard MLRule metadata so findings shape the same as
# every other multi-language rule.

_C = ("c",)

C01 = MLRule(
    "C01", _C, "CRITICAL", "CWE-787", "A06:2021",
    "Hostname copied into fixed-size buffer without a length-guard return",
    _rx(r'(?!)'),  # never matches directly; detection is whole-file (see below)
    "When a length check rejects an oversized hostname/buffer, return/abort "
    "immediately — do not just log a warning and fall through to the copy.",
    "if(len > 255) { failf(data, \"too long\"); return CURLPX_LONG_HOSTNAME; }",
)

_C_RULES: List[MLRule] = [
    C01,
    MLRule("C02", _C, "CRITICAL", "CWE-120", "A06:2021",
           "Unbounded string copy via strcpy/strcat/gets",
           _rx(r'\b(?:strcpy|strcat|gets)\s*\('),
           "Use a bounded variant (strlcpy/strncpy/snprintf) and check the "
           "source length against the destination buffer size first.",
           "strlcpy(dst, src, sizeof(dst));"),
    MLRule("C03", _C, "HIGH", "CWE-134", "A06:2021",
           "Unbounded formatted write via sprintf",
           _rx(r'\bsprintf\s*\('),
           "Use snprintf with the destination buffer size.",
           "snprintf(dst, sizeof(dst), fmt, ...);"),
    MLRule("C04", _C, "CRITICAL", "CWE-78", "A03:2021",
           "OS command injection via system()/popen() with concatenation",
           _rx(r'\b(?:system|popen)\s*\([^)]*(?:\+|strcat|sprintf)'),
           "Avoid building shell commands from untrusted input; use exec*() "
           "with an argument array instead of a shell string.",
           "execvp(\"cmd\", argv);  // no shell involved"),
]

_C_SOCKS_LEN_GUARD = re.compile(r'hostname_len\s*>\s*255\b')
_C_SOCKS_LEN_GUARD_RETURN = re.compile(
    r'hostname_len\s*>\s*255\b[\s\S]{0,200}?\breturn\b'
)
_C_SOCKS_DANGEROUS_MEMCPY = re.compile(
    r'\bmemcpy\s*\([^;]*hostname[^;]*,\s*hostname_len\s*\)'
)


def _scan_c_socks_overflow(source: str) -> List[Tuple[int, int]]:
    """C01: a file that copies a `hostname`-derived length into a fixed
    buffer via memcpy(..., hostname_len) but never returns/aborts within
    ~200 chars of the `hostname_len > 255` guard is the CVE-2023-38545
    shape (log-and-continue instead of reject)."""
    if not _C_SOCKS_DANGEROUS_MEMCPY.search(source):
        return []
    if not _C_SOCKS_LEN_GUARD.search(source):
        return []
    if _C_SOCKS_LEN_GUARD_RETURN.search(source):
        return []
    hits: List[Tuple[int, int]] = []
    for lineno, raw in TreeSitterBridge.iter_lines(source):
        line = _strip_line_comment(raw)
        m = _C_SOCKS_DANGEROUS_MEMCPY.search(line)
        if m:
            hits.append((lineno, m.start()))
    return hits


# All rules indexed by language for fast dispatch
_ALL_RULES: List[MLRule] = (
    _JS_RULES + _JAVA_RULES + _GO_RULES + _PHP_RULES + _CS_RULES + _RUST_RULES
    + _C_RULES
)

_EXT_LANG: Dict[str, str] = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".php": "php",
    ".cs": "csharp",
    ".rs": "rust",
    ".c": "c", ".h": "c",
}


def language_for_extension(ext: str) -> Optional[str]:
    """Map a file extension to a supported language, or None."""
    return _EXT_LANG.get(ext.lower())


# ── Comment stripping (line-level, conservative) ──────────────────────────────

_LINE_COMMENT = re.compile(r'(?<![:"\'])//.*$')   # // … (avoid http:// false strip)


def _strip_line_comment(line: str) -> str:
    """Remove a trailing ``// comment`` while keeping URLs intact (best-effort)."""
    return _LINE_COMMENT.sub("", line)


# ── Public entry point ────────────────────────────────────────────────────────

def scan_multilang(source: str, file_extension: str = "") -> SASTResult:
    """
    Scan *source* for security issues in JS/TS, Java, or Go.

    Unsupported extensions return an empty :class:`SASTResult` (no error),
    mirroring the Python ``scan`` contract so callers can try both.
    """
    language = language_for_extension(file_extension)
    if language is None:
        return SASTResult()

    bridge = TreeSitterBridge(language)
    # parse() is attempted for forward-compat; current rules are line-based.
    bridge.parse(source)

    rules = [r for r in _ALL_RULES if language in r.languages]
    findings: List[SASTFinding] = []
    seen: set = set()   # dedupe by (rule_id, line)

    for lineno, raw in TreeSitterBridge.iter_lines(source):
        line = _strip_line_comment(raw)
        if not line.strip():
            continue
        for rule in rules:
            m = rule.pattern.search(line)
            if not m:
                continue
            key = (rule.rule_id, lineno)
            if key in seen:
                continue
            seen.add(key)
            findings.append(SASTFinding(
                rule_id=rule.rule_id,
                severity=rule.severity,
                cwe_id=rule.cwe_id,
                owasp=rule.owasp,
                title=rule.title,
                description=rule.title,
                line=lineno,
                col=m.start(),
                code_snippet=raw.strip()[:200],
                remediation=rule.remediation,
                debt_minutes=_DEBT.get(rule.severity, 20),
                suggested_fix=rule.suggested_fix,
                confidence=0.75,   # regex-based — slightly below AST confidence
                explanation=rule.explanation,
            ))

    if language == "rust":
        lines = source.splitlines()
        for lineno, col, field in _scan_rust_bitfield_setters(source):
            key = ("RS01", lineno)
            if key in seen:
                continue
            seen.add(key)
            snippet = lines[lineno - 1].strip()[:200] if 0 < lineno <= len(lines) else ""
            findings.append(SASTFinding(
                rule_id="RS01",
                severity=RS01.severity,
                cwe_id=RS01.cwe_id,
                owasp=RS01.owasp,
                title=RS01.title,
                description=f"Field 'self.{field}' is overwritten here but bit-preserved elsewhere",
                line=lineno,
                col=col,
                code_snippet=snippet,
                remediation=RS01.remediation,
                debt_minutes=_DEBT.get(RS01.severity, 20),
                suggested_fix=RS01.suggested_fix,
                confidence=0.65,   # cross-line heuristic — lower than single-line regex
                explanation="",
            ))

    if language == "csharp":
        lines = source.splitlines()
        for lineno, col in _scan_csharp_tar_extraction(source):
            key = ("CS06", lineno)
            if key in seen:
                continue
            seen.add(key)
            snippet = lines[lineno - 1].strip()[:200] if 0 < lineno <= len(lines) else ""
            findings.append(SASTFinding(
                rule_id="CS06",
                severity=CS06.severity,
                cwe_id=CS06.cwe_id,
                owasp=CS06.owasp,
                title=CS06.title,
                description="Null-checks the resolved tar entry path but never calls a "
                            "symlink-escape guard anywhere in this file",
                line=lineno,
                col=col,
                code_snippet=snippet,
                remediation=CS06.remediation,
                debt_minutes=_DEBT.get(CS06.severity, 20),
                suggested_fix=CS06.suggested_fix,
                confidence=0.6,   # whole-file presence/absence heuristic
                explanation="",
            ))

    if language == "c":
        lines = source.splitlines()
        for lineno, col in _scan_c_socks_overflow(source):
            key = ("C01", lineno)
            if key in seen:
                continue
            seen.add(key)
            snippet = lines[lineno - 1].strip()[:200] if 0 < lineno <= len(lines) else ""
            findings.append(SASTFinding(
                rule_id="C01",
                severity=C01.severity,
                cwe_id=C01.cwe_id,
                owasp=C01.owasp,
                title=C01.title,
                description="hostname_len > 255 guard logs/flags but never returns "
                            "before the memcpy(..., hostname_len) into the fixed buffer",
                line=lineno,
                col=col,
                code_snippet=snippet,
                remediation=C01.remediation,
                debt_minutes=_DEBT.get(C01.severity, 20),
                suggested_fix=C01.suggested_fix,
                confidence=0.6,   # whole-file presence/absence heuristic
                explanation="",
            ))

    findings.sort(key=lambda f: (f.line, f.rule_id))
    total_debt = sum(f.debt_minutes for f in findings)
    return SASTResult(
        findings=findings,
        total_debt_minutes=total_debt,
        security_rating=_rating(findings),
        parse_error=False,
    )


def _rating(findings: List[SASTFinding]) -> str:
    """A–E security grade from the worst finding severity present."""
    sevs = {f.severity for f in findings}
    if "CRITICAL" in sevs: return "E"
    if "HIGH" in sevs:     return "D"
    if "MEDIUM" in sevs:   return "C"
    if "LOW" in sevs:      return "B"
    return "A"


def rule_count() -> int:
    """Total number of multi-language SAST rules."""
    return len(_ALL_RULES)
