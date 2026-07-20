#!/usr/bin/env python3
"""
_ast_helpers.py — shared AST-scan primitives for the security gates.

WHY THIS EXISTS:
  `skill_scout.ast_security_scan` and `guards.forge_load_gate` both need the same
  low-level checks (dangerous `open()` modes, deserializer RCE sinks). Before v1.60.1
  each carried its OWN copy of `_write_open_mode` (C-07 in the correction inventory) —
  so a fix to one drifted from the other, and the SAME blind spots lived in two places
  (C-04: numpy.load(allow_pickle=True), pandas.read_pickle, open() with a NON-literal
  mode all passed as safe). Centralising the primitives fixes both gates at once.

WHEN TO USE:
  From any static gate that walks a `ast` tree of untrusted code before staging/exec.

WHAT IF IT FAILS:
  Pure stdlib (`ast`), no I/O, no network — cannot fail at runtime beyond a caller
  passing a non-node, which is a programming error surfaced immediately.
"""
import ast

# Methods that deserialize attacker-controlled bytes into live objects => RCE, even when
# the receiving module is on the import whitelist (numpy/pandas). C-04.
_RCE_DESERIALIZER_METHODS = {"read_pickle"}   # pandas.read_pickle(...)


def open_mode_risk(n):
    """Classify a builtin open()/Path.open() call by its mode argument.

    Returns:
      "write"   -> a LITERAL mode string containing w/a/x/+ (proven filesystem write)
      "unknown" -> a mode argument is present but is NOT a literal string, so we cannot
                   prove it is read-only (C-04: `m="w"; open(p, m)` bypassed the old check)
      None      -> no mode arg (open(path) == read) or not an open() call at all
    """
    if not (isinstance(n, ast.Call) and (
            (isinstance(n.func, ast.Name) and n.func.id == "open")
            or (isinstance(n.func, ast.Attribute) and n.func.attr == "open"))):
        return None
    mode_node = None
    if len(n.args) >= 2:
        mode_node = n.args[1]
    for kw in n.keywords:
        if kw.arg == "mode":
            mode_node = kw.value
    if mode_node is None:
        return None                                   # open(path) -> read, safe
    if isinstance(mode_node, ast.Constant) and isinstance(mode_node.value, str):
        return "write" if any(c in mode_node.value for c in ("w", "a", "x", "+")) else None
    return "unknown"                                  # non-literal mode: cannot prove read-only


def deserializer_rce_reason(n):
    """Return a reason string if this call is a deserializer RCE sink on a whitelisted lib
    (pandas.read_pickle, numpy.load(allow_pickle=True)), else None. C-04."""
    if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)):
        return None
    attr = n.func.attr
    if attr in _RCE_DESERIALIZER_METHODS:
        return f"deserializer .{attr}() (line {n.lineno})"
    if attr == "load":                                # numpy.load with pickle enabled
        for kw in n.keywords:
            if kw.arg == "allow_pickle" and not (
                    isinstance(kw.value, ast.Constant) and kw.value.value is False):
                return f".load(allow_pickle=...) pickle RCE (line {n.lineno})"
    return None
