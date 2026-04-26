"""
UCO-Sensor — PHP Adapter  (M6.2)
==================================
Covers: PHP (.php, .phtml, .php3, .php4, .php5, .phps, .phar)

PHP-specific calibration:
  • `match` expression (PHP 8.0) — exhaustive, each arm is +1 CC
  • `??` null-coalescing = +1 CC (branch)
  • `elseif` (one word) and `else if` both count
  • `foreach`, `do..while`, `switch/case`
  • `include`, `require`, `include_once`, `require_once`, `use` = imports
  • `function`, `fn` (arrow), `__construct` for callables
  • `class`, `abstract class`, `final class`, `interface`, `trait`, `enum`
  • Infinite: `while(true)`, `while(1)`, `for(;;)`
  • PHP has multiple comment styles: //, #, /* */
"""
from __future__ import annotations
import re
from .generic import GenericRegexAdapter


class PhpAdapter(GenericRegexAdapter):
    LANGUAGE   = "php"
    EXTENSIONS = (".php", ".phtml", ".php3", ".php4", ".php5", ".phps", ".phar")

    # PHP: //, # and /* */
    LINE_COMMENT_RE  = re.compile(r'(?://|#)[^\n]*',  re.MULTILINE)
    BLOCK_COMMENT_RE = re.compile(r'/\*.*?\*/',        re.DOTALL)
    STRING_RE        = re.compile(
        r'"(?:[^"\\]|\\.)*"'
        r"|'(?:[^'\\]|\\.)*'"
        r'|<<<["\']?(\w+)["\']?\s*\n.*?\n\1;',   # heredoc / nowdoc
        re.DOTALL,
    )

    CC_RE = re.compile(
        r'\b(?:if|elseif|else\s+if|for|foreach|while|do|switch|case|catch'
        r'|match|finally)\b'
        r'|&&|\|\||\?\?(?!=)'
        r'|\?(?!\?)[^:\s]',    # ternary ?
        re.MULTILINE,
    )

    IMPORT_RE = re.compile(
        r'^\s*(?:require|require_once|include|include_once|use)\b',
        re.MULTILINE,
    )

    FUNCTION_RE = re.compile(
        r'\b(?:(?:public|protected|private|static|abstract|final|async'
        r'|readonly)\s+)*function\s+[a-zA-Z_]\w*\s*\(',
        re.MULTILINE,
    )

    CLASS_RE = re.compile(
        r'\b(?:(?:abstract|final|readonly)\s+)*'
        r'(?:class|interface|trait|enum)\s+[a-zA-Z_]\w*',
        re.MULTILINE,
    )

    INFINITE_LOOP_RE = re.compile(
        r'\bwhile\s*\(\s*(?:true|1|TRUE)\s*\)'
        r'|\bfor\s*\(\s*;;\s*\)',
        re.MULTILINE,
    )

    TERMINAL_RE = re.compile(
        r'^\s*(?:return|throw|break|continue|exit|die|header\s*\()',
        re.MULTILINE,
    )

    def _comment_prefix(self) -> str:
        return '//'
