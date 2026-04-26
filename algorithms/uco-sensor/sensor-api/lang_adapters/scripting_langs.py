"""
UCO-Sensor — Scripting Language Adapters  (M6.2)
==================================================
Covers: R (.r .R .Rmd), Shell/Bash (.sh .bash .zsh .ksh .fish),
        PowerShell (.ps1 .psm1 .psd1), Lua (.lua),
        Perl (.pl .pm .t .cgi), MATLAB (.m variant via .matlab extension)

These languages are widely used in data science, DevOps, and automation.
All share the characteristic that LOC and branch complexity are the dominant
quality signals — Halstead is less meaningful but still computable.
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


# ── R ─────────────────────────────────────────────────────────────────────────

class RAdapter(GenericRegexAdapter):
    """
    R statistical language adapter.

    R-specific notes:
      • `if`, `else if`, `for`, `while`, `repeat`, `tryCatch` condition
        parameter, `switch` = CC increments
      • `repeat {}` without `break` = ILR
      • `source()`, `library()`, `require()`, `import()` = imports
      • `function(` = callable declaration
      • S4: `setClass`, `setGeneric`, `setMethod`; R5/R6: `R6Class$new`
      • Comments: `#` only
    """
    LANGUAGE   = "r"
    EXTENSIONS = (".r", ".R", ".rmd", ".Rmd", ".rscript")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)  # R has no block comments
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r'|`[^`]*`',                 # backtick names
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|else\b|for|while|repeat|switch|tryCatch'
        r'|withCallingHandlers|vapply|sapply|lapply|Map)\b'
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:library|require|source|import|loadNamespace|requireNamespace)\s*\(',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'[a-zA-Z_]\w*\s*(?:<-|=)\s*function\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:setClass|setRefClass|R6Class|setGeneric|setMethod)\s*\(',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\brepeat\s*\{'
        r'|\bwhile\s*\(\s*TRUE\s*\)'
        r'|\bwhile\s*\(\s*T\s*\)',
        re.MULTILINE,
    )

    BREAK_RE = re.compile(
        r'\b(?:break|return|stop|next|quit)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|stop|break|next|quit)\s*\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── Shell / Bash ──────────────────────────────────────────────────────────────

class ShellAdapter(GenericRegexAdapter):
    """
    Shell/Bash adapter for .sh, .bash, .zsh, .ksh, .fish scripts.

    Shell-specific notes:
      • `if/elif/then/fi`, `case/esac` constructs
      • `[[`, `[`, `&&`, `||` within conditions
      • `while true; do`, `while :; do` = infinite loops
      • `source` and `.` commands = imports
      • `function name()` or `name()` for function declarations
      • No class concepts (n_classes always 0)
    """
    LANGUAGE   = "shell"
    EXTENSIONS = (".sh", ".bash", ".zsh", ".ksh", ".fish", ".command")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)  # no block comments
    STRING_RE        = re.compile(
        r'"(?:[^"\\$`]|\\.|\$[^{(]|\$\{[^}]*\}|\$\([^)]*\)|`[^`]*`)*"'
        r"|'[^']*'",                # single-quoted: no escapes
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elif|while|for|until|case|select)\b'
        r'|\[\[|\[(?!\[)'           # [[ and [ conditions
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:source|\.|bash\s+|sh\s+)\s+[^\s;]+',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:function\s+)?[a-zA-Z_]\w*\s*\(\s*\)\s*\{',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(r'(?!x)x', re.MULTILINE)   # shells have no classes

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+(?:true|:)\s*(?:;|do)\b'
        r'|\bwhile\s+\[\s+1\s+\]\s*(?:;|do)\b',
        re.MULTILINE,
    )

    BREAK_RE = re.compile(
        r'\b(?:break|return|exit|continue)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|exit|break|continue)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── PowerShell ────────────────────────────────────────────────────────────────

class PowerShellAdapter(GenericRegexAdapter):
    """
    PowerShell adapter for .ps1, .psm1, .psd1 files.

    PowerShell-specific notes:
      • Case-insensitive keywords: if/elseif/else, foreach, while, do, switch
      • `-and`, `-or`, `-not` boolean operators = CC increments
      • `Import-Module`, `using module`, `#requires` = imports
      • `function` keyword for callables
      • `class` keyword (PS 5.0+) for types
      • `while ($true)` = infinite loop
    """
    LANGUAGE   = "powershell"
    EXTENSIONS = (".ps1", ".psm1", ".psd1", ".pssc")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',        re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'<#.*?#>',        re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"$`]|`.|"\$[^{]|\$\{[^}]*\})*"'
        r"|'[^']*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|foreach|while|do|switch|catch|finally|for)\b'
        r'|-and\b|-or\b'
        r'|\?\s*\{',               # Where-Object shorthand
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:Import-Module|using\s+module|#requires\s+-Module)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*function\s+[a-zA-Z_]\w*(?:-\w+)*\s*(?:\{|\()',
        re.MULTILINE | re.IGNORECASE,
    )

    CLASS_RE = re.compile(
        r'^\s*class\s+[a-zA-Z_]\w*',
        re.MULTILINE | re.IGNORECASE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*\$true\s*\)'
        r'|\bwhile\s*\(\s*1\s*\)',
        re.MULTILINE | re.IGNORECASE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|exit)\b',
        re.MULTILINE | re.IGNORECASE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── Lua ───────────────────────────────────────────────────────────────────────

class LuaAdapter(GenericRegexAdapter):
    """
    Lua adapter for .lua files.

    Lua-specific notes:
      • `if/elseif/then/end`, `while/do/end`, `repeat/until`, `for/do/end`
      • `and`/`or` boolean operators = +1 CC
      • `require('mod')` = imports
      • `function name(` and `name = function(` patterns
      • No classes natively (metatables simulate OOP — counted via patterns)
      • `repeat...until` with `until true` = ILR (unusual but possible)
      • Comments: `--` (line), `--[[ ]]` (block)
    """
    LANGUAGE   = "lua"
    EXTENSIONS = (".lua",)

    LINE_COMMENT_RE  = re.compile(r'--(?!\[\[)[^\n]*',  re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'--\[\[.*?\]\]',     re.DOTALL)
    STRING_RE        = re.compile(
        r'\[\[.*?\]\]'              # long strings
        r'|"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|while|repeat|for)\b'
        r'|\band\b|\bor\b',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'\brequire\s*[\("\']\s*[^\s"\']+',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\bfunction\s+(?:[a-zA-Z_]\w*(?:\.|\:))*[a-zA-Z_]\w*\s*\('
        r'|[a-zA-Z_]\w*\s*=\s*function\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'[a-zA-Z_]\w*\s*=\s*\{\s*\}|setmetatable\s*\(',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\s+do\b'
        r'|\brepeat\b(?:(?!until).)*\buntil\s+false\b',
        re.MULTILINE | re.DOTALL,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|break|error)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '--'


# ── Perl ──────────────────────────────────────────────────────────────────────

class PerlAdapter(GenericRegexAdapter):
    """
    Perl adapter for .pl, .pm, .t, .cgi files.

    Perl-specific notes:
      • `if/elsif/unless`, `while/until`, `for/foreach`
      • `and`/`or` statement modifiers = +1 CC
      • `die`, `warn`, `exit` = terminal
      • `use`, `require`, `do` = imports
      • `sub name {` = function declaration
      • `package` = namespace (proxy for class)
      • `while (1)` / `while (true)` / `for (;;)` = ILR
      • Comments: `#` only; POD documentation skipped
    """
    LANGUAGE   = "perl"
    EXTENSIONS = (".pl", ".pm", ".t", ".cgi", ".plx")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',              re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'^=\w+.*?^=cut\s*$',   re.DOTALL | re.MULTILINE)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r'|qq\{[^}]*\}'
        r'|q\{[^}]*\}',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elsif|unless|while|until|for|foreach|when)\b'
        r'|\band\b|\bor\b'
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:use|require|do)\s+[a-zA-Z_]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*sub\s+[a-zA-Z_]\w*\s*(?:\{|\()',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*package\s+[a-zA-Z_]\w*(?:::\w+)*\s*;',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:1|true|TRUE)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|die|exit|last|next|redo)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── MATLAB ────────────────────────────────────────────────────────────────────

class MatlabAdapter(GenericRegexAdapter):
    """
    MATLAB / Octave adapter for .matlab and .m (Octave) files.

    Note: .m extension is shared with Objective-C. In the registry,
    .matlab maps here and .m maps to ObjectiveCAdapter by default.
    Override by passing file_extension='.matlab' explicitly.

    MATLAB-specific notes:
      • `if/elseif/end`, `for/end`, `while/end`, `switch/case/end`
      • `&&`, `||`, `&`, `|` boolean = +1 CC each
      • `function [out] = name(in)` declarations (may be end-terminated or not)
      • `classdef`, `properties`, `methods` for OOP
      • `import`, `addpath`, `run` = imports
      • Comments: `%` (line), `%{ %}` (block)
      • `while true`, `while 1` = ILR
    """
    LANGUAGE   = "matlab"
    EXTENSIONS = (".matlab", ".octave")

    LINE_COMMENT_RE  = re.compile(r'%[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'%\{.*?%\}',  re.DOTALL)
    STRING_RE        = re.compile(
        r"'[^'\n]*'"              # single-quoted (matrix transpose uses ' too — best effort)
        r'|"(?:[^"\\]|\\.)*"',   # double-quoted (Octave-style)
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|while|for|switch|case|catch|parfor)\b'
        r'|&&|\|\||&(?!&)|\|(?!\|)',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:import|addpath|run)\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*function\s+(?:\[[^\]]*\]\s*=\s*|[a-zA-Z_]\w*\s*=\s*)?[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*classdef\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+(?:true|1|TRUE)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|break|continue|error)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '%'
