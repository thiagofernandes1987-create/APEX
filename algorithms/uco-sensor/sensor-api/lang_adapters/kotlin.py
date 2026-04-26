"""
UCO-Sensor — Kotlin Adapter  (M6.2)
=====================================
Covers: Kotlin (.kt, .kts)

Kotlin-specific calibration:
  • `when` expressions (exhaustive switch) — each arm is +1 CC
  • `?.` safe-call operator = +1 CC (optional access = branch)
  • `?:` Elvis operator = +1 CC (fallback = branch)
  • Lambda/function literals `{ params -> body }` = +1 per unique call
  • Coroutines: `suspend fun` — not a CC increment but noted
  • `for`, `while`, `do..while`, `if`, `else if`, `catch`
  • `import` for modules; `package` for namespacing
  • `fun`, `suspend fun`, `inline fun`, `tailrec fun` for callables
  • `class`, `data class`, `sealed class`, `object`, `interface`, `enum class`
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class KotlinAdapter(GenericRegexAdapter):
    LANGUAGE   = "kotlin"
    EXTENSIONS = (".kt", ".kts")

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'               # multiline
        r'|"(?:[^"\\$]|\\.|\$[^{]|\$\{[^}]*\})*"',  # with string templates
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|when|catch|finally)\b'
        r'|&&|\|\|'
        r'|\?\.'                    # safe-call
        r'|\?:',                    # elvis
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:(?:public|private|protected|internal|open|final|override'
        r'|abstract|suspend|inline|tailrec|operator|infix|external)\s+)*'
        r'fun\s+(?:<[^>]+>\s+)?(?:[a-zA-Z_]\w*\.)?[a-zA-Z_]\w*\s*[<(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:public|private|protected|internal|open|final|abstract|sealed'
        r'|data|inner|value|annotation|enum)\s+)*'
        r'(?:class|object|interface|companion\s+object)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)'
        r'|\bdo\s*\{[^}]*\}\s*while\s*\(\s*true\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|error|TODO)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
