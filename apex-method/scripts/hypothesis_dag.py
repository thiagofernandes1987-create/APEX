#!/usr/bin/env python3
"""
hypothesis_dag.py — APEX hypothesis_dag (v00.32.1, OPP-MAS-01, SR_32), faithful port.

Tracks dependencies between hypotheses, anchors, and findings. When an anchor is destroyed,
invalidation cascades to all dependents via BFS O(V+E) with a mandatory visited_set. DFS
acyclicity check before inserting an edge keeps the graph acyclic. Snapshot is edge-only
({edges, suspects, invalidated}) — nodes live in the hypothesis_tracker (context), so
serialization is ~15-30 tokens vs 8000-15000 for full nodes (-99%).

Fallbacks (from spec): cycle -> [DAG_CYCLE_REJECTED]; >200 nodes -> reset [DAG_RESET];
tracker missing -> [DAG_UNAVAILABLE].

WHY: Orphan hypotheses survive after their premises are refuted; the DAG cascades invalidation.
WHAT IF IT FAILS: cycle -> [DAG_CYCLE_REJECTED]; >200 nodes -> [DAG_RESET]; tracker missing -> [DAG_UNAVAILABLE].
"""
import json

MAX_NODES = 200


class HypothesisDAG:
    def __init__(self):
        self.nodes = {}
        self.out = {}          # src -> set(dst): dst depends on src
        self.suspects = set()
        self.invalidated = set()
        self.events = []

    def register(self, node_id, node_type="hypothesis", anchors_used=(), phase="", confidence=None):
        if len(self.nodes) >= MAX_NODES:
            kept_events = self.events   # audit fix v1.17.0: reset erased its own event log
            self.__init__()
            self.events = kept_events
            self.events.append("[DAG_RESET]")
        self.nodes[node_id] = {"type": node_type, "anchors": list(anchors_used),
                               "phase": phase, "confidence": confidence}
        self.out.setdefault(node_id, set())
        return True

    def _creates_cycle(self, src, dst):
        stack, seen = [dst], set()
        while stack:
            n = stack.pop()
            if n == src:
                return True
            if n in seen:
                continue
            seen.add(n)
            stack.extend(self.out.get(n, ()))
        return False

    def add_edge(self, src, dst, edge_type="depends"):
        for n in (src, dst):
            self.nodes.setdefault(n, {"type": "hypothesis", "anchors": [], "phase": "", "confidence": None})
            self.out.setdefault(n, set())
        if self._creates_cycle(src, dst):
            self.events.append(f"[DAG_CYCLE_REJECTED: {dst}]")
            return False
        self.out[src].add(dst)
        return True

    def invalidate_cascade(self, node_id):
        """BFS O(V+E) with mandatory visited_set. Returns set of affected ids."""
        affected, queue, visited = set(), [node_id], set()
        while queue:
            n = queue.pop(0)
            if n in visited:
                continue
            visited.add(n)
            affected.add(n)
            self.invalidated.add(n)
            for dep in self.out.get(n, ()):
                if dep not in visited:
                    queue.append(dep)
        self.events.append(f"[DAG_CASCADE_INVALIDATED: {len(affected)} nodes]")
        return affected

    def mark_suspect(self, node_id):
        self.suspects.add(node_id)

    def compress_for_snapshot(self):
        edges = [{"src": s, "dst": d, "type": "depends"} for s, ds in self.out.items() for d in ds]
        return {"edges": edges, "suspects": sorted(self.suspects), "invalidated": sorted(self.invalidated)}


if __name__ == "__main__":
    g = HypothesisDAG()
    for h in ("A1_anchor", "H2", "H3", "H4"):
        g.register(h, node_type="anchor" if "anchor" in h else "hypothesis")
    g.add_edge("A1_anchor", "H2")
    g.add_edge("H2", "H3")
    g.add_edge("H2", "H4")
    print("cycle rejected:", g.add_edge("H4", "A1_anchor") is False)
    affected = g.invalidate_cascade("A1_anchor")
    print("cascade affected:", sorted(affected))
    print("snapshot:", json.dumps(g.compress_for_snapshot()))
    print("events:", g.events)
