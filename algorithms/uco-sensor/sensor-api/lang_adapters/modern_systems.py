"""
UCO-Sensor — Modern Systems Language Adapters  (M6.2)
======================================================
Covers: Dart (.dart), Julia (.jl), Zig (.zig),
        Nim (.nim .nims), Crystal (.cr), D (.d .di)

These are post-2010 systems languages with modern type systems,
first-class async, and strong safety guarantees. UCO metrics
calibrated for their specific idioms.
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


# ── Dart ──────────────────────────────────────────────────────────────────────

class DartAdapter(GenericRegexAdapter):
    """
    Dart adapter for .dart files.

    Dart-specific calibration:
      • `if/else if`, `for`, `for-in`, `while`, `do-while`, `switch/case`
      • `catch`, `on`, `rethrow` in exception handling
      • `??` null-aware coalescing = +1 CC
      • `?.` null-aware method call = +1 CC
      • `async*` / `yield*` = stream patterns (elevated complexity)
      • `import`, `export`, `part` = dependency management
      • `void`/typed `Function`, `get`, `set` = callables
      • `class`, `mixin`, `extension`, `enum`, `typedef` = types
      • `while (true)` / `for (;;)` = ILR
    """
    LANGUAGE   = "dart"
    EXTENSIONS = (".dart",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)
    STRING_RE        = re.compile(
        r"'''.*?'''"
        r'|""".*?"""'
        r"|'(?:[^'\\]|\\.)*'"
        r'|"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|while|do|switch|case|catch|on|finally)\b'
        r'|&&|\|\|'
        r'|\?\?(?!=)'             # null-coalescing
        r'|\?\.',                 # null-aware access
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:import|export|part\s+of|part)\s+[\'"]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:void|int|double|bool|String|dynamic|Future|Stream|List|Map'
        r'|Set|Iterable|Object|Never|[A-Z]\w*)\s+'
        r'(?:get\s+|set\s+|async\s+|sync\s*\*\s*|async\s*\*\s*)?'
        r'[a-zA-Z_]\w*\s*[<(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:abstract|final|sealed|base|interface|mixin)\s+)*'
        r'(?:class|mixin|extension|enum|typedef)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|rethrow)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


# ── Julia ─────────────────────────────────────────────────────────────────────

class JuliaAdapter(GenericRegexAdapter):
    """
    Julia adapter for .jl files.

    Julia-specific calibration:
      • `if/elseif/else/end`, `for/end`, `while/end`, `try/catch/finally/end`
      • `begin/end`, `let/end` blocks for scope
      • Short-circuit: `&&`, `||`, ternary `? :`
      • `using`, `import`, `include` = imports
      • `function name(...) ... end` and `name(args) = expr` = callables
      • `struct`, `mutable struct`, `abstract type`, `primitive type` = types
      • `while true` = ILR; `Threads.@spawn` loops = elevated ILR
      • Comments: `#` (line), `#= =#` (block)
    """
    LANGUAGE   = "julia"
    EXTENSIONS = (".jl",)

    LINE_COMMENT_RE  = re.compile(r'#(?!=)[^\n]*',  re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'#=.*?=#',        re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'
        r'|"(?:[^"\\$]|\\.|\$[^(]|\$\([^)]*\))*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|for|while|try|catch|finally)\b'
        r'|&&|\|\|'
        r'|\?(?!\s*\))',           # ternary
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:using|import|include)\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:function\s+[a-zA-Z_!]\w*|[a-zA-Z_!]\w*\s*\([^)]*\)\s*=)',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:struct|mutable\s+struct|abstract\s+type|primitive\s+type|module)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|error|rethrow|break|continue|exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── Zig ───────────────────────────────────────────────────────────────────────

class ZigAdapter(GenericRegexAdapter):
    """
    Zig adapter for .zig files.

    Zig-specific calibration:
      • `if`, `else`, `while`, `for`, `switch` with prong `=>` = CC
      • `comptime` blocks = elevated complexity (meta-programming)
      • `orelse` = null-handling branch = +1 CC
      • `catch` on error union = +1 CC
      • `try` (short-circuit error return) = +1 CC approximation
      • `@import("...")` = imports
      • `fn`, `pub fn`, `comptime fn` = functions
      • `struct`, `union`, `enum`, `opaque`, `interface` = types
      • `while (true)` = ILR; `while (cond) |val|` = guarded loop
      • Comments: `//` only (no block comments)
    """
    LANGUAGE   = "zig"
    EXTENSIONS = (".zig",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)  # no block comments
    STRING_RE        = re.compile(
        r'\\\\[^\n]*'           # multiline string \\
        r'|"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else|while|for|switch|comptime|orelse|catch|try)\b'
        r'|and\b|or\b',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'@import\s*\(',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:pub\s+)?(?:extern\s+)?(?:inline\s+)?fn\s+[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\bconst\s+[A-Z]\w*\s*=\s*(?:struct|union|enum|opaque)\s*\{',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|break|continue|@panic|unreachable)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


# ── Nim ───────────────────────────────────────────────────────────────────────

class NimAdapter(GenericRegexAdapter):
    """
    Nim adapter for .nim, .nims files.

    Nim-specific calibration:
      • `if/elif/else`, `case/of/else`, `for`, `while`
      • `and`, `or`, `not` = +1 CC
      • `try/except/finally`, `raise`
      • `import`, `include`, `from X import` = imports
      • `proc`, `func`, `method`, `iterator`, `macro`, `template` = callables
      • `type` blocks with `object`, `ref object`, `enum`, `distinct` = types
      • `while true` = ILR
      • Comments: `#` (line), `#[...]#` (block)
    """
    LANGUAGE   = "nim"
    EXTENSIONS = (".nim", ".nims")

    LINE_COMMENT_RE  = re.compile(r'#(?!\[)[^\n]*',  re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'#\[.*?\]#',       re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'
        r'|"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elif|else|case|of|for|while|try|except|finally)\b'
        r'|\band\b|\bor\b|\bnot\b',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:import|include|from\s+\S+\s+import)\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:proc|func|method|iterator|macro|template|converter)\s+[a-zA-Z_]\w*[*]?\s*[<(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*type\b'               # type block (may span multiple lines)
        r'|[A-Z]\w*\s*=\s*(?:object|ref\s+object|enum|distinct|tuple)',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|raise|break|continue|quit|system\.quit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── Crystal ───────────────────────────────────────────────────────────────────

class CrystalAdapter(GenericRegexAdapter):
    """
    Crystal adapter for .cr files.

    Crystal is heavily inspired by Ruby; shares most patterns with RubyAdapter
    but adds:
      • Static typing with `Union` types and `Nil`-safety
      • `select` on channels (concurrency) = CC
      • `unless`, `until`, `rescue`, `ensure`
      • `require` = imports
      • `def`, `private def`, `abstract def` = functions
      • `class`, `struct`, `module`, `lib`, `enum`, `annotation` = types
      • `loop` without `break` = ILR
    """
    LANGUAGE   = "crystal"
    EXTENSIONS = (".cr",)

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)
    STRING_RE        = re.compile(
        r'"(?:[^"\\#]|\\.|#[^{]|#\{[^}]*\})*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elsif|unless|while|until|for|case|when|rescue|ensure|select)\b'
        r'|\band\b|\bor\b'
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*require\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:(?:private|protected|abstract|class)\s+)?def\s+(?:self\.)?[a-zA-Z_]\w*[!?]?\s*[<(]',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:abstract\s+)?(?:class|struct|module|lib|enum|annotation)\s+[A-Z]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bloop\s+do\b|\bloop\s*\{'
        r'|\bwhile\s+true\b|\buntil\s+false\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|raise|next|break|exit|abort)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── D ─────────────────────────────────────────────────────────────────────────

class DAdapter(GenericRegexAdapter):
    """
    D language adapter for .d, .di files.

    D-specific calibration:
      • `if/else`, `for`, `foreach`, `while`, `do`, `switch/case`
      • `try/catch/finally`, `scope(exit/failure/success)` = +1 CC
      • `&&`, `||`, ternary `?:` = +1 CC
      • `import` = dependency
      • Functions: typed declarations like C/C++; also `auto` return
      • `class`, `struct`, `interface`, `union`, `enum`, `template` = types
      • `while (true)` / `for (;;)` = ILR
      • `unittest` blocks = test code
      • Comments: `//` (line), `/* */` (block), `/+ +/` (nestable block)
    """
    LANGUAGE   = "d"
    EXTENSIONS = (".d", ".di")

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',         re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/|/\+.*?\+/', re.DOTALL)
    STRING_RE        = re.compile(
        r'`[^`]*`'              # wysiwyg strings
        r'|"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|for|foreach|foreach_reverse|while|do|switch|case'
        r'|catch|finally|scope)\b'
        r'|&&|\|\||\?(?!\?)',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:void|int|long|float|double|bool|char|string|auto|size_t'
        r'|[A-Z]\w*)\s+[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:class|struct|interface|union|enum|template|mixin\s+template)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*true\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|goto|exit|abort)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
