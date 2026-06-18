"""
UCO-Sensor — TestQualityAnalyzer  (M7.6)
=========================================
AST-based detection of test-suite quality signals in Python source code.

Eight test-quality channels
---------------------------
1. assertion_density
   Total ``assert`` statements (and unittest ``self.assert*`` calls) divided
   by the number of test functions.  Target ≥ 2.0.

2. test_complexity
   Mean cyclomatic complexity across all test functions.  Test code should
   be straight-line — high CC in tests is itself a code smell.  Target < 3.0.

3. mock_overuse_ratio
   Mock/patch construction sites divided by the total number of ``Call``
   nodes inside the test scope.  Heavy mocking decouples tests from real
   behaviour.  Target < 0.3.

4. test_isolation_score
   Heuristic ∈ [0, 1]:  ``1 - (n_polluting_tests / n_tests)`` where a
   polluting test declares ``global``/``nonlocal``, mutates a non-self
   attribute on an imported module, or writes to a module-level variable
   defined outside the function.  Higher = more isolated.  Target > 0.8.

5. flaky_test_risk
   Count of test functions whose body references at least one known
   non-deterministic primitive: ``time.sleep``, ``time.time``,
   ``datetime.now``, ``datetime.utcnow``, ``random.*`` (without a seed),
   ``uuid.uuid4``.  Target 0.

6. parameterized_ratio
   Tests decorated with ``@pytest.mark.parametrize`` (or
   ``@parameterized.expand``) divided by the total test count.  Higher
   parameterization usually means broader coverage with less duplication.
   Target > 0.3.

7. test_naming_quality
   Fraction of test functions whose name (after the ``test_`` prefix) has
   ≥ 3 snake_case tokens — a proxy for descriptive naming.
   ``test_x`` is poor; ``test_user_login_with_invalid_password`` is good.
   Target > 0.7.

8. dead_test_count
   Test functions whose body contains NO ``assert`` statement and no
   ``self.assert*`` / ``self.fail`` call.  These are tautologically green
   and provide no signal.  Target 0.

A *test function* is any ``FunctionDef`` whose name starts with ``test_``
(top-level or inside a class that inherits from a name ending in
``TestCase``).

All detection is AST-only, stdlib pure.  On ``SyntaxError`` the analyzer
returns a zeroed result rather than raising.

Public API
----------
    TestQualityAnalyzer().analyze(source, module_id="") -> TestQualityResult

References
----------
Meszaros, G. (2007). xUnit Test Patterns: Refactoring Test Code. Addison-Wesley.
Beck, K.    (2002). Test-Driven Development By Example. Addison-Wesley.
Fowler, M.  (2007). Mocks Aren't Stubs. martinfowler.com.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import FrozenSet, List, Optional, Set, Tuple


# ─── Detection registries ────────────────────────────────────────────────────

# Cyclomatic-complexity contributing nodes (McCabe)
_CC_NODES = (
    ast.If, ast.While, ast.For, ast.AsyncFor,
    ast.ExceptHandler, ast.With, ast.AsyncWith,
    ast.Assert, ast.comprehension,
)
_BOOL_OPS = (ast.And, ast.Or)

# Mock / patch construction call-target names
_MOCK_NAMES: FrozenSet[str] = frozenset({
    "Mock", "MagicMock", "AsyncMock", "NonCallableMock",
    "NonCallableMagicMock", "PropertyMock", "create_autospec",
    "patch", "patch_object",
    "mock_open",
})

# Flaky primitives — (module, attr) pairs OR bare callable names
_FLAKY_ATTR_CALLS: FrozenSet[Tuple[str, str]] = frozenset({
    ("time",     "sleep"),
    ("time",     "time"),
    ("time",     "monotonic"),
    ("time",     "perf_counter"),
    ("datetime", "now"),
    ("datetime", "utcnow"),
    ("datetime", "today"),
    ("uuid",     "uuid1"),
    ("uuid",     "uuid4"),
    ("random",   "random"),
    ("random",   "randint"),
    ("random",   "choice"),
    ("random",   "shuffle"),
    ("random",   "sample"),
    ("random",   "uniform"),
    ("os",       "urandom"),
})

# Decorator names that mark a parameterized test
_PARAMETRIZE_NAMES: FrozenSet[str] = frozenset({
    "parametrize",   # pytest.mark.parametrize
    "expand",        # parameterized.expand
    "parameters",    # parameterized.parameters
    "params",        # absltest.parameterized.params
    "data",          # ddt
    "given",         # hypothesis (property-based)
})


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _is_test_function(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """A test function is any ``def test_*`` (top-level OR inside a TestCase)."""
    return fn.name.startswith("test_")


def _collect_test_functions(
    tree: ast.AST,
) -> List[ast.FunctionDef | ast.AsyncFunctionDef]:
    """
    Return every test function in *tree* (module-level or class-scoped).

    A class scopes a test function regardless of its base — pytest accepts
    plain classes prefixed with ``Test``.  We collect any ``def test_*``
    found anywhere in the tree.
    """
    out: List[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_test_function(node):
                out.append(node)
    return out


def _call_name(node: ast.Call) -> str:
    """Return the simple name of the callable target."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _call_module(node: ast.Call) -> str:
    """Return the receiver/module identifier of an attribute call."""
    if isinstance(node.func, ast.Attribute):
        v = node.func.value
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Attribute):
            return v.attr
    return ""


def _decorator_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> List[str]:
    """Return the simple attribute names of every decorator on *fn*."""
    names: List[str] = []
    for dec in fn.decorator_list:
        target = dec.func if isinstance(dec, ast.Call) else dec
        if isinstance(target, ast.Attribute):
            names.append(target.attr)
        elif isinstance(target, ast.Name):
            names.append(target.id)
    return names


def _function_cc(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Cyclomatic complexity of *fn* using McCabe's classical formula:
    ``1 + count(decision points)`` where decision points are If, For,
    While, ExceptHandler, With, Assert, comprehensions and each
    ``and``/``or`` operand in BoolOp.
    """
    cc = 1
    for node in ast.walk(fn):
        if isinstance(node, _CC_NODES):
            cc += 1
        elif isinstance(node, ast.BoolOp) and isinstance(node.op, _BOOL_OPS):
            # n operands → n-1 short-circuit branches
            cc += max(0, len(node.values) - 1)
    return cc


def _is_assertion(node: ast.AST) -> bool:
    """
    A test "assertion" is either:
      - an ``assert`` statement, OR
      - a Call whose target attribute starts with ``assert`` or equals ``fail``
        (covers unittest's ``self.assertEqual``, ``self.fail()``, etc.).
    """
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        attr = node.func.attr
        if attr.startswith("assert") or attr == "fail":
            return True
    return False


def _count_assertions(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    return sum(1 for n in ast.walk(fn) if _is_assertion(n))


def _is_mock_construction(node: ast.Call) -> bool:
    """``Mock()``, ``patch('x')``, ``mock.patch(...)`` — anything that creates a mock."""
    name = _call_name(node)
    if name in _MOCK_NAMES:
        return True
    # Also catch ``unittest.mock.patch``, ``mock.MagicMock`` via the receiver
    module = _call_module(node)
    if module in {"mock", "unittest", "mock_patch"} and name in _MOCK_NAMES:
        return True
    return False


def _is_flaky_call(node: ast.Call) -> bool:
    """Detect calls to non-deterministic primitives."""
    name   = _call_name(node)
    module = _call_module(node)
    if not name:
        return False
    if (module, name) in _FLAKY_ATTR_CALLS:
        return True
    # ``datetime.datetime.now()`` → module="datetime", name="now" already covered
    # Bare ``time()`` is never standard — skip the false positive on user code
    return False


def _is_polluting_test(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """
    A test pollutes shared state when it:
      - declares ``global`` or ``nonlocal``
      - assigns to ``Module.attribute`` (mutating an import)

    Heuristic only — not perfect, but matches Meszaros's "shared fixture"
    smell and gives a useful proxy for isolation.
    """
    for node in ast.walk(fn):
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            return True
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id not in {"self", "cls"}
                ):
                    return True
        if isinstance(node, ast.AugAssign):
            target = node.target
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id not in {"self", "cls"}
            ):
                return True
    return False


def _is_parameterized(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Parametrize / expand / hypothesis ``given`` decorator present?"""
    return any(d in _PARAMETRIZE_NAMES for d in _decorator_names(fn))


def _name_quality_ok(fn_name: str) -> bool:
    """
    A descriptive test name has ≥ 3 snake_case tokens after the ``test_``
    prefix.  Acronyms (``test_aws``) and one-word tests (``test_login``) do
    not pass.
    """
    if not fn_name.startswith("test_"):
        return False
    body = fn_name[len("test_"):]
    tokens = [t for t in body.split("_") if t]
    return len(tokens) >= 3


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class TestQualityResult:
    """Raw counts and ratios from TestQualityAnalyzer.analyze()."""
    __test__ = False  # pytest: this is a data container, not a test class

    n_test_functions:    int   = 0
    assertion_density:   float = 0.0
    test_complexity:     float = 0.0
    mock_overuse_ratio:  float = 0.0
    test_isolation_score: float = 1.0
    flaky_test_risk:     int   = 0
    parameterized_ratio: float = 0.0
    test_naming_quality: float = 0.0
    dead_test_count:     int   = 0


# ─── Main analyzer ───────────────────────────────────────────────────────────

class TestQualityAnalyzer:
    """
    Walks a Python AST and produces eight test-quality channels.

    Usage
    -----
        result = TestQualityAnalyzer().analyze(source)
        tqv    = TestQualityVector.from_analyzer(result, module_id="tests.foo")
    """

    def analyze(self, source: str, module_id: str = "") -> TestQualityResult:
        """
        Parse *source* and produce a :class:`TestQualityResult`.

        On ``SyntaxError`` returns the default zeroed result (with
        ``test_isolation_score = 1.0`` — vacuously isolated).
        """
        result = TestQualityResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        tests = _collect_test_functions(tree)
        n = len(tests)
        result.n_test_functions = n
        if n == 0:
            return result

        total_assertions = 0
        cc_sum           = 0
        mock_calls       = 0
        total_calls      = 0
        polluting        = 0
        flaky            = 0
        parametrized     = 0
        good_names       = 0
        dead             = 0

        for fn in tests:
            asserts = _count_assertions(fn)
            total_assertions += asserts

            cc_sum += _function_cc(fn)

            fn_calls = 0
            fn_mocks = 0
            fn_flaky = False
            for node in ast.walk(fn):
                if isinstance(node, ast.Call):
                    fn_calls += 1
                    if _is_mock_construction(node):
                        fn_mocks += 1
                    if _is_flaky_call(node):
                        fn_flaky = True
            total_calls += fn_calls
            mock_calls  += fn_mocks
            if fn_flaky:
                flaky += 1

            if _is_polluting_test(fn):
                polluting += 1
            if _is_parameterized(fn):
                parametrized += 1
            if _name_quality_ok(fn.name):
                good_names += 1
            if asserts == 0:
                dead += 1

        result.assertion_density   = round(total_assertions / n, 4)
        result.test_complexity     = round(cc_sum           / n, 4)
        result.mock_overuse_ratio  = (
            round(mock_calls / total_calls, 4) if total_calls else 0.0
        )
        result.test_isolation_score = round(1.0 - (polluting / n), 4)
        result.flaky_test_risk     = flaky
        result.parameterized_ratio = round(parametrized / n, 4)
        result.test_naming_quality = round(good_names   / n, 4)
        result.dead_test_count     = dead

        return result
