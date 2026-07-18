"""M2.5 — estrutura tipada do CausalDSM, sem pesos biológicos implícitos."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Mapping

from ..contracts import GateEnvelope, GateStatus
from ..formula_registry import FormulaEvidence, get_formula


class CausalRegime(str, Enum):
    STATIC_DAG = "STATIC_DAG"
    DYNAMIC_DSCM = "DYNAMIC_DSCM"


class NodeKind(str, Enum):
    DRUG = "DRUG"
    TARGET = "TARGET"
    PATHWAY = "PATHWAY"
    OUTCOME = "OUTCOME"
    RISK = "RISK"


class OptimizationRole(str, Enum):
    NONE = "NONE"
    DECISION = "DECISION"
    OBJECTIVE = "OBJECTIVE"
    CONSTRAINT = "CONSTRAINT"


class ObjectiveDirection(str, Enum):
    NONE = "NONE"
    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


_LAYER = {
    NodeKind.DRUG: 0,
    NodeKind.TARGET: 1,
    NodeKind.PATHWAY: 2,
    NodeKind.OUTCOME: 3,
    NodeKind.RISK: 3,
}


@dataclass(frozen=True)
class CausalNode:
    node_id: str
    kind: NodeKind
    unit: str
    role: OptimizationRole = OptimizationRole.NONE
    direction: ObjectiveDirection = ObjectiveDirection.NONE
    baseline: float | None = None
    bounds: tuple[float, float] | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.node_id.strip() or not self.unit.strip():
            raise ValueError("node_id e unit são obrigatórios")
        if self.baseline is not None and not math.isfinite(self.baseline):
            raise ValueError("baseline deve ser finito")
        if self.bounds is not None:
            low, high = self.bounds
            if not math.isfinite(low) or not math.isfinite(high) or low >= high:
                raise ValueError("bounds deve conter limites finitos e crescentes")
            if self.baseline is not None and not low <= self.baseline <= high:
                raise ValueError("baseline deve pertencer aos bounds")
        if self.role is OptimizationRole.OBJECTIVE:
            if self.direction is ObjectiveDirection.NONE:
                raise ValueError("Nós objetivo devem declarar MINIMIZE ou MAXIMIZE")
        elif self.direction is not ObjectiveDirection.NONE:
            raise ValueError("Somente nós objetivo podem declarar direção")


@dataclass(frozen=True)
class Hyperedge:
    edge_id: str
    tails: tuple[str, ...]
    head: str
    mechanism: str
    formula_id: str | None = None
    sign: int = 1
    delay: float = 0.0
    parameters: Mapping[str, float] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.edge_id.strip() or not self.head.strip() or not self.mechanism.strip():
            raise ValueError("edge_id, head e mechanism são obrigatórios")
        if not self.tails or any(not tail.strip() for tail in self.tails):
            raise ValueError("Uma hiperaresta exige ao menos um nó de entrada")
        if len(set(self.tails)) != len(self.tails):
            raise ValueError("tails não pode conter nós duplicados")
        if self.sign not in {-1, 1}:
            raise ValueError("sign deve ser -1 ou 1")
        if not math.isfinite(self.delay) or self.delay < 0:
            raise ValueError("delay deve ser finito e não negativo")
        if not all(math.isfinite(value) for value in self.parameters.values()):
            raise ValueError("Parâmetros de hiperarestas devem ser finitos")


@dataclass
class CausalDSM:
    regime: CausalRegime
    nodes: dict[str, CausalNode] = field(default_factory=dict)
    edges: dict[str, Hyperedge] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CausalDSM":
        try:
            dsm = cls(CausalRegime(str(data["regime"])))
            for raw in data["nodes"]:
                node = CausalNode(
                    node_id=str(raw["node_id"]),
                    kind=NodeKind(str(raw["kind"])),
                    unit=str(raw["unit"]),
                    role=OptimizationRole(str(raw.get("role", "NONE"))),
                    direction=ObjectiveDirection(str(raw.get("direction", "NONE"))),
                    baseline=raw.get("baseline"),
                    bounds=tuple(raw["bounds"]) if raw.get("bounds") is not None else None,
                    metadata=dict(raw.get("metadata", {})),
                )
                dsm.add_node(node)
            for raw in data["edges"]:
                edge = Hyperedge(
                    edge_id=str(raw["edge_id"]),
                    tails=tuple(str(item) for item in raw["tails"]),
                    head=str(raw["head"]),
                    mechanism=str(raw["mechanism"]),
                    formula_id=raw.get("formula_id"),
                    sign=int(raw.get("sign", 1)),
                    delay=float(raw.get("delay", 0.0)),
                    parameters={str(key): float(value) for key, value in raw.get("parameters", {}).items()},
                    evidence_ids=tuple(str(item) for item in raw.get("evidence_ids", [])),
                )
                dsm.add_edge(edge)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Payload CausalDSM inválido: {exc}") from exc
        return dsm

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime.value,
            "nodes": [
                {
                    "node_id": node.node_id,
                    "kind": node.kind.value,
                    "unit": node.unit,
                    "role": node.role.value,
                    "direction": node.direction.value,
                    "baseline": node.baseline,
                    "bounds": list(node.bounds) if node.bounds is not None else None,
                    "metadata": dict(node.metadata),
                }
                for node in self.nodes.values()
            ],
            "edges": [
                {
                    "edge_id": edge.edge_id,
                    "tails": list(edge.tails),
                    "head": edge.head,
                    "mechanism": edge.mechanism,
                    "formula_id": edge.formula_id,
                    "sign": edge.sign,
                    "delay": edge.delay,
                    "parameters": dict(edge.parameters),
                    "evidence_ids": list(edge.evidence_ids),
                }
                for edge in self.edges.values()
            ],
        }

    def add_node(self, node: CausalNode) -> None:
        if node.node_id in self.nodes:
            raise ValueError(f"Nó duplicado: {node.node_id}")
        self.nodes[node.node_id] = node

    def add_edge(self, edge: Hyperedge) -> None:
        if edge.edge_id in self.edges:
            raise ValueError(f"Hiperaresta duplicada: {edge.edge_id}")
        missing = [node_id for node_id in (*edge.tails, edge.head) if node_id not in self.nodes]
        if missing:
            raise ValueError("Nós ausentes na hiperaresta: " + ", ".join(sorted(set(missing))))
        self.edges[edge.edge_id] = edge

    def _adjacency(self) -> dict[str, set[str]]:
        adjacency = {node_id: set() for node_id in self.nodes}
        for edge in self.edges.values():
            for tail in edge.tails:
                adjacency[tail].add(edge.head)
        return adjacency

    def _has_cycle(self) -> bool:
        adjacency = self._adjacency()
        state = {node_id: 0 for node_id in self.nodes}

        def visit(node_id: str) -> bool:
            state[node_id] = 1
            for child in adjacency[node_id]:
                if state[child] == 1 or (state[child] == 0 and visit(child)):
                    return True
            state[node_id] = 2
            return False

        return any(state[node_id] == 0 and visit(node_id) for node_id in self.nodes)

    def validation_issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        for edge in self.edges.values():
            head = self.nodes[edge.head]
            tails = [self.nodes[node_id] for node_id in edge.tails]
            if self.regime is CausalRegime.STATIC_DAG:
                if edge.head in edge.tails:
                    issues.append(f"{edge.edge_id}: autorreferência não é válida em STATIC_DAG")
                if any(_LAYER[head.kind] != _LAYER[tail.kind] + 1 for tail in tails):
                    issues.append(f"{edge.edge_id}: conexão viola a progressão de camadas do DAG")
                if edge.delay != 0:
                    issues.append(f"{edge.edge_id}: delay pertence ao regime dinâmico")
            else:
                backward_or_same = any(_LAYER[head.kind] <= _LAYER[tail.kind] for tail in tails)
                if backward_or_same and edge.delay <= 0:
                    issues.append(
                        f"{edge.edge_id}: feedback deve declarar atraso positivo no D-SCM"
                    )
            if edge.formula_id is None:
                issues.append(f"{edge.edge_id}: fórmula estrutural não declarada")
            else:
                try:
                    get_formula(edge.formula_id)
                except KeyError:
                    issues.append(f"{edge.edge_id}: fórmula desconhecida {edge.formula_id}")
        if self.regime is CausalRegime.STATIC_DAG and self._has_cycle():
            issues.append("A topologia STATIC_DAG contém ciclo")
        return tuple(issues)

    def topological_order(self) -> tuple[str, ...]:
        if self.regime is not CausalRegime.STATIC_DAG:
            raise ValueError("Ordem topológica só é definida para STATIC_DAG")
        adjacency = self._adjacency()
        indegree = {node_id: 0 for node_id in self.nodes}
        for children in adjacency.values():
            for child in children:
                indegree[child] += 1
        queue = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
        order: list[str] = []
        while queue:
            node_id = queue.pop(0)
            order.append(node_id)
            for child in sorted(adjacency[node_id]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
                    queue.sort()
        if len(order) != len(self.nodes):
            raise ValueError("A topologia contém ciclo")
        return tuple(order)

    def dependency_matrix(self) -> tuple[tuple[str, ...], tuple[tuple[int, ...], ...]]:
        """Retorna DSM onde matriz[head][tail] contém o sinal da dependência."""
        node_ids = tuple(sorted(self.nodes))
        index = {node_id: position for position, node_id in enumerate(node_ids)}
        matrix = [[0 for _ in node_ids] for _ in node_ids]
        for edge in self.edges.values():
            for tail in edge.tails:
                matrix[index[edge.head]][index[tail]] = edge.sign
        return node_ids, tuple(tuple(row) for row in matrix)

    def descendants(self, node_id: str) -> tuple[str, ...]:
        if node_id not in self.nodes:
            raise KeyError(f"Nó desconhecido: {node_id}")
        adjacency = self._adjacency()
        found: set[str] = set()
        pending = list(adjacency[node_id])
        while pending:
            child = pending.pop()
            if child in found:
                continue
            found.add(child)
            pending.extend(adjacency[child])
        return tuple(sorted(found))

    def intervene(self, values: Mapping[str, float]) -> "CausalDSM":
        clone = CausalDSM(self.regime, self.nodes.copy(), self.edges.copy())
        for node_id, value in values.items():
            if node_id not in clone.nodes:
                raise KeyError(f"Nó desconhecido: {node_id}")
            if not math.isfinite(value):
                raise ValueError("Valores de intervenção devem ser finitos")
            node = clone.nodes[node_id]
            if node.bounds is not None and not node.bounds[0] <= value <= node.bounds[1]:
                raise ValueError(f"Intervenção fora dos bounds de {node_id}")
            clone.nodes[node_id] = replace(node, baseline=value)
        clone.edges = {
            edge_id: edge for edge_id, edge in clone.edges.items() if edge.head not in values
        }
        return clone

    def objective_nodes(self) -> tuple[CausalNode, ...]:
        return tuple(node for node in self.nodes.values() if node.role is OptimizationRole.OBJECTIVE)

    def constraint_nodes(self) -> tuple[CausalNode, ...]:
        return tuple(node for node in self.nodes.values() if node.role is OptimizationRole.CONSTRAINT)

    def structural_gate(self) -> GateEnvelope:
        issues = self.validation_issues()
        if issues:
            return GateEnvelope(
                gate_id="M2.5.STRUCTURE",
                module_id="M2.5",
                status=GateStatus.FAILED,
                summary="O CausalDSM viola contratos topológicos ou semânticos.",
                metrics={"nodes": len(self.nodes), "edges": len(self.edges)},
                errors=issues,
            )
        weak_formulas = []
        for edge in self.edges.values():
            formula = get_formula(edge.formula_id or "")
            if formula.evidence not in {
                FormulaEvidence.TESTED,
                FormulaEvidence.REPRODUCED,
                FormulaEvidence.EXTERNALLY_VALIDATED,
            }:
                weak_formulas.append(formula.formula_id)
        return GateEnvelope(
            gate_id="M2.5.STRUCTURE",
            module_id="M2.5",
            status=GateStatus.NEEDS_REVIEW,
            summary="A estrutura causal é consistente; previsão numérica permanece bloqueada.",
            metrics={
                "nodes": len(self.nodes),
                "edges": len(self.edges),
                "regime": self.regime.value,
                "formulas_without_strong_evidence": sorted(set(weak_formulas)),
            },
            warnings=(
                "Topologia válida não identifica efeitos nem calibra pesos biológicos.",
                "Ativação de M2.5 exige equações, parâmetros, incerteza e validação M11.",
            ),
        )
