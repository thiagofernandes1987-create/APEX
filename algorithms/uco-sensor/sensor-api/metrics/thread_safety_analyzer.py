"""
UCO-Sensor — ThreadSafetyAnalyzer  (M7.7)
==========================================
AST-based detection of six concurrency-correctness anti-patterns.

Six channels
------------
1. global_shared_state_count
   Function declares ``global X`` AND assigns to ``X``, and the function is
   used as the ``target=`` argument of a ``threading.Thread(...)`` /
   ``Process(...)`` construction anywhere in the module.  Classic data
   race (CWE-362) — two threads mutating module-level state.

2. lock_missing_count
   Same shared-state mutation as above, but the function body contains NO
   ``Lock``/``RLock``/``Semaphore`` acquisition (``with lock:`` /
   ``lock.acquire()``).  Subset of #1 by definition — counts threads
   missing a synchronisation primitive.

3. daemon_thread_risk
   ``Thread(daemon=True)`` constructed without any matching ``.join()``
   call visible in the module.  Daemon threads die when the main thread
   exits — silent loss of in-flight work (CWE-366).

4. queue_unbounded_risk
   ``queue.Queue()`` / ``asyncio.Queue()`` / ``multiprocessing.Queue()``
   built without a ``maxsize=`` argument.  Unbounded producer queues
   leak memory under back-pressure (CWE-400).

5. asyncio_blocking_call
   Blocking call (``time.sleep``, ``requests.*``, ``urllib.urlopen``,
   raw ``socket.*``) used inside an ``async def`` function.  Stalls
   the event loop (CWE-557).

6. shared_mutable_default
   Module-level ``list``/``dict``/``set`` is mutated inside a function
   that is used as a ``Thread(target=...)`` target.  Same family as
   #1 but via implicit closure rather than ``global``.

All detection is AST-only, stdlib pure.  On ``SyntaxError`` the analyzer
returns a zeroed result rather than raising.

Public API
----------
    ThreadSafetyAnalyzer().analyze(source, module_id="") -> ThreadSafetyResult

References
----------
Lea, D.    (1999). Concurrent Programming in Java. Addison-Wesley.
Goetz, B.  (2006). Java Concurrency in Practice. Addison-Wesley.
PEP 492    — Coroutines with async and await syntax.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Set, Tuple


# ─── Detection registries ────────────────────────────────────────────────────

# Threading constructors whose ``target=`` kwarg names the worker function.
_THREAD_CTORS: FrozenSet[str] = frozenset({
    "Thread", "Process", "Timer",
})

# Lock / synchronisation primitives — presence of any of these in a function
# body disqualifies it from ``lock_missing_count``.
_LOCK_CTORS: FrozenSet[str] = frozenset({
    "Lock", "RLock", "Semaphore", "BoundedSemaphore", "Condition", "Event",
})
_LOCK_METHODS: FrozenSet[str] = frozenset({"acquire", "release"})

# Blocking primitives that must not appear inside ``async def`` bodies.
_ASYNC_BLOCKING_ATTR_CALLS: FrozenSet[Tuple[str, str]] = frozenset({
    ("time",     "sleep"),
    ("urllib",   "urlopen"),
    ("requests", "get"),    ("requests", "post"),    ("requests", "put"),
    ("requests", "delete"), ("requests", "patch"),   ("requests", "head"),
    ("requests", "request"),("requests", "options"),
    ("socket",   "connect"),("socket",   "recv"),    ("socket",   "send"),
    ("socket",   "sendall"),("socket",   "accept"),
    ("subprocess","run"),   ("subprocess","call"),   ("subprocess","check_output"),
    ("subprocess","Popen"),
})

# Queue constructors whose ``maxsize=`` arg controls back-pressure.
_QUEUE_CTORS: FrozenSet[str] = frozenset({"Queue", "LifoQueue", "PriorityQueue", "SimpleQueue"})

# Module-level mutable-literal AST node types.
_MUTABLE_LITERALS = (ast.List, ast.Dict, ast.Set)

# Mutation methods on shared collections.
_MUTATION_METHODS: FrozenSet[str] = frozenset({
    "append", "extend", "insert", "remove", "pop", "clear",
    "update", "add", "discard",
})


# ─── AST helpers ─────────────────────────────────────────────────────────────

def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def _call_module(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        v = node.func.value
        if isinstance(v, ast.Name):
            return v.id
        if isinstance(v, ast.Attribute):
            return v.attr
    return ""


def _kwarg(node: ast.Call, name: str) -> Optional[ast.expr]:
    """Return the value-expr of the ``name`` keyword argument, or None."""
    for kw in node.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _is_true_literal(node: Optional[ast.expr]) -> bool:
    return isinstance(node, ast.Constant) and node.value is True


def _collect_thread_targets(tree: ast.AST) -> Set[str]:
    """Return the set of function names referenced as ``Thread(target=fn)``."""
    targets: Set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _call_name(node) not in _THREAD_CTORS:
            continue
        target_expr = _kwarg(node, "target")
        if isinstance(target_expr, ast.Name):
            targets.add(target_expr.id)
        elif isinstance(target_expr, ast.Attribute):
            targets.add(target_expr.attr)
    return targets


def _function_has_lock_synchronisation(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """
    True iff *fn* contains a Lock/RLock construction, ``with lock:`` context
    manager, or explicit ``.acquire()``/``.release()`` call.
    """
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _LOCK_CTORS or name in _LOCK_METHODS:
                return True
        if isinstance(node, (ast.With, ast.AsyncWith)):
            # ``with self._lock:`` / ``with Lock():`` both qualify
            return True
    return False


def _function_mutates_global(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Optional[str]:
    """
    Return the name of a ``global X``-declared variable that *fn* also
    assigns to, or ``None`` if no such pattern exists.
    """
    globals_declared: Set[str] = set()
    assigned: Set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Global):
            globals_declared.update(node.names)
        elif isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    assigned.add(tgt.id)
        elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            assigned.add(node.target.id)
    shared = globals_declared & assigned
    return next(iter(shared)) if shared else None


def _function_mutates_module_collection(
    fn: ast.FunctionDef | ast.AsyncFunctionDef,
    module_collections: Set[str],
) -> bool:
    """
    True iff *fn* calls a mutation method (``append``, ``extend``,
    ``update``, …) on any name in *module_collections*.
    """
    if not module_collections:
        return False
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _MUTATION_METHODS:
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Name) and receiver.id in module_collections:
            return True
    return False


def _collect_module_level_collections(tree: ast.AST) -> Set[str]:
    """
    Return the set of names assigned to a mutable literal at module scope.

        SHARED = []
        CACHE  = {}
        SEEN   = set()
    """
    out: Set[str] = set()
    if not isinstance(tree, ast.Module):
        return out
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, _MUTABLE_LITERALS):
            # ``set()`` constructor counts too
            if (
                isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name)
                and node.value.func.id in {"list", "dict", "set"}
            ):
                pass
            else:
                continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name):
                out.add(tgt.id)
    return out


def _module_has_join_call(tree: ast.AST) -> bool:
    """True iff the module contains any ``.join()`` call."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and not node.args  # str.join takes an arg; thread.join() doesn't
        ):
            return True
    return False


# ─── Result dataclass ────────────────────────────────────────────────────────

@dataclass
class ThreadSafetyResult:
    """Raw counts from ThreadSafetyAnalyzer.analyze()."""
    __test__ = False  # pytest: data container, not a test class

    global_shared_state_count: int = 0
    lock_missing_count:        int = 0
    daemon_thread_risk:        int = 0
    queue_unbounded_risk:      int = 0
    asyncio_blocking_call:     int = 0
    shared_mutable_default:    int = 0


# ─── Main analyzer ───────────────────────────────────────────────────────────

class ThreadSafetyAnalyzer:
    """
    Walks Python AST and detects six concurrency-correctness anti-patterns.

    Usage
    -----
        result = ThreadSafetyAnalyzer().analyze(source_code)
        tsv    = ThreadSafetyVector.from_analyzer(result, module_id="myapp.worker")
    """

    def analyze(self, source: str, module_id: str = "") -> ThreadSafetyResult:
        """
        Parse *source* and produce a :class:`ThreadSafetyResult`.

        Returns the default zeroed result on ``SyntaxError``.
        """
        result = ThreadSafetyResult()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        thread_targets       = _collect_thread_targets(tree)
        module_collections   = _collect_module_level_collections(tree)
        any_join_in_module   = _module_has_join_call(tree)

        # Iterate every function / async function in the tree
        all_fns: List[ast.FunctionDef | ast.AsyncFunctionDef] = [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        for fn in all_fns:
            # 1 + 2: global shared state + lock missing
            if fn.name in thread_targets:
                if _function_mutates_global(fn) is not None:
                    result.global_shared_state_count += 1
                    if not _function_has_lock_synchronisation(fn):
                        result.lock_missing_count += 1

                # 6: shared mutable default (collection via closure)
                if _function_mutates_module_collection(fn, module_collections):
                    result.shared_mutable_default += 1
                    if not _function_has_lock_synchronisation(fn):
                        # Pollutes lock_missing too — same root cause
                        result.lock_missing_count += 1

            # 5: asyncio_blocking_call (only inside ``async def``)
            if isinstance(fn, ast.AsyncFunctionDef):
                result.asyncio_blocking_call += self._count_async_blocking(fn)

        # 3: daemon_thread_risk (module-level walk — independent of fns)
        result.daemon_thread_risk = self._count_daemon_threads(tree, any_join_in_module)

        # 4: queue_unbounded_risk (module-level walk)
        result.queue_unbounded_risk = self._count_unbounded_queues(tree)

        return result

    # ── Sub-detectors ─────────────────────────────────────────────────────────

    @staticmethod
    def _count_async_blocking(fn: ast.AsyncFunctionDef) -> int:
        count = 0
        seen_lines: Set[int] = set()
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            module = _call_module(node)
            name   = _call_name(node)
            if (module, name) in _ASYNC_BLOCKING_ATTR_CALLS:
                lineno = getattr(node, "lineno", -1)
                if lineno not in seen_lines:
                    count += 1
                    seen_lines.add(lineno)
        return count

    @staticmethod
    def _count_daemon_threads(tree: ast.AST, module_has_join: bool) -> int:
        """
        ``Thread(daemon=True)`` without any ``.join()`` anywhere in the module.

        If the module contains at least one ``.join()`` we assume the daemon
        threads are joined explicitly somewhere — conservative to avoid FPs.
        """
        if module_has_join:
            return 0
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node) not in _THREAD_CTORS:
                continue
            daemon = _kwarg(node, "daemon")
            if _is_true_literal(daemon):
                count += 1
        return count

    @staticmethod
    def _count_unbounded_queues(tree: ast.AST) -> int:
        count = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node) not in _QUEUE_CTORS:
                continue
            # maxsize as positional or keyword?
            if node.args or _kwarg(node, "maxsize") is not None:
                continue
            count += 1
        return count
