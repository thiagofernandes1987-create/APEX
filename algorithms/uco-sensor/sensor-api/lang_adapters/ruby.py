"""
UCO-Sensor — Ruby Adapter  (M6.2)
===================================
Covers: Ruby (.rb, .rake, .gemspec, .ru, .rbw)

Ruby-specific calibration:
  • Blocks (do...end / {|x| ...}) are first-class — each adds CC
  • `unless`/`until` are inverted conditionals (+1 CC each)
  • `rescue`/`ensure` in exception handling (+1 CC)
  • `when` in case expressions (+1 CC)
  • `&&`/`||`/`and`/`or` boolean operators (+1 CC each)
  • `require`/`require_relative`/`load` = imports
  • `def`/`define_method`/`attr_accessor` = function proxies
  • `class`/`module` = type declarations
  • `loop do...end` without `break` = ILR
  • Comments: `#` only (no block comments natively; =begin/=end is docs)
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class RubyAdapter(GenericRegexAdapter):
    LANGUAGE   = "ruby"
    EXTENSIONS = (".rb", ".rake", ".gemspec", ".ru", ".rbw")

    # Ruby: # comments; =begin...=end for doc blocks
    LINE_COMMENT_RE  = re.compile(r'#[^\n]*',       re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'^=begin.*?^=end', re.DOTALL | re.MULTILINE)
    STRING_RE        = re.compile(
        r'""".*?"""|\'\'\'.*?\'\'\''
        r'|"(?:[^"\\#]|\\.|#\{[^}]*\})*"'  # double-quoted with interpolation
        r"|'(?:[^'\\]|\\.)*'",              # single-quoted
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elsif|unless|while|until|for|case|when|rescue|ensure'
        r'|and\b|or\b)\b'
        r'|&&|\|\|'
        r'|\.\s*(?:each|map|select|reject|detect|any\?|all\?|none\?)\s*(?:do|\{)',
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:require|require_relative|load|autoload)\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'^\s*def\s+(?:self\.)?[a-zA-Z_]\w*[!?]?',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'^\s*(?:class|module)\s+[A-Z]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bloop\s+do\b'
        r'|\bloop\s*\{'
        r'|\bwhile\s+true\b'
        r'|\buntil\s+false\b',
        re.MULTILINE,
    )

    BREAK_RE = re.compile(
        r'\b(?:break|return|raise|next|exit|abort)\b',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|raise|next|break|exit|abort|throw)\b',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '#'
