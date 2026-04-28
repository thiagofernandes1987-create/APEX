"""
UCO-Sensor — ArchitectureAnalyzer  (M7.5)
==========================================
AST-based detection of architecture coupling and cohesion metrics.

8 Channels
----------
1. fan_out
   Number of distinct top-level modules imported by this module.

2. fan_in
   Number of modules in the project that import this module.
   Requires project-level graph — pass fan_in= to analyze().

3. coupling_between_objects (CBO)
   Count of distinct external type/module names referenced inside class
   method bodies (type annotations + call targets on capitalized objects).
   External = not ``self``/``cls`` and not a locally-defined class name.
   CBO < 5 is considered healthy per Martin (2002).

4. response_for_class (RFC)
   Unique callable names invoked from within class methods, including the
   methods themselves.  RFC = |own_methods| + |unique_external_calls|.
   RFC < 20 is considered healthy (Chidamber & Kemerer 1994).

5. lack_of_cohesion (LCOM)
   Henderson-Sellers LCOM' = (P − Q) / max(P + Q, 1)
   P = method pairs with NO shared instance attribute (``self.x`` accesses)
   Q = method pairs with ≥ 1 shared instance attribute
   Range [0.0, 1.0].  LCOM < 0.5 is considered healthy.

6. abstraction_level
   abstract_classes / max(1, total_classes)
   A class is abstract when it inherits from ``ABC``/``ABCMeta`` or
   contains at least one ``@abstractmethod``-decorated method.
   Range [0.0, 1.0].

7. circular_import_count
   Number of circular import cycles detected at project level.
   Single-module analysis cannot detect cycles — pass circular_import_count=
   from the project-level ImportGraphAnalyzer DFS.  Default: 0.

8. layer_violation_count
   Number of imports that violate the clean-architecture layer hierarchy:
       infra → domain → app → api
   A violation occurs when a module at a lower layer (e.g. infra) imports a
   module at a higher layer (e.g. api).  Layer is inferred from module name
   keywords.  0 = ideal (Dependency Inversion Principle).

All detection is AST-only (no runtime).  ``fan_in`` and
``circular_import_count`` require project-level context provided externally.

Public API
----------
    ArchitectureAnalyzer().analyze(source, module_id="", fan_in=0,
                                   circular_import_count=0)
        -> ArchitectureResult

References
----------
Chidamber, S.R. & Kemerer, C.F. (1994). A metrics suite for object-oriented
  design. IEEE TSE 20(6), 476-493.
Martin, R.C. (2002). Agile Software Development. Prentice Hall.
Henderson-Sellers, B. (1996). Object-Oriented Metrics. Prentice Hall.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Dict, FrozenSet, Iterator, List, Optional, Set, Tuple


# ─── Layer hierarchy ──────────────────────────────────────────────────────────

# Layer index: 0=infra (lowest), 1=domain, 2=app, 3=api (highest).
# Violation: a module at layer L imports a module at layer > L.
_LAYER_MAP: List[Tuple[int, FrozenSet[str]]] = [
    (3, frozenset({"api", "endpoint", "route", "controller", "view", "handler", "router"})),
    (2, frozenset({"app", "application", "use_case", "usecase", "service", "interactor"})),
    (1, frozenset({"domain", "entity", "model", "aggregate", "value_object", "valueobject"})),
    (0, frozenset({"infra", "infrastructure", "repository", "repo", "db", "database",
                   "storage", "persistence", "adapter", "gateway"})),
]


def _module_layer(module_name: str) -> Optional[int]:
    """
    Return the architecture layer index [0–3] for *module_name*, or ``None``
    if the module name doesn't match any known layer keyword.

    Detection uses both dot-separated parts and underscore-split tokens.
    """
    name_lower = module_name.lower()
    parts: Set[str] = set()
    # Dot-separated parts (e.g. "infra.db" → {"infra", "db"})
    parts.update(name_lower.split("."))
    # Underscore-split tokens within each part
    for part in list(parts):
        parts.update(part.split("_"))

    for layer_idx, keywords in _LAYER_MAP:
        if parts & keywords:
            return layer_idx
    return None


# ─── AST helpers ─────────────────────────────────────────────────────────────

def _collect_imports(tree: ast.AST) -> List[str]:
    """
    Return a list of all top-level module names imported anywhere in *tree*.

    For ``import a.b.c`` the top-level name is ``a``.
    For ``from a.b import c`` the top-level name is ``a``.
    """
    modules: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top:
                    modules.append(top)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.split(".")[0]
                if top:
                    modules.append(top)
    return modules


def _instance_attrs(fn_node: ast.FunctionDef) -> Set[str]:
    """Return the set of ``self.x`` attribute names accessed in *fn_node*."""
    attrs: Set[str] = set()
    for node in ast.walk(fn_node):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "self"
        ):
            attrs.add(node.attr)
    return attrs


def _method_calls(fn_node: ast.FunctionDef) -> Set[str]:
    """Return all unique callable names invoked within *fn_node*."""
    calls: Set[str] = set()
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            calls.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            calls.add(node.func.attr)
    return calls


def _external_types(
    fn_node: ast.FunctionDef,
    local_classes: Set[str],
) -> Set[str]:
    """
    Collect distinct external type references from *fn_node*.

    Considers:
    - Type annotations on parameters and return type
    - Method calls on capitalized non-self objects
      (heuristic: ``Foo.bar()`` — the receiver ``Foo`` is an external type)

    Excludes: ``self``, ``cls``, names in *local_classes*.
    """
    external: Set[str] = set()

    # Annotation-based coupling
    all_args = (
        fn_node.args.args
        + fn_node.args.posonlyargs
        + fn_node.args.kwonlyargs
    )
    for arg in all_args:
        if arg.annotation and isinstance(arg.annotation, ast.Name):
            name = arg.annotation.id
            if name not in {"self", "cls"} and name not in local_classes:
                external.add(name)

    if fn_node.returns and isinstance(fn_node.returns, ast.Name):
        name = fn_node.returns.id
        if name not in local_classes:
            external.add(name)

    # Call-site coupling: method calls on external capitalized objects
    for node in ast.walk(fn_node):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            obj = node.func.value
            if (
                isinstance(obj, ast.Name)
                and obj.id not in {"self", "cls"}
                and obj.id not in local_classes
                and obj.id[0:1].isupper()  # capitalized = likely a class/type
            ):
                external.add(obj.id)

    return external


# ─── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class ArchitectureResult:
    """Raw architecture metric counts from ArchitectureAnalyzer.analyze()."""
    fan_in:                   int   = 0
    fan_out:                  int   = 0
    coupling_between_objects: int   = 0
    response_for_class:       int   = 0
    lack_of_cohesion:         float = 0.0
    abstraction_level:        float = 0.0
    circular_import_count:    int   = 0
    layer_violation_count:    int   = 0


# ─── Main analyzer ───────────────────────────────────────────────────────────

class ArchitectureAnalyzer:
    """
    Walks a Python AST and measures 8 architecture quality channels.

    Usage
    -----
        result = ArchitectureAnalyzer().analyze(source_code, module_id="myapp.api")
        av = ArchitectureVector.from_analyzer(result, module_id="myapp.api")

    Project-level channels
    ----------------------
    Pass ``fan_in`` and ``circular_import_count`` from a project-level
    ``ImportGraphAnalyzer`` run — single-file analysis cannot compute them.
    """

    def analyze(
        self,
        source: str,
        module_id: str = "",
        fan_in: int = 0,
        circular_import_count: int = 0,
    ) -> ArchitectureResult:
        """
        Parse *source* and collect all 8 architecture metric channels.

        Returns an :class:`ArchitectureResult` with all counts populated.
        On ``SyntaxError`` returns a zeroed result (with fan_in / circular
        preserved from the arguments).
        """
        result = ArchitectureResult(
            fan_in=fan_in,
            circular_import_count=circular_import_count,
        )
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return result

        # Channel 2 — fan_out
        imports = _collect_imports(tree)
        result.fan_out = len(set(imports))

        # Channel 8 — layer violations
        result.layer_violation_count = self._layer_violations(module_id, imports)

        # Channels 3–6 — class-level metrics
        self._analyze_classes(tree, result)

        return result

    # ── Pass 1: layer violations ───────────────────────────────────────────────

    def _layer_violations(self, module_id: str, imports: List[str]) -> int:
        """
        Count the number of imports that originate from a higher architecture
        layer than *module_id*'s own layer.

        Returns 0 if *module_id* is empty or its layer is unknown.
        """
        if not module_id:
            return 0
        own_layer = _module_layer(module_id)
        if own_layer is None:
            return 0
        violations = 0
        for imp in set(imports):
            imp_layer = _module_layer(imp)
            if imp_layer is not None and imp_layer > own_layer:
                violations += 1
        return violations

    # ── Pass 2: class-level metrics ────────────────────────────────────────────

    def _analyze_classes(self, tree: ast.AST, result: ArchitectureResult) -> None:
        """
        Walk all class definitions in *tree* and compute CBO, RFC, LCOM,
        and abstraction_level.

        When multiple classes exist the aggregated values are:
        - CBO: sum across all classes (total external types)
        - RFC: sum across all classes (total response set)
        - LCOM: mean across all classes
        - abstraction_level: abstract_classes / total_classes
        """
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if not classes:
            return

        local_class_names: Set[str] = {c.name for c in classes}
        total_cbo       = 0
        total_rfc       = 0
        lcom_sum        = 0.0
        abstract_count  = 0
        n_classes       = len(classes)

        for cls_node in classes:
            if self._is_abstract(cls_node):
                abstract_count += 1

            methods: List[ast.FunctionDef] = [
                n for n in cls_node.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            if not methods:
                continue

            own_method_names: Set[str] = {m.name for m in methods}
            cls_external:     Set[str] = set()
            cls_calls:        Set[str] = set()
            method_attrs:     Dict[str, Set[str]] = {}

            for method in methods:
                method_attrs[method.name] = _instance_attrs(method)
                cls_external |= _external_types(method, local_class_names)
                cls_calls    |= _method_calls(method)

            # CBO: unique external types referenced in this class
            total_cbo += len(cls_external)

            # RFC: own methods + external calls not in own_method_names
            external_calls = cls_calls - own_method_names
            total_rfc += len(own_method_names) + len(external_calls)

            # LCOM
            lcom_sum += self._lcom(method_attrs)

        result.coupling_between_objects = total_cbo
        result.response_for_class       = total_rfc
        result.lack_of_cohesion         = round(lcom_sum / n_classes, 4)
        result.abstraction_level        = round(abstract_count / n_classes, 4)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_abstract(cls_node: ast.ClassDef) -> bool:
        """
        Return ``True`` when a class is abstract.

        A class is considered abstract if:
        - It directly inherits from ``ABC`` or ``ABCMeta``
        - Any method is decorated with ``@abstractmethod``
        """
        for base in cls_node.bases:
            if isinstance(base, ast.Name) and base.id in {"ABC", "ABCMeta"}:
                return True
            if isinstance(base, ast.Attribute) and base.attr in {"ABC", "ABCMeta"}:
                return True

        for node in ast.walk(cls_node):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    if isinstance(dec, ast.Name) and dec.id == "abstractmethod":
                        return True
                    if isinstance(dec, ast.Attribute) and dec.attr == "abstractmethod":
                        return True
        return False

    @staticmethod
    def _lcom(method_attrs: Dict[str, Set[str]]) -> float:
        """
        Compute Henderson-Sellers LCOM' for one class.

        P = method pairs with NO shared instance attribute
        Q = method pairs with ≥ 1 shared instance attribute
        LCOM' = (P − Q) / max(P + Q, 1)

        Returns a value in [0.0, 1.0].  0 means perfect cohesion.
        """
        items = list(method_attrs.items())
        n = len(items)
        if n < 2:
            return 0.0

        P = 0
        Q = 0
        for i in range(n):
            for j in range(i + 1, n):
                shared = items[i][1] & items[j][1]
                if shared:
                    Q += 1
                else:
                    P += 1

        denom = max(P + Q, 1)
        return max(0.0, (P - Q) / denom)
