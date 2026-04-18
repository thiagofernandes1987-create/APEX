"""
UCO-Sensor — extract_repo_history (shim para frequency-engine)
==============================================================
Módulo shim que expõe as funções usadas pelos testes do frequency-engine.

Funções principais:
  extract_metrics(code, commit_hash, timestamp, filepath) -> RawMetrics
  detect_runtime_cycles(code, tree=None) -> float
  is_channel_stable(raw_values, cv_threshold, window) -> bool

Implementação standalone via AST — não requer acesso a git ou subprocess.
Usado pelos testes T18a, T18b, T19e, T26a, T26b, T26c, T27 em run_tests.py.

GAP-R01: dependency_instability = max_methods_per_class / 20
         Captura crescimento de responsabilidades (God Class formation).
GAP-N1:  cc_hotspot_ratio = max_fn_cc / (avg_fn_cc * 3), clampado em [0, 1]
GAP-N3:  detect_runtime_cycles detecta LocalProxy e padrões de ciclo runtime
GAP-R03: is_channel_stable via CV rolling windows
BUG-E1:  cyclomatic_complexity SEM cap (suporta CC > 200 para funções gigantes)
"""
from __future__ import annotations
import ast
import math
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


# ─── RawMetrics ───────────────────────────────────────────────────────────────

@dataclass
class RawMetrics:
    commit_hash:             str
    timestamp:               float
    filepath:                str
    cyclomatic_complexity:   int
    syntactic_dead_code:     int
    duplicate_block_count:   int
    halstead_bugs:           float
    dsm_density:             float
    dependency_instability:  float   # GAP-R01: por max_methods_per_class/20
    infinite_loop_risk:      float
    dsm_cyclic_ratio:        float
    hamiltonian:             float
    loc_effective:           int
    n_functions:             int
    n_classes:               int
    max_methods_per_class:   int     # GAP-R01: campo auxiliar
    channel_stability:       Dict[str, bool] = field(default_factory=dict)
    window_position:         float = 0.5
    parse_error:             bool = False
    cc_hotspot_ratio:        float = 0.0   # GAP-N1
    max_function_cc:         int   = 0     # GAP-N1


# ─── is_channel_stable (GAP-R03) ─────────────────────────────────────────────

def is_channel_stable(
    raw_values: List[float],
    cv_threshold: float = 0.03,
    window: int = 5,
) -> bool:
    """
    GAP-R03: True se o canal está estabilizado.

    Critérios:
      1. Guarda de range global: se range > 5% de mean → não estável
      2. CV rolling em janelas de tamanho `window` > cv_threshold → não estável
    """
    if len(raw_values) < window * 2:
        return False

    mean_val = statistics.mean(raw_values)
    if abs(mean_val) > 1e-10:
        global_range = max(raw_values) - min(raw_values)
        if global_range / abs(mean_val) > 0.05:
            return False
    elif max(raw_values) - min(raw_values) > 1e-6:
        return False

    step = max(1, window // 2)
    for i in range(0, len(raw_values) - window, step):
        seg = raw_values[i:i + window]
        seg_m = statistics.mean(seg)
        if abs(seg_m) < 1e-10:
            continue
        try:
            cv = statistics.stdev(seg) / abs(seg_m)
            if cv > cv_threshold:
                return False
        except statistics.StatisticsError:
            pass

    return True


# ─── detect_runtime_cycles (GAP-N3) ──────────────────────────────────────────

# Padrões de proxy runtime conhecidos por criar ciclos de dependência não-detectáveis
# estaticamente — só aparecem em runtime via __getattr__ dinâmico
_PROXY_NAMES = frozenset([
    "LocalProxy", "Proxy", "ObjectProxy", "CallableProxyMixin",
    "SimpleLazyObject", "LazyObject", "PromiseMixin",
    "wrapt.ObjectProxy", "lazy_object_proxy",
])

_PROXY_MODULES = frozenset([
    "werkzeug.local", "werkzeug.utils", "flask.globals",
    "django.utils.functional", "lazy_object_proxy",
    "wrapt", "objproxies",
])

_CYCLE_BUILTINS = frozenset(["__class__", "__self__", "__func__"])


def detect_runtime_cycles(code: str, tree: Optional[ast.AST] = None) -> float:
    """
    GAP-N3: Detecta padrões de ciclo de dependência em runtime.

    Retorna score ∈ [0, 1]:
      ≥ 0.45 → ciclo de runtime detectado (LocalProxy, forward reference, etc.)
      < 0.20 → código limpo sem padrões de ciclo

    Detecta:
      1. Importação de LocalProxy ou proxies similares de módulos conhecidos
      2. Uso de LocalProxy(...) como instanciação
      3. Forward references implícitas via TYPE_CHECKING + string annotations
      4. Atributos de ciclo (__self__, __func__) em calls encadeadas
    """
    if tree is None:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return 0.0

    score = 0.0
    found_proxy_import = False
    found_proxy_use    = False

    for node in ast.walk(tree):
        # 1. Importação de proxy de módulo conhecido
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module in _PROXY_MODULES:
                imported_names = {alias.name for alias in node.names}
                if imported_names & _PROXY_NAMES:
                    score += 0.50
                    found_proxy_import = True
            elif any(m in module for m in ["local", "proxy", "lazy"]):
                score += 0.20

        # 2. Import simples de módulo proxy
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(m in alias.name for m in _PROXY_MODULES):
                    score += 0.15

        # 3. Uso de proxy conhecido como callable
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _PROXY_NAMES:
                score += 0.30
                found_proxy_use = True
            if isinstance(node.func, ast.Attribute) and node.func.attr in _PROXY_NAMES:
                score += 0.30

        # 4. Atributos de ciclo
        if isinstance(node, ast.Attribute) and node.attr in _CYCLE_BUILTINS:
            score += 0.05

    # Sinalizar se encontrou import E uso (ciclo confirmado)
    if found_proxy_import and found_proxy_use:
        score = max(score, 0.75)   # ciclo de runtime confirmado

    return min(1.0, score)


# ─── Visitor AST para extract_metrics ────────────────────────────────────────

class _MetricsVisitor(ast.NodeVisitor):
    """AST visitor que computa métricas UCO para extract_metrics."""

    def __init__(self):
        self.cc_module:     int = 1
        self.fn_cc:         Dict[str, int] = {}
        self._fn_stack:     List[str] = []
        self._class_methods: Dict[str, int] = {}
        self._class_stack:  List[str] = []
        self.n_functions:   int = 0
        self.n_classes:     int = 0
        self.dead_lines:    int = 0
        self.loop_risk:     int = 0
        self.n_while:       int = 0
        self.imports:       Set[str] = set()
        # Halstead counters
        self._ops:      Dict[str, int] = {}
        self._operands: Dict[str, int] = {}

    # CC

    def visit_FunctionDef(self, node):
        self.n_functions += 1
        name = node.name
        full = f"{self._class_stack[-1]}.{name}" if self._class_stack else name
        if self._class_stack:
            self._class_methods[self._class_stack[-1]] = \
                self._class_methods.get(self._class_stack[-1], 0) + 1
        old = self.cc_module
        self.cc_module = 1
        self._fn_stack.append(full)
        self.generic_visit(node)
        fn_cc = self.cc_module
        self.fn_cc[full] = fn_cc
        self._fn_stack.pop()
        self.cc_module = old + fn_cc - 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node):
        self.n_classes += 1
        self._class_stack.append(node.name)
        self._class_methods[node.name] = 0
        self.generic_visit(node)
        self._class_stack.pop()

    def visit_If(self, node):
        self.cc_module += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.cc_module += 1
        self.n_while += 1
        # ILR: while True sem escape incondicional direto
        if isinstance(node.test, ast.Constant) and bool(node.test.value) is True:
            has_unconditional = any(
                isinstance(s, (ast.Break, ast.Return))
                for s in node.body
            )
            if not has_unconditional:
                self.loop_risk += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.cc_module += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.cc_module += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.cc_module += len(node.values) - 1
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.cc_module += 1
        self.generic_visit(node)

    # Dead code
    def visit_Module(self, node):
        self._scan_dead(node.body)
        self.generic_visit(node)

    def _scan_dead(self, stmts):
        terminal = False
        for stmt in stmts:
            if terminal:
                start = getattr(stmt, 'lineno', 0)
                end   = getattr(stmt, 'end_lineno', start)
                self.dead_lines += max(1, end - start + 1)
                continue
            if isinstance(stmt, (ast.Return, ast.Raise, ast.Break, ast.Continue)):
                terminal = True
            if isinstance(stmt, ast.If):
                self._scan_dead(stmt.body); self._scan_dead(stmt.orelse)
            elif isinstance(stmt, (ast.For, ast.While)):
                self._scan_dead(stmt.body); self._scan_dead(stmt.orelse)
            elif isinstance(stmt, ast.With):
                self._scan_dead(stmt.body)
            elif isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self._scan_dead(stmt.body)

    # Halstead
    def visit_BinOp(self, node):
        self._ops[type(node.op).__name__] = self._ops.get(type(node.op).__name__, 0) + 1
        self.generic_visit(node)

    def visit_Compare(self, node):
        for op in node.ops:
            k = type(op).__name__
            self._ops[k] = self._ops.get(k, 0) + 1
        self.generic_visit(node)

    def visit_Constant(self, node):
        k = repr(node.value)[:30]
        self._operands[k] = self._operands.get(k, 0) + 1

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self._operands[node.id] = self._operands.get(node.id, 0) + 1

    def visit_Import(self, node):
        for alias in node.names:
            self.imports.add(alias.name.split(".")[0])

    def visit_ImportFrom(self, node):
        if node.module:
            self.imports.add(node.module.split(".")[0])

    @property
    def max_methods_per_class(self) -> int:
        return max(self._class_methods.values(), default=0)

    @property
    def max_fn_cc(self) -> int:
        return max(self.fn_cc.values(), default=self.cc_module)

    @property
    def fn_cc_list(self) -> List[int]:
        return list(self.fn_cc.values())


# ─── extract_metrics ─────────────────────────────────────────────────────────

def extract_metrics(
    code: str,
    commit_hash: str,
    timestamp: float,
    filepath: str,
    window_position: float = 0.5,
) -> RawMetrics:
    """
    Extrai métricas UCO de código-fonte via AST.

    Parâmetros
    ----------
    code          : código-fonte Python como string
    commit_hash   : hash do commit (usado como ID)
    timestamp     : UNIX timestamp do snapshot
    filepath      : caminho do arquivo (para detecção GAP-N3)
    window_position: posição na janela de análise [0, 1] (GAP-R04)

    Retorna
    -------
    RawMetrics com todos os canais preenchidos.

    GAP-R01: dependency_instability = max_methods_per_class / 20
    GAP-N1:  cc_hotspot_ratio = max_fn_cc / (avg_fn_cc * 3), clampado [0,1]
    GAP-N3:  dsm_cyclic_ratio via detect_runtime_cycles
    BUG-E1:  CC sem cap (suporta CC > 200)
    """
    try:
        tree = ast.parse(code, mode="exec")
        parse_ok = True
    except SyntaxError:
        tree = None
        parse_ok = False

    if not parse_ok or tree is None:
        loc = len([l for l in code.splitlines() if l.strip()])
        return RawMetrics(
            commit_hash=commit_hash, timestamp=timestamp, filepath=filepath,
            cyclomatic_complexity=1, syntactic_dead_code=0, duplicate_block_count=0,
            halstead_bugs=0.0, dsm_density=0.0, dependency_instability=0.0,
            infinite_loop_risk=0.0, dsm_cyclic_ratio=0.0,
            hamiltonian=float(loc) * 0.05, loc_effective=loc,
            n_functions=0, n_classes=0, max_methods_per_class=0,
            parse_error=True, window_position=window_position,
        )

    v = _MetricsVisitor()
    v.visit(tree)

    loc = len([l for l in code.splitlines() if l.strip()])

    # ── Cyclomatic Complexity (BUG-E1: NO CAP) ─────────────────────────────
    cc = max(1, v.cc_module)

    # ── Halstead → Hamiltonian ──────────────────────────────────────────────
    n1 = max(1, len(v._ops))
    N1 = max(1, sum(v._ops.values()))
    n2 = max(1, len(v._operands))
    N2 = max(1, sum(v._operands.values()))
    vocab  = n1 + n2
    length = N1 + N2
    volume = length * math.log2(vocab) if vocab > 0 else 0.0
    diff   = (n1 / 2) * (N2 / max(1, n2))
    effort = diff * volume
    bugs   = volume / 3000.0
    h      = effort / max(1, loc) * 0.01

    # ── ILR ────────────────────────────────────────────────────────────────
    ilr = float(v.loop_risk) / max(1, v.n_while) if v.n_while > 0 else 0.0
    ilr = min(1.0, ilr)

    # ── GAP-R01: DI = max_methods_per_class / 20 ────────────────────────
    max_meth = v.max_methods_per_class
    di = min(3.0, max_meth / 20.0)   # DI pode ultrapassar 1 em god classes extremas

    # ── DSM density ────────────────────────────────────────────────────────
    n_imports = len(v.imports)
    dsm_d = min(1.0, n_imports / (max(1, v.n_functions) * 2 + 1))

    # ── GAP-N3: dsm_cyclic_ratio via runtime cycles ──────────────────────
    dsm_c = detect_runtime_cycles(code, tree)

    # ── GAP-N1: cc_hotspot_ratio ────────────────────────────────────────
    fn_list = v.fn_cc_list
    cc_hotspot = 0.0
    if fn_list and len(fn_list) > 1:
        avg = sum(fn_list) / len(fn_list)
        cc_hotspot = min(1.0, v.max_fn_cc / max(1, avg * 3))
    elif fn_list:
        # Única função: hotspot = ratio normalizado pelo threshold de 20 CC
        cc_hotspot = min(1.0, v.max_fn_cc / 20.0)

    # ── channel_stability placeholder ──────────────────────────────────────
    ch_stab: Dict[str, bool] = {}

    return RawMetrics(
        commit_hash=commit_hash,
        timestamp=timestamp,
        filepath=filepath,
        cyclomatic_complexity=cc,
        syntactic_dead_code=v.dead_lines,
        duplicate_block_count=0,
        halstead_bugs=round(bugs, 4),
        dsm_density=round(dsm_d, 4),
        dependency_instability=round(di, 4),
        infinite_loop_risk=round(ilr, 4),
        dsm_cyclic_ratio=round(dsm_c, 4),
        hamiltonian=round(h, 4),
        loc_effective=loc,
        n_functions=v.n_functions,
        n_classes=v.n_classes,
        max_methods_per_class=max_meth,
        channel_stability=ch_stab,
        window_position=window_position,
        parse_error=False,
        cc_hotspot_ratio=round(cc_hotspot, 4),
        max_function_cc=v.max_fn_cc,
    )
