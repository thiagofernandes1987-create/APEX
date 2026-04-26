"""
UCO-Sensor — Functional Language Adapters  (M6.2)
===================================================
Covers: Haskell (.hs .lhs), Erlang (.erl .hrl),
        Elixir (.ex .exs), F# (.fs .fsx .fsi),
        OCaml (.ml .mli), Clojure (.clj .cljs .cljc .edn)

Functional languages require calibration adjustments:
  • Pattern matching is the dominant branching construct
  • Guards (|, when) replace if/else in many patterns
  • Immutability reduces state complexity — CC weight adjusted
  • Recursion is the loop primitive — detected via self-calls
  • Modules/namespaces replace classes as structural units
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


# ── Haskell ───────────────────────────────────────────────────────────────────

class HaskellAdapter(GenericRegexAdapter):
    """
    Haskell adapter for .hs, .lhs files.

    Haskell-specific calibration:
      • Guards (`|`) in function definitions = +1 CC each
      • `case ... of` with N alternatives = +(N-1) CC
      • `where`, `let ... in` = structural, not CC
      • `if/then/else` = +1 CC (infrequent in idiomatic Haskell)
      • `import` = dependency
      • Top-level bindings `name :: type\nname args = body` = functions
      • `data`, `newtype`, `type`, `class`, `instance` = types
      • `Data.IORef` / recursion loops — ILR detection approximated
      • Comments: `--` (line), `{- -}` (block)
    """
    LANGUAGE   = "haskell"
    EXTENSIONS = (".hs", ".lhs")

    LINE_COMMENT_RE  = re.compile(r'--[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'\{-.*?-\}',   re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'",
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\|(?!\|)(?!\s*\])'       # guards in pattern match / list comp (not ||)
        r'|\bif\b'
        r'|\bcase\b'
        r'|\bguard\b'
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*import\s+(?:qualified\s+)?[A-Z]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^[a-z_]\w*\s+::\s*',       # type signature  (proxy for declaration)
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:data|newtype|type|class|instance)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bforever\b'                # Control.Monad.forever
        r'|\bfix\b',                  # Data.Function.fix recursion combinator
        re.MULTILINE,
    )

    BREAK_RE = re.compile(
        r'\b(?:return|error|undefined|throwIO|exitWith|exitSuccess|exitFailure)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|error|undefined|throwIO|exitSuccess|exitFailure)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '--'


# ── Erlang ────────────────────────────────────────────────────────────────────

class ErlangAdapter(GenericRegexAdapter):
    """
    Erlang adapter for .erl, .hrl files.

    Erlang-specific calibration:
      • `case ... of ... end` — each clause `Pattern ->` = +1 CC
      • `if` guards (`when`) = +1 CC each
      • `receive ... end` — each message clause = +1 CC
      • `andalso`, `orelse` = +1 CC each
      • `receive` without `after 0` = potential ILR (mailbox block)
      • `-import`, `-include` = imports
      • `Function(Args) ->` = function declarations
      • `-record`, `-type`, `-module` = structural declarations
      • Comments: `%` only; no block comments
    """
    LANGUAGE   = "erlang"
    EXTENSIONS = (".erl", ".hrl")

    LINE_COMMENT_RE  = re.compile(r'%[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)  # no block comments
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|case|receive|when|catch)\b'
        r'|\bandAlso\b|\borElse\b'
        r'|\bAndalso\b|\bOrelse\b'   # alternate capitalizations
        r'|->(?!\s*\})',             # clause arrows
        re.MULTILINE | re.IGNORECASE,
    )

    IMPORT_RE = re.compile(
        r'^-(?:import|include|include_lib)\s*\(',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^[a-z_]\w*\s*\([^)]*\)\s*(?:when\s+[^->]+)?->',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^-(?:record|module|type|opaque)\s*\(',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\breceive\b(?:(?!after|end).)*\bend\b',
        re.MULTILINE | re.DOTALL,
    )

    BREAK_RE = re.compile(
        r'\b(?:exit|erlang:exit|throw|halt)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:exit|throw|halt|erlang:exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '%'


# ── Elixir ────────────────────────────────────────────────────────────────────

class ElixirAdapter(GenericRegexAdapter):
    """
    Elixir adapter for .ex, .exs files.

    Elixir-specific calibration:
      • `case`, `cond`, `with`, `receive` = pattern-matching branches
      • `->` in case/cond clauses = +1 CC each
      • `if`, `unless`, `when` = +1 CC each
      • `and`, `or`, `&&`, `||` = +1 CC each
      • `for` comprehension = +1 CC
      • `receive` without timeout = potential ILR
      • `import`, `require`, `use`, `alias` = imports
      • `def`, `defp`, `defmacro`, `defmacrop` = functions
      • `defmodule`, `defprotocol`, `defimpl`, `defstruct` = types
      • Comments: `#` only
    """
    LANGUAGE   = "elixir"
    EXTENSIONS = (".ex", ".exs")

    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'(?!x)x',     re.MULTILINE)  # no block comments
    STRING_RE        = re.compile(
        r'~[a-zA-Z]\(.*?\)(?:[a-zA-Z]*)'      # sigils ~r/.../, ~s"..."
        r'|""".*?"""'
        r"|'''.*?'''"
        r'|"(?:[^"\\#]|\\.|\#[^{]|\#\{[^}]*\})*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|unless|cond|case|for|with|receive|when)\b'
        r'|\band\b|\bor\b|\bnot\b'
        r'|&&|\|\|'
        r'|->(?!\s*end)',          # clause arrows
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:import|require|use|alias)\s+[A-Z]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*def(?:p|macro|macrop)?\s+[a-z_]\w*[!?]?\s*(?:\([^)]*\))?\s*(?:do|when)',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*defmodule\s+[A-Z]\w*'
        r'|^\s*defprotocol\s+[A-Z]\w*'
        r'|^\s*defimpl\s+[A-Z]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\breceive\b(?:(?!after|end).)*\bend\b',
        re.MULTILINE | re.DOTALL,
    )

    BREAK_RE = re.compile(
        r'\b(?:raise|exit|throw|halt|Process\.exit)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:raise|exit|throw|halt|reraise)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'


# ── F# ────────────────────────────────────────────────────────────────────────

class FSharpAdapter(GenericRegexAdapter):
    """
    F# adapter for .fs, .fsx, .fsi files.

    F#-specific calibration:
      • `match ... with | Pattern ->` — each `|` arm = +1 CC
      • `if/elif/else`, `while/do`, `for ... in ... do`
      • `|>` pipe operator: not a branch but signals complexity
      • `open` = import
      • `let`, `let rec`, `member`, `override` = functions
      • `type`, `module`, `namespace` = types/structural
      • `while true do` = ILR
      • Comments: `//` (line), `(* *)` (block)
    """
    LANGUAGE   = "fsharp"
    EXTENSIONS = (".fs", ".fsx", ".fsi")

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',      re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'\(\*.*?\*\)',   re.DOTALL)
    STRING_RE        = re.compile(
        r'""".*?"""'
        r'|"(?:[^"\\]|\\.)*"'
        r'|@"[^"]*"',          # verbatim strings
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elif|while|for|match|when|try|with|catch)\b'
        r'|\|(?!\|)(?!\s*>)'   # pattern arms (not || or |>)
        r'|&&|\|\|',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*open\s+[A-Z]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:let|let\s+rec|member|override|abstract\s+member)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*type\s+[a-zA-Z_]\w*'
        r'|^\s*module\s+[a-zA-Z_]\w*'
        r'|^\s*namespace\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\s+do\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|raise|failwith|failwithf|invalidOp|reraise|exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'


# ── OCaml ─────────────────────────────────────────────────────────────────────

class OCamlAdapter(GenericRegexAdapter):
    """
    OCaml adapter for .ml, .mli files.

    OCaml-specific calibration:
      • `match ... with | Pattern ->` — each `|` arm = +1 CC
      • `if/then/else`, `while/do/done`, `for/to/do/done`
      • `fun _ -> | ...` anonymous function pattern matching
      • `try ... with | Pattern ->` = CC
      • `open` = imports
      • `let`, `let rec`, `val` = functions
      • `type`, `module`, `sig`, `struct`, `class` = types
      • Comments: `(* *)` only (can nest)
    """
    LANGUAGE   = "ocaml"
    EXTENSIONS = (".ml", ".mli")

    LINE_COMMENT_RE  = re.compile(r'(?!x)x',      re.MULTILINE)  # no line comments
    BLOCK_COMMENT_RE = re.compile(r'\(\*.*?\*\)', re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|then|else|while|for|match|when|try|with|function)\b'
        r'|\|(?!\|)(?!>)',         # pattern arms
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*open\s+[A-Z]',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*(?:let\s+(?:rec\s+)?|val\s+)[a-z_]\w*\s',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:type|module|class|sig)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s+true\s+do\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:raise|failwith|invalid_arg|exit|assert\s+false)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '(*'


# ── Clojure ───────────────────────────────────────────────────────────────────

class ClojureAdapter(GenericRegexAdapter):
    """
    Clojure adapter for .clj, .cljs, .cljc, .edn files.

    Clojure-specific calibration:
      • `(if ...)`, `(when ...)`, `(cond ...)`, `(case ...)` = branches
      • `(doseq ...)`, `(dotimes ...)`, `(loop ...)` = loop constructs
      • `(recur ...)` = tail-call recursion (counted in loop detection)
      • `(require ...)`, `(use ...)`, `(:require ...)` = imports
      • `(defn ...)`, `(defn- ...)`, `(fn ...)` = functions
      • `(defrecord ...)`, `(defprotocol ...)`, `(deftype ...)` = types
      • `(loop [...] ... (recur ...))` = definite loop, ILR only if no exit
      • Comments: `;` (line), `#_` (datum comment)
    """
    LANGUAGE   = "clojure"
    EXTENSIONS = (".clj", ".cljs", ".cljc", ".edn")

    LINE_COMMENT_RE  = re.compile(r';[^\n]*',    re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'#_\S+',      re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"',
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\((?:if|when|when-not|cond|case|condp|and|or|while|doseq|dotimes'
        r'|for|loop|try|catch|finally)\b',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'\(:require\b|\(:use\b|\(require\b|\(use\b|\(import\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\(defn-?\s+[a-zA-Z_\-!?\*<>+=/]\w*',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\((?:defrecord|defprotocol|deftype|defmulti|ns)\s+[a-zA-Z_\-]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\(loop\s+\[[^\]]*\](?:(?!\(recur).)*\)',
        re.MULTILINE | re.DOTALL,
    )

    BREAK_RE = re.compile(
        r'\b(?:recur|throw|System/exit)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*\((?:throw|System/exit)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return ';'
