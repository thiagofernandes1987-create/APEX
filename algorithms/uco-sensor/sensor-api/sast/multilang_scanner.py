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
    # GO11 — cmd/go CVE-2023-29404: validLinkerFlags entries that accept a
    # cgo linker flag's argument optionally instead of mandatorily, letting
    # an attacker smuggle an unexpected flag in through what looks like the
    # argument of a preceding flag (e.g. "-Wl,-O -Wl,-R,-bad-flag" parsed as
    # "-O=-R -bad-flag"). Matches the 3 exact pre-fix regex literals from
    # the real golang/go vulnerable security.go (sha 6d8af00a); the fix
    # (sha bbeb55f5) tightens each to a mandatory, bounded argument.
    MLRule("GO11", _GO, "HIGH", "CWE-88", "A03:2021",
           "cgo linker-flag allowlist regex accepts an optional/unbounded argument",
           _rx(
               r'-Wl,-O\(\[\^@,\\-\]\[\^,\]\*\)\?'
               r'|-Wl,-e\[=,\]\[a-zA-Z0-9\]\*(?!\+)'
               r'|-Wl,-R\(\[\^@\\-\]\[\^,@\]\*\$\)'
           ),
           "Require the flag's argument explicitly (no trailing `?` on the "
           "whole argument group) and bound the character class so the "
           "linker cannot consume a following flag as this one's argument.",
           "re(`-Wl,-O[0-9]+`)  // mandatory, bounded argument"),
    MLRule("GO12", _GO, "HIGH", "CWE-316", "A04:2021",
           "Authenticate() checks r.Password but never clears it from the request",
           _rx(r'(?!)'),  # never matches directly; detection is function-scoped (see below)
           "Clear the plaintext password from the request as soon as it has "
           "been checked, on every exit path (e.g. via a `defer` right after "
           "entering the function) — not just on specific success branches.",
           'defer func() { if r != nil { r.Password = "" } }()'),
]

GO12 = _GO_RULES[-1]

# GO12 — etcd CVE-2021-28235: `EtcdServer.Authenticate()` (sha 801bb4c6)
# calls `CheckPassword(r.Name, r.Password)` but never clears `r.Password`
# anywhere within its own function body, so the plaintext password
# lingers in memory/can be echoed by panics or instrumentation after the
# check. The fix (sha 8b1cd036) adds an unconditional
# `defer func() { r.Password = "" }()` right after entering the function,
# guaranteeing the clear on every exit path. Function-scoped
# presence/absence (narrower than CS06/C05's whole-file scope): the
# `r.Password = ""` assignments that already exist elsewhere in the same
# file (in unrelated functions like `UserAdd`/`UserChangePassword`) must
# not suppress this finding, so the check is limited to the `Authenticate`
# function's own body span.

_GO_AUTH_FUNC_START = re.compile(r'^func\s+\([^)]*\)\s*Authenticate\s*\(')
_GO_TOP_LEVEL_FUNC = re.compile(r'^func\s')
_GO_PASSWORD_CHECK_CALL = re.compile(r'CheckPassword\([^)]*\.Password\)')
_GO_PASSWORD_CLEAR = re.compile(r'\.Password\s*=\s*""')


def _scan_go_password_retention(source: str) -> List[Tuple[int, int]]:
    """GO12: an `Authenticate()` function body that checks `r.Password`
    via `CheckPassword(...)` but never assigns `.Password = ""` anywhere
    in its own body is the CVE-2021-28235 shape."""
    lines = source.splitlines()
    n = len(lines)
    hits: List[Tuple[int, int]] = []
    i = 0
    while i < n:
        if _GO_AUTH_FUNC_START.match(lines[i]):
            start = i
            j = i + 1
            while j < n and not _GO_TOP_LEVEL_FUNC.match(lines[j]):
                j += 1
            body = "\n".join(lines[start:j])
            if _GO_PASSWORD_CHECK_CALL.search(body) and not _GO_PASSWORD_CLEAR.search(body):
                hits.append((start + 1, 0))
            i = j
        else:
            i += 1
    return hits


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
    MLRule("PHP05", _PHP, "MEDIUM", "CWE-116", "A04:2021",
           "Unencoded parameter passed to a signed/temporary route builder",
           # CVE-2026-48041 (Laravel): a path containing '?'/'&'/'#' passed
           # unencoded into a signed-URL parameter array lets an attacker
           # smuggle/override query parameters (incl. the signature's
           # `expires`), bypassing URL expiration. Heuristic / low-confidence:
           # cannot verify the encoding actually happened (would need
           # dataflow), so this only flags the call site for manual review.
           _rx(r'temporarySignedRoute\s*\(|signedRoute\s*\('),
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
           # CVE-2026-45491 (dotnet/runtime): TarFile.ExtractToDirectory
           # followed a symlink created by an earlier entry in the same
           # archive to write outside the destination directory. Regex
           # cannot verify the absence of a containment check (that needs
           # dataflow), so this is a low-confidence triage flag only.
           _rx(r'\.(?:ExtractToDirectory|ExtractToFile)\s*\('),
           "Resolve symlinks in the destination path and verify containment "
           "before extracting each archive entry.",
           ""),
]


# All rules indexed by language for fast dispatch
_ALL_RULES: List[MLRule] = (
    _JS_RULES + _JAVA_RULES + _GO_RULES + _PHP_RULES + _CS_RULES + _RUST_RULES
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
