"""
Sprint X — CFG visualizável + hotspot overlay (v3.7.0)
========================================================

Extract a coarse control-flow graph from Python source, return it as
structured JSON (and optionally DOT), optionally overlaid with hotspot
metadata (APS contribution, latest SAST findings).

Design choices (APEX SCIENTIFIC)
--------------------------------

* **Function-level granularity** — one CFG per top-level function or
  method.  Module-level statements collapsed to a "<module>" node.
* **Bounded** — max 200 nodes per CFG (TRUNCATED status when hit).
* **Pure Python AST** — no tree-sitter dep so CFG works in any sandbox.
* **Defensive** — invalid source returns ``status="ERROR"`` with the
  reason, never raises to the caller.
* **Read-only** — does NOT mutate the snapshot store.

Public API
----------

* ``build_cfg(source: str, *, max_nodes=200) -> Dict``
  → ``{"status":"OK"|"TRUNCATED"|"ERROR", "functions": [...]}``
* ``overlay_hotspots(cfg: Dict, store, module_id: str) -> Dict``
  → enriches each node with ``severity`` (max SAST finding severity that
  maps to its line) and ``aps_contribution`` (fraction of module APS
  delta attributable to the function, or 0.0 when not computable).
* ``cfg_as_dot(cfg: Dict) -> str`` — render the CFG as Graphviz DOT.
"""
from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple


_MAX_NODES_DEFAULT = 200

# Node kind taxonomy — small fixed set to keep visualisers consistent.
_KIND_ENTRY  = "entry"
_KIND_EXIT   = "exit"
_KIND_STMT   = "stmt"
_KIND_IF     = "if"
_KIND_LOOP   = "loop"
_KIND_RETURN = "return"
_KIND_CALL   = "call"
_KIND_RAISE  = "raise"
_KIND_TRY    = "try"


class _CFGBuilder(ast.NodeVisitor):
    """Walks a function body, emitting nodes and edges to a shared graph."""

    def __init__(self, fn_name: str, max_nodes: int):
        self.fn_name = fn_name
        self.max_nodes = max_nodes
        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Tuple[int, int]] = []
        self.truncated = False
        # Each visit_* returns (entry_id, exit_ids) — exit_ids is the set
        # of node ids that fall through to the next statement.
        self._entry_id = self._new(_KIND_ENTRY, line=0, text=f"entry::{fn_name}")
        self._exit_id  = self._new(_KIND_EXIT,  line=0, text=f"exit::{fn_name}")

    # ──────────────────────────────────────────────────────────────────────

    def _new(self, kind: str, *, line: int, text: str) -> int:
        if len(self.nodes) >= self.max_nodes:
            self.truncated = True
            return -1
        nid = len(self.nodes)
        self.nodes.append({
            "id":   nid,
            "kind": kind,
            "line": int(line),
            "text": (text or "")[:120],
        })
        return nid

    def _link(self, src: int, dst: int) -> None:
        if src < 0 or dst < 0:
            return
        self.edges.append((src, dst))

    def _link_many(self, srcs: List[int], dst: int) -> None:
        for s in srcs:
            self._link(s, dst)

    # ──────────────────────────────────────────────────────────────────────

    def build(self, body: List[ast.stmt]) -> None:
        last_exits = [self._entry_id]
        for stmt in body:
            entry, exits = self._visit_stmt(stmt)
            if entry < 0:
                break
            self._link_many(last_exits, entry)
            last_exits = exits
            if self.truncated:
                break
        self._link_many(last_exits, self._exit_id)

    def _visit_stmt(self, stmt: ast.stmt) -> Tuple[int, List[int]]:
        line = getattr(stmt, "lineno", 0)
        if isinstance(stmt, ast.If):
            test_id = self._new(_KIND_IF, line=line, text=ast.unparse(stmt.test)
                                if hasattr(ast, "unparse") else "if")
            if test_id < 0:
                return -1, []
            then_entry, then_exits = self._visit_block(stmt.body)
            else_entry, else_exits = self._visit_block(stmt.orelse) if stmt.orelse else (test_id, [test_id])
            if then_entry >= 0:
                self._link(test_id, then_entry)
            if stmt.orelse and else_entry >= 0:
                self._link(test_id, else_entry)
            elif not stmt.orelse:
                else_exits = [test_id]
            return test_id, list(set(then_exits + else_exits))

        if isinstance(stmt, (ast.For, ast.While, ast.AsyncFor)):
            kind_text = ("while " + (ast.unparse(stmt.test)
                                     if isinstance(stmt, ast.While) and hasattr(ast, "unparse")
                                     else "")) if isinstance(stmt, ast.While) else "for"
            loop_id = self._new(_KIND_LOOP, line=line, text=kind_text)
            if loop_id < 0:
                return -1, []
            body_entry, body_exits = self._visit_block(stmt.body)
            if body_entry >= 0:
                self._link(loop_id, body_entry)
            # back-edge: body exits feed back into the loop head
            self._link_many(body_exits, loop_id)
            return loop_id, [loop_id]

        if isinstance(stmt, ast.Return):
            nid = self._new(_KIND_RETURN, line=line, text="return")
            if nid < 0:
                return -1, []
            self._link(nid, self._exit_id)
            return nid, []

        if isinstance(stmt, ast.Raise):
            nid = self._new(_KIND_RAISE, line=line, text="raise")
            if nid < 0:
                return -1, []
            self._link(nid, self._exit_id)
            return nid, []

        if isinstance(stmt, ast.Try):
            nid = self._new(_KIND_TRY, line=line, text="try")
            if nid < 0:
                return -1, []
            body_entry, body_exits = self._visit_block(stmt.body)
            if body_entry >= 0:
                self._link(nid, body_entry)
            handler_exits: List[int] = []
            for h in stmt.handlers:
                h_entry, h_exits = self._visit_block(h.body)
                if h_entry >= 0:
                    self._link(nid, h_entry)
                handler_exits.extend(h_exits)
            final_entry, final_exits = (-1, [])
            if stmt.finalbody:
                final_entry, final_exits = self._visit_block(stmt.finalbody)
                if final_entry >= 0:
                    self._link_many(body_exits + handler_exits, final_entry)
                return nid, final_exits
            return nid, list(set(body_exits + handler_exits))

        # Generic statement — also detect call expressions in lhs/rhs.
        text = ""
        if hasattr(ast, "unparse"):
            try:
                text = ast.unparse(stmt).splitlines()[0]
            except Exception:
                text = type(stmt).__name__
        else:
            text = type(stmt).__name__
        kind = _KIND_CALL if _contains_call(stmt) else _KIND_STMT
        nid = self._new(kind, line=line, text=text)
        if nid < 0:
            return -1, []
        return nid, [nid]

    def _visit_block(self, body: List[ast.stmt]) -> Tuple[int, List[int]]:
        if not body:
            return -1, []
        first_entry, last_exits = -1, []
        for stmt in body:
            entry, exits = self._visit_stmt(stmt)
            if entry < 0:
                break
            if first_entry < 0:
                first_entry = entry
            self._link_many(last_exits, entry)
            last_exits = exits
        return first_entry, last_exits


def _contains_call(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            return True
    return False


# ─── Public API ──────────────────────────────────────────────────────────────

def build_cfg(source: str, *, max_nodes: int = _MAX_NODES_DEFAULT) -> Dict[str, Any]:
    """Parse *source* and return a JSON-serialisable CFG per function."""
    if not source or not source.strip():
        return {"status": "ERROR", "error": "empty source", "functions": []}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "status":   "ERROR",
            "error":    f"SyntaxError line {exc.lineno}: {exc.msg}",
            "functions": [],
        }

    functions: List[Dict[str, Any]] = []
    truncated = False
    nodes_budget = max(8, int(max_nodes))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            builder = _CFGBuilder(node.name, max_nodes=nodes_budget)
            builder.build(node.body)
            functions.append({
                "name":       node.name,
                "lineno":     node.lineno,
                "nodes":      builder.nodes,
                "edges":      [{"from": a, "to": b} for (a, b) in builder.edges],
                "n_nodes":    len(builder.nodes),
                "n_edges":    len(builder.edges),
                "truncated":  builder.truncated,
            })
            truncated = truncated or builder.truncated

    if not functions:
        # No functions — still produce a module-level pseudo-CFG.
        functions.append({
            "name":      "<module>",
            "lineno":    1,
            "nodes":     [
                {"id": 0, "kind": _KIND_ENTRY, "line": 0, "text": "entry::<module>"},
                {"id": 1, "kind": _KIND_EXIT,  "line": 0, "text": "exit::<module>"},
            ],
            "edges":     [{"from": 0, "to": 1}],
            "n_nodes":   2,
            "n_edges":   1,
            "truncated": False,
        })

    return {
        "status":     "TRUNCATED" if truncated else "OK",
        "n_functions": len(functions),
        "functions":  functions,
    }


def overlay_hotspots(
    cfg: Dict[str, Any],
    store: Any,
    module_id: str,
    *,
    findings: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Annotate each CFG node with severity (from SAST findings on its line)
    and aps_contribution (per-function APS delta share, when computable)."""
    if cfg.get("status") == "ERROR":
        return cfg
    # Severity map: line → max severity
    sev_by_line: Dict[int, str] = {}
    if findings is None:
        findings = _collect_findings_for_module(store, module_id)
    sev_rank = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
    for f in findings or []:
        line = int(f.get("line") or 0)
        sev  = (f.get("severity") or "INFO").upper()
        prev = sev_by_line.get(line)
        if prev is None or sev_rank.get(sev, 0) > sev_rank.get(prev, 0):
            sev_by_line[line] = sev

    # APS contribution: total APS delta proxy = SAST count per line (proxy
    # when store cannot deliver per-function APS).  We compute share
    # relative to the function's total finding count.
    out_funcs: List[Dict[str, Any]] = []
    for fn in cfg.get("functions", []):
        fn_lines = [n["line"] for n in fn["nodes"] if n.get("line", 0) > 0]
        fn_findings = [
            sev for line, sev in sev_by_line.items()
            if fn_lines and min(fn_lines) <= line <= max(fn_lines)
        ]
        total_findings = max(1, len(fn_findings))
        annotated_nodes = []
        for n in fn["nodes"]:
            line = int(n.get("line") or 0)
            sev  = sev_by_line.get(line)
            contrib = 0.0
            if sev and total_findings:
                contrib = round(1.0 / total_findings, 4)
            annotated_nodes.append({
                **n,
                "severity":         sev,
                "aps_contribution": contrib,
            })
        out_funcs.append({
            **fn,
            "nodes":           annotated_nodes,
            "n_hotspot_nodes": sum(1 for n in annotated_nodes if n["severity"]),
        })
    return {
        **cfg,
        "functions":           out_funcs,
        "overlay_module_id":   module_id,
        "overlay_findings":    len(findings or []),
    }


def _collect_findings_for_module(store: Any, module_id: str) -> List[Dict[str, Any]]:
    """Best-effort fetch of SAST findings persisted for the module."""
    if store is None:
        return []
    for method in ("get_anomalies", "get_diagnostic", "get_history"):
        fn = getattr(store, method, None)
        if not callable(fn):
            continue
        try:
            res = fn(module_id, window=1) if method == "get_history" else fn(module_id)
        except Exception:
            continue
        if not res:
            continue
        # Common shapes — return whatever looks like a list of dicts with line+severity
        if isinstance(res, list):
            return [r for r in res
                    if isinstance(r, dict) and "line" in r and "severity" in r]
    return []


def cfg_as_dot(cfg: Dict[str, Any]) -> str:
    """Render the CFG as Graphviz DOT — one subgraph per function."""
    if cfg.get("status") == "ERROR":
        return f"digraph cfg {{\n  /* {cfg.get('error','error')} */\n}}\n"
    lines = ["digraph cfg {", "  rankdir=TB;"]
    for fn in cfg.get("functions", []):
        safe_name = fn["name"].replace('"', "'")
        lines.append(f'  subgraph "cluster_{safe_name}" {{')
        lines.append(f'    label="{safe_name}";')
        for n in fn["nodes"]:
            label = f'{n["kind"]}@{n["line"]}: {n["text"]}'.replace('"', "'")
            lines.append(f'    "{safe_name}_{n["id"]}" [label="{label}"];')
        for e in fn["edges"]:
            lines.append(f'    "{safe_name}_{e["from"]}" -> "{safe_name}_{e["to"]}";')
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines) + "\n"
