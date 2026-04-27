"""
UCO-Sensor — Taint Analysis Engine  (M7.2)
==========================================
Intra-function Data Flow Analysis (DFA) for Python source code.

Algorithm: TaintSet propagation
  1. SOURCES   — identify taint entry points (user-controlled inputs)
  2. PROPAGATE — track variable assignments that carry taint forward
  3. SINKS     — detect dangerous call sites that consume tainted values
  4. SANITIZE  — recognize sanitizer calls that neutralize taint
  5. REPORT    — emit TaintFlow findings with full provenance chain

Cross-function analysis (M7.2 scope): tracks when tainted values are passed
as arguments to non-sink calls (cross_fn_taint_risk), without full
interprocedural DFA (that requires a call graph — deferred to M9.x).

Source categories
-----------------
  HTTP inputs   : request.args / form / json / data / values / files /
                  cookies / headers / GET / POST / body / query
  CLI inputs    : sys.argv[n]
  OS inputs     : os.environ[key], os.getenv(key)
  Python built-in: input(), raw_input()

Sink categories
---------------
  SQL           : cursor.execute(), db.execute(), session.execute()
  OS command    : os.system(), os.popen(), os.execv()
  Subprocess    : subprocess.call/run/Popen/check_output
  Template      : Template.render(), env.get_template()
  Code          : eval(), exec(), compile()
  File          : open()

Sanitizer categories
--------------------
  HTML escape   : html.escape(), markupsafe.escape(), jinja2.escape()
  URL encode    : urllib.parse.quote/quote_plus/urlencode
  Regex escape  : re.escape()
  Bleach        : bleach.clean()
  Crypto        : hashlib.sha256(), hmac.new()  (data no longer injectable)

Rule IDs emitted (as SASTFinding-compatible dicts)
---------------------------------------------------
  SAST040  SQL injection via taint flow        CWE-89   CRITICAL
  SAST041  Command injection via taint flow     CWE-78   CRITICAL
  SAST042  Template injection via taint flow    CWE-94   CRITICAL
  SAST043  Code injection via taint flow        CWE-95   HIGH
  SAST044  Path traversal via taint flow        CWE-22   HIGH
  SAST045  Taint flow to unclassified sink      CWE-20   MEDIUM

Public API
----------
  TaintAnalyzer().analyze(source, module_id="") -> TaintResult
  TaintResult.to_dict()       -> dict
  FlowVector.from_taint_result(result) -> FlowVector  (in extended_vectors.py)
"""
from __future__ import annotations

import ast
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ─── Source registry ─────────────────────────────────────────────────────────

# (object_name, attribute_name) — attribute access that yields user data
_SOURCE_ATTRS: FrozenSet[Tuple[str, str]] = frozenset({
    # Flask / generic WSGI request
    ("request", "args"),
    ("request", "form"),
    ("request", "json"),
    ("request", "data"),
    ("request", "values"),
    ("request", "files"),
    ("request", "cookies"),
    ("request", "headers"),
    # Django
    ("request", "GET"),
    ("request", "POST"),
    ("request", "body"),
    # aiohttp / FastAPI
    ("request", "query"),
    ("request", "match_info"),
    ("request", "path_params"),
    # CLI args — sys.argv as a whole is tainted (attacker controls argv)
    ("sys", "argv"),
    # OS environment — os.environ mapping is tainted
    ("os",  "environ"),
})

# Bare function names that return tainted data when called
_SOURCE_CALLS: FrozenSet[str] = frozenset({
    "input",
    "raw_input",       # Python 2 compat
})

# (module_name, attr_name) — subscript/call patterns treated as sources
_SOURCE_SUBSCRIPT_BASES: FrozenSet[Tuple[str, str]] = frozenset({
    ("os",  "environ"),
    ("sys", "argv"),
})

# (module_name, function_name) — call patterns treated as sources
_SOURCE_MODULE_CALLS: FrozenSet[Tuple[str, str]] = frozenset({
    ("os", "getenv"),
})


# ─── Sink registry ───────────────────────────────────────────────────────────

# (object_name_pattern, method_name) → (rule_id, severity, vuln_type, cwe)
_SINK_METHODS: Dict[Tuple[str, str], Tuple[str, str, str, str]] = {
    # SQL injection (CWE-89)
    ("cursor",  "execute"):      ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    ("cursor",  "executemany"):  ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    ("db",      "execute"):      ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    ("session", "execute"):      ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    ("conn",    "execute"):      ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    ("con",     "execute"):      ("SAST040", "CRITICAL", "SQL_INJECTION",     "CWE-89"),
    # OS command injection (CWE-78)
    ("os",      "system"):       ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("os",      "popen"):        ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("os",      "execv"):        ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("os",      "execl"):        ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("os",      "execvp"):       ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("os",      "execle"):       ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    # subprocess (CWE-78)
    ("subprocess", "call"):          ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("subprocess", "run"):           ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("subprocess", "Popen"):         ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("subprocess", "check_output"):  ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    ("subprocess", "check_call"):    ("SAST041", "CRITICAL", "COMMAND_INJECTION", "CWE-78"),
    # Template injection (CWE-94)
    ("Template", "render"):   ("SAST042", "CRITICAL", "TEMPLATE_INJECTION", "CWE-94"),
    ("template", "render"):   ("SAST042", "CRITICAL", "TEMPLATE_INJECTION", "CWE-94"),
    ("env",      "get_template"): ("SAST042", "CRITICAL", "TEMPLATE_INJECTION", "CWE-94"),
}

# Bare function names → sink metadata
_SINK_FUNCTIONS: Dict[str, Tuple[str, str, str, str]] = {
    "eval":      ("SAST043", "HIGH",     "CODE_INJECTION",  "CWE-95"),
    "exec":      ("SAST043", "HIGH",     "CODE_INJECTION",  "CWE-95"),
    "compile":   ("SAST043", "HIGH",     "CODE_INJECTION",  "CWE-95"),
    "open":      ("SAST044", "HIGH",     "PATH_TRAVERSAL",  "CWE-22"),
    "__import__":("SAST043", "HIGH",     "CODE_INJECTION",  "CWE-95"),
}

# Generic: any .execute() call (handles ORM patterns like raw())
_SINK_GENERIC_METHODS: FrozenSet[str] = frozenset({
    "execute", "executemany", "raw",
})


# ─── Sanitizer registry ──────────────────────────────────────────────────────

# (object_name, method_name) — calls that neutralize taint
_SANITIZER_METHODS: FrozenSet[Tuple[str, str]] = frozenset({
    ("bleach",            "clean"),
    ("bleach",            "linkify"),
    ("markupsafe",        "escape"),
    ("html",              "escape"),
    ("urllib.parse",      "quote"),
    ("urllib.parse",      "quote_plus"),
    ("urllib.parse",      "urlencode"),
    ("re",                "escape"),
    ("cgi",               "escape"),
    ("jinja2",            "escape"),
    ("hashlib",           "sha256"),
    ("hashlib",           "sha512"),
    ("hashlib",           "sha3_256"),
    ("hashlib",           "sha3_512"),
    ("hmac",              "new"),
    ("hmac",              "digest"),
    ("secrets",           "token_hex"),
    ("secrets",           "token_bytes"),
})

# Bare function names that sanitize taint
_SANITIZER_FUNCTIONS: FrozenSet[str] = frozenset({
    "quote",
    "escape",
})


# ─── Rule metadata (for SASTFinding-compatible output) ───────────────────────

_TAINT_RULE_META: Dict[str, Dict] = {
    "SAST040": {
        "title":       "SQL Injection via Taint Flow",
        "owasp":       "A03:2021",
        "description": "User-controlled input flows directly into a SQL query without sanitisation.",
        "remediation": "Use parameterised queries: cursor.execute(sql, (param,)). Never format user input into SQL strings.",
        "debt_minutes": 240,
    },
    "SAST041": {
        "title":       "Command Injection via Taint Flow",
        "owasp":       "A03:2021",
        "description": "User-controlled input reaches an OS command execution call without sanitisation.",
        "remediation": "Avoid passing user input to shell commands. Use subprocess with shell=False and a fixed command list.",
        "debt_minutes": 240,
    },
    "SAST042": {
        "title":       "Template Injection (SSTI) via Taint Flow",
        "owasp":       "A03:2021",
        "description": "User-controlled input is rendered inside a template engine without escaping.",
        "remediation": "Use autoescaping templates. Never pass raw user input as a template string.",
        "debt_minutes": 240,
    },
    "SAST043": {
        "title":       "Code Injection via Taint Flow",
        "owasp":       "A03:2021",
        "description": "User-controlled input reaches eval/exec/compile, enabling arbitrary code execution.",
        "remediation": "Never use eval/exec on user-provided strings. Use ast.literal_eval for safe deserialization.",
        "debt_minutes": 120,
    },
    "SAST044": {
        "title":       "Path Traversal via Taint Flow",
        "owasp":       "A01:2021",
        "description": "User-controlled input is used as a file path argument without sanitisation.",
        "remediation": "Validate and normalize file paths. Use os.path.abspath + assert path.startswith(allowed_root).",
        "debt_minutes": 120,
    },
    "SAST045": {
        "title":       "Taint Flow to Unclassified Sink",
        "owasp":       "A03:2021",
        "description": "User-controlled input reaches a potentially dangerous call site.",
        "remediation": "Validate and sanitize user input before using it in sensitive operations.",
        "debt_minutes": 60,
    },
}


# ─── Data structures ─────────────────────────────────────────────────────────

class TaintInfo:
    """Provenance information for a tainted variable."""

    __slots__ = ("origin", "origin_line", "path")

    def __init__(self, origin: str, origin_line: int, path: List[str]) -> None:
        self.origin:      str       = origin
        self.origin_line: int       = origin_line
        self.path:        List[str] = path

    def extend(self, new_var: str) -> "TaintInfo":
        """Return copy of this TaintInfo with new_var appended to path."""
        return TaintInfo(
            origin      = self.origin,
            origin_line = self.origin_line,
            path        = self.path + [new_var],
        )

    def __repr__(self) -> str:
        return f"TaintInfo(origin={self.origin!r}, path={self.path})"


class TaintFlow:
    """A confirmed data flow path from a taint source to a dangerous sink."""

    __slots__ = (
        "source_desc", "source_line",
        "sink_desc", "sink_line",
        "path", "sanitized", "vuln_type",
        "rule_id", "severity", "cwe_id",
    )

    def __init__(
        self,
        source_desc: str, source_line: int,
        sink_desc:   str, sink_line:   int,
        path:        List[str],
        sanitized:   bool = False,
        vuln_type:   str  = "TAINT_FLOW",
        rule_id:     str  = "SAST045",
        severity:    str  = "MEDIUM",
        cwe_id:      str  = "CWE-20",
    ) -> None:
        self.source_desc = source_desc
        self.source_line = source_line
        self.sink_desc   = sink_desc
        self.sink_line   = sink_line
        self.path        = path
        self.sanitized   = sanitized
        self.vuln_type   = vuln_type
        self.rule_id     = rule_id
        self.severity    = severity
        self.cwe_id      = cwe_id

    def to_dict(self) -> Dict:
        meta = _TAINT_RULE_META.get(self.rule_id, _TAINT_RULE_META["SAST045"])
        return {
            "rule_id":      self.rule_id,
            "severity":     self.severity,
            "cwe_id":       self.cwe_id,
            "owasp":        meta["owasp"],
            "title":        meta["title"],
            "description":  meta["description"],
            "source_desc":  self.source_desc,
            "source_line":  self.source_line,
            "sink_desc":    self.sink_desc,
            "line":         self.sink_line,
            "col":          0,
            "code_snippet": "",
            "remediation":  meta["remediation"],
            "debt_minutes": meta["debt_minutes"],
            "flow_path":    self.path,
            "sanitized":    self.sanitized,
            "vuln_type":    self.vuln_type,
        }


class TaintResult:
    """
    Aggregate result of taint analysis on a Python module.

    Attributes
    ----------
    flows           : confirmed taint flow paths (source → sink)
    source_count    : unique taint source expressions detected
    sink_count      : unique sink call sites detected
    cross_fn_risk   : count of calls where tainted value passed as arg
                      to a non-sink, non-sanitizer function (interprocedural
                      risk indicator, deduped by line)
    """

    def __init__(self) -> None:
        self.flows:          List[TaintFlow]            = []
        self._source_locs:   Set[Tuple[int, str]]       = set()
        self._sink_locs:     Set[int]                   = set()
        self._cross_fn_locs: Set[int]                   = set()

    # ── internal registration ─────────────────────────────────────────────────

    def _register_source(self, line: int, desc: str) -> None:
        self._source_locs.add((line, desc))

    def _register_sink(self, line: int) -> None:
        self._sink_locs.add(line)

    def _register_cross_fn(self, line: int) -> None:
        self._cross_fn_locs.add(line)

    # ── computed properties ───────────────────────────────────────────────────

    @property
    def source_count(self) -> int:
        return len(self._source_locs)

    @property
    def sink_count(self) -> int:
        return len(self._sink_locs)

    @property
    def cross_fn_risk(self) -> int:
        return len(self._cross_fn_locs)

    @property
    def taint_path_count(self) -> int:
        return len(self.flows)

    @property
    def sanitized_count(self) -> int:
        return sum(1 for f in self.flows if f.sanitized)

    @property
    def taint_sanitized_ratio(self) -> float:
        n = self.taint_path_count
        return round(self.sanitized_count / n, 4) if n > 0 else 0.0

    @property
    def injection_surface(self) -> float:
        return round(self.taint_path_count * (1.0 - self.taint_sanitized_ratio), 4)

    def to_dict(self) -> Dict:
        return {
            "flows":                  [f.to_dict() for f in self.flows],
            "taint_path_count":       self.taint_path_count,
            "source_count":           self.source_count,
            "sink_count":             self.sink_count,
            "sanitized_count":        self.sanitized_count,
            "taint_sanitized_ratio":  self.taint_sanitized_ratio,
            "injection_surface":      self.injection_surface,
            "cross_fn_risk":          self.cross_fn_risk,
        }


# ─── TaintSet ────────────────────────────────────────────────────────────────

class TaintSet:
    """
    Maps variable names to their TaintInfo within a single scope.

    Semantics
    ---------
    add(name, info)    — mark name as tainted
    remove(name)       — name sanitized or reassigned to clean value
    is_tainted(name)   — check membership
    get(name)          — retrieve TaintInfo or None
    clone()            — shallow copy for branch analysis
    names()            — set of currently tainted variable names
    """

    __slots__ = ("_store",)

    def __init__(self) -> None:
        self._store: Dict[str, TaintInfo] = {}

    def add(self, name: str, info: TaintInfo) -> None:
        self._store[name] = info

    def remove(self, name: str) -> None:
        self._store.pop(name, None)

    def is_tainted(self, name: str) -> bool:
        return name in self._store

    def get(self, name: str) -> Optional[TaintInfo]:
        return self._store.get(name)

    def clone(self) -> "TaintSet":
        ts = TaintSet()
        ts._store = dict(self._store)
        return ts

    def names(self) -> Set[str]:
        return set(self._store.keys())

    def merge_from(self, other: "TaintSet") -> None:
        """Conservative merge: a name is tainted if tainted in self OR other."""
        for name, info in other._store.items():
            if name not in self._store:
                self._store[name] = info

    def __len__(self) -> int:
        return len(self._store)


# ─── AST helpers ─────────────────────────────────────────────────────────────

def _node_name(node) -> str:
    """Return a simple dotted string from a Name / Attribute / Constant node."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        outer = _node_name(node.value)
        return f"{outer}.{node.attr}" if outer else node.attr
    if isinstance(node, ast.Constant):
        return str(node.value)
    return ""


def _call_func_name(call: ast.Call) -> str:
    """Return bare function name of a Call (without object prefix)."""
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


# ─── TaintAnalyzer ───────────────────────────────────────────────────────────

class TaintAnalyzer:
    """
    Intra-function taint analysis engine for Python source code.

    Usage
    -----
    result = TaintAnalyzer().analyze(source_code, module_id="mymod")
    for flow in result.flows:
        print(flow.to_dict())
    """

    def analyze(self, source: str, module_id: str = "") -> TaintResult:
        """
        Perform taint analysis on Python source. Returns TaintResult.

        Parameters
        ----------
        source    : Python source code string
        module_id : optional identifier for reporting

        Returns
        -------
        TaintResult with all detected taint flows.
        """
        result = TaintResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        # Analyse module-level statements first
        ts_module = TaintSet()
        self._analyze_stmts(tree.body, ts_module, result)

        # Analyse each top-level function (already visited in module stmts,
        # but analyse them again independently so they have their own clean TaintSet)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._analyze_function(node, result)

        return result

    # ── Function analysis ─────────────────────────────────────────────────────

    def _analyze_function(self, fn_node, result: TaintResult) -> None:
        """Analyse a single function body for taint flows."""
        ts = TaintSet()
        self._analyze_stmts(fn_node.body, ts, result)

    # ── Statement list ────────────────────────────────────────────────────────

    def _analyze_stmts(
        self, stmts: List, ts: TaintSet, result: TaintResult
    ) -> None:
        for stmt in stmts:
            self._analyze_stmt(stmt, ts, result)

    def _analyze_stmt(self, stmt, ts: TaintSet, result: TaintResult) -> None:
        """Dispatch on statement type."""
        if isinstance(stmt, ast.Assign):
            self._stmt_assign(stmt, ts, result)

        elif isinstance(stmt, ast.AnnAssign):
            if stmt.value is not None:
                self._stmt_ann_assign(stmt, ts, result)

        elif isinstance(stmt, ast.AugAssign):
            self._stmt_aug_assign(stmt, ts, result)

        elif isinstance(stmt, ast.Expr):
            if isinstance(stmt.value, ast.Call):
                self._stmt_call(stmt.value, ts, result)

        elif isinstance(stmt, ast.If):
            self._stmt_if(stmt, ts, result)

        elif isinstance(stmt, (ast.For, ast.AsyncFor)):
            self._stmt_for(stmt, ts, result)

        elif isinstance(stmt, ast.While):
            self._stmt_while(stmt, ts, result)

        elif isinstance(stmt, (ast.With, ast.AsyncWith)):
            self._stmt_with(stmt, ts, result)

        elif isinstance(stmt, ast.Try):
            self._stmt_try(stmt, ts, result)

        elif isinstance(stmt, ast.Return):
            # Returns don't reach sinks directly — but evaluate for cross-fn risk
            if stmt.value:
                self._eval_taint(stmt.value, ts, result)

        elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Nested function def: analyse in its own scope (already done in
            # top-level walk, but we re-analyse here for correctness)
            self._analyze_function(stmt, result)

        # TryStar (Python 3.11 exception groups) — treat like Try
        elif hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar):
            self._stmt_try(stmt, ts, result)

    # ── Statement handlers ────────────────────────────────────────────────────

    def _stmt_assign(self, stmt: ast.Assign, ts: TaintSet, result: TaintResult) -> None:
        taint = self._eval_taint(stmt.value, ts, result)
        for target in stmt.targets:
            self._apply_taint(target, taint, ts)

    def _stmt_ann_assign(self, stmt: ast.AnnAssign, ts: TaintSet, result: TaintResult) -> None:
        taint = self._eval_taint(stmt.value, ts, result)
        self._apply_taint(stmt.target, taint, ts)

    def _stmt_aug_assign(self, stmt: ast.AugAssign, ts: TaintSet, result: TaintResult) -> None:
        existing = ts.get(_node_name(stmt.target))
        rhs      = self._eval_taint(stmt.value, ts, result)
        combined = existing or rhs
        name = _node_name(stmt.target)
        if name:
            if combined:
                ts.add(name, combined.extend(name))
            else:
                ts.remove(name)

    def _stmt_call(self, call: ast.Call, ts: TaintSet, result: TaintResult) -> None:
        """Handle a function call used as a standalone statement."""
        sink_meta = self._get_sink_meta(call)
        if sink_meta:
            rule_id, severity, vuln_type, cwe_id = sink_meta
            line = getattr(call, "lineno", 0)
            result._register_sink(line)
            self._check_args_for_sink(call, ts, result, rule_id, severity, vuln_type, cwe_id)
            return

        # Not a sink — track cross-function risk
        self._check_cross_fn_risk(call, ts, result)

    def _stmt_if(self, stmt: ast.If, ts: TaintSet, result: TaintResult) -> None:
        ts_then = ts.clone()
        self._analyze_stmts(stmt.body, ts_then, result)

        ts_else = ts.clone()
        if stmt.orelse:
            self._analyze_stmts(stmt.orelse, ts_else, result)

        # Conservative merge: tainted in any branch → tainted after
        ts.merge_from(ts_then)
        ts.merge_from(ts_else)

    def _stmt_for(self, stmt: ast.For, ts: TaintSet, result: TaintResult) -> None:
        iter_taint = self._eval_taint(stmt.iter, ts, result)
        # Loop variable inherits taint from the iterable
        if iter_taint:
            self._apply_taint(stmt.target, iter_taint, ts)

        ts_body = ts.clone()
        self._analyze_stmts(stmt.body, ts_body, result)
        if stmt.orelse:
            self._analyze_stmts(stmt.orelse, ts_body, result)

        ts.merge_from(ts_body)

    def _stmt_while(self, stmt: ast.While, ts: TaintSet, result: TaintResult) -> None:
        ts_body = ts.clone()
        self._analyze_stmts(stmt.body, ts_body, result)
        if stmt.orelse:
            self._analyze_stmts(stmt.orelse, ts_body, result)
        ts.merge_from(ts_body)

    def _stmt_with(self, stmt: ast.With, ts: TaintSet, result: TaintResult) -> None:
        for item in stmt.items:
            ctx_taint = self._eval_taint(item.context_expr, ts, result)
            if item.optional_vars and ctx_taint:
                self._apply_taint(item.optional_vars, ctx_taint, ts)
        self._analyze_stmts(stmt.body, ts, result)

    def _stmt_try(self, stmt: ast.Try, ts: TaintSet, result: TaintResult) -> None:
        self._analyze_stmts(stmt.body, ts, result)
        for handler in stmt.handlers:
            ts_h = ts.clone()
            if handler.name:
                # The exception variable itself is not user-tainted
                ts_h.remove(handler.name)
            self._analyze_stmts(handler.body, ts_h, result)
            ts.merge_from(ts_h)
        if stmt.orelse:
            self._analyze_stmts(stmt.orelse, ts, result)
        if stmt.finalbody:
            self._analyze_stmts(stmt.finalbody, ts, result)

    # ── Taint propagation ─────────────────────────────────────────────────────

    def _apply_taint(
        self, target, taint: Optional[TaintInfo], ts: TaintSet
    ) -> None:
        """Apply (or clear) taint on an assignment target."""
        if isinstance(target, ast.Name):
            if taint:
                ts.add(target.id, taint.extend(target.id))
            else:
                ts.remove(target.id)

        elif isinstance(target, (ast.Tuple, ast.List)):
            # Tuple unpack: x, y = tainted → both tainted
            for elt in target.elts:
                self._apply_taint(elt, taint, ts)

        elif isinstance(target, ast.Starred):
            self._apply_taint(target.value, taint, ts)

    def _eval_taint(
        self, expr, ts: TaintSet, result: TaintResult
    ) -> Optional[TaintInfo]:
        """
        Evaluate expr and return TaintInfo if tainted, else None.
        Side effects: may register source/sink/cross-fn in result.
        """
        if expr is None:
            return None

        # ── Source check ──────────────────────────────────────────────────────
        src = self._is_source(expr)
        if src is not None:
            line = getattr(expr, "lineno", 0)
            result._register_source(line, src)
            return TaintInfo(origin=src, origin_line=line, path=[src])

        # ── Variable lookup ───────────────────────────────────────────────────
        if isinstance(expr, ast.Name):
            return ts.get(expr.id)

        # ── Attribute access propagates taint ─────────────────────────────────
        if isinstance(expr, ast.Attribute):
            return self._eval_taint(expr.value, ts, result)

        # ── Subscript: x[key] inherits taint from x ───────────────────────────
        if isinstance(expr, ast.Subscript):
            return self._eval_taint(expr.value, ts, result)

        # ── Call expression ────────────────────────────────────────────────────
        if isinstance(expr, ast.Call):
            return self._eval_call_taint(expr, ts, result)

        # ── Binary op: tainted OP clean → tainted ─────────────────────────────
        if isinstance(expr, ast.BinOp):
            left  = self._eval_taint(expr.left,  ts, result)
            right = self._eval_taint(expr.right, ts, result)
            return left or right

        # ── F-string: f"...{tainted}..." → tainted ────────────────────────────
        if isinstance(expr, ast.JoinedStr):
            for val in expr.values:
                t = self._eval_taint(val, ts, result)
                if t:
                    return t
            return None

        if isinstance(expr, ast.FormattedValue):
            return self._eval_taint(expr.value, ts, result)

        # ── Conditional expression: a if cond else b ──────────────────────────
        if isinstance(expr, ast.IfExp):
            return (
                self._eval_taint(expr.body,  ts, result)
                or self._eval_taint(expr.orelse, ts, result)
            )

        # ── Unary op ──────────────────────────────────────────────────────────
        if isinstance(expr, ast.UnaryOp):
            return self._eval_taint(expr.operand, ts, result)

        # ── Starred ───────────────────────────────────────────────────────────
        if isinstance(expr, ast.Starred):
            return self._eval_taint(expr.value, ts, result)

        # ── List/Tuple/Set literals: tainted if any element is tainted ─────────
        if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            for elt in expr.elts:
                t = self._eval_taint(elt, ts, result)
                if t:
                    return t
            return None

        # ── Dict literal: tainted if any value is tainted ─────────────────────
        if isinstance(expr, ast.Dict):
            for val in expr.values:
                if val is not None:
                    t = self._eval_taint(val, ts, result)
                    if t:
                        return t
            return None

        # Constants and everything else → not tainted
        return None

    def _eval_call_taint(
        self, call: ast.Call, ts: TaintSet, result: TaintResult
    ) -> Optional[TaintInfo]:
        """
        Evaluate taint from a Call expression.
        - Sanitizer call → return None (result is clean)
        - Sink call → check args, emit TaintFlow, return None
        - Other call with tainted arg → propagate taint (heuristic), track cross-fn risk
        """
        # Sanitizer check first — neutralizes taint
        if self._is_sanitizer(call):
            return None

        # Sink check
        sink_meta = self._get_sink_meta(call)
        if sink_meta:
            rule_id, severity, vuln_type, cwe_id = sink_meta
            line = getattr(call, "lineno", 0)
            result._register_sink(line)
            self._check_args_for_sink(call, ts, result, rule_id, severity, vuln_type, cwe_id)
            return None  # sink result isn't further propagated

        # Generic propagation: taint flows through the call result
        tainted_arg: Optional[TaintInfo] = None
        for arg in call.args:
            t = self._eval_taint(arg, ts, result)
            if t and tainted_arg is None:
                tainted_arg = t
        for kw in call.keywords:
            if kw.value:
                t = self._eval_taint(kw.value, ts, result)
                if t and tainted_arg is None:
                    tainted_arg = t

        if tainted_arg:
            # Cross-function taint risk: taint is being passed to a non-sink call
            line = getattr(call, "lineno", 0)
            result._register_cross_fn(line)

        return tainted_arg

    # ── Sink, Source, Sanitizer checks ───────────────────────────────────────

    def _is_source(self, expr) -> Optional[str]:
        """Return human-readable source label if expr is a taint source, else None."""
        # input() / raw_input()
        if isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name) and expr.func.id in _SOURCE_CALLS:
                return f"{expr.func.id}()"
            # os.getenv(...)
            if isinstance(expr.func, ast.Attribute):
                obj = _node_name(expr.func.value)
                if (obj, expr.func.attr) in _SOURCE_MODULE_CALLS:
                    return f"{obj}.{expr.func.attr}()"

        # request.args / request.form / etc.
        if isinstance(expr, ast.Attribute):
            obj = _node_name(expr.value)
            if (obj, expr.attr) in _SOURCE_ATTRS:
                return f"{obj}.{expr.attr}"

        # os.environ[key] / sys.argv[n]
        if isinstance(expr, ast.Subscript):
            if isinstance(expr.value, ast.Attribute):
                obj  = _node_name(expr.value.value)
                attr = expr.value.attr
                if (obj, attr) in _SOURCE_SUBSCRIPT_BASES:
                    return f"{obj}.{attr}[...]"
            elif isinstance(expr.value, ast.Name):
                if expr.value.id in ("environ",):
                    return "environ[...]"

        return None

    def _get_sink_meta(
        self, call: ast.Call
    ) -> Optional[Tuple[str, str, str, str]]:
        """Return (rule_id, severity, vuln_type, cwe_id) if call is a sink, else None."""
        if isinstance(call.func, ast.Attribute):
            obj_name  = _node_name(call.func.value).split(".")[0]  # first segment
            meth_name = call.func.attr
            # Exact match
            key = (obj_name, meth_name)
            if key in _SINK_METHODS:
                return _SINK_METHODS[key]
            # Generic: any .execute() on any object → SQL injection
            if meth_name in _SINK_GENERIC_METHODS:
                return ("SAST040", "CRITICAL", "SQL_INJECTION", "CWE-89")

        elif isinstance(call.func, ast.Name):
            fn = call.func.id
            if fn in _SINK_FUNCTIONS:
                return _SINK_FUNCTIONS[fn]

        return None

    def _is_sanitizer(self, call: ast.Call) -> bool:
        """Return True if this call neutralizes taint."""
        if isinstance(call.func, ast.Attribute):
            obj  = _node_name(call.func.value)
            meth = call.func.attr
            if (obj, meth) in _SANITIZER_METHODS:
                return True
        elif isinstance(call.func, ast.Name):
            if call.func.id in _SANITIZER_FUNCTIONS:
                return True
        return False

    def _check_args_for_sink(
        self,
        call: ast.Call,
        ts: TaintSet,
        result: TaintResult,
        rule_id: str,
        severity: str,
        vuln_type: str,
        cwe_id: str,
    ) -> None:
        """Check all call arguments; emit a TaintFlow for each tainted arg."""
        sink_line = getattr(call, "lineno", 0)
        sink_desc = _node_name(call.func) or "unknown_sink"

        def _check(arg):
            taint = self._eval_taint(arg, ts, result)
            if taint:
                result.flows.append(TaintFlow(
                    source_desc = taint.origin,
                    source_line = taint.origin_line,
                    sink_desc   = sink_desc,
                    sink_line   = sink_line,
                    path        = taint.path,
                    sanitized   = False,
                    vuln_type   = vuln_type,
                    rule_id     = rule_id,
                    severity    = severity,
                    cwe_id      = cwe_id,
                ))

        for arg in call.args:
            _check(arg)
        for kw in call.keywords:
            if kw.value:
                _check(kw.value)

    def _check_cross_fn_risk(
        self, call: ast.Call, ts: TaintSet, result: TaintResult
    ) -> None:
        """Track when tainted values are passed to non-sink calls."""
        line = getattr(call, "lineno", 0)
        for arg in call.args:
            if self._eval_taint(arg, ts, result):
                result._register_cross_fn(line)
                return
        for kw in call.keywords:
            if kw.value and self._eval_taint(kw.value, ts, result):
                result._register_cross_fn(line)
                return
