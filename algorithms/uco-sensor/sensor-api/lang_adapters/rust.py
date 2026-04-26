"""
UCO-Sensor — Rust Adapter  (M6.2)
===================================
Covers: Rust (.rs)

Rust-specific calibration:
  • `match` arms (=>) each increment CC — Rust match is exhaustive,
    so many arms indicate real branching complexity
  • `loop {}` without `break` = infinite loop risk (ILR)
  • `while let` and `if let` are decision points (+1 CC each)
  • `?` operator (propagate error) counts as a branch point
  • `unsafe {}` blocks are flagged via ILR (elevated risk)
  • `use` for imports; `mod` for module declarations
  • `fn`, `async fn`, `pub fn`, `const fn`, `unsafe fn` for functions
  • `struct`, `enum`, `trait`, `impl`, `type` for types
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class RustAdapter(GenericRegexAdapter):
    LANGUAGE   = "rust"
    EXTENSIONS = (".rs",)

    LINE_COMMENT_RE  = re.compile(r'//[^\n]*',   re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',  re.DOTALL)

    # Rust raw strings r#"..."# need special handling
    STRING_RE = re.compile(
        r'r#+"[^"]*"+#+'           # raw strings r#"..."#, r##"..."##, ...
        r'|b?"(?:[^"\\]|\\.)*"'   # byte and normal strings
        r"|b?'(?:[^'\\]|\\.)*'",  # byte and char literals
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|else\s+if|if\s+let|while|while\s+let|for|match|loop'
        r'|break|continue)\b'
        r'|&&|\|\|'
        r'|\?(?!\s*[>])'          # ? error propagation (not ?>)
        r'|=>\s*(?!\s*\{)',       # match arms that aren't block arms
        re.MULTILINE,
    )

    # `use` and `extern crate`
    IMPORT_RE = re.compile(
        r'^\s*(?:use\s+|extern\s+crate\s+)',
        re.MULTILINE,
    )

    # Rust functions: fn, pub fn, async fn, pub async fn, const fn, unsafe fn
    FUNCTION_RE = re.compile(
        r'\b(?:pub\s+)?(?:async\s+)?(?:const\s+)?(?:unsafe\s+)?fn\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    # Rust types: struct, enum, trait, impl, type alias, union
    CLASS_RE = re.compile(
        r'\b(?:struct|enum|trait|impl(?:\s+\w+\s+for)?|type|union)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    # `loop {}` without break = true infinite; `while true {}` = infinite
    INFINITE_LOOP_RE = re.compile(
        r'\bloop\s*\{'
        r'|\bwhile\s+true\s*\{'
        r'|\bwhile\s*\(\s*true\s*\)\s*\{',
        re.MULTILINE,
    )

    BREAK_RE = re.compile(
        r'\b(?:break|return|panic!|process::exit|std::process::exit)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|panic!|todo!|unimplemented!|break|continue)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
