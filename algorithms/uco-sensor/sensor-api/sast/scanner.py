"""
UCO-Sensor — SAST Security Scanner (M3 + M7.1)
================================================

Static Application Security Testing engine for Python source code.
Pure stdlib — no external dependencies.

Rules implemented
-----------------
  SAST001  SQL Injection              CWE-89   CRITICAL
  SAST002  OS Command Injection       CWE-78   CRITICAL
  SAST003  Unsafe Eval / Exec         CWE-95   HIGH
  SAST004  Pickle Deserialization     CWE-502  HIGH
  SAST005  YAML Unsafe Load           CWE-502  MEDIUM
  SAST006  Weak Crypto Algorithm      CWE-327  MEDIUM   (MD5, SHA-1, DES, RC4 — M7.1)
  SAST007  Insecure Randomness        CWE-338  MEDIUM   (narrowed — M7.1)
  SAST008  Hardcoded Secret           CWE-798  HIGH
  SAST009  Hardcoded Private Key      CWE-321  CRITICAL
  SAST010  Debug Mode Enabled         CWE-489  MEDIUM
  SAST011  Path Traversal via open()  CWE-22   HIGH
  SAST012  Assert for Security Check  CWE-617  LOW
  SAST013  Subprocess shell=True      CWE-78   HIGH
  SAST014  SSRF                       CWE-918  HIGH     (M7.1)
  SAST015  XXE Injection              CWE-611  HIGH     (M7.1)
  SAST018  Template Injection (SSTI)  CWE-94   CRITICAL (M7.1)
  SAST019  ReDoS                      CWE-400  MEDIUM   (M7.1)
  SAST021  Weak Asymmetric Key Size   CWE-326  HIGH     (M7.1)
  SAST022  Weak IV / All-Zero Nonce   CWE-329  MEDIUM   (M7.1)
  SAST023  ECB Mode / Weak Cipher     CWE-327  MEDIUM   (M7.1)
  SAST024  JWT None Algorithm         CWE-347  CRITICAL (M7.1)
  SAST025  Timing Attack via ==       CWE-208  MEDIUM   (M7.1)
  SAST026  CSRF Exempt Decorator      CWE-352  MEDIUM   (M7.1)
  SAST027  SSL Verify Disabled        CWE-295  HIGH     (M7.1)
  SAST028  Weak TLS Protocol          CWE-326  MEDIUM   (M7.1)
  SAST037  Resource Leak (open)       CWE-772  MEDIUM   (M7.1)
  SAST038  Exception Swallowing       CWE-390  LOW      (M7.1)
  SAST039  Mutable Default Argument   CWE-1386 LOW      (M7.1)

SQALE debt per severity
-----------------------
  CRITICAL : 240 min (4 h)
  HIGH     : 120 min (2 h)
  MEDIUM   :  60 min (1 h)
  LOW      :  30 min (0.5 h)

Public API
----------
    scan(source, file_extension=".py")  -> SASTResult
    RULES                               -> List[SASTRuleInfo]
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# Optional: ReDoS pattern analyzer (M7.1 — sast/regex_analyzer.py)
try:
    from sast.regex_analyzer import is_vulnerable as _redos_is_vulnerable
    _REDOS_AVAILABLE = True
except ImportError:
    try:
        from regex_analyzer import is_vulnerable as _redos_is_vulnerable
        _REDOS_AVAILABLE = True
    except ImportError:
        _REDOS_AVAILABLE = False


# ── Severity & SQALE cost ─────────────────────────────────────────────────────

_SEVERITY_DEBT: Dict[str, int] = {
    "CRITICAL": 240,
    "HIGH":     120,
    "MEDIUM":    60,
    "LOW":       30,
    "INFO":       5,
}

# ── Rule catalogue (metadata only) ───────────────────────────────────────────

@dataclass
class SASTRuleInfo:
    rule_id:     str
    title:       str
    cwe_id:      str
    owasp:       str
    severity:    str
    description: str
    remediation: str


RULES: List[SASTRuleInfo] = [
    # ── SAST001-013: original rules ───────────────────────────────────────────
    SASTRuleInfo(
        rule_id="SAST001", title="SQL Injection",
        cwe_id="CWE-89", owasp="A03:2021",
        severity="CRITICAL",
        description=(
            "SQL query constructed by string formatting/concatenation with "
            "non-literal arguments. Attacker-controlled input may alter query structure."
        ),
        remediation="Use parameterised queries: cursor.execute(sql, (param,))",
    ),
    SASTRuleInfo(
        rule_id="SAST002", title="OS Command Injection",
        cwe_id="CWE-78", owasp="A03:2021",
        severity="CRITICAL",
        description=(
            "os.system() or os.popen() called with a non-literal argument. "
            "Attacker-controlled input may execute arbitrary shell commands."
        ),
        remediation=(
            "Use subprocess with a list of arguments and shell=False: "
            "subprocess.run(['cmd', arg], shell=False)"
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST003", title="Unsafe eval() / exec()",
        cwe_id="CWE-95", owasp="A03:2021",
        severity="HIGH",
        description=(
            "eval() or exec() called with a non-constant expression. "
            "If the argument contains attacker-controlled data, arbitrary code executes."
        ),
        remediation=(
            "Avoid eval/exec entirely. If necessary, use ast.literal_eval() for "
            "safe expression evaluation of literals."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST004", title="Pickle Deserialization",
        cwe_id="CWE-502", owasp="A08:2021",
        severity="HIGH",
        description=(
            "pickle.load() or pickle.loads() deserialises arbitrary Python objects. "
            "Malicious pickle data can execute arbitrary code during deserialisation."
        ),
        remediation=(
            "Replace pickle with a safe format (JSON, msgpack). If pickle is required, "
            "validate the data source with HMAC before deserialising."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST005", title="YAML Unsafe Load",
        cwe_id="CWE-502", owasp="A08:2021",
        severity="MEDIUM",
        description=(
            "yaml.load() called without Loader=yaml.SafeLoader. "
            "Untrusted YAML can construct arbitrary Python objects."
        ),
        remediation="Use yaml.safe_load() or yaml.load(data, Loader=yaml.SafeLoader).",
    ),
    SASTRuleInfo(
        rule_id="SAST006", title="Weak Cryptographic Algorithm",
        cwe_id="CWE-327", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "Use of a weak or broken cryptographic algorithm: MD5 or SHA-1 (hashing), "
            "DES or RC4/ARC4 (encryption). These algorithms have known cryptanalytic "
            "weaknesses and do not meet current security standards."
        ),
        remediation=(
            "For hashing: use hashlib.sha256(), sha3_256(), or blake2b(). "
            "For encryption: use AES-256-GCM or ChaCha20-Poly1305."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST007", title="Insecure Randomness",
        cwe_id="CWE-338", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "random module used for cryptographic-strength randomness generation "
            "(token, key, salt, nonce). The random module is not cryptographically "
            "secure and its output can be predicted from observed values."
        ),
        remediation=(
            "Use the secrets module for cryptographic randomness: "
            "secrets.token_hex(), secrets.token_bytes(), secrets.randbelow()."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST008", title="Hardcoded Secret",
        cwe_id="CWE-798", owasp="A07:2021",
        severity="HIGH",
        description=(
            "A variable with a security-sensitive name (password, secret, api_key, "
            "token, etc.) is assigned a hardcoded string literal."
        ),
        remediation=(
            "Load secrets from environment variables or a secrets manager: "
            "os.environ['SECRET_KEY'] or vault/AWS Secrets Manager."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST009", title="Hardcoded Private Key Material",
        cwe_id="CWE-321", owasp="A02:2021",
        severity="CRITICAL",
        description=(
            "PEM-format private key material detected in source code. "
            "Exposing private keys in source repositories is a critical security risk."
        ),
        remediation=(
            "Remove private keys from source code immediately. Store them in a "
            "secrets manager or HSM and load via environment variables."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST010", title="Debug Mode Enabled",
        cwe_id="CWE-489", owasp="A05:2021",
        severity="MEDIUM",
        description=(
            "Application server started with debug=True. Debug mode exposes "
            "stack traces, interactive debuggers, and verbose error pages."
        ),
        remediation=(
            "Set debug=False in production. Control debug mode via environment "
            "variable: debug=os.environ.get('DEBUG', 'false').lower() == 'true'."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST011", title="Path Traversal via open()",
        cwe_id="CWE-22", owasp="A01:2021",
        severity="HIGH",
        description=(
            "open() called with a non-literal path argument. If the path is "
            "attacker-controlled, directory traversal (../../etc/passwd) is possible."
        ),
        remediation=(
            "Validate and sanitise file paths: use pathlib.Path.resolve() and "
            "verify the resolved path starts within an allowed base directory."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST012", title="Assert Used for Security Check",
        cwe_id="CWE-617", owasp="A05:2021",
        severity="LOW",
        description=(
            "assert used to enforce a security constraint. Python's -O flag "
            "removes all assert statements, bypassing the check entirely."
        ),
        remediation=(
            "Replace assert with an explicit if-raise: "
            "if not condition: raise ValueError('...')"
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST013", title="Subprocess with shell=True",
        cwe_id="CWE-78", owasp="A03:2021",
        severity="HIGH",
        description=(
            "subprocess.call/run/Popen used with shell=True and a non-literal "
            "command. Shell metacharacters in the command can lead to injection."
        ),
        remediation=(
            "Pass a list of arguments and set shell=False: "
            "subprocess.run(['cmd', arg], shell=False, check=True)"
        ),
    ),
    # ── SAST014-039: M7.1 new rules ──────────────────────────────────────────
    SASTRuleInfo(
        rule_id="SAST014", title="Server-Side Request Forgery (SSRF)",
        cwe_id="CWE-918", owasp="A10:2021",
        severity="HIGH",
        description=(
            "HTTP request function called with a non-literal URL argument. If the "
            "URL originates from user input, an attacker can force the server to "
            "make requests to internal services (metadata endpoints, Redis, RDS) "
            "or arbitrary external hosts."
        ),
        remediation=(
            "Validate and whitelist allowed URL schemes and hosts before making "
            "outbound HTTP requests. Reject private/loopback IP ranges. "
            "Use an allowlist of permitted external destinations."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST015", title="XML External Entity (XXE) Injection",
        cwe_id="CWE-611", owasp="A05:2021",
        severity="HIGH",
        description=(
            "XML parser invoked without explicitly disabling external entity "
            "resolution. Malicious XML can read local files via file:// URIs, "
            "trigger SSRF via http:// URIs, or cause denial-of-service through "
            "entity expansion (Billion Laughs attack)."
        ),
        remediation=(
            "Use defusedxml for all XML parsing: defusedxml.ElementTree.parse(). "
            "For lxml: set resolve_entities=False in XMLParser constructor. "
            "Never parse untrusted XML with minidom.parse() or xml.sax.parse()."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST018", title="Server-Side Template Injection (SSTI)",
        cwe_id="CWE-94", owasp="A03:2021",
        severity="CRITICAL",
        description=(
            "Jinja2 Template compiled from a non-literal string, or "
            "render_template_string() called with a non-literal template argument. "
            "If user-controlled data reaches the template string, arbitrary code "
            "execution is possible via Jinja2 expressions: {{ ''.__class__.__mro__ }}."
        ),
        remediation=(
            "Never build template strings from user input. Load templates from "
            "a trusted directory using env.get_template('name.html'). "
            "Use render_template() instead of render_template_string()."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST019", title="ReDoS — Catastrophic Backtracking",
        cwe_id="CWE-400", owasp="A06:2021",
        severity="MEDIUM",
        description=(
            "Regular expression pattern susceptible to catastrophic backtracking "
            "(ReDoS — CWE-400). Patterns with nested quantifiers (e.g. (\\w+)+) "
            "or overlapping alternation (e.g. (a|aa)+) allow crafted input to "
            "cause exponential regex evaluation time."
        ),
        remediation=(
            "Rewrite to eliminate nested quantifiers and overlapping alternation. "
            "Use the 'regex' library with possessive quantifiers/atomic groups, "
            "or Google's RE2 engine (no backtracking). Test patterns with a "
            "ReDoS checker before deployment."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST021", title="Weak Asymmetric Key Size",
        cwe_id="CWE-326", owasp="A02:2021",
        severity="HIGH",
        description=(
            "RSA or DSA key generated with fewer than 2048 bits. Keys below "
            "2048 bits are considered insecure against modern factoring attacks "
            "and do not meet NIST SP 800-131A requirements (deprecated since 2013)."
        ),
        remediation=(
            "Use at least 2048 bits for RSA/DSA. Prefer RSA-3072 or RSA-4096 "
            "for new deployments. For elliptic-curve cryptography, use P-256 "
            "(256-bit) or higher curves."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST022", title="Weak IV / All-Zero Nonce",
        cwe_id="CWE-329", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "Cipher or AEAD scheme initialised with an all-zero IV or nonce "
            "(bytes(N) or b'\\x00'*N). A static or predictable IV removes "
            "semantic security: identical plaintexts produce identical ciphertexts, "
            "enabling ciphertext analysis and replay attacks."
        ),
        remediation=(
            "Generate IVs and nonces with a cryptographically secure random source: "
            "os.urandom(16) or secrets.token_bytes(16). Never reuse nonces."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST023", title="ECB Mode or Weak Cipher",
        cwe_id="CWE-327", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "Electronic Codebook (ECB) cipher mode in use, or a deprecated "
            "cipher algorithm (DES, 3DES/TripleDES, Blowfish, RC4/ARC4). "
            "ECB mode is deterministic — identical plaintext blocks produce "
            "identical ciphertext blocks, revealing patterns. DES and RC4 are "
            "cryptographically broken."
        ),
        remediation=(
            "Use AES-256-GCM or ChaCha20-Poly1305 for authenticated encryption. "
            "Replace ECB mode with GCM, CCM, or CBC+HMAC."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST024", title="JWT None Algorithm / Signature Bypass",
        cwe_id="CWE-347", owasp="A02:2021",
        severity="CRITICAL",
        description=(
            "JWT decoded with signature verification disabled (verify_signature=False, "
            "verify=False, options={'verify_signature': False}) or 'none' algorithm "
            "accepted. Attackers can forge arbitrary JWT tokens without a valid key."
        ),
        remediation=(
            "Always verify JWT signatures. Specify an explicit allowlist of "
            "algorithms: jwt.decode(token, key, algorithms=['HS256']). "
            "Never include 'none' in the algorithms list."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST025", title="Timing Attack via String Comparison",
        cwe_id="CWE-208", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "Security-sensitive value compared with the == operator. Python's "
            "built-in string comparison short-circuits on the first differing "
            "byte, leaking timing information that attackers can use to reconstruct "
            "secrets (tokens, HMACs, passwords) one byte at a time."
        ),
        remediation=(
            "Use hmac.compare_digest() for all security-sensitive string comparisons: "
            "hmac.compare_digest(expected_mac, provided_mac)"
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST026", title="CSRF Protection Disabled",
        cwe_id="CWE-352", owasp="A01:2021",
        severity="MEDIUM",
        description=(
            "@csrf_exempt decorator applied to a view. This disables Django's "
            "built-in CSRF protection for the decorated endpoint, allowing "
            "cross-site request forgery attacks from malicious third-party pages."
        ),
        remediation=(
            "Remove @csrf_exempt. For REST APIs, implement token-based CSRF "
            "protection (e.g. double-submit cookie or HMAC-signed header). "
            "Use DRF's SessionAuthentication which enforces CSRF by default."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST027", title="SSL Certificate Verification Disabled",
        cwe_id="CWE-295", owasp="A07:2021",
        severity="HIGH",
        description=(
            "requests called with verify=False, completely disabling TLS certificate "
            "verification. The connection is vulnerable to man-in-the-middle attacks: "
            "any attacker with network access can intercept or modify traffic."
        ),
        remediation=(
            "Remove verify=False. If using a private CA, pass the CA bundle: "
            "requests.get(url, verify='/path/to/ca-bundle.crt'). "
            "Never use verify=False in production code."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST028", title="Deprecated TLS/SSL Protocol Version",
        cwe_id="CWE-326", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "Deprecated SSL/TLS protocol version referenced in ssl module constants "
            "(PROTOCOL_SSLv2, PROTOCOL_SSLv3, PROTOCOL_TLSv1, PROTOCOL_TLSv1_1). "
            "These versions are vulnerable to known attacks: POODLE (SSLv3), "
            "BEAST (TLS 1.0), and CRIME."
        ),
        remediation=(
            "Use ssl.PROTOCOL_TLS_CLIENT or ssl.PROTOCOL_TLS_SERVER and enforce "
            "a minimum version: context.minimum_version = ssl.TLSVersion.TLSv1_2. "
            "Prefer TLS 1.3 where supported."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST037", title="Resource Leak — Unclosed File Handle",
        cwe_id="CWE-772", owasp="A06:2021",
        severity="MEDIUM",
        description=(
            "open() called outside a 'with' statement and result assigned to a "
            "variable. If an exception occurs before .close() is called explicitly, "
            "the file descriptor is leaked, consuming OS resources and potentially "
            "preventing other processes from accessing the file."
        ),
        remediation=(
            "Always use the 'with' context manager: "
            "with open(path, 'r') as f: data = f.read(). "
            "This guarantees the file is closed even when exceptions occur."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST038", title="Exception Swallowing",
        cwe_id="CWE-390", owasp="A09:2021",
        severity="LOW",
        description=(
            "Exception caught and silently discarded with 'pass' (bare 'except: pass' "
            "or 'except Exception: pass'). Swallowed exceptions hide application errors, "
            "suppress security-relevant events (authentication failures, I/O errors), "
            "and make debugging nearly impossible."
        ),
        remediation=(
            "At minimum log the exception: except Exception as e: logger.warning(e). "
            "Catch the most specific exception type possible and handle it explicitly."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST039", title="Mutable Default Argument",
        cwe_id="CWE-1386", owasp="A04:2021",
        severity="LOW",
        description=(
            "Function defined with a mutable default argument (list [], dict {}, "
            "or set set()). Python evaluates default values once at function "
            "definition time. Mutations to the default persist across calls, "
            "causing shared-state bugs that are difficult to trace."
        ),
        remediation=(
            "Use None as the default and initialise the mutable object inside "
            "the function body: def f(arg=None): arg = [] if arg is None else arg"
        ),
    ),
]

_RULE_MAP: Dict[str, SASTRuleInfo] = {r.rule_id: r for r in RULES}


# ── Finding ───────────────────────────────────────────────────────────────────

@dataclass
class SASTFinding:
    """One security issue detected by the SAST scanner."""
    rule_id:      str
    severity:     str
    cwe_id:       str
    owasp:        str
    title:        str
    description:  str
    line:         int
    col:          int
    code_snippet: str
    remediation:  str
    debt_minutes: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id":      self.rule_id,
            "severity":     self.severity,
            "cwe_id":       self.cwe_id,
            "owasp":        self.owasp,
            "title":        self.title,
            "description":  self.description,
            "line":         self.line,
            "col":          self.col,
            "code_snippet": self.code_snippet,
            "remediation":  self.remediation,
            "debt_minutes": self.debt_minutes,
        }


@dataclass
class SASTResult:
    """Aggregated result of a SAST scan."""
    findings:           List[SASTFinding] = field(default_factory=list)
    total_debt_minutes: int  = 0
    security_rating:    str  = "A"     # A–E
    parse_error:        bool = False

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "CRITICAL")

    @property
    def high_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "HIGH")

    @property
    def medium_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "MEDIUM")

    @property
    def low_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "LOW")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings":           [f.to_dict() for f in self.findings],
            "finding_count":      len(self.findings),
            "critical":           self.critical_count,
            "high":               self.high_count,
            "medium":             self.medium_count,
            "low":                self.low_count,
            "total_debt_minutes": self.total_debt_minutes,
            "security_rating":    self.security_rating,
            "parse_error":        self.parse_error,
        }


# ── Public entry point ────────────────────────────────────────────────────────

def scan(source: str, file_extension: str = ".py") -> SASTResult:
    """
    Scan Python source code for security vulnerabilities.

    Only Python (.py, .pyw, .pyi) is supported for AST analysis.
    All other extensions return an empty result (no parse error).
    """
    if file_extension not in (".py", ".pyw", ".pyi"):
        return SASTResult()

    findings: List[SASTFinding] = []

    # 1. Regex-based rules (work on raw source, no AST needed)
    findings.extend(_check_hardcoded_private_key(source))
    findings.extend(_check_hardcoded_secrets_regex(source))
    findings.extend(_check_weak_tls_regex(source))

    # 2. AST-based rules
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return SASTResult(parse_error=True)

    lines = source.splitlines()

    scanner = _ASTScanner(lines)
    scanner.visit(tree)
    findings.extend(scanner.findings)

    # Deduplicate by (rule_id, line)
    seen: Set[tuple] = set()
    unique: List[SASTFinding] = []
    for f in findings:
        key = (f.rule_id, f.line)
        if key not in seen:
            seen.add(key)
            unique.append(f)

    unique.sort(key=lambda f: (
        {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
        .get(f.severity, 5),
        f.line,
    ))

    total_debt = sum(f.debt_minutes for f in unique)
    rating = _security_rating(unique)

    return SASTResult(
        findings=unique,
        total_debt_minutes=total_debt,
        security_rating=rating,
    )


# ── Rating ────────────────────────────────────────────────────────────────────

def _security_rating(findings: List[SASTFinding]) -> str:
    """A–E security rating based on finding severity counts."""
    crits = sum(1 for f in findings if f.severity == "CRITICAL")
    highs = sum(1 for f in findings if f.severity == "HIGH")
    meds  = sum(1 for f in findings if f.severity == "MEDIUM")
    if crits >= 1:  return "E"
    if highs >= 2:  return "D"
    if highs == 1:  return "C"
    if meds >= 2:   return "C"
    if meds == 1:   return "B"
    return "A"


# ── Regex-based detectors ─────────────────────────────────────────────────────

_PEM_PATTERN = re.compile(
    r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
    re.IGNORECASE,
)

_SECRET_NAMES = re.compile(
    r"""(?:^|[;\n])\s*(?:\w+\s*[=:]\s*)?
        (?:password|passwd|secret|api_key|apikey|auth_token|access_token|
           access_key|private_key|client_secret|db_password|jwt_secret|
           encryption_key|signing_key|webhook_secret)\s*=\s*
        ['"]((?!^\s*$|YOUR_|CHANGEME|CHANGE_ME|PLACEHOLDER|EXAMPLE|FIXME|TODO|<).{4,})['"]\s*
    """,
    re.IGNORECASE | re.VERBOSE | re.MULTILINE,
)

# SAST028: deprecated ssl protocol constants in source
_WEAK_TLS_PATTERN = re.compile(
    r"\bssl\.(?:PROTOCOL_SSLv2|PROTOCOL_SSLv3|PROTOCOL_TLSv1|PROTOCOL_TLSv1_1)\b",
)


def _check_hardcoded_private_key(source: str) -> List[SASTFinding]:
    findings = []
    for i, line in enumerate(source.splitlines(), start=1):
        if _PEM_PATTERN.search(line):
            rule = _RULE_MAP["SAST009"]
            findings.append(_make_finding(rule, i, 0, line.strip()))
    return findings


def _check_hardcoded_secrets_regex(source: str) -> List[SASTFinding]:
    """Regex scan for hardcoded secret assignments."""
    findings = []
    lines_src = source.splitlines()
    for m in _SECRET_NAMES.finditer(source):
        lineno = source[:m.start()].count("\n") + 1
        snippet = lines_src[lineno - 1].strip() if lineno <= len(lines_src) else ""
        rule = _RULE_MAP["SAST008"]
        findings.append(_make_finding(rule, lineno, m.start(), snippet))
    return findings


def _check_weak_tls_regex(source: str) -> List[SASTFinding]:
    """SAST028: detect deprecated ssl.PROTOCOL_* constants in raw source."""
    findings = []
    lines_src = source.splitlines()
    for m in _WEAK_TLS_PATTERN.finditer(source):
        lineno = source[:m.start()].count("\n") + 1
        snippet = lines_src[lineno - 1].strip() if lineno <= len(lines_src) else ""
        rule = _RULE_MAP["SAST028"]
        findings.append(_make_finding(rule, lineno, m.start(), snippet))
    return findings


# ── AST-based scanner ─────────────────────────────────────────────────────────

_SQL_CALL_NAMES    = frozenset({"execute", "executemany", "executescript", "query", "raw"})
_OS_CMD_CALLS      = frozenset({"system", "popen", "popen2", "popen3", "popen4", "startfile"})
_PICKLE_CALLS      = frozenset({"load", "loads"})
_SUBPROCESS_NAMES  = frozenset({"call", "run", "Popen", "check_call", "check_output"})

# SAST006: weak hash algorithms (hashlib.md5, hashlib.sha1, hashlib.new)
_WEAK_HASH_NAMES   = frozenset({"md5", "sha1", "sha"})
_WEAK_HASH_ALIASES = frozenset({"md5", "sha1", "sha", "des", "rc4", "arcfour", "des3"})

# SAST007 (narrowed): only random calls that are plausible in crypto contexts
_CRYPTO_RANDOM_CALLS = frozenset({
    "random", "randint", "randrange", "getrandbits", "choice",
})

# SAST008 hardcoded secrets
_SECRET_VAR_NAMES = frozenset({
    "password", "passwd", "secret", "api_key", "apikey",
    "auth_token", "access_token", "access_key", "private_key",
    "client_secret", "db_password", "jwt_secret", "encryption_key",
    "signing_key", "webhook_secret", "token",
})

# SAST012 assert security context
_SECURITY_CONTEXT_NAMES = frozenset({
    "password", "secret", "token", "key", "auth", "salt", "nonce",
    "csrf", "session", "credential", "pin", "otp",
})

# SAST014 SSRF: HTTP client methods
_HTTP_REQUEST_METHODS = frozenset({
    "get", "post", "put", "delete", "patch", "head", "request", "options",
})

# SAST015 XXE: vulnerable XML parsers
_XML_PARSE_MODULES = frozenset({"minidom", "sax", "expat"})
_XML_PARSE_CALLS   = frozenset({"parse", "parseString", "fromstring", "XML", "XMLParser"})

# SAST018 SSTI: template-injection sinks
_SSTI_TEMPLATE_CALLS   = frozenset({"Template"})
_SSTI_RENDER_CALLS     = frozenset({"render_template_string"})

# SAST021 weak key size
_WEAK_KEY_CALLS    = frozenset({"generate", "generate_private_key", "construct"})
_WEAK_KEY_SIZE_MAX = 2047  # anything ≤ this is flagged

# SAST023 ECB / weak cipher modules (PyCryptodome / PyCrypto naming)
_WEAK_CIPHER_MODULES = frozenset({"DES", "DES3", "TripleDES", "ARC4", "RC4", "Blowfish"})
_ECB_MODE_NAMES      = frozenset({"MODE_ECB"})

# SAST025 timing attack: security-sensitive variable names in comparisons
_TIMING_SENSITIVE_NAMES = frozenset({
    "password", "passwd", "token", "secret", "key", "api_key", "apikey",
    "hash", "digest", "mac", "hmac", "signature", "sig", "nonce",
    "auth_token", "access_token", "session_key",
})

# SAST027 SSL verify=False
_REQUESTS_MODULES  = frozenset({"requests", "session", "Session"})


class _ASTScanner(ast.NodeVisitor):
    """Walk the AST and collect SAST findings."""

    def __init__(self, lines: List[str]):
        self.lines    = lines
        self.findings: List[SASTFinding] = []
        # Track depth inside `with` blocks for SAST037
        self._with_depth: int = 0

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add(self, rule_id: str, node: ast.AST) -> None:
        rule    = _RULE_MAP[rule_id]
        line    = getattr(node, "lineno", 0)
        col     = getattr(node, "col_offset", 0)
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(_make_finding(rule, line, col, snippet))

    def _is_literal(self, node: ast.expr) -> bool:
        """True if the node is a compile-time constant (string, number, None, bool)."""
        return isinstance(node, ast.Constant)

    def _contains_var(self, node: ast.expr) -> bool:
        """True if the node contains at least one Name node (variable reference)."""
        if isinstance(node, ast.Name):
            return True
        return any(
            self._contains_var(child)
            for child in ast.iter_child_nodes(node)
            if isinstance(child, ast.expr)
        )

    def _is_formatted_str(self, node: ast.expr) -> bool:
        """True if the node is an f-string, %-format, or .format() call."""
        if isinstance(node, ast.JoinedStr):
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return True
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return True
        return False

    def _call_name(self, node: ast.Call) -> str:
        """Return the simple name of a Call node's function (e.g. 'execute')."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        if isinstance(node.func, ast.Attribute):
            return node.func.attr
        return ""

    def _call_module(self, node: ast.Call) -> str:
        """Return the module part of a Call (e.g. 'os' from 'os.system')."""
        if isinstance(node.func, ast.Attribute):
            val = node.func.value
            if isinstance(val, ast.Name):
                return val.id
            if isinstance(val, ast.Attribute):
                return val.attr
        return ""

    def _kw_value(self, node: ast.Call, kw_name: str) -> Optional[ast.expr]:
        """Return the AST node for a specific keyword argument, or None."""
        for kw in node.keywords:
            if kw.arg == kw_name:
                return kw.value
        return None

    def _kw_is_false(self, node: ast.Call, kw_name: str) -> bool:
        """True if keyword kw_name=False is present."""
        val = self._kw_value(node, kw_name)
        return isinstance(val, ast.Constant) and val.value is False

    def _kw_is_true(self, node: ast.Call, kw_name: str) -> bool:
        """True if keyword kw_name=True is present."""
        val = self._kw_value(node, kw_name)
        return isinstance(val, ast.Constant) and val.value is True

    def _is_zero_bytes(self, node: ast.expr) -> bool:
        """True if node represents an all-zero bytes literal: bytes(N) or b'\\x00'*N."""
        # bytes(N) call
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "bytes"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, int)):
            return True
        # b'\x00' * N or N * b'\x00'
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left, right = node.left, node.right
            if isinstance(left, ast.Constant) and isinstance(left.value, bytes):
                return all(b == 0 for b in left.value)
            if isinstance(right, ast.Constant) and isinstance(right.value, bytes):
                return all(b == 0 for b in right.value)
        # b'\x00\x00...' literal
        if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
            return len(node.value) > 0 and all(b == 0 for b in node.value)
        return False

    # ── SAST001-SAST013 + M7.1 call checks ───────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:  # noqa: C901  (complex — intentional)
        name   = self._call_name(node)
        module = self._call_module(node)

        # SAST001: SQL injection
        if name in _SQL_CALL_NAMES and node.args:
            arg0 = node.args[0]
            if self._is_formatted_str(arg0) or (
                not self._is_literal(arg0) and self._contains_var(arg0)
            ):
                self._add("SAST001", node)

        # SAST002: os.system / os.popen
        if module == "os" and name in _OS_CMD_CALLS and node.args:
            if not self._is_literal(node.args[0]):
                self._add("SAST002", node)

        # SAST003: eval / exec
        if name in ("eval", "exec") and node.args:
            if not self._is_literal(node.args[0]):
                self._add("SAST003", node)

        # SAST004: pickle.load / pickle.loads / cPickle.loads
        if module in ("pickle", "cPickle") and name in _PICKLE_CALLS:
            self._add("SAST004", node)

        # SAST005: yaml.load without SafeLoader
        if module == "yaml" and name == "load":
            safe = False
            for kw in node.keywords:
                if kw.arg == "Loader":
                    loader_text = ast.unparse(kw.value) if hasattr(ast, "unparse") else ""
                    if "Safe" in loader_text or "safe" in loader_text.lower():
                        safe = True
            if not safe and len(node.args) < 2:
                self._add("SAST005", node)

        # SAST006: hashlib weak hash + DES/RC4 cipher modules (M7.1 expanded)
        if module == "hashlib":
            if name in _WEAK_HASH_NAMES:
                self._add("SAST006", node)
            elif name == "new" and node.args and isinstance(node.args[0], ast.Constant):
                algo = str(node.args[0].value).lower().replace("-", "")
                if algo in _WEAK_HASH_ALIASES:
                    self._add("SAST006", node)
        # DES / RC4 cipher usage via PyCryptodome
        if module in ("DES", "DES3", "TripleDES", "ARC4", "RC4") and name == "new":
            self._add("SAST006", node)

        # SAST007: random.xxx — narrowed to crypto-relevant calls only (M7.1)
        if module == "random" and name in _CRYPTO_RANDOM_CALLS:
            self._add("SAST007", node)

        # SAST010: app.run(debug=True)
        if name == "run" and self._kw_is_true(node, "debug"):
            self._add("SAST010", node)

        # SAST011: open() with non-literal path
        if name == "open" and node.args:
            if not self._is_literal(node.args[0]):
                self._add("SAST011", node)

        # SAST013: subprocess with shell=True + non-literal command
        if module == "subprocess" and name in _SUBPROCESS_NAMES:
            if self._kw_is_true(node, "shell") and node.args and not self._is_literal(node.args[0]):
                self._add("SAST013", node)

        # ── M7.1 new call checks ──────────────────────────────────────────────

        # SAST014: SSRF — requests.get/post/... with non-literal URL
        if module in _REQUESTS_MODULES and name in _HTTP_REQUEST_METHODS:
            if node.args and not self._is_literal(node.args[0]):
                self._add("SAST014", node)
        # urllib.request.urlopen with non-literal URL
        if module in ("request", "urllib") and name == "urlopen":
            if node.args and not self._is_literal(node.args[0]):
                self._add("SAST014", node)

        # SAST015: XXE — vulnerable XML parsers
        if module in _XML_PARSE_MODULES and name in _XML_PARSE_CALLS:
            self._add("SAST015", node)
        # etree.parse / etree.fromstring without XMLParser(resolve_entities=False)
        if module in ("etree", "ElementTree", "lxml") and name in ("parse", "fromstring", "XML"):
            self._add("SAST015", node)

        # SAST018: SSTI — jinja2.Template(non_literal) or render_template_string(non_literal)
        if module in ("jinja2", "Environment") and name in _SSTI_TEMPLATE_CALLS:
            if node.args and not self._is_literal(node.args[0]):
                self._add("SAST018", node)
        if name in _SSTI_RENDER_CALLS and node.args and not self._is_literal(node.args[0]):
            self._add("SAST018", node)

        # SAST019: ReDoS — re.compile/match/search with vulnerable literal pattern
        if _REDOS_AVAILABLE and module == "re" and name in (
            "compile", "match", "search", "fullmatch", "findall", "sub", "split"
        ):
            if node.args and isinstance(node.args[0], ast.Constant):
                pattern_str = node.args[0].value
                if isinstance(pattern_str, str) and _redos_is_vulnerable(pattern_str):
                    self._add("SAST019", node)

        # SAST021: weak asymmetric key size (< 2048 bits)
        # RSA.generate(1024), DSA.generate(1024), generate_private_key(key_size=1024)
        if name in ("generate", "generate_key") and node.args:
            bits_node = node.args[0]
            if isinstance(bits_node, ast.Constant) and isinstance(bits_node.value, int):
                if bits_node.value <= _WEAK_KEY_SIZE_MAX:
                    self._add("SAST021", node)
        if name == "generate_private_key":
            kw_size = self._kw_value(node, "key_size")
            if kw_size is None and len(node.args) >= 2:
                kw_size = node.args[1]  # positional key_size
            if isinstance(kw_size, ast.Constant) and isinstance(kw_size.value, int):
                if kw_size.value <= _WEAK_KEY_SIZE_MAX:
                    self._add("SAST021", node)

        # SAST022: weak IV — cipher.new(key, mode, bytes(N)) or all-zero IV
        if name == "new" and module not in ("DES", "DES3", "ARC4", "RC4"):
            # Look for 3rd positional arg (IV/nonce) being zero bytes
            if len(node.args) >= 3 and self._is_zero_bytes(node.args[2]):
                self._add("SAST022", node)
            # Check iv= or nonce= keyword
            for kw_name in ("iv", "nonce", "IV", "initial_value"):
                kw_iv = self._kw_value(node, kw_name)
                if kw_iv is not None and self._is_zero_bytes(kw_iv):
                    self._add("SAST022", node)

        # SAST023: ECB mode — AES.new(key, AES.MODE_ECB) or Cipher with ECB
        if name == "new" and node.args and len(node.args) >= 2:
            mode_node = node.args[1]
            mode_src = ast.unparse(mode_node) if hasattr(ast, "unparse") else ""
            if "ECB" in mode_src:
                self._add("SAST023", node)
        # Weak cipher module (DES, RC4, etc.) — new() already flagged in SAST006
        # Also flag direct references to MODE_ECB as attribute access
        if isinstance(node.func, ast.Attribute) and node.func.attr in _ECB_MODE_NAMES:
            self._add("SAST023", node)

        # SAST024: JWT none algorithm / signature bypass
        if module in ("jwt", "PyJWT") and name == "decode":
            # verify=False (older PyJWT)
            if self._kw_is_false(node, "verify"):
                self._add("SAST024", node)
            # options={"verify_signature": False}
            opts_kw = self._kw_value(node, "options")
            if opts_kw is not None and isinstance(opts_kw, ast.Dict):
                for k, v in zip(opts_kw.keys, opts_kw.values):
                    if (isinstance(k, ast.Constant) and k.value == "verify_signature"
                            and isinstance(v, ast.Constant) and v.value is False):
                        self._add("SAST024", node)
            # algorithms=['none'] or algorithms=["none"]
            algos_kw = self._kw_value(node, "algorithms")
            if algos_kw is not None and isinstance(algos_kw, ast.List):
                for elt in algos_kw.elts:
                    if isinstance(elt, ast.Constant) and str(elt.value).lower() == "none":
                        self._add("SAST024", node)

        # SAST027: SSL verify=False
        if module in _REQUESTS_MODULES and name in _HTTP_REQUEST_METHODS:
            if self._kw_is_false(node, "verify"):
                self._add("SAST027", node)

        self.generic_visit(node)

    # ── SAST008 + SAST037: assignments ───────────────────────────────────────

    def visit_Assign(self, node: ast.Assign) -> None:
        """
        SAST008: secret_name = "hardcoded_value"
        SAST037: var = open(...)  — file handle opened outside 'with'
        """
        # SAST008: hardcoded secret
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            val = node.value.value
            if len(val) >= 4 and val.upper() not in (
                "YOUR_PASSWORD", "CHANGEME", "CHANGE_ME",
                "PLACEHOLDER", "EXAMPLE", "TODO", "FIXME",
                "PASSWORD", "SECRET", "TOKEN",
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if target.id.lower() in _SECRET_VAR_NAMES:
                            self._add("SAST008", node)
                            break
                    elif isinstance(target, ast.Attribute):
                        if target.attr.lower() in _SECRET_VAR_NAMES:
                            self._add("SAST008", node)
                            break

        # SAST037: resource leak — open() outside `with` block
        if (self._with_depth == 0
                and isinstance(node.value, ast.Call)
                and self._call_name(node.value) == "open"):
            self._add("SAST037", node)

        self.generic_visit(node)

    # ── SAST012: assert for security ──────────────────────────────────────────

    def visit_Assert(self, node: ast.Assert) -> None:
        test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
        lowered  = test_src.lower()
        if any(kw in lowered for kw in _SECURITY_CONTEXT_NAMES):
            self._add("SAST012", node)
        self.generic_visit(node)

    # ── SAST025: timing attack via == ─────────────────────────────────────────

    def visit_Compare(self, node: ast.Compare) -> None:
        """SAST025: == comparison on security-sensitive variables."""
        for op in node.ops:
            if isinstance(op, ast.Eq):
                # Gather all operand names (substring match to catch user_token, auth_token, etc.)
                operands = [node.left] + node.comparators
                for operand in operands:
                    name = ""
                    if isinstance(operand, ast.Name):
                        name = operand.id.lower()
                    elif isinstance(operand, ast.Attribute):
                        name = operand.attr.lower()
                    if any(sensitive in name for sensitive in _TIMING_SENSITIVE_NAMES):
                        self._add("SAST025", node)
                        break
                break  # one finding per Compare node is sufficient
        self.generic_visit(node)

    # ── SAST026 + SAST039: function definitions ───────────────────────────────

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def _check_function(self, node: Any) -> None:
        # SAST026: @csrf_exempt decorator
        for dec in node.decorator_list:
            dec_name = ""
            if isinstance(dec, ast.Name):
                dec_name = dec.id
            elif isinstance(dec, ast.Attribute):
                dec_name = dec.attr
            if dec_name == "csrf_exempt":
                self._add("SAST026", node)
                break

        # SAST039: mutable default argument (list [], dict {}, set literal, or set()/list()/dict() call)
        for default in node.args.defaults + node.args.kw_defaults:
            if default is None:
                continue
            if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                self._add("SAST039", node)
                break
            # set(), list(), dict() zero-arg calls are also mutable defaults
            if (isinstance(default, ast.Call)
                    and isinstance(default.func, ast.Name)
                    and default.func.id in ("set", "list", "dict")
                    and not default.args
                    and not default.keywords):
                self._add("SAST039", node)
                break

    # ── SAST038: exception swallowing ────────────────────────────────────────

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """SAST038: except [Exception]: pass — silently swallowed exception."""
        body_stmts = [s for s in node.body if not isinstance(s, ast.Pass)]
        if not body_stmts:
            # Body contains only Pass (possibly with docstring constant, tolerate)
            all_pass = all(
                isinstance(s, ast.Pass) or (
                    isinstance(s, ast.Expr)
                    and isinstance(s.value, ast.Constant)
                    and isinstance(s.value.value, str)
                )
                for s in node.body
            )
            if all_pass:
                self._add("SAST038", node)
        self.generic_visit(node)

    # ── SAST037: with-depth tracking ─────────────────────────────────────────

    def visit_With(self, node: ast.With) -> None:
        self._with_depth += 1
        self.generic_visit(node)
        self._with_depth -= 1

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:
        self._with_depth += 1
        self.generic_visit(node)
        self._with_depth -= 1


# ── Helper ────────────────────────────────────────────────────────────────────

def _make_finding(rule: SASTRuleInfo, line: int, col: int, snippet: str) -> SASTFinding:
    return SASTFinding(
        rule_id=rule.rule_id,
        severity=rule.severity,
        cwe_id=rule.cwe_id,
        owasp=rule.owasp,
        title=rule.title,
        description=rule.description,
        line=line,
        col=col,
        code_snippet=snippet,
        remediation=rule.remediation,
        debt_minutes=_SEVERITY_DEBT.get(rule.severity, 30),
    )
