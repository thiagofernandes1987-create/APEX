"""
UCO-Sensor — Governance Policy Engine (M2.1 + M2.2)
======================================================

M2.1  Policy Engine — rules evaluated against MetricVector attributes
M2.2  Quality Gate  — pass/fail outcome for CI/CD pipelines

Policy format (Python dict or YAML-like dict):
    {
        "name":    "default",
        "version": "1.0",
        "pass_threshold": 70,     # gate_score threshold for PASS (0–100)
        "rules": [
            {
                "id":        "CC_LIMIT",
                "field":     "cyclomatic_complexity",
                "operator":  "lte",
                "threshold": 15,
                "severity":  "WARNING",   # WARNING | ERROR | INFO
                "message":   "Cyclomatic complexity too high"
            },
            ...
        ]
    }

Operators
---------
    lte, gte, lt, gt, eq, neq  : numeric/string comparison
    in, not_in                 : membership in list threshold
    rating_lte, rating_gte     : A≤B≤C≤D≤E letter-rating comparison

Gate Score
----------
    Starts at 100.
    ERROR  violation: −20 pts
    WARNING violation: −10 pts
    INFO   violation: −2  pts
    Clamped to [0, 100].
    passed = gate_score >= pass_threshold  (default: 70)

Public API
----------
    evaluate_policy(metrics, policy)     -> PolicyResult
    load_default_policy()                -> Policy
    policy_from_dict(d)                  -> Policy
    gate_score_to_grade(score)           -> str  (A–F)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


# ── Rating helpers ────────────────────────────────────────────────────────────

_RATING_NUM: Dict[str, int] = {"A": 1, "B": 2, "C": 3, "D": 4, "E": 5}

_OPERATOR_FNS = {
    "lte":        lambda a, b: _num(a) <= _num(b),
    "gte":        lambda a, b: _num(a) >= _num(b),
    "lt":         lambda a, b: _num(a) <  _num(b),
    "gt":         lambda a, b: _num(a) >  _num(b),
    "eq":         lambda a, b: a == b,
    "neq":        lambda a, b: a != b,
    "in":         lambda a, b: a in b,
    "not_in":     lambda a, b: a not in b,
    "rating_lte": lambda a, b: _RATING_NUM.get(str(a), 9) <= _RATING_NUM.get(str(b), 9),
    "rating_gte": lambda a, b: _RATING_NUM.get(str(a), 0) >= _RATING_NUM.get(str(b), 0),
}

_SEVERITY_PENALTY: Dict[str, int] = {
    "ERROR":   20,
    "WARNING": 10,
    "INFO":     2,
}

_GATE_GRADES = [
    (90, "A"),
    (80, "B"),
    (70, "C"),
    (60, "D"),
    (50, "E"),
    (0,  "F"),
]


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class PolicyRule:
    """A single quality rule."""
    id:        str
    field:     str
    operator:  str          # lte | gte | lt | gt | eq | neq | in | not_in | rating_lte | rating_gte
    threshold: Any          # numeric, string, or list
    severity:  str = "WARNING"
    message:   str = ""

    def __post_init__(self) -> None:
        self.severity = self.severity.upper()
        if self.severity not in _SEVERITY_PENALTY:
            self.severity = "WARNING"


@dataclass
class Policy:
    """A named collection of quality rules."""
    name:           str
    version:        str   = "1.0"
    pass_threshold: int   = 70     # minimum gate_score to PASS
    rules:          List[PolicyRule] = field(default_factory=list)
    description:    str   = ""


@dataclass
class Violation:
    """A single rule violation."""
    rule_id:   str
    field:     str
    operator:  str
    threshold: Any
    actual:    Any
    severity:  str
    message:   str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id":   self.rule_id,
            "field":     self.field,
            "operator":  self.operator,
            "threshold": self.threshold,
            "actual":    self.actual,
            "severity":  self.severity,
            "message":   self.message,
        }


@dataclass
class PolicyResult:
    """Result of evaluating a policy against a metrics snapshot."""
    passed:     bool
    gate_score: int
    grade:      str             # A–F
    violations: List[Violation] = field(default_factory=list)
    policy_name: str = ""
    summary:    str = ""

    @property
    def errors(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == "ERROR"]

    @property
    def warnings(self) -> List[Violation]:
        return [v for v in self.violations if v.severity == "WARNING"]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed":      self.passed,
            "gate_score":  self.gate_score,
            "grade":       self.grade,
            "policy_name": self.policy_name,
            "summary":     self.summary,
            "violations":  [v.to_dict() for v in self.violations],
            "error_count": len(self.errors),
            "warning_count": len(self.warnings),
        }


# ── Core evaluation ───────────────────────────────────────────────────────────

def evaluate_policy(
    metrics:  Dict[str, Any],
    policy:   Union[Policy, Dict],
) -> PolicyResult:
    """
    Evaluate a metrics dict against a policy.

    Parameters
    ----------
    metrics : flat dict with metric field values, e.g.:
        {
            "cyclomatic_complexity": 12,
            "cognitive_complexity": 18,
            "infinite_loop_risk": 0.1,
            "sqale_rating": "B",
            ...
        }
    policy  : Policy object or plain dict (converted via policy_from_dict)
    """
    if isinstance(policy, dict):
        policy = policy_from_dict(policy)

    violations: List[Violation] = []

    for rule in policy.rules:
        actual = metrics.get(rule.field)
        if actual is None:
            continue   # skip rules for metrics not present in this snapshot

        op_fn = _OPERATOR_FNS.get(rule.operator)
        if op_fn is None:
            continue   # unknown operator — skip silently

        try:
            satisfied = op_fn(actual, rule.threshold)
        except Exception:
            satisfied = True   # evaluation error → don't penalise

        if not satisfied:
            msg = rule.message or (
                f"{rule.field} {rule.operator} {rule.threshold} "
                f"(actual: {actual})"
            )
            violations.append(Violation(
                rule_id=rule.id,
                field=rule.field,
                operator=rule.operator,
                threshold=rule.threshold,
                actual=actual,
                severity=rule.severity,
                message=msg,
            ))

    # Compute gate score
    penalty = sum(_SEVERITY_PENALTY.get(v.severity, 10) for v in violations)
    gate_score = max(0, min(100, 100 - penalty))

    passed = gate_score >= policy.pass_threshold
    grade  = gate_score_to_grade(gate_score)

    n_err  = sum(1 for v in violations if v.severity == "ERROR")
    n_warn = sum(1 for v in violations if v.severity == "WARNING")
    summary = (
        f"{'PASS' if passed else 'FAIL'} — score={gate_score}/100 ({grade}) | "
        f"{n_err} errors, {n_warn} warnings"
    )

    return PolicyResult(
        passed=passed,
        gate_score=gate_score,
        grade=grade,
        violations=violations,
        policy_name=policy.name,
        summary=summary,
    )


def gate_score_to_grade(score: int) -> str:
    """Map gate score [0–100] to letter grade A–F."""
    for threshold, grade in _GATE_GRADES:
        if score >= threshold:
            return grade
    return "F"


# ── Default policy ────────────────────────────────────────────────────────────

_DEFAULT_POLICY_DICT: Dict[str, Any] = {
    "name":           "uco_default",
    "version":        "1.0",
    "description":    "Default UCO quality policy — enforces safe thresholds for all 9 channels + M1",
    "pass_threshold": 70,
    "rules": [
        # ── M0 metrics (9 canais UCO) ─────────────────────────────────────
        {
            "id": "CC_WARNING",
            "field": "cyclomatic_complexity",
            "operator": "lte",
            "threshold": 15,
            "severity": "WARNING",
            "message": "Cyclomatic complexity > 15 — consider extracting methods",
        },
        {
            "id": "CC_ERROR",
            "field": "cyclomatic_complexity",
            "operator": "lte",
            "threshold": 25,
            "severity": "ERROR",
            "message": "Cyclomatic complexity > 25 — code is dangerously complex",
        },
        {
            "id": "ILR_ERROR",
            "field": "infinite_loop_risk",
            "operator": "lte",
            "threshold": 0.5,
            "severity": "ERROR",
            "message": "Infinite loop risk > 0.5 — loops lack guaranteed termination",
        },
        {
            "id": "DEAD_CODE_WARNING",
            "field": "syntactic_dead_code",
            "operator": "lte",
            "threshold": 20,
            "severity": "WARNING",
            "message": "More than 20 dead code lines detected",
        },
        {
            "id": "HALSTEAD_BUGS_WARNING",
            "field": "halstead_bugs",
            "operator": "lte",
            "threshold": 2.0,
            "severity": "WARNING",
            "message": "Halstead bug estimate > 2.0 — high defect probability",
        },
        {
            "id": "DI_WARNING",
            "field": "dependency_instability",
            "operator": "lte",
            "threshold": 0.8,
            "severity": "WARNING",
            "message": "Dependency Instability > 0.8 — module too efferent-coupled",
        },
        # ── M1 metrics (advanced) ──────────────────────────────────────────
        {
            "id": "COG_CC_WARNING",
            "field": "cognitive_complexity",
            "operator": "lte",
            "threshold": 20,
            "severity": "WARNING",
            "message": "Cognitive complexity > 20 — code is hard to understand",
        },
        {
            "id": "COG_CC_ERROR",
            "field": "cognitive_complexity",
            "operator": "lte",
            "threshold": 35,
            "severity": "ERROR",
            "message": "Cognitive complexity > 35 — code is extremely hard to understand",
        },
        {
            "id": "SQALE_RATING_WARNING",
            "field": "sqale_rating",
            "operator": "rating_lte",
            "threshold": "C",
            "severity": "WARNING",
            "message": "SQALE rating worse than C — technical debt is accumulating",
        },
        {
            "id": "SQALE_RATING_ERROR",
            "field": "sqale_rating",
            "operator": "rating_lte",
            "threshold": "D",
            "severity": "ERROR",
            "message": "SQALE rating D or E — critical technical debt",
        },
        {
            "id": "CLONE_WARNING",
            "field": "clone_count",
            "operator": "lte",
            "threshold": 3,
            "severity": "WARNING",
            "message": "More than 3 clone groups detected — refactor duplicated logic",
        },
    ],
}


def load_default_policy() -> Policy:
    """Return the built-in UCO default quality policy."""
    return policy_from_dict(_DEFAULT_POLICY_DICT)


def policy_from_dict(d: Dict[str, Any]) -> Policy:
    """Convert a plain dict to a Policy object."""
    rules = [
        PolicyRule(
            id=r.get("id", f"rule_{i}"),
            field=r.get("field", ""),
            operator=r.get("operator", "lte"),
            threshold=r.get("threshold", 0),
            severity=r.get("severity", "WARNING"),
            message=r.get("message", ""),
        )
        for i, r in enumerate(d.get("rules", []))
    ]
    return Policy(
        name=d.get("name", "unnamed"),
        version=str(d.get("version", "1.0")),
        pass_threshold=int(d.get("pass_threshold", 70)),
        rules=rules,
        description=d.get("description", ""),
    )


def mv_to_metrics_dict(mv: Any) -> Dict[str, Any]:
    """
    Extract a flat metrics dict from a MetricVector (or any object with
    standard UCO attributes).  Includes M1 fields if present.
    """
    fields = [
        "cyclomatic_complexity", "hamiltonian", "infinite_loop_risk",
        "dsm_density", "dsm_cyclic_ratio", "dependency_instability",
        "syntactic_dead_code", "duplicate_block_count", "halstead_bugs",
        # M1
        "cognitive_complexity", "cognitive_fn_max",
        "sqale_debt_minutes", "sqale_ratio", "sqale_rating",
        "clone_count",
    ]
    result: Dict[str, Any] = {}
    for f in fields:
        v = getattr(mv, f, None)
        if v is not None:
            result[f] = v
    # ratings sub-fields
    ratings = getattr(mv, "ratings", None)
    if isinstance(ratings, dict):
        for k, v in ratings.items():
            result[f"rating_{k}"] = v
    return result
