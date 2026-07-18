import unittest

from apex_r.contracts import GateStatus
from apex_r.formula_registry import FormulaEvidence, get_formula, list_formulas
from apex_r.modules.causal_dsm import (
    CausalDSM,
    CausalNode,
    CausalRegime,
    Hyperedge,
    NodeKind,
    ObjectiveDirection,
    OptimizationRole,
)


def build_static_dsm() -> CausalDSM:
    dsm = CausalDSM(CausalRegime.STATIC_DAG)
    dsm.add_node(
        CausalNode(
            "dose_a",
            NodeKind.DRUG,
            "mg",
            role=OptimizationRole.DECISION,
            bounds=(0.0, 100.0),
        )
    )
    dsm.add_node(CausalNode("target_a", NodeKind.TARGET, "fraction"))
    dsm.add_node(CausalNode("pathway_a", NodeKind.PATHWAY, "fraction"))
    dsm.add_node(
        CausalNode(
            "efficacy",
            NodeKind.OUTCOME,
            "fraction",
            role=OptimizationRole.OBJECTIVE,
            direction=ObjectiveDirection.MAXIMIZE,
        )
    )
    dsm.add_edge(
        Hyperedge("e1", ("dose_a",), "target_a", "binding", "M5.HILL")
    )
    dsm.add_edge(
        Hyperedge("e2", ("target_a",), "pathway_a", "activation", "M5.HILL")
    )
    dsm.add_edge(
        Hyperedge("e3", ("pathway_a",), "efficacy", "response", "M5.HILL")
    )
    return dsm


class FormulaRegistryTests(unittest.TestCase):
    def test_registry_has_no_false_external_validation(self):
        self.assertGreaterEqual(len(list_formulas()), 7)
        self.assertFalse(
            any(formula.evidence is FormulaEvidence.EXTERNALLY_VALIDATED for formula in list_formulas())
        )
        self.assertEqual(get_formula("m2.delta_g_from_kd").evidence, FormulaEvidence.TESTED)


class CausalDsmTests(unittest.TestCase):
    def test_static_dsm_has_order_matrix_and_optimization_roles(self):
        dsm = build_static_dsm()
        self.assertEqual(dsm.validation_issues(), ())
        self.assertEqual(dsm.topological_order(), ("dose_a", "target_a", "pathway_a", "efficacy"))
        node_ids, matrix = dsm.dependency_matrix()
        self.assertEqual(matrix[node_ids.index("target_a")][node_ids.index("dose_a")], 1)
        self.assertEqual([node.node_id for node in dsm.objective_nodes()], ["efficacy"])
        self.assertEqual(dsm.structural_gate().status, GateStatus.NEEDS_REVIEW)

    def test_json_round_trip_preserves_structure(self):
        original = build_static_dsm()
        restored = CausalDSM.from_dict(original.to_dict())
        self.assertEqual(restored.to_dict(), original.to_dict())
        self.assertEqual(restored.validation_issues(), ())

    def test_intervention_removes_incoming_edges(self):
        dsm = build_static_dsm()
        intervened = dsm.intervene({"pathway_a": 0.0})
        self.assertNotIn("e2", intervened.edges)
        self.assertIn("e3", intervened.edges)
        self.assertIn("efficacy", intervened.descendants("pathway_a"))

    def test_static_dag_rejects_layer_skip(self):
        dsm = build_static_dsm()
        dsm.add_edge(Hyperedge("bad", ("dose_a",), "efficacy", "shortcut", "M5.HILL"))
        self.assertTrue(any("progressão de camadas" in issue for issue in dsm.validation_issues()))

    def test_dynamic_feedback_requires_positive_delay(self):
        dsm = CausalDSM(CausalRegime.DYNAMIC_DSCM)
        dsm.add_node(CausalNode("target", NodeKind.TARGET, "fraction"))
        dsm.add_node(CausalNode("pathway", NodeKind.PATHWAY, "fraction"))
        dsm.add_edge(Hyperedge("forward", ("target",), "pathway", "activation", "M5.HILL"))
        dsm.add_edge(Hyperedge("feedback", ("pathway",), "target", "feedback", "M5.HILL"))
        self.assertTrue(any("atraso positivo" in issue for issue in dsm.validation_issues()))


if __name__ == "__main__":
    unittest.main()
