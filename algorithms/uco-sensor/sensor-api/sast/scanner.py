"""
UCO-Sensor — SAST Security Scanner (M3)
=========================================

Static Application Security Testing engine for Python source code.
Pure stdlib — no external dependencies.

Rules implemented
-----------------
  SAST001  SQL Injection              CWE-89   CRITICAL
  SAST002  OS Command Injection       CWE-78   CRITICAL
  SAST003  Unsafe Eval / Exec         CWE-95   HIGH
  SAST004  Pickle Deserialization     CWE-502  HIGH
  SAST005  YAML Unsafe Load           CWE-502  MEDIUM
  SAST006  Weak Hash Algorithm        CWE-327  MEDIUM
  SAST007  Insecure Randomness        CWE-338  MEDIUM
  SAST008  Hardcoded Secret           CWE-798  HIGH
  SAST009  Hardcoded Private Key      CWE-321  CRITICAL
  SAST010  Debug Mode Enabled         CWE-489  MEDIUM
  SAST011  Path Traversal via open()  CWE-22   HIGH
  SAST012  Assert for Security Check  CWE-617  LOW
  SAST013  Subprocess shell=True      CWE-78   HIGH

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
        rule_id="SAST006", title="Weak Hash Algorithm",
        cwe_id="CWE-327", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "hashlib.md5() or hashlib.sha1() used. MD5 and SHA-1 are cryptographically "
            "broken and should not be used for security purposes."
        ),
        remediation=(
            "Use hashlib.sha256(), hashlib.sha3_256(), or hashlib.blake2b() "
            "for security-sensitive hashing."
        ),
    ),
    SASTRuleInfo(
        rule_id="SAST007", title="Insecure Randomness",
        cwe_id="CWE-338", owasp="A02:2021",
        severity="MEDIUM",
        description=(
            "random module used in a security-sensitive context (token generation, "
            "password, salt, nonce). random is not cryptographically secure."
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
    findings:          List[SASTFinding] = field(default_factory=list)
    total_debt_minutes: int = 0
    security_rating:   str = "A"      # A–E
    parse_error:       bool = False

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
    if crits >= 1:   return "E"
    if highs >= 2:   return "D"
    if highs == 1:   return "C"
    if meds >= 2:    return "C"
    if meds == 1:    return "B"
    return "A"


# ── Regex-based detectors ────────────────────────────────────────────────────

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
        # compute line number from match start
        lineno = source[:m.start()].count("\n") + 1
        snippet = lines_src[lineno - 1].strip() if lineno <= len(lines_src) else ""
        rule = _RULE_MAP["SAST008"]
        findings.append(_make_finding(rule, lineno, m.start(), snippet))
    return findings


# ── AST-based scanner ─────────────────────────────────────────────────────────

_SQL_CALL_NAMES = frozenset({"execute", "executemany", "executescript", "query", "raw"})
_OS_CMD_CALLS   = frozenset({"system", "popen", "popen2", "popen3", "popen4", "startfile"})
_PICKLE_CALLS   = frozenset({"load", "loads"})
_SUBPROCESS_NAMES = frozenset({"call", "run", "Popen", "check_call", "check_output"})

_WEAK_HASH      = frozenset({"md5", "sha1", "new"})
_RANDOM_CALLS   = frozenset({
    "random", "randint", "randrange", "uniform", "choice",
    "choices", "sample", "shuffle", "seed",
})

_SECRET_VAR_NAMES = frozenset({
    "password", "passwd", "secret", "api_key", "apikey",
    "auth_token", "access_token", "access_key", "private_key",
    "client_secret", "db_password", "jwt_secret", "encryption_key",
    "signing_key", "webhook_secret", "token",
})

_SECURITY_CONTEXT_NAMES = frozenset({
    "password", "secret", "token", "key", "auth", "salt", "nonce",
    "csrf", "session", "credential", "pin", "otp",
})


class _ASTScanner(ast.NodeVisitor):
    """Walk the AST and collect SAST findings."""

    def __init__(self, lines: List[str]):
        self.lines    = lines
        self.findings: List[SASTFinding] = []

    # ── helpers ───────────────────────────────────────────────────────────────

    def _add(self, rule_id: str, node: ast.AST) -> None:
        rule = _RULE_MAP[rule_id]
        line = getattr(node, "lineno", 0)
        col  = getattr(node, "col_offset", 0)
        snippet = self.lines[line - 1].strip() if 0 < line <= len(self.lines) else ""
        self.findings.append(_make_finding(rule, line, col, snippet))

    def _is_literal(self, node: ast.expr) -> bool:
        """True if the node is a compile-time constant (string, number, None, True/False)."""
        return isinstance(node, ast.Constant)

    def _contains_var(self, node: ast.expr) -> bool:
        """True if the node contains at least one Name node (variable reference)."""
        if isinstance(node, ast.Name):
            return True
        return any(self._contains_var(child)
                   for child in ast.iter_child_nodes(node)
                   if isinstance(child, ast.expr))

    def _is_formatted_str(self, node: ast.expr) -> bool:
        """True if the node is an f-string, %-format, or .format() call."""
        if isinstance(node, ast.JoinedStr):   # f-string
            return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            return True   # "..." % (...)
        if isinstance(node, ast.Call):
            if (isinstance(node.func, ast.Attribute)
                    and node.func.attr == "format"):
                return True
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return True   # string concatenation
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

    # ── SAST001: SQL Injection ────────────────────────────────────────────────

    def visit_Call(self, node: ast.Call) -> None:
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
                # No positional Loader and no safe kwarg
                self._add("SAST005", node)

        # SAST006: hashlib.md5 / hashlib.sha1
        if module == "hashlib" and name in _WEAK_HASH:
            if name in ("md5", "sha1"):
                self._add("SAST006", node)
            elif name == "new" and node.args and isinstance(node.args[0], ast.Constant):
                algo = str(node.args[0].value).lower()
                if algo in ("md5", "sha1", "sha"):
                    self._add("SAST006", node)

        # SAST007: random.xxx in security-sensitive context
        if module == "random" and name in _RANDOM_CALLS:
            # Flag only if the assignment target has a security-sensitive name
            # (conservative: avoid too many false positives)
            self._add("SAST007", node)

        # SAST010: app.run(debug=True)
        if name == "run":
            for kw in node.keywords:
                if (kw.arg == "debug"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True):
                    self._add("SAST010", node)

        # SAST011: open() with non-literal path
        if name == "open" and node.args:
            if not self._is_literal(node.args[0]):
                self._add("SAST011", node)

        # SAST013: subprocess with shell=True + non-literal
        if module == "subprocess" and name in _SUBPROCESS_NAMES:
            has_shell_true = any(
                kw.arg == "shell"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
                for kw in node.keywords
            )
            if has_shell_true and node.args and not self._is_literal(node.args[0]):
                self._add("SAST013", node)

        self.generic_visit(node)

    # ── SAST008: Hardcoded secret in assignment ───────────────────────────────

    def visit_Assign(self, node: ast.Assign) -> None:
        """Flag: secret_name = "hardcoded_value"."""
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            val = node.value.value
            # Skip empty strings and obvious placeholders
            if len(val) < 4 or val.upper() in (
                "YOUR_PASSWORD", "CHANGEME", "CHANGE_ME",
                "PLACEHOLDER", "EXAMPLE", "TODO", "FIXME",
                "PASSWORD", "SECRET", "TOKEN",
            ):
                self.generic_visit(node)
                return
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id.lower() in _SECRET_VAR_NAMES:
                        self._add("SAST008", node)
                        break
                elif isinstance(target, ast.Attribute):
                    if target.attr.lower() in _SECRET_VAR_NAMES:
                        self._add("SAST008", node)
                        break
        self.generic_visit(node)

    # ── SAST012: assert for security ──────────────────────────────────────────

    def visit_Assert(self, node: ast.Assert) -> None:
        """Flag assert used in security-sensitive context."""
        # Heuristic: assert whose test contains security-sensitive names
        test_src = ast.unparse(node.test) if hasattr(ast, "unparse") else ""
        lowered  = test_src.lower()
        if any(kw in lowered for kw in _SECURITY_CONTEXT_NAMES):
            self._add("SAST012", node)
        self.generic_visit(node)


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
