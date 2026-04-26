"""
UCO-Sensor — Swift Adapter  (M6.2)
====================================
Covers: Swift (.swift)

Swift-specific calibration:
  • `guard` is a CC increment — forces early exit pattern
  • `where` clause in generics/switch = +1 CC
  • `switch` with pattern-matching `case let`, `case .enum` = +1 each
  • `if let` / `guard let` / `while let` optional binding = +1 CC
  • `try?` / `try!` optional-try = not counted (no branch, result is Optional)
  • `??` nil-coalescing = +1 CC
  • Infinite loops: `while true {}`, `repeat {} while true`
  • `import` for modules
  • `func`, `init`, `subscript`, `deinit` for callables
  • `class`, `struct`, `enum`, `protocol`, `extension`, `actor` for types
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class SwiftAdapter(GenericRegexAdapter):
    LANGUAGE   = "swift"
    EXTENSIONS = (".swift",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'                 # multi-line string
        r'|"(?:[^"\\]|\\.)*"',      # regular string
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|guard|for|while|switch|case|catch|where)\b'
        r'|&&|\|\|'
        r'|\?\?'                     # nil-coalescing = branch
        r'|\bif\s+let\b'
        r'|\bguard\s+let\b'
        r'|\bwhile\s+let\b',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:(?:public|private|internal|fileprivate|open|static|class|final'
        r'|override|mutating|nonmutating|convenience|required|optional)\s+)*'
        r'(?:func|init|subscript|deinit)\s*(?:[a-zA-Z_]\w*)?\s*[<(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:public|private|internal|fileprivate|open|final)\s+)*'
        r'(?:class|struct|enum|protocol|extension|actor|typealias)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\s*\{'
        r'|\brepeat\s*\{[^}]*\}\s*while\s+true',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|fatalError|preconditionFailure'
        r'|assertionFailure)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
