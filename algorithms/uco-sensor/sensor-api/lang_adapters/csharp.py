"""
UCO-Sensor — C# Adapter  (M6.2)
=================================
Covers: C# (.cs)

Differentiators vs C:
  • foreach, when, yield return, async/await, LINQ
  • using directives (imports)
  • record, interface, abstract class, sealed class
  • switch expressions with => arms (each arm = +1 CC)
  • pattern matching: is T { prop: val } → +1 CC
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class CSharpAdapter(GenericRegexAdapter):
    LANGUAGE   = "csharp"
    EXTENSIONS = (".cs",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|foreach|while|do|switch|case|catch|when'
        r'|goto|continue)\b'
        r'|&&|\|\||\?\s*(?![:\s]*\))'   # ternary but not null-conditional
        r'|\?\?(?!=)',                  # null-coalescing branch
        re.MULTILINE,
    )

    # C# uses `using` (both directive and statement) + `global using`
    IMPORT_RE = re.compile(
        r'^\s*(?:global\s+)?using\s+(?:static\s+)?[a-zA-Z_]',
        re.MULTILINE,
    )

    # C#: all access-modifier combinations before return type + method name
    FUNCTION_RE = re.compile(
        r'\b(?:public|private|protected|internal|static|async|override'
        r'|virtual|abstract|sealed|extern|partial|new)\s+'
        r'(?:(?:public|private|protected|internal|static|async|override'
        r'|virtual|abstract|sealed|extern|partial|new)\s+)*'
        r'(?:void|int|long|float|double|bool|string|char|decimal|object'
        r'|var|Task|IEnumerable|List|IActionResult|[A-Z]\w*(?:<[^>]+>)?)\s+'
        r'[a-zA-Z_]\w*\s*[(<]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:public|private|protected|internal|static|abstract|sealed'
        r'|partial)\s+)*(?:class|struct|interface|enum|record)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:true|1|True)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|goto)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
