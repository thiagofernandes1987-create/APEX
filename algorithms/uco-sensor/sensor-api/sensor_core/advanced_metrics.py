"""
UCO-Sensor — Advanced Metrics (M1)
====================================

M1.1  Cognitive Complexity  — Campbell 2018 (SonarQube-compatible)
M1.2  SQALE Technical Debt  — ISO/IEC 9126-style debt estimation
M1.3  Function-level Breakdown — FunctionProfile per function/method
M1.4  Import-graph DI          — Martin's real Ce/(Ca+Ce)
M1.5  Clone Detection          — AST skeleton hash (Type-2 clones)
M1.6  Ratings A–E              — UCO, SQALE, Reliability, Security

All M1 metrics are attached to a MetricVector as dynamic attributes
(setattr pattern) so the FrequencyEngine pipeline is never disrupted.

Public API
----------
    cognitive_complexity(source)           -> (total: int, per_fn: dict)
    sqale_debt(metrics_dict, loc)          -> SQALEResult
    build_function_profiles(source, ...)   -> List[FunctionProfile]
    detect_clones(source)                  -> int  (clone group count)
    compute_ratings(uco_score, sqale_pct)  -> Ratings
    class ImportGraphAnalyzer              (project-level DI)
    class AdvancedAnalyzer                 (orchestrates all M1 for one file)

Refs
----
    Campbell, G.A. (2018). Cognitive Complexity: A New Way of Measuring
      Understandability. SonarSource SA.
    Martin, R.C. (2002). Agile Software Development. Prentice Hall.
    SQALE Method (2016). SQALE Technical Report.
"""
from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


# ══════════════════════════════════════════════════════════════════════════════
# M1.1 — Cognitive Complexity (Campbell 2018)
# ══════════════════════════════════════════════════════════════════════════════

def cognitive_complexity(source: str) -> Tuple[int, Dict[str, int]]:
    """
    Compute Cognitive Complexity for a Python source file.

    Algorithm (Campbell 2018):
    - Structural increments: +1 + nesting_depth for if/for/while/except/
      with/lambda/nested-function
    - Hybrid increments: +1 flat for BoolOp sequences, ternary (IfExp),
      and recursive call sites
    - elif: +1 flat (no depth bonus — same conceptual level as the if)
    - else: +1 flat (no depth bonus)
    - Nesting depth increases inside: if/for/while/except/with/lambda/
      nested functions

    Returns
    -------
    (total, per_function)
        total        : sum of all top-level function CCs (module total)
        per_function : {qualified_name: cognitive_cc}
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0, {}

    fn_scores: Dict[str, int] = {}
    total = 0
    for node in tree.body:
        total += _cog_stmt(node, depth=0, fn_name=None,
                           fn_scores=fn_scores, ctx="")
    return total, fn_scores


# ── Internal recursive helpers ────────────────────────────────────────────────

def _cog_stmt(
    stmt: ast.stmt,
    depth: int,
    fn_name: Optional[str],
    fn_scores: Dict[str, int],
    ctx: str,
) -> int:
    """Cognitive complexity contribution of a single statement."""
    score = 0

    # ── Function / async function ─────────────────────────────────────────
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
        full = f"{ctx}.{stmt.name}" if ctx else stmt.name
        # Nested inside another function: add structural increment
        if fn_name is not None:
            score += 1 + depth
        # Compute function body independently (body resets to depth=0)
        fn_score = _cog_body(stmt.body, depth=0,
                             fn_name=stmt.name, fn_scores=fn_scores, ctx=full)
        fn_scores[full] = fn_score
        score += fn_score
        return score

    # ── Class definition ──────────────────────────────────────────────────
    if isinstance(stmt, ast.ClassDef):
        full = f"{ctx}.{stmt.name}" if ctx else stmt.name
        for child in stmt.body:
            score += _cog_stmt(child, depth, fn_name, fn_scores, full)
        return score

    # ── if / elif / else chain ────────────────────────────────────────────
    if isinstance(stmt, ast.If):
        score += 1 + depth                                       # if
        score += _cog_expr(stmt.test, depth, fn_name)            # BoolOp in test
        score += _cog_body(stmt.body, depth + 1, fn_name, fn_scores, ctx)
        score += _cog_orelse(stmt.orelse, depth, fn_name, fn_scores, ctx)
        return score

    # ── for / async for ───────────────────────────────────────────────────
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        score += 1 + depth
        score += _cog_expr(stmt.iter, depth, fn_name)
        score += _cog_body(stmt.body, depth + 1, fn_name, fn_scores, ctx)
        if stmt.orelse:
            score += 1                                           # else: flat
            score += _cog_body(stmt.orelse, depth + 1, fn_name, fn_scores, ctx)
        return score

    # ── while ─────────────────────────────────────────────────────────────
    if isinstance(stmt, ast.While):
        score += 1 + depth
        score += _cog_expr(stmt.test, depth, fn_name)
        score += _cog_body(stmt.body, depth + 1, fn_name, fn_scores, ctx)
        if stmt.orelse:
            score += 1
            score += _cog_body(stmt.orelse, depth + 1, fn_name, fn_scores, ctx)
        return score

    # ── try / except / finally ────────────────────────────────────────────
    if isinstance(stmt, ast.Try):
        score += _cog_body(stmt.body, depth, fn_name, fn_scores, ctx)
        for handler in stmt.handlers:
            score += 1 + depth                                   # each except
            score += _cog_body(handler.body, depth + 1, fn_name, fn_scores, ctx)
        if stmt.orelse:
            score += _cog_body(stmt.orelse, depth, fn_name, fn_scores, ctx)
        finalbody = getattr(stmt, "finalbody", [])
        if finalbody:
            score += _cog_body(finalbody, depth, fn_name, fn_scores, ctx)
        return score

    # ── Python 3.11+: TryStar (except*) ──────────────────────────────────
    if hasattr(ast, "TryStar") and isinstance(stmt, ast.TryStar):
        score += _cog_body(stmt.body, depth, fn_name, fn_scores, ctx)
        for handler in stmt.handlers:
            score += 1 + depth
            score += _cog_body(handler.body, depth + 1, fn_name, fn_scores, ctx)
        if stmt.orelse:
            score += _cog_body(stmt.orelse, depth, fn_name, fn_scores, ctx)
        finalbody = getattr(stmt, "finalbody", [])
        if finalbody:
            score += _cog_body(finalbody, depth, fn_name, fn_scores, ctx)
        return score

    # ── with / async with ────────────────────────────────────────────────
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        score += 1 + depth
        score += _cog_body(stmt.body, depth + 1, fn_name, fn_scores, ctx)
        return score

    # ── match / case (Python 3.10+) ───────────────────────────────────────
    if hasattr(ast, "Match") and isinstance(stmt, ast.Match):
        for case in stmt.cases:
            score += 1 + depth
            score += _cog_body(case.body, depth + 1, fn_name, fn_scores, ctx)
        return score

    # ── Generic statement: visit child expressions ────────────────────────
    for child in ast.iter_child_nodes(stmt):
        if isinstance(child, ast.expr):
            score += _cog_expr(child, depth, fn_name)
    return score


def _cog_body(
    stmts: List[ast.stmt],
    depth: int,
    fn_name: Optional[str],
    fn_scores: Dict[str, int],
    ctx: str,
) -> int:
    return sum(_cog_stmt(s, depth, fn_name, fn_scores, ctx) for s in stmts)


def _cog_orelse(
    orelse: List[ast.stmt],
    depth: int,
    fn_name: Optional[str],
    fn_scores: Dict[str, int],
    ctx: str,
) -> int:
    if not orelse:
        return 0
    # elif: single If in else-list → +1 flat (no depth bonus)
    if len(orelse) == 1 and isinstance(orelse[0], ast.If):
        node = orelse[0]
        score = 1                                                # elif flat
        score += _cog_expr(node.test, depth, fn_name)
        score += _cog_body(node.body, depth + 1, fn_name, fn_scores, ctx)
        score += _cog_orelse(node.orelse, depth, fn_name, fn_scores, ctx)
        return score
    # else: +1 flat
    return 1 + _cog_body(orelse, depth + 1, fn_name, fn_scores, ctx)


def _cog_expr(
    expr: ast.expr,
    depth: int,
    fn_name: Optional[str],
) -> int:
    """Cognitive complexity contribution from expressions."""
    score = 0

    if isinstance(expr, ast.BoolOp):
        score += 1                                               # +1 flat
        for v in expr.values:
            score += _cog_expr(v, depth, fn_name)

    elif isinstance(expr, ast.IfExp):
        score += 1                                               # ternary: +1 flat
        score += _cog_expr(expr.test, depth, fn_name)
        score += _cog_expr(expr.body, depth, fn_name)
        score += _cog_expr(expr.orelse, depth, fn_name)

    elif isinstance(expr, ast.Lambda):
        score += 1 + depth                                       # lambda: +1 + depth
        score += _cog_expr(expr.body, depth + 1, fn_name)

    elif isinstance(expr, ast.Call):
        # Recursion: direct self-call → +1 flat
        if (fn_name is not None
                and isinstance(expr.func, ast.Name)
                and expr.func.id == fn_name):
            score += 1
        score += _cog_expr(expr.func, depth, fn_name)
        for arg in expr.args:
            score += _cog_expr(arg, depth, fn_name)
        for kw in expr.keywords:
            score += _cog_expr(kw.value, depth, fn_name)

    else:
        for child in ast.iter_child_nodes(expr):
            if isinstance(child, ast.expr):
                score += _cog_expr(child, depth, fn_name)

    return score


# ══════════════════════════════════════════════════════════════════════════════
# M1.2 — SQALE Technical Debt
# ══════════════════════════════════════════════════════════════════════════════

# Remediation cost table (minutes per violation)
_SQALE_REMEDIATION: Dict[str, int] = {
    "cc_high":         30,   # CC > 10 per function
    "cc_very_high":    60,   # CC > 20 per function (additional)
    "cog_high":        30,   # Cognitive CC > 15 per function
    "dead_code_line":   5,   # per dead code line
    "ilr_loop":        30,   # per ILR-risky loop
    "clone_group":     30,   # per clone group found
    "di_unstable":    480,   # DI > 0.8 (one day)
    "loc_fat_fn":       2,   # per line over 50 in a single function
    "halstead_high":   60,   # Halstead bugs > 2.0
}

# SQALE rating thresholds (ratio as percentage of total dev cost)
_SQALE_THRESHOLDS = [5.0, 10.0, 20.0, 50.0]   # A≤5%, B≤10%, C≤20%, D≤50%, E>50%
_SQALE_LETTERS    = ["A", "B", "C", "D", "E"]


@dataclass
class SQALEResult:
    """Technical debt estimation (SQALE method)."""
    debt_minutes:  int    = 0
    sqale_ratio:   float  = 0.0   # debt / (loc * 30) as percentage [0–100]
    rating:        str    = "A"
    breakdown:     Dict[str, int] = field(default_factory=dict)


def sqale_debt(metrics: Dict[str, Any], loc: int) -> SQALEResult:
    """
    Estimate SQALE technical debt for a module.

    Parameters
    ----------
    metrics : dict with keys:
        cyclomatic_complexity  (int, module-level CC)
        fn_cc_max              (int, max CC over all functions)
        fn_cc_avg              (float, average CC)
        cognitive_cc           (int, module cognitive CC)
        cognitive_fn_max       (int, max cognitive CC per function)
        syntactic_dead_code    (int, dead lines)
        ilr_loop_count         (int, risky loop count)
        clone_count            (int, clone groups)
        dependency_instability (float, DI)
        halstead_bugs          (float)
        fn_profiles            (list, optional)
    loc : int — lines of code
    """
    breakdown: Dict[str, int] = {}
    debt = 0

    fn_cc_max  = int(metrics.get("fn_cc_max", metrics.get("cyclomatic_complexity", 1)))
    fn_cog_max = int(metrics.get("cognitive_fn_max", metrics.get("cognitive_cc", 0)))
    dead       = int(metrics.get("syntactic_dead_code", 0))
    ilr_loops  = int(metrics.get("ilr_loop_count", 0))
    clones     = int(metrics.get("clone_count", 0))
    di         = float(metrics.get("dependency_instability", 0.0))
    h_bugs     = float(metrics.get("halstead_bugs", 0.0))

    # CC violations
    if fn_cc_max > 20:
        c = _SQALE_REMEDIATION["cc_very_high"]
        breakdown["cc_very_high"] = c
        debt += c
    if fn_cc_max > 10:
        c = _SQALE_REMEDIATION["cc_high"]
        breakdown["cc_high"] = c
        debt += c

    # Cognitive CC violations
    if fn_cog_max > 15:
        c = _SQALE_REMEDIATION["cog_high"]
        breakdown["cog_high"] = c
        debt += c

    # Dead code
    if dead > 0:
        c = dead * _SQALE_REMEDIATION["dead_code_line"]
        breakdown["dead_code"] = c
        debt += c

    # ILR
    if ilr_loops > 0:
        c = ilr_loops * _SQALE_REMEDIATION["ilr_loop"]
        breakdown["ilr_loops"] = c
        debt += c

    # Clone groups
    if clones > 0:
        c = clones * _SQALE_REMEDIATION["clone_group"]
        breakdown["clone_groups"] = c
        debt += c

    # DI instability
    if di > 0.8:
        c = _SQALE_REMEDIATION["di_unstable"]
        breakdown["di_unstable"] = c
        debt += c

    # Halstead bug density
    if h_bugs > 2.0:
        c = _SQALE_REMEDIATION["halstead_high"]
        breakdown["halstead_high"] = c
        debt += c

    # SQALE ratio: debt vs cost-to-write (30 min/LOC)
    cost_to_write = max(1, loc) * 30
    ratio = (debt / cost_to_write) * 100.0

    rating = _SQALE_LETTERS[-1]
    for i, threshold in enumerate(_SQALE_THRESHOLDS):
        if ratio <= threshold:
            rating = _SQALE_LETTERS[i]
            break

    return SQALEResult(
        debt_minutes=debt,
        sqale_ratio=round(ratio, 2),
        rating=rating,
        breakdown=breakdown,
    )


# ══════════════════════════════════════════════════════════════════════════════
# M1.3 — Function-level Breakdown
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class FunctionProfile:
    """Per-function metrics breakdown."""
    name:               str
    loc:                int
    cc:                 int     # McCabe cyclomatic
    cognitive_cc:       int     # Campbell cognitive
    halstead_volume:    float   # estimated from function LOC
    is_complex:         bool    # CC > 10 or cognitive_cc > 15
    debt_minutes:       int     # SQALE debt for this function
    risk_level:         str     # LOW / MEDIUM / HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name":            self.name,
            "loc":             self.loc,
            "cc":              self.cc,
            "cognitive_cc":    self.cognitive_cc,
            "halstead_volume": round(self.halstead_volume, 2),
            "is_complex":      self.is_complex,
            "debt_minutes":    self.debt_minutes,
            "risk_level":      self.risk_level,
        }


def build_function_profiles(
    source: str,
    fn_cc:      Dict[str, int],
    fn_cog:     Dict[str, int],
) -> List[FunctionProfile]:
    """
    Build per-function profiles by combining McCabe CC, cognitive CC,
    and LOC estimation from the parsed AST.

    Parameters
    ----------
    source  : original source code
    fn_cc   : {qualified_name: cyclomatic_cc} from _UCOVisitor
    fn_cog  : {qualified_name: cognitive_cc}  from _CognitiveCalculator
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    # Build map of function name → (start_line, end_line)
    fn_lines: Dict[str, Tuple[int, int]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fn_lines[node.name] = (
                getattr(node, "lineno", 1),
                getattr(node, "end_lineno", getattr(node, "lineno", 1)),
            )

    profiles: List[FunctionProfile] = []
    for fn_name, cc in fn_cc.items():
        short = fn_name.split(".")[-1]
        loc   = 0
        if short in fn_lines:
            s, e = fn_lines[short]
            loc  = max(1, e - s + 1)

        cog_cc = fn_cog.get(fn_name, fn_cog.get(short, 0))
        # Rough Halstead volume estimate for function body
        h_vol  = loc * 4.5   # empirical: ~4.5 bits/LOC average

        is_complex = cc > 10 or cog_cc > 15
        # SQALE per-function debt
        fn_debt = 0
        if cc > 20:   fn_debt += 60
        if cc > 10:   fn_debt += 30
        if cog_cc > 15: fn_debt += 30
        if loc > 50:  fn_debt += (loc - 50) * 2

        if cc > 20 or cog_cc > 25:
            risk = "HIGH"
        elif cc > 10 or cog_cc > 15:
            risk = "MEDIUM"
        else:
            risk = "LOW"

        profiles.append(FunctionProfile(
            name=fn_name,
            loc=loc,
            cc=cc,
            cognitive_cc=cog_cc,
            halstead_volume=h_vol,
            is_complex=is_complex,
            debt_minutes=fn_debt,
            risk_level=risk,
        ))

    return sorted(profiles, key=lambda p: (p.cc + p.cognitive_cc), reverse=True)


# ══════════════════════════════════════════════════════════════════════════════
# M1.4 — Import Graph Dependency Instability (project-level)
# ══════════════════════════════════════════════════════════════════════════════

class ImportGraphAnalyzer:
    """
    Compute Martin's real Dependency Instability for a set of Python modules.

    DI(m) = Ce(m) / (Ca(m) + Ce(m))

        Ce(m) = efferent coupling — modules in the project that m imports
        Ca(m) = afferent coupling — modules in the project that import m

    Usage
    -----
        analyzer = ImportGraphAnalyzer()
        for module_id, imports in module_imports.items():
            analyzer.add_module(module_id, imports)
        di_map = analyzer.compute_di()
    """

    def __init__(self) -> None:
        self._imports: Dict[str, Set[str]] = {}

    def add_module(self, module_id: str, imports: Set[str]) -> None:
        """Register a module and its set of imported module ids."""
        self._imports[module_id] = set(imports)

    def compute_di(self) -> Dict[str, float]:
        """
        Compute DI for all registered modules.

        Only internal imports (modules known to this analyzer) count for
        Ce — external dependencies (numpy, os, etc.) are excluded.
        """
        known = set(self._imports)

        # Ca: count how many internal modules import each module
        ca: Dict[str, int] = {m: 0 for m in known}
        for _mod, imported in self._imports.items():
            for imp in imported:
                if imp in ca:
                    ca[imp] += 1

        result: Dict[str, float] = {}
        for module_id, imported in self._imports.items():
            ce = sum(1 for imp in imported if imp in known)
            ca_m = ca.get(module_id, 0)
            denom = ca_m + ce
            result[module_id] = round(ce / denom, 4) if denom > 0 else 0.0

        return result

    def instability_summary(self) -> Dict[str, Any]:
        """Return aggregated instability stats."""
        di_map = self.compute_di()
        if not di_map:
            return {"count": 0, "avg_di": 0.0, "unstable_modules": []}
        values = list(di_map.values())
        avg = sum(values) / len(values)
        unstable = [m for m, di in di_map.items() if di > 0.7]
        return {
            "count":            len(di_map),
            "avg_di":           round(avg, 4),
            "max_di":           round(max(values), 4),
            "unstable_modules": unstable,
            "di_map":           di_map,
        }


# ══════════════════════════════════════════════════════════════════════════════
# M1.5 — Clone Detection via AST Skeleton Hash (Type-2)
# ══════════════════════════════════════════════════════════════════════════════

_MIN_CLONE_STMTS = 5   # minimum statements to consider a function for cloning


def detect_clones(source: str) -> int:
    """
    Detect Type-2 code clones (same structure, different identifiers/constants).

    Returns the number of clone groups found (groups of ≥2 functions with
    identical AST skeleton).

    Algorithm
    ---------
    1. Parse source to AST
    2. For each function with ≥5 statements, compute a "skeleton" hash:
       - Normalize all `Name(id=...)` → `Name(id=V)`
       - Normalize all `Constant(value=...)` → `Constant(value=C)`
       - Use ast.dump() on the normalized subtree
    3. Group functions by skeleton hash
    4. Count groups with ≥2 members
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0

    hashes: Dict[str, List[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _stmt_count(node.body) < _MIN_CLONE_STMTS:
            continue
        h = _skeleton_hash(node)
        hashes.setdefault(h, []).append(node.name)

    return sum(1 for group in hashes.values() if len(group) >= 2)


def _stmt_count(stmts: List[ast.stmt]) -> int:
    """Count all statements recursively (proxy for function body size)."""
    count = 0
    for s in stmts:
        for node in ast.walk(s):
            if isinstance(node, ast.stmt):
                count += 1
    return count


def _skeleton_hash(fn_node: ast.AST) -> str:
    """
    Compute a Type-2 clone hash for a function node.

    Normalizes all identifier names and constant values so that
    structurally identical functions hash to the same value.
    """
    dumped = ast.dump(fn_node)
    # Normalize function/class name: name='anything' → name='N'
    normalized = re.sub(r"\bname='[^']*'", "name='N'", dumped)
    # Normalize identifier names: id='anything' → id='V'
    normalized = re.sub(r"\bid='[^']*'", "id='V'", normalized)
    # Normalize arg names: arg='anything' → arg='V'
    normalized = re.sub(r"\barg='[^']*'", "arg='V'", normalized)
    # Normalize attribute names: attr='anything' → attr='A'
    normalized = re.sub(r"\battr='[^']*'", "attr='A'", normalized)
    # Normalize constants: value=<anything up to , or ) > → value=C
    normalized = re.sub(r"\bvalue=[^,\)]*", "value=C", normalized)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


# ══════════════════════════════════════════════════════════════════════════════
# M1.6 — Ratings A–E
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class Ratings:
    """Letter ratings (A–E) for key quality dimensions."""
    uco:         str = "A"   # Overall UCO Score rating
    sqale:       str = "A"   # SQALE technical debt rating
    reliability: str = "A"   # Based on ILR + CC
    security:    str = "A"   # Based on dead code + Halstead bugs

    def to_dict(self) -> Dict[str, str]:
        return {
            "uco":         self.uco,
            "sqale":       self.sqale,
            "reliability": self.reliability,
            "security":    self.security,
        }


def compute_ratings(
    uco_score:       float,
    sqale_ratio_pct: float,
    ilr:             float  = 0.0,
    cc:              int    = 1,
    dead_lines:      int    = 0,
    loc:             int    = 1,
    halstead_bugs:   float  = 0.0,
) -> Ratings:
    """
    Compute A–E ratings for UCO, SQALE, Reliability, and Security.

    UCO rating
    ----------
    A: score ≥ 80    B: ≥ 60    C: ≥ 40    D: ≥ 20    E: < 20

    SQALE rating
    ------------
    A: ratio ≤ 5%   B: ≤ 10%   C: ≤ 20%   D: ≤ 50%   E: > 50%

    Reliability
    -----------
    Composite of ILR and CC normalised to 0–100:
    - ILR > 0.5 → −40 pts; ILR > 0.2 → −20 pts
    - CC > 20   → −20 pts; CC > 10 → −10 pts

    Security
    --------
    Composite of dead code ratio and Halstead bugs:
    - dead_ratio > 0.1 → −30 pts
    - Halstead bugs > 3 → −30 pts; > 1 → −15 pts
    """
    # UCO
    uco_rating = _threshold_rating(uco_score, [80, 60, 40, 20])

    # SQALE
    sqale_rating = _threshold_rating(
        100 - sqale_ratio_pct, [95, 90, 80, 50])

    # Reliability
    rel_score = 100.0
    if ilr > 0.5:  rel_score -= 40
    elif ilr > 0.2: rel_score -= 20
    if cc > 20:    rel_score -= 20
    elif cc > 10:  rel_score -= 10
    rel_score = max(0.0, rel_score)
    rel_rating = _threshold_rating(rel_score, [80, 60, 40, 20])

    # Security
    dead_ratio = dead_lines / max(1, loc)
    sec_score  = 100.0
    if dead_ratio > 0.1: sec_score -= 30
    if halstead_bugs > 3.0:  sec_score -= 30
    elif halstead_bugs > 1.0: sec_score -= 15
    sec_score = max(0.0, sec_score)
    sec_rating = _threshold_rating(sec_score, [80, 60, 40, 20])

    return Ratings(
        uco=uco_rating,
        sqale=sqale_rating,
        reliability=rel_rating,
        security=sec_rating,
    )


def _threshold_rating(score: float, thresholds: List[float]) -> str:
    """Map a score to A–E using descending thresholds."""
    letters = ["A", "B", "C", "D", "E"]
    for i, t in enumerate(thresholds):
        if score >= t:
            return letters[i]
    return letters[-1]


# ══════════════════════════════════════════════════════════════════════════════
# Orchestrator — AdvancedAnalyzer
# ══════════════════════════════════════════════════════════════════════════════

class AdvancedAnalyzer:
    """
    Orchestrates all M1 advanced metrics for a single Python source file.

    Attaches results to the MetricVector as dynamic attributes (setattr
    pattern) without modifying MetricVector's fixed dataclass fields.

    Dynamic attributes added to MetricVector
    -----------------------------------------
    mv.cognitive_complexity       int    — module total cognitive CC
    mv.cognitive_per_function     dict   — {fn_name: cog_cc}
    mv.cognitive_fn_max           int    — max cognitive CC across functions
    mv.sqale_debt_minutes         int    — total SQALE debt in minutes
    mv.sqale_ratio                float  — debt ratio as % [0–100]
    mv.sqale_rating               str    — A–E
    mv.sqale_breakdown            dict   — per-rule debt breakdown
    mv.function_profiles          list   — List[FunctionProfile.to_dict()]
    mv.clone_count                int    — Type-2 clone group count
    mv.ratings                    dict   — {"uco":"A","sqale":"B",...}
    mv.advanced_ok                bool   — True if M1 analysis succeeded
    """

    def analyze(self, source: str, mv: Any, visitor: Any) -> None:
        """
        Enrich mv with M1 metrics.

        Parameters
        ----------
        source  : original Python source code
        mv      : MetricVector (will be mutated via setattr)
        visitor : _UCOVisitor instance (already visited the same source)
        """
        try:
            self._analyze_impl(source, mv, visitor)
            mv.advanced_ok = True
        except Exception as exc:   # pragma: no cover — safety net
            mv.advanced_ok = False
            mv.advanced_error = str(exc)
            # Set safe defaults so downstream code never KeyErrors
            mv.cognitive_complexity   = 0
            mv.cognitive_per_function = {}
            mv.cognitive_fn_max       = 0
            mv.sqale_debt_minutes     = 0
            mv.sqale_ratio            = 0.0
            mv.sqale_rating           = "A"
            mv.sqale_breakdown        = {}
            mv.function_profiles      = []
            mv.clone_count            = 0
            mv.ratings                = Ratings().to_dict()

    # ── Internal ─────────────────────────────────────────────────────────────

    def _analyze_impl(self, source: str, mv: Any, visitor: Any) -> None:
        loc = getattr(mv, "lines_of_code", 1)

        # M1.1 — Cognitive Complexity
        cog_total, cog_per_fn = cognitive_complexity(source)
        cog_fn_max = max(cog_per_fn.values(), default=0)
        mv.cognitive_complexity   = cog_total
        mv.cognitive_per_function = cog_per_fn
        mv.cognitive_fn_max       = cog_fn_max

        # M1.3 — Function profiles (needs fn_cc from visitor)
        fn_cc_dict: Dict[str, int] = {}
        if hasattr(visitor, "fn_cc"):
            fn_cc_dict = dict(visitor.fn_cc)
        profiles = build_function_profiles(source, fn_cc_dict, cog_per_fn)
        mv.function_profiles = [p.to_dict() for p in profiles]

        # M1.5 — Clone detection
        clone_count = detect_clones(source)
        mv.clone_count = clone_count

        # M1.2 — SQALE debt (uses all metrics computed so far)
        ilr_loop_count = getattr(visitor, "loop_risk_count", 0)
        metrics_for_sqale: Dict[str, Any] = {
            "cyclomatic_complexity": getattr(mv, "cyclomatic_complexity", 1),
            "fn_cc_max":    max(fn_cc_dict.values(), default=1),
            "cognitive_cc": cog_total,
            "cognitive_fn_max": cog_fn_max,
            "syntactic_dead_code": getattr(mv, "syntactic_dead_code", 0),
            "ilr_loop_count": ilr_loop_count,
            "clone_count":  clone_count,
            "dependency_instability": getattr(mv, "dependency_instability", 0.0),
            "halstead_bugs": getattr(mv, "halstead_bugs", 0.0),
        }
        sqale = sqale_debt(metrics_for_sqale, loc)
        mv.sqale_debt_minutes = sqale.debt_minutes
        mv.sqale_ratio        = sqale.sqale_ratio
        mv.sqale_rating       = sqale.rating
        mv.sqale_breakdown    = sqale.breakdown

        # M1.6 — Ratings
        uco_score = float(getattr(mv, "_uco_score", 0.0))
        # If the MetricVector doesn't carry uco_score, derive it from status
        if uco_score == 0.0:
            status = getattr(mv, "status", "STABLE")
            uco_score = {"STABLE": 75.0, "WARNING": 50.0, "CRITICAL": 20.0}.get(status, 50.0)

        ratings = compute_ratings(
            uco_score       = uco_score,
            sqale_ratio_pct = sqale.sqale_ratio,
            ilr             = getattr(mv, "infinite_loop_risk", 0.0),
            cc              = getattr(mv, "cyclomatic_complexity", 1),
            dead_lines      = getattr(mv, "syntactic_dead_code", 0),
            loc             = loc,
            halstead_bugs   = getattr(mv, "halstead_bugs", 0.0),
        )
        mv.ratings = ratings.to_dict()
