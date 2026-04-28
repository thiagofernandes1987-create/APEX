"""
UCO-Sensor — PerformanceAnalyzer  (M7.4)
=========================================
AST-based detection of performance anti-patterns in Python source code.

8 Anti-patterns detected
------------------------
1. N+1 Query Risk
   DB-accessor method calls (execute/query/filter/get/all/…) found inside
   a ``for`` / ``while`` loop.  Each loop iteration may issue a separate
   query instead of a single batched query — the classic ORM N+1 problem.

2. List Append in Loop (prefer comprehension)
   ``list.append(x)`` call site inside a ``for`` loop where the target
   list was created *before* the loop.  A list-comprehension or generator
   expression is both faster and more idiomatic.

3. String Concatenation in Loop (O(n²))
   ``AugAssign`` node with ``Add`` operator (``s += …``) inside a loop.
   CPython strings are immutable — each concatenation allocates a new
   object and copies the old content.  Use ``list.append`` + ``''.join``.

4. Quadratic Nested Loop
   A ``for`` / ``while`` node whose body (not crossing function
   boundaries) contains another ``for`` / ``while``.  Minimum O(n²)
   unless an early ``break`` is reachable on the inner loop.

5. Repeated Computation in Loop
   The same expensive-looking call expression (identical ``ast.dump``)
   appears ≥ 2 times inside the same loop body.  A trivial cache variable
   hoisted before the loop would eliminate the redundancy.

6. Regex Compile / Match in Loop
   ``re.compile`` / ``re.search`` / ``re.match`` (and other ``re.*``
   functions) called inside a loop.  The regex is recompiled every
   iteration — compile once outside and reuse.

7. I/O in Tight Loop
   ``open()``, ``requests.*``, or raw-socket calls inside a loop.
   I/O operations have high latency; batching them outside or using
   async I/O is almost always preferable.

8. Inefficient dict.keys() Membership Test
   ``k in d.keys()`` — the ``.keys()`` call is redundant; Python's
   ``in`` operator on a dict tests membership in O(1) without materialising
   a view.  Replace with ``k in d``.

All detection is AST-only (no runtime).  Nested function/class definitions
inside a loop body are excluded to avoid false-positives on decorators and
lambda closures.

Public API
----------
    PerformanceAnalyzer().analyze(source, module_id="") -> PerformanceResult
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Set


# ─── Sink registries ─────────────────────────────────────────────────────────

# N+1: method names that indicate a DB query
_N1_METHODS: FrozenSet[str] = frozenset({
    "execute", "executemany", "executescript",
    "query", "filter", "filter_by", "get", "all", "first", "one",
    "one_or_none", "scalar", "scalar_one", "count", "exists",
    "select", "find", "find_one", "find_all",
    "aggregate", "distinct", "order_by",
    "fetchall", "fetchone", "fetchmany",
    "fetch", "fetch_all", "fetch_one",
    "raw", "extra",
})

# N+1: module-level query call patterns (module, func)
_N1_MODULE_CALLS: FrozenSet[tuple] = frozenset({
    ("sqlite3",    "connect"),  # sqlite3.connect inside loop is unusual
    ("psycopg2",   "connect"),
})

# Regex functions that should be compiled outside of loops
_RE_FUNCTIONS: FrozenSet[str] = frozenset({
    "compile", "search", "match", "fullmatch",
    "findall", "finditer", "sub", "subn", "split",
})

# I/O call patterns
_IO_BARE_CALLS: FrozenSet[str] = frozenset({"open"})

_IO_MODULE_METHODS: FrozenSet[tuple] = frozenset({
    # requests
    ("requests", "get"),   ("requests", "post"),  ("requests", "put"),
    ("requests", "delete"),("requests", "patch"),  ("requests", "head"),
    ("requests", "request"),("requests", "options"),
    # httpx
    ("httpx", "get"),      ("httpx", "post"),      ("httpx", "put"),
    ("httpx", "delete"),   ("httpx", "request"),
    # urllib
    ("urllib", "urlopen"), ("urllib.request", "urlopen"),
    # socket
    ("socket", "connect"), ("socket", "recv"),     ("socket", "send"),
    ("socket", "sendall"), ("socket", "accept"),
    # aiohttp (blocking usage risk)
    ("session", "get"),    ("session", "post"),
})


# ─── AST helpers ─────────────────────────────────────────────────────────────

_LOOP_TYPES = (ast.For, ast.AsyncFor, ast.While)


def _walk_no_fn(node: ast.AST) -> Iterator[ast.AST]:
    """
    Yield all descendant nodes of *node* WITHOUT crossing
    FunctionDef / AsyncFunctionDef / ClassDef boundaries.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            yield from _walk_no_fn(child)


def _call_name(node: ast.Call) -> str:
    """Return the simple function / method name of a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _call_module(node: ast.Call) -> str:
    """Return the object / module name (left side of the dot)."""
    if isinstance(node.func, ast.Attribute):
        v = node.func.value
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Attribute):
            return v.attr
    return ""


def _loop_body_nodes(loop: ast.For | ast.AsyncFor | ast.While) -> Iterator[ast.AST]:
    """Yield all nodes inside *loop*'s body without crossing fn/class/inner-loop boundaries."""
    stmts = loop.body + (loop.orelse or [])
    for stmt in stmts:
        for node in _walk_no_fn(stmt):
            yield node


# ─── Detection helpers ───────────────────────────────────────────────────────

def _is_n1_call(node: ast.Call) -> bool:
    return _call_name(node) in _N1_METHODS


def _is_re_call(node: ast.Call) -> bool:
    return (
        _call_module(node) == "re"
        and _call_name(node) in _RE_FUNCTIONS
    )


def _is_io_call(node: ast.Call) -> bool:
    name   = _call_name(node)
    module = _call_module(node)
    if name in _IO_BARE_CALLS:
        return True
    return (module, name) in _IO_MODULE_METHODS


def _has_inner_loop(loop: ast.For | ast.AsyncFor | ast.While) -> bool:
    """Return True if *loop* body (no fn boundary) contains another loop."""
    for stmt in loop.body:
        # The statement itself may be a loop (direct nesting: for i: for j:)
        if isinstance(stmt, _LOOP_TYPES):
            return True
        # Or a loop may be inside a conditional / try block within the loop body
        for child in _walk_no_fn(stmt):
            if child is not stmt and isinstance(child, _LOOP_TYPES):
                return True
    return False


def _count_repeated_computations(loop: ast.For | ast.AsyncFor | ast.While) -> int:
    """
    Count unique Call expressions that appear ≥ 2 times in the loop body.
    Uses ``ast.dump(node.func)`` as the fingerprint — same function with same
    arg structure is considered a repeated computation candidate.
    """
    seen: Dict[str, int] = {}
    for node in _loop_body_nodes(loop):
        if not isinstance(node, ast.Call):
            continue
        key = ast.dump(node.func) + f":{len(node.args)}"
        seen[key] = seen.get(key, 0) + 1
    return sum(1 for c in seen.values() if c >= 2)


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class PerformanceResult:
    """Raw counts from PerformanceAnalyzer.analyze()."""
    n_plus_one_risk:             int = 0
    list_in_loop_append_count:   int = 0
    string_concat_in_loop:       int = 0
    quadratic_nested_loop_count: int = 0
    repeated_computation_count:  int = 0
    regex_compile_in_loop:       int = 0
    io_in_tight_loop:            int = 0
    inefficient_dict_lookup:     int = 0


# ─── Main analyzer ───────────────────────────────────────────────────────────

class PerformanceAnalyzer:
    """
    Walks Python AST and detects 8 performance anti-patterns.

    Usage
    -----
        result = PerformanceAnalyzer().analyze(source_code)
        pv = PerformanceVector.from_analyzer(result, module_id="myapp.views")
    """

    def analyze(self, source: str, module_id: str = "") -> PerformanceResult:
        """
        Parse *source* and collect all performance anti-pattern counts.

        Returns a :class:`PerformanceResult` with the 8 channel counts.
        On ``SyntaxError`` returns a zeroed result.
        """
        result = PerformanceResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        # Pass 1: module-wide patterns (no loop context needed)
        self._check_inefficient_dict_lookups(tree, result)

        # Pass 2: loop-level patterns
        self._check_loops(tree, result)

        return result

    # ── Pass 1: module-wide ───────────────────────────────────────────────────

    def _check_inefficient_dict_lookups(
        self, tree: ast.AST, result: PerformanceResult,
    ) -> None:
        """
        Detect ``k in d.keys()`` patterns anywhere in the module.

        The ``in`` membership test on a dict is O(1) without calling
        ``.keys()``, which materialises a view object.
        """
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for op, comp in zip(node.ops, node.comparators):
                if not isinstance(op, ast.In):
                    continue
                # comp should be a Call to .keys()
                if (
                    isinstance(comp, ast.Call)
                    and isinstance(comp.func, ast.Attribute)
                    and comp.func.attr == "keys"
                    and not comp.args
                    and not comp.keywords
                ):
                    result.inefficient_dict_lookup += 1

    # ── Pass 2: per-loop analysis ─────────────────────────────────────────────

    def _check_loops(self, tree: ast.AST, result: PerformanceResult) -> None:
        """Walk all For/AsyncFor/While nodes and collect loop-body anti-patterns."""
        for node in ast.walk(tree):
            if not isinstance(node, _LOOP_TYPES):
                continue
            self._analyze_loop(node, result)

    def _analyze_loop(
        self,
        loop: ast.For | ast.AsyncFor | ast.While,
        result: PerformanceResult,
    ) -> None:
        # 4. Quadratic nested loop
        if _has_inner_loop(loop):
            result.quadratic_nested_loop_count += 1

        # 5. Repeated computations
        result.repeated_computation_count += _count_repeated_computations(loop)

        # Collect list variables assigned before this loop (approximate:
        # we just check for any .append() call inside the loop body)
        seen_n1:      Set[int] = set()   # deduplicate by line
        seen_regex:   Set[int] = set()
        seen_io:      Set[int] = set()
        seen_concat:  Set[int] = set()
        seen_append:  Set[int] = set()

        for node in _loop_body_nodes(loop):
            lineno = getattr(node, "lineno", -1)

            # 1. N+1 risk: DB method calls inside loop
            if isinstance(node, ast.Call) and _is_n1_call(node) and lineno not in seen_n1:
                result.n_plus_one_risk += 1
                seen_n1.add(lineno)

            # 2. List append inside loop
            if (
                isinstance(node, ast.Call)
                and _call_name(node) == "append"
                and lineno not in seen_append
            ):
                result.list_in_loop_append_count += 1
                seen_append.add(lineno)

            # 3. String concat in loop: s += x
            if (
                isinstance(node, ast.AugAssign)
                and isinstance(node.op, ast.Add)
                and lineno not in seen_concat
            ):
                result.string_concat_in_loop += 1
                seen_concat.add(lineno)

            # 6. Regex call inside loop
            if isinstance(node, ast.Call) and _is_re_call(node) and lineno not in seen_regex:
                result.regex_compile_in_loop += 1
                seen_regex.add(lineno)

            # 7. I/O inside loop
            if isinstance(node, ast.Call) and _is_io_call(node) and lineno not in seen_io:
                result.io_in_tight_loop += 1
                seen_io.add(lineno)
