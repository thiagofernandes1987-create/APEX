"""
UCO-Sensor — Scala & Groovy Adapters  (M6.2)
=============================================
Covers: Scala (.scala, .sc, .sbt), Groovy (.groovy, .gradle, .gvy)

Scala-specific:
  • `match { case ... }` — each case arm is +1 CC
  • `for { ... } yield` (for-comprehension) = +1 CC
  • `if`, `else if`, `while`, `do`, `try/catch`
  • `=>` lambda/case arm  — pattern-matching arms
  • `import` for modules
  • `def`, `val/var` methods, `override def` for callables
  • `class`, `case class`, `sealed class`, `abstract class`,
    `object`, `trait`, `type` for types

Groovy-specific:
  • Inherits most patterns from Scala/Java but uses `def` for everything
  • Closures `{ -> ... }` are idiomatic (counted via lambda pattern)
  • `import` statements
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class ScalaAdapter(GenericRegexAdapter):
    LANGUAGE   = "scala"
    EXTENSIONS = (".scala", ".sc", ".sbt")

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'               # triple-quoted
        r'|"(?:[^"\\]|\\.)*"'     # regular string
        r'|s"(?:[^"\\]|\\.)*"'    # string interpolation s"..."
        r'|f"(?:[^"\\]|\\.)*"',   # f-string
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|while|do|for|match|case|catch|finally)\b'
        r'|&&|\|\|'
        r'|\?\.',                  # optional-chaining proxy
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:(?:override|abstract|final|sealed|private|protected|public'
        r'|implicit|lazy|inline|transparent)\s+)*'
        r'def\s+[a-zA-Z_]\w*\s*(?:\[[^\]]*\])?\s*[:(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:abstract|sealed|final|case|open)\s+)*'
        r'(?:class|object|trait|enum|type)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|sys\.exit|System\.exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


class GroovyAdapter(GenericRegexAdapter):
    LANGUAGE   = "groovy"
    EXTENSIONS = (".groovy", ".gradle", ".gvy", ".gy")

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'
        r"|'''.*?'''"
        r'|"(?:[^"\\$]|\\.|\$[^{]|\$\{[^}]*\})*"'  # GString
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|switch|case|catch|finally'
        r'|each|collect|find|findAll|any|every)\b'
        r'|&&|\|\||\?:'            # Elvis operator
        r'|\?\.',                  # Safe navigation
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:def|void|int|String|boolean|static)\s+[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:class|interface|trait|enum|@interface)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:true|1|TRUE)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|System\.exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
