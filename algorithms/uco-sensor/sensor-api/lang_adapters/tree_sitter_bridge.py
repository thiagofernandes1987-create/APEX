"""
UCO-Sensor — Tree-Sitter Bridge  (M9.0.1)
==========================================
A thin, dependency-optional bridge to tree-sitter with an automatic
regex fallback.  Lets multi-language SAST scanners run whether or not the
``tree-sitter`` wheels are installed in the host environment.

Design
------
* ``TreeSitterBridge.available()`` probes for the ``tree_sitter`` package
  AND a grammar for the requested language.  When both are present a real
  parse tree is exposed; otherwise the bridge degrades to line-oriented
  regex scanning (``iter_lines`` / ``search_lines``) — the same primitives
  the Tier-2 ``GenericRegexAdapter`` family already relies on.
* No import-time crash: ``import tree_sitter`` is attempted lazily and any
  failure is swallowed, so this module is always importable.

Why a bridge rather than a hard dependency?
-------------------------------------------
The sensor ships offline-first.  Tree-sitter grammars are compiled native
artifacts that may be absent on minimal CI images.  The regex fallback
keeps the JS/TS/Java/Go SAST rules functional everywhere; when the grammars
ARE installed, the same rule sets can be re-expressed as S-expression
queries for higher precision without changing the public API.

Public API
----------
    bridge = TreeSitterBridge("javascript")
    bridge.available()                      -> bool
    bridge.parse(source)                    -> Optional[tree]   (None on fallback)
    TreeSitterBridge.iter_lines(source)     -> Iterator[(lineno, text)]
    TreeSitterBridge.search_lines(pattern, source, flags=0)
        -> Iterator[(lineno, col, line_text, match)]
"""
from __future__ import annotations

import re
from typing import Any, Iterator, Optional, Tuple

# Map our language name → tree_sitter grammar module name.
#
# Most grammars expose a top-level ``language()`` callable returning the
# capsule.  A handful use a differently-named entry point (notably
# ``tree_sitter_php`` which ships ``language_php()`` because the wheel bundles
# both the full-PHP and PHP-only grammars).  ``_GRAMMAR_ENTRYPOINTS`` records
# those exceptions; everything else falls back to ``language``.
_GRAMMARS = {
    "javascript": "tree_sitter_javascript",
    "typescript": "tree_sitter_typescript",
    "java":       "tree_sitter_java",
    "go":         "tree_sitter_go",
    "python":     "tree_sitter_python",
    # M9.2 — AST coverage extended to the regex-Tier-2 languages whose
    # one-line security fixes the GenericRegexAdapter family under-detects.
    "c":          "tree_sitter_c",
    "cpp":        "tree_sitter_cpp",
    "php":        "tree_sitter_php",
    "ruby":       "tree_sitter_ruby",
    "csharp":     "tree_sitter_c_sharp",
    "rust":       "tree_sitter_rust",
}

# language name → entry-point function on the grammar module (default: language)
_GRAMMAR_ENTRYPOINTS = {
    "php": "language_php",
}


def _probe_tree_sitter() -> bool:
    """Return True iff the core ``tree_sitter`` package imports cleanly."""
    try:
        import tree_sitter  # noqa: F401
        return True
    except Exception:
        return False


class TreeSitterBridge:
    """
    Optional tree-sitter front-end with a guaranteed regex fallback.

    Parameters
    ----------
    language
        One of ``javascript`` / ``typescript`` / ``java`` / ``go``.
    """

    def __init__(self, language: str) -> None:
        self.language = language.lower()
        self._parser: Optional[Any] = None
        self._checked = False

    # ── availability ──────────────────────────────────────────────────────────

    def available(self) -> bool:
        """
        True when both ``tree_sitter`` and the language grammar are importable
        and a parser was successfully constructed.

        Caches the result after the first probe.
        """
        if self._checked:
            return self._parser is not None
        self._checked = True
        self._parser = self._try_build_parser()
        return self._parser is not None

    def _try_build_parser(self) -> Optional[Any]:
        if not _probe_tree_sitter():
            return None
        grammar_mod = _GRAMMARS.get(self.language)
        if grammar_mod is None:
            return None
        try:
            import importlib
            import tree_sitter
            mod = importlib.import_module(grammar_mod)
            # tree-sitter ≥0.22 API: Language(capsule), Parser(language).
            # Resolve the grammar entry point, honouring per-grammar overrides
            # (e.g. tree_sitter_php → language_php()).
            entry = _GRAMMAR_ENTRYPOINTS.get(self.language, "language")
            if hasattr(mod, entry):
                lang_capsule = getattr(mod, entry)()
            elif hasattr(mod, "language"):
                lang_capsule = mod.language()
            else:
                lang_capsule = mod.LANGUAGE
            language = tree_sitter.Language(lang_capsule)
            parser = tree_sitter.Parser(language)
            return parser
        except Exception:
            return None

    # ── parse ─────────────────────────────────────────────────────────────────

    def parse(self, source: str) -> Optional[Any]:
        """
        Return a tree-sitter parse tree, or ``None`` when running in
        regex-fallback mode (caller must then use ``search_lines``).
        """
        if not self.available():
            return None
        try:
            return self._parser.parse(bytes(source, "utf-8"))
        except Exception:
            return None

    # ── regex fallback primitives (static — always available) ─────────────────

    @staticmethod
    def iter_lines(source: str) -> Iterator[Tuple[int, str]]:
        """Yield ``(1-based-lineno, line_text)`` for every line."""
        for i, line in enumerate(source.splitlines(), start=1):
            yield i, line

    @staticmethod
    def search_lines(
        pattern: "re.Pattern[str] | str",
        source: str,
        flags: int = 0,
    ) -> Iterator[Tuple[int, int, str, "re.Match[str]"]]:
        """
        Yield ``(lineno, col, line_text, match)`` for each *first* match of
        *pattern* on each line.  Compiled patterns are used as-is; string
        patterns are compiled with *flags*.

        Comment-only lines are still scanned — callers that need to skip
        comments should pre-filter with their language's comment syntax.
        """
        rx = pattern if isinstance(pattern, re.Pattern) else re.compile(pattern, flags)
        for lineno, line in TreeSitterBridge.iter_lines(source):
            m = rx.search(line)
            if m:
                yield lineno, m.start(), line, m
